"""Holdout product replication using RADIANT's Italian cheese sample."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import hashlib
import json

import numpy as np
import pandas as pd

import optout_pilot as pilot
from optout_transfer import outcome, predictions
from order_screen import WORK, encode, send
import protocol

RUN = WORK / 'cheese-pilot-v1'
SOURCE = WORK / 'materials/radiant/COITPR.xlsx'
SHA256 = '27d4211b50529ed8bcd5d485bfd7730ffa3fdd1d00be1e477eaa98d1c8dd4a91'
LABELS = {
    'feed': {1:'alfalfa', 2:'mixture of grasses', 3:'mixture with legumes'},
    'label': {1:'no mountain label', 2:'Parmigiano Reggiano di Montagna label'},
    'ageing': {1:'12 months', 2:'24 months', 3:'36 months or more'},
    'place': {1:'supermarket', 2:'directly from the producer'},
    'envir': {1:'production CO2 emissions not compensated', 2:'production CO2 emissions compensated'},
}


def load_deck():
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=SHA256:
        raise ValueError('Unexpected author workbook')
    frame = pd.read_excel(SOURCE,'choices')
    if len(frame)!=6120 or frame.unique_id.nunique()!=340:
        raise ValueError('Unexpected source size')
    frame = frame.loc[frame.treated==0]
    jobs, features = {}, {}
    for card, group in frame.groupby('choice_card'):
        key = f'card{card:02}'
        profiles = group[['option',*LABELS,'price']].drop_duplicates().sort_values('option')
        if list(profiles.option)!=[1,2,3]:
            raise ValueError('Inconsistent card alternatives')
        options = {}
        x = []
        for record in profiles.iloc[:2].to_dict('records'):
            labels = [LABELS[f][record[f]] for f in LABELS]
            options[str(record['option'])] = ', '.join(labels+[f'EUR {record["price"]:.2f} per kg'])
            x.append([float(record[f]==level) for f, levels in LABELS.items() for level in list(levels)[1:]]
                     + [(record['price']-21)/3])
        options['0'] = 'Neither, I would not buy either offer'
        q = {'id':key,'prompt':'Which offer would you choose?', 'options':options}
        body = protocol.build({'title':'Parmigiano Reggiano purchase choices',
            'context':('Italy, February to March 2025. Choose one of two offers or neither. '
                       'The mountain label certifies milk and ageing from designated mountain areas '
                       'and at least 60% of feed from those areas. Direct purchase can be ordered from the producer.'),
            'questions':[q],'basic':{}},'basic','qwen',{}, {},512)
        jobs[key] = {'body':body,'questions':[q]}
        features[key] = x
    if len(jobs)!=36 or frame.unique_id.nunique()!=170:
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
            'study':pilot.evaluate(*inputs)}


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
