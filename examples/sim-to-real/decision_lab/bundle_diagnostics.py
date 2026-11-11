"""Answer-pattern repetition only among people seeing the same semantic tasks."""
from collections import defaultdict,Counter
from .core import digest,probabilities,validate


def summarize(rows,predictions=None):
    validate(rows,require_answers=predictions is None)
    people=defaultdict(list);ties=0
    if predictions is not None and set(predictions)!={(r['person'],r['task']) for r in rows}:
        raise ValueError('Prediction coverage differs')
    for row in rows:
        card=digest([row['stratum'],row['question'],row['context'],row['options']])
        if predictions is None:choice=row['answer']
        else:
            p=probabilities(predictions[(row['person'],row['task'])],len(row['options']))
            ties+=sum(x==max(p) for x in p)>1;choice=p.index(max(p))
        people[row['person']].append((card,choice))
    bundles=defaultdict(list)
    for items in people.values():
        canonical=sorted(items)
        signature=tuple(card for card,_ in canonical)
        bundles[signature].append(tuple(choice for _,choice in canonical))
    comparable=[patterns for patterns in bundles.values() if len(patterns)>=2]
    denominator=sum(map(len,comparable))
    repeated=sum(sum(count for count in Counter(patterns).values() if count>=2) for patterns in comparable)
    return {'people':len(people),'comparable_people':denominator,'incomparable_people':len(people)-denominator,
            'comparable_bundles':len(comparable),'people_sharing_complete_pattern':repeated,
            'fraction_sharing_complete_pattern':repeated/denominator if denominator else None,'argmax_ties':ties,
            'interpretation':'Descriptive unweighted proportion among people with identical semantic task multisets and strata. Repeated cards canonicalized; not a claim about original answer order or psychological consistency. Predicted patterns use argmax, with first-option tie breaking.'}
