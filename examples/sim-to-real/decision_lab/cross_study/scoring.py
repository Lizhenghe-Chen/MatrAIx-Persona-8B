"""Cross-study scoring: person-level Brier, card-level shares, paired bootstrap.

A "card" is one frozen question with its exact option set. Studies whose
respondents saw different choice sets (the dryer study has four national
versions) are therefore compared card by card, never by assuming one shared
questionnaire.

Statistical references use only respondents outside the evaluated cohort, so
an evaluated person's own answer never enters the reference vector.
"""
import datetime
import random
import re
from collections import defaultdict

REFUSAL = re.compile(
    r"(refus|don't know|do not know|not sure|no answer|no opinion|prefer not|"
    r"neither|none of|would not buy|wouldn't buy)", re.I)


def option_ids(question):
    return [str(o['id']) if isinstance(o, dict) else str(o) for o in question['options']]


def option_label(option):
    return str(option['label']) if isinstance(option, dict) else str(option)


def card_key(question):
    """Identity of a frozen card: question id plus the exact published options."""
    return (str(question['id']),
            tuple((str(o['id']) if isinstance(o, dict) else str(o), option_label(o))
                  for o in question['options']))


def refusal_ids(questions):
    """Identify refusal-like options from published labels, before scoring."""
    found = {}
    for question in questions:
        ids = [str(o['id']) if isinstance(o, dict) else str(o)
               for o in question['options'] if REFUSAL.search(option_label(o))]
        if ids:
            found[str(question['id'])] = ids
    return found


def one_hot(answer, ids):
    if answer not in ids:
        raise ValueError('Answer is not an option of the frozen questionnaire')
    return [1.0 if a == answer else 0.0 for a in ids]


def brier(probabilities, answer, ids):
    return sum((p - t) ** 2 for p, t in zip(probabilities, one_hot(answer, ids)))


def weighted_mean(pairs):
    mass = sum(w for _, w in pairs)
    return sum(v * w for v, w in pairs) / mass if mass else None


def _shares(rows, question_key, truth_key='truth'):
    """Weighted shares for one card over the rows that answered it."""
    ids = [option for option, _ in question_key[1]]
    totals = [0.0] * len(ids)
    mass = 0.0
    counted = 0
    for row in rows:
        answer = row[truth_key].get(question_key[0])
        if answer not in ids:
            continue
        weight = float(row.get('weight', 1.0))
        totals = [t + weight * v for t, v in zip(totals, one_hot(answer, ids))]
        mass += weight
        counted += 1
    return ([v / mass for v in totals] if mass else None), counted, mass


def card_index(source_rows):
    """Card key -> the respondents who answered it, built in one pass.

    Scanning every source row per card is quadratic; with thousands of distinct
    cards that is the difference between seconds and hours.
    """
    index = defaultdict(dict)
    for position, row in enumerate(source_rows):
        for question in row['questions']:
            index[card_key(question)][row['person']] = row
    return {key: list(people.values()) for key, people in index.items()}


def build_references(evaluation_cases, source_rows, minimum=20):
    """Global and stratum-conditional shares for every card under evaluation."""
    keys = {card_key(q) for case in evaluation_cases for q in case['questions']}
    index = card_index(source_rows)
    global_shares, per_stratum, unavailable = {}, {}, []
    for key in keys:
        rows = index.get(key, [])
        shares, counted, _ = _shares(rows, key)
        if shares is None:
            unavailable.append(key[0])
            continue
        global_shares[key] = shares
        per_stratum[key] = {}
        for stratum in sorted({str(c['stratum']) for c in evaluation_cases}):
            subset = [r for r in rows if str(r.get('stratum')) == stratum]
            if len(subset) < minimum:
                continue
            shares, _, _ = _shares(subset, key)
            if shares is not None:
                per_stratum[key][str(stratum)] = shares
    return {'history': {'global': global_shares, 'stratum': {}},
            'stratum_history': {'global': global_shares, 'stratum': per_stratum},
            'card_people': {key: len(index.get(key, [])) for key in keys if key in global_shares},
            'unavailable_cards': unavailable}


def reference_vector(references, name, question, stratum):
    ids = option_ids(question)
    if name == 'uniform':
        return [1.0 / len(ids)] * len(ids)
    entry = references[name]
    key = card_key(question)
    return entry['stratum'].get(key, {}).get(str(stratum)) or entry['global'].get(key)


def scored_questions(case, vector_of):
    return sum(1 for q in case['questions'] if vector_of(q, case) is not None)


def person_brier(case, vector_of):
    values = []
    for question in case['questions']:
        vector = vector_of(question, case)
        if vector is None:
            continue
        values.append(brier(vector, case['truth'][str(question['id'])], option_ids(question)))
    return sum(values) / len(values) if values else None


def person_accuracy(case, vector_of):
    correct = 0
    scored = 0
    for question in case['questions']:
        qid = str(question['id'])
        ids = option_ids(question)
        vector = vector_of(question, case)
        if vector is None:
            continue
        correct += ids[max(range(len(ids)), key=lambda i: vector[i])] == case['truth'][qid]
        scored += 1
    return correct / scored if scored else None


def card_error(cases, vector_of, minimum_people=20):
    """Equal-card mean of absolute weighted share differences, in percentage points.

    Cards with fewer than `minimum_people` evaluated respondents are not
    estimable at population level and are excluded, not averaged in.
    """
    grouped = defaultdict(list)
    for case in cases:
        for question in case['questions']:
            grouped[card_key(question)].append((case, question))
    errors, people = [], []
    for key, items in sorted(grouped.items()):
        ids = [option for option, _ in key[1]]
        human = [0.0] * len(ids)
        model = [0.0] * len(ids)
        mass = 0.0
        seen = set()
        for case, question in items:
            answer = case['truth'].get(key[0])
            if answer not in ids:
                continue
            weight = float(case.get('weight', 1.0))
            vector = vector_of(question, case)
            if vector is None:
                continue
            for index, value in enumerate(one_hot(answer, ids)):
                human[index] += weight * value
            for index, value in enumerate(vector):
                model[index] += weight * vector[index]
            mass += weight
            seen.add(case['person'])
        if mass and len(seen) >= minimum_people:
            errors.append(50 * sum(abs(h / mass - m / mass) for h, m in zip(human, model)))
            people.append(len(seen))
    return (sum(errors) / len(errors) if errors else None), len(errors), (sum(people) / len(people) if people else 0)


def refusal_mass(cases, vector_of, question, ids):
    indexes = [option_ids(question).index(i) for i in ids]
    total = mass = 0.0
    for case in cases:
        weight = float(case.get('weight', 1.0))
        vector = vector_of(question, case)
        total += weight * sum(vector[i] for i in indexes)
        mass += weight
    return total / mass if mass else None


def paired_interval(rows, repeats=2000, seed=20261109):
    """Person-cluster bootstrap within stratum; positive means the right side is better."""
    if not rows:
        raise ValueError('Empty comparison')
    reference = weighted_mean([(r['left'], r['weight']) for r in rows])
    candidate = weighted_mean([(r['right'], r['weight']) for r in rows])
    by_stratum = defaultdict(list)
    for row in rows:
        by_stratum[str(row['stratum'])].append(row)
    rng = random.Random(seed)
    draws = []
    for _ in range(repeats):
        left, right = [], []
        for stratum in sorted(by_stratum):
            group = by_stratum[stratum]
            for row in rng.choices(group, k=len(group)):
                left.append((row['left'], row['weight']))
                right.append((row['right'], row['weight']))
        draws.append(weighted_mean(left) - weighted_mean(right))
    draws.sort()
    improvement = reference - candidate
    return {'reference': reference, 'candidate': candidate, 'improvement': improvement,
            'relative_improvement': improvement / reference if reference else None,
            'improvement_95_ci': [draws[int(0.025 * repeats)], draws[int(0.975 * repeats) - 1]],
            'repeats': repeats, 'seed': seed, 'people': len(rows)}


def passes_brier_gate(comparison, minimum=0.02):
    relative = comparison['relative_improvement']
    return bool(comparison['reference'] > 0 and relative is not None and relative >= minimum
                and comparison['improvement_95_ci'][0] > 0)


def evaluate(cases, references, arms, seed=20261109, case_references=None):
    """Per-arm and per-reference summaries plus prespecified paired contrasts.

    case_references maps a comparator name to {person: {question id: vector}},
    for fitted models whose reference depends on that person's own choice card.
    """
    case_references = case_references or {}
    names = list(arms) + ['history', 'stratum_history', 'uniform'] + list(case_references)
    vectors = {arm: (lambda q, case, arm=arm: case['predictions'][arm][str(q['id'])]) for arm in arms}
    for name in ['history', 'stratum_history', 'uniform']:
        vectors[name] = (lambda q, case, name=name: reference_vector(references, name, q, case['stratum']))
    for name, table in case_references.items():
        vectors[name] = (lambda q, case, name=name, table=table: table[case['person']][str(q['id'])])
    summary, brier_rows, coverage = {}, {}, {}
    refusals = refusal_ids([q for case in cases for q in case['questions']])
    for name in names:
        vector_of = vectors[name]
        coverage[name] = (sum(scored_questions(c, vector_of) for c in cases)
                          / max(1, sum(len(c['questions']) for c in cases)))
        brier_rows[name] = {p: v for p, v in
                            ((c['person'], person_brier(c, vector_of)) for c in cases) if v is not None}
        error, cards, people_per_card = card_error(cases, vector_of)
        available = coverage[name] >= 0.8
        summary[name] = {
            'available': available,
            'question_coverage': coverage[name],
            'people': len(brier_rows[name]),
            'questions_per_person': sorted({len(c['questions']) for c in cases}),
            'brier': (weighted_mean([(brier_rows[name][c['person']], float(c.get('weight', 1.0)))
                                 for c in cases if c['person'] in brier_rows[name]])
                  if available else None),
            'accuracy': (weighted_mean([(a, float(c.get('weight', 1.0))) for c in cases
                                        if (a := person_accuracy(c, vector_of)) is not None])
                         if available else None),
            'card_tv_pp': error if available else None, 'cards': cards,
            'mean_people_per_card': people_per_card,
            'refusal': _refusal_by_question(cases, vector_of, refusals),
        }
    contrasts = {}
    for left, right in [('original', 'output_only'), ('original', 'prompt_only'),
                        ('original', 'optimized'), ('prompt_only', 'optimized'),
                        ('output_only', 'optimized'),
                        ('history', 'original'), ('history', 'optimized'),
                        ('stratum_history', 'original'), ('stratum_history', 'optimized')] + \
                      [(name, 'optimized') for name in case_references]:
        rows = [{'person': c['person'], 'stratum': c['stratum'], 'weight': float(c.get('weight', 1.0)),
                 'left': brier_rows[left][c['person']], 'right': brier_rows[right][c['person']]}
                for c in cases
                if c['person'] in brier_rows[left] and c['person'] in brier_rows[right]]
        if not summary[left]['available'] or not summary[right]['available'] or not rows:
            contrasts[f'{left}__to__{right}'] = {'available': False,
                                                 'reason': 'no question with both vectors'}
            continue
        comparison = paired_interval(rows, seed=seed)
        comparison['passes_brier_gate'] = passes_brier_gate(comparison)
        contrasts[f'{left}__to__{right}'] = comparison
    card_contrasts = {}
    card_pairs = [('original', 'optimized')] + [(name, 'optimized') for name in
                                                ('history', 'stratum_history') + tuple(case_references)]
    for left, right in card_pairs:
        card_contrasts[f'{left}__to__{right}'] = card_interval(cases, vectors[left], vectors[right])
    return {'arms': summary, 'contrasts': contrasts, 'card_contrasts': card_contrasts,
            'refusal_options': refusals,
            'estimable_cards': {'minimum_people_per_card': 20},
            'unavailable_reference_cards': references.get('unavailable_cards', []),
            'aggregation': ('Weighted by survey weight; each person contributes one Brier score averaged over '
                            'their own questions; card shares are averaged over distinct frozen cards.'),
            'computed_at': datetime.datetime.now().astimezone().isoformat()}


def _refusal_by_question(cases, vector_of, refusals):
    """Average refusal mass over the distinct cards that carry that question id."""
    grouped = defaultdict(list)
    for case in cases:
        for question in case['questions']:
            if str(question['id']) in refusals:
                grouped[str(question['id'])].append((case, question))
    result = {}
    for qid, items in grouped.items():
        by_card = defaultdict(list)
        for case, question in items:
            by_card[card_key(question)].append((case, question))
        values = []
        for key, group in by_card.items():
            ids = refusals[qid]
            total = mass = 0.0
            for case, question in group:
                weight = float(case.get('weight', 1.0))
                vector = vector_of(question, case)
                if vector is None:
                    continue
                indexes = [option_ids(question).index(i) for i in ids if i in option_ids(question)]
                total += weight * sum(vector[i] for i in indexes)
                mass += weight
            if mass:
                values.append(total / mass)
        if values:
            result[qid] = sum(values) / len(values)
    return result


def card_interval(cases, left_vector, right_vector, repeats=2000, seed=20261109):
    """Paired bootstrap of equal-card share error difference, resampling people within stratum."""
    if not cases:
        raise ValueError('Empty card comparison')
    by_stratum = defaultdict(list)
    for case in cases:
        by_stratum[str(case['stratum'])].append(case)

    support = defaultdict(set)
    for case in cases:
        for question in case['questions']:
            support[card_key(question)].add(case['person'])
    estimable = {key for key, people in support.items() if len(people) >= 20}
    if not estimable:
        return {'available': False, 'reason': 'no card reaches 20 evaluated respondents',
                'cards_with_support': len(support)}

    def error(vector_of, sample):
        grouped = defaultdict(list)
        for case in sample:
            for question in case['questions']:
                key = card_key(question)
                if key in estimable:
                    grouped[key].append((case, question))
        values = []
        for key, items in grouped.items():
            ids = [option for option, _ in key[1]]
            human = [0.0] * len(ids)
            model = [0.0] * len(ids)
            mass = 0.0
            for case, question in items:
                answer = case['truth'].get(key[0])
                if answer not in ids:
                    continue
                weight = float(case.get('weight', 1.0))
                vector = vector_of(question, case)
                if vector is None:
                    continue
                for index, value in enumerate(one_hot(answer, ids)):
                    human[index] += weight * value
                for index, value in enumerate(vector):
                    model[index] += weight * vector[index]
                mass += weight
            if mass:
                values.append(50 * sum(abs(h / mass - m / mass) for h, m in zip(human, model)))
        return sum(values) / len(values) if values else None

    left_point = error(left_vector, cases)
    right_point = error(right_vector, cases)
    if left_point is None or right_point is None:
        return {'available': False, 'reason': 'no card has enough support for this comparator'}
    rng = random.Random(seed)
    draws = []
    for _ in range(repeats):
        sample = []
        for stratum in sorted(by_stratum):
            group = by_stratum[stratum]
            sample.extend(rng.choices(group, k=len(group)))
        a, b = error(left_vector, sample), error(right_vector, sample)
        if a is None or b is None:
            continue
        draws.append(a - b)
    if len(draws) < int(repeats * 0.9):
        return {'available': False, 'reason': 'too few bootstrap draws retained card support',
                'retained_draws': len(draws), 'repeats': repeats}
    draws.sort()
    low = draws[int(0.025 * len(draws))]
    high = draws[min(len(draws) - 1, int(0.975 * len(draws)))]
    improvement = left_point - right_point
    return {'available': True, 'reference_pp': left_point, 'candidate_pp': right_point,
            'improvement_pp': improvement, 'improvement_95_ci': [low, high],
            'repeats': repeats, 'retained_draws': len(draws), 'seed': seed,
            'estimable_cards': len(estimable),
            'passes_2pp_gate': bool(improvement >= 2.0 and low > 0)}
