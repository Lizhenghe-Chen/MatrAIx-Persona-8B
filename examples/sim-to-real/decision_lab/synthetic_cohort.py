"""Match aggregate background counts; never attach synthetic people to real IDs."""
import json,random,collections,hashlib,os
from pathlib import Path
from .core import split,digest
from .persona_mapping import common_background


def construct(root,kind,pool_path,seed=20261109):
    prepared=json.loads((Path(root)/'prepared.json').read_text());pool_path=Path(pool_path)
    pool=json.loads(pool_path.read_text());assignment=split(prepared['rows'])
    people={r['person']:r for r in prepared['rows'] if assignment[r['person']]=='test'}
    targets=collections.Counter();excluded=0
    for r in people.values():
        bg=common_background(r['background'],kind)
        if bg is None:excluded+=1;continue
        region='Western Europe' if kind=='swiss' or r['stratum'].split('_')[0] in ['IRE','UK'] else 'North America'
        targets[(r['stratum'],region,bg['age_bracket'],bg['education_group'])]+=1
    candidates=collections.defaultdict(list)
    for r in pool['records']:
        f=r['generated_fields'];education='bachelor_or_higher' if f['highest_education'] in ["Bachelor's","Master's",'Doctorate','Postdoc'] else 'below_bachelor'
        candidates[(f['region'],f['age_bracket'],education)].append(r)
    demand=collections.Counter()
    for (_,region,age,education),n in targets.items():demand[(region,age,education)]+=n
    gaps=[{'cell':list(cell),'needed':n,'available':len(candidates[cell])} for cell,n in demand.items() if len(candidates[cell])<n]
    if gaps:return {'status':'coverage_gap','gaps':gaps}
    rng=random.Random(seed)
    for cell in sorted(candidates):rng.shuffle(candidates[cell])
    records=[]
    for (stratum,region,age,education),n in sorted(targets.items()):
        for _ in range(n):
            donor=candidates[(region,age,education)].pop()
            records.append({'synthetic_id':donor['synthetic_id'],'stratum':stratum,
                            'background':{'age_bracket':age,'education_group':education},
                            'generated_personality':{k:donor['generated_fields'][k] for k in ['decision_style','risk_tolerance','values_priority','bfi2_domain_conscientiousness']}})
    return {'status':'matched_background_cohort_not_execution_ready','seed':seed,'kind':kind,
            'source_sha256':digest(prepared),'pool_sha256':hashlib.sha256(pool_path.read_bytes()).hexdigest(),
            'eligible_test_people':len(people),'excluded_unknown_background_people':excluded,
            'matching':'Exact aggregate counts by design stratum, age band, coarse education; no person linkage.',
            'limits':'No fine education inferred. Synthetic personality is unmeasured. Same regional pool across studies is not independent population evidence.',
            'records':records}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--kind',choices=['dryer','swiss'],required=True);p.add_argument('--pool',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=construct(a.root,a.kind,a.pool)
    fd=os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))
