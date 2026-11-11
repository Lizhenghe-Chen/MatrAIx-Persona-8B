"""Export aggregate execution evidence, never targets, choices or respondent IDs."""
import argparse
import json
import sqlite3
from pathlib import Path
from ..core.checkpoint import read_predictions


def summarize(directory):
    directory=Path(directory)
    study=json.loads((directory/'study.json').read_text())
    expected=len(study['rows'])
    expected_conditions={p.name.removesuffix('-config.json') for p in directory.glob('*-config.json')}
    results={}
    for path in sorted(Path(directory).glob('*.sqlite')):
        db=sqlite3.connect(f'file:{path}?mode=ro',uri=True)
        records=db.execute('SELECT status,response,elapsed,reserved_usd FROM calls').fetchall();db.close()
        complete=[json.loads(r[1]) for r in records if r[0]=='complete']
        config=json.loads((directory/(path.stem+'-config.json')).read_text())
        seal=json.loads((directory/(path.stem+'-seal.json')).read_text())
        read_predictions(study,seal,config,path,'train',require_complete=False)
        results[path.stem]={'completed':len(complete),'failed':sum(r[0]=='failed' for r in records),
                           'pending':sum(r[0]=='pending' for r in records),
                           'identities':[json.loads(v) for v in sorted({json.dumps(r['identity'],sort_keys=True) for r in complete})],
                           'prompt_tokens':sum(r['usage'].get('prompt_tokens',0) for r in complete),
                           'completion_tokens':sum(r['usage'].get('completion_tokens',0) for r in complete),
                           'total_call_seconds':sum(r[2] or 0 for r in records),
                           'reserved_cost_usd':sum(r[3] for r in records)}
    return {'purpose':'Technical validity only; no prediction score calculated',
            'expected_people':len({r['person'] for r in study['rows']}),'expected_calls':expected*len(expected_conditions),
            'passed':set(results)==expected_conditions and all(r['completed']==expected and r['failed']==0 and r['pending']==0 for r in results.values()),
            'conditions':results,'cost_note':'Reserved cost is a conservative cap, not actual billing.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=summarize(a.directory)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'completed':sum(x['completed'] for x in result['conditions'].values())}))
