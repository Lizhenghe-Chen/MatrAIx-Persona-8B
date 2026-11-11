"""Frozen, bounded two-observation exploratory experiment; no prompt selection."""
import argparse
from collections import Counter, defaultdict
import copy
import json
import os
from pathlib import Path
import random
import sqlite3

from ..core.core import digest, request_payload, validate
from ..core.choice_history import card_key, observation, text_observation, checked_history
from ..core.provider import build_request
from ..core.runner import run
from ..ops.retry_failed import retry
from .persona_mapping import common_background

ROOT = Path.home()/'.local/share/matraix-decision-lab'
OUT = ROOT/'choice-history-v2'
KINDS = {'dryer': 'dryer-text-v1', 'swiss': 'swiss-appliances-v1'}
ARMS = ('background', 'own', 'other')
SEED = 20261109


def read(p):
    return json.loads(Path(p).read_text())


def private_write(p, data):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(p, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def quotas(counts, n):
    if sum(counts.values()) < n:
        raise ValueError('Insufficient eligible people; do not shrink silently')
    exact = {k: n*v/sum(counts.values()) for k,v in counts.items()}
    q = {k: int(v) for k,v in exact.items()}
    for k in sorted(q, key=lambda k: (-(exact[k]-q[k]), k))[:n-sum(q.values())]:
        q[k] += 1
    return q


def choose_rows(rows, kind, sample_size=48):
    """No outcomes inspected: select distinct designs, then assign known/target roles."""
    people = defaultdict(list)
    for row in rows:
        people[row['person']].append(row)
    designs = {}; cells = {}; excluded = Counter()
    for person, items in sorted(people.items()):
        bg = common_background(items[0]['background'], kind)
        if bg is None:
            excluded['unmappable_age_or_education'] += 1; continue
        shuffled = sorted(items, key=lambda r: str(r['task']))
        random.Random(digest([SEED, kind, person, 'tasks'])).shuffle(shuffled)
        distinct = []; seen = set()
        for row in shuffled:
            key = card_key(row)
            if key not in seen:
                distinct.append(row); seen.add(key)
        if len(distinct) < 4:
            excluded['fewer_than_four_distinct_cards'] += 1; continue
        designs[person] = {'known': distinct[:2], 'targets': distinct[2:4]}
        age = '65+' if bg['age_bracket'] in ('65-74','75-84','85+') else '18-64'
        cells[person] = (items[0]['stratum'], age, bg['education_group'])
    donors = {}
    for person, design in designs.items():
        target_keys = {card_key(r) for r in design['targets']}
        own_content = digest([observation(r) for r in design['known']])
        candidates = [p for p in designs if p != person and cells[p] == cells[person]
                      and not target_keys.intersection(card_key(r) for r in designs[p]['known'])
                      and digest([observation(r) for r in designs[p]['known']]) != own_content]
        if not candidates:
            excluded['no_eligible_donor'] += 1; continue
        candidates.sort()
        donors[person] = random.Random(digest([SEED, kind, person, 'donor'])).choice(candidates)
    eligible = defaultdict(list)
    for person in donors:
        eligible[cells[person][0]].append(person)
    counts = {k: len(v) for k,v in eligible.items()}
    allocation = quotas(counts, sample_size)
    main = []; remaining = []
    for stratum, ids in sorted(eligible.items()):
        ids = sorted(ids); random.Random(digest([SEED,kind,stratum,'sample'])).shuffle(ids)
        main.extend(ids[:allocation[stratum]]); remaining.extend(ids[allocation[stratum]:])
    random.Random(digest([SEED,kind,'pilot'])).shuffle(remaining)
    if len(remaining) < 4: raise ValueError('Insufficient separate pilot people')
    pilot = remaining[:4]
    return designs, donors, cells, main, pilot, {
        'development_people': len(people), 'eligible_people': len(donors),
        'excluded': dict(excluded), 'eligible_strata': counts,
        'evaluation_quota': allocation, 'pilot_people': len(pilot)}


def prepare(people=48, total_cap=660):
    aborted = read(ROOT/"choice-history-v1/INVALIDATED.json")
    remaining_calls = total_cap-aborted["attempts"]
    remaining_budget = 10-aborted["reserved_usd"]
    OUT.mkdir(mode=0o700, parents=True, exist_ok=True)
    if (OUT/'experiment-seal.json').exists(): raise ValueError('Already frozen; do not overwrite')
    all_rows = []; mappings = {}; coverage = {}; sources = {}; cfg = None
    for kind, folder in KINDS.items():
        src = ROOT/folder/'formal-v1'
        study = read(src/'rich_development-study.json')
        seal = read(src/'rich_development-seal.json')
        config = read(src/'rich_development-config.json')
        if digest(study) != seal['input_sha256'] or digest(config) != seal['config_sha256']:
            raise ValueError('Historical development freeze mismatch')
        if not all(study['audit'].values()): raise ValueError('Missing admission review')
        rows = [r for r in study['rows'] if seal['assignments'][r['person']]=='development']
        designs, donors, cells, main, pilot, cov = choose_rows(rows, kind, people)
        coverage[kind] = cov
        sources[kind] = {'study_sha256':digest(study), 'seal_sha256':digest(seal)}
        mappings[kind] = {'main': main, 'pilot': pilot, 'people': {}}
        if cfg is None: cfg = copy.deepcopy(config)
        elif cfg['expected_identity'] != config['expected_identity']:
            raise ValueError('Historical model identities differ')
        for stage, selected in [('pilot',pilot),('evaluation',main)]:
            for person in selected:
                design = designs[person]; donor = donors[person]
                mappings[kind]['people'][person] = {
                    'donor':donor, 'cell':cells[person],
                    'known_tasks':[r['task'] for r in design['known']],
                    'target_tasks':[r['task'] for r in design['targets']],
                    'donor_tasks':[r['task'] for r in designs[donor]['known']]}
                for target in design['targets'][:1 if stage=='pilot' else 2]:
                    order = list(ARMS)
                    random.Random(digest([SEED,kind,person,target['task'],'arms'])).shuffle(order)
                    for arm in order:
                        history = [] if arm=='background' else [text_observation(r) for r in designs[person if arm=='own' else donor]['known']]
                        row = copy.deepcopy(target)
                        row['background'] = {f:target['background'].get(f,'unknown') for f in config['background_fields']}
                        row.update(person=kind+':'+person, task=str(target['task'])+'::'+arm,
                                   target_person=person, target_task=target['task'],
                                   kind=kind, stage=stage, arm=arm, known_choices=history)
                        checked_history(history, target)
                        all_rows.append(row)
    # Pilot first; interleave studies at the respondent/task block level.
    blocks = defaultdict(list)
    for row in all_rows:
        blocks[(row['stage'],row['kind'],row['person'],row['target_task'])].append(row)
    ordered = []
    for stage in ('pilot','evaluation'):
        keys = sorted([k for k in blocks if k[0]==stage], key=str)
        random.Random(digest([SEED,stage,'block_order'])).shuffle(keys)
        ordered.extend(r for k in keys for r in blocks[k])
    all_rows = ordered
    cfg.update(include_choice_history=True, known_choice_encoding='selected_product_text', background_fields=sorted({f for r in all_rows for f in r['background']}),
               max_calls=min(660,remaining_calls), max_cost_usd=remaining_budget, documentation_checked_on='2026-11-11')
    # Per-study background fields: prevent other-study unknown placeholders appearing in payloads.
    cfg['background_fields_by_kind'] = {kind:read(ROOT/folder/'formal-v1/rich_development-config.json')['background_fields'] for kind,folder in KINDS.items()}
    study = {'study':'choice-history-v2', 'status':'exploratory_frozen',
             'audit':{k:True for k in ('license_cloud_use','question_mapping','background_timing','author_statistics','leakage_review')},
             'rows':all_rows}
    validate(all_rows)
    bodies = [build_request(request_payload(r,cfg),cfg) for r in all_rows]
    bounds = [((len(json.dumps(b,ensure_ascii=False).encode())+1024)*cfg['input_usd_per_million']+cfg['max_tokens']*cfg['output_usd_per_million'])/1e6 for b in bodies]
    if len(all_rows)!=24+12*people or len(all_rows)>cfg['max_calls'] or sum(bounds)>remaining_budget: raise ValueError('Call or conservative budget limit exceeded before running')
    protocol = {'seed':SEED, 'scope':'Exploratory reuse of previous development data; not independent confirmation',
                'model':cfg['model'], 'expected_identity':cfg['expected_identity'], 'sources':sources,
                'coverage':coverage, 'calls':{'pilot':24,'evaluation':12*people,'people_per_study':people,'maximum_attempts':cfg['max_calls'],'global_maximum_attempts':total_cap},
                'budget_usd':10, 'remaining_budget_usd':remaining_budget, 'aborted_run':aborted, 'known_choice_encoding':'selected_product_text', 'planned_conservative_reservation_usd':sum(bounds),
                'prompt_sha256':digest(bodies[0]['messages'][0]),
                'selection':'Largest-remainder proportional quota among eligible people; seeded task sampling without outcome-based selection',
                'donors':'Same original stratum, 18–64/65+, below bachelor/bachelor+. Same source development pool; donors may recur. Full distinct records, no target cards.',
                'screening_gate':'Both studies own vs background relative Brier improvement >=2%, and own Brier < other. Intervals crossing zero mean tentative lead only.',
                'bootstrap':'2000 paired respondent resamples within original study strata; fixed assigned observations/donors',
                'retry_policy':'At most one explicit retry per failed job; no identity/auth/pending retries; all reservations and attempts count toward global caps',
                'known_vs_future':'Task split is random, not chronological; no future-purchase claim',
                'statistics':'Frozen train-fitted, development-selected rich baseline; reference only, not equal-information competitor',
                'examples':'First evaluation participant in each study by frozen order; first target, irrespective of outcome',
                'limitations':['Two appliance studies only','Previously used development data','No complete original MatrAIx comparison','Not zero-shot or synthetic-population validation','Donor dependence and model-call noise not separately estimated']}
    seal = {'input_sha256':digest(study),'config_sha256':digest(cfg),
            'assignments':{r['person']:'development' for r in all_rows},'protocol_sha256':digest(protocol)}
    for name,obj in [('experiment-study',study),('experiment-config',cfg),('experiment-seal',seal),('protocol',protocol),('private-map',mappings)]:
        private_write(OUT/(name+'.json'),obj)
    print(json.dumps(protocol, ensure_ascii=False, indent=2))


def execution_summary():
    path = OUT/'experiment.sqlite'
    if not path.exists(): return {'attempts':0,'complete':0,'reserved_usd':0}
    with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as db:
        counts = dict(db.execute('select status,count(*) from calls group by status'))
        retries = db.execute('select count(*) from failed_attempts').fetchone()[0] if db.execute("select 1 from sqlite_master where name='failed_attempts'").fetchone() else 0
        return {'states':counts,'complete':counts.get('complete',0),'attempts':sum(counts.values())+retries,
                'retries':retries,'reserved_usd':db.execute('select coalesce(sum(reserved_usd),0) from calls').fetchone()[0]}


def execute(stage):
    credentials = Path.home()/'.config/matraix-decision-lab/credentials.json'
    os.environ['DEEPSEEK_API_KEY'] = read(credentials)['DEEPSEEK_API_KEY']
    study,config,seal = [read(OUT/('experiment-'+x+'.json')) for x in ('study','config','seal')]
    if stage=='evaluation':
        pilot=read(OUT/'pilot-result.json')
        if pilot['complete_pilot_jobs']!=24 or pilot['projected_upper_usage_usd']>config['max_cost_usd']:
            raise ValueError('Pilot not passed or projected cost too high')
    while True:
        summary=execution_summary()
        if summary['attempts']>=config['max_calls'] or summary['reserved_usd']>=config['max_cost_usd']: break
        if summary.get('states',{}).get('pending'): raise ValueError('Uncertain pending call; no automatic resubmission')
        if summary.get('states',{}).get('failed'):
            with sqlite3.connect(OUT/'experiment.sqlite') as db:
                job,error=db.execute("select job,error from calls where status='failed'").fetchone()
                previous=db.execute('select count(*) from failed_attempts where job=?',(job,)).fetchone()[0] if db.execute("select 1 from sqlite_master where name='failed_attempts'").fetchone() else 0
            if error not in ('invalid_json','probabilities_sum_not_one','unexpected_finish_reasoning_or_tools') or previous:
                raise RuntimeError('Execution stopped for inspected failure: '+str(error))
            print(json.dumps(retry(OUT,'experiment',credentials)),flush=True)
        limit = 24-execution_summary()['complete'] if stage=='pilot' else 30
        if limit<=0: break
        try: result=run(study,seal,config,OUT/'experiment.sqlite','development',max_new_calls=limit)
        except RuntimeError:
            print(json.dumps(execution_summary()),flush=True); continue
        print(json.dumps(execution_summary()),flush=True)
        if result['complete'] or (stage=='pilot' and execution_summary()['complete']>=24):break
        if result['stop_reason']!='batch_limit':break
    summary=execution_summary()
    if stage=='pilot' and summary['complete']==24:
        with sqlite3.connect(OUT/'experiment.sqlite') as db:
            responses=[json.loads(x[0]) for x in db.execute("select response from calls where status='complete'")]
        usage_cost=sum((r['usage'].get('prompt_tokens',0)*1.32+r['usage'].get('completion_tokens',0)*3.96)/1e6 for r in responses)
        identities={digest(r['identity']) for r in responses}
        if len(identities)!=1:raise ValueError('Pilot identity differs')
        result={'complete_pilot_jobs':24,'identity':responses[0]['identity'],
                'pilot_peak_no_cache_usage_estimate_usd':usage_cost,
                'projected_upper_usage_usd':usage_cost/24*config['max_calls'],
                'planned_conservative_reservation_usd':read(OUT/'protocol.json')['planned_conservative_reservation_usd'],
                'execution':summary,'scores_computed':False}
        private_write(OUT/'pilot-result.json',result)
        print(json.dumps(result),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','pilot','evaluation'])
    parser.add_argument('--people',type=int,choices=[16,48],default=48)
    parser.add_argument('--total-cap',type=int,choices=[660,1100],default=660)
    args=parser.parse_args()
    prepare(args.people,args.total_cap) if args.action=='prepare' else execute(args.action)
