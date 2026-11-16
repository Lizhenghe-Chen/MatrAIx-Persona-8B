"""Test fixed statistical shrinkage and a Qwen blend on unseen electricity offers."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from hashlib import sha256
import json

import numpy as np
from scipy.special import softmax

from attribute_regularization import PENALTY_MULTIPLIER
from choice_predictor import fit_products
from optout_transfer import predictions
from order_screen import SEED, WORK, encode, send
from paid_choice_model_mix import WEIGHT
import protocol

SOURCE = WORK / 'electricity-admission/Electricity.rda'
SOURCE_URL = 'https://raw.githubusercontent.com/cran/mlogit/master/data/Electricity.rda'
DIGEST = '100ef289e7ba045457e29727091c45e5bc8b75cbbf61b833676a4b3faf59178d'
RUN = WORK / 'electricity-replication-v1'
FIELDS = ('pf', 'cl', 'loc', 'wk', 'tod', 'seas')
SIZES = (5, 10, 25)


def load():
    import pyreadr

    if sha256(SOURCE.read_bytes()).hexdigest() != DIGEST:
        raise ValueError('Unexpected electricity data version')
    frame = pyreadr.read_r(str(SOURCE))['Electricity']
    columns = [f'{name}{i}' for name in FIELDS for i in range(1, 5)]
    if list(frame) != ['choice', 'id', *columns] or frame.shape != (4308, 26):
        raise ValueError('Unexpected choice layout')
    x = frame[columns].to_numpy().reshape(-1, 6, 4).transpose(0, 2, 1)
    choice = frame.choice.to_numpy()
    people, ids = np.unique(frame.id.to_numpy(), return_inverse=True)
    if (len(people) != 361 or not np.isin(choice, [1, 2, 3, 4]).all()
            or not np.isin(x[..., 0], [0, 7, 9]).all()
            or not np.isin(x[..., 1], [0, 1, 5]).all()
            or not np.isin(x[..., 2:], [0, 1]).all()
            or np.any(x[..., 2:4].sum(axis=-1) > 1)
            or np.any((x[..., 0] > 0) + x[..., 4:].sum(axis=-1) != 1)):
        raise ValueError('Unexpected respondent or option code')
    # Canonicalize complete cards so swapped positions cannot cross the split.
    order = np.lexsort(tuple(x[..., col] for col in range(5, -1, -1)), axis=1)
    canonical = np.take_along_axis(x, order[..., None], axis=1)
    if np.any(np.all(canonical[:, 1:] == canonical[:, :-1], axis=-1)):
        raise ValueError('Duplicate offer within a card')
    cards, inverse = np.unique(canonical, axis=0, return_inverse=True)
    truth = order == (choice[:, None] - 1)
    held = np.sort(np.random.default_rng(SEED).choice(len(cards), 15, replace=False))
    return cards, inverse, ids, truth, held


def label(offer):
    fixed, years, local, known, tod, seasonal = map(int, offer)
    rate = f'Fixed {fixed} cents per kWh'
    if tod:
        rate = 'Time-of-day: 11 cents per kWh 8 am to 8 pm, 5 cents per kWh 8 pm to 8 am'
    if seasonal:
        rate = 'Seasonal: 10 cents per kWh in summer, 8 in winter, 6 in spring and fall'
    contract = (f'{years}-year contract with guaranteed rate and a penalty for early switching'
                if years else 'No contract; either party can stop at any time')
    supplier = 'Your local utility' if local else ('Well-known company other than your local utility'
                                                   if known else 'Unfamiliar company')
    return f'{supplier}; {contract}; {rate}'


def build(cards, held):
    jobs = {}
    for position, card in enumerate(held, 1):
        key = f'card{position:02}'
        q = {'id': key, 'prompt': 'Which electricity supplier would you choose?',
             'options': {str(i): label(offer) for i, offer in enumerate(cards[card], 1)}}
        body = protocol.build(
            {'title': 'Residential electricity supplier choices',
             'context': ('Consider a US residential household in a market opening to competition '
                         'in the late 1990s. Prices cover electricity only; transmission and '
                         'distribution remain with the regulated local utility.'),
             'questions': [q], 'basic': {}}, 'basic', 'qwen', {}, {}, 512,
            preamble='Estimate the proportion of survey respondents who choose each option.')
        jobs[key] = {'questions': [q], 'body': body}
    return jobs


def score(cards, inverse, ids, truth, held, jobs):
    predicted, identities = predictions(jobs, RUN)
    if len(identities) != 1:
        raise ValueError('Mixed Qwen identities')
    qwen = np.array([[predicted[key][str(i)] for i in range(1, 5)] for key in jobs])
    is_test_card = np.isin(inverse, held)
    # Separate rate-type indicators represent the two variable tariffs. Center
    # fixed prices at 8 only on fixed offers; zero is never interpreted as free.
    fixed = cards[..., 0]
    x = np.concatenate((cards[..., 1:], np.where(fixed > 0, fixed - 8, 0)[..., None]), axis=-1)
    features = {'full': x, 'shrink_all': x / np.sqrt(PENALTY_MULTIPLIER)}
    rng = np.random.default_rng(SEED + 1)
    results = {n: [] for n in SIZES}
    counts = []
    for _ in range(100):
        order = rng.permutation(len(np.unique(ids)))
        test = is_test_card & ~np.isin(ids, order[:max(SIZES)])
        target = inverse[test]
        people, person_index, tasks = np.unique(ids[test], return_inverse=True, return_counts=True)
        weights = 1 / tasks[person_index] / len(people)
        counts.append((len(people), int(test.sum())))
        llm = qwen[np.searchsorted(held, target)]
        for n, rows in results.items():
            train = ~is_test_card & np.isin(ids, order[:n])
            answer = np.column_stack((np.zeros(train.sum()), truth[train]))
            forecasts = {'qwen': llm, 'uniform': np.full_like(llm, .25)}
            for name, values in features.items():
                beta = fit_products(values[inverse[train]], answer, nonpositive_price=True)
                forecasts[name] = softmax(values[target] @ beta, axis=-1)
            base = forecasts['shrink_all']
            for name in ('qwen', 'uniform'):
                forecasts[f'shrink_all_{name}'] = (1 - WEIGHT) * base + WEIGHT * forecasts[name]
            rows.append({key: float(weights @ np.square(p - truth[test]).sum(axis=-1))
                         for key, p in forecasts.items()})
    summary = {}
    for n, rows in results.items():
        scores = {name: np.array([row[name] for row in rows]) for name in rows[0]}
        gains = {}
        for candidate, reference in (('shrink_all', 'full'), ('shrink_all_qwen', 'shrink_all'),
                                     ('shrink_all_qwen', 'shrink_all_uniform')):
            delta = scores[reference] - scores[candidate]
            gains[f'{candidate}_over_{reference}'] = {
                'mean': float(delta.mean()), 'wins': int((delta > 1e-10).sum()),
                'p05_p95': np.quantile(delta, [.05, .95]).tolist(),
            }
        summary[n] = {'brier': {key: float(value.mean()) for key, value in scores.items()},
                      'gains': gains}
    return {'source': SOURCE_URL, 'source_sha256': DIGEST, 'people': len(np.unique(ids)),
            'answers': len(ids), 'unique_cards': len(cards), 'heldout_cards': len(held),
            'available_training_answers': int((~is_test_card).sum()),
            'evaluation_people_range': [int(min(row[0] for row in counts)),
                                        int(max(row[0] for row in counts))],
            'evaluation_answers_range': [int(min(row[1] for row in counts)),
                                         int(max(row[1] for row in counts))],
            'seed': SEED, 'replays': len(counts), 'qwen_weight': WEIGHT,
            'penalty_multiplier': PENALTY_MULTIPLIER, 'valid_calls': len(predicted),
            'identity': json.loads(next(iter(identities))), 'budgets': summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    args = parser.parse_args()
    cards, inverse, ids, truth, held = load()
    jobs = build(cards, held)
    RUN.mkdir(mode=0o700, exist_ok=True)
    manifest = RUN / 'jobs.json'
    if manifest.exists() and manifest.read_bytes() != encode(list(jobs.values())):
        raise ValueError('Frozen requests changed')
    if args.action == 'run':
        if not manifest.exists():
            manifest.write_bytes(encode(list(jobs.values())))
        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(partial(send, directory=RUN), jobs.values()))
    elif not manifest.exists():
        raise ValueError('Frozen requests are missing')
    print(json.dumps(score(cards, inverse, ids, truth, held, jobs), indent=2))


if __name__ == '__main__':
    main()
