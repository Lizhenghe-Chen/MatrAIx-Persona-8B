"""Transfer product trade-offs and update the opt-out rate in UK and Ireland."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from hashlib import sha256
import json
import re

import numpy as np
from scipy.special import softmax

from dryer_refusal import SOURCE, outcome, predictions
from dryer_unseen_transfer import BUDGETS, contrast, retained
from optout_pilot import REPEATS, SEED, fit_products, losses, split_cards
from order_screen import WORK, encode, read, send
import protocol

RUN = WORK / 'dryer-refusal-transfer-v1'
COUNTRIES = {'UK': ('GBP', 220), 'IRE': ('EUR', 198)}
ENERGY = ('C', 'B', 'A', 'A+', 'A++', 'A+++')
PRIOR_PEOPLE = 10


def load():
    jobs, cards = {}, {}
    people = {country: {} for country in COUNTRIES}
    for row in read(SOURCE)['rows']:
        country = row['country']
        if country not in COUNTRIES or row['treatment'] != 'C':
            continue
        currency, _ = COUNTRIES[country]
        key = f"{country}-{int(row['task']):02d}"
        a, b, optout = row['options']
        if optout != 'Neither' or row['answer'] not in (0, 1, 2):
            raise ValueError('Unexpected response mapping')
        question = {'id': key, 'prompt': row['question'],
                    'options': {'1': a, '2': b, '0': optout}}
        body = protocol.build({'title': 'Tumble dryer purchase choices',
                               'context': row['context'], 'questions': [question],
                               'basic': {}}, 'basic', 'qwen', {}, {}, 512)
        job = {'questions': [question], 'body': body}
        if key in jobs and jobs[key] != job:
            raise ValueError('Inconsistent stimuli')
        jobs[key] = job
        cards[key] = [features(a, currency), features(b, currency)]
        person = people[country].setdefault(row['person'], {})
        if key in person:
            raise ValueError('Duplicate choice')
        person[key] = ('1', '2', '0')[row['answer']]
    for country, (_, count) in COUNTRIES.items():
        if len(people[country]) != count or any(len(row) != 8 for row in people[country].values()):
            raise ValueError('Unexpected cohort')
    if len(cards) != 64:
        raise ValueError('Unexpected number of cards')
    for key, card in cards.items():
        country, task = key.split('-')
        other = 'IRE' if country == 'UK' else 'UK'
        if card != cards[f'{other}-{task}']:
            raise ValueError('The country designs no longer align')
    return jobs, cards, people


def features(label, currency):
    # Compare experimental price steps in local currency without FX conversion.
    brand, capacity, rating, stars, price = re.search(
        rf'Brand: (Established|New); Capacity: (\d+) kg; Energy rating: ([^;]+); '
        rf'Customer rating: (\d+) stars; Price: {currency} (\d+)$', label
    ).groups()
    return [float(brand == 'Established'), int(capacity) - 7,
            ENERGY.index(rating), int(stars) - 3, (int(price) - 200) / 200]


def evaluate(target, source):
    p, y, keys, x = target
    _, sy, _, sx = source
    sx, sy = sx.reshape(-1, *sx.shape[2:]), sy.reshape(-1, sy.shape[-1])
    rng = np.random.default_rng(SEED)
    results = {n: [] for n in BUDGETS}
    for _ in range(REPEATS):
        available = split_cards(keys, rng)
        holdout = {contrast(card) for card in x[~available]}
        source_mask = retained(sx, holdout)
        local_mask = available & retained(x.reshape(-1, *x.shape[2:]), holdout).reshape(available.shape)
        source_x, source_y = sx[source_mask], sy[source_mask]
        source_rate = (source_y[:, 0].sum() + .5) / (len(source_y) + 1)
        source_beta = fit_products(source_x, source_y)
        order = rng.permutation(len(y))
        test = order[max(BUDGETS):]
        test_mask = ~available[test]
        test_x, test_y, qwen = x[test][test_mask], y[test][test_mask], p[test][test_mask]
        products = softmax(test_x @ source_beta, axis=1)
        for n in BUDGETS:
            pilot = order[:n]
            mask = local_mask[pilot]
            train_x, train_y = x[pilot][mask], y[pilot][mask]
            person_counts = mask.sum(axis=1)
            local_rows = y[pilot, :, 0]
            person_rate = (local_rows * mask).sum(axis=1)[person_counts > 0] / person_counts[person_counts > 0]
            local_rate = (train_y[:, 0].sum() + .5) / (len(train_y) + 1)
            blended_rate = (person_rate.sum() + PRIOR_PEOPLE * source_rate) / (len(person_rate) + PRIOR_PEOPLE)
            local_products = softmax(test_x @ fit_products(train_x, train_y), axis=1)
            methods = {'source_only': (source_rate, products),
                       'source_local_rate': (local_rate, products),
                       'source_blended_rate': (blended_rate, products),
                       'local_only': (local_rate, local_products)}
            scores = {name: losses(np.full(len(test_y), rate), choices, test_y)
                      for name, (rate, choices) in methods.items()}
            scores['qwen'] = float(np.mean(np.sum((qwen - test_y) ** 2, axis=1)))
            scores['source_products_qwen_refusal'] = losses(qwen[:, 0], products, test_y)
            optout = test_y[:, 0]
            scores['refusal'] = {name: float(np.mean((rate - optout) ** 2))
                                  for name, (rate, _) in methods.items()}
            scores['refusal']['qwen'] = float(np.mean((qwen[:, 0] - optout) ** 2))
            scores['rates'] = {name: float(rate) for name, (rate, _) in methods.items()}
            scores['rates'].update(qwen=float(qwen[:, 0].mean()), observed=float(optout.mean()))
            results[n].append(scores)
    return {n: summarize(rows) for n, rows in results.items()}


def summarize(rows):
    mean = {k: float(np.mean([r[k] for r in rows])) for k in rows[0] if k not in ('refusal', 'rates')}
    for metric in ('refusal', 'rates'):
        mean[metric] = {k: float(np.mean([r[metric][k] for r in rows])) for k in rows[0][metric]}
    delta = np.asarray([r['source_only'] - r['source_blended_rate'] for r in rows])
    mean['blend_over_source'] = {'win_rate': float(np.mean(delta > 0)),
                                 'p05_p95': np.quantile(delta, [.05, .95]).tolist()}
    return mean


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run', 'score'])
    action = parser.parse_args().action
    jobs, cards, people = load()
    RUN.mkdir(mode=0o700, exist_ok=True)
    frozen = RUN / 'jobs.json'
    if frozen.exists() and frozen.read_bytes() != encode(jobs):
        raise ValueError('Frozen requests changed')
    if not frozen.exists():
        frozen.write_bytes(encode(jobs))
    if action == 'run':
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(partial(send, directory=RUN), jobs.values()))
    p, identities = predictions(jobs, RUN)
    if len(identities) != 1:
        raise ValueError('Unexpected model identity')
    data = {}
    for country, group in people.items():
        ordered = [dict(sorted(row.items())) for row in group.values()]
        probs, y = outcome(p, ordered)
        keys = np.asarray([list(row) for row in ordered])
        data[country] = probs, y, keys, np.asarray([[cards[k] for k in row] for row in keys])
    results = {country: evaluate(data[country], data[other])
               for country, other in [('UK', 'IRE'), ('IRE', 'UK')]}
    print(json.dumps({'seed': SEED, 'splits': REPEATS, 'prior_people': PRIOR_PEOPLE,
                      'card_predictions': len(jobs), 'identity': json.loads(next(iter(identities))),
                      'source_sha256': sha256(SOURCE.read_bytes()).hexdigest(),
                      'studies': results}, indent=2))


if __name__ == '__main__':
    main()
