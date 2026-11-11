import unittest
from ..adoption_summary import summarize,CONTRASTS

class AdoptionTests(unittest.TestCase):
    def fixture(self,kind,passed=True,ci=(.01,.03)):
        c={'relative_improvement':.03,'improvement':.02,'improvement_95_ci':list(ci),'passes_2_percent_gate':passed}
        return {'status':'complete_test_primary_brier_only','kind':kind,'calibration_llm_weight':0,'comparisons':{k:dict(c) for k in CONTRASTS}}
    def test_two_appliance_studies_never_become_broad_claim(self):
        result=summarize([self.fixture('dryer'),self.fixture('swiss')])
        for c in result['contrasts'].values():
            self.assertTrue(c['replicated_within_included_studies'])
            self.assertFalse(c['broad_cross_study_claim_allowed'])
    def test_regression_and_duplicate_study(self):
        result=summarize([self.fixture('dryer'),self.fixture('swiss',False,(-.03,-.01))])
        self.assertFalse(result['contrasts']['basic__to__rich']['replicated_within_included_studies'])
        with self.assertRaises(ValueError):summarize([self.fixture('dryer'),self.fixture('dryer')])
