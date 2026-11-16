"""Compare a Qwen category ranking with historical popularity on real later baskets."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import json

import numpy as np

from grocery_next_basket import HASHES, load
from order_screen import SEED, WORK, encode, read, result_path
from protocol import MODELS
from retail_unseen_rerank import TOP, send_ranking

RUN = WORK / 'grocery-category-v1'
SIZE = 48


def prepare():
    categories, history, targets, _ = load()
    eligible = sorted(h for h in targets if len(history.get(h, [])) >= 2)
    rng = np.random.default_rng(SEED)
    test = rng.permutation(eligible)[::3]
    sampled = rng.choice(test, SIZE, replace=False)
    test_ids = set(test)
    frequency = Counter()
    for household, baskets in history.items():
        if household not in test_ids:
            for basket in baskets:
                frequency.update({categories[item] for item in basket})
    catalogue = sorted(frequency, key=lambda category: (-frequency[category], category))
    jobs, references = [], []
    for i, household in enumerate(sampled, 1):
        earlier = [{categories[item] for item in basket} for basket in history[household]]
        seen = set().union(*earlier)
        candidates = [category for category in catalogue if category not in seen][:20]
        popular = set(candidates[:TOP])
        rng.shuffle(candidates)
        question = {'id': f'case{i:02}', 'prompt': 'Which categories appear in the later basket?',
                    'options': {str(j): ' / '.join(value) for j, value in enumerate(candidates, 1)}}
        notes = '\n'.join('Order ' + str(j) + ': ' + '; '.join(' / '.join(x) for x in sorted(basket))
                          for j, basket in enumerate(earlier[-2:], 1))
        menu = '\n'.join(f'{key}. {value}' for key, value in question['options'].items())
        prompt = ('Predict which product categories this US supermarket household might try in a later basket. '
                  'Use these last two orders. Return only JSON with key ranking and exactly five distinct '
                  f'integer option numbers, most likely first.\n{notes}\nCandidates:\n{menu}')
        body = {'model': MODELS['qwen'], 'temperature': .7, 'top_p': 1,
                'max_tokens': 256, 'response_format': {'type': 'json_object'},
                'chat_template_kwargs': {'enable_thinking': False},
                'messages': [{'role': 'user', 'content': prompt}]}
        jobs.append({'questions': [question], 'body': body})
        actual = {categories[item] for item in targets[household]} - seen
        references.append((candidates, popular, actual))
    return jobs, references


def score(jobs, references):
    identities, rows = set(), []
    failures = Counter()
    coverage = 0
    for job, (candidates, popular, actual) in zip(jobs, references, strict=True):
        path = result_path(job, RUN)
        response = read(path) if path.exists() else {'status': 'error', 'type': 'missing'}
        if response['status'] != 'ok':
            failures[response['type']] += 1
            continue
        identities.add(json.dumps(response['identity'], sort_keys=True))
        picks = {candidates[i - 1] for i in response['ranking']}
        coverage += bool(actual.intersection(candidates))
        rows.append([len(actual & choices) for choices in (popular, picks)])
    if len(identities) != 1:
        raise ValueError('Unexpected model identity')
    values = np.asarray(rows)
    delta = values[:, 1] - values[:, 0]
    draws = np.random.default_rng(SEED).integers(len(delta), size=(2000, len(delta)))
    return {'sources': HASHES, 'requests': len(jobs), 'valid': len(rows),
            'failures': dict(failures), 'identity': json.loads(identities.pop()),
            'orders_with_target_in_candidates': coverage,
            'hits': dict(zip(('popular', 'qwen'), values.sum(axis=0).tolist(), strict=True)),
            'orders_with_hits': dict(zip(('popular', 'qwen'), (values > 0).sum(axis=0).tolist(), strict=True)),
            'delta_hits_per_order': float(delta.mean()),
            'interval_95': np.quantile(delta[draws].mean(axis=1), [.025, .975]).tolist()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    action = parser.parse_args().action
    jobs, references = prepare()
    RUN.mkdir(mode=0o700, exist_ok=True)
    manifest = RUN / 'jobs.json'
    if manifest.exists() and manifest.read_bytes() != encode(jobs):
        raise ValueError('Frozen requests changed')
    if not manifest.exists():
        manifest.write_bytes(encode(jobs))
    if action == 'run':
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(partial(send_ranking, directory=RUN), jobs))
    print(json.dumps(score(jobs, references), indent=2))
