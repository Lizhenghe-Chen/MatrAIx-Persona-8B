"""Test whether a small pilot can choose among simple product probability models."""
import json

import numpy as np
from scipy.special import softmax

from adaptive_pilot import spanish
from cheese_pilot import evaluation_inputs, load_deck
import optout_pilot as pilot
from price_study_transfer import fit, log_prices
import shortbread_pilot

STATISTICAL = ('uniform', 'historical_price', 'local_price', 'all_attributes')
CANDIDATES = (*STATISTICAL, 'qwen')


def candidates(train_x, train_y, test_x, qwen, prior):
    return np.asarray([
        np.full(test_x.shape[:2], 1 / test_x.shape[1]),
        softmax(test_x[..., -1] * prior, axis=1),
        softmax(test_x[..., -1] * fit(train_x[..., -1:], train_y)[-1], axis=1),
        softmax(test_x @ fit(train_x, train_y), axis=1),
        qwen,
    ])


def scores(train_y, test_y, probabilities):
    rate = (train_y[:, 0].sum() + .5) / (len(train_y) + 1)
    joint_products = (1 - rate) * probabilities
    return (joint_products - test_y[:, 1:]) ** 2, (rate - test_y[:, 0]) ** 2


def card_folds(keys, mask):
    assignment = {}
    for block in np.unique(keys, axis=0):
        available = sorted(set(block) & set(keys[mask]))
        for i, key in enumerate(available):
            if assignment.setdefault(key, i % 3) != i % 3:
                raise ValueError('Inconsistent card block')
    return np.array([[assignment.get(k, -1) for k in row] for row in keys])


def select(x, y, p, keys, mask, prior):
    people = np.arange(len(y))[:, None] % 5
    cards = card_folds(keys, mask)
    losses = np.zeros(len(CANDIDATES))
    visited = 0
    for person_fold in range(5):
        for card_fold in range(3):
            valid = mask & (people == person_fold) & (cards == card_fold)
            if not valid.any():
                continue
            train = mask & (people != person_fold) & (cards != card_fold)
            if not train.any():
                raise ValueError('Empty inner training set')
            products = candidates(x[train], y[train], x[valid], p[valid], prior)
            product_error, _ = scores(y[train], y[valid], products)
            losses += product_error.sum(axis=(1, 2))
            visited += valid.sum()
    if visited != mask.sum():
        raise ValueError('Incomplete inner validation')
    return int(losses[:-1].argmin()), int(losses.argmin())


def evaluate(p, y, keys, x, prior):
    mass = p[:, :, 1:].sum(axis=-1, keepdims=True)
    conditional = np.divide(p[:, :, 1:], mass, where=mass > 0,
                            out=np.full_like(p[:, :, 1:], 1 / (p.shape[-1] - 1)))
    rng = np.random.default_rng(pilot.SEED)
    rows = {n: [] for n in pilot.SIZES}
    for _ in range(pilot.REPEATS):
        available = pilot.split_cards(keys, rng)
        order = rng.permutation(len(y))
        test = order[max(pilot.SIZES):]
        held = ~available[test]
        test_x, test_y, test_p = x[test][held], y[test][held], conditional[test][held]
        for n in pilot.SIZES:
            train = order[:n]
            mask = available[train]
            study_choice, any_choice = select(x[train], y[train], conditional[train],
                                              keys[train], mask, prior)
            train_x, train_y = x[train][mask], y[train][mask]
            products = candidates(train_x, train_y, test_x, test_p, prior)
            all_probs = np.concatenate((products, [
                products[:-1].mean(axis=0), products.mean(axis=0),
                products[study_choice], products[any_choice],
            ]))
            errors, optout = scores(train_y, test_y, all_probs)
            methods = (*CANDIDATES, 'equal_statistics', 'equal_with_qwen', 'select_statistics', 'select_with_qwen')
            losses = dict(zip(methods, errors.sum(axis=2).mean(axis=1) + optout.mean(), strict=True))
            raw = p[test][held]
            losses['qwen_direct'] = float(np.sum((raw - test_y) ** 2, axis=1).mean())
            rows[n].append((losses, study_choice, any_choice))
    return {n: summarize(results) for n, results in rows.items()}


def summarize(rows):
    losses, statistics, including_qwen = zip(*rows, strict=True)
    mean = {method: float(np.mean([row[method] for row in losses])) for method in losses[0]}
    comparisons = {}
    for name, base, candidate in (
        ('selection_vs_fixed_mix', 'equal_statistics', 'select_statistics'),
        ('qwen_increment_selection', 'select_statistics', 'select_with_qwen'),
        ('qwen_increment_fixed_mix', 'equal_statistics', 'equal_with_qwen'),
    ):
        delta = np.asarray([row[base] - row[candidate] for row in losses])
        comparisons[name] = {'improvement': float(delta.mean()),
                             'win_rate': float(np.mean(delta > 1e-9)),
                             'p05_p95': np.quantile(delta, [.05, .95]).tolist()}
    return {'brier': mean, 'comparisons': comparisons,
            'selected_without_qwen': dict(zip(STATISTICAL, np.bincount(statistics, minlength=4).tolist())),
            'selected_with_qwen': dict(zip(CANDIDATES, np.bincount(including_qwen, minlength=5).tolist()))}


def main():
    italian, _, _ = evaluation_inputs(*load_deck())
    scottish, _, _ = shortbread_pilot.evaluation_inputs(*shortbread_pilot.load_deck())
    inputs = {**pilot.load(), 'spain': spanish(), 'italy': italian, 'scotland': scottish}
    data, slopes = {}, {}
    for study, (p, y, keys, _, features) in inputs.items():
        x = features.copy()
        x[..., -1] = log_prices(x, study)
        data[study] = p, y, keys, x
        if study != 'german':
            slopes[study] = float(fit(x.reshape(-1, *x.shape[2:]), y.reshape(-1, y.shape[-1]))[-1])
    results = {}
    for study, study_data in data.items():
        prior = float(np.mean([value for name, value in slopes.items() if name != study]))
        results[study] = evaluate(*study_data, prior)
    print(json.dumps({'seed': pilot.SEED, 'splits': pilot.REPEATS, 'new_calls': 0,
                      'studies': results}, indent=2))


if __name__ == '__main__':
    main()
