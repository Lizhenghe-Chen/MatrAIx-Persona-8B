import unittest
from .population_concentration import summarize

class ConcentrationTests(unittest.TestCase):
    def test_argmax_collapse_is_distinct_from_probability_distribution(self):
        base=dict(task='q',stratum='s',question='choose',context='same',options=['a','b'])
        human=[dict(base,person=f'h{i}',answer=i%2) for i in range(20)]
        synthetic=[dict(base,person=f's{i}') for i in range(20)]
        p={(r['person'],'q'):[.5,.5] for r in synthetic}
        result=summarize(human,synthetic,p)
        self.assertEqual(result['supported_cards'],1)
        self.assertEqual(result['argmax_ties'],20)
        self.assertEqual(result['thresholds']['1.0'],{'human':0,'mean_probabilities':0,'argmax_votes':1})
        small=summarize(human,synthetic[:1],{('s0','q'):[.5,.5]})
        self.assertEqual(small['supported_cards'],0)
