import unittest
from ..survey_baseline import SurveyBaseline

class SurveyBaselineTests(unittest.TestCase):
    def rows(self):
        return [{'person':str(i),'score_group':'q','options':['A','B','C'],'answer':i%2,'background':{'age':'young' if i%2 else 'old'}} for i in range(20)]
    def test_prediction_does_not_need_answers(self):
        rows=self.rows();m=SurveyBaseline(['age']).fit(rows)
        clean=[{k:v for k,v in r.items() if k!='answer'} for r in rows]
        p=m.predict(clean);self.assertEqual(len(p[0]),3);self.assertAlmostEqual(sum(p[0]),1)
        self.assertGreater(p[0][0],p[0][1])
    def test_single_class_keeps_all_options(self):
        rows=self.rows()[:1];m=SurveyBaseline(['age']).fit(rows)
        p=m.predict(rows)[0];self.assertTrue(all(x>0 for x in p));self.assertAlmostEqual(sum(p),1)
    def test_unseen_background(self):
        rows=self.rows();m=SurveyBaseline(['age']).fit(rows)
        rows[0]['background']={'age':'unseen'}
        self.assertAlmostEqual(sum(m.predict(rows[:1])[0]),1)
