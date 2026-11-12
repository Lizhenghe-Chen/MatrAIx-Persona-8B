"""Candidate pool and demographic matching for the clean-v1 studies (drone, shoes).

Same selection rules as the v2 cohort: disjoint pilot/screen/reserve phases, largest
remainder allocation over the strata that actually exist, and personas drawn from the
release pool by hash order. No answer is read while selecting.
"""
import hashlib
import json
import random
from collections import Counter, defaultdict

import pyarrow.parquet as pq

from .adapters import (drone_rows, german_rows, origin_rows, packaging_rows, pew111_rows,
                       radiant_rows, shoes_rows, tshirt_rows)
from .matching import compatible, constraints
from .personas import FIELDS, decode
from .registry import DATA, OUT
from .targets import PRIVATE

SEED = 20261109
STUDIES = ('drone', 'shoes')
WIDE = ('origin', 'packaging', 'pew111', 'german', 'tshirt', 'radiant')
WIDE_LOADERS = {'origin': origin_rows, 'packaging': packaging_rows, 'pew111': pew111_rows,
                'german': german_rows, 'tshirt': tshirt_rows, 'radiant': radiant_rows}
PHASES = (('pilot', 8), ('screen', 48), ('reserve', 96))
UNDER_18 = ('Under 5', '5-12', '13-17', 'unknown')


def eligible(studies=STUDIES):
    loaders = {'drone': drone_rows, 'shoes': shoes_rows, **WIDE_LOADERS}
    by_study, excluded = {}, {}
    for study in studies:
        kept, reasons = [], Counter()
        for row in loaders[study]():
            rule, error = constraints(row)
            if error:
                reasons[error] += 1
                continue
            kept.append({**row, 'matching_rule': rule})
        by_study[study] = kept
        excluded[study] = dict(reasons)
    return by_study, excluded


def allocate(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[str(row['stratum'])].append(row)
    for key in groups:
        random.Random(f'{SEED}:{key}').shuffle(groups[key])
    chosen, used, summary = [], set(), {}
    for phase, size in PHASES:
        available = {k: [x for x in v if x['person'] not in used] for k, v in groups.items()}
        available = {k: v for k, v in available.items() if v}
        total = sum(map(len, available.values()))
        if total < size:
            raise ValueError(f'Insufficient disjoint participants for {phase}: {total} < {size}')
        quota = {k: int(size * len(v) / total) for k, v in available.items()}
        for key in sorted(available, key=lambda k: (-(size * len(available[k]) / total - quota[k]), k))[
                :size - sum(quota.values())]:
            quota[key] += 1
        phase_rows = []
        for key in sorted(available):
            for row in available[key][:quota[key]]:
                phase_rows.append({**row, 'phase': phase,
                                   'inclusion_probability': quota[key] / len(available[key])})
                used.add(row['person'])
        chosen += phase_rows
        summary[phase] = dict(Counter(str(r['stratum']) for r in phase_rows))
    return chosen, summary


def pool(needed_ages, regions=('North America',)):
    release = DATA / '09_MatrAIx画像/Persona-1M发行版'
    manifest = json.loads((release / 'manifest.json').read_text())
    columns = list(enumerate(json.loads((release / 'persona_codes.schema.json').read_text())['columns']))
    keep = [(i, c) for i, c in columns if c['id'] in FIELDS]
    buckets, seen, rng = defaultdict(list), Counter(), random.Random(SEED)
    for entry in manifest['files']:
        offset = 0
        for batch in pq.ParquetFile(release / entry['path']).iter_batches(
                batch_size=4096, columns=['source', 'attributes', 'null_bitmap', 'attribute_overrides']):
            for row in batch.to_pylist():
                index = offset
                offset += 1
                fields = decode(row, keep)
                if fields['region'] not in regions or fields['age_bracket'] not in needed_ages:
                    continue
                if row['source'] == 'real_human_survey':
                    continue
                key = (row['source'], *(str(fields[k]) for k in FIELDS))
                seen[key] += 1
                slot = len(buckets[key]) if len(buckets[key]) < 12 else rng.randrange(seen[key])
                if slot >= 12:
                    continue
                candidate = {'source': row['source'], 'shard': entry['path'], 'row_index': index,
                             'fields': fields}
                if slot == len(buckets[key]):
                    buckets[key].append(candidate)
                else:
                    buckets[key][slot] = candidate
        print('scanned', entry['path'], 'candidates', sum(map(len, buckets.values())), flush=True)
    return [x for key in sorted(buckets) for x in buckets[key]]


def build(studies, path, report_path):
    if path.exists():
        raise ValueError('Do not overwrite a frozen cohort snapshot: ' + str(path))
    by_study, excluded = eligible(studies)
    chosen, summaries = {}, {}
    for study in studies:
        chosen[study], summaries[study] = allocate(by_study[study])
    needed, regions = set(), set()
    for rows in chosen.values():
        for row in rows:
            needed.update(row['matching_rule']['allowed']['age_bracket'])
            regions.update(row['matching_rule']['allowed']['region'])
    candidates = pool(needed, tuple(sorted(regions)))
    by_age = defaultdict(list)
    for candidate in candidates:
        by_age[candidate['fields']['age_bracket']].append(candidate)
    matched, used_per_study = [], defaultdict(set)
    for study in studies:
        for row in chosen[study]:
            rule = row['matching_rule']
            options = [c for age in rule['allowed']['age_bracket'] for c in by_age.get(age, [])]
            options = [c for c in options if compatible(c, rule)]
            options.sort(key=lambda c: hashlib.sha256(
                f"{SEED}:{study}:{row['person']}:{c['shard']}:{c['row_index']}".encode()).hexdigest())
            unused = [c for c in options if (c['shard'], c['row_index']) not in used_per_study[study]]
            pick = (unused or options or [None])[0]
            if pick:
                used_per_study[study].add((pick['shard'], pick['row_index']))
            matched.append({**row, 'persona': pick,
                            'match_status': 'release_match' if pick else 'requires_generated_supplement',
                            'candidate_pool_matches': len(options)})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(matched, ensure_ascii=False) + '\n')
    path.chmod(0o600)
    report = {'status': 'candidate_matching_not_formal_freeze', 'seed': SEED,
              'candidate_pool_records': len(candidates),
              'snapshot_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'studies': {}}
    for study in studies:
        rows = [r for r in matched if r['study'] == study]
        report['studies'][study] = {
            'eligible_respondents': len(by_study[study]),
            'excluded': excluded[study],
            'phase_allocation': summaries[study],
            'selected': len(rows),
            'matched': sum(r['persona'] is not None for r in rows),
            'unique_release_profiles': len(used_per_study[study]),
            'age_resolutions': dict(Counter(r['matching_rule']['age_resolution'] for r in rows)),
            'education_resolution': 'unavailable_in_instrument',
            'match_fields': sorted({k for r in rows for k in r['matching_rule']['allowed']}),
            'source_counts': dict(Counter(r['persona']['source'] for r in rows if r['persona'])),
        }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({s: (v['matched'], v['selected']) for s, v in report['studies'].items()}))


def main():
    build(STUDIES, PRIVATE / 'cohort-clean-v1.json', OUT / 'matching-clean-v1.json')


def main_wide():
    build(WIDE, PRIVATE / 'cohort-wide-v1.json', OUT / 'matching-wide-v1.json')


if __name__ == '__main__':
    main()
