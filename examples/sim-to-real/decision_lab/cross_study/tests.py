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
