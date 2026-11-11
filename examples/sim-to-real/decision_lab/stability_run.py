"""Development-only repeated-call and option-order diagnostics, max 24 people."""
import argparse,json,os,copy,random
from pathlib import Path
from .core import digest
from .conditions import permute_options
from .runner import run
from .dryer_pilot import private_write

def execute(root,credentials):
    root=Path(root);formal=root/'formal-v1';out=root/'stability-v1'
    read=lambda p:json.loads(p.read_text())
    source=read(formal/'rich_development-study.json');frozen=read(formal/'rich_development-seal.json')
    people={}
    for r in source['rows']:
        if frozen['assignments'][r['person']]=='development':people.setdefault(r['person'],r)
    strata={}
    for p,r in people.items():strata.setdefault(r['stratum'],[]).append(p)
    rng=random.Random(20261109)
    for group in strata.values():group.sort();rng.shuffle(group)
    chosen=[]
    while len(chosen)<24 and any(strata.values()):
        for s in sorted(strata):
            if strata[s] and len(chosen)<24:chosen.append(strata[s].pop())
    original=[people[p] for p in chosen];orders={}
    rotated=[]
    for r in original:
        order=list(range(1,len(r['options'])))+[0];orders[digest([r['person'],r['task']])]=order
        rotated.append(permute_options(r,order))
    out.mkdir(exist_ok=True);os.chmod(out,0o700)
    if not (out/'orders.json').exists():private_write(out/'orders.json',orders)
    os.environ['DEEPSEEK_API_KEY']=read(Path(credentials))['DEEPSEEK_API_KEY']
    results={}
    for name,rows in [('original',original),('repeat',original),('rotated',rotated)]:
        study={**source,'rows':rows};config=read(formal/'rich_development-config.json');config.update(max_calls=len(rows),max_cost_usd=1)
        seal={'input_sha256':digest(study),'config_sha256':digest(config),'assignments':{p:'development' for p in chosen}}
        for suffix,obj in [('study',study),('config',config),('seal',seal)]:
            path=out/(name+'-'+suffix+'.json')
            if path.exists():
                if read(path)!=obj:raise ValueError('Diagnostic input changed')
            else:private_write(path,obj)
        results[name]=run(study,seal,config,out/(name+'.sqlite'),'development')
    summary={'people':len(chosen),'conditions':results,'phase':'development','interpretation':'Diagnostic only; does not change frozen main tests. One cyclic permutation is not a full balanced-order optimization.'}
    private_write(out/'result.json',summary);return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--credentials',required=True);a=p.parse_args();print(json.dumps(execute(a.root,a.credentials)))
