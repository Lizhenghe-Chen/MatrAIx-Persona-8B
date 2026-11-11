import unittest
from ..evaluation.bundle_diagnostics import summarize

class BundleTests(unittest.TestCase):
    def test_different_cards_never_count_as_same_answer(self):
        base=dict(task='q',stratum='s',question='choose',context='same',options=['a','b'])
        rows=[dict(base,person='one'),dict(base,person='two'),dict(base,person='three',options=['c','d'])]
        p={(r['person'],'q'):[.8,.2] for r in rows}
        result=summarize(rows,p)
        self.assertEqual(result['comparable_people'],2)
        self.assertEqual(result['incomparable_people'],1)
        self.assertEqual(result['fraction_sharing_complete_pattern'],1)
        human=[dict(r,answer=i%2) for i,r in enumerate(rows)]
        self.assertEqual(summarize(human)['fraction_sharing_complete_pattern'],0)
    def test_unique_bundle_is_unavailable_not_zero(self):
        row=dict(person='one',task='q',stratum='s',question='choose',context='same',options=['a','b'],answer=0)
        self.assertIsNone(summarize([row])['fraction_sharing_complete_pattern'])
