"""Execute frozen population units only after a passed disjoint technical pilot."""
import json,os,argparse
from pathlib import Path
from .core import digest
from .runner import run

def execute(root,credentials):
    root=Path(root);directory=root/'synthetic-formal-v1';read=lambda p:json.loads(p.read_text())
    manifest=read(directory/'manifest.json');pilot=read(root/'synthetic-pilot-v1/result.json')
    if pilot['status']!='passed' or pilot['formal_people_overlap']!=0 or pilot['formal_manifest_sha256']!=digest(manifest):raise ValueError('Pilot gate not met')
    if read(directory/'protocol.json')!=read(Path(__file__).parent/'specs/formal/synthetic-protocol-v1.json'):raise ValueError('Protocol changed')
    os.environ['DEEPSEEK_API_KEY']=read(Path(credentials))['DEEPSEEK_API_KEY']
    for u in manifest['units']:
        name=u['name'];objects=[read(directory/(name+'-'+suffix+'.json')) for suffix in ['study','config','seal']]
        for suffix,obj in zip(['study','config','seal'],objects):
            if digest(obj)!=u[suffix+'_sha256']:raise ValueError('Frozen unit changed')
        result=run(objects[0],objects[2],objects[1],directory/(name+'.sqlite'),'test')
        print(json.dumps({'unit':name,**result}),flush=True)
        if result['stop_reason']:return
        if not result['complete']:raise RuntimeError('Unit incomplete')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--credentials',required=True);a=p.parse_args();execute(a.root,a.credentials)
