"""Compare price-only and Qwen-assisted refusal with identical pilot answers."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import hashlib
import json
import re

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, logit, softmax

from optout_pilot import SEED, REPEATS, fit_products, losses, split_cards
from optout_transfer import outcome, predictions
from order_screen import WORK, encode, read, send
from price_pilot import price_refusal
import protocol

SOURCE = WORK.parents[1] / 'matraix-decision-lab/dryer-text-v1/prepared.json'
RUN = WORK / 'dryer-refusal-v1'
COUNTRIES = ('CAN','USA')
BUDGETS = (10,25,50,100)


def features(label):
    return [float('Brand: Established;' in label),
            float('Energy Star: Yes' in label),
            int(re.search(r'Capacity: (\d+) cu ft',label)[1])-6,
            int(re.search(r'Customer rating: (\d+) stars',label)[1])-3,
            (int(re.search(r'Price: [A-Z]+ (\d+)',label)[1])-900)/200]


def deck():
    doc = read(SOURCE)
    jobs, cards, groups = {}, {}, {}
    for row in doc['rows']:
        country = row['country']
        if country not in COUNTRIES or row['treatment'] != 'C':
            continue
        key = f"{country}-card{int(row['task']):02}"
        a,b,refusal = row['options']
        if refusal!='Neither' or row['answer'] not in (0,1,2):
            raise ValueError('Unexpected source mapping')
        q = {'id':key,'prompt':row['question'],'options':{'1':a,'2':b,'0':refusal}}
        body = protocol.build({'title':'Tumble dryer purchase choices',
            'context':row['context'],'questions':[q],'basic':{}},'basic','qwen',{}, {},512)
        job = {'questions':[q],'body':body}
        if key in jobs and jobs[key]!=job:
            raise ValueError('Inconsistent stimuli for card')
        jobs[key] = job
        cards[key] = [features(a),features(b)]
        person = groups.setdefault(country,{}).setdefault(row['person'],{})
        if key in person:
            raise ValueError('Duplicate choice')
        person[key] = ('1','2','0')[row['answer']]
    if len(jobs)!=64 or [len(groups[c]) for c in COUNTRIES]!=[214,208]:
        raise ValueError('Unexpected cohort')
    if any(len(row)!=8 for people in groups.values() for row in people.values()):
        raise ValueError('Incomplete design')
    return jobs, cards, groups


def qwen_refusal(train_x, y, test_x):
    """Price and Qwen columns share the same fixed ridge and sign restrictions."""
    center = train_x.mean(axis=0)
    design = np.column_stack((np.ones(len(y)+2),np.vstack((train_x-center,np.zeros((2,2))))))
    truth = np.r_[y,0.,1.]
    weight = np.r_[np.ones(len(y)),.5,.5]/(len(y)+1)

    def objective(beta):
        z = design @ beta
        penalty = np.r_[0.,beta[1:]]
        value = weight @ (np.logaddexp(0,z)-truth*z) + .01*(penalty @ penalty)
        grad = design.T @ (weight*(expit(z)-truth)) + .02*penalty
        return value,grad

    fit = minimize(objective,[logit((y.sum()+.5)/(len(y)+1)),0.,0.],
                   jac=True,method='L-BFGS-B',bounds=[(None,None),(0,None),(0,None)])
    if not fit.success:
        raise RuntimeError(fit.message)
    return expit(fit.x[0]+(test_x-center) @ fit.x[1:])


def evaluate(p, y, keys, features_):
    rng = np.random.default_rng(SEED)
    scores = {n:[] for n in BUDGETS}
    covariates = np.stack((features_[:,:,:,-1].min(axis=2), p[:,:,0]/.25),axis=2)
    for _ in range(REPEATS):
        cards = split_cards(keys,rng)
        order = rng.permutation(len(y))
        test = order[max(BUDGETS):]
        held = ~cards[test]
        test_y, test_x = y[test][held], features_[test][held]
        for n in BUDGETS:
            train = order[:n]
            picked = cards[train]
            train_y, train_x = y[train][picked], features_[train][picked]
            products = softmax(test_x @ fit_products(train_x,train_y),axis=1)
            raw = p[test][held]
            constant = np.full(len(test_y),(train_y[:,0].sum()+.5)/(len(train_y)+1))
            price, _ = price_refusal(train_x,train_y[:,0],test_x)
            assisted = qwen_refusal(covariates[train][picked],train_y[:,0],covariates[test][held])
            scores[n].append({
                'qwen_direct':float(np.sum((raw-test_y)**2,axis=1).mean()),
                **{label:losses(q,products,test_y) for label,q in [
                    ('constant',constant),('price',price),('price_and_qwen',assisted)]},
                'price_refusal_brier':float(np.mean(2*(price-test_y[:,0])**2)),
                'price_and_qwen_refusal_brier':float(np.mean(2*(assisted-test_y[:,0])**2)),
            })
    out = {}
    for n, rows in scores.items():
        delta = np.asarray([r['price']-r['price_and_qwen'] for r in rows])
        out[n] = {k:float(np.mean([r[k] for r in rows])) for k in rows[0]}
        out[n]['qwen_increment'] = {'win_rate':float(np.mean(delta>1e-6)),
                                     'p05_p95':np.quantile(delta,[.05,.95]).tolist()}
    return out


def score(jobs,cards,groups):
    p,ids = predictions(jobs,RUN)
    if len(ids)!=1:
        raise ValueError('Mixed model versions')
    out = {}
    for country, people in groups.items():
        ordered = [dict(sorted(person.items())) for person in people.values()]
        probs,truth = outcome(p,ordered)
        keys = np.asarray([list(person) for person in ordered])
        x = np.asarray([[cards[key] for key in person] for person in keys])
        out[country] = {'people':len(ordered),'actual_refusal':float(truth[:,:,0].mean()),
                        'budgets':evaluate(probs,truth,keys,x)}
    return {'calls':len(jobs),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            'seed':SEED,'splits':REPEATS,'identity':json.loads(next(iter(ids))),'studies':out}


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['run','score'])
    action = parser.parse_args().action
    jobs,cards,groups = deck()
    RUN.mkdir(mode=0o700,exist_ok=True)
    path = RUN/'jobs.json'
    if path.exists() and path.read_bytes()!=encode(jobs):
        raise ValueError('Frozen requests changed')
    if not path.exists():
        path.write_bytes(encode(jobs))
    if action=='run':
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(partial(send,directory=RUN),jobs.values()))
    print(json.dumps(score(jobs,cards,groups) if action=='score' else {'calls':len(jobs)},indent=2))
