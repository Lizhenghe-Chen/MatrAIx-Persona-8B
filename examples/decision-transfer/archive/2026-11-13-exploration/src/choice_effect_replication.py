"""Replay direct versus differenced estimates of changes in product choice."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from functools import partial
import json
import random

import numpy as np

from order_screen import SEED, WORK, encode, read, result_path, send
from paired_scenario_screen import beef_cases, beer_cases
from pepper_effect_repeats import parse_change
import protocol

RUN = WORK / 'choice-effect-replication-v1'


def prepare(cases):
    jobs = {}
    for study, cards in cases.items():
        for question, context, control, treatment, _, _ in cards:
            key = question['id']
            ids = tuple(question['options'])
            pair = [{**question, 'id': f'{key}-{i}', 'prompt': f'{condition}\n{question["prompt"]}'}
                    for i, condition in enumerate((control, treatment), 1)]
            body = protocol.build({'title': 'Product choice forecast', 'context': context,
                                   'questions': pair, 'basic': {}}, 'basic', 'qwen', {}, {}, 768,
                                  preamble='Compare the two scenarios and estimate how participants choose.')
            direct = deepcopy(body)
            content = direct['messages'][-1]['content'].split('## Answer envelope', 1)[0]
            example = dict.fromkeys(ids, 0)
            example[ids[0]], example[ids[1]] = 2, -2
            direct['messages'][-1]['content'] = content + (
                '## Answer envelope\nPredict the change from scenario 1 to scenario 2 for each option. '
                'Return only a JSON object with a changes field containing signed percentage-point changes '
                'keyed by each exact option ID. The values must sum to zero and each must be in [-100, 100]. '
                f'Example format: {json.dumps({"changes": example})}.'
            )
            for arm, request in [('joint', body), ('direct', direct)]:
                for draw in range(2):
                    jobs[study, key, arm, draw] = {'study': study, 'arm': arm, 'draw': draw,
                                                  'questions': pair, 'body': request}
    return jobs


def dispatch(job):
    parser = partial(parse_change, ids=tuple(job['questions'][0]['options']))
    send(job, RUN, parser if job['arm'] == 'direct' else None)


def score(cases, jobs):
    results, identities = {}, set()
    retries = recovered = 0
    for study, cards in cases.items():
        errors, truth, estimates, focus_masks = {}, [], [], []
        for question, _, _, _, counts, focus in cards:
            key, ids = question['id'], tuple(question['options'])
            observed = np.array([[group[i] / sum(group.values()) for i in ids] for group in counts])
            values = []
            for arm in ('joint', 'direct'):
                draws = []
                for draw in range(2):
                    job = jobs[study, key, arm, draw]
                    reply = read(result_path(job, RUN))
                    if reply['status'] != 'ok':
                        error = f'{arm}/{reply["type"]}'
                        errors[error] = errors.get(error, 0) + 1
                        retry = result_path({**job, 'attempt': 2}, RUN)
                        if not retry.exists():
                            continue
                        retries += 1
                        reply = read(retry)
                        if reply['status'] != 'ok':
                            continue
                        recovered += 1
                    identities.add(json.dumps(reply['identity'], sort_keys=True))
                    if arm == 'joint':
                        draws.append([reply['p'][f'{key}-2'][i] - reply['p'][f'{key}-1'][i] for i in ids])
                    else:
                        draws.append(reply['change'])
                values.append(draws)
            if all(len(draws) == 2 for draws in values):
                truth.append(observed[1] - observed[0])
                estimates.append(values)
                focus_masks.append([i in focus for i in ids])
        result = {'planned_cards': len(cards), 'common_cards': len(truth), 'errors': errors}
        results[study] = result
        if len(truth) < .98 * len(cards):
            continue
        truth, estimates, focus_masks = map(np.asarray, (truth, estimates, focus_masks))
        avg = estimates.mean(axis=2)
        baseline = .5 * np.abs(truth).sum(axis=1)
        loss = .5 * np.abs(avg - truth[:, None]).sum(axis=2)
        rng = np.random.default_rng(SEED)
        draws = rng.integers(len(truth), size=(2000, len(truth)))
        result['unchanged_error'] = float(baseline.mean())
        result['actual_no_purchase_change'] = float((truth * focus_masks).sum(axis=1).mean())
        for j, name in enumerate(('joint', 'direct')):
            result[name] = {
                'average_single_error': float(.5 * np.abs(estimates[:, j] - truth[:, None]).sum(axis=2).mean()),
                'two_draw_error': float(loss[:, j].mean()),
                'repeat_gap': float(.5 * np.abs(estimates[:, j, 0] - estimates[:, j, 1]).sum(axis=1).mean()),
                'no_purchase_change': float((avg[:, j] * focus_masks).sum(axis=1).mean()),
                'gain_over_unchanged_interval_95': np.quantile((baseline - loss[:, j])[draws].mean(axis=1),
                                                              [.025, .975]).tolist(),
            }
        result['direct_over_joint_interval_95'] = np.quantile(
            (loss[:, 0] - loss[:, 1])[draws].mean(axis=1), [.025, .975]).tolist()
    if len(identities) != 1 or json.loads(next(iter(identities)))['model'] != protocol.MODELS['qwen']:
        raise ValueError('Unexpected model identity')
    return {'seed': SEED, 'planned_calls': len(jobs), 'retry_calls': retries, 'recovered': recovered,
            'identity': json.loads(next(iter(identities))),
            'studies': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    action = parser.parse_args().action
    cases = {'beef': beef_cases(), 'beer': beer_cases()}
    jobs = prepare(cases)
    batch = list(jobs.values())
    random.Random(SEED).shuffle(batch)
    RUN.mkdir(mode=0o700, exist_ok=True)
    manifest = RUN / 'jobs.json'
    if manifest.exists() and manifest.read_bytes() != encode(batch):
        raise ValueError('Frozen requests changed')
    if not manifest.exists():
        manifest.write_bytes(encode(batch))
    if action == 'run':
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(dispatch, batch))
            failed = [{**job, 'attempt': 2} for job in batch
                      if read(result_path(job, RUN))['status'] != 'ok']
            list(pool.map(dispatch, failed))
    print(json.dumps(score(cases, jobs), indent=2))


if __name__ == '__main__':
    main()
