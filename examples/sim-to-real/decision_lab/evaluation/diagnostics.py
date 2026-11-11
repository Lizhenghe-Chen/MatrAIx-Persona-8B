"""Local diagnostics for minority choices and concentration, with support counts."""
from collections import defaultdict,Counter
from ..core.core import probabilities


def choice_diagnostics(rows,predictions):
    groups=defaultdict(list);counts=defaultdict(lambda:[0,0]);ties=0
    for row in rows:
        key=(row['person'],row['task']);p=probabilities(predictions[key],len(row['options']))
        best=max(p);ties+=sum(v==best for v in p)>1;selected=p.index(best)
        # Local index recalls are only meaningful within identical semantic choice cards.
        group=row['score_group'];groups[group].append((row,p,selected))
        k=(group,row['answer']);counts[k][0]+=1;counts[k][1]+=selected==row['answer']
    result={'tasks':len(rows),'argmax_ties':ties,'groups':{},'concentration_thresholds':{},
            'interpretation':'Argmax uses first maximum; ties reported. Card concentration is descriptive; small groups are not population evidence.'}
    for group,items in groups.items():
        options=items[0][0]['options']
        if any(r['options']!=options for r,_,_ in items):raise ValueError('Semantic options differ')
        n=len(items);chosen=Counter(s for _,_,s in items)
        mean=[sum(p[i] for _,p,_ in items)/n for i in range(len(options))]
        result['groups'][group]={'people':len({r['person'] for r,_,_ in items}),'tasks':n,
            'max_argmax_share':max(chosen.values())/n,'max_mean_probability':max(mean),
            'recall':[{'option':option,'human_count':counts[(group,i)][0],
                       'correct_count':counts[(group,i)][1],
                       'recall':counts[(group,i)][1]/counts[(group,i)][0] if counts[(group,i)][0] else None}
                      for i,option in enumerate(options)]}
    for threshold in [.95,.99,1.]:
        result['concentration_thresholds'][str(threshold)]={
            'all_groups':sum(g['max_argmax_share']>=threshold for g in result['groups'].values()),
            'groups_with_at_least_20_people':sum(g['max_argmax_share']>=threshold and g['people']>=20 for g in result['groups'].values())}
    return result
