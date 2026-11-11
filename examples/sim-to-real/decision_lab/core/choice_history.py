"""Small, provider-independent input contract for observed choices, not targets."""
from .core import digest


def card_key(row):
    # Remove alternative display names; retain question, context and all attributes.
    options = [x.split('; ', 1)[1] if '; ' in x else x for x in row['options']]
    return digest([row['question'], row['context'], sorted(options)])


def observation(row):
    return {k: row[k] for k in ('context', 'question', 'options')} | {'selected_option': row['answer']}


def text_observation(row):
    """Unambiguous selected product text; never require the LLM to infer index origin."""
    return {k: row[k] for k in ('context', 'question', 'options')} | {'selected_option_text': row['options'][row['answer']]}


def checked_history(history, target):
    if not isinstance(history, list) or len(history) not in (0, 2):
        raise ValueError('Expected zero or exactly two known choices')
    result = []
    seen = {card_key(target)}
    for item in history:
        text_mode = 'selected_option_text' in item
        selected_key = 'selected_option_text' if text_mode else 'selected_option'
        if set(item) != {'context', 'question', 'options', selected_key}:
            raise ValueError('Unapproved history fields')
        if not isinstance(item['context'], str) or not isinstance(item['question'], str):
            raise ValueError('Invalid history text')
        opts = item['options']; selected = item[selected_key]
        if not isinstance(opts, list) or len(opts) < 2 or any(not isinstance(x, str) for x in opts):
            raise ValueError('Invalid history options')
        valid_choice = (isinstance(selected, str) and selected in opts) if text_mode else (type(selected) is int and 0 <= selected < len(opts))
        if len(set(opts)) != len(opts) or not valid_choice:
            raise ValueError('Invalid known choice')
        key = card_key(item)
        if key in seen:
            raise ValueError('Repeated known card or target card in history')
        seen.add(key)
        result.append({**item, 'options': list(opts)})
    return result
