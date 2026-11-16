"""Hold people and prediction cards fixed while varying the two-question pool."""
from itertools import combinations
import json

import numpy as np

from choice_predictor import fit_products
from order_screen import SEED
from personal_choice_products import STRENGTH
from personal_choice_update import cohort, data, loss, preference_components
from personal_question_design import expected_gain

STUDIES = ('electricity', 'streaming', 'swissmetro')
POOL_SIZES = (3, 4, 6)


def replay(study):
    x, y, people, available, held = data(study)
    rng = np.random.default_rng(SEED)
    ids = rng.permutation(np.unique(people))
    fit_ids, dev_ids, test_ids = np.split(ids, [int(.6 * len(ids)), int(.8 * len(ids))])
    fit = available & np.isin(people, fit_ids)
    beta = fit_products(x[fit], np.column_stack((np.zeros(fit.sum()), y[fit])), nonpositive_price=True)
    cohort(people, dev_ids, available, held, rng)  # Preserve the original target draw.
    _, targets, excluded = cohort(people, test_ids, available, held, rng)
    pools = [np.flatnonzero(available & (people == people[target[0]])) for target in targets]
    # Restrict all pool sizes to one common cohort within each study.
    eligible = np.array([len(pool) >= max(POOL_SIZES) for pool in pools])
    if not eligible.any():
        raise ValueError('No comparable candidates across pool sizes')
    rows = {size: [] for size in POOL_SIZES}
    blind_answers = np.zeros_like(y)
    for pool, target in zip(pools, targets, strict=True):
        if len(pool) < max(POOL_SIZES):
            continue
        if np.intersect1d(pool, target).size or not np.all(people[target] == people[pool[0]]):
            raise ValueError('History pool overlaps or mismatches targets')
        log_p, weights, target_p = preference_components(
            x, blind_answers, beta, pool[None, :], target[None, :], STRENGTH)
        p = np.exp(log_p[0])
        prior = weights[0]
        target_p = target_p[0]
        flat_target = target_p.reshape(-1, len(prior))
        pairs = np.array(list(combinations(range(len(pool)), 2)))
        pair_index = {tuple(pair): i for i, pair in enumerate(pairs)}
        scores = np.array([expected_gain((p[a, :, None] * p[b, None, :]).reshape(-1, len(prior)),
                                         prior, flat_target) for a, b in pairs])
        # Actual history answers are used only after all question-pair scores
        # are computed. Test answers only enter the paired loss calculation.
        observed = p[np.arange(len(pool)), y[pool].argmax(axis=1)]
        posterior = prior * observed[pairs].prod(axis=1)
        posterior /= posterior.sum(axis=1, keepdims=True)
        errors = loss(np.einsum('tak,nk->nta', target_p, posterior), y[target])
        random_error = errors.mean()
        for size in POOL_SIZES:
            indices = np.array([[pair_index[pair] for pair in combinations(subset, 2)]
                                for subset in combinations(range(len(pool)), size)])
            best = indices[np.arange(len(indices)), scores[indices].argmax(axis=1)]
            if not np.isclose(errors[indices].mean(), random_error, atol=1e-12, rtol=0):
                raise ValueError('Random-pair baseline changed across pool sizes')
            rows[size].append([float(random_error), float(errors[best].mean())])
    bootstrap = np.random.default_rng(SEED + 1).integers(int(eligible.sum()), size=(2000, int(eligible.sum())))
    gains = {}
    for size, scores in rows.items():
        a = np.array(scores)
        delta = a[:, 0] - a[:, 1]
        gains[size] = {'random_brier': float(a[:, 0].mean()), 'targeted_brier': float(a[:, 1].mean()),
                       'gain': float(delta.mean()), 'ci95': np.quantile(delta[bootstrap].mean(axis=1), [.025, .975]).tolist()}
    small, large = (np.array(rows[size])[:, 1] for size in (min(POOL_SIZES), max(POOL_SIZES)))
    change = small - large
    return {'fit_people': len(fit_ids), 'test_people': int(eligible.sum()),
            'excluded_people': int(excluded + (~eligible).sum()), 'pool_sizes': gains,
            'six_vs_three_gain': float(change.mean()),
            'six_vs_three_ci95': np.quantile(change[bootstrap].mean(axis=1), [.025, .975]).tolist()}


if __name__ == '__main__':
    print(json.dumps({'seed': SEED, 'strength': STRENGTH, 'new_calls': 0,
                      'studies': {study: replay(study) for study in STUDIES}}, indent=2))
