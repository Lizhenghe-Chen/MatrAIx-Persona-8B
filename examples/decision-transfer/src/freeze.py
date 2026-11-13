"""Read-only historical snapshot. Manifests never overwrite an earlier freeze."""
import argparse, hashlib, json, os, subprocess, tarfile, gzip
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
HERE=Path(__file__).resolve().parents[1]
REPO=HERE.parents[1]
OLD=REPO/'examples/sim-to-real'
PRIVATE=Path.home()/'.local/share/matraix-decision-lab'
SNAP=Path.home()/'.local/share/matraix-decision-transfer/frozen/2026-11-13-v1'
DATA=Path(os.environ.get('MATRAIX_DATA_ROOT','/Volumes/元宇宙联合创新实验室/实验数据/MatrAIx多地区选品源数据'))
SKIP={'__pycache__','.git','.DS_Store'}
def files(root):
 return sorted(p for p in root.rglob('*') if (p.is_file() or p.is_symlink()) and not any(x in SKIP for x in p.relative_to(root).parts) and not p.name.startswith('._'))
def row(root,p):
 before=p.lstat()
 if p.is_symlink():
  target=os.readlink(p);payload=target.encode();kind='symlink';digest=hashlib.sha256(payload).hexdigest();size=len(payload)
 else:
  kind='file';target=None;size=before.st_size
  with p.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
 after=p.lstat()
 if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise RuntimeError('File changed while hashing')
 return {'path':p.relative_to(root).as_posix(),'kind':kind,'bytes':size,'sha256':digest,**({'target':target} if target else {})}
def scan(root):
 with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(lambda p:row(root,p),files(root)))
def write(p,data):
 with p.open('x') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
def create():
 public=HERE/'archive/frozen-history.json'
 if public.exists() or SNAP.exists():raise RuntimeError('Freeze exists; verify or choose a new version, never overwrite')
 if subprocess.check_output(['git','status','--porcelain','--','examples/sim-to-real'],cwd=REPO,text=True).strip():raise RuntimeError('Old tree has uncommitted changes')
 for root in [OLD,PRIVATE,DATA]:
  if not root.is_dir():raise RuntimeError('Required storage missing')
 SNAP.mkdir(parents=True,mode=0o700);SNAP.chmod(0o700)
 manifests={};summary={}
 for name,root in [('historical_tree',OLD),('private_runs',PRIVATE),('shared_sources',DATA)]:
  print('Hashing',name,flush=True);items=scan(root);path=SNAP/(name+'.json');write(path,{'root':str(root),'files':items});path.chmod(0o600)
  manifests[name]=items;summary[name]={'file_count':len(items),'bytes':sum(x['bytes'] for x in items),'manifest_sha256':row(SNAP,path)['sha256']}
  print(name,summary[name]['file_count'],'files verified',flush=True)
 tracked=set(subprocess.check_output(['git','ls-files','-z','--','examples/sim-to-real'],cwd=REPO).decode().split('\0'))
 public_files=[r for r in manifests['historical_tree'] if 'examples/sim-to-real/'+r['path'] in tracked]
 # Reconstruct tracked code/report from Git; preserve only untracked old assets plus local runs in backup.
 bundle=SNAP/'local-evidence.tar.gz'
 print('Backing up local-only evidence',flush=True)
 with bundle.open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=3,mtime=0) as zipped,tarfile.open(fileobj=zipped,mode='w|') as tar:
  for name,root in [('historical_tree',OLD),('private_runs',PRIVATE)]:
   for r in manifests[name]:
    if name=='historical_tree' and 'examples/sim-to-real/'+r['path'] in tracked:continue
    tar.add(root/r['path'],arcname=name+'/'+r['path'],recursive=False)
 bundle.chmod(0o600)
 # Verify the recovery copy by content, not only archive readability.
 expected={name+'/'+r['path']:r for name in ['historical_tree','private_runs'] for r in manifests[name] if not(name=='historical_tree' and 'examples/sim-to-real/'+r['path'] in tracked)}
 with tarfile.open(bundle,'r:gz') as tar:
  seen=set()
  for member in tar:
   r=expected[member.name];seen.add(member.name)
   if member.issym():digest=hashlib.sha256(member.linkname.encode()).hexdigest()
   else:
    with tar.extractfile(member) as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
   if digest!=r['sha256']:raise RuntimeError('Recovery backup mismatch: '+member.name)
  if seen!=set(expected):raise RuntimeError('Recovery backup incomplete')
 commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
 write(public,{'version':'2026-11-13-v1','date':'2026-11-13','status':'content_frozen_not_scientific_reendorsement','historical_commit':commit,'historical_root':'examples/sim-to-real','git_tag':'experiments-frozen-2026-11-13-v1','tracked_files':public_files,'local_manifest_location':str(SNAP),'storage':summary,'recovery_bundle':{'bytes':bundle.stat().st_size,'sha256':row(SNAP,bundle)['sha256'],'members_verified':len(expected)},'policy':['Do not rewrite historical reports or checkpoints. New work stays in examples/decision-transfer.','Shared raw sources retained in place and hashed, not duplicated or deleted.','Local recovery bundle is on the same machine; this is not an off-site disaster backup.','Corrections must be new errata, not silent edits.']})
 print('Frozen manifest created; recovery verified',flush=True)
def verify(local=False):
 spec=json.loads((HERE/'archive/frozen-history.json').read_text())
 for r in spec['tracked_files']:
  if row(OLD,OLD/r['path'])!=r:raise RuntimeError('Historical tracked file changed: '+r['path'])
 if local:
  for name in spec['storage']:
   path=SNAP/(name+'.json')
   if row(SNAP,path)['sha256']!=spec['storage'][name]['manifest_sha256']:raise RuntimeError('Manifest changed')
   saved=json.loads(path.read_text());current=scan(Path(saved['root']))
   if current!=saved['files']:raise RuntimeError('Storage drift: '+name)
  b=SNAP/'local-evidence.tar.gz'
  if row(SNAP,b)['sha256']!=spec['recovery_bundle']['sha256']:raise RuntimeError('Backup changed')
 print('PASS: frozen evidence unchanged'+(' including private runs and shared originals' if local else ' (tracked files only)'),flush=True)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('action',choices=['create','verify']);a.add_argument('--local',action='store_true');args=a.parse_args()
 create() if args.action=='create' else verify(args.local)
