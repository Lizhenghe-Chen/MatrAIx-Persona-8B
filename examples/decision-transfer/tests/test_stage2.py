"""Stage-2 invariants: sampling, donor legality, arm equality and scoring arithmetic."""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'src'))

import payloads  # noqa: E402
import personas  # noqa: E402
import protocol  # noqa: E402
import sample  # noqa: E402
import score  # noqa: E402
import swiss  # noqa: E402


class AllocationTest(unittest.TestCase):
    def test_largest_remainder_matches_population_and_capacity(self):
        counts = {('a', 'x'): 291, ('a', 'y'): 262, ('b', 'x'): 3}
        seats = sample.largest_remainder(counts, 48)
        self.assertEqual(sum(seats.values()), 48)
        self.assertLessEqual(seats[('b', 'x')], 3)

    def test_tiny_population_is_capped(self):
        seats = sample.largest_remainder({('a', 'x'): 2}, 48)
        self.assertEqual(seats[('a', 'x')], 2)


class ScoringTest(unittest.TestCase):
    def test_brier_hand_example(self):
        self.assertAlmostEqual(score.brier([0.9, 0.1], 'offer-1', ['offer-1', 'offer-2']), 0.02)
        self.assertAlmostEqual(score.brier([0.5, 0.5], 'offer-2', ['offer-1', 'offer-2']), 0.5)
        self.assertAlmostEqual(score.brier([1.0, 0.0], 'offer-2', ['offer-1', 'offer-2']), 2.0)

    def test_unknown_option_is_rejected(self):
        with self.assertRaises(ValueError):
            score.brier([0.5, 0.5], 'offer-3', ['offer-1', 'offer-2'])


class PersonaTest(unittest.TestCase):
    def test_swiss_labels_map_to_audited_values(self):
        rule, error = personas.constraints({'age_band': '65+', 'education': 'University/ETH/UAS',
                                            'gender': 'Female'})
        self.assertIsNone(error)
        self.assertEqual(rule['age_bracket'], ['65-74', '75-84', '85+'])
        self.assertEqual(rule['gender_identity'], ['Woman'])

    def test_unmapped_label_is_reported(self):
        rule, error = personas.constraints({'age_band': None, 'education': 'Other', 'gender': 'Male'})
        self.assertIsNone(rule)
        self.assertTrue(error.startswith('unmapped_'))

    def test_renderer_rejects_unapproved_values(self):
        with self.assertRaises(ValueError):
            personas.render({'age_bracket': '42-50'})

    def test_snapshot_hashes_hold(self):
        self.assertIn('files', personas.verify_snapshot())


@unittest.skipUnless((swiss.RAW / 'w14_conjoint.RData').exists(), 'Swiss source data not mounted')
class DeckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sep = swiss.load_sep()
        cls.conjoint = swiss.load_conjoint()
        cls.selection = sample.build(cls.sep, cls.conjoint)

    def test_selection_is_deterministic(self):
        again = sample.build(self.sep, self.conjoint)
        self.assertEqual([p['pub_id'] for p in self.selection['evaluation']],
                         [p['pub_id'] for p in again['evaluation']])
        self.assertEqual(self.selection['donors'], again['donors'])

    def test_roles_are_disjoint(self):
        evaluation = {p['pub_id'] for p in self.selection['evaluation']}
        technical = {p['pub_id'] for p in self.selection['technical']}
        reserved = {p['pub_id'] for rows in self.selection['reserved'].values() for p in rows}
        donors = set(self.selection['donors'].values())
        self.assertEqual(evaluation & technical, set())
        self.assertEqual(evaluation & reserved, set())
        self.assertEqual(donors & (evaluation | technical | reserved), set())
        self.assertEqual(len(donors), len(self.selection['donors']))

    def test_every_recipient_gets_a_donor_in_its_own_cell(self):
        people = {p['pub_id']: p for p in self.selection['people']}
        for recipient, donor in self.selection['donors'].items():
            self.assertNotEqual(recipient, donor)
            self.assertEqual(sample.cell_of(people[recipient]), sample.cell_of(people[donor]))
            self.assertTrue(all(v is not None for v in people[donor]['facts'].values()))

    def test_all_arms_share_one_questionnaire_and_carry_no_answer(self):
        person = self.selection['evaluation'][0]
        donor = {p['pub_id']: p for p in self.selection['people']}[self.selection['donors'][person['pub_id']]]
        persona = personas.render({'region': 'Western Europe', 'age_bracket': '45-54'})
        bodies = {arm: payloads.payload(person, arm, donor=donor, persona_text=persona)
                  for arm in protocol.ARMS}
        base = (bodies['basic']['context'], bodies['basic']['questions'])
        for arm, body in bodies.items():
            self.assertEqual((body['context'], body['questions']), base, arm)
            self.assertNotIn('ground_truth', json.dumps(body, ensure_ascii=False).lower())
        self.assertNotIn('extra', bodies['basic'])
        self.assertEqual(len(bodies['own']['extra']), 29)
        self.assertEqual(bodies['own']['extra'], bodies['basic'].get('extra', bodies['own']['extra']))
        self.assertNotEqual(bodies['own']['extra'], bodies['other']['extra'])

    def test_questions_use_published_price_levels(self):
        person = self.selection['evaluation'][0]
        questions = payloads.questions(person)
        self.assertEqual(len(questions), 6)
        for question in questions:
            self.assertEqual(sorted(question['options']), ['offer-1', 'offer-2'])
            for label in question['options'].values():
                self.assertRegex(label, r'price \d+\.\d{2} CHF, environmental impact (very low|low|medium|high|very high)')


if __name__ == '__main__':
    unittest.main()
