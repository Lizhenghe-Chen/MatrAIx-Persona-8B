"""Replay two-question preference elicitation with a frozen statistical updater."""
from itertools import combinations
import json

import numpy as np
from scipy.special import xlogy

from adaptive_pilot import spanish
import cheese_pilot
import optout_pilot as pilot
from order_screen import SEED
from personal_choice_products import STRENGTH, prepare, split
from personal_choice_update import loss, preference_components
import shortbread_pilot


def expected_gain(likelihood, prior, target_predictions):
    """Expected reduction in squared prediction loss for a set of questions."""
    weighted = likelihood * prior
    outcome_probability = weighted.sum(axis=-1)
    posterior = weighted / outcome_probability[:, None]
    baseline = target_predictions @ prior
    difference = posterior @ target_predictions.T - baseline
    return outcome_probability @ np.square(difference).sum(axis=1)


def information(likelihood, prior):
    marginal = likelihood @ prior
    return float(np.sum(xlogy(likelihood, likelihood / marginal[:, None]) * prior))


def evaluate(y, keys, x):
    features, answers, beta, history, target, *_ = prepare(y, keys, x)
    train, held = split(x, keys, np.random.default_rng(SEED))
    width = keys.shape[1]
    candidate_pool = train
    if not held.ravel()[target].all() or not train.ravel()[history].all():
        raise ValueError('History and target partition changed')
    people = target[:, 0] // width
    truth = answers[target]
    rows, sizes, selections = [], [], []
    for i, person in enumerate(people):
        pool = person * width + np.flatnonzero(candidate_pool[person])
        if len(pool) < 2:
            raise ValueError('Too few history candidates')
        # Candidate predictions use only the offer matrix and population fit.
        log_p, prior, target_p = preference_components(
            features, np.zeros_like(answers), beta, pool[None, :], target[i:i + 1], STRENGTH)
        p = np.exp(log_p[0])
        prior = prior[0]
        target_p = target_p[0]
        target_flat = target_p.reshape(-1, len(prior))
        pairs = np.array(list(combinations(range(len(pool)), 2)))
        likelihoods = [(p[a, :, None, :] * p[b, None, :, :]).reshape(-1, len(prior)) for a, b in pairs]
        info = np.array([information(like, prior) for like in likelihoods])
        utility = np.array([expected_gain(like, prior, target_flat) for like in likelihoods])
        info_index, utility_index = int(info.argmax()), int(utility.argmax())
        # Adaptive arm selects the first question without answers, then uses
        # only the first observed answer to select the second.
        first = max(range(len(pool)), key=lambda j: expected_gain(p[j], prior, target_flat))
        observed = answers[pool].argmax(axis=1)
        conditional = prior * p[first, observed[first]]
        conditional /= conditional.sum()
        second = max((j for j in range(len(pool)) if j != first),
                     key=lambda j: expected_gain(p[j], conditional, target_flat))

        def predict(a, b):
            weight = prior * p[a, observed[a]] * p[b, observed[b]]
            return target_p @ (weight / weight.sum())

        all_predictions = np.array([predict(a, b) for a, b in pairs])
        random_losses = loss(all_predictions, truth[i])
        adaptive = predict(first, second)
        rows.append([
            float(loss(target_p @ prior, truth[i])),
            float(loss(np.array([target_p @ (w / w.sum())
                                 for w in prior * p[np.arange(len(pool)), observed]]), truth[i]).mean()),
            float(random_losses.mean()),
            float(random_losses[info_index]),
            float(random_losses[utility_index]),
            float(loss(adaptive, truth[i])),
        ])
        sizes.append(len(pool))
        selections.append((info_index == utility_index,
                           tuple(sorted((first, second))) == tuple(pairs[utility_index])))

    methods = ('no_history', 'random_single', 'random_pair', 'information_pair', 'target_pair', 'adaptive')
    errors = np.array(rows)
    boot = np.random.default_rng(SEED + 1).integers(len(errors), size=(2000, len(errors)))
    comparisons = {}
    for method in ('information_pair', 'target_pair', 'adaptive'):
        delta = errors[:, methods.index('random_pair')] - errors[:, methods.index(method)]
        comparisons[method] = {'mean': float(delta.mean()),
                               'ci95': np.quantile(delta[boot].mean(axis=1), [.025, .975]).tolist()}
    adaptive_gain = errors[:, methods.index('target_pair')] - errors[:, methods.index('adaptive')]
    return {'people': len(people), 'people_with_more_than_two_candidates': int(np.sum(np.array(sizes) > 2)),
            'candidate_range': [min(sizes), max(sizes)], 'history_questions': 2,
            'selection_overlap': np.mean(selections, axis=0).tolist(),
            'brier': dict(zip(methods, errors.mean(axis=0).tolist(), strict=True)),
            'gains_vs_random': comparisons,
            'adaptive_vs_target_pair': {'mean': float(adaptive_gain.mean()),
                                        'ci95': np.quantile(adaptive_gain[boot].mean(axis=1), [.025, .975]).tolist()}}


def main():
    studies = {**pilot.load(), 'spain': spanish(),
               'italy': cheese_pilot.evaluation_inputs(*cheese_pilot.load_deck())[0],
               'scotland': shortbread_pilot.evaluation_inputs(*shortbread_pilot.load_deck())[0]}
    print(json.dumps({'seed': SEED, 'new_model_calls': 0, 'strength': STRENGTH,
                      'studies': {name: evaluate(y, keys, x) for name, (_, y, keys, _, x) in studies.items()}},
                     indent=2))


if __name__ == '__main__':
    main()
