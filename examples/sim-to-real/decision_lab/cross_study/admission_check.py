"""Executable admission gate: a study is scoreable only with recorded evidence.

Three outcomes per study:
  admitted                 every gate has recorded evidence, a same-information
                           reference is declared, the card-support rule is set,
                           and pre-registered exclusions are listed.
  retrospective_incomplete  used before this gate existed; the missing evidence
                           is named instead of being certified after the fact.
  pending                  not ready for a formal run.
"""
import argparse
import json
from pathlib import Path

from .registry import OUT, SPEC

DECLARATIONS = SPEC / 'admission-declarations.json'
OUTPUT = OUT / 'admission-v2.json'


def evaluate(declarations):
    gates = declarations['gates']
    kinds = set(declarations['reference_kinds'])
    minimum = declarations['minimum_people_per_card']
    rows, failures = [], []
    for study in declarations['studies']:
        missing = []
        record = study.get('gates', {})
        for gate in gates:
            entry = record.get(gate) or {}
            if entry.get('status') != 'passed' or not entry.get('evidence'):
                missing.append(gate)
        reference = study.get('reference') or {}
        if reference.get('kind') not in kinds:
            missing.append('reference_not_declared')
        if reference.get('excludes_evaluated') is not True:
            missing.append('reference_may_include_evaluated')
        distribution = study.get('distribution') or {}
        if distribution.get('minimum_people_per_card', 0) < minimum:
            missing.append('card_support_rule_missing')
        if not isinstance(study.get('exclusions'), list):
            missing.append('exclusions_not_preregistered')
        status = study.get('status', 'pending')
        if status == 'admitted' and missing:
            failures.append({'id': study['id'], 'declared': 'admitted', 'missing': missing})
            status = 'misdeclared'
        rows.append({'id': study['id'], 'name': study.get('name'), 'evidence_tier': study.get('evidence_tier'),
                     'declared_status': study.get('status'), 'status': status, 'missing': missing,
                     'reference': reference.get('kind'),
                     'distribution_estimable': distribution.get('estimable'),
                     'exclusions': study.get('exclusions') or []})
    return {'status': 'admission_checked', 'studies': rows, 'misdeclared': failures,
            'admitted': [r['id'] for r in rows if r['status'] == 'admitted'],
            'incomplete': [r['id'] for r in rows if r['status'] != 'admitted']}


def require(result, ids):
    not_admitted = [i for i in ids if i not in result['admitted']]
    if not_admitted:
        raise ValueError('Not admitted: ' + ', '.join(not_admitted))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--declarations', type=Path, default=DECLARATIONS)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--require', nargs='*', default=[])
    args = parser.parse_args()
    result = evaluate(json.loads(args.declarations.read_text()))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'admitted': result['admitted'], 'incomplete': result['incomplete'],
                      'misdeclared': result['misdeclared']}, ensure_ascii=False))
    if result['misdeclared']:
        raise SystemExit(2)
    if args.require:
        require(result, args.require)


if __name__ == '__main__':
    main()
