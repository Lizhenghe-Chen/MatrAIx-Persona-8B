"""Dataset-independent, protocol-driven technical pilots with private checkpoints."""
import argparse,json,os,random
from collections import defaultdict
from pathlib import Path
from ..core.core import digest,request_payload,split,validate
from ..studies.dryer_pilot import private_write
from ..core.runner import run,GATES


def prepare(source,protocol_path,config_path,identity_path,directory):
    study=json.loads(Path(source).read_text());validate(study['rows'])
    protocol=json.loads(Path(protocol_path).read_text())
    if not all(protocol.get('admission_evidence',{}).get(k) for k in GATES):raise ValueError('Missing admission evidence')
    assignments=split(study['rows'],protocol['seed']);strata=defaultdict(dict)
    for row in study['rows']:
        if assignments[row['person']]=='train':strata[row['stratum']].setdefault(row['person'],[]).append(row)
    rng=random.Random(protocol['seed']);selected=[]
    for stratum,members in sorted(strata.items()):
        ids=sorted(members);rng.shuffle(ids)
        for person in ids[:protocol['people_per_stratum']]:selected.append(rng.choice(sorted(members[person],key=lambda r:r['task'])))
    if len(selected)!=protocol['expected_people'] or len(selected)>24:raise ValueError('Pilot coverage differs from protocol')
    doc={**study,'rows':selected,'audit':dict.fromkeys(GATES,True),
         'audit_evidence':protocol['admission_evidence'],'protocol_sha256':digest(protocol)}
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False);os.chmod(directory,0o700)
    private_write(directory/'study.json',doc);private_write(directory/'protocol.json',protocol)
    base=json.loads(Path(config_path).read_text());identity=json.loads(Path(identity_path).read_text())['identity']
    manifest={'input_sha256':digest(doc),'people':len(selected),'test_people_exposed':0,'conditions':[]}
    for name,condition in protocol['conditions'].items():
        config={**base,**condition,'status':'frozen','expected_identity':identity,'max_calls':len(selected),
                'max_cost_usd':protocol['max_cost_usd_per_condition'],'input_usd_per_million':1.32,'output_usd_per_million':3.96}
        payloads=[request_payload(r,config) for r in selected]
        if any(set(p)!={'question','options','context','background'} for p in payloads):raise ValueError('Unexpected payload fields')
        seal={'input_sha256':digest(doc),'config_sha256':digest(config),'assignments':{r['person']:'train' for r in selected},'seed':protocol['seed']}
        private_write(directory/(name+'-config.json'),config);private_write(directory/(name+'-seal.json'),seal)
        manifest['conditions'].append({'name':name,'config_sha256':digest(config),'payload_sha256':digest(payloads)})
    private_write(directory/'manifest.json',manifest)
    return manifest


def execute(directory,credentials):
    directory=Path(directory);manifest=json.loads((directory/'manifest.json').read_text())
    os.environ['DEEPSEEK_API_KEY']=json.loads(Path(credentials).read_text())['DEEPSEEK_API_KEY']
    study=json.loads((directory/'study.json').read_text())
    if digest(study)!=manifest['input_sha256']:raise ValueError('Study changed')
    for condition in manifest['conditions']:
        name=condition['name'];config=json.loads((directory/(name+'-config.json')).read_text())
        if digest(config)!=condition['config_sha256']:raise ValueError('Config changed')
        seal=json.loads((directory/(name+'-seal.json')).read_text())
        result=run(study,seal,config,directory/(name+'.sqlite'),'train')
        print(json.dumps({'condition':name,**result}),flush=True)
        if not result['complete']:raise RuntimeError('Incomplete pilot condition')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run']);p.add_argument('--directory',type=Path,required=True)
    for name in ['source','protocol','config','identity','credentials']:p.add_argument('--'+name,type=Path)
    a=p.parse_args()
    if a.command=='prepare':print(json.dumps(prepare(a.source,a.protocol,a.config,a.identity,a.directory)))
    else:execute(a.directory,a.credentials)
