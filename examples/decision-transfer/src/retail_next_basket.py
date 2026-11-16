"""Evaluate simple recommendations on timestamped UK online retail purchases."""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

SOURCE = Path.home() / '.local/share/matraix-decision-transfer/work/materials/online-retail/polito.csv'
CUTOFF = pd.Timestamp('2011-09-01')
K = 10
SEED = 20261109


def read_orders(path, *, dated=False):
    if path.suffix == '.csv':
        frame = pd.read_csv(path)
    else:
        with ZipFile(path) as archive, archive.open('Online Retail.xlsx') as workbook:
            frame = pd.read_excel(workbook)
    frame['InvoiceDate'] = pd.to_datetime(frame['InvoiceDate'], format='mixed')
    code = frame['StockCode'].astype(str)
    invoice = frame['InvoiceNo'].astype(str)
    keep = (
        frame['CustomerID'].notna() & frame['InvoiceDate'].notna()
        & frame['Country'].eq('United Kingdom') & frame['Quantity'].gt(0)
        & frame['UnitPrice'].gt(0) & invoice.str.fullmatch(r'\d{6}')
        & code.str.fullmatch(r'\d{5}[A-Z]{0,2}')
    )
    retained = frame.loc[keep, ['CustomerID', 'InvoiceNo', 'InvoiceDate']].assign(StockCode=code[keep])
    # Merge invoices with the same customer and timestamp. Their relative order is unknown.
    baskets = retained.groupby(['CustomerID', 'InvoiceDate'], sort=True)['StockCode'].agg(
        lambda values: tuple(sorted(set(values)))
    )
    history, targets, market = defaultdict(list), {}, []
    for (customer, date), items in baskets.items():
        if date < CUTOFF:
            history[customer].append((date, items) if dated else items)
            market.append((customer, items))
        else:
            targets.setdefault(customer, items)
    return history, targets, market, {'source_rows': len(frame), 'eligible_lines': len(retained),
                                      'timestamped_baskets': len(baskets)}


def top(counts, excluded=()):
    excluded = set(excluded)
    return sorted((item for item in counts if item not in excluded),
                  key=lambda item: (-counts[item], item))[:K]


def complete(prefix, fallback):
    return list(dict.fromkeys([*prefix, *fallback]))[:K]


def evaluate(history, targets, market, candidate_sets=None):
    # Learn population statistics only from customers outside the evaluation cohort.
    eligible = sorted(customer for customer in targets if len(history.get(customer, [])) >= 2)
    rng = np.random.default_rng(SEED)
    donors = set(history) - set(eligible)
    if not donors or not eligible:
        raise ValueError('Missing evaluation or donor cohort')
    pool = [basket for customer, basket in market if customer in donors]
    counts = Counter(item for basket in pool for item in basket)
    global_rank = top(counts)
    if len(global_rank) != K:
        raise ValueError('Insufficient historical catalogue')
    related = defaultdict(Counter)
    for basket in pool:
        for item in basket:
            related[item].update(other for other in basket if other != item)
    swap = rng.permutation(len(eligible))
    donors_for_history = dict(zip([eligible[i] for i in swap],
                                  [eligible[i] for i in np.roll(swap, 1)], strict=True))
    rows = defaultdict(list)
    target_sizes = []
    full_novelty = []
    for customer in eligible:
        before = history[customer][-2:]
        history_counts = Counter(item for basket in before for item in basket)
        seen = set(history_counts)
        older = {item for basket in history[customer] for item in basket}
        actual = set(targets[customer])
        associations = Counter()
        for item in seen:
            for other, count in related[item].items():
                associations[other] += count / counts[item]
        wrong = Counter(item for basket in history[donors_for_history[customer]][-2:] for item in basket)
        methods = {
            'population': global_rank,
            'own_repeat': complete(top(history_counts), global_rank),
            'other_repeat': complete(top(wrong), global_rank),
            'own_repeat_and_associations': complete(top(history_counts)[:5],
                                                    complete(top(associations, seen), global_rank)),
            'unseen_popularity': top(counts, older),
            'unseen_associations': complete(top(associations, older), top(counts, older)),
        }
        if candidate_sets is not None:
            candidate_sets[customer] = (
                before, methods['unseen_associations'], methods['unseen_popularity'], actual - older
            )
        new = actual - older
        full_novelty.append(len(new) / len(actual))
        target_sizes.append(len(actual))
        for name, picks in methods.items():
            picked = set(picks)
            rows[name].append((len(actual & picked) / len(actual),
                               len(new & picked) / len(new) if new else np.nan))
    draws = rng.integers(len(eligible), size=(2000, len(eligible)))
    metrics = {name: np.asarray(values) for name, values in rows.items()}
    improvements = {}
    for candidate, base, column in (
        ('own_repeat', 'population', 0),
        ('own_repeat', 'other_repeat', 0),
        ('own_repeat_and_associations', 'own_repeat', 0),
        ('unseen_associations', 'unseen_popularity', 1),
    ):
        delta = metrics[candidate][:, column] - metrics[base][:, column]
        valid = np.isfinite(delta)
        paired_draws = draws if valid.all() else rng.integers(valid.sum(), size=(2000, valid.sum()))
        interval = np.quantile(delta[valid][paired_draws].mean(axis=1), [.025, .975])
        improvements[f'{candidate}_over_{base}'] = {
            'mean': float(delta[valid].mean()), 'interval_95': interval.tolist()
        }
    return {
        'eligible_customers': len(eligible), 'donor_customers': len(donors),
        'donor_baskets': len(pool), 'mean_target_size': float(np.mean(target_sizes)),
        'targets_with_new_items': int(np.isfinite(metrics['population'][:, 1]).sum()),
        'mean_share_of_new_items': float(np.mean(full_novelty)),
        'metrics': {name: {'recall_at_10': float(values[:, 0].mean()),
                           'new_item_recall_at_10': float(np.nanmean(values[:, 1]))}
                    for name, values in metrics.items()},
        'improvements': improvements,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    path = parser.parse_args().source
    history, targets, market, coverage = read_orders(path)
    result = evaluate(history, targets, market)
    print(json.dumps({'sha256': sha256(path.read_bytes()).hexdigest(),
                      'cutoff': str(CUTOFF.date()), 'seed': SEED, **coverage, **result}, indent=2))


if __name__ == '__main__':
    main()
