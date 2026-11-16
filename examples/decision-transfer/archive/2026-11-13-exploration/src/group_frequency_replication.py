"""Replicate direct group forecasts on dryer and beef choice experiments."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import json

import numpy as np

import beef_payment_screen as beef
import dryer_refusal as dryer
import group_frequency_screen as group
from order_screen import WORK, encode, read, result_path

RUN = WORK / 'group-frequency-replication-v1'


def load_studies():
    jobs, _, cohorts = dryer.deck()
    studies = {country: ({key: job for key, job in jobs.items() if key.startswith(country + '-')},
                         list(people.values())) for country, people in cohorts.items()}
    beef_cohorts, _ = beef.load_responses(beef.SOURCE)
    decks = {condition: {} for condition in beef.PAYMENT}
    for job in beef.freeze():
        if job['approach'] != 'direct':
            continue
        question, = job['questions']
        decks[job['condition']][question['id']] = job
    for condition, rows in beef_cohorts.items():
        people = [{f'card{i:02}': str(choice) for i, choice in enumerate(row, 1)} for row in rows]
        studies[f'beef_{condition}'] = dict(sorted(decks[condition].items())), people
    return studies


def payment_gap(studies, jobs):
    forecasts = {}
    for job in jobs:
        if not job['study'].startswith('beef_'):
            continue
        path = result_path(job, RUN)
        if path.exists():
            response = read(path)
            if response['status'] == 'ok':
                forecasts[job['study'], job['cell'], job['arm']] = response['p']['6']
    paid, hypothetical = 'beef_incentivized', 'beef_hypothetical'
    indices = [i for i in range(len(beef.PRICES))
               if all((study, i, arm) in forecasts for study in (paid, hypothetical) for arm in group.ARMS)]
    if not indices:
        raise ValueError('No beef cards completed in both payment conditions')
    human = {}
    for study in (paid, hypothetical):
        deck, people = studies[study]
        keys = list(deck)
        human[study] = np.mean([[row[keys[i]] == '6' for i in indices] for row in people], axis=0)
    observed = human[paid] - human[hypothetical]
    predicted = {arm: np.array([forecasts[paid, i, arm] - forecasts[hypothetical, i, arm] for i in indices])
                 for arm in group.ARMS}
    return {'paired_cards': len(indices), 'human_gap': float(observed.mean()),
            'no_change_mae': float(np.abs(observed).mean()),
            'by_arm': {arm: {'gap': float(values.mean()),
                             'card_mae': float(np.abs(values - observed).mean()),
                             'cards_with_positive_gap': int(np.sum(values > 0))}
                       for arm, values in predicted.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'score'))
    action = parser.parse_args().action
    studies = load_studies()
    jobs = group.build_jobs(studies)
    RUN.mkdir(mode=0o700, exist_ok=True)
    manifest = RUN / 'jobs.json'
    if manifest.exists() and manifest.read_bytes() != encode(jobs):
        raise ValueError('Frozen requests changed')
    if not manifest.exists():
        manifest.write_bytes(encode(jobs))
    if action == 'run':
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(partial(group.send, directory=RUN), jobs))
    refusal = {study: '6' for study in studies if study.startswith('beef_')}
    result = group.score(studies, jobs, RUN, refusal, include_uniform=True)
    result['beef_payment_gap'] = payment_gap(studies, jobs)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
