import unittest
from ..studies.swiss_adapter import label,EDUCATION,INCOME

class SwissMappings(unittest.TestCase):
    def test_raw_codes_not_summary_table_zero_based_numbers(self):
        self.assertEqual(label(1,EDUCATION),'None')
        self.assertEqual(label(7,EDUCATION),'University/ETH')
        self.assertEqual(label(1,INCOME),'Under CHF 2000')
        self.assertEqual(label(10,INCOME),'Above CHF 18000')
    def test_missing_not_invented(self):
        self.assertEqual(label(float('nan'),EDUCATION),'unknown')
        self.assertEqual(label(-8,INCOME),'unknown')
        for value in [0,11,2.5]:
            with self.assertRaises(ValueError):label(value,INCOME)
