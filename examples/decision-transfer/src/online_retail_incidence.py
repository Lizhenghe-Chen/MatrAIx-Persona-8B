"""Replicate two-stage purchase forecasting on timestamped UK online orders."""
from collections import Counter
from hashlib import sha256
import json

import numpy as np
import pandas as pd

from dated_basket_incidence import NO_BUY, PRIOR_BASKETS, examples, score
from order_screen import SEED
from retail_next_basket import SOURCE, CUTOFF

DIGEST = 'c41dc0c7e3b6eef34ddd36a6813171dafda799ab4880476fc79a9db69248a53e'
FAMILIES = {
    'mugs': r'\bMUGS?\b',
    'candle_holders': r'\b(?:T[ -]?LIGHT|TEA[ -]?LIGHT|CANDLE)\s+HOLDERS?\b',
    'gift_bags': r'\bGIFT\s+BAGS?\b',
}


def load():
    if sha256(SOURCE.read_bytes()).hexdigest() != DIGEST:
        raise ValueError('Unexpected Online Retail version')
    raw = pd.read_csv(SOURCE)
    if len(raw) != 541909:
        raise ValueError('Unexpected row count')
    raw['InvoiceDate'] = pd.to_datetime(raw.InvoiceDate, format='%m/%d/%Y %H:%M')
    raw['StockCode'] = raw.StockCode.astype(str)
    valid = (raw.CustomerID.notna() & raw.InvoiceDate.notna()
             & raw.Country.eq('United Kingdom') & raw.Quantity.gt(0) & raw.UnitPrice.gt(0)
             & raw.InvoiceNo.astype(str).str.fullmatch(r'\d{6}')
             & raw.StockCode.str.fullmatch(r'\d{5}[A-Z]{0,2}'))
    rows = raw.loc[valid]
    before = rows.InvoiceDate.lt(CUTOFF)
    cohort = set(np.random.default_rng(SEED).permutation(sorted(rows.CustomerID.unique()))[::3])
    # Freeze the code-to-family mapping on training customers before the cutoff.
    descriptions = rows.loc[before & ~rows.CustomerID.isin(cohort), ['StockCode', 'Description']].dropna()
    names = descriptions.groupby('StockCode').Description.agg(lambda x: x.value_counts().index[0])
    families = {family: set(names[names.str.contains(pattern, case=False, regex=True)].index)
                for family, pattern in FAMILIES.items()}
    if len(set.union(*families.values())) != sum(map(len, families.values())):
        raise ValueError('Product families overlap')
    baskets = rows.groupby(['CustomerID', 'InvoiceDate'], sort=True).StockCode.agg(frozenset)
    return baskets, families, cohort


def evaluate(baskets, items, cohort):
    train, test = [], []
    coverage = Counter()
    for person, visits in baskets.groupby(level='CustomerID'):
        stamps = visits.index.get_level_values('InvoiceDate')
        stop = stamps.searchsorted(CUTOFF)
        if person in cohort:
            if stop == len(stamps):
                continue
            coverage['customers_with_later_order'] += 1
            limit = stop + 1
        else:
            limit = stop
        ordered = stamps[:limit]
        events = {}
        for stamp, contents in zip(ordered, visits.iloc[:limit], strict=True):
            subset = contents & items
            if subset:
                events[stamp] = next(iter(subset)) if len(subset) == 1 else ''
        for position, seen, features, outcome, count in examples(ordered, events):
            if person not in cohort:
                train.append((seen, features, outcome, count))
            elif position == stop:
                test.append((seen, features, outcome, count))
    if not train or not test or not any(row[2] != NO_BUY for row in test):
        raise ValueError('Not enough observations for a family')
    return {**coverage, 'catalogue_products': len(items), **score(train, test)}


if __name__ == '__main__':
    baskets, families, cohort = load()
    print(json.dumps({'source_sha256': DIGEST, 'cutoff': str(CUTOFF.date()), 'seed': SEED,
                      'prior_baskets': PRIOR_BASKETS, 'new_model_calls': 0, 'rules': FAMILIES,
                      'categories': {name: evaluate(baskets, items, cohort)
                                     for name, items in families.items()}}, indent=2))
