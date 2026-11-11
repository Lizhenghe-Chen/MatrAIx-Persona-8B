"""Freeze and execute an auditable, non-scoring technical pilot."""
import argparse
import json
import os
import random
from collections import defaultdict
from pathlib import Path
from .core import digest, request_payload, split
from .runner import run, GATES


def private_write(path, value):
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:json.dump(value,f,ensure_ascii=False,indent=2)


def prepare(source, output):
    here=Path(__file__).parent
    protocol=json.loads((here/'specs/pilots/dryer-pilot-protocol.json').read_text())
    study=json.loads(Path(source).read_text()); assignments=split(study['rows'])
    people=defaultdict(dict)
    for row in study['rows']:
        if assignments[row['person']]=='train':
            people[row['stratum']].setdefault(row['person'],[]).append(row)
    rng=random.Random(protocol['seed']); selected=[]
    for stratum, members in sorted(people.items()):
        ids=sorted(members);rng.shuffle(ids)
        for person in ids[:3]:selected.append(rng.choice(sorted(members[person],key=lambda r:r['task'])))
    if len({r['person'] for r in selected})!=21:raise ValueError('Unexpected pilot coverage')
    study={**study,'rows':selected,'status':'technical_pilot_admitted',
           'audit':{k:True for k in GATES},'audit_evidence':protocol['admission_evidence'],
           'protocol_sha256':digest(protocol)}
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    os.chmod(output,0o700)
    private_write(output/'study.json',study)
    config=json.loads((here/'specs/formal/deepseek-pro.json').read_text())
    config.update(status='frozen',expected_identity=json.loads((here/'specs/formal/endpoint-pilot.json').read_text())['identity'],
                  max_calls=21,max_cost_usd=1.,input_usd_per_million=1.32,output_usd_per_million=3.96)
    payload_hashes={}
    for arm,fields in protocol['background_conditions'].items():
        cfg={**config,'background_fields':fields}
        for row in selected:
            payload=request_payload(row,cfg)
            assert set(payload)=={'question','options','context','background'}
            assert set(payload['background'])==set(fields)
            assert row['person'] not in json.dumps(payload)
        seal={'config_sha256':digest(cfg),'input_sha256':digest(study),
              'assignments':{r['person']:'train' for r in selected},'seed':protocol['seed']}
        private_write(output/(arm+'-config.json'),cfg);private_write(output/(arm+'-seal.json'),seal)
        payload_hashes[arm]=digest([request_payload(r,cfg) for r in selected])
    return {'people':21,'tasks_per_condition':21,'conditions':list(protocol['background_conditions']),
            'test_people_exposed':0,'input_sha256':digest(study),'payload_hashes':payload_hashes,'scoring':'disabled'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run']);p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--source',type=Path);p.add_argument('--credentials',type=Path);a=p.parse_args()
    if a.command=='prepare':print(json.dumps(prepare(a.source,a.directory)))
    else:
        os.environ['DEEPSEEK_API_KEY']=json.loads(a.credentials.read_text())['DEEPSEEK_API_KEY']
        study=json.loads((a.directory/'study.json').read_text())
        for arm in ['none','basic','rich']:
            cfg=json.loads((a.directory/(arm+'-config.json')).read_text())
            seal=json.loads((a.directory/(arm+'-seal.json')).read_text())
            result=run(study,seal,cfg,a.directory/(arm+'.sqlite'),'train')
            print(json.dumps({'condition':arm,**result}),flush=True)
