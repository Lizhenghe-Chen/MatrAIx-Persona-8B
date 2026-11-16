"""Test whether hypothetical orange choices transfer to paid product choices."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from hashlib import sha256
import json

import numpy as np
from openpyxl import load_workbook
from scipy.special import softmax

from choice_predictor import fit_products
from optout_transfer import predictions
from order_screen import SEED, WORK, encode, send
import protocol

SOURCE = WORK / 'japan-orange-admission/choices.xlsx'
DIGEST = '0f6573d987a0fdab45404319b5f4c59d1811252459d12d2bc1ff80bf83439915'
RUN = WORK / 'orange-payment-transfer-v1'
BUDGETS = (5, 10, 25)


def load():
    if sha256(SOURCE.read_bytes()).hexdigest() != DIGEST:
        raise ValueError('Workbook version changed')
    book = load_workbook(SOURCE, read_only=True, data_only=True)
    rows = book.active.iter_rows(max_col=9, values_only=True)
    if next(rows) != ('id', 'treatment', 'set', 'alt1', 'alt2', 'alt3', 'price', 'carbon', 'choice'):
        raise ValueError('Workbook columns changed')
    groups = defaultdict(lambda: defaultdict(dict))
    for person, group, card, a, b, c, price, carbon, choice in rows:
        if group not in (0, 1):
            continue
        position = (a, b, c).index(1)
        options = groups[group][person].setdefault(card, {})
        if position in options:
            raise ValueError('Repeated option')
        options[position] = ((price, carbon), choice)
    book.close()
    profiles = sorted({tuple(options[i][0] for i in range(3)) for people in groups.values()
                       for answers in people.values() for options in answers.values()})
    index = {profile: i + 1 for i, profile in enumerate(profiles)}
    arrays = {}
    excluded = {}
    for group, people in groups.items():
        complete = []
        excluded[group] = 0
        for answers in people.values():
            keys = sorted(answers)
            if len(keys) != 12 or any(set(options) != {0, 1, 2} for options in answers.values()):
                raise ValueError('Unexpected block')
            values = [[answers[card][i][1] for i in range(3)] for card in keys]
            if any(None in row for row in values):
                excluded[group] += 1
                continue
            if any(sum(row) != 1 or not set(row) <= {0, 1} for row in values):
                raise ValueError('Expected one chosen offer')
            card_ids = [index[tuple(answers[card][i][0] for i in range(3))] for card in keys]
            complete.append((card_ids, values))
        arrays[group] = tuple(np.asarray(x) for x in zip(*complete, strict=True))
    if len(profiles) != 19 or [len(arrays[g][0]) for g in (0, 1)] != [104, 211]:
        raise ValueError('Unexpected cohort')
    return dict(enumerate(profiles, 1)), arrays, excluded


def build(cards):
    context = ('日本の大阪大学で、地元住民と学生が参加した実験です。'
               'みかんは小ぶりで、表示する炭素排出量の違いは主に輸送距離によります。産地は表示されません。'
               '各回に120円が与えられ、3つから1つを選び、代金が差し引かれます。'
               '実験後に選んだみかんを受け取ります。')
    jobs = {}
    for card, offers in cards.items():
        q = {'id': f'card{card}', 'prompt': '次の3つのみかんから、購入するものを1つ選んでください。',
             'options': {str(i): f'みかん1個、{price}円、炭素排出量{carbon}g'
                         for i, (price, carbon) in enumerate(offers, 1)}}
        body = protocol.build({'title': 'みかんの購入実験', 'context': context, 'questions': [q],
                               'basic': {}}, 'basic', 'qwen', {}, {}, 512,
                              preamble='実験参加者全体について、各選択肢を選ぶ割合を推定してください。')
        jobs[card] = {'questions': [q], 'body': body}
    return jobs


def score(cards, groups, jobs):
    predicted, identities = predictions(jobs, RUN)
    if len(identities) != 1:
        raise ValueError('Mixed model versions')
    qwen = np.array([[predicted[k][str(i)] for i in (1, 2, 3)] for k in cards])
    x = (np.array(list(cards.values()), dtype=float) - [35, 30]) / 10
    target_cards, target = groups[0]
    source_cards, source = groups[1]
    index = {key: i for i, key in enumerate(cards)}
    target_cards = np.vectorize(index.__getitem__)(target_cards)
    source_cards = np.vectorize(index.__getitem__)(source_cards)
    blocks = np.unique(target_cards, axis=0)
    if blocks.shape != (2, 12) or not np.array_equal(blocks, np.unique(source_cards, axis=0)):
        raise ValueError('Expected two blocks')
    only_first = np.setdiff1d(blocks[0], blocks[1])
    only_second = np.setdiff1d(blocks[1], blocks[0])
    shared = np.intersect1d(*blocks)

    def fit(ids, labels, features):
        return fit_products(features[ids], np.column_stack((np.zeros(len(labels)), labels)),
                            nonpositive_price=True)

    rng = np.random.default_rng(SEED)
    rows = {n: [] for n in BUDGETS}
    for _ in range(100):
        train_cards = np.concatenate([rng.permutation(pool)[:len(pool) // 2]
                                      for pool in (only_first, only_second, shared)])
        source_mask = np.isin(source_cards, train_cards)
        historical = softmax(x @ fit(source_cards[source_mask], source[source_mask], x), axis=1)
        price = x[..., :1]
        historical_price = softmax(price @ fit(source_cards[source_mask], source[source_mask], price), axis=1)
        order = rng.permutation(len(target))
        test = order[max(BUDGETS):]
        mask = ~np.isin(target_cards[test], train_cards)
        ids, observed = target_cards[test][mask], target[test][mask]
        for n, scores in rows.items():
            pilot = order[:n]
            available = np.isin(target_cards[pilot], train_cards)
            local = softmax(x @ fit(target_cards[pilot][available], target[pilot][available], x), axis=1)
            methods = {'uniform': np.full_like(qwen, 1 / 3), 'qwen': qwen, 'hypothetical': historical,
                       'hypothetical_price_only': historical_price, 'paid_pilot': local,
                       'half_mix': .5 * (historical + local)}
            scores.append({name: float(np.square(probs[ids] - observed).sum(axis=1).mean())
                           for name, probs in methods.items()})
    result = {}
    for n, scores in rows.items():
        result[n] = {name: float(np.mean([r[name] for r in scores])) for name in scores[0]}
        for base in ('paid_pilot', 'hypothetical', 'qwen'):
            delta = np.array([r[base] - r['half_mix'] for r in scores])
            result[n][f'half_mix_over_{base}'] = {'win_rate': float(np.mean(delta > 0)),
                                                'p05_p95': np.quantile(delta, [.05, .95]).tolist()}
    return {'source_sha256': DIGEST, 'seed': SEED, 'replays': 100, 'cards': len(cards),
            'identity': json.loads(next(iter(identities))), 'valid_requests': len(predicted), 'budgets': result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    args = parser.parse_args()
    cards, groups, excluded = load()
    jobs = build(cards)
    RUN.mkdir(mode=0o700, exist_ok=True)
    manifest = RUN / 'jobs.json'
    if manifest.exists() and manifest.read_bytes() != encode(jobs):
        raise ValueError('Frozen requests changed')
    if not manifest.exists():
        manifest.write_bytes(encode(jobs))
    if args.action == 'run':
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(partial(send, directory=RUN), jobs.values()))
    print(json.dumps({**score(cards, groups, jobs), 'excluded_incomplete': excluded}, indent=2))


if __name__ == '__main__':
    main()
