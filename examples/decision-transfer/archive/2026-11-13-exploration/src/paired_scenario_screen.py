"""Compare joint versus separate population forecasts for matched scenarios."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import hashlib
import json
import random

import numpy as np
import pyreadstat

from optout_transfer import beer_deck
from order_screen import SEED, WORK, encode, read, result_path, send
import packaging_transfer as tomato
import protocol

RUN = WORK / 'paired-scenario-v1'


def beer_cases():
    deck, people = beer_deck()
    contexts = sorted({context for context, _ in deck}, key=len)
    if len(contexts) != 2 or not contexts[1].startswith(contexts[0]):
        raise ValueError('Unexpected beer scenarios')
    results = []
    for card in sorted({card for _, card in deck}):
        keys = [(context, card) for context in contexts]
        questions = [deck[key]['questions'][0] for key in keys]
        if questions[0] != questions[1]:
            raise ValueError('Beer options differ by condition')
        counts = [Counter(row[key] for row in people if key in row) for key in keys]
        results.append((questions[0], contexts[0], 'No additional instruction.', contexts[1][len(contexts[0]):],
                        counts, {'0'}))
    return results


def tomato_cases():
    for name, digest in tomato.HASHES.items():
        if hashlib.md5((tomato.SOURCE / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Unexpected tomato source version')
    page = tomato.PdfReader(tomato.SOURCE / 'survey_original.pdf').pages[3].extract_text()
    information = page.split('bb == 1; Gruppe 1 (Info)', 1)[1].split('Im Folgenden', 1)[0]
    information = ' '.join(information.split())
    frame, meta = pyreadstat.read_sav(str(tomato.SOURCE / 'data_valid.sav'))
    if meta.variable_value_labels['Group'] != {
        1: 'G1: with information about bioplastic', 2: 'G2: without information about bioplastic'
    }:
        raise ValueError('Unexpected tomato groups')
    results = []
    for card, profiles in sorted(tomato.cards().items()):
        options = {str(i): f'Verpackung: {material}. {decay}. Produkt hält {days} Tage länger. '
                           f'Preis Verpackung: {price:.2f} EUR.'
                   for i, (material, decay, days, price) in enumerate(profiles, 1)}
        options['0'] = 'Keines dieser 3 Produkte'
        counts = []
        for group in (2, 1):
            answers = frame.loc[frame.Group == group, card]
            if not answers.isin([0, 1, 2, 3]).all():
                raise ValueError('Unexpected tomato response')
            counts.append(Counter(str(int(choice)) for choice in answers))
        focus = {str(i) for i, profile in enumerate(profiles, 1) if profile[0] == 'Biokunststoff'}
        results.append(({'id': card, 'prompt': 'Welches dieser Produkte würden Sie kaufen?', 'options': options},
                        tomato.CONTEXT, 'Keine zusätzlichen Informationen.', information, counts, focus))
    return results


def beef_cases():
    import beef_payment_screen as beef

    cohorts, _ = beef.load_responses(beef.SOURCE)
    results = []
    for i, prices in enumerate(beef.PRICES):
        options = {str(j): f'{label} ribeye steak, USD {price / 100:.2f}'
                   for j, (label, price) in enumerate(zip(beef.OPTIONS[:-1], prices, strict=True), 1)}
        options['6'] = 'None of these'
        counts = [Counter(str(row[i]) for row in cohorts[group])
                  for group in ('hypothetical', 'incentivized')]
        results.append(({'id': f'card{i + 1:02}', 'prompt': 'Which steak, if any, would you purchase?',
                         'options': options},
                        beef.CONTEXT, beef.PAYMENT['hypothetical'], beef.PAYMENT['incentivized'], counts, {'6'}))
    return results


def prepare(cases):
    jobs = []
    for study, cards in cases.items():
        for question, context, control, treatment, _, _ in cards:
            card = question['id']
            pair = [{**question, 'id': f'{card}-{i + 1}', 'prompt': question['prompt'] + '\n' + instruction}
                    for i, instruction in enumerate((control, treatment))]
            # Compare the same output format and same question IDs in both methods.
            for name, questions in [('separate_control', pair[:1]), ('separate_treatment', pair[1:]), ('joint', pair)]:
                instruction = 'Estimate the proportion of participants who choose each option in each scenario.'
                if name == 'joint':
                    instruction += ' Compare the two scenarios explicitly and reflect any difference in the probabilities.'
                body = protocol.build({'title': 'Product choice forecast', 'context': context, 'questions': questions,
                                       'basic': {}}, 'basic', 'qwen', {}, {}, 768, preamble=instruction)
                jobs.append({'study': study, 'card': card, 'arm': name, 'questions': questions, 'body': body})
    random.Random(SEED).shuffle(jobs)
    return jobs


def score(cases, jobs, directory):
    outcomes, identities, errors = {}, set(), Counter()
    for job in jobs:
        path = result_path(job, directory)
        response = read(path) if path.exists() else {'status': 'error', 'type': 'missing'}
        if response['status'] != 'ok':
            errors[f"{job['study']}/{job['arm']}/{response['type']}"] += 1
            continue
        outcomes[job['study'], job['card'], job['arm']] = response['p']
        identities.add(json.dumps(response['identity'], sort_keys=True))
    if len(identities) != 1:
        raise ValueError('Unexpected model identity')
    results = {}
    for study, cards in cases.items():
        rows = []
        for question, _, _, _, counts, focus in cards:
            card, keys = question['id'], list(question['options'])
            arms = [outcomes.get((study, card, key)) for key in ('separate_control', 'separate_treatment', 'joint')]
            if any(response is None for response in arms):
                continue
            human = np.array([[count[key] / sum(count.values()) for key in keys] for count in counts])
            estimates = [np.array([[responses[f'{card}-{i + 1}'][key] for key in keys]
                                   for i, responses in enumerate(pair)])
                         for pair in (arms[:2], [arms[2], arms[2]])]
            focus_idx = [i for i, key in enumerate(keys) if key in focus]
            contrasts = [p[1] - p[0] for p in (human, *estimates)]
            effects = [d[focus_idx].sum() for d in contrasts]
            errors_full = [.5 * np.abs(d - contrasts[0]).sum() for d in (np.zeros(len(keys)), *contrasts[1:])]
            levels = [.5 * np.abs(p - human).sum(axis=1).mean() for p in estimates]
            rows.append([*effects, *errors_full, *levels])
        a = np.asarray(rows)
        means = a.mean(axis=0)
        rng = np.random.default_rng(SEED)
        draws = rng.integers(len(a), size=(2000, len(a)))
        results[study] = {'paired_cards': len(a), 'planned_cards': len(cards),
                          'responses_per_card_by_condition': [[sum(group.values()) for group in case[4]] for case in cards],
                          'focus_gap': dict(zip(('human', 'separate', 'joint'), means[:3].tolist(), strict=True)),
                          'full_change_error': dict(zip(('zero', 'separate', 'joint'), means[3:6].tolist(), strict=True)),
                          'level_error': dict(zip(('separate', 'joint'), means[6:].tolist(), strict=True)),
                          'joint_over_separate_interval_95': np.quantile(
                              (a[:, 4] - a[:, 5])[draws].mean(axis=1), [.025, .975]).tolist(),
                          'joint_over_zero_interval_95': np.quantile(
                              (a[:, 3] - a[:, 5])[draws].mean(axis=1), [.025, .975]).tolist()}
    return {'requests': len(jobs), 'valid': len(outcomes), 'errors': dict(errors),
            'identity': json.loads(identities.pop()), 'studies': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    parser.add_argument('--beef', action='store_true')
    args = parser.parse_args()
    cases = {'beef': beef_cases()} if args.beef else {'beer': beer_cases(), 'tomato': tomato_cases()}
    jobs = prepare(cases)
    directory = RUN.with_name('paired-scenario-beef-v1') if args.beef else RUN
    directory.mkdir(mode=0o700, exist_ok=True)
    manifest = directory / 'jobs.json'
    if manifest.exists() and manifest.read_bytes() != encode(jobs):
        raise ValueError('Frozen requests changed')
    if not manifest.exists():
        manifest.write_bytes(encode(jobs))
    if args.action == 'run':
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(partial(send, directory=directory), jobs))
    print(json.dumps(score(cases, jobs, directory), indent=2))
