"""Fit and apply a small-pilot product choice model without any LLM service."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp, softmax


def fit_products(features, targets, *, pseudo=None, nonpositive_price=False):
    """Estimate conditional product utility from purchased alternatives."""
    keep = targets[:, 0] == 0
    x = features[keep]
    y = targets[keep, 1:]
    weights = np.ones(len(y))
    if pseudo is not None:
        pseudo_x, pseudo_y, mass = pseudo
        x = np.concatenate((x, pseudo_x))
        y = np.concatenate((y, pseudo_y))
        weights = np.concatenate((weights, np.full(len(pseudo_y), mass / len(pseudo_y))))
    if not len(y):
        return np.zeros(features.shape[-1])
    weights /= weights.sum()

    def objective(beta):
        utility = x @ beta
        loss = weights @ (logsumexp(utility, axis=1) - (utility * y).sum(axis=1))
        gradient = np.einsum('i,ij,ijk->k', weights, softmax(utility, axis=1) - y, x)
        return loss + .01 * (beta @ beta), gradient + .02 * beta

    fit = minimize(objective, np.zeros(x.shape[-1]), jac=True, method='BFGS')
    if fit.success and nonpositive_price and fit.x[-1] > 0:
        bounds = [(None, None)] * (x.shape[-1] - 1) + [(None, 0)]
        fit = minimize(objective, np.zeros(x.shape[-1]), jac=True, method='L-BFGS-B', bounds=bounds)
    if not fit.success:
        raise RuntimeError(fit.message)
    return fit.x


def fit_model(features, choices):
    """Choices are zero for no purchase, otherwise one-based product indices."""
    targets = np.eye(features.shape[1] + 1)[choices]
    return {'coefficients': fit_products(features, targets).tolist(),
            'no_buy_rate': float(((choices == 0).sum() + .5) / (len(choices) + 1))}


def predict(model, features):
    conditional = softmax(features @ np.asarray(model['coefficients']), axis=-1)
    no_buy = model['no_buy_rate']
    return np.concatenate((np.full((*conditional.shape[:-1], 1), no_buy),
                           (1 - no_buy) * conditional), axis=-1)


def features_for(rows, feature_names, *, observed):
    allowed = {'card', 'products'} | ({'choice'} if observed else set())
    if not isinstance(rows,list) or not rows:
        raise ValueError('Provide a nonempty list of cards')
    for row in rows:
        if set(row) != allowed or not isinstance(row['card'],str) or not row['card']:
            raise ValueError('Each card needs a label and product features; only pilot rows have a choice')
        if not isinstance(row['products'],list) or len(row['products'])<2:
            raise ValueError('Each card needs at least two purchase alternatives')
        for product in row['products']:
            if not isinstance(product,list) or len(product)!=len(feature_names) or any(
                    type(value) not in (int,float) or not np.isfinite(value) for value in product):
                raise ValueError('Product must have a finite numeric value for every feature')
        if observed and (type(row['choice']) is not int or not 0<=row['choice']<=len(row['products'])):
            raise ValueError('Choice is zero for no purchase or the one-based product index')
    return [np.asarray(row['products'],dtype=float) for row in rows]


def run(spec):
    if set(spec) != {'feature_names','pilot','target'}:
        raise ValueError('Expected feature_names, pilot, and target')
    names = spec['feature_names']
    if not isinstance(names,list) or not names or any(not isinstance(n,str) or not n for n in names) or len(set(names))!=len(names):
        raise ValueError('Feature names must be unique nonempty strings')
    pilot = features_for(spec['pilot'],names,observed=True)
    targets = features_for(spec['target'],names,observed=False)
    if len({len(x) for x in pilot}) != 1:
        raise ValueError('Pilot cards must have a consistent number of products')
    if len({row['card'] for row in spec['target']}) != len(targets):
        raise ValueError('Target labels must be unique')
    observed = np.asarray([row['choice'] for row in spec['pilot']],dtype=int)
    model = fit_model(np.asarray(pilot),observed)
    return {'feature_names':names, 'pilot_answers':len(pilot),
            'pilot_purchase_answers':int((observed!=0).sum()),
            **model,
            'predictions':[{'card':row['card'],'probabilities':predict(model,x).tolist()}
                           for row,x in zip(spec['target'],targets,strict=True)]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(json.loads(args.input.read_text())),indent=2))
