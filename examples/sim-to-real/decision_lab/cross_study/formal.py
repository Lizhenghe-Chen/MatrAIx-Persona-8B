"""Frozen formal runs for the six admitted studies; nothing runs before the freeze.

Commands:
  prepare  build jobs for the reserve cohort, freeze counts, hashes and caps
  run      execute the frozen plan with a resumable SQLite checkpoint
  retry    recover exactly one known failed call, preserving the failure record
  score    aggregate the checkpoint into card/share and paired-Brier results

No default answers are ever filled in: a failed call stays failed until an
explicit recovery.
"""
import argparse
import fcntl
import hashlib
import json
import math
import os
import sqlite3
import time
from collections import Counter, defaultdict
from pathlib import Path

from .protocol import ARMS, build_body, parse
from .registry import OUT, ROOT, SPEC
from .scoring import build_references, card_key, evaluate
from .targets import PRIVATE, load_existing
from ..core.provider import send

STUDIES = ['anes', 'dryer', 'pew13', 'pew168', 'shed', 'swiss']
IDENTITY = {'model': 'deepseek-v4-pro', 'system_fingerprint': 'a307abda487cd1b463329ccb945ce396'}
INPUT_USD, OUTPUT_USD = 1.32, 3.96
FORMS = PRIVATE / 'formal-v1-jobs.json'
RESULT = OUT / 'formal-results.json'
SPEC_FILE = SPEC / 'formal-v1.json'
DB = PRIVATE / 'formal-v1.sqlite'
CONTROL = PRIVATE / 'formal-v1-control.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _profiles(wanted):
    """Approved persona dimensions by (shard, row_index); never free text."""
    import pyarrow.parquet as pq
    from .personas import decode
    from .registry import DATA
    release = DATA / '09_MatrAIx画像/Persona-1M发行版'
    schema = json.loads((release / 'persona_codes.schema.json').read_text())['columns']
    allowed = {d['id']: set(d['values']) for d in
               json.loads((ROOT.parents[2] / 'persona/schema/dimensions.json').read_text())['dimensions']}
    by_shard = defaultdict(dict)
    for key in wanted:
        by_shard[key[0]][key[1]] = True
    out, dropped = {}, {}
    for shard, indices in by_shard.items():
        offset = 0
        for batch in pq.ParquetFile(release / shard).iter_batches(batch_size=4096,
                                                                  columns=['attributes', 'null_bitmap', 'attribute_overrides']):
            if not any(offset <= i < offset + len(batch) for i in indices):
                offset += len(batch)
                continue
            for i, row in enumerate(batch.to_pylist(), offset):
                if i not in indices:
                    continue
                dims = decode(row, list(enumerate(schema)))
                approved = {k: v for k, v in dims.items()
                            if k in allowed and isinstance(v, str) and v in allowed[k]}
                if not approved:
                    raise ValueError('Persona has no approved categorical dimension')
                out[(shard, i)] = approved
                dropped[(shard, i)] = len(dims) - len(approved)
            offset += len(batch)
    return out, dropped



def _distribution(values):
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    return {'min': ordered[0], 'median': median, 'max': ordered[-1],
            'mean': sum(ordered) / len(ordered), 'people': len(ordered)}



def prepare():
    if SPEC_FILE.exists() or FORMS.exists():
        raise ValueError('Formal plan already frozen; inspect it instead of rebuilding')
    cohort = json.loads((PRIVATE / 'cohort-candidate-v2.json').read_text())
    reserve = [r for r in cohort if r['phase'] == 'reserve' and r['study'] in STUDIES]
    excluded = [{'study': r['study'], 'person': r['person'],
                 'reason': 'no_frozen_persona_in_release' if not r.get('persona') else 'unknown'}
                for r in reserve if not r.get('persona')]
    usable = [r for r in reserve if r.get('persona')]
    wanted = {(r['persona']['shard'], r['persona']['row_index']) for r in usable}
    profiles, dropped = _profiles(wanted)
    jobs = []
    for row in usable:
        key = (row['persona']['shard'], row['persona']['row_index'])
        instrument = {'id': 'cross_study_' + row['study'], 'title': 'Survey',
                      'questions': row['questions']}
        for arm in ARMS:
            body = build_body(profiles[key], instrument, row['context'], arm)
            jobs.append({'study': row['study'], 'arm': arm, 'person': row['person'],
                         'instrument': instrument, 'body': body,
                         'body_sha256': hashlib.sha256(
                             json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()})
    # Interleave arms and studies so a time trend cannot align with one arm.
    order = sorted(range(len(jobs)), key=lambda i: hashlib.sha256(
        f'20261109:{i}'.encode()).hexdigest())
    jobs = [jobs[i] for i in order]
    counts = Counter((j['study'], j['arm']) for j in jobs)
    reserved = sum(((len(json.dumps(j['body'], ensure_ascii=False).encode()) + 1024) * INPUT_USD
                    + j['body']['max_tokens'] * OUTPUT_USD) / 1e6 for j in jobs)
    FORMS.parent.mkdir(parents=True, exist_ok=True)
    FORMS.write_text(json.dumps({'purpose': 'formal_cross_study', 'jobs': jobs}, ensure_ascii=False))
    os.chmod(FORMS, 0o600)
    spec = {
        'status': 'frozen_not_started',
        'studies': STUDIES, 'arms': list(ARMS),
        'excluded_participants': excluded,
        'excluded_policy': 'Excluded before any effect was computed: no complete approved persona exists in the release. Reported, never replaced by a hand-written profile.',
        'people_with_persona': dict(Counter(r['study'] for r in usable)),
        'jobs_per_study_arm': {f'{s}/{a}': counts[(s, a)] for s in STUDIES for a in ARMS},
        'total_calls': len(jobs),
        'max_calls': len(jobs),
        'max_retries': len(jobs) // 20 + 5,
        'reserved_peak_usd': reserved,
        'max_cost_usd': math.ceil(reserved * 1.2 * 100) / 100,
        'input_peak_usd_per_million': INPUT_USD,
        'output_peak_usd_per_million': OUTPUT_USD,
        'price_source': 'https://api-docs.deepseek.com/quick_start/pricing/',
        'expected_identity': IDENTITY,
        'jobs_sha256': sha(FORMS),
        'people_per_study': dict(Counter(r['study'] for r in usable)),
        'persona_field_distribution': {
            s: _distribution([len(profiles[(r['persona']['shard'], r['persona']['row_index'])])
                              for r in usable if r['study'] == s]) for s in STUDIES},
        'omitted_dimension_distribution': {
            s: _distribution([dropped[(r['persona']['shard'], r['persona']['row_index'])]
                              for r in usable if r['study'] == s]) for s in STUDIES},
        'persona_richness_note': ('Approved categorical dimensions sent per persona differ by study and by person. '
                                  'A cross-study comparison must read this table: a larger field count is not evidence '
                                  'that the persona is more accurate, but it is a confound for how much information '
                                  'the model received.'),
        'scoring_plan': {
            'primary': 'optimized versus original, per-person Brier, paired by person within stratum, 2000 draws',
            'required_comparators': ['history (weighted option shares from non-evaluated respondents)',
                                     'stratum_history (same, within stratum where at least 20 respondents exist)',
                                     'uniform'],
            'distribution': 'equal-card mean absolute share difference in percentage points',
            'gates': 'relative Brier improvement at least 2% with the 95% interval above zero; card-share improvement reported separately',
            'no_default_answers': True,
        },
        'formal_effects_available': False,
        'formal_run_authorized_by_user': True,
        'authorization_note': 'User authorized the formal run after this freeze on 2026-11-12.',
    }
    SPEC_FILE.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: spec[k] for k in ['total_calls', 'max_calls', 'reserved_peak_usd',
                                           'max_cost_usd', 'people_with_persona']},
                     ensure_ascii=False, indent=2))


def _load_credentials():
    if not os.environ.get('DEEPSEEK_API_KEY'):
        path = Path.home() / '.config/matraix-decision-lab/credentials.json'
        os.environ['DEEPSEEK_API_KEY'] = json.loads(path.read_text())['DEEPSEEK_API_KEY']


def _control():
    return json.loads(CONTROL.read_text()) if CONTROL.exists() else {}


def reconcile():
    """Turn an interrupted pending call into a retained failure, never a silent resend."""
    connection = sqlite3.connect(DB)
    try:
        connection.execute('CREATE TABLE IF NOT EXISTS failed_attempts (archived_at REAL, job TEXT, '
                           'request_hash TEXT, error TEXT, elapsed REAL, reserved_usd REAL)')
        pending = connection.execute("SELECT job,request_hash,reserved_usd,elapsed FROM calls "
                                     "WHERE status='pending'").fetchall()
        for job, request_hash, reserved, elapsed in pending:
            connection.execute('INSERT INTO failed_attempts VALUES (?,?,?,?,?,?)',
                               (time.time(), job, request_hash, 'interrupted_request_uncertain',
                                elapsed, reserved))
            connection.execute("UPDATE calls SET status='failed',error=? WHERE job=?",
                               ('interrupted_request_uncertain', job))
        connection.commit()
        print(json.dumps({'reconciled': len(pending)}))
    finally:
        connection.close()


def run(workers=1):
    spec = json.loads(SPEC_FILE.read_text())
    if spec['status'] not in ('frozen_not_started', 'running_paused', 'complete'):
        raise ValueError('Unknown frozen status')
    if sha(FORMS) != spec['jobs_sha256']:
        raise ValueError('Frozen job file changed')
    jobs = json.loads(FORMS.read_text())['jobs']
    if len(jobs) != spec['max_calls']:
        raise ValueError('Call count differs from the freeze')
    if spec['reserved_peak_usd'] > spec['max_cost_usd']:
        raise ValueError('Reservation exceeds the frozen cap')
    _load_credentials()
    setup = sqlite3.connect(DB)
    os.chmod(DB, 0o600)
    try:
        setup.execute('PRAGMA journal_mode=WAL')
        setup.execute('CREATE TABLE IF NOT EXISTS calls (job TEXT PRIMARY KEY, request_hash TEXT, '
                      'status TEXT, reserved_usd REAL, response TEXT, error TEXT, elapsed REAL)')
        setup.execute('CREATE TABLE IF NOT EXISTS failed_attempts (archived_at REAL, job TEXT, '
                      'request_hash TEXT, error TEXT, elapsed REAL, reserved_usd REAL)')
        setup.commit()
        if setup.execute("SELECT count(*) FROM calls WHERE status='pending'").fetchone()[0]:
            raise RuntimeError('Uncertain pending request: run reconcile, then retry explicitly')
    finally:
        setup.close()
    spec['status'] = 'running_paused'
    spec['execution_mode'] = {'workers': workers,
                              'claim': 'INSERT OR IGNORE inside BEGIN IMMEDIATE; one row per frozen body hash'}
    SPEC_FILE.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + '\n')

    import threading
    results = {}
    lock = threading.Lock()

    def worker(index):
        connection = sqlite3.connect(DB, timeout=60, isolation_level=None)
        connection.execute('PRAGMA busy_timeout=60000')
        done = failed = 0
        try:
            for job in jobs:
                if _control().get('stop_requested'):
                    break
                key = job['body_sha256']
                row = connection.execute('SELECT status FROM calls WHERE job=?', (key,)).fetchone()
                if row:
                    done += row[0] == 'complete'
                    continue
                bound = ((len(json.dumps(job['body'], ensure_ascii=False).encode()) + 1024) * INPUT_USD
                         + job['body']['max_tokens'] * OUTPUT_USD) / 1e6
                connection.execute('BEGIN IMMEDIATE')
                try:
                    claimed = connection.execute('INSERT OR IGNORE INTO calls VALUES (?,?,?,?,?,?,?)',
                                                 (key, key, 'pending', bound, None, None, None)).rowcount
                    connection.execute('COMMIT')
                except Exception:
                    connection.execute('ROLLBACK')
                    raise
                if claimed != 1:
                    continue
                start = time.monotonic()
                try:
                    raw = send(job['body'], 'https://api.deepseek.com/chat/completions', timeout=120)
                    result = parse(raw, job['instrument'], job['arm'], spec['expected_identity'])
                except Exception as exc:
                    connection.execute('UPDATE calls SET status=?,error=?,elapsed=? WHERE job=?',
                                       ('failed', getattr(exc, 'reason_code', type(exc).__name__),
                                        time.monotonic() - start, key))
                    failed += 1
                    print(json.dumps({'worker': index, 'failed': job['study'], 'error':
                                      getattr(exc, 'reason_code', type(exc).__name__)}), flush=True)
                    continue
                connection.execute('UPDATE calls SET status=?,response=?,elapsed=? WHERE job=?',
                                   ('complete', json.dumps(result), time.monotonic() - start, key))
                done += 1
                if done % 100 == 0:
                    print(json.dumps({'worker': index, 'done': done}), flush=True)
        finally:
            connection.close()
            with lock:
                results[index] = {'complete': done, 'failed': failed}

    threads = [threading.Thread(target=worker, args=(i,), daemon=False) for i in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    states = {}
    connection = sqlite3.connect(DB)
    try:
        states = dict(connection.execute('SELECT status,count(*) FROM calls GROUP BY status'))
        if states.get('pending'):
            raise RuntimeError('Pending rows remain; run reconcile before continuing')
        spec = json.loads(SPEC_FILE.read_text())
        spec['status'] = 'complete' if states.get('complete') == len(jobs) else 'running_paused'
        SPEC_FILE.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + '\n')
    finally:
        connection.close()
    print(json.dumps({'states': states, 'workers': results}, ensure_ascii=False))


def retry():
    spec = json.loads(SPEC_FILE.read_text())
    jobs = json.loads(FORMS.read_text())['jobs']
    by_hash = {j['body_sha256']: j for j in jobs}
    _load_credentials()
    with (DB.parent / 'formal-v1.lock').open('a') as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        connection = sqlite3.connect(DB)
        try:
            if connection.execute("SELECT count(*) FROM calls WHERE status='pending'").fetchone()[0]:
                raise ValueError('Uncertain pending request; inspect before retrying')
            failed = connection.execute("SELECT * FROM calls WHERE status='failed'").fetchall()
            if not failed:
                raise ValueError('No failed call to recover')
            if len(failed) > 1 and not os.environ.get('MATRAIX_RETRY_ALL'):
                raise ValueError('Several failures; set MATRAIX_RETRY_ALL=1 to recover them one by one')
            key, request_hash, _, reserved, _, error, elapsed = failed[0]
            job = by_hash.get(key)
            if job is None or request_hash != job['body_sha256']:
                raise ValueError('Failed job is not part of the frozen plan')
            if _control().get('stop_requested'):
                raise ValueError('Operational stop is set')
            connection.execute('INSERT INTO failed_attempts VALUES (?,?,?,?,?,?)',
                               (time.time(), key, request_hash, error, elapsed, reserved))
            connection.execute("UPDATE calls SET status='pending',error=NULL WHERE job=?", (key,))
            connection.commit()
            start = time.monotonic()
            try:
                raw = send(job['body'], 'https://api.deepseek.com/chat/completions', timeout=120)
                result = parse(raw, job['instrument'], job['arm'], spec['expected_identity'])
            except Exception as exc:
                connection.execute("UPDATE calls SET status='failed',error=?,elapsed=? WHERE job=?",
                                   (getattr(exc, 'reason_code', type(exc).__name__),
                                    time.monotonic() - start, key))
                connection.commit()
                raise RuntimeError('Recovery failed; record retained') from None
            connection.execute("UPDATE calls SET status='complete',response=?,elapsed=? WHERE job=?",
                               (json.dumps(result), time.monotonic() - start, key))
            connection.commit()
            print(json.dumps({'recovered': 1, 'identity': result['identity'],
                              'original_failure_retained': True}))
        finally:
            connection.close()


def _cases():
    spec = json.loads(SPEC_FILE.read_text())
    cohort = json.loads((PRIVATE / 'cohort-candidate-v2.json').read_text())
    reserve = [r for r in cohort if r['phase'] == 'reserve' and r.get('persona') and r['study'] in STUDIES]
    truth = {(r['study'], r['person']): r for r in reserve}
    jobs = json.loads(FORMS.read_text())['jobs']
    connection = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    try:
        states = dict(connection.execute('SELECT status,count(*) FROM calls GROUP BY status'))
        rows = {j: json.loads(r) for j, r in
                connection.execute("SELECT job,response FROM calls WHERE status='complete'")}
    finally:
        connection.close()
    if states.get('failed') or states.get('pending'):
        raise ValueError('Checkpoint is not clean: ' + json.dumps(states))
    predictions = defaultdict(dict)
    missing = 0
    for job in jobs:
        result = rows.get(job['body_sha256'])
        if result is None:
            missing += 1
            continue
        predictions[(job['study'], job['person'])][job['arm']] = result['probabilities']
    cases_by_study = defaultdict(list)
    partial = defaultdict(lambda: {'people_with_any_missing_answer': 0, 'dropped_questions': 0,
                                   'people_excluded_for_coverage': 0})
    from .scoring import option_ids
    for (study, person), arms in predictions.items():
        if set(arms) != set(ARMS):
            missing += len(set(ARMS) - set(arms))
            continue
        row = truth[(study, person)]
        # Truth completeness is a data property, fixed before any model output is read.
        answered = [q for q in row['questions']
                    if row['truth'].get(str(q['id'])) in option_ids(q)]
        if len(answered) != len(row['questions']):
            partial[study]['people_with_any_missing_answer'] += 1
            partial[study]['dropped_questions'] += len(row['questions']) - len(answered)
        if not answered or len(answered) < math.ceil(len(row['questions']) / 2):
            partial[study]['people_excluded_for_coverage'] += 1
            continue
        cases_by_study[study].append({'study': study, 'person': person, 'stratum': row['stratum'],
                                      'weight': row.get('weight', 1.0),
                                      'truth': {k: v for k, v in row['truth'].items() if k in
                                                {str(q['id']) for q in answered}},
                                      'questions': answered, 'predictions': arms})
    return spec, cases_by_study, {"states": states, "missing_calls": missing,
                                  "answer_coverage": dict(partial),
                                  "coverage_rule": ('A person is scored on the questions they actually answered; '
                                                    'a person with fewer than half answered is excluded and counted. '
                                                    'The rule uses observed answers only, never model output.')}



def _attribute_baseline(study, cases, history_rows):
    """Same-information reference on displayed product attributes, fitted off the evaluated cohort.

    Used where choice cards are randomized, or where every card is unique, so no
    card-level historical share is estimable: conditional logit for choice cards,
    a rating model for 1-7 scales. Contains no evaluated person's answer.
    """
    if study == 'shoes':
        from .shoes_baseline import build
        table, note = build(cases, history_rows)
        if not table or not any(table.values()):
            return {}, note
        return {'attribute_rating': table}, note
    if study == 'swiss':
        from ..studies.swiss_baseline import attributes as parse
    elif study == 'dryer':
        from ..studies.dryer_baseline import attributes as parse
    else:
        return {}, 'no attribute model declared for this study'
    from ..core.baselines import ConditionalLogit

    def tasks(rows):
        out = []
        for row in rows:
            for question in row['questions']:
                ids = [str(o['id']) for o in question['options']]
                answer = row['truth'].get(str(question['id']))
                if answer not in ids:
                    continue
                try:
                    features = [parse(o['label']) for o in question['options']]
                except Exception:
                    continue
                out.append({'person': row['person'], 'features': features,
                            'answer': ids.index(answer), 'weight': float(row.get('weight', 1.0))})
        return out

    fit_rows = tasks(history_rows)
    if len(fit_rows) < 50:
        return {}, 'too few historical tasks to fit an attribute model'
    people = sorted({r['person'] for r in fit_rows})
    cut = max(1, int(len(people) * 0.8))
    train_people = set(people[:cut])
    train = [r for r in fit_rows if r['person'] in train_people]
    selection = [r for r in fit_rows if r['person'] not in train_people]
    model = ConditionalLogit(0.01).fit(train)
    penalty = 0.01
    if len(selection) >= 20:
        best_loss, best_penalty, best_model = None, penalty, model
        for candidate in (0.001, 0.01, 0.1, 1.0):
            fitted = ConditionalLogit(candidate).fit(train)
            probs = fitted.predict(selection)
            loss = sum(sum((v - int(i == t['answer'])) ** 2 for i, v in enumerate(q))
                       for t, q in zip(selection, probs)) / len(selection)
            if best_loss is None or loss < best_loss:
                best_loss, best_penalty, best_model = loss, candidate, fitted
        penalty, model = best_penalty, best_model
    table = {}
    for case in cases:
        vectors = {}
        for question in case['questions']:
            try:
                features = [parse(o['label']) for o in question['options']]
            except Exception:
                continue
            vectors[str(question['id'])] = model.predict(
                [{'features': features, 'answer': 0}])[0]
        table[case['person']] = vectors
    note = {'penalty': penalty, 'fit_tasks': len(train), 'fit_people': len(train_people),
            'selection_people': len(people) - len(train_people),
            'comparator': 'conditional logit on displayed product attributes only'}
    return {'attribute_logit': table}, note



def score():
    spec, cases_by_study, execution = _cases()
    source = list(load_existing())
    source_by_study = defaultdict(list)
    for row in source:
        source_by_study[row['study']].append(row)
    results = {'status': 'complete_formal_cross_study', 'arms': list(ARMS),
               'spec_sha256': sha(SPEC_FILE), 'jobs_sha256': spec['jobs_sha256'],
               'execution': execution, 'studies': {}, 'budget': {
                   'max_calls': spec['max_calls'],
                   'reserved_peak_usd': spec['reserved_peak_usd'],
                   'max_cost_usd': spec['max_cost_usd']}}
    for study in STUDIES:
        cases = cases_by_study.get(study, [])
        if not cases:
            raise ValueError('No complete cases for ' + study)
        evaluated = {c['person'] for c in cases}
        history_rows = [r for r in source_by_study.get(study, []) if r['person'] not in evaluated]
        if len(history_rows) < 20:
            raise ValueError('Too few non-evaluated respondents for a history baseline: ' + study)
        references = build_references(cases, history_rows)
        fitted = _attribute_baseline(study, cases, history_rows) or ({}, None)
        case_references, fitted_note = fitted
        results['studies'][study] = {
            'people': len(cases),
            'history_source_people': len(history_rows),
            'excluded_evaluated_from_history': True,
            'answer_coverage': execution['answer_coverage'].get(study, {}),
            'cards': len({card_key(q) for c in cases for q in c['questions']}),
            'cards_with_at_least_20_people': sum(
                1 for key in {card_key(q) for c in cases for q in c['questions']}
                if sum(1 for c in cases for q in c['questions'] if card_key(q) == key) >= 20),
            'attribute_baseline': fitted_note,
            'results': evaluate(cases, references, list(ARMS), case_references=case_references),
        }
    RESULT.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': results['status'],
                      'studies': {s: {'people': v['people'],
                                      'brier': {a: (None if m['brier'] is None else round(m['brier'], 4))
                                                for a, m in v['results']['arms'].items()}}
                                  for s, v in results['studies'].items()}}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'run', 'retry', 'score', 'reconcile'])
    parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args()
    if args.command == 'run':
        run(workers=max(1, args.workers))
    else:
        {'prepare': prepare, 'retry': retry, 'score': score, 'reconcile': reconcile}[args.command]()
