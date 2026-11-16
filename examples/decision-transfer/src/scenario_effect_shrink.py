"""Evaluate conservative effect forecasts with whole-study holdouts."""
import json

import numpy as np

from order_screen import SEED, read, result_path
import paired_scenario_screen as paired

METHODS = ('separate', 'joint')
FIXED_STRENGTH = .25


def load():
    studies = {'beer': paired.beer_cases(), 'tomato': paired.tomato_cases(), 'beef': paired.beef_cases()}
    output, identities = {}, set()
    for name, cards in studies.items():
        directory = paired.RUN.with_name('paired-scenario-beef-v1') if name == 'beef' else paired.RUN
        jobs = paired.prepare({name: cards})
        frozen = {result_path(job, directory) for job in read(directory / 'jobs.json')}
        responses = {}
        for job in jobs:
            path = result_path(job, directory)
            if path not in frozen:
                raise ValueError('Response does not belong to the frozen experiment')
            result = read(path)
            if result['status'] != 'ok':
                raise ValueError('Incomplete paired result')
            responses[job['card'], job['arm']] = result['p']
            identities.add(json.dumps(result['identity'], sort_keys=True))
        forecasts = {method: [] for method in METHODS}
        observed, focus_indices = [], []
        for question, _, _, _, counts, focus in cards:
            card, keys = question['id'], list(question['options'])
            shares = np.array([[count[key] / sum(count.values()) for key in keys] for count in counts])
            observed.append(shares[1] - shares[0])
            focus_indices.append([key in focus for key in keys])
            for method in METHODS:
                arms = ('joint', 'joint') if method == 'joint' else ('separate_control', 'separate_treatment')
                values = np.array([[responses[card, arm][f'{card}-{i}'][key] for key in keys]
                                   for i, arm in enumerate(arms, 1)])
                forecasts[method].append(values[1] - values[0])
        output[name] = np.asarray(observed), {key: np.asarray(value) for key, value in forecasts.items()}, np.asarray(focus_indices)
    if len(identities) != 1:
        raise ValueError('Mixed model identities')
    return output, json.loads(identities.pop())


def fit_strength(sources, method):
    """Minimize study-balanced absolute share-change error over one scale in [0, 1]."""
    ratios, weights = [], []
    for truth, forecasts, _ in sources:
        p = forecasts[method]
        nonzero = np.abs(p) > 1e-12
        ratios.extend((truth[nonzero] / p[nonzero]).tolist())
        weights.extend((np.abs(p[nonzero]) / len(p)).tolist())
    if not weights:
        return 0.
    order = np.argsort(ratios)
    cumulative = np.cumsum(np.asarray(weights)[order])
    median = np.asarray(ratios)[order][np.searchsorted(cumulative, cumulative[-1] / 2)]
    return float(np.clip(median, 0., 1.))


def score(data, held_study):
    y, forecasts, focus = data[held_study]
    sources = [rows for name, rows in data.items() if name != held_study]
    zero = .5 * np.abs(y).sum(axis=1)
    draws = np.random.default_rng(SEED).integers(len(y), size=(2000, len(y)))
    output = {}
    single_source = {}
    for method, p in forecasts.items():
        strengths = {'raw': 1., 'fixed': FIXED_STRENGTH, 'transferred': fit_strength(sources, method)}
        single_source[method] = {
            name: fit_strength([rows], method) for name, rows in data.items() if name != held_study
        }
        for label, strength in strengths.items():
            forecast = strength * p
            loss = .5 * np.abs(forecast - y).sum(axis=1)
            improvement = zero - loss
            output[f'{method}_{label}'] = {
                'weight': strength, 'error': float(loss.mean()),
                'focus_change': float(np.sum(forecast * focus, axis=1).mean()),
                'gain_over_zero': float(improvement.mean()),
                'gain_interval_95': np.quantile(improvement[draws].mean(axis=1), [.025, .975]).tolist(),
            }
    return {'cards': len(y), 'source_studies': sorted(set(data) - {held_study}),
            'zero_error': float(zero.mean()), 'human_focus_change': float(np.sum(y * focus, axis=1).mean()),
            'methods': output, 'weight_if_using_only_one_source': single_source}


if __name__ == '__main__':
    data, identity = load()
    print(json.dumps({'identity': identity, 'seed': SEED, 'new_model_calls': 0,
                      'studies': {name: score(data, name) for name in data}}, indent=2))
