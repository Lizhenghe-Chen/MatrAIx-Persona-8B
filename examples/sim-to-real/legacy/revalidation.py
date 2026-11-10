"""Frozen internal replication: demographic matching, choice format, models.

Cloud requests are built exclusively from generated synthetic records. Real
product respondents remain local. No target answers enter request builders.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import argparse
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sqlite3
import sys
import time

import httpx
import numpy as np

ROOT = Path(__file__).parent
REPO = ROOT.parents[1]
sys.path.insert(0,str(REPO))
STUDY = ROOT/'study'
OUT = STUDY/'10_匹配与商品复验'
LOCAL = OUT/'本机运行'
SEED = 20261110
REPEATS = 3
N = 240
MODELS = {'qwen':'Qwen/Qwen3.8-27B','pro':'deepseek-v4-pro'}
ARMS = ('coarse','matched','matched_traits')
FIELDS = ('Age group','Education','Gender','Household income')
AGES = ('18–64','65 or older')
EDU = ("Below bachelor's degree","Bachelor's degree or higher")
INCOME = ('Below $100,000','$100,000 or more')
PARAMS = {'temperature':.7,'top_p':1,'max_tokens':1536,'response_format':{'type':'json_object'}}
PREDICT = ('Predict how a respondent with the supplied background would answer at the stated survey date. '
           'Use only the supplied background when relevant. Do not invent unstated personal experiences. '
           'Use only the original options. Return only the requested JSON object.')


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def seed(*parts):
    return int.from_bytes(hashlib.sha256(repr((SEED,parts)).encode()).digest()[:8],'big')


def read(path):
    return json.loads(path.read_text())


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def frozen(path,data):
    data=json.loads(json.dumps(data))
    if path.exists():
        assert read(path)==data, f'Frozen input changed: {path.name}'
    else:
        write(path,data)


def coarse_real(background):
    age = AGES[background['Age group']=='65+'] if background['Age group'] in ('18-29','30-49','50-64','65+') else None
    education = background['Education']
    edu = EDU[education=='College graduate+'] if education in ('H.S. graduate or less','Some college','College graduate+') else None
    gender = {'Male':'Man','Female':'Woman'}.get(background['Sex'])
    inc = background['Income']
    high = ('$150,000 or more','100 to under $150,000 [OR]')
    low = ('Less than $10,000','10 to under $20,000','20 to under $30,000','30 to under $40,000',
           '40 to under $50,000','50 to under $75,000','75 to under $100,000')
    income = INCOME[inc in high] if inc in high+low else None
    known_missing={'Unknown',"(VOL) Don't know/Refused"}
    for field,value in [('Age group',age),('Education',edu),('Sex',gender),('Income',income)]:
        if value is None and background[field] not in known_missing:
            raise ValueError(f'Unmapped nonmissing background label: {field}={background[field]}')
    return dict(zip(FIELDS,(age,edu,gender,income))) if all((age,edu,gender,income)) else None


def cell(background):
    return '|'.join(background[k] for k in FIELDS)


def allocations(masses,n):
    # At least one synthetic case per supported cell, then largest remainders.
    values=np.array(list(masses.values()),float);values/=values.sum()
    raw=values*(n-len(values));counts=np.floor(raw).astype(int)+1
    for i in np.argsort(-(raw-np.floor(raw)),kind='stable')[:n-int(counts.sum())]:
        counts[i]+=1
    assert counts.sum()==n
    return dict(zip(masses,map(int,counts)))


def make_pool():
    from persona.synthesis.sampler import PersonaForwardSampler,SamplingConfig,DEFAULT_GRAPH_PATH
    from experiment import AGE_MAP,EDUCATION_MAP,TRAITS
    sampler=PersonaForwardSampler(DEFAULT_GRAPH_PATH,SamplingConfig(seed=SEED))
    codes=sampler.sample_indices(50000,fixed={'region':'North America'})
    rows=[]
    for i in range(50000):
        values={k:sampler.values[k][codes[k][i]] for k in ('age_bracket','highest_education','gender_identity','demo_household_income',*TRAITS)}
        a=AGE_MAP.get(values['age_bracket']);e=EDUCATION_MAP.get(values['highest_education'])
        if a is None or e is None or values['gender_identity'] not in ('Man','Woman'):
            continue
        background=dict(zip(FIELDS,(AGES[a],EDU[e],values['gender_identity'],INCOME[values['demo_household_income'] in ('$100k-200k','$200k+')])) )
        rows.append({'generated_id':f's-dag-{SEED}-{i:05d}','background':background,
                     'traits':{label:values[k] for k,label in TRAITS.items()}})
    return rows,digest(DEFAULT_GRAPH_PATH)


def prepare():
    from retail_pew import dataset, ITEMS, SOURCE
    from shopping import product_people,split,STRATA as PRODUCT_STRATA
    from data_sources import frozen_code_matches, shopping_sources
    sources=shopping_sources()
    people,options=dataset()
    eligible=[]
    for p in people.values():
        bg=coarse_real(p['background'])
        if bg is not None and len(p['truth'])==len(ITEMS):
            eligible.append({**p,'common_background':bg})
    assert len(eligible)>4000, 'Check codebook labels and complete-case eligibility'
    masses=defaultdict(float);counts=Counter()
    for p in eligible:
        key=cell(p['common_background']);masses[key]+=p['weight'];counts[key]+=1
    masses={k:v/sum(masses.values()) for k,v in sorted(masses.items())}
    assert len(masses)==16 and min(counts.values())>=10
    reference={q:np.average(np.eye(len(options[q]))[[p['truth'][q] for p in eligible]],axis=0,
                            weights=[p['weight'] for p in eligible]).tolist() for q in ITEMS}
    pool,graph_hash=make_pool()
    by_coarse=defaultdict(list);by_cell=defaultdict(list)
    for p in pool:
        key=cell(p['background']);by_coarse['|'.join(key.split('|')[:2])].append(p);by_cell[key].append(p)
    cohorts={'formal':[],'pilot':[]}
    used=set()
    for phase,n in [('formal',60),('pilot',3)]:
        for age in AGES:
            for edu in EDU:
                coarse=f'{age}|{edu}'
                target={k:v for k,v in masses.items() if k.startswith(coarse+'|')}
                if phase=='pilot':
                    # Pilot only checks format; cycle three of four cells.
                    counts_by_cell={k:int(i<n) for i,k in enumerate(target)}
                else:
                    counts_by_cell=allocations(target,n)
                coarse_members=[p for p in by_coarse[coarse] if p['generated_id'] not in used]
                coarse_sample=random.Random(seed(phase,coarse,'coarse')).sample(coarse_members,n)
                used.update(p['generated_id'] for p in coarse_sample)
                cursor=0
                for key,amount in counts_by_cell.items():
                    members=[p for p in by_cell[key] if p['generated_id'] not in used]
                    assert len(members)>=amount, f'Insufficient synthetic support: {key}'
                    matched=random.Random(seed(phase,key,'matched')).sample(members,amount)
                    used.update(p['generated_id'] for p in matched)
                    for p in matched:
                        row={'id':f's-{phase}-{len(cohorts[phase]):04d}','analysis_cell':key,
                             'weight':masses[key]/amount,'coarse':coarse_sample[cursor], 'matched':p}
                        cursor+=1;cohorts[phase].append(row)
    assert len(cohorts['formal'])==N
    # Every arm receives the exact same fixed analysis-slot weights. Only
    # generated profile selection differs; there is no person-level linkage.
    total=sum(r['weight'] for r in cohorts['formal']);assert abs(total-1)<1e-9
    for r in cohorts['formal']:
        assert cell(r['matched']['background'])==r['analysis_cell']
        assert list(r['coarse']['background'].values())[:2]==list(r['matched']['background'].values())[:2]
    products={};overlap={}
    for survey in ('origin','packaging'):
        persons=product_people(sources[f'{survey}.csv'],survey)
        ds=split(persons,survey)
        saved=read(STUDY/'06_北美电商选品/sample-index.json')[survey]
        assert all([r['id'] for r in ds[k]]==saved[k] for k in ds)
        # Reuse the old fixed test set intentionally; this is a format ablation,
        # not a newly untouched population. Statistical training stays disjoint.
        product_pilot=[p for s in PRODUCT_STRATA for p in [r for r in ds['pilot'] if r['stratum']==s][:2]]
        products[survey]={'formal':ds['formal'],'pilot':product_pilot,
                          'training':ds['training'],'pool':persons}
        overlap[survey]={'prior_evaluation_people_reused':len(ds['formal']),
                         'formal_training_overlap':len(set(saved['formal'])&set(saved['training']))}
    data={'seed':SEED,'repeats':REPEATS,'questions':ITEMS,'options':options,
          'reference':reference,'cohorts':cohorts,'products':products}
    protocol={'date':'2026-11-10','revision':2,'status':'Mapping corrected before outcome analysis; reuse earlier responses only if full request hashes match',
              'purpose':'Internal replication; these public data have already informed earlier analyses. No fresh external validation claim.',
              'matching':{'human_eligible':len(eligible),'source_network_n':len(people),'complete_cases_and_common_fields_required':True,
                          'source_cell_n':dict(counts),'weighted_cell_mass':masses,'fields':FIELDS,
                          'income_mapping':'Only the shared $100,000 boundary; do not infer finer incomes',
                          'gender_mapping':'Source binary sex labels mapped to Man/Woman for this operational comparison; not a claim about gender identity',
                          'region':'Native North America pinned; common US survey context. No US subregion matching.',
                          'formal_synthetic_slots':N,'pilot_slots':12,'arms':ARMS,'models':MODELS,
                          'same_slot_weights_in_all_arms':True,
                          'cloud_boundary':'Only native DAG records plus public questions. Aggregate demographic quotas, no individual source profiles, IDs or answers.',
                          'graph_sha256':graph_hash,'pool_n':50000},
              'products':{'surveys':['origin','packaging'],'people_per_survey':N,'model':'qwen',
                          'arms':['choice','probability'],'background':'Identical original P1+B3 respondent background',
                          'prior_overlap':overlap,'pilot_per_survey':8},
              'repeats':REPEATS,'parameters':PARAMS,'thinking':False,
              'probability_decoder':'Reject out-of-range values or absolute sum error > 0.02; normalize accepted rounding errors to sum 1',
              'formal_requests':N*REPEATS*(len(ARMS)*len(MODELS)+2*2),
              'pilot_requests':12*len(ARMS)*len(MODELS)+8*2*2,
              'scoring':{'matching':'13 question TV errors averaged equally; fixed human reference. No individual accuracy for synthetic profiles.',
                         'origin':'Four original attribute-choice proportion errors equally averaged',
                         'packaging':'16 card-level A/B/neither TV errors equally averaged; opt-out recall and Brier reported separately',
                         'replicates':'Score each generation repetition and the averaged probabilities; show all three, no best-run selection',
                         'bootstrap':'2000 samples, respondents clustered for products; fixed demographic cells for synthesis. Coarse versus matched cohorts resampled independently; same synthetic cohort paired across models and trait conditions.',
                         'uncertainty':'Intervals conditional on three generated repetitions and fixed reference; not full survey-design or deployment uncertainty',
                         'adoption':'Gain >= 2pp and bootstrap lower bound > 0 and positive gain in all three repetitions; tasks reported separately',
                         'completion':'>=98% in every cell and repetition, comparisons on common completed IDs; never route real profiles to cloud'},
              'source_sha256':{'pew13':digest(SOURCE),**{s:digest(sources[f'{s}.csv']) for s in ('origin','packaging')}},
              'runner_sha256':digest(Path(__file__))}
    frozen(LOCAL/'freeze.json',data)
    protocol_path=OUT/'protocol.json'
    if protocol_path.exists():
        previous=read(protocol_path)['runner_sha256']
        if frozen_code_matches('revalidation.py',previous,protocol['runner_sha256']):
            protocol['runner_sha256']=previous
    frozen(protocol_path,protocol)
    frozen(OUT/'synthetic-cohorts.json',cohorts)
    print(json.dumps({'frozen':True,'human_reference_n':len(eligible),'formal_requests':protocol['formal_requests'],
                      'pilot_requests':protocol['pilot_requests'],'minimum_reference_cell':min(counts.values())}))


def synthetic_request(data,slot,arm):
    p=slot['coarse'] if arm=='coarse' else slot['matched']
    assert p['generated_id'].startswith('s-dag-')
    background=dict(p['background'])
    if arm=='matched_traits':background.update(p['traits'])
    system='United States, November–December 2015. '+PREDICT+'\n'+'\n'.join(f'{k}: {v}' for k,v in background.items())
    questions=list(data['questions'])
    rng=random.Random(seed(slot['id'],'question-order'))
    for start,stop in [(0,7),(7,10),(11,13)]:
        group=questions[start:stop];rng.shuffle(group);questions[start:stop]=group
    mapping={};lines=[]
    for i,q in enumerate(questions,1):
        mapping[str(i)]=(q,list(range(len(data['options'][q]))))
        lines.append(f'{i}. {data["questions"][q]}\n'+' | '.join(f'{j+1}. {v}' for j,v in enumerate(data['options'][q])))
    instruction='For each question number return an array of option probabilities in displayed order, summing to 1. Return JSON only.'
    return system,instruction+'\n'+'\n'.join(lines),mapping


def product_request(survey,person,arm):
    from shopping import prompt
    job,old_mapping=prompt(survey,person,'P1+B3')
    # Preserve the original choice cards, context and system prompt verbatim.
    old='For each item, return its option ID. Output JSON only, e.g. {"answers":{"q1":"1"}}. Include exactly one value for each item.'
    assert old in job['user']
    instruction=('Return JSON keyed by question ID with one displayed option ID per question.' if arm=='choice' else
                 'Return JSON keyed by question ID with an array of probabilities in displayed option order, summing to 1 for each question.')
    mapping={}
    for i,t in enumerate(person['tasks'],1):
        k=f'q{i}';display=list(t['codes'])
        mapping[k]=(t['id'],[list(t['codes']).index(old_mapping[k][code]) for code in display])
    return job['system'],job['user'].replace(old,instruction),mapping


def decode(content,mapping,probability):
    raw=json.loads(content)
    if set(raw)!=set(mapping):raise ValueError('question keys mismatch')
    result={}
    for key,(qid,order) in mapping.items():
        value=raw[key]
        if probability:
            if not isinstance(value,list) or len(value)!=len(order):raise ValueError('probability shape')
            if any(type(v) not in (float,int) or not math.isfinite(v) or v<0 or v>1 for v in value):raise ValueError('probability bounds')
            if abs(sum(value)-1)>.02:raise ValueError('probability sum')
            value=np.array(value,float)/sum(value)
        else:
            # Product displayed labels are 1,2,0; not zero-based positions.
            code=str(value);labels=['1','2']+(['0'] if len(order)==3 else [])
            if code not in labels:raise ValueError('illegal choice')
            value=np.eye(len(order))[labels.index(code)]
        out=np.zeros(len(order))
        for displayed,original in enumerate(order):out[original]=value[displayed]
        result[qid]=out.tolist()
    return result


def jobs(data,phase):
    repeats=range(REPEATS) if phase=='formal' else range(1)
    for slot in data['cohorts'][phase]:
        for model in MODELS:
            for arm in ARMS:
                system,user,mapping=synthetic_request(data,slot,arm)
                for repeat in repeats:
                    yield {'task':'matching','id':slot['id'],'model':model,'arm':arm,'repeat':repeat,
                           'system':system,'user':user,'mapping':mapping,'probability':True,'human':False}
    for survey,ds in data['products'].items():
        for i,p in enumerate(ds[phase]):
            for arm in ('choice','probability'):
                system,user,mapping=product_request(survey,p,arm)
                for repeat in repeats:
                    yield {'task':survey,'id':f'p-{phase}-{i:04d}','model':'qwen','arm':arm,'repeat':repeat,
                           'system':system,'user':user,'mapping':mapping,'probability':arm=='probability','human':True}


def preflight(data):
    for survey,ds in data['products'].items():
        assert not {p['id'] for p in ds['formal']} & {p['id'] for p in ds['training']}
        for p in ds['formal']+ds['pilot']:
            changed=deepcopy(p);changed['weight']=98765
            for t in changed['tasks']:t['truth']='CANARY_TARGET'
            for arm in ('choice','probability'):
                a=product_request(survey,p,arm)
                assert a==product_request(survey,changed,arm)
                assert p['id'] not in a[0]+a[1]
                # A displayed answer must always map back to the original item.
                for i,t in enumerate(p['tasks'],1):
                    k=f'q{i}';order=a[2][k][1]
                    assert sorted(order)==list(range(len(t['codes'])))
    for phase in ('pilot','formal'):
        for j in jobs(data,phase):
            assert j['model']=='qwen' or not j['human']
            assert j['id'] not in j['system']+j['user']
            assert 'CANARY_TARGET' not in j['user']
    return {'target_and_weight_input_invariance':True,'real_profiles_local_only':True,
            'original_product_id_not_in_requests':True,'display_mapping_valid':True,
            'same_analysis_weights_all_synthetic_arms':True}


def key(job):
    return '|'.join(str(job[k]) for k in ('task','id','model','arm','repeat'))


def request_body(job):
    if job['human'] and job['model']!='qwen':raise ValueError('Real respondent cloud request prohibited')
    body={**PARAMS,'model':MODELS[job['model']], 'messages':[{'role':'system','content':job['system']},{'role':'user','content':job['user']}]}
    if job['model']=='qwen':body['chat_template_kwargs']={'enable_thinking':False}
    else:body['thinking']={'type':'disabled'}
    return body


async def run(phase,only,credentials):
    data=read(LOCAL/'freeze.json');protocol=read(OUT/'protocol.json')
    from data_sources import frozen_code_matches
    assert frozen_code_matches('revalidation.py',protocol['runner_sha256'],digest(Path(__file__))),'Runner changed after freeze'
    checked=preflight(data);write(OUT/'input-checks.json',checked)
    secrets=read(Path(credentials)) if credentials else {}
    provider_key=os.environ.get('DEEPSEEK_API_KEY') or secrets.get('DEEPSEEK_API_KEY')
    if only in ('all','pro') and not provider_key:raise ValueError('DeepSeek credential missing')
    db=sqlite3.connect(LOCAL/'responses.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS responses (phase TEXT, job TEXT, task TEXT, model TEXT, arm TEXT, repetition INT, subject TEXT, output TEXT, errors TEXT, request_hash TEXT, elapsed REAL, usage TEXT, PRIMARY KEY(phase,job))')
    done={k for k, in db.execute('SELECT job FROM responses WHERE phase=? AND output IS NOT NULL',(phase,))}
    if phase=='formal':
        pilot=list(jobs(data,'pilot'))
        needed=[j for j in pilot if only=='all' or j['model']==only]
        valid={k for k, in db.execute("SELECT job FROM responses WHERE phase='pilot' AND output IS NOT NULL")}
        assert all(key(j) in valid for j in needed),'All selected endpoint pilot jobs must pass before formal run'
    limits={'qwen':asyncio.Semaphore(16),'pro':asyncio.Semaphore(12)}
    selected=[j for j in jobs(data,phase) if (only=='all' or j['model']==only) and key(j) not in done]
    for j in jobs(data,phase):
        if key(j) in done:
            saved_hash=db.execute('SELECT request_hash FROM responses WHERE phase=? AND job=?',(phase,key(j))).fetchone()[0]
            assert saved_hash==hashlib.sha256(json.dumps(request_body(j),sort_keys=True).encode()).hexdigest(),'Cached request changed'
    total=len(selected);complete=0;errors_count=0;started=time.monotonic()
    print(json.dumps({'phase':phase,'provider':only,'pending':total}),flush=True)
    async with httpx.AsyncClient(timeout=120,trust_env=False,limits=httpx.Limits(max_connections=40,max_keepalive_connections=32)) as client:
        async def one(j):
            nonlocal complete,errors_count
            if j['human'] and j['model']!='qwen':raise ValueError('Real respondent cloud request prohibited')
            body=request_body(j)
            if j['model']=='qwen':
                url='http://10.120.47.101:8000/v1/chat/completions';headers={}
                body['chat_template_kwargs']={'enable_thinking':False}
            else:
                url='https://api.deepseek.com/chat/completions';headers={'Authorization':'Bearer '+provider_key}
                body['thinking']={'type':'disabled'}
            request_hash=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
            previous=db.execute('SELECT errors FROM responses WHERE phase=? AND job=?',(phase,key(j))).fetchone()
            output=None;failures=json.loads(previous[0]) if previous else [];usage={};t0=time.monotonic()
            async with limits[j['model']]:
                for attempt in range(3):
                    try:
                        response=await client.post(url,headers=headers,json=body)
                        response.raise_for_status();obj=response.json();choice=obj['choices'][0];msg=choice['message']
                        if obj['model']!=MODELS[j['model']] or choice['finish_reason']!='stop' or msg.get('reasoning_content') or msg.get('reasoning'):
                            raise ValueError('model or non-thinking protocol mismatch')
                        output=decode(msg['content'],j['mapping'],j['probability']);usage=obj.get('usage',{});break
                    except (httpx.HTTPError,ValueError,KeyError,TypeError,IndexError) as error:
                        status=error.response.status_code if isinstance(error,httpx.HTTPStatusError) else None
                        failures.append({'type':type(error).__name__,'status':status,
                                         'detail':str(error)[:120] if type(error) is ValueError else None})
                        if status in (401,403,404):break
                        await asyncio.sleep(attempt+1)
                complete+=1;errors_count+=output is None
                db.execute('INSERT OR REPLACE INTO responses VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                           (phase,key(j),j['task'],j['model'],j['arm'],j['repeat'],j['id'],
                            json.dumps(output) if output is not None else None,json.dumps(failures),request_hash,
                            time.monotonic()-t0,json.dumps(usage)))
                db.commit()
                if complete%25==0 or complete==total:
                    print(json.dumps({'phase':phase,'provider':only,'completed':complete,'pending_total':total,
                                      'failed_jobs':errors_count,'elapsed_seconds':round(time.monotonic()-started)}),flush=True)
        await asyncio.gather(*(one(j) for j in selected))
    db.close()
    if errors_count:print('Some requests failed; retain checkpoints and rerun the same command.',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','pilot','formal']);p.add_argument('--only',choices=['all','qwen','pro'],default='all');p.add_argument('--credentials')
    args=p.parse_args()
    if args.action=='prepare':prepare()
    else:asyncio.run(run(args.action,args.only,args.credentials))
