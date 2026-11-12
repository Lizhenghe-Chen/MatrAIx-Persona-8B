"""Spanish hanging-tomato study: attribute features for the conditional-logit fallback.

The study has only 32 distinct cards, all answered by at least 20 people, so the
historical-share reference is the primary comparator; this parser exists so the same
attribute model can be fitted when a card-level share is missing.
"""
import re

NUMERIC = {'cost': r'cost: ([\d.]+) EUR/kg'}
CATEGORICAL = ('variety', 'cultural value', 'access', 'label', 'place of production')
LEVELS = {
    'variety': ['Underutilised variety', 'Commercial variety'],
    'cultural value': ['Without cultural value', 'With cultural value'],
    'access': ['Short food supply chain', 'Speciality food shop', 'Supermarket'],
    'label': ['Without label', 'With label'],
    'place of production': ['Locally (your province)', 'Elsewhere in Spain', 'Outside Spain'],
}


def attributes(label):
    """Opt-out scores zero everywhere; otherwise numeric cost plus dummy-coded attributes."""
    if label.startswith('Neither'):
        return [0.0] * (1 + sum(len(v) - 1 for v in LEVELS.values()))
    vector = []
    for key in CATEGORICAL:
        match = re.search(re.escape(key) + r': ([^,]+)', label)
        if match is None:
            raise ValueError('Missing attribute: ' + key)
        value = match.group(1).strip()
        if value not in LEVELS[key]:
            raise ValueError(f'Unknown level for {key}: {value}')
        vector.extend(1.0 if value == level else 0.0 for level in LEVELS[key][1:])
    cost = re.search(NUMERIC['cost'], label)
    if cost is None:
        raise ValueError('Missing cost: ' + label)
    vector.append(float(cost.group(1)))
    return vector
