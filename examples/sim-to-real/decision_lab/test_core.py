import unittest
from .core import probabilities, split, request_payload, brier, tv

class CoreTests(unittest.TestCase):
    def test_probability_validation(self):
        for p in [[.8,.8], [float('nan'),1], [-.1,1.1]]:
            with self.assertRaises(ValueError): probabilities(p,2)
    def test_privacy_boundary(self):
        row={'question':'Q','options':['A','B'],'context':'C','background':{'age':30,'answer':1},'answer':1,'person':'secret','weight':9}
        p=request_payload(row,{'background_fields':['age']})
        self.assertEqual(set(p),{'question','options','context','background'})
        self.assertEqual(p['background'],{'age':30})
    def test_repeated_people(self):
        rows=[{'person':str(i),'stratum':'s'} for i in range(20)]*3
        self.assertEqual(split(rows),split(rows[:20]))
        self.assertEqual(len(split(rows)),20)
    def test_metrics(self):
        self.assertAlmostEqual(brier([.2,.8],1),.08)
        self.assertAlmostEqual(tv([.2,.8],[.5,.5]),.3)

if __name__=='__main__': unittest.main()
