"""Test whether Qwen predicts a difference between two real survey conditions."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import json
import random

import numpy as np

from optout_transfer import predictions
from order_screen import SEED, WORK, encode, read, result_path, send
import protocol
import taiwan_pepper as pepper

RUN = WORK / 'taiwan-pepper-information-v1'
JOINT_RUN = WORK / 'taiwan-pepper-information-joint-v1'
NOTICE = ('無論在台灣販售的有機產品產自何處，均適用相同的規範和管理程序。'
          '在台灣以有機標示販售的產品必須符合台灣有機生產規範，沒有例外。')


def prepare(original):
    jobs = {}
    for key, job in original.items():
        question = job['questions'][0]
        for condition in ('control', 'notice'):
            context = pepper.CONTEXT if condition == 'control' else f'{NOTICE}\n\n{pepper.CONTEXT}'
            body = protocol.build({'title': '台灣消費者之甜椒選擇', 'context': context,
                                   'questions': [question], 'basic': {}}, 'basic', 'qwen', {}, {}, 512)
            if condition == 'control' and body != job['body']:
                raise ValueError('Control no longer matches prior round')
            jobs[key, condition] = {'questions': [question], 'body': body, 'condition': condition}
    return jobs


def joint_jobs(original):
    jobs = {}
    for key, job in original.items():
        question = job['questions'][0]
        pair = [{**question, 'id': f'{key}-{i}', 'prompt': f'{condition}\n{question["prompt"]}'}
                for i, condition in enumerate(('受訪者未收到額外說明。', NOTICE), 1)]
        body = protocol.build({'title': '台灣消費者之甜椒選擇', 'context': pepper.CONTEXT,
                               'questions': pair, 'basic': {}}, 'basic', 'qwen', {}, {}, 512,
                              preamble='請比較兩種情境，估計每種情境下各個選項的受訪者比例。')
        jobs[key] = {'questions': pair, 'body': body}
    return jobs


def observed(cards, people, rng):
    boot, point = [], []
    for block in range(1, 7):
        keys = [key for key in cards if key.startswith(f'b{block}')]
        answers = np.asarray([[int(row[key]) - 1 for key in keys] for row in people if keys[0] in row])
        one_hot = np.eye(4)[answers]
        point.append(one_hot.mean(axis=0))
        draws = rng.integers(len(answers), size=(2000, len(answers)))
        boot.append(one_hot[draws].mean(axis=1))
    return np.concatenate(point), np.concatenate(boot, axis=1)


def score(original, jobs):
    new, new_ids = predictions(jobs, RUN)
    old, old_ids = predictions(original, pepper.RUN)
    if len(new_ids | old_ids) != 1:
        raise ValueError('Mixed model versions')
    cards = list(original)
    rng = np.random.default_rng(SEED)
    control, control_boot = observed(cards, pepper.observed_group(original, '0'), rng)
    notice, notice_boot = observed(cards, pepper.observed_group(original, '1'), rng)
    ids = tuple('1234')
    model = {condition: np.asarray([[new[key, condition][i] for i in ids] for key in cards])
             for condition in ('control', 'notice')}
    prior_control = np.asarray([[old[key][i] for i in ids] for key in cards])
    human_effect = notice - control
    human_boot = notice_boot - control_boot
    model_effect = model['notice'] - model['control']
    joint = []
    for key, job in joint_jobs(original).items():
        reply = read(result_path(job, JOINT_RUN))
        if reply['status'] != 'ok' or json.dumps(reply['identity'], sort_keys=True) not in new_ids:
            raise ValueError('Invalid joint result')
        joint.append([[reply['p'][f'{key}-{arm}'][i] for i in ids] for arm in (1, 2)])
    joint = np.asarray(joint)
    joint_effect = joint[:, 1] - joint[:, 0]
    changes = {'unchanged': np.zeros_like(model_effect), 'qwen': model_effect,
               'quarter_qwen': .25 * model_effect, 'joint_qwen': joint_effect,
               'quarter_joint_qwen': .25 * joint_effect}
    errors = {k: float(.5 * np.abs(v - human_effect).sum(axis=1).mean()) for k, v in changes.items()}
    baseline_boot = .5 * np.abs(human_boot).sum(axis=2).mean(axis=1)
    gain_intervals = {
        k: np.quantile(baseline_boot - .5 * np.abs(v - human_boot).sum(axis=2).mean(axis=1),
                       [.025, .975]).tolist() for k, v in changes.items() if k != 'unchanged'
    }
    endpoints = {'no_purchase': [[False, False, False, True]] * len(cards)}
    for origin in ('台灣', '日本', '中國'):
        endpoints[origin + '_organic'] = [
            [f'產地：{origin}' in label and '有機生產' in label
             for label in original[key]['questions'][0]['options'].values()] for key in cards]
    return {'identity': json.loads(next(iter(new_ids))), 'requests': len(jobs) + len(joint),
            'valid': len(new) + len(joint), 'cards': len(cards), 'people': {'control': 526, 'notice': 361},
            'mean_effect_error': errors,
            'improvement_over_unchanged_interval_95': gain_intervals,
            'qwen_notice_vs_control_tv': float(.5 * np.abs(model_effect).sum(axis=1).mean()),
            'qwen_control_repeat_tv': float(.5 * np.abs(model['control'] - prior_control).sum(axis=1).mean()),
            'endpoints': {key: {'human': float((human_effect * mask).sum(axis=1).mean()),
                                'human_interval_95': np.quantile((human_boot * mask).sum(axis=2).mean(axis=1),
                                                                 [.025, .975]).tolist(),
                                'qwen': float((model_effect * mask).sum(axis=1).mean()),
                                'joint_qwen': float((joint_effect * mask).sum(axis=1).mean())}
                          for key, mask in endpoints.items()},
            'card_results': {key: {'human_control': control[i].tolist(), 'human_notice': notice[i].tolist(),
                                   'qwen_control': model['control'][i].tolist(),
                                   'qwen_notice': model['notice'][i].tolist(),
                                   'joint_control': joint[i, 0].tolist(), 'joint_notice': joint[i, 1].tolist()}
                             for i, key in enumerate(cards)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    args = parser.parse_args()
    original = pepper.deck()
    jobs = prepare(original)
    batch = list(jobs.values())
    random.Random(SEED).shuffle(batch)
    RUN.mkdir(mode=0o700, exist_ok=True)
    manifest = RUN / 'jobs.json'
    if manifest.exists() and manifest.read_bytes() != encode(batch):
        raise ValueError('Frozen requests changed')
    if not manifest.exists():
        manifest.write_bytes(encode(batch))
    if args.action == 'run':
        JOINT_RUN.mkdir(mode=0o700, exist_ok=True)
        joint = list(joint_jobs(original).values())
        random.Random(SEED).shuffle(joint)
        joint_manifest = JOINT_RUN / 'jobs.json'
        if joint_manifest.exists() and joint_manifest.read_bytes() != encode(joint):
            raise ValueError('Frozen joint requests changed')
        if not joint_manifest.exists():
            joint_manifest.write_bytes(encode(joint))
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(partial(send, directory=RUN), batch))
            list(pool.map(partial(send, directory=JOINT_RUN), joint))
    print(json.dumps(score(original, jobs), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
