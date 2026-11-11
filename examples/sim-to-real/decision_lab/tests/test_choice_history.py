import copy
import json
import tempfile
import unittest
import sqlite3
from pathlib import Path
from decision_lab.core.core import digest, request_payload
from decision_lab.core.choice_history import card_key, checked_history, observation, text_observation
from decision_lab.core.provider import build_request
from decision_lab.core.runner import run
from decision_lab.studies.choice_history import quotas, read, OUT

class ChoiceHistoryTests(unittest.TestCase):
    def test_selected_product_text_is_unambiguous(self):
        source={'question':'q','context':'c','options':['expensive','cheap'],'answer':1}
        item=text_observation(source)
        self.assertEqual(item['selected_option_text'],'cheap')
        self.assertNotIn('selected_option',item)
        target={**source,'options':['different expensive','different cheap'], 'background':{}}
        second=text_observation({**source,'options':['third expensive','third cheap']})
        cfg={'background_fields':[],'include_choice_history':True,'known_choice_encoding':'selected_product_text',
             'model':'deepseek-v4-pro','temperature':.7,'top_p':1,'max_tokens':768}
        payload=request_payload({**target,'known_choices':[item,second]},cfg)
        body=build_request(payload,cfg)
        self.assertIn('exact alternative previously chosen',body['messages'][0]['content'])
        with self.assertRaises(ValueError):
            request_payload({**target,'known_choices':[observation(source),second]},cfg)
        with self.assertRaises(ValueError):
            checked_history([{**item,'selected_option_text':'not offered'},second],target)

    def test_whitelist_and_target_exclusion(self):
        row={'question':'Choose','context':'US','options':['A; price: 10','B; price: 20'], 'answer':1}
        history=[observation({**row,'options':['A; price: 3','B; price: 4']}),observation({**row,'options':['A; price: 5','B; price: 6']})]
        self.assertEqual(checked_history(history,row),history)
        for field in ['person','weight','answer','name']:
            bad=copy.deepcopy(history);bad[0][field]='secret'
            with self.assertRaises(ValueError):checked_history(bad,row)
        bad=copy.deepcopy(history);bad[0]=observation({**row,'options':list(reversed(row['options']))})
        with self.assertRaises(ValueError):checked_history(bad,row)
        with self.assertRaises(ValueError):checked_history([history[0],history[0]],row)

    def test_no_target_or_identifiers_in_payload(self):
        row={'question':'Choose','context':'US','options':['a','b'],'background':{'age':30,'unapproved':'secret'},'answer':1,'person':'secret','weight':9,'known_choices':[]}
        cfg={'background_fields':['age'],'include_choice_history':True}
        payload=request_payload(row,cfg)
        self.assertNotIn('secret',json.dumps(payload))
        self.assertEqual(set(payload),{'question','context','options','background','known_choices'})

    def test_quotas(self):
        self.assertEqual(quotas({'a':10,'b':20},9),{'a':3,'b':6})
        with self.assertRaises(ValueError):quotas({'a':1},2)

    def test_resume_and_batch_stop(self):
        rows=[{'person':str(i),'task':'t','stratum':'s','question':'q','context':'c','options':['a','b'],'answer':0,'background':{}} for i in range(3)]
        study={'rows':rows,'audit':{k:True for k in ['license_cloud_use','question_mapping','background_timing','author_statistics','leakage_review']}}
        config={'background_fields':[],'model':'deepseek-v4-pro','temperature':.7,'top_p':1,'max_tokens':768,'status':'frozen','expected_identity':{'model':'deepseek-v4-pro','system_fingerprint':'x'},'endpoint':'unused','max_calls':4,'max_cost_usd':1,'input_usd_per_million':1.32,'output_usd_per_million':3.96}
        seal={'input_sha256':digest(study),'config_sha256':digest(config),'assignments':{str(i):'development' for i in range(3)}}
        calls=[]
        def fake(body,endpoint):
            calls.append(body)
            return {'model':'deepseek-v4-pro','system_fingerprint':'x','choices':[{'finish_reason':'stop','message':{'content':'{"probabilities":[0.5,0.5]}'}}]}
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'run.sqlite'
            self.assertFalse(run(study,seal,config,db,'development',transport=fake,max_new_calls=1)['complete'])
            self.assertTrue(run(study,seal,config,db,'development',transport=fake)['complete'])
            run(study,seal,config,db,'development',transport=fake)
            self.assertEqual(len(calls),3)

    def test_archived_attempts_count_toward_cap(self):
        from .test_runner import RunnerTests
        study,seal,config=RunnerTests().fixtures()
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'run.sqlite'
            # Two archived attempts exhaust max_calls=2 before any new request.
            with sqlite3.connect(db) as conn:
                conn.execute('create table failed_attempts (job text)')
                conn.executemany('insert into failed_attempts values (?)',[('a',),('b',)])
            result=run(study,seal,config,db,'test',transport=lambda *args:self.fail('Cap must block transport'))
            self.assertFalse(result['complete'])
            self.assertEqual(result['states'],{})

    def test_frozen_experiment(self):
        if not (OUT/'experiment-seal.json').exists():self.skipTest('Private freeze unavailable')
        study=read(OUT/'experiment-study.json');config=read(OUT/'experiment-config.json');seal=read(OUT/'experiment-seal.json')
        self.assertEqual(digest(study),seal['input_sha256']);self.assertEqual(digest(config),seal['config_sha256'])
        self.assertEqual(len(study['rows']),24+12*read(OUT/'protocol.json')['calls']['people_per_study'])
        stages={s:{r['person'] for r in study['rows'] if r['stage']==s} for s in ['pilot','evaluation']}
        self.assertFalse(stages['pilot']&stages['evaluation'])
        grouped={}
        for r in study['rows']:
            p=request_payload(r,config);checked_history(p['known_choices'],r)
            self.assertEqual(len(p['known_choices']),0 if r['arm']=='background' else 2)
            grouped.setdefault((r['person'],r['target_task']),[]).append(r)
        for group in grouped.values():
            self.assertEqual({r['arm'] for r in group},{'background','own','other'})
            self.assertEqual(len({digest([r['question'],r['context'],r['options'],r['background']]) for r in group}),1)
            self.assertEqual(len({digest(build_request(request_payload(r,config),config)['messages'][0]) for r in group}),1)
        from decision_lab.studies.choice_history import ROOT, KINDS
        from decision_lab.studies.persona_mapping import common_background
        mapping=read(OUT/'private-map.json')
        for kind,folder in KINDS.items():
            source=read(ROOT/folder/'formal-v1/rich_development-study.json')
            original={(r['person'],r['task']):r for r in source['rows']}
            for person,link in mapping[kind]['people'].items():
                self.assertNotEqual(person,link['donor'])
                known=[original[(person,t)] for t in link['known_tasks']]
                donor=[original[(link['donor'],t)] for t in link['donor_tasks']]
                target=[original[(person,t)] for t in link['target_tasks']]
                self.assertEqual(known[0]['stratum'],donor[0]['stratum'])
                a=common_background(known[0]['background'],kind);b=common_background(donor[0]['background'],kind)
                self.assertEqual(a['education_group'],b['education_group'])
                self.assertEqual(int(a['age_bracket'][:2])>=65,int(b['age_bracket'][:2])>=65)
                for r in target:checked_history([observation(x) for x in donor],r)
                for row in study['rows']:
                    if row['kind']==kind and row['target_person']==person and row['arm']!='background':
                        self.assertEqual(row['known_choices'],[text_observation(x) for x in (known if row['arm']=='own' else donor)])
