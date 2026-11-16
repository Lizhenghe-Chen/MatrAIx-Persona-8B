import sys
import json
import copy
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from protocol import build, parse, MODELS


class ProtocolTest(unittest.TestCase):
    def setUp(self):
        self.q = [
            {
                'id': 'q1',
                'prompt': 'Choose a product',
                'options': {'a': 'Product A', 'b': 'Product B'},
            }
        ]
        self.common = {
            'title': 'Fixture survey',
            'context': 'Fictional software test, not a real respondent',
            'questions': self.q,
        }
        self.base = {'age': 'Age'}
        self.extra = {'attitude': 'Measured attitude'}

    def body(self, arm, model='qwen'):
        p = copy.deepcopy(self.common)
        if arm == 'matraix':
            p['persona_text'] = 'Test native persona placeholder'
        else:
            p['basic'] = {'age': '35'}
            if arm != 'basic':
                p['extra'] = {'attitude': None if arm == 'other' else 'Concerned'}
        return build(p, arm, model, self.base, self.extra, 768)

    def test_task_identical_across_arms(self):
        messages = [
            self.body(a)['messages'][1] for a in ['matraix', 'basic', 'own', 'other']
        ]
        self.assertTrue(all(m == messages[0] for m in messages))
        self.assertIn('Unknown', self.body('other')['messages'][0]['content'])

    def test_models(self):
        q = self.body('own')
        p = self.body('own', 'pro')
        self.assertEqual(q['messages'], p['messages'])
        self.assertFalse(q['chat_template_kwargs']['enable_thinking'])
        self.assertEqual(p['thinking'], {'type': 'disabled'})

    def test_payload_leak(self):
        for key in ['weight', 'answer', 'person_id', 'donor_id']:
            with self.subTest(key=key), self.assertRaises(ValueError):
                build(
                    {**self.common, 'basic': {'age': '35'}, key: 'secret'},
                    'basic',
                    'qwen',
                    self.base,
                    self.extra,
                    768,
                )

    def response(self, answers=None):
        return {
            'model': MODELS['pro'],
            'choices': [
                {
                    'finish_reason': 'stop',
                    'message': {
                        'content': json.dumps(
                            {
                                'answers': answers
                                if answers is not None
                                else [
                                    {
                                        'questionId': 'q1',
                                        'probabilities': {'a': 0.6, 'b': 0.4},
                                    }
                                ]
                            }
                        )
                    },
                }
            ],
        }

    def test_parse(self):
        self.assertEqual(
            parse(self.response(), self.q, 'pro')['probabilities'], {'q1': [0.6, 0.4]}
        )

    def test_invalid_response(self):
        r = self.response()
        row = json.loads(r['choices'][0]['message']['content'])['answers'][0]
        for answers in [[], [row, row], [{**row, 'questionId': 'secret'}]]:
            with self.subTest(answers=answers), self.assertRaises(ValueError):
                parse(self.response(answers), self.q, 'pro')
        with self.assertRaises(ValueError):
            parse(r, self.q, 'qwen')
        with self.assertRaises(ValueError):
            parse(
                r,
                self.q,
                'pro',
                {'model': MODELS['pro'], 'system_fingerprint': 'different'},
            )
        r['choices'][0]['finish_reason'] = 'length'
        with self.assertRaises(ValueError):
            parse(r, self.q, 'pro')
