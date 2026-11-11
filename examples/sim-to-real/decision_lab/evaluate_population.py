"""Separate-population evaluation with fixed eligible human reference."""
import argparse,json,os
from pathlib import Path
from .core import digest,split
from .checkpoint import read_predictions
from .persona_mapping import common_background
from .property_intervals import compare as property_intervals
from .product_summary import population_properties
from .population_scoring import distribution_comparison,paired_population_interval


def evaluate(root,kind):
    root=Path(root);read=lambda p:json.loads(p.read_text());formal=root/'synthetic-formal-v1'
    prepared=read(root/'prepared.json');design=read(root/'synthetic-tasks-v1.json')
    if design['prepared_sha256']!=digest(prepared):raise ValueError('Human reference changed')
    assignment=split(prepared['rows'])
    human=[]
    for r in prepared['rows']:
        if assignment[r['person']]!='test':continue
        bg=common_background(r['background'],kind)
        if bg is not None:human.append({**r,'background':bg})
    manifest=read(formal/'manifest.json');protocol=read(formal/'protocol.json')
    if manifest['design_sha256']!=digest(design):raise ValueError('Synthetic design changed')
    if protocol!=read(Path(__file__).parent/'synthetic-protocol-v1.json'):raise ValueError('Protocol differs')
    predictions={};synthetic=None
    for unit in manifest['units']:
        name=unit['name'];study=read(formal/(name+'-study.json'));seal=read(formal/(name+'-seal.json'));cfg=read(formal/(name+'-config.json'))
        for key,obj in [('study',study),('seal',seal),('config',cfg)]:
            if digest(obj)!=unit[key+'_sha256']:raise ValueError('Manifest mismatch')
        rows,p,missing=read_predictions(study,seal,cfg,formal/(name+'.sqlite'),'test')
        if synthetic is None:synthetic=rows
        else:
            canonical=lambda rs:{(r['person'],r['task']):(r['stratum'],r['question'],r['context'],r['options'],{k:r['background'][k] for k in ['age_bracket','education_group']}) for r in rs}
            if canonical(rows)!=canonical(synthetic):raise ValueError('Condition exposures differ')
        predictions[name]=p
    results={name:distribution_comparison(human,synthetic,p) for name,p in predictions.items()}
    subgroup={}
    for field in ['age_bracket','education_group']:
        subgroup[field]={}
        for value in sorted({r['background'][field] for r in human}):
            h=[r for r in human if r['background'][field]==value];s=[r for r in synthetic if r['background'][field]==value]
            keys={(r['person'],r['task']) for r in s}
            subgroup[field][value]={name:distribution_comparison(h,s,{k:v for k,v in p.items() if k in keys}) for name,p in predictions.items()}
    comparison=paired_population_interval(human,synthetic,predictions['demographics'],predictions['personality']) if kind=='dryer' else None
    return {'status':'complete_population_distribution_analysis','kind':kind,'protocol_sha256':digest(protocol),
            'manifest_sha256':digest(manifest),'human_people':len({r['person'] for r in human}),
            'synthetic_people':len({r['person'] for r in synthetic}),'individual_accuracy_computed':False,
            'methods':results,'subgroups':subgroup,'primary_distribution_comparison':comparison,
            'property_comparisons':{label:property_intervals(human,synthetic,predictions[left],predictions['personality'],kind) for label,left in [('add_personality','demographics'),('shuffle_diagnostic','shuffled')]},
            'property_choices':{'human':population_properties(human,kind),**{name:population_properties(synthetic,kind,p) for name,p in predictions.items()}},
            'limits':'Swiss card distributions are descriptive only; Property-choice intervals keep the human reference fixed; no combined adoption claim is generated for them. This file alone is not the full population report.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--kind',choices=['dryer','swiss'],required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Do not overwrite population analysis')
    result=evaluate(a.root,a.kind);fd=os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'status':result['status'],'human_people':result['human_people'],'synthetic_people':result['synthetic_people']}))
