"""Native persona rendering and demographic matching for the Swiss study.

The renderer is a frozen copy of the product implementation (see data/native/persona
and provenance.json). Matching uses only audited categorical demographics; target
choices never enter the match.
"""
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

NATIVE = Path(__file__).resolve().parents[1] / 'data/native/persona'
SEED = 20261109
# Persona-1M dimension ids used for matching and rendering.
FIELDS = ['region', 'age_bracket', 'highest_education', 'gender_identity',
          'demo_household_income', 'demo_employment_status', 'lstyle_household_size']
# Rows whose provenance cannot rule out overlap with the survey panel are quarantined.
EXCLUDED_SOURCES = {'real_human_survey'}
REGION = 'Western Europe'  # Switzerland; coarse by construction, never a residence claim.
AGE = ['18-24', '25-34', '35-44', '45-54', '55-64', '65-74', '75-84', '85+']
DEGREE = ["Bachelor's", "Master's", 'Doctorate', 'Postdoc']
AGE_FOR_BAND = {'18-29': ['18-24', '25-34'],
                '30-64': ['25-34', '35-44', '45-54', '55-64'],
                '65+': ['65-74', '75-84', '85+']}
EDUCATION = {
    'University/ETH/UAS': DEGREE,
    'Apprenticeship/Vocational school': ['Vocational / cert', "Associate's"],
    'High school (Matura)': ['Secondary'],
    'No/Compulsory school': ['No formal', 'Primary'],
}
GENDER = {'Male': 'Man', 'Female': 'Woman'}


def sha256(path):
    with open(path, 'rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def verify_snapshot():
    provenance = json.loads((NATIVE / 'provenance.json').read_text())
    for name, entry in provenance['files'].items():
        if sha256(NATIVE / name) != entry['sha256']:
            raise ValueError('Native renderer snapshot changed: ' + name)
    return provenance


def constraints(background):
    """Persona constraints for one respondent; None when the instrument cannot map."""
    ages = AGE_FOR_BAND.get(background.get('age_band'))
    education = EDUCATION.get(background.get('education'))
    gender = GENDER.get(background.get('gender'))
    if not ages or not education or not gender:
        return None, 'unmapped_' + ('age' if not ages else 'education' if not education else 'gender')
    return {'region': [REGION], 'age_bracket': ages,
            'highest_education': education, 'gender_identity': [gender]}, None


def compatible(fields, rule):
    return all(fields.get(key) in values for key, values in rule.items())


def render(dimensions):
    """Native dimension narrative; unmeasured attributes are omitted, never invented."""
    dimensions = {k: v for k, v in dimensions.items() if v not in (None, 'unknown', 'invalid_code')}
    if not dimensions:
        raise ValueError('No measured persona dimension to render')
    schema = json.loads((NATIVE / 'dimensions.json').read_text())
    allowed = {d['id']: d['values'] for d in schema['dimensions']}
    for key, value in dimensions.items():
        if key not in allowed or not isinstance(value, str) or value not in allowed[key]:
            raise ValueError('Unapproved persona field or value: ' + str(key))
    import sys
    sys.path.insert(0, str(NATIVE))
    import persona_dimension_catalog as catalog
    env = Environment(loader=FileSystemLoader(str(NATIVE)), undefined=StrictUndefined,
                      trim_blocks=True, lstrip_blocks=True)
    context = dict(dimensions=dimensions, display_name='', demographics={}, psychology={},
                   communication={}, preferences={}, behavior={}, summary='', system_prompt='')
    text = env.get_template('persona_system.md.j2').render(
        **context, **catalog.build_template_context_extras(dimensions, catalog_path=str(NATIVE / 'dimensions.json'))).strip()
    if not text or text == '## Who you are':
        raise ValueError('Native renderer produced no profile')
    return text


def decode_row(row, columns):
    import json as _json
    overrides = row['attribute_overrides'] or {}
    if isinstance(overrides, str):
        overrides = _json.loads(overrides)
    if isinstance(overrides, list):
        overrides = dict(overrides)
    out = {}
    for index, column in columns:
        key = column['id']
        if key in overrides:
            out[key] = overrides[key]
        elif row['null_bitmap'] is not None and (row['null_bitmap'][index // 8] >> (index % 8)) & 1:
            out[key] = 'unknown'
        else:
            code = (row['attributes'][index // 2] >> (4 * (index % 2))) & 15
            out[key] = column['values'][code] if code < len(column['values']) else 'invalid_code'
    return out


def build_pool(root, wanted_regions=(REGION,), shards=None):
    """Scan the release once and keep a bounded reservoir per demographic cell."""
    import pyarrow.parquet as pq
    manifest = json.loads((root / 'manifest.json').read_text())
    schema = json.loads((root / 'persona_codes.schema.json').read_text())['columns']
    columns = [(i, c) for i, c in enumerate(schema) if c['id'] in FIELDS]
    pool = defaultdict(list)
    counts = defaultdict(int)
    for entry in manifest['files']:
        if shards and entry['path'] not in shards:
            continue
        handle = pq.ParquetFile(root / entry['path'])
        for batch in handle.iter_batches(batch_size=4096, columns=['source', 'attributes', 'null_bitmap', 'attribute_overrides']):
            for offset, row in enumerate(batch.to_pylist()):
                if row['source'] in EXCLUDED_SOURCES:
                    continue
                fields = decode_row(row, columns)
                if fields['region'] not in wanted_regions:
                    continue
                if fields['age_bracket'] in (None, 'unknown', 'Under 5', '5-12', '13-17', 'invalid_code'):
                    continue
                key = (row['source'], *(str(fields[f]) for f in ('age_bracket', 'highest_education', 'gender_identity')))
                counts[key] += 1
                key_full = (row['source'], *(str(fields[f]) for f in FIELDS))
                bucket = pool[key_full]
                if len(bucket) < 6:
                    bucket.append({'source': row['source'], 'shard': entry['path'],
                                   'row_index': offset, 'fields': fields})
        del handle
    return pool, counts


def match(pool, rule, pub_id, used):
    """Deterministic choice among compatible unused profiles; no answer is consulted."""
    candidates = []
    for key, rows in pool.items():
        for row in rows:
            if compatible(row['fields'], rule) and (row['shard'], row['row_index']) not in used:
                candidates.append(row)
    if not candidates:
        return None
    candidates.sort(key=lambda c: hashlib.sha256(
        f'{SEED}:{pub_id}:{c["shard"]}:{c["row_index"]}'.encode()).hexdigest())
    return candidates[0]


def _main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['build-pool'])
    parser.add_argument('--root', default='/Volumes/元宇宙联合创新实验室/实验数据/MatrAIx多地区选品源数据/09_MatrAIx画像/Persona-1M发行版')
    parser.add_argument('--out', default=str(Path.home() / '.local/share/matraix-decision-transfer/work/stage2/persona-pool.json'))
    parser.add_argument('--shards', type=int, default=0, help='limit shards for a quick coverage probe')
    args = parser.parse_args()
    root = Path(args.root)
    manifest = json.loads((root / 'manifest.json').read_text())
    shards = [entry['path'] for entry in manifest['files'][:args.shards]] if args.shards else None
    pool, counts = build_pool(root, shards=shards)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'seed': SEED, 'shards': shards or 'all',
                               'cells': {json.dumps(list(k)): v for k, v in pool.items()},
                               'cell_counts': {json.dumps(list(k)): v for k, v in counts.items()}}))
    print(json.dumps({'pool_cells': len(pool), 'pool_profiles': sum(len(v) for v in pool.values()),
                      'distinct_demographic_cells': len(counts)}, ensure_ascii=False))


if __name__ == '__main__':
    _main()
