"""Offline four-condition request construction. No transport or participant linkage."""
import hashlib
import json
from pathlib import Path
from probabilities import validate_questions, parse_probabilities

ARMS = ('matraix', 'basic', 'own', 'other')
MODELS = {'qwen': 'Qwen/Qwen3.8-27B', 'pro': 'deepseek-v4-pro'}
NATIVE = Path(__file__).resolve().parents[1] / 'data/native'

def facts_text(values, approved_fields):
    if not isinstance(values, dict) or set(values) != set(approved_fields):
        raise ValueError('Facts must exactly match frozen whitelist, including unknowns')
    lines=[]
    for key, label in approved_fields.items():
        val=values[key]
        if val is not None and (not isinstance(val,str) or not val.strip()):
            raise ValueError('Facts must be original decoded labels or unknown')
        lines.append(f'- {label}: {val if val is not None else "Unknown"}')
    return '\n'.join(lines)

def build(payload, arm, model, basic_fields, extra_fields, max_tokens):
    """payload already stripped by adapter; donor/answer/weight/ID stay outside."""
    if arm not in ARMS or model not in MODELS:
        raise ValueError('Unapproved arm or model')
    if type(max_tokens) is not int or max_tokens <= 0:
        raise ValueError('Freeze a positive output limit')
    common={'title','context','questions'}
    expected=common | ({'persona_text'} if arm=='matraix' else {'basic'} | ({'extra'} if arm!='basic' else set()))
    if not isinstance(payload,dict) or set(payload)!=expected:
        raise ValueError('Unexpected payload field or missing required data')
    validate_questions(payload['questions'])
    if any(not isinstance(payload[k],str) or not payload[k].strip() for k in ['title','context']):
        raise ValueError('Missing original title/context')
    if arm=='matraix':
        system=payload['persona_text']
        if not isinstance(system,str) or not system.strip():raise ValueError('Missing frozen native persona')
    else:
        system='## Respondent background\n'+facts_text(payload['basic'],basic_fields)
        if arm!='basic':system+='\n\n## Additional measured information\n'+facts_text(payload['extra'],extra_fields)
    source=json.loads((NATIVE/'provenance.json').read_text())
    task=(NATIVE/'task.txt').read_text()
    if hashlib.sha256(task.encode()).hexdigest()!=source['task_sha256']:
        raise ValueError('Frozen task template changed')
    task=task.replace('__SURVEY_TITLE__',payload['title']).strip()
    # Native question rendering layout, limited to required single choice tasks.
    lines=[f'# {payload["title"]}', '', 'Use exact `questionId` and valid choice ids.', '']
    for q in payload['questions']:
        lines += [f'## {q["id"]}', '', f'Prompt: {q["prompt"]}', '', '- Type: `single_choice`', '- Required: `true`', '', '| choice_id | label |', '|-----------|-------|']
        lines += [f'| `{k}` | {v} |' for k,v in q['options'].items()]
        lines += ['']
    schema='Return JSON with only answers: a list of objects with questionId and probabilities. probabilities is an object keyed by every exact choice id. All probabilities must be finite numbers from 0 to 1 and sum to 1 for each question. No rationale, confidence, or explanations.'
    user=f'## Task instruction\n\n{task}\n\n## Context\n\n{payload["context"]}\n\n## Questionnaire\n\n'+ '\n'.join(lines).strip() + '\n\n## Answer envelope\n\n'+schema
    body={'model':MODELS[model],'temperature':.7,'top_p':1,'max_tokens':max_tokens,'response_format':{'type':'json_object'},'messages':[{'role':'system','content':system},{'role':'user','content':user}]}
    if model=='qwen':body['chat_template_kwargs']={'enable_thinking':False}
    else:body['thinking']={'type':'disabled'}
    return body

def parse(raw, questions, model, expected_identity=None):
    validate_questions(questions)
    identity={'model':raw.get('model'),'system_fingerprint':raw.get('system_fingerprint')}
    if identity['model']!=MODELS[model] or expected_identity is not None and identity!=expected_identity:
        raise ValueError('Model identity changed')
    if len(raw['choices'])!=1:raise ValueError('Unexpected completion count')
    choice=raw['choices'][0];msg=choice['message']
    if choice['finish_reason']!='stop' or msg.get('reasoning_content') or msg.get('tool_calls'):
        raise ValueError('Truncated, thinking or tool response')
    data=json.loads(msg['content'])
    if not isinstance(data,dict) or set(data)!={'answers'} or not isinstance(data['answers'],list):
        raise ValueError('Invalid answer envelope')
    expected={q['id']:list(q['options']) for q in questions};out={};normalized=0
    for row in data['answers']:
        if not isinstance(row,dict) or set(row)!={'questionId','probabilities'}:raise ValueError('Unexpected answer field')
        q=row['questionId']
        if q not in expected or q in out:raise ValueError('Unknown or duplicate answer')
        out[q], flag=parse_probabilities(row['probabilities'],expected[q]);normalized+=flag
    if set(out)!=set(expected):raise ValueError('Missing question; no default fill')
    return {'probabilities':out,'identity':identity,'renormalised':normalized,'usage':raw.get('usage',{})}
