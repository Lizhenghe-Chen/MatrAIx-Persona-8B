import unittest
from unittest.mock import patch
from .product_summary import summarize

class ProductSummaryTests(unittest.TestCase):
    def test_ties_refusal_and_person_weight(self):
        def attrs(x):return {'cheap':[0,5,0,2],'dear':[0,10,0,2]}[x]
        rows=[dict(person='a',task=str(i),options=['cheap','dear','Neither'],answer=2) for i in range(3)]
        rows.append(dict(person='b',task='0',options=['cheap','dear','Neither'],answer=0))
        p={(r['person'],r['task']):[.2,.3,.5] for r in rows}
        with patch('decision_lab.dryer_baseline.attributes',attrs):result=summarize(rows,p,'dryer')['events']
        self.assertEqual(result['lower_price']['human_share'],.5)
        self.assertAlmostEqual(result['lower_price']['model_probability_share'],.2)
        self.assertEqual(result['refusal']['human_share'],.5)
        self.assertNotIn('higher_customer_rating',result)
