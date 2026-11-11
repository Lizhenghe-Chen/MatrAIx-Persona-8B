"""Format-only population pilot on generated IDs outside formal cohorts."""
import json,copy,argparse,os
from pathlib import Path
from .core import digest
from .runner import run
from .dryer_pilot import private_write
from .synthetic_prepare import TRAITS

def execute(root,credentials):
    root=Path(root);formal=root/'synthetic-formal-v1';out=root/'synthetic-pilot-v1'
    out.mkdir(exist_ok=True);os.chmod(out,0o700)
    os.environ['DEEPSEEK_API_KEY']=json.loads(Path(credentials).read_text())['DEEPSEEK_API_KEY']
    read=lambda p:json.loads(p.read_text())
    source=read(formal/'personality-study.json');used={r['person'] for r in source['rows']}
    pool=read(root.parent/'synthetic-pool-v1.json')
    spare=[p for p in pool['records'] if p['synthetic_id'] not in used]
    templates={r['stratum']:r for r in source['rows']};pilot=[]
    for stratum,template in sorted(templates.items()):
        for _ in range(2):
            donor=spare.pop();row=copy.deepcopy(template);row['person']='pilot-'+donor['synthetic_id'];row['task']='format-check'
            f=donor['generated_fields'];row['background']={'age_bracket':f['age_bracket'],'education_group':'bachelor_or_higher' if f['highest_education'] in ["Bachelor's","Master's",'Doctorate','Postdoc'] else 'below_bachelor',**{k:f[k] for k in TRAITS}}
            pilot.append(row)
    if len(pilot)>24:raise ValueError('Pilot exceeds person cap')
    results={}
    for name in ['demographics','personality','shuffled']:
        study={**source,'rows':pilot};config=read(formal/(name+'-config.json'));config.update(max_calls=len(pilot),max_cost_usd=1)
        seal={'input_sha256':digest(study),'config_sha256':digest(config),'assignments':{r['person']:'test' for r in pilot}}
        for suffix,obj in [('study',study),('config',config),('seal',seal)]:
            p=out/(name+'-'+suffix+'.json')
            if p.exists():
                if read(p)!=obj:raise ValueError('Pilot changed')
            else:private_write(p,obj)
        results[name]=run(study,seal,config,out/(name+'.sqlite'),'test')
    summary={'status':'passed' if all(r['complete'] for r in results.values()) else 'incomplete','people':len(pilot),'conditions':results,'formal_people_overlap':0,'human_scores_computed':False,'formal_manifest_sha256':digest(read(formal/'manifest.json'))}
    private_write(out/'result.json',summary);return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--credentials',required=True);a=p.parse_args();print(json.dumps(execute(a.root,a.credentials)))
