"""Question-specific demographic statistical references for ordinary surveys."""
from collections import Counter
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from .core import brier


class SurveyBaseline:
    def __init__(self, fields, regularization=1.0):
        self.fields=tuple(fields);self.regularization=regularization
        if regularization<=0:raise ValueError('Positive regularization required')
    def features(self, rows):
        # Treat background levels as categorical; unknown is retained explicitly.
        return [{k:str(r['background'].get(k,'unknown')) for k in self.fields} for r in rows]
    def fit(self, rows):
        if not rows:raise ValueError('No training observations')
        self.options=list(rows[0]['options']);self.question=rows[0]['score_group']
        self.check(rows)
        self.training_people={r['person'] for r in rows}
        counts=Counter(r['person'] for r in rows)
        weights=np.array([r.get('weight',1)/counts[r['person']] for r in rows],float)
        if not np.isfinite(weights).all() or np.any(weights<=0):raise ValueError('Invalid weights')
        weights*=len(counts)/weights.sum()
        y=np.array([r['answer'] for r in rows]);n=len(self.options)
        self.prior=np.bincount(y,weights=weights,minlength=n)+1
        self.prior=self.prior/self.prior.sum()
        self.vectorizer=DictVectorizer(sparse=True)
        x=self.vectorizer.fit_transform(self.features(rows))
        self.model=None
        if len(set(y))>1 and x.shape[1]>0:
            self.model=LogisticRegression(C=self.regularization,max_iter=1000)
            self.model.fit(x,y,sample_weight=weights)
            if np.any(self.model.n_iter_>=1000):raise RuntimeError('Baseline did not converge')
        return self
    def check(self, rows):
        for r in rows:
            if r['options']!=self.options or r['score_group']!=self.question:raise ValueError('Question or option mismatch')
            if r['answer'] not in range(len(self.options)):raise ValueError('Invalid answer')
    def predict(self, rows):
        # No answers needed or inspected during prediction.
        if any(r['options']!=self.options or r['score_group']!=self.question for r in rows):raise ValueError('Question mismatch')
        if self.model is None:return [self.prior.tolist() for _ in rows]
        values=self.model.predict_proba(self.vectorizer.transform(self.features(rows)))
        result=np.zeros((len(rows),len(self.options)))
        result[:,self.model.classes_.astype(int)]=values
        return result.tolist()
