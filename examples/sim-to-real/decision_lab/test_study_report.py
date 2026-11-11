import unittest
from .study_report import render,conclusion
class ReportTests(unittest.TestCase):
    def test_completed_evidence_and_escaping(self):
        with self.assertRaises(ValueError):render({'status':'running'})
        data={'status':'complete_test_primary_brier_only','kind':'dryer','methods':{'rich':{'brier':.5}},'comparisons':{},'product_choice_shares':{},'subgroups':{},'calibration_llm_weight':.25,'history_unseen_tasks':0,'prepared_sha256':'<unsafe>'}
        page=render(data)
        self.assertIn('&lt;unsafe&gt;',page);self.assertNotIn('<unsafe>',page)
        self.assertIn('25%',page);self.assertIn('0.500',page)
        self.assertIn('先说结论',page);self.assertIn('真实背景',page)
    def test_conclusions_do_not_promote_uncertain_or_small_gains(self):
        for interval,passes,expected in [([.01,.03],True,'达到预先规定'),
                                         ([.001,.002],False,'幅度未达到'),
                                         ([-.01,.03],False,'尚无明确'),
                                         ([-.03,-.01],False,'明确退化')]:
            data={'comparisons':{'basic__to__rich':{'improvement_95_ci':interval,'passes_2_percent_gate':passes}}}
            self.assertIn(expected,conclusion(data))
