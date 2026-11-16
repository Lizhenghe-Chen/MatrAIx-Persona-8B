"""Test if training-household switching destinations improve dated purchase forecasts."""
from collections import Counter, defaultdict
import json

import numpy as np
import pandas as pd

from dated_purchase_repeat import CATEGORIES, CUTOFF, HASHES, load, partition
from order_screen import SEED

PSEUDO_COUNT = 20
METHODS = ('market', 'global_switch', 'last_label_switch')


def distribution(counts, catalogue):
    p = np.zeros(len(catalogue) + 1)
    for label, count in counts.items():
        p[catalogue[label]] = count
    return p


def evaluate(series, cutoff):
    counts, fit, test, excluded = partition(series, cutoff)
    switched = Counter()
    transitions = defaultdict(Counter)
    for seen, chosen, _ in fit:
        if chosen not in seen:
            switched[chosen] += 1
            transitions[seen[-1]][chosen] += 1
    catalogue = {label: i for i, label in enumerate(sorted(counts))}
    unknown = len(catalogue)
    market = distribution(counts, catalogue) + .5
    global_switch = distribution(switched, catalogue) + .5
    transition_arrays = {label: distribution(row, catalogue) for label, row in transitions.items()}
    repeat_rate = (len(fit) - switched.total() + .5) / (len(fit) + 1)
    full_losses, conditional_losses, coverage = [], [], []
    for seen, chosen, _ in test:
        extras = {label: unknown + 1 + i for i, label in enumerate(sorted(set(seen) - catalogue.keys()))}
        local = {**catalogue, **extras}
        indices = [local[label] for label in seen]
        destination = local.get(chosen, unknown)
        own = np.bincount(indices, minlength=len(local) + 1) / 2

        def masked(p, fill):
            p = np.r_[p, np.full(len(extras), fill)]
            p[indices] = 0
            return p

        market_dest = masked(market, .5)
        market_dest /= market_dest.sum()
        global_dest = masked(global_switch, .5)
        global_dest /= global_dest.sum()
        recent = transition_arrays.get(seen[-1], np.zeros_like(market))
        local_counts = masked(recent, 0.)
        recent_dest = local_counts + PSEUDO_COUNT * global_dest
        recent_dest /= recent_dest.sum()
        candidates = np.array([market_dest, global_dest, recent_dest])
        full = repeat_rate * own + (1 - repeat_rate) * candidates
        full_losses.append((full**2).sum(axis=1) + 1 - 2 * full[:, destination])
        if chosen not in seen:
            conditional_losses.append((candidates**2).sum(axis=1) + 1 - 2 * candidates[:, destination])
            coverage.append(local_counts.sum() > 0)

    def summarize(rows):
        scores = np.array(rows)
        rng = np.random.default_rng(SEED + 1)
        boot = rng.integers(len(scores), size=(2000, len(scores)))
        comparisons = {}
        for a, b in ((0, 1), (0, 2), (1, 2)):
            delta = scores[:, a] - scores[:, b]
            comparisons[f'{METHODS[b]}_over_{METHODS[a]}'] = {
                'mean': float(delta.mean()), 'ci95': np.quantile(delta[boot].mean(axis=1), [.025, .975]).tolist(),
            }
        return {'brier': dict(zip(METHODS, scores.mean(axis=0).tolist(), strict=True)), 'comparisons': comparisons}

    return {'test_households': len(test), 'observed_switches': len(conditional_losses),
            'training_switches': switched.total(), 'excluded': dict(excluded),
            'switches_with_matching_transition': int(sum(coverage)),
            'fixed_repeat_probability': repeat_rate, 'full_prediction': summarize(full_losses),
            'conditional_switch_destination': summarize(conditional_losses)}


if __name__ == '__main__':
    data = load()
    print(json.dumps({'sources': HASHES, 'seed': SEED, 'new_calls': 0,
                      'transition_prior_count': PSEUDO_COUNT,
                      'by_cutoff': {str(cutoff.date()): {c: evaluate(data.loc[c], cutoff) for c in CATEGORIES}
                                    for cutoff in (CUTOFF, pd.Timestamp('2017-07-01'))}}, indent=2))
