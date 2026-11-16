"""Restore refusal to scoring while reusing the frozen streaming predictions."""
import json

import numpy as np
from scipy.special import softmax

from choice_predictor import fit_products
from optout_transfer import predictions
from order_screen import SEED, result_path
import streaming_price_mix as streaming
import streaming_pro_replication as pro


def load_predictions(x, test):
    qwen_jobs = streaming.build(x, test)
    pro_jobs = pro.build(x, test)
    pro_jobs = {k: ({**job, 'attempt': 2}
                    if result_path({**job, 'attempt': 2}, pro.RUN).exists() else job)
                for k, job in pro_jobs.items()}
    raw = {}
    identities = {}
    for name, jobs, directory in [('qwen', qwen_jobs, streaming.RUN), ('pro', pro_jobs, pro.RUN)]:
        pred, ids = predictions(jobs, directory)
        if len(ids) != 1 or set(jobs) != set(qwen_jobs):
            raise ValueError('Unexpected model identity or task coverage')
        identities[name] = json.loads(next(iter(ids)))
        raw[name] = np.array([[pred[k][str(i)] for i in range(5)] for k in qwen_jobs])
    return raw, identities


def main():
    x, y, train, test = streaming.load()
    raw, identities = load_predictions(x, test)
    conditional = {}
    for name, p in raw.items():
        mass = p[:, 1:].sum(axis=1, keepdims=True)
        conditional[name] = np.divide(p[:, 1:], mass, out=np.full_like(p[:, 1:], .25), where=mass > 0)

    x = np.concatenate((x[..., 1:], (x[..., :1] - 9.99) / 2), axis=-1)
    rng = np.random.default_rng(SEED + 1)
    results = {n: [] for n in streaming.SIZES}
    refusal_rates = []
    for _ in range(100):
        order = rng.permutation(len(y))
        test_mask = ~np.isin(np.nonzero(test)[0], order[:max(streaming.SIZES)])
        truth = y[test][test_mask]
        target = x[test][test_mask]
        refusal_rates.append(float(truth[:, 0].mean()))
        for n, rows in results.items():
            pilot = order[:n]
            available = train[pilot]
            xx, yy = x[pilot][available], y[pilot][available]
            refusal = (yy[:, 0].sum() + .5) / (len(yy) + 1)
            full = softmax(target @ fit_products(xx, yy, nonpositive_price=True), axis=-1)
            price = softmax(target[..., -1:] @ fit_products(xx[..., -1:], yy, nonpositive_price=True), axis=-1)
            methods = {name: p[test_mask] for name, p in raw.items()}
            products = {'local_full': full, 'local_price': price,
                        'price_uniform': (1 - streaming.WEIGHT) * price + streaming.WEIGHT * .25}
            for name, p in conditional.items():
                products[f'price_{name}'] = (1 - streaming.WEIGHT) * price + streaming.WEIGHT * p[test_mask]
            for name, product in products.items():
                methods[name] = np.column_stack((np.full(len(truth), refusal), (1 - refusal) * product))
            # Cross the refusal source with the same conditional product forecast.
            for name in conditional:
                model_refusal = raw[name][test_mask, :1]
                methods[f'price_{name}_model_refusal'] = np.column_stack(
                    (model_refusal, (1 - model_refusal) * products[f'price_{name}']))
            rows.append({name: [float(np.square(pred - truth).sum(axis=-1).mean()),
                                float(np.square(pred[:, 0] - truth[:, 0]).mean()),
                                float(pred[:, 0].mean())] for name, pred in methods.items()})
    summary = {}
    for n, rows in results.items():
        scores = {name: np.array([r[name] for r in rows]) for name in rows[0]}
        gains = {}
        for candidate in ('price_qwen', 'price_pro'):
            for base in ('local_price', 'local_full', 'price_uniform'):
                delta = scores[base][:, 0] - scores[candidate][:, 0]
                gains[f'{candidate}_over_{base}'] = {
                    'mean': float(delta.mean()), 'wins': int((delta > 1e-10).sum()),
                    'p05_p95': np.quantile(delta, [.05, .95]).tolist(),
                }
        summary[n] = {'scores': {k: v.mean(axis=0).tolist() for k, v in scores.items()}, 'gains': gains}
    print(json.dumps({'source_sha256': streaming.DIGEST, 'seed': SEED, 'replays': 100, 'new_calls': 0,
                      'identities': identities, 'test_people_per_split': len(y) - max(streaming.SIZES),
                      'test_cards_per_split': len(truth), 'mean_observed_refusal': float(np.mean(refusal_rates)),
                      'score_order': ['full_brier', 'binary_refusal_brier', 'predicted_refusal'],
                      'budgets': summary}, indent=2))


if __name__ == '__main__':
    main()
