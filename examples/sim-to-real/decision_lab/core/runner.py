"""Sequential checkpointed execution with frozen inputs and conservative spend caps."""
import fcntl
import json
import math
import os
from pathlib import Path
import sqlite3
import time
from .core import digest, request_payload, validate
from .provider import build_request, parse_response, send

GATES=('license_cloud_use','question_mapping','background_timing','author_statistics','leakage_review')


def run(study, seal, config, database, phase, transport=send, max_new_calls=None):
    population=study.get('evaluation_mode')=='synthetic_population'
    if population and study.get('person_source')!='generated':
        raise ValueError('Synthetic population requires explicit generated provenance')
    validate(study['rows'],require_answers=not population)
    if not all(study.get('audit',{}).get(k) is True for k in GATES):
        raise ValueError('Data admission incomplete')
    if seal['input_sha256']!=digest(study) or seal['config_sha256']!=digest(config):
        raise ValueError('Frozen input or config changed')
    if phase not in ('train','development','test'):raise ValueError('Unknown phase')
    if config.get('status')!='frozen':raise ValueError('Run configuration not frozen')
    expected=config['expected_identity']
    if not expected.get('model'):raise ValueError('Missing verified server identity')
    cap=config['max_calls'];budget=config['max_cost_usd']
    if not isinstance(cap,int) or cap<1 or not math.isfinite(budget) or budget<=0:raise ValueError('Invalid limits')
    rows=[r for r in study['rows'] if seal['assignments'][r['person']]==phase]
    jobs=[]
    for r in rows:
        body=build_request(request_payload(r,config),config)
        # One UTF-8 byte per input token is deliberately conservative; add envelope margin.
        bound=((len(json.dumps(body,ensure_ascii=False).encode())+1024)*config['input_usd_per_million']+
               config['max_tokens']*config['output_usd_per_million'])/1e6
        jobs.append((digest([r['person'],r['task']]),body,bound,len(r['options'])))
    path=Path(database);path.parent.mkdir(parents=True,exist_ok=True)
    stop_reason=None
    control_path=path.parent/'run-control.json'
    with path.with_suffix('.lock').open('a') as lock:
        os.chmod(lock.name,0o600);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        db=sqlite3.connect(path);os.chmod(path,0o600)
        try:
            db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS calls (job TEXT PRIMARY KEY, request_hash TEXT, status TEXT, reserved_usd REAL, response TEXT, error TEXT, elapsed REAL)')
            run_hash=digest({'seal':seal,'phase':phase})
            existing=db.execute("SELECT value FROM metadata WHERE key='run_hash'").fetchone()
            if existing and existing[0]!=run_hash:raise ValueError('Checkpoint belongs to another frozen run')
            db.execute("INSERT OR IGNORE INTO metadata VALUES ('run_hash',?)",(run_hash,));db.commit()
            if db.execute("SELECT count(*) FROM calls WHERE status='pending'").fetchone()[0]:
                raise RuntimeError('Uncertain interrupted request: reconcile before resuming; no automatic repeat')
            started = 0
            for job,body,bound,n in jobs:
                if max_new_calls is not None and started >= max_new_calls:
                    stop_reason='batch_limit'; break
                if control_path.exists():
                    control=json.loads(control_path.read_text())
                    deadline=control.get('stop_starting_calls_at_epoch')
                    if control.get('stop_requested') or (deadline is not None and time.time()>=float(deadline)):
                        stop_reason='user_stop' if control.get('stop_requested') else 'deadline'
                        break
                old=db.execute('SELECT request_hash,status FROM calls WHERE job=?',(job,)).fetchone()
                if old:
                    if old[0]!=digest(body):raise ValueError('Request changed')
                    continue
                count,spent=db.execute('SELECT count(*),coalesce(sum(reserved_usd),0) FROM calls').fetchone()
                if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='failed_attempts'").fetchone():
                    count += db.execute('SELECT count(*) FROM failed_attempts').fetchone()[0]
                if count>=cap or spent+bound>budget:break
                db.execute('INSERT INTO calls VALUES (?,?,?,?,?,?,?)',(job,digest(body),'pending',bound,None,None,None));db.commit()
                start=time.monotonic()
                started += 1
                try:
                    raw=transport(body,config['endpoint'])
                    result=parse_response(raw,n,expected,config.get('output_mode','probabilities'))
                except Exception as exc:
                    # Persist only error type, never request content, headers or server body.
                    db.execute('UPDATE calls SET status=?,error=?,elapsed=? WHERE job=?',('failed',getattr(exc,'reason_code',type(exc).__name__),time.monotonic()-start,job));db.commit()
                    raise RuntimeError('Call failed; inspect checkpoint before explicit retry') from None
                db.execute('UPDATE calls SET status=?,response=?,elapsed=? WHERE job=?',('complete',json.dumps(result),time.monotonic()-start,job));db.commit()
            counts=dict(db.execute('SELECT status,count(*) FROM calls GROUP BY status'))
            return {'expected_jobs':len(jobs),'states':counts,'stop_reason':stop_reason,'complete':counts.get('complete',0)==len(jobs),
                    'reserved_cost_usd':db.execute('SELECT coalesce(sum(reserved_usd),0) FROM calls').fetchone()[0]}
        finally:db.close()
