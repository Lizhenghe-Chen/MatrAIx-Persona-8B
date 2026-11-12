"""Exploratory screening on the free local endpoint.

The frozen formal plans answer one question: does this method beat the statistical
reference. This module answers a cheaper, repeated question: which task framings
move the three metrics the project now tracks — cohort distribution error,
individual Brier score, and ranking of options.

Rules that keep the loop honest:

* every attempt is recorded, including the ones that lose;
* nothing here writes to a frozen plan, its spec, or its checkpoint;
* a framing is only promoted to a paid confirmation run on the strong model after
  it clears the gate on the free endpoint in at least two studies, in the same
  direction, without making any of the three metrics clearly worse.

Two task shapes are supported. "cohort" asks once per study for the distribution
of the whole group. "person" asks once per respondent, which is what the formal
plans do; its per-card aggregate is then compared on the same footing.
"""
import argparse
import hashlib
import json
import math
import os
import random
import sqlite3
import threading
import time
from collections import Counter, defaultdict

from ..core.provider import LOCAL, send
from . import formal
from .protocol import persona_text
from .registry import ROOT
from .scoring import build_references, card_key, option_ids, option_label, reference_vector
from .targets import load_existing

FREE_MODEL = 'Qwen/Qwen3.8-27B'
SCREEN = ROOT / 'specs/cross-study-v1/screening'

VARIANTS = {
    'opt': {'shape': 'person', 'note': ''},
    'hetero': {'shape': 'person',
               'note': ('Respondents in the same demographic group do not all answer the same way. '
                        'Reflect the disagreement that plausibly exists between them.')},
    'scoped': {'shape': 'person',
               'note': ('First decide how people who share this respondent\'s age and education usually '
                        'answer this question, then adjust for anything specific in the profile. '
                        'Report the probabilities after that adjustment.')},
    'agg': {'shape': 'cohort', 'note': ''},
    'agg_scoped': {'shape': 'cohort',
                   'note': ('Reason group by group: for each age and education group, estimate its '
                            'share, then weight the groups by their respondent counts.')},
    'counts': {'shape': 'person',
               'note': 'Answer as counts out of 100 similar respondents rather than as probabilities.',
               'envelope': ('Return JSON with only answers: a list of objects with questionId and counts. '
                            'counts is an object keyed by every exact choice id; the non-negative integers '
                            'must sum to 100 for each question. No rationale or explanations.')},
    'refusal': {'shape': 'person',
                'note': ('Answer options such as "none of these", "would not buy" or "no opinion" are '
                         'real answers, not leftovers. Many respondents do choose them. Estimate their '
                         'share on its merits instead of shrinking it toward zero.')},
    'brief': {'shape': 'person', 'note': '', 'persona': 'brief'},
    'brief_scoped': {'shape': 'person', 'persona': 'brief',
                     'note': ('First decide how people who share this respondent\'s age and education usually '
                              'answer this question, then adjust for anything specific in the profile.')},
}

PERSON_INSTRUCTION = ('Predict the choices the respondent represented by the provided profile would '
                      'make in the stated survey context. Use only supplied information; do not invent '
                      'missing personal experiences. Answer every required question.')

ENVELOPE = ('Return JSON with only answers: a list of objects with questionId and probabilities. '
            'probabilities is an object keyed by every exact option id. All probabilities must be '
            'finite numbers from 0 to 1 and sum to 1 for each question. No rationale, confidence, '
            'or explanations.')


def _queue_for(study):
    for plan in formal.PLANS.values():
        if study in plan['studies']:
            return plan
    raise ValueError('unknown study ' + study)


def cohort_rows(study):
    plan = _queue_for(study)
    cohort = json.loads((formal.PRIVATE / plan['cohort']).read_text())
    return [r for r in cohort if r['phase'] == 'reserve' and r['study'] == study and r.get('persona')]


def cohort_cases(study):
    return [{'study': study, 'person': r['person'], 'stratum': r['stratum'],
             'weight': r.get('weight', 1.0), 'truth': dict(r['truth']),
             'questions': r['questions'], 'context': r['context'], 'persona': r['persona']}
            for r in cohort_rows(study)]


def unique_questions(cases):
    seen, out = set(), []
    for case in cases:
        for question in case['questions']:
            key = card_key(question)
            if key in seen:
                continue
            seen.add(key)
            out.append(question)
    out.sort(key=lambda q: str(q['id']))
    return out


def _table(questions):
    lines = []
    for question in questions:
        lines.append(f'### {question["id"]}')
        lines.append(str(question.get('prompt', '')).strip())
        lines.append('| id | option |')
        lines.append('|---|---|')
        for option in question['options']:
            if isinstance(option, dict):
                lines.append(f'| `{option["id"]}` | {option_label(option)} |')
            else:
                lines.append(f'| `{option}` | {option} |')
        lines.append('')
    return '\n'.join(lines).strip()


def _composition(cases):
    counter = Counter(str(case['stratum']) for case in cases)
    lines = ['| stratum | respondents |', '|---|---|']
    for stratum, count in sorted(counter.items()):
        lines.append(f'| {stratum} | {count} |')
    return '\n'.join(lines)


def cohort_body(study, cases, variant):
    questions = unique_questions(cases)
    note = VARIANTS[variant]['note']
    user = ('## Task\n\n'
            f'A survey was answered by {len(cases)} respondents. You are given their demographic '
            'composition and the questionnaire.\n\n'
            'Estimate the share of the whole cohort that picked each option.\n'
            + (note + '\n' if note else '') +
            '\n## Cohort composition\n\n' + _composition(cases) + '\n\n'
            '## Questionnaire\n\n' + _table(questions) + '\n\n'
            '## Answer envelope\n\n' + ENVELOPE)
    return {'model': FREE_MODEL, 'temperature': 0.3, 'top_p': 1, 'max_tokens': 4096,
            'response_format': {'type': 'json_object'},
            'chat_template_kwargs': {'enable_thinking': False},
            'messages': [{'role': 'system',
                          'content': 'You estimate population shares from a described cohort.'},
                         {'role': 'user', 'content': user}]}


def brief_persona(persona):
    """Only the three approved fields that matter for the question, no template."""
    parts = [persona.get('age_bracket'), persona.get('region'), persona.get('highest_education')]
    parts = [p for p in parts if isinstance(p, str)]
    return ('You are answering as this respondent: ' + ', '.join(parts) + '.'
            if parts else 'You are answering as an adult survey respondent.')


def person_body(case, persona, variant, temperature):
    spec = VARIANTS[variant]
    note = spec['note']
    envelope = spec.get('envelope', ENVELOPE)
    instruction = PERSON_INSTRUCTION + ((' ' + note) if note else '')
    user = (f'## Task instruction\n\n{instruction}\n\n'
            f'## Context\n\n{case["context"]}\n\n'
            f'## Questionnaire\n\n{_table(case["questions"])}\n\n'
            f'## Answer envelope\n\n{envelope}')
    system = brief_persona(persona) if spec.get('persona') == 'brief' else persona_text(persona)
    body = {'model': FREE_MODEL, 'temperature': temperature, 'top_p': 1, 'max_tokens': 4096,
            'response_format': {'type': 'json_object'},
            'chat_template_kwargs': {'enable_thinking': False},
            'messages': [{'role': 'system', 'content': system},
                         {'role': 'user', 'content': user}]}
    return body


def _answers_list(data, expected):
    """Accept the answer list wherever the model put it.

    Screening only compares the numbers, so a different container is not an error;
    the container actually used is recorded so the pattern stays visible. A missing
    or duplicated question is still a failure, never a filled-in default.
    """
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return None
    if isinstance(data.get('answers'), list):
        return data['answers']
    # question-keyed object: {qid: [ {...}, ... ]} or {qid: {option: probability}}
    out = []
    for qid, value in data.items():
        if qid not in expected:
            continue
        if isinstance(value, list) and value and isinstance(value[0], dict):
            out.extend(value)
        elif isinstance(value, dict):
            if 'probabilities' in value or 'questionId' in value:
                out.append({'questionId': qid, 'probabilities': value.get('probabilities', value)})
            else:
                out.append({'questionId': qid, 'probabilities': value})
    return out or None


def parse_answers(raw, questions):
    content = raw['choices'][0]['message']['content']
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f'unparseable_json({exc.msg}): {content[:160]!r}') from None
    expected = {q['id']: option_ids(q) for q in questions}
    answers = _answers_list(data, expected)
    if answers is None:
        raise ValueError(f'missing_answers keys={sorted(data)[:6] if isinstance(data, dict) else type(data).__name__} '
                         f'preview={content[:160]!r}')
    out = {}
    for answer in answers:
        qid = answer.get('questionId')
        if qid not in expected or qid in out:
            raise ValueError('unknown_or_duplicate_question')
        field = 'counts' if 'counts' in answer else 'probabilities'
        probabilities = answer.get(field)
        ids = expected[qid]
        if not isinstance(probabilities, dict) or set(probabilities) != set(ids):
            raise ValueError('invalid_probability_keys')
        values = [probabilities[option] for option in ids]
        target = 100.0 if field == 'counts' else 1.0
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
            raise ValueError('invalid_probability_values')
        total = sum(values)
        if abs(total - target) > 0.02 * target:
            raise ValueError('invalid_probability_values')
        out[qid] = [v / total for v in values]
    if set(out) != set(expected):
        raise ValueError('missing_required_answers_no_default_fill')
    return out, raw.get('usage', {})


def _connect(round_name):
    SCREEN.mkdir(parents=True, exist_ok=True)
    os.chmod(SCREEN, 0o700)
    connection = sqlite3.connect(SCREEN / f'{round_name}.sqlite')
    connection.execute('CREATE TABLE IF NOT EXISTS calls (job TEXT PRIMARY KEY, study TEXT, '
                       'variant TEXT, person TEXT, sample INTEGER, status TEXT, response TEXT, '
                       'error TEXT, elapsed REAL, usage TEXT)')
    connection.commit()
    return connection


def _personas(cases):
    wanted = {(case['persona']['shard'], case['persona']['row_index']) for case in cases}
    return formal._profiles(wanted)[0]


def build_plan(studies, variant, samples, temperature):
    shape = VARIANTS[variant]['shape']
    plan = []
    for study in studies:
        cases = cohort_cases(study)
        if shape == 'cohort':
            questions = unique_questions(cases)
            for sample in range(samples):
                plan.append({'study': study, 'person': '', 'sample': sample, 'variant': variant,
                             'questions': questions, 'body': cohort_body(study, cases, variant)})
        else:
            profiles = _personas(cases)
            for case in cases:
                persona = profiles[(case['persona']['shard'], case['persona']['row_index'])]
                for sample in range(samples):
                    plan.append({'study': study, 'person': case['person'], 'sample': sample,
                                 'variant': variant, 'questions': case['questions'],
                                 'body': person_body(case, persona, variant, temperature)})
    for item in plan:
        item['job'] = hashlib.sha256(
            json.dumps({'body': item['body'], 'study': item['study'], 'person': item['person'],
                        'sample': item['sample']}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return plan


def run(round_name, studies, variant, samples=1, workers=4, temperature=0.7, limit=None):
    plan = build_plan(studies, variant, samples, temperature)
    if limit:
        plan = plan[:limit]
    _connect(round_name).close()
    done = failed = 0
    lock = threading.Lock()
    cursor = [0]

    def worker():
        nonlocal done, failed
        local = sqlite3.connect(SCREEN / f'{round_name}.sqlite', timeout=60, isolation_level=None)
        local.execute('PRAGMA busy_timeout=60000')
        try:
            while True:
                with lock:
                    index = cursor[0]
                    cursor[0] += 1
                if index >= len(plan):
                    return
                item = plan[index]
                existing = local.execute('SELECT status FROM calls WHERE job=?',
                                         (item['job'],)).fetchone()
                if existing and existing[0] == 'complete':
                    continue
                start = time.monotonic()
                try:
                    raw = send(item['body'], LOCAL, timeout=300)
                    parsed, usage = parse_answers(raw, item['questions'])
                    values = (item['job'], item['study'], item['variant'], item['person'],
                              item['sample'], 'complete', json.dumps(parsed), None,
                              time.monotonic() - start, json.dumps(usage))
                    with lock:
                        done += 1
                except Exception as exc:  # noqa: BLE001 - reason recorded verbatim
                    values = (item['job'], item['study'], item['variant'], item['person'],
                              item['sample'], 'failed', None,
                              f'{type(exc).__name__}: {str(exc)[:200]}',
                              time.monotonic() - start, None)
                    with lock:
                        failed += 1
                local.execute('INSERT OR REPLACE INTO calls VALUES (?,?,?,?,?,?,?,?,?,?)', values)
        finally:
            local.close()

    threads = [threading.Thread(target=worker) for _ in range(max(1, workers))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    print(json.dumps({'round': round_name, 'variant': variant, 'planned': len(plan),
                      'complete': done, 'failed': failed}, ensure_ascii=False))


_HISTORY = {}
_ADAPTER_CACHE = {}


def history_rows(study):
    if study not in _HISTORY:
        if study in formal.PLANS['v1']['studies']:
            rows = [r for r in load_existing() if r['study'] == study]
        else:
            plan = next(name for name, plan in formal.PLANS.items()
                        if study in plan['studies'] and plan['sources'] == 'adapters')
            if plan not in _ADAPTER_CACHE:
                formal.select_plan(plan)
                _ADAPTER_CACHE[plan] = list(formal._adapter_rows())  # generator: materialise once
            rows = [r for r in _ADAPTER_CACHE[plan] if r['study'] == study]
        _HISTORY[study] = [{'person': r['person'], 'stratum': r['stratum'],
                            'questions': r['questions'], 'truth': r['truth']} for r in rows]
    return _HISTORY[study]


def score(round_name, studies, variant):
    """Three metrics per study, all on the evaluated cohort only."""
    connection = sqlite3.connect(SCREEN / f'{round_name}.sqlite')
    rows = connection.execute('SELECT study,person,sample,status,response FROM calls WHERE variant=?',
                              (variant,)).fetchall()
    connection.close()
    report = {}
    for study in studies:
        cases = cohort_cases(study)
        questions = unique_questions(cases)
        keys = {card_key(q): q for q in questions}
        actual = {}
        for key, question in keys.items():
            ids = option_ids(question)
            counts = Counter()
            for case in cases:
                for q in case['questions']:
                    if card_key(q) == key and case['truth'].get(str(q['id'])) in ids:
                        counts[case['truth'][str(q['id'])]] += 1
            if sum(counts.values()) >= 20:
                actual[key] = [counts[i] / sum(counts.values()) for i in ids]
        predictions = defaultdict(lambda: defaultdict(list))
        for study_name, person, sample, status, response in rows:
            if study_name != study or status != 'complete':
                continue
            shares = json.loads(response)
            for key, question in keys.items():
                vector = shares.get(question['id'])
                if vector:
                    predictions[key][person].append(vector)
        shape = VARIANTS[variant]['shape']
        tv, brier, hits, detail = [], [], [], []
        for key, question in keys.items():
            if key not in actual:
                continue
            ids = option_ids(question)
            per_person = predictions.get(key, {})
            if not per_person:
                continue
            if shape == 'cohort':
                vectors = [v for values in per_person.values() for v in values]
                model = [sum(v[i] for v in vectors) / len(vectors) for i in range(len(ids))]
            else:
                by_person = []
                for case in cases:
                    values = per_person.get(case['person'])
                    answer = case['truth'].get(str(question['id']))
                    if not values or answer not in ids:
                        continue
                    mean = [sum(v[i] for v in values) / len(values) for i in range(len(ids))]
                    by_person.append((answer, mean))
                    brier.append(sum((p - (1.0 if o == answer else 0.0)) ** 2
                                     for p, o in zip(mean, ids)))
                if not by_person:
                    continue
                model = [sum(mean[i] for _, mean in by_person) / len(by_person)
                         for i in range(len(ids))]
                truth = [sum(1.0 for answer, _ in by_person if answer == o) / len(by_person)
                         for o in ids]
                hits.append(int(max(range(len(ids)), key=lambda i: model[i])
                                == max(range(len(ids)), key=lambda i: truth[i])))
            card_tv = 50 * sum(abs(m - a) for m, a in zip(model, actual[key]))
            tv.append(card_tv)
            detail.append({'question': str(question['id']), 'options': len(ids),
                           'tv_pp': card_tv,
                           'model': [round(m, 4) for m in model],
                           'actual': [round(a, 4) for a in actual[key]]})
        evaluated = {case['person'] for case in cases}
        history = [r for r in history_rows(study) if r['person'] not in evaluated]
        references = build_references(cases, history)
        reference_tv, uniform_tv = [], []
        for key, question in keys.items():
            if key not in actual:
                continue
            ids = option_ids(question)
            # The reference is per respondent: each person is compared with their own stratum,
            # then averaged inside the card, exactly as the formal scorer does.
            vectors = []
            for case in cases:
                answer = case['truth'].get(str(question['id']))
                if answer not in ids:
                    continue
                vector = (reference_vector(references, 'stratum_history', question, case['stratum'])
                          or reference_vector(references, 'history', question, case['stratum']))
                if vector:
                    vectors.append(vector)
            if vectors:
                mean = [sum(v[i] for v in vectors) / len(vectors) for i in range(len(ids))]
                reference_tv.append(50 * sum(abs(v - a) for v, a in zip(mean, actual[key])))
            uniform_tv.append(50 * sum(abs(1 / len(ids) - a) for a in actual[key]))
        report[study] = {
            'shape': shape,
            'cards': len(tv),
            'tv_pp': (sum(tv) / len(tv)) if tv else None,
            'brier': (sum(brier) / len(brier)) if brier else None,
            'argmax': (sum(hits) / len(hits)) if hits else None,
            'reference_tv_pp': (sum(reference_tv) / len(reference_tv)) if reference_tv else None,
            'uniform_tv_pp': (sum(uniform_tv) / len(uniform_tv)) if uniform_tv else None,
            'people': len({person for key in predictions for person in predictions[key]}),
            'cards_detail': detail,
        }
    return {'round': round_name, 'variant': variant, 'studies': report}


def _load(round_name, variant):
    path = ROOT / f'reports/cross-study-v1/screening-{round_name}-{variant}.json'
    return json.loads(path.read_text())['studies'] if path.exists() else None


def compare(round_name, baseline='opt', variants=None):
    """Score every screened variant against the baseline on the three metrics.

    The gate is declared here, once, and never relaxed per variant: a framing is
    promoted only if it improves the cohort distribution on average by at least
    one percentage point, does so in most studies, and does not degrade the other
    two metrics beyond a small tolerance. A framing that trades one metric for
    another is reported as a trade-off, not as a win.
    """
    base = _load(round_name, baseline)
    if not base:
        raise ValueError('baseline results missing: ' + baseline)
    variants = variants or [name for name in VARIANTS if _load(round_name, name)]
    summary = {'round': round_name, 'baseline': baseline,
               'gate': {'mean_tv_gain_pp': 1.0, 'studies_improved_fraction': 0.6,
                        'max_brier_worsening': 0.02, 'max_argmax_drop': 0.03},
               'variants': {}}
    for variant in variants:
        if variant == baseline:
            continue
        block = _load(round_name, variant)
        if not block:
            continue
        deltas, brier_ratio, argmax_delta, rows = [], [], [], {}
        for study, base_row in base.items():
            row = block.get(study)
            if not row or row['tv_pp'] is None or base_row['tv_pp'] is None:
                continue
            delta = base_row['tv_pp'] - row['tv_pp']
            deltas.append(delta)
            if row['brier'] is not None and base_row['brier']:
                brier_ratio.append(row['brier'] / base_row['brier'])
            if row['argmax'] is not None and base_row['argmax'] is not None:
                argmax_delta.append(row['argmax'] - base_row['argmax'])
            rows[study] = {'tv_pp': row['tv_pp'], 'tv_gain_pp': delta,
                           'brier': row['brier'], 'argmax': row['argmax'],
                           'reference_tv_pp': row['reference_tv_pp']}
        if not deltas:
            continue
        improved = sum(1 for d in deltas if d > 0)
        mean_gain = sum(deltas) / len(deltas)
        worst_brier = max(brier_ratio) if brier_ratio else None
        worst_argmax = min(argmax_delta) if argmax_delta else None
        ok = (mean_gain >= summary['gate']['mean_tv_gain_pp']
              and improved / len(deltas) >= summary['gate']['studies_improved_fraction']
              and (worst_brier is None or worst_brier <= 1 + summary['gate']['max_brier_worsening'])
              and (worst_argmax is None or worst_argmax >= -summary['gate']['max_argmax_drop']))
        summary['variants'][variant] = {
            'studies': len(deltas), 'mean_tv_gain_pp': mean_gain,
            'improved_studies': improved, 'worst_brier_ratio': worst_brier,
            'worst_argmax_delta': worst_argmax, 'passes_gate': ok, 'rows': rows}
    path = ROOT / f'reports/cross-study-v1/screening-{round_name}-compare.json'
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    header = f"{'variant':12s} {'studies':>7s} {'ΔTVpp':>7s} {'improved':>9s} {'worstBrier':>11s} {'worstArgmax':>12s}  gate"
    print(header)
    for variant, block in summary['variants'].items():
        print(f"{variant:12s} {block['studies']:7d} {block['mean_tv_gain_pp']:+7.2f} "
              f"{block['improved_studies']:4d}/{block['studies']:<4d} "
              f"{(block['worst_brier_ratio'] or 1):11.3f} {(block['worst_argmax_delta'] or 0):+12.3f}  "
              f"{'PASS' if block['passes_gate'] else 'no'}")
    return summary


def _card_bootstrap(deltas, repeats=4000, seed=20261112):
    """Paired bootstrap over cards: the card is the unit that varies within a study."""
    if not deltas:
        return None
    rng = random.Random(seed)
    n = len(deltas)
    means = sorted(sum(deltas[rng.randrange(n)] for _ in range(n)) / n for _ in range(repeats))
    return [means[int(0.025 * repeats)], means[int(0.975 * repeats) - 1]]


def compare_cards(round_name, baseline='opt', variants=None):
    """Variant versus baseline, paired per card, with a card-level bootstrap interval."""
    base = _load(round_name, baseline)
    variants = variants or [n for n in VARIANTS if _load(round_name, n)]
    out = {'round': round_name, 'baseline': baseline, 'variants': {}}
    for variant in variants:
        if variant == baseline:
            continue
        block = _load(round_name, variant)
        if not block:
            continue
        per_study, pooled = {}, []
        for study, base_row in base.items():
            row = block.get(study)
            if not row or not row.get('cards_detail') or not base_row.get('cards_detail'):
                continue
            base_cards = {c['question']: c['tv_pp'] for c in base_row['cards_detail']}
            deltas = [base_cards[c['question']] - c['tv_pp'] for c in row['cards_detail']
                      if c['question'] in base_cards]
            if not deltas:
                continue
            per_study[study] = {'cards': deltas and len(deltas),
                                'mean_gain_pp': sum(deltas) / len(deltas),
                                'ci': _card_bootstrap(deltas),
                                'improved_cards': sum(1 for d in deltas if d > 0)}
            pooled.extend(deltas)
        if not per_study:
            continue
        improved_studies = sum(1 for v in per_study.values() if v['mean_gain_pp'] > 0)
        out['variants'][variant] = {
            'pooled_cards': len(pooled),
            'pooled_mean_gain_pp': sum(pooled) / len(pooled) if pooled else None,
            'pooled_ci': _card_bootstrap(pooled),
            'improved_cards_fraction': (sum(1 for d in pooled if d > 0) / len(pooled)) if pooled else None,
            'improved_studies': improved_studies,
            'studies': len(per_study),
            'per_study': per_study}
    path = ROOT / f'reports/cross-study-v1/screening-{round_name}-cards.json'
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(f"{'variant':12s} {'cards':>6s} {'ΔTVpp':>7s} {'95% CI':>18s} {'cards+':>7s} {'studies+':>9s}")
    for variant, block in out['variants'].items():
        ci = block['pooled_ci'] or [0, 0]
        print(f"{variant:12s} {block['pooled_cards']:6d} {block['pooled_mean_gain_pp']:+7.2f} "
              f"[{ci[0]:+6.2f}, {ci[1]:+6.2f}]  {block['improved_cards_fraction']:6.0%} "
              f"{block['improved_studies']:4d}/{block['studies']:<4d}")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['run', 'score', 'both', 'compare', 'compare-cards'])
    parser.add_argument('--round', required=True)
    parser.add_argument('--variant', default='opt', choices=sorted(VARIANTS))
    parser.add_argument('--studies', default='german,pew111')
    parser.add_argument('--samples', type=int, default=1)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--temperature', type=float, default=0.7)
    parser.add_argument('--limit', type=int, default=None)
    options = parser.parse_args()
    studies = [s for s in options.studies.split(',') if s]
    if options.command in ('run', 'both'):
        run(options.round, studies, options.variant, options.samples, options.workers,
            options.temperature, options.limit)
    if options.command == 'compare':
        compare(options.round, options.variant)
        return
    if options.command == 'compare-cards':
        compare_cards(options.round, options.variant)
        return
    if options.command in ('score', 'both'):
        result = score(options.round, studies, options.variant)
        target = ROOT / f'reports/cross-study-v1/screening-{options.round}-{options.variant}.json'
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        for study, block in result['studies'].items():
            def fmt(value, digits=2):
                return '—' if value is None else f'{value:.{digits}f}'
            print(f"{study:10s} {block['shape']:6s} cards={block['cards']:3d} "
                  f"tv={fmt(block['tv_pp'])}pp ref={fmt(block['reference_tv_pp'])} "
                  f"uniform={fmt(block['uniform_tv_pp'])} "
                  f"brier={fmt(block['brier'], 3)} argmax={fmt(block['argmax'])}")


if __name__ == '__main__':
    main()
