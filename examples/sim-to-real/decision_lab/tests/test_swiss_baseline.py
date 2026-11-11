import unittest
from ..studies.swiss_baseline import attributes

class SwissFeatures(unittest.TestCase):
    def test_features_do_not_depend_on_position(self):
        text='Smartphone A; Price: CHF 180; Functional life: 2 years; Env. production impact: Medium; Energy efficiency: C; Recyclability: Recyclable; Repairability: Not repairable at all'
        self.assertEqual(attributes(text),[180,2,1,1,2,0])
        self.assertEqual(attributes(text.replace('Smartphone A','Smartphone B')),attributes(text))
    def test_unknown_label_stops(self):
        with self.assertRaises(KeyError):attributes('A; Price: CHF 180; Functional life: 2 years; Env. production impact: unknown')
