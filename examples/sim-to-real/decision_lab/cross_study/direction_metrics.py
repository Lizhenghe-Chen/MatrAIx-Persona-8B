"""Direction metrics: does the model rank options the way people actually did?

Brier is a magnitude score and hides an important question for anything
product-facing: when the model says "almost nobody picks this", is that right in
direction even if the number is off? This module answers that separately, and
then asks where the persona is supposed to earn its keep: on people who are
unusual relative to their population.

Both parts read existing checkpoints, so they cost nothing and can be rerun after
any paid run.
"""
import argparse
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

from . import formal
from .scoring import build_references, card_key, option_ids, reference_vector

CARD_MINIMUM = 20
REFERENCE_ORDER = ('stratum_history', 'history')


def _source_rows():
    if formal.SOURCE_KIND == 'existing':
        from .targets import load_existing
        return list(load_existing())
    return formal._adapter_rows()


def _cards(cases, references):
    """Group scored cases by frozen card; keep only cards with enough respondents."""
    grouped = defaultdict(list)
    for case in cases:
        for question in case['questions']:
            grouped[card_key(question)].append((case, question))
    out = []
    for key, members in grouped.items():
        if len(members) < CARD_MINIMUM:
            continue
        question = members[0][1]
        ids = option_ids(question)
        answered = [(case, q) for case, q in members if case['truth'].get(str(q['id'])) in ids]
        if len(answered) < CARD_MINIMUM:
            continue
        actual = [0.0] * len(ids)
        for case, q in answered:
            actual[ids.index(case['truth'][str(q['id'])])] += 1 / len(answered)
        ai = [0.0] * len(ids)
        ref = None
        ref_name = None
        for name in REFERENCE_ORDER:
            vectors = [reference_vector(references, name, q, case['stratum']) for case, q in answered]
            if all(v and len(v) == len(ids) for v in vectors):
                ref = [sum(v[i] for v in vectors) / len(vectors) for i in range(len(ids))]
                ref_name = name
                break
        for case, q in answered:
            vector = case['predictions']['optimized'].get(str(q['id']))
            if vector and len(vector) == len(ids):
                for i, value in enumerate(vector):
                    ai[i] += value / len(answered)
        out.append({'question': str(question['id']), 'options': len(ids), 'people': len(answered),
                    'actual': actual, 'ai': ai, 'reference': ref, 'reference_name': ref_name,
                    'members': answered})
    return out


def _top(vector, k=1):
    order = sorted(range(len(vector)), key=lambda i: -vector[i])
    return set(order[:k])


def _median_abs_error(predicted, actual):
    return statistics.median(abs(a - b) for a, b in zip(predicted, actual))


def _study_block(cards):
    hits = sum(1 for c in cards if _top(c['ai']) == _top(c['actual']))
    top2 = sum(1 for c in cards if _top(c['ai'], 2) == _top(c['actual'], 2))
    with_reference = [c for c in cards if c['reference']]
    ref_hits = sum(1 for c in with_reference if _top(c['reference']) == _top(c['actual']))
    ref_top2 = sum(1 for c in with_reference if _top(c['reference'], 2) == _top(c['actual'], 2))
    return {'cards': len(cards),
            'ai_argmax': hits / len(cards),
            'ai_top2': top2 / len(cards),
            'reference_argmax': (ref_hits / len(with_reference)) if with_reference else None,
            'reference_top2': (ref_top2 / len(with_reference)) if with_reference else None,
            'ai_median_share_error': statistics.median(_median_abs_error(c['ai'], c['actual']) for c in cards),
            'reference_median_share_error': (statistics.median(
                _median_abs_error(c['reference'], c['actual']) for c in with_reference)
                if with_reference else None),
            'reference_name': with_reference[0]['reference_name'] if with_reference else None,
            'ai_mean_share_error': statistics.mean(
                statistics.mean(abs(a - b) for a, b in zip(c['ai'], c['actual'])) for c in cards)}


def _deviation_block(cards):
    """Compare the model against the population distribution on typical versus unusual people.

    Atypicality is the total variation distance between one person's answer and the
    card's population shares. The persona is only earning its keep if the model
    beats the population distribution more on the unusual end of that scale.
    """
    pairs = []
    for card in cards:
        if not card['reference']:
            continue
        population = card['reference']
        for case, question in card['members']:
            vector = case['predictions']['optimized'].get(str(question['id']))
            answer = case['truth'].get(str(question['id']))
            if not vector or answer is None:
                continue
            ids = option_ids(question)
            if answer not in ids or len(vector) != len(ids):
                continue
            truth = [1.0 if o == answer else 0.0 for o in ids]
            pairs.append({'study': case['study'], 'person': case['person'],
                          'atypical': 0.5 * sum(abs(t - p) for t, p in zip(truth, population)),
                          'ai': sum((p - t) ** 2 for p, t in zip(vector, truth)),
                          'population': sum((p - t) ** 2 for p, t in zip(population, truth))})
    if len(pairs) < 50:
        return {'available': False, 'pairs': len(pairs)}
    pairs.sort(key=lambda r: r['atypical'])
    size = len(pairs) // 5
    buckets = []
    for index in range(5):
        chunk = pairs[index * size:(index + 1) * size] if index < 4 else pairs[4 * size:]
        gains = [r['population'] - r['ai'] for r in chunk]
        buckets.append({
            'quintile': index + 1,
            'atypical_from': round(chunk[0]['atypical'], 3),
            'atypical_to': round(chunk[-1]['atypical'], 3),
            'people_cards': len(chunk),
            'ai_brier': statistics.mean(r['ai'] for r in chunk),
            'population_brier': statistics.mean(r['population'] for r in chunk),
            'ai_advantage': statistics.mean(gains),
            'ai_advantage_ci': _bootstrap(gains)})
    return {'available': True, 'pairs': len(pairs),
            'note': ('ai_advantage above zero means the model beat the population '
                     'distribution for that group. Quintiles are cut by the distance '
                     'between a person\'s own answer and the population shares, so this '
                     'is a post-hoc decomposition of where the persona helps, not a rule '
                     'that can be applied before an answer is known.'),
            'quintiles': buckets}


def _bootstrap(gains, repeats=2000, seed=20261112):
    rng = random.Random(seed)
    n = len(gains)
    means = []
    for _ in range(repeats):
        means.append(sum(gains[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return [means[int(0.025 * repeats)], means[int(0.975 * repeats) - 1]]


def build(plan):
    formal.select_plan(plan)
    _, cases_by_study, _ = formal._cases()
    source = _source_rows()
    by_study = defaultdict(list)
    for row in source:
        by_study[row['study']].append(row)
    studies = {}
    all_cards = []
    for study in formal.STUDIES:
        cases = cases_by_study.get(study) or []
        if not cases:
            continue
        evaluated = {c['person'] for c in cases}
        history = [r for r in by_study[study] if r['person'] not in evaluated]
        if len(history) < CARD_MINIMUM:
            continue
        cards = _cards(cases, build_references(cases, history))
        if not cards:
            continue
        studies[study] = _study_block(cards)
        all_cards.extend(cards)
    return {'status': 'direction_metrics_from_checkpoints',
            'plan': plan,
            'card_minimum_people': CARD_MINIMUM,
            'note': ('argmax/top2 use the card\'s real majority ranking, so they answer '
                     '"is the direction right" separately from Brier\'s "is the number right".'),
            'studies': studies,
            'deviation': _deviation_block(all_cards)}


def build_all(plans=('v1', 'clean-v1', 'wide-v1')):
    payload = {'status': 'direction_metrics_from_checkpoints',
               'card_minimum_people': CARD_MINIMUM,
               'note': ('argmax/top2 use the card\'s real majority ranking, so they answer '
                        '"is the direction right" separately from Brier\'s "is the number right". '
                        'Cards need at least 20 scored respondents; studies whose every card is '
                        'unique therefore have no direction metric, by construction.'),
               'plans': {}}
    for plan in plans:
        block = build(plan)
        payload['plans'][plan] = {'studies': block['studies'], 'deviation': block['deviation']}
    blocks = [s for b in payload['plans'].values() for s in b['studies'].values()]
    cards = sum(s['cards'] for s in blocks)
    with_reference = [s for s in blocks if s['reference_argmax'] is not None]
    ref_cards = sum(s['cards'] for s in with_reference)
    payload['totals'] = {
        'studies': len(blocks),
        'cards': cards,
        'ai_argmax': sum(s['cards'] * s['ai_argmax'] for s in blocks) / max(1, cards),
        'ai_top2': sum(s['cards'] * s['ai_top2'] for s in blocks) / max(1, cards),
        'reference_argmax': (sum(s['cards'] * s['reference_argmax'] for s in with_reference)
                             / max(1, ref_cards)),
        'reference_top2': (sum(s['cards'] * s['reference_top2'] for s in with_reference)
                           / max(1, ref_cards)),
        'ai_median_share_error': statistics.median(s['ai_median_share_error'] for s in blocks),
        'reference_median_share_error': statistics.median(
            s['reference_median_share_error'] for s in with_reference)}
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=None)
    options = parser.parse_args()
    payload = build_all()
    target = Path(options.output) if options.output else formal.OUT / 'direction-metrics.json'
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'studies': payload['totals']['studies'],
                      'cards': payload['totals']['cards'],
                      'ai_argmax': round(payload['totals']['ai_argmax'], 3)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
