import unittest
import numpy as np
from ..core.baselines import ConditionalLogit,select_penalty

class ChoiceBaselineTests(unittest.TestCase):
    def tasks(self):
        return [{'person':str(i),'features':[[1.0,0],[3.0,0]],'answer':0} for i in range(20)]
    def test_learns_and_respects_permutation(self):
        m=ConditionalLogit(.01).fit(self.tasks())
        p=m.predict([{'features':[[1.,0],[3.,0]]},{'features':[[3.,0],[1.,0]]}])
        self.assertGreater(p[0][0],.8)
        np.testing.assert_allclose(p[0],p[1][::-1])
    def test_repeating_same_person_does_not_add_weight(self):
        t=self.tasks();a=ConditionalLogit(.01).fit(t);b=ConditionalLogit(.01).fit(t+t[:1]*20)
        np.testing.assert_allclose(a.beta,b.beta,atol=1e-6)
    def test_development_overlap_rejected(self):
        with self.assertRaises(ValueError):select_penalty(self.tasks(),self.tasks())
    def test_unseen_set_size(self):
        m=ConditionalLogit().fit(self.tasks());p=m.predict([{'features':[[1.,0],[2.,0],[3.,0]]}])[0]
        self.assertEqual(len(p),3);self.assertAlmostEqual(sum(p),1)
