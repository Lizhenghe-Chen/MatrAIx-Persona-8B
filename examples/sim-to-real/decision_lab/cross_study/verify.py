"""Offline verification of preflight artifacts, no model calls or effect scoring."""
import hashlib,json,re
from pathlib import Path
from collections import defaultdict
from .registry import OUT,SPEC,ROOT
from .targets import PRIVATE
from .protocol import parse

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 inv=json.loads((OUT/'source-inventory.json').read_text())
 assert len(inv['studies'])==19
 assert all(f['exists'] and f['read_status']=='metadata_readable' for s in inv['studies'] for f in s['files'])
 for version in ('v23','v22','v21','v20','v19','v18','v17','v16','v15','v14','v13','v12','v11','v10','v9','v8','v7','v6','v5','v3','v2','v1'):
  accepted_path=ROOT.parent/f'archive/accepted-report-{version}.json'
  if accepted_path.exists():break
 accepted=json.loads(accepted_path.read_text())
 for f in accepted['files']:assert sha(ROOT.parent/f['path'])==f['sha256'],f['path']
 native=json.loads((SPEC/'native-runtime.json').read_text())
 for f in native['files']:assert sha(ROOT.parents[2]/f['path'])==f['sha256'],f['path']
 cohort=json.loads((PRIVATE/'cohort-candidate-v2.json').read_text());seen=set()
 for r in cohort:
  key=(r['study'],r['person']);assert key not in seen;seen.add(key)
  if r['persona']:
   from .matching import compatible
   assert compatible(r['persona'],r['matching_rule'])
 spec=json.loads((SPEC/'participant-pilot.json').read_text());assert sha(PRIVATE/'participant-pilot-v1.json')==spec['input_sha256']
 jobs=json.loads((PRIVATE/'participant-pilot-v1.json').read_text())['jobs'];groups=defaultdict(list)
 identity=json.loads((OUT/'technical-result.json').read_text())['rows'][0]['identity']
 for i,j in enumerate(jobs):
  groups[j['study']].append(j)
  record=json.loads((PRIVATE/'participant-pilot-results'/f'{i:03}.json').read_text())
  assert record['status']=='complete'
  parse(record['raw'],j['instrument'],j['arm'],identity)
  assert all(k not in j['body'] for k in ['truth','weight','person','background'])
 for study,rows in groups.items():
  assert len(rows)==4
  assert len({json.dumps(r['instrument'],sort_keys=True) for r in rows})==1
  assert len({r['body']['messages'][0]['content'] for r in rows})==1
 for target in re.findall(r'href="([^"]+)"',(OUT/'index.html').read_text()):
  if not target.startswith(('http:','https:','#')):assert (OUT/target).is_file(),target
 assert not json.loads((OUT/'admission.json').read_text())['formal_effects_available']
 formal=''
 if (OUT/'formal-results.json').exists():
  spec=json.loads((SPEC/'formal-v1.json').read_text());results=json.loads((OUT/'formal-results.json').read_text())
  assert spec['status']=='complete' and spec['completion']['completed_calls']==spec['max_calls']
  assert results['status']=='complete_formal_cross_study'
  assert results['jobs_sha256']==spec['jobs_sha256']
  assert results['execution']['states']=={'complete':spec['max_calls']},results['execution']['states']
  assert set(results['studies'])==set(spec['studies'])
  for study,entry in results['studies'].items():
   assert entry['results']['arms']['original']['brier'] is not None
   assert entry['results']['arms']['optimized']['brier'] is not None
   assert entry['results']['contrasts']['original__to__optimized']['improvement_95_ci'][0] is not None
  summary=json.loads((OUT/'formal-report.summary.json').read_text())
  assert set(summary['rows'])==set(spec['studies'])
  formal=f" Formal: {spec['max_calls']} calls, {len(results['studies'])} studies, "
  formal+=f"{len(summary['supporting'])} studies pass both gates, cross-study gate {summary['cross_study_gate']}."
 clean=''
 if (OUT/'clean-v1-results.json').exists():
  cs=json.loads((SPEC/'clean-v1.json').read_text());cr=json.loads((OUT/'clean-v1-results.json').read_text())
  assert cs['status']=='complete' and cs['total_calls']==cs['max_calls']
  assert cr['status']=='complete_formal_cross_study'
  assert cr['jobs_sha256']==cs['jobs_sha256']
  assert cr['execution']['states']=={'complete':cs['max_calls']},cr['execution']['states']
  assert set(cr['studies'])==set(cs['studies'])=={'drone','shoes'}
  assert cr['arms']==cs['arms']==['original','optimized']
  for study,entry in cr['studies'].items():
   assert entry['results']['arms']['original']['brier'] is not None
   assert entry['results']['arms']['optimized']['brier'] is not None
   # The two-arm plan must never report an ablation it did not run.
   assert 'output_only' not in entry['results']['arms'] and 'prompt_only' not in entry['results']['arms']
   statistical=entry['results']['contrasts']
   assert 'history__to__optimized' in statistical or 'attribute_rating__to__optimized' in statistical
  clean=json.loads((OUT/'clean-v1-report.summary.json').read_text())
  assert set(clean['rows'])=={'drone','shoes'}
  assert clean['beats_statistics']==[]
  clean=(f" Clean-v1: {cs['max_calls']} calls, {len(cr['studies'])} studies, "
         f"{len(clean['rows'])} behind the statistical reference.")

 wide=''
 if (OUT/'wide-v1-results.json').exists():
  ws=json.loads((SPEC/'wide-v1.json').read_text());wr=json.loads((OUT/'wide-v1-results.json').read_text())
  assert ws['status']=='complete'
  assert wr['jobs_sha256']==ws['jobs_sha256']
  assert set(wr['studies'])==set(ws['studies'])
  assert wr['arms']==ws['arms']==['original','optimized']
  full=sum(1 for _ in json.loads((PRIVATE/'wide-v1-jobs.json').read_text())['jobs'])
  assert wr['execution']['states']['complete']+wr['execution']['states'].get('failed',0)>=full-4
  wide=(f" Wide-v1: {ws['total_calls']} frozen calls, {len(wr['studies'])} studies, "
        f"{wr['execution']['states']['complete']} complete.")
 anchor=''
 if (OUT/'anchor-v1-results.json').exists():
  ans=json.loads((SPEC/'anchor-v1.json').read_text());anr=json.loads((OUT/'anchor-v1-results.json').read_text())
  assert ans['status']=='complete' and ans['total_calls']==ans['max_calls']
  assert anr['jobs_sha256']==ans['jobs_sha256']
  assert anr['arms']==ans['arms']==['optimized','anchored','bounded']
  assert set(anr['studies'])==set(ans['studies'])=={'german','pew111'}
  for study,entry in anr['studies'].items():
   arms=entry['results']['arms']
   # This plan never runs the native arm, so it must not report one.
   assert 'original' not in arms
   for name in ('optimized','anchored','bounded'):
    assert arms[name]['brier'] is not None
   contrasts=entry['results']['contrasts']
   for key in ('optimized__to__anchored','optimized__to__bounded','anchored__to__bounded'):
    assert contrasts[key]['relative_improvement'] is not None, key
  # Reused calls must reproduce the source numbers exactly: same bytes, same answers.
  wide_results=json.loads((OUT/'wide-v1-results.json').read_text())
  for study in ('german','pew111'):
   source=wide_results['studies'][study]['results']['arms']['optimized']['brier']
   reused=anr['studies'][study]['results']['arms']['optimized']['brier']
   assert abs(source-reused)<1e-12,(study,source,reused)
  adherence=json.loads((OUT/'anchor-v1-adherence.json').read_text())
  for study,block in adherence['studies'].items():
   # If the model had ignored the anchor, the two distant arms would tie; they do not.
   assert block['anchored']['median_tv_to_reference']<block['optimized']['median_tv_to_reference']*0.5,study
   assert block['bounded']['median_tv_to_reference']<=block['anchored']['median_tv_to_reference'],study
   assert block['bounded']['share_cells_beyond_bound']<0.15,study
  anchor=(f" Anchor-v1: {ans['max_calls']} frozen calls, {ans['reuse']['jobs_adopted']} reused, "
          f"{anr['execution']['states']['complete']} answered, arms {anr['arms']}.")
 direction=''
 if (OUT/'direction-metrics.json').exists():
  dm=json.loads((OUT/'direction-metrics.json').read_text())
  totals=dm['totals']
  assert totals['cards']==sum(s['cards'] for b in dm['plans'].values() for s in b['studies'].values())
  assert totals['studies']==sum(len(b['studies']) for b in dm['plans'].values())
  assert 0<=totals['ai_argmax']<=1 and 0<=totals['reference_argmax']<=1
  for payload in dm['plans'].values():
   for block in payload['studies'].values():
    assert 0<=block['ai_argmax']<=1 and block['cards']>=1
   deviation=payload['deviation']
   if deviation.get('available'):
    assert len(deviation['quintiles'])==5
    for quintile in deviation['quintiles']:
     low,high=quintile['ai_advantage_ci']
     assert low<=quintile['ai_advantage']<=high
  direction=f" Direction: {totals['studies']} studies, {totals['cards']} cards, AI argmax {100*totals['ai_argmax']:.1f}%."
 pilot=''
 for model in ('qwen','pro'):
  path=OUT/f'blend-{model}.json'
  if not path.exists(): continue
  data=json.loads(path.read_text())
  assert data['k0']==20.0
  positives=0
  for study,block in data['studies'].items():
   row=block['blend']['20']
   if row.get('model_gain_pp') is None: continue
   positives += row['model_gain_pp']>0
   # Card-specific information must beat the shuffled-card prior, or the claim fails.
   ab=block['shuffle_ablation']['20']
   assert ab['model']<=ab['shuffled']+1e-9,(model,study)
  assert positives>=6,(model,positives)
  pilot += f' {model}: {positives}/{len(data["studies"])} studies gain from the model.'

 print('PASS: 19 source inventories; accepted report unchanged; native hashes; disjoint cohorts; 24 strict responses; four-arm parity; report links.'+formal+clean+wide+anchor+direction+pilot)
if __name__=='__main__':main()
