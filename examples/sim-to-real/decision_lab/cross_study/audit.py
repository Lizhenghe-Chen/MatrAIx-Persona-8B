"""Reproducible read-only source inventory and native-runtime snapshot."""
import csv,gzip,hashlib,json,subprocess,zipfile
from pathlib import Path
from .registry import ROWS,DATA,OUT,SPEC,ROOT

def sha(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def inspect(path):
 result={'path':str(path.relative_to(DATA)),'exists':path.is_file()}
 if not path.is_file():return result
 result.update(bytes=path.stat().st_size,sha256=sha(path))
 name=path.name.lower()
 try:
  if name.endswith('.zip'):
   with zipfile.ZipFile(path) as z:result['members']=[{'name':x.filename,'bytes':x.file_size} for x in z.infolist() if not x.is_dir()]
  elif name.endswith(('.csv','.tab','.csv.gz')):
   op=gzip.open if name.endswith('.gz') else open
   with op(path,'rt',encoding='utf-8-sig',errors='replace',newline='') as f:
    result['columns']=next(csv.reader(f,delimiter='\t' if name.endswith('.tab') else ','))
  elif name.endswith(('.xlsx','.xlsm')):
   import openpyxl
   b=openpyxl.load_workbook(path,read_only=True,data_only=True,keep_links=False)
   result['sheets']=[{'name':s.title,'rows':s.max_row,'columns':s.max_column} for s in b];b.close()
  elif name.endswith(('.sav','.dta')):
   import pyreadstat
   _,m=(pyreadstat.read_sav if name.endswith('.sav') else pyreadstat.read_dta)(path,metadataonly=True)
   result['rows']=m.number_rows;result['columns']=m.column_names
  result['read_status']='metadata_readable'
 except Exception as e:result['read_status']='metadata_error';result['error_type']=type(e).__name__
 return result

NATIVE=[
'environment/agents/matraix/agents/persona/json_survey.py',
'packages/playground/src/playground/inprocess/survey_eval.py',
'packages/playground/src/playground/user_sim/prompt.py',
'application/playground/backend/service/survey_instruction_builder.py',
'application/playground/backend/service/survey_types.py',
'environment/agents/matraix/agents/persona/templates/persona_system.md.j2',
'environment/agents/matraix/agents/persona/templates/persona_macros.md.j2',
'environment/agents/matraix/agents/persona/templating.py',
'src/matraix/persona_dimension_catalog.py']

def main():
 repo=ROOT.parents[2];OUT.mkdir(parents=True,exist_ok=True);SPEC.mkdir(parents=True,exist_ok=True)
 studies=[]
 for ident,name,tier,files,task,gap in ROWS:
  row={'id':ident,'name':name,'evidence_tier':tier,'task_scope':task,'admission':'pending_current_protocol_checks','outstanding':gap,'files':[inspect(DATA/p) for p in files],
       'approved_for_cloud_run':False,'participants_frozen':False,'budget_approved':False}
  studies.append(row);print('Inspected',ident,'files',len(files),flush=True)
 payload={'status':'inventory_not_admission','studies':studies,'counts':{'historical':sum(s['evidence_tier']=='historical' for s in studies),'external_candidates':sum(s['evidence_tier']=='external_candidate' for s in studies)},'notes':['No target outcome scores computed.','No raw respondent rows exported. File readability does not prove task recoverability or admissibility.']}
 (OUT/'source-inventory.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
 snapshot={'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),'files':[{'path':p,'sha256':sha(repo/p)} for p in NATIVE],
 'native_request':'system=render_persona_block; user=build_survey_task_prompt; one instrument per complete_json call',
 'native_failure_behavior':'_normalize_answers fills missing required items; _normalize_value replaces invalid single choices with first option',
 'required_adaptation':'Strict raw-response validation in ALL arms. Never silently fill or clip. Native prompt reference, not full production behavior.',
 'persona_rendering':'Native dimension narrative; no implicit fallback allowed in experiment',
 'output_granularity':'Preserve complete frozen instrument blocks, not necessarily one item per request'}
 (SPEC/'native-runtime.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
