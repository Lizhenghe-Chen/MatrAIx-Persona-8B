"""Replay answer-free risk signals on existing paired Qwen survey predictions."""
import json
from collections import defaultdict

import numpy as np

from order_screen import DRAWS, RUN, SEED, WORK, read, result_path

COVERAGES = (.25, .5, .75, 1.)
DRAWS_BOOTSTRAP = 2000


def load():
    labels = {'swiss': read(WORK / 'stage2/answers.json'), 'pew': read(WORK / 'pew/answers.json')}
    people = defaultdict(dict)
    identities = set()
    jobs = read(RUN / 'jobs.json')
    for job in jobs:
        answer = read(result_path(job))
        if answer['status'] != 'ok':
            raise ValueError('Invalid frozen response')
        identities.add(json.dumps(answer['identity'], sort_keys=True))
        people[job['study'], job['person']][job['draw']] = answer['p']
    if len(identities) != 1:
        raise ValueError('Inconsistent model identity')
    studies = defaultdict(list)
    for (study, person), replies in people.items():
        if set(replies) != set(DRAWS):
            raise ValueError('Incomplete replicate responses')
        rows = []
        for question, original in sorted(replies['original'].items()):
            keys = sorted(original)
            p, r, v = np.array([[replies[draw][question][k] for k in keys] for draw in DRAWS])
            choice = labels[study][person][question]
            choice = {0: 'rest', 1: 'top'}[choice] if study == 'pew' else str(choice)
            if len(keys) != 2:
                raise ValueError('Expected binary question')
            truth = np.eye(2)[keys.index(choice)]
            estimate = (p + r) / 2
            # Higher score means retain first. Round to avoid floating point tie artifacts.
            rows.append([np.max(estimate), -np.abs(p - r).sum() / 2, -np.abs(p - v).sum() / 2,
                         np.sum((estimate - truth) ** 2),
                         np.sum(((estimate + .5) / 2 - truth) ** 2)])
        studies[study].append(rows)
    return {study: np.array(rows).round(12) for study, rows in studies.items()}, json.loads(identities.pop())


def weights(scores, fraction):
    count = fraction * len(scores)
    threshold = np.sort(scores)[-int(np.ceil(count))]
    above = scores > threshold
    tied = scores == threshold
    return above + tied * ((count - above.sum()) / tied.sum())


def measure(rows, fraction):
    loss, softened_loss = rows[:, 3:].T
    full = loss.mean()
    # Random retention has expected error equal to full-set error.
    random_shrink = (fraction * loss + (1 - fraction) * softened_loss).mean()
    result = {'all_raw': full, 'uniform_brier': .5, 'random_shrink': random_shrink}
    for index, name in enumerate(('self_confidence', 'repeat_agreement', 'order_agreement')):
        keep = weights(rows[:, index], fraction)
        retained = np.average(loss, weights=keep)
        combined = (keep * loss + (1 - keep) * softened_loss).mean()
        result[name] = np.array([retained, full - retained, combined, full - combined,
                                 random_shrink - combined])
    return result


def summarize(data):
    rng = np.random.default_rng(SEED)
    indices = rng.integers(len(data), size=(DRAWS_BOOTSTRAP, len(data)))
    result = {}
    for fraction in COVERAGES:
        estimate = measure(data.reshape(-1, 5), fraction)
        samples = [measure(data[ids].reshape(-1, 5), fraction) for ids in indices]
        result[str(fraction)] = {
            'raw_brier': estimate['all_raw'],
            'uniform_brier': estimate['uniform_brier'],
            'random_shrink_brier': estimate['random_shrink'],
            'signals': {},
        }
        for name in ('self_confidence', 'repeat_agreement', 'order_agreement'):
            values = np.array([sample[name] for sample in samples])
            fields = ('retained_brier', 'retained_improvement_vs_random', 'full_brier_with_shrink',
                      'shrink_improvement_vs_raw', 'shrink_improvement_vs_random_shrink')
            result[str(fraction)]['signals'][name] = {
                field: {'mean': float(value),
                        'interval_95': np.quantile(values[:, i], [.025, .975]).tolist()}
                for i, (field, value) in enumerate(zip(fields, estimate[name], strict=True))
            }
    retained_by_question = {}
    for index, name in enumerate(('self_confidence', 'repeat_agreement', 'order_agreement')):
        keep = weights(data[:, :, index].ravel(), .5).reshape(data.shape[:2])
        retained_by_question[name] = keep.mean(axis=0).tolist()
    return {'people': len(data), 'answers': data.shape[0] * data.shape[1],
            'half_retention_by_question_position': retained_by_question,
            'coverage': result}


if __name__ == '__main__':
    studies, model = load()
    print(json.dumps({'identity': model, 'seed': SEED, 'new_model_calls': 0,
                      'bootstrap_draws': DRAWS_BOOTSTRAP,
                      'studies': {study: summarize(data) for study, data in studies.items()}}, indent=2))
