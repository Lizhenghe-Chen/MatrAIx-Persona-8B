"""Full-release aggregate provenance/coverage audit. Never export respondent rows."""
import argparse,json,hashlib
from collections import Counter
from pathlib import Path
import pyarrow.parquet as pq
from .registry import DATA,OUT
FIELDS=['region','age_bracket','highest_education','gender_identity','demo_household_income','demo_employment_status','lstyle_household_size']
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def decode(row,columns):
 overrides=row['attribute_overrides'] or {}
 if isinstance(overrides,str):overrides=json.loads(overrides)
 if isinstance(overrides,list):overrides=dict(overrides)
 out={}
 for i,c in columns:
  key=c['id']; bitmap=row['null_bitmap']
  if key in overrides:out[key]=overrides[key]
  elif bitmap is not None and (bitmap[i//8]>>(i%8))&1:out[key]='unknown'
  else:
   code=(row['attributes'][i//2]>>(4*(i%2)))&15
   out[key]=c['values'][code] if code<len(c['values']) else 'invalid_code'
 return out

def audit():
 root=DATA/'09_MatrAIx画像/Persona-1M发行版'; manifest=json.loads((root/'manifest.json').read_text())
 cols=[(i,c) for i,c in enumerate(json.loads((root/'persona_codes.schema.json').read_text())['columns']) if c['id'] in FIELDS]
 counts=Counter();joint=Counter();missing=Counter();margins=Counter();files=[]
 for ent in manifest['files']:
  p=root/ent['path'];sha=digest(p)
  if sha!=ent['sha256']:raise ValueError('Release shard content hash mismatch: '+ent['path'])
  f=pq.ParquetFile(p);assert f.metadata.num_rows==ent['rows']
  for batch in f.iter_batches(batch_size=4096,columns=['source','attributes','null_bitmap','attribute_overrides']):
   for row in batch.to_pylist():
    s=row['source'];counts[s]+=1;d=decode(row,cols)
    for k,v in d.items():
     if v in (None,'unknown','invalid_code'):missing[(s,k)]+=1
     margins[(s,k,str(v))]+=1
    joint[(s,str(d['region']),str(d['age_bracket']),str(d['highest_education']))]+=1
  files.append({'path':ent['path'],'sha256':sha,'rows':f.metadata.num_rows,'bytes':p.stat().st_size})
  print('Audited shard',ent['path'],'cumulative rows',sum(counts.values()),flush=True)
 assert dict(counts)==manifest['sources']
 result={'status':'full_shards_hashed_and_all_sources_decoded','rows':sum(counts.values()),'source_counts':dict(counts),'files':files,
 'release_manifest_sha256':digest(root/'manifest.json'),'schema_sha256':digest(root/'persona_codes.schema.json'),
 'joint_cells':[dict(source=s,region=r,age=a,education=e,count=n) for (s,r,a,e),n in sorted(joint.items())],
 'margins':[dict(source=s,field=k,value=v,count=n) for (s,k,v),n in sorted(margins.items())],
 'missing':[dict(source=s,field=k,count=n) for (s,k),n in sorted(missing.items())],
 'source_exclusion_policy':{'all_external':['real_human_survey'],'amazon':['amazon'],'anes':['gss'],
 'reason':'Conservative provenance quarantine; source labels alone cannot prove absence of overlap. Real-human-survey origin unresolved; Amazon provenance must be traced before any relaxation.'},
 'limitations':['Coverage is not representative matching. No country residence inferred from region.','No individual identifiers or grounding text exported.','Human-grounded does not mean attributes directly measured.']}
 OUT.mkdir(exist_ok=True,parents=True);(OUT/'persona-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 return result
if __name__=='__main__':audit()
