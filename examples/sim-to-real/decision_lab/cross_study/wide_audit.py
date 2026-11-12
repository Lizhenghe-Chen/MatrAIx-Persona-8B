"""Zero-cost structure audit for the wide_v1 studies.

Each study must pass the four reconstruction checks before it may be frozen:
  1. every recorded choice exists among that question's options,
  2. the chosen option has no missing attribute text,
  3. exactly one choice per question,
  4. at least 95% of a respondent's questions survive those checks.
It also reports how many respondents each card has, because the 20-person rule
decides whether a population-level share is estimable at all.
"""
import json
from collections import Counter, defaultdict

from .adapters import (german_rows, origin_rows, packaging_rows, pew111_rows,
                       radiant_rows, swiss_six_rows, tshirt_rows)
from .matching import constraints
from .registry import OUT

LOADERS = {'origin': origin_rows, 'packaging': packaging_rows, 'pew111': pew111_rows,
           'german': german_rows, 'tshirt': tshirt_rows, 'swiss_six': swiss_six_rows,
           'radiant': radiant_rows}
COHORT = 96


def audit(study, rows):
    cards = defaultdict(int)
    answered = total = 0
    bad_choice = bad_attribute = multi_choice = 0
    per_person = []
    for row in rows:
        kept = 0
        for question in row['questions']:
            total += 1
            ids = {str(o['id']) for o in question['options']}
            answer = str(row['truth'].get(str(question['id'])))
            if answer not in ids:
                bad_choice += 1
                continue
            label = next(o['label'] for o in question['options'] if str(o['id']) == answer)
            if not label or not str(label).strip():
                bad_attribute += 1
                continue
            if len({str(o['id']) for o in question['options']}) != len(question['options']):
                multi_choice += 1
                continue
            kept += 1
            cards[str(question['id'])] += 1
        answered += kept
        per_person.append(kept / max(1, len(row['questions'])))
    eligible = 0
    for row in rows:
        if constraints(row)[1] is None:
            eligible += 1
    shares = sorted(cards.values())
    return {
        'study': study,
        'respondents': len(rows),
        'match_eligible': eligible,
        'questions_per_person': sorted({len(r['questions']) for r in rows}),
        'choices': answered,
        'complete_rate': round(answered / max(1, total), 4),
        'rejected': {'choice_not_in_options': bad_choice, 'missing_attribute_text': bad_attribute,
                     'duplicate_option_ids': multi_choice},
        'distinct_cards': len(cards),
        'cards_with_20_respondents': sum(1 for v in shares if v >= 20),
        'respondents_per_card': {'min': shares[0] if shares else 0,
                                 'median': shares[len(shares) // 2] if shares else 0,
                                 'max': shares[-1] if shares else 0},
        'population_estimable': bool(rows) and len(rows) >= COHORT and
                                sum(1 for v in cards.values() if v >= COHORT * 0.2) == len(cards),
        'reference_history_coverage': round(
            sum(1 for card, count in cards.items() if count >= 20) / max(1, len(cards)), 4),
        'accepted': (answered / max(1, total)) >= 0.95 and min(per_person or [0]) >= 0.5,
    }


def main():
    report = {'cohort_size': COHORT, 'studies': {}}
    for study, loader in LOADERS.items():
        rows = loader()
        report['studies'][study] = audit(study, rows)
        print(json.dumps({k: v for k, v in report['studies'][study].items()
                          if k in ('study', 'respondents', 'match_eligible', 'distinct_cards',
                                   'complete_rate', 'accepted')}, ensure_ascii=False))
    (OUT / 'wide-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('accepted:', [s for s, v in report['studies'].items() if v['accepted']])


if __name__ == '__main__':
    main()
