"""Replay transfer of conditional dryer preferences between Canada and the US."""
import json

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import logsumexp, softmax

import dryer_refusal as dryer
from optout_pilot import fit_products, losses, split_cards, SEED, REPEATS

BUDGETS = (10, 25, 50, 100)


def fit_scale(utilities, truth):
    bought = truth[:, 0] == 0
    if not bought.any():
        return 1.0
    x = utilities[bought]
    y = truth[bought, 1:]

    def objective(scale):
        z = scale * x
        return np.mean(logsumexp(z, axis=1) - (z * y).sum(axis=1)) + .01 * (scale - 1)**2

    fit = minimize_scalar(objective, bounds=(0, 3), method='bounded')
    if not fit.success:
        raise RuntimeError(fit.message)
    return float(fit.x)


def compare(target, source_beta, source_rate):
    p, y, keys, features = target
    rng = np.random.default_rng(SEED)
    rows = {n: [] for n in BUDGETS}
    for _ in range(REPEATS):
        fit_cards = split_cards(keys, rng)
        order = rng.permutation(len(y))
        test = order[max(BUDGETS):]
        heldout = ~fit_cards[test]
        test_x, test_y = features[test][heldout], y[test][heldout]
        source_u = test_x @ source_beta
        borrowed = softmax(source_u, axis=1)
        qwen = p[test][heldout]
        direct = float(np.sum((qwen - test_y)**2, axis=1).mean())
        for n in BUDGETS:
            train = order[:n]
            pilot = fit_cards[train]
            train_x, train_y = features[train][pilot], y[train][pilot]
            refusal = np.full(len(test_y), (train_y[:,0].sum() + .5)/(len(train_y) + 1))
            local = softmax(test_x @ fit_products(train_x, train_y), axis=1)
            scale = fit_scale(train_x @ source_beta, train_y)
            methods = {
                'local': (refusal, local),
                'transfer': (refusal, borrowed),
                'transfer_rescaled': (refusal, softmax(scale * source_u, axis=1)),
                'source_only': (np.full(len(test_y), source_rate), borrowed),
                'uniform_products': (refusal, np.full_like(local, .5)),
            }
            result = {name: losses(rate, products, test_y) for name, (rate, products) in methods.items()}
            result.update({'qwen_direct': direct, 'scale': scale})
            rows[n].append(result)

    def paired(reference, candidate):
        delta = np.asarray(reference) - candidate
        return {'mean': float(delta.mean()), 'win_rate': float(np.mean(delta > 1e-9)),
                'p05_p95': np.quantile(delta,[.05,.95]).tolist()}

    out = {}
    local_50 = np.asarray([r['local'] for r in rows[50]])
    for n, trials in rows.items():
        out[n] = {
            'means': {k: float(np.mean([r[k] for r in trials])) for k in trials[0]},
            'transfer_vs_same_budget': paired([r['local'] for r in trials],
                                              [r['transfer'] for r in trials]),
            'rescaled_vs_transfer': paired([r['transfer'] for r in trials],
                                           [r['transfer_rescaled'] for r in trials]),
            'transfer_vs_local_50': paired(local_50, [r['transfer'] for r in trials]),
        }
    return out


def main():
    jobs, cards, people = dryer.deck()
    probabilities, identities = dryer.predictions(jobs, dryer.RUN)
    if len(identities) != 1:
        raise ValueError('Mixed model versions')
    data = {}
    for country, group in people.items():
        ordered = [dict(sorted(row.items())) for row in group.values()]
        p, y = dryer.outcome(probabilities, ordered)
        keys = np.asarray([list(person) for person in ordered])
        x = np.asarray([[cards[key] for key in person] for person in keys])
        data[country] = p, y, keys, x
    results = {}
    for target, source in [('USA','CAN'),('CAN','USA')]:
        _, y, _, x = data[source]
        beta = fit_products(x.reshape(-1, *x.shape[2:]), y.reshape(-1, y.shape[-1]))
        rate = (y[:,:,0].sum()+.5)/(y.shape[0]*y.shape[1]+1)
        results[target] = {'source': source, 'source_people': len(y),
                           'source_beta': beta.tolist(), 'source_no_buy_rate': float(rate),
                           'target_people': len(data[target][1]),
                           'budgets': compare(data[target], beta, rate)}
    print(json.dumps({'seed': SEED, 'splits': REPEATS, 'new_calls': 0,
                      'model_identity': json.loads(next(iter(identities))), 'studies': results}, indent=2))


if __name__ == '__main__':
    main()
