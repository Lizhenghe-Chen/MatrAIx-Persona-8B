"""Read-only, identity-checked export from frozen execution checkpoints."""
import json
import sqlite3
from pathlib import Path
from .core import digest,request_payload,probabilities
from .provider import build_request


def read_predictions(study,seal,config,database,phase,require_complete=True):
    if seal['input_sha256']!=digest(study) or seal['config_sha256']!=digest(config):
        raise ValueError('Frozen input mismatch')
    path=Path(database)
    if not path.is_file():raise ValueError('Checkpoint missing')
    db=sqlite3.connect(f'file:{path}?mode=ro',uri=True)
    try:
        entry=db.execute("SELECT value FROM metadata WHERE key='run_hash'").fetchone()
        if not entry or entry[0]!=digest({'seal':seal,'phase':phase}):raise ValueError('Wrong checkpoint run')
        calls={r[0]:r[1:] for r in db.execute('SELECT job,request_hash,status,response FROM calls')}
    finally:db.close()
    selected=[r for r in study['rows'] if seal['assignments'][r['person']]==phase]
    expected={digest([r['person'],r['task']]) for r in selected}
    if set(calls)-expected:raise ValueError('Unexpected jobs in checkpoint')
    predictions={};missing=[]
    for row in selected:
        key=(row['person'],row['task']);call=calls.get(digest(list(key)))
        if call is None or call[1]!='complete':
            missing.append({'person':key[0],'task':key[1],'stratum':row['stratum'],'status':'not_started' if call is None else call[1]});continue
        if call[0]!=digest(build_request(request_payload(row,config),config)):
            raise ValueError('Request hash mismatch')
        response=json.loads(call[2])
        if response['identity']!=config['expected_identity']:raise ValueError('Response identity mismatch')
        if response.get('output_mode','probabilities')!=config.get('output_mode','probabilities'):
            raise ValueError('Response mode mismatch')
        predictions[key]=probabilities(response['probabilities'],len(row['options']))
    if require_complete and missing:raise ValueError('Incomplete unit; no silent row dropping')
    # Scoring metadata is local only and does not mutate frozen model inputs.
    rows=[{**r,'score_group':r.get('score_group',r.get('group'))} for r in selected]
    if any(r['score_group'] is None for r in rows):raise ValueError('Missing semantic score group')
    return rows,predictions,missing
