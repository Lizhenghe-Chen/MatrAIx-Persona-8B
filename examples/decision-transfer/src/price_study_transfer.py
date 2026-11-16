"""Replay a leave-one-study-out prior for price sensitivity across retail studies."""
import json

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp, softmax

from adaptive_pilot import spanish
from cheese_pilot import evaluation_inputs, load_deck
import optout_pilot as pilot
import shortbread_pilot

# Each adapter's final column is (original price - offset) / step.
PRICE_UNITS = {'beer': (9, 1.5), 'german': (.45, .15), 'spain': (6.5, 2),
               'italy': (21, 3), 'scotland': (6, 2.5)}
PRIOR_STRENGTH = .25


def log_prices(features, study):
    offset, step = PRICE_UNITS[study]
    prices = features[..., -1] * step + offset
    if not np.isfinite(prices).all() or np.any(prices <= 0):
        raise ValueError(f'Invalid reconstructed price: {study}')
    # Units cancel within a card; scaling by five puts 20% log-price changes near one.
    return 5 * (np.log(prices) - np.log(prices).mean(axis=-1, keepdims=True))


def fit(features, targets, prior=None):
    bought = targets[:, 0] == 0
    x, y = features[bought], targets[bought, 1:]
    center = np.zeros(features.shape[-1])
    if prior is not None:
        center[-1] = prior
    if not len(y):
        return center
    strength = .01 + (PRIOR_STRENGTH if prior is not None else 0)

    def objective(beta):
        u = x @ beta
        mean_nll = np.mean(logsumexp(u, axis=1) - np.sum(u * y, axis=1))
        gradient = np.einsum('ij,ijk->k', softmax(u, axis=1) - y, x) / len(y)
        diff = beta - center
        penalty = .01 * (diff[:-1] @ diff[:-1]) + strength * diff[-1] ** 2
        gradient += 2 * diff * np.r_[np.full(len(diff) - 1, .01), strength]
        return mean_nll + penalty, gradient

    fit_result = minimize(objective, center, jac=True, method='L-BFGS-B',
                          bounds=[(None, None)] * (len(center) - 1) + [(None, 0)])
    if not fit_result.success:
        raise RuntimeError(fit_result.message)
    return fit_result.x


def evaluate(data, prior):
    p, y, keys, _, x = data
    rng = np.random.default_rng(pilot.SEED)
    out = {n: [] for n in pilot.SIZES}
    for _ in range(pilot.REPEATS):
        available = pilot.split_cards(keys, rng)
        # Use one copy of each distinct price profile and Qwen response.
        # Exclude cards where Qwen gives no probability mass to any product.
        x_price = x[available][..., -1]
        p_products = p[available][:, 1:]
        rows = np.unique(np.column_stack((x_price, p_products)), axis=0)
        n_products = x.shape[-2]
        raw = rows[:, n_products:]
        valid = raw.sum(axis=1) > 0
        if not valid.any():
            raise ValueError('No conditional Qwen predictions on available cards')
        conditional = raw[valid] / raw[valid].sum(axis=1, keepdims=True)
        qwen_price = fit(rows[valid, :n_products, None],
                         np.column_stack((np.zeros(valid.sum()), conditional)))[-1]
        order = rng.permutation(len(y))
        test = order[max(pilot.SIZES):]
        held = ~available[test]
        ty, tx, qwen = y[test][held], x[test][held], p[test][held]
        bought = ty[:, 0] == 0
        for n in pilot.SIZES:
            train = order[:n]
            mask = available[train]
            py, px = y[train][mask], x[train][mask]
            rate = np.full(len(ty), (py[:, 0].sum() + .5) / (len(py) + 1))
            candidates = {
                'local': softmax(tx @ fit(px, py), axis=1),
                'zero_center': softmax(tx @ fit(px, py, prior=0.), axis=1),
                'source_center': softmax(tx @ fit(px, py, prior=prior), axis=1),
                'source_price_only': softmax(tx[..., -1] * prior, axis=1),
                'qwen_price_only': softmax(tx[..., -1] * qwen_price, axis=1),
                'local_price_only': softmax(tx[..., -1] * fit(px[..., -1:], py)[-1], axis=1),
                'uniform_products': np.full(tx.shape[:2], 1 / tx.shape[1]),
            }
            scores = {name: pilot.losses(rate, conditional, ty)
                      for name, conditional in candidates.items()}
            scores['qwen'] = float(np.mean(np.sum((qwen - ty) ** 2, axis=1)))
            scores['purchase_conditional'] = {
                name: float(np.mean(np.sum((conditional[bought] - ty[bought, 1:]) ** 2, axis=1)))
                for name, conditional in candidates.items()
            }
            out[n].append(scores)
    return {n: summarize(rows) for n, rows in out.items()}


def summarize(rows):
    scores = {key: float(np.mean([row[key] for row in rows]))
              for key in rows[0] if key != 'purchase_conditional'}
    scores['purchase_conditional'] = {key: float(np.mean([row['purchase_conditional'][key] for row in rows]))
                                      for key in rows[0]['purchase_conditional']}
    for key in ('local', 'zero_center', 'uniform_products'):
        delta = np.asarray([row[key] - row['source_center'] for row in rows])
        scores[f'source_center_over_{key}'] = {
            'win_rate': float(np.mean(delta > 0)),
            'p05_p95': np.quantile(delta, [.05, .95]).tolist(),
        }
    for key in ('local_price_only', 'qwen_price_only', 'uniform_products'):
        delta = np.asarray([row[key] - row['source_price_only'] for row in rows])
        scores[f'source_price_only_over_{key}'] = {
            'win_rate': float(np.mean(delta > 0)),
            'p05_p95': np.quantile(delta, [.05, .95]).tolist(),
        }
    return scores


def main():
    italian, _, _ = evaluation_inputs(*load_deck())
    scottish, _, _ = shortbread_pilot.evaluation_inputs(*shortbread_pilot.load_deck())
    inputs = {**pilot.load(), 'spain': spanish(), 'italy': italian, 'scotland': scottish}
    data, slopes = {}, {}
    for study, (p, y, keys, extra, raw) in inputs.items():
        x = raw.copy()
        x[..., -1] = log_prices(x, study)
        data[study] = p, y, keys, extra, x
        # German cards price only the packaging. Keep them as a distinct stress test.
        if study != 'german':
            slopes[study] = float(fit(x.reshape(-1, x.shape[-2], x.shape[-1]),
                                      y.reshape(-1, y.shape[-1]))[-1])
    results = {}
    for study, inputs in data.items():
        sources = {name: beta for name, beta in slopes.items() if name != study}
        prior = float(np.mean(list(sources.values())))
        results[study] = {'people': len(inputs[1]), 'sources': sources, 'price_prior': prior,
                          'budgets': evaluate(inputs, prior)}
    print(json.dumps({'seed': pilot.SEED, 'splits': pilot.REPEATS,
                      'new_calls': 0, 'extra_price_penalty': PRIOR_STRENGTH,
                      'studies': results}, indent=2))


if __name__ == '__main__':
    main()
