"""Compare separate human and generated populations; no individual target pairing."""
from collections import defaultdict,Counter
import math
from .core import probabilities,tv,digest,validate


def distribution_comparison(human,synthetic,predictions):
    validate(human)
    validate(synthetic,require_answers=False)
    for population in [human,synthetic]:
        metadata={}
        for row in population:
            weight=row.get('weight',1)
            if not math.isfinite(weight) or weight<=0:raise ValueError('Invalid population weight')
            signature=(row['stratum'],weight)
            if row['person'] in metadata and metadata[row['person']]!=signature:
                raise ValueError('Inconsistent respondent stratum or weight')
            metadata[row['person']]=signature
    expected={(r['person'],r['task']) for r in synthetic}
    if set(predictions)!=expected:raise ValueError('Predictions do not exactly cover synthetic tasks')
    def group(row):return (row['stratum'],digest([row['question'],row['context'],row['options']]))
    humans=defaultdict(list);models=defaultdict(list)
    for r in human:humans[group(r)].append(r)
    for r in synthetic:
        if 'answer' in r:raise ValueError('Synthetic individual targets forbidden')
        models[group(r)].append(r)
    if set(humans)!=set(models):raise ValueError('Choice-card support differs')
    stratum_people=defaultdict(set)
    for r in human:stratum_people[r['stratum']].add(r['person'])
    results=[];stratum_scores=defaultdict(list)
    for key in sorted(humans):
        h,m=humans[key],models[key];options=h[0]['options'];n=len(options)
        def average(rows,is_human):
            counts=Counter(r['person'] for r in rows);sums=[0.]*n;total=0.
            for r in rows:
                weight=r.get('weight',1)/counts[r['person']]
                p=[int(i==r['answer']) for i in range(n)] if is_human else probabilities(predictions[(r['person'],r['task'])],n)
                for i in range(n):sums[i]+=weight*p[i]
                total+=weight
            return [v/total for v in sums]
        hp,mp=average(h,True),average(m,False);error=100*tv(hp,mp)
        stratum_scores[key[0]].append(error)
        results.append({'stratum':key[0],'card_hash':key[1],'options':options,'human':hp,'model':mp,'tv_pp':error,
                        'human_people':len({r['person'] for r in h}),'synthetic_people':len({r['person'] for r in m}),
                        'small_human_group':len({r['person'] for r in h})<20})
    total=sum(len(v) for v in stratum_people.values())
    mean=sum(sum(values)/len(values)*len(stratum_people[s])/total for s,values in stratum_scores.items())
    return {'mean_tv_pp':mean,'cards':results,'aggregation':'Equal cards within design stratum; strata weighted by eligible human people.',
            'warning':'Sparse cards are descriptive; study protocol determines whether this aggregate can support adoption.'}
