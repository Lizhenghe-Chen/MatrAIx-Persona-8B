import unittest
from ..diagnostics import choice_diagnostics

class DiagnosticsTests(unittest.TestCase):
    def test_minority_and_ties_not_hidden(self):
        rows=[{'person':str(i),'task':'q','score_group':'card','options':['buy','neither'],'answer':i%2} for i in range(4)]
        p={(r['person'],'q'):[.5,.5] for r in rows}
        d=choice_diagnostics(rows,p)
        self.assertEqual(d['argmax_ties'],4)
        self.assertEqual(d['groups']['card']['recall'][1]['recall'],0)
        self.assertEqual(d['groups']['card']['max_mean_probability'],.5)
        self.assertEqual(d['concentration_thresholds']['1.0']['groups_with_at_least_20_people'],0)
