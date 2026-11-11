"""Descriptive product trade-offs, not causal attribute effects."""
from collections import defaultdict
from ..core.core import probabilities


def summarize(rows,predictions,kind):
    if kind=='dryer':
        from ..studies.dryer_baseline import attributes
        rules={'lower_price':(1,min),'higher_customer_rating':(3,max)}
    elif kind=='swiss':
        from ..studies.swiss_baseline import attributes
        rules={'lower_price':(0,min),'longer_functional_life':(1,max)}
    else:raise ValueError('Unknown reviewed adapter')
    events=defaultdict(list)
    for r in rows:
        p=probabilities(predictions[(r['person'],r['task'])],len(r['options']))
        products=[(i,attributes(o)) for i,o in enumerate(r['options']) if o!='Neither']
        if len(products)<2:raise ValueError('Insufficient products')
        for name,(column,fn) in rules.items():
            values=[a[column] for _,a in products]
            if len(set(values))==1:continue
            best=fn(values);selected=[i for i,a in products if a[column]==best]
            if len(selected)!=1:continue
            events[name].append((r,float(r['answer'] in selected),sum(p[i] for i in selected)))
        if 'Neither' in r['options']:
            i=r['options'].index('Neither')
            events['refusal'].append((r,float(r['answer']==i),p[i]))
    output={}
    for name,items in events.items():
        people=defaultdict(list)
        for r,y,p in items:people[r['person']].append((y,p,r.get('weight',1)))
        if any(len({x[2] for x in v})!=1 for v in people.values()):raise ValueError('Inconsistent weights')
        denominator=sum(v[0][2] for v in people.values())
        human=sum(sum(x[0] for x in v)/len(v)*v[0][2] for v in people.values())/denominator
        model=sum(sum(x[1] for x in v)/len(v)*v[0][2] for v in people.values())/denominator
        output[name]={'human_share':human,'model_probability_share':model,'signed_gap_pp':100*(model-human),
                      'people':len(people),'eligible_tasks':len(items),'excluded_tasks':len(rows)-len(items)}
    return {'events':output,'interpretation':'Observed choice shares on eligible cards, averaging within person first. Price and other attributes vary together; these are not causal effects. Refusal remains in the denominator when available.'}


def population_properties(rows,kind,predictions=None):
    """Choice-property rates for either observed humans or target-free predictions."""
    if kind=='dryer':
        from ..studies.dryer_baseline import attributes
        rules={'lower_price':(1,min),'higher_customer_rating':(3,max)}
    elif kind=='swiss':
        from ..studies.swiss_baseline import attributes
        rules={'lower_price':(0,min),'longer_functional_life':(1,max)}
    else:raise ValueError('Unknown adapter')
    events=defaultdict(lambda:defaultdict(list))
    for r in rows:
        if predictions is None:p=[int(i==r['answer']) for i in range(len(r['options']))]
        else:
            if 'answer' in r:raise ValueError('Generated rows must not contain answers')
            p=probabilities(predictions[(r['person'],r['task'])],len(r['options']))
        products=[(i,attributes(o)) for i,o in enumerate(r['options']) if o!='Neither']
        for name,(column,fn) in rules.items():
            values=[a[column] for _,a in products]
            if len(set(values))<2:continue
            selected=[i for i,a in products if a[column]==fn(values)]
            if len(selected)!=1:continue
            events[name][r['person']].append((p[selected[0]],r.get('weight',1)))
        if 'Neither' in r['options']:events['refusal'][r['person']].append((p[r['options'].index('Neither')],r.get('weight',1)))
    result={}
    for name,people in events.items():
        if any(len({w for _,w in v})!=1 for v in people.values()):raise ValueError('Inconsistent weights')
        mass=sum(v[0][1] for v in people.values())
        result[name]={'share':sum(sum(p for p,_ in v)/len(v)*v[0][1] for v in people.values())/mass,
                      'people':len(people),'eligible_tasks':sum(map(len,people.values()))}
    return result
