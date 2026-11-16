"""Test transfer of no-buy rates and model calibration between two studies."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import json

import numpy as np
from scipy.optimize import brentq
from scipy.special import expit, logit, softmax
import pyreadstat

import packaging_transfer as germany
import protocol
from order_screen import WORK, encode, read, result_path, send, SEED

RUN = WORK / 'optout-transfer-v1'
BEER = WORK.parents[1] / 'matraix-decision-lab/cross-study-v1/adapters/packaging.json'


def beer_deck():
    deck, people = {}, []
    for row in read(BEER)['rows']:
        answers = {}
        for question in row['questions']:
            qid = question['id']
            q = {'id':qid,'prompt':question['prompt'],
                 'options':{str(o['id']):o['label'] for o in question['options']}}
            if set(q['options']) != {'0','1','2'}:
                raise ValueError('Unexpected beer options')
            payload = {'title':'United States six-pack beer choices, 2019',
                       'context':row['context'],'questions':[q],'basic':{}}
            body = protocol.build(payload,'basic','qwen',{}, {},512)
            key = (row['context'],qid)
            job = {'body':body,'questions':[q]}
            if key in deck and deck[key] != job:
                raise ValueError('Same design cell has inconsistent stimuli')
            deck[key] = job
            answers[key] = str(row['truth'][qid])
        people.append(answers)
    counts = [choice for person in people for choice in person.values()]
    if len(people)!=1291 or len(counts)!=10328 or counts.count('0')!=3332:
        raise ValueError('Beer counts differ from author data index')
    return deck, people


def freeze():
    deck, _ = beer_deck()
    jobs = list(deck.values())
    RUN.mkdir(mode=0o700,exist_ok=True)
    path = RUN/'jobs.json'
    if path.exists() and path.read_bytes() != encode(jobs):
        raise ValueError('Frozen beer tasks changed')
    if not path.exists():
        path.write_bytes(encode(jobs))
    return jobs


def predictions(deck, directory):
    output = {}
    identities = set()
    for key, job in deck.items():
        res = read(result_path(job,directory))
        if res['status'] != 'ok':
            raise RuntimeError(f'Unusable response: {res["type"]}')
        output[key] = res['p'][job['questions'][0]['id']]
        identities.add(json.dumps(res['identity'],sort_keys=True))
    return output, identities


def german_deck():
    jobs = {j['questions'][0]['id']:j for j in read(germany.RUN/'jobs.json') if j['study']=='direct'}
    frame, meta = pyreadstat.read_sav(str(germany.SOURCE/'data_valid.sav'))
    assert meta.variable_value_labels['Group'][2] == 'G2: without information about bioplastic'
    people = [{q:str(int(code)) for q,code in row.items()}
              for row in frame.loc[frame.Group==2,list(jobs)].to_dict('records')]
    return jobs, people


def outcome(predicted, people):
    probabilities, targets = [], []
    for person in people:
        p, y = [], []
        for card, choice in person.items():
            ids = sorted(predicted[card])
            p.append([predicted[card][i] for i in ids])
            y.append([float(choice==i) for i in ids])
        probabilities.append(p)
        targets.append(y)
    return np.asarray(probabilities), np.asarray(targets)


def estimate(p, y, source_rate, source_offset, conditional_override=None):
    no_buy = p[:,:,0]
    conditional = p[:,:,1:]/p[:,:,1:].sum(axis=2,keepdims=True)
    opts = {'qwen':no_buy,'source_rate':np.full_like(no_buy,source_rate),
            'source_logit_offset':expit(logit(np.clip(no_buy,1e-5,1-1e-5))+source_offset)}
    combinations = {name:(rate,conditional) for name,rate in opts.items()}
    if conditional_override is not None:
        combinations.update({f'swiss_products_{name}':(rate,conditional_override) for name,rate in opts.items()})
    full, summary = {}, {}
    for name, (rate, products) in combinations.items():
        joint = np.concatenate((rate[:,:,None],products*(1-rate[:,:,None])),axis=2)
        full[name] = np.sum((joint-y)**2,axis=2).mean(axis=1)
        binary = (2*(rate-y[:,:,0])**2).mean(axis=1)
        summary[name] = {'no_buy_rate':float(rate.mean()),'full_brier':float(full[name].mean()),
                         'no_buy_brier':float(binary.mean())}
    for name in sorted(combinations.keys() - {'qwen'}):
        delta = full['qwen']-full[name]
        rng = np.random.default_rng(SEED)
        boot = delta[rng.integers(len(delta),size=(2000,len(delta)))].mean(axis=1)
        summary[name]['full_improvement_ci95'] = np.quantile(boot,[.025,.975]).tolist()
    return summary


def score():
    beer, people_beer = beer_deck()
    german, people_german = german_deck()
    pred_beer, id_beer = predictions(beer,RUN)
    pred_german, id_german = predictions(german,germany.RUN)
    arrays = {'beer':outcome(pred_beer,people_beer), 'german':outcome(pred_german,people_german)}
    output = {'new_qwen_calls':len(beer),'reused_german_calls':len(german),
              'identities':{'beer':[json.loads(i) for i in sorted(id_beer)],
                            'german':[json.loads(i) for i in sorted(id_german)]},
              'studies':{}}
    for target, source in [('beer','german'),('german','beer')]:
        sp, sy = arrays[source]
        target_p, target_y = arrays[target]
        rate = float(sy[:,:,0].mean())
        logits = logit(np.clip(sp[:,:,0],1e-5,1-1e-5))
        offset = brentq(lambda b: expit(logits+b).mean()-rate,-30,30)
        override = None
        if target=='german':
            beta = read(WORK/'attribute-transfer-v1/frozen.json')['beta']
            design = germany.cards()
            first_order = list(people_german[0])
            if any(list(person)!=first_order for person in people_german):
                raise ValueError('Inconsistent target card order')
            override = softmax([[-beta[0]*price/.15 + beta[1]*(decay=='Biologisch abbaubar')
                                  for _,decay,_,price in design[card]] for card in first_order],axis=1)
        output['studies'][target] = {'people':len(target_y),'choices':int(np.prod(target_y.shape[:2])),
          'actual_no_buy_rate':float(target_y[:,:,0].mean()),'source':source,
          'source_logit_offset':offset,'methods':estimate(target_p,target_y,rate,offset,override)}
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['freeze','run','score'])
    args = parser.parse_args()
    if args.action=='score':
        print(json.dumps(score(),indent=2))
    else:
        jobs = freeze()
        if args.action=='run':
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(partial(send,directory=RUN),jobs))
        print(json.dumps({'jobs':len(jobs)}))
