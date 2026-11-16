"""Measure Qwen price response with controlled offers and score on original beef cards."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import json
import random

import numpy as np
from scipy.special import softmax

import beef_payment_screen as beef
from order_screen import SEED, WORK, encode, send
from optout_transfer import predictions
import protocol

RUN = WORK / 'beef-own-price-v1'
CENTER = beef.PRICES[-1]


def prepare():
    jobs = {}
    for condition, payment in beef.PAYMENT.items():
        offers = {'center': CENTER}
        for i, prices in enumerate(zip(*beef.PRICES[:16], strict=True)):
            for side, extreme in [('low', min(prices)), ('high', max(prices))]:
                changed = list(CENTER)
                changed[i] = extreme
                offers[f'product{i + 1}-{side}'] = changed
        for key, prices in offers.items():
            options = {str(i): f'{label} ribeye steak, USD {price / 100:.2f}'
                       for i, (label, price) in enumerate(zip(beef.OPTIONS[:-1], prices, strict=True), 1)}
            options['6'] = 'None of these'
            question = {'id': 'offer', 'prompt': 'Which steak, if any, would you purchase?', 'options': options}
            body = protocol.build({'title': 'Ribeye steak choices', 'context': beef.CONTEXT + payment,
                                   'questions': [question], 'basic': {}}, 'basic', 'qwen', {}, {}, 512)
            jobs[condition, key] = {'questions': [question], 'body': body}
    return jobs


def price_model(anchor, slopes, prices):
    log_odds = np.log(np.maximum(anchor, .005))
    changes = (prices - np.array(CENTER)) / 100
    return softmax(np.r_[log_odds[:5] + changes * slopes, log_odds[5]])


def score(jobs):
    p, ids = predictions(jobs, RUN)
    frozen, prior_ids, failures = beef.load_predictions(beef.freeze())
    if failures or len(ids | prior_ids) != 1:
        raise ValueError('Missing predictions or mixed model versions')
    truth, _ = beef.load_responses(beef.SOURCE)
    results = {}
    rng = np.random.default_rng(SEED)
    for condition, choices in truth.items():
        def prob(key):
            return np.array([p[condition, key][str(i)] for i in range(1, 7)])

        anchor = prob('center')
        profiles = []
        for j, prices in enumerate(zip(*beef.PRICES[:16], strict=True), 1):
            low, high = prob(f'product{j}-low'), prob(f'product{j}-high')
            # Estimate own-versus-outside log odds per dollar, with a fixed floor.
            odds = np.log(np.maximum([high[j - 1], low[5]], .005)).sum() - np.log(
                np.maximum([low[j - 1], high[5]], .005)).sum()
            slope = odds / ((max(prices) - min(prices)) / 100)
            profiles.append({'product': beef.OPTIONS[j - 1], 'low_price': min(prices), 'high_price': max(prices),
                             'share_at_low': float(low[j - 1]), 'share_at_high': float(high[j - 1]),
                             'raw_log_odds_slope': float(slope)})
        slopes = np.array([row['raw_log_odds_slope'] for row in profiles])
        indices = [i for i, row in enumerate(beef.PRICES[:16])
                   if np.count_nonzero(np.asarray(row) != CENTER) > 1]
        cards = np.asarray(beef.PRICES)[indices]
        observed = np.eye(6)[np.asarray(choices)[:, indices] - 1].mean(axis=0)
        direct = np.array([frozen['direct', condition, f'card{i + 1:02}'] for i in indices])
        estimates = {'direct': direct, 'same_price_anchor': np.broadcast_to(anchor, observed.shape),
                     'price_model': np.array([price_model(anchor, slopes, row) for row in cards]),
                     'monotone_price_model': np.array([price_model(anchor, np.minimum(slopes, 0), row) for row in cards])}
        losses = {name: .5 * np.abs(values - observed).sum(axis=1) for name, values in estimates.items()}
        draws = rng.integers(len(cards), size=(2000, len(cards)))
        improvements = {}
        for name in ('direct', 'same_price_anchor', 'price_model'):
            delta = losses[name] - losses['monotone_price_model']
            improvements[name] = np.quantile(delta[draws].mean(axis=1), [.025, .975]).tolist()
        actual = np.asarray(choices)
        matched_human = (actual[:, 16] == 1).mean() - (actual[:, 13] == 1).mean()
        matched_qwen = frozen['direct', condition, 'card17'][0] - frozen['direct', condition, 'card14'][0]
        constrained = np.minimum(slopes, 0)
        matched_low = price_model(anchor, constrained, np.array(beef.PRICES[13]))[0]
        matched_high = price_model(anchor, constrained, np.array(beef.PRICES[16]))[0]
        results[condition] = {'people': len(actual), 'held_out_cards': len(indices), 'price_profiles': profiles,
                              'increases_after_price_rise': sum(row['share_at_high'] > row['share_at_low']
                                                                for row in profiles),
                              'observed_single_price_pair': {'human': float(matched_human), 'qwen': matched_qwen,
                                                             'monotone_price_model': float(matched_high - matched_low)},
                              'tv': {name: float(values.mean()) for name, values in losses.items()},
                              'monotone_gain_interval_95': improvements}
    return {'requests': len(jobs), 'valid': len(p), 'identity': json.loads(next(iter(ids))), 'studies': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    action = parser.parse_args().action
    jobs = prepare()
    frozen = list(jobs.values())
    random.Random(SEED).shuffle(frozen)
    RUN.mkdir(mode=0o700, exist_ok=True)
    manifest = RUN / 'jobs.json'
    if manifest.exists() and manifest.read_bytes() != encode(frozen):
        raise ValueError('Frozen requests changed')
    if not manifest.exists():
        manifest.write_bytes(encode(frozen))
    if action == 'run':
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(partial(send, directory=RUN), frozen))
    print(json.dumps(score(jobs), indent=2))
