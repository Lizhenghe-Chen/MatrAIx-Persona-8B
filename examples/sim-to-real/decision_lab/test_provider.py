import unittest
from .provider import build_request,parse_response

class ProviderTests(unittest.TestCase):
    def response(self):
        return {'model':'deepseek-v4-pro','choices':[{'finish_reason':'stop','message':{'content':'{"probabilities":[0.25,0.75]}'}}]}
    def test_valid(self):
        self.assertEqual(parse_response(self.response(),2)['probabilities'],[.25,.75])
    def test_drift_stops(self):
        with self.assertRaises(ValueError):parse_response(self.response(),2,{'model':'different','system_fingerprint':None})
    def test_truncation_stops(self):
        r=self.response();r['choices'][0]['finish_reason']='length'
        with self.assertRaises(ValueError):parse_response(r,2)
    def test_request_modes(self):
        c={'model':'deepseek-v4-pro','temperature':.7,'top_p':1,'max_tokens':768}
        r=build_request({'question':'Synthetic format check','options':['A','B']},c)
        self.assertNotIn('tools',r);self.assertEqual(r['thinking'],{'type':'disabled'})
    def test_single_choice_is_observed_not_probability_estimate(self):
        r=self.response();r['choices'][0]['message']['content']='{"choice":1}'
        result=parse_response(r,2,output_mode='single_choice')
        self.assertEqual(result['probabilities'],[0,1])
        self.assertEqual(result['output_mode'],'single_choice')
        for content in ['{"choice":true}','{"choice":2}','{"choice":-1}','{"choice":1.0}','{"probabilities":[0,1]}']:
            r['choices'][0]['message']['content']=content
            with self.assertRaises(ValueError):parse_response(r,2,output_mode='single_choice')
    def test_single_choice_prompt(self):
        c={'model':'deepseek-v4-pro','temperature':.7,'top_p':1,'max_tokens':768,'output_mode':'single_choice'}
        r=build_request({'options':['A','B']},c)
        self.assertIn('zero-based',r['messages'][0]['content'])
        self.assertNotIn('probabilities array',r['messages'][0]['content'])
