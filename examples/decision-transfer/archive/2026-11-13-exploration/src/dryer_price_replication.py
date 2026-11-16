"""Compare learned and fixed own-price slopes on dryer choice cards."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from functools import partial
import json
import random
import re

import numpy as np
from scipy.special import softmax

import dryer_refusal as dryer
from optout_transfer import predictions
from order_screen import SEED, WORK, encode, send

RUN = WORK / 'dryer-own-price-v1'
CENTERS = {'USA': 900, 'CAN': 1000}
STEP = 200
FIXED_SLOPE = -np.log(2)
FLOOR = .005


def prepare():
    original, _, cohorts = dryer.deck()
    selected = {}
    jobs = {}
    rng = random.Random(SEED)
    for country, center in CENTERS.items():
        cards = []
        for key, job in sorted(original.items()):
            if not key.startswith(country + '-'):
                continue
            options = job['questions'][0]['options']
            prices = np.array([int(re.search(r'Price: [A-Z]+ (\d+)$', options[i])[1]) for i in ('1', '2')])
            # Hold out original scenarios that cannot coincide with an anchor or probe.
            if np.count_nonzero(prices != center) == 2:
                cards.append((key, prices))
        selected[country] = sorted(rng.sample(cards, 16), key=lambda row: row[0])
        for key, _ in selected[country]:
            for arm, amounts in [('anchor', [center, center]), ('first', [center + STEP, center]),
                                 ('second', [center, center + STEP])]:
                job = deepcopy(original[key])
                options = job['questions'][0]['options']
                message = job['body']['messages'][-1]
                for option, amount in zip(('1', '2'), amounts, strict=True):
                    label = options[option]
                    updated = re.sub(r'(Price: [A-Z]+ )\d+$', lambda m: m[1] + str(amount), label)
                    old_row = f'| `{option}` | {label} |'
                    if message['content'].count(old_row) != 1:
                        raise ValueError('Cannot find unique offer row')
                    message['content'] = message['content'].replace(old_row, f'| `{option}` | {updated} |')
                    options[option] = updated
                jobs[key, arm] = job
    return original, cohorts, selected, jobs


def score(original, cohorts, selected, jobs):
    raw, new_ids = predictions(jobs, RUN)
    prior, old_ids = predictions(original, dryer.RUN)
    if len(new_ids | old_ids) != 1:
        raise ValueError('Model identity changed')
    result = {}
    for country, cards in selected.items():
        truth = {key: Counter(row[key] for row in cohorts[country].values() if key in row) for key, _ in cards}
        losses = []
        positive_shares = positive_slopes = 0
        for key, prices in cards:
            options = ('1', '2', '0')
            anchor, first, second = [np.array([raw[key, arm][option] for option in options])
                                     for arm in ('anchor', 'first', 'second')]
            positive_shares += int(first[0] > anchor[0]) + int(second[1] > anchor[1])
            anchor_log = np.log(np.maximum(anchor, FLOOR))
            probe_log = np.log(np.maximum([first, second], FLOOR))
            slopes = probe_log[[0, 1], [0, 1]] - probe_log[:, 2] - (anchor_log[:2] - anchor_log[2])
            positive_slopes += int(np.sum(slopes > 0))
            change = (prices - CENTERS[country]) / STEP
            variants = [np.array([prior[key][option] for option in options]), anchor]
            fixed = np.r_[change * FIXED_SLOPE, 0.]
            for slope in (slopes, np.minimum(slopes, 0)):
                variants.append(softmax(anchor_log + np.r_[change * slope, 0.]))
            variants.append(softmax(anchor_log + fixed))
            # Post-hoc control: identical price rule, with equal odds at the reference price.
            variants.append(softmax(fixed))
            observed = np.array([truth[key][option] for option in options]) / sum(truth[key].values())
            losses.append(.5 * np.abs(np.asarray(variants) - observed).sum(axis=1))
        errors = np.asarray(losses)
        names = ('direct_qwen', 'anchor', 'learned', 'constrained', 'fixed', 'price_only')
        draws = np.random.default_rng(SEED).integers(len(errors), size=(2000, len(errors)))
        intervals = {}
        for a, b in [('direct_qwen', 'constrained'), ('learned', 'constrained'), ('constrained', 'fixed'),
                     ('direct_qwen', 'fixed'), ('price_only', 'fixed'), ('price_only', 'direct_qwen')]:
            delta = errors[:, names.index(a)] - errors[:, names.index(b)]
            intervals[b + '_over_' + a] = np.quantile(delta[draws].mean(axis=1), [.025, .975]).tolist()
        card_ids = set(truth)
        result[country] = {'cards': len(cards),
                           'people': sum(bool(card_ids.intersection(row)) for row in cohorts[country].values()),
                           'source_cohort_people': len(cohorts[country]),
                           'rise_in_own_share': positive_shares, 'positive_odds_slope': positive_slopes,
                           'distribution_tv': dict(zip(names, errors.mean(axis=0).tolist(), strict=True)),
                           'intervals_95': intervals}
    return {'seed': SEED, 'requests': len(jobs), 'unique_requests': len({encode(job) for job in jobs.values()}),
            'valid': len(raw), 'identity': json.loads(next(iter(new_ids))),
            'price_step': STEP, 'fixed_slope': float(FIXED_SLOPE), 'studies': result}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    action = parser.parse_args().action
    original, cohorts, selected, jobs = prepare()
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
            list(pool.map(partial(send, directory=RUN), batch))
    print(json.dumps(score(original, cohorts, selected, jobs), indent=2))
