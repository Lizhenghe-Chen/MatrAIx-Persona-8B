import unittest
from .scoring import score,paired_interval

class ScoringTests(unittest.TestCase):
    def rows(self):
        return [{'person':str(i),'task':'q','score_group':'q','stratum':'s','options':['yes','no'],'answer':i%2} for i in range(10)]
    def test_perfect(self):
        rows=self.rows();p={(r['person'],'q'):[int(i==r['answer']) for i in range(2)] for r in rows}
        result=score(rows,p);self.assertEqual(result['brier'],0);self.assertEqual(result['mean_tv_pp'],0)
        self.assertEqual(paired_interval(rows,p,p,repeats=20)['brier']['improvement_95_ci'],[0,0])
    def test_missing_fails(self):
        with self.assertRaises(ValueError):score(self.rows(),{})
    def test_repeated_tasks_do_not_overweight_people(self):
        rows=self.rows();p={(r['person'],'q'):[.5,.5] for r in rows}
        extra={**rows[0],'task':'q2'};rows.append(extra);p[('0','q2')]=[.5,.5]
        self.assertAlmostEqual(score(rows,p)['brier'],.5)
    def test_misaligned_options_fail(self):
        rows=self.rows();rows[0]['options']=['other','no'];p={(r['person'],'q'):[.5,.5] for r in rows}
        with self.assertRaises(ValueError):score(rows,p)
