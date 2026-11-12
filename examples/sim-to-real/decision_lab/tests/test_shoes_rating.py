import unittest

from ..core.baselines import RatingAttributeBaseline
from ..cross_study.adapters import SHOES_ATTRIBUTES, shoe_card_id
from ..cross_study.shoes_baseline import attributes, encode, vocabulary

LEVELS = tuple(range(1, 8))


class RatingBaselineTests(unittest.TestCase):
    def tasks(self):
        rows = []
        for person in range(40):
            for step in range(6):
                value = float(step)
                rows.append({'person': f'p{person}', 'features': [value], 'answer': int(1 + round(value))})
        return rows

    def test_predicts_a_normalised_scale_distribution(self):
        model = RatingAttributeBaseline(LEVELS).fit(self.tasks())
        low, high = model.predict([{'features': [0.0]}, {'features': [5.0]}])
        for vector in (low, high):
            self.assertEqual(len(vector), 7)
            self.assertAlmostEqual(sum(vector), 1.0, places=6)
        self.assertGreater(high.index(max(high)), low.index(max(low)))

    def test_rating_outside_declared_scale_rejected(self):
        with self.assertRaises(ValueError):
            RatingAttributeBaseline(LEVELS).fit([{'person': 'p', 'features': [1.0], 'answer': 9}])


class ShoeCardIdentityTests(unittest.TestCase):
    def shoe(self, **changes):
        row = {'attr_' + key: f'value{i}' for i, key in enumerate(SHOES_ATTRIBUTES)}
        row.update({'attr_' + key: value for key, value in changes.items()})
        return row

    def test_different_shoes_never_share_a_card_id(self):
        self.assertNotEqual(shoe_card_id(self.shoe()), shoe_card_id(self.shoe(brand='Nike')))

    def test_identical_shoes_share_a_card_id(self):
        self.assertEqual(shoe_card_id(self.shoe()), shoe_card_id(self.shoe()))


class ShoePromptParsingTests(unittest.TestCase):
    def prompt(self, brand='Puma', price='$88'):
        return ('Rate this shoe: ave customer review: 4 out of 5, best seller: #12 in Athletic Shoes, '
                f'brand: {brand}, color: Gray, eco friendly materials: No Eco-Friendly Materials Used, '
                f'gel cushioning: Has Gel Cushioning, model year: 2017, price: {price}, '
                'shipping: Free Expedited Shipping, weight: 7 oz.')

    def test_reads_every_displayed_attribute(self):
        found = attributes(self.prompt())
        self.assertEqual(found['brand'], 'Puma')
        self.assertEqual(len(found), len(SHOES_ATTRIBUTES))

    def test_unseen_category_rejected(self):
        levels = vocabulary([self.prompt()])
        with self.assertRaises(ValueError):
            encode(attributes(self.prompt(brand='Saucony')), levels)

    def test_encoding_is_stable_and_price_sensitive(self):
        levels = vocabulary([self.prompt()])
        self.assertEqual(encode(attributes(self.prompt()), levels), encode(attributes(self.prompt()), levels))
        self.assertNotEqual(encode(attributes(self.prompt()), levels),
                            encode(attributes(self.prompt(price='$110')), levels))
