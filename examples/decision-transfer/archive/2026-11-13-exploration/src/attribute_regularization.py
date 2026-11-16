"""Compare fixed coefficient shrinkage with Qwen on full survey choices."""
import json

import numpy as np
from scipy.special import softmax

from optout_pilot import REPEATS, SEED, fit_products, load, split_cards
from price_mix_replication import data, pepper_features
from small_choice_mix_transfer import BUDGETS, WEIGHT
import shortbread_pilot
import taiwan_pepper as pepper

PENALTY_MULTIPLIER = 10


def evaluate(p, y, keys, features):
    products = p[..., 1:]
    mass = products.sum(axis=-1, keepdims=True)
    uniform = 1 / products.shape[-1]
    qwen = np.divide(products, mass, out=np.full_like(products, uniform), where=mass > 0)
    scale = 1 / np.sqrt(PENALTY_MULTIPLIER)
    nonprice_scale = np.r_[np.full(features.shape[-1] - 1, scale), 1.]
    variants = {'full': features, 'price': features[..., -1:],
                'shrink_all': scale * features, 'shrink_nonprice': nonprice_scale * features}
    rng = np.random.default_rng(SEED)
    results = {n: [] for n in BUDGETS}
    for _ in range(REPEATS):
        available = split_cards(keys, rng)
        order = rng.permutation(len(y))
        test = ~available
        test[order[:max(BUDGETS)]] = False
        truth = y[test]
        for n, rows in results.items():
            train = available.copy()
            train[order[n:]] = False
            answers = y[train]
            refusal = (answers[:, 0].sum() + .5) / (len(answers) + 1)
            fitted = {name: softmax(x[test] @ fit_products(x[train], answers, nonpositive_price=True), axis=-1)
                      for name, x in variants.items()}
            fitted['price_qwen'] = (1 - WEIGHT) * fitted['price'] + WEIGHT * qwen[test]
            fitted['full_qwen'] = (1 - WEIGHT) * fitted['full'] + WEIGHT * qwen[test]
            fitted['shrink_nonprice_qwen'] = (1 - WEIGHT) * fitted['shrink_nonprice'] + WEIGHT * qwen[test]
            fitted['shrink_nonprice_uniform'] = (1 - WEIGHT) * fitted['shrink_nonprice'] + WEIGHT * uniform
            rows.append({name: float(np.square(
                np.column_stack((np.full(len(truth), refusal), (1 - refusal) * pred)) - truth
            ).sum(axis=-1).mean()) for name, pred in fitted.items()})
    summary = {}
    for n, rows in results.items():
        scores = {name: np.array([r[name] for r in rows]) for name in rows[0]}
        comparisons = {}
        for base, candidate in [('full', 'shrink_nonprice'), ('price', 'shrink_nonprice'),
                                ('price_qwen', 'shrink_nonprice'),
                                ('shrink_nonprice', 'shrink_nonprice_qwen'),
                                ('shrink_nonprice_uniform', 'shrink_nonprice_qwen')]:
            gain = scores[base] - scores[candidate]
            comparisons[f'{candidate}_over_{base}'] = {
                'wins': int((gain > 1e-10).sum()), 'p05_p95': np.quantile(gain, [.05, .95]).tolist(),
            }
        summary[n] = {'brier': {name: float(loss.mean()) for name, loss in scores.items()},
                      'comparisons': comparisons}
    return {'people': len(y), 'cards': len(np.unique(keys)), 'budgets': summary}


def main():
    studies = {name: (p, y, keys, x) for name, (p, y, keys, _, x) in load().items()}
    p, y, keys, _, x = shortbread_pilot.evaluation_inputs(*shortbread_pilot.load_deck())[0]
    studies['scotland'] = p, y, keys, x
    deck = pepper.deck()
    profiles = {key: [pepper_features(job['questions'][0]['options'][i]) for i in ('1', '2', '3')]
                for key, job in deck.items()}
    studies['taiwan'] = data(deck, pepper.observed_control(deck), profiles, pepper.RUN, refusal_last=True)
    print(json.dumps({'seed': SEED, 'replays': REPEATS, 'penalty_multiplier': PENALTY_MULTIPLIER,
                      'new_calls': 0, 'studies': {name: evaluate(*args) for name, args in studies.items()}},
                     indent=2))


if __name__ == '__main__':
    main()
