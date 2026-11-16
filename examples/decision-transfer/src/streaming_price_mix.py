"""Test the frozen 75/25 price blend on an independent streaming survey."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from hashlib import sha256
import json
import random

import numpy as np
from scipy.io import loadmat
from scipy.special import softmax

from choice_predictor import fit_products
from optout_transfer import predictions
from order_screen import SEED, WORK, encode, send
from paid_choice_model_mix import WEIGHT
import protocol

SOURCE = WORK / 'streaming-admission/videodata100.mat'
DIGEST = 'e5c9948187c69129a7965947702b8f8e6df7a3a7dda52364b37ec3b7ab07a9e0'
RUN = WORK / 'streaming-price-mix-v1'
SIZES = (5, 10, 25)


def load():
    if sha256(SOURCE.read_bytes()).hexdigest() != DIGEST:
        raise ValueError('Unexpected workbook version')
    a = loadmat(SOURCE)['XMAT'].reshape(100, 11, 5, 11)
    if (not np.all(a[..., 0] == np.arange(1, 101)[:, None, None])
            or not np.all(a[..., 1] == np.arange(1, 1101).reshape(100, 11, 1))
            or not np.all(a[..., 2].sum(axis=-1) == 1)
            or not np.all(a[..., 10] == [0, 0, 0, 0, 1])):
        raise ValueError('Unexpected respondent, option or answer layout')
    x = a[..., :4, 3:10]
    profiles = np.asarray([sorted(map(tuple, row)) for row in x.reshape(-1, 4, 7)])
    _, inverse = np.unique(profiles.reshape(-1, 28), axis=0, return_inverse=True)
    rng = np.random.default_rng(SEED)
    order = np.argsort(rng.random((100, 11)), axis=1)
    test = np.zeros((100, 11), dtype=bool)
    np.put_along_axis(test, order[:, :2], True, axis=1)
    train = ~np.isin(inverse.reshape(100, 11), inverse[test.ravel()])
    return x, np.roll(a[..., 2], 1, axis=-1), train, test


def label(row):
    price, usage, sharing, ads, fast, more_tv, more_all = row
    library = ('2,000 movies and 13,000 TV episodes' if more_tv else
               '10,000 movies and 5,000 TV episodes' if more_all else
               '5,000 movies and 2,500 TV episodes')
    release = ('TV episodes next day, movies in 3 months' if fast else
               'TV episodes in 3 months, movies in 6 months')
    privacy = ('Usage and personal information shared with third parties' if sharing else
               'Usage information shared with third parties' if usage else
               'Information collected but not shared')
    return f'${price:.2f} per month; {"commercials" if ads else "no commercials"}; {release}; {library}; {privacy}'


def build(x, test):
    jobs = {}
    for index, offers in enumerate(x[test], 1):
        q = {'id': f'card{index:03}', 'prompt': 'Which video streaming service would you choose?',
             'options': {**{str(i): label(row) for i, row in enumerate(offers, 1)}, '0': 'No service'}}
        body = protocol.build({'title': 'Video streaming service choices',
                               'context': 'Consider this survey choice between four hypothetical subscription services.',
                               'questions': [q], 'basic': {}}, 'basic', 'qwen', {}, {}, 512,
                              preamble='Estimate the proportion of survey respondents who choose each option.')
        jobs[q['id']] = {'questions': [q], 'body': body}
    return jobs


def score(x, y, train, test, jobs, directory=RUN):
    predicted, identities = predictions(jobs, directory)
    if len(identities) != 1:
        raise ValueError('Mixed Qwen identities')
    raw = np.array([[predicted[key][str(i)] for i in range(1, 5)] for key in jobs])
    uniform = np.full_like(raw, .25)
    mass = raw.sum(axis=-1, keepdims=True)
    qwen = np.divide(raw, mass, out=uniform.copy(), where=mass > 0)
    x = np.concatenate((x[..., 1:], (x[..., :1] - 9.99) / 2), axis=-1)
    rng = np.random.default_rng(SEED + 1)
    results = {n: [] for n in SIZES}
    for _ in range(100):
        order = rng.permutation(len(y))
        fit_people = order[:max(SIZES)]
        mask = (y[test][:, 0] == 0) & ~np.isin(np.nonzero(test)[0], fit_people)
        truth = y[test][mask, 1:]
        target = x[test][mask]
        for n, rows in results.items():
            pilot = order[:n]
            available = train[pilot]
            xx, yy = x[pilot][available], y[pilot][available]
            full = softmax(target @ fit_products(xx, yy, nonpositive_price=True), axis=-1)
            price = softmax(target[..., -1:] @ fit_products(xx[..., -1:], yy, nonpositive_price=True), axis=-1)
            methods = {'full': full, 'price': price, 'qwen': qwen[mask],
                       'price_qwen': (1 - WEIGHT) * price + WEIGHT * qwen[mask],
                       'price_uniform': (1 - WEIGHT) * price + WEIGHT * uniform[mask]}
            rows.append({name: float(np.square(p - truth).sum(axis=-1).mean()) for name, p in methods.items()})
    summary = {}
    for n, rows in results.items():
        scores = {key: np.array([r[key] for r in rows]) for key in rows[0]}
        gains = {}
        for name in ('full', 'price', 'qwen', 'price_uniform'):
            delta = scores[name] - scores['price_qwen']
            gains[name] = {'win_rate': float((delta > 1e-10).mean()),
                           'p05_p95': np.quantile(delta, [.05, .95]).tolist()}
        summary[n] = {'brier': {key: float(value.mean()) for key, value in scores.items()}, 'gain': gains}
    return {'source_sha256': DIGEST, 'people': len(y), 'test_cards': int(test.sum()),
            'test_subscription_choices': int((y[test][:, 0] == 0).sum()),
            'test_subscription_choices_with_zero_qwen_mass': int(
                ((y[test][:, 0] == 0) & (mass[:, 0] == 0)).sum()),
            'available_train_cards': int(train.sum()), 'identity': json.loads(next(iter(identities))),
            'valid_calls': len(predicted), 'seed': SEED, 'replays': 100, 'qwen_weight': WEIGHT,
            'budgets': summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    args = parser.parse_args()
    x, y, train, test = load()
    jobs = build(x, test)
    batch = list(jobs.values())
    random.Random(SEED).shuffle(batch)
    RUN.mkdir(mode=0o700, exist_ok=True)
    manifest = RUN / 'jobs.json'
    if manifest.exists() and manifest.read_bytes() != encode(batch):
        raise ValueError('Frozen requests changed')
    if not manifest.exists():
        manifest.write_bytes(encode(batch))
    if args.action == 'run':
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(partial(send, directory=RUN), batch))
    print(json.dumps(score(x, y, train, test, jobs), indent=2))


if __name__ == '__main__':
    main()
