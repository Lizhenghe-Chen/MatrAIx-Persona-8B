"""Compare single-person probability and group forecasts on fixed choice cards."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from functools import partial
import json
import random
import urllib.request

import numpy as np

from optout_transfer import beer_deck, german_deck
from order_screen import SEED, URL, WORK, encode, read, result_path
import protocol

RUN = WORK / 'group-frequency-v1'
ARMS = ('individual', 'group_probability', 'group_count')
INDIVIDUAL = 'Estimate the probability that one randomly selected participant chooses each option.'
GROUP_PROBABILITY = 'Estimate the proportion of participants who choose each option.'
GROUP_COUNT = 'Out of 100 participants, estimate how many choose each option.'


def prepare():
    studies = {'beer': beer_deck(), 'tomato': german_deck()}
    return studies, build_jobs(studies)


def build_jobs(studies):
    jobs = []
    for study, (deck, _) in studies.items():
        for index, job in enumerate(deck.values()):
            for arm, instruction in zip(ARMS, (INDIVIDUAL, GROUP_PROBABILITY, GROUP_COUNT), strict=True):
                body = deepcopy(job['body'])
                message = body['messages'][-1]
                content = message['content']
                start, end = content.index('## Context'), content.index('## Answer envelope')
                common = content[start:end]
                envelope = content[end:]
                if arm == 'group_count':
                    envelope = ('## Answer envelope\nReturn JSON with only answers: a list of objects '
                                'with questionId and counts. counts is an object keyed by every exact '
                                'choice id. Use nonnegative integers adding to exactly 100. '
                                'Return no explanation.')
                message['content'] = instruction + ' Use the context and options below.\n\n' + common + envelope
                jobs.append({'study': study, 'cell': index, 'arm': arm, 'body': body,
                             'questions': job['questions']})
    random.Random(SEED).shuffle(jobs)
    return jobs


def send(job, directory=RUN):
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
        if job['arm'] == 'group_count':
            choice, = raw['choices']
            message = choice['message']
            document = json.loads(message['content'])
            row, = document['answers']
            counts = row['counts']
            if set(document) != {'answers'} or set(row) != {'questionId', 'counts'} or not all(
                type(n) is int and n >= 0 for n in counts.values()
            ) or sum(counts.values()) != 100:
                raise ValueError('Invalid integer counts')
            message['content'] = json.dumps({'answers': [{'questionId': row['questionId'],
                                                         'probabilities': {key: n / 100 for key, n in counts.items()}}]})
        parsed = protocol.parse(raw, job['questions'], 'qwen')
        q, = job['questions']
        probabilities = dict(zip(q['options'], parsed['probabilities'][q['id']], strict=True))
        record = {'status': 'ok', 'p': probabilities, 'identity': parsed['identity']}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        record = {'status': 'error', 'type': type(error).__name__}
    temporary = path.with_suffix('.tmp')
    temporary.write_bytes(encode(record))
    temporary.replace(path)
    marker.unlink()


def score(studies, jobs, directory=RUN, refusal_ids=None, *, include_uniform=False):
    refusal_ids = refusal_ids or {}
    estimates, failures, identities = {}, Counter(), set()
    for job in jobs:
        path = result_path(job, directory)
        result = read(path) if path.exists() else {'status': 'error', 'type': 'missing'}
        if result['status'] != 'ok':
            failures[f"{job['study']}/{job['arm']}/{result['type']}"] += 1
            continue
        estimates[job['study'], job['cell'], job['arm']] = result['p']
        identities.add(json.dumps(result['identity'], sort_keys=True))
    if len(identities) != 1:
        raise ValueError('Expected one model fingerprint')
    output = {}
    for study, (deck, people) in studies.items():
        truth = defaultdict(Counter)
        for person in people:
            for key, choice in person.items():
                truth[key][choice] += 1
        clusters = defaultdict(list)
        pairs = [(0, 1), (1, 2), (0, 2)]
        pairwise = {pair: defaultdict(lambda: np.zeros(2)) for pair in pairs}
        paired = 0
        fallback_tv = np.zeros(len(ARMS))
        total_choices = 0
        uniform_tv = 0.
        for i, key in enumerate(deck):
            options = sorted(deck[key]['questions'][0]['options'])
            refusal_index = options.index(refusal_ids.get(study, '0'))
            n = sum(truth[key].values())
            human = np.array([truth[key][option] / n for option in options])
            card = key[-1] if isinstance(key, tuple) else key
            available = {j: np.array([estimates[study, i, arm][option] for option in options])
                         for j, arm in enumerate(ARMS) if (study, i, arm) in estimates}
            for arm_index in range(len(ARMS)):
                forecast = available.get(arm_index, np.full(len(options), 1 / len(options)))
                fallback_tv[arm_index] += n * .5 * np.abs(forecast - human).sum()
            total_choices += n
            for a, b in pairs:
                if a in available and b in available:
                    gain = .5 * (np.abs(available[a] - human).sum() - np.abs(available[b] - human).sum())
                    pairwise[a, b][card] += [n * gain, n]
            if len(available) != len(ARMS):
                continue
            p = np.array(list(available.values()))
            tv = .5 * np.abs(p - human).sum(axis=1)
            brier = (p ** 2).sum(axis=1) - 2 * (p @ human) + 1
            clusters[card].append(np.r_[n, n * np.r_[tv, brier, p[:, refusal_index], human[refusal_index]]])
            paired += 1
            uniform_tv += n * .5 * np.abs(1 / len(options) - human).sum()
        rows = np.array([np.sum(values, axis=0) for values in clusters.values()])
        n, *total = rows.sum(axis=0)
        means = np.asarray(total) / n
        draws = np.random.default_rng(SEED).integers(len(rows), size=(2000, len(rows)))
        samples = rows[draws].sum(axis=1)
        boot = samples[:, 1:] / samples[:, :1]
        intervals, available_pairs = {}, {}
        for label, a, b in [('group_probability_vs_individual', 0, 1),
                            ('group_count_vs_group_probability', 1, 2),
                            ('group_count_vs_individual', 0, 2)]:
            intervals[label] = np.quantile(boot[:, a] - boot[:, b], [.025, .975]).tolist()
            data = np.array(list(pairwise[a, b].values()))
            sums = data[np.random.default_rng(SEED).integers(len(data), size=(2000, len(data)))].sum(axis=1)
            available_pairs[label] = {'choices': int(data[:, 1].sum()),
                                      'gain': float(data[:, 0].sum() / data[:, 1].sum()),
                                      'interval_95': np.quantile(sums[:, 0] / sums[:, 1], [.025, .975]).tolist()}
        output[study] = {'people_in_dataset': len(people), 'paired_cells': paired,
                         'paired_choices': int(n), 'card_clusters': len(rows), 'total_choices': total_choices,
                         'all_cells_tv_uniform_on_failure': dict(zip(ARMS, (fallback_tv / total_choices).tolist(),
                                                                    strict=True)),
                         'distribution_tv': dict(zip(ARMS, means[:3].tolist(), strict=True)),
                         'brier': dict(zip(ARMS, means[3:6].tolist(), strict=True)),
                         'refusal': dict(zip((*ARMS, 'human'), means[6:].tolist(), strict=True)),
                         'distribution_gain_interval_95': intervals, 'pairwise_available': available_pairs}
        if include_uniform:
            output[study]['paired_uniform_tv'] = uniform_tv / n
    return {'requests': len(jobs), 'valid': len(estimates), 'failures': dict(failures),
            'identity': json.loads(identities.pop()), 'studies': output}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    action = parser.parse_args().action
    studies, jobs = prepare()
    RUN.mkdir(mode=0o700, exist_ok=True)
    manifest = RUN / 'jobs.json'
    if manifest.exists() and manifest.read_bytes() != encode(jobs):
        raise ValueError('Frozen requests changed')
    if not manifest.exists():
        manifest.write_bytes(encode(jobs))
    if action == 'run':
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(send, jobs))
    print(json.dumps(score(studies, jobs), indent=2))
