"""Aggregate-only audit of the packed release; no profiles exported."""
import argparse,json,hashlib
from collections import Counter
from pathlib import Path
import pyarrow.parquet as pq


def audit(root):
    root=Path(root);manifest=json.loads((root/'manifest.json').read_text())
    columns=json.loads((root/'persona_codes.schema.json').read_text())['columns']
    wanted=['region','age_bracket','highest_education','risk_tolerance','decision_style']
    lookup={c['id']:(i,c) for i,c in enumerate(columns) if c['id'] in wanted}
    sources=Counter();cells=Counter();files=[];missing=Counter()
    for entry in manifest['files']:
        path=root/entry['path'];f=pq.ParquetFile(path)
        files.append({'path':entry['path'],'footer_rows':f.metadata.num_rows,'bytes':path.stat().st_size,
                      'manifest_rows_match':f.metadata.num_rows==entry['rows'],
                      'manifest_bytes_match':path.stat().st_size==entry['bytes']})
        for batch in f.iter_batches(batch_size=8192,columns=['source','attributes','null_bitmap','attribute_overrides']):
            for row in batch.to_pylist():
                sources[row['source']]+=1
                if row['source']!='synthetic':continue
                overrides=row['attribute_overrides'] or {}
                if isinstance(overrides,str):overrides=json.loads(overrides)
                if isinstance(overrides,list):overrides=dict(overrides)
                decoded={}
                for name,(i,col) in lookup.items():
                    if name in overrides:decoded[name]=overrides[name];continue
                    bitmap=row['null_bitmap']
                    if bitmap is not None and (bitmap[i//8]>>(i%8))&1:
                        missing[name]+=1;decoded[name]='unknown';continue
                    code=(row['attributes'][i//2]>>(4*(i%2)))&15
                    decoded[name]=col['values'][code] if code<len(col['values']) else 'invalid_code'
                cells[(decoded['region'],decoded['age_bracket'],decoded['highest_education'])]+=1
    return {'release_manifest_sha256':hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest(),
            'files':files,'sources':dict(sources),'actual_rows':sum(sources.values()),
            'manifest_source_counts_match':dict(sources)==manifest['sources'],
            'synthetic_joint_cells':[{'region':r,'age_bracket':a,'highest_education':e,'rows':n} for (r,a,e),n in sorted(cells.items())],
            'synthetic_missing_fields':dict(missing),
            'limits':['Footer and file-size validation is not a full shard hash check.',
                      'Human-grounded attributes are not necessarily directly measured.',
                      'Synthetic records are generated, not observed respondents.',
                      'Region is not country; do not infer American or Swiss residency.']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.root);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'rows':result['actual_rows'],'sources':result['sources'],'manifest_match':result['manifest_source_counts_match']}))
