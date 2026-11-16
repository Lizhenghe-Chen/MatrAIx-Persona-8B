"""Compare random and information-based card selection under equal pilot budgets."""
import itertools
import json

import numpy as np
from scipy.special import softmax

from adaptive_pilot import spanish
import optout_pilot as pilot

BUDGETS = (10, 24, 25, 36, 50)
METHODS = ('random', 'uniform_information', 'qwen_information')


def select_cards(keys, available, x, p, rng):
    """Use one information matrix per card, averaging known instruction arms."""
    matrices = {method:{} for method in METHODS[1:]}
    blocks = sorted({tuple(sorted(set(block))) for block in keys})
    candidates = set(keys[available])
    for card in sorted(candidates):
        take = keys==card
        # Duplicate respondents receiving identical stimuli do not affect the design.
        packed = np.column_stack((x[take].reshape(take.sum(),-1),p[take]))
        _, unique = np.unique(packed,axis=0,return_index=True)
        xs, ps = x[take][unique], p[take][unique]
        for method in matrices:
            weights = (np.full_like(ps[:,1:],1/x.shape[2]) if method=='uniform_information'
                       else ps[:,1:]/ps[:,1:].sum(axis=1,keepdims=True))
            mean = np.einsum('na,nad->nd',weights,xs)
            centered = xs-mean[:,None,:]
            info = np.einsum('na,nad,nae->nde',weights,centered,centered)
            matrices[method][card] = info.mean(axis=0)
    selected = {method:[] for method in METHODS}
    for block in blocks:
        pool = sorted(set(block)&candidates)
        count = (len(pool)+1)//2
        selected['random'].extend(rng.choice(pool,count,replace=False))
        for method, info in matrices.items():
            # Exact within-block subset search. Ridge ensures a finite score
            # when the budget cannot separately identify every coefficient.
            def criterion(subset):
                return np.linalg.slogdet(.1*np.eye(x.shape[-1])+sum(info[c] for c in subset))[1]
            selected[method].extend(max(itertools.combinations(pool,count),key=criterion))
    return {method:np.isin(keys,cards) for method,cards in selected.items()}


def evaluate(p,y,keys,_,features):
    rng = np.random.default_rng(pilot.SEED)
    selection_rng = np.random.default_rng(pilot.SEED+1)
    rows = {n:[] for n in BUDGETS}
    overlap = []
    for _ in range(pilot.REPEATS):
        available = pilot.split_cards(keys,rng)
        order = rng.permutation(len(y))
        # Keep the same test cohorts as previous experiments.
        test_people = order[max(pilot.SIZES):]
        heldout = ~available[test_people]
        test_y = y[test_people][heldout]
        test_x = features[test_people][heldout]
        chosen = select_cards(keys,available,features,p,selection_rng)
        assert all(not np.any(mask & ~available) for mask in chosen.values())
        counts = {int(mask.sum(axis=1)[0]) for mask in chosen.values()}
        if len(counts)!=1 or any(not np.all(m.sum(axis=1)==next(iter(counts))) for m in chosen.values()):
            raise ValueError('Unequal card budgets')
        overlap.append(np.sum(chosen['qwen_information'] & chosen['uniform_information'])/
                       np.sum(chosen['qwen_information']))
        for n in BUDGETS:
            train_people = order[:n]
            scores = {}
            for method, mask in chosen.items():
                train = mask[train_people]
                target = y[train_people][train]
                train_x = features[train_people][train]
                beta = pilot.fit_products(train_x,target)
                refusal = (target[:,0].sum()+.5)/(len(target)+1)
                scores[method] = pilot.losses(np.full(len(test_y),refusal),softmax(test_x @ beta,axis=1),test_y)
            train = available[train_people]
            target = y[train_people][train]
            beta = pilot.fit_products(features[train_people][train],target)
            refusal = (target[:,0].sum()+.5)/(len(target)+1)
            scores['all_candidate_cards'] = pilot.losses(np.full(len(test_y),refusal),
                                                        softmax(test_x @ beta,axis=1),test_y)
            rows[n].append(scores)
    out = {}
    for n, trials in rows.items():
        data = np.asarray([[r[m] for m in METHODS] for r in trials])
        out[n] = {'brier':dict(zip(METHODS,data.mean(axis=0).tolist())),
                  'all_candidate_cards_brier':float(np.mean([r['all_candidate_cards'] for r in trials])),
                  'total_pilot_choices':n*next(iter(counts)),
                  'all_candidate_choices':n*keys.shape[1]//2,
                  'qwen_vs_uniform_win_rate':float(np.mean(data[:,2]<data[:,1]-1e-12)),
                  'qwen_vs_uniform_tie_rate':float(np.mean(np.abs(data[:,2]-data[:,1])<=1e-12)),
                  'qwen_vs_uniform_delta_p05_p95':np.quantile(data[:,1]-data[:,2],[.05,.95]).tolist(),
                  'uniform_vs_random_win_rate':float(np.mean(data[:,1]<data[:,0]-1e-12))}
    short, long = (36,24) if keys.shape[1]//2 == 3 else (50,25)
    if out[short]['total_pilot_choices'] != out[long]['all_candidate_choices']:
        raise ValueError('Equal answer budget contrast is not matched')
    delta = np.asarray([full['all_candidate_cards']-limited['uniform_information']
                        for full, limited in zip(rows[long],rows[short],strict=True)])
    return {'people':len(y),'pilot_cards_per_person':next(iter(counts)),
            'qwen_uniform_card_overlap':float(np.mean(overlap)), 'budgets':out,
            'equal_answer_budget':{
                'more_people':short,'more_cards':long,'total_answers':out[short]['total_pilot_choices'],
                'more_people_brier':out[short]['brier']['uniform_information'],
                'more_cards_brier':out[long]['all_candidate_cards_brier'],
                'more_people_win_rate':float(np.mean(delta>0)),
            }}


if __name__=='__main__':
    inputs = {**pilot.load(),'spain':spanish()}
    print(json.dumps({'seed':pilot.SEED,'splits':pilot.REPEATS,'new_calls':0,
                      'studies':{k:evaluate(*v) for k,v in inputs.items()}},indent=2))
