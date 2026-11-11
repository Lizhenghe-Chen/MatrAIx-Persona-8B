"""Inspect source schemas without exporting respondent records or running macros."""
import json
import os
from pathlib import Path
import hashlib
import pandas as pd
import pyreadstat
import openpyxl


def inspect(root):
    result=[]
    for group in ['04_四国烘干机','05_瑞士家电规格','01_中国日本有机蔬菜','03_德国番茄包装']:
        for p in sorted((root/group).iterdir()):
            if p.suffix.lower() not in ['.xlsx','.csv','.dta','.sav','.xlsm']:
                continue
            row={'study':group,'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
            try:
                if p.suffix in ['.xlsx','.xlsm']:
                    book=openpyxl.load_workbook(p,read_only=True,data_only=True,keep_links=False)
                    row['sheets']=[{'name':s.title,'rows':s.max_row,'columns':s.max_column} for s in book]
                    book.close()
                else:
                    if p.suffix=='.sav':
                        df,meta=pyreadstat.read_sav(p)
                        row['labels']=meta.column_names_to_labels
                    elif p.suffix=='.dta': df=pd.read_stata(p,convert_categoricals=False)
                    else: df=pd.read_csv(p)
                    row['records']=len(df);row['columns']=list(df.columns)
                    for key in ['PubId','id','ID','respondent']:
                        if key in df:row['unique_'+key]=int(df[key].nunique())
                row['status']='schema_inspected_not_admitted'
            except Exception as e:row['status']='read_error';row['error']=type(e).__name__+': '+str(e)
            result.append(row)
    return {'note':'Schema inspection only. Question mapping, timing, license and author-statistic checks remain required. No respondent rows exported.','files':result}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    root=Path(os.environ.get('MATRAIX_DATA_ROOT','/Volumes/元宇宙联合创新实验室/实验数据/MatrAIx多地区选品源数据'))
    a.output.write_text(json.dumps(inspect(root),ensure_ascii=False,indent=2)+'\n')
