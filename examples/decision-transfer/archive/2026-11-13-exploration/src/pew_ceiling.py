"""Ceiling test on Pew Wave 13: how much of a person's answers is predictable at all?

Answers three questions with real data before any model is called:
1. How split is each item (a degenerate item cannot show individual differences)?
2. How much of the variance is between people (information a profile could carry)?
3. What does a demographics-only model achieve out of sample, versus predicting the
   marginal for everyone?
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

SAV = Path('/tmp/w13/W13_Dec15/ATP W13.sav')
OUT = Path(__file__).resolve().parents[1] / 'data/pew13-ceiling.json'
# Binarised so every item is a two-option question, matching the frozen decoder.
ITEMS = {
    'SHOP6A_W13': ('look at or try out the product in person', 1),
    'SHOP6B_W13': ('read ratings or reviews online', 1),
    'SHOP6C_W13': ('buy online without a store trip', 1),
    'SHOP6D_W13': ('compare prices from different sellers', 1),
    'SHOP6E_W13': ('ask questions about what they are buying', 1),
    'SHOP6F_W13': ('get advice from people they know', 1),
    'SHOP6G_W13': ('buy from a familiar store or seller', 1),
    'SHOP7A_W13': ('government should ensure products are safe', 1),
    'SHOP7B_W13': ('government should make consumers confident', 1),
    'SHOP7C_W13': ('government should hold companies accountable', 1),
    'SHOP20B_W13': ('check online for a better price', 1),
    'SHOP20C_W13': ('look up reviews before buying', 1),
    'SHOP20D_W13': ('call or text someone about a purchase', 1),
}
DEMOGRAPHICS = ['F_AGECAT_FINAL', 'F_SEX_FINAL', 'F_EDUCCAT_FINAL', 'F_INCOME_FINAL',
                'F_RACETHN_RECRUITMENT', 'F_CREGION_FINAL', 'F_PARTY_FINAL']


def two_option_brier(p, y):
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    return float(np.mean((p - y) ** 2 + ((1 - p) - (1 - y)) ** 2))


def load():
    import pyreadstat
    frame, meta = pyreadstat.read_sav(str(SAV))
    keep = {}
    for column, (label, positive) in ITEMS.items():
        series = frame[column]
        if meta.variable_value_labels.get(column, {}).get(5.0) == 'Refused' or True:
            series = series.where(series <= 4)
        keep[column] = (series == positive).astype(float).where(series.notna())
    answers = pd.DataFrame(keep)
    return frame, answers


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def rasch_decomposition(values, rounds=40):
    """p_ij = sigmoid(a_i + b_j). Item effects are what a card shows; person effects are
    what only knowing the person can add. Returns the two prediction matrices."""
    y = values.astype(float)
    n, k = y.shape
    b = np.log(y.mean(axis=0) / (1 - y.mean(axis=0)))
    b -= b.mean()
    a = np.zeros(n)
    for _ in range(rounds):
        for _ in range(3):
            p = _sigmoid(a[:, None] + b[None, :])
            residual = (y - p).sum(axis=1)
            weight = (p * (1 - p)).sum(axis=1) + 1e-9
            a = a + residual / weight * 0.5
        p = _sigmoid(a[:, None] + b[None, :])
        b = b + (y - p).sum(axis=0) / ((p * (1 - p)).sum(axis=0) + 1e-9) * 0.5
        b -= b.mean()
    item_only = np.repeat(_sigmoid(b)[None, :], n, axis=0)
    with_person = _sigmoid(a[:, None] + b[None, :])
    return item_only, with_person


def _fit_item_effects(y, rounds=40):
    b = np.log(y.mean(axis=0) / (1 - y.mean(axis=0)))
    b -= b.mean()
    for _ in range(rounds):
        p = _sigmoid(b[None, :])
        b = b + (y - p).mean(axis=0) / ((p * (1 - p)).mean(axis=0) + 1e-9) * 0.3
        b -= b.mean()
    return b


def transfer(frame, fit_items, test_items, label):
    """Does a person effect learned on one battery carry to the other? Honest ceiling,
    because the estimate never sees the answers it is scored on."""
    a_values = frame[fit_items].to_numpy()
    b_values = frame[test_items].to_numpy()
    b_fit = _fit_item_effects(a_values)
    b_test = _fit_item_effects(b_values)
    n = len(a_values)
    person = np.zeros(n)
    for _ in range(40):
        p = _sigmoid(person[:, None] + b_fit[None, :])
        person = person + (a_values - p).sum(axis=1) / ((p * (1 - p)).sum(axis=1) + 1e-9) * 0.4
    predicted = _sigmoid(person[:, None] + b_test[None, :])
    reference = np.repeat(_sigmoid(b_test)[None, :], n, axis=0)
    ref_brier = two_option_brier(reference, b_values)
    person_brier = two_option_brier(predicted, b_values)
    return {'split': label, 'fit_items': len(fit_items), 'test_items': len(test_items),
            'brier_item_only': round(ref_brier, 4), 'brier_with_person_effect': round(person_brier, 4),
            'gain': round(ref_brier - person_brier, 4)}


def run():
    frame, answers = load()
    complete = answers.dropna()
    people = len(complete)
    stats = {}
    for column, (label, _) in ITEMS.items():
        share = float(complete[column].mean())
        stats[column] = {'label': label, 'share_positive': round(share, 4),
                         'max_option_share': round(max(share, 1 - share), 4)}
    person_rate = complete.mean(axis=1)
    between = float(person_rate.var(ddof=1))
    within = float(complete.sub(person_rate, axis=0).var(ddof=1).mean())
    icc = between / (between + within) if between + within else 0.0

    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import KFold

    demo = frame[DEMOGRAPHICS].astype('object')
    demo = demo.fillna('missing')
    design = pd.get_dummies(demo, dummy_na=False).astype(float)
    design = design.loc[complete.index]

    rows = []
    folds = KFold(n_splits=5, shuffle=True, random_state=20261109)
    for column, (label, _) in ITEMS.items():
        y = complete[column].to_numpy()
        marginal = np.full(len(y), y.mean())
        predictions = np.zeros(len(y))
        for train, test in folds.split(design):
            model = LogisticRegression(max_iter=500, C=1.0)
            model.fit(design.iloc[train], y[train])
            predictions[test] = model.predict_proba(design.iloc[test])[:, 1]
        rows.append({'item': column, 'label': label, 'share': round(float(y.mean()), 4),
                     'brier_marginal': round(two_option_brier(marginal, y), 4),
                     'brier_demographics': round(two_option_brier(predictions, y), 4)})

    values = complete.to_numpy()
    item_only, person_only = rasch_decomposition(values)
    transfers = [
        transfer(complete, ['SHOP6A_W13', 'SHOP6C_W13', 'SHOP6E_W13', 'SHOP6G_W13'],
                 ['SHOP6B_W13', 'SHOP6D_W13', 'SHOP6F_W13'], 'importance odd to even'),
        transfer(complete, ['SHOP6A_W13', 'SHOP6B_W13', 'SHOP6C_W13', 'SHOP6D_W13'],
                 ['SHOP6E_W13', 'SHOP6F_W13', 'SHOP6G_W13'], 'importance first four to last three'),
        transfer(complete, ['SHOP6A_W13', 'SHOP6B_W13', 'SHOP6C_W13', 'SHOP6D_W13', 'SHOP6E_W13',
                            'SHOP6F_W13', 'SHOP6G_W13'], ['SHOP7A_W13', 'SHOP7B_W13', 'SHOP7C_W13'],
                 'importance to government role'),
        transfer(complete, ['SHOP20B_W13', 'SHOP20C_W13'], ['SHOP20D_W13'], 'behaviour pair to behaviour'),
    ]

    summary = {
        'date': '2026-11-13',
        'source': 'Pew American Trends Panel Wave 13 (Dec 2015), ATP W13.sav',
        'people_with_all_items': people,
        'items': len(ITEMS),
        'single_option_share_median': round(float(np.median([s['max_option_share'] for s in stats.values()])), 4),
        'icc_between_person': round(icc, 4),
        'brier_marginal_average': round(float(np.mean([r['brier_marginal'] for r in rows])), 4),
        'brier_demographics_average': round(float(np.mean([r['brier_demographics'] for r in rows])), 4),
        'brier_item_only_reference': round(two_option_brier(item_only, values), 4),
        'brier_with_true_person_effect': round(two_option_brier(person_only, values), 4),
        'headroom_from_person_effect': round(two_option_brier(item_only, values)
                                            - two_option_brier(person_only, values), 4),
        'cross_item_transfer': transfers,
        'per_item': rows,
        'icc_note': 'Share of item variance that sits between people; an upper bound on what any profile could carry.',
        'limitations': [
            'Binarised items (top category versus the rest); other splits would shift the levels.',
            'Demographics are a lower bound on profile information: richer audited facts could carry more.',
            'The oracle row uses the respondent\'s other answers, which the protocol forbids as input; it is a '
            'ceiling only, never a method.',
        ],
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + '\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    result = run()
    print(json.dumps(result if args.json else {k: v for k, v in result.items() if k != 'per_item'},
                     ensure_ascii=False, indent=1))
