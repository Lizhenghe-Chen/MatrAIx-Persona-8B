import unittest
from ..population_scoring import distribution_comparison

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
    def test_duplicates_missing_and_invalid_weights_fail(self):
        base=dict(task='q',stratum='s',question='choose',context='same',options=['a','b'])
        human=[dict(base,person='h',answer=0)];synthetic=[dict(base,person='s')];p={('s','q'):[.5,.5]}
        for h,s,probs in [(human*2,synthetic,p),(human,synthetic,{}),([dict(human[0],weight=0)],synthetic,p)]:
            with self.assertRaises(ValueError):distribution_comparison(h,s,probs)
    def test_paired_fixed_reference_interval(self):
        from ..population_scoring import paired_population_interval
        base=dict(task='q',stratum='s',question='choose',context='same',options=['a','b'],background={'age_bracket':'18-24','education_group':'below_bachelor'})
        human=[dict(base,person='h',answer=0)];synthetic=[dict(base,person='s1'),dict(base,person='s2')]
        a={(r['person'],'q'):[.5,.5] for r in synthetic};b={(r['person'],'q'):[1,0] for r in synthetic}
        result=paired_population_interval(human,synthetic,a,b,repeats=20)
        self.assertEqual(result['improvement_95_ci'],[50,50]);self.assertTrue(result['passes_2pp_gate'])
