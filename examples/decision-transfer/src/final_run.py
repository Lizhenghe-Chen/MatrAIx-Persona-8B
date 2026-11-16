"""Execute immutable final requests, keeping results and request IDs private."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json

from final_inputs import WORK, digest, read
from decision_lab.cross_study.protocol import parse
from run import ENDPOINTS, cost_of, key_for, post

QWEN = 'Qwen/Qwen3.8-27B'
CAP = 440
USD = 10.0
# Price in USD per token at peak, uncached. Recheck against the official price before a new version.
PROMPT_RATE, OUTPUT_RATE = 1.32e-6, 3.96e-6
TECHNICAL_CALLS = 16


def reserve(item):
    body = item['body']
    # UTF-8 byte count with a margin for message framing bounds the expected token count.
    return (len(json.dumps(body, ensure_ascii=False).encode()) + 192) * PROMPT_RATE + body['max_tokens'] * OUTPUT_RATE


def perform(item, provider, credential, identity):
    body = item['body'].copy()
    model = body['model']
    if provider == 'qwen':
        model = QWEN
        body.update(model=model, chat_template_kwargs={'enable_thinking': False})
        body.pop('thinking')
    status, response = post(ENDPOINTS[provider], credential, body, timeout=75)
    row = {'request': item['request'], 'sample': item['sample'], 'status': 'failed',
           'http': status, 'usage': (response.get('usage') or {}) if isinstance(response, dict) else {}}
    if status != 200:
        row['reason'] = 'transport_unknown' if status is None else 'http_error'
        if status in (401, 402, 403):
            row['stop'] = True
        return row
    served = {key: response.get(key) for key in ('model', 'system_fingerprint')}
    row['identity'] = served
    if served['model'] != model or (identity and identity != served):
        row.update(reason='identity_changed', stop=True)
        return row
    try:
        # The public response contract is the same. The two served identities are checked above.
        checked = {**response, 'model': 'deepseek-v4-pro'}
        result = parse(checked, item['instrument'], item['arm'])
    except (ValueError, KeyError, TypeError, AttributeError, IndexError) as error:
        row['reason'] = str(error) if isinstance(error, ValueError) and type(error) is ValueError else type(error).__name__
        return row
    row.update(status='ok', probabilities=result['probabilities'], renormalised=result['renormalised'])
    return row


def load_log(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def run(provider, phase):
    freeze = read('freeze.json')
    for name in ('requests', 'people'):
        if digest(WORK / f'{name}.json') != freeze[f'{name}_sha256']:
            raise ValueError('Frozen input hash mismatch')
    items = read('requests.json')
    by_key = {item['request']: item for item in items}
    log = WORK / f'final-{provider}.jsonl'
    history = load_log(log)
    if any(row.get('stop') for row in history):
        raise SystemExit('Earlier request stopped at a provider or model identity boundary')
    if phase == 'evaluation':
        for dependency in (WORK / 'final-qwen.jsonl', log):
            if len({row['request'] for row in load_log(dependency)
                    if row['sample'] == 'technical' and row['status'] == 'ok'}) != TECHNICAL_CALLS:
                raise SystemExit('Technical checks must succeed on both models')
    spent = sum(cost_of(provider, row['usage']) if row['http'] == 200 and row['usage'] else
                reserve(by_key[row['request']]) if provider == 'pro' and row['http'] in (None, 200) else 0
                for row in history)
    identity = next((row['identity'] for row in history if 'identity' in row), None)
    attempts = Counter(row['request'] for row in history)
    successes = {row['request'] for row in history if row['status'] == 'ok'}
    last = {row['request']: row for row in history}
    items = [item for item in items if item['sample'] == phase and item['request'] not in successes
             and attempts[item['request']] < 2 and last.get(item['request'], {}).get('http', 200) in
             (200, 408, 429, 500, 502, 503, 504)]
    cap = CAP if provider == 'pro' else 32
    if provider == 'pro':
        projected = spent + sum(reserve(item) for item in items)
        print(f'Peak uncached reserve for this pass: USD {projected:.2f} of {USD:.2f}', flush=True)
        if projected > USD:
            raise SystemExit('Aggregate reservation would exceed the cap')
    credential = key_for(provider)
    with log.open('a') as handle, ThreadPoolExecutor(max_workers=12) as executor:
        while items and len(history) < cap:
            count = min(len(items), cap - len(history), 12 if identity else 1)
            batch, items = items[:count], items[count:]
            if provider == 'pro' and spent + sum(reserve(item) for item in batch) > USD:
                raise SystemExit('Next batch would exceed the cap')
            # Record uncertain sends before submitting them, so an interruption cannot silently resend them.
            pending = WORK / f'pending-{provider}.json'
            pending.write_text(json.dumps([item['request'] for item in batch]))
            rows = list(executor.map(lambda item: perform(item, provider, credential, identity), batch))
            seen = identity
            for row in rows:
                if 'identity' in row:
                    seen = seen or row['identity']
                    if row['identity'] != seen:
                        row.update(status='failed', reason='identity_changed', stop=True)
                        row.pop('probabilities', None)
                if provider == 'pro':
                    spent += (cost_of(provider, row['usage']) if row['usage'] else
                              reserve(by_key[row['request']]) if row['http'] in (None, 200) else 0)
                handle.write(json.dumps(row, ensure_ascii=False) + '\n')
            handle.flush()
            pending.unlink()
            identity = seen
            history.extend(rows)
            counts = Counter(row['status'] for row in history if row['sample'] == phase)
            print(provider, phase, dict(counts), f'reserved/actual USD {spent:.4f}', flush=True)
            if any(row.get('stop') for row in rows):
                raise SystemExit('Stopped because model identity or account status changed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('provider', choices=('pro', 'qwen'))
    parser.add_argument('phase', choices=('technical', 'evaluation'))
    args = parser.parse_args()
    if args.provider == 'qwen' and args.phase != 'technical':
        parser.error('Qwen is used only for technical checks')
    with (WORK / f'{args.provider}.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (WORK / f'pending-{args.provider}.json').exists():
            raise SystemExit('Resolve pending requests against the private log before resuming')
        run(args.provider, args.phase)


if __name__ == '__main__':
    main()
