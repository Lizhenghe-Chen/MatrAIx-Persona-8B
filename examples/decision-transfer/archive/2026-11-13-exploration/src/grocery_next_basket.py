"""Test repurchase and cross-category discovery in timestamped supermarket baskets."""
from collections import Counter, defaultdict
from hashlib import sha256
import json

import numpy as np
import pandas as pd
import pyreadr

from order_screen import SEED, WORK

SOURCE = WORK / 'materials/completejourney'
HASHES = {
    'transactions.rds': '1fa0700033f1e5d9bb6b09e2be063d8d68474d346e95c50f2833e09d083e0007',
    'products.rda': 'a80c6df33623b4af296ae9f317a6647e369db7e8ce7e7baed0e1bf44b9d979e5',
}
CUTOFF = pd.Timestamp('2017-10-01')
K = 20


def load(*, dated=False):
    for file, expected in HASHES.items():
        if sha256((SOURCE / file).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Unexpected source version: {file}')
    transactions = pyreadr.read_r(str(SOURCE / 'transactions.rds'))[None]
    metadata = pyreadr.read_r(str(SOURCE / 'products.rda'))['products']
    metadata = metadata.dropna(subset=['product_id', 'department', 'product_category'])
    if metadata.product_id.duplicated().any():
        raise ValueError('Duplicate catalogue product')
    categories = {p: (d, c) for p, d, c in metadata[
        ['product_id', 'department', 'product_category']
    ].itertuples(index=False, name=None) if d.strip() and c.strip()}
    rows = transactions.loc[
        transactions.quantity.gt(0) & transactions.sales_value.gt(0)
        & transactions.product_id.isin(categories)
    ].dropna(subset=['household_id', 'transaction_timestamp'])
    grouped = rows.groupby(['household_id', 'transaction_timestamp'], sort=True).product_id.agg(
        lambda items: frozenset(items)
    )
    history, targets = defaultdict(list), {}
    for (household, time), items in grouped.items():
        if time < CUTOFF:
            history[household].append((time, items) if dated else items)
        else:
            targets.setdefault(household, items)
    return categories, history, targets, {
        'rows': len(transactions), 'retained_rows': len(rows), 'baskets': len(grouped),
    }


def rank(scores, excluded, limit=K):
    return sorted((item for item in scores if item not in excluded),
                  key=lambda item: (-scores[item], item))[:limit]


def evaluate(categories, history, targets):
    eligible = sorted(h for h in targets if len(history.get(h, [])) >= 2)
    # Fixed household split. Historical training baskets from other households only.
    rng = np.random.default_rng(SEED)
    test = sorted(rng.permutation(eligible)[::3].tolist())
    train = set(history) - set(test)
    baskets = [basket for household in sorted(train) for basket in history[household]]
    counts = Counter(item for basket in baskets for item in sorted(basket))
    all_popular = rank(counts, set())
    co_item, co_category = defaultdict(Counter), defaultdict(Counter)
    category_counts = Counter()
    for basket in baskets:
        items = sorted(basket)
        present = sorted({categories[item] for item in items})
        category_counts.update(present)
        for item in items:
            co_item[item].update(other for other in items if other != item)
        for category in present:
            co_category[category].update(items)
    by_score = defaultdict(list)
    coverage = Counter()
    for household in test:
        prior = history[household]
        recent = prior[-2:]
        past = set().union(*prior)
        past_categories = {categories[item] for item in past}
        actual = targets[household]
        new_items = actual - past
        new_categories = {item for item in actual if categories[item] not in past_categories}
        for name, items in [('any', actual), ('new_items', new_items), ('new_categories', new_categories)]:
            coverage[f'{name}_orders'] += bool(items)
            coverage[f'{name}_items'] += len(items)
            coverage[f'{name}_in_train_catalogue'] += len(items & counts.keys())
        recent_counts = Counter(item for basket in recent for item in sorted(basket))
        repeat = list(dict.fromkeys(rank(recent_counts, set()) + all_popular))[:K]
        item_scores, category_scores = Counter(), Counter()
        for item in sorted(recent_counts):
            for candidate, count in co_item[item].items():
                item_scores[candidate] += count / counts[item]
        for category in sorted({categories[item] for item in recent_counts}):
            for candidate, count in co_category[category].items():
                category_scores[candidate] += count / category_counts[category]
        popular_new = rank(counts, past)
        item_new = list(dict.fromkeys(rank(item_scores, past) + popular_new))[:K]
        category_new = list(dict.fromkeys(rank(category_scores, past) + popular_new))[:K]
        # Two candidate channels share the same twenty slots.
        combined = list(dict.fromkeys(item for pair in zip(item_new, category_new, strict=True) for item in pair))[:K]
        candidates = {'popular': all_popular, 'own_repeat': repeat, 'popular_new': popular_new,
                      'item_association': item_new, 'category_association': category_new,
                      'combined': combined}
        for method, picks in candidates.items():
            chosen = set(picks)
            by_score[method].append([len(chosen & target) / len(target) if target else np.nan
                                     for target in (actual, new_items, new_categories)])
    metrics = {method: np.asarray(rows) for method, rows in by_score.items()}
    columns = ('any', 'new_items', 'new_categories')
    comparisons = {}
    for candidate, base, col in [('own_repeat', 'popular', 0),
                                 ('item_association', 'popular_new', 1),
                                 ('category_association', 'item_association', 2),
                                 ('combined', 'item_association', 1),
                                 ('combined', 'item_association', 2)]:
        delta = (metrics[candidate] - metrics[base])[:, col]
        delta = delta[np.isfinite(delta)]
        bootstrap = rng.integers(len(delta), size=(2000, len(delta)))
        comparisons[f'{candidate}_minus_{base}_{columns[col]}'] = {
            'delta': float(delta.mean()), 'interval_95': np.quantile(
                delta[bootstrap].mean(axis=1), [.025, .975]).tolist(),
        }
    return {'train_households': len(train), 'train_baskets': len(baskets),
            'train_products': len(counts), 'test_households': len(test), 'coverage': dict(coverage),
            'recall_at_20': {name: dict(zip(columns, np.nanmean(value, axis=0).tolist(), strict=True))
                             for name, value in metrics.items()},
            'comparisons': comparisons}


if __name__ == '__main__':
    categories, history, targets, coverage = load()
    print(json.dumps({'sources': HASHES, 'cutoff': str(CUTOFF.date()), 'seed': SEED, **coverage,
                      **evaluate(categories, history, targets)}, indent=2))
