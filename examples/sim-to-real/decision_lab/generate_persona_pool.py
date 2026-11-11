"""Local synthetic proposal pool, deliberately separate from real respondents."""
import argparse,json,os,hashlib
from pathlib import Path
from persona.synthesis.sampler import PersonaForwardSampler,SamplingConfig,DEFAULT_GRAPH_PATH

FIELDS=['region','age_bracket','highest_education','decision_style','risk_tolerance','values_priority','bfi2_domain_conscientiousness']

def generate(out,n=20000,seed=20261109):
    out=Path(out)
    if out.exists():raise ValueError('Do not overwrite a generated pool')
    sampler=PersonaForwardSampler(DEFAULT_GRAPH_PATH,SamplingConfig(seed=seed))
    records=[]
    for region in ['North America','Western Europe']:
        codes=sampler.sample_indices(n,fixed={'region':region})
        for i in range(n):
            fields={f:sampler.values[f][int(codes[f][i])] for f in FIELDS}
            if fields['age_bracket'] in ['Under 5','5-12','13-17']:continue
            records.append({'synthetic_id':f'{region}-{i:06d}','generated_fields':fields})
    doc={'status':'proposal_pool_not_evaluation_cohort','seed':seed,'proposals_per_region':n,
         'graph_sha256':hashlib.sha256(DEFAULT_GRAPH_PATH.read_bytes()).hexdigest(),
         'sampler_sha256':hashlib.sha256(Path(__import__('persona.synthesis.sampler.sampler',fromlist=['x']).__file__).read_bytes()).hexdigest(),
         'generation':'Pinned region, forward generation, adults retained. No respondent answers used.',
         'limits':'Synthetic attributes, not measured facts. Not population representative until explicitly matched; no country inferred.',
         'records':records}
    out.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(doc,f,ensure_ascii=False)
    return len(records)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--n',type=int,default=20000);a=p.parse_args()
    print(json.dumps({'adult_records':generate(a.output,a.n)}))
