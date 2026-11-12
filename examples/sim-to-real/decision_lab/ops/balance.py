"""Balance ledger: the only trustworthy cost measurement for paid runs.

Token counts come from the API's own usage block and are exact, but multiplying
them by a price list has been off by 3-7x against the account. The balance
endpoint is the billing truth, so every paid run should be bracketed by two
snapshots recorded here.

  python -m decision_lab.ops.balance snapshot --note before-wide-v1
  python -m decision_lab.ops.balance show
"""
import argparse
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ENDPOINT = 'https://api.deepseek.com/user/balance'
CREDENTIALS = Path.home() / '.config/matraix-decision-lab/credentials.json'
LEDGER = Path.home() / '.local/share/matraix-decision-lab/balance-ledger.jsonl'


def key():
    data = json.loads(CREDENTIALS.read_text())
    value = data.get('DEEPSEEK_API_KEY')
    if not value:
        raise SystemExit('DEEPSEEK_API_KEY is not configured')
    return value


def query():
    request = urllib.request.Request(ENDPOINT, headers={'Authorization': 'Bearer ' + key()})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.load(response)
    info = body['balance_infos'][0]
    return {'currency': info['currency'], 'total': float(info['total_balance']),
            'granted': float(info['granted_balance']), 'topped_up': float(info['topped_up_balance']),
            'available': body.get('is_available')}


def snapshot(note=''):
    row = {'at': datetime.now(timezone.utc).isoformat(timespec='seconds'), **query(), 'note': note}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.parent.chmod(0o700)
    with LEDGER.open('a') as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(f"{row['at']}  {row['total']:.2f} {row['currency']}  {note}")
    return row


def rows():
    if not LEDGER.exists():
        return []
    return [json.loads(line) for line in LEDGER.read_text().splitlines() if line.strip()]


def show():
    history = rows()
    if not history:
        print('ledger is empty; take a snapshot first')
        return
    for previous, current in zip([None] + history, history):
        cost = '' if previous is None else f'  spent {previous["total"] - current["total"]:.2f} {current["currency"]}'
        print(f"{current['at']}  {current['total']:>8.2f} {current['currency']}{cost}  {current['note']}")
    if len(history) > 1:
        total = history[0]['total'] - history[-1]['total']
        print(f'\nfrozen span: {total:.2f} {history[-1]["currency"]} over {len(history) - 1} intervals')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['snapshot', 'show'])
    parser.add_argument('--note', default='')
    command = parser.parse_args()
    snapshot(command.note) if command.command == 'snapshot' else show()
