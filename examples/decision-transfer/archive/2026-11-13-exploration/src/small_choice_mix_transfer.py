"""Transfer fixed Qwen blending to other product surveys with small pilots."""
import json

import numpy as np
from scipy.special import softmax

from adaptive_pilot import spanish
from cheese_pilot import evaluation_inputs, load_deck
from optout_pilot import REPEATS, SEED, fit_products, load, split_cards
from paid_choice_model_mix import WEIGHT
import shortbread_pilot

BUDGETS = (5, 10, 25)


def evaluate(p, y, keys, features, *, price_uniform_control=False):
    bought = y[..., 0] == 0
    mass = p[..., 1:].sum(axis=-1, keepdims=True)
    uniform = np.full_like(p[..., 1:], 1 / (p.shape[-1] - 1))
    qwen = np.divide(p[..., 1:], mass, out=uniform.copy(), where=mass > 0)
    rng = np.random.default_rng(SEED)
    scores = {n: [] for n in BUDGETS}
    for _ in range(REPEATS):
        available = split_cards(keys, rng)
        order = rng.permutation(len(y))
        test = ~available & bought
        test[order[:max(BUDGETS)]] = False
        truth = y[test][:, 1:]
        for n, rows in scores.items():
            train = available.copy()
            train[order[n:]] = False
            stats = softmax(features[test] @ fit_products(
                features[train], y[train], nonpositive_price=True), axis=-1)
            prices = features[..., -1:]
            price_only = softmax(prices[test] @ fit_products(
                prices[train], y[train], nonpositive_price=True), axis=-1)
            methods = {
                'stats': stats, 'price_only': price_only, 'qwen': qwen[test],
                'mix': (1 - WEIGHT) * stats + WEIGHT * qwen[test],
                'uniform_mix': (1 - WEIGHT) * stats + WEIGHT * uniform[test],
                'price_mix': (1 - WEIGHT) * price_only + WEIGHT * qwen[test],
            }
            if price_uniform_control:
                methods['price_uniform_mix'] = (1 - WEIGHT) * price_only + WEIGHT * uniform[test]
            rows.append({k: float(np.square(pred - truth).sum(axis=-1).mean())
                         for k, pred in methods.items()})
    result = {}
    for n, rows in scores.items():
        errors = {k: np.array([row[k] for row in rows]) for k in rows[0]}
        comparisons = {}
        for base in ('stats', 'price_only', 'uniform_mix'):
            delta = errors[base] - errors['mix']
            comparisons[base] = {'gain': float(delta.mean()), 'win_rate': float((delta > 1e-10).mean()),
                                 'p05_p95': np.quantile(delta, [.05, .95]).tolist()}
        result[n] = {'brier': {k: float(v.mean()) for k, v in errors.items()}, 'mix_over': comparisons}
        delta = errors['price_only'] - errors['price_mix']
        result[n]['price_mix_over_price_only'] = {
            'gain': float(delta.mean()), 'win_rate': float((delta > 1e-10).mean()),
            'p05_p95': np.quantile(delta, [.05, .95]).tolist(),
        }
        if price_uniform_control:
            for base in ('stats', 'price_uniform_mix', 'mix'):
                delta = errors[base] - errors['price_mix']
                result[n][f'price_mix_over_{base}'] = {
                    'gain': float(delta.mean()), 'win_rate': float((delta > 1e-10).mean()),
                    'p05_p95': np.quantile(delta, [.05, .95]).tolist(),
                }
    return {'people': len(y), 'cards': len(np.unique(keys)),
            'purchases_with_zero_qwen_mass': int((bought & (mass[..., 0] == 0)).sum()), 'budgets': result}


if __name__ == '__main__':
    inputs = load()
    inputs.update(spain=spanish(), italy=evaluation_inputs(*load_deck())[0],
                  scotland=shortbread_pilot.evaluation_inputs(*shortbread_pilot.load_deck())[0])
    results = {name: evaluate(p, y, keys, x) for name, (p, y, keys, _, x) in inputs.items()}
    print(json.dumps({'seed': SEED, 'replays': REPEATS, 'qwen_weight': WEIGHT,
                      'new_calls': 0, 'studies': results}, indent=2))
