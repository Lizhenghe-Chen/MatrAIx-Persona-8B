"""Score only the frozen exploratory evaluation; never tune on its outcomes."""
from collections import Counter, defaultdict
import json
import sqlite3
from pathlib import Path

from ..core.core import digest, brier
from ..core.checkpoint import read_predictions
from .scoring import paired_brier_interval
from .baseline_replay import replay
from ..studies.choice_history import ROOT, OUT, KINDS, ARMS, read, private_write, execution_summary


def evaluate(check=False):
    study,config,seal=[read(OUT/('experiment-'+x+'.json')) for x in ('study','config','seal')]
    protocol=read(OUT/'protocol.json')
    if (OUT/'INVALIDATED.json').exists():raise ValueError('Invalidated run cannot be scored')
    planned_people=protocol['calls']['people_per_study']
    if digest(protocol)!=seal['protocol_sha256']:raise ValueError('Protocol drift')
    observed,pred,missing=read_predictions(study,seal,config,OUT/'experiment.sqlite','development',require_complete=False)
    public={'scope':'exploratory_development_reuse','protocol_sha256':digest(protocol),
            'input_sha256':digest(study),'config_sha256':digest(config),
            'model':config['expected_identity'],'coverage':protocol['coverage'], 'studies':{},
            'execution':execution_summary(), 'examples':{}, 'aborted_run':protocol['aborted_run'], 'planned_people':planned_people, 'global_attempt_cap':protocol['calls']['global_maximum_attempts']}
    private_predictions=[]
    for kind,folder in KINDS.items():
        selected=[r for r in observed if r['kind']==kind and r['stage']=='evaluation']
        completeness={a:sum((r['person'],r['task']) in pred for r in selected if r['arm']==a)/(planned_people*2) for a in ARMS}
        if min(completeness.values())<.98:raise ValueError('Below 98% completion; no effect scoring')
        by_person=defaultdict(list)
        for r in selected:by_person[r['person']].append(r)
        keep={p for p,rs in by_person.items() if len(rs)==6 and all((r['person'],r['task']) in pred for r in rs)}
        prepared=read(ROOT/folder/'prepared.json')
        source={(r['person'],r['task']):r for r in prepared['rows']}
        originals=[]; ps={a:{} for a in ARMS}; seen=set()
        for r in selected:
            if r['person'] not in keep:continue
            key=(r['target_person'],r['target_task'])
            if key not in seen:originals.append(source[key]);seen.add(key)
            for field in ['question','context','options','answer','stratum']:
                if r[field]!=source[key][field]:raise ValueError('Target mapping differs from source')
            ps[r['arm']][key]=pred[(r['person'],r['task'])]
            private_predictions.append({'kind':kind,'person':key[0],'task':key[1],'arm':r['arm'],'probabilities':ps[r['arm']][key]})
        ps['statistics']=replay(prepared,read(ROOT/folder/'baseline-development.json'),originals,kind,'rich')
        summaries={}
        for arm,p in ps.items():
            per_person=defaultdict(list);correct=defaultdict(list);refusal_n=refusal_hits=ties=0
            for r in originals:
                values=p[(r['person'],r['task'])]
                guess=max(range(len(values)),key=values.__getitem__)
                ties+=sum(v==max(values) for v in values)>1
                per_person[r['person']].append(brier(values,r['answer']))
                correct[r['person']].append(int(guess==r['answer']))
                if kind=='dryer' and r['options'][r['answer']]=='Neither':
                    refusal_n+=1;refusal_hits+=guess==r['answer']
            summaries[arm]={'brier':sum(sum(v)/len(v) for v in per_person.values())/len(per_person),
                            'accuracy':sum(sum(v)/len(v) for v in correct.values())/len(correct),
                            'refusal_true_tasks':refusal_n,'refusal_hits':refusal_hits,
                            'refusal_recall':refusal_hits/refusal_n if refusal_n else None,
                            'argmax_ties':ties}
        comparisons={arm:paired_brier_interval(originals,ps[arm],ps['own']) for arm in ['background','other']}
        passed=comparisons['background']['relative_improvement']>=.02 and comparisons['other']['improvement']>0
        public['studies'][kind]={'people':len(keep),'tasks':len(originals),'completion':completeness,
            'excluded_incomplete_people':planned_people-len(keep),'methods':summaries,'comparisons':comparisons,
            'screening_point_gate':passed,
            'both_intervals_positive':all(c['improvement_95_ci'][0]>0 for c in comparisons.values()),
            'failures_by_stratum':dict(Counter(r['stratum'] for r in selected if (r['person'],r['task']) not in pred))}
        # The frozen first case, not a hand-picked success. No identity or demographics exported.
        first=next(r for r in selected if r['arm']=='own')
        key=(first['target_person'],first['target_task'])
        other=next(r for r in selected if (r['target_person'],r['target_task'],r['arm'])==(*key,'other'))
        public['examples'][kind]={'context':first['context'],'question':first['question'],
            'options':first['options'],'actual_choice':first['answer'],
            'own_observations':first['known_choices'],'other_observations':other['known_choices'],
            'predictions':{a:ps[a].get(key) for a in ps},
            'selection':'First participant/target in frozen execution order; not selected for outcome'}
    with sqlite3.connect(f'file:{OUT/"experiment.sqlite"}?mode=ro',uri=True) as db:
        responses=[json.loads(r[0]) for r in db.execute("select response from calls where status='complete'")]
        public['execution']['errors']=dict(db.execute('select error,count(*) from failed_attempts group by error')) if db.execute("select 1 from sqlite_master where name='failed_attempts'").fetchone() else {}
    prompt=sum(r['usage'].get('prompt_tokens',0) for r in responses)
    completion=sum(r['usage'].get('completion_tokens',0) for r in responses)
    public['execution'].update(prompt_tokens=prompt,completion_tokens=completion,
        peak_no_cache_usage_estimate_usd=(prompt*1.32+completion*3.96)/1e6)
    public['recommend_independent_replication']=all(s['screening_point_gate'] for s in public['studies'].values())
    public['all_comparisons_positive_intervals']=all(s['both_intervals_positive'] for s in public['studies'].values())
    if check:
        if read(OUT/'result.json') != public or read(OUT/'scored-predictions.json') != private_predictions:
            raise ValueError('Recomputed result differs from frozen scored outputs')
        if read(Path(__file__).resolve().parents[1]/'reports/choice-history-result.json') != public:
            raise ValueError('Public result differs from private scored output')
        print('Verified all frozen request hashes, probabilities, scores and paired intervals; no API calls.')
        return
    private_write(OUT/'scored-predictions.json',private_predictions)
    private_write(OUT/'result.json',public)
    out=Path(__file__).resolve().parents[1]/'reports/choice-history-result.json'
    if out.exists():raise ValueError('Do not overwrite evaluated result')
    out.write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in public.items() if k in ['studies','execution','recommend_independent_replication']},ensure_ascii=False,indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    evaluate(parser.parse_args().check)
