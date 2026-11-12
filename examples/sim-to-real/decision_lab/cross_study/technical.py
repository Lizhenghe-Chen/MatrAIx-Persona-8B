"""Four synthetic-only native-format checks. No human answers or effect scores."""
import hashlib,json,os,time
from pathlib import Path
from .protocol import ARMS,build_body,parse
from .registry import SPEC,OUT
from ..core.provider import send

def main():
 private=Path.home()/'.local/share/matraix-decision-lab/cross-study-v1/technical';private.mkdir(parents=True,exist_ok=True);os.chmod(private,0o700)
 creds=Path.home()/'.config/matraix-decision-lab/credentials.json'
 if not os.environ.get('DEEPSEEK_API_KEY'):
  data=json.loads(creds.read_text());key=data.get('DEEPSEEK_API_KEY')
  if not key:raise RuntimeError('Missing configured credential')
  os.environ['DEEPSEEK_API_KEY']=key
 instrument={'id':'cross_study_format_check_v1','title':'Hypothetical product survey','questions':[
  {'id':'q1','type':'single_choice','prompt':'Which product would you choose?','required':True,'options':[{'id':'a','label':'Product A costs $20 and has a one-year warranty.'},{'id':'b','label':'Product B costs $25 and has a two-year warranty.'},{'id':'neither','label':'Neither product.'}]},
  {'id':'q2','type':'single_choice','prompt':'How important is comparing prices before buying?','required':True,'options':[{'id':'very','label':'Very important'},{'id':'somewhat','label':'Somewhat important'},{'id':'not','label':'Not important'}]}]}
 profile={'age_bracket':'25-34','region':'North America','highest_education':"Bachelor's"}
 context='United States. This is a hypothetical survey used only to verify response formatting. No actual person or purchase record is supplied.'
 jobs=[(a,build_body(profile,instrument,context,a)) for a in ARMS]
 manifest={'status':'technical_only_no_effect_scoring','max_calls':4,'max_cost_usd':1,'input_peak_usd_per_million':1.32,'output_peak_usd_per_million':3.96,'price_source':'https://api-docs.deepseek.com/quick_start/pricing/','price_checked':'2026-11-12','jobs':[{'arm':a,'sha256':hashlib.sha256(json.dumps(b,ensure_ascii=False,sort_keys=True).encode()).hexdigest()} for a,b in jobs]}
 seal=private/'manifest.json'
 if seal.exists() and json.loads(seal.read_text())!=manifest:raise ValueError('Technical inputs changed; use another version')
 seal.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');os.chmod(seal,0o600)
 (SPEC/'technical-protocol.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 bound=sum(((len(json.dumps(b).encode())+1024)*1.32+b['max_tokens']*3.96)/1e6 for _,b in jobs)
 if bound>1:raise ValueError('Technical cost cap')
 rows=[];identity=None
 for a,b in jobs:
  p=private/(a+'.json')
  if p.exists():record=json.loads(p.read_text())
  else:
   pending=private/(a+'.pending')
   if pending.exists():raise RuntimeError('Uncertain interrupted call; reconcile before resuming')
   pending.write_text('reserved before send');os.chmod(pending,0o600);start=time.monotonic()
   try:
    raw=send(b,'https://api.deepseek.com/chat/completions',timeout=90)
    result=parse(raw,instrument,a,identity)
    record={'arm':a,'status':'complete','elapsed_seconds':time.monotonic()-start,'result':result}
   except Exception as exc:record={'arm':a,'status':'failed','error_type':type(exc).__name__,'elapsed_seconds':time.monotonic()-start}
   p.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');os.chmod(p,0o600);pending.unlink()
  if record['status']=='complete':
   if identity is None:identity=record['result']['identity']
   elif identity!=record['result']['identity']:raise ValueError('Technical identity changed')
  rows.append({k:v for k,v in record.items() if k!='result'}|({'identity':record['result']['identity'],'usage':record['result']['usage']} if record['status']=='complete' else {}))
  print(a,record['status'],flush=True)
  if record['status']!='complete':break
 summary={'purpose':'synthetic-format-only; not participant pilot or experiment evidence','planned':4,'attempts':len(rows),'rows':rows,'conservative_reservation_usd':bound,'formal_budget_approved':False}
 (OUT/'technical-result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
