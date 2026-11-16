"""Compare Qwen with small-panel baselines on held-out scanner purchases."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from functools import partial
from hashlib import sha256
import json
import random

import numpy as np
from scipy.special import softmax

from choice_predictor import fit_products
from order_screen import WORK, SEED, encode, read, result_path, send
import protocol

SOURCE = WORK / 'materials/scanner-brand'
RUN = WORK / 'scanner-brand-v1'
DATASETS = {
    'Yogurt': ('522552372b313d537a7c8b9d7acf28a3d9a6ba8950c69a0dd78d86f0e164cf0d',
               2412, 'id', 'choice', ('yoplait', 'dannon', 'hiland', 'weight'),
               ('Yoplait', 'Dannon', 'Hiland', 'Weight Watchers')),
    'Ketchup': ('85f068c8e455a56fe06aa9e75affebd8c65de00edffe55dcfebb737441d9702c',
                4956, 'Ketchup.hid', 'Ketchup.choice', ('heinz', 'hunts', 'delmonte', 'stb'),
                ('Heinz', "Hunt’s", 'Del Monte', 'Store brand')),
}
N_PILOT, N_EVAL = 10, 24


def load(study):
    digest, size, person, choice, keys, brands = DATASETS[study]
    path = SOURCE / f'{study}.csv'
    if sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError(f'Unexpected {study} data version')
    with path.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != size:
        raise ValueError(f'Unexpected {study} row count')
    ids = np.asarray([int(row[person]) for row in rows])
    prices = np.asarray([[float(row[f'price.{key}']) for key in keys] for row in rows])
    if not np.isfinite(prices).all() or np.any(prices <= 0):
        raise ValueError(f'Invalid {study} prices')
    index = np.round(100 * prices / prices.min(axis=1, keepdims=True), 1)
    feat = np.asarray([[int(row.get(f'feat.{key}', 0)) for key in keys] for row in rows])
    if not np.isin(feat, [0, 1]).all():
        raise ValueError(f'Invalid {study} promotion code')
    y = np.eye(len(keys))[[keys.index(row[choice]) for row in rows]]
    return ids, index, feat, y, brands


def split(ids, index, feat):
    rng = np.random.default_rng(SEED)
    households = rng.permutation(np.unique(ids))
    train = np.isin(ids, households[:N_PILOT])
    signatures = [tuple(row) for row in np.column_stack((index, feat))]
    seen = {signatures[i] for i in np.flatnonzero(train)}
    eval_rows = []
    for household in households[N_PILOT:]:
        eligible = [i for i in np.flatnonzero(ids == household) if signatures[i] not in seen]
        if eligible:
            eval_rows.append(int(rng.choice(eligible)))
        if len(eval_rows) == N_EVAL:
            break
    if len(eval_rows) != N_EVAL:
        raise ValueError('Not enough unseen household and offer combinations')
    return train, np.asarray(eval_rows)


def deck(study, data, selected):
    _, index, feat, _, brands = data
    jobs = []
    for i, row in enumerate(selected, 1):
        names = {}
        for k, brand in enumerate(brands, 1):
            label = f'{brand}. Relative price index: {index[row, k - 1]:.1f}.'
            if study == 'Yogurt':
                label += f' Featured in a newspaper ad: {"yes" if feat[row, k - 1] else "no"}.'
            names[str(k)] = label
        question = {'id': f'{study.lower()}-{i:02}', 'options': names,
                    'prompt': f'Which brand would the household purchase from these four {study.lower()} options?'}
        body = protocol.build({'title': 'US grocery brand purchase',
                               'context': 'Historical US supermarket. The household is buying one of the four brands. '
                               'The lowest price index in each set is 100. An index of 120 means 20% more expensive.',
                               'questions': [question], 'basic': {}}, 'basic', 'qwen', {}, {}, 512)
        jobs.append({'questions': [question], 'body': body})
    return jobs


def score(data, train, test, qwen):
    ids, index, feat, truth, _ = data
    count = len(truth)
    price = 5 * (np.log(index) - np.log(index).mean(axis=1, keepdims=True))
    x = np.concatenate((np.broadcast_to(np.eye(4), (count, 4, 4)),
                        feat[..., None], price[..., None]), axis=-1)
    train_y = np.column_stack((np.zeros(train.sum()), truth[train]))
    beta = fit_products(x[train], train_y, nonpositive_price=True)
    no_price_beta = fit_products(x[train, :, :-1], train_y)
    price_beta = fit_products(x[train, :, -1:], train_y, nonpositive_price=True)
    historical = (truth[train].sum(axis=0) + .5) / (train.sum() + 2)
    statistics = softmax(x[test] @ beta, axis=1)
    predictions = {
        'uniform': np.full_like(qwen, .25),
        'brand_frequencies': np.broadcast_to(historical, qwen.shape),
        'price_only': softmax(x[test, :, -1:] @ price_beta, axis=1),
        'attributes_without_price': softmax(x[test, :, :-1] @ no_price_beta, axis=1),
        'attributes': statistics,
        'qwen': qwen,
        'attributes_qwen_half': (statistics + qwen) / 2,
    }
    losses = {name: np.sum((p - truth[test]) ** 2, axis=1) for name, p in predictions.items()}
    rng = np.random.default_rng(SEED)
    draws = rng.integers(len(test), size=(2000, len(test)))

    def interval(base, candidate):
        delta = losses[base] - losses[candidate]
        return np.quantile(delta[draws].mean(axis=1), [.025, .975]).tolist()

    # Keep the same evaluation households and offers while resampling training households.
    signatures = [tuple(row) for row in np.column_stack((index, feat))]
    held_offers = {signatures[i] for i in test}
    available = ~np.isin(ids, ids[test]) & np.asarray([key not in held_offers for key in signatures])
    eligible_households = np.unique(ids[available])
    sensitivity = []
    for _ in range(100):
        chosen = rng.choice(eligible_households, N_PILOT, replace=False)
        sample = available & np.isin(ids, chosen)
        targets = np.column_stack((np.zeros(sample.sum()), truth[sample]))
        p = softmax(x[test] @ fit_products(x[sample], targets, nonpositive_price=True), axis=1)
        brier = np.sum((p - truth[test]) ** 2, axis=1).mean()
        sensitivity.append(float(brier))

    return {
        'brand_order': list(data[-1]),
        'households_total': len(np.unique(ids)),
        'transactions_total': count,
        'brand_shares_all': truth.mean(axis=0).tolist(),
        'pilot_households': len(np.unique(ids[train])),
        'pilot_transactions': int(train.sum()),
        'evaluation_households': len(test),
        'brier': {name: float(values.mean()) for name, values in losses.items()},
        'statistics_over_qwen_bootstrap_95': interval('qwen', 'attributes'),
        'mix_improvement_bootstrap_95': interval('attributes', 'attributes_qwen_half'),
        'statistics_pilot_resampling': {
            'runs': len(sensitivity),
            'mean_brier': float(np.mean(sensitivity)),
            'brier_p05_p95': np.quantile(sensitivity, [.05, .95]).tolist(),
            'runs_better_than_qwen': int(np.sum(np.asarray(sensitivity) < losses['qwen'].mean())),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    action = parser.parse_args().action
    data = {study: load(study) for study in DATASETS}
    splits = {study: split(*values[:3]) for study, values in data.items()}
    by_study = {study: deck(study, values, splits[study][1]) for study, values in data.items()}
    jobs = [job for batch in by_study.values() for job in batch]
    random.Random(SEED).shuffle(jobs)
    RUN.mkdir(mode=0o700, exist_ok=True)
    frozen = RUN / 'jobs.json'
    if frozen.exists() and frozen.read_bytes() != encode(jobs):
        raise ValueError('Frozen scanner requests changed')
    if not frozen.exists():
        frozen.write_bytes(encode(jobs))
    if action == 'run':
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(partial(send, directory=RUN), jobs))
    identities, results = set(), {}
    for study, batch in by_study.items():
        estimates = []
        for job in batch:
            result = read(result_path(job, RUN))
            if result['status'] != 'ok':
                raise ValueError(f'Invalid response for {study}: {result["type"]}')
            identities.add(json.dumps(result['identity'], sort_keys=True))
            p = result['p'][job['questions'][0]['id']]
            estimates.append([p[str(i)] for i in range(1, 5)])
        results[study] = score(data[study], *splits[study], np.asarray(estimates))
        results[study]['source_sha256'] = DATASETS[study][0]
    if len(identities) != 1:
        raise ValueError('Qwen identity changed')
    print(json.dumps({'seed': SEED, 'predictions': len(jobs),
                      'identity': json.loads(identities.pop()), 'studies': results}, indent=2))


if __name__ == '__main__':
    main()
