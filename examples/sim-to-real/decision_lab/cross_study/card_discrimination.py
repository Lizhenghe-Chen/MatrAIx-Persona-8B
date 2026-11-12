"""Card-level discrimination: does the model move with the card, not just with the base rate?

A memorised study would show up as a flat line: the model reproduces the overall answer mix
but not the differences between cards. For every study whose cards repeat, this compares each
card-option's predicted mean probability with its observed share across respondents and reports
the correlation and the regression slope (1.0 = follows the cards exactly).
This measures discrimination; on its own it cannot prove the absence of training-data recall,
so the report states it as evidence on that question rather than as a clean test.
"""
import json
from collections import defaultdict

from .registry import OUT
from .scoring import card_key

PLANS = ('v1', 'clean-v1', 'wide-v1')


def _observed(source_rows):
    """Card -> observed answer counts, taken from every respondent, evaluated or not.

    Using only the 96 evaluated people would leave a handful of answers per card and
    make the share pure noise; the question here is whether the model tracks the card,
    so the card's real share is the right yardstick.
    """
    counts = defaultdict(lambda: defaultdict(int))
    for row in source_rows:
        for question in row['questions']:
            key = card_key(question)
            answer = str(row['truth'].get(str(question['id'])))
            if answer in {str(o['id']) for o in question['options']}:
                counts[key][answer] += 1
    return counts


def _pairs(cases, observed):
    """(observed share, predicted mean probability) for every card-option cell."""
    predicted = defaultdict(lambda: defaultdict(float))
    answers = defaultdict(int)
    for case in cases:
        for question in case['questions']:
            key = card_key(question)
            answers[key] += 1
            vector = case['predictions']['optimized'][str(question['id'])]
            for index, option in enumerate(question['options']):
                predicted[key][str(option['id'])] += vector[index]
    pairs = []
    for key, counts in observed.items():
        if key not in predicted or not answers.get(key):
            continue
        total = sum(counts.values())
        for option_id, count in counts.items():
            pairs.append((count / total, predicted[key][option_id] / answers[key], total))
    return pairs, len({key for key in observed if key in predicted})


def _fit(pairs):
    if len(pairs) < 3:
        return None
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return {'cells': len(xs), 'corr': round(sxy / (sxx * syy) ** 0.5, 4),
            'slope': round(sxy / sxx, 4), 'intercept': round(my - sxy / sxx * mx, 4)}


def run(plan):
    from . import formal
    from .targets import load_existing
    formal.select_plan(plan)
    _, cases_by_study, _ = formal._cases()
    source = list(load_existing()) if formal.SOURCE_KIND == 'existing' else list(formal._adapter_rows())
    by_study = defaultdict(list)
    for row in source:
        by_study[row['study']].append(row)
    rows = {}
    for study, cases in cases_by_study.items():
        pairs, cards = _pairs(cases, _observed(by_study.get(study, [])))
        fit = _fit(pairs)
        rows[study] = ({'cards': cards, 'available': False} if fit is None
                       else {'cards': cards, 'available': True, **fit})
    return rows


def main():
    report = {'status': 'card_discrimination_from_checkpoints',
              'interpretation': ('slope 1.0 = the model follows the card differences exactly; '
                                 'a flat line means it only reproduces the overall answer mix. '
                                 'This is evidence about memorisation, not a test that rules it out.'),
              'plans': {}}
    for plan in PLANS:
        try:
            rows = run(plan)
        except Exception as exc:  # a plan without a checkpoint must not hide the others
            report['plans'][plan] = {'available': False, 'reason': type(exc).__name__}
            print(plan, 'unavailable:', type(exc).__name__)
            continue
        report['plans'][plan] = {'available': True, 'studies': rows}
        print(plan, {s: (v.get('slope'), v.get('corr')) for s, v in rows.items() if v.get('available')})
    (OUT / 'card-discrimination.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
