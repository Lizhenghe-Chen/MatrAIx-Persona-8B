"""Reconstruct public cards, cross-checking original PDF against author workbook."""
import re,json,hashlib,logging
from pathlib import Path
import openpyxl
from pypdf import PdfReader


def extract(root):
    root=Path(root)
    book=openpyxl.load_workbook(root/'XLSTAT_V4_final.xlsm',read_only=True,data_only=True)
    sheet=book['Choices_Frequ3'];profiles={}
    for row in sheet.iter_rows(min_row=2,max_row=13,values_only=True):
        pid=int(re.search(r'\d+',row[7]).group())
        profiles[pid]={'biobased':row[8]=='Bio-based','biodegradable':row[9]=='Biodegradable',
                       'extra_days':int(re.search(r'\d+',row[10]).group()),
                       'packaging_price_eur':float(row[11].split()[0].replace(',','.'))}
    book.close();cards=[]
    for n,page in enumerate(PdfReader(root/'survey_original.pdf').pages,1):
        text=page.extract_text();q=re.search(r'Choice\d{2}',text)
        if not q:continue
        matches=list(re.finditer(r'Verpackung:\s*(Biokunststoff|Konventioneller\s+Kunststoff)(.*?)Profile\s*#(\d+)',text,re.S|re.I))
        if len(matches)!=3:raise ValueError('Expected three product descriptions on page '+str(n))
        opts=[]
        for m in matches:
            pid=int(m[3]);body=m[2]
            parsed={'biobased':m[1]=='Biokunststoff',
                    'biodegradable':'Nicht biologisch abbaubar' not in body,
                    'extra_days':int(re.search(r'(\d+)\s*Tage länger',body)[1]),
                    'packaging_price_eur':float(re.search(r'Preis Verpackung:\s*([\d,]+)',body)[1].replace(',','.'))}
            if parsed!=profiles[pid]:raise ValueError('Workbook/PDF mismatch '+str(pid))
            opts.append({'profile':pid,**parsed,
                         'text_de':('Verpackung: Biokunststoff' if parsed['biobased'] else 'Verpackung: Konventioneller Kunststoff')+'; '+('Biologisch abbaubar' if parsed['biodegradable'] else 'Nicht biologisch abbaubar')+f"; Produkt hält {parsed['extra_days']} Tage länger; Preis Verpackung: {parsed['packaging_price_eur']:.2f} EUR".replace('.',',')})
        opts.append({'profile':None,'no_buy':True,'text_de':'Keines dieser 3 Produkte'})
        cards.append({'task':q[0],'page':n,'question_de':'Welches dieser Produkte würden Sie kaufen?',
                      'product_de':'Kirschtomaten (250 g)','options':opts,'source_codes':[1,2,3,0]})
    if len(cards)!=12:raise ValueError('Expected twelve cards')
    return {'status':'all_36_profile_appearances_cross_checked','cards':cards,
            'sources':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['XLSTAT_V4_final.xlsm','survey_original.pdf']},
            'note':'Public card attributes only; not a full respondent prompt. Original instructions and treatment text must also be included before model execution.'}

if __name__=='__main__':
    logging.disable(logging.WARNING)
    import argparse
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.write_text(json.dumps(extract(a.directory),ensure_ascii=False,indent=2)+'\n')
