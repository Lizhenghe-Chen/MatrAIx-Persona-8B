"""Publish aggregate readiness evidence without inspecting test outcomes."""
import argparse
import json
from pathlib import Path
from ..core.conditions import shuffled_background
from ..core.core import split,digest


def summarize(directory):
    directory=Path(directory)
    doc=json.loads((directory/'prepared.json').read_text())
    baseline=json.loads((directory/'baseline-development.json').read_text())
    if baseline['source_sha256']!=digest(doc):raise ValueError('Baseline input changed')
    assignments=split(doc['rows'])
    _,audit=shuffled_background(doc['rows'],['age_band','education'],['weekly_dryer_use','household_size'],assignments)
    coverage={}
    for phase in ['train','development','test']:
        ids={p for p,s in assignments.items() if s==phase}
        coverage[phase]={'people':len(ids),'singleton_people':len(ids & set(audit['unshuffled_singletons'])),
                         'content_changed_people':len(ids & set(audit['content_changed_people']))}
    result={'status':'development_and_input_diagnostics_only','test_outcomes_scored':False,
            'input_sha256':digest(doc),'background_shuffle_coverage':coverage,
            'development_baselines':{k:{f:v[f] for f in ['penalty','development_brier','feature_count','background_fields']} for k,v in baseline['baselines'].items()},
            'interpretation':['Development-set differences are not formal evidence or AI results.',
                              'Report full-cohort shuffled arm and actual-content-changed subset separately; use paired comparisons on the same subset.',
                              'Singletons and equal-valued donor blocks are not active information perturbations.',
                              'Do not use these target-development scores to select cold-start prompts.'],
            'formal_scale_estimate':{'test_people':coverage['test']['people'],'tasks_per_person':8,
                                     'calls_per_full_test_arm':coverage['test']['people']*8,
                                     'five_arm_test_calls':coverage['test']['people']*8*5,
                                     'note':'Planning count only; formal protocol and cost caps still require freezing.'}}
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.write_text(json.dumps(summarize(a.directory),ensure_ascii=False,indent=2)+'\n')
