"""Structural reconstruction against the author's public choices; no AI scores."""
import csv,gzip,re,json,hashlib
from collections import Counter
from .registry import DATA,OUT
PATTERN=re.compile(r'^CHOICE_v([0-3])_gc([0-3])_gt([0-3])_dc([0-3])_dt([0-3])_dp([01])_1(?:\.1)?$')
def main():
 path=DATA/'08_购物研究与候选/drone-survey.csv.gz'
 with gzip.open(path,'rt') as f:
  reader=csv.DictReader(f);columns=[k for k in reader.fieldnames if k.startswith('CHOICE')];rows=list(reader)
 invalid=[k for k in columns if not PATTERN.fullmatch(k)]
 # Retain both Qualtrics copies. Never drop a .1 suffix without checking its answers.
 counts=Counter();vendors=Counter();duplicates=0;invalid_codes=Counter();source_choices=Counter()
 for row in rows:
  answered=[c for c in columns if row[c]];counts[len(answered)]+=1;seen=set()
  for c in answered:
   if not PATTERN.fullmatch(c):continue
   key=c.removesuffix('.1')
   if key in seen:duplicates+=1
   seen.add(key);vendors[PATTERN.fullmatch(c).group(1)]+=1
   if row[c] not in ['0','1']:invalid_codes[row[c]]+=1
   source_choices[row[c]]+=1
 result={'study':'drone','status':'structure_reconstructed_pending_original_presentation_check','respondents':len(rows),'choice_columns':len(columns),
 'responses':sum(k*v for k,v in counts.items()),'questions_per_person':dict(counts),'vendor_response_counts':dict(vendors),
 'invalid_column_patterns':invalid,'invalid_choice_codes':dict(invalid_codes),'same_card_twice_within_person':duplicates,
 'answer_mapping':{'0':'Ground vehicle','1':'Drone'},'answer_mapping_evidence':'Author transformation notebook explicitly groups choice==0 as ground and choice==1 as drone.',
 'source_response_counts':dict(source_choices),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
 'publication_source':'https://github.com/aberke/drones-consumer-privacy/tree/d8d1811d4c93e2a86b0d898f097411d5d043cee9',
 'original_instructions_located':True,'original_instructions_pages':[5,6,7,8,9,10],
 'matching_fields_available':['age band','gender','household income','urban/rural','residence type'],
 'education_available':False,'country':'United States','source_participant_age_minimum':18,
 'routing':'Original nonempty choice columns preserve actual delivery-category eligibility; routing answers are not profile fields.',
 'unresolved':['Confirm screen/table presentation and historical survey date before admission.','No education measurement: match available age/sex/income only, explicitly report unavailable education; do not infer it.','Freeze vendor-block handling and unknown original random order adaptation.','Sparse cards: preregister vendor-level/attribute-conditioned shares, not unsupported per-card distribution claims.','Source overlap and cloud field policy require final review.'],
 'effects_scored':False}
 (OUT/'drone-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print({k:result[k] for k in ['respondents','responses','invalid_column_patterns','same_card_twice_within_person']})
if __name__=='__main__':main()
