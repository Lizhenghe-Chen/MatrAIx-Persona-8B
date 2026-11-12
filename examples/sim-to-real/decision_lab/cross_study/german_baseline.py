"""German tomato packaging study: author design table and attribute parsing.

The choice design is fixed for every respondent (12 tasks x 3 profiles), which is
why it can be reconstructed exactly from the author's XLSTAT workbook. Only the
"without bioplastic information" arm is used: the information text itself is not in
the archive, so including that arm would show respondents something they did not see.
"""
import re

PROFILES = {
    'Profil 1': ('Bio-based', 'Non-biodegradable', '5 days', '0,45 EUR'),
    'Profil 2': ('Fossil-based', 'Biodegradable', '5 days', '0,30 EUR'),
    'Profil 3': ('Fossil-based', 'Non-biodegradable', '7 days', '0,60 EUR'),
    'Profil 4': ('Bio-based', 'Biodegradable', '7 days', '0,45 EUR'),
    'Profil 5': ('Fossil-based', 'Biodegradable', '7 days', '0,45 EUR'),
    'Profil 6': ('Fossil-based', 'Non-biodegradable', '3 days', '0,45 EUR'),
    'Profil 7': ('Bio-based', 'Non-biodegradable', '7 days', '0,30 EUR'),
    'Profil 8': ('Fossil-based', 'Biodegradable', '5 days', '0,60 EUR'),
    'Profil 9': ('Bio-based', 'Biodegradable', '3 days', '0,60 EUR'),
    'Profil 10': ('Bio-based', 'Non-biodegradable', '5 days', '0,60 EUR'),
    'Profil 11': ('Fossil-based', 'Non-biodegradable', '3 days', '0,30 EUR'),
    'Profil 12': ('Bio-based', 'Biodegradable', '3 days', '0,30 EUR'),
}
# Author's design: task -> the three profiles shown, in the order the choice codes refer to.
TASKS = {
    1: ('Profil 12', 'Profil 1', 'Profil 11'),
    2: ('Profil 2', 'Profil 3', 'Profil 4'),
    3: ('Profil 7', 'Profil 6', 'Profil 5'),
    4: ('Profil 8', 'Profil 9', 'Profil 10'),
    5: ('Profil 1', 'Profil 12', 'Profil 2'),
    6: ('Profil 5', 'Profil 4', 'Profil 3'),
    7: ('Profil 6', 'Profil 7', 'Profil 8'),
    8: ('Profil 11', 'Profil 10', 'Profil 9'),
    9: ('Profil 3', 'Profil 2', 'Profil 1'),
    10: ('Profil 4', 'Profil 5', 'Profil 6'),
    11: ('Profil 9', 'Profil 8', 'Profil 7'),
    12: ('Profil 10', 'Profil 11', 'Profil 12'),
}
NONE = ('0', 'None of these (I would not buy any)')


def option_text(profile):
    material, biodegradable, shelf, price = PROFILES[profile]
    return (f'Packaging material: {material}, biodegradability: {biodegradable}, '
            f'shelf life: {shelf}, price: {price}')


def attributes(label):
    """Numeric features for the conditional-logit fallback: bio, biodegradable, days, euro."""
    if label == NONE[1]:
        return [0.0, 0.0, 0.0, 0.0]
    bio = 1.0 if 'Bio-based' in label else 0.0
    degradable = 1.0 if 'biodegradability: Biodegradable' in label else 0.0
    days = re.search(r'shelf life: (\d+) days', label)
    price = re.search(r'price: ([\d,]+) EUR', label)
    if days is None or price is None:
        raise ValueError('Unreadable packaging attributes: ' + label)
    return [bio, degradable, float(days.group(1)), float(price.group(1).replace(',', '.'))]
