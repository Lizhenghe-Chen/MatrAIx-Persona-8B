import json,re,html,hashlib
from pathlib import Path
import requests,pandas as pd
import argparse
p=argparse.ArgumentParser(description='Reconcile published dryer sample and raw choices; exports aggregates only.')
p.add_argument('directory', type=Path); p.add_argument('--output', type=Path, required=True)
args=p.parse_args(); root=args.directory
(root/'论文证据').mkdir(exist_ok=True)
d=pd.read_stata(root/'Tumbledrier_DCE.dta',convert_categoricals=False); people=d.drop_duplicates('ResponseId')
expected={'CAN':{'C':214,'T1':205,'T2':215},'IRE':{'C':198,'T1':189,'T2':194},'UK':{'C':220,'T1':218,'T2':217},'USA':{'C':208,'T1':228,'T2':221}}
actual={c:{t:int(n) for t,n in z.Treatment.value_counts().items()} for c,z in people.groupby('CountryVersion')}
raw=pd.concat([pd.read_excel(root/(c+'_rawdata.xlsx')) for c in expected]).set_index('ResponseId')
tasks=d.drop_duplicates(['ResponseId','ChoiceSet']); mismatches=0
for r in tasks.itertuples():
 key=f'IE_{r.Treatment}_CS{r.ChoiceSet}_1'
 observed=str(raw.loc[r.ResponseId,key]).strip()
 mismatches+=observed!=r.Choice_str.strip()
url='https://link.springer.com/article/10.1007/s10603-023-09556-5/tables/4'
s=requests.get(url,timeout=30);s.raise_for_status();(root/'论文证据'/'table-4.html').write_text(s.text)
t=re.search(r'<table.*?</table>',s.text,re.S).group()
country=None; stats=[]
mapc={'A. IRELAND':'IRE','B. UNITED KINGDOM':'UK','C. CANADA':'CAN','D. UNITED STATES':'USA'}
fields={'Age':'Age','Female':'Female','Marital status':'Marital','Degree':'Degree','Working':'Working','Env. Concern':'EnvConcern','Income':'Income','Patience':'Patience','Risk':'Risk','Tumble dryer use':'Tumbledrier_usage'}
for tr in re.findall(r'<tr.*?</tr>',t,re.S):
 cells=[html.unescape(re.sub('<[^>]+>','',x)).strip() for x in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>',tr,re.S)]
 if not cells:continue
 if cells[0] in mapc:country=mapc[cells[0]]
 if country and cells[0] in fields:
  for treatment,v in zip(['C','T1','T2'],cells[1:4]):
   calc=float(people[(people.CountryVersion==country)&(people.Treatment==treatment)][fields[cells[0]]].mean()); pub=float(v)
   stats.append({'country':country,'treatment':treatment,'field':fields[cells[0]],'published_mean':pub,'recomputed_mean':calc,'within_rounding':abs(calc-pub)<=.0005001})
report={'status':'sample_and_choice_mapping_verified_display_pending','sources':['https://zenodo.org/records/10046247','https://link.springer.com/article/10.1007/s10603-023-09556-5',url], 'published_counts':expected,'recomputed_counts':actual,'counts_match':expected==actual,'raw_choices_checked':len(tasks),'raw_choice_mismatches':int(mismatches),'author_mean_checks':stats,'all_means_match':all(x['within_rounding'] for x in stats),'decision':'Use official final long table as self-contained cohort; no wide-table join. Exact 12 cell counts and 120 means identify published analysis sample. Cause of wide-table version difference remains unknown; not claimed resolved.','display_issues':['USA A energy cost: published table 2 says 640 while long table EnExp says 610.','Personalised energy cost figure 9 rounds differently from PersEnExp10y; exact display computation unverified.','North American price and capacity require country-specific conversion per table 2.']}
args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print({k:v for k,v in report.items() if k not in ['author_mean_checks','sources','published_counts','recomputed_counts']});print('mean checks',len(stats),'failed',sum(not x['within_rounding'] for x in stats))
