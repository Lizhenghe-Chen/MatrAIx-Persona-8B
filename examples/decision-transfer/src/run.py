"""Frozen-input runner: approved endpoints only, append-only state, hard caps.

A successful request is never sent twice. Unknown transport states are recorded and
left for explicit inspection rather than retried automatically. Any change in the
served model identity stops the run.
"""
import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

import payloads
import protocol

ENDPOINTS = {'pro': 'https://api.deepseek.com/chat/completions',
             'qwen': 'http://10.120.47.101:8000/v1/chat/completions'}
CREDENTIALS = Path.home() / '.config/matraix-decision-lab/credentials.json'
PRIVATE = Path.home() / '.local/share/matraix-decision-transfer/work/stage2'
CAPS = {'qwen': 96, 'pro': 476}
PRO_CAP_USD = 10.0
PRICE = {'pro': {'input_miss': 1.32, 'cache_hit': 0.044, 'output': 3.96}}  # USD per 1M, peak


def key_for(model):
    if model != 'pro':
        return None
    key = os.environ.get('DEEPSEEK_API_KEY')
    if not key:
        data = json.loads(CREDENTIALS.read_text())
        key = data.get('DEEPSEEK_API_KEY')
    if not key:
        raise RuntimeError('DEEPSEEK_API_KEY is not configured')
    return key


def state_file(model):
    directory = PRIVATE / 'runs'
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f'{model}.jsonl'


def load_state(model):
    path = state_file(model)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def append(model, record):
    with state_file(model).open('a') as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + '\n')


def key_of(item):
    """Deliberate repeats carry their own key; a successful request is never re-sent."""
    return item.get('key') or item['sha256']


def completed(model):
    return {row.get('key') or row['sha256'] for row in load_state(model) if row.get('status') == 'ok'}


def post(url, key, body, timeout=180):
    data = json.dumps(body, ensure_ascii=False).encode()
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['Authorization'] = f'Bearer {key}'
    request = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        return error.code, {'error': error.read().decode()[:2000]}
    except Exception as error:  # unknown transport state: record, never auto-retry
        return None, {'error': type(error).__name__ + ': ' + str(error)[:300]}


def cost_of(model, usage):
    if model not in PRICE:
        return 0.0
    rate = PRICE[model]
    hit = usage.get('prompt_cache_hit_tokens', 0) or 0
    miss = usage.get('prompt_cache_miss_tokens')
    if miss is None:
        miss = max(usage.get('prompt_tokens', 0) - hit, 0)
    return (miss / 1e6 * rate['input_miss'] + hit / 1e6 * rate['cache_hit']
            + usage.get('completion_tokens', 0) / 1e6 * rate['output'])


def run(model, requests, limit=None, tag='formal', retry_failed=False, verbose=True):
    if model not in CAPS:
        raise ValueError('Unknown model')
    done = completed(model)
    history = load_state(model)
    calls = len(history)
    start_calls = calls
    spent = sum(row.get('usd', 0.0) for row in history)
    failed_hashes = {row.get('key') or row['sha256'] for row in history if row.get('status') != 'ok'}
    key = key_for(model)
    url = ENDPOINTS[model]
    identity = None
    for item in requests:
        item_key = key_of(item)
        if item_key in done:
            continue
        if item_key in failed_hashes and not retry_failed:
            continue
        if limit is not None and calls - start_calls >= limit:
            break
        if calls >= CAPS[model]:
            raise RuntimeError(f'Call cap reached for {model}: {CAPS[model]}')
        if model == 'pro' and spent >= PRO_CAP_USD:
            raise RuntimeError(f'USD cap reached: {spent:.2f}')
        api_body = protocol.build(item['body'], item['arm'], model,
                                  payloads.BASIC_FIELDS, payloads.extra_whitelist(), payloads.MAX_TOKENS)
        started = time.time()
        status, payload = post(url, key, api_body)
        seconds = round(time.time() - started, 2)
        record = {'key': item_key, 'sha256': item['sha256'], 'rig': item['rig'], 'arm': item['arm'],
                  'role': item.get('role', tag), 'model': model, 'seconds': seconds,
                  'request_model': api_body['model'], 'tag': tag}
        if status == 200:
            try:
                parsed = protocol.parse(payload, item['questions'], model, identity)
                identity = parsed['identity']
                record.update({'status': 'ok', 'usage': parsed['usage'],
                               'renormalised': parsed['renormalised'],
                               'probabilities': parsed['probabilities'],
                               'identity': parsed['identity']})
            except Exception as error:
                if 'identity' in str(error).lower():
                    append(model, {**record, 'status': 'identity_stop',
                                   'reason': str(error)[:300], 'raw': json.dumps(payload)[:2000]})
                    raise RuntimeError('Served model identity changed; run stopped: ' + str(error)) from error
                record.update({'status': 'invalid', 'reason': type(error).__name__ + ': ' + str(error)[:300],
                               'raw': json.dumps(payload)[:3000]})
        else:
            record.update({'status': 'http_error' if status else 'transport_unknown',
                           'http_status': status, 'raw': json.dumps(payload)[:1000]})
        record['usd'] = round(cost_of(model, record.get('usage', {})), 6)
        append(model, record)
        if record['status'] == 'ok':
            done.add(item_key)
        calls += 1
        spent += record['usd']
        if verbose:
            print(json.dumps({'n': calls, 'arm': record['arm'], 'status': record['status'],
                              'sec': seconds, 'usd_total': round(spent, 4)}, ensure_ascii=False), flush=True)
    return {'calls': calls, 'spent_usd': round(spent, 4), 'state': str(state_file(model))}


def load_requests(private=PRIVATE):
    return json.loads((private / 'requests.json').read_text())


def load_repeats(private=PRIVATE):
    return json.loads((private / 'repeats.json').read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['qwen', 'pro'], required=True)
    parser.add_argument('--set', dest='which', choices=['technical', 'evaluation', 'repeats', 'formal'], default='technical')
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--retry-failed', action='store_true')
    args = parser.parse_args()
    requests = load_requests()
    repeats = load_repeats()
    if args.which == 'technical':
        deck = [r for r in requests if r['role'] == 'technical'] + repeats
    elif args.which == 'evaluation':
        deck = [r for r in requests if r['role'] == 'evaluation']
    elif args.which == 'repeats':
        deck = repeats
    else:
        deck = requests + repeats
    print(json.dumps(run(args.model, deck, limit=args.limit, tag=args.which,
                         retry_failed=args.retry_failed), ensure_ascii=False))


if __name__ == '__main__':
    main()
