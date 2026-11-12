"""Author attribute tables and label parsing for the drone delivery study.

Level tables are copied from the author's `drone-attributes.py`; the option text
here is our declared rendering of those codes, because the published survey's
screens are not in the archive. Nothing outside the author's own level strings is
invented: privacy uses the author's literal 'NO privacy' / 'YES privacy'.
"""
import re

VENDOR_TYPES = ['take-out food', 'prescription medications', 'items from a liquor store',
                'last-minute groceries']
COST_LEVELS = [[0, 1, 3, 5], [0, 1, 5, 10], [0, 1, 3, 5], [0, 1, 3, 5]]
TIME_MINUTES = [[15, 20, 30, 45], [30, 120, 360, 1440], [15, 20, 30, 45], [15, 20, 30, 45]]
TIME_TEXT = {15: '15 minutes', 20: '20 minutes', 30: '30 minutes', 45: '45 minutes',
             120: '2 hrs', 360: '6 hrs', 1440: '1 day'}
PRIVACY_TEXT = {0: 'NO privacy', 1: 'YES privacy'}
GROUND = 'Ground vehicle'
DRONE = 'Drone'


def option_text(alternative, vendor, cost, minutes, privacy):
    if alternative == 0:
        return f'{GROUND}: delivery fee ${cost}, wait {TIME_TEXT[minutes]}'
    return f'{DRONE}: delivery fee ${cost}, wait {TIME_TEXT[minutes]}, privacy: {PRIVACY_TEXT[privacy]}'


def attributes(label):
    """Numeric features for one displayed alternative: fee, minutes, drone, privacy protected."""
    is_drone = 1.0 if label.startswith(DRONE) else 0.0
    fee = re.search(r'delivery fee \$([\d.]+)', label)
    if fee is None:
        raise ValueError('Missing delivery fee: ' + label)
    wait = re.search(r'wait ([^,]+)', label)
    if wait is None:
        raise ValueError('Missing wait time: ' + label)
    minutes = {'15 minutes': 15, '20 minutes': 20, '30 minutes': 30, '45 minutes': 45,
               '2 hrs': 120, '6 hrs': 360, '1 day': 1440}
    if wait.group(1).strip() not in minutes:
        raise ValueError('Unknown wait time: ' + wait.group(1))
    protected = 1.0 if 'YES privacy' in label else 0.0
    return [float(fee.group(1)), float(minutes[wait.group(1).strip()]), is_drone,
            is_drone * protected]
