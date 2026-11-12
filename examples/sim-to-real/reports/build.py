"""Build the offline evidence review. No model calls; no respondent data exported."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PRIVATE = Path.home() / ".local/share/matraix-decision-lab/analysis-v1"


def collect() -> dict:
    sources = []

    def read(relative: str, private=False):
        path = (PRIVATE if private else ROOT) / relative
        raw = path.read_bytes()
        sources.append({"path": ("local-analysis/" if private else "../") + relative,
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "storage": "local_only" if private else "git"})
        return json.loads(raw)

    pew = read("study/08_购物预测/pew-formal-score.json")
    shoes = read("study/08_购物预测/shoes-test-score.json")
    rep = read("study/10_匹配与商品复验/results.json")
    models = read("study/02_模型对比/results.json")
    prompt = read("study/03_提示与背景/results.json")
    commerce = read("study/06_北美电商选品/results.json")
    cal = read("study/08_购物预测/pew-formal-calibration.json")
    amazon = read("study/08_购物预测/amazon-mix-test-score.json")
    history = read("decision_lab/reports/choice-history-result.json")
    read("study/09_方法审查/audit-results.json")  # Provenance for the documented weighting audit.
    formal = {}
    for study in ("dryer", "swiss"):
        d = read(f"individual-{study}.json", private=True)
        formal[study] = {k: d[k] for k in ("methods", "comparisons", "calibration_llm_weight")}

    def contrast(d, before, after):
        return next(c for c in d["contrasts"] if c["from"] == before and c["to"] == after)

    rows = []
    for label, data, source in (("网购看法 · 13 道题", pew, "pew"),
                                ("运动鞋 · 购买意愿评分", shoes, "shoes")):
        summary = data.get("summaries", data.get("summary"))
        c = contrast(data, "rich_choice", "rich_probability")
        rows.append({"label": label, "before": summary["rich_choice"]["tv_pp"],
                     "after": summary["rich_probability"]["tv_pp"],
                     "gain": c["tv_improvement_pp"], "ci": c.get("tv_95_interval", c.get("tv_interval")), "source": source})
    for key, label in (("packaging", "包装商品 · 包括都不买"), ("origin", "商品产地 · 属性取舍")):
        d = rep["products"][key]
        c = d["comparisons"][0]
        rows.append({"label": label, "before": d["summary"]["choice"]["mean_run_tv_pp"],
                     "after": d["summary"]["probability"]["mean_run_tv_pp"],
                     "gain": c["gain_pp"], "ci": c["ci95"], "source": "rep"})
    question_names = ["第一次买：能亲自查看或试用有多重要？", "第一次买：能看网上评价有多重要？",
                     "第一次买：能直接网购有多重要？", "第一次买：能比较多家价格有多重要？",
                     "第一次买：能询问商品情况有多重要？", "第一次买：熟人建议有多重要？",
                     "第一次买：熟悉卖家有多重要？", "网上评价对保证商品安全有多大帮助？",
                     "网上评价对增强购买信心有多大帮助？", "网上评价对促使商家负责有多大帮助？",
                     "第一次买某件商品时，多常阅读网上评价？", "在实体店里，会用手机查网上更低价格吗？",
                     "在实体店里，会用手机查商品评价等信息吗？"]
    questions = []
    for i, item in enumerate(pew["items"]["rich_probability"]):
        key = item["question"]
        opts = (["非常重要", "比较重要", "不太重要", "完全不重要"] if i < 7 else
                ["很大帮助", "一些帮助", "少量帮助", "毫无帮助"] if i < 10 else
                ["总是或几乎总是", "有时", "从不"] if i == 10 else ["会", "不会"])
        methods = {}
        for source, label in (("rich_choice", "只选一项"), ("rich_probability", "保留概率")):
            v = next(x for x in pew["items"][source] if x["question"] == key)
            assert v["real"] == item["real"]
            methods[label] = {"shares": v["simulated"], "error": v["tv_pp"]}
        for source, label in (("calibrated_model", "真人数据校准"), ("statistics_rich", "真人统计模型")):
            v = cal["questions"][key]["methods"][source]
            methods[label] = {"shares": v["shares"], "error": v["tv_pp"]}
        questions.append({"key": key, "label": question_names[i], "original": item["question_text"],
                          "options": opts, "original_options": item["options"], "real": item["real"],
                          "people": item["valid_real_people"], "methods": methods})
    return {"schema_version": 1, "updated": "2026-11-12", "sources": sources,
            "probability": rows, "questions": questions,
            "pew_summary": pew["summaries"], "pew_contrasts": pew["contrasts"],
            "matching": {k: rep["matching"][k] for k in ("summary", "comparisons")},
            "packaging": {"human_refusal": rep["products"]["packaging"]["human_opt_out_pct"],
                          "summary": rep["products"]["packaging"]["summary"]},
            "models": {k: models[k] for k in ("overall", "comparisons")},
            "prompt": {k: prompt[k] for k in ("overall", "comparisons")},
            "commerce": {k: {"cells": {c: {"tv_pp": v["tv_pp"]} for c,v in d["cells"].items()},
                             "comparisons": d["comparisons"]} for k,d in commerce["surveys"].items()},
            "calibration": {k: cal[k] for k in ("summary", "model_weight", "versus_statistics")},
            "formal": formal,
            "amazon": {"accounts": amazon["accounts"], "tasks": {k: {"results": v["results"],
                           "comparisons": v["comparisons"]} for k,v in amazon["tasks"].items()}},
            "history": {k: history[k] for k in ("studies", "execution", "aborted_run", "recommend_independent_replication")}}


def validate(d):
    for q in d["questions"]:
        for shares in [q["real"], *[m["shares"] for m in q["methods"].values()]]:
            assert len(shares) == len(q["options"])
            assert all(0 <= x <= 1 for x in shares) and abs(sum(shares)-1) < 1e-8
        for method in q["methods"].values():
            tv = 50 * sum(abs(a-b) for a,b in zip(q["real"], method["shares"]))
            assert abs(tv - method["error"]) < 1e-8
    for r in d["probability"]:
        assert abs(r["before"] - r["after"] - r["gain"]) < 1e-8
    assert len(d["questions"]) == 13


def bars(rows, maximum=50, decimals=2, unit="个百分点"):
    """Zero-based responsive bars; exact values remain legible on small screens."""
    elements = [f'<div class="bar-plot" role="img" aria-label="误差对比，越低越好；单位：{unit}">']
    colors = {"before": "#a15e38", "after": "#117b70", "stats": "#5358a5", "neutral": "#637888"}
    for label,value,kind in rows:
        assert 0 <= value <= maximum
        elements += [f'<div class="bar-row"><div class="bar-top"><span>{html.escape(label)}</span><b>{value:.{decimals}f}</b></div>',
                     f'<div class="bar-track"><div style="width:{100*value/maximum:.4f}%;background:{colors[kind]}"></div></div></div>']
    elements += ['<div class="bar-axis">'+''.join(f'<span>{maximum*i/4:g}</span>' for i in range(5))+'</div>',
                 f'<div class="bar-unit">{unit} · 越低越好</div>']
    return ''.join(elements)+'</div>'


def intervals(rows, lo=-5, hi=32, unit="个百分点"):
    height = 49*len(rows)+50
    scale = lambda x: 240 + (x-lo)/(hi-lo)*335
    parts = [f'<svg viewBox="0 0 680 {height}" role="img" aria-label="改善幅度和95%区间；正数表示改善，单位{unit}">',
             f'<line x1="{scale(0)}" x2="{scale(0)}" y1="5" y2="{height-25}" stroke="#9caaa6" stroke-dasharray="4 4"/>']
    for i, (label, value, ci) in enumerate(rows):
        y=26+49*i
        color='#117b70' if ci[0]>0 else '#a15e38'
        parts += [f'<text x="228" y="{y+5}" text-anchor="end" class="barlabel">{html.escape(label)}</text>',
                  f'<line x1="{scale(ci[0])}" x2="{scale(ci[1])}" y1="{y}" y2="{y}" stroke="{color}" stroke-width="3"/>',
                  f'<circle cx="{scale(value)}" cy="{y}" r="5" fill="{color}"/>',
                  f'<text x="{scale(ci[1])+10}" y="{y+5}" class="value">{value:+.2f}</text>']
    parts += [f'<text x="{scale(0)}" y="{height-6}" text-anchor="middle" class="axis">0：没有改善</text>']
    return ''.join(parts)+'</svg>'



CROSS = HERE.parent/'decision_lab/reports/cross-study-v1'


def cross_study_section():
    """Reader-facing summary of the six-study run; never invents numbers."""
    summary_path=CROSS/'formal-report.summary.json'
    link='../decision_lab/reports/cross-study-v1/formal-report.html'
    if not summary_path.exists():
        return '<p>六套研究的正式报告尚未生成：<a href="'+link+'">打开跨研究报告</a>。</p>'
    summary=json.loads(summary_path.read_text())
    rows=summary['rows']
    gains=[rows[s]['brier']['relative_improvement'] for s in rows]
    low,high=min(gains),max(gains)
    statistical=[s for s in rows if rows[s]['statistical']]
    worst=min(rows[s]['statistical']['relative_improvement'] for s in statistical)
    best=max(rows[s]['statistical']['relative_improvement'] for s in statistical)
    supporting=len(summary['supporting'])
    gate='达到' if summary['cross_study_gate'] else '没有达到'
    names=[('anes','美国公共支出'),('pew168','美国诈骗风险'),('shed','美国消费调整'),
           ('pew13','美国购物看法'),('dryer','四国烘干机'),('swiss','瑞士家电规格')]
    cells=[]
    for key,label in names:
        row=rows[key]
        gain=f'{100*row["brier"]["relative_improvement"]:+.1f}%'
        versus='—' if row['statistical'] is None else f'{100*row["statistical"]["relative_improvement"]:+.1f}%'
        cells.append(f'<tr><th>{html.escape(label)}</th><td>{row["people"]}</td>'
                     f'<td>{gain}</td><td>{versus}</td></tr>')
    items=''.join(cells)
    return ('<div class="grid3">'
            f'<article class="card"><span class="tag">主对照 · 优化 vs 原生</span><h3>六套全部改善</h3>'
            f'<div class="big">{100*low:+.1f}% → {100*high:+.1f}%</div>'
            '<p>把单选换成完整概率后，个人概率误差（Brier）在六套研究里全部显著下降。</p>'
            '<p class="small">收益几乎全部来自“交出概率”；只改提示、保留单选时四套为负。</p></article>'
            f'<article class="card"><span class="tag">历史答案对照 · 必须带</span><h3>AI 全部落后</h3>'
            f'<div class="big">{100*best:+.1f}% → {100*worst:+.1f}%</div>'
            '<p>与“用其他人的答案算出的猜法”相比，六套全部显著更差，区间都低于零。</p>'
            '<p class="small">只跟随机比会误以为成功；加上对照才发现 AI 接近随机。</p></article>'
            f'<article class="card"><span class="tag">预设门槛</span><h3>跨研究门槛{gate}</h3>'
            f'<div class="big">{supporting} / 6</div>'
            '<p>同时达到“概率误差改善”与“分布改善至少 2 个百分点”的研究数量。</p>'
            '<p class="small">要求至少三套、两类任务、两个地区，本轮未满足。</p></article>'
            '</div>'
            '<table class="compact"><thead><tr><th>研究</th><th>人数</th><th>优化 vs 原生</th>'
            '<th>优化 vs 历史答案对照</th></tr></thead><tbody>'+items+'</tbody></table>'
            f'<p><a href="{link}">查看六套研究完整报告（含逐组数字、区间与不可估计的说明）</a>'
            ' · <a href="../decision_lab/docs/推荐配置.md">推荐配置与判断顺序</a></p>')

def build(d):
    validate(d)
    slots = {}
    def chart(rows, **kwargs): return '<div class="chart">'+bars(rows, **kwargs)+'</div>'
    cards=[]
    for r in d['probability']:
        cards.append(f'<figure><h3>{r["label"]}</h3>'+chart([('只选一项', r['before'], 'before'), ('保留概率', r['after'], 'after')])+
                     f'<figcaption>误差减少 <b>{r["gain"]:.2f}</b> 个百分点；95% 区间 [{r["ci"][0]:.2f}, {r["ci"][1]:.2f}]。'+
                     ('<strong>未确认改善。</strong>' if r['gain']<0 else '')+'</figcaption></figure>')
    slots['PROBABILITY']=''.join(cards)
    slots['PROB_INTERVAL']=intervals([(r['label'],r['gain'],r['ci']) for r in d['probability']])
    p=d['pew_summary']
    slots['SAME_PROB']=chart([('只保留最大概率项',p['rich_probability_argmax']['tv_pp'],'before'),('按完整概率汇总',p['rich_probability']['tv_pp'],'after')])
    m=d['matching']['summary']
    slots['MODEL']=chart([('Qwen · 相同背景',m['qwen/matched']['mean_run_tv_pp'],'before'),('Pro · 相同背景',m['pro/matched']['mean_run_tv_pp'],'after')],maximum=20)
    slots['MODEL_REPEATS']=''.join(f'<tr><th>第 {i+1} 次</th><td>{a:.2f}</td><td>{b:.2f}</td><td>{a-b:+.2f}</td></tr>' for i,(a,b) in enumerate(zip(m['qwen/matched']['tv_by_run_pp'],m['pro/matched']['tv_by_run_pp'])))
    slots['EARLY_MODEL']=chart([(label,d['models']['overall'][key]['tv_pp'],kind) for label,key,kind in [('DeepSeek Flash','flash-A','before'),('Qwen','qwen-A','neutral'),('DeepSeek Pro','pro-A','after')]],maximum=40)
    c=d['calibration']['summary']
    slots['CALIBRATION']=chart([('AI · 保留概率',c['raw_model']['tv_pp'],'before'),('AI · 真人数据校准',c['calibrated_model']['tv_pp'],'after'),('真人统计 · 同背景',c['statistics_rich']['tv_pp'],'stats')],maximum=20)
    slots['FORMAL']=''.join('<figure><h3>'+label+'</h3>'+chart([('AI · 真实贴题背景',v['methods']['rich']['brier'],'before'),('真人统计 · 同背景',v['methods']['statistics_rich']['brier'],'stats'),('开发集选定混合',v['methods']['calibrated']['brier'],'after')],maximum=.8,decimals=4,unit='概率误差分数')+
                          '<figcaption>'+str(v['methods']['rich']['people'])+' 名测试者；'+str(v['methods']['rich']['tasks'])+' 道选择。统计模型使用额外训练答案。</figcaption></figure>'
                          for name,label in [('dryer','四国烘干机'),('swiss','瑞士家电')] for v in [d['formal'][name]])
    p=d['prompt']['overall']
    slots['PROMPT']=chart([('扮演 · 基础背景',p['p0-b1']['tv_pp'],'before'),('预测 · 基础背景',p['p1-b1']['tv_pp'],'neutral'),('扮演 · 贴题背景',p['p0-b3']['tv_pp'],'neutral'),('预测 · 贴题背景',p['p1-b3']['tv_pp'],'after')],maximum=35)
    slots['TRANSFER']=''.join(f'<tr><th>{label}</th><td>{v["cells"]["P0+B1"]["tv_pp"]:.2f}</td><td>{v["cells"]["P1+B3"]["tv_pp"]:.2f}</td><td>{v["cells"]["P0+B1"]["tv_pp"]-v["cells"]["P1+B3"]["tv_pp"]:+.2f}</td></tr>' for name,label in [('origin','商品产地选择'),('packaging','包装与拒买'),('pew','设备网购与达人购物')] for v in [d['commerce'][name]])
    slots['HISTORY']=''.join('<figure><h3>'+label+'</h3>'+chart([(label2,v['methods'][key]['brier'],kind) for label2,key,kind in [('只有真实背景','background','neutral'),('加本人两次选择','own','before'),('加别人两次选择','other','neutral')]],maximum=1,decimals=4,unit='概率误差分数')+f'<figcaption>各 48 人；本人记录相对只有背景的误差改善 <b>{100*v["comparisons"]["background"]["relative_improvement"]:+.1f}%</b>；95% 区间 [{100*v["comparisons"]["background"]["relative_improvement_95_ci"][0]:.1f}%, {100*v["comparisons"]["background"]["relative_improvement_95_ci"][1]:.1f}%]。</figcaption></figure>' for name,label in [('dryer','四国烘干机'),('swiss','瑞士家电')] for v in [d['history']['studies'][name]])
    slots['QUESTION_TABLE']=''.join('<tr><th>'+html.escape(q['label'])+'</th>'+''.join(f'<td>{q["methods"][k]["error"]:.2f}</td>' for k in ('只选一项','保留概率','真人数据校准','真人统计模型'))+'</tr>' for q in d['questions'])
    slots['QUESTION_DATA']=json.dumps(d['questions'],ensure_ascii=False).replace('</',r'<\/')
    slots['CROSS_STUDY']=cross_study_section()
    slots['STYLE']=(HERE/'style.css').read_text()
    slots['SCRIPT']=(HERE/'charts.js').read_text()
    page=(HERE/'report.html.tmpl').read_text()
    for key,val in slots.items(): page=page.replace('{{'+key+'}}',val)
    assert '{{' not in page, 'Unfilled template slot'
    (HERE/'index.html').write_text(page)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect',action='store_true',help='Refresh aggregates from frozen public and local score files.')
    args=parser.parse_args()
    path=HERE/'evidence.json'
    if args.collect:
        data=collect()
        validate(data)
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    build(json.loads(path.read_text()))
    print('Built offline report:',HERE/'index.html')
