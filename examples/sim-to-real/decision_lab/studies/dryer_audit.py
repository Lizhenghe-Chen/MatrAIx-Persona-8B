"""Audit official dryer tables without exporting respondent identifiers."""
import hashlib
import json
from pathlib import Path
import pandas as pd


def audit(directory):
    directory = Path(directory)
    paths = [directory / n for n in ('Tumbledrier_DCE.dta', 'Tumbledrier_DCE_wide.dta')]
    long, wide = [pd.read_stata(p, convert_categoricals=False) for p in paths]
    keys = ['ResponseId', 'ChoiceSet']
    cards = long.groupby(keys)
    errors = []
    if long.duplicated(keys + ['Alternative']).any(): errors.append('duplicate alternative')
    if not cards['Alternative'].apply(lambda x: set(x) == {0, 1, 2}).all():
        errors.append('unexpected alternatives')
    if not cards.choicer.sum().eq(1).all(): errors.append('invalid selected alternative count')
    if not long.choicer.eq(long.Choice.eq(long.Alternative).astype(int)).all():
        errors.append('Choice and choicer disagree')
    if not long.OptOut.eq(long.Alternative.eq(0).astype(int)).all():
        errors.append('opt-out mapping mismatch')
    people = long.drop_duplicates('ResponseId')
    joined = people.merge(wide, on='ResponseId', suffixes=('_long', '_wide'), validate='one_to_one')
    differences = {}
    for field in ['Age', 'Education', 'Treatment', 'CountryVersion', 'Tumbledrier_usage']:
        differences[field] = int((joined[field+'_long'].fillna('NA') != joined[field+'_wide'].fillna('NA')).sum())
    long_ids, wide_ids = set(long.ResponseId), set(wide.ResponseId)
    return {
        'status': 'not_admitted_pending_sample_and_display_reconciliation',
        'source': 'https://zenodo.org/records/10046247',
        'files': {p.name: {'bytes':p.stat().st_size, 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths},
        'alternative_rows':len(long), 'people':len(people), 'choice_tasks':cards.ngroups,
        'tasks_per_person':{str(k):int(v) for k,v in long.groupby('ResponseId').ChoiceSet.nunique().value_counts().items()},
        'alternatives':{'0':'Neither', '1':'Tumble dryer 1', '2':'Tumble dryer 2'},
        'people_by_survey_version':{str(k):int(v) for k,v in people.CountryVersion.value_counts().items()},
        'wide_people':len(wide), 'shared_people':len(long_ids & wide_ids),
        'only_long_people':len(long_ids-wide_ids), 'only_wide_people':len(wide_ids-long_ids),
        'shared_background_mismatches':differences, 'structural_errors':errors,
        'pending':['Explain 14 wide-only and 2 long-only respondents; do not assume a simple exclusion filter.',
                   'Verify country/treatment-specific displayed energy information against original choice cards.',
                   'Reproduce author descriptive statistics and freeze background timing whitelist.'],
        'privacy':'Only aggregate audit counts and source hashes exported; respondent identifiers stay in source files.'}

if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser(); p.add_argument('directory'); p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); a.output.write_text(json.dumps(audit(a.directory),ensure_ascii=False,indent=2)+'\n')
