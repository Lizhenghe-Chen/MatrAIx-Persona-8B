"""Training-only semantic-option frequencies; unseen cards fall back to uniform.

Never pool arbitrary A/B positions across different product combinations.
"""
from collections import defaultdict,Counter
import math

class HistoricalProportions:
    def fit(self, rows):
        if not rows:raise ValueError('Empty training set')
        self.people={r['person'] for r in rows}
        counts=Counter(r['person'] for r in rows)
        self.mass=defaultdict(Counter);self.support=defaultdict(set)
        seen=set()
        for r in rows:
            key=(r['person'],r['task'])
            if key in seen:raise ValueError('Duplicate task')
            seen.add(key)
            options=r['options']
            if len(options)<2 or len(set(options))!=len(options):raise ValueError('Ambiguous options')
            if r['answer'] not in range(len(options)):raise ValueError('Invalid answer')
            weight=r.get('weight',1)
            if not math.isfinite(weight) or weight<=0:raise ValueError('Invalid weight')
            # Context must distinguish currencies, treatment instructions and dates.
            card=(r['context'],r['question'],tuple(sorted(options)))
            self.mass[card][options[r['answer']]]+=weight/counts[r['person']]
            self.support[card].add(r['person'])
        return self

    def predict(self, rows):
        if self.people & {r['person'] for r in rows}:raise ValueError('Training/evaluation person overlap')
        predictions={};support={}
        for r in rows:
            key=(r['person'],r['task']);options=r['options']
            if key in predictions:raise ValueError('Duplicate evaluation task')
            if len(options)<2 or len(set(options))!=len(options):raise ValueError('Ambiguous options')
            card=(r['context'],r['question'],tuple(sorted(options)))
            mass=self.mass.get(card);total=sum(mass.values()) if mass else 0
            predictions[key]=[mass.get(o,0)/total for o in options] if total else [1/len(options)]*len(options)
            support[key]=len(self.support.get(card,()))
        return predictions,support
