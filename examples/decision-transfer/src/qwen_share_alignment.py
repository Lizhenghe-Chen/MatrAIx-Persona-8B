"""Replay Qwen blending while anchoring aggregate shares to the statistical model."""
import json

import numpy as np
from scipy.special import softmax

from choice_predictor import fit_products
import electricity_replication as electricity
import modecanada_qwen_blend as canada
from optout_transfer import predictions
from order_screen import SEED
from paid_choice_model_mix import WEIGHT
import streaming_price_mix as streaming
import swissmetro_qwen_blend as swiss

REPLAYS = 100


def align(p, target, weights):
    """Scale option columns then normalize each card, preserving cross-card odds ratios."""
    p = np.maximum(p, 1e-6)
    for _ in range(1000):
        p *= target / (weights @ p)
        p /= p.sum(axis=1, keepdims=True)
        if np.max(np.abs(weights @ p - target)) < 1e-10:
            return p
    raise RuntimeError('Share alignment did not converge')


def replies(study, jobs, keys):
    values, identities = predictions(jobs, study.RUN)
    if len(identities) != 1:
        raise ValueError('Mixed Qwen identities')
    return np.array([[values[key][str(i)] for i in keys] for key in jobs])


def canada_replays():
    x, y = canada.load()
    train, held, cards, mapping = canada.split(x)
    q = replies(canada, canada.build(cards), range(1, 5))[mapping]
    constants = np.broadcast_to(np.eye(4)[:, [0, 1, 3]], (len(x), 4, 3))
    x = np.concatenate((constants, x / [100, 100, 10, 100]), axis=-1)
    rng = np.random.default_rng(SEED + 1)
    for _ in range(REPLAYS):
        order = rng.choice(train, max(canada.PILOT_SIZES), replace=False)
        for n in canada.PILOT_SIZES:
            pilot = order[:n]
            answer = np.column_stack((np.zeros(n), y[pilot]))
            yield n, x[pilot], answer, x[held], y[held], q, held, False


def swiss_replays():
    x, y = swiss.load()
    cards, mapping, available, held = swiss.split(x)
    q = replies(swiss, swiss.build(cards), range(1, 4))[mapping]
    eligible = np.flatnonzero(available.sum(axis=1) >= 4)
    ids = np.nonzero(held)[0]
    rng = np.random.default_rng(SEED + 1)
    for _ in range(REPLAYS):
        order = rng.choice(eligible, max(swiss.PILOT_SIZES), replace=False)
        for n in swiss.PILOT_SIZES:
            pilot = order[:n]
            mask = available[pilot]
            yield n, x[pilot][mask], y[pilot][mask], x[held], y[held][:, 1:], q, ids, False


def electricity_replays():
    cards, inverse, ids, y, held = electricity.load()
    q = replies(electricity, electricity.build(cards, held), range(1, 5))
    fixed = cards[..., 0]
    x = np.concatenate((cards[..., 1:], np.where(fixed > 0, fixed - 8, 0)[..., None]), axis=-1)
    test_card = np.isin(inverse, held)
    rng = np.random.default_rng(SEED + 1)
    for _ in range(REPLAYS):
        order = rng.permutation(len(np.unique(ids)))
        test = test_card & ~np.isin(ids, order[:max(electricity.SIZES)])
        target = inverse[test]
        for n in electricity.SIZES:
            train = ~test_card & np.isin(ids, order[:n])
            answer = np.column_stack((np.zeros(train.sum()), y[train]))
            yield n, x[inverse[train]], answer, x[target], y[test], q[np.searchsorted(held, target)], ids[test], False


def streaming_replays():
    x, y, train, test = streaming.load()
    q = replies(streaming, streaming.build(x, test), range(1, 5))
    mass = q.sum(axis=1, keepdims=True)
    q = np.divide(q, mass, out=np.full_like(q, .25), where=mass > 0)
    x = np.concatenate((x[..., 1:], (x[..., :1] - 9.99) / 2), axis=-1)
    rng = np.random.default_rng(SEED + 1)
    ids = np.nonzero(test)[0]
    for _ in range(REPLAYS):
        order = rng.permutation(len(y))
        mask = ~np.isin(ids, order[:max(streaming.SIZES)])
        for n in streaming.SIZES:
            pilot = order[:n]
            available = train[pilot]
            yield n, x[pilot][available], y[pilot][available], x[test][mask], y[test][mask], q[mask], ids[mask], True


def evaluate(replays):
    rows = {}
    rng = np.random.default_rng(SEED + 4)
    for n, x, answers, held, truth, qwen, ids, has_refusal in replays:
        _, inverse, count = np.unique(ids, return_inverse=True, return_counts=True)
        weights = 1 / count[inverse] / len(count)
        stats = softmax(held @ fit_products(x, answers, nonpositive_price=True), axis=-1)
        corrected = align(qwen, weights @ stats, weights)
        shuffled = align(qwen[rng.permutation(len(qwen))], weights @ stats, weights)
        forecasts = {'stats': stats, 'raw_mix': (1 - WEIGHT) * stats + WEIGHT * qwen,
                     'aligned_mix': (1 - WEIGHT) * stats + WEIGHT * corrected,
                     'aligned_shuffled_mix': (1 - WEIGHT) * stats + WEIGHT * shuffled,
                     'uniform_mix': (1 - WEIGHT) * stats + WEIGHT / stats.shape[1]}
        refusal = (answers[:, 0].sum() + .5) / (len(answers) + 1)
        row = {}
        for method, pred in forecasts.items():
            if has_refusal:
                pred = np.column_stack((np.full(len(pred), refusal), (1 - refusal) * pred))
            if method.startswith('aligned') and not np.allclose(weights @ pred, row_share, atol=1e-9, rtol=0):
                raise ValueError('Aligned blend changed the aggregate shares')
            if method == 'stats':
                row_share = weights @ pred
            error = pred - truth
            row[method] = [float(weights @ np.square(error).sum(axis=1)),
                           float(np.abs(weights @ error).sum() * 50)]
        rows.setdefault(n, []).append(row)
    results = {}
    for n, runs in rows.items():
        scores = {key: np.array([row[key] for row in runs]) for key in runs[0]}
        gains = {}
        for ref in ('stats', 'raw_mix', 'uniform_mix', 'aligned_shuffled_mix'):
            delta = scores[ref][:, 0] - scores['aligned_mix'][:, 0]
            gains[ref] = {'mean': float(delta.mean()), 'wins': int((delta > 1e-10).sum()),
                          'pilot_p05_p95': np.quantile(delta, [.05, .95]).tolist()}
        results[n] = {'brier': {k: float(v[:, 0].mean()) for k, v in scores.items()},
                      'share_error_pp': {k: float(v[:, 1].mean()) for k, v in scores.items()},
                      'aligned_gain': gains}
    return results


if __name__ == '__main__':
    studies = {'canada': canada_replays, 'swissmetro': swiss_replays,
               'electricity': electricity_replays, 'streaming': streaming_replays}
    print(json.dumps({'seed': SEED, 'new_model_calls': 0, 'replays': REPLAYS, 'qwen_weight': WEIGHT,
                      'studies': {name: evaluate(replays()) for name, replays in studies.items()}}, indent=2))
