"""OpenAI-compatible transport, separately testable from participant data."""
import json
import os
import urllib.request
from .core import probabilities


class ResponseValidationError(ValueError):
    def __init__(self, code):
        self.reason_code=code
        super().__init__(code)


def build_request(payload, config):
    if config['model'] != 'deepseek-v4-pro':
        raise ValueError('This experiment freezes DeepSeek Pro')
    mode=config.get('output_mode','probabilities')
    if mode not in ('probabilities','single_choice'):
        raise ValueError('Unknown output mode')
    instruction=("Return JSON with only a probabilities array, in the supplied option order. Nonnegative probabilities must sum to 1."
                 if mode=='probabilities' else
                 "Return JSON with only a choice integer: the zero-based index of the single selected option in the supplied option order.")
    grounding = ('provided background and known choices. Known choices are separate observations; '
                 'predict the current question, not a repetition of a known answer'
                 if config.get('include_choice_history') else 'provided background')
    if config.get('known_choice_encoding') == 'selected_product_text':
        instruction = ('In each known choice, selected_option_text is the exact alternative previously chosen. ' + instruction)
    return {'model': config['model'], 'temperature': config['temperature'],
            'top_p': config['top_p'], 'max_tokens': config['max_tokens'],
            'thinking': {'type': 'disabled'}, 'response_format': {'type':'json_object'},
            'messages': [
                {'role':'system','content':
                 'Predict this respondent\'s choice in the supplied context using only the '+grounding+'. '
                 'Do not invent personal experiences. '+instruction+' Do not include explanations.'},
                {'role':'user','content':json.dumps(payload,ensure_ascii=False)}]}


def parse_response(response, option_count, expected_identity=None, output_mode="probabilities"):
    identity = {'model':response.get('model'), 'system_fingerprint':response.get('system_fingerprint')}
    if not identity['model']:
        raise ResponseValidationError('missing_model_identity')
    if expected_identity is not None and identity != expected_identity:
        raise ResponseValidationError('server_identity_changed')
    choice=response['choices'][0]
    msg=choice['message']
    if choice['finish_reason'] != 'stop' or msg.get('reasoning_content') or msg.get('tool_calls'):
        raise ResponseValidationError('unexpected_finish_reasoning_or_tools')
    try:result=json.loads(msg['content'])
    except (json.JSONDecodeError,TypeError):raise ResponseValidationError('invalid_json') from None
    if not isinstance(result,dict):raise ResponseValidationError('json_not_object')
    if output_mode == 'single_choice':
        selected=result.get('choice')
        if set(result)!={'choice'} or type(selected) is not int or not 0<=selected<option_count:
            raise ResponseValidationError('invalid_single_choice')
        values=[int(i==selected) for i in range(option_count)]
    elif output_mode == 'probabilities':
        if set(result)!={'probabilities'}:
            raise ResponseValidationError('unexpected_json_fields')
        raw=result['probabilities']
        if not isinstance(raw,list):raise ResponseValidationError('probabilities_not_array')
        try:values=probabilities(raw,option_count)
        except ValueError as exc:
            code='probabilities_sum_not_one' if str(exc)=='Probabilities must sum to one; no silent normalization' else 'invalid_probability_vector'
            raise ResponseValidationError(code) from None
    else:
        raise ValueError('Unknown output mode')
    return {'probabilities':values, 'output_mode':output_mode,
            'identity':identity,'usage':response.get('usage',{})}


def send(body, endpoint, timeout=90):
    if endpoint != 'https://api.deepseek.com/chat/completions':
        raise ValueError('Only the approved official endpoint is allowed')
    key=os.environ.get('DEEPSEEK_API_KEY')
    if not key:
        raise RuntimeError('DEEPSEEK_API_KEY is not configured')
    req=urllib.request.Request(endpoint, data=json.dumps(body).encode(),
        headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    # Do not print headers, raw request records, or response error bodies.
    with urllib.request.urlopen(req,timeout=timeout) as response:
        return json.load(response)
