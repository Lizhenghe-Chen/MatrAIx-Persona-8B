"""Replicate the fixed 25% Qwen blend on independently collected travel choices."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from hashlib import sha256
import json

import numpy as np
from scipy.special import softmax

from attribute_regularization import PENALTY_MULTIPLIER
from choice_predictor import fit_products
from optout_transfer import predictions
from order_screen import SEED, WORK, encode, send
from paid_choice_model_mix import WEIGHT
import protocol

SOURCE = WORK / 'modecanada-admission/ModeCanada.rda'
URL = 'https://raw.githubusercontent.com/cran/mlogit/master/data/ModeCanada.rda'
DIGEST = '5667b1487ec0598ede18bb53f124a99faf89eea619d4d65ced0dfbd1edb97ec8'
RUN = WORK / 'modecanada-qwen-blend-v1'
MODES = ('air', 'bus', 'car', 'train')
LABELS = ('Airplane', 'Intercity bus', 'Private car', 'Train')
PILOT_SIZES = (5, 10, 25, 50)
REPLAYS = 100
EVALUATION = 200


def load():
    import pyreadr

    if sha256(SOURCE.read_bytes()).hexdigest() != DIGEST:
        raise ValueError('Unexpected ModeCanada version')
    f = pyreadr.read_r(str(SOURCE))['ModeCanada']
    f = f[f.noalt.eq(4)].assign(alt=lambda df: df.alt.astype(str)).sort_values(['case', 'alt'])
    x = f[['ivt', 'ovt', 'freq', 'cost']].to_numpy().reshape(-1, 4, 4)
    y = f.choice.to_numpy().reshape(-1, 4)
    if (len(x) != 2779 or not np.all(f.alt.to_numpy().reshape(-1, 4) == MODES)
            or not f.groupby('case').size().eq(4).all() or not np.isin(y, [0, 1]).all()
            or not (y.sum(axis=1) == 1).all() or not np.isfinite(x).all() or (x < 0).any()):
        raise ValueError('Unexpected ModeCanada option layout')
    return x, y


def split(x):
    rng = np.random.default_rng(SEED)
    held = np.sort(rng.choice(len(x), EVALUATION, replace=False))
    cards, inverse = np.unique(x.reshape(-1, 16), axis=0, return_inverse=True)
    target = np.unique(inverse[held])
    train = np.flatnonzero(~np.isin(inverse, target))
    return train, held, cards[target].reshape(-1, 4, 4), np.searchsorted(target, inverse[held])


def option(label, row):
    ivt, ovt, freq, cost = row
    service = '' if label == 'Private car' else f', {freq:g} service frequency (survey value)'
    return f'{label}, CAD {cost:.2f}, {ivt:g} minutes in vehicle, {ovt:g} minutes outside vehicle{service}'


def build(cards):
    jobs = {}
    for i, card in enumerate(cards, 1):
        key = f'card{i:03}'
        q = {'id': key, 'prompt': 'Which of these travel modes would you choose for this trip?',
             'options': {str(j): option(label, row)
                         for j, (label, row) in enumerate(zip(LABELS, card, strict=True), 1)}}
        body = protocol.build(
            {'title': 'Canadian intercity travel choices',
             'context': 'Consider intercity trips in the Toronto–Montreal corridor in 1989. '
                        'Each option below is available for the trip.',
             'questions': [q], 'basic': {}}, 'basic', 'qwen', {}, {}, 384,
            preamble='Estimate the proportion of travelers who choose each travel mode. '
                     'Use the displayed trip times, costs, and service frequency.')
        jobs[key] = {'questions': [q], 'body': body}
    return jobs


def score(x, y, train, held, mapping, jobs):
    replies, identities = predictions(jobs, RUN)
    if len(identities) != 1:
        raise ValueError('Mixed Qwen identities')
    qwen = np.array([[replies[key][str(i)] for i in range(1, 5)] for key in jobs])[mapping]
    # Use the same predictors as the requests. Car is the reference mode.
    constants = np.broadcast_to(np.eye(4)[:, [0, 1, 3]], (len(x), 4, 3))
    features = np.concatenate((constants, x / [100, 100, 10, 100]), axis=-1)
    rng = np.random.default_rng(SEED + 1)
    truth = y[held]
    observed = truth.mean(axis=0)
    losses = {n: [] for n in PILOT_SIZES}
    share_errors = {n: [] for n in PILOT_SIZES}
    for _ in range(REPLAYS):
        order = rng.choice(train, max(PILOT_SIZES), replace=False)
        for n in PILOT_SIZES:
            pilot = order[:n]
            answer = np.column_stack((np.zeros(n), y[pilot]))
            beta = fit_products(features[pilot], answer, nonpositive_price=True)
            stats = softmax(features[held] @ beta, axis=-1)
            # Supplementary control using the earlier fixed tenfold penalty.
            scale = 1 / np.sqrt(PENALTY_MULTIPLIER)
            regularized = fit_products(features[pilot] * scale, answer, nonpositive_price=True)
            strong_stats = softmax(features[held] @ (regularized * scale), axis=-1)
            forecasts = {'stats': stats, 'strong_stats': strong_stats, 'qwen': qwen,
                         'pilot_share': np.broadcast_to((y[pilot].sum(axis=0) + .5) / (n + 2), stats.shape),
                         'uniform': np.full_like(stats, .25),
                         'qwen_mean': np.broadcast_to(qwen.mean(axis=0), stats.shape)}
            for source in ('qwen', 'uniform', 'pilot_share', 'qwen_mean'):
                forecasts[f'mix_{source}'] = (1 - WEIGHT) * stats + WEIGHT * forecasts[source]
            losses[n].append({k: np.square(p - truth).sum(axis=-1) for k, p in forecasts.items()})
            share_errors[n].append({k: float(np.abs(p.mean(axis=0) - observed).sum() * 50)
                                    for k, p in forecasts.items()})
    bootstrap = np.random.default_rng(SEED + 2).integers(len(held), size=(2000, len(held)))
    budgets = {}
    for n, rows in losses.items():
        error = {key: np.array([row[key] for row in rows]) for key in rows[0]}
        gains = {}
        for reference in ('stats', 'mix_uniform', 'mix_pilot_share', 'mix_qwen_mean', 'strong_stats'):
            diff = error[reference] - error['mix_qwen']
            by_pilot = diff.mean(axis=1)
            by_person = diff.mean(axis=0)
            gains[reference] = {
                'mean': float(diff.mean()), 'wins': int((by_pilot > 1e-10).sum()),
                'pilot_p05_p95': np.quantile(by_pilot, [.05, .95]).tolist(),
                'evaluation_bootstrap_95': np.quantile(by_person[bootstrap].mean(axis=1), [.025, .975]).tolist(),
            }
        budgets[n] = {'brier': {k: float(v.mean()) for k, v in error.items()}, 'gains': gains,
                      'share_error_pp': {k: float(np.mean([row[k] for row in share_errors[n]])) for k in error}}
    return {'source': URL, 'source_sha256': DIGEST, 'requests_sha256': sha256(encode(list(jobs.values()))).hexdigest(),
            'seed': SEED, 'qwen_weight': WEIGHT, 'strong_penalty_multiplier': PENALTY_MULTIPLIER, 'replays': REPLAYS, 'identity': json.loads(next(iter(identities))),
            'evaluation_cases': len(held), 'eligible_pilot_cases': len(train), 'valid_calls': len(replies),
            'modes': MODES, 'observed_shares': observed.tolist(), 'qwen_shares': qwen.mean(axis=0).tolist(),
            'budgets': budgets}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    args = parser.parse_args()
    x, y = load()
    train, held, cards, mapping = split(x)
    jobs = build(cards)
    RUN.mkdir(mode=0o700, exist_ok=True)
    path = RUN / 'jobs.json'
    if path.exists():
        if path.read_bytes() != encode(list(jobs.values())):
            raise ValueError('Frozen requests changed')
    elif args.action == 'run':
        path.write_bytes(encode(list(jobs.values())))
    else:
        raise ValueError('Frozen requests are missing')
    if args.action == 'run':
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(partial(send, directory=RUN), jobs.values()))
    print(json.dumps(score(x, y, train, held, mapping, jobs), indent=2))


if __name__ == '__main__':
    main()
