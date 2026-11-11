"""Development-only temperature calibration and convex baseline mixing."""
from collections import Counter
import math
import numpy as np
from scipy.special import softmax
from .core import probabilities,digest


def transform(p, temperature):
    probabilities(p,len(p))
    if not math.isfinite(temperature) or temperature<=0:raise ValueError('Invalid temperature')
    # Preserve genuine zero mass rather than silently clipping probabilities.
    values=np.asarray(p,dtype=float);logs=np.full(len(values),-np.inf)
    positive=values>0;logs[positive]=np.log(values[positive])/temperature
    return softmax(logs).tolist()


def select(development, llm, baseline, forbidden_people=(), temperatures=(.5,1.,2.,4.), mixture_weights=(0.,.25,.5,.75,1.)):
    if not development:raise ValueError('Empty development data')
    people={r['person'] for r in development}
    if people&set(forbidden_people):raise ValueError('Development/test leakage')
    if any(r.get('split')!='development' for r in development):raise ValueError('Calibration requires development rows')
    counts=Counter(r['person'] for r in development);keys=[(r['person'],r['task']) for r in development]
    if len(set(keys))!=len(keys):raise ValueError('Duplicate development task')
    weights=np.array([r.get('weight',1)/counts[r['person']] for r in development],dtype=float)
    if not np.isfinite(weights).all() or np.any(weights<=0):raise ValueError('Invalid weights')
    weights/=weights.sum()
    candidates=[]
    for temperature in temperatures:
        for alpha in mixture_weights:
            if not math.isfinite(alpha) or not 0<=alpha<=1:raise ValueError('Invalid mixture weight')
            losses=[]
            for r,key in zip(development,keys):
                p=np.asarray(transform(llm[key],temperature));q=np.asarray(probabilities(baseline[key],len(p)))
                if len(p)!=len(r['options']):raise ValueError('Option mismatch')
                mixed=alpha*p+(1-alpha)*q
                losses.append(sum((v-int(i==r['answer']))**2 for i,v in enumerate(mixed)))
            candidates.append({'temperature':temperature,'llm_weight':alpha,'development_brier':float(weights@losses)})
    best=min(candidates,key=lambda x:(x['development_brier'],x['llm_weight'],abs(x['temperature']-1)))
    return {**best,'selection':'development_only','development_people_hash':digest(sorted(people)),
            'candidates':candidates,'interpretation':'LLM weight 0 means statistical baseline selected; not an LLM improvement.'}


def apply(p,q,selection):
    p=transform(p,selection['temperature']);probabilities(q,len(p))
    alpha=selection['llm_weight']
    if not 0<=alpha<=1:raise ValueError('Invalid saved mixture weight')
    return [alpha*a+(1-alpha)*b for a,b in zip(p,q)]
