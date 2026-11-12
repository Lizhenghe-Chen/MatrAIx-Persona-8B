import unittest

from ..cross_study import drone_baseline, matching, scoring


def question(qid, options):
    return {'id': qid, 'prompt': 'Which?', 'type': 'single_choice', 'required': True,
            'options': [{'id': o, 'label': l} for o, l in options]}


def case(person, answer, vectors, stratum='25-34|Male'):
    return {'person': person, 'stratum': stratum, 'weight': 1.0, 'group': stratum,
            'questions': [question('card1', [('0', 'Ground vehicle: a'), ('1', 'Drone: b')])],
            'truth': {'card1': answer}, 'predictions': vectors}


class DroneAttributeTests(unittest.TestCase):
    def test_option_text_round_trips_through_the_feature_parser(self):
        ground = drone_baseline.option_text(0, 0, 3, 30, 1)
        drone = drone_baseline.option_text(1, 0, 5, 1440, 0)
        self.assertEqual(drone_baseline.attributes(ground), [3.0, 30.0, 0.0, 0.0])
        self.assertEqual(drone_baseline.attributes(drone), [5.0, 1440.0, 1.0, 0.0])
        self.assertEqual(drone_baseline.attributes(drone_baseline.option_text(1, 0, 1, 120, 1)),
                         [1.0, 120.0, 1.0, 1.0])

    def test_privacy_only_counts_for_the_drone(self):
        self.assertEqual(drone_baseline.attributes(drone_baseline.option_text(0, 1, 10, 360, 1))[3], 0.0)

    def test_unknown_wait_time_is_rejected(self):
        with self.assertRaises(ValueError):
            drone_baseline.attributes('Drone: delivery fee $1, wait 3 days, privacy: NO privacy')


class NoEducationMatchingTests(unittest.TestCase):
    def record(self, study, age):
        return {'study': study, 'background': {'Age group': age, 'Gender': 'Female'},
                'country': 'United States'}

    def test_instrument_without_education_drops_the_constraint_and_declares_it(self):
        rule, error = matching.constraints(self.record('shoes', '26-35 years old'))
        self.assertIsNone(error)
        self.assertNotIn('highest_education', rule['allowed'])
        self.assertEqual(rule['education_resolution'], 'unavailable_in_instrument')
        self.assertEqual(rule['allowed']['age_bracket'], ['25-34', '35-44'])

    def test_missing_education_still_excluded_where_the_instrument_measured_it(self):
        _, error = matching.constraints(self.record('shed', '25-34'))
        self.assertEqual(error, 'unmapped_education:Unknown')


class TwoArmScoringTests(unittest.TestCase):
    def test_contrasts_only_cover_arms_that_were_run(self):
        cases = [case(f'p{i}', '1' if i % 2 else '0',
                      {'original': {'card1': [1.0, 0.0]}, 'optimized': {'card1': [0.4, 0.6]}})
                 for i in range(24)]
        results = scoring.evaluate(cases, scoring.build_references(cases, []), ['original', 'optimized'])
        self.assertNotIn('output_only__to__optimized', results['contrasts'])
        self.assertNotIn('prompt_only__to__optimized', results['contrasts'])
        self.assertIn('original__to__optimized', results['contrasts'])

    def test_four_arm_contrasts_are_unchanged(self):
        arms = ['original', 'output_only', 'prompt_only', 'optimized']
        cases = [case(f'p{i}', '1' if i % 2 else '0',
                      {a: {'card1': [0.5, 0.5]} for a in arms}) for i in range(24)]
        results = scoring.evaluate(cases, scoring.build_references(cases, []), arms)
        self.assertIn('output_only__to__optimized', results['contrasts'])
        self.assertIn('prompt_only__to__optimized', results['contrasts'])
