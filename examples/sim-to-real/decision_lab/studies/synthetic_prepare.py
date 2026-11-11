"""Freeze three population execution inputs, with no fabricated target answers."""
import json,copy,os,argparse
from pathlib import Path
from ..core.core import digest,validate
from ..core.conditions import shuffled_background
from .dryer_pilot import private_write

BASIC=['age_bracket','education_group']
TRAITS=['decision_style','risk_tolerance','values_priority','bfi2_domain_conscientiousness']

def prepare(root):
    root=Path(root);design=json.loads((root/'synthetic-tasks-v1.json').read_text())
    formal=root/'formal-v1';source=json.loads((formal/'rich_test-study.json').read_text())
    config=json.loads((formal/'rich_test-config.json').read_text())
    if design['prepared_sha256']!=digest(json.loads((root/'prepared.json').read_text())):raise ValueError('Source changed')
    rows=[]
    for r in design['rows']:
        rows.append({'person':r['synthetic_id'],'task':r['task'],'stratum':r['stratum'],'question':r['question'],
                     'context':r['context'],'options':r['options'],'group':r['score_group'],
                     'background':{**r['background'],**r['generated_personality']}})
    validate(rows,require_answers=False)
    assignments={r['person']:'test' for r in rows}
    shuffled,diagnostic=shuffled_background(rows,BASIC,TRAITS,assignments)
    output=root/'synthetic-formal-v1';output.mkdir(exist_ok=False);os.chmod(output,0o700)
    manifest={'design_sha256':digest(design),'people':len(assignments),'tasks_per_condition':len(rows),
              'maximum_calls':3*len(rows),'maximum_reserved_usd':120,
              'status':'frozen_inputs_pending_technical_pilot','units':[],
              'interpretation':'No individual truth. Evaluate group distributions only. Within-cell permutation preserves trait margins and tests task-allocation sensitivity, not measured personality alignment.'}
    private_write(output/'shuffle-map.json',diagnostic)
    for name,fields,input_rows in [('demographics',BASIC,rows),('personality',BASIC+TRAITS,rows),('shuffled',BASIC+TRAITS,shuffled)]:
        study={'rows':input_rows,'evaluation_mode':'synthetic_population','person_source':'generated',
               'audit':copy.deepcopy(source['audit']),'audit_evidence':source.get('audit_evidence'),
               'synthetic_design_sha256':digest(design)}
        cfg={**config,'background_fields':fields,'max_calls':len(rows),'max_cost_usd':40}
        seal={'input_sha256':digest(study),'config_sha256':digest(cfg),'assignments':assignments,'seed':20261109}
        for suffix,value in [('study',study),('config',cfg),('seal',seal)]:private_write(output/(name+'-'+suffix+'.json'),value)
        manifest['units'].append({'name':name,'study_sha256':digest(study),'config_sha256':digest(cfg),'seal_sha256':digest(seal)})
    private_write(output/'manifest.json',manifest)
    # Preserve the user's established overnight cutoff for this execution family.
    if (formal/'run-control.json').exists():private_write(output/'run-control.json',json.loads((formal/'run-control.json').read_text()))
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args();print(json.dumps(prepare(a.root)))
