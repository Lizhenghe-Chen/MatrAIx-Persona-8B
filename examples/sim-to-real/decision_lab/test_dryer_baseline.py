import unittest
from .dryer_baseline import attributes

class DisplayedFeatures(unittest.TestCase):
    def test_reject_option_preserved(self):
        self.assertEqual(attributes('Neither'),[1,0,0,0,0,0])
    def test_no_hidden_north_american_grade(self):
        text='Tumble dryer 1; Brand: New; Capacity: 6 cu ft; Energy Star: Yes; Customer rating: 4 stars; Price: USD 300'
        self.assertEqual(attributes(text),[0,300,6,4,0,1])
        self.assertEqual(attributes(text.replace('dryer 1','dryer 2')),attributes(text))
    def test_energy_cost_is_not_efficiency_grade(self):
        text='Tumble dryer 1; Brand: Established; Capacity: 7 kg; 10 year Energy Cost: EUR 950; Customer rating: 3 stars; Price: EUR 600'
        self.assertEqual(attributes(text),[0,600,7,3,1,950])
