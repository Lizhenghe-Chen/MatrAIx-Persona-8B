"""Explicit one-attempt recovery; preserve failed attempts and cumulative spend."""
import json,sqlite3,fcntl,time,os,argparse
from pathlib import Path
from .core import digest,request_payload
from .provider import build_request,send,parse_response

def retry(directory,unit,credentials):
    root=Path(directory);read=lambda suffix:json.loads((root/(unit+suffix+'.json')).read_text())
    study,seal,config=read('-study'),read('-seal'),read('-config')
    if digest(study)!=seal['input_sha256'] or digest(config)!=seal['config_sha256']:raise ValueError('Freeze mismatch')
    os.environ['DEEPSEEK_API_KEY']=json.loads(Path(credentials).read_text())['DEEPSEEK_API_KEY']
    path=root/(unit+'.sqlite')
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        db=sqlite3.connect(path)
        try:
            if db.execute("select count(*) from calls where status='pending'").fetchone()[0]:raise ValueError('Uncertain pending request; do not retry')
            failed=db.execute("select * from calls where status='failed'").fetchall()
            if len(failed)!=1:raise ValueError('Recovery requires exactly one known failed request')
            old=failed[0];job,request_hash,status,reserved,response,error,elapsed=old
            row=next(r for r in study['rows'] if digest([r['person'],r['task']])==job)
            body=build_request(request_payload(row,config),config)
            if digest(body)!=request_hash:raise ValueError('Request differs')
            bound=((len(json.dumps(body,ensure_ascii=False).encode())+1024)*config['input_usd_per_million']+config['max_tokens']*config['output_usd_per_million'])/1e6
            spent=db.execute('select sum(reserved_usd) from calls').fetchone()[0]
            if spent+bound>config['max_cost_usd']:raise ValueError('Recovery exceeds budget')
            control=json.loads((root/'run-control.json').read_text()) if (root/'run-control.json').exists() else {}
            if control.get('stop_requested') or time.time()>=control.get('stop_starting_calls_at_epoch',float('inf')):raise ValueError('Operational stop applies')
            db.execute('create table if not exists failed_attempts (archived_at real,job text,request_hash text,error text,elapsed real,reserved_usd real)')
            db.execute('insert into failed_attempts values (?,?,?,?,?,?)',(time.time(),job,request_hash,error,elapsed,reserved))
            db.execute("update calls set status='pending',reserved_usd=?,error=NULL where job=?",(reserved+bound,job));db.commit()
            start=time.monotonic()
            try:result=parse_response(send(body,config['endpoint']),len(row['options']),config['expected_identity'],config.get('output_mode','probabilities'))
            except Exception as exc:
                db.execute("update calls set status='failed',error=?,elapsed=? where job=?",(getattr(exc,'reason_code',type(exc).__name__),time.monotonic()-start,job));db.commit();raise RuntimeError('Recovery failed; retained for inspection') from None
            db.execute("update calls set status='complete',response=?,elapsed=? where job=?",(json.dumps(result),time.monotonic()-start,job));db.commit()
            return {'recovered':1,'identity':result['identity'],'original_failure_retained':True}
        finally:db.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--unit',required=True);p.add_argument('--credentials',required=True);a=p.parse_args();print(json.dumps(retry(a.directory,a.unit,a.credentials)))
