"""Shared arm semantics and strict survey-block response validation."""
import json,math,sys
from pathlib import Path
from .registry import ROOT
REPO=ROOT.parents[2]
for p in ['src','application/playground','packages/playground/src']:
 if str(REPO/p) not in sys.path:sys.path.insert(0,str(REPO/p))
from backend.service.survey_types import SurveyInstrument
from backend.service.survey_instruction_builder import render_survey_task_instruction_markdown,render_survey_questionnaire_markdown,render_survey_output_schema_markdown
from matraix.persona_dimension_catalog import build_template_context_extras
from jinja2 import Environment,FileSystemLoader,StrictUndefined
ARMS={'original':('native','choice'),'output_only':('native','probabilities'),'prompt_only':('predict','choice'),'optimized':('predict','probabilities'),'anchored':('predict','probabilities'),'bounded':('predict','probabilities')}
ANCHOR_BOUND=15.0
# Exact 1e-6 was too strict for free-form decimals: the anchored arms produced 15%
# unusable answers whose only fault was a rounding drift. Drift up to 1% is
# renormalised and counted; anything larger is still a failure, never a guess.
PROBABILITY_TOLERANCE=1e-2
ANCHOR_RULE={'anchored':'Treat these shares as the starting point, then adjust them using only the profile.',
             'bounded':('Treat these shares as the starting point, then adjust them using only the profile. '
                        'No single choice may move more than 15 percentage points away from its reference share; '
                        'renormalise so the probabilities still sum to 1.')}
PREDICT='Predict the choices the respondent represented by the provided profile would make in the stated survey context. Use only supplied information; do not invent missing personal experiences. Answer every required question.'

def persona_text(dimensions):
 if not isinstance(dimensions,dict) or not dimensions:raise ValueError('Missing approved persona dimensions')
 # The caller must supply only audited categorical schema values, never metadata/grounding/free text.
 schema=json.loads((REPO/'persona/schema/dimensions.json').read_text())
 allowed={d['id']:d['values'] for d in schema['dimensions']}
 for key,value in dimensions.items():
  if key not in allowed or not isinstance(value,str) or value not in allowed[key]:
   raise ValueError('Unapproved persona field or value: '+str(key))
 env=Environment(loader=FileSystemLoader(REPO/'environment/agents/matraix/agents/persona/templates'),undefined=StrictUndefined,trim_blocks=True,lstrip_blocks=True)
 context=dict(dimensions=dimensions,display_name='',demographics={},psychology={},communication={},preferences={},behavior={},summary='',system_prompt='')
 text=env.get_template('persona_system.md.j2').render(**context,**build_template_context_extras(dimensions)).strip()
 if not text or text=='## Who you are':raise ValueError('Native renderer produced no profile')
 return text

def anchor_text(anchors):
 if not anchors:raise ValueError('Anchored arms need a reference share for every question')
 lines=['## Reference shares from comparable respondents','',
        'These shares come from respondents outside the evaluated cohort who match the same age and education band.']
 for question_id,rows in anchors.items():
  lines.append('')
  lines.append('- '+question_id)
  for option_id,label,share in rows:
   lines.append(f'  - {option_id} ({label}): {share*100:.1f}%')
 return '\n'.join(lines)

def build_body(profile,instrument,context,arm,max_tokens=4096,anchors=None):
 if arm not in ARMS:raise ValueError('Unknown arm')
 if not isinstance(context,str):raise ValueError('Context must be explicitly reviewed text')
 if set(instrument)-{'id','title','description','questions'}:raise ValueError('Unexpected instrument metadata')
 for q in instrument['questions']:
  if set(q)-{'id','prompt','type','required','options'}:raise ValueError('Unexpected question field, including possible answer')
  if q['type']!='single_choice' or not q.get('required',False):raise ValueError('V1 requires explicit required categorical choices; ordinal mapping needs adapter')
  if len(q['options'])<2:raise ValueError('Missing alternatives')
 obj=SurveyInstrument.from_dict(instrument);prompt,mode=ARMS[arm]
 instruction=render_survey_task_instruction_markdown(obj).strip() if prompt=='native' else PREDICT
 questionnaire=render_survey_questionnaire_markdown(obj).strip()
 if mode=='probabilities':
  instruction=instruction.replace('- Answer with the selected value only unless a question explicitly\n  asks for `askRationale` / `askConfidence`.','- Estimate a probability for every choice rather than selecting one value.')
  schema='Return JSON with only answers: a list of objects with questionId and probabilities. probabilities is an object keyed by every exact choice id. All probabilities must be finite numbers from 0 to 1 and sum to 1 for each question. No rationale, confidence, or explanations.'
 else:schema=render_survey_output_schema_markdown(obj).strip()+'\nReturn valid JSON. No rationale or confidence.'
 if arm in ANCHOR_RULE:
  reference=anchor_text(anchors)
  instruction=instruction+'\n'+ANCHOR_RULE[arm]
  body_context=f'{context}\n\n{reference}'
 else:body_context=context
 user=f'## Task instruction\n\n{instruction}\n\n## Context\n\n{body_context}\n\n## Questionnaire\n\n{questionnaire}\n\n## Answer envelope\n\n{schema}'
 return {'model':'deepseek-v4-pro','temperature':.7,'top_p':1,'max_tokens':max_tokens,'thinking':{'type':'disabled'},'response_format':{'type':'json_object'},'messages':[{'role':'system','content':persona_text(profile)},{'role':'user','content':user}]}

def parse(raw,instrument,arm,expected_identity=None):
 identity={'model':raw.get('model'),'system_fingerprint':raw.get('system_fingerprint')}
 if identity['model']!='deepseek-v4-pro':raise ValueError('model_identity_mismatch')
 if expected_identity is not None and identity!=expected_identity:raise ValueError('server_identity_changed')
 choice=raw['choices'][0];message=choice['message']
 if choice['finish_reason']!='stop' or message.get('reasoning_content') or message.get('tool_calls'):raise ValueError('unexpected_finish_reasoning_or_tools')
 data=json.loads(message['content']);allowed={'answers'} if ARMS[arm][1]=='probabilities' else {'instrument','answers'}
 if not isinstance(data,dict) or set(data)-allowed:raise ValueError('unexpected_envelope')
 expected={q['id']:[str(o['id']) if isinstance(o,dict) else str(o) for o in q['options']] for q in instrument['questions']}
 answers=data.get('answers');result={};renormalised=0
 if not isinstance(answers,list):raise ValueError('missing_answers')
 for a in answers:
  q=a.get('questionId')
  if q not in expected or q in result:raise ValueError('unknown_or_duplicate_question')
  opts=expected[q]
  if ARMS[arm][1]=='choice':
   if set(a)!={'questionId','value'} or a['value'] not in opts:raise ValueError('invalid_choice')
   result[q]=[float(o==a['value']) for o in opts]
  else:
   if set(a)!={'questionId','probabilities'} or not isinstance(a['probabilities'],dict) or set(a['probabilities'])!=set(opts):raise ValueError('invalid_probability_keys')
   v=[a['probabilities'][o] for o in opts]
   if any(type(x) not in (int,float) or not math.isfinite(x) or not 0<=x<=1 for x in v):raise ValueError('invalid_probability_values')
   total=sum(v)
   if abs(total-1)>PROBABILITY_TOLERANCE:raise ValueError('invalid_probability_values')
   if abs(total-1)>1e-6:
    v=[x/total for x in v];renormalised+=1
   result[q]=v
 if set(result)!=set(expected):raise ValueError('missing_required_answers_no_default_fill')
 return {'probabilities':result,'identity':identity,'usage':raw.get('usage',{}),'renormalised':renormalised}
