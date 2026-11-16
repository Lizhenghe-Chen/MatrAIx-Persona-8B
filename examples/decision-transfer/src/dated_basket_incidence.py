"""Predict the next observed basket, including absence of a target category."""
from collections import Counter
import json

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

import dated_purchase_repeat as labels
import grocery_next_basket as grocery
from order_screen import SEED

NO_BUY = '__no_category__'
OTHER = '__mixed_or_unseen_label__'
PRIOR_BASKETS = 10
METHODS = ('market', 'history_label_only', 'history_incidence_only',
           'smoothed_frequency_and_label', 'history_both')


def examples(baskets, category_visits):
    previous = []
    category_count = 0
    for i, stamp in enumerate(baskets):
        current = category_visits.get(stamp, NO_BUY)
        if len(previous) >= 2 and previous[-1][1] and previous[-2][1]:
            origin = baskets[i - 1]
            last_date = baskets[previous[-1][0]]
            elapsed_days = (origin - last_date).total_seconds() / 86400
            features = [1., category_count / i, np.log1p(i - 1 - previous[-1][0]),
                        np.log1p(elapsed_days) / 4]
            yield i, (previous[-2][1], previous[-1][1]), features, current or OTHER, i
        if current != NO_BUY:
            previous.append((i, current))
            category_count += 1


def fit_incidence(rows):
    x = np.array([features for _, features, _, _ in rows])
    y = np.array([target != NO_BUY for _, _, target, _ in rows], dtype=float)
    penalty = np.array([0., .01, .01, .01])

    def objective(beta):
        z = x @ beta
        return (np.mean(np.logaddexp(0, z) - y * z) + penalty @ beta**2,
                x.T @ (expit(z) - y) / len(y) + 2 * penalty * beta)

    fit = minimize(objective, np.zeros(x.shape[1]), jac=True)
    if not fit.success:
        raise RuntimeError(fit.message)
    return float((y.sum() + .5) / (len(y) + 1)), fit.x


def evaluate(visits, history, first_targets):
    by_person = {person: rows.droplevel('household_id').to_dict()
                 for person, rows in visits.groupby(level='household_id')}
    people = sorted(set(history) | set(first_targets))
    cohort = set(np.random.default_rng(SEED).permutation(people)[::3])
    train, test = [], []
    for person in people:
        past = history.get(person, [])
        stamps = [t for t, _ in past]
        records = by_person.get(person, {})
        if person in cohort:
            if not past or person not in first_targets:
                continue
            stamps.append(first_targets[person])
            test.extend((seen, x, outcome, count) for index, seen, x, outcome, count in examples(stamps, records)
                        if index == len(stamps) - 1)
        else:
            train.extend((seen, x, outcome, count) for _, seen, x, outcome, count in examples(stamps, records))
    return score(train, test)


def score(train, test):
    rate, beta = fit_incidence(train)
    counts = Counter(outcome for _, _, outcome, _ in train if outcome != NO_BUY)
    catalogue = sorted((set(counts) - {OTHER}) | {OTHER})
    index = {name: i for i, name in enumerate(catalogue)}
    market = np.array([counts[k] + .5 for k in catalogue])
    market /= market.sum()
    joint, binary, chosen_errors, observed = [], [], [], []
    for seen, x, outcome, count in test:
        bought = outcome != NO_BUY
        code = index.get(outcome, index[OTHER])
        own = np.bincount([index.get(k, index[OTHER]) for k in seen], minlength=len(market)) / 2
        personal = .5 * market + .5 * own
        buy_probability = float(expit(x @ beta))
        frequency = (x[1] * count + PRIOR_BASKETS * rate) / (count + PRIOR_BASKETS)
        rates = np.array([rate, rate, buy_probability, frequency, buy_probability])
        conditional = np.stack([market, personal, market, personal, personal])
        product = rates[:, None] * conditional
        joint.append(np.square(product).sum(axis=1) + np.square(1 - rates) + 1
                     - 2 * (product[:, code] if bought else 1 - rates))
        binary.append(np.square(rates - bought))
        if bought:
            chosen_errors.append(np.square(conditional).sum(axis=1) + 1 - 2 * conditional[:, code])
        observed.append(bought)
    scores = np.asarray(joint)
    boot = np.random.default_rng(SEED + 1).integers(len(test), size=(2000, len(test)))
    def summarize_gain(delta):
        interval = None
        if len(delta) > 1:
            interval = np.quantile(delta[boot].mean(axis=1), [.025, .975]).tolist()
        return {'mean': float(delta.mean()), 'ci95': interval}

    gains = {method: summarize_gain(scores[:, i] - scores[:, -1])
             for i, method in enumerate(METHODS[:-1])}
    smooth_gain = summarize_gain(scores[:, 0] - scores[:, METHODS.index('smoothed_frequency_and_label')])
    return {'smoothed_over_market': smooth_gain, 'test_households': len(test), 'category_purchases': int(sum(observed)),
            'training_visits': len(train), 'constant_buy_probability': rate,
            'joint_brier': dict(zip(METHODS, scores.mean(axis=0).tolist(), strict=True)),
            'incidence_brier': dict(zip(METHODS, np.mean(binary, axis=0).tolist(), strict=True)),
            'choice_given_purchase_brier': dict(zip(METHODS, np.mean(chosen_errors, axis=0).tolist(), strict=True)),
            'joint_gains': gains}


def main():
    visits = labels.load()
    _, history, _, _ = grocery.load(dated=True)
    # Use the same positive, catalog-matched transaction filter for all baskets.
    tx = grocery.pyreadr.read_r(str(grocery.SOURCE / 'transactions.rds'))[None]
    meta = grocery.pyreadr.read_r(str(grocery.SOURCE / 'products.rda'))['products']
    catalog = meta.dropna(subset=['product_id', 'department', 'product_category'])
    catalog = catalog[catalog.department.str.strip().ne('') & catalog.product_category.str.strip().ne('')]
    valid = tx.quantity.gt(0) & tx.sales_value.gt(0) & tx.product_id.isin(catalog.product_id)
    after = tx.loc[valid & tx.transaction_timestamp.ge(grocery.CUTOFF)]
    first = after.groupby('household_id').transaction_timestamp.min().to_dict()
    print(json.dumps({'sources': grocery.HASHES, 'cutoff': str(grocery.CUTOFF.date()), 'seed': SEED,
                      'new_model_calls': 0, 'prior_baskets': PRIOR_BASKETS, 'categories': {
                          category: evaluate(visits.loc[category], history, first) for category in labels.CATEGORIES
                      }}, indent=2))


if __name__ == '__main__':
    main()
