"""Replay same-question forecasts with the previous year's published aggregate."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import json

import numpy as np

import protocol
import survey_pilot
from optout_transfer import predictions
from order_screen import WORK, encode, send

RUN = WORK / 'survey-time-transfer-v1'
# Table 16 of the Fed's 2024 report, in INF3 a–f order.
HISTORY = {2022: [64,66,51,15,49,18], 2023: [62,61,45,15,48,18],
           2024: [63,61,43,16,46,18]}
ITEMS = list(survey_pilot.QUESTIONS)[:6]


def deck():
    jobs = {}
    for year in (2023,2024,2025):
        for item, previous in zip(ITEMS,HISTORY[year-1],strict=True):
            question = {'id':item,'prompt':survey_pilot.QUESTIONS[item],
                        'options':{'1':'Yes','0':'No'}}
            for condition in ('direct','previous_rate'):
                context = (f'Estimate how US adults would answer in October {year}. '
                           'Only use information that could have been available by that date.')
                if condition == 'previous_rate':
                    context += (f' In the previous annual survey, {previous}% answered Yes to this same item. '
                                'Use that result as a starting point and estimate the current percentage.')
                payload = {'title':'US household survey','context':context,
                           'questions':[question],'basic':{}}
                jobs[f'{year}:{item}:{condition}'] = {
                    'body':protocol.build(payload,'basic','qwen',{}, {},256),'questions':[question]}
    RUN.mkdir(mode=0o700,exist_ok=True)
    path = RUN/'jobs.json'
    if path.exists() and path.read_bytes()!=encode(jobs):
        raise ValueError('Frozen requests changed')
    if not path.exists():
        path.write_bytes(encode(jobs))
    return jobs


def score(jobs):
    answer, identities = predictions(jobs,RUN)
    if len(identities)!=1:
        raise ValueError('Model identity changed')
    y,w = survey_pilot.load_answers()
    targets = {2023:HISTORY[2023],2024:HISTORY[2024],2025:(100*np.average(y[:,:6],axis=0,weights=w)).tolist()}
    results = {}
    for year, target in targets.items():
        estimates = {'previous_rate':HISTORY[year-1]}
        if year-2 in HISTORY:
            estimates['linear_trend'] = (2*np.asarray(HISTORY[year-1])-HISTORY[year-2]).tolist()
        for condition in ('direct','previous_rate'):
            estimates['qwen_'+condition] = [
                100*answer[f'{year}:{item}:{condition}']['1'] for item in ITEMS]
        results[year] = {'actual_yes_pct':dict(zip(ITEMS,target,strict=True)),
                         'methods':{name:{
                             'estimate_yes_pct':dict(zip(ITEMS,p,strict=True)),
                             'mae_pp':float(np.mean(np.abs(np.asarray(p)-target))),
                             'max_error_pp':float(np.max(np.abs(np.asarray(p)-target))),
                         } for name,p in estimates.items()}}
    return {'requests':len(jobs),'model':json.loads(next(iter(identities))),
            '2025_complete_cases':len(y),'results':results}


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['run','score'])
    action = parser.parse_args().action
    jobs = deck()
    if action=='run':
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(partial(send,directory=RUN),jobs.values()))
        print(json.dumps({'requests':len(jobs)}))
    else:
        print(json.dumps(score(jobs),indent=2))
