"""Development-only choice baselines using the same displayed information as AI."""
import argparse
import json
import os
import re
from pathlib import Path
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from .baselines import select_penalty
from .core import split, digest


def attributes(text):
    if text=='Neither':return [1.,0.,0.,0.,0.,0.]
    def number(pattern):
        found=re.search(pattern,text)
        if not found:raise ValueError('Unrecognized displayed attribute')
        return float(found[1])
    price=number(r'Price: [A-Z]+ (\d+)')
    capacity=number(r'Capacity: (\d+)')
    stars=number(r'Customer rating: (\d+)')
    established=float('Brand: Established;' in text)
    if 'Energy Star:' in text:energy=float('Energy Star: Yes' in text)
    elif 'Energy rating:' in text:
        rating=re.search(r'Energy rating: ([^;]+)',text)[1]
        energy={'C':1,'B':2,'A':3,'A+':4,'A++':5,'A+++':6}[rating]
    else:energy=number(r'Energy Cost: [A-Z]+ (\d+)')
    return [0.,price,capacity,stars,established,energy]


def inputs(rows,fields):
    return [{**{'country_treatment':r['stratum']},
             **{f:r['background'].get(f,'unknown') for f in fields}} for r in rows]


def tasks(rows,fields,vectorizer,fit=False):
    bg=inputs(rows,fields)
    z=vectorizer.fit_transform(bg) if fit else vectorizer.transform(bg)
    result=[]
    for row,background in zip(rows,z):
        x=np.asarray([attributes(t) for t in row['options']])
        # Country and information-group interactions separate units and energy scales.
        features=np.concatenate([x,np.einsum('ij,k->ijk',x,background).reshape(len(x),-1)],axis=1)
        result.append({'person':row['person'],'answer':row['answer'],'features':features,'weight':row.get('weight',1)})
    return result


def develop(source):
    study=json.loads(Path(source).read_text());assignment=split(study['rows'])
    train=[r for r in study['rows'] if assignment[r['person']]=='train']
    dev=[r for r in study['rows'] if assignment[r['person']]=='development']
    output={'status':'development_only','source_sha256':digest(study),
            'people':{'train':len({r['person'] for r in train}),'development':len({r['person'] for r in dev})},
            'test_scored':False,'baselines':{},
            'feature_policy':'Only displayed product attributes, context country-treatment and whitelisted background. No position features. Energy scale is ordinal for EU labels, binary for EnergyStar, currency for costs.'}
    for arm,fields in [('none',[]),('basic',['age_band','education']),('rich',['age_band','education','weekly_dryer_use','household_size'])]:
        vectorizer=DictVectorizer(sparse=False)
        training=tasks(train,fields,vectorizer,True);development=tasks(dev,fields,vectorizer)
        model,selection=select_penalty(training,development)
        output['baselines'][arm]={**selection,'feature_count':len(model.beta),'background_fields':fields,
                                  'beta':model.beta.tolist(),'scale':model.scale.tolist(),
                                  'background_feature_names':vectorizer.get_feature_names_out().tolist()}
        print(json.dumps({'condition':arm,'development_brier':selection['development_brier']}),flush=True)
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=develop(a.source)
    fd=os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(result,f,ensure_ascii=False,indent=2)
