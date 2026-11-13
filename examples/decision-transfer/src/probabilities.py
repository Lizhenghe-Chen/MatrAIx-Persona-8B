"""Answer isolation and strict probability validation; no network or data reads."""
import math

def parse_probabilities(value, option_ids):
    if not isinstance(value, dict) or set(value) != set(option_ids):
        raise ValueError('Missing or unexpected option')
    values = [value[k] for k in option_ids]
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
        raise ValueError('Invalid probability')
    total = sum(values)
    if abs(total - 1) > 0.01 or total == 0:
        raise ValueError('Probability sum outside tolerance')
    return [v / total for v in values], abs(total - 1) > 1e-6

def validate_questions(questions):
    seen = set()
    for q in questions:
        if set(q) != {'id', 'prompt', 'options'}:
            raise ValueError('Unexpected question field: possible answer leakage')
        if not isinstance(q['id'], str) or q['id'] in seen:
            raise ValueError('Invalid or duplicate question ID')
        seen.add(q['id'])
        if not isinstance(q['prompt'], str) or not q['prompt'].strip():
            raise ValueError('Missing original question')
        if not isinstance(q['options'], dict) or len(q['options']) < 2:
            raise ValueError('Incomplete alternatives')
        if any(not isinstance(k,str) or not isinstance(v,str) or not k or not v for k,v in q['options'].items()):
            raise ValueError('Invalid option label')
    if not seen:
        raise ValueError('Empty questionnaire')
