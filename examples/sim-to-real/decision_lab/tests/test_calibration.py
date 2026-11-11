import unittest
from ..core.calibration import transform,select,apply

class CalibrationTests(unittest.TestCase):
    def test_identity_and_zero(self):
        self.assertEqual(transform([0,1],2),[0,1])
        self.assertAlmostEqual(transform([.2,.8],1)[0],.2)
    def test_statistical_baseline_can_win(self):
        rows=[{'person':'a','task':'q','split':'development','answer':1,'options':['A','B']}]
        result=select(rows,{('a','q'):[1,0]},{('a','q'):[0,1]})
        self.assertEqual(result['llm_weight'],0)
        self.assertEqual(apply([1,0],[0,1],result),[0,1])
    def test_test_data_rejected(self):
        r=[{'person':'a','task':'q','split':'test'}]
        with self.assertRaises(ValueError):select(r,{}, {})
    def test_person_overlap_rejected(self):
        r=[{'person':'a','task':'q','split':'development'}]
        with self.assertRaises(ValueError):select(r,{}, {},forbidden_people=['a'])
