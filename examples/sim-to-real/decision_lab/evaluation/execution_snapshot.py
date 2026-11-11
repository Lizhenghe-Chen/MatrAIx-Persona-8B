"""Read-only proof that a finished checkpoint still matches its frozen inputs."""
import argparse, json, sqlite3
from pathlib import Path
from ..core.core import digest, request_payload
from ..core.provider import build_request
from .execution_quality import summarize


def _plan(root):
    root=Path(root);plan=[]
    formal=root/'formal-v1'
    if formal.exists():
        manifest=json.loads((formal/'manifest.json').read_text())
        for unit in manifest['units']:
            plan.append({'track':'formal-v1','directory':formal,'name':unit['name'],'phase':unit['phase'],
                         'expected':unit['calls'],'hashes':unit})
    synthetic=root/'synthetic-formal-v1'
    if synthetic.exists():
        manifest=json.loads((synthetic/'manifest.json').read_text())
        expected=manifest['tasks_per_condition']
        for unit in manifest['units']:
            plan.append({'track':'synthetic-formal-v1','directory':synthetic,'name':unit['name'],'phase':'test',
                         'expected':expected,'hashes':unit})
    return plan


def verify_unit(item):
    directory=item['directory'];name=item['name']
    study=json.loads((directory/(name+'-study.json')).read_text())
    config=json.loads((directory/(name+'-config.json')).read_text())
    seal=json.loads((directory/(name+'-seal.json')).read_text())
    record={'track':item['track'],'unit':name,'phase':item['phase'],'expected_tasks':item['expected']}
    record['frozen_hashes_match']=all(
        digest(obj)==item['hashes'][key]
        for obj,key in [(study,'study_sha256'),(config,'config_sha256'),(seal,'seal_sha256')])
    record['seal_matches']=seal['input_sha256']==digest(study) and seal['config_sha256']==digest(config)
    database=directory/(name+'.sqlite')
    if not database.exists():
        record.update(checkpoint='missing',completed_tasks=0,complete=False,request_identities_verified=False)
        return record
    connection=sqlite3.connect(f'file:{database}?mode=ro',uri=True)
    try:
        record['sqlite_integrity']=connection.execute('PRAGMA integrity_check').fetchone()[0]
        stored=dict(connection.execute('SELECT job,request_hash FROM calls'))
        responses=connection.execute("SELECT response FROM calls WHERE status='complete'").fetchall()
    finally:
        connection.close()
    rows=[r for r in study['rows'] if seal['assignments'][r['person']]==item['phase']]
    mismatched=0;unexpected=0
    for row in rows:
        job=digest([row['person'],row['task']])
        stored_hash=stored.get(job)
        if stored_hash is None:continue
        body=build_request(request_payload(row,config),config)
        mismatched+=digest(body)!=stored_hash
    expected_jobs={digest([r['person'],r['task']]) for r in rows}
    unexpected=len(set(stored)-expected_jobs)
    identity=json.dumps(config['expected_identity'],sort_keys=True)
    bad_identity=sum(json.dumps(json.loads(text)['identity'],sort_keys=True)!=identity for (text,) in responses)
    execution=summarize(database)
    record.update(execution=execution,completed_tasks=execution['states'].get('complete',0),
                  complete=execution['states'].get('complete',0)==item['expected'] and not execution['states'].get('failed') and not execution['states'].get('pending'),
                  request_hashes_mismatched=mismatched,unexpected_jobs=unexpected,
                  request_identities_verified=bad_identity==0,
                  failure_reasons=execution['error_categories'])
    return record


def snapshot(root):
    units=[verify_unit(item) for item in _plan(root)]
    failures=[]
    for unit in units:
        label=f"{unit['track']}/{unit['unit']}"
        if not unit['frozen_hashes_match']:failures.append(f'{label}: frozen files changed')
        if not unit.get('seal_matches',False):failures.append(f'{label}: seal does not match its inputs')
        if unit.get('checkpoint')=='missing':failures.append(f'{label}: no checkpoint')
        elif not unit['complete']:failures.append(f'{label}: incomplete {unit.get("execution",{}).get("states")}')
        if unit.get('sqlite_integrity') not in (None,'ok'):failures.append(f'{label}: sqlite integrity {unit["sqlite_integrity"]}')
        if unit.get('request_hashes_mismatched'):failures.append(f'{label}: {unit["request_hashes_mismatched"]} requests differ from frozen inputs')
        if unit.get('unexpected_jobs'):failures.append(f'{label}: {unit["unexpected_jobs"]} stored jobs are outside the frozen plan')
        if unit.get('request_identities_verified') is False:failures.append(f'{label}: server identity differs from the frozen identity')
    return {'status':'verified_complete_plan' if not failures else 'verification_failed',
            'root':str(Path(root)),'units':units,'failures':failures,
            'limits':['This checks frozen-input fidelity and completion, not scientific validity.',
                      'Reserved budget is a conservative request bound, not an invoiced cost.',
                      'Token totals omit unsuccessful responses whose usage was not retained.']}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('root',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Do not overwrite a verification record')
    result=snapshot(args.root)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'units':len(result['units']),'failures':result['failures']},ensure_ascii=False))
    raise SystemExit(0 if result['status']=='verified_complete_plan' else 1)
