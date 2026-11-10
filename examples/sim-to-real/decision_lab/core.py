"""Pure validation, splitting, privacy boundary and probability scoring."""
import hashlib
import json
import math
import random
from collections import defaultdict


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def probabilities(values, n):
    if len(values) != n or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0 or x > 1 for x in values):
        raise ValueError('Invalid probability vector')
    if abs(sum(values) - 1) > 1e-6:
        raise ValueError('Probabilities must sum to one; no silent normalization')
    return values


def validate(rows):
    keys = set()
    for r in rows:
        key = (r['person'], r['task'])
        if key in keys:
            raise ValueError('Duplicate person/task')
        keys.add(key)
        if len(r['options']) < 2 or len(set(r['options'])) != len(r['options']):
            raise ValueError('Invalid options')
        if r['answer'] not in range(len(r['options'])):
            raise ValueError('Invalid answer')
        if not r['question'] or not r['stratum']:
            raise ValueError('Missing question or design stratum')
    if not rows:
        raise ValueError('Empty study')


def split(rows, seed=20261109):
    groups = defaultdict(set)
    seen = {}
    for r in rows:
        if r['person'] in seen and seen[r['person']] != r['stratum']:
            raise ValueError('Person belongs to inconsistent strata')
        seen[r['person']] = r['stratum']
        groups[r['stratum']].add(r['person'])
    assignments = {}
    rng = random.Random(seed)
    for group in sorted(groups):
        ids = sorted(groups[group]); rng.shuffle(ids)
        if len(ids) < 5:
            raise ValueError('Stratum too small; revise design before freezing')
        a, b = int(.6 * len(ids)), int(.8 * len(ids))
        for i, person in enumerate(ids):
            assignments[person] = 'train' if i < a else 'development' if i < b else 'test'
    return assignments


def request_payload(row, config):
    # Construct explicitly; never serialize the original row.
    fields = config['background_fields']
    forbidden = {'person', 'answer', 'weight', 'email', 'name', 'phone', 'id'}
    if forbidden.intersection(fields):
        raise ValueError('Forbidden background field')
    return {'question': row['question'], 'options': row['options'],
            'context': row['context'],
            'background': {k: row['background'].get(k, 'unknown') for k in fields}}


def brier(p, answer):
    probabilities(p, len(p))
    return sum((v - int(i == answer)) ** 2 for i, v in enumerate(p))


def tv(p, q):
    if len(p) != len(q):
        raise ValueError('Different option counts')
    return sum(abs(a-b) for a,b in zip(p,q))/2
