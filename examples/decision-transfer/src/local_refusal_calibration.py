"""Measure whether model differences add value after fixing the local refusal rate."""
import json
import re

import numpy as np
from scipy.optimize import brentq
from scipy.special import expit, logit

import dryer_refusal as dryer
import shortbread_pilot
import taiwan_pepper as pepper
from adaptive_pilot import spanish
from cheese_pilot import evaluation_inputs, load_deck
from optout_pilot import REPEATS, SEED, load, split_cards
from optout_transfer import outcome, predictions
from price_study_transfer import PRICE_UNITS

BUDGETS = (5, 10, 25)


def calibrated(signal, train, test, rate):
    offset = brentq(lambda b: expit(signal[train] + b).mean() - rate, -40, 40)
    return expit(signal[test] + offset)


def evaluate(p, y, keys, lowest_price):
    model = logit(np.clip(p, 1e-5, 1 - 1e-5))
    log_price = np.log(lowest_price)
    unique = np.unique(log_price)
    # The price comparator also uses a fixed slope and the same local labels.
    price_signal = .5 * (log_price - unique.mean()) / max(unique.std(), 1e-6)
    rng = np.random.default_rng(SEED)
    results = {size: [] for size in BUDGETS}
    for _ in range(REPEATS):
        available = split_cards(keys, rng)
        order = rng.permutation(len(y))
        test = ~available
        test[order[:max(BUDGETS)]] = False
        truth = y[test]
        for size, rows in results.items():
            train = available.copy()
            train[order[size:]] = False
            rate = (y[train].sum() + .5) / (train.sum() + 1)
            estimates = {
                'qwen_raw': p[test], 'local_rate': rate,
                'local_plus_price': calibrated(price_signal, train, test, rate),
                'local_plus_half_qwen': calibrated(.5 * model, train, test, rate),
                'local_plus_full_qwen': calibrated(model, train, test, rate),
            }
            rows.append({key: float(np.square(est - truth).mean()) for key, est in estimates.items()})
    summary = {}
    for size, rows in results.items():
        scores = {k: np.array([r[k] for r in rows]) for k in rows[0]}
        output = {'brier': {k: float(v.mean()) for k, v in scores.items()}, 'paired': {}}
        for base in ('local_rate', 'local_plus_price'):
            for candidate in ('local_plus_half_qwen', 'local_plus_full_qwen'):
                delta = scores[base] - scores[candidate]
                output['paired'][f'{candidate}_over_{base}'] = {
                    'gain': float(delta.mean()), 'win_rate': float(np.mean(delta > 1e-10)),
                    'p05_p95': np.quantile(delta, [.05, .95]).tolist(),
                }
        summary[size] = output
    return summary


def load_inputs():
    jobs = pepper.deck()
    people = pepper.observed_control(jobs)
    predicted, identities = predictions(jobs, pepper.RUN)
    if len(identities) != 1:
        raise ValueError('Mixed sweet pepper model identities')
    p, y = outcome(predicted, people)
    keys = np.asarray([list(person) for person in people])
    card_min = {key: min(int(re.search(r'NT (\d+)', label)[1]) for label in
                         list(job['questions'][0]['options'].values())[:3]) for key, job in jobs.items()}
    lowest = np.asarray([[card_min[key] for key in row] for row in keys])
    inputs = {'taiwan': (p[..., 3], y[..., 3], keys, lowest)}
    foods = load()
    foods.update(spain=spanish(), italy=evaluation_inputs(*load_deck())[0],
                 scotland=shortbread_pilot.evaluation_inputs(*shortbread_pilot.load_deck())[0])
    for name in ('beer', 'spain', 'italy', 'scotland'):
        p, y, keys, _, x = foods[name]
        offset, step = PRICE_UNITS[name]
        inputs[name] = (p[..., 0], y[..., 0], keys, (offset + step * x[..., -1]).min(axis=-1))
    jobs, features, cohorts = dryer.deck()
    predicted, identities = predictions(jobs, dryer.RUN)
    if len(identities) != 1:
        raise ValueError('Mixed dryer model identities')
    for name, cohort in cohorts.items():
        people = [dict(sorted(row.items())) for row in cohort.values()]
        p, y = outcome(predicted, people)
        keys = np.asarray([list(person) for person in people])
        lowest = np.asarray([[min(900 + 200 * x[-1] for x in features[card])
                              for card in row] for row in keys])
        inputs[name] = (p[..., 0], y[..., 0], keys, lowest)
    return inputs


def main():
    inputs = load_inputs()
    out = {name: {'people': len(y), 'cards': len(np.unique(keys)),
                  'budgets': evaluate(p, y, keys, lowest)} for name, (p, y, keys, lowest) in inputs.items()}
    print(json.dumps({'seed': SEED, 'splits': REPEATS, 'new_calls': 0, 'studies': out}, indent=2))


if __name__ == '__main__':
    main()
