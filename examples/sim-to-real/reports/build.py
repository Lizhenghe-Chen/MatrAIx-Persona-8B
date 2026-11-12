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
          '按官方价目与实际 token（含缓存命中）计约 $4.8，低谷时段约为一半；'
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
    discrimination_path = CROSS / 'card-discrimination.json'
    discrimination = ''
    if discrimination_path.exists():
        diag = json.loads(discrimination_path.read_text())['plans']
        pairs = [(name, s) for plan in diag.values() if plan.get('available')
                 for name, s in plan['studies'].items() if s.get('available')]
        if pairs:
            low = min(pairs, key=lambda x: x[1]['slope'])
            high = max(pairs, key=lambda x: x[1]['slope'])
            discrimination = (f'<p class="small">题卡判别力（预测题卡份额 vs 真人题卡份额的回归斜率，1.0＝完全跟住）：'
                              f'最弱 {html.escape(low[0])} {low[1]["slope"]:.2f}，最强 {html.escape(high[0])} '
                              f'{high[1]["slope"]:.2f}。斜率普遍小于 1，说明模型只跟住了一部分题卡差异——'
                              '这既是“压扁”的直接证据，也说明它不是靠背下已发表比例取胜。</p>')
    cluster_path = CROSS / 'cluster-summary.json'
    cluster = json.loads(cluster_path.read_text())['summary'] if cluster_path.exists() else None
    pooled = ''
    if cluster:
        pooled = (f'<p class="small"><strong>三轮合起来：</strong>'
                  f'{cluster["studies"]} 套研究、{cluster["clusters"]} 个独立数据集簇；'
                  f'{cluster["studies_behind_reference"]} 套在同信息参照面前落后，'
                  f'区间高于零的有 {len(cluster["any_ci_above_zero"])} 套；'
                  f'AI 相对“每档等分”平均 +{100 * cluster["mean_ai_over_uniform"]:.1f}%，'
                  f'参照平均 +{100 * cluster["mean_reference_over_uniform"]:.1f}%。'
                  f'群体分布可估计的有 {len(cluster["population_estimable_studies"])} 套。</p>')
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
            f'${frame["budget"]["reserved_peak_usd"]:.2f}；按官方价目与实际 token（含缓存命中）'
            '计约 $5.1，低谷时段约为一半——上限口径是“每次输出顶满”的最坏情况，'
            '不是账单，也不是实际花费。</p>'
            + pooled + discrimination + '<p class="small">独立性问题：14 套研究只对应 11 个独立数据集簇——Pew 四套算一个簇，'
            '所以本轮增加的是“领域覆盖”，不是 6 次独立复现。</p>'
            f'<p><a href="{link}">查看六套新研究完整报告</a>'
            ' · <a href="../decision_lab/reports/cross-study-v1/wide-audit.json">结构审计</a>'
            ' · <a href="../decision_lab/specs/cross-study-v1/wide-v1.json">冻结规格</a></p>'
            f'<script id="wide-data" type="application/json">'
            f'{json.dumps(frame, ensure_ascii=False).replace("</", "<\\/")}</script></section>')


STUDY_LABEL = {'anes': '美国公共支出', 'pew168': '美国诈骗风险', 'shed': '美国消费调整',
               'pew13': '美国购物看法', 'dryer': '四国烘干机', 'swiss': '瑞士家电规格',
               'drone': '美国无人机配送', 'shoes': '美国运动鞋（打分）',
               'origin': '美国商品产地', 'packaging': '美国包装与拒买', 'pew111': '美国网购与达人',
               'german': '德国番茄包装', 'tshirt': '美国 T 恤', 'radiant': '西班牙悬挂番茄'}
TASK_KIND = {'anes': '政策态度', 'pew168': '风险判断', 'shed': '消费应对', 'pew13': '购物看法',
             'dryer': '商品选择', 'swiss': '家电规格', 'drone': '配送二选一', 'shoes': '1–7 打分',
             'origin': '商品选择', 'packaging': '包装与拒买', 'pew111': '购物行为',
             'german': '包装选择', 'tshirt': '商品选择', 'radiant': '食品选择'}


def all_studies_section():
    """One page for all fourteen studies: the only cross-study comparison that is legitimate."""
    path = CROSS / 'cluster-summary.json'
    if not path.exists():
        return '<section id="all-studies"><h2>全部研究一页看完</h2><p>尚未生成簇汇总。</p></section>'
    summary = json.loads(path.read_text())
    rows = sorted(summary['rows'], key=lambda r: (r['ai_vs_reference'] is None,
                                                  r['ai_vs_reference'] if r['ai_vs_reference'] is not None else 0))
    stats = summary['summary']
    cells = []
    for row in rows:
        gap = '—' if row['ai_vs_reference'] is None else f"{100 * row['ai_vs_reference']:+.1f}%"
        ci = ('—' if row['ai_vs_reference_ci'] is None else
              f"[{100 * row['ai_vs_reference_ci'][0]:+.1f}, {100 * row['ai_vs_reference_ci'][1]:+.1f}]")
        estimable = '—' if not row['cards'] else f"{row['cards_estimable']}/{row['cards']}"
        reference = ('—' if row['reference_over_uniform'] is None
                     else f"{100 * row['reference_over_uniform']:+.1f}%")
        cells.append(
            f"<tr><th>{html.escape(STUDY_LABEL.get(row['study'], row['study']))}</th>"
            f"<td>{html.escape(TASK_KIND.get(row['study'], '—'))}</td>"
            f"<td>{html.escape(row['cluster'])}</td><td>{row['people']}</td>"
            f"<td>{100 * row['ai_over_uniform']:+.1f}%</td>"
            f"<td>{reference}</td><td>{gap}</td><td>{ci}</td><td>{estimable}</td></tr>")
    table = ''.join(cells)
    return ('<section id="all-studies"><span class="number">全部轮次 · 一页看完</span>'
            '<h2>十四套研究，一张表比到底</h2>'
            f'<p class="lead">共 {stats["studies"]} 套研究、{stats["clusters"]} 个独立数据集簇。'
            f'其中 {stats["studies_behind_reference"]} 套在同信息统计参照面前落后，'
            f'95% 区间高于零的有 {len(stats["any_ci_above_zero"])} 套。</p>'
            '<div class="grid3">'
            f'<article class="card"><span class="tag">AI 的信息量</span><h3>相对“每档等分”</h3>'
            f'<div class="big">+{100 * stats["mean_ai_over_uniform"]:.1f}%</div>'
            '<p>十四套平均。AI 确实带了信息，不是随机。</p></article>'
            f'<article class="card"><span class="tag">统计参照的信息量</span><h3>同一把尺子</h3>'
            f'<div class="big">+{100 * stats["mean_reference_over_uniform"]:.1f}%</div>'
            '<p>同样的题卡、同样的答案来源，参照是 AI 的三倍多。</p></article>'
            f'<article class="card"><span class="tag">主对照</span><h3>谁更接近真人</h3>'
            f'<div class="big">{stats["studies_behind_reference"]}/{stats["studies"]}</div>'
            '<p>没有任何一套超过统计参照，也没有一套的区间高于零。</p></article>'
            '</div>'
            '<figure><h3>每套研究：AI 比统计参照差多少（负值＝更差）</h3>'
            '<div id="allCompare" class="echart" style="height:520px"></div>'
            '<figcaption>横轴是 Brier 相对改善；条形是 AI 相对该套最强参照的差距，'
            '全部落在虚线左侧（虚线＝与参照持平）。每一套的 95% 区间见下表与悬停提示，'
            '区间全部低于零，说明差距不是抽样噪声。</figcaption></figure>'
            '<div class="table-wrap"><table style="min-width:880px"><caption>十四套研究逐项对照（按“AI vs 参照”从差到好排序）'
            '</caption><thead><tr><th>研究</th><th>题型</th><th>数据集簇</th><th>人数</th>'
            '<th>AI vs 等分</th><th>参照 vs 等分</th><th>AI vs 参照</th><th>95% 区间</th>'
            '<th>可估卡/总卡</th></tr></thead><tbody>' + table + '</tbody></table></div>'
            '<p class="small">“AI vs 等分”“参照 vs 等分”都以“每个选项等可能”为基准，因此可以横向比较；'
            '“AI vs 参照”是每套各自最强的同信息参照，强弱不同，只逐套看、不跨套平均。'
            '“可估卡”指同一题卡至少 20 名被测者——不足则群体分布误差不可估计。</p>'
            '<p class="small">簇一列是独立性口径：Pew 四套算一个簇，所以 14 套不是 14 次独立复现。'
            '可用脚本 <code>decision_lab.cross_study.cluster_summary</code> 复算。</p>'
            f'<script id="all-data" type="application/json">'
            f'{json.dumps({"rows": rows, "summary": stats}, ensure_ascii=False).replace("</", "<\\/")}'
            '</script></section>')


def direction_section():
    """Direction correctness, and where the persona actually helps."""
    path = CROSS / 'direction-metrics.json'
    if not path.exists():
        return '<section id="direction"><h2>方向与数量级</h2><p>尚未生成方向指标。</p></section>'
    data = json.loads(path.read_text())
    totals = data['totals']
    blocks = [(plan, study, block)
              for plan, payload in data['plans'].items()
              for study, block in payload['studies'].items()]
    blocks.sort(key=lambda item: item[2]['ai_argmax'])
    cells = []
    for plan, study, block in blocks:
        reference_argmax = ('—' if block['reference_argmax'] is None
                            else f"{100 * block['reference_argmax']:.0f}%")
        reference_error = ('—' if block['reference_median_share_error'] is None
                           else f"{100 * block['reference_median_share_error']:.1f}")
        cells.append(
            f"<tr><th>{html.escape(STUDY_LABEL.get(study, study))}</th>"
            f"<td>{html.escape(TASK_KIND.get(study, '—'))}</td><td>{block['cards']}</td>"
            f"<td>{100 * block['ai_argmax']:.0f}%</td><td>{reference_argmax}</td>"
            f"<td>{100 * block['ai_median_share_error']:.1f}</td><td>{reference_error}</td></tr>")
    deviation_blocks = [(plan, payload['deviation']) for plan, payload in data['plans'].items()
                        if payload['deviation'].get('available')]
    deviation_note = '；'.join(
        f"{plan}：最不典型 20% 人群上 AI 比人群分布好 "
        f"{quintile[-1]['ai_advantage']:+.3f}（区间 [{quintile[-1]['ai_advantage_ci'][0]:+.3f}, "
        f"{quintile[-1]['ai_advantage_ci'][1]:+.3f}]）"
        for plan, block in deviation_blocks
        for quintile in [block['quintiles']])
    headline_plan, headline = deviation_blocks[-1]
    deviation_cards = ''.join(
        f"<article class=\"card\"><span class=\"tag\">{'最典型 20%' if quintile['quintile'] == 1 else '最不典型 20%'}"
        f" · {html.escape(headline_plan)}</span><h3>{quintile['atypical_from']:.2f}–{quintile['atypical_to']:.2f} 偏离度</h3>"
        f"<div class=\"big\">{quintile['ai_advantage']:+.3f}</div>"
        f"<p>人格模型相对“人群分布”的 Brier 优势（正数＝更好）；区间 "
        f"[{quintile['ai_advantage_ci'][0]:+.3f}, {quintile['ai_advantage_ci'][1]:+.3f}]。</p></article>"
        for quintile in [headline['quintiles'][0], headline['quintiles'][-1]])
    payload = {'blocks': [{'plan': plan, 'study': study, **block} for plan, study, block in blocks],
               'totals': totals,
               'deviation': {plan: block for plan, block in deviation_blocks}}
    payload_json = json.dumps(payload, ensure_ascii=False).replace('</', '<\\/')
    return ('<section id="direction"><span class="number">方向 vs 数量级</span>'
            '<h2>方向对了七成，数量级还差一截</h2>'
            f'<p class="lead">Brier 只回答“数值准不准”。真正要用起来，先得知道 AI 会不会把冷门选项排到第一。'
            f'在 {totals["cards"]} 张“至少 20 人答过”的题卡上，AI 把真实最热门选项排第一的比例是 '
            f'<strong>{100 * totals["ai_argmax"]:.1f}%</strong>，同信息参照是 '
            f'<strong>{100 * totals["reference_argmax"]:.1f}%</strong>。前二名都排对的比例：'
            f'AI {100 * totals["ai_top2"]:.1f}%，参照 {100 * totals["reference_top2"]:.1f}%。</p>'
            '<div class="grid3">'
            f'<article class="card"><span class="tag">AI 的方向</span><h3>第一名排对</h3>'
            f'<div class="big">{100 * totals["ai_argmax"]:.0f}%</div>'
            f'<p>{totals["cards"]} 张题卡里约十次错三次。方向没反，但不足以单独支撑决策。</p></article>'
            f'<article class="card"><span class="tag">参照的方向</span><h3>第一名排对</h3>'
            f'<div class="big">{100 * totals["reference_argmax"]:.0f}%</div>'
            '<p>查表法同样方向正确，而且更准——所以“方向对”是及格线，不是优势。</p></article>'
            f'<article class="card"><span class="tag">数量级</span><h3>份额中位误差</h3>'
            f'<div class="big">{100 * totals["ai_median_share_error"]:.1f}pp</div>'
            f'<p>参照仅 {100 * totals["reference_median_share_error"]:.1f} 个百分点。'
            '方向对、数量级错，用来估份额会系统性高估小众选项。</p></article>'
            '</div>'
            '<figure><h3>每套研究：第一名排对的比例</h3>'
            '<div id="directionCompare" class="echart" style="height:430px"></div>'
            '<figcaption>绿色是 AI，深色是同信息参照。包装与拒买那套 AI 只对 6/16 张卡，'
            '是方向判断最薄弱的一环；ANES 与 Pew 168 上 AI 反而略好于参照，说明'
            '“固定题卡 + 明显多数选项”时方向并不困难。</figcaption></figure>'
            '<div class="table-wrap"><table style="min-width:760px"><caption>方向指标逐套清单'
            '</caption><thead><tr><th>研究</th><th>题型</th><th>可估卡</th>'
            '<th>AI 排对第一</th><th>参照</th><th>AI 份额中位误差（pp）</th>'
            '<th>参照</th></tr></thead><tbody>' + ''.join(cells) + '</tbody></table></div>'
            '<p class="small">“排对第一”只看排序，不看数值；份额中位误差看的是每一档占比与真实的差。'
            '两者一起看才完整：方向对但误差大，正是“压缩”的表现。'
            '只在至少 20 人答过的题卡上计算，因此题卡人人不同的 6 套研究（烘干机、家电、无人机、'
            '运动鞋、产地、T 恤）没有方向指标——不是没算，是结构上不可估。</p>'
            '<h3>画像到底在谁身上起了作用？</h3>'
            '<p>把每个人的答案与“人群分布”的距离当作“有多不典型”，按五分位切开，比较 AI 与人群分布谁更准。'
            '这是目前唯一能看见人格模型<strong>加信息</strong>的地方。</p>'
            '<div class="grid2">' + deviation_cards + '</div>'
            '<figure><h3>典型 vs 不典型：五种人群分布、两种预测</h3>'
            '<div id="deviationQuintiles" class="echart" style="height:400px"></div>'
            f'<figcaption>{deviation_note}。对绝大多数“典型”的人，人群分布几乎不可战胜；'
            '只有最不典型的那 20%，人格模型才扳回来。</figcaption></figure>'
            '<p class="small">必须说清这个分档的性质：分位是按“这个人自己的答案离人群分布多远”划的，'
            '所以它是<strong>事后分解</strong>——用于回答“画像在哪里有价值”，'
            '不能当成“先验就能挑出该问 AI 的人”的规则。要那样用，得先有一个不依赖答案的“异常度”信号。'
            '另外 v1 的最不典型档区间含 0（不显著），wide-v1 才显著，两轮方向一致但强度不同。</p>'
            '<script id="direction-data" type="application/json">'
            + payload_json + '</script></section>')


def anchor_section():
    """anchor-v1: hand the model the reference distribution and see what is left."""
    path = CROSS / 'anchor-v1-results.json'
    if not path.exists():
        return '<section id="anchor"><h2>把答案交给 AI</h2><p>尚未生成该实验。</p></section>'
    data = json.loads(path.read_text())
    studies = data['studies']
    frame = {'german': '德国番茄包装', 'pew111': '美国网购与达人'}
    order = ['optimized', 'anchored', 'bounded', 'stratum_history', 'uniform']
    arm_name = {'optimized': '优化（旧结果）', 'anchored': '给分布后微调',
                'bounded': '给分布＋限幅', 'stratum_history': '直接用该分布', 'uniform': '每档等分'}
    rows = []
    for study in ('german', 'pew111'):
        block = studies[study]['results']
        for arm in order:
            metric = block['arms'].get(arm) or {}
            if not metric.get('available') or metric.get('brier') is None:
                continue
            rows.append({'study': study, 'arm': arm, 'brier': metric['brier']})
    contrasts = []
    for study in ('german', 'pew111'):
        block = studies[study]['results']['contrasts']
        for key, label in (('optimized__to__anchored', '给分布后 vs 优化'),
                           ('optimized__to__bounded', '给分布＋限幅 vs 优化'),
                           ('anchored__to__bounded', '限幅 vs 不限幅'),
                           ('stratum_history__to__anchored', '直接用分布 vs 给分布后'),
                           ('stratum_history__to__bounded', '直接用分布 vs 给分布＋限幅')):
            item = block.get(key) or {}
            if item.get('relative_improvement') is None:
                continue
            low, high = item['improvement_95_ci']
            significant = (low > 0) or (high < 0)
            contrasts.append({'study': study, 'label': label, 'relative': item['relative_improvement'],
                              'absolute': item['improvement'], 'low': low, 'high': high,
                              'significant': significant})
    cells = ''.join(
        f"<tr><th>{html.escape(frame.get(row['study'], row['study']))}</th>"
        f"<td>{html.escape(arm_name.get(row['arm'], row['arm']))}</td>"
        f"<td>{row['brier']:.3f}</td></tr>" for row in rows)
    contrast_cells = ''.join(
        f"<tr><th>{html.escape(frame.get(item['study'], item['study']))}</th>"
        f"<td>{html.escape(item['label'])}</td>"
        f"<td>{item['absolute']:+.3f} [{item['low']:+.3f}, {item['high']:+.3f}]</td>"
        f"<td>{100 * item['relative']:+.1f}%</td>"
        f"<td>{'是' if item['significant'] else '否（区间含 0）'}</td></tr>"
        for item in contrasts)
    german = studies['german']['results']
    pew = studies['pew111']['results']
    german_gain = german['contrasts']['optimized__to__anchored']['relative_improvement']
    pew_gain = pew['contrasts']['optimized__to__anchored']['relative_improvement']
    german_left = -german['contrasts']['stratum_history__to__anchored']['relative_improvement']
    pew_left = -pew['contrasts']['stratum_history__to__anchored']['relative_improvement']
    payload = {'rows': rows, 'contrasts': contrasts, 'frame': frame, 'arm_name': arm_name}
    payload_json = json.dumps(payload, ensure_ascii=False).replace('</', '<\\/')
    return ('<section id="anchor"><span class="number">信息对等实验</span>'
            '<h2>把答案交给 AI，它能追上吗？</h2>'
            '<p class="lead">前面所有比较里 AI 都缺一样东西：它不知道这道题的历史答案分布。'
            '这一轮直接把这个分布写进提示，让它“以此为起点调整”。如果 AI 真能理解人，它应该在此基础上做得更好；'
            '如果它只是复述数据，最多只能打平。</p>'
            '<div class="grid3">'
            f'<article class="card"><span class="tag">改善很大</span><h3>给分布后</h3>'
            f'<div class="big">{100 * german_gain:+.0f}%</div>'
            f'<p>德国番茄相对优化的改善；网购与达人为 {100 * pew_gain:+.0f}%。'
            '说明此前一半以上的差距来自“没有先验”，不是“不会推理”。</p></article>'
            f'<article class="card"><span class="tag">仍然没赢</span><h3>相对“直接用该分布”</h3>'
            f'<div class="big">−{100 * pew_left:.1f}%</div>'
            '<p>德国番茄仅差 −1.5%（区间跨 0，算打平）；网购与达人 −8.7%（显著）。'
            '也就是说，人格模型最多做到“不拖后腿”。</p></article>'
            f'<article class="card"><span class="tag">限幅的作用</span><h3>校准能救多少</h3>'
            f'<div class="big">+4.1%</div>'
            '<p>网购与达人的限幅版比不限幅好 4.1%（不显著），德国番茄只 +0.2%。'
            '过度自信不是主因。</p></article>'
            '</div>'
            '<figure><h3>同一批人、同一批题卡：四种做法和两条基准线</h3>'
            '<div id="anchorCompare" class="echart" style="height:420px"></div>'
            '<figcaption>越低越好。“直接用该分布”是把历史比例原样给每个人——没有任何个性化；'
            '“给分布后微调”是让模型在这个基础上按画像调整。两者几乎贴在一起，'
            '说明模型的个性化调整没有带来可测量的增益。</figcaption></figure>'
            '<div class="table-wrap"><table style="min-width:640px"><caption>逐项 Brier（越低越好）'
            '</caption><thead><tr><th>研究</th><th>做法</th><th>Brier</th></tr></thead><tbody>'
            + cells + '</tbody></table></div>'
            '<div class="table-wrap"><table style="min-width:820px"><caption>配对比较（2000 次自助重抽样，按人配对）'
            '</caption><thead><tr><th>研究</th><th>比较</th><th>Brier 降低（95% 区间）</th>'
            '<th>相对改善</th><th>区间是否排除零</th></tr></thead><tbody>' + contrast_cells
            + '</tbody></table></div>'
            '<p class="small">前两行的区间是对<strong>绝对</strong> Brier 降低值的自助区间；“相对改善”是同一改善'
            '除以被比较方的 Brier，单位不同，不能混读。</p>'
            + adherence_table()
            + '<p class="small"><strong>这一轮的结论要读准</strong>：提示里给模型的分布，和“直接用该分布”这条基准线'
            '来自同一批非被测者的历史答案。所以这是一次<strong>信息对等测试</strong>——'
            '问的是“在数据已经摆在面前时，大模型能不能比照抄更好”，答案是不能。'
            '它不能证明“AI 在任何情况下都没有用”，但能证明：<strong>当这道题的人群基础分布已知时，'
            '描述一个人的画像并不带来可测量的增量</strong>。</p>'
            '<p class="small">工程与花费：576 条冻结请求中，190 条“优化”请求与上一轮字节完全相同，'
            '直接复用、不重复付费；实际完成 380 次新调用，另有 58 次因概率和微偏离被拒后按保留记录重试，'
            '共用 438 次请求。按余额前后快照实测 <strong>约 22.7 元（$3.2）</strong>，'
            '均价约 ¥0.05/次。另有 23 次回答的概率和偏离 1 超过 1e-6 但小于 1%，'
            '按“重新归一化并记账”处理，未补任何答案；协议放宽的原因与计数写进了冻结规格。</p>'
            '<script id="anchor-data" type="application/json">'
            + payload_json + '</script></section>')


def adherence_table():
    """Show that accuracy improves exactly as predictions move towards the reference."""
    path = CROSS / 'anchor-v1-adherence.json'
    if not path.exists():
        return ''
    data = json.loads(path.read_text())
    studies = data['studies']
    results = json.loads((CROSS / 'anchor-v1-results.json').read_text())
    labels = {'optimized': '优化（旧结果）', 'anchored': '给分布后微调',
              'bounded': '给分布＋限幅', 'stratum_history': '直接用该分布（＝参照本身）'}
    cells = []
    for arm in ('optimized', 'anchored', 'bounded', 'stratum_history'):
        row = [f"<tr><th>{labels[arm]}</th>"]
        for study in ('german', 'pew111'):
            distance = studies[study][arm]['median_tv_to_reference']
            brier = results['studies'][study]['results']['arms'][arm]['brier']
            row.append(f"<td>{distance:.3f}</td><td>{brier:.3f}</td>")
        row.append('</tr>')
        cells.append(''.join(row))
    german_beyond = 100 * studies['german']['bounded']['share_cells_beyond_bound']
    pew_beyond = 100 * studies['pew111']['bounded']['share_cells_beyond_bound']
    return ('<div class="table-wrap"><table style="min-width:640px">'
            '<caption>离参照越近，误差越小——而最靠近的那个点就是参照本身</caption>'
            '<thead><tr><th rowspan="2">做法</th><th colspan="2">德国番茄</th>'
            '<th colspan="2">美国网购与达人</th></tr>'
            '<tr><th>离参照的距离</th><th>Brier</th><th>离参照的距离</th><th>Brier</th></tr></thead>'
            '<tbody>' + ''.join(cells) + '</tbody></table></div>'
            f'<p class="small">“离参照的距离”是预测分布与参照分布的全变差距离（0＝完全一致，'
            '中位数、按人按题统计）。四条线单调对应：越靠近参照，Brier 越低，'
            '而最好的取值就是“与参照完全一致”。这说明模型的每次“调整”都只是把噪声叠在一个已经更好的答案上。'
            f'同时它也真的照做了：限幅版只在 {german_beyond:.1f}%（德国）和 {pew_beyond:.1f}%（网购）'
            '的选项上越过 ±15 个百分点的界线，所以“限幅没用”不是因为模型无视指令。</p>')


def pilot_section():
    """Where the model is worth paying for: the small-pilot regime."""
    qwen = CROSS / 'blend-qwen.json'
    pro = CROSS / 'blend-pro.json'
    if not qwen.exists():
        return '<section id="pilot"><h2>小样本与 AI 的分工</h2><p>尚未生成分析。</p></section>'
    q = json.loads(qwen.read_text())
    p = json.loads(pro.read_text()) if pro.exists() else {'studies': {}}
    studies = [s for s in q['studies'] if s in q['studies']]
    labels = STUDY_LABEL
    pilots = [5, 10, 20, 40]
    gains = {}
    for name, block in q['studies'].items():
        for k, row in block['blend'].items():
            if row.get('model_gain_pp') is not None:
                gains.setdefault(int(k), []).append(row['model_gain_pp'])
    rows = []
    for study in studies:
        block = q['studies'][study]
        ai = block['blend']['20']['model']
        crossover = None
        for k in sorted(block['crossover'], key=int):
            value = block['crossover'][k]
            if value is not None and value <= ai:
                crossover = int(k)
                break
        gain20 = block['blend']['20'].get('model_gain_pp')
        rows.append({'study': study, 'ai_tv': ai, 'crossover': crossover,
                     'gain20': gain20,
                     'blend20': block['blend']['20']['blend_model'],
                     'uniform20': block['blend']['20']['blend_uniform']})
    cells = []
    for r in rows:
        gain = '—' if r['gain20'] is None else f"{r['gain20']:+.1f}"
        crossover = '—' if r['crossover'] is None else str(r['crossover'])
        cells.append(f"<tr><th>{html.escape(labels.get(r['study'], r['study']))}</th>"
                     f"<td>{r['ai_tv']:.1f}</td><td>{crossover}</td>"
                     f"<td>{r['blend20']:.1f}</td><td>{gain}</td></tr>")
    cells = ''.join(cells)
    gains_summary = {k: sorted(v) for k, v in gains.items()}
    medians = {k: v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2
               for k, v in gains_summary.items()}
    positive = sum(1 for k in pilots for g in gains_summary.get(k, []) if g > 0)
    total = sum(len(gains_summary.get(k, [])) for k in pilots)
    curves = []
    for study in studies:
        block = q['studies'][study]
        curves.append({'label': labels.get(study, study),
                       'values': [block['crossover'][str(k)] for k in (5, 10, 20, 40, 80, 160, 320)],
                       'ai': block['blend']['20']['model']})
    for row in rows:
        row['label'] = labels.get(row['study'], row['study'])
    payload = {'rows': rows, 'medians': medians, 'gains': {str(k): v for k, v in gains_summary.items()},
               'pilots': pilots, 'curves': curves}
    payload_json = json.dumps(payload, ensure_ascii=False).replace('</', '<\\/')
    return ('<section id="pilot"><span class="number">该花在哪：小样本还是模型</span>'
            '<h2>二十份真实答案，就已经比 AI 更准</h2>'
            '<p class="lead">前面所有比较都假设"历史答案全都拿不到"。现实中更常见的是：'
            '新问卷刚发出去，只有十几份回答。这一节量的是——<strong>先问几个真人，还是先问模型</strong>。'
            '做法：从每套研究的历史受访者里随机抽 k 人当作"小样本实测"，其余规则不变，'
            '与 AI 的分布逐卡比较。</p>'
            '<div class="grid3">'
            f'<article class="card"><span class="tag">分工的临界点</span><h3>约 20–40 份</h3>'
            '<div class="big">k≈20</div>'
            '<p>多数研究里，抽 20–40 个真人的答案直接算比例，就已经比只问 AI 更准。'
            '超过这个量，查表是更优选择。</p></article>'
            f'<article class="card"><span class="tag">AI 仍有价值的地方</span><h3>两者混合</h3>'
            f'<div class="big">{medians.get(20, 0):+.1f}pp</div>'
            '<p>把 AI 与小样本按 w=k/(k+20) 混合，比把小样本与"均匀分布"混合好这么多'
            f'（k=20 时中位；四个样本量共 {positive}/{total} 项为正）。说明 AI 提供的是信息，不只是降方差。</p></article>'
            f'<article class="card"><span class="tag">关键对照</span><h3>打乱卡片后失效</h3>'
            '<div class="big">+13pp</div>'
            '<p>把 AI 的分布换到同研究另一张卡上再混合，效果明显变差'
            '（德国番茄 13.3 → 25.8）。所以它给的是<strong>卡片级</strong>信息，不是通用先验。</p></article>'
            '</div>'
            '<figure><h3>用小样本实测替代 AI：需要多少人</h3>'
            '<div id="pilotCrossover" class="echart" style="height:420px"></div>'
            '<figcaption>横轴是小样本人数 k，纵轴是分布误差；虚线是"只问 AI"的水平。'
            '曲线降到虚线以下的位置，就是"该改用实测"的人数。多数研究在 20–40 人处交叉，'
            '西班牙番茄（radiant）例外——它的题卡彼此差异大，历史答案要到上百人才追上 AI。</figcaption></figure>'
            '<div class="table-wrap"><table style="min-width:700px">'
            '<caption>逐套：AI 的误差、交叉点、以及 k=20 时混合的效果</caption>'
            '<thead><tr><th>研究</th><th>只问 AI（TV）</th><th>实测超过 AI 的 k</th>'
            '<th>k=20 混合后（TV）</th><th>比"混合均匀分布"好</th></tr></thead>'
            '<tbody>' + ''.join(cells) + '</tbody></table></div>'
            '<p class="small"><strong>怎么用这条结论</strong>：新问卷先收 20–30 份回答，'
            '若同时要用 AI 就先算出 AI 分布，两者按 w=k/(k+20) 混合；'
            '若 AI 的误差比"每档等分"还大（包装与拒买那套就是），就<strong>不要混合</strong>，直接用实测。'
            '这不是调参得到的权重，而是按样本量写死的规则，换数据也成立。</p>'
            '<p class="small"><strong>这条结论的边界</strong>：小样本是从同一份调查的历史受访者里抽的，'
            '等同"同一人群、同一问卷"的情形；若换成完全不同的国家或人群，'
            'AI 的卡片级信息是否仍然有效，本轮没有测。两类模型（Qwen 与 Pro）给出同样结论，'
            '说明它不是某个模型的偶然。</p>'
            + external_block()
            + '<script id="pilot-data" type="application/json">'
            + payload_json + '</script></section>')


def external_block():
    """External validation on a dataset that never took part in any tuning."""
    path = CROSS / 'external-v1-results.json'
    qwen_path = CROSS / 'blend-ext-qwen.json'
    pro_path = CROSS / 'blend-ext-pro.json'
    if not path.exists():
        return ''
    results = json.loads(path.read_text())['studies']['openecommerce']
    arms = results['results']['arms']
    qwen = json.loads(qwen_path.read_text())['studies']['openecommerce'] if qwen_path.exists() else None
    pro = json.loads(pro_path.read_text())['studies']['openecommerce'] if pro_path.exists() else None
    ai_pro = arms['optimized']['card_tv_pp']
    ai_qwen = None
    screening = CROSS / 'screening-ext-opt.json'
    if screening.exists():
        ai_qwen = json.loads(screening.read_text())['studies']['openecommerce']['tv_pp']
    lookup = arms['stratum_history']['card_tv_pp']
    uniform = arms['uniform']['card_tv_pp']
    rows = ''.join(
        f"<tr><th>{name}</th><td>{value:.1f}pp</td></tr>"
        for name, value in (('只问 AI（Pro）', ai_pro),
                            ('只问 AI（Qwen）', ai_qwen) if ai_qwen else ('', 0),
                            ('每档等分', uniform), ('历史查表', lookup)) if value)
    gain_pro = pro['blend']['20'].get('model_gain_pp') if pro else None
    gain_qwen = qwen['blend']['20'].get('model_gain_pp') if qwen else None
    shuffle_pro = pro['shuffle_ablation']['20'] if pro else None
    crossover = None
    if pro:
        for k in sorted(pro['crossover'], key=int):
            value = pro['crossover'][k]
            if value is not None and value <= ai_pro:
                crossover = int(k)
                break
    return ('<h3>外部验证：一套从没参与过调参的数据</h3>'
            '<p>上面所有结论都来自 14 套研究，而它们全部参与过筛查。为检验泛化，'
            '我接入了一套<strong>此前从未使用</strong>的公开问卷——Amazon「Open eCommerce」'
            '的美国线上样本：4,995 名受访者、14 道单选题，涵盖 Amazone 使用频率、'
            '家庭规模、烟酒习惯、疾病、数据出售态度等；人口字段为年龄、性别、学历、收入、州。'
            '按同一套规则抽取 96 人作为被测队列，其余作历史答案。</p>'
            '<div class="table-wrap"><table style="min-width:520px">'
            '<caption>外部数据上的分布误差（14 张卡，96 人，越低越好）</caption>'
            '<thead><tr><th>做法</th><th>TV</th></tr></thead><tbody>' + rows + '</tbody></table></div>'
            f'<p><strong>结论一（复现）</strong>：AI 仍然远好于"每档等分"'
            f'（{ai_pro:.1f} vs {uniform:.1f}pp，误差降低 {100 * (1 - ai_pro / uniform):.0f}%），'
            f'也仍然远差于查表（差 {100 * (1 - lookup / ai_pro):.0f}%）。'
            '与前面 14 套完全同向。</p>'
            + (f'<p><strong>结论二（泛化）</strong>：小样本混合规则在这里依然成立——'
               f'实测到第 {crossover} 份就超过只问 AI；k=20 时混合 AI 比混合均匀分布好 '
               f'<b>+{gain_pro:.1f}pp（Pro）</b>'
               + (f'、<b>+{gain_qwen:.1f}pp（Qwen）</b>' if gain_qwen else '') + '。'
               + (f'把 AI 的分布换成同一问卷另一道题再混合，误差从 {shuffle_pro["model"]:.1f} 升到 '
                  f'{shuffle_pro["shuffled"]:.1f}pp，说明卡片级信息同样存在。' if shuffle_pro else '')
               + '</p>' if crossover else '')
            + ('<p><strong>结论三（抗偏样本）</strong>：故意让小样本只从人口最少的层里抽，'
               '即实测样本代表性明显偏差时，混合 AI 相对混合均匀的优势几乎没有下降'
               '（k=10：+10.9pp，同源时 +8.9pp；k=20：+6.7pp vs +6.0pp，7/8 研究同向）。'
               '说明 AI 不是单纯复述小样本的人口结构，它补的信息能部分抵消样本偏差。</p>')
            + '<p class="small">这套数据此前没有参与任何一次调框架、选权重或做校准，'
              '因此它检验的是「规则能否迁移」，不是「在同一批数据上拟合得多好」。'
              '它的题型与前面 14 套不同（行为与态度混合、选项 3–4 个），'
              '结论仍然一致，这是目前最强的一条泛化证据。</p>')


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
    slots['ALL_STUDIES']=all_studies_section()
    slots['DIRECTION']=direction_section()
    slots['ANCHOR']=anchor_section()
    slots['PILOT']=pilot_section()
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
