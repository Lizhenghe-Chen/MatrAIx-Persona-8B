"""Prepare private, disjoint datasets and native questionnaire requests for the final replication."""
import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

import personas

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parent / 'sim-to-real'))
from decision_lab.cross_study.protocol import build_body  # native baseline

os.umask(0o077)
WORK = Path.home() / '.local/share/matraix-decision-transfer/work/final-v1'
RELEASE = Path(os.environ.get('MATRAIX_DATA_ROOT',
                '/Volumes/元宇宙联合创新实验室/实验数据/MatrAIx多地区选品源数据')) / '09_MatrAIx画像/Persona-1M发行版'
SEED = 20261109
AGES = personas.AGE
DEGREES = personas.DEGREE
FIELDS = ('region', 'age_bracket', 'highest_education', 'gender_identity', 'demo_employment_status',
          'lstyle_household_size')
TOPIC = {'nhanes': 'Shopping and food package labels', 'tofu': 'Undersökning om matkonsumtionsbeteende'}
CONTEXT = {
    'nhanes': 'United States, 2017–2018. Adult follow-up telephone interview. The respondent does not have the hand cards or a food package to consult.',
    'tofu': ('Sverige, 2021. Tänk dig följande scenario: du är i en mataffär och vill köpa 400 g naturlig tofu. '
             'Det finns två varianter av tofu, 400 g, i butiken. De är lika i smak, näringsinnehåll och har liknande '
             'förpackningar men skiljer sig åt i följande egenskaper: Tofun har tillverkats i olika länder, sojabönorna '
             'har odlats i olika länder, de har odlats med ekologiska eller konventionella metoder och/eller produkten '
             'har olika pris. Vänligen välj den variant som du skulle köpa i en verklig butik. Om du inte skulle '
             'köpa någon av dem, välj det tredje alternativet.'),
}
LABELS = ['Always', 'Most of the time', 'Sometimes', 'Rarely', 'Never', 'Never seen']
FREQUENCY = ' Would you say always, most of the time, sometimes, rarely, or never?'
# Interviewer wording for CBQ502=2 and CBQ503=2, with no visual hand-card reference.
CDC_ITEMS = {
    'CBQ700': 'Many food packages contain an expiration date such as "use by" or "sell by". How often do you use the expiration date when deciding to buy a food product?',
    'DBQ780': ('Some food packages contain health claims about the benefits of nutrients or foods. For example, '
               '"Diets low in sodium may reduce the risk of high blood pressure", or "Adequate calcium throughout life '
               'may reduce the risk of osteoporosis". How often do you use this kind of health claim when deciding to buy a product?'),
    'DBQ750': ('Next, we have some questions about food labels. A food label usually is on the back or on the side of '
               'the food package. It has two parts, a Nutrition Facts panel and a list of ingredients. The "Nutrition '
               'Facts panel" of a food label lists the amount of calories, fat, fiber, carbohydrates and some other nutritional '
               'information. How often do you use the Nutrition Facts panel when deciding to buy a food product?'),
    'DBQ760': 'How often do you use the list of ingredients on a food label when deciding to buy a food product?',
    'DBQ770': 'How about the information on the serving size? How often do you use information on the serving size on a food label when deciding to buy a food product?',
}
SWEDISH_LEVELS = (
    ('Sverige', 'Annat land inom EU', 'Land utanför EU'),
    ('Sverige', 'Annat land inom EU', 'Land utanför EU'),
    ('Ekologiska metoder', 'Icke-ekologiska konventionella metoder'),
    ('15 SEK', '20 SEK', '25 SEK', '30 SEK', '35 SEK', '40 SEK', '50 SEK', '60 SEK'),
)
TOFU_ATTRIBUTES = ('Landet där tofuen tillverkas', 'Sojabönornas ursprungsland',
                   'Kultivering av sojabönorna', 'Pris per 400g')
TOFU_FIELDS = ['RID', 'VERSION', 'STATUS', 'gender', 'age_other', 'split', 'q55']
TOFU_TARGET_FIELDS = ['RID', 'DESIGN_ROW', 'SEQ', 'pref1', *(f'a{a}_x{x}' for a in (1, 2) for x in range(1, 5))]


def write(path, value):
    path = WORK / path
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')
    tmp.replace(path)


def read(name):
    return json.loads((WORK / name).read_text())


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def age_group(age):
    return AGES[next(i for i, end in enumerate((24, 34, 44, 54, 64, 74, 84, 120)) if age <= end)]


def question(key, prompt, labels):
    return {'id': key, 'prompt': prompt, 'type': 'single_choice', 'required': True,
            'options': [{'id': str(i + 1), 'label': label} for i, label in enumerate(labels)]}


def tofutask(record):
    attrs = [[int(record[f'a{a}_x{x}']) for x in range(1, 5)] for a in (1, 2)]
    labels = []
    for i, profile in enumerate(attrs, 1):
        description = '; '.join(f'{title}: {levels[value - 1]}'
                                for title, levels, value in zip(TOFU_ATTRIBUTES, SWEDISH_LEVELS, profile, strict=True))
        labels.append(f'Variant {i} av 400 g tofu. {description}')
    labels.append('Jag skulle inte köpa någon av varianterna')
    q = question(f"task_{int(record['SEQ'])}",
                 'Vilken produkt skulle du föredra? Ta hänsyn till priset när du gör ditt val. '
                 'Var realistisk i ditt beslut och välj endast den variant som du skulle vara beredd att betala för i en verklig butik.',
                 labels)
    return {'question': q, 'card': json.dumps(attrs, separators=(',', ':')), 'attrs': attrs,
            'answer': int(record['pref1']) - 1}


def load_nhanes():
    demo_fields = ['SEQN', 'RIDAGEYR', 'DMDEDUC2', 'RIAGENDR', 'SDMVSTRA', 'SDMVPSU']
    demo = pd.read_sas(WORK / 'DEMO_J.xpt', format='xport')[demo_fields]
    answers = pd.read_sas(WORK / 'CBQPFA_J.xpt', format='xport')
    expected = {'CBQ700': (2302, 957, 516, 207, 215, 3), 'DBQ780': (366, 704, 1544, 878, 700, 5),
                'DBQ750': (610, 1050, 1472, 602, 463, 1)}
    for key, counts in expected.items():
        if tuple((answers[key] == i).sum() for i in range(1, 7)) != counts:
            raise ValueError('CDC codebook frequency mismatch')
    joined = answers.merge(demo, on='SEQN', validate='one_to_one')
    target = joined[(joined.CBQ502 == 2) & (joined.CBQ503 == 2) & (joined.RIDAGEYR >= 20)
                    & joined.DMDEDUC2.isin(range(1, 6)) & (joined.WTDRD1 > 0)
                    & joined[list(CDC_ITEMS)].isin(range(1, 7)).all(axis=1)]
    edu = {1: ['No formal', 'Primary'], 2: ['Primary', 'Secondary'], 3: ['Secondary'],
           4: ['Some college', "Associate's", 'Vocational / cert'], 5: DEGREES}
    people = {}
    for row in target.to_dict('records'):
        tasks = [{'question': question(key, text + FREQUENCY, LABELS), 'card': key, 'answer': int(row[key]) - 1}
                 for key, text in CDC_ITEMS.items()]
        age = age_group(row['RIDAGEYR'])
        # NHANES public ages are top-coded at 80. Use a compatible top band, not exact age.
        ages = AGES[-2:] if row['RIDAGEYR'] == 80 else [age]
        people[int(row['SEQN'])] = {'age': age, 'education': int(row['DMDEDUC2']),
                                  'rule': ('North America', ages, edu[row['DMDEDUC2']],
                                           'Man' if row['RIAGENDR'] == 1 else 'Woman'),
                                  'weight': row['WTDRD1'],
                                  'sampling_stratum': int(row['SDMVSTRA']), 'tasks': tasks}
    return people


def load_tofu():
    cov = pd.read_excel(WORK / 'tofu_main_swe_covariates.xlsx', usecols=TOFU_FIELDS)
    tasks = pd.read_excel(WORK / 'tofu_main_swe_tofu.xlsx', usecols=TOFU_TARGET_FIELDS)
    if tuple((tasks.pref1 == i).sum() for i in range(1, 4)) != (6349, 4788, 2568):
        raise ValueError('Unexpected tofu response frequencies in author workbook')
    control = cov[(cov.STATUS == 7) & (cov.split == 4)]
    assert len(control) == 368 and control.RID.is_unique
    cov = control[(control.age_other.between(18, 100)) & control.gender.isin((1, 2)) & control.q55.isin((1, 2, 3, 4))]
    edu = {1: ['No formal', 'Primary'], 2: ['Primary'], 3: ['Secondary'], 4: DEGREES}
    by_person = tasks.groupby('RID')
    people = {}
    for row in cov.itertuples(index=False):
        subset = by_person.get_group(row.RID).sort_values('SEQ')
        if tuple(subset.SEQ) != tuple(range(1, 10)) or not subset.pref1.isin((1, 2, 3)).all():
            raise ValueError('Completed control has incomplete choices')
        original_tasks = [tofutask(task) for task in subset.to_dict('records')]
        known_cards = {task['card'] for task in original_tasks[:2]}
        targets = [task for task in original_tasks[2:] if task['card'] not in known_cards]
        if len(targets) < 2:
            continue
        age = age_group(row.age_other)
        people[int(row.RID)] = {'age': age, 'education': int(row.q55), 'weight': 1,
                                'rule': ('Western Europe', [age], edu[row.q55], 'Woman' if row.gender == 1 else 'Man'),
                                'sampling_stratum': 0, 'history': original_tasks[:2], 'tasks': targets}
    return people


def persona_pool(path):
    if (WORK / 'persona-pool.json').exists():
        return read('persona-pool.json')
    manifest = json.loads((path / 'manifest.json').read_text())
    schema = json.loads((path / 'persona_codes.schema.json').read_text())['columns']
    columns = [(i, entry) for i, entry in enumerate(schema) if entry['id'] in FIELDS]
    allowed = {v['id']: set(v['values']) for v in json.loads((personas.NATIVE / 'dimensions.json').read_text())['dimensions']}
    regions = {'North America', 'Western Europe'}
    cells = defaultdict(list)
    for entry in manifest['files']:
        offset = 0
        file = pq.ParquetFile(path / entry['path'])
        for batch in file.iter_batches(batch_size=4096, columns=['source', 'attributes', 'null_bitmap', 'attribute_overrides']):
            for i, row in enumerate(batch.to_pylist()):
                if row['source'] in {'real_human_survey', 'gss', 'amazon'}:
                    continue
                fields = {k: v for k, v in personas.decode_row(row, columns).items()
                          if isinstance(v, str) and v in allowed[k]}
                if fields.get('region') not in regions or not all(k in fields for k in FIELDS[:4]):
                    continue
                cell = tuple(fields[k] for k in FIELDS[:4])
                if len(cells[cell]) < 32:
                    cells[cell].append({'source': row['source'], 'key': [entry['path'], offset + i], 'fields': fields})
            offset += batch.num_rows
        print('Scanned release shard', entry['path'], flush=True)
    pool = [p for cell in cells.values() for p in cell]
    write('persona-pool.json', pool)
    return pool


def freeze():
    rng = np.random.default_rng(SEED)
    private = {}
    requests = []
    metadata = {}
    pool = persona_pool(RELEASE)
    for name, load_data in [('nhanes', load_nhanes), ('tofu', load_tofu)]:
        people = load_data()
        used = set()
        # Shuffle once before matching, then freeze selection based on demographic rules only.
        picked = []
        excluded = 0
        for key in rng.permutation(sorted(people)):
            key = int(key)
            person = people[key]
            region, ages, education, gender = person['rule']
            candidates = [p for p in pool if tuple(p['key']) not in used
                          and p['fields']['region'] == region and p['fields']['age_bracket'] in ages
                          and p['fields']['highest_education'] in education and p['fields']['gender_identity'] == gender]
            if not candidates:
                excluded += 1
                continue
            chosen = candidates[int(rng.integers(len(candidates)))]
            if len(picked) >= 100:
                continue
            used.add(tuple(chosen['key']))
            picked.append(key)
            sample = 'technical' if len(picked) <= 4 else 'evaluation'
            instrument = {'id': name, 'title': TOPIC[name], 'description': '',
                          'questions': [t['question'] for t in person['tasks']]}
            for arm in ('original', 'output_only'):
                body = build_body(chosen['fields'], instrument, CONTEXT[name], arm, max_tokens=1024)
                requests.append({'study': name, 'sample': sample, 'person': key, 'arm': arm,
                                 'body': body, 'instrument': instrument})
        if len(picked) != 100:
            raise ValueError(f'{name} lacks 100 matched participants including four for technical checks')
        private[name] = {'people': people, 'technical': picked[:4], 'evaluation': picked[4:],
                         'training': sorted(set(people) - set(picked))}
        cards = Counter(t['card'] for k in picked[4:] for t in people[k]['tasks'])
        metadata[name] = {'eligible': len(people), 'technical': 4, 'evaluation': 96,
                          'training': len(private[name]['training']), 'unique_profiles': len(used),
                          'cards': len(cards), 'cards_at_least_20': sum(v >= 20 for v in cards.values())}
    rng.shuffle(requests)
    for index, row in enumerate(requests):
        row['request'] = index
    source_files = ('DEMO_J.xpt', 'DEMO_J.htm', 'CBQPFA_J.xpt', 'CBQPFA_J.htm', 'Survey_Tofu_final_SWE.pdf',
                    'tofu_questionnaire_english.pdf', 'tofu_main_swe_covariates.xlsx', 'tofu_main_swe_tofu.xlsx')
    write('people.json', private)
    write('requests.json', requests)
    manifest = {'seed': SEED, 'model': 'deepseek-v4-pro', 'metadata': metadata,
                'materials_sha256': {name: digest(WORK / name) for name in source_files},
                'release_manifest_sha256': digest(RELEASE / 'manifest.json'),
                'adapter_sha256': digest(Path(__file__)),
                'requests_sha256': digest(WORK / 'requests.json'), 'people_sha256': digest(WORK / 'people.json')}
    write('freeze.json', manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    if (WORK / 'freeze.json').exists():
        raise SystemExit('Inputs already frozen')
    freeze()
