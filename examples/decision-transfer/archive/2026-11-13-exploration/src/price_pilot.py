"""Isolate price monotonicity and price-sensitive refusal in historical pilots."""
import json

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, logit, softmax

from adaptive_pilot import spanish
from cheese_pilot import evaluation_inputs, load_deck
import optout_pilot as pilot


def price_refusal(train_x, refused, test_x):
    """Estimate a nonnegative refusal slope using the cheapest offered price."""
    train = train_x[:, :, -1].min(axis=1)
    test = test_x[:, :, -1].min(axis=1)
    rate = (refused.sum()+.5)/(len(refused)+1)
    # One half-weight observation of each outcome at the mean stabilizes the intercept.
    center = train.mean()
    train = np.r_[train-center, 0., 0.]
    labels = np.r_[refused, 0., 1.]
    weights = np.r_[np.ones(len(refused)), .5, .5]/(len(refused)+1)
    x = np.column_stack((np.ones(len(train)),train))
    def objective(beta):
        z = x @ beta
        loss = weights @ (np.logaddexp(0,z)-labels*z) + .01*beta[1]**2
        gradient = x.T @ (weights*(expit(z)-labels)) + np.array([0.,.02*beta[1]])
        return loss, gradient
    fit = minimize(objective,[logit(rate),0.],jac=True,method='L-BFGS-B',
                   bounds=[(None,None),(0,None)])
    if not fit.success:
        raise RuntimeError(fit.message)
    return expit(fit.x[0]+fit.x[1]*(test-center)),float(fit.x[1])


def evaluate(p, y, keys, _prior, features):
    rng = np.random.default_rng(pilot.SEED)
    results = {n:[] for n in pilot.SIZES}
    for _ in range(pilot.REPEATS):
        fit_cards = pilot.split_cards(keys,rng)
        order = rng.permutation(len(y))
        test = order[max(pilot.SIZES):]
        mask = ~fit_cards[test]
        test_y, test_x = y[test][mask], features[test][mask]
        qwen = p[test][mask]
        for n in pilot.SIZES:
            train = order[:n]
            mask = fit_cards[train]
            train_y, train_x = y[train][mask], features[train][mask]
            raw = pilot.fit_products(train_x,train_y)
            constrained = pilot.fit_products(train_x,train_y,nonpositive_price=True)
            q0 = np.full(len(test_y),(train_y[:,0].sum()+.5)/(len(train_y)+1))
            q1,slope = price_refusal(train_x,train_y[:,0],test_x)
            product = softmax(test_x @ raw,axis=1)
            restricted = softmax(test_x @ constrained,axis=1)
            outcomes = {
                'qwen':np.sum((qwen-test_y)**2,axis=1).mean(),
                'uniform':pilot.losses(q0,np.full_like(product,1/product.shape[1]),test_y),
                'baseline':pilot.losses(q0,product,test_y),
                'uniform_price_refusal':pilot.losses(q1,np.full_like(product,1/product.shape[1]),test_y),
                'price_bound':pilot.losses(q0,restricted,test_y),
                'price_refusal':pilot.losses(q1,product,test_y),
                'both':pilot.losses(q1,restricted,test_y),
                'constant_refusal_brier':np.mean(2*(q0-test_y[:,0])**2),
                'price_refusal_brier':np.mean(2*(q1-test_y[:,0])**2),
                'positive_unconstrained_price':float(raw[-1]>0),
                'refusal_slope':slope,
            }
            results[n].append(outcomes)
    output = {}
    for n, rows in results.items():
        output[n] = {key:float(np.mean([r[key] for r in rows])) for key in rows[0]}
        output[n]['vs_baseline'] = {}
        for method in ('price_bound','price_refusal','both'):
            delta = np.array([r['baseline']-r[method] for r in rows])
            output[n]['vs_baseline'][method] = {
                'win_rate':float(np.mean(delta>1e-9)),
                'tie_rate':float(np.mean(np.abs(delta)<=1e-9)),
                'p05_p95':np.quantile(delta,[.05,.95]).tolist(),
            }
    return output


if __name__ == '__main__':
    italian, _, _ = evaluation_inputs(*load_deck())
    inputs = {**pilot.load(),'spain':spanish(),'italy':italian}
    print(json.dumps({'seed':pilot.SEED,'splits':pilot.REPEATS,'new_calls':0,
                      'studies':{name:evaluate(*args) for name,args in inputs.items()}},indent=2))
