"""Aggregate summary refuses incomplete evidence and never pools studies."""
import unittest,tempfile,json,sqlite3
from pathlib import Path
from ..aggregate_report import build,render

IDENTITY={'model':'deepseek-v4-pro','system_fingerprint':'x'}


def _checkpoint(path,rows):
    database=sqlite3.connect(path)
    database.execute('CREATE TABLE calls (job TEXT PRIMARY KEY, request_hash TEXT, status TEXT, reserved_usd REAL, response TEXT, error TEXT, elapsed REAL)')
    for index in range(rows):
        database.execute('INSERT INTO calls VALUES (?,?,?,?,?,?,?)',(f'j{index}','h','complete',0.5,
            json.dumps({'probabilities':[0.5,0.5],'identity':IDENTITY,'usage':{'prompt_tokens':10,'completion_tokens':2,'total_tokens':12}}),None,1.0))
    database.commit();database.close()


def _root(directory):
    formal=directory/'formal-v1';formal.mkdir(parents=True)
    (formal/'manifest.json').write_text(json.dumps({'units':[{'name':'rich_test','calls':2}]}))
    _checkpoint(formal/'rich_test.sqlite',2)
    synthetic=directory/'synthetic-formal-v1';synthetic.mkdir()
    (synthetic/'manifest.json').write_text(json.dumps({'people':1,'tasks_per_condition':2,'units':[{'name':'demographics'}]}))
    _checkpoint(synthetic/'demographics.sqlite',2)


def _individual(kind):
    interval={'improvement':0.01,'relative_improvement':0.03,'improvement_95_ci':[0.001,0.02],'passes_2_percent_gate':True}
    return {'status':'complete_test_primary_brier_only','kind':kind,
            'comparisons':{'basic__to__rich':interval,'statistics_rich__to__rich':interval,'rich__to__calibrated':interval},
            'calibration_llm_weight':0.0,'limitations':['no synthetic conclusion']}


def _population(kind):
    return {'status':'complete_population_distribution_analysis','kind':kind,'human_people':10,'synthetic_people':10,
            'methods':{'demographics':{'mean_tv_pp':10.0},'personality':{'mean_tv_pp':9.25},'shuffled':{'mean_tv_pp':9.5}},
            'primary_distribution_comparison':{'improvement_pp':0.75,'improvement_95_ci':None,'passes_2pp_gate':False,'replicates':2000},
            'property_comparisons':{'add_personality':{'lower_price':{'human_share':0.5,'candidate_prediction_share':0.55,
                                    'absolute_error_reduction_pp':1.5,'improvement_95_ci':[0.5,2.5]}}}}


class AggregateTests(unittest.TestCase):
    def test_single_scope_and_no_pooled_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);roots={}
            for kind in ['dryer','swiss']:
                roots[kind]=base/kind;_root(roots[kind])
            summary=build([_individual(k) for k in roots],[_population(k) for k in roots],roots)
            self.assertEqual(summary['independent_studies'],2)
            page=render(summary)
            self.assertIn('完成率 100.00%',page)
            self.assertIn('未给出可靠区间',page)
            self.assertIn('AI 权重为 0',page)
            self.assertIn('不是七次独立复现',page)

    def test_incomplete_unit_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);roots={}
            for kind in ['dryer','swiss']:
                roots[kind]=base/kind;_root(roots[kind])
            database=sqlite3.connect(roots['swiss']/'formal-v1/rich_test.sqlite')
            database.execute("DELETE FROM calls WHERE job='j1'");database.commit();database.close()
            with self.assertRaisesRegex(ValueError,'incomplete units'):
                build([_individual(k) for k in roots],[_population(k) for k in roots],roots)

    def test_duplicate_study_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);roots={}
            for kind in ['dryer','swiss']:
                roots[kind]=base/kind;_root(roots[kind])
            with self.assertRaisesRegex(ValueError,'not independent'):
                build([_individual('dryer'),_individual('dryer')],[_population('dryer'),_population('swiss')],roots)

    def test_unfinished_analysis_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);roots={}
            for kind in ['dryer','swiss']:
                roots[kind]=base/kind;_root(roots[kind])
            broken=_individual('dryer');broken['status']='partial'
            with self.assertRaisesRegex(ValueError,'Completed individual'):
                build([broken,_individual('swiss')],[_population(k) for k in roots],roots)
