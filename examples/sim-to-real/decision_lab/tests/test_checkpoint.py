import json,sqlite3,tempfile,unittest
from pathlib import Path
from ..core.checkpoint import read_predictions
from ..core.runner import run
from . import test_runner

class CheckpointTests(unittest.TestCase):
    def fixture(self):
        s,f,c=test_runner.RunnerTests().fixtures()
        from ..core.core import digest
        for r in s['rows']:r['group']='q'
        f['input_sha256']=digest(s)
        return s,f,c
    def test_round_trip_and_tamper(self):
        s,f,c=self.fixture()
        def transport(*args):
            return {'model':'deepseek-v4-pro','choices':[{'finish_reason':'stop','message':{'content':'{"probabilities":[0.4,0.6]}'}}]}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'calls.sqlite';run(s,f,c,p,'test',transport)
            rows,predictions,missing=read_predictions(s,f,c,p,'test')
            self.assertEqual(len(predictions),2);self.assertEqual(missing,[]);self.assertEqual(rows[0]['score_group'],'q')
            db=sqlite3.connect(p);db.execute("UPDATE calls SET request_hash='tampered'");db.commit();db.close()
            with self.assertRaises(ValueError):read_predictions(s,f,c,p,'test')
    def test_incomplete_does_not_silently_pass(self):
        s,f,c=self.fixture()
        from ..core.core import digest
        c['max_cost_usd']=1e-9;f['config_sha256']=digest(c)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'calls.sqlite';run(s,f,c,p,'test')
            with self.assertRaises(ValueError):read_predictions(s,f,c,p,'test')
            _,predictions,missing=read_predictions(s,f,c,p,'test',False)
            self.assertEqual(predictions,{});self.assertEqual(len(missing),2)
