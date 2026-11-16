"""Validate short-pilot allocation on the Swissmetro stated-choice benchmark."""
from hashlib import sha256
import json

import numpy as np
import pandas as pd
from scipy.special import softmax

from attribute_regularization import PENALTY_MULTIPLIER
from choice_predictor import fit_products
from order_screen import SEED, WORK

SOURCE = WORK / 'swissmetro-admission/swissmetro.dat'
URL = 'https://raw.githubusercontent.com/michelbierlaire/biogeme/master/src/biogeme/data/data/swissmetro.dat'
DIGEST = '27432693cf052985d79a950b4b888be3efca798fc89b0d3ffefe40608ede00f2'
DESIGNS = ((5, 4), (10, 2), (20, 1), (10, 4), (20, 2), (40, 1), (10, 1))
COMPARISONS = (((5, 4), (10, 2)), ((5, 4), (20, 1)), ((10, 4), (20, 2)),
               ((10, 4), (40, 1)), ((5, 4), (10, 1)), ((10, 4), (20, 1)))
REPLAYS = 100


def load():
    if sha256(SOURCE.read_bytes()).hexdigest() != DIGEST:
        raise ValueError('Unexpected Swissmetro version')
    frame = pd.read_csv(SOURCE, sep='\t')
    eligible = frame.CHOICE.isin((1, 2, 3)) & frame.SP.eq(1)
    eligible &= frame[['TRAIN_AV', 'SM_AV', 'CAR_AV']].eq(1).all(axis=1)
    f = frame.loc[eligible].sort_values('ID', kind='stable')
    if frame.shape != (10728, 28) or len(f) != 9036 or not f.groupby('ID').size().eq(9).all():
        raise ValueError('Unexpected Swissmetro panel layout')
    # Alternative-specific constants, plus generic time and effective trip cost.
    time = f[['TRAIN_TT', 'SM_TT', 'CAR_TT']].to_numpy() / 100
    cost = f[['TRAIN_CO', 'SM_CO', 'CAR_CO']].to_numpy(dtype=float)
    cost[f.GA.eq(1), :2] = 0
    constants = np.broadcast_to([[1, 0], [0, 1], [0, 0]], (len(f), 3, 2))
    x = np.concatenate((constants, time[..., None], cost[..., None] / 100), axis=-1)
    y = np.eye(4)[f.CHOICE.to_numpy()]
    return x.reshape(-1, 9, 3, 4), y.reshape(-1, 9, 4)


def evaluate(x, y):
    rng = np.random.default_rng(SEED)
    # Freeze two tasks per person, independent of responses. Exclude matching
    # effective choice sets from every pilot; alternatives have fixed identities.
    selected = np.argsort(rng.random(x.shape[:2]), axis=1)[:, :2]
    test = np.zeros(x.shape[:2], dtype=bool)
    np.put_along_axis(test, selected, True, axis=1)
    _, cards = np.unique(x.reshape(-1, 12), axis=0, return_inverse=True)
    cards = cards.reshape(test.shape)
    available = ~np.isin(cards, cards[test])
    pools = [np.flatnonzero(mask) for mask in available]
    eligible = np.array([i for i, pool in enumerate(pools) if len(pool) >= 4])
    if len(eligible) < 40 or not np.all(available.sum(axis=1) <= 7):
        raise ValueError('Infeasible pilot split')
    scaled = x / np.sqrt(PENALTY_MULTIPLIER)
    scores = {design: [] for design in DESIGNS}
    evaluated = []
    for _ in range(REPLAYS):
        # This common 40-person pool keeps the evaluated respondents identical
        # for every design. Within person, the short design uses nested cards.
        cohort = rng.choice(eligible, 40, replace=False)
        cards_by_person = np.stack([rng.choice(pools[i], 4, replace=False) for i in cohort])
        is_evaluation = test.copy()
        is_evaluation[cohort] = False
        truth = y[is_evaluation][:, 1:]
        evaluated.append(len(truth))
        for design in DESIGNS:
            people, tasks = design
            person = cohort[:people, None]
            task = cards_by_person[:people, :tasks]
            pilot_x = scaled[person, task].reshape(-1, 3, 4)
            pilot_y = y[person, task].reshape(-1, 4)
            beta = fit_products(pilot_x, pilot_y, nonpositive_price=True)
            prediction = softmax(scaled[is_evaluation] @ beta, axis=-1)
            scores[design].append(np.square(prediction - truth).sum(axis=-1).mean())
    summary = {}
    for ref, cand in COMPARISONS:
        delta = np.array(scores[ref]) - scores[cand]
        summary[f'{label(cand)}_vs_{label(ref)}'] = {
            'mean_gain': float(delta.mean()), 'wins': int((delta > 1e-10).sum()),
            'p05_p95': np.quantile(delta, [.05, .95]).tolist(),
        }
    return {'source': URL, 'source_sha256': DIGEST, 'seed': SEED, 'replays': REPLAYS,
            'new_model_calls': 0, 'penalty_multiplier': PENALTY_MULTIPLIER,
            'people': len(y), 'tasks': int(np.prod(y.shape[:2])), 'pilot_eligible_people': len(eligible),
            'evaluation_tasks_per_replay': sorted(set(evaluated)),
            'unique_target_cards': int(len(np.unique(cards[test]))),
            'brier': {label(key): float(np.mean(value)) for key, value in scores.items()},
            'comparisons': summary}


def label(design):
    return f'{design[0]}x{design[1]}'


if __name__ == '__main__':
    print(json.dumps(evaluate(*load()), indent=2))
