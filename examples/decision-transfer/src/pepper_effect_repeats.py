"""Compare direct effects and joint probabilities with two calls per method."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from functools import partial
import json
import random

import numpy as np

from order_screen import SEED, WORK, encode, read, result_path, send
import taiwan_pepper as pepper
from taiwan_pepper_information import joint_jobs, observed

RUN = WORK / 'pepper-effect-repeats-v1'
IDS = tuple('1234')
DRAWS = 2


def build(cards):
    jobs = {}
    for key, joint in joint_jobs(cards).items():
        direct = deepcopy(joint)
        message = direct['body']['messages'][-1]
        content = message['content'].split('## Answer envelope', 1)[0]
        message['content'] = content + (
            '## 輸出格式\n直接預測由情境一到情境二，各選項的比例改變多少。'
            '只回傳 JSON 物件，唯一欄位為 changes，內含選項 1、2、3、4 的帶正負號百分點變化。'
            '四個數值之和必須為零，且每個數值在 -100 到 100 之間。'
            '例如 {"changes":{"1":2,"2":-2,"3":0,"4":0}}。'
        )
        for name, body in [('joint', joint), ('direct', direct)]:
            for draw in range(DRAWS):
                jobs[key, name, draw] = {**body, 'arm': name, 'draw': draw}
    return jobs


def parse_change(raw, ids=IDS):
    choice, = raw['choices']
    message = choice['message']
    if choice['finish_reason'] != 'stop' or message.get('reasoning_content') or message.get('tool_calls'):
        raise ValueError('Incomplete or unexpected response')
    data = json.loads(message['content'])
    if set(data) != {'changes'} or set(data['changes']) != set(ids):
        raise ValueError('Incorrect change fields')
    values = [data['changes'][k] for k in ids]
    if any(type(x) not in (int, float) or not np.isfinite(x) or abs(x) > 100 for x in values):
        raise ValueError('Invalid change magnitude')
    if abs(sum(values)) > .05:
        raise ValueError('Changes must sum to zero')
    return {'status': 'ok', 'change': [x / 100 for x in values],
            'identity': {k: raw.get(k) for k in ('model', 'system_fingerprint')}}


def dispatch(job):
    send(job, RUN, parse_change if job['arm'] == 'direct' else None)


def score(cards, jobs):
    rng = np.random.default_rng(SEED)
    a, a_boot = observed(cards, pepper.observed_group(cards, '0'), rng)
    b, b_boot = observed(cards, pepper.observed_group(cards, '1'), rng)
    human = b - a
    boot = b_boot - a_boot
    effects, errors, identities = {}, {}, set()
    for name in ('joint', 'direct'):
        effects[name] = {}
        errors[name] = {}
        for key in cards:
            rows = []
            for draw in range(DRAWS):
                path = result_path(jobs[key, name, draw], RUN)
                result = read(path) if path.exists() else {'status': 'error', 'type': 'missing'}
                if result['status'] != 'ok':
                    kind = result['type']
                    errors[name][kind] = errors[name].get(kind, 0) + 1
                    continue
                identities.add(json.dumps(result['identity'], sort_keys=True))
                if name == 'joint':
                    rows.append([result['p'][f'{key}-2'][i] - result['p'][f'{key}-1'][i] for i in IDS])
                else:
                    rows.append(result['change'])
            if len(rows) == DRAWS:
                effects[name][key] = rows
    if len(identities) != 1 or json.loads(next(iter(identities)))['model'] != 'Qwen/Qwen3.8-27B':
        raise ValueError('Unexpected model identity')
    common = [key for key in cards if all(key in effect for effect in effects.values())]
    idx = [i for i, key in enumerate(cards) if key in common]
    result = {'cards': len(cards), 'common_cards': len(common), 'errors': errors,
              'identity': json.loads(next(iter(identities))), 'new_calls': len(jobs)}
    if len(common) < .98 * len(cards):
        return result
    baseline = .5 * np.abs(boot[:, idx]).sum(axis=2).mean(axis=1)
    result['unchanged_error'] = float(.5 * np.abs(human[idx]).sum(axis=1).mean())
    bootstrap_losses = {}
    for name, effect in effects.items():
        values = np.asarray([effect[key] for key in common])
        avg = values.mean(axis=1)
        model_loss = .5 * np.abs(avg - human[idx]).sum(axis=1).mean()
        bootstrap_losses[name] = .5 * np.abs(avg - boot[:, idx]).sum(axis=2).mean(axis=1)
        gain = baseline - bootstrap_losses[name]
        result[name] = {
            'average_single_error': float(.5 * np.abs(values - human[idx, None]).sum(axis=2).mean()),
            'two_draw_error': float(model_loss),
            'repeat_gap': float(.5 * np.abs(values[:, 0] - values[:, 1]).sum(axis=1).mean()),
            'gain_over_unchanged_interval_95': np.quantile(gain, [.025, .975]).tolist(),
            'mean_no_purchase_effect': float(avg[:, 3].mean()),
        }
    result['direct_over_joint_interval_95'] = np.quantile(
        bootstrap_losses['joint'] - bootstrap_losses['direct'], [.025, .975]).tolist()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    action = parser.parse_args().action
    cards = pepper.deck()
    jobs = build(cards)
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
    print(json.dumps(score(cards, jobs), indent=2))


if __name__ == '__main__':
    main()
