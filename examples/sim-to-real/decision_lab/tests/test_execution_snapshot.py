"""Verification must accept a faithful checkpoint and reject a tampered one."""
import unittest,tempfile,json,sqlite3
from pathlib import Path
from ..core.core import digest,split
from ..core.runner import run,GATES
from ..evaluation.execution_snapshot import snapshot,verify_unit

CONFIG={'model':'deepseek-v4-pro','temperature':0.7,'top_p':1,'max_tokens':64,'status':'frozen',
        'expected_identity':{'model':'deepseek-v4-pro','system_fingerprint':'fp'},'max_calls':8,
        'max_cost_usd':5,'input_usd_per_million':1.32,'output_usd_per_million':3.96,
        'endpoint':'offline-test','background_fields':['age'],'output_mode':'probabilities'}


def _transport(body,endpoint):
    return {'model':'deepseek-v4-pro','system_fingerprint':'fp',
            'usage':{'prompt_tokens':10,'completion_tokens':2},
            'choices':[{'finish_reason':'stop','message':{'content':'{"probabilities":[0.6,0.4]}'}}]}


def _build(root):
    rows=[dict(person=f'p{i}',task='q1',stratum='S',question='q',context='c',options=['A','B'],
               answer=i%2,group='g',background={'age':float(i)}) for i in range(8)]
    study={'rows':rows,'audit':dict.fromkeys(GATES,True)}
    seal={'input_sha256':digest(study),'config_sha256':digest(CONFIG),'assignments':{f'p{i}':'test' for i in range(8)}}
    formal=root/'formal-v1';formal.mkdir(parents=True)
    write=lambda p,d:p.write_text(json.dumps(d))
    for suffix,obj in [('study',study),('config',CONFIG),('seal',seal)]:write(formal/('unit_test-'+suffix+'.json'),obj)
    write(formal/'manifest.json',{'units':[{'name':'unit_test','phase':'test','calls':8,
          'study_sha256':digest(study),'config_sha256':digest(CONFIG),'seal_sha256':digest(seal)}]})
    assert run(study,seal,CONFIG,formal/'unit_test.sqlite','test',_transport)['complete']
    return formal


class SnapshotTests(unittest.TestCase):
    def test_faithful_checkpoint_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            _build(Path(tmp))
            result=snapshot(Path(tmp))
            self.assertEqual(result['status'],'verified_complete_plan',result['failures'])
            self.assertTrue(result['units'][0]['request_identities_verified'])

    def test_changed_frozen_input_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            formal=_build(Path(tmp))
            study=json.loads((formal/'unit_test-study.json').read_text())
            study['rows'][0]['context']='changed after freezing'
            (formal/'unit_test-study.json').write_text(json.dumps(study))
            result=snapshot(Path(tmp))
            self.assertEqual(result['status'],'verification_failed')
            self.assertTrue(any('frozen files changed' in x for x in result['failures']))

    def test_dropped_row_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            formal=_build(Path(tmp))
            database=sqlite3.connect(formal/'unit_test.sqlite')
            database.execute('DELETE FROM calls WHERE rowid=1');database.commit();database.close()
            result=snapshot(Path(tmp))
            self.assertEqual(result['status'],'verification_failed')
            self.assertTrue(any('incomplete' in x for x in result['failures']))

    def test_wrong_server_identity_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            formal=_build(Path(tmp))
            database=sqlite3.connect(formal/'unit_test.sqlite')
            row=database.execute('SELECT job,response FROM calls LIMIT 1').fetchone()
            payload=json.loads(row[1]);payload['identity']={'model':'deepseek-v4-pro','system_fingerprint':'other'}
            database.execute('UPDATE calls SET response=? WHERE job=?',(json.dumps(payload),row[0]))
            database.commit();database.close()
            result=snapshot(Path(tmp))
            self.assertEqual(result['status'],'verification_failed')
            self.assertTrue(any('server identity' in x for x in result['failures']))


class SyntheticSnapshotTests(unittest.TestCase):
    def test_tasks_per_condition_is_the_unit_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            rows=[dict(person=f'p{i}',task='q1',stratum='S',question='q',context='c',options=['A','B'],
                       group='g',background={'age':float(i)}) for i in range(6)]
            study={'rows':rows,'audit':dict.fromkeys(GATES,True),'evaluation_mode':'synthetic_population',
                   'person_source':'generated'}
            config={**CONFIG,'max_calls':6}
            seal={'input_sha256':digest(study),'config_sha256':digest(config),'assignments':{r['person']:'test' for r in rows}}
            synthetic=root/'synthetic-formal-v1';synthetic.mkdir()
            write=lambda p,d:p.write_text(json.dumps(d))
            for suffix,obj in [('study',study),('config',config),('seal',seal)]:write(synthetic/('demographics-'+suffix+'.json'),obj)
            # people is the generated cohort size, not a multiplier for the unit task count
            write(synthetic/'manifest.json',{'people':99,'tasks_per_condition':6,'units':[{'name':'demographics',
                  'study_sha256':digest(study),'config_sha256':digest(config),'seal_sha256':digest(seal)}]})
            assert run(study,seal,config,synthetic/'demographics.sqlite','test',_transport)['complete']
            result=snapshot(root)
            self.assertEqual(result['status'],'verified_complete_plan',result['failures'])
            self.assertEqual(result['units'][0]['expected_tasks'],6)
