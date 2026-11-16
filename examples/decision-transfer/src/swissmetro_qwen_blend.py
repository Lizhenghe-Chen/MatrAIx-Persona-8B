"""Compare fixed Qwen blending to statistical controls on unseen travel offers."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from hashlib import sha256
import json

import numpy as np
from scipy.special import softmax

from choice_predictor import fit_products
from optout_transfer import predictions
from order_screen import SEED, WORK, encode, send
from paid_choice_model_mix import WEIGHT
import protocol
from swissmetro_pilot_allocation import DIGEST, PENALTY_MULTIPLIER, load

RUN = WORK / 'swissmetro-qwen-blend-v1'
PILOT_SIZES = (5, 10, 25)
EVALUATION_PEOPLE = 100
REPLAYS = 100
MODES = ('Conventional train', 'Proposed Swissmetro high-speed maglev train', 'Private car')


def split(x):
    rng = np.random.default_rng(SEED)
    tasks = np.argsort(rng.random(x.shape[:2]), axis=1)[:, :2]
    cohort = np.sort(rng.choice(len(x), EVALUATION_PEOPLE, replace=False))
    held = np.zeros(x.shape[:2], dtype=bool)
    held[cohort[:, None], tasks[cohort]] = True
    cards, inverse = np.unique(x.reshape(-1, 12), axis=0, return_inverse=True)
    inverse = inverse.reshape(x.shape[:2])
    target = np.unique(inverse[held])
    available = ~np.isin(inverse, target)
    available[cohort] = False
    return cards[target].reshape(-1, 3, 4), np.searchsorted(target, inverse[held]), available, held


def build(cards):
    jobs = {}
    for index, card in enumerate(cards, 1):
        key = f'card{index:03}'
        q = {'id': key, 'prompt': 'Which of these three travel modes would you choose for this trip?',
             'options': {str(i): f'{mode}, {time * 100:g} minutes door to door, '
                                  f'{cost * 100:g} Swiss francs out of pocket'
                         for i, (mode, (_, _, time, cost)) in enumerate(zip(MODES, card, strict=True), 1)}}
        body = protocol.build(
            {'title': 'Swiss intercity travel choices',
             'context': 'Consider intercity travelers in Switzerland in the late 1990s comparing '
                        'hypothetical ways to make an intercity trip. All three modes are available.',
             'questions': [q], 'basic': {}}, 'basic', 'qwen', {}, {}, 384,
            preamble='Estimate the proportion of survey respondents who choose each travel mode. '
                     'Use the displayed trip times and costs.')
        jobs[key] = {'questions': [q], 'body': body}
    return jobs


def score(x, y, mapping, available, held, jobs):
    predicted, identities = predictions(jobs, RUN)
    if len(identities) != 1:
        raise ValueError('Mixed Qwen identities')
    qwen = np.array([[predicted[key][str(i)] for i in range(1, 4)] for key in jobs])[mapping]
    qwen_mean = np.broadcast_to(qwen.mean(axis=0), qwen.shape)
    rng = np.random.default_rng(SEED + 1)
    eligible = np.flatnonzero(available.sum(axis=1) >= 4)
    if np.any(held[eligible]) or len(eligible) < max(PILOT_SIZES):
        raise ValueError('Invalid pilot pool')
    truth = y[held][:, 1:]
    rows = {n: [] for n in PILOT_SIZES}
    person_gains = {n: [] for n in PILOT_SIZES}
    share_errors = {n: [] for n in PILOT_SIZES}
    observed = truth.mean(axis=0)
    for _ in range(REPLAYS):
        people = rng.choice(eligible, max(PILOT_SIZES), replace=False)
        for n in PILOT_SIZES:
            cohort = people[:n]
            train = available[cohort]
            features = x[cohort][train]
            answers = y[cohort][train]
            shrink = 1 / np.sqrt(PENALTY_MULTIPLIER)
            base = softmax((x[held] * shrink) @ fit_products(features * shrink, answers, nonpositive_price=True), axis=-1)
            plain = softmax(x[held] @ fit_products(features, answers, nonpositive_price=True), axis=-1)
            shares = (answers[:, 1:].sum(axis=0) + .5) / (len(answers) + 1.5)
            uniform = np.full_like(base, 1 / 3)
            forecasts = {'uniform': uniform, 'qwen': qwen, 'plain': plain,
                         'shrink': base, 'pilot_shares': np.broadcast_to(shares, base.shape),
                         'qwen_mean': qwen_mean}
            for method in ('uniform', 'qwen', 'pilot_shares', 'qwen_mean'):
                forecasts[f'shrink_{method}'] = (1 - WEIGHT) * base + WEIGHT * forecasts[method]
            # Additional diagnostic: test whether Qwen also helps the less constrained fit.
            for method in ('uniform', 'qwen', 'pilot_shares', 'qwen_mean'):
                forecasts[f'plain_{method}'] = (1 - WEIGHT) * plain + WEIGHT * forecasts[method]
            losses = {k: np.square(p - truth).sum(axis=-1).reshape(EVALUATION_PEOPLE, 2).mean(axis=1)
                      for k, p in forecasts.items()}
            rows[n].append({k: float(loss.mean()) for k, loss in losses.items()})
            person_gains[n].append(losses['plain'] - losses['plain_qwen'])
            share_errors[n].append({k: float(np.abs(p.mean(axis=0) - observed).sum() * 50)
                                    for k, p in forecasts.items()})
    summary = {}
    bootstrap = np.random.default_rng(SEED + 2).integers(EVALUATION_PEOPLE, size=(2000, EVALUATION_PEOPLE))
    for n, runs in rows.items():
        scores = {k: np.array([row[k] for row in runs]) for k in runs[0]}
        gains = {}
        for reference in ('shrink', 'plain', 'shrink_uniform', 'shrink_pilot_shares', 'shrink_qwen_mean'):
            delta = scores[reference] - scores['shrink_qwen']
            gains[reference] = {'mean': float(delta.mean()), 'wins': int((delta > 1e-10).sum()),
                                'p05_p95': np.quantile(delta, [.05, .95]).tolist()}
        plain_gains = {}
        for reference in ('plain', 'plain_uniform', 'plain_pilot_shares', 'plain_qwen_mean'):
            delta = scores[reference] - scores['plain_qwen']
            plain_gains[reference] = {'mean': float(delta.mean()), 'wins': int((delta > 1e-10).sum()),
                                      'p05_p95': np.quantile(delta, [.05, .95]).tolist()}
        boot = np.mean(person_gains[n], axis=0)[bootstrap].mean(axis=1)
        plain_gains['plain']['evaluation_person_bootstrap_95'] = np.quantile(boot, [.025, .975]).tolist()
        summary[n] = {'brier': {k: float(values.mean()) for k, values in scores.items()},
                      'share_error_pp': {k: float(np.mean([row[k] for row in share_errors[n]]))
                                         for k in scores},
                      'qwen_mix_gain': gains, 'plain_qwen_gain': plain_gains}
    return {'data_sha256': DIGEST, 'requests_sha256': sha256(encode(list(jobs.values()))).hexdigest(),
            'seed': SEED, 'identity': json.loads(next(iter(identities))), 'valid_calls': len(jobs),
            'evaluation_people': EVALUATION_PEOPLE, 'evaluation_tasks': len(truth),
            'eligible_pilot_people': len(eligible), 'replays': REPLAYS,
            'observed_shares': truth.mean(axis=0).tolist(), 'qwen_shares': qwen.mean(axis=0).tolist(),
            'qwen_weight': WEIGHT, 'penalty_multiplier': PENALTY_MULTIPLIER, 'budgets': summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    args = parser.parse_args()
    x, y = load()
    cards, mapping, available, held = split(x)
    jobs = build(cards)
    RUN.mkdir(mode=0o700, exist_ok=True)
    manifest = RUN / 'jobs.json'
    if manifest.exists():
        if manifest.read_bytes() != encode(list(jobs.values())):
            raise ValueError('Frozen requests changed')
    elif args.action == 'run':
        manifest.write_bytes(encode(list(jobs.values())))
    else:
        raise ValueError('Frozen requests are missing')
    if args.action == 'run':
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(partial(send, directory=RUN), jobs.values()))
    print(json.dumps(score(x, y, mapping, available, held, jobs), indent=2))


if __name__ == '__main__':
    main()
