"""Chart-ready diagnostics for the clean-v1 studies. Reads only the local checkpoint.

Every number the report draws comes from here, so the page never contains a
hard-coded value that could drift from the frozen results. No model calls.
"""
import json
import re
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path

from .adapters import drone_rows, shoes_rows
from .registry import OUT
from .targets import PRIVATE

PLAN = PRIVATE / 'clean-v1.sqlite'
JOBS = PRIVATE / 'clean-v1-jobs.json'
RESULTS = OUT / 'clean-v1-results.json'


def _responses():
    jobs = {j['body_sha256']: j for j in json.loads(JOBS.read_text())['jobs']}
    connection = sqlite3.connect(f'file:{PLAN}?mode=ro', uri=True)
    try:
        rows = connection.execute("SELECT job,response FROM calls WHERE status='complete'").fetchall()
    finally:
        connection.close()
    out = defaultdict(dict)
    for key, response in rows:
        job = jobs[key]
        out[(job['study'], job['arm'])][job['person']] = json.loads(response)['probabilities']
    return out


def _arms(results, study):
    arms = results['studies'][study]['results']['arms']
    return {name: (entry['brier'], entry['available']) for name, entry in arms.items()}


def drone_diagnostics(responses, results):
    rows = drone_rows()
    actual = defaultdict(list)
    for row in rows:
        for question in row['questions']:
            actual[question['id']].append(int(row['truth'][question['id']]))
    usable = {card: values for card, values in actual.items() if len(values) >= 20}
    predicted = defaultdict(list)
    for person, answers in responses[('drone', 'optimized')].items():
        for card, vector in answers.items():
            predicted[card].append(vector[1])
    shares = [sum(values) / len(values) for values in usable.values()]
    chosen = sum(sum(values) for values in usable.values()) / sum(len(values) for values in usable.values())
    model = [statistics.mean(predicted[card]) for card in usable if predicted.get(card)]
    model_share = statistics.mean([p for values in predicted.values() for p in values])
    points = [{'card': card, 'actual': round(sum(values) / len(values), 4),
               'predicted': round(statistics.mean(predicted[card]), 4),
               'n': len(values)}
              for card, values in usable.items() if predicted.get(card)]
    bands = defaultdict(int)
    for share in shares:
        bands[f'{int(share * 5) * 20}-{int(share * 5) * 20 + 19}%'] += 1
    xs = [p['actual'] for p in points]
    ys = [p['predicted'] for p in points]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sxx = sum((a - mx) ** 2 for a in xs)
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    slope = sxy / sxx
    buckets = {}
    for label, low, high in [('under10', 0.0, 0.1), ('over70', 0.7, 1.01)]:
        subset = [p['predicted'] for p in points if low <= p['actual'] < high]
        buckets[label] = {'cards': len(subset),
                          'predicted': round(statistics.mean(subset), 4) if subset else None}
    return {
        'respondents': len(rows),
        'cards': len(usable),
        'responses': sum(len(values) for values in usable.values()),
        'people_per_card': {'min': min(len(v) for v in usable.values()),
                            'max': max(len(v) for v in usable.values())},
        'actual_drone_share': round(chosen, 4),
        'predicted_drone_share': round(model_share, 4),
        'actual_share_sd': round(statistics.pstdev(shares), 4),
        'actual_share_range': [round(min(shares), 4), round(max(shares), 4)],
        'predicted_share_sd': round(statistics.pstdev([p for v in predicted.values() for p in v]), 4),
        'scatter': points,
        'bands': dict(sorted(bands.items())),
        'fit': {'corr': round(sxy / (sxx * sum((b - my) ** 2 for b in ys)) ** 0.5, 4),
                'slope': round(slope, 4), 'intercept': round(my - slope * mx, 4),
                'buckets': buckets},
        'arms': _arms(results, 'drone'),
        'reference': 'stratum_history',
    }


def shoes_diagnostics(responses, results):
    rows = shoes_rows()
    human = defaultdict(list)
    for row in rows:
        for question in row['questions']:
            human[row['person']].append(int(row['truth'][question['id']]))
    histogram = [0] * 7
    for values in human.values():
        for value in values:
            histogram[value - 1] += 1
    total = sum(histogram)
    predicted = [0.0] * 7
    items = 0
    expected, review, price = [], [], []
    prompts = {q['id']: q['prompt'] for row in rows for q in row['questions']}
    per_person = defaultdict(list)
    for person, answers in responses[('shoes', 'optimized')].items():
        for question, vector in answers.items():
            items += 1
            for level, probability in enumerate(vector):
                predicted[level] += probability
            value = sum((i + 1) * p for i, p in enumerate(vector))
            per_person[person].append(value)
            expected.append(value)
            text = prompts[question]
            star = re.search(r'ave customer review: ([\d.]+)', text)
            money = re.search(r'price: \$([\d,]+)', text)
            review.append(float(star.group(1)) if star else None)
            price.append(float(money.group(1).replace(',', '')) if money else None)

    def correlation(left, right):
        pairs = [(a, b) for a, b in zip(left, right) if a is not None and b is not None]
        xs = [a for a, _ in pairs]
        ys = [b for _, b in pairs]
        mx, my = statistics.mean(xs), statistics.mean(ys)
        denominator = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
        return round(sum((x - mx) * (y - my) for x, y in pairs) / denominator, 4) if denominator else None

    human_means = [statistics.mean(values) for values in human.values()]
    human_within = [statistics.pstdev(values) for values in human.values() if len(values) > 1]
    model_means = [statistics.mean(values) for values in per_person.values()]
    model_within = [statistics.pstdev(values) for values in per_person.values() if len(values) > 1]
    between_human, within_human = statistics.pstdev(human_means), statistics.mean(human_within)
    between_model, within_model = statistics.pstdev(model_means), statistics.mean(model_within)
    return {
        'respondents': len(rows),
        'people_per_person_questions': sorted({len(values) for values in human.values()}),
        'items_predicted': items,
        'human_histogram': [round(value / total, 4) for value in histogram],
        'model_histogram': [round(value / items, 4) for value in predicted],
        'human_mean_rating': round(sum((i + 1) * v for i, v in enumerate(histogram)) / total, 4),
        'model_mean_rating': round(statistics.mean(expected), 4),
        'variation': {
            'between_human': round(between_human, 4), 'between_model': round(between_model, 4),
            'within_human': round(within_human, 4), 'within_model': round(within_model, 4),
            'between_kept': round(between_model / between_human, 4),
            'within_kept': round(within_model / within_human, 4),
        },
        'correlation': {'review': correlation(expected, review), 'price': correlation(expected, price)},
        # Unique shoes, not rating rows: a "card" here is one product profile.
        'cards': len({q['id'] for row in rows for q in row['questions']}),
        'ratings': total,
        'cards_with_20_people': 0,
        'arms': _arms(results, 'shoes'),
        'reference': 'attribute_rating',
    }


def main():
    results = json.loads(RESULTS.read_text())
    responses = _responses()
    drone = drone_diagnostics(responses, results)
    shoes = shoes_diagnostics(responses, results)
    for entry in (drone, shoes):
        uniform = entry['arms']['uniform'][0]
        # Positive means better than "every option equally likely"; Brier is a loss, so flip the sign.
        entry['improvement'] = {name: (None if values[0] is None else 1 - values[0] / uniform)
                                for name, values in entry['arms'].items()}
    payload = {'status': 'derived_from_clean_v1_checkpoint', 'drone': drone, 'shoes': shoes,
               'plans': {'calls': results['budget']['max_calls'],
                         'reserved_usd': results['budget']['reserved_peak_usd'],
                         'arms': results['arms']}}
    (OUT / 'clean-v1-diagnostics.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'drone_cards': drone['cards'], 'drone_actual': drone['actual_drone_share'],
                      'drone_predicted': drone['predicted_drone_share'],
                      'shoes_between_kept': shoes['variation']['between_kept'],
                      'shoes_within_kept': shoes['variation']['within_kept'],
                      'shoes_review_corr': shoes['correlation']['review']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
