"""Equal-cost repeated versus reordered Qwen predictions on full product choice cards."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from functools import partial
import json
import random

import numpy as np

from optout_transfer import beer_deck, german_deck, outcome, predictions
import optout_transfer as transfer
from order_screen import SEED, WORK, encode, send

RUN = WORK / 'product-order-v1'


def rotate(job):
    changed = deepcopy(job)
    q, = changed['questions']
    options = q['options']
    ids = [key for key in options if key != '0']
    shifted = iter(ids[1:] + ids[:1])
    order = [key if key == '0' else next(shifted) for key in options]
    original = '\n'.join(f'| `{key}` | {value} |' for key, value in options.items())
    replacement = '\n'.join(f'| `{key}` | {options[key]} |' for key in order)
    message = changed['body']['messages'][-1]
    if message['content'].count(original) != 1:
        raise ValueError('Cannot locate unique rendered options')
    message['content'] = message['content'].replace(original, replacement)
    q['options'] = {key: options[key] for key in order}
    return changed


def prepare():
    studies = {'beer': (*beer_deck(), transfer.RUN),
               'tomato': (*german_deck(), transfer.germany.RUN)}
    decks, jobs = {}, []
    for study, (deck, people, old_dir) in studies.items():
        same = {key: {**job, 'draw': 'same'} for key, job in deck.items()}
        different = {key: {**rotate(job), 'draw': 'rotated'} for key, job in deck.items()}
        decks[study] = deck, people, old_dir, same, different
        jobs.extend(same.values())
        jobs.extend(different.values())
    random.Random(SEED).shuffle(jobs)
    return decks, jobs


def score(studies):
    identities = set()
    result = {}
    for study, (deck, people, old_dir, same, different) in studies.items():
        cell_probabilities = []
        for source, directory in ((deck, old_dir), (same, RUN), (different, RUN)):
            probabilities, identity = predictions(source, directory)
            identities.update(identity)
            cell_probabilities.append(probabilities)
        p, y = outcome(cell_probabilities[0], people)
        r, _ = outcome(cell_probabilities[1], people)
        v, _ = outcome(cell_probabilities[2], people)
        estimates = {'original': p, 'same_twice': (p + r) / 2, 'rotated_twice': (p + v) / 2}
        person_loss = {name: np.sum((q - y) ** 2, axis=-1).mean(axis=1) for name, q in estimates.items()}
        # Compare observed and predicted shares at the actual card and information cell.
        cell_truth = {key: [] for key in deck}
        for person in people:
            for key, answer in person.items():
                ids = sorted(deck[key]['questions'][0]['options'])
                cell_truth[key].append(np.eye(len(ids))[ids.index(answer)])
        tv = {name: 0. for name in estimates}
        total = sum(map(len, cell_truth.values()))
        cells = []
        for key, truths in cell_truth.items():
            a, b, c = [np.array([q[key][i] for i in sorted(q[key])]) for q in cell_probabilities]
            shares = np.mean(truths, axis=0)
            same_q, rotated_q = (a + b) / 2, (a + c) / 2
            cell_delta = np.mean(np.sum((same_q - truths) ** 2 - (rotated_q - truths) ** 2, axis=1))
            cells.append((cell_delta, len(truths)))
            for name, q in zip(tv, (a, same_q, rotated_q), strict=True):
                tv[name] += .5 * np.abs(q - shares).sum() * len(truths) / total
        delta = person_loss['same_twice'] - person_loss['rotated_twice']
        rng = np.random.default_rng(SEED)
        sample = rng.integers(len(delta), size=(2000, len(delta)))
        # Resample underlying cards as clusters, keeping beer information variants together.
        card_totals = {}
        for key, (gain, count) in zip(cell_truth, cells, strict=True):
            card = key[-1] if isinstance(key, tuple) else key
            card_totals.setdefault(card, np.zeros(2))[:] += [gain * count, count]
        cards = np.array(list(card_totals.values()))
        card_draws = cards[rng.integers(len(cards), size=(2000, len(cards)))].sum(axis=1)
        card_interval = np.quantile(card_draws[:, 0] / card_draws[:, 1], [.025, .975])
        result[study] = {'people': len(people), 'cards_and_contexts': len(deck), 'unique_cards': len(cards),
                         'card_resampling_gain_interval_95': card_interval.tolist(),
                         'brier': {name: float(loss.mean()) for name, loss in person_loss.items()},
                         'distribution_tv': tv, 'human_no_buy': float(y[..., 0].mean()),
                         'no_buy': {name: float(q[..., 0].mean()) for name, q in estimates.items()},
                         'repeat_tv': float(.5 * np.abs(p - r).sum(axis=-1).mean()),
                         'rotate_tv': float(.5 * np.abs(p - v).sum(axis=-1).mean()),
                         'brier_gain_interval_95': np.quantile(delta[sample].mean(axis=1), [.025, .975]).tolist()}
    if len(identities) != 1:
        raise ValueError('Mixed Qwen versions across runs')
    return {'identity': json.loads(identities.pop()), 'studies': result}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    action = parser.parse_args().action
    studies, jobs = prepare()
    RUN.mkdir(mode=0o700, exist_ok=True)
    manifest = RUN / 'jobs.json'
    if manifest.exists() and manifest.read_bytes() != encode(jobs):
        raise ValueError('Frozen inputs changed')
    if not manifest.exists():
        manifest.write_bytes(encode(jobs))
    if action == 'run':
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(partial(send, directory=RUN), jobs))
    print(json.dumps({'new_requests': len(jobs), **score(studies)}, indent=2))
