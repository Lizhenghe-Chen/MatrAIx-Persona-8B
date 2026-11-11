import unittest
from .population_scoring import distribution_comparison

class PopulationTests(unittest.TestCase):
    def test_no_individual_pairing(self):
        base=dict(task='q',stratum='s',question='choose',context='same',options=['a','b'])
        human=[dict(base,person='real1',answer=0),dict(base,person='real2',answer=1)]
        synthetic=[dict(base,person='generated1')]
        result=distribution_comparison(human,synthetic,{('generated1','q'):[.5,.5]})
        self.assertEqual(result['mean_tv_pp'],0)
        self.assertEqual(result['cards'][0]['human_people'],2)
        with self.assertRaises(ValueError):distribution_comparison(human,[dict(synthetic[0],answer=0)],{})
    def test_different_products_rejected(self):
        base=dict(task='q',stratum='s',question='choose',context='same',options=['a','b'])
        with self.assertRaises(ValueError):distribution_comparison([dict(base,person='h',answer=0)],[dict(base,person='s',options=['a','c'])],{})
