"""Measure probability drift after mapping rotated choices back to original products."""
import json,argparse
from pathlib import Path
from .core import digest,tv
from .checkpoint import read_predictions
from .conditions import restore_probabilities

def score(root):
    root=Path(root)/'stability-v1';read=lambda p:json.loads(p.read_text())
    values={};rows=None
    for name in ['original','repeat','rotated']:
        study=read(root/(name+'-study.json'));seal=read(root/(name+'-seal.json'));cfg=read(root/(name+'-config.json'))
        current,p,_=read_predictions(study,seal,cfg,root/(name+'.sqlite'),'development')
        values[name]=p
        if name=='original':rows=current
    orders=read(root/'orders.json');rotated={k:restore_probabilities(p,orders[digest(list(k))]) for k,p in values['rotated'].items()}
    if any(set(p)!=set(values['original']) for p in values.values()):raise ValueError('Diagnostic cohorts differ')
    output={}
    for name,p in [('repeat',values['repeat']),('rotated_restored',rotated)]:
        differences=[100*tv(values['original'][k],p[k]) for k in p]
        output[name]={'mean_tv_drift_pp':sum(differences)/len(differences),'maximum_tv_drift_pp':max(differences),
                      'argmax_changed_tasks':sum(max(range(len(p[k])),key=p[k].__getitem__)!=max(range(len(p[k])),key=values['original'][k].__getitem__) for k in p)}
    return {'people':len(rows),'diagnostics':output,'target_answers_used_for_metric':False,
            'limits':'24 development people; one repeat and one rotation. Difference beyond repeat drift is suggestive, not a precise isolated causal position effect.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--output',type=Path,required=True);a=p.parse_args();result=score(a.root)
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))
