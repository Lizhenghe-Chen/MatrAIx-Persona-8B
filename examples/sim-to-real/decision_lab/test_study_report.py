import unittest
from .study_report import render
class ReportTests(unittest.TestCase):
    def test_completed_evidence_and_escaping(self):
        with self.assertRaises(ValueError):render({'status':'running'})
        data={'status':'complete_test_primary_brier_only','kind':'dryer','methods':{'rich':{'brier':.5}},'comparisons':{},'product_choice_shares':{},'subgroups':{},'calibration_llm_weight':.25,'history_unseen_tasks':0,'prepared_sha256':'<unsafe>'}
        page=render(data)
        self.assertIn('&lt;unsafe&gt;',page);self.assertNotIn('<unsafe>',page)
        self.assertIn('25%',page);self.assertIn('0.500',page)
