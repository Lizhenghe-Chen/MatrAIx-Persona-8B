"""Per-question distributions: real respondents, the native arm, and the optimized arm.

The summaries elsewhere answer "which method scored better". This module answers the
question people actually ask next: on question 7 of this survey, how did the real
respondents split, how did the native one-choice output split, and how did the
optimized probability output split.

Three readings must not be confused:

* ``truth`` is the share of evaluated respondents who picked each option;
* ``original`` is the share of the model's one-choice answers per option, i.e. what
  you get if you treat each model instance as one respondent;
* ``optimized`` is the mean probability the model assigned to each option.

All three are distributions over the same options, so they can sit side by side.
Cards with fewer than 20 evaluated respondents cannot support a per-card reading;
those studies also get a pooled marginal over every card, which is always valid.

Reads frozen checkpoints only. No model calls.
"""
import argparse
import json
from collections import Counter, defaultdict

from . import formal
from .registry import OUT
from .scoring import card_key, option_ids, option_label

MINIMUM = 20


def _distributions(cases, arms):
    """Per-card human share, native choice share and mean optimized probability.

    `arms` is the plan actually run: a study can appear in several plans, and only
    the plan under evaluation says which arms exist.
    """
    cards = {}
    for case in cases:
        for question in case['questions']:
            key = card_key(question)
            entry = cards.setdefault(key, {'question': question, 'people': 0,
                                           'truth': Counter(), 'original': Counter(),
                                           'optimized': [0.0] * len(option_ids(question)),
                                           'weight': 0.0})
            ids = option_ids(question)
            answer = case['truth'].get(str(question['id']))
            if answer not in ids:
                continue
            weight = float(case.get('weight', 1.0))
            entry['people'] += 1
            entry['truth'][answer] += weight
            entry['weight'] += weight
            if 'original' in arms:
                vector = case['predictions']['original'].get(str(question['id']))
                if vector:
                        # The native arm returns a one-hot vector; its index is the chosen option.
                    picked = ids[vector.index(max(vector))]
                    entry['original'][picked] += weight
            vector = case['predictions']['optimized'].get(str(question['id']))
            if vector and len(vector) == len(ids):
                for index, value in enumerate(vector):
                    entry['optimized'][index] += value * weight
    out = []
    for key, entry in cards.items():
        ids = option_ids(entry['question'])
        mass = entry['weight'] or 1.0
        truth = [entry['truth'].get(o, 0.0) / mass for o in ids]
        original = ([entry['original'].get(o, 0.0) / mass for o in ids]
                    if 'original' in arms else None)
        optimized = [v / mass for v in entry['optimized']]
        out.append({
            'question': str(entry['question']['id']),
            'prompt': str(entry['question'].get('prompt', '')).strip(),
            'people': entry['people'],
            'estimable': entry['people'] >= MINIMUM,
            'options': [{'id': o, 'label': option_label(opt)}
                        for o, opt in zip(ids, entry['question']['options'])],
            'truth': truth, 'original': original, 'optimized': optimized,
            'tv_original': _tv(original, truth) if original else None,
            'tv_optimized': _tv(optimized, truth),
        })
    out.sort(key=lambda card: card['question'])
    return out, arms


def _tv(predicted, actual):
    return 50 * sum(abs(p - a) for p, a in zip(predicted, actual))


def _uniform_tv(card):
    """What an equally-likely guess would score on this card: the weakest useful baseline."""
    width = len(card['truth'])
    return 50 * sum(abs(1 / width - value) for value in card['truth'])


def _card_tv(cards):
    """Mean per-card TV over estimable cards: the same quantity the frozen summaries report.

    `uniform` is included because a study that ran only the optimized arm still needs
    something to be read against; without it the error number has no scale.
    """
    usable = [card for card in cards if card['estimable']]
    if not usable:
        return None
    with_native = [card for card in usable if card['tv_original'] is not None]
    return {'cards': len(usable),
            'optimized': sum(card['tv_optimized'] for card in usable) / len(usable),
            'original': (sum(card['tv_original'] for card in with_native) / len(with_native)
                         if with_native else None),
            'uniform': sum(_uniform_tv(card) for card in usable) / len(usable)}


def _pooled(cards):
    """Study-level marginal over every card, which is valid even without 20 people per card."""
    if not cards:
        return None
    options = max(len(card['truth']) for card in cards)
    truth = [0.0] * options
    optimized = [0.0] * options
    original = [0.0] * options if cards[0]['original'] is not None else None
    counted = 0
    for card in cards:
        width = len(card['truth'])
        for index in range(width):
            truth[index] += card['truth'][index]
            optimized[index] += card['optimized'][index]
            if original is not None:
                original[index] += card['original'][index]
        counted += 1
    if not counted:
        return None
    truth = [v / counted for v in truth]
    optimized = [v / counted for v in optimized]
    if original is not None:
        original = [v / counted for v in original]
    return {'cards': counted, 'options': options, 'truth': truth,
            'original': original, 'optimized': optimized,
            'tv_original': _tv(original, truth) if original else None,
            'tv_optimized': _tv(optimized, truth),
            'note': ('Illustration only: cards are aligned by option position, so this is a '
                     'picture of where the mass sits, not the error metric. card_tv is the '
                     'metric, and it equals the frozen per-card mean.')}


REFERENCE_LABELS = {'attribute_logit': '属性模型（条件逻辑回归）',
                    'attribute_rating': '属性评分模型',
                    'stratum_history': '历史分层查表',
                    'history': '历史查表'}


def _individual(study_block):
    """Person-level reading, which survives even when no card has 20 respondents.

    A share needs many people; one outcome is enough to score one prediction. That is
    why the six conjoint studies are still judged, just not on a per-card distribution.
    """
    results = study_block.get('results') or {}
    arms = results.get('arms') or {}
    brier = {name: payload['brier'] for name, payload in arms.items()
             if payload.get('available') and payload.get('brier') is not None}
    if not brier:
        return None
    best = None
    for name, value in brier.items():
        if name in REFERENCE_LABELS and (best is None or value < best[1]):
            best = (name, value)
    contrast = (results.get('contrasts') or {}).get('original__to__optimized')
    return {'brier': brier,
            'reference': ({'name': best[0], 'label': REFERENCE_LABELS[best[0]], 'brier': best[1]}
                          if best else None),
            'native_to_optimized': contrast if contrast and contrast.get('improvement') is not None
            else None}


def build(plans=None):
    payload = {'status': 'per_question_distributions', 'minimum_people': MINIMUM,
               'note': ('truth = evaluated respondents\' share; original = share of the '
                        'model\'s single choices; optimized = mean predicted probability. '
                        'Per-card readings need at least 20 respondents; every study also '
                        'gets a pooled marginal that does not.'),
               'plans': {}}
    for plan in (plans or list(formal.PLANS)):
        formal.select_plan(plan)
        _, cases_by_study, _ = formal._cases()
        block = {'arms': json.loads(formal.SPEC_FILE.read_text())['arms'], 'studies': {}}
        frozen = OUT / formal.PLANS[plan]['result']
        results = json.loads(frozen.read_text()).get('studies', {}) if frozen.exists() else {}
        for study in formal.PLANS[plan]['studies']:
            cases = cases_by_study.get(study) or []
            if not cases:
                continue
            cards, arms = _distributions(cases, block['arms'])
            block['studies'][study] = {
                'people': len(cases),
                'cards': len(cards),
                'estimable_cards': sum(1 for card in cards if card['estimable']),
                'arms': arms,
                # Whether a same-information attribute model exists for this study;
                # conjoint data is only fairly scored at the attribute level.
                'attribute_model': any(
                    name.startswith('attribute')
                    for name in results.get(study, {}).get('results', {}).get('arms', {})),
                'individual': _individual(results.get(study, {})),
                'card_tv': _card_tv(cards),
                'pooled': _pooled(cards),
                'questions': cards,
            }
        payload['plans'][plan] = block
    target = OUT / 'per-card.json'
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plans', default=None)
    options = parser.parse_args()
    plans = [p for p in options.plans.split(',')] if options.plans else None
    payload = build(plans)
    for plan, block in payload['plans'].items():
        for study, entry in block['studies'].items():
            print(f"{plan:11s} {study:14s} people={entry['people']:3d} cards={entry['cards']:4d} "
                  f"estimable={entry['estimable_cards']:4d} arms={entry['arms']}")


if __name__ == '__main__':
    main()
