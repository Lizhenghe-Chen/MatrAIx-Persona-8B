"""Cross-country replay excluding held-out attribute contrasts in both countries."""
import json

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp, softmax

import dryer_refusal as dryer
from optout_pilot import fit_products, losses, split_cards, SEED, REPEATS

BUDGETS = (10, 25, 50, 100)


def contrast(products):
    diff = tuple(np.round(products[0] - products[1], 9))
    return min(diff, tuple(-x for x in diff))


def retained(features, holdout):
    return np.asarray([contrast(card) not in holdout for card in features])


def update_beta(x, y, source):
    bought = y[:, 0] == 0
    x, y = x[bought], y[bought, 1:]
    if not len(y):
        return source
    # Fixed weight of 40 comparable choice records, decaying with local evidence.
    strength = .01 * 40 / len(y)

    def objective(beta):
        utility = x @ beta
        diff = beta - source
        loss = np.mean(logsumexp(utility, axis=1) - (utility*y).sum(axis=1))
        grad = np.einsum('ij,ijk->k', softmax(utility, axis=1)-y, x)/len(y)
        return loss + .01*(beta @ beta) + strength*(diff @ diff), grad + .02*beta + 2*strength*diff

    fit = minimize(objective, source, jac=True, method='BFGS')
    if not fit.success:
        raise RuntimeError(fit.message)
    return fit.x


def compare(target, source):
    p, y, keys, x = target
    _, sy, _, sx = source
    sx, sy = sx.reshape(-1,*sx.shape[2:]), sy.reshape(-1,sy.shape[-1])
    rng = np.random.default_rng(SEED)
    rows = {n: [] for n in BUDGETS}
    source_counts = []
    for _ in range(REPEATS):
        available = split_cards(keys, rng)
        heldout = {contrast(card) for card in x[~available]}
        source_train = retained(sx, heldout)
        local_train = retained(x.reshape(-1,*x.shape[2:]), heldout).reshape(available.shape) & available
        if np.any(local_train & ~available):
            raise AssertionError('Local holdout overlap')
        source_counts.append(int(source_train.sum()))
        source_beta = fit_products(sx[source_train], sy[source_train])
        source_rate = (sy[source_train,0].sum()+.5)/(source_train.sum()+1)
        order = rng.permutation(len(y))
        test = order[max(BUDGETS):]
        test_mask = ~available[test]
        test_x, test_y = x[test][test_mask], y[test][test_mask]
        source_probs = softmax(test_x @ source_beta, axis=1)
        raw = p[test][test_mask]
        for n in BUDGETS:
            selected = order[:n]
            mask = local_train[selected]
            train_x, train_y = x[selected][mask], y[selected][mask]
            rate = (train_y[:,0].sum()+.5)/(len(train_y)+1)
            local_beta = fit_products(train_x, train_y)
            updated_beta = update_beta(train_x, train_y, source_beta)
            estimates = {
                'local': (rate, softmax(test_x @ local_beta, axis=1)),
                'source_only': (source_rate, source_probs),
                'source_local_refusal': (rate, source_probs),
                'source_updated': (rate, softmax(test_x @ updated_beta, axis=1)),
            }
            summary = {k:losses(np.full(len(test_y),r),z,test_y) for k,(r,z) in estimates.items()}
            summary['qwen_direct'] = float(np.sum((raw-test_y)**2,axis=1).mean())
            summary['pilot_choices'] = len(train_y)
            rows[n].append(summary)
    out = {}
    for n, trials in rows.items():
        out[n] = {k:float(np.mean([r[k] for r in trials])) for k in trials[0]}
        for model in ('source_only','source_local_refusal','source_updated'):
            delta = np.asarray([r['local']-r[model] for r in trials])
            out[n][model+'_over_local'] = {
                'win_rate':float(np.mean(delta>0)),
                'p05_p95':np.quantile(delta,[.05,.95]).tolist(),
            }
    return {'source_choices_range':[min(source_counts),max(source_counts)],'budgets':out}


def main():
    jobs, cards, people = dryer.deck()
    p, identities = dryer.predictions(jobs, dryer.RUN)
    if len(identities) != 1:
        raise ValueError('Mixed model versions')
    data = {}
    for country, group in people.items():
        ordered = [dict(sorted(row.items())) for row in group.values()]
        probs, y = dryer.outcome(p, ordered)
        keys = np.asarray([list(row) for row in ordered])
        x = np.asarray([[cards[k] for k in row] for row in keys])
        data[country] = probs, y, keys, x
    print(json.dumps({'seed':SEED,'splits':REPEATS,'new_calls':0,
        'studies':{target:compare(data[target],data[source])
                   for target,source in [('USA','CAN'),('CAN','USA')]}},indent=2))


if __name__=='__main__':
    main()
