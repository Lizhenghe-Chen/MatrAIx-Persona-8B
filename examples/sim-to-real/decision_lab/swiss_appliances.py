"""Validate published choice cards; not yet an admitted model-input adapter."""
from pathlib import Path
import hashlib
import json
import re
import pandas as pd

PRODUCT_INDEX = {'Smartphone': 0, 'TV': 1, 'Washing machine': 2}


def decode_composite(value, product):
    if product not in PRODUCT_INDEX:
        raise ValueError('Unreviewed product type: ' + product)
    numbers = re.findall(r'\d+', value)
    if len(numbers) != 3:
        raise ValueError('Expected three product-specific values')
    return int(numbers[PRODUCT_INDEX[product]])


def audit(directory):
    directory = Path(directory)
    source = directory / 'w8_conjoint.csv'
    df = pd.read_csv(source)
    bg = pd.read_csv(directory / 'w7_w8_subgroups.csv')
    errors = []
    keys = ['PubId', 'round', 'product']
    if df.duplicated(keys).any() or bg.duplicated(keys).any():
        errors.append('duplicate person-round-product')
    joined = df.merge(bg, on=keys, how='outer', indicator=True, suffixes=('', '_bg'))
    if not joined['_merge'].eq('both').all():
        errors.append('background join does not cover every choice row')
    for c in ['choice','Price','Functional duration','product_type']:
        if not joined[c].eq(joined[c+'_bg']).all():
            errors.append('choice/background disagreement: '+c)
    cards = df.groupby(['PubId','round'])
    if not cards.size().eq(2).all(): errors.append('not exactly two alternatives')
    if not cards['choice'].sum().eq(1).all(): errors.append('not exactly one choice')
    if not df['choice'].isin([0,1]).all(): errors.append('invalid choice encoding')
    unknown = sorted(set(df['product_type']) - set(PRODUCT_INDEX))
    if unknown: errors.append('unreviewed product labels: '+str(unknown))
    decoded = {}
    if not unknown:
        for product, group in df.groupby('product_type'):
            decoded[product] = {
                'people': int(group['PubId'].nunique()),
                'prices_CHF': sorted({decode_composite(x,product) for x in group['Price']}),
                'duration_years': sorted({decode_composite(x,product) for x in group['Functional duration']})}
    return {'status':'structural_checks_passed_not_admitted' if not errors else 'mapping_error',
            'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'rows':len(df),'people':int(df['PubId'].nunique()),'choice_cards':len(cards),
            'tasks_per_person':{str(k):int(v) for k,v in cards.size().groupby(level=0).size().value_counts().items()},
            'decoded_attributes':decoded,'errors':errors,
            'mapping_evidence':'data_structuring_ce_paper.R lines 185–197 map composite values to smartphone/television/washing machine; lines 223–226 label product assignment.',
            'pending':['original questionnaire language and instructions','background measurement timing and white list','author descriptive statistics','cloud-use license review'],
            'excluded_pending_review':['choice-derived ce_index and ce_category','same-wave stated attribute importance','willingness-to-pay fields']}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.write_text(json.dumps(audit(a.directory),ensure_ascii=False,indent=2)+'\n')
