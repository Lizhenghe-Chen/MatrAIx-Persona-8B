"""Adapters for the three v2 historical re-checks.

Each adapter reads the original files and emits the same row shape as
`targets.load_existing`, so the frozen protocol and scoring apply unchanged.

Rules kept from the plan:
- origin rereads age and education from the author's original table instead of
  reusing historical stratum labels;
- packaging keeps the information arm, packaging labels, refusal coding and the
  per-task scoring unit;
- pew111 treats skip logic only as display eligibility and rereads education
  coding and survey weights.
Truth, identifiers and respondent-level fields stay in local private blocks.
"""
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from .matching import AGE
from .registry import DATA

ORIGIN = DATA / '06_历史北美电商/origin.csv'
ORIGIN_ORIGINAL = DATA / '06_历史北美电商/origin-original.tab'
PACKAGING = DATA / '06_历史北美电商/packaging.csv'
PEW111 = DATA / '06_历史北美电商/Pew-W111.zip'
SHOES = DATA / '08_购物研究与候选/shoes.csv.gz'
DRONE = DATA / '08_购物研究与候选/drone-survey.csv.gz'

ORIGIN_CONTEXT = 'United States. Survey period: June 2020.'
PACKAGING_CONTEXT = ('United States. Survey period: 2019. The two six-packs differ only in the displayed '
                     'attributes and packaging; taste is unchanged. You may choose either product or neither.')
PACKAGING_CHEAP_TALK = (' No money changes hands in this survey. Make each choice as if paying the displayed '
                        'price at your usual retailer. Choose neither if you would buy neither.')
PEW111_CONTEXT = 'United States. Survey period: July 2022.'
# The published instrument stores the conjoint screens as images, so the exact 1-7 anchor
# wording could not be read back. The neutral wording below is declared, not reconstructed.
SHOES_CONTEXT = ('United States. Survey period: 2020, online panel. Each screen shows one shoe. Rate how '
                 'likely you would be to buy it, on a scale from 1 (not at all likely) to 7 (extremely likely).')
SHOES_SCALE = [str(level) for level in range(1, 8)]
DRONE_COLUMN = re.compile(r'^CHOICE_v([0-3])_gc([0-3])_gt([0-3])_dc([0-3])_dt([0-3])_dp([01])_1(?:\.1)?$')
DRONE_GENDER = {'1': 'Male', '2': 'Female', '3': 'Other', '4': 'Prefer not to answer'}
DRONE_AGE = {'1': '18-24', '2': '25-34', '3': '35-44', '4': '45-54', '5': '55-64', '6': '65+'}
DRONE_INCOME = {'1': 'Less than $25,000', '2': '$25,000 to $49,999', '3': '$50,000 to $74,999',
                '4': '$75,000 to $99,999', '5': '$100,000 to $149,999', '6': '$150,000 to $199,999',
                '7': '$200,000 or more'}
DRONE_RESIDENCE = {'1': 'Private home', '2': 'Apartment', '3': 'Other'}
DRONE_CONTEXT = ('United States. Survey period: 2022, online panel, adults 18+. Each screen compares two '
                 'ways to receive the same order. Choose the option you prefer.')
SHOES_ATTRIBUTES = ('ave_customer_review', 'best_seller', 'brand', 'color', 'eco_friendly_materials',
                    'gel_cushioning', 'model_year', 'price', 'shipping', 'weight')

PEW111_ITEMS = {
    'ONLSHOP1_a': ('Do you ever buy things online using a desktop or laptop computer?', ('Yes', 'No')),
    'ONLSHOP1_b': ('Do you ever buy things online using a tablet?', ('Yes', 'No')),
    'ONLSHOP1_c': ('Do you ever buy things online using a smartphone?', ('Yes', 'No')),
    'SHOP4': ('If given the choice, do you generally prefer to buy online or from a physical store?',
              ('Online', 'Physical store')),
    'ONLSHOP3': ('Do you follow any influencers or content creators on social media?', ('Yes', 'No', 'Not sure')),
    'ONLSHOP4': ('Have you ever purchased something after seeing an influencer or content creator post about it '
                 'on social media?', ('Yes', 'No', 'Not sure')),
}
PEW111_ROUTED = ('ONLSHOP3', 'ONLSHOP4')


def person_id(study, raw_id):
    return hashlib.sha256(f'cross-study/{study}/{raw_id}'.encode()).hexdigest()[:24]


def age_band(years):
    for index, upper in enumerate([24, 34, 44, 54, 64, 74, 84]):
        if years <= upper:
            return AGE[index]
    return AGE[-1]


def question(identifier, prompt, options):
    return {'id': str(identifier), 'prompt': prompt, 'type': 'single_choice', 'required': True,
            'options': [{'id': str(code), 'label': label} for code, label in options]}


def product_label(attributes):
    return ', '.join(f'{key}: {value}' for key, value in attributes.items() if value not in ('', None))


def origin_rows():
    """Two products per card, no refusal option; demographics reread from the original table."""
    with ORIGIN_ORIGINAL.open(newline='') as stream:
        original = {}
        for row in csv.DictReader(stream, delimiter='\t'):
            original.setdefault(row['id'], row)
    by_person = defaultdict(lambda: defaultdict(list))
    with ORIGIN.open(newline='') as stream:
        for row in csv.DictReader(stream):
            by_person[row['id']][row['task']].append(row)
    rows = []
    for raw_id, groups in by_person.items():
        source = original.get(raw_id)
        if source is None:
            continue
        first = next(iter(groups.values()))[0]
        try:
            age = int(float(source['age']))
        except (TypeError, ValueError):
            continue
        college = str(source.get('college', '')).strip()
        if college not in ('0.0', '0', '1.0', '1'):
            continue
        education = "Bachelor's degree or higher" if float(college) == 1 else 'Below bachelor\'s degree'
        income = None
        try:
            income = int(float(source.get('inc') or 0))
        except ValueError:
            income = None
        background = {'Age': str(age), 'Education': education}
        if income is not None:
            background['Household income code'] = str(income)
        questions, truth = [], {}
        for task, items in sorted(groups.items(), key=lambda kv: int(kv[0])):
            items = sorted(items, key=lambda item: int(item['profile']))
            if len(items) != 2:
                continue
            chosen = [str(i + 1) for i, item in enumerate(items) if str(item['choice']).strip() == '1']
            if len(chosen) > 1 or (not chosen and first['cov_age']):
                # The published design allows exactly one choice; skip malformed cards.
                if len(chosen) > 1:
                    continue
            labels = [product_label({k.removeprefix('attr_'): v for k, v in item.items() if k.startswith('attr_')})
                      for item in items]
            if any(not label for label in labels):
                continue
            questions.append(question(f'card{task}', 'Compare the two products. Which would you choose?',
                                      [('1', labels[0]), ('2', labels[1])]))
            if chosen:
                truth[f'card{task}'] = chosen[0]
        if not questions or len(truth) != len(questions):
            continue
        rows.append({'study': 'origin', 'person': person_id('origin', raw_id),
                     'stratum': f'{age_band(age)}|{education}', 'weight': 1.0,
                     'background': background, 'context': ORIGIN_CONTEXT,
                     'questions': questions, 'truth': truth,
                     'group': f'{age_band(age)}|{education}', 'country': 'United States',
                     'source_id': raw_id})
    return rows


def packaging_rows():
    """Two products plus an explicit refusal option; keeps information arm and cheap-talk wording."""
    by_person = defaultdict(list)
    with PACKAGING.open(newline='') as stream:
        for row in csv.DictReader(stream):
            by_person[row['id']].append(row)
    rows = []
    for raw_id, items in by_person.items():
        first = items[0]
        education = first['cov_education']
        age = first['cov_age_group']
        background = {'Age': age, 'Education': education,
                      'Household income': first['cov_income_usd'], 'US census region': first['cov_region']}
        context = PACKAGING_CONTEXT + (PACKAGING_CHEAP_TALK if first.get('trial_cheap_talk') == '1' else '')
        groups = defaultdict(list)
        for item in items:
            groups[(item['trial_block'], item['task'])].append(item)
        questions, truth = [], {}
        for (block, task), group in sorted(groups.items(), key=lambda kv: (kv[0][0], int(kv[0][1]))):
            group = sorted(group, key=lambda item: int(item['profile']))
            if len(group) != 2:
                continue
            # In the source, '0' marks "this profile not chosen"; a card with no chosen
            # profile is the explicit "do not buy either" answer.
            chosen = [str(i + 1) for i, item in enumerate(group) if str(item['choice']).strip() == '1']
            if len(chosen) > 1:
                continue
            labels = [product_label({k.removeprefix('attr_'): v for k, v in item.items() if k.startswith('attr_')})
                      for item in group]
            if any(not label for label in labels):
                continue
            qid = f'block{block}_card{task}'
            questions.append(question(qid, 'Which would you choose?',
                                      [('1', labels[0]), ('2', labels[1]), ('0', 'Do not buy either')]))
            truth[qid] = chosen[0] if chosen else '0'
        if not questions:
            continue
        rows.append({'study': 'packaging', 'person': person_id('packaging', raw_id),
                     'stratum': f'{age}|{education}', 'weight': 1.0,
                     'background': background, 'context': context,
                     'questions': questions, 'truth': truth,
                     'group': f'{age}|{education}', 'country': 'United States',
                     'information_arm': first.get('trial_block'), 'source_id': raw_id})
    return rows


def pew111_rows():
    """Skip logic only gates display eligibility; weights and education coding reread from the file."""
    import tempfile
    import zipfile

    import pyreadstat

    names = ['QKEY', 'WEIGHT_W111', 'F_AGECAT', 'F_EDUCCAT2', 'F_INC_SDT1', 'F_INTFREQ',
             'XTABLET_W111', 'SNSUSE_W111', *(f'{q}_W111' for q in PEW111_ITEMS)]
    with zipfile.ZipFile(PEW111) as archive, tempfile.TemporaryDirectory() as directory:
        source = archive.extract(next(n for n in archive.namelist() if n.endswith('.sav')), directory)
        table, meta = pyreadstat.read_sav(source, usecols=names, output_format='dict')
    age_labels = meta.variable_value_labels['F_AGECAT']
    education_labels = meta.variable_value_labels['F_EDUCCAT2']
    rows = []
    for values in zip(*(table[name] for name in names)):
        row = dict(zip(names, values))
        age_code, education_code, weight = row['F_AGECAT'], row['F_EDUCCAT2'], row['WEIGHT_W111']
        if age_code not in age_labels or education_code not in education_labels:
            continue
        if not weight or weight <= 0:
            continue
        if row['XTABLET_W111'] != 2:
            continue
        questions, truth = [], {}
        for item, (prompt, options) in PEW111_ITEMS.items():
            eligible = item not in PEW111_ROUTED or row['SNSUSE_W111'] == 1
            raw = row[f'{item}_W111']
            valid = raw in range(1, len(options) + 1)
            if not eligible:
                if valid:
                    raise ValueError(f'Pew routing disagrees with the source for {item}')
                continue
            if not valid:
                continue
            questions.append(question(item, prompt, [(str(i + 1), label) for i, label in enumerate(options)]))
            truth[item] = str(int(raw))
        if not questions:
            continue
        background = {'Age': age_labels[age_code], 'Education': education_labels[education_code]}
        income = row.get('F_INC_SDT1')
        if income not in (None, 99):
            background['Family income code'] = str(int(income))
        rows.append({'study': 'pew111', 'person': person_id('pew111', row['QKEY']),
                     'stratum': f"{age_labels[age_code]}|{education_labels[education_code]}",
                     'weight': float(weight), 'background': background, 'context': PEW111_CONTEXT,
                     'questions': questions, 'truth': truth,
                     'group': f"{age_labels[age_code]}|{education_labels[education_code]}",
                     'country': 'United States', 'source_id': row['QKEY']})
    return rows


ADAPTERS = {'origin': origin_rows, 'packaging': packaging_rows, 'pew111': pew111_rows}


def build(study):
    if study not in ADAPTERS:
        raise ValueError('Unknown adapter ' + study)
    return ADAPTERS[study]()


def summary(rows):
    """Facts a reader needs before any model call; no scores here."""
    from collections import Counter

    from .matching import constraints

    eligible, excluded = [], Counter()
    for row in rows:
        rule, error = constraints(row)
        if error:
            excluded[error] += 1
        else:
            eligible.append(row)
    cards = Counter()
    for row in {r['person']: r for r in eligible}.values():
        for item in row['questions']:
            cards[(item['id'], tuple(o['label'] for o in item['options']))] += 1
    return {'people': len({r['person'] for r in rows}),
            'eligible_people': len(eligible),
            'excluded': dict(excluded),
            'questions_per_person': sorted({len(r['questions']) for r in rows}),
            'cards': len(cards),
            'cards_with_at_least_20_people': sum(1 for v in cards.values() if v >= 20),
            'weights': sorted({r['weight'] for r in rows})[:5] if rows else [],
            'mean_questions_per_person': (sum(len(r['questions']) for r in rows) / len(rows)) if rows else 0}


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('study', choices=sorted(ADAPTERS))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    data = build(args.study)
    result = summary(data)
    if args.output:
        if args.output.exists():
            raise ValueError('Do not overwrite a private adapter snapshot')
        args.output.write_text(json.dumps({'study': args.study, 'rows': data}, ensure_ascii=False))
        args.output.chmod(0o600)
    print(json.dumps(result, ensure_ascii=False))


def shoe_card_id(row):
    """Card identity from the displayed shoe, never from the per-respondent task index.

    Every respondent sees a different shoe under the same task number, so a
    task-based identity would silently merge unrelated cards and invent a
    historical share that no respondent ever produced.
    """
    values = '|'.join(f'{key}={row.get("attr_" + key, "")}' for key in SHOES_ATTRIBUTES)
    return 'shoe' + hashlib.sha256(values.encode()).hexdigest()[:12]


def rating_question(identifier, prompt, scale=SHOES_SCALE):
    return {'id': str(identifier), 'prompt': prompt, 'type': 'single_choice', 'required': True,
            'options': [{'id': str(level), 'label': str(level)} for level in scale]}


def shoes_rows():
    """One 1-7 rating per displayed shoe; no education variable exists in this study."""
    import gzip
    by_person = defaultdict(list)
    with gzip.open(SHOES, 'rt', newline='') as stream:
        for row in csv.DictReader(stream):
            by_person[row['id']].append(row)
    rows = []
    for raw_id, items in by_person.items():
        first = items[0]
        age_group = first.get('cov_age_group') or ''
        race = first.get('cov_race') or ''
        background = {'Age group': age_group, 'Race': race}
        party = first.get('cov_party_id') or ''
        if party:
            background['Party identification'] = party
        questions, truth = [], {}
        for item in sorted(items, key=lambda r: (int(r['task']), int(r['profile']))):
            rating = str(item.get('rating', '')).strip()
            if rating not in SHOES_SCALE:
                continue
            attributes = {key.replace('_', ' '): item.get(f'attr_{key}', '') for key in SHOES_ATTRIBUTES}
            label = product_label(attributes)
            if not label:
                continue
            identifier = shoe_card_id(item)
            if identifier in truth:
                continue
            questions.append(rating_question(identifier, f'Rate this shoe: {label}'))
            truth[identifier] = rating
        if not questions or len(truth) != len(questions):
            continue
        rows.append({'study': 'shoes', 'person': person_id('shoes', raw_id),
                     'stratum': f'{age_group}|{race}', 'weight': 1.0,
                     'background': background, 'context': SHOES_CONTEXT,
                     'questions': questions, 'truth': truth,
                     'group': f'{age_group}|{race}', 'country': 'United States',
                     'source_id': raw_id})
    return rows


def drone_rows():
    """One two-option delivery choice per answered card; the author's 0/1 codes are kept."""
    from .drone_baseline import COST_LEVELS, TIME_MINUTES, option_text
    import gzip
    with gzip.open(DRONE, 'rt', newline='') as stream:
        reader = csv.DictReader(stream)
        columns = [c for c in reader.fieldnames if DRONE_COLUMN.fullmatch(c)]
        records = list(reader)
    rows = []
    for row in records:
        background = {'Age group': DRONE_AGE.get(row.get('Q_age', '').strip(), 'Unknown'),
                      'Gender': DRONE_GENDER.get(row.get('Q_gender', '').strip(), 'Unknown')}
        for key, label in (('Household income', DRONE_INCOME), ('Residence type', DRONE_RESIDENCE)):
            value = label.get(row.get({'Household income': 'Q_income',
                                       'Residence type': 'Q_residence_type'}[key], '').strip())
            if value:
                background[key] = value
        questions, truth, seen = [], {}, set()
        for column in columns:
            parts = DRONE_COLUMN.fullmatch(column)
            answer = row[column]
            if answer not in ('0', '1'):
                continue
            vendor, gc, gt, dc, dt, dp = (int(parts.group(i)) for i in range(1, 7))
            card = f'drone_v{vendor}_gc{gc}_gt{gt}_dc{dc}_dt{dt}_dp{dp}'
            if card in seen:
                continue
            seen.add(card)
            options = [('0', option_text(0, vendor, COST_LEVELS[vendor][gc], TIME_MINUTES[vendor][gt], dp)),
                       ('1', option_text(1, vendor, COST_LEVELS[vendor][dc], TIME_MINUTES[vendor][dt], dp))]
            questions.append(question(card,
                                      f'Delivery of {["take-out food", "prescription medications", "items from a liquor store", "last-minute groceries"][vendor]}. '
                                      'Compare the two options. Which would you choose?', options))
            truth[card] = answer
        if not questions or len(truth) != len(questions):
            continue
        rows.append({'study': 'drone', 'person': person_id('drone', row['ResponseId']),
                     'stratum': f"{background['Age group']}|{background['Gender']}", 'weight': 1.0,
                     'background': background, 'context': DRONE_CONTEXT,
                     'questions': questions, 'truth': truth,
                     'group': f"{background['Age group']}|{background['Gender']}",
                     'country': 'United States', 'source_id': row['ResponseId']})
    return rows
