"""Test whether two same-household purchase records improve brand prediction."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import json
import random

import numpy as np

from order_screen import WORK, SEED, encode, read, result_path, send
from scanner_brand_screen import DATASETS, load
import protocol

RUN = WORK / 'scanner-history-v1'
ARMS = ('none', 'own', 'other')
EVAL = 24
HISTORY_WEIGHT = .5


def prepare(study):
    ids, _, _, y, brands = load(study)
    rng = np.random.default_rng(SEED)
    groups = {household: np.flatnonzero(ids == household) for household in np.unique(ids)}
    eligible = [household for household, rows in groups.items() if len(rows) >= 3]
    panel = rng.permutation(eligible)[:EVAL]
    if len(panel) != EVAL:
        raise ValueError('Insufficient households with three records')
    rows = np.asarray([groups[household][:3] for household in panel])
    # Shift entire history blocks; keep the distribution of brand histories fixed.
    histories = y[rows[:, :2]].argmax(axis=-1)
    swapped = np.roll(histories, 1, axis=0)
    jobs = {}
    for i in range(EVAL):
        question = {'id': f'{study.lower()}-{i + 1:02}',
                    'prompt': f'Which brand would this household buy on the target {study.lower()} purchase?',
                    'options': {str(k): brand for k, brand in enumerate(brands, 1)}}
        for arm in ARMS:
            context = 'Historical US grocery purchases. The household bought one of these four brands.'
            if arm != 'none':
                record = histories[i] if arm == 'own' else swapped[i]
                context += f' Two other purchases attributed to this household: {brands[record[0]]}; {brands[record[1]]}.'
            body = protocol.build({'title': 'US grocery brand purchase', 'context': context,
                                   'questions': [question], 'basic': {}}, 'basic', 'qwen', {}, {}, 512)
            jobs[i, arm] = {'questions': [question], 'body': body}
    # Use one cohort of ten other households, without using evaluation or donor outcomes.
    training = rng.choice(np.setdiff1d(np.unique(ids), panel), 10, replace=False)
    train_y = y[np.isin(ids, training)]
    population = (train_y.sum(axis=0) + .5) / (len(train_y) + 2)
    empirical = np.eye(len(brands))[histories].mean(axis=1)
    shuffled = np.eye(len(brands))[swapped].mean(axis=1)
    truth = y[rows[:, 2]]
    statistical = {'population': np.broadcast_to(population, truth.shape),
                   'own_history': (1 - HISTORY_WEIGHT) * population + HISTORY_WEIGHT * empirical,
                   'other_history': (1 - HISTORY_WEIGHT) * population + HISTORY_WEIGHT * shuffled,
                   'history_only': empirical}
    coverage = {'total_households': len(groups), 'eligible_households': len(eligible),
                'evaluation_households': len(panel), 'training_transactions': len(train_y),
                'histories_changed': int((empirical != shuffled).any(axis=1).sum())}
    return jobs, truth, statistical, coverage


def score(truth, statistical, qwen):
    predictions = {**statistical, **{f'qwen_{name}': p for name, p in qwen.items()}}
    brier = {name: np.sum((p - truth) ** 2, axis=1) for name, p in predictions.items()}
    rng = np.random.default_rng(SEED)
    bootstrap = rng.integers(len(truth), size=(2000, len(truth)))
    pairs = [('population', 'own_history'), ('other_history', 'own_history'),
             ('qwen_none', 'qwen_own'), ('qwen_other', 'qwen_own'), ('qwen_own', 'own_history'), ('qwen_own', 'history_only')]
    improvements = {}
    for base, candidate in pairs:
        delta = brier[base] - brier[candidate]
        improvements[f'{candidate}_over_{base}'] = {
            'mean': float(delta.mean()),
            'interval_95': np.quantile(delta[bootstrap].mean(axis=1), [.025, .975]).tolist(),
        }
    return {'brier': {name: float(errors.mean()) for name, errors in brier.items()},
            'accuracy': {name: float(np.mean(p.argmax(axis=1) == truth.argmax(axis=1)))
                         for name, p in predictions.items()}, 'improvements': improvements}


def broader_replay(study):
    """Score the same fixed history rule on all eligible households in held-out folds."""
    ids, _, _, y, _ = load(study)
    groups = {household: np.flatnonzero(ids == household) for household in np.unique(ids)}
    eligible = [household for household, rows in groups.items() if len(rows) >= 3]
    rng = np.random.default_rng(SEED)
    per_household = []
    for test in np.array_split(rng.permutation(eligible), 5):
        rest = y[~np.isin(ids, test)]
        population = (rest.sum(axis=0) + .5) / (len(rest) + 2)
        rows = np.asarray([groups[household][:3] for household in test])
        histories = y[rows[:, :2]].mean(axis=1)
        truth = y[rows[:, 2]]
        own = (1 - HISTORY_WEIGHT) * population + HISTORY_WEIGHT * histories
        other = (1 - HISTORY_WEIGHT) * population + HISTORY_WEIGHT * np.roll(histories, 1, axis=0)
        per_household.extend(np.column_stack([
            np.sum((probabilities - truth) ** 2, axis=1)
            for probabilities in (population, own, other, histories)
        ]).tolist())
    errors = np.asarray(per_household)
    return {'households': len(errors), 'folds': 5,
            'brier': dict(zip(('population', 'own_history', 'other_history', 'history_only'), errors.mean(axis=0).tolist()))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    action = parser.parse_args().action
    data = {study: prepare(study) for study in DATASETS}
    jobs = [job for batch, _, _, _ in data.values() for job in batch.values()]
    random.Random(SEED).shuffle(jobs)
    RUN.mkdir(mode=0o700, exist_ok=True)
    frozen = RUN / 'jobs.json'
    if frozen.exists() and frozen.read_bytes() != encode(jobs):
        raise ValueError('Frozen history requests changed')
    if not frozen.exists():
        frozen.write_bytes(encode(jobs))
    if action == 'run':
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(partial(send, directory=RUN), jobs))
    identities, results = set(), {}
    for study, (batch, truth, statistical, coverage) in data.items():
        qwen = {arm: [] for arm in ARMS}
        for (_, arm), job in batch.items():
            result = read(result_path(job, RUN))
            if result['status'] != 'ok':
                raise ValueError(f'Invalid response for {study}: {result["type"]}')
            identities.add(json.dumps(result['identity'], sort_keys=True))
            p = result['p'][job['questions'][0]['id']]
            qwen[arm].append([p[str(i)] for i in range(1, 5)])
        results[study] = {**coverage, **score(truth, statistical, {k: np.asarray(v) for k, v in qwen.items()}),
                          'source_sha256': DATASETS[study][0], 'broader_statistical_replay': broader_replay(study)}
    if len(identities) != 1:
        raise ValueError('Qwen identity changed')
    print(json.dumps({'seed': SEED, 'conditions': list(ARMS), 'logical_requests': len(jobs),
                      'unique_requests': len({result_path(job, RUN) for job in jobs}),
                      'history_weight': HISTORY_WEIGHT,
                      'identity': json.loads(identities.pop()), 'studies': results}, indent=2))


if __name__ == '__main__':
    main()
