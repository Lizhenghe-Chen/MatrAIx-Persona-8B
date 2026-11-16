"""Compare brand-history updates with price-aware prediction on scanner purchases."""
import json

import numpy as np
from scipy.special import softmax

from choice_predictor import fit_products
from order_screen import SEED
from personal_choice_products import STRENGTH
from personal_choice_update import forecasts
from scanner_brand_screen import DATASETS, load

METHODS = ('attributes', 'brand_frequency', 'history_only', 'frequency_half_history',
           'attributes_half_history', 'preference_update', 'matched_attributes', 'learned_history',
           'learned_other_history')


def evaluate(study):
    ids, price, feature, y, _ = load(study)
    price = 5 * (np.log(price) - np.log(price).mean(axis=1, keepdims=True))
    x = np.concatenate((np.broadcast_to(np.eye(4), (len(y), 4, 4)),
                        feature[..., None], price[..., None]), axis=-1)
    groups = {person: np.flatnonzero(ids == person)[:3] for person in np.unique(ids)}
    eligible = np.array([person for person, rows in groups.items() if len(rows) == 3])
    rng = np.random.default_rng(SEED)
    folds = np.array_split(rng.permutation(eligible), 5)
    losses, repeat, test_sizes = [], [], []
    for test in folds:
        set_test = set(test)
        train = ~np.isin(ids, test)
        targets = np.array([groups[p] for p in test])
        hist, target = targets[:, :2], targets[:, 2:]
        if not np.all(ids[hist] == ids[target]) or np.any(train[targets]):
            raise ValueError('Household or record leakage')
        beta = fit_products(x[train], np.column_stack((np.zeros(train.sum()), y[train])),
                            nonpositive_price=True)
        individual = forecasts(x, y, beta, hist, target, STRENGTH)
        base = individual['population'][:, 0]
        population = (y[train].sum(axis=0) + .5) / (train.sum() + 2)
        own = y[hist].mean(axis=1)
        other = np.roll(own, 1, axis=0)

        # Fit the history effect only using analogously constructed records
        # from households outside this fold, with the target price last.
        fit_rows = np.array([groups[p] for p in eligible if p not in set_test])
        history_share = y[fit_rows[:, :2]].mean(axis=1)
        fit_target = fit_rows[:, 2]
        fit_x = np.concatenate((x[fit_target, :, :-1], history_share[..., None],
                                x[fit_target, :, -1:]), axis=-1)
        fit_answers = np.column_stack((np.zeros(len(fit_target)), y[fit_target]))
        history_beta = fit_products(fit_x, fit_answers, nonpositive_price=True)
        matched_beta = fit_products(x[fit_target], fit_answers, nonpositive_price=True)
        matched = softmax(x[target[:, 0]] @ matched_beta, axis=1)

        def learned(h):
            chosen = target[:, 0]
            inputs = np.concatenate((x[chosen, :, :-1], h[..., None], x[chosen, :, -1:]), axis=-1)
            return softmax(inputs @ history_beta, axis=1)

        predictions = (base, np.broadcast_to(population, base.shape), own, (population + own) / 2,
                       (base + own) / 2, individual['own'][:, 0], matched, learned(own), learned(other))
        truth = y[target[:, 0]]
        repeat.extend(np.sum(own * truth, axis=1) > 0)
        losses.extend(np.column_stack([np.square(p - truth).sum(axis=1) for p in predictions]))
        test_sizes.append(len(test))
    error = np.asarray(losses)
    repeat = np.asarray(repeat)
    boot = rng.integers(len(error), size=(2000, len(error)))
    pairs = [('attributes', 'attributes_half_history'), ('attributes', 'preference_update'),
             ('attributes', 'learned_history'), ('matched_attributes', 'learned_history'), ('frequency_half_history', 'learned_history'),
             ('attributes_half_history', 'learned_history'), ('learned_other_history', 'learned_history')]
    gains = {}
    for ref, cand in pairs:
        delta = error[:, METHODS.index(ref)] - error[:, METHODS.index(cand)]
        gains[f'{cand}_over_{ref}'] = {'mean': float(delta.mean()),
                                      'ci95': np.quantile(delta[boot].mean(axis=1), [.025, .975]).tolist()}
    return {'source_sha256': DATASETS[study][0], 'total_households': len(groups), 'eligible': len(error),
            'fold_sizes': test_sizes, 'repeat_brand_count': int(repeat.sum()),
            'brier': dict(zip(METHODS, error.mean(axis=0).tolist(), strict=True)),
            'brier_brand_seen_in_history': dict(zip(METHODS, error[repeat].mean(axis=0).tolist(), strict=True)),
            'brier_brand_absent_from_history': dict(zip(METHODS, error[~repeat].mean(axis=0).tolist(), strict=True)),
            'gains': gains}


if __name__ == '__main__':
    print(json.dumps({'seed': SEED, 'new_model_calls': 0, 'record_order': 'source_file_only',
                      'studies': {study: evaluate(study) for study in DATASETS}}, indent=2))
