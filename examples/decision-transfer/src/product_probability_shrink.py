"""Test fixed probability shrinkage and out-of-family shrinkage on Qwen choice cards."""
from collections import defaultdict
import json

import numpy as np

import adaptive_pilot
import beef_payment_screen as beef
import cheese_pilot
import dryer_refusal
import optout_pilot
import shortbread_pilot
from order_screen import SEED

FIXED = .25
FAMILIES = {'beer': 'beer', 'german': 'german', 'spain': 'radiant',
            'italy': 'radiant', 'scotland': 'radiant', 'USA': 'dryer', 'CAN': 'dryer',
            'beef_incentivized': 'beef', 'beef_hypothetical': 'beef'}


def load():
    datasets = {name: (p, y, keys) for name, (p, y, keys, _, _) in optout_pilot.load().items()}
    for name, (p, y, keys, _, _) in (
        ('spain', adaptive_pilot.spanish()),
        ('italy', cheese_pilot.evaluation_inputs(*cheese_pilot.load_deck())[0]),
        ('scotland', shortbread_pilot.evaluation_inputs(*shortbread_pilot.load_deck())[0]),
    ):
        datasets[name] = p, y, keys
    jobs, _, cohorts = dryer_refusal.deck()
    estimates, identity = dryer_refusal.predictions(jobs, dryer_refusal.RUN)
    if len(identity) != 1:
        raise ValueError('Inconsistent dryer model identity')
    for name, cohort in cohorts.items():
        rows = list(cohort.values())
        p, y = dryer_refusal.outcome(estimates, rows)
        datasets[name] = p, y, np.asarray([list(row) for row in rows])
    beef_jobs = beef.freeze()
    estimates, _, errors = beef.load_predictions(beef_jobs)
    if errors:
        raise ValueError('Missing beef predictions')
    cohorts, _ = beef.load_responses(beef.SOURCE)
    for group, rows in cohorts.items():
        ordered = ['6', '1', '2', '3', '4', '5']
        target = np.eye(6)[[[ordered.index(str(option)) for option in row] for row in rows]]
        keys = [f'card{i:02}' for i in range(1, len(beef.PRICES) + 1)]
        probability = np.array([estimates['direct', group, key] for key in keys])
        probability = np.broadcast_to(np.roll(probability, 1, axis=-1), target.shape)
        datasets['beef_' + group] = probability, target, np.broadcast_to(keys, target.shape[:2])
    for name, (p, y, keys) in datasets.items():
        if p.shape != y.shape or keys.shape != y.shape[:2] or not np.allclose(p.sum(axis=-1), 1):
            raise ValueError(f'Invalid mapped predictions: {name}')
    return datasets


def direction(p):
    """Move conditional product shares toward equal odds, leaving no-buy unchanged."""
    average = p[..., 1:].mean(axis=-1, keepdims=True)
    return np.concatenate((np.zeros_like(p[..., :1]), average - p[..., 1:]), axis=-1)


def fit_strength(datasets, held_family):
    families = defaultdict(list)
    for name, (p, y, _) in datasets.items():
        if FAMILIES[name] in (held_family, 'beef'):
            continue
        uniform = 1 / p.shape[-1] - p
        numerator = np.mean(np.sum((y - p) * uniform, axis=-1))
        denominator = np.mean(np.sum(uniform ** 2, axis=-1))
        families[FAMILIES[name]].append((numerator, denominator))
    numerator, denominator = np.mean([np.mean(rows, axis=0) for rows in families.values()], axis=0)
    return float(np.clip(numerator / denominator, 0, 1)) if denominator else 0.


def score(p, y, keys, transferred, *, cell_keys=None):
    n_options = p.shape[-1]
    methods = {
        'raw': p,
        'uniform': np.full_like(p, 1 / n_options),
        'fixed_all_options': (1 - FIXED) * p + FIXED / n_options,
        'fixed_products_only': p + FIXED * direction(p),
        'source_fitted': (1 - transferred) * p + transferred / n_options,
    }
    # Preserve the original card clusters even where the beer instructions differ.
    unique, card_index = np.unique(keys, return_inverse=True)
    card_index = card_index.ravel()
    counts = np.bincount(card_index)
    if cell_keys is None:
        cell_keys = keys
    _, cell_index = np.unique(cell_keys, return_inverse=True)
    cell_index = cell_index.ravel()
    n_cells = np.bincount(cell_index)
    rng = np.random.default_rng(SEED)
    people_draws = rng.integers(len(y), size=(2000, len(y)))
    card_draws = rng.integers(len(unique), size=(2000, len(unique)))
    raw_loss = np.sum((p - y) ** 2, axis=-1)
    result = {}
    for name, q in methods.items():
        loss = np.sum((q - y) ** 2, axis=-1)
        delta = raw_loss - loss
        gains = np.bincount(card_index, weights=delta.ravel())
        per_card = gains[card_draws].sum(axis=1) / counts[card_draws].sum(axis=1)
        per_person = delta.mean(axis=1)[people_draws].mean(axis=1)
        mean = q.mean(axis=(0, 1))
        observed = y.mean(axis=(0, 1))
        cell_errors = np.array([np.bincount(cell_index, weights=diff.ravel())
                                for diff in np.moveaxis(q - y, -1, 0)])
        result[name] = {
            'card_context_tv': float(.5 * np.abs(cell_errors).sum() / n_cells.sum()),
            'brier': float(loss.mean()), 'brier_improvement': float(delta.mean()),
            'overall_tv': float(.5 * np.abs(mean - observed).sum()),
            'no_buy': float(mean[0]),
            'person_interval_95': np.quantile(per_person, [.025, .975]).tolist(),
            'card_interval_95': np.quantile(per_card, [.025, .975]).tolist(),
        }
    return {'people': len(y), 'card_clusters': len(unique), 'human_no_buy': float(y[..., 0].mean()),
            'transferred_strength': transferred, 'methods': result}


if __name__ == '__main__':
    data = load()
    beer_deck, beer_people = optout_pilot.transfer.beer_deck()
    cells = np.asarray([[list(beer_deck).index(key) for key in row] for row in beer_people])
    print(json.dumps({'new_model_calls': 0, 'fixed_strength': FIXED, 'families': FAMILIES,
                      'studies': {name: score(*inputs, fit_strength(data, FAMILIES[name]),
                                              cell_keys=cells if name == 'beer' else None)
                                  for name, inputs in data.items()}}, indent=2))
