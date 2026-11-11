"""Offline synthetic fixture: complete flow, never sent to a model provider."""
import unittest,tempfile,json
from unittest.mock import patch
from pathlib import Path
from ..core import digest,split
from ..runner import run,GATES
from ..dryer_baseline import develop
from ..calibrate_study import calibrate
from ..evaluate_study import evaluate
from ..study_report import render

class PipelineTests(unittest.TestCase):
    def test_frozen_calibration_to_report(self):
        option=lambda price,stars:f'Price: USD {price}; Capacity: 5; Customer rating: {stars}; Brand: Established; Energy Star: Yes'
        rows=[dict(person=f'p{i:02}',task='q',stratum='USA_C',question='Choose a dryer',context='Artificial software test',options=[option(500,3),option(700,5),'Neither'],answer=i%3,group='same-card',background={'age_band':'25-34','education':'High school','weekly_dryer_use':float(i%4),'household_size':float(i%3+1)}) for i in range(30)]
        prepared={'rows':rows};assignment=split(rows)
        fields={'none':[],'basic':['age_band','education'],'rich':['age_band','education','weekly_dryer_use','household_size']}
        config={'model':'deepseek-v4-pro','temperature':.7,'top_p':1,'max_tokens':64,'status':'frozen','expected_identity':{'model':'deepseek-v4-pro','system_fingerprint':None},'max_calls':30,'max_cost_usd':10,'input_usd_per_million':1.32,'output_usd_per_million':3.96,'endpoint':'offline-test'}
        def transport(body,endpoint):
            content='{"choice":0}' if 'choice integer' in body['messages'][0]['content'] else '{"probabilities":[0.5,0.3,0.2]}'
            return {'model':'deepseek-v4-pro','choices':[{'finish_reason':'stop','message':{'content':content}}]}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);formal=root/'formal-v1';formal.mkdir()
            write=lambda p,d:p.write_text(json.dumps(d))
            write(root/'prepared.json',prepared)
            write(root/'baseline-development.json',develop(root/'prepared.json'))
            protocol={'backgrounds':fields,'calibrated':{'temperature_grid':[1,2],'llm_weight_grid':[0,.5,1]}}
            write(formal/'protocol.json',protocol)
            for name,arm,phase in [('rich_development','rich','development'),('none_test','none','test'),('basic_test','basic','test'),('rich_test','rich','test'),('shuffled_test','rich','test'),('single_test','rich','test')]:
                study={'rows':rows,'audit':dict.fromkeys(GATES,True)}
                cfg={**config,'background_fields':fields[arm],'output_mode':'single_choice' if name=='single_test' else 'probabilities'}
                seal={'input_sha256':digest(study),'config_sha256':digest(cfg),'assignments':assignment}
                for suffix,obj in [('study',study),('config',cfg),('seal',seal)]:write(formal/(name+'-'+suffix+'.json'),obj)
                self.assertTrue(run(study,seal,cfg,formal/(name+'.sqlite'),phase,transport)['complete'])
            selection=calibrate(root,'dryer');write(root/'calibration.json',selection)
            # Matching identifiers alone must not allow a different answer key.
            from ..checkpoint import read_predictions
            def altered_content(*args,**kwargs):
                observed,predictions,missing=read_predictions(*args,**kwargs)
                observed[0]={**observed[0],'answer':(observed[0]['answer']+1)%3}
                return observed,predictions,missing
            with patch('decision_lab.calibrate_study.read_predictions',side_effect=altered_content):
                with self.assertRaisesRegex(ValueError,'Development content differs'):
                    calibrate(root,'dryer')
            result=evaluate(root,'dryer',root/'calibration.json')
            self.assertEqual(result['methods']['rich']['people'],6)
            self.assertEqual(result['shuffle_changed_content_diagnostic']['changed_people'],0)
            self.assertEqual(result['comparisons']['basic__to__rich']['improvement_95_ci'],[0,0])
            page=render(result);self.assertIn('每个商品组合',page);self.assertIn('真人',page)
            selection['selection']['llm_weight']=.123;write(root/'calibration.json',selection)
            with self.assertRaises(ValueError):evaluate(root,'dryer',root/'calibration.json')
