"""Ask Qwen to reweight statistical preference candidates without seeing target cards."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from hashlib import sha256
import json
import math

import numpy as np

from cheese_pilot import LABELS
from order_screen import SEED, WORK, encode, read, result_path, send
from personal_choice_products import STRENGTH, prepare
from personal_choice_qwen import N, experiment, studies
from personal_choice_update import loss, preference_components
import protocol

RUN = WORK / 'personal-preference-weights-v2'


def descriptions(name):
    if name == 'beer':
        return ('choosing neither', 'cans versus bottles', 'water conservation', 'energy conservation',
                'waste reduction', 'local production', 'higher price')
    return ('choosing neither', *(f'{label} versus {next(iter(levels.values()))}'
                                 for levels in LABELS.values() for label in list(levels.values())[1:]),
            'higher price')


def setup(name, y, keys, x, cards, contexts, deck):
    previous, stat, truth = experiment(name, y, keys, x, cards, contexts, deck)
    features, answers, beta, history, target, *_ = prepare(y, keys, x)
    idx = np.random.default_rng(SEED + 11).choice(len(target), N, replace=False)
    history, target = history[idx], target[idx]
    log_known, weights, target_p = preference_components(features, answers, beta, history, target, STRENGTH)
    reconstructed = np.einsum('ntak,nk->nta', target_p, weights)
    if not np.allclose(stat['own'], reconstructed) or not np.array_equal(truth, answers[target]):
        raise ValueError('Reference split or statistics changed')
    descriptions_for_study = descriptions(name)
    if len(descriptions_for_study) != len(beta):
        raise ValueError('Missing feature description')
    # Candidate descriptions use the actual signed change, including the price constraint.
    change = np.vstack((np.eye(len(beta)), -np.eye(len(beta)))) * STRENGTH
    change[len(beta) - 1, -1] = min(STRENGTH, -beta[-1])
    labels = ['Unchanged population preferences']
    for i, step in enumerate(change):
        val = step[i % len(beta)]
        label = descriptions_for_study[i % len(beta)]
        labels.append(f'Change utility for {label} by {val:+.3f} relative to the population')
    chosen = answers[history].argmax(axis=-1)
    selected = np.take_along_axis(log_known, chosen[..., None, None], axis=2).squeeze(axis=2)
    orders = np.random.default_rng(SEED + 12)
    jobs, permutations = [], []
    for i in range(N):
        order = orders.permutation(len(labels))
        permutations.append(order)
        previous_prompt = previous[(i, 'own')]['body']['messages'][-1]['content']
        history_text = previous_prompt.split('Known choices for this person: ', 1)[1].split('\n\n', 1)[0]
        records = json.loads(history_text)
        if len(records) != 2 or [r['observed_choice'] for r in records] != [str(v) for v in chosen[i]]:
            raise ValueError('History serialization changed')
        candidates = {str(j): {'description': labels[k],
                               'probabilities_of_observed_choices': np.exp(selected[i, :, k]).round(6).tolist()}
                      for j, k in enumerate(order)}
        prompt = (
            f'{contexts[target[i, 0] // keys.shape[1]]}\n'
            'Infer the relative support for a list of equally plausible preference candidates. '
            'The two examples are choices by one person. Candidate likelihoods are the probabilities '
            'the candidate assigns to the chosen options in those two examples, in the same order. '
            'Start from equal prior weights and use both likelihoods and the descriptions. '
            'Avoid inferring traits unsupported by the two observations. '
            'Return a JSON object with only a "weights" object containing one numeric '
            'score per candidate ID, each from 0 to 100. Scores are relative, do not make them sum to 1.\n'
            f'Observed examples: {history_text}\nCandidates: {json.dumps(candidates)}'
        )
        body = {'model': protocol.MODELS['qwen'], 'temperature': .7, 'top_p': 1,
                'max_tokens': 768, 'response_format': {'type': 'json_object'},
                'chat_template_kwargs': {'enable_thinking': False},
                'messages': [{'role': 'user', 'content': prompt}]}
        jobs.append({'body': body, 'study': name})
    return jobs, np.array(permutations), weights, target_p, truth, stat['population']


def parse(raw, count):
    identity = {key: raw.get(key) for key in ('model', 'system_fingerprint')}
    if identity['model'] != protocol.MODELS['qwen'] or len(raw['choices']) != 1:
        raise ValueError('Unexpected model response')
    choice = raw['choices'][0]
    message = choice['message']
    if choice['finish_reason'] != 'stop' or message.get('reasoning_content') or message.get('tool_calls'):
        raise ValueError('Incomplete or unexpected completion')
    data = json.loads(message['content'])
    if not isinstance(data, dict) or set(data) != {'weights'}:
        raise ValueError('Invalid weight envelope')
    keys = [str(i) for i in range(count)]
    scores = data['weights']
    if not isinstance(scores, dict) or set(scores) != set(keys):
        raise ValueError('Incomplete candidate scores')
    values = [scores[k] for k in keys]
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 100 for v in values):
        raise ValueError('Invalid candidate score')
    total = sum(values)
    if total == 0:
        raise ValueError('No positive candidate score')
    return {'status': 'ok', 'weights': [v / total for v in values], 'identity': identity}


def summarize(jobs, orders, weights, target_p, truth, population):
    collected, identities = [], set()
    for job, order in zip(jobs, orders, strict=True):
        reply = read(result_path(job, RUN))
        if reply['status'] == 'error':
            reply = read(result_path({**job, 'attempt': 2}, RUN))
        if reply['status'] != 'ok':
            raise ValueError(f'Unusable weights: {reply["type"]}')
        collected.append(np.array(reply['weights'])[np.argsort(order)])
        identities.add(json.dumps(reply['identity'], sort_keys=True))
    if len(identities) != 1:
        raise ValueError('Mixed Qwen identities')
    qwen_weights = np.array(collected)
    map_weights = np.eye(weights.shape[1])[weights.argmax(axis=1)]
    pred = {name: np.einsum('ntak,nk->nta', target_p, w) for name, w in (
        ('stat_update', weights), ('stat_top_candidate', map_weights), ('qwen_weights', qwen_weights),
        ('stat_qwen_mix', .75 * weights + .25 * qwen_weights),
    )}
    pred['population'] = population
    pred['no_history'] = target_p.mean(axis=-1)
    losses = {k: loss(p, truth) for k, p in pred.items()}
    boot = np.random.default_rng(SEED + 1).integers(N, size=(2000, N))
    comparisons = {}
    for method, errors in losses.items():
        delta = losses['stat_update'] - errors
        comparisons[method] = {'mean': float(delta.mean()),
                               'ci95': np.quantile(delta[boot].mean(axis=1), [.025, .975]).tolist()}
    return {'identity': json.loads(next(iter(identities))), 'people': len(truth),
            'candidate_count': weights.shape[1],
            'brier': {k: float(v.mean()) for k, v in losses.items()}, 'gains_vs_stat_update': comparisons,
            'refusal_brier': {k: float(np.square(p[..., 0] - truth[..., 0]).mean()) for k, p in pred.items()},
            'mean_weight_difference_tv': float(np.abs(weights - qwen_weights).sum(axis=1).mean() / 2),
            'top_weight_match': float((weights.argmax(axis=1) == qwen_weights.argmax(axis=1)).mean())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    args = parser.parse_args()
    experiments = {name: setup(name, *data) for name, *data in studies()}
    jobs = [(job, data[2].shape[1]) for data in experiments.values() for job in data[0]]
    manifest = encode(jobs)
    RUN.mkdir(mode=0o700, exist_ok=True)
    path = RUN / 'jobs.json'
    if path.exists():
        if path.read_bytes() != manifest:
            raise ValueError('Frozen requests changed')
    elif args.action == 'run':
        path.write_bytes(manifest)
    else:
        raise ValueError('Missing request manifest')
    if args.action == 'run':
        def submit(item):
            job, count = item
            send(job, directory=RUN, parse_reply=partial(parse, count=count))
        order = np.random.default_rng(SEED + 2).permutation(len(jobs))
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(submit, (jobs[i] for i in order)))
    retries = [({**job, 'attempt': 2}, count) for job, count in jobs
               if read(result_path(job, RUN))['status'] == 'error']
    if args.action == 'run':
        for item in retries:
            submit(item)
    print(json.dumps({'seed': SEED, 'requests': len(jobs), 'retry_requests': len(retries),
                      'requests_sha256': sha256(manifest).hexdigest(),
                      'studies': {name: summarize(*data) for name, data in experiments.items()}}, indent=2))


if __name__ == '__main__':
    main()
