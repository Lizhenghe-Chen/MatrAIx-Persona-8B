"""Cheap direction screen on the free internal endpoint.

Purpose: decide whether a direction has headroom at all, never to produce a result.
Every arm here is compared against the same-information references, because "better
than the baseline arm" is not the question.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import diagnostics as D
import payloads
import protocol
import references as R

PRIVATE = Path.home() / '.local/share/matraix-decision-transfer/work/stage2'
SCREEN = PRIVATE / 'runs/qwen-screen.jsonl'

VARIANTS = {
    'baseline': protocol.PREDICTION,
    'prior': protocol.PREDICTION + ' Respondents are not equally likely to pick either offer: use what you know '
             'about how consumers actually weigh price against environmental impact instead of assuming 50/50.',
    'decompose': protocol.PREDICTION + ' Before answering, compare the two offers on price and on environmental '
                 'impact; then give the probability the respondent picks each offer.',
}


def load_screen():
    if not SCREEN.exists():
        return []
    return [json.loads(line) for line in SCREEN.read_text().splitlines() if line.strip()]


def call(model, api_body, timeout=120):
    import urllib.request
    request = urllib.request.Request(
        'http://10.120.47.101:8000/v1/chat/completions',
        data=json.dumps(api_body, ensure_ascii=False).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode())


def run(variant, people, arm='own', limit=None):
    requests, answers, _ = D.load('pro')
    evaluation = [row for row in requests if row['role'] == 'evaluation']
    by_rig = {}
    for row in evaluation:
        by_rig.setdefault(row['rig'], row)[row['arm']] = row
    done = {(row['rig'], row['variant'], row['arm']) for row in load_screen() if row.get('status') == 'ok'}
    records = []
    for rig in people:
        if (rig, variant, arm) in done:
            continue
        payload = by_rig[rig][arm]['body']
        body = protocol.build(payload, arm, 'qwen', payloads.BASIC_FIELDS,
                              payloads.extra_whitelist(), payloads.MAX_TOKENS, preamble=VARIANTS[variant])
        started = time.time()
        try:
            raw = call('qwen', body)
            parsed = protocol.parse(raw, by_rig[rig][arm]['questions'], 'qwen')
            record = {'rig': rig, 'variant': variant, 'arm': arm, 'status': 'ok',
                      'seconds': round(time.time() - started, 2), 'probabilities': parsed['probabilities']}
        except Exception as error:
            record = {'rig': rig, 'variant': variant, 'arm': arm, 'status': 'error',
                      'seconds': round(time.time() - started, 2), 'reason': str(error)[:200]}
        with SCREEN.open('a') as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
        records.append(record)
        print(json.dumps({k: record[k] for k in ('rig', 'variant', 'status', 'seconds')}), flush=True)
        if limit and len(records) >= limit:
            break
    return records


def evaluate():
    requests, answers, state = D.load('pro')
    deck = {row['rig']: row['questions'] for row in requests if row['role'] == 'evaluation'}
    refs, _ = R.build(requests, answers)
    rows = []
    for record in load_screen():
        if record.get('status') != 'ok':
            continue
        for question in deck[record['rig']]:
            green = R.green_option(question)
            options = list(question['options'])
            rows.append({'variant': record['variant'], 'rig': record['rig'], 'qid': question['id'],
                         'green': 1 if answers[str(record['rig'])][question['id']] == green else 0,
                         'p': record['probabilities'][question['id']][options.index(green)],
                         'p_base': refs[(str(record['rig']), question['id'])]['base_rate'][options.index(green)],
                         'p_logit': refs[(str(record['rig']), question['id'])]['logit'][options.index(green)]})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return {}

    def brier(p, y):
        return float(np.mean((p - y) ** 2 + ((1 - p) - (1 - y)) ** 2))

    out = {}
    for variant, group in frame.groupby('variant'):
        out[variant] = {'questions': int(len(group)),
                        'brier': round(brier(group.p.values, group.green.values), 4),
                        'base_rate_reference': round(brier(group.p_base.values, group.green.values), 4),
                        'logit_reference': round(brier(group.p_logit.values, group.green.values), 4),
                        'mean_p_green': round(float(group.p.mean()), 3),
                        'actual_green_rate': round(float(group.green.mean()), 3),
                        'accuracy': round(float(((group.p > 0.5) == (group.green == 1)).mean()), 3)}
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--variant', choices=sorted(VARIANTS), default='prior')
    parser.add_argument('--people', type=int, default=20)
    parser.add_argument('--arm', default='own')
    parser.add_argument('--evaluate', action='store_true')
    args = parser.parse_args()
    if args.evaluate:
        print(json.dumps(evaluate(), ensure_ascii=False, indent=1))
    else:
        requests = json.loads((PRIVATE / 'requests.json').read_text())
        rigs = sorted({row['rig'] for row in requests if row['role'] == 'evaluation'})[:args.people]
        run(args.variant, rigs, arm=args.arm)
