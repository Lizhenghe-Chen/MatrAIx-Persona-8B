"""Score repeated forecasts without selecting a best run or changing targets."""
from collections import defaultdict
import argparse
import json
from pathlib import Path
import sqlite3

import numpy as np

from revalidation import OUT, LOCAL, ARMS, MODELS, REPEATS, FIELDS, read, write, seed, digest

REPS=2000


def weighted_draws(groups,masses,salt):
    n=len(groups);result=np.zeros((REPS+1,n));rng=np.random.default_rng(seed(salt,'bootstrap'))
    for group in sorted(set(groups)):
        ids=[i for i,g in enumerate(groups) if g==group]
        weights=np.vstack([np.ones(len(ids)),rng.multinomial(len(ids),np.full(len(ids),1/len(ids)),REPS)])
        result[:,ids]=weights*(masses[group]/len(ids))
    return result/result.sum(axis=1,keepdims=True)


def contrast(before,after,errors,runs):
    difference=errors[before]-errors[after]
    ci=np.quantile(difference[1:],[.025,.975]).tolist()
    gains=[a-b for a,b in zip(runs[before],runs[after])]
    return {'before':before,'after':after,'gain_pp':float(difference[0]),'ci95':ci,
            'gain_by_run_pp':gains,'passes':bool(difference[0]>=2 and ci[0]>0 and min(gains)>0)}


def checkpoints():
    with sqlite3.connect(f"file:{LOCAL/'responses.sqlite'}?mode=ro",uri=True) as db:
        rows=db.execute("SELECT task,model,arm,repetition,subject,output,errors FROM responses WHERE phase='formal'").fetchall()
    out={};counts=defaultdict(int);failures=defaultdict(int)
    for task,model,arm,repeat,subject,raw,errs in rows:
        label=f'{task}/{model}/{arm}/run{repeat+1}'
        counts[label]+=raw is not None
        failures[label]+=len(json.loads(errs))
        if raw is not None:out[task,model,arm,repeat,subject]=json.loads(raw)
    return out,dict(counts),dict(failures)


def matching(data,predictions,models):
    people=data['cohorts']['formal'];conditions=[f'{m}/{a}' for m in models for a in ARMS]
    common=[p for p in people if all(('matching',m,a,r,p['id']) in predictions for m in models for a in ARMS for r in range(REPEATS))]
    assert len(common)/len(people)>=.98,'Synthetic common cohort below 98%'
    masses=defaultdict(float)
    for p in people:masses[p['analysis_cell']]+=p['weight']
    groups=[p['analysis_cell'] for p in common]
    assert set(groups)==set(masses)
    weights={a:weighted_draws(groups,masses,'synthetic-'+('coarse' if a=='coarse' else 'matched')) for a in ARMS}
    errors={};run_errors={};summary={};items={};draw_errors=defaultdict(list)
    for c in conditions:
        model,arm=c.split('/');w=weights[arm];details=[];run_metrics=[]
        for q,options in data['options'].items():
            actual=np.array(data['reference'][q]);p=np.array([[predictions['matching',model,arm,r,x['id']][q] for x in common] for r in range(REPEATS)])
            estimates=np.einsum('bn,rnk->rbk',w,p)
            tv=50*abs(estimates-actual).sum(axis=2)
            draw_errors[c].append(tv.mean(axis=0))
            by_run=tv[:,0];average=estimates[:,0,:].mean(axis=0)
            details.append({'question':q,'text':data['questions'][q],'options':options,
                            'human_pct':(100*actual).tolist(),'predicted_pct':(100*average).tolist(),
                            'predicted_pct_by_run':(100*estimates[:,0,:]).tolist(),
                            'mean_run_tv_pp':float(by_run.mean()),'tv_by_run_pp':by_run.tolist(),
                            'ensemble_tv_pp':float(50*abs(average-actual).sum())})
            run_metrics.append(by_run)
        errors[c]=np.mean(draw_errors[c],axis=0);run_errors[c]=np.mean(run_metrics,axis=0).tolist();items[c]=details
        summary[c]={'mean_run_tv_pp':float(errors[c][0]),'tv_by_run_pp':run_errors[c],
                    'ensemble_tv_pp':float(np.mean([d['ensemble_tv_pp'] for d in details])),
                    'concentration_by_run':[{str(t):sum(max(d['predicted_pct_by_run'][r])>=t-1e-8 for d in details) for t in (95,99,100)} for r in range(REPEATS)]}
    pairs=[(f'{m}/coarse',f'{m}/matched') for m in models]+[(f'{m}/matched',f'{m}/matched_traits') for m in models]
    if set(models)==set(MODELS):pairs += [(f'qwen/{a}',f'pro/{a}') for a in ARMS]
    margins={}
    for field in FIELDS:
        values=sorted({p['matched']['background'][field] for p in people}|{p['coarse']['background'][field] for p in people})
        margins[field]=[{'label':v,**{a:100*sum(p['weight']*(p[a]['background'][field]==v) for p in people) for a in ('coarse','matched')}} for v in values]
    joint={}
    for a in ('coarse','matched'):
        d=defaultdict(float)
        for p in people:d['|'.join(p[a]['background'][f] for f in FIELDS)]+=p['weight']
        joint[a]=dict(d)
    return {'people_per_cohort':len(common),'reference_people':read(OUT/'protocol.json')['matching']['human_eligible'],
            'summary':summary,'items':items,'comparisons':[contrast(a,b,errors,run_errors) for a,b in pairs],
            'margins':margins,'joint_distribution_distance_pp':50*sum(abs(joint['coarse'].get(k,0)-v) for k,v in joint['matched'].items()),
            'unique_visible_backgrounds':{a:len({tuple(p[a]['background'].values()) for p in people}) for a in ('coarse','matched')},
            'no_individual_accuracy':'Synthetic profiles have no corresponding real individual.'}


def products(data,predictions,survey):
    from shopping_score import product_baseline,metrics_for
    ds=data['products'][survey]
    indexed=[(f'p-formal-{i:04d}',p) for i,p in enumerate(ds['formal'])]
    paired=[(key,p) for key,p in indexed if all((survey,'qwen',a,r,key) in predictions for a in ('choice','probability') for r in range(REPEATS))]
    assert len(paired)/len(indexed)>=.98,'Product common cohort below 98%'
    people=[p for key,p in paired];ids=[key for key,p in paired];n=len(people)
    masses=defaultdict(float)
    for p in ds['pool']:masses[p['stratum']]+=p['weight']
    weights=weighted_draws([p['stratum'] for p in people],masses,'product-'+survey)
    baseline=product_baseline(ds['training'],people)
    conditions=['choice','probability','statistics']
    matrices={};cards={};metrics={c:{'brier':np.zeros((REPEATS,n)),'accuracy':np.zeros((REPEATS,n)),'number':np.zeros(n),
                                   'refusal_correct':np.zeros((REPEATS,n))} for c in conditions}
    rejection={'actual':np.zeros(n),'number':np.zeros(n),**{c:np.zeros((REPEATS,n)) for c in conditions}}
    for i,(pid,person) in enumerate(paired):
        for task in person['tasks']:
            if task['truth'] is None:continue
            y=task['codes'].index(task['truth']);actual=np.eye(len(task['codes']))[y]
            probs={c:np.array([predictions[survey,'qwen',c,r,pid][task['id']] for r in range(REPEATS)]) for c in conditions[:2]}
            probs['statistics']=np.tile(baseline[person['id'],task['id']],(REPEATS,1))
            for c,p in probs.items():
                metrics[c]['number'][i]+=1
                metrics[c]['brier'][:,i]+=((p-actual)**2).sum(axis=1)
                metrics[c]['accuracy'][:,i]+=p.argmax(axis=1)==y
                if survey=='packaging' and y==2:metrics[c]['refusal_correct'][:,i]+=p.argmax(axis=1)==2
            if survey=='packaging':
                rejection['actual'][i]+=y==2;rejection['number'][i]+=1
                for c,p in probs.items():rejection[c][:,i]+=p[:,2]
                cards[task['card']]=task['attrs']
            for label,buckets in metrics_for(survey,task):
                if label not in matrices:
                    matrices[label]={'human':np.zeros((n,len(buckets))),**{c:np.zeros((REPEATS,n,len(buckets))) for c in conditions}}
                matrix=matrices[label]
                for j,bucket in enumerate(buckets):
                    idx=[task['codes'].index(v) for v in bucket]
                    matrix['human'][i,j]+=y in idx
                    for c,p in probs.items():matrix[c][:,i,j]+=p[:,idx].sum(axis=1)
    details={c:[] for c in conditions};run_errors={};errors={};boot=defaultdict(list);all_runs=defaultdict(list)
    for label,matrix in sorted(matrices.items()):
        actual=weights@matrix['human'];total=actual.sum(axis=1);actual/=total[:,None]
        for c in conditions:
            estimates=np.einsum('bn,rnk->rbk',weights,matrix[c])/total[None,:,None]
            tv=50*abs(estimates-actual[None,:,:]).sum(axis=2)
            boot[c].append(tv.mean(axis=0));all_runs[c].append(tv[:,0])
            mean=estimates[:,0,:].mean(axis=0)
            details[c].append({'question':label,'human_pct':(100*actual[0]).tolist(),
                               'predicted_pct':(100*mean).tolist(),'predicted_pct_by_run':(100*estimates[:,0,:]).tolist(),
                               'mean_run_tv_pp':float(tv[:,0].mean()),'tv_by_run_pp':tv[:,0].tolist(),
                               'ensemble_tv_pp':float(50*abs(mean-actual[0]).sum()),'choices':int(matrix['human'].sum())})
    summary={};individual_draws={}
    for c in conditions:
        errors[c]=np.mean(boot[c],axis=0);run_errors[c]=np.mean(all_runs[c],axis=0).tolist()
        m=metrics[c];individual_draws[c]={}
        for name in ('brier','accuracy'):
            normalized=m[name]/m['number'][None,:]
            individual_draws[c][name]=weights@normalized.mean(axis=0)
        summary[c]={'mean_run_tv_pp':float(errors[c][0]),'tv_by_run_pp':run_errors[c],
                    'ensemble_tv_pp':float(np.mean([d['ensemble_tv_pp'] for d in details[c]])),
                    'brier':float(individual_draws[c]['brier'][0]),
                    'accuracy_pct':100*float(individual_draws[c]['accuracy'][0]),
                    'concentration_by_run':([{str(t):sum(max(d['predicted_pct_by_run'][r])>=t-1e-8 for d in details[c]) for t in (95,99,100)} for r in range(REPEATS)] if survey=='packaging' else None)}
        if survey=='packaging':
            summary[c]['opt_out_pct_by_run']=(100*(rejection[c]@weights[0])/(rejection['number']@weights[0])).tolist()
            summary[c]['opt_out_pct']=float(np.mean(summary[c]['opt_out_pct_by_run']))
            summary[c]['opt_out_recall_pct']=float(100*(m['refusal_correct'].mean(axis=0)@weights[0])/(rejection['actual']@weights[0]))
    comparisons=[]
    for before,after in [('choice','probability'),('statistics','probability')]:
        row=contrast(before,after,errors,run_errors)
        for measure in ('brier','accuracy'):
            # Positive Brier gain is good; positive accuracy change is good.
            gain=individual_draws[before][measure]-individual_draws[after][measure]
            if measure=='accuracy':gain=-gain*100
            row[measure+'_gain']=float(gain[0]);row[measure+'_ci95']=np.quantile(gain[1:],[.025,.975]).tolist()
        comparisons.append(row)
    return {'people':n,'training_people':len(ds['training']),'summary':summary,'items':details,'comparisons':comparisons,
            'cards':cards,'human_opt_out_pct':float(100*(rejection['actual']@weights[0])/(rejection['number']@weights[0])) if survey=='packaging' else None,
            'statistics_input_note':'Same product attributes and allowed respondent background; instruction arm represented because the prompt includes it. Trained on separate real respondents, unlike untuned LLM.'}


def main(allow_missing_pro=False):
    seal=read(OUT/'analysis-seal.json')
    assert digest(Path(__file__))==seal['score_code_sha256'],'Scoring code changed after pre-analysis seal'
    data=read(LOCAL/'freeze.json');pred,coverage,failures=checkpoints()
    models=['qwen','pro']
    if allow_missing_pro:models=['qwen']
    for task,model,arms in [('matching',m,ARMS) for m in models]+[(s,'qwen',('choice','probability')) for s in ('origin','packaging')]:
        for arm in arms:
            for r in range(REPEATS):
                assert coverage.get(f'{task}/{model}/{arm}/run{r+1}',0)>=.98*240,'Incomplete formal cell'
    result={'experiment':'Internal repeated replication, not fresh external validation','primary_metric':'Mean of separately scored three runs; pooled probabilities shown only as secondary',
            'repeats':REPEATS,'bootstrap_replicates':REPS,'protocol_sha256':digest(OUT/'protocol.json'),
            'freeze_sha256':digest(LOCAL/'freeze.json'),'completion':coverage,'failure_attempts':failures,
            'missing_models':['pro'] if allow_missing_pro else [],'matching':matching(data,pred,models),
            'products':{s:products(data,pred,s) for s in ('origin','packaging')}}
    write(OUT/'results.json',result)
    print(json.dumps({'matching':result['matching']['summary'],
                      'products':{s:v['summary'] for s,v in result['products'].items()}},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--allow-missing-pro',action='store_true');args=p.parse_args();main(args.allow_missing_pro)
