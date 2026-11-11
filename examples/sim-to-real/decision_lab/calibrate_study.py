"""Freeze calibration from complete development calls; never score test answers."""
import argparse,json,os
from pathlib import Path
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from .core import digest,split
from .checkpoint import read_predictions
from .baselines import ConditionalLogit
from .calibration import select


def calibrate(directory,kind):
    directory=Path(directory);prepared=json.loads((directory/'prepared.json').read_text())
    saved=json.loads((directory/'baseline-development.json').read_text())
    if saved['source_sha256']!=digest(prepared):raise ValueError('Baseline source mismatch')
    if kind=='dryer':from .dryer_baseline import tasks
    elif kind=='swiss':from .swiss_baseline import tasks
    else:raise ValueError('Unknown reviewed adapter')
    formal=directory/'formal-v1';name='rich_development'
    study=json.loads((formal/(name+'-study.json')).read_text())
    config=json.loads((formal/(name+'-config.json')).read_text())
    seal=json.loads((formal/(name+'-seal.json')).read_text())
    rows,llm,missing=read_predictions(study,seal,config,formal/(name+'.sqlite'),'development')
    assignment=split(prepared['rows']);train=[r for r in prepared['rows'] if assignment[r['person']]=='train']
    params=saved['baselines']['rich'];vectorizer=DictVectorizer(sparse=False)
    tasks(train,params['background_fields'],vectorizer,True)
    if vectorizer.get_feature_names_out().tolist()!=params['background_feature_names']:raise ValueError('Feature vocabulary changed')
    model=ConditionalLogit(params['penalty']);model.beta=np.asarray(params['beta']);model.scale=np.asarray(params['scale'])
    predicted=model.predict(tasks(rows,params['background_fields'],vectorizer))
    baseline={(r['person'],r['task']):p for r,p in zip(rows,predicted)}
    protocol=json.loads((formal/'protocol.json').read_text())
    selection=select([{**r,'split':'development'} for r in rows],llm,baseline,
                     forbidden_people=[p for p,s in assignment.items() if s=='test'],
                     temperatures=protocol['calibrated']['temperature_grid'],
                     mixture_weights=protocol['calibrated']['llm_weight_grid'])
    return {'selection':selection,'baseline_sha256':digest(saved),'protocol_sha256':digest(protocol),
            'development_input_sha256':seal['input_sha256'],'development_predictions_sha256':digest(predicted),
            'llm_predictions_sha256':digest([llm[(r['person'],r['task'])] for r in rows]),
            'test_scored':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--kind',choices=['dryer','swiss'],required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=calibrate(a.directory,a.kind)
    fd=os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(result,f,indent=2)
    print(json.dumps({'selection':result['selection'],'test_scored':False}))
