"""Build a plain-language story from frozen experiment aggregates only."""
import hashlib
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).parent
STUDY = ROOT / 'study'


def read(name):
    return json.loads((STUDY / name).read_text())


def bars(rows, maximum=100, suffix='%', label='回答比例'):
    html = f'<div class="bar-chart" role="img" aria-label="{escape(label)}">'
    for name, value, color in rows:
        html += (f'<div class="bar-row"><div class="bar-heading"><span>{escape(name)}</span>'
                 f'<strong>{value:.1f}{suffix}</strong></div><div class="bar-track">'
                 f'<span class="bar-fill {color}" style="width:{100*value/maximum:.5f}%"></span></div></div>')
    return html + '</div>'


def table(headers, rows):
    return '<div class="table-scroll"><table><thead><tr>'+''.join(f'<th>{escape(v)}</th>' for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{escape(str(v))}</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def build():
    files = {
        'first':'01_首轮归档/results.json', 'models':'02_模型对比/results.json',
        'profiles':'03_提示与背景/results.json', 'shopping':'06_北美电商选品/results.json',
        'pew':'08_购物预测/pew-formal-score.json', 'shoes':'08_购物预测/shoes-test-score.json',
        'parity':'08_购物预测/shoes-input-parity-score.json',
        'amazon':'08_购物预测/amazon-test-score.json',
        'revalidation':'10_匹配与商品复验/results.json',
    }
    data = {k:read(v) for k,v in files.items()}
    first = next(x for x in data['first']['items'] if (x['survey'],x['item'],x['group'])==('shed','INF3_a','overall'))
    profiles=data['profiles'];latest=data['revalidation'];m=latest['matching'];products=latest['products']
    pack=products['packaging'];origin=products['origin'];pew=data['pew'];shoes=data['shoes']
    models=data['models']['overall']
    oldp=profiles['overall']['p0-b1']['tv_pp'];newp=profiles['overall']['p1-b3']['tv_pp']
    cases={}
    def case(key,title,scope,before,after,stat,change,verdict,meaning,note,detail,ci):
        cases[key]=dict(title=title,scope=scope,before=before,after=after,statistics=stat,
                        change=change,verdict=verdict,meaning=meaning,note=note,detail=detail,ci=ci)
    pair=next(x for x in profiles['comparisons'] if x['reference']=='p0-b1' and x['candidate']=='p1-b3')
    case('profiles','生活问卷：换问法、补背景','消费调整、诈骗风险、公共支出；18题，三份调查各240人',
         oldp,newp,profiles['overall']['historical-stratum']['tv_pp'],
         '从“给年龄学历、扮演一个人”，改为“给真实的贴题背景、预测这个人会怎样答”。这里同时改变了问法与背景。',
         '在这18道题上，有明显改善。','改善后仍不如从其他真人的同题回答计算比例。到了电商任务，也没有处处成功。',
         '每份调查先平均各题，再让三份调查各占三分之一。第三轮结果；简单方法用了另外一批真人的答案。',
         'evidence.html#profiles',pair['overall']['ci95'])
    pair=next(x for x in pew['contrasts'] if x['from']=='rich_choice' and x['to']=='rich_probability')
    case('pew','购物问卷：每题给出各项可能性','2015年Pew购物问卷；13题、240人',
         pew['summaries']['rich_choice']['tv_pp'],pew['summaries']['rich_probability']['tv_pp'],pew['summaries']['statistics']['tv_pp'],
         '真人背景和题目相同，把“每题只选一个答案”改成“估计各选项的可能性，再汇总”。',
         '这份购物问卷明显改善。','模型不再把很多人答成一样，但其他真人的同题比例仍更接近。',
         '13道题各占相同比重。第五轮结果；简单方法按其他真人的年龄、学历计算同题比例。',
         'evidence.html#survey',pair['tv_95_interval'])
    pair=next(x for x in shoes['contrasts'] if x['from']=='rich_choice' and x['to']=='rich_probability')
    case('shoes','运动鞋：保留不同评分的可能性','240人评价1,920对运动鞋，使用1–7分购买意愿',
         shoes['summary']['rich_choice']['tv_pp'],shoes['summary']['rich_probability']['tv_pp'],data['parity']['summary']['statistics_rich']['tv_pp'],
         '同样的鞋和人口背景，从“只给一个分数”改为“给1–7分各自的可能性”。',
         '评分比例更像真人，产品卖点仍没有估准。','只增加环保材质时，真人意愿提高1.61分，概率模型只估到0.58分。整体比例变像，不等于选对了卖点。',
         '比较全部评分的分布。简单方法先学习其他人的评分；后来去掉它比模型多知道的信息，重新比较，误差为2.16。这是同一批数据上的补查，不是新验证。',
         'evidence.html#shoes',pair['tv_interval'])
    for key,title,meaning in [('origin','产地、价格：两款商品选哪款','对高评分款的过度偏好减轻了，但中国产、美国产、便宜款的比例更偏了；合起来没有改善。'),
                               ('packaging','包装、价格：也允许两款都不买','“都不买”的总比例估得更近了，但逐次判断真人会不会拒买，仍然不准。')]:
        d=products[key];s=d['summary'];pair=d['comparisons'][0]
        case(key,title,'原商品实验240人，每种设置重新运行三次',s['choice']['mean_run_tv_pp'],s['probability']['mean_run_tv_pp'],s['statistics']['mean_run_tv_pp'],
             '同一个人的真实背景、商品和问法不变，只把“选一项”改成“给各项可能性”。',
             '三次均改善，但仍未超过真人数据方法。' if pair['passes'] else '没有发现明确改善。',meaning,
             ('产地按四个选择比例平均：中国产、美国产、便宜款、高评分款。' if key=='origin' else '包装按16张商品卡的选项比例误差平均，包含“都不买”。')+
             '每次先评分，再平均三次；第六轮沿用已有评估数据，属于内部复验。简单方法用其他真人选择训练。',
             'evidence.html#revalidation',pair['ci95'])
    def case_html(c):
        return (f'<p class="context">{escape(c["scope"])}</p><h3>{escape(c["title"])}</h3><p>{escape(c["change"])}</p>'+
                bars([('改之前',c['before'],'before'),('改之后',c['after'],'after'),('用其他真人数据的方法',c['statistics'],'statistics')],50,' 点','平均分布误差，条越短越好')+
                f'<p class="takeaway"><strong>{escape(c["verdict"])}</strong> {escape(c["meaning"])}</p>'+
                f'<p class="small">{escape(c["note"])}</p><p><a class="text-link" href="{c["detail"]}">查看这项实验的每道题与完整比较 →</a></p>')
    checks=[]
    for model,name in [('qwen','Qwen'),('pro','DeepSeek Pro')]:
        for old,new,description in [('coarse','matched','再匹配性别与收入'),('matched','matched_traits','再加四项合成人格')]:
            pair=next(x for x in m['comparisons'] if x['before']==model+'/'+old and x['after']==model+'/'+new)
            checks.append([name,description,f"{m['summary'][model+'/'+old]['mean_run_tv_pp']:.2f} → {m['summary'][model+'/'+new]['mean_run_tv_pp']:.2f}",
                           '有小幅改善，未达到2点门槛' if pair['ci95'][0]>0 else '没有达到采用门槛'])
    all_cases=table(['同一项任务内比较','改前误差','改后误差','其他真人数据方法'],[
        [c['title'],f"{c['before']:.2f}",f"{c['after']:.2f}",f"{c['statistics']:.2f}"] for c in cases.values()])
    source_rows=[
        ['美联储SHED 2025','物价上涨后如何调整消费','第一至三轮','https://www.federalreserve.gov/consumerscommunities/shed_data.htm'],
        ['Pew第168波','对网络诈骗风险的判断','第一至三轮','https://www.pewresearch.org/dataset/american-trends-panel-wave-168/'],
        ['ANES 2024','公共服务支出偏好','第一至三轮','https://electionstudies.org/data-center/2024-time-series-study/'],
        ['Bankert商品产地实验','在不同产地、价格、评分的两款商品间选择','第四、六轮','https://itemresponsewarehouse.org/tables/bankert_2023_consumer_origin/'],
        ['Purdue包装实验','选择啤酒包装、价格和标签，也可都不买','第四、六轮','https://data.mendeley.com/datasets/4z748jnnjs/2'],
        ['Pew第111波','网购设备、到店偏好和达人购物','第四轮','https://www.pewresearch.org/internet/dataset/american-trends-panel-wave-111/'],
        ['Pew第13波','购物决策、评论作用和店内比价','第五、六轮','https://www.pewresearch.org/dataset/american-trends-panel-wave-13/'],
        ['Horiuchi运动鞋实验','不同商品属性下的购买意愿评分','第五轮','https://doi.org/10.1017/pan.2021.30'],
        ['Open eCommerce购买记录','参与者捐赠的实际Amazon购买记录','第五轮','https://doi.org/10.7910/DVN/YGLYDY'],
    ]
    sources=''.join(f'<li><a href="{url}">{escape(name)}</a><span>{escape(task)} · {rounds}</span></li>' for name,task,rounds,url in source_rows)
    model_pair=next(x for x in m['comparisons'] if (x['before'],x['after'])==('qwen/matched','pro/matched'))
    tokens={
        'FIRST_BARS':bars([('真人说改买了便宜商品',100*first['human']['1'],'human'),('模型也说改买了便宜商品',100*first['simulated']['C']['1'],'before')]),
        'FIRST_REAL':f"{100*first['human']['1']:.1f}",'FIRST_MODEL':f"{100*first['simulated']['C']['1']:.1f}",
        'REFUSAL_BARS':bars([('真人实际都不买',pack['human_opt_out_pct'],'human'),('模型原来：每题选一个',pack['summary']['choice']['opt_out_pct'],'before'),
                              ('模型改后：汇总各项可能性',pack['summary']['probability']['opt_out_pct'],'after'),('其他真人数据训练的方法',pack['summary']['statistics']['opt_out_pct'],'statistics')]),
        'REFUSAL_REAL':f"{pack['human_opt_out_pct']:.1f}",'REFUSAL_BEFORE':f"{pack['summary']['choice']['opt_out_pct']:.1f}",
        'REFUSAL_AFTER':f"{pack['summary']['probability']['opt_out_pct']:.1f}",'REFUSAL_RECALL':f"{pack['summary']['probability']['opt_out_recall_pct']:.1f}",
        'REFUSAL_RECALL_INT':f"{pack['summary']['probability']['opt_out_recall_pct']:.0f}",
        'MODEL_BARS':bars([('同样背景：内网Qwen',m['summary']['qwen/matched']['mean_run_tv_pp'],'before'),('同样背景：DeepSeek Pro',m['summary']['pro/matched']['mean_run_tv_pp'],'after')],20,' 点','13题平均分布误差，越低越好'),
        'MODEL_GAIN':f"{model_pair['gain_pp']:.2f}",'MODEL_CI':f"{model_pair['ci95'][0]:.2f}–{model_pair['ci95'][1]:.2f}",
        'MODEL_HISTORY':table(['第二轮：只给共同情境','平均误差'],[[name,f"{models[key+'-A']['tv_pp']:.2f}"] for key,name in [('flash','Flash'),('pro','Pro'),('qwen','Qwen')]]),
        'PROFILE_BEFORE':f'{oldp:.1f}','PROFILE_AFTER':f'{newp:.1f}',
        'PROFILE_PARTS':table(['只改一件事','平均误差前后','这说明什么'],[
            ['贴题背景不变，改为预测真人答案',f"{profiles['overall']['p0-b3']['tv_pp']:.2f} → {newp:.2f}",'误差减少2.50点，达到原实验门槛'],
            ['预测问法不变，在细分年龄学历外补贴题信息',f"{profiles['overall']['p1-b2']['tv_pp']:.2f} → {newp:.2f}",'误差减少5.27点，达到原实验门槛'],
            ['在上述基础上，再加四项合成人格',f"{newp:.2f} → {profiles['overall']['p1-b4']['tv_pp']:.2f}",'只减少0.13点，变化尚不明确']]),
        'MATCH_TABLE':table(['模型','只改变什么','平均误差前后','判断'],checks),
        'CASE_OPTIONS':''.join(f'<option value="{key}"'+(' selected' if key=='packaging' else '')+f'>{escape(c["title"])}</option>' for key,c in cases.items()),
        'DEFAULT_CASE':case_html(cases['packaging']),'CASE_TABLE':all_cases,'SOURCES':sources,
        'AMAZON_GAIN':f"{100*(data['amazon']['summary']['recent']['brier']-data['amazon']['summary']['blend']['brier'])/data['amazon']['summary']['recent']['brier']:.1f}",
        'PAYLOAD':json.dumps({'cases':cases},ensure_ascii=False).replace('<','\\u003c'),
        'SCRIPT':(ROOT/'retail_story_charts.js').read_text(),
    }
    page=(ROOT/'retail_story_template.html.tmpl').read_text()
    for key,value in tokens.items():page=page.replace('{{'+key+'}}',value)
    assert '{{' not in page
    (STUDY/'index.html').write_text(page)
    legacy=page.replace('<head>','<head><base href="../index.html">',1)
    (STUDY/'08_购物预测/index.html').write_text(legacy)
    manifest={'purpose':'Plain-language story; full experimental evidence retained separately',
              'report':'index.html','full_evidence':'evidence.html','data_changed':False,
              'sources':{k:{'path':v,'sha256':hashlib.sha256((STUDY/v).read_bytes()).hexdigest()} for k,v in files.items()},
              'report_sha256':hashlib.sha256(page.encode()).hexdigest(),
              'render_sources':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('retail_story_template.html.tmpl','retail_story_charts.js')},
              'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (STUDY/'00_导航/通俗报告数据核验.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return page,legacy


if __name__=='__main__':build()
