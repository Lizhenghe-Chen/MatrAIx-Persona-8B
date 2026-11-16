"""Third-study replication of the small-pilot product choice comparison."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import hashlib
import json

import numpy as np
import pandas as pd

import optout_pilot
import optout_transfer
import protocol
from order_screen import WORK, encode, read, send

RUN = WORK / 'radiant-pilot-v1'
SOURCE = WORK / 'materials/radiant/COESHT.xlsx'
SHA256 = '7cc938266619a06c2d75d30bfc04bfb93682b48185911ef056dd4574f369de69'
ATTRIBUTES = ('variety', 'cultur', 'access', 'label', 'place', 'cost')
LABELS = {
    'variety': {1:'underutilised variety', 2:'commercial variety'},
    'cultur': {1:'without cultural value', 2:'with cultural value'},
    'access': {1:'short food supply chain', 2:'speciality food shop', 3:'supermarket'},
    'label': {1:'without quality and territorial label', 2:'with quality and territorial label'},
    'place': {1:'your province', 2:'elsewhere in Spain', 3:'outside Spain'},
}


def attributes(row):
    return [float(row[field]==level) for field, levels in LABELS.items()
            for level in list(levels)[1:]] + [(row['cost']-6.5)/2]


def deck():
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SHA256:
        raise ValueError('Unexpected RADIANT workbook version')
    frame = pd.read_excel(SOURCE, sheet_name='choice')
    if frame.shape[0] != 6210 or frame.unique_id.nunique()!=345:
        raise ValueError('Unexpected study size')
    clean = frame[frame.treated==0]
    if clean.unique_id.nunique()!=175:
        raise ValueError('Unexpected untreated cohort')
    jobs, features = {}, {}
    for card, group in clean.groupby('choice_card'):
        qid = f'card{card:02}'
        profiles = group[['option',*ATTRIBUTES]].drop_duplicates().sort_values('option')
        if list(profiles.option)!=[1,2,3]:
            raise ValueError('Card ID has inconsistent options')
        options = {'0':'Neither, I would buy neither offer'}
        product_features = []
        for row in profiles.iloc[:2].to_dict('records'):
            parts = [f'{field}: {LABELS[field][row[field]]}' for field in LABELS]
            parts.append(f'price: {row["cost"]:.2f} EUR per kilogram')
            options[str(row['option'])] = ', '.join(parts)
            product_features.append(attributes(row))
        options = {i:options[i] for i in ('1','2','0')}
        q = {'id':qid,'prompt':'Which option would you choose?', 'options':options}
        payload = {'title':'Hanging tomato shopping choices',
                   'context':('Spain, January 2025. Choose between two offers of hanging tomatoes or neither. '
                              'Variety alone does not determine nutritional value or quality.'),
                   'questions':[q],'basic':{}}
        jobs[qid] = {'body':protocol.build(payload,'basic','qwen',{}, {},512),'questions':[q]}
        features[qid] = product_features
    if len(jobs)!=36:
        raise ValueError('Expected 36 distinct cards')
    return clean, jobs, features


def freeze(jobs):
    RUN.mkdir(mode=0o700,exist_ok=True)
    path = RUN/'jobs.json'
    if path.exists() and path.read_bytes()!=encode(jobs):
        raise ValueError('Frozen requests changed')
    if not path.exists():
        path.write_bytes(encode(jobs))


def score(frame, jobs, features):
    predictions, identities = optout_transfer.predictions(jobs,RUN)
    if len(identities)!=1:
        raise ValueError('Mixed model versions')
    people = []
    for _, group in frame.groupby('unique_id'):
        if len(group)!=18 or group.choice_set.nunique()!=1 or group.choice_card.nunique()!=6:
            raise ValueError('Unexpected participant design')
        chosen = group[group.choice==1].sort_values('choice_card')
        if len(chosen)!=6 or chosen.choice_card.nunique()!=6:
            raise ValueError('Each card must have one selected option')
        people.append({f'card{row.choice_card:02}':str(row.option if row.option!=3 else 0)
                       for row in chosen.itertuples(index=False)})
    p,y = optout_transfer.outcome(predictions,people)
    keys = np.asarray([list(row) for row in people])
    x = np.asarray([[features[k] for k in row] for row in keys])
    return {'workbook_sha256':SHA256,'seed':optout_pilot.SEED,
            'splits':optout_pilot.REPEATS,'new_qwen_calls':len(jobs),
            'identity':json.loads(next(iter(identities))),
            'study':optout_pilot.evaluate(p,y,keys,None,x)}


if __name__=='__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action',choices=['freeze','run','score'])
    args = cli.parse_args()
    frame,jobs,features = deck()
    freeze(jobs)
    if args.action=='run':
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(partial(send,directory=RUN),jobs.values()))
    result = score(frame,jobs,features) if args.action=='score' else {'jobs':len(jobs)}
    print(json.dumps(result,indent=2))
