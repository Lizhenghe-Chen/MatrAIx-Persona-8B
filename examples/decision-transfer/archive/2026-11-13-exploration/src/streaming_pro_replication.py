"""Compare the frozen streaming prediction rule with DeepSeek Pro."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import random

from order_screen import SEED, WORK, encode, read, result_path
import protocol
from run import ENDPOINTS, cost_of, key_for, post
import streaming_price_mix as streaming

RUN = WORK / 'streaming-price-mix-pro-v1'
MAX_REQUESTS = 200
MAX_FORMAT_RETRIES = 4
CAP_USD = 10


def build(x, test):
    jobs = streaming.build(x, test)
    for job in jobs.values():
        body = job['body']
        body['model'] = protocol.MODELS['pro']
        del body['chat_template_kwargs']
        body['thinking'] = {'type': 'disabled'}
    return jobs


def submit(job, key, identity):
    path = result_path(job, RUN)
    if path.exists():
        return read(path)
    marker = path.with_suffix('.pending')
    marker.touch(mode=0o600, exist_ok=False)
    status, raw = post(ENDPOINTS['pro'], key, job['body'], timeout=45)
    usage = raw.get('usage') or {}
    result = {'status': 'http_error' if status else 'transport_unknown', 'http_status': status}
    if status == 200:
        try:
            parsed = protocol.parse(raw, job['questions'], 'pro', identity)
        except (ValueError, KeyError, TypeError) as error:
            result = {'status': 'invalid', 'type': str(error)[:180]}
        else:
            result = {'status': 'ok', 'identity': parsed['identity'],
                      'p': {q['id']: dict(zip(q['options'], parsed['probabilities'][q['id']], strict=True))
                            for q in job['questions']}}
    result['usage'] = usage
    result['peak_cost_usd'] = cost_of('pro', usage)
    temporary = path.with_suffix('.tmp')
    temporary.write_bytes(encode(result))
    temporary.replace(path)
    marker.unlink()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    args = parser.parse_args()
    x, y, train, test = streaming.load()
    jobs = build(x, test)
    batch = list(jobs.values())
    random.Random(SEED).shuffle(batch)
    if len(batch) > MAX_REQUESTS:
        raise ValueError('Request budget exceeded')
    # Conservative planning estimate: one token per UTF-8 byte plus 512 output tokens.
    ceilings = [(len(encode(job['body'])) + 128) * 1.32 + 512 * 3.96 for job in batch]
    ceiling = (sum(ceilings) + MAX_FORMAT_RETRIES * max(ceilings)) / 1e6
    if ceiling > CAP_USD:
        raise ValueError('Estimated peak-price cost exceeds the budget')
    RUN.mkdir(mode=0o700, exist_ok=True)
    manifest = RUN / 'jobs.json'
    if manifest.exists() and manifest.read_bytes() != encode(batch):
        raise ValueError('Frozen requests changed')
    if not manifest.exists():
        manifest.write_bytes(encode(batch))
    if args.action == 'run':
        key = key_for('pro')
        smoke = submit(batch[0], key, None)
        if smoke['status'] != 'ok':
            raise RuntimeError(f'Pro card validation failed: {smoke["status"]}')
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda job: submit(job, key, smoke['identity']), batch[1:]))
        for job in [j for j in batch if read(result_path(j, RUN))['status'] == 'invalid'][:MAX_FORMAT_RETRIES]:
            prior = read(result_path(job, RUN))
            if 'identity' not in prior.get('type', '').lower():
                submit({**job, 'attempt': 2}, key, smoke['identity'])
    records = [read(result_path(job, RUN)) for job in batch if result_path(job, RUN).exists()]
    retry_records = [read(result_path({**job, 'attempt': 2}, RUN)) for job in batch
                     if result_path({**job, 'attempt': 2}, RUN).exists()]
    recovered = sum(r['status'] == 'ok' for r in retry_records)
    failures = [r for r in records if r['status'] != 'ok']
    output = {'planned_requests': len(batch), 'completed_requests': len(records),
              'format_retry_requests': len(retry_records), 'recovered': recovered,
              'peak_price_budget_estimate_usd': ceiling,
              'peak_price_usage_estimate_usd': sum(r['peak_cost_usd'] for r in records + retry_records),
              'failures': [{k: v for k, v in r.items() if k not in ('usage', 'peak_cost_usd')} for r in failures]}
    if len(records) == len(batch) and len(failures) == recovered:
        score_jobs = {k: ({**job, 'attempt': 2} if result_path({**job, 'attempt': 2}, RUN).exists()
                          else job) for k, job in jobs.items()}
        pro = streaming.score(x, y, train, test, score_jobs, RUN)
        for budget in pro['budgets'].values():
            budget['brier']['price_pro'] = budget['brier'].pop('price_qwen')
            for section in ('brier', 'gain'):
                budget[section]['pro'] = budget[section].pop('qwen')
        pro['pro_weight'] = pro.pop('qwen_weight')
        output['pro'] = pro
        output['qwen'] = streaming.score(x, y, train, test, streaming.build(x, test))
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
