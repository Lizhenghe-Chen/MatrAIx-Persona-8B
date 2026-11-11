"""Evaluate complete frozen test units only after development calibration freezes."""
import argparse,json,os
from pathlib import Path
from .bundle_diagnostics import summarize as bundle_summary
from ..core.core import digest,split
from ..core.checkpoint import read_predictions
from .baseline_replay import replay
from ..core.calibration import apply
from .history_baseline import HistoricalProportions
from .scoring import paired_brier_interval,score
from .product_summary import summarize
from .subgroups import summarize as subgroup_summary
from .diagnostics import choice_diagnostics


def evaluate(directory,kind,calibration_path):
    root=Path(directory);formal=root/'formal-v1'
    read=lambda p:json.loads(p.read_text())
    prepared=read(root/'prepared.json');saved=read(root/'baseline-development.json')
    protocol=read(formal/'protocol.json');calibration=read(Path(calibration_path))
    if calibration['baseline_sha256']!=digest(saved) or calibration['protocol_sha256']!=digest(protocol):
        raise ValueError('Calibration provenance mismatch')
    # Reproduce development selection rather than trust an arbitrary parameter file.
    from .calibrate_study import calibrate
    if calibration!=calibrate(root,kind):raise ValueError('Calibration differs from frozen development selection')
    assignment=split(prepared['rows'])
    rows=[r for r in prepared['rows'] if assignment[r['person']]=='test']
    keys={(r['person'],r['task']) for r in rows}
    predictions={};provenance={};changed_people=set()
    for name in ['none','basic','rich','shuffled','single']:
        unit=name+'_test';study=read(formal/(unit+'-study.json'))
        config=read(formal/(unit+'-config.json'));seal=read(formal/(unit+'-seal.json'))
        observed,p,missing=read_predictions(study,seal,config,formal/(unit+'.sqlite'),'test')
        if set(p)!=keys:raise ValueError('Test cohorts differ')
        reference={(r['person'],r['task']):r for r in rows}
        for r in observed:
            original=reference[(r['person'],r['task'])]
            if name=='shuffled':
                basic=protocol['backgrounds']['basic']
                additional=[f for f in protocol['backgrounds']['rich'] if f not in basic]
                if any(r['background'].get(f,'unknown')!=original['background'].get(f,'unknown') for f in basic):
                    raise ValueError('Shuffling changed basic background')
                if any(r['background'].get(f,'unknown')!=original['background'].get(f,'unknown') for f in additional):
                    changed_people.add(r['person'])
            for field in ['options','answer','question','context','stratum']:
                if r[field]!=original[field]:raise ValueError('Test task mapping differs')
        predictions[name]=p
        provenance[name]={'seal_sha256':digest(seal),'complete_tasks':len(p),'missing_tasks':len(missing)}
    for arm in ['none','basic','rich']:
        predictions['statistics_'+arm]=replay(prepared,saved,rows,kind,arm)
    predictions['uniform']={k:[1/len(r['options'])]*len(r['options']) for r in rows for k in [(r['person'],r['task'])]}
    train=[r for r in prepared['rows'] if assignment[r['person']]=='train']
    predictions['history'],support=HistoricalProportions().fit(train).predict(rows)
    predictions['calibrated']={k:apply(predictions['rich'][k],predictions['statistics_rich'][k],calibration['selection']) for k in keys}
    predictions['probability_argmax']={}
    for k,p in predictions['rich'].items():
        index=max(range(len(p)),key=p.__getitem__)
        predictions['probability_argmax'][k]=[int(i==index) for i in range(len(p))]
    card_rows=[{**r,'score_group':r.get('score_group',r.get('group'))} for r in rows]
    per_card={name:score(card_rows,p)['groups'] for name,p in predictions.items()}
    summaries={}
    for name,p in predictions.items():
        result=paired_brier_interval(rows,p,p,repeats=1)
        summaries[name]={'brier':result['reference_brier'],'people':result['people'],'tasks':result['tasks']}
    contrasts=[('none','basic'),('basic','rich'),('shuffled','rich'),('single','rich'),
               ('probability_argmax','rich'),('statistics_rich','rich'),('rich','calibrated'),('statistics_rich','calibrated')]
    comparisons={a+'__to__'+b:paired_brier_interval(rows,predictions[a],predictions[b]) for a,b in contrasts}
    changed_rows=[r for r in rows if r['person'] in changed_people]
    shuffle_diagnostic={'changed_people':len(changed_people),'unchanged_people':len({r['person'] for r in rows})-len(changed_people),
                        'interpretation':'Actual changed content only; descriptive diagnostic, not a new primary cohort.'}
    if changed_rows:
        shuffle_diagnostic['comparison']=paired_brier_interval(changed_rows,predictions['shuffled'],predictions['rich'])
    return {'status':'complete_test_primary_brier_only','kind':kind,'prepared_sha256':digest(prepared),
            'calibration_sha256':digest(calibration),'units':provenance,'methods':summaries,'comparisons':comparisons,'per_card':per_card,
            'bundle_repetition':{'human':bundle_summary(rows),**{name:bundle_summary([{k:v for k,v in r.items() if k!='answer'} for r in rows],p) for name,p in predictions.items()}},
            'choice_diagnostics':{name:choice_diagnostics(card_rows,p) for name,p in predictions.items()},
            'product_choice_shares':{name:summarize(rows,p,kind) for name,p in predictions.items()},
            'subgroups':{name:subgroup_summary(rows,p,protocol['backgrounds']['basic']) for name,p in predictions.items()},
            'history_unseen_tasks':sum(n==0 for n in support.values()),
            'calibration_llm_weight':calibration['selection']['llm_weight'],
            'shuffle_changed_content_diagnostic':shuffle_diagnostic,
            'limitations':['This file is the primary individual-prediction analysis, not the full report.',
                          'Single-choice and argmax are point predictions; their Brier scores also measure lost uncertainty.',
                          'No synthetic-persona or cross-study conclusion follows from this file.']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--kind',choices=['dryer','swiss'],required=True)
    p.add_argument('--calibration',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Do not overwrite frozen test analysis')
    result=evaluate(a.directory,a.kind,a.calibration)
    fd=os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'status':result['status'],'methods':result['methods']}))
