"""Choice-set conditional logit; task weights normalized within respondent."""
from collections import Counter
import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp


class ConditionalLogit:
    """Caller supplies reviewed alternative features, including background interactions.

    Features must be available before choice. Never encode alternative position as
    a product attribute. Fit only on the declared training people.
    """
    def __init__(self, penalty=1.0):
        if penalty<=0:raise ValueError('Positive regularization required')
        self.penalty=penalty

    def fit(self, tasks):
        if not tasks:raise ValueError('Empty training tasks')
        counts=Counter(t['person'] for t in tasks)
        xs=[np.asarray(t['features'],dtype=float) for t in tasks]
        width=xs[0].shape[1]
        for x,t in zip(xs,tasks):
            if x.ndim!=2 or len(x)<2 or x.shape[1]!=width or not np.isfinite(x).all():raise ValueError('Invalid features')
            if t['answer'] not in range(len(x)):raise ValueError('Invalid choice')
        # Scale using training feature differences, not held-out values.
        centered=[x-x.mean(axis=0) for x in xs]
        self.scale=np.std(np.concatenate(centered),axis=0)
        self.scale[self.scale<1e-12]=1
        xs=[x/self.scale for x in centered]
        weights=np.array([t.get('weight',1)/counts[t['person']] for t in tasks],dtype=float)
        if not np.isfinite(weights).all() or np.any(weights<=0):raise ValueError('Invalid weights')
        weights/=weights.sum()
        def objective(beta):
            value=self.penalty*np.dot(beta,beta)/2
            grad=self.penalty*beta.copy()
            for x,t,w in zip(xs,tasks,weights):
                z=x@beta;lse=logsumexp(z);p=np.exp(z-lse)
                value+=w*(lse-z[t['answer']]);grad+=w*(p@x-x[t['answer']])
            return value,grad
        result=minimize(objective,np.zeros(width),jac=True,method='L-BFGS-B')
        if not result.success:raise RuntimeError('Choice baseline did not converge: '+result.message)
        self.beta=result.x;self.training_people=set(counts)
        return self

    def predict(self,tasks):
        result=[]
        for t in tasks:
            x=np.asarray(t['features'],dtype=float)
            if x.ndim!=2 or x.shape[1]!=len(self.beta) or not np.isfinite(x).all():raise ValueError('Invalid prediction features')
            z=((x-x.mean(axis=0))/self.scale)@self.beta
            result.append(np.exp(z-logsumexp(z)).tolist())
        return result


def select_penalty(train, development, grid=(.001,.01,.1,1.0)):
    if {t['person'] for t in train}&{t['person'] for t in development}:
        raise ValueError('Training and development people overlap')
    if not development:raise ValueError('Empty development set')
    counts=Counter(t['person'] for t in development)
    weights=np.array([t.get('weight',1)/counts[t['person']] for t in development]);weights=weights/weights.sum()
    candidates=[]
    for penalty in grid:
        model=ConditionalLogit(penalty).fit(train);p=model.predict(development)
        losses=[sum((v-int(i==t['answer']))**2 for i,v in enumerate(q)) for t,q in zip(development,p)]
        candidates.append((float(weights@losses),penalty,model))
    loss,penalty,model=min(candidates,key=lambda x:(x[0],-x[1]))
    return model,{'penalty':penalty,'development_brier':loss,'grid':list(grid)}
