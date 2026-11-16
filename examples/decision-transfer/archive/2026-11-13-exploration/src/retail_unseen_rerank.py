"""Check whether Qwen improves a fixed list of unseen next-order candidates."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from hashlib import sha256
import json
import random
import urllib.request

import numpy as np
import pandas as pd

from order_screen import WORK, SEED, URL, encode, read, result_path, send
import protocol
from retail_next_basket import CUTOFF, evaluate, read_orders

SOURCE = WORK / 'materials/online-retail/polito.csv'
RUN = WORK / 'retail-unseen-rerank-v1'
N = 60
TOP = 5


def catalogue_and_cases():
    frame = pd.read_csv(SOURCE, usecols=['StockCode', 'Description', 'InvoiceDate'])
    frame = frame.loc[pd.to_datetime(frame.InvoiceDate, format='mixed') < CUTOFF].dropna()
    labels = frame.groupby(['StockCode', 'Description']).size().reset_index(name='count')
    labels = labels.sort_values(['count', 'Description'], ascending=[False, True]).drop_duplicates('StockCode')
    names = dict(zip(labels.StockCode, labels.Description, strict=True))
    candidate_sets = {}
    evaluate(*read_orders(SOURCE)[:3], candidate_sets=candidate_sets)
    return names, candidate_sets


def prepare(ranking):
    names, candidate_sets = catalogue_and_cases()
    rng = random.Random(SEED)
    jobs, cases = [], []
    for customer in rng.sample(sorted(candidate_sets), N):
        before, related, popular, actual = candidate_sets[customer]
        candidates = list(dict.fromkeys([*related, *popular]))
        if len(candidates) < TOP or not all(item in names for item in candidates):
            raise ValueError('Unusable candidate set')
        rng.shuffle(candidates)
        lines = ['; '.join(names[item] for item in basket if item in names) for basket in before]
        context = 'The customer placed these two prior orders with a UK online gift retailer. '
        context += 'Older order: ' + lines[0] + '. More recent order: ' + lines[1] + '. '
        context += 'Rank the candidates by their likelihood of appearing in the later order. '
        context += 'Several or none may appear. Use normalized scores only to rank the options.'
        question = {'id': f'order{len(jobs) + 1:02}',
                    'prompt': 'Which of these products is most likely to appear in the later order?',
                    'options': {str(i): names[item] for i, item in enumerate(candidates, 1)}}
        body = protocol.build({'title': 'Later order product ranking', 'context': context,
                               'questions': [question], 'basic': {}}, 'basic', 'qwen', {}, {}, 768)
        if ranking:
            body['messages'][-1]['content'] = (
                context.split('Use normalized scores')[0]
                + ' Return a JSON object with one key, ranking, listing exactly five distinct integer '
                'option numbers from most likely to least likely. Candidates:\n'
                + '\n'.join(f'{key}. {name}' for key, name in question['options'].items())
            )
        jobs.append({'questions': [question], 'body': body})
        cases.append((candidates, related[:TOP], popular[:TOP], actual))
    return jobs, cases


def send_ranking(job, directory):
    path = result_path(job, directory)
    if path.exists():
        return
    marker = path.with_suffix('.pending')
    try:
        marker.touch(exist_ok=False)
    except FileExistsError:
        return
    try:
        request = urllib.request.Request(URL, data=encode(job['body']),
                                         headers={'Content-Type': 'application/json'})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=45) as response:
            raw = json.load(response)
        choice, = raw['choices']
        identity = {key: raw.get(key) for key in ('model', 'system_fingerprint')}
        message = choice['message']
        if identity['model'] != protocol.MODELS['qwen'] or choice['finish_reason'] != 'stop' or any(
            message.get(key) for key in ('reasoning_content', 'tool_calls')
        ):
            raise ValueError('Unexpected model identity or incomplete response')
        envelope = json.loads(message['content'])
        rank = envelope.get('ranking') if isinstance(envelope, dict) else None
        valid_ids = job['questions'][0]['options']
        if not isinstance(rank, list) or len(rank) != TOP or any(
            type(option) is not int or str(option) not in valid_ids for option in rank
        ) or len(set(rank)) != TOP or set(envelope) != {'ranking'}:
            raise ValueError('Invalid ranking')
        result = {'status': 'ok', 'ranking': rank, 'identity': identity}
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = {'status': 'error', 'type': type(error).__name__}
    temp = path.with_suffix('.tmp')
    temp.write_bytes(encode(result))
    temp.replace(path)
    marker.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    parser.add_argument('--probabilities', action='store_true')
    args = parser.parse_args()
    ranking = not args.probabilities
    directory = RUN.with_name('retail-unseen-rerank-v2') if ranking else RUN
    jobs, cases = prepare(ranking)
    directory.mkdir(mode=0o700, exist_ok=True)
    manifest = directory / 'jobs.json'
    if manifest.exists() and manifest.read_bytes() != encode(jobs):
        raise ValueError('Frozen candidate requests changed')
    if not manifest.exists():
        manifest.write_bytes(encode(jobs))
    if args.action == 'run':
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(partial(send_ranking if ranking else send, directory=directory), jobs))
    results, identities = [], set()
    coverage = 0
    for job, (options, related, popular, actual) in zip(jobs, cases, strict=True):
        result = read(result_path(job, directory))
        if result['status'] != 'ok':
            raise ValueError(result['type'])
        identities.add(json.dumps(result['identity'], sort_keys=True))
        if ranking:
            qwen = [options[i - 1] for i in result['ranking']]
        else:
            p = result['p'][job['questions'][0]['id']]
            ranked = sorted(enumerate(options, 1), key=lambda pair: (-p[str(pair[0])], pair[0]))
            qwen = [item for _, item in ranked[:TOP]]
        coverage += bool(actual.intersection(options))
        results.append([len(actual.intersection(items)) for items in (popular, related, qwen)])
    if len(identities) != 1:
        raise ValueError('Model identity changed')
    values = np.asarray(results)
    delta = values[:, 2] - values[:, 1]
    rng = np.random.default_rng(SEED)
    indices = rng.integers(len(values), size=(2000, len(values)))
    print(json.dumps({'source_sha256': sha256(SOURCE.read_bytes()).hexdigest(),
                      'output': 'ranking' if ranking else 'probabilities',
                      'seed': SEED, 'valid_requests': len(values), 'top_k': TOP,
                      'identity': json.loads(identities.pop()),
                      'orders_with_any_target_in_candidates': coverage,
                      'hits': dict(zip(('popular', 'related', 'qwen'), values.sum(axis=0).tolist())),
                      'orders_with_hit': dict(zip(('popular', 'related', 'qwen'),
                                                  (values > 0).sum(axis=0).tolist())),
                      'qwen_minus_related_hits_per_order_interval_95':
                          np.quantile(delta[indices].mean(axis=1), [.025, .975]).tolist()}, indent=2))


if __name__ == '__main__':
    main()
