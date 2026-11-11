"""Structural admission check only for RADIANT consumer workbooks."""
import json,hashlib,argparse
from pathlib import Path
import pandas as pd

def audit(root):
    output=[]
    for p in sorted(Path(root).glob('CO*.xlsx')):
        book=pd.ExcelFile(p);survey=pd.read_excel(book,'survey')
        choice=pd.read_excel(book,'choices' if 'choices' in book.sheet_names else 'choice')
        cards=choice.groupby(['unique_id','choice_card']);errors=[]
        if survey.unique_id.duplicated().any():errors.append('duplicate survey person')
        if choice.duplicated(['unique_id','choice_card','option']).any():errors.append('duplicate alternative')
        if not cards.size().eq(3).all():errors.append('not three alternatives')
        if not choice.choice.isin([0,1]).all():errors.append('unknown choice code')
        if not cards.choice.sum().eq(1).all():errors.append('not one chosen alternative')
        if not set(choice.unique_id).issubset(set(survey.unique_id)):errors.append('choice person without survey')
        tasks=cards.size().groupby(level=0).size()
        output.append({'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                       'survey_people':len(survey),'choice_people':choice.unique_id.nunique(),
                       'choice_rows':len(choice),'cards':len(cards),
                       'tasks_per_person_histogram':{str(k):int(v) for k,v in tasks.value_counts().items()},
                       'errors':errors,'choice_columns':choice.columns.tolist()})
    return {'source':'https://doi.org/10.5281/zenodo.15420092','status':'structural_only_not_admitted',
            'files':output,'pending':['Original questionnaire and randomized information text',
            'Author sample statistics and exclusions','Background measurement timing',
            'Exact product display and price units; inspect metadata inconsistencies'],
            'study_count_policy':'Five country/product datasets within one project are not automatically five independent studies.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=audit(a.root);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result))
