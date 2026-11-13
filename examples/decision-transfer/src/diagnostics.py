"""Post-hoc diagnostics: does the model actually react to the fact block?

These checks explain the comparison; they never replace the pre-registered primary one.
"""
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

PRIVATE = Path.home() / '.local/share/matraix-decision-transfer/work/stage2'


def load(model='pro'):
    requests = json.loads((PRIVATE / 'requests.json').read_text())
    answers = json.loads((PRIVATE / 'answers.json').read_text())
    state = [json.loads(line) for line in (PRIVATE / 'runs' / f'{model}.jsonl').read_text().splitlines()
             if line.strip() and json.loads(line).get('status') == 'ok']
    return requests, answers, state


def block_mean(extra):
    items = [int(value) for value in extra.values() if value != 'Unknown']
    return sum(items) / len(items) if items else None


def run(model='pro'):
    requests, answers, state = load(model)
    by_rig = defaultdict(dict)
    for request in requests:
        if request['role'] != 'evaluation':
            continue
        by_rig[request['rig']][request['arm']] = request['sha256']
    probs = {(row['sha256'], row['arm']): row['probabilities'] for row in state}
    rows = []
    for rig, arms in by_rig.items():
        own_req = next(r for r in requests if r['rig'] == rig and r['arm'] == 'own')
        other_req = next(r for r in requests if r['rig'] == rig and r['arm'] == 'other')
        own_key, other_key = arms.get('own'), arms.get('other')
        if own_key is None or other_key is None:
            continue
        truth = answers[str(rig)]
        own_probs = probs.get((own_key, 'own'))
        other_probs = probs.get((other_key, 'other'))
        if not own_probs or not other_probs:
            continue
        for question in own_req['questions']:
            qid = question['id']
            options = list(question['options'])
            truth_index = 0 if truth[qid] == options[0] else 1
            rows.append({'rig': rig, 'qid': qid, 'truth': truth_index,
                         'p_own': own_probs[qid][0], 'p_other': other_probs[qid][0],
                         'own_facts': block_mean(own_req['body']['extra']),
                         'other_facts': block_mean(other_req['body']['extra'])})
    frame = pd.DataFrame(rows)
    frame['own_correct'] = ((frame['p_own'] >= 0.5) == (frame['truth'] == 0)).astype(int)
    frame['other_correct'] = ((frame['p_other'] >= 0.5) == (frame['truth'] == 0)).astype(int)
    frame['confident_wrong_own'] = ((frame['p_own'] - 0.5).abs() > 0.3) & (frame['own_correct'] == 0)
    frame['confident_wrong_other'] = ((frame['p_other'] - 0.5).abs() > 0.3) & (frame['other_correct'] == 0)
    reacts = float((frame['p_own'] - frame['p_other']).abs().mean())
    same_side = float((((frame['p_own'] >= 0.5) == (frame['p_other'] >= 0.5))).mean())
    corr_own = frame[['own_facts', 'p_own']].corr().iloc[0, 1]
    corr_other = frame[['other_facts', 'p_other']].corr().iloc[0, 1]
    return {
        'questions': int(len(frame)),
        'mean_abs_probability_gap_own_vs_other': round(reacts, 4),
        'share_identical_side_of_0.5': round(same_side, 4),
        'corr_own_facts_vs_probability': round(float(corr_own), 4),
        'corr_donor_facts_vs_probability': round(float(corr_other), 4),
        'mean_own_block': round(float(frame['own_facts'].mean()), 3),
        'mean_donor_block': round(float(frame['other_facts'].mean()), 3),
        'own_confident_wrong': round(float(frame['confident_wrong_own'].mean()), 4),
        'other_confident_wrong': round(float(frame['confident_wrong_other'].mean()), 4),
        'accuracy_own': round(float(frame['own_correct'].mean()), 4),
        'accuracy_other': round(float(frame['other_correct'].mean()), 4),
        'note': 'Diagnostic only: shows whether the model moves with the supplied block. It cannot '
                'identify why a block helps; the pre-registered comparison stays authoritative.',
    }


if __name__ == '__main__':
    print(json.dumps(run(), ensure_ascii=False, indent=1))
