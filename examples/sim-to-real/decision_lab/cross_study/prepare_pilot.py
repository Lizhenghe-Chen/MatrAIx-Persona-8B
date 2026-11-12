"""One participant per available study, four interleaved arms; format checks only."""
import json,hashlib,random
from collections import defaultdict,Counter
import pyarrow.parquet as pq
from .registry import DATA,ROOT,OUT,SPEC
from .targets import PRIVATE
from .personas import decode
from .protocol import ARMS,build_body

def main():
 path=PRIVATE/'participant-pilot-v1.json'
 if path.exists():raise ValueError('Immutable pilot exists; inspect it rather than rebuilding')
 cohort=json.loads((PRIVATE/'cohort-candidate-v2.json').read_text());chosen={}
 for row in cohort:
  if row['phase']=='pilot' and row['study'] not in chosen and row['persona']:chosen[row['study']]=row
 release=DATA/'09_MatrAIx画像/Persona-1M发行版'
 schema=json.loads((release/'persona_codes.schema.json').read_text())['columns']
 allowed={d['id']:set(d['values']) for d in json.loads((ROOT.parents[2]/'persona/schema/dimensions.json').read_text())['dimensions']}
 wanted=defaultdict(dict)
 for study,r in chosen.items():wanted[r['persona']['shard']][r['persona']['row_index']]=study
 profiles={};dropped={}
 for shard,indices in wanted.items():
  offset=0
  for batch in pq.ParquetFile(release/shard).iter_batches(batch_size=4096,columns=['attributes','null_bitmap','attribute_overrides']):
   if not any(offset<=i<offset+len(batch) for i in indices):offset+=len(batch);continue
   for i,row in enumerate(batch.to_pylist(),offset):
    if i not in indices:continue
    dims=decode(row,list(enumerate(schema)));approved={k:v for k,v in dims.items() if k in allowed and isinstance(v,str) and v in allowed[k]}
    study=indices[i];profiles[study]=approved;dropped[study]=len(dims)-len(approved)
   offset+=len(batch)
 jobs=[]
 for study,r in chosen.items():
  inst={'id':'cross_study_'+study,'title':'Survey','questions':r['questions']}
  for arm in ARMS:
   body=build_body(profiles[study],inst,r['context'],arm)
   jobs.append({'study':study,'arm':arm,'instrument':inst,'body':body})
 random.Random(20261109).shuffle(jobs)
 # No person IDs, truth, source pointers or original background in request artifact.
 payload={'purpose':'format_only_no_scoring','jobs':jobs}
 path.write_text(json.dumps(payload,ensure_ascii=False)+'\n');path.chmod(0o600)
 summary={'status':'prepared_not_run','participants_per_study':1,'jobs':len(jobs),'max_calls':len(jobs),'max_retries':0,'max_cost_usd':5,
 'reserved_peak_usd':sum(((len(json.dumps(j['body']).encode())+1024)*1.32+j['body']['max_tokens']*3.96)/1e6 for j in jobs),
 'studies':{s:{'questions':len(r['questions']),'canonical_profile_dimensions':len(profiles[s]),'omitted_noncanonical_or_null':dropped[s]} for s,r in chosen.items()},
 'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'scope':'Only format/identity and input isolation. No effect metrics. These pilot people cannot enter screening.',
 'formal_budget_approved':False}
 (SPEC/'participant-pilot.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
