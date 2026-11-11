"""Population report must not import another study's wording."""
import unittest
from ..reporting.population_report import render

CARD={'options':['A','B'],'human':[0.5,0.5],'model':[0.6,0.4],'tv_pp':10.0,'people':30,'small_group':False}


def _analysis(kind):
    method={'mean_tv_pp':10.0,'cards':[CARD]}
    shares={'lower_price':{'share':0.5,'people':30,'eligible_tasks':60}}
    return {'status':'complete_population_distribution_analysis','kind':kind,'human_people':30,'synthetic_people':30,
            'individual_accuracy_computed':False,'methods':{k:dict(method) for k in ['demographics','personality','shuffled']},
            'primary_distribution_comparison':{'improvement_pp':0.5,'improvement_95_ci':[0.1,0.9],'passes_2pp_gate':False,'replicates':2000},
            'property_choices':{k:shares for k in ['human','demographics','personality','shuffled']},
            'property_comparisons':{},'subgroups':{},
            'bundle_repetition':{'human':{'fraction_sharing_complete_pattern':None,'comparable_people':0,'incomparable_people':30}},
            'concentration':{}}


class PopulationReportTests(unittest.TestCase):
    def test_swiss_only_note_stays_out_of_dryer_report(self):
        self.assertNotIn('瑞士家电的这一汇总',render(_analysis('dryer')))
        self.assertIn('瑞士家电的这一汇总',render(_analysis('swiss')))

    def test_empty_interval_is_reported_as_uncertified(self):
        data=_analysis('dryer');data['primary_distribution_comparison']={'improvement_pp':0.5,'improvement_95_ci':None,'passes_2pp_gate':False,'replicates':2000}
        self.assertIn('未给出可靠区间',render(data))

    def test_individual_pairing_is_refused(self):
        data=_analysis('dryer');data['individual_accuracy_computed']=True
        with self.assertRaises(ValueError):render(data)
