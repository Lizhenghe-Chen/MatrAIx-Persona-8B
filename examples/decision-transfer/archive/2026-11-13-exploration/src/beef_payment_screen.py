"""Compare paired Qwen predictions for hypothetical and potentially binding purchases."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import json
import random

import numpy as np
from scipy.special import softmax

from choice_predictor import fit_products

from beef_admission import OPTIONS, PRICES, SOURCE, SOURCE_SHA, load_responses
from order_screen import WORK, SEED, encode, read, result_path, send
import protocol

RUN = WORK / 'beef-payment-v1'
CONTEXT = (
    'Participants in a US consumer study were shown five 12-ounce ribeye steaks and given '
    'product information. Each task shows the price of each whole steak in US dollars. '
    'A participant can choose one steak or none. '
)
PAYMENT = {
    'incentivized': 'After all tasks, one of the 17 tasks will be selected at random. '
    'Participants must pay the displayed price and receive the steak they selected on '
    'that task. Participants who selected none on that task will make no purchase.',
    'hypothetical': 'Participants should make their choices as realistically as they can, '
    'considering that they would buy at most one steak. No actual payment or purchase will occur.',
}
APPROACH = {
    'direct': '',
    'separate': ' To estimate the probabilities, first assess the chance of buying none '
    'under these purchase conditions. Then estimate relative preferences among the steaks '
    'conditional on buying. Combine those estimates into one probability distribution '
    'over the six options. Return only the requested JSON.',
}


def freeze():
    jobs = []
    for card, prices in enumerate(PRICES, 1):
        options = {str(i): f'{label} ribeye steak, USD {price / 100:.2f}'
                   for i, (label, price) in enumerate(zip(OPTIONS[:-1], prices, strict=True), 1)}
        options['6'] = 'None of these'
        q = {'id': f'card{card:02}', 'prompt': 'Which steak, if any, would you purchase?',
             'options': options}
        for approach, extra in APPROACH.items():
            for condition, payment in PAYMENT.items():
                body = protocol.build({'title': 'Ribeye steak choices',
                                       'context': CONTEXT + payment + extra,
                                       'questions': [q], 'basic': {}},
                                      'basic', 'qwen', {}, {}, 512)
                jobs.append({'condition': condition, 'approach': approach,
                             'body': body, 'questions': [q]})
    random.Random(SEED).shuffle(jobs)
    RUN.mkdir(mode=0o700, exist_ok=True)
    manifest = RUN / 'jobs.json'
    if manifest.exists() and manifest.read_bytes() != encode(jobs):
        raise ValueError('Frozen requests changed')
    if not manifest.exists():
        manifest.write_bytes(encode(jobs))
    return jobs


def load_predictions(jobs):
    predictions = {}
    identities = set()
    errors = {}
    for job in jobs:
        qid = job['questions'][0]['id']
        path = result_path(job, RUN)
        key = (job['approach'], job['condition'], qid)
        if not path.exists():
            errors['missing'] = errors.get('missing', 0) + 1
            continue
        result = read(path)
        if result['status'] != 'ok':
            reason = result['type']
            errors[reason] = errors.get(reason, 0) + 1
            continue
        identities.add(json.dumps(result['identity'], sort_keys=True))
        probabilities = result['p'][qid]
        predictions[key] = [probabilities[str(i)] for i in range(1, 7)]
    return predictions, identities, errors


def pilot_replay(truth, direct):
    """Use disjoint cards and people to compare affordable calibration options."""
    rng = np.random.default_rng(SEED)
    target = truth['incentivized'][:, :16]
    source = truth['hypothetical'][:, :16]
    prices = np.asarray(PRICES[:16], dtype=float)
    price = 5 * (np.log(prices) - np.log(prices).mean(axis=1, keepdims=True))
    x = np.concatenate((np.broadcast_to(np.eye(5), (16, 5, 5)), price[..., None]), axis=2)
    predictions = direct['incentivized'][:16]
    rows = []
    for _ in range(100):
        train, test = np.split(rng.permutation(16), [8])
        order = rng.permutation(len(target))
        local = target[order[:10]][:, train]
        test_y = target[order[10:]][:, test]
        hist = source[:, train]
        local_rate = (local[..., -1].sum() + .5) / (local.shape[0] * len(train) + 1)
        hist_rate = (hist[..., -1].sum() + .5) / (hist.shape[0] * len(train) + 1)

        def product_probabilities(y):
            features = np.broadcast_to(x[train], (*y.shape[:2], 5, x.shape[-1]))
            labels = np.roll(y, 1, axis=-1).reshape(-1, 6)
            beta = fit_products(features.reshape(-1, 5, x.shape[-1]), labels, nonpositive_price=True)
            return softmax(x[test] @ beta, axis=1)

        raw = predictions[test]
        mass = raw[:, :-1].sum(axis=1, keepdims=True)
        model_products = np.divide(raw[:, :-1], mass, out=np.full_like(raw[:, :-1], .2), where=mass > 0)
        hist_products = product_probabilities(hist)
        local_products = product_probabilities(local)
        combined = {'qwen_raw': raw}
        for name, conditional, rate in (
            ('qwen_products_local_rate', model_products, local_rate),
            ('hypothetical_only', hist_products, hist_rate),
            ('hypothetical_products_local_rate', hist_products, local_rate),
            ('local_only', local_products, local_rate),
            ('uniform_products_local_rate', np.full_like(local_products, .2), local_rate),
        ):
            combined[name] = np.column_stack((conditional * (1 - rate), np.full(len(test), rate)))
        rows.append({name: {
            'brier': float(np.sum((probs - test_y) ** 2, axis=-1).mean()),
            'no_buy_brier': float(np.mean((probs[:, -1] - test_y[..., -1]) ** 2)),
            'absolute_no_buy_share_error': float(abs(probs[:, -1].mean() - test_y[..., -1].mean())),
        } for name, probs in combined.items()})
    return {name: {metric: float(np.mean([row[name][metric] for row in rows]))
                   for metric in rows[0][name]} for name in rows[0]}


def score(jobs):
    predictions, identities, errors = load_predictions(jobs)
    if errors or len(identities) != 1:
        raise ValueError(f'Incomplete or inconsistent responses: {errors}; identities: {len(identities)}')
    cohorts, _ = load_responses(SOURCE)
    truth = {group: np.eye(6)[np.asarray(rows) - 1] for group, rows in cohorts.items()}
    shares = {group: y.mean(axis=0) for group, y in truth.items()}
    groups = list(PAYMENT)
    observed_gap = shares[groups[0]][:, -1] - shares[groups[1]][:, -1]
    rng = np.random.default_rng(SEED)
    boot_rates = {}
    for group, y in truth.items():
        people = y[:, :, -1].mean(axis=1)
        boot_rates[group] = people[rng.integers(len(y), size=(2000, len(y)))].mean(axis=1)
    gap_interval = np.quantile(boot_rates[groups[0]] - boot_rates[groups[1]], [.025, .975])
    arrays = {approach: {group: np.asarray([predictions[approach, group, f'card{i:02}']
                                           for i in range(1, len(PRICES) + 1)])
                         for group in groups} for approach in APPROACH}
    results = {}
    for approach, estimates in arrays.items():
        gap = estimates[groups[0]][:, -1] - estimates[groups[1]][:, -1]
        results[approach] = {
            'predicted_gap': float(gap.mean()),
            'gap_mean_absolute_error': float(np.abs(gap - observed_gap).mean()),
            'cards_with_positive_gap': int((gap > 0).sum()),
            'by_group': {group: {
                'predicted_no_buy': float(p[:, -1].mean()),
                'brier': float(np.sum((p - truth[group]) ** 2, axis=-1).mean()),
                'mean_tv': float(.5 * np.abs(p - shares[group]).sum(axis=1).mean()),
                'no_buy_card_mae': float(np.abs(p[:, -1] - shares[group][:, -1]).mean()),
            } for group, p in estimates.items()},
        }
    return {
        'workbook_sha256': SOURCE_SHA,
        'identity': json.loads(next(iter(identities))),
        'valid_requests': len(predictions),
        'human_gap': float(observed_gap.mean()),
        'human_gap_person_bootstrap_95': gap_interval.tolist(),
        'human_cards_with_positive_gap': int((observed_gap > 0).sum()),
        'no_change_gap_mae': float(np.abs(observed_gap).mean()),
        'approaches': results,
        'ten_person_pilot_replay': pilot_replay(truth, arrays['direct']),
        'cards': [{'card': i + 1, 'prices_cents': PRICES[i],
                   'human': {g: shares[g][i].tolist() for g in groups},
                   'predictions': {a: {g: p[i].tolist() for g, p in est.items()}
                                   for a, est in arrays.items()}}
                  for i in range(len(PRICES))],
        'option_order': OPTIONS,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    action = parser.parse_args().action
    jobs = freeze()
    if action == 'run':
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(partial(send, directory=RUN), jobs))
        predictions, identities, errors = load_predictions(jobs)
        print(json.dumps({'expected': len(jobs), 'valid': len(predictions),
                          'identities': len(identities), 'errors': errors}, indent=2))
    else:
        print(json.dumps(score(jobs), indent=2))
