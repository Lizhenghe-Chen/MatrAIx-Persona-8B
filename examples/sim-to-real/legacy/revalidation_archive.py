"""Archive synthetic answers only; reproduce their scores without private inputs."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3

import numpy as np

from revalidation import OUT, LOCAL, read, write, digest, jobs, key, request_body
from revalidation_score import matching


def archive():
    data=read(LOCAL/'freeze.json')
    expected={phase:{key(j):j for j in jobs(data,phase)} for phase in ('pilot','formal')}
    rows=[];counts={};attempts=0
    with sqlite3.connect(LOCAL/'responses.sqlite') as db:
        for phase in expected:
            saved=db.execute('SELECT job,output,request_hash,errors FROM responses WHERE phase=?',(phase,)).fetchall()
            assert len(saved)==len(expected[phase])
            counts[phase]=len(saved)
            for job,raw,request_hash,errors in saved:
                j=expected[phase][job]
                assert raw is not None
                assert request_hash==hashlib.sha256(json.dumps(request_body(j),sort_keys=True).encode()).hexdigest()
                attempts+=len(json.loads(errors))
                if j['task']=='matching':
                    rows.append({'phase':phase,'model':j['model'],'arm':j['arm'],'repetition':j['repeat'],
                                 'synthetic_slot':j['id'],'output':json.loads(raw),
                                 'request_sha256':request_hash,'errors':json.loads(errors)})
    # Explicit allow-list: no product records, respondent IDs or individual answers.
    public={k:data[k] for k in ('seed','repeats','questions','options','reference')}
    write(OUT/'matching-reference.json',public)
    content=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in sorted(rows,key=lambda r:(r['phase'],r['model'],r['arm'],r['repetition'],r['synthetic_slot'])))
    (OUT/'synthetic-responses.jsonl.gz').write_bytes(gzip.compress(content.encode(),mtime=0))
    write(OUT/'completion-checks.json',{'valid':counts,'all_frozen_request_hashes_match':True,
          'recorded_error_attempts':attempts,'all_valid_answers_archived_or_kept_locally':True,
          'synthetic_archive_rows':len(rows),'product_answers':'Private local checkpoint only',
          'input_freeze_sha256':digest(LOCAL/'freeze.json'),
          'response_checkpoint_sha256':digest(LOCAL/'responses.sqlite'),
          'synthetic_archive_sha256':digest(OUT/'synthetic-responses.jsonl.gz')})
    print(json.dumps({'valid':counts,'archived_synthetic_rows':len(rows),'failed_attempts':attempts}))


def check():
    data=read(OUT/'matching-reference.json');data['cohorts']=read(OUT/'synthetic-cohorts.json')
    predictions={}
    for line in gzip.decompress((OUT/'synthetic-responses.jsonl.gz').read_bytes()).decode().splitlines():
        row=json.loads(line)
        if row['phase']=='formal':
            predictions['matching',row['model'],row['arm'],row['repetition'],row['synthetic_slot']]=row['output']
    actual=matching(data,predictions,['qwen','pro']);expected=read(OUT/'results.json')['matching']
    def compare(a,b,path='matching'):
        if isinstance(a,dict):
            assert a.keys()==b.keys(),path
            for k in a:compare(a[k],b[k],path+'/'+k)
        elif isinstance(a,list):
            assert len(a)==len(b),path
            for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+'/'+str(i))
        elif isinstance(a,(float,int)) and not isinstance(a,bool):
            assert np.isclose(a,b,rtol=0,atol=1e-10),(path,a,b)
        else:assert a==b,(path,a,b)
    compare(actual,expected)
    print('All synthetic matching results reproduced from Git-portable inputs; no private respondent data used.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['archive','check']);a=p.parse_args()
    archive() if a.action=='archive' else check()
