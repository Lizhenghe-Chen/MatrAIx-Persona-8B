import unittest
from types import SimpleNamespace
from ..studies.dryer_adapter import option_text

class DryerCards(unittest.TestCase):
    def row(self, **changes):
        fields=dict(Alternative=1,CountryVersion='USA',Treatment='C',Price=200,Capacity=7,Rating='A++',EnExp=370,Brand='New',Stars=4)
        fields.update(changes);return SimpleNamespace(**fields)
    def test_north_american_units(self):
        text=option_text(self.row())
        self.assertIn('USD 300',text);self.assertIn('6 cu ft',text);self.assertIn('Energy Star: Yes',text)
        self.assertNotIn('A++',text)
    def test_european_generic(self):
        text=option_text(self.row(CountryVersion='IRE',Treatment='T1',EnExp=500))
        self.assertIn('EUR 200',text);self.assertIn('7 kg',text);self.assertIn('Energy Cost: EUR 500',text)
    def test_ambiguous_conditions_rejected(self):
        for changes in [dict(Treatment='T2'),dict(Treatment='T1')]:
            with self.assertRaises(ValueError):option_text(self.row(**changes))
    def test_neither_is_preserved(self):
        self.assertEqual(option_text(self.row(Alternative=0)),'Neither')
