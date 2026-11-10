"""Read-only audit and weighting sensitivity analysis; never calls an LLM.

Writes aggregate evidence only. Frozen answers, scores, and local respondent
records remain untouched. Run with the experiment's pyreadstat/pyreadr deps.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
from zipfile import ZipFile

import numpy as np

from experiment import ITEMS, STRATA, SEED, human_reference, stable_seed
from optimize import draw
from optimize_profiles import read_people

ROOT = Path(__file__).parent
STUDY = ROOT / "study"
OUT = STUDY / "09_方法审查"
REPS = 2000


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def close(actual, expected):
    if isinstance(actual, dict):
        assert actual.keys() == expected.keys()
        for k in actual:
            close(actual[k], expected[k])
    elif isinstance(actual, list):
        assert len(actual) == len(expected)
        for x, y in zip(actual, expected):
            close(x, y)
    elif isinstance(actual, (float, int)):
        assert np.isclose(actual, expected, rtol=1e-11, atol=1e-9), (actual, expected)
    else:
        assert actual == expected


def trials(folder):
    with sqlite3.connect(f"file:{folder / 'checkpoints.sqlite'}?mode=ro", uri=True) as db:
        return [json.loads(p) for (p,) in db.execute(
            "SELECT payload FROM trials WHERE stage='formal' AND ok=1")]


def verify_sources():
    checked = {}
    for folder in ('02_模型对比', '03_提示与背景'):
        manifest = read(STUDY/folder/'manifest.json')
        for name, checksum in manifest['inputs'].items():
            assert sha(STUDY/name) == checksum
        audit = read(STUDY/folder/'input-audit.json')
        for name in ('experiment.py','instruments.py','optimize.py','optimize_profiles.py'):
            assert sha(ROOT/name) == audit['source_hashes'][name]
        # Score/report code had a separately recorded analysis revision;
        # do not compare it to the older input-preflight code revision.
        analysis = read(STUDY/folder/'analysis-source-sha256.json')
        assert sha(ROOT/'optimize_score.py') == analysis['optimize_score.py']
        checked[folder] = {'original_input_files_and_profile_code_verified':True,
                           'scoring_code_matches_recorded_analysis_revision':True}
    return checked


def cohort_audit():
    cohort = read(STUDY / "01_首轮归档/cohort.json")
    refs = read(STUDY / "01_首轮归档/reference.json")
    for survey in ITEMS:
        close(human_reference(survey, STUDY / f"数据/{survey}.zip"), refs[survey])
    first = []
    with ZipFile(STUDY / "01_首轮归档/formal-trials.zip") as z:
        for name in z.namelist():
            if name.endswith('.json'):
                r = json.loads(z.read(name))
                if 'answers' in r:
                    first.append({**r, 'condition': r['arm']})
    subset = draw(cohort['formal'], 60, 'model-comparison')
    indices = read(STUDY / '02_模型对比/sample-index.json')
    assert all(set(ids) == {r['id'] for r in subset} for ids in indices.values())
    output = {'source': cohort['source'], 'pins': cohort['pins'],
              'source_reference_reproduced': True,
              'raw_formal_counts': dict(Counter(r['stratum'] for r in cohort['formal'])),
              'model_subset_counts': dict(Counter(r['stratum'] for r in subset)),
              'target_stratum_pct': {s: {k: 100*v for k, v in r['stratum_weight'].items()}
                                     for s, r in refs.items()}, 'rounds': {}}
    for name, rows, participants in [('first', first, cohort['formal']),
                                     ('models', trials(STUDY/'02_模型对比'), subset)]:
        by = {(r['survey'], r['condition'], r['id']): r['answers'] for r in rows}
        conditions = sorted({r['condition'] for r in rows})
        ids = [[r['id'] for r in participants if r['stratum'] == s] for s in STRATA]
        if name == 'models':
            ids = [sorted(group) for group in ids]
        assert len(by) == len(participants) * len(conditions) * len(ITEMS)
        rng = np.random.default_rng(SEED)
        draws = []
        for group in ids:
            sampler = np.random.default_rng(stable_seed(SEED, tuple(group))) if name == 'models' else rng
            draws.append(np.vstack([np.ones(len(group)), sampler.multinomial(
                len(group), np.full(len(group), 1/len(group)), REPS)]) / len(group))
        published = read(STUDY / ('01_首轮归档/results.json' if name == 'first' else '02_模型对比/results.json'))
        result, error_draws, verified = {}, {}, []
        for survey, items in ITEMS.items():
            result[survey], error_draws[survey] = {}, {}
            for condition in conditions:
                variants = defaultdict(list)
                details = {}
                for item, (_, options) in items.items():
                    codes = list(map(str, options))
                    ref = refs[survey]
                    human = np.average([[ref['items'][item][s]['distribution'][k] for k in codes] for s in STRATA],
                                       axis=0, weights=[ref['items'][item][s]['weight'] for s in STRATA])
                    distributions = np.stack([d @ np.array([[by[survey, condition, i][item] == k for k in codes] for i in group])
                                              for group, d in zip(ids, draws)], axis=1)
                    masses = [ref['stratum_weight'][s] for s in STRATA]
                    weights = {'original': [1]*4 if condition.endswith('A') else masses,
                               'common_population_weight': masses,
                               'common_valid_item_weight': [ref['items'][item][s]['weight'] for s in STRATA]}
                    for mode, w in weights.items():
                        simulated = np.average(distributions, axis=1, weights=w)
                        variants[mode].append(50*abs(simulated-human).sum(axis=1))
                    old = (next(r for r in published['items'] if r['survey']==survey and r['item']==item and r['group']=='overall')['error_pp'][condition]
                           if name == 'first' else published['surveys'][survey][condition]['items'][item]['tv_pp'])
                    verified.append(abs(old-variants['original'][-1][0]))
                    details[item] = {mode: float(values[-1][0]) for mode, values in variants.items()}
                errors = {mode: np.mean(values, axis=0) for mode, values in variants.items()}
                error_draws[survey][condition] = errors
                result[survey][condition] = {'mean_tv_pp': {k: float(v[0]) for k,v in errors.items()}, 'items': details}
        overall = {c: {mode: float(np.mean([error_draws[s][c][mode][0] for s in ITEMS]))
                       for mode in error_draws['shed'][c]} for c in conditions}
        pairs = [('A', 'B'), ('B','C')] if name == 'first' else [(f'{m}-{a}',f'{m}-{b}') for m in ('flash','pro','qwen') for a,b in [('A','B'),('B','C')]]
        comparisons = []
        for before, after in pairs:
            row = {'before':before,'after':after,'methods':{}}
            for mode in overall[before]:
                changes = {s:error_draws[s][before][mode]-error_draws[s][after][mode] for s in ITEMS}
                gain = np.mean(list(changes.values()),axis=0)
                per_survey = {s:{'gain_pp':float(d[0]),'ci95':np.quantile(d[1:],[.025,.975]).tolist()} for s,d in changes.items()}
                bounds=np.quantile(gain[1:],[.025,.975]).tolist()
                row['methods'][mode] = {'gain_pp':float(gain[0]),'ci95':bounds,'surveys':per_survey,
                    'optimization_threshold':bool(gain[0]>=2 and bounds[0]>0
                        and sum(v['gain_pp']>0 for v in per_survey.values())>=2
                        and all(v['ci95'][1]>=0 for v in per_survey.values()))}
                if name=='models' and mode=='original':
                    prior=next(r for r in published['comparisons'] if r['reference']==before and r['candidate']==after)
                    close(bounds,prior['overall']['ci95'])
            comparisons.append(row)
        assert max(verified) < 1e-8
        output['rounds'][name] = {'answer_sheets':len(rows),'item_scores_recomputed':len(verified),
                                 'max_original_score_difference_pp':max(verified), 'overall':overall,
                                 'surveys':result,'comparisons':comparisons}
    return output


def real_profile_audit():
    saved = read(STUDY/'03_提示与背景/sample-index.json')
    published = read(STUDY/'03_提示与背景/results.json')
    refs = read(STUDY/'01_首轮归档/reference.json')
    dag = read(STUDY/'01_首轮归档/cohort.json')['formal']
    raw = trials(STUDY/'03_提示与背景')
    predictions = {(r['survey'],r['condition'],r['id']):r['answers'] for r in raw}
    result = {}
    for survey in ITEMS:
        people = read_people(STUDY,survey)
        formal = draw(people,60,survey,'respondents')
        selected = {p['id'] for p in formal}
        assert selected == set(saved[survey]['formal'])
        assert not selected.intersection(saved[survey]['pilot'])
        traits = draw(dag,60,survey,'traits')
        assert saved[survey]['trait_match'] == {p['id']:t['id'] for p,t in zip(formal,traits)}
        assert all(p['stratum']==t['stratum'] for p,t in zip(formal,traits))
        # Finite-difference input isolation: changing truth and weight must not
        # change any of the eight model inputs. Stub only the external task
        # renderer; actual jobs_for builds all profile/system text unchanged.
        import optimize_profiles as profiles
        original = profiles.task_text
        profiles.task_text = lambda survey,pid: 'fixed instrument order:' + pid
        try:
            jobs = profiles.jobs_for(survey,formal,traits)
            mutated = deepcopy(formal)
            for p in mutated:
                p['answers']={'AUDIT_CANARY':'never send target answers'}
                p['weight']=123456789.
            assert jobs == profiles.jobs_for(survey,mutated,traits)
            assert all(j['id'] not in j['system'] for j in jobs)
        finally:
            profiles.task_text = original
        errors = []
        for c in published['overall']:
            if c == 'historical-stratum':
                continue
            for item,(_,options) in ITEMS[survey].items():
                numerator = np.zeros((2,len(options)))
                for s in STRATA:
                    group=[p for p in formal if p['stratum']==s]
                    denominator=sum(p['weight'] for p in group)
                    for p in group:
                        if item not in p['answers']:
                            continue
                        w=p['weight']/denominator*refs[survey]['stratum_weight'][s]
                        for j,k in enumerate(map(str,options)):
                            numerator[0,j] += w*(p['answers'][item]==k)
                            numerator[1,j] += w*(predictions[survey,c,p['id']][item]==k)
                distribution=numerator/numerator[0].sum()
                error=50*abs(distribution[0]-distribution[1]).sum()
                errors.append(abs(error-published['surveys'][survey][c]['items'][item]['tv_pp']))
        assert max(errors)<1e-8
        weights=[p['weight']*refs[survey]['stratum_weight'][p['stratum']] /
                 sum(q['weight'] for q in formal if q['stratum']==p['stratum']) for p in formal]
        result[survey]={'eligible_people':len(people),'formal':len(formal),'formal_matches_raw_source_draw':True,
                       'formal_pilot_overlap':0,'pilot_in_statistics_training':len(saved[survey]['pilot']),
                       'trait_match_is_same_stratum_random_assignment':True,'truth_weight_prompt_invariance':True,
                       'effective_sample_size_before_item_missingness':float(sum(weights)**2/sum(w*w for w in weights)),
                       'unknown_background_cells':sum(v=='Unknown' for p in formal for v in [*p['background'].values(),*p['detail'].values()]),
                       'item_scores_recomputed':len(errors),'max_score_difference_pp':max(errors)}
    return result


def shopping_audit():
    import shopping
    folder=STUDY/'06_北美电商选品'
    saved=read(folder/'sample-index.json')
    result={}
    for survey in shopping.SURVEYS:
        people=(shopping.pew_people(folder/'数据/pew.zip') if survey=='pew' else
                shopping.product_people(folder/f'数据/{survey}.csv',survey))
        ds=shopping.split(people,survey)
        assert saved[survey]=={k:[p['id'] for p in rows] for k,rows in ds.items()}
        ids=[p['id'] for group in ds.values() for p in group]
        assert len(ids)==len(set(ids))==len(people)
        for p in ds['formal']:
            altered=deepcopy(p)
            altered['weight']=123456789.
            for task in altered['tasks']:
                task['truth']='AUDIT_CANARY'
            for condition in shopping.CONDITIONS:
                assert shopping.prompt(survey,p,condition)==shopping.prompt(survey,altered,condition)
        result[survey]={'source_draw_and_partitions_reproduced':True,'splits_disjoint':True,
                       'truth_weight_prompt_invariance':True,
                       'counts':{k:len(v) for k,v in ds.items()},
                       'formal_strata':dict(Counter(p['stratum'] for p in ds['formal']))}
    return result


def margins(people, selected, fields):
    result={}
    for field in fields:
        pool, sample=defaultdict(float),defaultdict(float)
        for key,p in people.items():
            value=p['background'][field]
            pool[value]+=p.get('weight',1.)
            if key in selected:
                sample[value]+=p.get('weight',1.)
        values=sorted(set(pool)|set(sample))
        a=np.array([pool[v] for v in values]);a/=a.sum()
        b=np.array([sample[v] for v in values]);b/=b.sum()
        result[field]={'distance_pp':float(50*abs(a-b).sum()),
                       'categories':[{'label':v,'source_pct':float(100*x),'evaluated_pct':float(100*y)}
                                     for v,x,y in zip(values,a,b)]}
    return result


def later_audit():
    from retail_pew import dataset, RUN
    people,options=dataset()
    freeze=read(RUN/'pew-freeze.json')
    keys=freeze['splits']['formal']
    with sqlite3.connect(f"file:{RUN/'pew.sqlite'}?mode=ro",uri=True) as db:
        forecasts={(k,a):json.loads(p) for k,a,p in db.execute('SELECT person,arm,output FROM runs WHERE output IS NOT NULL')}
    published=read(RUN.parent/'pew-formal-score.json')
    errors=[]
    for arm in ('basic_choice','rich_choice','basic_probability','rich_probability'):
        for row in published['items'][arm]:
            q=row['question'];valid=[k for k in keys if q in people[k]['truth']]
            w=np.array([people[k]['weight'] for k in valid]);w/=w.sum()
            human=w@np.eye(len(options[q]))[[people[k]['truth'][q] for k in valid]]
            pred=w@np.array([forecasts[k,arm][q] for k in valid])
            errors.append(abs(50*abs(human-pred).sum()-row['tv_pp']))
    assert max(errors)<1e-8
    pew={'margins_against_eligible_source':margins(people,set(keys),list(next(iter(people.values()))['background'])),
         'item_scores_recomputed':len(errors),'max_score_difference_pp':max(errors)}
    from retail_shoes_prepare import prepare, load, BACKGROUND
    shoes=read(RUN/'shoes-freeze.json')
    assert prepare()==shoes
    wave1,_,analysis=load()
    counts=analysis.MID.value_counts()
    eligible=set(counts[counts==40].index)
    wave1.index=wave1.WorkerId.str.upper()
    pool={hashlib.sha256(('shoes:'+person).encode()).hexdigest()[:24]:
          {'background':{label:str(wave1.at[person.upper(),col]) for col,label in BACKGROUND.items()}}
          for person in eligible}
    return {'pew13':pew,'shoes':{'background_stimuli_answers_and_splits_reproduced_from_source':True,
                               'margins_against_eligible_source':margins(pool,set(shoes['split']['test']),list(BACKGROUND.values())[:4]),
                               'missing_background_cells':sum(v.lower() in ('nan','none','') for r in shoes['records'].values() for v in r['background'].values())}}


def main():
    output={'audit_date':'2026-11-10','scope':'Read-only recomputation and source/profile matching audit; not a new LLM experiment',
            'bootstrap_scope':'Synthetic weighting sensitivity only: 2000 paired draws of the same IDs within four strata, synchronized across surveys; human reference fixed',
            'input_version_checks':verify_sources(),
            'synthetic':cohort_audit(),'real_profiles':real_profile_audit(),
            'shopping':shopping_audit(),'later':later_audit()}
    sources=[STUDY/'01_首轮归档/reference.json',STUDY/'01_首轮归档/cohort.json',
             *[STUDY/f/'results.json' for f in ('01_首轮归档','02_模型对比','03_提示与背景','06_北美电商选品')]]
    output['source_sha256']={str(p.relative_to(STUDY)):sha(p) for p in sources}
    output['audit_code_sha256']=sha(Path(__file__))
    OUT.mkdir(exist_ok=True)
    (OUT/'audit-results.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'passed','output':str(OUT/'audit-results.json'),
                      'synthetic':{k:v['overall'] for k,v in output['synthetic']['rounds'].items()},
                      'real_profiles':output['real_profiles'],
                      'later':output['later']},ensure_ascii=False))


if __name__=='__main__':
    main()
