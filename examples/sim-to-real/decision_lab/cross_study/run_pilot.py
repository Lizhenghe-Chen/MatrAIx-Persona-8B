"""Bounded technical checks, no outcome comparison; immutable request checkpointing."""
import hashlib,json,os,time
from pathlib import Path
from .registry import SPEC,OUT
from .targets import PRIVATE
from .protocol import parse
from ..core.provider import send

def main():
 spec=json.loads((SPEC/'participant-pilot.json').read_text());p=PRIVATE/'participant-pilot-v1.json'
 if hashlib.sha256(p.read_bytes()).hexdigest()!=spec['input_sha256']:raise ValueError('Pilot input changed')
 if spec['reserved_peak_usd']>spec['max_cost_usd']:raise ValueError('Pilot reservation exceeds cap')
 jobs=json.loads(p.read_text())['jobs']
 if len(jobs)!=spec['max_calls']:raise ValueError('Call count mismatch')
 if not os.environ.get('DEEPSEEK_API_KEY'):os.environ['DEEPSEEK_API_KEY']=json.loads((Path.home()/'.config/matraix-decision-lab/credentials.json').read_text())['DEEPSEEK_API_KEY']
 folder=PRIVATE/'participant-pilot-results';folder.mkdir(exist_ok=True);folder.chmod(0o700)
 identity=json.loads((OUT/'technical-result.json').read_text())['rows'][0]['identity'];public=[]
 for i,job in enumerate(jobs):
  target=folder/f'{i:03}.json';pending=folder/f'{i:03}.pending'
  if target.exists():record=json.loads(target.read_text())
  else:
   if pending.exists():raise RuntimeError('Interrupted request needs reconciliation; do not resend blindly')
   pending.write_text('reserved');pending.chmod(0o600);start=time.monotonic()
   record={'study':job['study'],'arm':job['arm'],'status':'failed','request_sha256':hashlib.sha256(json.dumps(job['body'],sort_keys=True).encode()).hexdigest()}
   try:
    raw=send(job['body'],'https://api.deepseek.com/chat/completions',timeout=90)
    record['raw']=raw
    record['result']=parse(raw,job['instrument'],job['arm'],identity);record['status']='complete'
   except Exception as exc:record['error_type']=type(exc).__name__
   record['seconds']=time.monotonic()-start;target.write_text(json.dumps(record,ensure_ascii=False)+'\n');target.chmod(0o600);pending.unlink()
  row={k:v for k,v in record.items() if k not in ['raw','result']}
  row['usage']=record.get('raw',{}).get('usage',{})
  public.append(row)
  (OUT/'participant-pilot-result.json').write_text(json.dumps({'purpose':'format_only_no_effect_scoring','planned':len(jobs),'attempted':len(public),'rows':public,'formal_budget_approved':False},ensure_ascii=False,indent=2)+'\n')
  print(i+1,len(jobs),job['study'],job['arm'],record['status'],flush=True)
  actual=record.get('raw',{})
  if actual and {'model':actual.get('model'),'system_fingerprint':actual.get('system_fingerprint')}!=identity:raise ValueError('Model identity changed; stop')
if __name__=='__main__':main()
