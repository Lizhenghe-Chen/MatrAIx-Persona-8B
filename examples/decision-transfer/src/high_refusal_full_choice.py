"""Replay full-choice scoring across surveys with different opt-out rates."""
import json

import numpy as np
from scipy.special import softmax

from optout_pilot import REPEATS, SEED, fit_products, load, split_cards
from small_choice_mix_transfer import BUDGETS, WEIGHT
import shortbread_pilot


def evaluate(p, y, keys, features):
    rng = np.random.default_rng(SEED)
    products = p[..., 1:]
    mass = products.sum(axis=-1, keepdims=True)
    uniform = 1 / products.shape[-1]
    conditional = np.divide(products, mass, out=np.full_like(products, uniform), where=mass > 0)
    prices = features[..., -1:]
    results = {n: [] for n in BUDGETS}
    observed_refusal = []
    for _ in range(REPEATS):
        available = split_cards(keys, rng)
        order = rng.permutation(len(y))
        test = ~available
        test[order[:max(BUDGETS)]] = False
        truth = y[test]
        observed_refusal.append(float(truth[:, 0].mean()))
        qwen = conditional[test]
        for n, rows in results.items():
            train = available.copy()
            train[order[n:]] = False
            answers = y[train]
            refusal = (answers[:, 0].sum() + .5) / (len(answers) + 1)
            full = softmax(features[test] @ fit_products(
                features[train], answers, nonpositive_price=True), axis=-1)
            price = softmax(prices[test] @ fit_products(
                prices[train], answers, nonpositive_price=True), axis=-1)
            product_forecasts = {
                'local_price': price, 'local_full': full,
                'price_uniform': (1 - WEIGHT) * price + WEIGHT * uniform,
                'price_qwen': (1 - WEIGHT) * price + WEIGHT * qwen,
                'full_qwen': (1 - WEIGHT) * full + WEIGHT * qwen,
                'full_uniform': (1 - WEIGHT) * full + WEIGHT * uniform,
            }
            forecasts = {name: np.column_stack((np.full(len(truth), refusal), (1 - refusal) * values))
                         for name, values in product_forecasts.items()}
            forecasts['raw_qwen'] = p[test]
            model_refusal = p[test][:, :1]
            forecasts['price_qwen_model_refusal'] = np.column_stack(
                (model_refusal, (1 - model_refusal) * product_forecasts['price_qwen']))
            rows.append({name: {
                'full_brier': float(np.square(pred - truth).sum(axis=-1).mean()),
                'refusal_brier': float(np.square(pred[:, 0] - truth[:, 0]).mean()),
                'refusal_rate': float(pred[:, 0].mean()),
            } for name, pred in forecasts.items()})
    summaries = {}
    for n, rows in results.items():
        metrics = {name: {metric: np.array([row[name][metric] for row in rows])
                          for metric in values} for name, values in rows[0].items()}
        gains = {}
        for candidate in ('price_qwen', 'full_qwen', 'price_qwen_model_refusal'):
            for base in ('local_price', 'local_full', 'price_uniform', 'price_qwen', 'full_uniform'):
                if base == candidate:
                    continue
                delta = metrics[base]['full_brier'] - metrics[candidate]['full_brier']
                gains[f'{candidate}_over_{base}'] = {
                    'mean': float(delta.mean()), 'wins': int((delta > 1e-10).sum()),
                    'p05_p95': np.quantile(delta, [.05, .95]).tolist(),
                }
        summaries[n] = {'metrics': {name: {metric: float(vals.mean()) for metric, vals in values.items()}
                                     for name, values in metrics.items()}, 'gains': gains}
    return {'people': len(y), 'cards': len(np.unique(keys)), 'observed_refusal': float(y[..., 0].mean()),
            'mean_test_refusal': float(np.mean(observed_refusal)),
            'budgets': summaries}


if __name__ == '__main__':
    studies = load()
    studies['scotland'] = shortbread_pilot.evaluation_inputs(*shortbread_pilot.load_deck())[0]
    print(json.dumps({'seed': SEED, 'replays': REPEATS, 'new_calls': 0, 'qwen_weight': WEIGHT,
                      'studies': {name: evaluate(p, y, keys, features)
                                  for name, (p, y, keys, _, features) in studies.items()}}, indent=2))
