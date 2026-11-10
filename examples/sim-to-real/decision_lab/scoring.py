"""Local-only scoring: paired people, explicit question groups, no API access."""
from collections import defaultdict
import math
import random
from .core import brier, probabilities, tv


def score(rows, predictions):
    people=defaultdict(list)
    groups=defaultdict(list)
    seen=set()
    for r in rows:
        key=(r['person'],r['task'])
        if key in seen: raise ValueError('Duplicate scoring row')
        seen.add(key)
        if key not in predictions: raise ValueError('Missing prediction; select and report common completion first')
        p=probabilities(predictions[key],len(r['options']))
        w=r.get('weight',1.0)
        if not math.isfinite(w) or w<=0:raise ValueError('Invalid survey weight')
        people[r['person']].append((brier(p,r['answer']),w,int(max(range(len(p)),key=p.__getitem__)==r['answer'])))
        # score_group must refer to identical semantic options, never randomized A/B labels.
        groups[r['score_group']].append((r,p,w))
    if not people:raise ValueError('Empty evaluation')
    person_scores={}
    for person,items in people.items():
        weights={x[1] for x in items}
        if len(weights)!=1:raise ValueError('Inconsistent within-person survey weights')
        person_scores[person]={'brier':sum(x[0] for x in items)/len(items),
                               'accuracy':sum(x[2] for x in items)/len(items),'weight':items[0][1]}
    total=sum(v['weight'] for v in person_scores.values())
    result={k:sum(v[k]*v['weight'] for v in person_scores.values())/total for k in ['brier','accuracy']}
    result['people']=len(people);result['tasks']=len(rows);result['groups']={}
    for name,items in groups.items():
        options=items[0][0]['options']
        if any(r['options']!=options for r,_,_ in items):
            raise ValueError('Group options are not semantically aligned')
        # Each respondent contributes equal total mass within a group before survey weighting.
        counts=defaultdict(int)
        for r,_,_ in items:counts[r['person']]+=1
        mass=sum(w/counts[r['person']] for r,_,w in items)
        human=[sum(w/counts[r['person']] for r,_,w in items if r['answer']==i)/mass for i in range(len(options))]
        model=[sum(w*p[i]/counts[r['person']] for r,p,w in items)/mass for i in range(len(options))]
        result['groups'][name]={'options':options,'human':human,'model':model,'tv_pp':100*tv(human,model)}
    result['mean_tv_pp']=sum(x['tv_pp'] for x in result['groups'].values())/len(groups)
    return result


def paired_interval(rows, left, right, repeats=2000, seed=20261109):
    strata=defaultdict(set);person_rows=defaultdict(list);membership={}
    for r in rows:
        person=r['person']
        if person in membership and membership[person]!=r['stratum']:raise ValueError('Inconsistent strata')
        membership[person]=r['stratum'];strata[r['stratum']].add(person);person_rows[person].append(r)
    rng=random.Random(seed);samples=defaultdict(list)
    for _ in range(repeats):
        sampled=[];a={};b={};serial=0
        for stratum in sorted(strata):
            ids=sorted(strata[stratum])
            for original in rng.choices(ids,k=len(ids)):
                synthetic=str(serial);serial+=1
                for r in person_rows[original]:
                    item={**r,'person':synthetic};sampled.append(item)
                    key=(original,r['task']);newkey=(synthetic,r['task'])
                    a[newkey]=left[key];b[newkey]=right[key]
        sa=score(sampled,a);sb=score(sampled,b)
        for metric in ['brier','mean_tv_pp']:samples[metric].append(sa[metric]-sb[metric])
    import numpy as np
    return {k:{'improvement_95_ci':np.quantile(v,[.025,.975]).tolist(),'replicates':repeats} for k,v in samples.items()}
