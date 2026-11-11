"""Descriptive held-out prediction summaries; never select a method by subgroup."""
from collections import defaultdict
from .core import probabilities,brier


def summarize(rows,predictions,fields=()):
    groups=defaultdict(list)
    for r in rows:
        groups[('all','all')].append(r)
        groups[('stratum',r['stratum'])].append(r)
        for field in fields:groups[(field,str(r['background'].get(field,'unknown')))].append(r)
    result=[]
    for (field,value),items in groups.items():
        people=defaultdict(list);ties=0
        for r in items:
            p=probabilities(predictions[(r['person'],r['task'])],len(r['options']))
            ties+=sum(x==max(p) for x in p)>1
            people[r['person']].append((brier(p,r['answer']),float(p.index(max(p))==r['answer']),r.get('weight',1)))
        if any(len({x[2] for x in v})!=1 for v in people.values()):raise ValueError('Inconsistent weights')
        total=sum(v[0][2] for v in people.values())
        means=[sum(sum(x[i] for x in v)/len(v)*v[0][2] for v in people.values())/total for i in [0,1]]
        result.append({'field':field,'value':value,'people':len(people),'tasks':len(items),
                       'brier':means[0],'accuracy':means[1],'argmax_ties':ties,
                       'small_group':len(people)<20,'descriptive_only':True})
    return result
