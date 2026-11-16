"""Exploratory equal-cost Qwen comparison of original and reversed option order."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import urllib.request

import numpy as np
from scipy.optimize import minimize_scalar
import protocol
import payloads
from references import green_option
from pew_stage import BASIC_FIELDS as PEW_FIELDS

WORK = Path.home() / '.local/share/matraix-decision-transfer/work'
RUN = WORK / 'order-screen-v1'
URL = 'http://10.120.47.101:8000/v1/chat/completions'
SEED = 20261109
N = 24
DRAWS = ('original', 'repeat', 'reverse')

def read(path):
    return json.loads(path.read_text())

def encode(obj):
    return json.dumps(obj, ensure_ascii=False).encode()

def freeze():
    rng = random.Random(SEED)
    swiss = [r for r in read(WORK/'stage2/requests.json')
             if r['role']=='evaluation' and r['arm']=='basic']
    pew = [r for r in read(WORK/'pew/deck.json') if r['arm']=='own']
    jobs = []
    for study, deck, key, fields, tokens in [
        ('swiss', swiss, 'rig', payloads.BASIC_FIELDS, 768),
        ('pew', pew, 'key', PEW_FIELDS, 512),
    ]:
        assert len({str(r[key]) for r in deck}) == len(deck) >= N
        for row in rng.sample(sorted(deck, key=lambda r: str(r[key])), N):
            for draw in DRAWS:
                payload = deepcopy(row['body'])
                payload.pop('extra', None)
                if draw == 'reverse':
                    for q in payload['questions']:
                        q['options'] = dict(reversed(list(q['options'].items())))
                body = protocol.build(payload, 'basic', 'qwen', fields, {}, tokens)
                jobs.append({'study':study,'person':str(row[key]),'draw':draw,
                             'body':body,'questions':payload['questions']})
    rng.shuffle(jobs)
    RUN.mkdir(mode=0o700, exist_ok=True)
    path = RUN/'jobs.json'
    if path.exists():
        if path.read_bytes() != encode(jobs):
            raise RuntimeError('Frozen inputs changed; create a new version')
    else:
        path.write_bytes(encode(jobs))
    return jobs

def result_path(job, directory=RUN):
    return directory/(hashlib.sha256(encode(job)).hexdigest()+'.json')

def send(job, directory=RUN, parse_reply=None):
    path = result_path(job, directory)
    if path.exists():
        return
    # Exclusive marker prevents a concurrent run or an uncertain send from resubmitting.
    marker = path.with_suffix('.pending')
    try:
        marker.touch(exist_ok=False)
    except FileExistsError:
        return
    try:
        req = urllib.request.Request(URL, data=encode(job['body']),
                                     headers={'Content-Type':'application/json'})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=45) as res:
            raw = json.load(res)
        if parse_reply is None:
            parsed = protocol.parse(raw, job['questions'], 'qwen')
            mapped = {q['id']:dict(zip(q['options'], parsed['probabilities'][q['id']], strict=True))
                      for q in job['questions']}
            result = {'status':'ok','p':mapped,'identity':parsed['identity']}
        else:
            result = parse_reply(raw)
    except Exception as err:
        result = {'status':'error','type':type(err).__name__}
    tmp = path.with_suffix('.tmp')
    tmp.write_bytes(encode(result))
    tmp.replace(path)
    marker.unlink()

def scale_probability(p, log_temperature):
    logits = np.log(np.clip(p, 1e-6, 1)) / np.exp(log_temperature)
    values = np.exp(logits - logits.max(axis=-1, keepdims=True))
    return values / values.sum(axis=-1, keepdims=True)

def calibration_report(samples):
    out = {}
    for study, source in [('pew', 'swiss'), ('swiss', 'pew')]:
        if study not in samples or source not in samples:
            continue
        p, y = (np.asarray(x) for x in zip(*samples[source], strict=True))
        fit = minimize_scalar(
            lambda t: np.mean(np.sum((scale_probability(p, t)-y)**2, axis=-1)),
            bounds=(np.log(.25), np.log(4)), method='bounded')
        p, y = (np.asarray(x) for x in zip(*samples[study], strict=True))
        old = np.sum((p-y)**2, axis=-1).mean(axis=1)
        new = np.sum((scale_probability(p, fit.x)-y)**2, axis=-1).mean(axis=1)
        delta = old-new
        rng = np.random.default_rng(SEED)
        boot = delta[rng.integers(len(delta), size=(2000, len(delta)))].mean(axis=1)
        out[study] = {'fit_study':source, 'temperature':float(np.exp(fit.x)),
                      'before':float(old.mean()), 'after':float(new.mean()),
                      'paired_improvement':float(delta.mean()),
                      'ci95_conditional_on_fit':np.quantile(boot,[.025,.975]).tolist()}
    return out

def score():
    jobs = read(RUN/'jobs.json')
    truth = {'swiss':read(WORK/'stage2/answers.json'), 'pew':read(WORK/'pew/answers.json')}
    swiss_deck = {str(row['rig']): row['questions']
                  for row in read(WORK/'stage2/requests.json')
                  if row['role']=='evaluation' and row['arm']=='basic'}
    swiss_counts = {person: (sum(truth['swiss'][person][q['id']]==green_option(q)
                                 for q in questions), len(questions))
                    for person, questions in swiss_deck.items()}
    swiss_total = np.sum(list(swiss_counts.values()), axis=0)
    question_lookup = {(job['study'],job['person'],q['id']):q
                       for job in jobs for q in job['questions'] if job['draw']=='original'}
    observed = {}
    identities = set()
    errors = pending = 0
    for job in jobs:
        path = result_path(job)
        if not path.exists():
            pending += 1
            continue
        result = read(path)
        if result['status'] != 'ok':
            errors += 1
            continue
        identities.add(json.dumps(result['identity'], sort_keys=True))
        observed.setdefault((job['study'], job['person']), {})[job['draw']] = result['p']
    if len(identities)>1:
        raise RuntimeError('Model identity changed')
    out = {'planned_requests':len(jobs),'errors':errors,'pending':pending,
           'seed':SEED,'model_identity':[json.loads(i) for i in sorted(identities)],'studies':{}}
    calibration = {}
    for study in truth:
        rows=[]
        people=[]
        distributions={}
        for (s, person), draws in observed.items():
            if s != study or set(draws)!=set(DRAWS):
                continue
            cards=[]
            probabilities=[]
            targets=[]
            for qid, a in draws['original'].items():
                keys = sorted(a)
                p, r, v = (np.array([draws[d][qid][k] for k in keys]) for d in DRAWS)
                y = truth[s][person][qid]
                y = {0: 'rest', 1: 'top'}[y] if study == 'pew' else str(y)
                if y not in keys:
                    raise ValueError('Truth option not mapped')
                target=np.array([float(k==y) for k in keys])
                probabilities.append((p+r)/2)
                targets.append(target)
                if study == 'pew':
                    share = np.mean([answers[qid] for key, answers in truth[study].items() if key != person])
                    ref = np.array([share if k == 'top' else 1-share for k in keys])
                    group, focal = qid, 'top'
                else:
                    count, total = swiss_total - swiss_counts[person]
                    share = count/total
                    green = green_option(question_lookup[study, person, qid])
                    ref = np.array([share if k == green else 1-share for k in keys])
                    group, focal = 'greener_or_cheaper_on_equal_impact', green
                index = keys.index(focal)
                distributions.setdefault(group, []).append([x[index] for x in (target,p,(p+r)/2,(p+v)/2)])
                cards.append([np.sum((x-target)**2) for x in (p,(p+r)/2,(p+v)/2)]
                             + [np.abs(p-r).sum()/2,np.abs(p-v).sum()/2,np.sum((ref-target)**2)])
            rows.append(np.mean(cards,axis=0))
            people.append((probabilities,targets))
        if not rows:
            continue
        calibration[study] = people
        a=np.asarray(rows)
        delta=a[:,1]-a[:,2]
        rng=np.random.default_rng(SEED)
        samples=delta[rng.integers(0,len(delta),size=(2000,len(delta)))].mean(axis=1)
        out['studies'][study]={'complete_people':len(a),'original':float(a[:,0].mean()),
          'two_same_order':float(a[:,1].mean()),'two_opposite_orders':float(a[:,2].mean()),
          'paired_improvement':float(delta.mean()),'ci95':np.quantile(samples,[.025,.975]).tolist(),
          'same_order_probability_tv':float(a[:,3].mean()),'reverse_order_probability_tv':float(a[:,4].mean()),
          'leave_one_person_out_human_rate':float(a[:,5].mean()),
          'focal_choice_shares':{group:dict(zip(('human','original','two_same_order','two_opposite_orders'),
                                   np.mean(values,axis=0).tolist(),strict=True))
                                 for group,values in distributions.items()}}
    out['transferred_temperature'] = calibration_report(calibration)
    print(json.dumps(out,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze','run','score'])
    args=parser.parse_args()
    if args.action=='score':
        score()
    else:
        jobs=freeze()
        if args.action=='run':
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(send,jobs))
        print(json.dumps({'jobs':len(jobs),'action':args.action}))
