"""Text reconstruction of unambiguous dryer conditions; private prepared rows."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pandas as pd
from ..core.core import validate, split

COUNTRIES = {'IRE': ('Ireland','EUR'), 'UK': ('United Kingdom','GBP'),
             'CAN': ('Canada','CAD'), 'USA': ('United States','USD')}
BASIC_FIELDS = ['age_band','education']
RICH_FIELDS = BASIC_FIELDS + ['weekly_dryer_use','household_size','financial_comfort']


def option_text(row):
    if int(row.Alternative) == 0:
        return 'Neither'
    country, currency = COUNTRIES[row.CountryVersion]
    if row.Treatment == 'T2' or (row.CountryVersion == 'USA' and row.Treatment == 'T1'):
        raise ValueError('Unresolved displayed energy cost; excluded from version 1')
    price = int(row.Price) + {'IRE':0,'UK':0,'CAN':200,'USA':100}[row.CountryVersion]
    north_america = row.CountryVersion in {'CAN','USA'}
    capacity = int(row.Capacity) - int(north_america)
    unit = 'cu ft' if north_america else 'kg'
    if row.Treatment == 'C':
        energy = ('Energy Star: '+ ('Yes' if row.Rating in {'A+','A++','A+++'} else 'No')) if north_america else ('Energy rating: '+row.Rating)
    else:
        energy = f'10 year Energy Cost: {currency} {int(row.EnExp)}'
    return (f'Tumble dryer {int(row.Alternative)}; Brand: {row.Brand}; '
            f'Capacity: {capacity} {unit}; {energy}; Customer rating: {int(row.Stars)} stars; '
            f'Price: {currency} {price}')


def prepare(directory):
    path=Path(directory)/'Tumbledrier_DCE.dta'
    df=pd.read_stata(path,convert_categoricals=False)
    eligible=df[(df.Treatment=='C') | ((df.Treatment=='T1') & (df.CountryVersion!='USA'))]
    rows=[]
    for (person,task), group in eligible.groupby(['ResponseId','ChoiceSet'],sort=True):
        # Actual presentation order: dryer 1, dryer 2, neither.
        group=group.set_index('Alternative').loc[[1,2,0]].reset_index()
        first=group.iloc[0]
        context=f'November 2018. Survey in {COUNTRIES[first.CountryVersion][0]}. You own and use a tumble dryer.'
        context+=' Established brands have operated for more than five years; new brands for less than five years.'
        if first.Treatment=='T1':
            context+=' Energy costs cover ten years under typical operating conditions and constant electricity prices.'
        rows.append({'person':str(person),'task':str(int(task)),
                     'stratum':first.CountryVersion+'_'+first.Treatment,
                     'group':first.CountryVersion+'_'+first.Treatment+'_card_'+str(int(task)),
                     'question':'Which of these two tumble dryers would you choose?',
                     'context':context,'options':[option_text(r) for r in group.itertuples()],
                     'answer':[1,2,0].index(int(first.Choice)),
                     'background':{'age_band':first.Age_str,'education':first.Education_str,
                                   'weekly_dryer_use':float(first.Tumbledrier_usage),
                                   'household_size':first.Household_str,'financial_comfort':first.Income_str},
                     'country':first.CountryVersion,'treatment':first.Treatment,
                     'weight':1.0})
    validate(rows)
    return {'study':'dryer_2018_text_v1','status':'prepared_not_admitted',
            'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'audit':{k:False for k in ['license_cloud_use','question_mapping','background_timing','author_statistics','leakage_review']},
            'limitations':['Text rendering of visual choice cards; does not reproduce visual layout.',
                           'Excludes all personalised-cost groups and USA generic-cost group because source values conflict.',
                           'Financial comfort is self-reported ease of living on income, not an income amount.',
                           'Background timing review must be approved before cloud use.'],
            'rows':rows}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();doc=prepare(a.directory)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f: json.dump(doc,f,ensure_ascii=False)
    assignments=split(doc['rows'])
    print(json.dumps({'people':len(assignments),'tasks':len(doc['rows']),
                      'split_counts':{k:list(assignments.values()).count(k) for k in ['train','development','test']},
                      'status':doc['status']}))
