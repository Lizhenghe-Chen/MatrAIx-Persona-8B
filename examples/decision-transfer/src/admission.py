"""Rebuild the data-admission records from the sources, never from cached numbers.

Swiss: wording from supplementary A.1, order from A.10, mapping proven by reproducing
Table 2 and by an exact person-level link to the conjoint choices.
US origin: demographics are resolvable, but the six attitude items cannot be tied to
the data columns, so the study is not admitted.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

import pandas as pd

import swiss

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / 'data/admission'
ORIGIN = Path('/Volumes/元宇宙联合创新实验室/实验数据/MatrAIx多地区选品源数据/06_历史北美电商/origin-original.tab')
MATERIALS = Path.home() / '.local/share/matraix-decision-transfer/work/materials'


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def swiss_record(sep, conjoint):
    people, linkage, persons = swiss.people(sep, conjoint)
    valid = [p for p in people if swiss.valid_task_person(p)]
    complete = [p for p in valid if all(v is not None for v in p['facts'].values())]
    reliability = swiss.reliability(sep)
    bad = swiss.check_reliability(reliability)
    if bad:
        raise RuntimeError('Item mapping does not reproduce Table 2: ' + json.dumps(bad))
    return {
        'study': 'swiss_six',
        'date': '2026-11-13',
        'status': 'admitted_for_stage2',
        'sources': {
            'conjoint': {'path': str(swiss.RAW / 'w14_conjoint.RData'),
                         'sha256': sha(swiss.RAW / 'w14_conjoint.RData')},
            'background': {'path': str(swiss.RAW / 'SEP_w14_reduced.RData'),
                           'sha256': sha(swiss.RAW / 'SEP_w14_reduced.RData')},
            'author_code': {'path': str(swiss.RAW / 'Dragons_ReplicationCode_Gomm.R'),
                            'sha256': sha(swiss.RAW / 'Dragons_ReplicationCode_Gomm.R')},
            'supplement': {'path': str(MATERIALS / 'swiss-six-supplement.docx'),
                           'sha256': sha(MATERIALS / 'swiss-six-supplement.docx'),
                           'origin': 'Elsevier mmc1.docx for PII S2352550926000461, CC BY 4.0'},
            'questionnaire_ocr': str(MATERIALS / 'swiss-six-questionnaire-ocr.txt'),
        },
        'evidence': {
            'wording': 'Supplementary A.1 lists every TPB and DIPB item verbatim; the OCR of A.10 '
                       'shows the items as administered, including the 1-7 anchors.',
            'timing': 'A.10 page order: person details, TPB block, DIPB block, conjoint task, post-conjoint '
                      'labels, closing questions. Every fact item is answered before any product choice.',
            'instrument': 'Paper section 3.2.2 and A.10: two products, three paired rounds, forced binary '
                          'choice, then a separate purchase-likelihood rating.',
            'price_levels': 'Table 1 CHF levels per product; the questionnaire displayed a coloured A-E impact '
                            'scale whose exact letter-to-level assignment is not recoverable, so only the '
                            'published level labels are used.',
        },
        'linkage': {
            'method': 'SEP rows follow ascending PubId; verified by recomputing eight published aggregates.',
            'checks': linkage,
            'persons': persons,
            'mismatches': 0,
        },
        'reliability_check': {'computed': reliability,
                              'paper_table2': {k: list(v) for k, v in swiss.PAPER_TABLE2.items()},
                              'tolerance': {'alpha': 0.02, 'mean': 0.12, 'sd': 0.06}},
        'counts': {'persons_with_valid_choices': len(valid), 'persons_with_all_29_items': len(complete)},
        'fields': [{'column': column, 'block': block, 'wording': wording,
                    'scale': '1-7', 'measured': 'before the choice task',
                    'answer_derived': False} for column, block, wording in swiss.FACT_ITEMS],
        'excluded_fields': {'columns': swiss.PROHIBITED,
                            'reason': 'choice, rating, intention and any choice-derived score'},
        'limitations': [
            'The authors excluded speeders and registry mismatches; those flags are not in the released files, so '
            'the analysed sample cannot be reproduced exactly. The frame here is every respondent with valid '
            'choices and complete items.',
            'envcon, envbeh and cfc exist only as precomputed indices in the release; they are not used because a '
            'standardised score cannot be turned into a faithful natural-language fact.',
            'Paper text says jeans in one place and the data says Jacket; the data label is used and not harmonised.',
            'The paper anchors the rating scale in the opposite direction to the questionnaire screenshot; ratings '
            'are excluded from model input, so this does not affect the experiment.',
        ],
    }


def origin_record():
    frame = pd.read_csv(ORIGIN, sep='\t', dtype=str)
    person = frame.groupby('id').first().reset_index()
    person['ethnocentrism'] = pd.to_numeric(person['ethnocentrism'])
    items = [f'q11_{i}_w1' for i in range(1, 7)]
    for column in items:
        person[column] = pd.to_numeric(person[column])
    subset = person.dropna(subset=items + ['ethnocentrism'])
    hits = []
    for size in (4, 5, 6):
        for columns in itertools.combinations(items, size):
            for signs in itertools.product([1, -1], repeat=size):
                adjusted = pd.DataFrame({c: (subset[c] if s == 1 else 6 - subset[c])
                                         for c, s in zip(columns, signs)})
                candidate = (adjusted.mean(axis=1) - 1) / 4
                if float((candidate - subset['ethnocentrism']).abs().max()) < 1e-9:
                    hits.append({'columns': list(columns), 'signs': list(signs), 'formula': '(mean-1)/4'})
    return {
        'study': 'origin',
        'date': '2026-11-13',
        'status': 'not_admitted',
        'source': {'path': str(ORIGIN), 'sha256': sha(ORIGIN), 'rows': int(len(frame)),
                   'note': 'Byte-identical to the authors\' final_w1w2.tab in the Dataverse archive.'},
        'resolved': {
            'age': 'stored as (age - 17); the authors add 17 in Appendix.R before banding',
            'education': 'q22_w1 (1-7) is the education instrument; the educ column is a different, coarser code',
            'income': 'inc 1-11 folded into four published bands; code 5 is captured by the 30-59k branch because '
                      'the authors\' case_when tests that range first',
            'gender': '1 Male, 2 Female, 3 Other, missing treated as Other by the authors',
            'timing': 'Wave 1 (April 2020) held the attitudes; wave 2 (June 2020) held the conjoint, so attitudes '
                      'are strictly pre-choice.',
        },
        'unresolved': [
            'The six attitude items are known only as appendix prose. Without the instrument screenshot, the text '
            'cannot be tied to q11_1..q11_6: exactly one four-item combination reproduces the published scale, '
            'and its sign pattern does not match the appendix ordering.',
            'Column-to-wording order may have been randomised at administration; guessing would mislabel facts.',
        ],
        'scale_reconstruction': {'matches': hits, 'people_compared': int(len(subset)),
                                 'max_abs_error': 0.0 if hits else None},
        'consequence': 'No extra measured facts can be produced without inventing wording, so this study stays out '
                       'of the stage-2 screen. It is not swapped for a different dataset.',
        'next_source_needed': 'The article\'s online appendix Figure A1 (survey instrument screenshot) or the '
                              'preregistered questionnaire at https://osf.io/dnujq.',
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    sep = swiss.load_sep()
    conjoint = swiss.load_conjoint()
    records = {'swiss.json': swiss_record(sep, conjoint), 'origin.json': origin_record()}
    for name, record in records.items():
        path = OUT / name
        text = json.dumps(record, ensure_ascii=False, indent=1) + '\n'
        if args.check:
            if path.read_text() != text:
                raise SystemExit('Admission record is stale: ' + name)
        else:
            path.write_text(text)
    print(json.dumps({'swiss': records['swiss.json']['status'], 'origin': records['origin.json']['status'],
                      'swiss_persons': records['swiss.json']['counts'],
                      'origin_scale_matches': len(records['origin.json']['scale_reconstruction']['matches'])},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
