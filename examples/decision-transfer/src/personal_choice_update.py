"""Evaluate individual probability updates from two observed choices."""
import json

import numpy as np
from scipy.special import log_softmax, softmax

from choice_predictor import fit_products
from order_screen import SEED
from pilot_target_design import inputs
import swissmetro_pilot_allocation as swiss

STRENGTHS = (0., .25, .5, 1., 2.)


def data(study):
    if study == 'swissmetro':
        x, y = swiss.load()
        rng = np.random.default_rng(SEED)
        test = np.zeros(x.shape[:2], dtype=bool)
        selected = np.argsort(rng.random(x.shape[:2]), axis=1)[:, :2]
        np.put_along_axis(test, selected, True, axis=1)
        _, cards = np.unique(x.reshape(-1, 12), axis=0, return_inverse=True)
        cards = cards.reshape(test.shape)
        train = ~np.isin(cards, cards[test])
        people = np.repeat(np.arange(len(x)), x.shape[1])
        return x.reshape(-1, 3, 4), y.reshape(-1, 4)[:, 1:], people, train.ravel(), test.ravel()
    x, y, people, train, test, refusal = inputs(study)
    if refusal:
        # Model refusal alongside all four subscriptions. Its own indicator
        # lets evidence of willingness to subscribe enter the same update.
        offers = np.pad(x, ((0, 0), (1, 0), (1, 0)))
        offers[:, 0, 0] = 1
        return offers, y, people, train, test
    return x, y[:, 1:], people, train, test


def cohort(people, group, train, test, rng):
    history, target = [], []
    for person in group:
        known = np.flatnonzero((people == person) & train)
        held = np.flatnonzero((people == person) & test)
        if len(known) >= 2 and len(held) >= 2:
            history.append(rng.choice(known, 2, replace=False))
            target.append(rng.choice(held, 2, replace=False))
    return np.array(history), np.array(target), len(group) - len(history)


def preference_components(x, y, beta, history, target, strength, *, axes=None):
    # Each particle changes one utility coefficient; the central particle
    # leaves the population coefficients unchanged.
    directions = np.eye(len(beta)) * strength
    if axes is not None:
        directions = directions[list(axes)]
    particles = beta + np.vstack((np.zeros(len(beta)), directions, -directions))
    particles[:, -1] = np.minimum(particles[:, -1], 0)
    log_known = log_softmax(x[history] @ particles.T, axis=2)
    chosen = (log_known * y[history, :, None]).sum(axis=(1, 2))
    weights = softmax(chosen, axis=1)
    target_probabilities = softmax(x[target] @ particles.T, axis=2)
    return log_known, weights, target_probabilities


def forecasts(x, y, beta, history, target, strength, *, axes=None):
    _, weights, target_probabilities = preference_components(x, y, beta, history, target, strength, axes=axes)
    return {
        'population': softmax(x[target] @ beta, axis=2),
        'no_history': target_probabilities.mean(axis=-1),
        'own': np.einsum('ntak,nk->nta', target_probabilities, weights),
        'other': np.einsum('ntak,nk->nta', target_probabilities, np.roll(weights, 1, axis=0)),
    }


def loss(p, y):
    return np.square(p - y).sum(axis=-1).mean(axis=-1)


def evaluate(study):
    x, y, people, train, test = data(study)
    rng = np.random.default_rng(SEED)
    ids = rng.permutation(np.unique(people))
    fit_end, dev_end = int(.6 * len(ids)), int(.8 * len(ids))
    fit_ids, dev_ids, test_ids = np.split(ids, [fit_end, dev_end])
    fit = np.isin(people, fit_ids) & train
    beta = fit_products(x[fit], np.column_stack((np.zeros(fit.sum()), y[fit])), nonpositive_price=True)
    dev_history, dev_target, dev_excluded = cohort(people, dev_ids, train, test, rng)
    test_history, test_target, test_excluded = cohort(people, test_ids, train, test, rng)
    if len(dev_target) < 2 or len(test_target) < 2 or np.any(train & test):
        raise ValueError('Invalid person or task split')
    for history, target in ((dev_history, dev_target), (test_history, test_target)):
        if not (train[history].all() and test[target].all()
                and np.all(people[history] == people[target][:, :1])
                and np.all(people[target] == people[target][:, :1])):
            raise ValueError('Mismatched history and evaluation choices')
    dev = {s: float(loss(forecasts(x, y, beta, dev_history, dev_target, s)['own'], y[dev_target]).mean())
           for s in STRENGTHS}
    strength = min(dev, key=dev.get)
    truth = y[test_target]
    pred = forecasts(x, y, beta, test_history, test_target, strength)
    losses = {name: loss(p, truth) for name, p in pred.items()}
    bootstrap = np.random.default_rng(SEED + 1).integers(len(truth), size=(2000, len(truth)))
    gains = {}
    for name in ('population', 'no_history', 'other'):
        delta = losses[name] - losses['own']
        gains[name] = {'mean': float(delta.mean()),
                       'ci95': np.quantile(delta[bootstrap].mean(axis=1), [.025, .975]).tolist()}
    refusal = {}
    if study == 'streaming':
        refusal = {name: float(np.square(p[..., 0] - truth[..., 0]).mean())
                   for name, p in pred.items()}
    return {'fit_people': len(fit_ids), 'fit_choices': int(fit.sum()), 'dev_people': len(dev_target),
            'test_people': len(test_target), 'dev_excluded': dev_excluded, 'test_excluded': test_excluded,
            'refusal_binary_brier': refusal, 'dev_own_brier': dev, 'chosen_strength': strength,
            'brier': {k: float(v.mean()) for k, v in losses.items()}, 'own_gain': gains,
            'accuracy': {k: float(np.mean(p.argmax(axis=-1) == truth.argmax(axis=-1))) for k, p in pred.items()}}


if __name__ == '__main__':
    print(json.dumps({'seed': SEED, 'new_model_calls': 0,
                      'history_per_person': 2, 'test_choices_per_person': 2,
                      'studies': {study: evaluate(study) for study in ('electricity', 'streaming', 'swissmetro')}}, indent=2))
