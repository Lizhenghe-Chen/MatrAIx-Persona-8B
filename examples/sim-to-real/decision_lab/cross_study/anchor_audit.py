"""Did the anchored arms actually use the distribution they were given?

A difference in Brier is not evidence about mechanism by itself. This audit
measures, per arm, how far the predictions sit from the reference distribution
(total variation, 0 = identical) and how often the bounded arm breaks its own
15-percentage-point promise. If the models ignored the anchor, the whole
interpretation of anchor-v1 changes, so the check has to be explicit.
"""
import argparse
import json
import statistics
from collections import defaultdict

from . import formal
from .scoring import build_references, option_ids, reference_vector

BOUND = 0.15
ARMS = ('optimized', 'anchored', 'bounded')


def build(plan='anchor-v1'):
    formal.select_plan(plan)
    _, cases_by_study, _ = formal._cases()
    source = formal._adapter_rows()
    by_study = defaultdict(list)
    for row in source:
        by_study[row['study']].append(row)
    studies = {}
    for study, cases in cases_by_study.items():
        evaluated = {c['person'] for c in cases}
        history = [r for r in by_study[study] if r['person'] not in evaluated]
        references = build_references(cases, history)
        block = {}
        for arm in ARMS:
            distances, violations, cells = [], 0, 0
            for case in cases:
                for question in case['questions']:
                    ids = option_ids(question)
                    reference = (reference_vector(references, 'stratum_history', question, case['stratum'])
                                 or reference_vector(references, 'history', question, case['stratum']))
                    predicted = case['predictions'][arm].get(str(question['id']))
                    if not reference or not predicted or len(predicted) != len(ids):
                        continue
                    distances.append(sum(abs(p - r) for p, r in zip(predicted, reference)) / 2)
                    for p, r in zip(predicted, reference):
                        cells += 1
                        if abs(p - r) > BOUND + 1e-9:
                            violations += 1
            block[arm] = {'people_cards': len(distances),
                          'median_tv_to_reference': statistics.median(distances) if distances else None,
                          'mean_tv_to_reference': statistics.mean(distances) if distances else None,
                          'share_cells_beyond_bound': (violations / cells) if cells else None}
        block['stratum_history'] = {'median_tv_to_reference': 0.0, 'mean_tv_to_reference': 0.0,
                                    'share_cells_beyond_bound': 0.0,
                                    'note': 'the reference compared with itself'}
        studies[study] = block
    return {'status': 'anchor_adherence_from_checkpoints', 'plan': plan, 'bound': BOUND,
            'note': ('median_tv_to_reference is half the L1 distance between the predicted '
                     'distribution and the reference distribution; 0 means identical. '
                     'A model that ignored the anchor would keep the optimized distance.'),
            'studies': studies}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', default='anchor-v1')
    parser.add_argument('--output', default=None)
    options = parser.parse_args()
    payload = build(options.plan)
    target = formal.OUT / 'anchor-v1-adherence.json'
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({study: {arm: (None if block[arm]['median_tv_to_reference'] is None
                                  else round(block[arm]['median_tv_to_reference'], 3))
                              for arm in ARMS}
                      for study, block in payload['studies'].items()}, ensure_ascii=False))


if __name__ == '__main__':
    main()
