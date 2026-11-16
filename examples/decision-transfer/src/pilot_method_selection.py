"""Test whether a small survey pilot can select a full-choice predictor."""
import json

import numpy as np
from scipy.special import softmax

from optout_pilot import REPEATS, SEED, fit_products, load, split_cards
from price_mix_replication import data, pepper_features
from small_choice_mix_transfer import BUDGETS, WEIGHT
import shortbread_pilot
import taiwan_pepper as pepper

NAMES = ('price', 'full', 'price_uniform', 'price_qwen', 'full_uniform', 'full_qwen')
FOLDS = 3


def forecast(features, y, qwen, train, target):
    x, answers = features[train], y[train]
    z = features[target]
    refusal = (answers[:, 0].sum() + .5) / (len(answers) + 1)
    price = softmax(z[..., -1:] @ fit_products(x[..., -1:], answers, nonpositive_price=True), axis=-1)
    full = softmax(z @ fit_products(x, answers, nonpositive_price=True), axis=-1)
    neutral = 1 / price.shape[-1]
    products = np.asarray([price, full, (1 - WEIGHT) * price + WEIGHT * neutral,
                           (1 - WEIGHT) * price + WEIGHT * qwen[target],
                           (1 - WEIGHT) * full + WEIGHT * neutral,
                           (1 - WEIGHT) * full + WEIGHT * qwen[target]])
    refuse = np.full((*products.shape[:-1], 1), refusal)
    return np.concatenate((refuse, (1 - refusal) * products), axis=-1)


def choose(features, y, qwen, keys, train, order, rng):
    card_ids = np.unique(keys[train])
    card_folds = {k: i % FOLDS for i, k in enumerate(rng.permutation(card_ids))}
    task_fold = np.array([[card_folds.get(k, -1) for k in row] for row in keys])
    person_fold = np.argsort(order)[:, None] % FOLDS
    errors = np.zeros(len(NAMES))
    count = 0
    for person in range(FOLDS):
        for card in range(FOLDS):
            validation = train & (person_fold == person) & (task_fold == card)
            if not validation.any():
                continue
            training = train & (person_fold != person) & (task_fold != card)
            if not training.any():
                return 0
            p = forecast(features, y, qwen, training, validation)
            errors += np.square(p - y[validation]).sum(axis=(1, 2))
            count += int(validation.sum())
    if count != train.sum():
        raise ValueError('Pilot validation did not cover every record')
    return int(np.argmin(errors))


def evaluate(p, y, keys, features):
    mass = p[..., 1:].sum(axis=-1, keepdims=True)
    qwen = np.divide(p[..., 1:], mass, out=np.full_like(p[..., 1:], 1 / (p.shape[-1] - 1)), where=mass > 0)
    rng, inner = (np.random.default_rng(seed) for seed in (SEED, SEED + 1))
    results = {n: [] for n in BUDGETS}
    selected = {n: np.zeros(len(NAMES), dtype=int) for n in BUDGETS}
    for _ in range(REPEATS):
        available = split_cards(keys, rng)
        order = rng.permutation(len(y))
        test = ~available
        test[order[:max(BUDGETS)]] = False
        for n, rows in results.items():
            train = available.copy()
            train[order[n:]] = False
            best = choose(features, y, qwen, keys, train, order, inner)
            selected[n][best] += 1
            forecasts = forecast(features, y, qwen, train, test)
            stats_only = forecasts[[0, 1, 2, 4]].mean(axis=0, keepdims=True)
            candidates = np.concatenate((forecasts, forecasts[best:best + 1],
                                         forecasts.mean(axis=0, keepdims=True), stats_only))
            rows.append(np.square(candidates - y[test]).sum(axis=-1).mean(axis=-1))
    names = (*NAMES, 'pilot_selection', 'equal_average', 'statistics_average')
    summary = {}
    for n, rows in results.items():
        scores = np.asarray(rows)
        gains = {}
        for i, name in enumerate(names):
            delta = scores[:, i] - scores[:, len(NAMES)]
            gains[name] = {'mean': float(delta.mean()), 'wins': int((delta > 1e-10).sum()),
                           'p05_p95': np.quantile(delta, [.05, .95]).tolist()}
        summary[n] = {'scores': dict(zip(names, scores.mean(axis=0).tolist(), strict=True)),
                      'selection_counts': dict(zip(NAMES, selected[n].tolist(), strict=True)),
                      'selection_over': gains,
                      'average_over_statistics': {
                          'wins': int((scores[:, -1] - scores[:, -2] > 1e-10).sum()),
                          'p05_p95': np.quantile(scores[:, -1] - scores[:, -2], [.05, .95]).tolist(),
                      }}
    return summary


def main():
    deck = pepper.deck()
    profiles = {k: [pepper_features(job['questions'][0]['options'][i]) for i in ('1', '2', '3')]
                for k, job in deck.items()}
    inputs = {name: (p, y, keys, x) for name, (p, y, keys, _, x) in load().items()}
    p, y, keys, _, x = shortbread_pilot.evaluation_inputs(*shortbread_pilot.load_deck())[0]
    inputs['scotland'] = p, y, keys, x
    inputs['taiwan'] = data(deck, pepper.observed_control(deck), profiles, pepper.RUN, refusal_last=True)
    print(json.dumps({'seed': SEED, 'replays': REPEATS, 'inner_folds_per_axis': FOLDS,
                      'new_calls': 0, 'studies': {name: evaluate(*args) for name, args in inputs.items()}},
                     indent=2))


if __name__ == '__main__':
    main()
