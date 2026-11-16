"""Transfer the fixed two-choice update to five product surveys with opt-out."""
import json

import numpy as np

from adaptive_pilot import spanish
import cheese_pilot
from choice_predictor import fit_products
import optout_pilot as pilot
from order_screen import SEED
from personal_choice_update import cohort, forecasts, loss
import shortbread_pilot

STRENGTH = 2.0


def split(x, keys, rng):
    """Keep unordered offer profiles and repeated card IDs on one side."""
    flat = x.reshape(-1, *x.shape[2:])
    order = np.lexsort(tuple(flat[..., i] for i in reversed(range(flat.shape[-1]))), axis=1)
    canonical = np.take_along_axis(flat, order[..., None], axis=1)
    _, groups = np.unique(canonical, axis=0, return_inverse=True)
    groups = groups.reshape(keys.shape)
    # Draw a half deck per design block, then embargo any duplicate profile.
    held = ~pilot.split_cards(keys, rng)
    train = ~np.isin(groups, groups[held])
    if np.any(train & held):
        raise ValueError('Unexpected overlapping choice set')
    return train, held


def prepare(y, keys, x):
    rng = np.random.default_rng(SEED)
    train, held = split(x, keys, rng)
    order = rng.permutation(len(y))
    cut = int(.6 * len(y))
    fit_people, evaluation_people = order[:cut], order[cut:]
    fit = train & np.isin(np.arange(len(y)), fit_people)[:, None]
    offers = np.pad(x, ((0, 0), (0, 0), (1, 0), (1, 0)))
    offers[:, :, 0, 0] = 1
    answers = y[fit]
    beta = fit_products(offers[fit], np.column_stack((np.zeros(len(answers)), answers)),
                        nonpositive_price=True)
    people = np.repeat(np.arange(len(y)), y.shape[1])
    history, target, excluded = cohort(people, evaluation_people, train.ravel(), held.ravel(), rng)
    if len(target) < 2 or not np.all(people[history] == people[target][:, :1]):
        raise ValueError('Missing or mismatched product choice histories')
    flat_x = offers.reshape(-1, *offers.shape[2:])
    flat_y = y.reshape(-1, y.shape[-1])
    return flat_x, flat_y, beta, history, target, len(fit_people), len(answers), excluded


def evaluate(y, keys, x):
    flat_x, flat_y, beta, history, target, fit_people, fit_choices, excluded = prepare(y, keys, x)
    pred = forecasts(flat_x, flat_y, beta, history, target, STRENGTH)
    # Same update rule, but only the person's propensity to refuse can vary.
    pred['refusal_only'] = forecasts(flat_x, flat_y, beta, history, target, STRENGTH, axes=(0,))['own']
    # Keep exactly the full update's refusal probability; remove its effect on
    # the relative probabilities of the two purchase alternatives.
    population_products = pred['population'][..., 1:]
    population_products = population_products / population_products.sum(axis=-1, keepdims=True)
    own_refusal = pred['own'][..., :1]
    pred['same_refusal_population_products'] = np.concatenate(
        (own_refusal, (1 - own_refusal) * population_products), axis=-1)
    truth = flat_y[target]
    bootstrap = np.random.default_rng(SEED + 1).integers(len(truth), size=(2000, len(truth)))

    metrics = {
        'brier': {name: loss(p, truth) for name, p in pred.items()},
        'refusal_brier': {name: np.square(p[..., 0] - truth[..., 0]).mean(axis=1)
                          for name, p in pred.items()},
        'accuracy': {name: (p.argmax(axis=-1) == truth.argmax(axis=-1)).mean(axis=1)
                     for name, p in pred.items()},
    }
    gains = {}
    for metric in ('brier', 'refusal_brier'):
        values = metrics[metric]
        gains[metric] = {}
        for name in ('population', 'no_history', 'other', 'refusal_only', 'same_refusal_population_products'):
            delta = values[name] - values['own']
            gains[metric][name] = {'mean': float(delta.mean()),
                                  'ci95': np.quantile(delta[bootstrap].mean(axis=1), [.025, .975]).tolist()}
    return {'fit_people': fit_people, 'fit_choices': fit_choices, 'test_people': len(target),
            'excluded_test_people': excluded, 'test_refusals': int(truth[..., 0].sum()),
            **{metric: {name: float(v.mean()) for name, v in values.items()}
               for metric, values in metrics.items()}, 'own_gains': gains}


def main():
    studies = {**pilot.load(), 'spain': spanish(),
               'italy': cheese_pilot.evaluation_inputs(*cheese_pilot.load_deck())[0],
               'scotland': shortbread_pilot.evaluation_inputs(*shortbread_pilot.load_deck())[0]}
    print(json.dumps({'seed': SEED, 'strength': STRENGTH, 'new_model_calls': 0,
                      'history_choices': 2, 'test_choices_per_person': 2,
                      'studies': {name: evaluate(y, keys, x) for name, (_, y, keys, _, x) in studies.items()}},
                     indent=2))


if __name__ == '__main__':
    main()
