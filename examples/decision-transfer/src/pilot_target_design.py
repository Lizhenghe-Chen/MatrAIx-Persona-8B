"""Replay equal-cost pilot designs with or without known deployment offers."""
import json

import numpy as np
from scipy.special import softmax

from attribute_regularization import PENALTY_MULTIPLIER
from choice_predictor import fit_products
import electricity_replication as electricity
from order_screen import SEED
import streaming_price_mix as streaming

TASKS = 4
BUDGETS = (5, 10, 25)
REPLAYS = 100


def inputs(study):
    if study == 'electricity':
        cards, inverse, people, truth, held = electricity.load()
        test = np.isin(inverse, held)
        price = cards[..., 0]
        x = np.concatenate((cards[..., 1:], np.where(price > 0, price - 8, 0)[..., None]), axis=-1)
        y = np.column_stack((np.zeros(len(truth)), truth))
        return x[inverse], y, people, ~test, test, False

    features, truth, train, test = streaming.load()
    x = np.concatenate((features[..., 1:], (features[..., :1] - 9.99) / 2), axis=-1)
    people = np.repeat(np.arange(len(truth)), truth.shape[1])
    return x.reshape(len(people), *x.shape[2:]), truth.reshape(len(people), truth.shape[-1]), people, train.ravel(), test.ravel(), True


def information(x):
    centered = x - x.mean(axis=1, keepdims=True)
    return np.einsum('nai,naj->nij', centered, centered) / x.shape[1]


def select(pools, info, prior, objective):
    """Select one available card per person each round, updating shared information."""
    remaining = [pool.copy() for pool in pools]
    matrix = prior.copy()
    selected = []
    for _ in range(TASKS):
        for i, pool in enumerate(remaining):
            candidates = matrix + info[pool]
            j = int(np.argmax(objective(candidates)))
            selected.append(pool[j])
            matrix = candidates[j]
            remaining[i] = np.delete(pool, j)
    return selected


def evaluate(study):
    x, y, people, available, held, has_refusal = inputs(study)
    info = information(x)
    # All held-out offer features are public design inputs. No labels or respondent
    # frequencies enter the design. Weight each distinct unordered card once.
    order = np.lexsort(tuple(x[..., col] for col in range(x.shape[-1] - 1, -1, -1)), axis=1)
    canonical = np.take_along_axis(x[held], order[held, :, None], axis=1)
    target = information(np.unique(canonical, axis=0)).mean(axis=0)
    pools = {person: np.flatnonzero((people == person) & available) for person in np.unique(people)}
    if any(len(pool) < TASKS for pool in pools.values()):
        raise ValueError('A respondent has too few available cards')
    scale = 1 / np.sqrt(PENALTY_MULTIPLIER)
    splits = np.random.default_rng(SEED + 1)
    controls = np.random.default_rng(SEED + 2)
    more_people_rng = np.random.default_rng(SEED + 3)
    rows = {n: [] for n in BUDGETS}
    for _ in range(REPLAYS):
        order = splits.permutation(list(pools))
        test = held & ~np.isin(people, order[:max(BUDGETS)])
        ids, ix, count = np.unique(people[test], return_inverse=True, return_counts=True)
        weights = 1 / count[ix] / len(ids)
        for n in BUDGETS:
            eligible = [pools[person] for person in order[:n]]
            # Scale the Fisher information to match the fitter's mean-loss L2 objective.
            prior = .02 * PENALTY_MULTIPLIER * n * TASKS * np.eye(x.shape[-1])
            designs = {
                'random': np.concatenate([controls.choice(pool, TASKS, replace=False) for pool in eligible]),
                'cover_attributes': select(eligible, info, prior, lambda m: np.linalg.slogdet(m)[1]),
                'cover_target': select(eligible, info, prior, lambda m: -np.einsum('nij,ji->n', np.linalg.inv(m), target)),
            }
            if 2 * n <= max(BUDGETS):
                designs['more_people'] = np.concatenate([
                    more_people_rng.choice(pools[person], TASKS // 2, replace=False) for person in order[:2 * n]
                ])
            scores = {}
            for name, train in designs.items():
                answers = y[train]
                refusal = (answers[:, 0].sum() + .5) / (len(answers) + 1) if has_refusal else 0
                beta = fit_products(x[train] * scale, answers, nonpositive_price=True)
                p = softmax((x[test] * scale) @ beta, axis=-1)
                prediction = np.column_stack((np.full(len(p), refusal), (1 - refusal) * p))
                scores[name] = float(weights @ np.square(prediction - y[test]).sum(axis=-1))
            rows[n].append(scores)
    budgets = {}
    for n, runs in rows.items():
        scores = {name: np.array([row[name] for row in runs]) for name in runs[0]}
        gains = {}
        comparisons = [('random', 'cover_attributes'), ('random', 'cover_target'),
                       ('cover_attributes', 'cover_target')]
        if 'more_people' in scores:
            comparisons.append(('random', 'more_people'))
        for reference, candidate in comparisons:
            gain = scores[reference] - scores[candidate]
            gains[f'{candidate}_over_{reference}'] = {
                'mean': float(gain.mean()), 'wins': int((gain > 1e-10).sum()),
                'p05_p95': np.quantile(gain, [.05, .95]).tolist(),
            }
        budgets[n] = {'brier': {name: float(values.mean()) for name, values in scores.items()}, 'gains': gains}
    return {'available_tasks_per_person': [min(map(len, pools.values())), max(map(len, pools.values()))],
            'evaluation_people': len(ids), 'unique_target_cards': len(np.unique(canonical, axis=0)),
            'budgets': budgets}


if __name__ == '__main__':
    print(json.dumps({'seed': SEED, 'replays': REPLAYS, 'tasks_per_pilot_person': TASKS,
                      'penalty_multiplier': PENALTY_MULTIPLIER, 'new_model_calls': 0,
                      'studies': {study: evaluate(study) for study in ('electricity', 'streaming')}}, indent=2))
