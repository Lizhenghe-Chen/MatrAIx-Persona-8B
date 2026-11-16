"""Evaluate transferring no-buy rates to a study with little or no local data."""
import json

import numpy as np

import dryer_refusal as dryer
import shortbread_pilot
from adaptive_pilot import spanish
from cheese_pilot import evaluation_inputs, load_deck
from optout_pilot import REPEATS, SEED, load, split_cards

SIZES = (0, 5, 10, 25)
PRIOR_WEIGHT = 10


def evaluate(p, y, keys, prior):
    rng = np.random.default_rng(SEED)
    results = {size: [] for size in SIZES}
    for _ in range(REPEATS):
        available = split_cards(keys, rng)
        order = rng.permutation(len(y))
        test = order[max(SIZES):]
        actual = y[test]
        held = ~available[test]
        # This offset uses only predictions on the target evaluation cards.
        deviations = p[test] - p[test][held].mean()
        for size, rows in results.items():
            pilot = order[:size]
            picked = available[pilot]
            rates = (y[pilot] * picked).sum(axis=1) / picked.sum(axis=1)
            local = (rates.sum() + .5) / (size + 1)
            blended = (rates.sum() + PRIOR_WEIGHT * prior) / (size + PRIOR_WEIGHT)
            methods = {'qwen': p[test], 'half': .5, 'historical': prior,
                       'local': local, 'historical_plus_local': blended,
                       'historical_with_qwen_variation': np.clip(prior + .5 * deviations, 0., 1.)}
            rows.append({key: float(np.mean(np.where(held, (estimate - actual)**2, 0.).sum(axis=1)
                                            / held.sum(axis=1)))
                         for key, estimate in methods.items()})
    output = {}
    for size, rows in results.items():
        output[size] = {k: float(np.mean([r[k] for r in rows])) for k in rows[0]}
        comparison = 'qwen' if size == 0 else 'local'
        candidate = 'historical' if size == 0 else 'historical_plus_local'
        delta = np.asarray([r[comparison] - r[candidate] for r in rows])
        output[size]['comparison'] = {'against': comparison, 'candidate': candidate,
                                      'p05_p95': np.quantile(delta, [.05, .95]).tolist(),
                                      'win_rate': float(np.mean(delta > 1e-10))}
    return output


def main():
    foods = load()
    foods.pop('german')  # The study manipulates packaging surcharges.
    foods['spain'] = spanish()
    foods['italy'] = evaluation_inputs(*load_deck())[0]
    foods['scotland'] = shortbread_pilot.evaluation_inputs(*shortbread_pilot.load_deck())[0]
    arrays = {k: (p[..., 0], y[..., 0], keys) for k, (p, y, keys, _, _) in foods.items()}
    jobs, _, groups = dryer.deck()
    predicted, identities = dryer.predictions(jobs, dryer.RUN)
    if len(identities) != 1:
        raise ValueError('Mixed dryer model identities')
    for key, group in groups.items():
        ordered = [dict(sorted(person.items())) for person in group.values()]
        p, y = dryer.outcome(predicted, ordered)
        arrays[key] = p[..., 0], y[..., 0], np.asarray([list(person) for person in ordered])
    families = {'beer': ('beer',), 'food_archive': ('spain', 'italy', 'scotland'),
                'dryer': ('USA', 'CAN')}
    rates = {name: float(y.mean()) for name, (_, y, _) in arrays.items()}
    source_rates = {family: float(np.mean([rates[name] for name in names]))
                    for family, names in families.items()}
    results = {}
    for family, names in families.items():
        sources = {key: rate for key, rate in source_rates.items() if key != family}
        prior = float(np.mean(list(sources.values())))
        for name in names:
            p, y, keys = arrays[name]
            results[name] = {'people': len(y), 'actual_rate': rates[name], 'qwen_rate': float(p.mean()),
                             'prior_rate': prior, 'source_rates': sources, 'budgets': evaluate(p, y, keys, prior)}
    print(json.dumps({'seed': SEED, 'splits': REPEATS, 'new_calls': 0,
                      'prior_equivalent_people': PRIOR_WEIGHT, 'studies': results}, indent=2))


if __name__ == '__main__':
    main()
