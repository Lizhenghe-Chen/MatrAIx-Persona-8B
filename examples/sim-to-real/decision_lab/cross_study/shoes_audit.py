"""Structure audit and reference bar for the 1-7 rating study (shoes).

Two facts decide whether this study can be scored like a choice study:
  1. how often a rating card repeats across respondents, and
  2. how accurate a same-information attribute model is on held-out people.
If cards never repeat, no historical share exists and the only legitimate
reference is the attribute model; item (2) then sets the bar an AI arm must beat.
No model output is used here, so this runs at zero API cost.
"""
import csv
import gzip
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from ..core.baselines import RatingAttributeBaseline
from .adapters import SHOES, SHOES_ATTRIBUTES

LEVELS = tuple(range(1, 8))
NUMERIC = {'attr_ave_customer_review': r'([\d.]+)', 'attr_best_seller': r'#(\d+)',
           'attr_model_year': r'(\d{4})', 'attr_price': r'\$([\d,]+)', 'attr_weight': r'([\d.]+)'}
CATEGORICAL = ('attr_brand', 'attr_color', 'attr_eco_friendly_materials', 'attr_gel_cushioning',
               'attr_shipping')


def load():
    people = defaultdict(list)
    with gzip.open(SHOES, 'rt', newline='') as stream:
        for row in csv.DictReader(stream):
            people[row['id']].append(row)
    return people


def design(people):
    """Dummy codes per displayed shoe; the display position is never a feature."""
    categories = {column: sorted({row.get(column, '') for items in people.values() for row in items})
                  for column in CATEGORICAL}
    tasks = []
    for raw_id, items in sorted(people.items()):
        for row in items:
            vector = []
            for column, pattern in NUMERIC.items():
                match = re.search(pattern, row.get(column, '') or '')
                vector.append(float(match.group(1).replace(',', '')) if match else 0.0)
            for column in CATEGORICAL:
                vector.extend(1.0 if row.get(column, '') == level else 0.0
                              for level in categories[column][1:])
            tasks.append({'person': raw_id, 'features': vector, 'answer': int(row['rating'])})
    return tasks, categories


def brier(probabilities, answer):
    return sum((p - (1.0 if level == answer else 0.0)) ** 2 for p, level in zip(probabilities, LEVELS))


def audit(folds=5, seed=20261109):
    people = load()
    tasks, categories = design(people)
    by_person = defaultdict(list)
    for task in tasks:
        by_person[task['person']].append(task)
    ids = sorted(by_person)
    random.Random(seed).shuffle(ids)
    reference_mae, global_mae, reference_brier, uniform_brier = [], [], [], []
    for fold in range(folds):
        held = set(ids[fold::folds])
        train = [t for i in ids if i not in held for t in by_person[i]]
        test = [t for i in ids if i in held for t in by_person[i]]
        model = RatingAttributeBaseline(LEVELS).fit(train)
        average = sum(t['answer'] for t in train) / len(train)
        for task, distribution in zip(test, model.predict(test)):
            reference_mae.append(abs(sum(p * level for p, level in zip(distribution, LEVELS)) - task['answer']))
            global_mae.append(abs(average - task['answer']))
            reference_brier.append(brier(distribution, task['answer']))
            uniform_brier.append(brier([1.0 / 7] * 7, task['answer']))
    cards = Counter(tuple(row.get(f'attr_{column}', '') for column in SHOES_ATTRIBUTES)
                    for items in people.values() for row in items)
    return {
        'people': len(people),
        'ratings': len(tasks),
        'ratings_per_person': sorted({len(items) for items in people.values()}),
        'rating_histogram': {str(level): sum(1 for t in tasks if t['answer'] == level) for level in LEVELS},
        'distinct_cards': len(cards),
        'cards_repeating_at_least_20': sum(1 for count in cards.values() if count >= 20),
        'max_repeats': max(cards.values()),
        'feature_width': len(tasks[0]['features']),
        'category_levels': {column: len(levels) for column, levels in categories.items()},
        'held_out_ratings': len(reference_mae),
        'reference_mae': round(sum(reference_mae) / len(reference_mae), 4),
        'global_mean_mae': round(sum(global_mae) / len(global_mae), 4),
        'reference_brier': round(sum(reference_brier) / len(reference_brier), 4),
        'uniform_brier': round(sum(uniform_brier) / len(uniform_brier), 4),
        'note': ('Rating cards are unique per respondent, so no card-level historical share exists; '
                 'the attribute model is the only same-information reference.'),
    }


if __name__ == '__main__':
    out = Path(__file__).resolve().parents[1] / 'reports/cross-study-v1/shoes-audit.json'
    result = audit()
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
