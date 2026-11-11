"""Paired synthetic-person intervals for prespecified product-choice shares."""
from collections import defaultdict
import random
import numpy as np
from .product_summary import population_properties
from .population_scoring import distribution_comparison


def compare(human,synthetic,left,right,kind,repeats=2000,seed=20261109):
    # Enforce target isolation, exact card coverage and complete probabilities.
    distribution_comparison(human,synthetic,left)
    distribution_comparison(human,synthetic,right)
    if repeats<1:raise ValueError('Positive repeat count required')
    reference=population_properties(human,kind)
    persons=defaultdict(list)
    for row in synthetic:persons[row['person']].append(row)
    ids=sorted(persons);cells=defaultdict(list)
    values=[{},{}]
    for i,person in enumerate(ids):
        rows=persons[person]
        signatures={(r['stratum'],r['background']['age_bracket'],r['background']['education_group']) for r in rows}
        if len(signatures)!=1:raise ValueError('Background cell varies within person')
        cells[next(iter(signatures))].append(i)
        for j,predictions in enumerate([left,right]):
            keys={(r['person'],r['task']) for r in rows}
            values[j][person]=population_properties(rows,kind,{k:predictions[k] for k in keys})
    rng=random.Random(seed);draws=np.zeros((repeats,len(ids)))
    for rep in range(repeats):
        for cell in sorted(cells):
            for i in rng.choices(cells[cell],k=len(cells[cell])):draws[rep,i]+=1
    result={}
    for event,target in reference.items():
        weights=np.array([persons[p][0].get('weight',1) if event in values[0][p] else 0 for p in ids])
        if weights.sum()==0:raise ValueError('No eligible synthetic people')
        mass=draws@weights;valid=mass>0;means=[];original=[]
        for j in range(2):
            shares=np.array([values[j][p].get(event,{'share':0})['share'] for p in ids])
            original.append(float(weights@shares/weights.sum()))
            means.append((draws@(weights*shares))/np.where(valid,mass,1))
        improvement=100*(abs(original[0]-target['share'])-abs(original[1]-target['share']))
        distribution=100*(np.abs(means[0]-target['share'])-np.abs(means[1]-target['share']))
        result[event]={'human_share':target['share'],'reference_prediction_share':original[0],
                       'candidate_prediction_share':original[1],'absolute_error_reduction_pp':improvement,
                       'improvement_95_ci':np.quantile(distribution,[.025,.975]).tolist() if valid.all() else None,
                       'draws_without_eligible_people':int((~valid).sum()),'replicates':repeats,
                       'interpretation':'Fixed human reference; paired generated people within background and design cells. Separate outcome, no combined adoption claim.'}
    return result
