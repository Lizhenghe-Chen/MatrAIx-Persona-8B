"""Replay Qwen and price-only predictions on offers with similar prices."""

import json

import numpy as np
from scipy.special import softmax

import dryer_refusal as dryer
from cheese_pilot import evaluation_inputs, load_deck
from optout_pilot import load
from order_screen import SEED
from price_study_transfer import PRICE_UNITS

PRICE_ELASTICITY = -3.


def paired(gain, eligible):
    count = eligible.sum(axis=1)
    keep = count > 0
    if not keep.any():
        return None
    gain = np.where(eligible, gain, 0.).sum(axis=1)[keep] / count[keep]
    rng = np.random.default_rng(SEED)
    draws = rng.integers(len(gain), size=(2000, len(gain)))
    return {
        'people': int(keep.sum()), 'choices': int(count.sum()),
        'improvement': float(gain.mean()),
        'interval_95': np.quantile(gain[draws].mean(axis=1), [.025, .975]).tolist(),
    }


def screen(prob, truth, keys, prices, max_gap):
    if np.any(prices <= 0) or not np.isfinite(prices).all():
        raise ValueError('Expected positive full prices')
    mask = prices.max(axis=-1) <= (1 + max_gap) * prices.min(axis=-1) + 1e-9
    bought = mask & (truth[..., 0] == 0)
    cards = len(np.unique(keys[mask]))
    purchase_mass = prob[..., 1:].sum(axis=-1, keepdims=True)
    valid = purchase_mass[..., 0] > 0
    price = softmax(PRICE_ELASTICITY * np.log(prices), axis=-1)
    qwen = np.divide(prob[..., 1:], purchase_mass, out=price.copy(), where=valid[..., None])
    uniform = 1 / prices.shape[-1]
    refusal = 1 / prob.shape[-1]
    actual_refusal = truth[..., 0]
    baseline = np.concatenate((np.full_like(prob[..., :1], refusal), (1 - refusal) * price), axis=-1)
    conditional_qwen_loss = np.square(qwen - truth[..., 1:]).sum(axis=-1)
    # Supplemental replay: keep refusal fixed and borrow half of the model's product prediction.
    blended = baseline.copy()
    blended[..., 1:] = (1 - refusal) * (.5 * price + .5 * qwen)
    baseline_loss = np.square(baseline - truth).sum(axis=-1)
    return {
        'cards': cards, 'undefined_qwen_product_choices': int((bought & ~valid).sum()),
        'actual_refusal': float(actual_refusal[mask].mean()) if cards else None,
        'qwen_refusal': float(prob[..., 0][mask].mean()) if cards else None,
        'qwen_over_price_when_bought': paired(
            np.square(price - truth[..., 1:]).sum(axis=-1) - conditional_qwen_loss, bought),
        'qwen_over_uniform_when_bought': paired(
            np.square(uniform - truth[..., 1:]).sum(axis=-1) - conditional_qwen_loss, bought),
        'qwen_over_uniform_refusal': paired(
            2 * (np.square(refusal - actual_refusal) - np.square(prob[..., 0] - actual_refusal)), mask),
        'qwen_over_price_full': paired(
            baseline_loss - np.square(prob - truth).sum(axis=-1), mask),
        'half_qwen_products_over_price_full': paired(
            baseline_loss - np.square(blended - truth).sum(axis=-1), mask),
    }


def main():
    jobs, cards, groups = dryer.deck()
    predictions, identities = dryer.predictions(jobs, dryer.RUN)
    if len(identities) != 1:
        raise ValueError('Mixed dryer model identities')
    result = {}
    for country, people in groups.items():
        rows = list(people.values())
        prob, truth = dryer.outcome(predictions, rows)
        keys = np.asarray([list(row) for row in rows])
        features = np.asarray([cards[key] for key in keys.ravel()]).reshape(*keys.shape, 2, -1)
        result[country] = screen(prob, truth, keys, features[..., -1] * 200 + 900, .20)

    foods = load()
    foods['italy'] = evaluation_inputs(*load_deck())[0]
    for name in ('beer', 'italy'):
        prob, truth, keys, _, features = foods[name]
        offset, step = PRICE_UNITS[name]
        result[name] = screen(prob, truth, keys, features[..., -1] * step + offset, .10)
    print(json.dumps({'seed': SEED, 'calls': 0, 'price_elasticity': PRICE_ELASTICITY,
                      'relative_gap': {'dryer': .20, 'food': .10}, 'studies': result}, indent=2))


if __name__ == '__main__':
    main()
