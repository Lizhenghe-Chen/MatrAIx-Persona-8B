"""Price-sensitive refusal replication using RADIANT's Scottish shortbread sample."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import hashlib
import json

import numpy as np
import pandas as pd

import optout_pilot as pilot
from price_pilot import evaluate
from optout_transfer import outcome, predictions
from order_screen import WORK, encode, send
import protocol

RUN = WORK / 'shortbread-pilot-v1'
SOURCE = WORK / 'materials/radiant/COSCBB.xlsx'
SHA256 = '447cb59fab8500639d9f5478dad4aeeeb64bc09f1d0d0848ae0219e1c42c88a0'
LABELS = {
    'ingr': {1:'contains Bere flour alongside other flour',2:'contains no Bere flour'},
    'nutr': {1:'low nutritional value',2:'medium nutritional value',3:'high nutritional value'},
    'label': {1:'no quality and territorial label',2:'quality and territorial label'},
    'access': {1:'short food supply chain',2:'speciality food shop',3:'commercial grocery shop'},
    'prox': {1:'main crop grown in a neighbouring region',2:'main crop grown elsewhere in Scotland',
             3:'main crop grown outside Scotland'},
}


def load_deck():
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=SHA256:
        raise ValueError('Unexpected author workbook')
    frame = pd.read_excel(SOURCE,'choices')
    if len(frame)!=5370 or frame.unique_id.nunique()!=299:
        raise ValueError('Unexpected source size')
    frame = frame.loc[frame.treated==0]
    jobs, features = {}, {}
    for card, group in frame.groupby('choice_card'):
        key = f'card{card:02}'
        profiles = group[['option',*LABELS,'cost']].drop_duplicates().sort_values('option')
        if list(profiles.option)!=[1,2,3]:
            raise ValueError('Inconsistent card alternatives')
        options = {}
        x = []
        for record in profiles.iloc[:2].to_dict('records'):
            labels = [LABELS[f][record[f]] for f in LABELS]
            options[str(record['option'])] = ', '.join(labels+[f'GBP {record["cost"]:.2f} per 250 g pack'])
            x.append([float(record[f]==level) for f, levels in LABELS.items() for level in list(levels)[1:]]
                     + [(record['cost']-6)/2.5])
        options['0'] = 'Neither, I would not buy either offer'
        q = {'id':key,'prompt':'Which offer would you choose?', 'options':options}
        body = protocol.build({'title':'Shortbread purchase choices',
            'context':'Scotland, February to March 2024. Choose one of two 250 g shortbread packs or neither.',
            'questions':[q],'basic':{}},'basic','qwen',{}, {},512)
        jobs[key] = {'body':body,'questions':[q]}
        features[key] = x
    if len(jobs)!=36 or frame.unique_id.nunique()!=154:
        raise ValueError('Unexpected comparison group')
    return frame,jobs,features


def evaluation_inputs(frame,jobs,features):
    p,identities = predictions(jobs,RUN)
    if len(identities)!=1:
        raise ValueError('Mixed model versions')
    people = []
    for _, rows in frame.groupby('unique_id'):
        chosen = rows[rows.choice==1].sort_values('choice_card')
        if len(rows)!=18 or len(chosen)!=6 or chosen.choice_card.nunique()!=6 or rows.choice_set.nunique()!=1:
            raise ValueError('Unexpected participant design')
        people.append({f'card{r.choice_card:02}':str(r.option if r.option!=3 else 0)
                       for r in chosen.itertuples(index=False)})
    probabilities,targets = outcome(p,people)
    keys = np.asarray([list(row) for row in people])
    x = np.asarray([[features[key] for key in row] for row in keys])
    return (probabilities,targets,keys,None,x), p, identities


def score(frame,jobs,features):
    inputs, p, identities = evaluation_inputs(frame,jobs,features)
    return {'source_sha256':SHA256,'seed':pilot.SEED,'splits':pilot.REPEATS,
            'calls':len(jobs),'refusal_only_cards':sum(v['0']==1 for v in p.values()),
            'identity':json.loads(next(iter(identities))),
            'eligible_people':len(frame.unique_id.unique()),'study':evaluate(*inputs)}


if __name__=='__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action',choices=['run','score'])
    action = cli.parse_args().action
    frame,jobs,x = load_deck()
    RUN.mkdir(mode=0o700,exist_ok=True)
    path = RUN/'jobs.json'
    if path.exists() and path.read_bytes()!=encode(jobs):
        raise ValueError('Frozen cards changed')
    if not path.exists():
        path.write_bytes(encode(jobs))
    if action=='run':
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(partial(send,directory=RUN),jobs.values()))
    print(json.dumps(score(frame,jobs,x) if action=='score' else {'requests':len(jobs)},indent=2))
