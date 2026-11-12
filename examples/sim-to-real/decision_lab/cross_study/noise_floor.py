"""How much error is irreducible when a card is measured on ~96 people?

Every "AI is 12 points off" statement needs a floor to be read against. If half
the cohort is compared with the other half, the same method applied twice still
disagrees by several percentage points purely from sampling. That disagreement is
the floor: no method, including the true population distribution, can beat it on
this sample size.

Run it once per study before interpreting any distribution error.
"""
import argparse
import json
import random
import statistics

from . import evolve
from .registry import ROOT
from .scoring import card_key, option_ids


def split_half(study, repeats=400, minimum=40, seed=20261112):
    rng = random.Random(seed)
    cases = evolve.cohort_cases(study)
    keys = {}
    for case in cases:
        for question in case['questions']:
            keys[card_key(question)] = question
    tvs, cards = [], 0
    for key, question in keys.items():
        ids = option_ids(question)
        answers = [case['truth'].get(str(question['id'])) for case in cases]
        answers = [a for a in answers if a in ids]
        if len(answers) < minimum:
            continue
        cards += 1
        for _ in range(repeats):
            shuffled = answers[:]
            rng.shuffle(shuffled)
            half = len(shuffled) // 2
            left, right = shuffled[:half], shuffled[half:]
            first = [sum(1 for x in left if x == i) / len(left) for i in ids]
            second = [sum(1 for x in right if x == i) / len(right) for i in ids]
            tvs.append(50 * sum(abs(a - b) for a, b in zip(first, second)))
    if not tvs:
        return {'study': study, 'available': False, 'cards': 0}
    # Split-half compares two halves, so each carries its own sampling error. The
    # floor for "a large-sample truth against this cohort" is smaller by sqrt(2).
    median = statistics.median(tvs)
    return {'study': study, 'available': True, 'cards': cards, 'splits': len(tvs),
            'split_half_median_pp': median,
            'cohort_vs_truth_floor_pp': median / (2 ** 0.5),
            'note': ('split_half_median_pp compares two halves of the same cohort; '
                     'cohort_vs_truth_floor_pp divides it by sqrt(2) to express how far a '
                     'large-sample truth would sit from this cohort by sampling alone.')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--studies', default='anes,pew13,pew168,shed,packaging,pew111,german,radiant')
    parser.add_argument('--repeats', type=int, default=400)
    options = parser.parse_args()
    studies = [s for s in options.studies.split(',') if s]
    result = {'status': 'sampling_noise_floor', 'studies': [split_half(s, options.repeats)
                                                            for s in studies]}
    target = ROOT / 'reports/cross-study-v1/noise-floor.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    for block in result['studies']:
        if not block['available']:
            print(f"{block['study']:10s} not estimable")
            continue
        print(f"{block['study']:10s} cards={block['cards']:3d} "
              f"split-half={block['split_half_median_pp']:.2f}pp "
              f"floor≈{block['cohort_vs_truth_floor_pp']:.2f}pp")


if __name__ == '__main__':
    main()
