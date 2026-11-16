"""Test whether local pilot answers can safely change the fixed price rule."""

import json

import numpy as np
from scipy.optimize import brentq, minimize
from scipy.special import expit, logit

from local_refusal_calibration import BUDGETS, REPEATS, SEED, calibrated, load_inputs, split_cards

PENALTY = .05


def fit_slopes(x, y, center, rate):
    target = (len(y) * y + .5) / (len(y) + 1)

    def objective(beta):
        signal = x @ beta
        offset = brentq(lambda b: expit(signal + b).mean() - rate, -100, 100)
        logits = signal + offset
        delta = beta - center
        loss = np.mean(np.logaddexp(0., logits) - target * logits) + PENALTY * (delta @ delta)
        grad = x.T @ (expit(logits) - target) / len(y) + 2 * PENALTY * delta
        return loss, grad

    fit = minimize(objective, center, jac=True, method='L-BFGS-B', bounds=[(0., 3.)] * len(center))
    if not fit.success:
        raise RuntimeError(fit.message)
    return fit.x


def standardize(x):
    levels = np.unique(x)
    return (x - levels.mean()) / max(levels.std(), 1e-6)


def evaluate(p, y, keys, lowest):
    price = standardize(np.log(lowest))
    model = standardize(logit(np.clip(p, 1e-5, 1 - 1e-5)))
    features = np.stack((price, model), axis=-1)
    rng = np.random.default_rng(SEED)
    losses = {size: [] for size in BUDGETS}
    for _ in range(REPEATS):
        available = split_cards(keys, rng)
        order = rng.permutation(len(y))
        test = ~available
        test[order[:max(BUDGETS)]] = False
        for size, rows in losses.items():
            train = available.copy()
            train[order[size:]] = False
            actual = y[train]
            rate = (actual.sum() + .5) / (len(actual) + 1)
            methods = {
                'fixed_price': .5 * price,
                'learn_price_from_zero': price * fit_slopes(price[train, None], actual, np.array([0.]), rate)[0],
                'learn_price_from_fixed': price * fit_slopes(price[train, None], actual, np.array([.5]), rate)[0],
                'learn_price_and_qwen': features @ fit_slopes(features[train], actual, np.array([.5, 0.]), rate),
            }
            rows.append({'local_rate': float(np.mean((rate - y[test]) ** 2)),
                         **{k: float(np.mean((calibrated(s, train, test, rate) - y[test]) ** 2))
                            for k, s in methods.items()}})
    result = {}
    for size, rows in losses.items():
        scores = {key: np.array([row[key] for row in rows]) for key in rows[0]}
        comparisons = {}
        for base, candidate in [('fixed_price', 'learn_price_from_fixed'),
                                ('local_rate', 'learn_price_from_zero'),
                                ('learn_price_from_fixed', 'learn_price_and_qwen')]:
            gain = scores[base] - scores[candidate]
            comparisons[f'{candidate}_over_{base}'] = {
                'mean_gain': float(gain.mean()), 'win_rate': float(np.mean(gain > 1e-10)),
                'p05_p95': np.quantile(gain, [.05, .95]).tolist(),
            }
        result[size] = {'brier': {key: float(value.mean()) for key, value in scores.items()},
                        'paired': comparisons}
    return result


if __name__ == '__main__':
    results = {name: evaluate(*inputs) for name, inputs in load_inputs().items()}
    print(json.dumps({'seed': SEED, 'splits': REPEATS, 'new_calls': 0, 'ridge_penalty': PENALTY,
                      'studies': results}, indent=2))
