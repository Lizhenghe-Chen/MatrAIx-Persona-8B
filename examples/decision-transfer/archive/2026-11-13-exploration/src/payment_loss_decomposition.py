"""Separate the errors in purchase incidence and product choice under payment."""
import json
from pathlib import Path

import numpy as np
from scipy.special import softmax

from beef_admission import PRICES, SOURCE, SOURCE_SHA, load_responses
from choice_predictor import fit_products
from order_screen import SEED

RESULT = Path(__file__).resolve().parents[1] / 'data/beef-payment-v1.json'
BUDGETS = (5, 10, 25)
REPLAYS = 100
FLOOR = 1e-6


def losses(y, refusal, products):
    """Categorical log loss is the sum of the binary and purchase contributions."""
    refusal = np.clip(refusal, FLOOR, 1 - FLOOR)
    products = np.maximum(products, FLOOR)
    products = products / products.sum(axis=-1, keepdims=True)
    bought = y != 5
    buy_loss = -np.log(np.where(bought, 1 - refusal, refusal))
    product_loss = -(np.eye(6)[y][..., :5] * np.log(products)).sum(axis=-1)
    return np.array([buy_loss.mean(), product_loss.mean(), (buy_loss + product_loss).mean()])


def fit_choice(x, y, target):
    features = np.broadcast_to(x, (*y.shape, *x.shape[1:]))
    truth = np.roll(np.eye(6)[y], 1, axis=-1)
    beta = fit_products(features.reshape(-1, *x.shape[1:]), truth.reshape(-1, 6), nonpositive_price=True)
    return softmax(target @ beta, axis=-1)


def main():
    prior = json.loads(RESULT.read_text())
    if prior['workbook_sha256'] != SOURCE_SHA:
        raise ValueError('Historical output uses different responses')
    people, _ = load_responses(SOURCE)
    target, source = (np.asarray(people[g]) - 1 for g in ('incentivized', 'hypothetical'))
    raw = np.array([card['predictions']['direct']['incentivized'] for card in prior['cards']])
    prices = np.log(PRICES)
    features = np.concatenate((np.broadcast_to(np.eye(5), (len(prices), 5, 5)),
                               (5 * (prices - prices.mean(axis=1, keepdims=True)))[..., None]), axis=2)
    if len(raw) != len(features) or any(list(row['prices_cents']) != list(price)
                                       for row, price in zip(prior['cards'], PRICES, strict=True)):
        raise ValueError('Misaligned prediction cards')
    rng = np.random.default_rng(SEED)
    results = {n: [] for n in BUDGETS}
    for _ in range(REPLAYS):
        train, test = np.split(rng.permutation(len(features)), [len(features) // 2])
        order = rng.permutation(len(target))
        y_test = target[order[max(BUDGETS):]][:, test]
        hist = source[:, train]
        hist_rate = ((hist == 5).sum() + .5) / (hist.size + 1)
        hist_products = fit_choice(features[train], hist, features[test])
        qwen_refusal = raw[test, -1]
        qwen_products = raw[test, :-1]
        for n, rows in results.items():
            local = target[order[:n]][:, train]
            local_rate = ((local == 5).sum() + .5) / (local.size + 1)
            local_products = fit_choice(features[train], local, features[test])
            rows.append({
                'qwen': losses(y_test, qwen_refusal, qwen_products),
                'hypothetical_only': losses(y_test, hist_rate, hist_products),
                'hypothetical_products_local_rate': losses(y_test, local_rate, hist_products),
                'qwen_products_local_rate': losses(y_test, local_rate, qwen_products),
                'local_only': losses(y_test, local_rate, local_products),
                'half_local_half_hypothetical_products': losses(
                    y_test, local_rate, .5 * (local_products + hist_products)),
                'uniform_products_local_rate': losses(y_test, local_rate, np.full_like(local_products, .2)),
            })
    summary = {}
    for n, rows in results.items():
        means = {name: np.mean([row[name] for row in rows], axis=0).tolist() for name in rows[0]}
        paired = {}
        for a, b in [('hypothetical_only', 'hypothetical_products_local_rate'),
                     ('qwen_products_local_rate', 'hypothetical_products_local_rate'),
                     ('local_only', 'hypothetical_products_local_rate'),
                     ('local_only', 'half_local_half_hypothetical_products'),
                     ('hypothetical_products_local_rate', 'half_local_half_hypothetical_products')]:
            delta = np.array([row[a][-1] - row[b][-1] for row in rows])
            paired[f'{b}_over_{a}'] = {'mean_gain': float(delta.mean()),
                                      'win_rate': float(np.mean(delta > 0)),
                                      'p05_p95': np.quantile(delta, [.05, .95]).tolist()}
        summary[n] = {'losses': means, 'paired': paired}
    print(json.dumps({'seed': SEED, 'replays': REPLAYS, 'new_calls': 0, 'cards': len(PRICES),
                      'people': {name: len(rows) for name, rows in people.items()},
                      'loss_order': ['buy_or_not', 'which_product_contribution', 'total'],
                      'budgets': summary}, indent=2))


if __name__ == '__main__':
    main()
