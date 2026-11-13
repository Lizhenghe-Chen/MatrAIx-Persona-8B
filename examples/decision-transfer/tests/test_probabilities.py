import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from probabilities import parse_probabilities, validate_questions

class ProbabilitiesTest(unittest.TestCase):
    def test_rounding(self):
        p, normalized = parse_probabilities({'a':.333,'b':.333,'c':.333},['a','b','c'])
        self.assertTrue(normalized)
        self.assertAlmostEqual(sum(p),1)
    def test_invalid(self):
        for value in [{'a':1}, {'a':True,'b':0}, {'a':float('nan'),'b':0}, {'a':.3,'b':.3}, {'a':-1,'b':2}]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_probabilities(value,['a','b'])
    def test_answer_leak(self):
        q={'id':'q1','prompt':'Choose','options':{'a':'One','b':'Two'}}
        validate_questions([q])
        for key in ['answer','weight','person_id']:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_questions([{**q,key:'secret'}])
    def test_duplicate(self):
        q={'id':'q1','prompt':'Choose','options':{'a':'One','b':'Two'}}
        with self.assertRaises(ValueError): validate_questions([q,q])
