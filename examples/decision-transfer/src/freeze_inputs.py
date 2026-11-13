"""Build and freeze stage-2 requests while keeping targets out of model input.

Private (never committed): participants, requests, answers.
Public: counts, hashes, caps and a synthetic preview.
"""
import argparse
import hashlib
import json
from pathlib import Path

import payloads
import personas
import protocol
import sample
import swiss

PRIVATE = Path.home() / '.local/share/matraix-decision-transfer/work/stage2'
PUBLIC = Path(__file__).resolve().parents[1] / 'data/stage2-freeze.json'
ARMS = protocol.ARMS
MAX_TOKENS = payloads.MAX_TOKENS
REPEATS = 2  # technical participants repeated once per arm to record output volatility
CAPS = {'qwen_calls': 96, 'pro_calls': 476, 'pro_usd': 10.0}


def canonical(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _truth(person):
    by_key = {}
    for item in person['tasks']:
        by_key.setdefault((item['product'], item['round']), []).append(item)
    for (product, round_number), items in sorted(by_key.items()):
        chosen = [item for item in items if item['chosen']]
        if len(chosen) != 1:
            raise ValueError('Card without exactly one choice')
        question_id = f'{product.lower().replace(" ", "-").replace("(100g)", "100g").replace("(1kg)", "1kg")}-r{round_number}'
        yield {'id': question_id}, chosen


def ground_truth(person):
    return {question['id']: f'offer-{items[0]["offer"]}' for question, items in _truth(person)}


def leakage_check(body, person):
    """The frozen input must not carry identifiers, weights or the recorded choice."""
    forbidden_keys = {'pubid', 'pub_id', 'respondent_id', 'chosen', 'choice', 'truth', 'ground_truth',
                      'answer', 'answers', 'weight', 'rating', 'rating_num'}
    stack = [body]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                if str(key).lower() in forbidden_keys:
                    raise ValueError('Leakage key in request: ' + str(key))
                stack.append(value)
        elif isinstance(node, list):
            stack.extend(node)
    if 'pubid' in json.dumps(body, ensure_ascii=False).lower():
        raise ValueError('Participant identifier field present')
    return True


def build_all(sep, conjoint, pool, verbose=True):
    result = sample.build(sep, conjoint)
    recipients = result['evaluation'] + result['technical']
    people = {p['pub_id']: p for p in result['people']}
    donors = {pub: people[donor] for pub, donor in result['donors'].items()}

    used = set()
    personas_map = {}
    for person in recipients:
        rule, error = personas.constraints(person['background'])
        if error:
            raise ValueError(f'Unmapped persona constraint for {person["pub_id"]}: {error}')
        match = personas.match(pool, rule, person['pub_id'], used)
        if match is None:
            raise ValueError('No compatible persona for a selected participant')
        used.add((match['shard'], match['row_index']))
        personas_map[person['pub_id']] = {**match, 'text': personas.render(match['fields'])}

    requests, answer_rows, arm_consistency = [], {}, {}
    for person in recipients:
        payloads_seen = {}
        for arm in ARMS:
            body = payloads.payload(person, arm, donor=donors.get(person['pub_id']),
                                    persona_text=personas_map[person['pub_id']]['text'])
            protocol.build(body, arm, 'pro', payloads.BASIC_FIELDS, payloads.extra_whitelist(), MAX_TOKENS)
            leakage_check(body, person)
            payloads_seen[arm] = (body['context'], body['questions'])
            requests.append({'rig': person['pub_id'], 'arm': arm,
                             'role': 'technical' if person in result['technical'] else 'evaluation',
                             'sha256': canonical(body), 'body': body, 'questions': body['questions']})
        base = payloads_seen['basic']
        if any((body[0], body[1]) != base for arm, body in payloads_seen.items()):
            raise ValueError('Arms disagree on context or questionnaire')
        arm_consistency[person['pub_id']] = True
        answer_rows[str(person['pub_id'])] = ground_truth(person)

    repeats = []
    for person in result['technical'][:REPEATS]:
        for arm in ARMS:
            body = payloads.payload(person, arm, donor=donors.get(person['pub_id']),
                                    persona_text=personas_map[person['pub_id']]['text'])
            digest = canonical(body)
            repeats.append({'rig': person['pub_id'], 'arm': arm, 'role': 'repeat',
                            'key': digest + ':repeat', 'sha256': digest, 'body': body,
                            'questions': body['questions']})

    if verbose:
        print(json.dumps({'requests': len(requests), 'repeats': len(repeats)}, ensure_ascii=False))
    return result, requests, repeats, answer_rows, personas_map


def estimate(requests):
    chars = sum(len(json.dumps(protocol.build(item['body'], item['arm'], 'pro', payloads.BASIC_FIELDS,
                                             payloads.extra_whitelist(), MAX_TOKENS), ensure_ascii=False))
                for item in requests)
    prompt_tokens = int(chars / 4) + 200 * len(requests)
    completion_tokens = 120 * len(requests) + 40 * len(requests)
    peak = {'input_miss': 1.32, 'output': 3.96}
    off_peak = {'input_miss': 0.66, 'output': 1.98}
    usd = {name: round(prompt_tokens / 1e6 * rate['input_miss'] + completion_tokens / 1e6 * rate['output'], 4)
           for name, rate in (('peak', peak), ('off_peak', off_peak))}
    return {'requests': len(requests), 'prompt_tokens_estimate': prompt_tokens,
            'completion_tokens_estimate': completion_tokens,
            'usd_peak': usd['peak'], 'usd_off_peak': usd['off_peak'],
            'basis': 'characters/4 plus a fixed per-request allowance; reconciled against the official usage report'}


def write(private, requests, repeats, answers_, result, persona_map):
    private.mkdir(parents=True, exist_ok=True)
    participants = [{'pub_id': p['pub_id'], 'role': 'evaluation', 'cell': list(sample.cell_of(p)),
                     'donor': result['donors'].get(p['pub_id'])} for p in result['evaluation']]
    participants += [{'pub_id': p['pub_id'], 'role': 'technical', 'cell': list(sample.cell_of(p)),
                      'donor': result['donors'].get(p['pub_id'])} for p in result['technical']]
    participants += [{'pub_id': p['pub_id'], 'role': 'reserved_' + domain, 'cell': list(sample.cell_of(p))}
                     for domain, rows in result['reserved'].items() for p in rows]
    for path, payload in (('participants.json', participants), ('answers.json', answers_),
                          ('requests.json', requests), ('repeats.json', repeats),
                          ('personas.json', {str(k): {kk: vv for kk, vv in v.items() if kk != 'text'}
                                             for k, v in persona_map.items()})):
        target = private / path
        if target.exists():
            raise ValueError('Frozen file already exists, refusing to overwrite: ' + str(target))
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
        target.chmod(0o600)
    return {'participants_sha256': hashlib.sha256((private / 'participants.json').read_bytes()).hexdigest(),
            'answers_sha256': hashlib.sha256((private / 'answers.json').read_bytes()).hexdigest(),
            'requests_sha256': hashlib.sha256((private / 'requests.json').read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pool', default=str(PRIVATE / 'persona-pool.json'))
    parser.add_argument('--private', default=str(PRIVATE))
    parser.add_argument('--dry-run', action='store_true', help='build and report without writing')
    args = parser.parse_args()

    personas.verify_snapshot()
    sep = swiss.load_sep()
    conjoint = swiss.load_conjoint()
    pool = {tuple(json.loads(key)): value for key, value in json.loads(Path(args.pool).read_text())['cells'].items()}
    result, requests, repeats, answer_rows, persona_map = build_all(sep, conjoint, pool)
    summary = sample.summarise(result)
    plan = {'status': 'frozen_pending_budget_confirmation', 'protocol_version': 'v2',
            'prediction_instruction': protocol.PREDICTION,
            'models': {'pro': protocol.MODELS['pro'], 'qwen': protocol.MODELS['qwen']},
            'arms': list(ARMS), 'max_tokens': MAX_TOKENS, 'temperature': 0.7, 'top_p': 1,
            'caps': CAPS, 'design': summary, 'request_estimate': estimate(requests + repeats),
            'baseline_field_whitelist': payloads.BASIC_FIELDS,
            'extra_field_whitelist': payloads.extra_whitelist(),
            'excluded_inputs': swiss.PROHIBITED,
            'native_persona': personas.verify_snapshot()['source_commit'],
            'notes': [
                'One request holds a participant\'s six paired choices; all arms share the identical '
                'questionnaire and context.',
                'Prices are the published CHF levels from Table 1; impact is the four-word level label because '
                'the coloured A-E display was not recoverable from the data.',
                'No participant id, weight or recorded choice is present in any request.',
                'Protocol v2 adds one prediction instruction identical in all four arms; nothing else differs.',
            ]}
    if args.dry_run:
        print(json.dumps(plan['request_estimate'], ensure_ascii=False, indent=1))
        print(json.dumps(plan['design'], ensure_ascii=False)[:800])
        return
    hashes = write(Path(args.private), requests, repeats, answer_rows, result, persona_map)
    plan['private_hashes'] = hashes
    PUBLIC.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({'written': True, 'requests': len(requests), 'repeats': len(repeats),
                      'estimate': plan['request_estimate']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
