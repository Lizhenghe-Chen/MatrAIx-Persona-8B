"""Same-information reference for the 1-7 rating study.

Every shoe card in this study is shown to about one respondent, so "what did
other people answer to this exact card" does not exist. The only reference whose
inputs the AI arm also has is a model of the ten displayed attributes, fitted on
respondents outside the evaluated cohort. Parsing goes through the rendered
prompt, so training rows and evaluated cases use exactly the same text.
"""
import re

NUMERIC = {'ave customer review': r'([\d.]+)', 'best seller': r'#(\d+)',
           'model year': r'(\d{4})', 'price': r'\$([\d,]+)', 'weight': r'([\d.]+)'}
CATEGORICAL = ('brand', 'color', 'eco friendly materials', 'gel cushioning', 'shipping')
PREFIX = 'Rate this shoe: '


def attributes(prompt):
    """Raw attribute values from the rendered question, in display order."""
    text = prompt[len(PREFIX):] if prompt.startswith(PREFIX) else prompt
    found = {}
    for part in text.split(', '):
        key, _, value = part.partition(': ')
        if value:
            found[key.strip()] = value.strip()
    missing = [key for key in list(NUMERIC) + list(CATEGORICAL) if key not in found]
    if missing:
        raise ValueError(f'Missing displayed attributes: {missing}')
    return found


def vocabulary(prompts):
    values = {key: set() for key in CATEGORICAL}
    for prompt in prompts:
        found = attributes(prompt)
        for key in CATEGORICAL:
            values[key].add(found[key])
    return {key: sorted(items) for key, items in values.items()}


def encode(found, levels):
    vector = []
    for key, pattern in NUMERIC.items():
        match = re.search(pattern, found[key])
        if match is None:
            raise ValueError(f'Unreadable numeric attribute: {key}={found[key]!r}')
        vector.append(float(match.group(1).replace(',', '')))
    for key in CATEGORICAL:
        if found[key] not in levels[key]:
            raise ValueError(f'Unseen category for {key}: {found[key]!r}')
        vector.extend(1.0 if found[key] == level else 0.0 for level in levels[key][1:])
    return vector


def build(cases, history_rows, scale=tuple(range(1, 8))):
    """Return ({person: {question id: probability vector}}, note) for the rating model."""
    from ..core.baselines import RatingAttributeBaseline

    prompts = [q['prompt'] for row in history_rows for q in row['questions']]
    if not prompts:
        return None, 'no historical prompts to fit on'
    levels = vocabulary(prompts)
    training = [{'person': row['person'], 'features': encode(attributes(q['prompt']), levels),
                 'answer': int(row['truth'][str(q['id'])])}
                for row in history_rows for q in row['questions']
                if str(q['id']) in row['truth']]
    if not training:
        return None, 'no historical ratings to fit on'
    model = RatingAttributeBaseline(scale).fit(training)
    table, skipped = {}, 0
    for case in cases:
        vectors = {}
        for question in case['questions']:
            try:
                vector = model.predict([{'features': encode(attributes(question['prompt']), levels)}])[0]
            except ValueError:
                skipped += 1
                continue
            vectors[str(question['id'])] = vector
        table[case['person']] = vectors
    if skipped:
        note = f'attribute rating model on {len(training)} historical ratings; {skipped} cases unencodable'
    else:
        note = f'attribute rating model on {len(training)} historical ratings; {len(levels)} categorical fields'
    return table, note
