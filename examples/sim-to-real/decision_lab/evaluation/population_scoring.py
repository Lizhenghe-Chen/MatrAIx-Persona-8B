"""Compare separate human and generated populations; no individual target pairing."""
from collections import defaultdict,Counter
import math
from ..core.core import probabilities,tv,digest,validate


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


def paired_population_interval(human,synthetic,left,right,repeats=2000,seed=20261109):
    """Fixed human reference; paired generated-person cluster bootstrap.

    If any draw loses a required card, no interval is certified. Missing support
    must not silently turn a different estimand into the frozen comparison.
    """
    import numpy as np
    import random
    if repeats<1:raise ValueError('Positive repeat count required')
    a=distribution_comparison(human,synthetic,left)
    b=distribution_comparison(human,synthetic,right)
    people=sorted({r['person'] for r in synthetic});index={p:i for i,p in enumerate(people)}
    cards={(r['stratum'],r['card_hash']):i for i,r in enumerate(a['cards'])}
    counts=Counter((r['person'],r['stratum'],digest([r['question'],r['context'],r['options']])) for r in synthetic)
    strata=defaultdict(set);signatures={}
    for r in synthetic:
        bg=r['background'];signature=(r['stratum'],bg['age_bracket'],bg['education_group'])
        if r['person'] in signatures and signatures[r['person']]!=signature:raise ValueError('Bootstrap cell varies within person')
        signatures[r['person']]=signature;strata[signature].add(index[r['person']])
    columns=[];denominators=[];targets=[];card_weights=[]
    human_strata=defaultdict(set)
    for r in human:human_strata[r['stratum']].add(r['person'])
    card_count=Counter(r['stratum'] for r in a['cards']);total=sum(map(len,human_strata.values()))
    for card in a['cards']:
        denominators.append(np.zeros(len(people)));columns.append([np.zeros((len(people),len(card['options']))) for _ in range(2)])
        targets.append(np.asarray(card['human']));card_weights.append(len(human_strata[card['stratum']])/total/card_count[card['stratum']])
    for r in synthetic:
        key=(r['stratum'],digest([r['question'],r['context'],r['options']]))
        j=cards[key];i=index[r['person']];w=r.get('weight',1)/counts[(r['person'],*key)]
        denominators[j][i]+=w
        for n,p in enumerate([left,right]):columns[j][n][i]+=w*np.asarray(p[(r['person'],r['task'])])
    rng=random.Random(seed);draws=np.zeros((repeats,len(people)))
    for rep in range(repeats):
        for cell in sorted(strata):
            ids=sorted(strata[cell])
            for i in rng.choices(ids,k=len(ids)):draws[rep,i]+=1
    valid=np.ones(repeats,dtype=bool);scores=np.zeros((repeats,2))
    for j,den in enumerate(denominators):
        masses=draws@den;valid &= masses>0
        safe=np.where(masses>0,masses,1)
        for n in range(2):
            means=(draws@columns[j][n])/safe[:,None]
            scores[:,n]+=50*np.abs(means-targets[j]).sum(axis=1)*card_weights[j]
    difference=scores[:,0]-scores[:,1]
    ci=np.quantile(difference,[.025,.975]).tolist() if valid.all() else None
    improvement=a['mean_tv_pp']-b['mean_tv_pp']
    return {'improvement_pp':improvement,'improvement_95_ci':ci,'replicates':repeats,
            'draws_missing_required_cards':int((~valid).sum()),'passes_2pp_gate':bool(ci and improvement>=2 and ci[0]>0),
            'reference':'human fixed','resampling':'paired synthetic people within design and background cells','seed':seed}
