"""Pew Wave 13 stage: can a model use measured facts where a little signal exists?

Cross-construct transfer is zero or negative, so the only place a person effect lives is
inside one battery. This stage therefore predicts three importance items from four other
importance items plus demographics, and scores the model against both a marginal
reference and a demographics-only reference.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

PRIVATE = Path.home() / '.local/share/matraix-decision-transfer/work/pew'
SAV = Path('/tmp/w13/W13_Dec15/ATP W13.sav')
SEED = 20261109
FACT_ITEMS = ['SHOP6A_W13', 'SHOP6C_W13', 'SHOP6E_W13', 'SHOP6G_W13']
TARGET_ITEMS = ['SHOP6B_W13', 'SHOP6D_W13', 'SHOP6F_W13']
DEMOGRAPHICS = ['F_AGECAT_FINAL', 'F_SEX_FINAL', 'F_EDUCCAT_FINAL', 'F_INCOME_FINAL',
                'F_RACETHN_RECRUITMENT', 'F_CREGION_FINAL', 'F_PARTY_FINAL']
ITEM_TEXT = {
    'SHOP6A_W13': 'look at or try out a product in person',
    'SHOP6B_W13': 'read ratings or reviews that other people have posted online',
    'SHOP6C_W13': 'buy online without making a trip to the store',
    'SHOP6D_W13': 'compare prices from a number of different sellers',
    'SHOP6E_W13': 'ask questions about what they are buying',
    'SHOP6F_W13': 'get advice or recommendations from people they know',
    'SHOP6G_W13': 'buy from a store or seller they are familiar with',
}
LEVELS = {1: 'extremely important', 2: 'somewhat important', 3: 'not too important', 4: 'not important at all'}
TITLE = 'Shopping habits survey (United States, December 2015)'
CONTEXT = ('You take part in an online panel survey. In this part you are asked how important several things are '
           'when you buy something you have not purchased before. Each question has four answer options, from '
           '"extremely important" to "not important at all".')


def build_people(limit=100):
    import pyreadstat
    frame, meta = pyreadstat.read_sav(str(SAV))
    needed = FACT_ITEMS + TARGET_ITEMS
    usable = frame.dropna(subset=needed)
    usable = usable[(usable[needed] <= 4).all(axis=1)]
    usable = usable.sort_values('QKEY').reset_index(drop=True)
    order = sorted(range(len(usable)), key=lambda i: hashlib.sha256(
        f'{SEED}:pew:{usable.loc[i, "QKEY"]}'.encode()).hexdigest())[:limit]
    chosen = usable.iloc[order].reset_index(drop=True)
    labels = {column: meta.variable_value_labels.get(column, {}) for column in DEMOGRAPHICS}
    people = []
    for index, row in chosen.iterrows():
        background = {}
        for column in DEMOGRAPHICS:
            raw = row[column]
            value = labels[column].get(raw, str(raw))
            background[column] = str(value)
        people.append({'key': str(row['QKEY']),
                       'facts': {column: LEVELS[int(row[column])] for column in FACT_ITEMS},
                       'targets': {column: int(row[column] == 1) for column in TARGET_ITEMS},
                       'raw_facts': {column: int(row[column]) for column in FACT_ITEMS},
                       'background': background,
                       'cell': (str(row['F_AGECAT_FINAL']), str(row['F_EDUCCAT_FINAL']))})
    pool = []
    for index, row in usable.iterrows():
        background = {column: str(labels[column].get(row[column], row[column])) for column in DEMOGRAPHICS}
        pool.append({'key': str(row['QKEY']),
                     'facts': {column: LEVELS[int(row[column])] for column in FACT_ITEMS},
                     'cell': (str(row['F_AGECAT_FINAL']), str(row['F_EDUCCAT_FINAL'])),
                     'background': background})
    return people, pool, meta


def donor_for(person, people):
    """Matched on coarse age and education band, never the same person."""
    candidates = [p for p in people if p['cell'] == person['cell'] and p['key'] != person['key']]
    candidates.sort(key=lambda p: hashlib.sha256(f'{SEED}:donor:{person["key"]}:{p["key"]}'.encode()).hexdigest())
    return candidates[0] if candidates else None


def questions():
    return [{'id': column, 'prompt': 'How important is it to be able to ' + ITEM_TEXT[column] + '?',
             'options': {'top': 'Extremely important', 'rest': 'Somewhat important, not too important, or not important at all'}}
            for column in TARGET_ITEMS]


BASIC_FIELDS = {'F_AGECAT_FINAL': 'Age group', 'F_SEX_FINAL': 'Sex',
                'F_EDUCCAT_FINAL': 'Education', 'F_INCOME_FINAL': 'Household income',
                'F_RACETHN_RECRUITMENT': 'Race and ethnicity', 'F_CREGION_FINAL': 'Region',
                'F_PARTY_FINAL': 'Party identification'}


def payload(person, arm, donor):
    facts = person['facts'] if arm == 'own' else donor['facts']
    return {'title': TITLE, 'context': CONTEXT, 'questions': questions(),
            'basic': person['background'],
            'extra': {column: facts[column] for column in FACT_ITEMS}}


def extra_labels():
    return {column: 'How important is it to be able to ' + ITEM_TEXT[column] + '? '
                     '(extremely / somewhat / not too / not at all important)' for column in FACT_ITEMS}


def freeze(limit=100, arms=('basic', 'own', 'other')):
    import protocol
    import payloads
    people, pool, _ = build_people(limit)
    donors = {p['key']: donor_for(p, pool) for p in people}
    missing = [k for k, v in donors.items() if v is None]
    deck = []
    for person in people:
        for arm in arms:
            body = payload(person, arm, donors[person['key']])
            if arm == 'basic':
                body.pop('extra')
            api = protocol.build(body, arm, 'qwen', BASIC_FIELDS, extra_labels(), 512)
            deck.append({'key': person['key'], 'arm': arm, 'sha256': hashlib.sha256(
                json.dumps(body, sort_keys=True).encode()).hexdigest(), 'body': body,
                'questions': body['questions'], 'api': api})
    PRIVATE.mkdir(parents=True, exist_ok=True)
    (PRIVATE / 'deck.json').write_text(json.dumps(deck, ensure_ascii=False))
    (PRIVATE / 'answers.json').write_text(json.dumps({p['key']: p['targets'] for p in people}, ensure_ascii=False))
    (PRIVATE / 'people.json').write_text(json.dumps(
        [{k: v for k, v in p.items() if k != 'raw_facts'} for p in people], ensure_ascii=False))
    return {'people': len(people), 'requests': len(deck), 'donors_missing': len(missing)}


def run(limit=None):
    import urllib.request
    deck = json.loads((PRIVATE / 'deck.json').read_text())
    log = PRIVATE / 'runs.jsonl'
    done = set()
    if log.exists():
        done = {json.loads(line)['sha256'] for line in log.read_text().splitlines() if json.loads(line).get('status') == 'ok'}
    calls = 0
    for item in deck:
        if item['sha256'] in done:
            continue
        if limit and calls >= limit:
            break
        started = time.time()
        request = urllib.request.Request('http://10.120.47.101:8000/v1/chat/completions',
                                         data=json.dumps(item['api'], ensure_ascii=False).encode(),
                                         headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = json.loads(response.read().decode())
            import protocol
            parsed = protocol.parse(raw, item['questions'], 'qwen')
            record = {'sha256': item['sha256'], 'key': item['key'], 'arm': item['arm'],
                      'status': 'ok', 'probabilities': parsed['probabilities'],
                      'seconds': round(time.time() - started, 2)}
        except Exception as error:
            record = {'sha256': item['sha256'], 'key': item['key'], 'arm': item['arm'],
                      'status': 'error', 'reason': str(error)[:200],
                      'seconds': round(time.time() - started, 2)}
        with log.open('a') as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
        calls += 1
        print(json.dumps({'n': calls, 'arm': record['arm'], 'status': record['status']}), flush=True)
    return {'new_calls': calls}


VARIANTS = {
    'baseline': None,
    'frequency': ('Before answering, consider how common each answer is among people in general. '
                  'Some answers are rare and some are widespread; do not assume the options are equally likely.'),
    'two_step': ('First judge how common each answer is among people in general, then adjust that judgement '
                 'using this respondent\'s information. Report only the adjusted probabilities.'),
}


def run_variant(variant, limit=None):
    """Same frozen facts and questions, only the instruction changes."""
    import urllib.request
    import protocol
    import payloads
    deck = [item for item in json.loads((PRIVATE / 'deck.json').read_text()) if item['arm'] == 'own']
    log = PRIVATE / f'runs-{variant}.jsonl'
    done = set()
    if log.exists():
        done = {json.loads(line)['sha256'] for line in log.read_text().splitlines()
                if json.loads(line).get('status') == 'ok'}
    calls = 0
    for item in deck:
        if item['sha256'] in done:
            continue
        if limit and calls >= limit:
            break
        body = protocol.build(item['body'], 'own', 'qwen', BASIC_FIELDS, extra_labels(), 512,
                              preamble=VARIANTS[variant])
        started = time.time()
        request = urllib.request.Request('http://10.120.47.101:8000/v1/chat/completions',
                                         data=json.dumps(body, ensure_ascii=False).encode(),
                                         headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = json.loads(response.read().decode())
            parsed = protocol.parse(raw, item['questions'], 'qwen')
            record = {'sha256': item['sha256'], 'key': item['key'], 'variant': variant, 'status': 'ok',
                      'probabilities': parsed['probabilities'], 'seconds': round(time.time() - started, 2)}
        except Exception as error:
            record = {'sha256': item['sha256'], 'key': item['key'], 'variant': variant, 'status': 'error',
                      'reason': str(error)[:200], 'seconds': round(time.time() - started, 2)}
        with log.open('a') as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
        calls += 1
        print(json.dumps({'n': calls, 'status': record['status']}), flush=True)
    return {'new_calls': calls, 'variant': variant}


def evaluate_variants():
    answers = json.loads((PRIVATE / 'answers.json').read_text())
    rows = []
    for variant in VARIANTS:
        log = PRIVATE / f'runs-{variant}.jsonl'
        if not log.exists():
            continue
        for line in log.read_text().splitlines():
            record = json.loads(line)
            if record.get('status') != 'ok':
                continue
            for qid, probability in record['probabilities'].items():
                rows.append({'variant': variant, 'key': record['key'], 'qid': qid,
                             'p': probability[0], 'y': answers[record['key']][qid]})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return {}

    def brier(p, y):
        p = np.asarray(p, float); y = np.asarray(y, float)
        return float(np.mean((p - y) ** 2 + ((1 - p) - (1 - y)) ** 2))

    base = frame[frame.variant == 'baseline']
    marginal = base.groupby('qid').y.transform('mean')
    out = {'marginal_reference': round(brier(marginal.values, base.y.values), 4), 'variants': {}}
    for variant, group in frame.groupby('variant'):
        out['variants'][variant] = {'questions': int(len(group)),
                                    'brier': round(brier(group.p.values, group.y.values), 4),
                                    'mean_p': round(float(group.p.mean()), 3),
                                    'actual_rate': round(float(group.y.mean()), 3)}
    return out


def evaluate():
    deck = json.loads((PRIVATE / 'deck.json').read_text())
    answers = json.loads((PRIVATE / 'answers.json').read_text())
    people = json.loads((PRIVATE / 'people.json').read_text())
    log = PRIVATE / 'runs.jsonl'
    rows_state = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    results = {}
    for record in rows_state:
        if record.get('status') != 'ok':
            continue
        for qid, probability in record['probabilities'].items():
            truth = answers[record['key']][qid]
            results.setdefault(record['arm'], []).append(
                {'key': record['key'], 'qid': qid, 'p': probability[0], 'y': truth})
    frame = {arm: pd.DataFrame(rows) for arm, rows in results.items()}
    if not frame:
        return {}

    def brier(p, y):
        p = np.asarray(p, float); y = np.asarray(y, float)
        return float(np.mean((p - y) ** 2 + ((1 - p) - (1 - y)) ** 2))

    out = {}
    for arm, group in frame.items():
        out[arm] = {'questions': int(len(group)),
                    'brier': round(brier(group.p.values, group.y.values), 4),
                    'mean_p': round(float(group.p.mean()), 3),
                    'actual_rate': round(float(group.y.mean()), 3)}
    baseline = frame.get('basic')
    if baseline is not None:
        pivot = baseline.pivot_table(index=['key', 'qid'], values='y').reset_index()
        marginal = baseline.groupby('qid').y.transform('mean')
        out['marginal_reference'] = round(brier(marginal.values, baseline.y.values), 4)
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--evaluate', action='store_true')
    parser.add_argument('--variant', choices=sorted(VARIANTS), default='frequency')
    parser.add_argument('--evaluate-variants', dest='evaluate_variants', action='store_true')
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--arms', default='basic,own,other')
    args = parser.parse_args()
    if args.freeze:
        print(json.dumps(freeze(args.limit, tuple(args.arms.split(','))), ensure_ascii=False))
    elif args.run:
        print(json.dumps(run(), ensure_ascii=False))
    elif args.evaluate:
        print(json.dumps(evaluate(), ensure_ascii=False, indent=1))
    elif args.evaluate_variants:
        print(json.dumps(evaluate_variants(), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(run_variant(args.variant), ensure_ascii=False))
