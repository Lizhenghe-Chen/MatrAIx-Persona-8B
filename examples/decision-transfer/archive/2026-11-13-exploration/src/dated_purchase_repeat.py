"""Forecast the next category purchase with a separately estimated repeat probability."""
from collections import Counter
from hashlib import sha256
import json

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

from grocery_next_basket import SOURCE, HASHES, CUTOFF, pyreadr
from order_screen import SEED

CATEGORIES = ('YOGURT', 'FLUID MILK PRODUCTS', 'PASTA SAUCE')
METHODS = ('market', 'fixed_mix', 'fixed_repeat_rate', 'learned_repeat_rate')


def load():
    for name, digest in HASHES.items():
        if sha256((SOURCE / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Unexpected source version: {name}')
    meta = pyreadr.read_r(str(SOURCE / 'products.rda'))['products']
    meta = meta.loc[meta.product_category.isin(CATEGORIES), ['product_id', 'product_category', 'brand', 'manufacturer_id']]
    if meta.product_id.duplicated().any():
        raise ValueError('Duplicate product metadata')
    tx = pyreadr.read_r(str(SOURCE / 'transactions.rds'))[None]
    keep = tx.quantity.gt(0) & tx.sales_value.gt(0) & tx.product_id.isin(meta.product_id)
    tx = tx.loc[keep, ['household_id', 'transaction_timestamp', 'product_id']].merge(meta, on='product_id', validate='many_to_one')
    tx = tx.dropna(subset=['household_id', 'transaction_timestamp'])
    # Manufacturer and label type are catalog proxies, not named brands.
    tx['label'] = np.where(tx.manufacturer_id.notna() & tx.manufacturer_id.astype(str).ne('0') & tx.brand.notna(),
                           tx.brand.astype(str) + '/' + tx.manufacturer_id.astype(str), '')
    visits = tx.groupby(['product_category', 'household_id', 'transaction_timestamp']).label.agg(
        lambda labels: next(iter(set(labels))) if labels.nunique() == 1 else '')
    return visits


def example(a, b, target):
    date_a, label_a = a
    date_b, label_b = b
    _, chosen = target
    if not all((label_a, label_b, chosen)):
        return None
    # The target date is only used to split/score, never as an input feature.
    gap = (date_b - date_a).total_seconds() / 86400
    return (label_a, label_b), chosen, np.array([1., float(label_a == label_b), np.log1p(gap) / 4])


def fit_gate(x, y):
    penalty = np.array([0., .02, .02])

    def objective(beta):
        z = x @ beta
        loss = np.mean(np.logaddexp(0, z) - y * z) + np.sum(penalty * beta**2)
        gradient = x.T @ (expit(z) - y) / len(y) + 2 * penalty * beta
        return loss, gradient

    fit = minimize(objective, np.zeros(x.shape[1]), jac=True)
    if not fit.success:
        raise RuntimeError(fit.message)
    return fit.x


def partition(series, cutoff=CUTOFF):
    series = series.sort_index()
    groups = {person: list(zip(rows.index.get_level_values('transaction_timestamp'), rows, strict=True))
              for person, rows in series.groupby(level='household_id')}
    people = np.random.default_rng(SEED).permutation(list(groups))
    test_people = set(people[::3])
    counts = Counter()
    fit, test = [], []
    exclusions = Counter()
    for person, visits in groups.items():
        before = [v for v in visits if v[0] < cutoff]
        if person not in test_people:
            counts.update(label for _, label in before if label)
            fit.extend(row for a, b, c in zip(before, before[1:], before[2:])
                       if (row := example(a, b, c)) is not None)
            continue
        after = next((v for v in visits if v[0] >= cutoff), None)
        if len(before) < 2 or after is None:
            exclusions['missing_visits'] += 1
            continue
        row = example(*before[-2:], after)
        if row is None:
            exclusions['mixed_or_unknown_label'] += 1
        else:
            test.append(row)
    return counts, fit, test, exclusions


def evaluate(series):
    counts, fit, test, exclusions = partition(series)
    # Use a single explicit bucket for unobserved catalog labels. The score
    # estimates category choice at this resolution, including out-of-catalog.
    catalogue = {label: i for i, label in enumerate(sorted(counts))}
    unknown = len(catalogue)
    market = np.array([counts[label] for label in catalogue] + [0], dtype=float) + .5
    market /= market.sum()
    fit_features = np.stack([x for _, _, x in fit])
    fit_repeat = np.array([chosen in seen for seen, chosen, _ in fit])
    beta = fit_gate(fit_features, fit_repeat)
    fixed_rate = float((fit_repeat.sum() + .5) / (len(fit_repeat) + 1))
    results, repeat_flags, repeat_predictions, new_labels = [], [], [], 0
    for seen, chosen, features in test:
        # A label absent from the training catalogue can still be in a given
        # household's history; give these known labels separate coordinates.
        extra = {label: len(market) + i for i, label in enumerate(sorted(set(seen) - catalogue.keys()))}
        brand = {**catalogue, **extra}
        local_market = np.r_[market, np.full(len(extra), market[unknown])]
        local_market /= local_market.sum()
        indices = [brand[label] for label in seen]
        history = np.bincount(indices, minlength=len(local_market)) / 2
        novel = local_market.copy()
        novel[indices] = 0
        novel /= novel.sum()
        probability = float(expit(features @ beta))
        predictions = np.array([
            local_market, .5 * local_market + .5 * history,
            fixed_rate * history + (1 - fixed_rate) * novel,
            probability * history + (1 - probability) * novel,
        ])
        target = brand.get(chosen, unknown)
        error = (predictions**2).sum(axis=1) + 1 - 2 * predictions[:, target]
        repeat_flags.append(chosen in seen)
        repeat_predictions.append(predictions[:, np.unique(indices)].sum(axis=1))
        new_labels += target == unknown
        results.append(error)
    losses = np.array(results)
    repeat = np.array(repeat_flags)
    rng = np.random.default_rng(SEED + 1)
    boot = rng.integers(len(losses), size=(2000, len(losses)))
    gains = {}
    for i, method in enumerate(METHODS[:-1]):
        delta = losses[:, i] - losses[:, -1]
        gains[method] = {'mean': float(delta.mean()), 'ci95': np.quantile(delta[boot].mean(axis=1), [.025, .975]).tolist()}
    return {'test_households': len(test), 'training_examples': len(fit),
            'repeat_targets': int(repeat.sum()), 'out_of_catalogue_targets': new_labels,
            'excluded': dict(exclusions), 'fixed_repeat_probability': fixed_rate,
            'predicted_repeat_probability': dict(zip(METHODS, np.mean(repeat_predictions, axis=0).tolist(), strict=True)),
            'repeat_event_brier': dict(zip(METHODS, np.square(
                np.asarray(repeat_predictions) - repeat[:, None]).mean(axis=0).tolist(), strict=True)),
            'brier': dict(zip(METHODS, losses.mean(axis=0).tolist(), strict=True)),
            'repeat_brier': dict(zip(METHODS, losses[repeat].mean(axis=0).tolist(), strict=True)),
            'novel_brier': dict(zip(METHODS, losses[~repeat].mean(axis=0).tolist(), strict=True)),
            'learned_gain': gains}


if __name__ == '__main__':
    data = load()
    print(json.dumps({'sources': HASHES, 'cutoff': str(CUTOFF.date()), 'seed': SEED, 'new_model_calls': 0,
                      'categories': {category: evaluate(data.loc[category]) for category in CATEGORIES}}, indent=2))
