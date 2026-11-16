"""Audit workbook response codes and freeze the original beef choice design."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

SOURCE = Path.home() / '.local/share/matraix-decision-transfer/work/materials/beef-steak/harrison.xls'
SOURCE_SHA = '4020d960f29e83fae668ea4b83929ce411876c7ffc1f92b06bbb09e871a37759'
# Original paper appendix, in cents. The replication book has several conflicting entries.
PRICES = (
    (338, 788, 675, 675, 675),
    (450, 900, 675, 563, 900),
    (675, 900, 563, 900, 675),
    (563, 900, 900, 675, 563),
    (675, 675, 675, 788, 563),
    (450, 788, 788, 900, 563),
    (450, 675, 563, 675, 788),
    (563, 563, 675, 900, 788),
    (563, 788, 563, 788, 900),
    (563, 675, 788, 563, 675),
    (675, 788, 900, 563, 788),
    (450, 563, 563, 788, 675),
    (338, 900, 788, 788, 788),
    (338, 563, 563, 563, 563),
    (338, 675, 900, 900, 900),
    (675, 563, 788, 675, 900),
    (563, 563, 563, 563, 563),
)
OPTIONS = ('Generic', 'Guaranteed Tender', 'Natural', 'USDA Choice', 'Certified Angus Beef', 'None')
# Published Table 2, "None" row for scenarios 1–17.
PUBLISHED_NO_BUY = {
    'incentivized': (25.4, 19.4, 37.3, 16.4, 16.4, 16.4, 32.8, 29.9, 41.8, 17.9, 17.9,
                     29.9, 32.8, 11.9, 31.3, 29.9, 14.9),
    'hypothetical': (2.7, 0, 10.8, 8.1, 8.1, 2.7, 0, 13.5, 13.5, 8.1, 8.1, 8.1, 16.2,
                     0, 13.5, 13.5, 2.7),
}


def load_responses(path):
    import xlrd

    if sha256(path.read_bytes()).hexdigest() != SOURCE_SHA:
        raise ValueError('Unexpected workbook hash')
    sheet = xlrd.open_workbook(path).sheet_by_name('trt 10&11')
    if sheet.cell_value(0, 0) != 'Subject' or sheet.row_values(1, 38, 55) != list(range(1, 18)):
        raise ValueError('Unexpected workbook layout')
    cohorts = {group: [] for group in PUBLISHED_NO_BUY}
    people, excluded = set(), 0
    for row in range(3, sheet.nrows):
        subject = sheet.cell_value(row, 0)
        if not isinstance(subject, float) or not 1001 <= subject <= 1199 or not subject.is_integer():
            continue
        if subject in people:
            raise ValueError('Duplicate subject')
        people.add(subject)
        choices = sheet.row_values(row, 38, 55)
        if all(choice == '' for choice in choices):
            excluded += 1
            continue
        if any(choice not in range(1, 7) for choice in choices):
            raise ValueError('Unexpected missing or invalid choice')
        group = 'incentivized' if subject < 1100 else 'hypothetical'
        cohorts[group].append([int(choice) for choice in choices])
    if [len(rows) for rows in cohorts.values()] != [67, 37] or excluded != 1:
        raise ValueError('Unexpected sample counts')
    return cohorts, excluded


def audit(path):
    cohorts, excluded = load_responses(path)
    observed = {}
    for group, choices in cohorts.items():
        rates = [round(100 * Counter(column)[6] / len(choices), 1) for column in zip(*choices, strict=True)]
        if tuple(rates) != PUBLISHED_NO_BUY[group]:
            raise ValueError(f'Workbook differs from published no-purchase percentages: {group}')
        observed[group] = {'people': len(choices), 'recorded_choices': len(choices) * len(PRICES),
                           'no_buy_pct_by_card': rates,
                           'no_buy_rate': sum(row.count(6) for row in choices) / (len(choices) * len(PRICES))}
    return {'source_sha256': SOURCE_SHA, 'excluded_empty_records': excluded,
            'option_order': OPTIONS, 'price_cents_by_card': PRICES, 'observed': observed}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    print(json.dumps(audit(parser.parse_args().source), indent=2))
