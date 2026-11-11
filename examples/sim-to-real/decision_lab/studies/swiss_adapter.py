"""Author-English text rendering of Swiss appliance choices, with measured backgrounds."""
import argparse,json,math,os
from pathlib import Path
import pandas as pd
from ..core.core import digest,split,validate
from .swiss_appliances import decode_composite,audit

EDUCATION=['None','Obligatory schooling','Apprenticeship/vocational school/commercial middle school',
'Matura/vocational school-leaving certificate','Higher technical/vocational training',
'University of Applied Sciences/University of Education','University/ETH','Other']
INCOME=['Under CHF 2000','CHF 2001–4000','CHF 4001–6000','CHF 6001–8000','CHF 8001–10000',
'CHF 10001–12000','CHF 12001–14000','CHF 14001–16000','CHF 16001–18000','Above CHF 18000']

def label(value,labels):
    if pd.isna(value) or value<0:return 'unknown'
    if value!=int(value) or not 1<=value<=len(labels):raise ValueError('Unknown category')
    return labels[int(value)-1]


def prepare(directory):
    directory=Path(directory);checks=audit(directory)
    if checks['errors']:raise ValueError(checks['errors'])
    df=pd.read_csv(directory/'w7_w8_subgroups.csv')
    rows=[]
    for (person,task),group in df.groupby(['PubId','round'],sort=True):
        group=group.sort_values('product');r=group.iloc[0];kind=r.product_type
        if list(group['product'])!=[1,2]:raise ValueError('Unknown product order')
        options=[]
        for _,product in group.iterrows():
            options.append(f'{kind} '+('A' if product['product']==1 else 'B')+'; '+
                           f'Price: CHF {decode_composite(product.Price,kind)}; '+
                           f'Functional life: {decode_composite(product["Functional duration"],kind)} years; '+
                           '; '.join(f'{field}: {product[field]}' for field in ['Env. production impact','Energy efficiency','Recyclability','Repairability']))
        background={'age_years':int(r.age),'education':label(r.Education,EDUCATION),
                    'household_monthly_income':label(r.w7_q40x1,INCOME)}
        ideology=r.w7_q26
        background['political_self_placement']=('unknown' if pd.isna(ideology) or ideology<0 else f'{int(ideology)} on a 1 (left) to 11 (right) scale')
        if background['political_self_placement']!='unknown' and not 1<=ideology<=11:raise ValueError('Invalid ideology')
        rows.append({'person':str(person),'task':str(task),'stratum':kind,'weight':1.,
                     'question':'Which of the two products would you choose?',
                     'context':f'Switzerland, November 2021–February 2022. Imagine that you want to buy a new {kind} today because your existing device is defective and can no longer be repaired. Do this thought experiment even if you do not currently own one. Choose which of the two you would rather buy if you had to choose. Functional life means years of good operation without major repairs. Environmental impact refers to production. Energy efficiency A means very low electricity consumption and G very high consumption. Household income, if supplied, is monthly income after social contributions but before tax.',
                     'options':options,'answer':int(group.choice.to_numpy().argmax()),'background':background,
                     'group':kind+'_'+digest(options)[:20]})
    validate(rows)
    return {'study':'swiss-appliances-author-english-v1','status':'prepared_pending_final_admission',
            'source_audit':checks,'rows':rows,
            'limitations':['Author-English rendering; original individual language unavailable.',
                           'Graphical icons/colors replaced by text. Attribute display order not retained; fixed semantic order is a reconstruction condition.',
                           'Repeated identical full choice cards may be rare: do not interpret single-person card shares as population distribution estimates.',
                           'Education, income and political self-placement measured in previous wave; not synthetic personality.']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    doc=prepare(a.directory);a.output.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(doc,f,ensure_ascii=False)
    assignment=split(doc['rows']);print(json.dumps({'people':len(assignment),'tasks':len(doc['rows']),'splits':{k:list(assignment.values()).count(k) for k in ['train','development','test']}}))
