"""OpenAI-compatible transport, separately testable from participant data."""
import json
import os
import urllib.request
from .core import probabilities


def build_request(payload, config):
    if config['model'] != 'deepseek-v4-pro':
        raise ValueError('This experiment freezes DeepSeek Pro')
    return {'model': config['model'], 'temperature': config['temperature'],
            'top_p': config['top_p'], 'max_tokens': config['max_tokens'],
            'thinking': {'type': 'disabled'}, 'response_format': {'type':'json_object'},
            'messages': [
                {'role':'system','content':
                 'Predict this respondent\'s choice in the supplied context using only the provided background. '
                 'Do not invent personal experiences. Return JSON with only a probabilities array, in the supplied '
                 'option order. Nonnegative probabilities must sum to 1. Do not include explanations.'},
                {'role':'user','content':json.dumps(payload,ensure_ascii=False)}]}


def parse_response(response, option_count, expected_identity=None):
    identity = {'model':response.get('model'), 'system_fingerprint':response.get('system_fingerprint')}
    if not identity['model']:
        raise ValueError('Server omitted model identity')
    if expected_identity is not None and identity != expected_identity:
        raise ValueError('Server identity changed; stop and investigate')
    choice=response['choices'][0]
    msg=choice['message']
    if choice['finish_reason'] != 'stop' or msg.get('reasoning_content') or msg.get('tool_calls'):
        raise ValueError('Unexpected truncated, thinking or tool response')
    result=json.loads(msg['content'])
    if set(result) != {'probabilities'}:
        raise ValueError('Unexpected response fields')
    return {'probabilities':probabilities(result['probabilities'],option_count),
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
