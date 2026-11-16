"""Evaluate same-item and held-out-item calibration of survey probabilities."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import expit, logit

import protocol
from order_screen import WORK, SEED, encode, read, send
from optout_transfer import predictions

RUN = WORK / 'survey-pilot-v1'
ZIP = Path(__file__).resolve().parents[2] / 'sim-to-real/study/数据/shed.zip'
ACTIONS = ('Switched to cheaper products', 'Used less or stopped using products',
           'Reduced savings', 'Increased borrowing', 'Delayed a major purchase',
           'Worked more or got another job')
QUESTIONS = {
    **{f'INF3_{c}': f'Did you take this action because of increases in prices over the past 12 months? {label}'
       for c, label in zip('abcdef', ACTIONS, strict=True)},
    'INF5': ('In the past 12 months, did you make any large purchases sooner than you had planned '
             'because you expected prices to increase?'),
}
BUDGETS = (10, 25, 50, 100)


def deck():
    jobs = {}
    for key, prompt in QUESTIONS.items():
        q = {'id':key, 'prompt':prompt, 'options':{'1':'Yes', '0':'No'}}
        payload = {'title':'US household survey, 2025',
                   'context':('Estimate how adults in the United States would respond in the 2025 survey. '
                              'The question concerns actions over the preceding year.'),
                   'questions':[q], 'basic':{}}
        jobs[key] = {'body':protocol.build(payload,'basic','qwen',{}, {},256),'questions':[q]}
    RUN.mkdir(mode=0o700,exist_ok=True)
    path = RUN/'jobs.json'
    if path.exists() and path.read_bytes() != encode(jobs):
        raise ValueError('Frozen deck changed')
    if not path.exists():
        path.write_bytes(encode(jobs))
    return jobs


def load_answers():
    cols = list(QUESTIONS)
    flags = [q+'_iflag' for q in cols]
    df = pd.read_csv(ZIP,usecols=[*cols,*flags,'weight'])
    valid = df[cols].isin(['Yes','No']).all(axis=1) & df[flags].eq(0).all(axis=1)
    valid &= np.isfinite(df.weight) & df.weight.gt(0)
    return df.loc[valid,cols].eq('Yes').to_numpy(float), df.loc[valid,'weight'].to_numpy(float)


def scores(prob, truth, truth_second):
    # Weighted Brier for binary observations equals twice squared error.
    return np.mean(2*(prob**2-2*prob*truth+truth_second),axis=-1)


def evaluate(y, weights, p):
    rng = np.random.default_rng(SEED)
    p_logit = logit(np.clip(p,1e-5,1-1e-5))
    folds = list(itertools.combinations(range(len(p)),3))
    output = {}
    for size in BUDGETS:
        same, held = [], []
        for _ in range(100):
            pilot = rng.choice(len(y),size=size,replace=False)
            mask = np.ones(len(y),dtype=bool)
            mask[pilot] = False
            pilot_weights = weights[pilot]/weights[pilot].mean()
            count = pilot_weights.sum()
            yes = pilot_weights @ y[pilot]
            mean = (yes+.5)/(count+1)
            prior = (yes+10*p)/(count+10)
            target = np.average(y[mask],axis=0,weights=weights[mask])
            same.append((scores(p,target,target),scores(mean,target,target),scores(prior,target,target),
                         np.abs(p-target).mean(),np.abs(mean-target).mean(),np.abs(prior-target).mean()))
            for anchor in folds:
                anchor = list(anchor)
                heldout = np.asarray([q for q in range(len(p)) if q not in anchor])
                observed = float(mean[anchor].mean())
                shift = brentq(lambda b: expit(p_logit[anchor]+b).mean()-observed,-30,30)
                updated = expit(p_logit[heldout]+shift)
                actual = target[heldout]
                held.append((scores(p[heldout],actual,actual),scores(observed,actual,actual),
                             scores(updated,actual,actual),np.abs(p[heldout]-actual).mean(),
                             np.abs(observed-actual).mean(),np.abs(updated-actual).mean()))
        def summary(rows, labels):
            data = np.asarray(rows)
            out = {}
            for i,name in enumerate(labels):
                delta = data[:,0]-data[:,i]
                out[name] = {'brier':float(data[:,i].mean()),'distribution_error_pp':float(data[:,i+3].mean()*100),
                             'relative_brier_improvement':float(delta.mean()/data[:,0].mean()),
                             'split_delta_p05_p95':np.quantile(delta,[.05,.95]).tolist()}
            return out
        output[size] = {'same_questions':summary(same,('qwen','pilot','pilot_with_qwen_prior')),
                        'heldout_questions':summary(held,('qwen','anchor_mean','qwen_shared_shift'))}
    return output


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action',choices=['run','score'])
    args = cli.parse_args()
    jobs = deck()
    if args.action == 'run':
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(partial(send,directory=RUN),jobs.values()))
        print(json.dumps({'requests':len(jobs)}))
    else:
        prediction, ids = predictions(jobs,RUN)
        if len(ids)!=1:
            raise ValueError('Mixed model versions')
        y,w = load_answers()
        p = np.asarray([prediction[q]['1'] for q in QUESTIONS])
        print(json.dumps({'seed':SEED,'calls':len(jobs),'eligible_people':len(y),
            'identity':json.loads(next(iter(ids))),
            'items':{q:{'actual_yes':float(rate),'qwen_yes':float(estimate)}
                     for q,rate,estimate in zip(QUESTIONS,np.average(y,axis=0,weights=w),p,strict=True)},
            'budgets':evaluate(y,w,p)},indent=2))
