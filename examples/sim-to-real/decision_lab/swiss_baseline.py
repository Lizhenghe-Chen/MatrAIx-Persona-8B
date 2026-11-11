"""Swiss displayed-attribute statistical reference; no test evaluation."""
import argparse,json,os,re
from pathlib import Path
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from .core import split,digest
from .baselines import select_penalty


def attributes(text):
    fields={k.strip():v.strip() for k,v in (part.split(':',1) for part in text.split(';')[1:])}
    return [float(fields['Price'].replace('CHF ','')),float(fields['Functional life'].replace(' years','')),
            {'Very low':0,'Medium':1,'Very high':2}[fields['Env. production impact']],
            {'A':0,'C':1,'E':2,'G':3}[fields['Energy efficiency']],
            {'Not recyclable':0,'Limited recyclable':1,'Recyclable':2}[fields['Recyclability']],
            {'Not repairable at all':0,'Repairable to a limited degree':1,'Repairable':2}[fields['Repairability']]]


def tasks(rows,fields,vectorizer,fit=False):
    backgrounds=[{'product_type':r['stratum'],**{k:r['background'][k] for k in fields}} for r in rows]
    z=vectorizer.fit_transform(backgrounds) if fit else vectorizer.transform(backgrounds)
    result=[]
    for row,bg in zip(rows,z):
        x=np.array([attributes(t) for t in row['options']])
        x=np.concatenate([x,np.einsum('ij,k->ijk',x,bg).reshape(len(x),-1)],axis=1)
        result.append({'person':row['person'],'features':x,'answer':row['answer'],'weight':1})
    return result


def develop(source):
    doc=json.loads(Path(source).read_text());assignment=split(doc['rows'])
    train=[r for r in doc['rows'] if assignment[r['person']]=='train'];dev=[r for r in doc['rows'] if assignment[r['person']]=='development']
    result={'source_sha256':digest(doc),'status':'development_only','test_scored':False,'baselines':{},
            'assumption':'Ordered environmental attributes use monotonic numeric coding; this is a simple statistical comparator, not all possible statistical models.'}
    for arm,fields in [('none',[]),('basic',['age_years','education']),('rich',['age_years','education','household_monthly_income','political_self_placement'])]:
        vectorizer=DictVectorizer(sparse=False)
        a=tasks(train,fields,vectorizer,True);b=tasks(dev,fields,vectorizer)
        model,selection=select_penalty(a,b)
        result['baselines'][arm]={**selection,'background_fields':fields,'beta':model.beta.tolist(),'scale':model.scale.tolist(),'background_feature_names':vectorizer.get_feature_names_out().tolist()}
        print(json.dumps({'condition':arm,**selection}),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=develop(a.source)
    fd=os.open(a.output,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:json.dump(result,f,indent=2)
