"""Read-only audit of US T-shirt three-product choice data."""
import argparse,json,hashlib
from pathlib import Path
import pandas as pd

def audit(directory):
    directory=Path(directory);source=directory/'CFTF_usa.dta'
    d=pd.read_stata(source,convert_categoricals=False)
    b=pd.read_stata(directory/'CTFTF_usa_w1_demos.dta',convert_categoricals=False)
    cards=d.groupby(['respid','taskid']);people=d.drop_duplicates('respid');errors=[]
    if d.duplicated(['respid','taskid','prof']).any():errors.append('duplicate alternative')
    if not cards.size().eq(3).all():errors.append('not three products')
    if not cards.tschoice.sum().eq(1).all():errors.append('not one selected product')
    if not d.tschoice.isin([0,1]).all():errors.append('unknown choice code')
    if b.workerid.duplicated().any():errors.append('duplicate wave-one join key')
    joined=people.merge(b,on='workerid',how='left',indicator=True,suffixes=('','_w1'),validate='many_to_one')
    mismatch={}
    for field in ['age','female','income_','PARTYID']:
        a=joined[field];v=joined[field+'_w1']
        mismatch[field]=int((~(a.eq(v)|(a.isna()&v.isna()))).sum())
    return {'status':'structural_audit_only_not_admitted','source':'https://doi.org/10.7910/DVN/PEZ7EE',
            'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'rows':len(d),
            'people':int(d.respid.nunique()),'tasks':len(cards),'alternatives_per_task':3,
            'refusal_option':False,'wave1_matched_people':int(joined['_merge'].eq('both').sum()),
            'wave1_background_mismatches':mismatch,'errors':errors,
            'pending':['Original English instructions and attribute definitions','Author final sample filters and descriptive statistics','Income coding: published labels omit a bracket; do not infer missing ranges','Background wave provenance and whitelist'],
            'privacy':'worker IDs, postal codes, platform assignment identifiers and timestamps excluded from future request whitelist.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.directory);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result))
