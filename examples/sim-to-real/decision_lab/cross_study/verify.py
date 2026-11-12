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
 for version in ('v12','v11','v10','v9','v8','v7','v6','v5','v3','v2','v1'):
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
 print('PASS: 19 source inventories; accepted report unchanged; native hashes; disjoint cohorts; 24 strict responses; four-arm parity; report links.'+formal+clean)
if __name__=='__main__':main()
