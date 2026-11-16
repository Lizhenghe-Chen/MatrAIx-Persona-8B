"""Restore Taiwan sweet-pepper choice cards and test a historical refusal prior."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from functools import partial
from hashlib import sha256
import json
import random
import re

import numpy as np
from pypdf import PdfReader

import protocol
from optout_transfer import outcome, predictions
from order_screen import SEED, WORK, encode, send
from refusal_prior_screen import evaluate

SOURCE = WORK / 'taiwan-pepper-admission'
RUN = WORK / 'taiwan-pepper-v1'
HASHES = {
    'mmc1.pdf': 'd30e6a24b273def98b848e0e2c5a62ca52f79f9247288588abc1e7df50d78e2d',
    'mmc2.pdf': '65a69c1c1b0d22270e7a03697d5a6ffae778bee0c9c3ab76614b74fd6284c0c3',
    'mmc4.csv': '81e3b970320db444c8c9b0957e10a9400a31a28f421fc58316aafa7d2679e39a',
    'mmc5.pdf': '90bc8d546ccc7913d4eda0c14ded37368fe3410b434ded96921a0890f3b8331d',
}
# Equal weight for the US beer study and the previously evaluated European food archive.
PRIOR = (.32261812548412083 + np.mean([.16952380952380952, .09215686274509804, .27705627705627706])) / 2
CONTEXT = ('2014 年台灣。請想像你在平常光顧的商店購物，這是六道新鮮紅甜椒購買題之一。'
           '甜椒的大小、顏色、成熟度與氣味等均相同。可以選擇不購買。'
           '任何購買都會減少你和家人可用於其他購物的金額。')


def deck():
    for name, digest in HASHES.items():
        if sha256((SOURCE / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Source changed: {name}')
    attributes = {}
    for page in PdfReader(SOURCE / 'mmc1.pdf').pages:
        for line in page.extract_text().splitlines():
            if re.fullmatch(r'(?:\d+\s+){6}\d+\s*', line):
                block, task, option, *features = map(int, line.split())
                key = (block, task, option)
                if key in attributes:
                    raise ValueError('Duplicate design row')
                attributes[key] = features
    if len(attributes) != 108:
        raise ValueError('Expected six blocks of six three-product cards')
    jobs = {}
    for block in range(1, 7):
        for task in range(1, 7):
            key = f'b{block}t{task}'
            options = {}
            for i in range(1, 4):
                origin, production, testing, price = attributes[block, task, i]
                label = f'新鮮紅甜椒；產地：{("台灣", "日本", "中國")[origin - 1]}'
                if production == 1:
                    label += '；有機生產'
                if testing != 3:
                    test_location = ('台灣', '日本', '中國')[origin - 1] if testing == 1 else '台灣'
                    label += f'；通過{test_location}的農藥殘留檢測'
                options[str(i)] = f'{label}；NT { (65, 85, 105, 125)[price - 1] }／600g'
            options['4'] = '我不會購買這些甜椒。'
            q = {'id': key, 'prompt': '以下三種甜椒，請問您會購買哪一種？', 'options': options}
            body = protocol.build({'title': '台灣消費者之甜椒選擇', 'context': CONTEXT,
                                   'questions': [q], 'basic': {}}, 'basic', 'qwen', {}, {}, 512)
            jobs[key] = {'questions': [q], 'body': body}
    return jobs


def observed_group(jobs, group):
    with (SOURCE / 'mmc4.csv').open(encoding='utf-8-sig', newline='') as file:
        rows = list(csv.DictReader(file))
    if len(rows) != 1309 or len({row['ID'] for row in rows}) != 1309:
        raise ValueError('Unexpected respondent count')
    people = []
    for row in rows:
        answers = [row[f'DCE{i}'] for i in range(1, 7)]
        if row['Group'] == group and all(answers):
            answers = {f'b{row["DCE blocking version"]}t{i}': a for i, a in enumerate(answers, 1)}
            if not all(card in jobs and answer in '1234' and len(answer) == 1
                       for card, answer in answers.items()):
                raise ValueError('Unmapped observed choice')
            people.append(answers)
    if len(people) != {'0': 526, '1': 361}[group]:
        raise ValueError('Unexpected complete respondents')
    return people


def observed_control(jobs):
    return observed_group(jobs, '0')


def score(jobs):
    people = observed_control(jobs)
    pred, identities = predictions(jobs, RUN)
    if len(identities) != 1:
        raise ValueError('Mixed model versions')
    p, y = outcome(pred, people)
    keys = np.asarray([list(person) for person in people])
    return {'people': len(people), 'cards': len(jobs), 'choices': y.shape[0] * y.shape[1],
            'actual_refusal': float(y[..., 3].mean()), 'qwen_refusal': float(p[..., 3].mean()),
            'prior': float(PRIOR), 'source_hashes': HASHES, 'identity': json.loads(next(iter(identities))),
            'budget_comparison': evaluate(p[..., 3], y[..., 3], keys, PRIOR)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('freeze', 'run', 'score'))
    args = parser.parse_args()
    jobs = deck()
    batch = list(jobs.values())
    random.Random(SEED).shuffle(batch)
    RUN.mkdir(mode=0o700, exist_ok=True)
    manifest = RUN / 'jobs.json'
    if manifest.exists() and manifest.read_bytes() != encode(batch):
        raise ValueError('Frozen requests changed')
    if not manifest.exists():
        manifest.write_bytes(encode(batch))
    if args.action == 'run':
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(partial(send, directory=RUN), batch))
    print(json.dumps(score(jobs) if args.action == 'score' else {'requests': len(jobs)}, indent=2))


if __name__ == '__main__':
    main()
