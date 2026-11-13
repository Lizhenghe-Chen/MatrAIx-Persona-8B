"""Read existing reviewed tasks into local-only blocks. Never send truth fields."""
import json,sys,hashlib
from pathlib import Path
from collections import defaultdict,Counter
from .registry import ROOT,OUT
BASE=ROOT.parent
# The historical readers live in legacy/; nothing at the top level is importable.
LEGACY=BASE/'legacy'
if str(LEGACY) not in sys.path:sys.path.insert(0,str(LEGACY))
PRIVATE=Path.home()/'.local/share/matraix-decision-lab/cross-study-v1'

def q(identifier,prompt,options):
 return {'id':str(identifier),'prompt':prompt,'type':'single_choice','required':True,'options':[{'id':str(k),'label':str(v)} for k,v in options]}

def load_existing():
 from optimize_profiles import read_people
 from instruments import ITEMS
 from experiment import DATES
 for study in ['shed','pew','anes']:
  for p in read_people(study):
   ident='pew168' if study=='pew' else study
   questions=[q(k,text,opts.items()) for k,(text,opts) in ITEMS[study].items()]
   yield {'study':ident,'person':p['id'],'stratum':p['stratum'],'weight':p['weight'],'background':p['background'],
     'context':f'United States. Survey period: {DATES[study]}.','questions':questions,'truth':p['answers'],'group':ident}
 from retail_pew import dataset,ITEMS as PITEMS
 people,options=dataset()
 for pid,p in people.items():
  yield {'study':'pew13','person':pid,'stratum':p['background']['Age group']+'|'+p['background']['Education'],'weight':p['weight'],'background':p['background'],
   'context':'United States, November–December 2015.','questions':[q(k,t,enumerate(options[k])) for k,t in PITEMS.items()],
   'truth':{k:str(v) for k,v in p['truth'].items()},'group':'pew13'}
 for ident,directory in [('dryer','dryer-text-v1'),('swiss','swiss-appliances-v1')]:
  raw=json.loads((Path.home()/'.local/share/matraix-decision-lab'/directory/'prepared.json').read_text());groups=defaultdict(list)
  for row in raw['rows']:groups[row['person']].append(row)
  for person,rows in groups.items():
   first=rows[0];background=first['background'];seen={r['context'] for r in rows}
   if len(seen)!=1:raise ValueError('Context changes within person; explicitly define blocks')
   questions=[q(r['task'],r['question'],enumerate(r['options'])) for r in rows]
   yield {'study':ident,'person':person,'stratum':first['stratum'],'weight':first['weight'],'background':background,
    'context':first['context'],'questions':questions,'truth':{str(r['task']):str(r['answer']) for r in rows},
    'group':first['stratum'],'country':first.get('country','Switzerland')}

def main():
 PRIVATE.mkdir(parents=True,exist_ok=True);PRIVATE.chmod(0o700)
 people=list(load_existing());p=PRIVATE/'existing-target-blocks.json'
 if p.exists():raise ValueError('Prepared target snapshot already exists; do not overwrite')
 p.write_text(json.dumps(people,ensure_ascii=False)+'\n');p.chmod(0o600)
 summary={}
 for study in sorted({x['study'] for x in people}):
  rows=[x for x in people if x['study']==study]
  summary[study]={'people':len(rows),'questions_per_person':dict(Counter(len(x['questions']) for x in rows)),
   'background_values':{field:dict(Counter(str(x['background'].get(field,'Unknown')) for x in rows)) for field in sorted({k for x in rows for k in x['background']})},
   'status':'locally_prepared_not_admitted_or_sample_frozen'}
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/'target-structure.json').write_text(json.dumps({'private_snapshot_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'studies':summary},ensure_ascii=False,indent=2)+'\n')
 print({s:summary[s]['people'] for s in summary})
if __name__=='__main__':main()
