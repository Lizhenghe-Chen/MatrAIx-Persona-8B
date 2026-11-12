"""How much is a model worth when you can only afford a small pilot?

The project kept comparing the model with a statistical reference built from every
available historical respondent, which is an unfair fight: the reference knows the
answer distribution. The realistic deployment question is different.

You have a new questionnaire and a little budget. You can ask k real people, or
you can ask a language model, or both. This module measures that trade-off:

* the crossover point where a pilot of k answers beats the model alone;
* whether blending the model with the pilot beats blending the pilot with a
  uniform guess, which is the only clean test of whether the model adds
  information rather than just reducing variance.

The blend weight is fixed in advance as w = k / (k + 20). Nothing is tuned on the
evaluation data, so the result is not an artefact of fitting.
"""
import argparse
import json
import random
import statistics
from collections import Counter

from . import evolve
from .registry import ROOT
from .scoring import card_key, option_ids

K0 = 20.0
PILOTS = (5, 10, 20, 40, 80, 160, 320)


def _actual(study):
    cases = evolve.cohort_cases(study)
    keys = {card_key(q): q for case in cases for q in case['questions']}
    actual, people = {}, {}
    for key, question in keys.items():
        ids = option_ids(question)
        counts = Counter()
        for case in cases:
            for q in case['questions']:
                if card_key(q) == key and case['truth'].get(str(q['id'])) in ids:
                    counts[case['truth'][str(q['id'])]] += 1
        if sum(counts.values()) >= 20:
            actual[key] = [counts[i] / sum(counts.values()) for i in ids]
            people[key] = sum(counts.values())
    return actual, keys


def _history(study):
    cases = evolve.cohort_cases(study)
    evaluated = {case['person'] for case in cases}
    return [r for r in evolve.history_rows(study) if r['person'] not in evaluated]


def _shares(rows, keys, ids_of):
    out = {}
    for key, question in keys.items():
        ids = ids_of(question)
        counts = Counter()
        for row in rows:
            for q in row['questions']:
                if card_key(q) == key and row['truth'].get(str(q['id'])) in ids:
                    counts[row['truth'][str(q['id'])]] += 1
        total = sum(counts.values())
        if total:
            out[question['id']] = ([counts[i] / total for i in ids], total)
    return out


def crossover(study, draws=30, seed=20261112):
    """Pilot size at which counting answers beats the model alone."""
    rng = random.Random(seed)
    actual, keys = _actual(study)
    history = _history(study)
    model = {c['question']: c['model'] for c in _model_cards(study)}
    row = {}
    for k in PILOTS:
        trials = []
        for _ in range(draws):
            sample = history if len(history) <= k else rng.sample(history, k)
            shares = _shares(sample, keys, option_ids)
            tvs = []
            for key, question in keys.items():
                if key not in actual:
                    continue
                ids = option_ids(question)
                entry = shares.get(question['id'])
                if not entry or entry[1] < 3:
                    continue
                tvs.append(50 * sum(abs(a - b) for a, b in zip(entry[0], actual[key])))
            if tvs:
                trials.append(statistics.mean(tvs))
        row[k] = statistics.mean(trials) if trials else None
    return row


def blend(study, pilots=(5, 10, 20, 40), draws=40, seed=20261113):
    """Fixed-weight blend of pilot answers with the model, against the same blend with uniform.

    The comparison is the point: if blending with a constant uniform vector does
    just as well, the model contributed nothing beyond shrinking a noisy estimate.
    """
    rng = random.Random(seed)
    actual, keys = _actual(study)
    history = _history(study)
    model = {c['question']: c['model'] for c in _model_cards(study)}
    out = {}
    for k in pilots:
        w = k / (k + K0)
        acc = {'model': [], 'pilot': [], 'blend_model': [], 'blend_uniform': []}
        for _ in range(draws):
            sample = history if len(history) <= k else rng.sample(history, k)
            shares = _shares(sample, keys, option_ids)
            buckets = {name: [] for name in acc}
            for key, question in keys.items():
                if key not in actual or question['id'] not in model:
                    continue
                ids = option_ids(question)
                entry = shares.get(question['id'])
                if not entry or entry[1] < 2:
                    continue
                pilot = entry[0]
                vector = model[question['id']]
                uniform = [1 / len(ids)] * len(ids)
                buckets['model'].append(50 * sum(abs(a - b) for a, b in zip(vector, actual[key])))
                buckets['pilot'].append(50 * sum(abs(a - b) for a, b in zip(pilot, actual[key])))
                mixed_model = [w * p + (1 - w) * m for p, m in zip(pilot, vector)]
                mixed_uniform = [w * p + (1 - w) * u for p, u in zip(pilot, uniform)]
                buckets['blend_model'].append(50 * sum(abs(a - b) for a, b in zip(mixed_model, actual[key])))
                buckets['blend_uniform'].append(50 * sum(abs(a - b) for a, b in zip(mixed_uniform, actual[key])))
            for name in acc:
                if buckets[name]:
                    acc[name].append(statistics.mean(buckets[name]))
        out[k] = {'weight_on_pilot': w,
                  **{name: (statistics.mean(values) if values else None) for name, values in acc.items()}}
        if out[k]['blend_model'] is not None and out[k]['blend_uniform'] is not None:
            out[k]['model_gain_pp'] = out[k]['blend_uniform'] - out[k]['blend_model']
    return out


SOURCE = {'model': 'qwen'}


def formal_model_cards(study, arm='optimized'):
    """Per-card aggregate distribution read from a frozen formal checkpoint."""
    from . import formal
    plan = 'v1' if study in formal.PLANS['v1']['studies'] else 'wide-v1'
    formal.select_plan(plan)
    _, cases_by_study, _ = formal._cases()
    cases = cases_by_study[study]
    keys = {}
    for case in cases:
        for question in case['questions']:
            keys.setdefault(card_key(question), question)
    out = []
    for key, question in keys.items():
        ids = option_ids(question)
        vectors = [case['predictions'][arm].get(str(question['id'])) for case in cases]
        vectors = [v for v in vectors if v and len(v) == len(ids)]
        if not vectors:
            continue
        mean = [sum(v[i] for v in vectors) / len(vectors) for i in range(len(ids))]
        out.append({'question': str(question['id']), 'options': len(ids), 'model': mean})
    return out


def _model_cards(study):
    """Per-card aggregate distribution for the model under evaluation."""
    if SOURCE['model'] == 'pro':
        return formal_model_cards(study)
    path = ROOT / 'reports/cross-study-v1/screening-r1-opt.json'
    data = json.loads(path.read_text())['studies']
    return data[study]['cards_detail']


def shuffle_ablation(study, pilots=(10, 20), draws=40, seed=20261114):
    """Same blend, but the prior comes from a different card of the same study.

    If the shuffled prior helps as much as the real one, the model is only
    supplying a generic shape prior. If it does not, the model knows something
    about that specific card.
    """
    rng = random.Random(seed)
    actual, keys = _actual(study)
    history = _history(study)
    cards = _model_cards(study)
    model = {c['question']: c['model'] for c in cards}
    pool = {}
    for card in cards:
        pool.setdefault(card['options'], []).append(card['model'])
    out = {}
    for k in pilots:
        w = k / (k + K0)
        acc = {'model': [], 'shuffled': [], 'uniform': []}
        for _ in range(draws):
            sample = history if len(history) <= k else rng.sample(history, k)
            shares = _shares(sample, keys, option_ids)
            buckets = {name: [] for name in acc}
            for key, question in keys.items():
                if key not in actual or question['id'] not in model:
                    continue
                ids = option_ids(question)
                entry = shares.get(question['id'])
                if not entry or entry[1] < 2:
                    continue
                pilot, vector = entry[0], model[question['id']]
                others = [v for v in pool.get(len(ids), []) if v is not vector]
                shuffled = rng.choice(others) if others else [1 / len(ids)] * len(ids)
                uniform = [1 / len(ids)] * len(ids)
                for name, prior in (('model', vector), ('shuffled', shuffled), ('uniform', uniform)):
                    mixed = [w * p + (1 - w) * x for p, x in zip(pilot, prior)]
                    buckets[name].append(50 * sum(abs(a - b) for a, b in zip(mixed, actual[key])))
            for name in acc:
                if buckets[name]:
                    acc[name].append(statistics.mean(buckets[name]))
        out[k] = {name: (statistics.mean(values) if values else None) for name, values in acc.items()}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--studies', default='anes,pew13,pew168,shed,packaging,pew111,german,radiant')
    parser.add_argument('--out', default=None)
    parser.add_argument('--model', default='qwen', choices=['qwen', 'pro'])
    options = parser.parse_args()
    studies = [s for s in options.studies.split(',') if s]
    SOURCE['model'] = options.model
    result = {'status': 'pilot_versus_model', 'model': options.model, 'k0': K0,
              'pilots': list(PILOTS), 'studies': {}}
    for study in studies:
        result['studies'][study] = {'crossover': crossover(study), 'blend': blend(study),
                                    'shuffle_ablation': shuffle_ablation(study)}
    target = ROOT / 'reports/cross-study-v1' / (options.out or f'blend-{options.model}.json')
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + '\n')
    print(f"{'study':10s} {'AI':>6s} " + ' '.join(f'k={k:<5d}' for k in PILOTS))
    for study, block in result['studies'].items():
        row = block['crossover']
        print(f"{study:10s} {block['blend'][20]['model']:6.2f} "
              + ' '.join(f"{(row[k] if row[k] is not None else float('nan')):5.1f} " for k in PILOTS))
    print(f"\n{'study':10s} {'k':>3s} {'+AI':>7s} {'+shuffled':>10s} {'+uniform':>9s} {'card info':>10s}")
    for study, block in result['studies'].items():
        for k, row in block['shuffle_ablation'].items():
            if row['model'] is None:
                continue
            gain = row['shuffled'] - row['model']
            print(f"{study:10s} {k:3d} {row['model']:7.2f} {row['shuffled']:10.2f} "
                  f"{row['uniform']:9.2f} {gain:+10.2f}")


if __name__ == '__main__':
    main()
