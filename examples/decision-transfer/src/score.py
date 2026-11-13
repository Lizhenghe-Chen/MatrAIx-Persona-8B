"""Per-person Brier scoring with paired, stratified resampling intervals.

The answer file is local only; nothing here is written to a public report without
aggregation over people.
"""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

PRIVATE = Path.home() / '.local/share/matraix-decision-transfer/work/stage2'
OUT = Path(__file__).resolve().parents[1] / 'data/stage2-results.json'
ARMS = ('matraix', 'basic', 'own', 'other')
RESAMPLES = 2000
SEED = 20261109


def one_hot(answer, option_ids):
    if answer not in option_ids:
        raise ValueError('Answer option not in the frozen option list')
    return [1.0 if option == answer else 0.0 for option in option_ids]


def brier(probabilities, answer, option_ids):
    truth = one_hot(answer, option_ids)
    return sum((p - t) ** 2 for p, t in zip(probabilities, truth))


def person_scores(requests, answers, state):
    """Mean Brier per person per arm; equal weight per question inside a person."""
    questions = {row['sha256']: row['questions'] for row in requests}
    per_person = defaultdict(lambda: defaultdict(list))
    for row in state:
        if row.get('status') != 'ok':
            continue
        deck = questions[row['sha256']]
        person = str(row['rig'])
        arm = row['arm']
        for question in deck:
            qid = question['id']
            options = list(question['options'])
            probs = row['probabilities'][qid]
            per_person[person][arm].append(brier(probs, answers[person][qid], options))
    return {person: {arm: sum(values) / len(values) for arm, values in arms.items() if values}
            for person, arms in per_person.items()}


def complete_people(scores, arms=ARMS):
    return [p for p, values in scores.items() if all(a in values for a in arms)]


def mean(values):
    return sum(values) / len(values)


def paired_interval(scores, people, arm, reference, cells, resamples=RESAMPLES, seed=SEED):
    """Stratified bootstrap over people; the same people stay paired in every arm."""
    rng = random.Random(seed)
    by_cell = defaultdict(list)
    for person in people:
        by_cell[cells[person]].append(person)
    diffs = [scores[p][reference] - scores[p][arm] for p in people]
    point = mean(diffs)
    draws = []
    for _ in range(resamples):
        sample = []
        for cell_people in by_cell.values():
            sample.extend(rng.choices(cell_people, k=len(cell_people)))
        draws.append(mean([scores[p][reference] - scores[p][arm] for p in sample]))
    draws.sort()
    baseline = mean([scores[p][reference] for p in people])
    return {'arm': arm, 'reference': reference, 'absolute': round(point, 5),
            'relative': round(point / baseline, 4) if baseline else None,
            'low': round(draws[int(0.025 * resamples)], 5), 'high': round(draws[int(0.975 * resamples)], 5),
            'n_people': len(people)}


def summarise(scores, cells, arms=ARMS):
    people = complete_people(scores, arms)
    result = {'complete_people': len(people), 'arms': {}}
    for arm in arms:
        values = [scores[p][arm] for p in people]
        result['arms'][arm] = {'mean_brier': round(mean(values), 5), 'n': len(values)}
    result['comparisons'] = [paired_interval(scores, people, 'own', 'basic', cells),
                             paired_interval(scores, people, 'own', 'other', cells),
                             paired_interval(scores, people, 'other', 'basic', cells),
                             paired_interval(scores, people, 'matraix', 'basic', cells),
                             paired_interval(scores, people, 'matraix', 'own', cells)]
    return result


def load(cells_source=PRIVATE / 'participants.json'):
    cells = {str(row['pub_id']): ' | '.join(row['cell']) for row in json.loads(cells_source.read_text())}
    return cells


def technical_summary(requests, state):
    """Format, latency and run-to-run volatility only. Never a scientific score."""
    ok = [row for row in state if row.get('status') == 'ok']
    bases = {(row['sha256'], row['arm']): row for row in ok if row.get('role') != 'repeat'}
    pairs, flips = 0, 0
    for row in ok:
        if row.get('role') != 'repeat':
            continue
        base = bases.get((row['sha256'], row['arm']))
        if base is None:
            continue
        pairs += 1
        flat = lambda d: [x for q in sorted(d) for x in d[q]]
        if max(abs(a - b) for a, b in zip(flat(base['probabilities']), flat(row['probabilities']))) > 1e-6:
            flips += 1
    probs = [x for row in ok for values in row['probabilities'].values() for x in values]
    return {
        'status': 'technical_only_not_an_effect_estimate',
        'calls': len(state), 'ok': len(ok),
        'failures': [{'arm': row['arm'], 'status': row['status'], 'reason': row.get('reason')}
                     for row in state if row.get('status') != 'ok'],
        'seconds_median': round(sorted(r['seconds'] for r in ok)[len(ok) // 2], 2) if ok else None,
        'seconds_max': max((r['seconds'] for r in ok), default=None),
        'answers_per_request': sorted({len(r['probabilities']) for r in ok}),
        'renormalised': sum(r.get('renormalised', 0) for r in ok),
        'mean_reported_probability': round(sum(probs) / len(probs), 4) if probs else None,
        'share_above_0_9': round(sum(1 for x in probs if x > 0.9) / len(probs), 4) if probs else None,
        'repeat_pairs': pairs, 'repeat_pairs_that_moved': flips,

        'note': 'Identical requests were deliberately repeated to record output volatility; the same model '
                'output cannot be assumed deterministic. No accuracy comparison is implied.',
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='pro')
    parser.add_argument('--out', default=str(OUT))
    parser.add_argument('--which', default='formal', choices=['formal', 'technical'])
    parser.add_argument('--technical-summary', action='store_true')
    args = parser.parse_args()
    requests = json.loads((PRIVATE / 'requests.json').read_text())
    answers = json.loads((PRIVATE / 'answers.json').read_text())
    state_path = PRIVATE / 'runs' / f'{args.model}.jsonl'
    state = [json.loads(line) for line in state_path.read_text().splitlines() if line.strip()]
    if args.which == 'technical':
        allowed = {row['sha256'] for row in requests if row['role'] == 'technical'}
        state = [row for row in state if row['sha256'] in allowed]
    else:
        # Technical participants and deliberate repeats never enter a scientific score.
        state = [row for row in state if row.get('role') == 'evaluation']
    if args.technical_summary:
        summary = technical_summary(requests, state)
        Path(args.out).write_text(json.dumps(summary, ensure_ascii=False, indent=1) + '\n')
        print(json.dumps(summary, ensure_ascii=False, indent=1))
        return
    scores = person_scores(requests, answers, state)
    cells = load()
    result = summarise(scores, cells)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps(result['comparisons'], ensure_ascii=False, indent=1))
    print(json.dumps(result['arms'], ensure_ascii=False))


if __name__ == '__main__':
    main()
