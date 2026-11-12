import unittest,json,copy
from .protocol import build_body,parse,ARMS
from .matching import constraints,compatible
class Contract(unittest.TestCase):
 def setUp(self):
  self.inst={'id':'technical','title':'Technical','questions':[{'id':'q1','prompt':'Choose one','required':True,'type':'single_choice','options':[{'id':'a','label':'A'},{'id':'b','label':'B'}]}]}
  self.profile={'age_bracket':'25-34','region':'North America','highest_education':"Bachelor's"}
 def response(self,a):return {'model':'deepseek-v4-pro','choices':[{'finish_reason':'stop','message':{'content':json.dumps({'answers':a})}}]}
 def test_same_profile_and_options(self):
  bodies=[build_body(self.profile,self.inst,'United States.',a) for a in ARMS]
  self.assertEqual(len({b['messages'][0]['content'] for b in bodies}),1)
  for b in bodies:self.assertIn('| `a` | A |',b['messages'][1]['content'])
 def test_missing_never_defaults(self):
  with self.assertRaises(ValueError):parse(self.response([]),self.inst,'original')
 def test_invalid_never_defaults(self):
  with self.assertRaises(ValueError):parse(self.response([{'questionId':'q1','value':'unknown'}]),self.inst,'original')
 def test_probability_keys_no_reordering(self):
  result=parse(self.response([{'questionId':'q1','probabilities':{'b':.8,'a':.2}}]),self.inst,'optimized')
  self.assertEqual(result['probabilities']['q1'],[.2,.8])
 def test_invalid_sum_no_normalizing(self):
  with self.assertRaises(ValueError):parse(self.response([{'questionId':'q1','probabilities':{'a':.8,'b':.8}}]),self.inst,'optimized')
 def test_answer_field_rejected(self):
  self.inst['questions'][0]['answer']='a'
  with self.assertRaises(ValueError):build_body(self.profile,self.inst,'USA','original')
 def test_matching_ignores_answers(self):
  r={'study':'pew168','background':{'Age':'30–49','Education':"Bachelor's degree"},'truth':{'q1':'a'}}
  a=constraints(r);r['truth']={'q1':'b'};self.assertEqual(a,constraints(r))
  self.assertEqual(a[0]['age_resolution'],'18_64_common_coarsening')
 def test_source_quarantine(self):
  r={'study':'anes','background':{'Age':'30','Education':"Bachelor's degree"}}
  rule,_=constraints(r)
  self.assertFalse(compatible({'source':'gss','fields':self.profile},rule))
 def test_country_codes_preserve_coverage(self):
  for country in ['CAN','IRE']:
   rule,error=constraints({'study':'dryer','country':country,'background':{'Age':'25-34','Education':"Bachelor's degree"}})
   self.assertIsNone(error)
   self.assertIn(rule['allowed']['region'][0],['North America','Western Europe'])
 def test_persona_free_text_rejected(self):
  with self.assertRaises(ValueError):build_body({**self.profile,'grounding':'private text'},self.inst,'USA','original')
  with self.assertRaises(ValueError):build_body({**self.profile,'region':'private text'},self.inst,'USA','original')
 def test_unknown_education_not_imputed(self):
  self.assertIsNone(constraints({'study':'swiss','background':{'age_years':30,'education':'Other'}})[0])
if __name__=='__main__':unittest.main()


class Scoring(unittest.TestCase):
 def _case(self,person,truth,weight=1.0,stratum='S',options=None):
  question={'id':'q1','prompt':'Choose','required':True,'type':'single_choice',
            'options':options or [{'id':'a','label':'A'},{'id':'b','label':'B'}]}
  good={'a':[.9,.1],'b':[.1,.9]}[truth]
  return {'study':'x','person':person,'stratum':stratum,'weight':weight,'truth':{'q1':truth},
          'questions':[question],'predictions':{'good':{'q1':good}}}

 def test_person_brier_matches_hand_calculation(self):
  from .scoring import person_brier
  case=self._case('p','a')
  self.assertAlmostEqual(person_brier(case,lambda q,c: case['predictions']['good']['q1']),0.02)

 def test_paired_interval_is_zero_for_identical_predictions(self):
  from .scoring import paired_interval
  rows=[{'person':f'p{i}','stratum':'S','weight':1.0,'left':0.2,'right':0.2} for i in range(5)]
  result=paired_interval(rows,repeats=50)
  self.assertEqual(result['improvement'],0)
  self.assertEqual(result['improvement_95_ci'],[0,0])

 def test_card_key_separates_national_versions(self):
  from .scoring import card_key
  a=card_key({'id':'25','options':[{'id':'1','label':'CAD 1200'},{'id':'2','label':'Neither'}]})
  b=card_key({'id':'25','options':[{'id':'1','label':'USD 900'},{'id':'2','label':'Neither'}]})
  self.assertNotEqual(a,b)

 def test_history_reference_uses_only_supplied_rows(self):
  from .scoring import build_references, reference_vector
  question={'id':'q1','options':[{'id':'a','label':'A'},{'id':'b','label':'B'}]}
  cases=[{'person':'evaluated','stratum':'S','questions':[question]}]
  source=[{'person':'other1','stratum':'S','weight':1.0,'truth':{'q1':'a'},'questions':[question]},
          {'person':'other2','stratum':'S','weight':1.0,'truth':{'q1':'b'},'questions':[question]}]
  refs=build_references(cases,source)
  self.assertEqual(reference_vector(refs,'history',question,'S'),[0.5,0.5])

 def test_refusal_options_detected_from_labels(self):
  from .scoring import refusal_ids
  questions=[{'id':'q','options':[{'id':'1','label':'Yes'},{'id':'9','label':'Neither'}]}]
  self.assertEqual(refusal_ids(questions),{'q':['9']})

 def test_gate_requires_relative_two_percent_and_positive_interval(self):
  from .scoring import passes_brier_gate
  self.assertTrue(passes_brier_gate({'reference':1.0,'relative_improvement':0.05,'improvement_95_ci':[0.01,0.09]}))
  self.assertFalse(passes_brier_gate({'reference':1.0,'relative_improvement':0.01,'improvement_95_ci':[0.001,0.02]}))
  self.assertFalse(passes_brier_gate({'reference':1.0,'relative_improvement':0.05,'improvement_95_ci':[-0.01,0.09]}))


class CardInterval(unittest.TestCase):
 def test_identical_predictions_give_zero(self):
  from .scoring import card_interval
  question={'id':'q','options':[{'id':'a','label':'A'},{'id':'b','label':'B'}]}
  cases=[{'person':f'p{i}','stratum':'S','weight':1.0,'truth':{'q':'a' if i%2 else 'b'},
          'questions':[question],'predictions':{'x':{'q':[.5,.5]}}} for i in range(25)]
  vector=lambda q,c: c['predictions']['x']['q']
  result=card_interval(cases,vector,vector,repeats=50)
  self.assertEqual(result['improvement_pp'],0)
  self.assertEqual(result['improvement_95_ci'],[0,0])
  self.assertFalse(result['passes_2pp_gate'])

 def test_sparse_cards_are_not_estimable(self):
  from .scoring import card_interval
  question={'id':'q','options':[{'id':'a','label':'A'},{'id':'b','label':'B'}]}
  cases=[{'person':f'p{i}','stratum':'S','weight':1.0,'truth':{'q':'a'},
          'questions':[question],'predictions':{'x':{'q':[.9,.1]}}} for i in range(5)]
  vector=lambda q,c: c['predictions']['x']['q']
  self.assertFalse(card_interval(cases,vector,vector,repeats=20).get('available',False))


class FormalReport(unittest.TestCase):
 def _data(self,supports):
  arm=lambda b: {'people':10,'brier':b,'accuracy':0.5,'card_tv_pp':20.0,'cards':4,
                 'mean_people_per_card':10,'refusal':{},'available':True,'question_coverage':1.0}
  contrast=lambda ref,cand,low,high,gate: {'reference':ref,'candidate':cand,'improvement':ref-cand,
   'relative_improvement':(ref-cand)/ref,'improvement_95_ci':[low,high],'passes_brier_gate':gate,'people':10}
  studies={}
  for study in ['anes','pew168','shed','pew13','dryer','swiss']:
   b=contrast(1.0,0.8,0.1,0.3,supports); h=contrast(1.0,1.1,-0.3,-0.1,False)
   studies[study]={'people':10,'cards':4,'cards_with_at_least_20_people':4,'results':{
     'arms':{a:arm(1.0 if a=='original' else 0.9) for a in
             ['original','output_only','prompt_only','optimized','history','stratum_history','uniform']},
     'contrasts':{'original__to__optimized':b,'history__to__optimized':h,
                  'stratum_history__to__optimized':h},
     'card_contrasts':{'original__to__optimized':{'available':True,
       'improvement_pp':3.0 if supports else 1.0,
       'improvement_95_ci':[1.0,5.0] if supports else [-1.0,3.0],'passes_2pp_gate':supports}},
     'refusal_options':{}}}
  return {'status':'complete_formal_cross_study','execution':{'states':{'complete':40},'missing_calls':0},
   'budget':{'max_calls':40,'reserved_peak_usd':1.0,'max_cost_usd':2.0},'studies':studies}

 def test_all_supporting_meets_cross_study_gate(self):
  from .formal_report import summarize
  s=summarize(self._data(True))
  self.assertEqual(len(s['supporting']),6)
  self.assertTrue(s['cross_study_gate'])
  self.assertFalse(s['beats_statistics'])

 def test_no_support_fails_gate(self):
  from .formal_report import summarize
  s=summarize(self._data(False))
  self.assertEqual(s['supporting'],[])
  self.assertFalse(s['cross_study_gate'])

 def test_incomplete_results_are_refused(self):
  from .formal_report import summarize
  data=self._data(True);data['status']='preflight'
  with self.assertRaises(ValueError):summarize(data)

 def test_unavailable_comparators_do_not_crash(self):
  from .formal_report import summarize,render
  data=self._data(True)
  for study in data['studies'].values():
   study['results']['contrasts']['stratum_history__to__optimized']={'available':False}
   study['results']['contrasts']['history__to__optimized']={'available':False}
   study['results']['card_contrasts']['original__to__optimized']={'available':False}
  s=summarize(data)
  self.assertEqual(s['supporting'],[])
  self.assertIn('不可估计',render(s))


class AdmissionGate(unittest.TestCase):
 def _decl(self, gate_status='passed', evidence='x', reference_excludes=True, minimum=20,
           exclusions=None, declared='admitted'):
  gates={g:{'status':gate_status,'evidence':evidence} for g in
         ['license_cloud_use','question_mapping','background_timing','author_statistics','leakage_review']}
  return {'gates':list(gates),'reference_kinds':['history','stratum_history','attribute_logit'],
   'minimum_people_per_card':20,
   'studies':[{'id':'s1','name':'S1','evidence_tier':'historical','status':declared,'gates':gates,
     'reference':{'kind':'history','fits_on':None,'excludes_evaluated':reference_excludes},
     'distribution':{'minimum_people_per_card':minimum,'estimable':True,'reason':'r'},
     'exclusions':[] if exclusions is None else exclusions}]}

 def test_complete_declaration_is_admitted(self):
  from .admission_check import evaluate
  result=evaluate(self._decl())
  self.assertEqual(result['admitted'],['s1'])
  self.assertEqual(result['misdeclared'],[])

 def test_missing_gate_evidence_blocks_admission(self):
  from .admission_check import evaluate
  for kwargs in [{'gate_status':'not_recorded'},{'evidence':None}]:
   result=evaluate(self._decl(**kwargs))
   self.assertEqual(result['admitted'],[])
   self.assertIn('misdeclared',str(result) if result['misdeclared'] else 'misdeclared')

 def test_reference_must_exclude_evaluated(self):
  from .admission_check import evaluate
  result=evaluate(self._decl(reference_excludes=False))
  self.assertEqual(result['admitted'],[])

 def test_card_rule_below_twenty_blocks_admission(self):
  from .admission_check import evaluate
  result=evaluate(self._decl(minimum=5))
  self.assertEqual(result['admitted'],[])

 def test_exclusions_must_be_a_list(self):
  from .admission_check import evaluate
  result=evaluate(self._decl(exclusions={'a':1}))
  self.assertEqual(result['admitted'],[])

 def test_require_reports_the_missing_studies(self):
  from .admission_check import evaluate, require
  result=evaluate(self._decl(gate_status='pending'))
  with self.assertRaises(ValueError):require(result,['s1'])


class RecommendedConfig(unittest.TestCase):
 def test_reference_preference_prefers_stratum_then_history_then_logit(self):
  from .recommended import choose_reference
  self.assertEqual(choose_reference({'history':True,'stratum_history':True,'attribute_logit':True}),'stratum_history')
  self.assertEqual(choose_reference({'history':True,'attribute_logit':True}),'history')
  self.assertEqual(choose_reference({'attribute_logit':True}),'attribute_logit')
  self.assertIsNone(choose_reference({}))

 def test_missing_reference_is_refused(self):
  from .recommended import required_comparators
  with self.assertRaises(ValueError):required_comparators({'history':False})

 def test_claim_levels(self):
  from .recommended import claim
  improve={'relative_improvement':0.05,'improvement_95_ci':[0.01,0.09]}
  weak={'relative_improvement':0.01,'improvement_95_ci':[0.001,0.02]}
  regress={'relative_improvement':-0.1,'improvement_95_ci':[-0.2,-0.05]}
  card_pass={'available':True,'improvement_pp':3.0,'improvement_95_ci':[1.0,5.0]}
  card_fail={'available':True,'improvement_pp':1.0,'improvement_95_ci':[-1.0,3.0]}
  card_missing={'available':False}
  self.assertEqual(claim(improve,card_pass),'improvement')
  self.assertEqual(claim(improve,card_fail),'direction_only')
  self.assertEqual(claim(improve,card_missing),'direction_only')
  self.assertEqual(claim(weak,card_pass),'no_evidence')
  self.assertEqual(claim(regress,card_pass),'regression')
  self.assertEqual(claim(None,card_pass),'no_reference')

 def test_config_declares_probabilities_and_limits(self):
  from .recommended import configuration
  config=configuration()
  self.assertEqual(config['output_mode'],'probabilities')
  self.assertEqual(config['prompt_variant'],'optional')
  self.assertEqual(config['gates']['minimum_people_per_card'],20)
  self.assertTrue(any('not purchase' in x for x in config['limits']))
