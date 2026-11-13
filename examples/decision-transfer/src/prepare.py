"""Copy public references and inspect candidate structure; no model/choice scoring."""
import csv, hashlib, json, shutil, os
from pathlib import Path
import pyreadr
from freeze import HERE, OLD, DATA

def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 out=HERE/'data/reference/provenance.json'
 if out.exists():raise RuntimeError('Reference snapshot exists; do not overwrite')
 refs=['reports/evidence.json','decision_lab/reports/cross-study-v1/cluster-summary.json','decision_lab/reports/cross-study-v1/external-v2-results.json','decision_lab/specs/audits/swiss-six-audit.json']
 provenance=[]
 for relative in refs:
  source=OLD/relative;dest=HERE/'data/reference'/source.name
  if dest.exists():raise RuntimeError('Destination already exists')
  shutil.copyfile(source,dest)
  assert digest(source)==digest(dest)
  provenance.append({'source':'examples/sim-to-real/'+relative,'copy':str(dest.relative_to(HERE)),'sha256':digest(dest),'role':'historical_reference_only_not_new_evaluation'})
 out.write_text(json.dumps({'historical_commit':json.loads((HERE/'archive/frozen-history.json').read_text())['historical_commit'],'files':provenance},ensure_ascii=False,indent=2)+'\n')
 origin=DATA/'06_历史北美电商/origin-original.tab'
 with origin.open(newline='') as f:cols=next(csv.reader(f,delimiter='\t'))
 p=DATA/'02_瑞士六品类/w14_conjoint.RData';df=pyreadr.read_r(p)['dfconj'];valid=df.dropna(subset=['PubId','round','choice','product'])
 catalog={'status':'structural_audit_only_not_admission','date':'2026-11-13','target_answers_used_for_selection':False,'model_calls':0,
 'data_root_env':'MATRAIX_DATA_ROOT','candidates':[
 {'id':'origin','title':'美国商品产地','role':'historical_development_only','source':'06_历史北美电商/origin-original.tab','sha256':digest(origin),'columns':cols,
 'potential_facts':['age','educ','gender','inc','q11_1_w1–q11_6_w1'],
 'pending':['Verify exact original labels and pre-choice timing.','Do not treat income as budget or cultural-attitude scores as universal purchase constraints.','Observed earlier experiment outcomes prohibit a fresh independent-validation claim.'],'admitted':False},
 {'id':'swiss_six','title':'瑞士六品类','role':'cross_category_candidate_same_panel_not_independent_country_replication','source':'02_瑞士六品类/w14_conjoint.RData','sha256':digest(p),
 'people':int(valid.PubId.nunique()),'tasks':int(valid.groupby(['PubId','round']).ngroups),'categories':sorted(map(str,valid['product'].unique())),
 'categories_per_person':{str(k):int(v) for k,v in valid.groupby('PubId')['product'].nunique().value_counts().items()},
 'potential_facts':['age','educ','inc','envcon','envbeh','cfc'],
 'prohibited_until_proven_safe':['choice','rating','green_*','intention_tpb','choice-derived attitude scores'],
 'pending':['Original instructions, price units and field labels.','Measurement timing and target-answer derivation for all proposed preference fields.','Shared wave8/wave14 IDs and global person-level split.','Each person sees two categories, not all six.','SEP_w14_reduced.RData dataframe conversion currently fails in pyreadr; do not infer unjoined fields.'],
 'admitted':False}],
 'independent_validation':'No new independently qualified validation dataset frozen yet; do not rename old test data as new.',
 'raw_copy_policy':'Raw human records remain in shared storage or local private stage directory; no raw copy made in Git.'}
 (HERE/'data/candidates.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
 print('Copied',len(refs),'small reference files; Swiss candidate:',catalog['candidates'][1]['people'],'people, two categories each. No target effects scored.')
if __name__=='__main__':main()
