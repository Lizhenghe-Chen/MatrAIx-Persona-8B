"""Test pilot-only decisions to use plain statistics, neutral smoothing or Qwen."""
import json

import numpy as np
from scipy.special import softmax

from adaptive_pilot import spanish
import cheese_pilot
import optout_pilot as pilot
from paid_choice_model_mix import WEIGHT
from pilot_model_selection import card_folds
import shortbread_pilot

BUDGETS = (5, 10, 25)
METHODS = ('stats', 'uniform_mix', 'qwen_mix')


def forecasts(x, y, target, qwen):
    beta = pilot.fit_products(x, y, nonpositive_price=True)
    p = softmax(target @ beta, axis=1)
    rate = (y[:, 0].sum() + .5) / (len(y) + 1)
    blends = np.array([p, (1 - WEIGHT) * p + WEIGHT / p.shape[1],
                       (1 - WEIGHT) * p + WEIGHT * qwen])
    return np.concatenate((np.full((*blends.shape[:2], 1), rate), (1 - rate) * blends), axis=2)


def choose(x, y, keys, qwen, mask):
    people = np.arange(len(y))[:, None] % 5
    cards = card_folds(keys, mask)
    losses = np.full((*mask.shape, len(METHODS)), np.nan)
    for person_fold in range(5):
        for card_fold in range(3):
            valid = mask & (people == person_fold) & (cards == card_fold)
            if not valid.any():
                continue
            fit = mask & (people != person_fold) & (cards != card_fold)
            if not fit.any():
                raise ValueError('Empty pilot training fold')
            p = forecasts(x[fit], y[fit], x[valid], qwen[valid])
            losses[valid] = np.square(p - y[valid]).sum(axis=2).T
    if not np.isfinite(losses[mask]).all():
        raise ValueError('Incomplete cross-fitting')
    by_person = np.nansum(losses, axis=1) / mask.sum(axis=1, keepdims=True)
    mean = by_person.mean(axis=0)
    stat_only = int(np.argmin(mean[:2]))
    # The standard error is a stability hurdle, not a confidence interval:
    # predictions for different people share inner training records.
    gain = by_person[:, stat_only] - by_person[:, 2]
    hurdle = gain.std(ddof=1) / np.sqrt(len(gain))
    guarded = 2 if gain.mean() > hurdle else stat_only
    return stat_only, int(np.argmin(mean)), guarded


def evaluate(p, y, keys, _, x):
    mass = p[..., 1:].sum(axis=-1, keepdims=True)
    qwen = np.divide(p[..., 1:], mass, where=mass > 0,
                     out=np.full_like(p[..., 1:], 1 / (p.shape[-1] - 1)))
    rng = np.random.default_rng(pilot.SEED)
    rows = {n: [] for n in BUDGETS}
    for _ in range(pilot.REPEATS):
        available = pilot.split_cards(keys, rng)
        order = rng.permutation(len(y))
        test = ~available
        test[order[:max(BUDGETS)]] = False
        truth = y[test]
        for n in BUDGETS:
            subset = order[:n]
            keep = available[subset]
            chosen = choose(x[subset], y[subset], keys[subset], qwen[subset], keep)
            pred = forecasts(x[subset][keep], y[subset][keep], x[test], qwen[test])
            errors = np.square(pred - truth).sum(axis=2).mean(axis=1)
            rows[n].append((errors, chosen))
    results = {}
    rules = ('choose_without_qwen', 'choose_any', 'guard_qwen')
    for n, runs in rows.items():
        error, selections = map(np.asarray, zip(*runs, strict=True))
        run_index = np.arange(len(runs))
        selected = {rule: error[run_index, selections[:, i]] for i, rule in enumerate(rules)}
        references = dict(zip(METHODS, error.T, strict=True))
        gains = {}
        for rule in ('choose_any', 'guard_qwen'):
            gains[rule] = {}
            for name, base in {**references, 'choose_without_qwen': selected[rules[0]]}.items():
                delta = base - selected[rule]
                gains[rule][name] = {'mean': float(delta.mean()),
                                     'wins': int((delta > 1e-10).sum()),
                                     'ties': int((np.abs(delta) <= 1e-10).sum()),
                                     'p05_p95': np.quantile(delta, [.05, .95]).tolist()}
        results[n] = {'brier': {k: float(v.mean()) for k, v in {**references, **selected}.items()},
                      'selected': {rule: dict(zip(METHODS, np.bincount(selections[:, i], minlength=3).tolist(), strict=True))
                                   for i, rule in enumerate(rules)},
                      'gains': gains}
    return {'people': len(y), 'pilot_cards_per_person': keys.shape[1] // 2, 'budgets': results}


def main():
    italian = cheese_pilot.evaluation_inputs(*cheese_pilot.load_deck())[0]
    scotland = shortbread_pilot.evaluation_inputs(*shortbread_pilot.load_deck())[0]
    studies = {**pilot.load(), 'spain': spanish(), 'italy': italian, 'scotland': scotland}
    print(json.dumps({'seed': pilot.SEED, 'replays': pilot.REPEATS, 'model_weight': WEIGHT,
                      'new_calls': 0, 'studies': {name: evaluate(*data) for name, data in studies.items()}},
                     indent=2))


if __name__ == '__main__':
    main()
