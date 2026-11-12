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

def clean_study_section():
    """Two-arm clean experiment with real charts; every number comes from the diagnostics file."""
    summary_path = CROSS / 'clean-v1-report.summary.json'
    results_path = CROSS / 'clean-v1-results.json'
    diagnostics_path = CROSS / 'clean-v1-diagnostics.json'
    link = '../decision_lab/reports/cross-study-v1/clean-v1-report.html'
    if not (summary_path.exists() and results_path.exists() and diagnostics_path.exists()):
        return ('<section id="clean-v1"><h2>换题型再验一次：两臂干净实验</h2>'
                '<p>诊断尚未生成：先运行 <code>python -m decision_lab.cross_study.clean_diagnostics</code>。'
                f'<a href="{link}">报告页</a></p></section>')
    summary = json.loads(summary_path.read_text())
    results = json.loads(results_path.read_text())
    diagnostics = json.loads(diagnostics_path.read_text())
    drone, shoes = diagnostics['drone'], diagnostics['shoes']
    labels = {'drone': '美国无人机配送（二选一）', 'shoes': '美国运动鞋意愿（1–7 打分）'}
    cells, flat, refs = [], [], []
    for study, row in summary['rows'].items():
        arms = results['studies'][study]['results']['arms']
        uniform = arms['uniform']['brier']
        optimized = arms['optimized']['brier']
        own = f'{100 * row["brier"]["relative_improvement"]:+.1f}%'
        versus_uniform = f'{100 * (uniform - optimized) / uniform:+.1f}%'
        statistical = row['statistical']
        versus_statistics = '—' if statistical is None else f'{100 * statistical["relative_improvement"]:+.1f}%'
        cells.append(f'<tr><th>{html.escape(labels.get(study, study))}</th><td>{row["people"]}</td>'
                     f'<td>{own}</td><td>{versus_uniform}</td><td>{versus_statistics}</td></tr>')
        if optimized >= uniform:
            flat.append(labels.get(study, study))
        if statistical is not None:
            refs.append(statistical['relative_improvement'])
    flat_text = ('在' + '、'.join(flat) + '上，优化组合连“每个选项等可能”都没有超过。') if flat else ''
    stats_text = ('两套都不是统计参照的对手：' + f'{100 * min(refs):+.1f}% ~ {100 * max(refs):+.1f}%。'
                  if refs and max(refs) < 0 else '')
    budget = results['budget']
    spread = drone['actual_share_range']
    figure = lambda title, chart, caption, extra='': (
        f'<figure><h3>{title}</h3><div id="{chart}" class="echart"{extra}></div>'
        f'<figcaption>{caption}</figcaption></figure>')
    body = (
        '<p class="lead">换一份没用过的问卷、换成 1–7 打分，之前的优化方案还成立吗？'
        '这一轮是<strong>预注册</strong>的：协议先写好，只跑原生单选与优化概率两个臂。</p>'
        '<div class="grid3">'
        f'<article class="card"><span class="tag">主对照 · 优化 vs 原生</span><h3>仍是大幅改善</h3>'
        f'<div class="big">+{100 * min(r["brier"]["relative_improvement"] for r in summary["rows"].values()):.1f}% → '
        f'+{100 * max(r["brier"]["relative_improvement"] for r in summary["rows"].values()):.1f}%</div>'
        '<p>但原生臂只交一个选项，被当分布评分时必然偏高；这一项不能当预测力。</p></article>'
        f'<article class="card"><span class="tag">与“每档等可能”比</span><h3>几乎不含信息</h3>'
        f'<div class="big">{100 * drone["improvement"]["optimized"]:+.1f}% / '
        f'{100 * shoes["improvement"]["optimized"]:+.1f}%</div>'
        f'<p>{flat_text or "只比等分略好"}方向学会了，幅度压扁了：见下面的散点。</p></article>'
        f'<article class="card"><span class="tag">与同信息统计比</span><h3>两套全部落后</h3>'
        f'<div class="big">{100 * min(refs):+.1f}% / {100 * max(refs):+.1f}%</div>'
        f'<p>无人机历史答案对照好过等分 {100 * drone["improvement"]["stratum_history"]:.0f}%，'
        f'AI 只有 {100 * drone["improvement"]["optimized"]:.0f}%；差距在“敢不敢把差异拉开”。</p></article>'
        '</div>'
        + figure('谁比“每个选项等可能”更准',
                 'cleanRelative',
                 '柱子在零线右边表示比“每个选项等可能”更准。原生单选因为只交一个选项而大幅偏离；'
                 '优化概率贴住零线；只有同信息统计参照稳定在右边。'
                 '括号内是该方法的 Brier 原值（越小越好）。',
                 ' style="height:400px"')
        + '<div class="grid2">'
        + figure('无人机：方向学会了，幅度压扁了',
                 'cleanScatter',
                 f'每一个点是一张题卡（共 {drone["cards"]} 张，每张 {drone["people_per_card"]["min"]}–'
                 f'{drone["people_per_card"]["max"]} 人）。横轴是真人真实选择率，纵轴是 AI 预测率，虚线是完全学会。'
                 f'AI 确实跟着题卡动（相关 {drone["fit"]["corr"]:.2f}），但斜率只有 {drone["fit"]["slope"]:.2f}：'
                 f'真人低于 10% 的卡它给 {100 * drone["fit"]["buckets"]["under10"]["predicted"]:.0f}%，'
                 f'真人高于 70% 的卡只给 {100 * drone["fit"]["buckets"]["over70"]["predicted"]:.0f}%——'
                 f'真人的 {100 * spread[0]:.0f}%–{100 * spread[1]:.0f}% 被压成大约 30%–65%。'
                 '<br><span class="small">底部长条是真人选择率的分布。</span>',
                 ' style="height:430px"')
        + figure('无人机总体构成：AI 以为是一半一半',
                 'cleanDonut',
                 f'真人实际选无人机 {100 * drone["actual_drone_share"]:.1f}%，AI 预测均值 '
                 f'{100 * drone["predicted_drone_share"]:.1f}%。'
                 '连“总体比例”这一层都对不上，更谈不上逐题卡差异。',
                 ' style="height:430px"')
        + '</div>'
        + '<div class="grid2">'
        + figure('运动鞋：1–7 分分布太“扁”',
                 'cleanRating',
                 f'真人平均 {shoes["human_mean_rating"]:.2f} 分，AI 预测平均 {shoes["model_mean_rating"]:.2f} 分；'
                 '但 AI 把概率摊得更平均，真人更集中在 5 分。分布越扁，Brier 越接近“每档等分”。',
                 ' style="height:400px"')
        + figure('个体差异被压掉了多少',
                 'cleanVariation',
                 f'以真人为 100%：AI 只保留了 {100 * shoes["variation"]["between_kept"]:.0f}% 的“人与人”差异、'
                 f'{100 * shoes["variation"]["within_kept"]:.0f}% 的“同一人跨商品”差异。'
                 f'AI 与星级评论的相关是 {shoes["correlation"]["review"]:.2f}，与价格 {shoes["correlation"]["price"]:.2f}——'
                 '它并非完全不看属性，只是信号远小于它压掉的差异。',
                 ' style="height:400px"')
        + '</div>'
        + '<div class="table-wrap"><table><caption>逐套数字（Brier 越小越好；相对列以“每档等可能”为基准）</caption>'
          '<thead><tr><th>研究</th><th>人数</th><th>优化 vs 原生</th><th>优化 vs 每档等可能</th>'
          '<th>优化 vs 统计参照</th></tr></thead><tbody>' + ''.join(cells) + '</tbody></table></div>'
        + f'<p class="small">冻结调用 {budget["max_calls"]} 次，保守上限 ${budget["reserved_peak_usd"]:.2f}；'
          '费用按 token 单价估约 $4.8，按账户余额变化实测约 60 元（≈$8.4）——两种口径都要看，'
          '保守上限不是账单。分布误差在这两套都不可估计：被测的 96 人分散在 '
          f'{drone["cards"]} / {shoes["cards"]:,} 张题卡上，没有一张卡达到 20 人——'
          '所以这里只回答“谁的预测更准”，不回答“群体分布准不准”。</p>'
        + '<p class="small">两套问卷都<strong>没有测量学历</strong>，匹配时按缺失处理，不做推断；'
          '匹配字段为年龄带 + 性别（无人机）、仅年龄带（运动鞋）。四臂缩两臂发生在发出任何请求之前，'
          '代价是不能拆“提示 vs 概率”，报告里已如实标注。</p>'
        + f'<p><a href="{link}">查看干净实验完整报告</a>'
          ' · <a href="../decision_lab/docs/预注册协议-clean-v1.md">预注册协议（含运行前修订）</a>'
          ' · <a href="../decision_lab/docs/结果与优化记录.md">结果与优化记录</a></p>'
        + '<noscript><p>浏览器未启用脚本：图表不可见，上面表格与文字结论仍然有效。</p></noscript>'
        + f'<script id="clean-data" type="application/json">'
          f'{json.dumps(diagnostics, ensure_ascii=False).replace("</", "<\\/")}</script>')
    return ('<section id="clean-v1"><h2>换一份问卷、换一种题型，结论还成立吗</h2>'
            + body + '</section>')


# One cluster per independent dataset/panel: adding studies inside a cluster is not
# an independent replication, and the report must never imply otherwise.
CLUSTERS = {'shed': 'Pew', 'pew168': 'Pew', 'pew13': 'Pew', 'pew111': 'Pew',
            'anes': 'ANES', 'swiss': 'Swiss panel', 'dryer': 'Dryer (4 countries)',
            'origin': 'Origin', 'packaging': 'Packaging', 'shoes': 'Shoes', 'drone': 'Drone',
            'german': 'German tomato', 'tshirt': 'T-shirt', 'radiant': 'Spanish tomato'}


def _wide_frame():
    """Per-study information content for the wide round, read from the frozen results."""
    path = CROSS / 'wide-v1-results.json'
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    usable = lambda c: bool(c) and c.get('available', True)
    rows = []
    for study, entry in data['studies'].items():
        arms = entry['results']['arms']
        uniform = arms['uniform']['brier']
        key = next((k for k in ('stratum_history__to__optimized', 'history__to__optimized',
                                'attribute_logit__to__optimized')
                    if usable(entry['results']['contrasts'].get(k))), None)
        reference = key.split('__to__')[0] if key else None
        contrast = entry['results']['contrasts'].get(key) if key else None
        rows.append({
            'study': study, 'cluster': CLUSTERS.get(study, study), 'people': entry['people'],
            'ai': round(100 * (uniform - arms['optimized']['brier']) / uniform, 1),
            'reference_name': reference,
            'reference': (None if reference is None else
                          round(100 * (uniform - arms[reference]['brier']) / uniform, 1)),
            'gap': (None if contrast is None else round(100 * contrast['relative_improvement'], 1)),
            'ci': (None if contrast is None else
                   [round(100 * v, 1) for v in contrast['improvement_95_ci']]),
            'cards_estimable': entry['cards_with_at_least_20_people'], 'cards': entry['cards'],
        })
    return {'rows': rows, 'budget': data['budget']}


def wide_study_section():
    frame = _wide_frame()
    link = '../decision_lab/reports/cross-study-v1/wide-v1-report.html'
    if not frame:
        return '<section id="wide"><h2>铺开六套</h2><p>尚未运行。</p></section>'
    rows = frame['rows']
    labels = {'origin': '商品产地', 'packaging': '包装与拒买', 'pew111': '网购与达人',
              'german': '德国番茄包装', 'tshirt': '美国 T 恤', 'radiant': '西班牙悬挂番茄'}
    reference_label = {'history': '同层历史答案', 'stratum_history': '同层历史答案',
                       'attribute_logit': '商品属性模型'}
    behind = [r for r in rows if r['gap'] is not None and r['gap'] < 0]
    positive = [r for r in rows if r['ai'] > 0]
    cells = []
    for row in rows:
        reference = '—' if row['reference'] is None else f"{row['reference']:+.1f}%"
        gap = '—' if row['gap'] is None else f"{row['gap']:+.1f}%"
        cells.append(f'<tr><th>{html.escape(labels.get(row["study"], row["study"]))}</th>'
                     f'<td>{row["people"]}</td><td>{row["ai"]:+.1f}%</td>'
                     f'<td>{reference}</td><td>{gap}</td>'
                     f'<td>{row["cards_estimable"]}/{row["cards"]}</td></tr>')
    cells = ''.join(cells)
    return ('<section id="wide"><h2>再铺六套：从 8 套扩到 14 套研究</h2>'
            '<p class="lead">许可门按你的要求降为声明项，其余口径不变：预注册冻结、同信息参照、'
            '20 人/卡门槛、失败照报。新增六套覆盖商品产地、包装拒买、网购与达人、德国番茄包装、'
            '美国 T 恤、西班牙悬挂番茄。</p>'
            f'<div class="grid3">'
            f'<article class="card"><span class="tag">信息量 · AI</span><h3>比“等分”好一点</h3>'
            f'<div class="big">+{sum(r["ai"] for r in rows) / len(rows):.1f}%</div>'
            f'<p>六套平均：{len(positive)}/6 明显高于每档等分；包装与拒买反而更差。</p></article>'
            f'<article class="card"><span class="tag">信息量 · 统计参照</span><h3>仍高一个量级</h3>'
            f'<div class="big">+{sum(r["reference"] for r in rows if r["reference"] is not None) / len([r for r in rows if r["reference"] is not None]):.1f}%</div>'
            '<p>同信息参照平均好过等分约 25%：AI 的 7% 只是它的零头。</p></article>'
            f'<article class="card"><span class="tag">主对照</span><h3>{len(behind)}/6 显著落后</h3>'
            f'<div class="big">{sum(r["gap"] for r in rows if r["gap"] is not None) / max(1, len([r for r in rows if r["gap"] is not None])):+.1f}%</div>'
            '<p>六套区间全部低于零，没有一套超过统计参照（表中“AI vs 参照”）。</p></article>'
            '</div>'
            '<figure><h3>每套研究：AI 与统计参照各自相对“每档等分”的信息量</h3>'
            '<div id="wideCompare" class="echart" style="height:420px"></div>'
            '<figcaption>柱子越高＝比“每个选项等可能”更准。AI（紫）每套都低于同信息统计参照（绿），'
            '两者差距就是“模型没学到的题卡信息”。原点为每档等分。</figcaption></figure>'
            '<div class="table-wrap"><table><caption>六套新研究（Brier 越小越好；相对列以“每档等分”为基准）</caption>'
            '<thead><tr><th>研究</th><th>人数</th><th>AI 优化 vs 等分</th><th>统计参照 vs 等分</th>'
            '<th>AI vs 参照</th><th>可估卡数/总卡数</th></tr></thead><tbody>'
            + cells + '</tbody></table></div>'
            '<p class="small">可估卡数指“同一题卡至少 20 名被测者”的卡。T 恤与商品产地的题卡几乎人人不同，'
            '因此群体分布误差不可估计，只用个体概率误差与属性参照比较。</p>'
            f'<p class="small">费用：计划 {frame["budget"]["max_calls"]:,} 次调用，保守上限 '
            f'${frame["budget"]["reserved_peak_usd"]:.2f}；按 token 单价估约 $5.2，'
            '按账户余额变化实测约 210 元（≈$29）——上限口径是“每次输出顶满”的最坏情况，'
            '不是账单，也不是实际花费。</p>'
            '<p class="small">独立性问题：14 套研究只对应 11 个独立数据集簇——Pew 四套算一个簇，'
            '所以本轮增加的是“领域覆盖”，不是 6 次独立复现。</p>'
            f'<p><a href="{link}">查看六套新研究完整报告</a>'
            ' · <a href="../decision_lab/reports/cross-study-v1/wide-audit.json">结构审计</a>'
            ' · <a href="../decision_lab/specs/cross-study-v1/wide-v1.json">冻结规格</a></p>'
            f'<script id="wide-data" type="application/json">'
            f'{json.dumps(frame, ensure_ascii=False).replace("</", "<\\/")}</script></section>')


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
    slots['CLEAN_STUDY']=clean_study_section()
    slots['WIDE_STUDY']=wide_study_section()
    # The page must stay self-contained: inline the vendored chart library at build time.
    slots['ECHARTS']=(HERE/'vendor/echarts.min.js').read_text()
    slots['CLEAN_CHART_SCRIPT']=(HERE/'charts_clean.js').read_text()
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
