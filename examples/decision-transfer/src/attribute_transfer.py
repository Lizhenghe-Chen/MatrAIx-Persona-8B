"""Transfer a source-only choice model to two other product categories."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import hashlib
import json
import random

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

import payloads
import protocol
from references import attribute_ranks
from order_screen import WORK, encode, read, send, result_path, SEED

RUN = WORK / 'attribute-transfer-v1'
DOMAINS = ('clothes', 'food')
N = 24


def design(conjoint):
    tasks = {}
    columns = ['PubId', 'product', 'round', 'measure', 'price', 'impact', 'choice']
    for person, product, round_, offer, price, impact, choice in conjoint[columns].itertuples(index=False, name=None):
        if not isinstance(product, str) or product not in payloads.PRICE_LEVELS:
            continue
        if price not in payloads.PRICE_ORDER or impact not in payloads.IMPACT_ORDER or choice not in (0, 1):
            continue
        if not np.isfinite(person) or not np.isfinite(round_) or offer not in (1, 2):
            continue
        tasks.setdefault(int(person), []).append({
            'product': product, 'domain': payloads.swiss.PRODUCT_DOMAIN[product],
            'round': int(round_), 'offer': int(offer), 'price': price, 'impact': impact, 'chosen': int(choice),
        })
    for person, rows in tasks.items():
        record = {'tasks': rows}
        domain = payloads.swiss.domain_of(record)
        if domain is None or not payloads.swiss.valid_task_person(record):
            continue
        questions = payloads.questions(record)
        truth = {payloads.questions({'tasks':[row]})[0]['id']: f"offer-{row['offer']}"
                 for row in rows if row['chosen']}
        if set(truth) != {q['id'] for q in questions}:
            raise ValueError('Choice cards and truth do not align')
        yield person, domain, questions, truth


def features(question):
    first, second = attribute_ranks(question).values()
    # Positive means the first offer costs less or causes less environmental impact.
    return np.asarray(second) - np.asarray(first)


def fit_logit(source):
    x = np.asarray([features(q) for _, qs, _ in source for q in qs])
    y = np.asarray([next(iter(q['options'])) == answers[q['id']]
                    for _, qs, answers in source for q in qs], dtype=float)
    def loss(beta):
        z = x @ beta
        return np.mean(np.logaddexp(0, z) - y*z) + 1e-4 * (beta @ beta)
    fit = minimize(loss, np.zeros(x.shape[1]), bounds=[(0, None)] * x.shape[1])
    if not fit.success:
        raise RuntimeError(fit.message)
    return fit.x


def load_pools():
    source_path = payloads.swiss.RAW / 'w14_conjoint.RData'
    if not source_path.is_file():
        source_path = WORK / 'materials/swiss-raw/w14_conjoint.RData'
    admission = read(protocol.NATIVE.parent/'admission/swiss.json')
    if hashlib.sha256(source_path.read_bytes()).hexdigest() != admission['sources']['conjoint']['sha256']:
        raise RuntimeError('Unexpected source data')
    existing = read(WORK/'stage2/participants.json')
    exclude = {int(p['pub_id']) for p in existing}
    exclude.update(int(p['donor']) for p in existing if p.get('donor') is not None)
    pool = {}
    for person, domain, qs, truth in design(payloads.swiss.load_conjoint(source_path)):
        if person not in exclude:
            pool.setdefault(domain, []).append((person, qs, truth))
    return pool


def freeze():
    pool = load_pools()
    source = pool['electronics']
    beta = fit_logit(source)
    jobs, truth = [], {}
    rng = random.Random(SEED)
    for domain in DOMAINS:
        for person, questions, answers in rng.sample(sorted(pool[domain]), N):
            key = str(person)
            truth[key] = answers
            payload = {'title': payloads.TITLE, 'context': payloads.CONTEXT,
                       'questions': questions, 'basic': {}}
            jobs.append({'study':domain, 'person':key, 'questions':questions,
                         'body':protocol.build(payload, 'basic', 'qwen', {}, {}, 768)})
    rng.shuffle(jobs)
    frozen = {'jobs': jobs, 'answers':truth, 'beta':beta.tolist(), 'source_people':len(source),
              'target_pools':{d:len(pool[d]) for d in DOMAINS}}
    RUN.mkdir(mode=0o700, exist_ok=True)
    path = RUN/'frozen.json'
    if path.exists() and path.read_bytes() != encode(frozen):
        raise RuntimeError('Freeze changed')
    if not path.exists():
        path.write_bytes(encode(frozen))
    return frozen


def score(frozen):
    identities = set()
    methods = ('uniform', 'qwen', 'source_logit', 'equal_mix')
    out = {'source_people':frozen['source_people'], 'target_pools':frozen['target_pools'],
           'source_coefficients_cheaper_greener':frozen['beta'], 'requests':len(frozen['jobs']),
           'failed':0, 'missing':0, 'targets':{}}
    for domain in DOMAINS:
        rows, conflicting = [], []
        for job in frozen['jobs']:
            if job['study'] != domain:
                continue
            path = result_path(job, RUN)
            if not path.exists():
                out['missing'] += 1
                continue
            result = read(path)
            if result['status'] != 'ok':
                out['failed'] += 1
                continue
            identities.add(json.dumps(result['identity'], sort_keys=True))
            cards, conflict_cards = [], []
            for q in job['questions']:
                keys = list(q['options'])
                x = features(q)
                llm = result['p'][q['id']][keys[0]]
                prior = float(expit(x @ np.asarray(frozen['beta'])))
                y = float(frozen['answers'][job['person']][q['id']] == keys[0])
                scores = 2 * (np.asarray([.5, llm, prior, (llm+prior)/2])-y)**2
                cards.append(scores)
                if x[0]*x[1] < 0:
                    conflict_cards.append(scores)
            rows.append(np.mean(cards,axis=0))
            if conflict_cards:
                conflicting.append(np.mean(conflict_cards,axis=0))
        if rows:
            a = np.asarray(rows)
            delta = a[:,2]-a[:,3]
            rng = np.random.default_rng(SEED)
            boot = delta[rng.integers(len(delta),size=(2000,len(delta)))].mean(axis=1)
            out['targets'][domain] = {
                'complete_people':len(a), 'brier':dict(zip(methods,a.mean(axis=0).tolist())),
                'mix_improvement_over_logit':float(delta.mean()),
                'ci95':np.quantile(boot,[.025,.975]).tolist(),
                'conflict_people':len(conflicting),
                'conflict_brier':dict(zip(methods,np.mean(conflicting,axis=0).tolist())) if conflicting else {},
            }
    if len(identities)>1:
        raise RuntimeError('Model identity changed')
    out['model_identity'] = [json.loads(i) for i in sorted(identities)]
    return out


def improvement_interval(rows):
    values = np.asarray(rows)
    delta = values[:, 1] - values[:, 2]
    rng = np.random.default_rng(SEED)
    boot = [float(delta[rng.integers(len(delta), size=len(delta))].mean()) for _ in range(2000)]
    return {'improvement':float(delta.mean()),'ci95_conditional_on_source':np.quantile(boot,[.025,.975]).tolist()}


def population(frozen):
    """Statistical comparison on all eligible target records, with no target fit."""
    pools = load_pools()
    beta = np.asarray(frozen['beta'])
    source_rows = []
    for _, questions, answers in pools['electronics']:
        for q in questions:
            x = features(q)
            first = next(iter(q['options']))
            if x[1] != 0:
                source_rows.append((answers[q['id']] == first) == (x[1] > 0))
    source_green = float(np.mean(source_rows))
    methods = ('uniform', 'source_green_rate', 'source_logit')
    out = {'source_green_rate':source_green,'targets':{}}
    for domain in DOMAINS:
        people, conflicts = [], []
        n_conflict = n_cards = 0
        for _, questions, answers in pools[domain]:
            losses, conflict_losses = [], []
            for q in questions:
                x = features(q)
                y = float(answers[q['id']] == next(iter(q['options'])))
                rate = source_green if x[1]>0 else 1-source_green if x[1]<0 else .5
                p = np.asarray([.5, rate, expit(x @ beta)])
                loss = 2*(p-y)**2
                losses.append(loss)
                n_cards += 1
                if x[0]*x[1]<0:
                    n_conflict += 1
                    conflict_losses.append(loss)
            people.append(np.mean(losses, axis=0))
            if conflict_losses:
                conflicts.append(np.mean(conflict_losses, axis=0))
        out['targets'][domain] = {
            'people':len(people), 'cards':n_cards, 'conflict_people':len(conflicts),
            'conflict_cards':n_conflict,
            'brier':dict(zip(methods,np.mean(people,axis=0).tolist())),
            'conflict_brier':dict(zip(methods,np.mean(conflicts,axis=0).tolist())),
            'over_source_rate':improvement_interval(people),
            'conflict_over_source_rate':improvement_interval(conflicts),
        }
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze','run','score','population'])
    args = parser.parse_args()
    frozen = freeze() if args.action=='freeze' else read(RUN/'frozen.json')
    if args.action=='run':
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(partial(send, directory=RUN), frozen['jobs']))
    if args.action=='score':
        print(json.dumps(score(frozen),indent=2))
    elif args.action=='population':
        print(json.dumps(population(frozen),indent=2))
    else:
        print(json.dumps({k:v for k,v in frozen.items() if k not in ('answers','jobs')},indent=2))
