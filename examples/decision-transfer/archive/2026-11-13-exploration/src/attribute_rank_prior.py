"""Test whether Qwen can guide which choice-model coefficients to shrink."""
import argparse
from collections import Counter
from hashlib import sha256
from itertools import permutations
import json

import numpy as np
from scipy.special import softmax

from attribute_regularization import PENALTY_MULTIPLIER
from choice_predictor import fit_products
import electricity_replication as electricity
from order_screen import SEED, WORK, encode, result_path, send
import protocol
import streaming_price_mix as streaming

RUN = WORK / 'attribute-rank-prior-v1'
STUDIES = {
    'electricity': (
        'US households choosing among electricity suppliers in a market opening to competition in the late 1990s.',
        ('Contract length between no contract and five years, with guaranteed rate and an early-switching penalty',
         'Current local utility versus unfamiliar supplier', 'Well-known non-local supplier versus unfamiliar supplier',
         'Day/night tariff of 11 and 5 cents per kWh versus an 8-cent fixed tariff',
         'Seasonal tariff of 6, 8 or 10 cents per kWh versus an 8-cent fixed tariff',
         'Increase in fixed price by 1 cent per kWh'),
    ),
    'streaming': (
        'Consumers choosing among hypothetical paid streaming subscriptions in a survey. Consider selection among subscriptions.',
        ('Usage information shared with third parties versus no sharing',
         'Usage and personal information shared with third parties versus no sharing',
         'Commercials versus no commercials', 'Earlier releases for TV episodes and movies',
         'More TV episodes and fewer movies versus the standard library',
         'More movies and more TV episodes versus the standard library', 'Increase in price by $2 per month'),
    ),
}


def build():
    jobs = []
    for study, (context, features) in STUDIES.items():
        for draw in range(3):
            order = np.random.default_rng(SEED + draw).permutation(len(features))
            fields = '\n'.join(f'{i}: {features[i]}' for i in order)
            prompt = (f'{context}\nRank the contrasts below by the absolute size of their typical effect on '
                      'choosing one offer over another, strongest first, holding other attributes fixed. '
                      'Use the size of each stated contrast. Include every id exactly once. '
                      'Return only a JSON object with key "ranking" and a list of integer ids.\n' + fields)
            body = {'model': protocol.MODELS['qwen'], 'temperature': .7, 'top_p': 1, 'max_tokens': 256,
                    'response_format': {'type': 'json_object'},
                    'chat_template_kwargs': {'enable_thinking': False},
                    'messages': [{'role': 'user', 'content': prompt}]}
            jobs.append({'study': study, 'draw': draw, 'body': body})
    return jobs


def parse(raw, n):
    identity = {key: raw.get(key) for key in ('model', 'system_fingerprint')}
    if identity['model'] != protocol.MODELS['qwen'] or len(raw['choices']) != 1:
        raise ValueError('Unexpected model or completion count')
    choice = raw['choices'][0]
    msg = choice['message']
    if choice['finish_reason'] != 'stop' or msg.get('reasoning_content') or msg.get('tool_calls'):
        raise ValueError('Invalid ranking completion')
    data = json.loads(msg['content'])
    if set(data) != {'ranking'} or not isinstance(data['ranking'], list):
        raise ValueError('Invalid ranking response')
    rank = data['ranking']
    if any(type(i) is not int for i in rank) or sorted(rank) != list(range(n)):
        raise ValueError('Ranking must contain each field once')
    return {'status': 'ok', 'ranking': rank, 'identity': identity}


def ranks(jobs):
    draws = {study: [] for study in STUDIES}
    identities = set()
    for job in jobs:
        result = json.loads(result_path(job, RUN).read_text())
        if result['status'] != 'ok':
            raise ValueError(f'Unusable ranking: {result["type"]}')
        draws[job['study']].append(result['ranking'])
        identities.add(json.dumps(result['identity'], sort_keys=True))
    if len(identities) != 1:
        raise ValueError('Mixed Qwen identities')
    return draws, json.loads(next(iter(identities)))


def scales(draws, seed):
    places = np.argsort(draws, axis=1)
    # Spread penalties symmetrically around the same geometric mean, at most 4x apart.
    multipliers = 2 ** (2 * places.mean(axis=0) / (places.shape[1] - 1) - 1)
    weights = 1 / np.sqrt(PENALTY_MULTIPLIER * multipliers)
    rng = np.random.default_rng(seed)
    # All random controls preserve the same spread and the exact price penalty.
    others = list(permutations(range(len(weights) - 1)))
    scrambled = rng.choice(len(others), size=12, replace=False)
    variants = {'plain': np.ones(len(weights)), 'equal': np.full(len(weights), 1 / np.sqrt(PENALTY_MULTIPLIER)),
                'ranked': weights}
    variants.update({f'shuffle{i}': weights[[*others[k], len(weights) - 1]] for i, k in enumerate(scrambled)})
    return variants, multipliers


def splits(study):
    rng = np.random.default_rng(SEED + 1)
    if study == 'electricity':
        cards, inverse, ids, truth, held = electricity.load()
        test_card = np.isin(inverse, held)
        price = cards[..., 0]
        features = np.concatenate((cards[..., 1:], np.where(price > 0, price - 8, 0)[..., None]), axis=-1)
        x = features[inverse]
        y = np.column_stack((np.zeros(len(truth)), truth))
        available = ~test_card
        has_refusal = False
    else:
        features, truth, train, test = streaming.load()
        features = np.concatenate((features[..., 1:], (features[..., :1] - 9.99) / 2), axis=-1)
        ids = np.repeat(np.arange(len(truth)), truth.shape[1])
        x = features.reshape(len(ids), *features.shape[2:])
        y = truth.reshape(len(ids), truth.shape[-1])
        available, test_card = train.ravel(), test.ravel()
        has_refusal = True
    for _ in range(100):
        order = rng.permutation(len(np.unique(ids)))
        test = test_card & ~np.isin(ids, order[:max(streaming.SIZES)])
        people, index, count = np.unique(ids[test], return_inverse=True, return_counts=True)
        weights = 1 / count[index] / len(people)
        for n in streaming.SIZES:
            train = available & np.isin(ids, order[:n])
            yield n, x[train], y[train], x[test], y[test], weights, has_refusal


def score(study, draws):
    variants, multipliers = scales(draws, SEED)
    rows = {n: [] for n in streaming.SIZES}
    for n, train, answers, test, truth, weights, has_refusal in splits(study):
        refusal = (answers[:, 0].sum() + .5) / (len(answers) + 1) if has_refusal else 0
        row = {}
        for name, scale in variants.items():
            beta = fit_products(train * scale, answers, nonpositive_price=True)
            p = softmax(test @ (beta * scale), axis=-1)
            pred = np.column_stack((np.full(len(p), refusal), (1 - refusal) * p))
            row[name] = weights @ np.square(pred - truth).sum(axis=-1)
        row['shuffle_mean'] = np.mean([v for k, v in row.items() if k.startswith('shuffle')])
        rows[n].append(row)
    budgets = {}
    for n, runs in rows.items():
        methods = {name: np.array([row[name] for row in runs])
                   for name in ('plain', 'equal', 'ranked', 'shuffle_mean')}
        gains = {}
        for name in ('plain', 'equal', 'shuffle_mean'):
            delta = methods[name] - methods['ranked']
            gains[name] = {'mean': float(delta.mean()), 'wins': int((delta > 1e-10).sum()),
                           'p05_p95': np.quantile(delta, [.05, .95]).tolist()}
        shuffled_means = [np.mean([row[k] for row in runs]) for k in variants if k.startswith('shuffle')]
        budgets[n] = {'brier': {k: float(v.mean()) for k, v in methods.items()}, 'ranked_gain': gains,
                      'scrambles_beaten': int(np.sum(np.array(shuffled_means) > methods['ranked'].mean() + 1e-10))}
    return {'draws': draws, 'top_rank_counts': dict(Counter(draw[0] for draw in draws)),
            'penalty_multipliers': multipliers.tolist(), 'budgets': budgets}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    args = parser.parse_args()
    jobs = build()
    RUN.mkdir(mode=0o700, exist_ok=True)
    manifest = RUN / 'jobs.json'
    if manifest.exists():
        if manifest.read_bytes() != encode(jobs):
            raise ValueError('Frozen requests changed')
    elif args.action == 'run':
        manifest.write_bytes(encode(jobs))
    else:
        raise ValueError('Frozen requests are missing')
    if args.action == 'run':
        for job in jobs:
            n = len(STUDIES[job['study']][1])
            send(job, RUN, lambda raw: parse(raw, n))
    draws, identity = ranks(jobs)
    print(json.dumps({'seed': SEED, 'replays': 100, 'valid_calls': len(jobs), 'identity': identity,
                      'requests_sha256': sha256(encode(jobs)).hexdigest(),
                      'base_penalty_multiplier': PENALTY_MULTIPLIER,
                      'feature_names': {study: names for study, (_, names) in STUDIES.items()},
                      'studies': {study: score(study, ranks) for study, ranks in draws.items()}}, indent=2))


if __name__ == '__main__':
    main()
