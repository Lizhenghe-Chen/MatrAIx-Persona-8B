import tempfile,unittest
from pathlib import Path
from .runner import run,GATES
from .core import digest

class RunnerTests(unittest.TestCase):
    def fixtures(self):
        rows=[{'person':str(i),'task':'q','stratum':'s','question':'Synthetic?','options':['A','B'],'answer':0,'context':'Synthetic','background':{}} for i in range(2)]
        study={'rows':rows,'audit':dict.fromkeys(GATES,True)}
        config={'model':'deepseek-v4-pro','temperature':.7,'top_p':1,'max_tokens':64,'status':'frozen','expected_identity':{'model':'deepseek-v4-pro','system_fingerprint':None},'background_fields':[],'max_calls':2,'max_cost_usd':1,'input_usd_per_million':1.32,'output_usd_per_million':3.96,'endpoint':'test'}
        seal={'input_sha256':digest(study),'config_sha256':digest(config),'assignments':{'0':'test','1':'test'}}
        return study,seal,config
    def test_resume_does_not_recall(self):
        s,f,c=self.fixtures();calls=[]
        def transport(body,endpoint):
            calls.append(body)
            return {'model':'deepseek-v4-pro','choices':[{'finish_reason':'stop','message':{'content':'{"probabilities":[0.5,0.5]}'}}]}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'calls.sqlite'
            self.assertTrue(run(s,f,c,p,'test',transport)['complete'])
            self.assertTrue(run(s,f,c,p,'test',transport)['complete'])
            self.assertEqual(len(calls),2)
    def test_gate_and_freeze(self):
        s,f,c=self.fixtures();s['audit']['license_cloud_use']=False
        with self.assertRaises(ValueError):run(s,f,c,'unused.sqlite','test')
    def test_budget_stops_before_call(self):
        s,f,c=self.fixtures();c['max_cost_usd']=.0000001;f['config_sha256']=digest(c)
        with tempfile.TemporaryDirectory() as d:
            result=run(s,f,c,Path(d)/'calls.sqlite','test',lambda *a:self.fail('Must not call'))
            self.assertFalse(result['complete']);self.assertEqual(result['states'],{})
    def test_operational_deadline_stops_without_new_call(self):
        import json,time
        s,f,c=self.fixtures()
        with tempfile.TemporaryDirectory() as d:
            Path(d,'run-control.json').write_text(json.dumps({'stop_starting_calls_at_epoch':time.time()-1}))
            result=run(s,f,c,Path(d)/'calls.sqlite','test',lambda *a:self.fail('Must not call after deadline'))
            self.assertEqual(result['states'],{})
            self.assertEqual(result['stop_reason'],'deadline')
    def test_generated_population_needs_no_fake_answer(self):
        s,f,c=self.fixtures();s.update(evaluation_mode='synthetic_population',person_source='generated')
        for r in s['rows']:r.pop('answer')
        f['input_sha256']=digest(s)
        def transport(body,endpoint):
            return {'model':'deepseek-v4-pro','choices':[{'finish_reason':'stop','message':{'content':'{"probabilities":[0.5,0.5]}'}}]}
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(run(s,f,c,Path(d)/'calls.sqlite','test',transport)['complete'])
