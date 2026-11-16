"""Compare Qwen and the statistical update using the same choice histories."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from hashlib import sha256
import json

import numpy as np

import cheese_pilot
from order_screen import SEED, WORK, encode, read, result_path, send
import optout_pilot as pilot
from optout_transfer import beer_deck
from personal_choice_products import STRENGTH, prepare
from personal_choice_update import forecasts, loss
import protocol

RUN = WORK / 'personal-choice-qwen-v1'
N = 48
ARMS = ('no_history', 'own', 'other')


def studies():
    _, y, keys, _, x = pilot.load()['beer']
    deck, people = beer_deck()
    cards = np.array([list(person) for person in people], dtype=object)
    if not np.array_equal(keys, cards[:, :, 1]):
        raise ValueError('Beer deck order changed')
    contexts = cards[:, 0, 0]
    yield 'beer', y, keys, x, cards, contexts, deck

    frame, deck, features = cheese_pilot.load_deck()
    _, y, keys, _, x = cheese_pilot.evaluation_inputs(frame, deck, features)[0]
    contexts = np.full(len(y), 'Italy, February to March 2025. Choose one of two offers or neither. '
                       'The mountain label certifies milk and ageing from designated mountain areas '
                       'and at least 60% of feed from those areas. Direct purchase can be ordered from the producer.')
    yield 'italy', y, keys, x, keys, contexts, deck


def experiment(name, y, keys, x, cards, contexts, deck):
    flat_x, flat_y, beta, history, target, *_ = prepare(y, keys, x)
    people = target[:, 0] // keys.shape[1]
    rng = np.random.default_rng(SEED + 11)
    sample = rng.choice(len(people), N, replace=False)
    history, target, people = history[sample], target[sample], people[sample]
    groups = defaultdict(list)
    for i, person in enumerate(people):
        groups[(str(contexts[person]), tuple(keys[person]))].append(i)
    donor = np.arange(N)
    for indices in groups.values():
        if len(indices) < 2:
            raise ValueError('No legal same-block donor')
        donor[indices] = np.roll(indices, 1)
    if np.any(donor == np.arange(N)) or len(set(donor)) != N:
        raise ValueError('Invalid donor permutation')
    statistical = forecasts(flat_x, flat_y, beta, history, target, STRENGTH)
    statistical['stat_other'] = forecasts(flat_x, flat_y, beta, history[donor], target, STRENGTH)['own']
    if not np.all(history // keys.shape[1] == people[:, None]):
        raise ValueError('Misaligned histories')
    if set(keys.ravel()[history.ravel()]) & set(keys.ravel()[target.ravel()]):
        raise ValueError('History and evaluation cards overlap')

    def options(index):
        person, task = divmod(index, keys.shape[1])
        key = cards[person, task]
        if name == 'beer':
            key = tuple(key)
        return deck[key]['questions'][0]['options']

    jobs = {}
    for i in range(N):
        questions = [
            {'id': f'target{j + 1}', 'prompt': 'Which would this person choose?', 'options': options(index)}
            for j, index in enumerate(target[i])
        ]
        population = [{str(k): round(float(p), 8) for k, p in enumerate(row)}
                      for row in statistical['population'][i]]
        context = f'{contexts[people[i]]}\nPopulation probabilities for target1 and target2: {json.dumps(population)}.'
        for arm in ARMS:
            facts = []
            if arm != 'no_history':
                for index in history[i if arm == 'own' else donor[i]]:
                    facts.append({'options': options(index), 'observed_choice': str(flat_y[index].argmax())})
            preamble = ('Predict the individual’s choices using the supplied population estimates as a starting point. '
                        'Adjust them only as warranted by the two examples, if supplied. The examples are unrelated '
                        'in order to the target questions. Choice codes are local to each question. '
                        'Do not invent personal facts.\n'
                        f'Known choices for this person: {json.dumps(facts, ensure_ascii=False)}')
            body = protocol.build({'title': 'Two product choices', 'context': context,
                                   'questions': questions, 'basic': {}}, 'basic', 'qwen', {}, {}, 512,
                                  preamble=preamble)
            jobs[(i, arm)] = {'body': body, 'questions': questions, 'study': name}
    return jobs, statistical, flat_y[target]


def response_for(job):
    result = read(result_path(job, RUN))
    if result['status'] == 'ok':
        return result
    return read(result_path({**job, 'attempt': 2}, RUN))


def score(jobs, stat, truth):
    predictions = {f'qwen_{arm}': np.empty_like(truth) for arm in ARMS}
    identities = set()
    for (i, arm), job in jobs.items():
        response = response_for(job)
        if response['status'] != 'ok':
            raise ValueError(f'Unusable response: {response["type"]}')
        identities.add(json.dumps(response['identity'], sort_keys=True))
        predictions[f'qwen_{arm}'][i] = [[response['p'][q['id']][str(k)] for k in range(3)]
                                         for q in job['questions']]
    if len(identities) != 1:
        raise ValueError('Mixed Qwen identities')
    predictions.update({'population': stat['population'], 'stat_own': stat['own'], 'stat_other': stat['stat_other']})
    predictions['mix_stat_qwen'] = .75 * stat['own'] + .25 * predictions['qwen_own']
    # Measure the squared-error change as adjustment size minus its alignment
    # with the correction needed on held-out choices.
    diagnostics = {}
    for name in ('stat_own', 'qwen_own'):
        base = stat['population'] if name == 'stat_own' else predictions['qwen_no_history']
        step = predictions[name] - base
        diagnostics[name] = {
            'squared_adjustment': float(np.square(step).sum(axis=-1).mean()),
            'twice_alignment': float((2 * (truth - base) * step).sum(axis=-1).mean()),
        }
    error = {k: loss(p, truth) for k, p in predictions.items()}
    boot = np.random.default_rng(SEED + 1).integers(N, size=(2000, N))
    comparisons = {}
    for a, b in [('qwen_no_history', 'qwen_own'), ('qwen_other', 'qwen_own'),
                 ('stat_own', 'qwen_own'), ('stat_own', 'mix_stat_qwen'), ('population', 'stat_own')]:
        delta = error[a] - error[b]
        comparisons[f'{b}_over_{a}'] = {'mean': float(delta.mean()),
                                        'ci95': np.quantile(delta[boot].mean(axis=1), [.025, .975]).tolist()}
    return {'identity': json.loads(next(iter(identities))), 'requests': len(jobs),
            'people': N, 'scored_choices': int(truth.shape[0] * truth.shape[1]),
            'brier': {k: float(v.mean()) for k, v in error.items()}, 'improvements': comparisons,
            'adjustment_diagnostics': diagnostics,
            'refusal_brier': {k: float(np.square(p[..., 0] - truth[..., 0]).mean()) for k, p in predictions.items()},
            'accuracy': {k: float((p.argmax(axis=-1) == truth.argmax(axis=-1)).mean())
                         for k, p in predictions.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    args = parser.parse_args()
    experiments = {name: experiment(name, *data) for name, *data in studies()}
    requests = [job for jobs, _, _ in experiments.values() for job in jobs.values()]
    manifest = encode(requests)
    RUN.mkdir(mode=0o700, exist_ok=True)
    path = RUN / 'jobs.json'
    if path.exists():
        if path.read_bytes() != manifest:
            raise ValueError('Frozen requests changed')
    elif args.action == 'run':
        path.write_bytes(manifest)
    else:
        raise ValueError('Frozen requests missing')
    if args.action == 'run':
        order = np.random.default_rng(SEED + 2).permutation(len(requests))
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(partial(send, directory=RUN), (requests[i] for i in order)))
        retries = {result_path(job, RUN): {**job, 'attempt': 2} for job in requests
                   if read(result_path(job, RUN))['status'] == 'error'}
        for job in retries.values():
            send(job, directory=RUN)
    retry_count = len({result_path(job, RUN) for job in requests
                       if read(result_path(job, RUN))['status'] == 'error'})
    results = {name: score(*data) for name, data in experiments.items()}
    print(json.dumps({'seed': SEED, 'requests_sha256': sha256(manifest).hexdigest(),
                      'unique_request_bodies': len({encode(job['body']) for job in requests}),
                      'retry_requests': retry_count,
                      'studies': results}, indent=2))


if __name__ == '__main__':
    main()
