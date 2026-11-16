"""Compare frequency, recency and a simple refill interval on two real basket datasets."""
from collections import Counter, defaultdict
from hashlib import sha256
import json

import numpy as np

import grocery_next_basket as grocery
import retail_next_basket as retail

HALF_LIFE_DAYS = 30
MIN_INTERVALS = 20
PRIOR_INTERVALS = 3


def days(later, earlier):
    return max(1., (later - earlier).total_seconds() / 86400)


def intervals(history):
    occurrences = defaultdict(list)
    for date, basket in history:
        for item in basket:
            occurrences[item].append(date)
    return occurrences


def frequency_scores(occurrences, cutoff):
    return {item: sum(2 ** (-days(cutoff, date) / HALF_LIFE_DAYS) for date in dates)
            for item, dates in occurrences.items()}


def score_study(history, targets, cutoff, test, limit):
    train = set(history) - set(test)
    popularity, gaps = Counter(), defaultdict(list)
    for person in sorted(train):
        for item, dates in intervals(history[person]).items():
            popularity[item] += len(dates)
            gaps[item].extend(days(b, a) for a, b in zip(dates, dates[1:]))
    typical = {item: float(np.median(gap)) for item, gap in gaps.items() if len(gap) >= MIN_INTERVALS}
    fallback = sorted(popularity, key=lambda item: (-popularity[item], item))[:limit]
    scores = defaultdict(list)
    with_cycles = 0
    for person in test:
        prior = history[person]
        seen = intervals(prior)
        decay = frequency_scores(seen, cutoff)
        actual = set(targets[person])
        repeat = set(seen) & actual
        frequency = {item: len(dates) for item, dates in seen.items()}
        last_two = Counter(item for _, basket in prior[-2:] for item in basket)
        due = {}
        supported = False
        for item, dates in seen.items():
            elapsed = days(cutoff, dates[-1])
            own = [days(b, a) for a, b in zip(dates, dates[1:])]
            interval = typical.get(item)
            if interval is not None:
                interval = (PRIOR_INTERVALS * interval + sum(own)) / (PRIOR_INTERVALS + len(own))
            elif own:
                interval = float(np.median(own))
            if interval is None:
                due[item] = decay[item]
                continue
            supported = True
            # Upweight near the expected interval, with at most a twofold increase.
            distance = np.log2(elapsed / interval)
            due[item] = decay[item] * (1 + np.exp(-.5 * distance**2))
        with_cycles += supported
        for name, values in [('recent_two', last_two), ('all_frequency', frequency),
                             ('time_decay', decay), ('time_decay_with_cycle', due)]:
            ranked = sorted(values, key=lambda item: (-values[item], item))[:limit]
            picks = set(list(dict.fromkeys(ranked + fallback))[:limit])
            scores[name].append([len(picks & actual) / len(actual),
                                 len(picks & repeat) / len(repeat) if repeat else np.nan])
    arrays = {name: np.asarray(rows) for name, rows in scores.items()}
    rng = np.random.default_rng(grocery.SEED)
    comparisons = {}
    for name, left, right in (
        ('decay_over_recent_two', 'time_decay', 'recent_two'),
        ('cycle_over_decay', 'time_decay_with_cycle', 'time_decay'),
        ('frequency_over_recent_two', 'all_frequency', 'recent_two'),
    ):
        delta = (arrays[left] - arrays[right])[:, 0]
        draws = rng.integers(len(delta), size=(2000, len(delta)))
        comparisons[name] = {'delta': float(delta.mean()), 'interval_95': np.quantile(
            delta[draws].mean(axis=1), [.025, .975]).tolist()}
    return {'test': len(test), 'limit': limit, 'with_cycle_estimate': with_cycles,
            'training_households': len(train), 'products_with_population_interval': len(typical),
            'recall': {name: dict(zip(('all', 'repeat_only'), np.nanmean(value, axis=0).tolist(), strict=True))
                       for name, value in arrays.items()},
            'comparisons': comparisons}


def main():
    _, gh, gt, _ = grocery.load(dated=True)
    rh, rt, _, _ = retail.read_orders(retail.SOURCE, dated=True)
    grocery_eligible = sorted(person for person in gt if len(gh.get(person, [])) >= 2)
    grocery_test = sorted(np.random.default_rng(grocery.SEED).permutation(grocery_eligible)[::3].tolist())
    retail_test = sorted(person for person in rt if len(rh.get(person, [])) >= 2)
    print(json.dumps({
        'half_life_days': HALF_LIFE_DAYS, 'min_population_intervals': MIN_INTERVALS,
        'prior_intervals': PRIOR_INTERVALS, 'model_calls': 0, 'grocery_source': grocery.HASHES,
        'retail_source': sha256(retail.SOURCE.read_bytes()).hexdigest(),
        'studies': {
            'grocery': score_study(gh, gt, grocery.CUTOFF, grocery_test, grocery.K),
            'retail': score_study(rh, rt, retail.CUTOFF, retail_test, retail.K),
        },
    }, indent=2))


if __name__ == '__main__':
    main()
