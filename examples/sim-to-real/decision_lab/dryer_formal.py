"""Immutable six-unit execution plan; private respondent artifacts only."""
import argparse
import copy
import json
import os
from pathlib import Path
from .conditions import shuffled_background
from .core import digest,split,request_payload
from .dryer_pilot import private_write
from .runner import run,GATES

UNITS=[('rich_development','rich','development'),('none_test','none','test'),
       ('basic_test','basic','test'),('rich_test','rich','test'),
       ('shuffled_test','rich','test'),('single_test','rich','test')]


def prepare(source,directory):
    here=Path(__file__).parent;directory=Path(directory)
    protocol=json.loads((here/'dryer-formal-protocol.json').read_text())
    pilot=json.loads((here/'dryer-pilot-protocol.json').read_text())
    doc=json.loads(Path(source).read_text());assignments=split(doc['rows'])
    counts={phase:list(assignments.values()).count(phase) for phase in ['train','development','test']}
    if counts!={'train':868,'development':292,'test':292}:raise ValueError('Unexpected split')
    doc.update(status='formal_frozen',audit=dict.fromkeys(GATES,True),
               audit_evidence=pilot['admission_evidence'],protocol_sha256=digest(protocol))
    shuffled,diagnostic=shuffled_background(doc['rows'],['age_band','education'],['weekly_dryer_use','household_size'],assignments)
    directory.mkdir(parents=True,exist_ok=False);os.chmod(directory,0o700)
    private_write(directory/'protocol.json',protocol)
    private_write(directory/'shuffle-map.json',diagnostic)
    base=json.loads((here/'deepseek-pro.json').read_text())
    base.update(status='frozen',expected_identity=json.loads((here/'endpoint-pilot.json').read_text())['identity'],
                max_calls=2336,max_cost_usd=20.,input_usd_per_million=1.32,output_usd_per_million=3.96)
    manifest={'protocol_sha256':digest(protocol),'units':[]}
    for name,background,phase in UNITS:
        study=copy.deepcopy(doc)
        if name=='shuffled_test':study['rows']=shuffled
        config={**base,'background_fields':protocol['backgrounds'][background],
                'output_mode':'single_choice' if name=='single_test' else 'probabilities'}
        rows=[r for r in study['rows'] if assignments[r['person']]==phase]
        if len(rows)!=2336:raise ValueError('Unexpected unit size')
        for row in rows:
            payload=request_payload(row,config)
            if row['person'] in json.dumps(payload):raise ValueError('Respondent identifier leaked')
        seal={'config_sha256':digest(config),'input_sha256':digest(study),'assignments':assignments,'seed':20261109}
        private_write(directory/(name+'-study.json'),study)
        private_write(directory/(name+'-config.json'),config)
        private_write(directory/(name+'-seal.json'),seal)
        manifest['units'].append({'name':name,'phase':phase,'calls':len(rows),'study_sha256':digest(study),'config_sha256':digest(config),'seal_sha256':digest(seal)})
    private_write(directory/'manifest.json',manifest)
    return manifest


def execute(directory,credentials):
    directory=Path(directory);manifest=json.loads((directory/'manifest.json').read_text())
    os.environ['DEEPSEEK_API_KEY']=json.loads(Path(credentials).read_text())['DEEPSEEK_API_KEY']
    for unit in manifest['units']:
        name=unit['name']
        study=json.loads((directory/(name+'-study.json')).read_text())
        config=json.loads((directory/(name+'-config.json')).read_text())
        seal=json.loads((directory/(name+'-seal.json')).read_text())
        if any(digest(obj)!=unit[key] for obj,key in [(study,'study_sha256'),(config,'config_sha256'),(seal,'seal_sha256')]):
            raise ValueError('Manifest mismatch')
        result=run(study,seal,config,directory/(name+'.sqlite'),unit['phase'])
        print(json.dumps({'unit':name,**result}),flush=True)
        if not result['complete']:raise RuntimeError('Unit incomplete; stop before next unit')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run']);p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--source',type=Path);p.add_argument('--credentials',type=Path);a=p.parse_args()
    if a.command=='prepare':print(json.dumps(prepare(a.source,a.directory)))
    else:execute(a.directory,a.credentials)
