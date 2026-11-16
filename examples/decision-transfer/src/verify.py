"""Verify isolation, provenance, admission state and the frozen stage-2 deck.

Version 2 (2026-11-13): the preparation-era assertion "zero calls, nothing admitted"
is replaced by the stage-2 state — Swiss admitted, origin rejected, and every sent
request accounted for in the append-only state files.
"""
import hashlib
import json
import re
import subprocess
from pathlib import Path

from freeze import HERE, REPO, verify

PRIVATE = Path.home() / '.local/share/matraix-decision-transfer/work/stage2'
ADMISSION = {'swiss': 'swiss_six', 'origin': 'origin'}
CONTEXT_PHRASE = 'one of the two is chosen'


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def check_archive():
    frozen = json.loads((HERE / 'archive/frozen-history.json').read_text())
    tag = subprocess.check_output(['git', 'rev-parse', frozen['git_tag'] + '^{}'], cwd=REPO, text=True).strip()
    if tag != frozen['historical_commit']:
        raise RuntimeError('Historical tag moved')
    refs = json.loads((HERE / 'data/reference/provenance.json').read_text())
    for row in refs['files']:
        if sha(HERE / row['copy']) != row['sha256'] or sha(REPO / row['source']) != row['sha256']:
            raise RuntimeError('Reference drift')
    changed = subprocess.check_output(['git', 'status', '--porcelain', '--', 'examples/sim-to-real'],
                                      cwd=REPO, text=True).strip()
    if changed:
        raise RuntimeError('Historical directory modified')


def check_report():
    for name in ('summary.html',):
        path = HERE / 'reports' / name
        if not path.exists():
            raise RuntimeError('Missing report: ' + name)
        report = path.read_text()
        for link in re.findall(r'href="([^"]+)"', report):
            if not link.startswith(('http:', 'https:', '#')) and not (HERE / 'reports' / link).is_file():
                raise RuntimeError(f'Broken link in {name}: {link}')
        if re.search(r'<(?:script|link|img)[^>]+(?:src|href)="https?://', report):
            raise RuntimeError('Offline report has network asset: ' + name)


def check_summary():
    """The frozen conclusions and the rendered summary must agree, number for number."""
    frozen = json.loads((HERE / 'data/conclusions-v1.json').read_text())
    for key, entry in frozen['sources'].items():
        if sha(HERE / 'data' / entry['file']) != entry['sha256']:
            raise RuntimeError('Conclusion source changed since freezing: ' + entry['file'])
    holds = sum(1 for row in frozen['gains'] if row['holds'])
    if holds != frozen['summary_counts']['interval_above_zero']:
        raise RuntimeError('Frozen count disagrees with its own rows')
    page = (HERE / 'reports/summary.html').read_text()
    if f'{frozen["summary_counts"]["comparisons"]} 组比较中有' not in page:
        raise RuntimeError('Summary page does not state the frozen comparison count')
    for row in frozen['gains']:
        if f'{row["relative"] * 100:+.1f}%' not in page:
            raise RuntimeError('Summary page is missing a frozen relative gain: ' + row['label'])


def check_admission():
    candidates = json.loads((HERE / 'data/candidates.json').read_text())
    by_id = {row['id']: row for row in candidates['candidates']}
    for name, study in ADMISSION.items():
        record = json.loads((HERE / f'data/admission/{name}.json').read_text())
        if record['study'] != study:
            raise RuntimeError('Admission record mismatch: ' + study)
    if not by_id['swiss_six']['admitted'] or by_id['origin']['admitted']:
        raise RuntimeError('Candidate admission flags disagree with the admission records')
    paid = candidates['model_calls']['pro_successful']
    if paid and candidates['status'] != 'stage2_pro_completed':
        raise RuntimeError('Status file must record the completed paid run')
    if paid:
        results = json.loads((HERE / 'data/stage2-results.json').read_text())
        if results['complete_people'] != 48:
            raise RuntimeError('Scored cohort is not the frozen evaluation set of 48')
        if set(results['arms']) != {'matraix', 'basic', 'own', 'other'}:
            raise RuntimeError('Results must cover all four arms')


def check_stage2():
    """The frozen deck must stay four arms per recipient with no recorded answer inside."""
    freeze = json.loads((HERE / 'data/stage2-freeze.json').read_text())
    if freeze['protocol_version'] != 'v2' or len(freeze['arms']) != 4:
        raise RuntimeError('Unexpected frozen protocol version or arms')
    if not (HERE / 'data/stage2-technical.json').exists():
        raise RuntimeError('Missing technical summary')
    if not PRIVATE.exists():
        return
    requests = json.loads((PRIVATE / 'requests.json').read_text())
    by_rig = {}
    for row in requests:
        by_rig.setdefault(row['rig'], {})[row['arm']] = row
        text = json.dumps(row['body'], ensure_ascii=False).lower().replace(CONTEXT_PHRASE, '')
        if 'chosen' in text:
            raise RuntimeError('Possible answer leakage in a frozen request')
    for rig, arms in by_rig.items():
        if set(arms) != {'matraix', 'basic', 'own', 'other'}:
            raise RuntimeError('Recipient without all four arms: ' + str(rig))
        base = (arms['basic']['body']['context'], arms['basic']['body']['questions'])
        if any((row['body']['context'], row['body']['questions']) != base for row in arms.values()):
            raise RuntimeError('Arms disagree on the frozen questionnaire')
    answers = json.loads((PRIVATE / 'answers.json').read_text())
    if set(answers) != {str(rig) for rig in by_rig}:
        raise RuntimeError('Answer file does not cover exactly the frozen recipients')


def check_state_files():
    """Every recorded call is a success or an explicit failure; caps are respected."""
    directory = PRIVATE / 'runs'
    if not directory.exists():
        return
    caps = {'qwen': 96, 'pro': 476}
    for path in directory.glob('*.jsonl'):
        model = path.stem
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        if model in caps and len(rows) > caps[model]:
            raise RuntimeError('Call cap exceeded for ' + model)
        for row in rows:
            if row['status'] != 'ok' and not (row.get('raw') or row.get('reason')):
                raise RuntimeError('Unaccounted failure without diagnostic')
            if row['status'] == 'ok' and 'probabilities' not in row:
                raise RuntimeError('Success without stored probabilities')


def main():
    verify()
    check_archive()
    check_report()
    check_summary()
    check_admission()
    check_stage2()
    check_state_files()
    print('PASS: archive, references, report, admission, frozen deck, call ledger.')


if __name__ == '__main__':
    main()
