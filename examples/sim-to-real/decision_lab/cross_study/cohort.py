"""Prepare a reproducible local candidate pool and six-study demographic matching audit."""
import json,hashlib,random,os
from pathlib import Path
from collections import defaultdict,Counter
import pyarrow.parquet as pq
from .registry import DATA,OUT
from .targets import PRIVATE
from .personas import decode,FIELDS
from .matching import constraints,compatible
SEED=20261109

def main():
 if (PRIVATE/'cohort-candidate-v2.json').exists():raise ValueError('Candidate snapshot already exists')
 targets=json.loads((PRIVATE/'existing-target-blocks.json').read_text());by_study=defaultdict(list);excluded=defaultdict(Counter)
 for r in targets:
  rule,error=constraints(r)
  if error:excluded[r['study']][error]+=1
  else:r['matching_rule']=rule;by_study[r['study']].append(r)
 # Make selections before looking at any answer; no scores are computed.
 selected=[];selection_summary={}
 for study,rows in sorted(by_study.items()):
  groups=defaultdict(list)
  for r in rows:groups[str(r['stratum'])].append(r)
  rng=random.Random(f'{SEED}:{study}:participants')
  for key in sorted(groups):rng.shuffle(groups[key])
  parts={};used=set()
  for phase,n in [('pilot',8),('screen',48),('reserve',96)]:
   available={k:[x for x in v if x['person'] not in used] for k,v in groups.items()};available={k:v for k,v in available.items() if v}
   total=sum(map(len,available.values()))
   if total<n:raise ValueError('Insufficient disjoint participants')
   # Largest remainder allocation, based on original stratum population counts.
   quota={k:int(n*len(v)/total) for k,v in available.items()}
   for k in sorted(available,key=lambda k:(-(n*len(available[k])/total-quota[k]),k))[:n-sum(quota.values())]:quota[k]+=1
   phase_rows=[]
   for k in sorted(available):
    for row in available[k][:quota[k]]:
     record={**row,'phase':phase,'inclusion_probability':quota[k]/len(available[k])}
     phase_rows.append(record);used.add(row['person'])
   parts[phase]=dict(Counter(str(r['stratum']) for r in phase_rows));selected+=phase_rows
  selection_summary[study]={'eligible_backgrounds':len(rows),'excluded_backgrounds':dict(excluded[study]),'allocation':parts,'warning':'A pilot may omit rare strata. Formal stratum coverage must be accepted before run.'}
 release=DATA/'09_MatrAIx画像/Persona-1M发行版';manifest=json.loads((release/'manifest.json').read_text());schema=json.loads((release/'persona_codes.schema.json').read_text())['columns'];cols=[(i,c) for i,c in enumerate(schema) if c['id'] in FIELDS]
 needed={r['matching_rule']['allowed']['region'][0] for r in selected};pool=defaultdict(list);seen=Counter();rng=random.Random(SEED)
 for ent in manifest['files']:
  offset=0;f=pq.ParquetFile(release/ent['path'])
  for batch in f.iter_batches(batch_size=4096,columns=['source','attributes','null_bitmap','attribute_overrides']):
   for row in batch.to_pylist():
    fields=decode(row,cols);idx=offset;offset+=1
    if fields['region'] not in needed or fields['age_bracket'] in ['Under 5','5-12','13-17','unknown']:continue
    if row['source']=='real_human_survey':continue
    key=(row['source'],*(str(fields[k]) for k in FIELDS if k!='demo_household_income' and k!='demo_employment_status'))
    seen[key]+=1;slot=len(pool[key]) if len(pool[key])<12 else rng.randrange(seen[key])
    if slot>=12:continue
    entry={'source':row['source'],'shard':ent['path'],'row_index':idx,'fields':fields}
    if slot==len(pool[key]):pool[key].append(entry)
    else:pool[key][slot]=entry
  print('Candidate pool scanned',ent['path'],flush=True)
 candidates=[x for k in sorted(pool) for x in pool[k]];by_region=defaultdict(list)
 for c in candidates:by_region[c['fields']['region']].append(c)
 matches=[];used_per_study=defaultdict(set)
 for row in selected:
  rule=row['matching_rule'];choices=[c for c in by_region[rule['allowed']['region'][0]] if compatible(c,rule)]
  choices.sort(key=lambda c:hashlib.sha256(f"{SEED}:{row['study']}:{row['person']}:{c['shard']}:{c['row_index']}".encode()).hexdigest())
  unused=[c for c in choices if (c['shard'],c['row_index']) not in used_per_study[row['study']]]
  chosen=unused[0] if unused else choices[0] if choices else None
  if chosen:used_per_study[row['study']].add((chosen['shard'],chosen['row_index']))
  matches.append({**row,'persona':chosen,'match_status':'release_match' if chosen else 'requires_generated_supplement','candidate_pool_matches':len(choices)})
 path=PRIVATE/'cohort-candidate-v2.json'
 if path.exists():raise ValueError('Do not overwrite participant/persona snapshot')
 path.write_text(json.dumps(matches,ensure_ascii=False)+'\n');path.chmod(0o600)
 for study in selection_summary:
  rows=[r for r in matches if r['study']==study];selection_summary[study].update(selected=len(rows),matched=sum(r['persona'] is not None for r in rows),unique_release_profiles=len(used_per_study[study]),source_counts=dict(Counter(r['persona']['source'] for r in rows if r['persona'])),age_resolutions=dict(Counter(r['matching_rule']['age_resolution'] for r in rows)))
 report={'status':'candidate_matching_not_formal_freeze','seed':SEED,'candidate_pool_records':len(candidates),'private_snapshot_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'studies':selection_summary,'limits':['Six existing study adapters only; remaining thirteen still require preparation.','Pool reservoirs are not full-population optimization; coverage shortfalls need full-cell verification before generation.','Income omitted pending currency/definition harmonization; no field silently imputed.','Source quarantine does not establish complete absence of training-data overlap.']}
 (OUT/'matching-candidate.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print({s:(v['matched'],v['selected']) for s,v in selection_summary.items()},flush=True)
if __name__=='__main__':main()
