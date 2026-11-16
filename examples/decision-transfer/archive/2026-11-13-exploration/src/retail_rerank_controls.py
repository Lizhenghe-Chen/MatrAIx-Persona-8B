"""Test whether a candidate reranker benefits from correctly matched order history."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from hashlib import sha256
import json
import math
import random
import re

import numpy as np

from order_screen import WORK, SEED, encode, read, result_path
from retail_unseen_rerank import SOURCE, N as PRIOR_N, TOP, catalogue_and_cases, send_ranking
import protocol

RUN = WORK / 'retail-rerank-controls-v1'
N = 96
ARMS = ('own', 'other', 'none')
SOURCE_HASH = 'c41dc0c7e3b6eef34ddd36a6813171dafda799ab4880476fc79a9db69248a53e'


def tokenize(name):
    return set(re.findall(r'[a-z0-9]+', name.lower()))


def prepare():
    if sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_HASH:
        raise ValueError('Unexpected source version')
    names, all_cases = catalogue_and_cases()
    all_ids = sorted(all_cases)
    prior_ids = set(random.Random(SEED).sample(all_ids, PRIOR_N))
    rng = random.Random(SEED + 1)
    ids = rng.sample([key for key in all_ids if key not in prior_ids], N)
    donors = ids.copy()
    rng.shuffle(donors)
    donor_for = dict(zip(donors, donors[1:] + donors[:1], strict=True))
    words = {item: tokenize(name) for item, name in names.items()}
    counts = Counter(word for tokens in words.values() for word in tokens)
    weights = {word: math.log1p(len(names) / count) for word, count in counts.items()}

    def history_text(baskets):
        lines = ['; '.join(names[item] for item in basket) for basket in baskets]
        return f'Older order: {lines[0]}. More recent order: {lines[1]}. '

    jobs, cases = [], []
    for i, customer in enumerate(ids, 1):
        baskets, related, popular, actual = all_cases[customer]
        other = all_cases[donor_for[customer]][0]
        candidates = list(dict.fromkeys([*related, *popular]))
        rng.shuffle(candidates)
        question = {'id': f'case{i:03}', 'prompt': 'Which items will appear in the later order?',
                    'options': {str(k): names[item] for k, item in enumerate(candidates, 1)}}
        candidate_text = '\n'.join(f'{key}. {name}' for key, name in question['options'].items())
        histories = {'own': history_text(baskets), 'other': history_text(other), 'none': ''}
        for arm in ARMS:
            prompt = ('Predict products in a later order at a UK online gift retailer. '
                      + histories[arm]
                      + 'Several or none may appear. Return only a JSON object with the key ranking '
                      'and exactly five distinct integer candidate numbers in descending likelihood.\n'
                      + candidate_text)
            body = {'model': protocol.MODELS['qwen'], 'temperature': .7, 'top_p': 1,
                    'max_tokens': 256, 'response_format': {'type': 'json_object'},
                    'chat_template_kwargs': {'enable_thinking': False},
                    'messages': [{'role': 'user', 'content': prompt}]}
            jobs.append({'questions': [question], 'body': body, 'case': i, 'arm': arm})

        history_words = set().union(*(words[item] for basket in baskets for item in basket))
        lexical = sorted(candidates,
                         key=lambda item: (-sum(weights[word] for word in sorted(words[item] & history_words)), item))
        fused = Counter()
        for ranking in (related, popular):
            for position, item in enumerate(ranking, 1):
                fused[item] += 1 / (10 + position)
        cases.append((candidates, actual, {'related': related[:TOP], 'popular': popular[:TOP],
                                          'lexical': lexical[:TOP], 'input_order': candidates[:TOP],
                                          'fused': sorted(fused, key=lambda item: (-fused[item], item))[:TOP]}))
    rng.shuffle(jobs)
    return jobs, cases


def score(jobs, cases):
    responses, identities, failures = {}, set(), Counter()
    for job in jobs:
        path = result_path(job, RUN)
        result = read(path) if path.exists() else {'status': 'error', 'type': 'missing'}
        if result['status'] != 'ok':
            failures[job['arm'], result['type']] += 1
            continue
        responses[job['case'], job['arm']] = result['ranking']
        identities.add(json.dumps(result['identity'], sort_keys=True))
    if len(identities) != 1:
        raise ValueError('Missing or mixed model identity')
    baselines_names = ('related', 'popular', 'lexical', 'input_order', 'fused')
    names = (*baselines_names, *ARMS)
    rows = []
    covered = 0
    oracle_hits = 0
    for i, (candidates, actual, baselines) in enumerate(cases, 1):
        if not all((i, arm) in responses for arm in ARMS):
            continue
        possible = len(actual.intersection(candidates))
        covered += bool(possible)
        oracle_hits += min(TOP, possible)
        picks = {**baselines, **{arm: [candidates[j - 1] for j in responses[i, arm]] for arm in ARMS}}
        rows.append([len(actual.intersection(picks[name])) for name in names])
    values = np.asarray(rows)
    if not len(values):
        raise ValueError('No complete paired cases')
    boot = np.random.default_rng(SEED).integers(len(values), size=(2000, len(values)))
    comparisons = {}
    for base in (*baselines_names, 'other', 'none'):
        delta = values[:, names.index('own')] - values[:, names.index(base)]
        comparisons[f'own_minus_{base}'] = {
            'hits_per_order': float(delta.mean()),
            'interval_95': np.quantile(delta[boot].mean(axis=1), [.025, .975]).tolist(),
        }
    return {'source_sha256': SOURCE_HASH, 'seed': SEED + 1, 'expected_requests': len(jobs),
            'valid_requests': len(responses), 'failures': {f'{a}/{b}': n for (a, b), n in failures.items()},
            'paired_orders': len(values), 'candidate_coverage_orders': covered,
            'oracle_top_five_hits': oracle_hits,
            'identity': json.loads(identities.pop()),
            'hits': dict(zip(names, values.sum(axis=0).tolist(), strict=True)),
            'orders_with_hit': dict(zip(names, (values > 0).sum(axis=0).tolist(), strict=True)),
            'comparisons': comparisons}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    action = parser.parse_args().action
    jobs, cases = prepare()
    RUN.mkdir(mode=0o700, exist_ok=True)
    manifest = RUN / 'jobs.json'
    if manifest.exists() and manifest.read_bytes() != encode(jobs):
        raise ValueError('Frozen candidate requests changed')
    if not manifest.exists():
        manifest.write_bytes(encode(jobs))
    if action == 'run':
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(partial(send_ranking, directory=RUN), jobs))
    print(json.dumps(score(jobs, cases), indent=2))


if __name__ == '__main__':
    main()
