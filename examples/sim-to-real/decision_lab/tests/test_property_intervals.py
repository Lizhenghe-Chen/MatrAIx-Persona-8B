import unittest
from ..property_intervals import compare

class PropertyIntervalTests(unittest.TestCase):
    def test_known_improvement_and_separate_person_ids(self):
        option=lambda price,stars:f'Price: USD {price}; Capacity: 5; Customer rating: {stars}; Brand: Established; Energy Star: Yes'
        base=dict(task='q',stratum='s',question='choose',context='same',options=[option(500,3),option(700,5),'Neither'],background={'age_bracket':'18-24','education_group':'below_bachelor'})
        human=[dict(base,person='human',answer=0)]
        synthetic=[dict(base,person='generated1'),dict(base,person='generated2')]
        a={(r['person'],'q'):[.5,.5,0] for r in synthetic};b={(r['person'],'q'):[1,0,0] for r in synthetic}
        result=compare(human,synthetic,a,b,'dryer',repeats=20)
        self.assertEqual(result['lower_price']['improvement_95_ci'],[50,50])
        self.assertEqual(result['higher_customer_rating']['absolute_error_reduction_pp'],50)
        self.assertEqual(result['refusal']['improvement_95_ci'],[0,0])
        with self.assertRaises(ValueError):compare(human,[dict(synthetic[0],answer=0)],a,b,'dryer',repeats=20)
