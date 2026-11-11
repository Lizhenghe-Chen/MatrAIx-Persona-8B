"""Audit six-category choices and potential shared panel identifiers."""
import argparse,json,hashlib
from pathlib import Path
import pandas as pd
import pyreadr


def audit(root):
    root=Path(root);path=root/'02_瑞士六品类/w14_conjoint.RData'
    data=pyreadr.read_r(path)['dfconj'];valid=data.dropna(subset=['measure','round','choice'])
    cards=valid.groupby(['PubId','round']);errors=[]
    if valid.duplicated(['PubId','round','measure']).any():errors.append('Duplicate valid alternative')
    if not cards.size().eq(2).all():errors.append('Invalid alternative count')
    if not cards.choice.sum().eq(1).all():errors.append('Invalid selected count')
    if not valid.choice.isin([0,1]).all():errors.append('Unknown choice code')
    earlier=pd.read_csv(root/'05_瑞士家电规格/w8_conjoint.csv')
    overlap=set(pd.to_numeric(valid.PubId,errors='raise')) & set(pd.to_numeric(earlier.PubId,errors='raise'))
    return {'source':'https://zenodo.org/records/20008484','sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'raw_rows':len(data),'rows_without_choice_keys':len(data)-len(valid),'valid_rows':len(valid),
            'people_with_choices':int(valid.PubId.nunique()),'choice_tasks':len(cards),
            'structural_errors':errors,'shared_numeric_identifiers_with_wave8':len(overlap),
            'independence':'Same panel family; shared numeric IDs require namespace confirmation. Do not count as independent-person replication without resolving linkage.',
            'role':'dependent-panel extension candidate; prioritize unrelated US T-shirt sample for independent validation',
            'pending':['Original instructions, language and background timing','Author final analytic sample filters (paper approximately 5000 vs 6535 with choices)','Rating vs forced-choice task mapping','Shared panel identifier namespace and globally consistent splits'],
            'excluded_inputs':['choice-derived green propensity scores','unverified concurrent intention scales'],
            'status':'not_admitted'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.write_text(json.dumps(audit(a.root),ensure_ascii=False,indent=2)+'\n')
