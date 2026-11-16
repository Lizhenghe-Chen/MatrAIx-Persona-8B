"""Test the AI increment against stronger statistical baselines on frozen cards."""
import json

import numpy as np
from scipy.special import softmax

from attribute_regularization import PENALTY_MULTIPLIER
from choice_predictor import fit_products
from order_screen import SEED
import streaming_price_mix as streaming
from streaming_full_choice import load_predictions


def score():
    x, y, train, test = streaming.load()
    raw, identities = load_predictions(x, test)
    conditional = {}
    for name, p in raw.items():
        mass = p[:, 1:].sum(axis=-1, keepdims=True)
        conditional[name] = np.divide(p[:, 1:], mass, out=np.full_like(p[:, 1:], .25), where=mass > 0)
    x = np.concatenate((x[..., 1:], (x[..., :1] - 9.99) / 2), axis=-1)
    scale = 1 / np.sqrt(PENALTY_MULTIPLIER)
    variants = {'full': x, 'price': x[..., -1:], 'shrink_all': x * scale,
                'shrink_nonprice': x * np.r_[np.full(x.shape[-1] - 1, scale), 1.]}
    rng = np.random.default_rng(SEED + 1)
    results = {n: [] for n in streaming.SIZES}
    test_people = np.nonzero(test)[0]
    for _ in range(100):
        order = rng.permutation(len(y))
        mask = ~np.isin(test_people, order[:max(streaming.SIZES)])
        truth = y[test][mask]
        for n, rows in results.items():
            people = order[:n]
            available = train[people]
            answers = y[people][available]
            refusal = (answers[:, 0].sum() + .5) / (len(answers) + 1)
            forecasts = {name: softmax(features[test][mask] @ fit_products(
                features[people][available], answers, nonpositive_price=True), axis=-1)
                         for name, features in variants.items()}
            for base in ('price', 'shrink_all', 'shrink_nonprice'):
                forecasts[f'{base}_uniform'] = (1 - streaming.WEIGHT) * forecasts[base] + streaming.WEIGHT / forecasts[base].shape[-1]
                for model, probabilities in conditional.items():
                    forecasts[f'{base}_{model}'] = (1 - streaming.WEIGHT) * forecasts[base] + streaming.WEIGHT * probabilities[mask]
            rows.append({name: float(np.square(
                np.column_stack((np.full(len(truth), refusal), (1 - refusal) * p)) - truth
            ).sum(axis=-1).mean()) for name, p in forecasts.items()})
    summary = {}
    for n, rows in results.items():
        scores = {name: np.array([row[name] for row in rows]) for name in rows[0]}
        gains = {}
        for base in ('price', 'shrink_all', 'shrink_nonprice'):
            for model in conditional:
                candidate = f'{base}_{model}'
                for reference in (base, f'{base}_uniform', 'full'):
                    delta = scores[reference] - scores[candidate]
                    gains[f'{candidate}_over_{reference}'] = {
                        'mean': float(delta.mean()), 'wins': int((delta > 1e-10).sum()),
                        'p05_p95': np.quantile(delta, [.05, .95]).tolist(),
                    }
        summary[n] = {'brier': {name: float(values.mean()) for name, values in scores.items()}, 'gains': gains}
    return {'seed': SEED, 'replays': 100, 'new_calls': 0, 'identities': identities,
            'source_sha256': streaming.DIGEST, 'penalty_multiplier': PENALTY_MULTIPLIER,
            'model_weight': streaming.WEIGHT, 'budgets': summary}


if __name__ == '__main__':
    print(json.dumps(score(), indent=2))
