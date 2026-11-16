"""Compare a fixed Qwen blend with pure statistics on paid product choices."""
import json

import numpy as np
from scipy.special import softmax

import orange_payment_transfer as orange
from beef_admission import PRICES, SOURCE, SOURCE_SHA, load_responses
from choice_predictor import fit_products
from order_screen import SEED
from payment_loss_decomposition import RESULT

WEIGHT = .25
REPLAYS = 100


def evaluate(features, p, source_ids, source, paid_ids, paid, *, source_budget=None):
    rng = np.random.default_rng(SEED)
    blocks = np.unique(paid_ids, axis=0)
    memberships = np.isin(np.arange(len(features)), blocks[0])
    if len(blocks) == 1:
        pools = [np.arange(len(features))]
    else:
        if len(blocks) != 2:
            raise ValueError('Expected one or two blocks')
        other = np.isin(np.arange(len(features)), blocks[1])
        pools = [np.flatnonzero(mask) for mask in (memberships & other, memberships & ~other,
                                                   other & ~memberships)]
    if not np.isfinite(p).all() or not np.allclose(p.sum(axis=1), 1):
        raise ValueError('Invalid model probabilities')
    uniform = np.full_like(p, 1 / p.shape[1])
    rows = []
    training_choices = []
    people_rng = np.random.default_rng(SEED + 1)
    for _ in range(REPLAYS):
        train = np.concatenate([rng.permutation(pool)[:len(pool) // 2] for pool in pools])
        source_mask = np.isin(source_ids, train) & (source.sum(axis=-1) == 1)
        if source_budget is not None:
            sampled = people_rng.permutation(len(source))[:source_budget]
            source_mask &= np.isin(np.arange(len(source)), sampled)[:, None]
            training_choices.append(int(source_mask.sum()))
        beta = fit_products(features[source_ids[source_mask]],
                            np.column_stack((np.zeros(source_mask.sum()), source[source_mask])),
                            nonpositive_price=True)
        historical = softmax(features @ beta, axis=1)
        # All paid respondents are eligible because no paid answers are used to fit.
        mask = ~np.isin(paid_ids, train) & (paid.sum(axis=-1) == 1)
        ids, y = paid_ids[mask], paid[mask]
        methods = {'historical': historical, 'qwen': p,
                   'historical_plus_qwen': (1 - WEIGHT) * historical + WEIGHT * p,
                   'historical_plus_uniform': (1 - WEIGHT) * historical + WEIGHT * uniform}
        rows.append({name: float(np.square(probs[ids] - y).sum(axis=1).mean())
                     for name, probs in methods.items()})
    scores = {key: np.array([r[key] for r in rows]) for key in rows[0]}
    comparisons = {}
    for base in ('historical', 'historical_plus_uniform'):
        delta = scores[base] - scores['historical_plus_qwen']
        comparisons[base] = {'gain': float(delta.mean()), 'win_rate': float(np.mean(delta > 0)),
                             'p05_p95': np.quantile(delta, [.05, .95]).tolist()}
    return {'paid_people': len(paid), 'hypothetical_people': len(source) if source_budget is None else source_budget,
            **({'mean_training_choices': float(np.mean(training_choices))} if training_choices else {}),
            'brier': {k: float(v.mean()) for k, v in scores.items()}, 'qwen_mix_over': comparisons}


def orange_inputs():
    cards, groups, _ = orange.load()
    p, identities = orange.predictions(orange.build(cards), orange.RUN)
    if len(identities) != 1:
        raise ValueError('Mixed model versions')
    x = (np.array(list(cards.values()), dtype=float) - [35, 30]) / 10
    probs = np.array([[p[card][str(i)] for i in (1, 2, 3)] for card in cards])
    source_ids, source = groups[1]
    paid_ids, paid = groups[0]
    return x, probs, source_ids - 1, source, paid_ids - 1, paid


def beef_inputs():
    cohorts, _ = load_responses(SOURCE)
    doc = json.loads(RESULT.read_text())
    if doc['workbook_sha256'] != SOURCE_SHA or [c['prices_cents'] for c in doc['cards']] != [list(p) for p in PRICES]:
        raise ValueError('Misaligned historical model outputs')
    p = np.array([c['predictions']['direct']['incentivized'][:5] for c in doc['cards']])
    mass = p.sum(axis=-1, keepdims=True)
    p = np.divide(p, mass, out=np.full_like(p, .2), where=mass > 0)
    prices = np.log(PRICES)
    x = np.concatenate((np.broadcast_to(np.eye(5), (len(prices), 5, 5)),
                        (5 * (prices - prices.mean(axis=1, keepdims=True)))[..., None]), axis=2)
    source, paid = (np.eye(6)[np.array(cohorts[g]) - 1][..., :5]
                    for g in ('hypothetical', 'incentivized'))
    return x, p, np.broadcast_to(np.arange(len(x)), source.shape[:2]), source, np.broadcast_to(
        np.arange(len(x)), paid.shape[:2]), paid


if __name__ == '__main__':
    print(json.dumps({'seed': SEED, 'replays': REPLAYS, 'new_calls': 0, 'qwen_weight': WEIGHT,
                      'studies': {'orange': evaluate(*orange_inputs()), 'beef': evaluate(*beef_inputs())}},
                     indent=2))
