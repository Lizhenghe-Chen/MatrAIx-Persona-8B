"""Audit choice mappings against labels and the original questionnaire."""
from pathlib import Path
import json,re,hashlib,logging
import pyreadstat
from pypdf import PdfReader


def audit(root):
    root=Path(root);df,meta=pyreadstat.read_sav(root/'data_valid.sav')
    pdf=PdfReader(root/'survey_original.pdf');pages=[p.extract_text() for p in pdf.pages]
    cards=[];errors=[]
    for i in range(1,13):
        name=f'Choice{i:02}'
        matches=[(n+1,t) for n,t in enumerate(pages) if name in t]
        if len(matches)!=1:errors.append('Nonunique questionnaire card '+name);continue
        page,text=matches[0]
        profiles=[int(x) for x in re.findall(r'Profile\s*#(\d+)',text)]
        expected=[int(x) for x in re.findall(r'#(\d+)',meta.column_names_to_labels[name])]
        if profiles!=expected:errors.append('Profile order mismatch '+name)
        values=set(df[name].dropna())
        if not values.issubset({0,1,2,3}):errors.append('Unexpected choice code '+name)
        if 'Keines dieser 3 Produkte' not in text:errors.append('Missing no-buy text '+name)
        cards.append({'question':name,'page':page,'profile_order':profiles,'legal_codes':[1,2,3,0],
                      'missing_records':int(df[name].isna().sum())})
    age=meta.variable_value_labels['Age']
    if age.get(2.)!='30-39':errors.append('Age mapping changed')
    return {'status':'card_order_verified_not_admitted' if not errors else 'mapping_error',
            'people':len(df),'unique_people':int(df.ID.nunique()),'cards':cards,'errors':errors,
            'source_sha256':hashlib.sha256((root/'data_valid.sav').read_bytes()).hexdigest(),
            'corrections':['Each task has three products plus no-buy, not two products.',
                           'Original questionnaire page 19 and SAV label both say age 30–39; English overview 30–49 is inconsistent.'],
            'timing_warning':'Original questionnaire interleaves choice blocks and attitude questions. English overview grouping is not a reliable chronology.',
            'excluded_background':['U_* and W_* utilities/importance derived from choices','Zero fitted no-choice utility','post-choice FNS items','interleaved attitudes unless task-specific timing is reconstructed'],
            'pending':['extract and cross-check all profile attributes against workbook','randomized information text and sequence','author descriptive statistics','background whitelist and timing approval']}

if __name__=='__main__':
    logging.disable(logging.WARNING)
    import argparse
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.write_text(json.dumps(audit(a.directory),ensure_ascii=False,indent=2)+'\n')
