"""Compare historical anchors with inflation context in a SHED replay."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import json

import protocol
from optout_transfer import predictions
from order_screen import WORK, encode, send

RUN = WORK / 'survey-shock-v1'
QUESTIONS = {
    'financial_ok': 'Would you describe your current finances as at least doing okay?',
    'cash_400': ('Would you pay for a hypothetical $400 emergency expense entirely '
                 'with cash, savings, or a credit card paid off at the next statement?'),
}
# Figures 1 and 24 in the Fed's accessible 2025 report.
RATES = {2018:(75,61), 2019:(75,63), 2020:(75,64), 2021:(78,68),
         2022:(73,63), 2023:(72,63), 2024:(73,63)}
# August CPI-U year-over-year, published by September of each year.
CPI = {2019:1.7, 2020:1.3, 2021:5.3, 2022:8.3, 2023:3.7, 2024:2.5}
YEARS = tuple(range(2020,2025))
CONDITIONS = ('history', 'history_and_cpi')


def deck():
    jobs = {}
    for year in YEARS:
        for index, (item, prompt) in enumerate(QUESTIONS.items()):
            for condition in CONDITIONS:
                context = (f'Historical forecast as of September 30, {year}, for the US adult population. '
                           f'Last year {RATES[year-1][index]}% answered Yes. Estimate this year’s share. '
                           'Only use information available by the forecast date.')
                if condition == 'history_and_cpi':
                    context += (f' US all-items CPI-U rose {CPI[year]:.1f}% year over year in August, '
                                f'compared with {CPI[year-1]:.1f}% in August of the prior year.')
                question = {'id':item,'prompt':prompt,'options':{'1':'Yes','0':'No'}}
                payload = {'title':'US household finances','context':context,
                           'questions':[question],'basic':{}}
                jobs[f'{year}:{item}:{condition}'] = {
                    'body':protocol.build(payload,'basic','qwen',{}, {},256),
                    'questions':[question]}
    RUN.mkdir(mode=0o700,exist_ok=True)
    path = RUN/'jobs.json'
    if path.exists() and path.read_bytes()!=encode(jobs):
        raise ValueError('Frozen requests changed')
    if not path.exists():
        path.write_bytes(encode(jobs))
    return jobs


def score(jobs):
    p, identities = predictions(jobs,RUN)
    if len(identities)!=1:
        raise ValueError('Mixed model versions')
    rows = []
    for year in YEARS:
        for index, item in enumerate(QUESTIONS):
            past, previous = RATES[year-2][index], RATES[year-1][index]
            forecasts = {'carry_forward':previous,'linear_trend':2*previous-past}
            forecasts.update({name:100*p[f'{year}:{item}:{name}']['1'] for name in CONDITIONS})
            rows.append({'year':year,'item':item,'actual_pct':RATES[year][index],
                         'forecast_pct':forecasts})

    def mae(group):
        return {name:sum(abs(r['actual_pct']-r['forecast_pct'][name]) for r in group)/len(group)
                for name in rows[0]['forecast_pct']}
    return {'requests':len(jobs),'identity':json.loads(next(iter(identities))),
            'all_mae_pp':mae(rows),'shock_2021_2022_mae_pp':mae([r for r in rows if r['year'] in (2021,2022)]),
            'by_year_mae_pp':{year:mae([r for r in rows if r['year']==year]) for year in YEARS},
            'rows':rows}


if __name__=='__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action',choices=['run','score'])
    args=cli.parse_args()
    jobs=deck()
    if args.action=='run':
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(partial(send,directory=RUN),jobs.values()))
        print(json.dumps({'requests':len(jobs)}))
    else:
        print(json.dumps(score(jobs),indent=2))
