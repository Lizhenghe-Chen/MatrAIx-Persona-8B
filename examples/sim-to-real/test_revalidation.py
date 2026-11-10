"""Protocol regressions without API calls or respondent data."""
import json
import unittest
import numpy as np

from revalidation import allocations,coarse_real,decode,request_body
from revalidation_score import weighted_draws,contrast


class RevalidationChecks(unittest.TestCase):
    def test_all_official_education_labels_and_missingness(self):
        background={'Age group':'30-49','Education':'H.S. graduate or less','Sex':'Female','Income':'20 to under $30,000'}
        for label in ('H.S. graduate or less','Some college','College graduate+'):
            result=coarse_real({**background,'Education':label})
            self.assertIsNotNone(result)
            self.assertEqual(result['Education']=="Bachelor's degree or higher",label=='College graduate+')
        self.assertIsNone(coarse_real({**background,'Income':"(VOL) Don't know/Refused"}))
        with self.assertRaisesRegex(ValueError,'Unmapped nonmissing'):
            coarse_real({**background,'Education':'HS grad or less'})

    def test_shared_income_boundary(self):
        base={'Age group':'65+','Education':'Some college','Sex':'Male'}
        for label,high in [('75 to under $100,000',False),('100 to under $150,000 [OR]',True),('$150,000 or more',True)]:
            result=coarse_real({**base,'Income':label})
            self.assertEqual(result['Household income']=='$100,000 or more',high)

    def test_choice_and_probability_mapping_keep_neither(self):
        mapping={'q1':('card',[1,0,2])}
        for shown,original in [('1',1),('2',0),('0',2)]:
            p=decode(json.dumps({'q1':shown}),mapping,False)['card']
            self.assertEqual(p[original],1)
        self.assertEqual(decode('{"q1":[0.2,0.3,0.5]}',mapping,True)['card'],[.3,.2,.5])
        for invalid in ('{"q1":[0.3,0.3,0.3]}','{"q1":[-0.1,0.5,0.6]}','{"q1":[true,0,0]}'):
            with self.assertRaises(ValueError):decode(invalid,mapping,True)

    def test_real_background_never_builds_cloud_request(self):
        j={'human':True,'model':'pro','system':'synthetic test','user':'test'}
        with self.assertRaisesRegex(ValueError,'cloud request prohibited'):request_body(j)
        body=request_body({**j,'model':'qwen'})
        self.assertFalse(body['chat_template_kwargs']['enable_thinking'])
        self.assertNotIn('Authorization',str(body))

    def test_allocation_and_bootstrap_preserve_population_mass(self):
        masses={'a':.9,'b':.07,'c':.02,'d':.01}
        counts=allocations(masses,60)
        self.assertEqual(sum(counts.values()),60)
        self.assertGreaterEqual(min(counts.values()),1)
        groups=[k for k,n in counts.items() for _ in range(n)]
        weights=weighted_draws(groups,masses,'test')
        np.testing.assert_allclose(weights.sum(axis=1),1)
        for k,mass in masses.items():
            np.testing.assert_allclose(weights[:,[i for i,g in enumerate(groups) if g==k]].sum(axis=1),mass)

    def test_one_bad_repetition_prevents_adoption(self):
        gains=[4.,4.,-1.]
        errors={'old':np.full(2001,10.),'new':np.full(2001,10.-np.mean(gains))}
        runs={'old':[10.]*3,'new':[10.-x for x in gains]}
        self.assertFalse(contrast('old','new',errors,runs)['passes'])


if __name__=='__main__':unittest.main()
