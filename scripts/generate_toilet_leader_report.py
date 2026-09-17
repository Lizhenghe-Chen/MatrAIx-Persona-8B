#!/usr/bin/env python3
"""Generate the leadership-friendly single-file HTML report for the
toilet-brush shopping simulation (North America, 1000 personas).

Charts are deterministic inline SVG (no CDN/JS needed) so the file opens
anywhere offline. Product photos are referenced from results/toilet_brush_assets/.

Usage: uv run python scripts/generate_toilet_leader_report.py
Output: results/toilet_brush_leader_report.html
"""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "toilet-brush-demo" / "toilet_brush_leader_report.html"
summary = json.loads((REPO / "results" / "toilet-brush-demo" / "toilet_brush_summary.json").read_text(encoding="utf-8"))

P = summary["products"]
MS = summary["market_share"]
SAMPLE = summary["sample"]
THR = summary["price_threshold"]
SENS = summary["price_sensitivity"]
LIKE = summary["purchase_likelihood"]
FEAT = summary["feature_priority"]
AGE_X = summary["choice_x_age"]
ECON_X = summary["choice_x_econ"]
GENDER_X = summary["choice_x_gender"]
SOCIO_X = summary["choice_x_socio"]
REV = summary["product_reviews"]
CONS = summary["consideration"]
PRICE = summary["chosen_price"]

ORDER = [
    "clorox_under_rim", "mdesign_compact", "boomjoy_tweezer", "sellemer_silicone",
    "oxo_hideaway", "ibergrif_silicone", "ixo_stainless", "nacena_long",
    "asobeage_silicone", "jiga_3pack", "none_of_these",
]
PROD_CN = {
    "clorox_under_rim": "Clorox 角落多功能",
    "mdesign_compact": "mDesign 古铜收纳款",
    "boomjoy_tweezer": "BOOMJOY 硅胶+镊子",
    "sellemer_silicone": "Sellemer 硅胶透气款",
    "oxo_hideaway": "OXO 隐藏式",
    "ibergrif_silicone": "Ibergrif 硅胶快干款",
    "ixo_stainless": "IXO 不锈钢双支装",
    "nacena_long": "nacena 长柄双支装",
    "asobeage_silicone": "Asobeage 硅胶白款",
    "jiga_3pack": "JIGA 三支装",
    "none_of_these": "都不买",
}
IMG = {
    "clorox_under_rim": ("assets/clorox.jpg", "白色刷柄+深灰防滑握把，附角落收纳架"),
    "mdesign_compact": ("assets/mdesign.jpg", "深古铜哑光金属质感，圆柱收纳桶"),
    "boomjoy_tweezer": ("assets/boomjoy.jpg", "白灰杆+黑色硅胶刷头，透气底座"),
    "sellemer_silicone": ("assets/sellemer.jpg", "白色长柄，黑色硅胶刷头，白底黑边底座"),
    "oxo_hideaway": ("assets/oxo.jpg", "浅灰白色流线刷柄+极简圆桶罐身"),
    "ibergrif_silicone": ("assets/ibergrif.jpg", "白柄银杆+黑色硅胶刷头，快干底座"),
    "ixo_stainless": ("assets/ixo.jpg", "深海军蓝底座+银色不锈钢杆，双支装"),
    "nacena_long": ("assets/nacena.jpg", "哑光黑长柄+圆柱收纳桶，双支装"),
    "asobeage_silicone": ("assets/asobeage.jpg", "白柄+黑色圆点硅胶头，白圆柱底座"),
    "jiga_3pack": ("assets/jiga2.jpg", "三支白色套装+同色收纳桶，超值组合"),
    "none_of_these": ("", ""),
}
PRICE_STR = {k: f"${v['price']:.2f}".rstrip("0").rstrip(".") for k, v in P.items()}

TOP_SELLERS = sorted([k for k in ORDER if k != "none_of_these"],
                     key=lambda k: MS[k]["count"], reverse=True)
NONE_RATE = MS["none_of_these"]["share_pct"]


def esc(v):
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg_hbar(items, *, width=680, row_h=40, label_w=200, max_val=None, value_fmt="{v}", title=""):
    if max_val is None:
        max_val = max(v for _, v, _ in items) or 1
    n = len(items)
    height = 36 + n * row_h
    plot_x, plot_w = label_w, width - label_w - 90
    rows = []
    for i, (label, val, color) in enumerate(items):
        y = 42 + i * row_h
        bw = int(plot_w * val / max_val) if max_val else 0
        bw = max(bw, 2 if val > 0 else 0)
        rows.append(
            f'<g><text x="{label_w - 12}" y="{y + 21}" text-anchor="end" class="lbl">{esc(label)}</text>'
            f'<rect x="{plot_x}" y="{y + 8}" width="{bw}" height="24" rx="4" fill="{color}"/>'
            f'<text x="{plot_x + bw + 8}" y="{y + 26}" class="val">{value_fmt.format(v=val)}</text></g>'
        )
    return (f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" class="chart" '
            f'role="img" aria-label="{esc(title)}">' + "".join(rows) + "</svg>")


def svg_stacked_pct(rows, *, width=680, row_h=42, label_w=170, title=""):
    n = len(rows)
    height = 36 + n * row_h
    plot_x, plot_w = label_w, width - label_w - 10
    out = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" class="chart" '
           f'role="img" aria-label="{esc(title)}">']
    colors = ["#2563EB", "#10B981", "#F59E0B", "#8B5CF6", "#DC2626", "#64748B", "#7C98B3", "#0EA5E9", "#F472B6", "#A3A3A3"]
    for i, (row_label, segs, n_label) in enumerate(rows):
        y = 42 + i * row_h
        out.append(f'<text x="{plot_x - 12}" y="{y + 21}" text-anchor="end" class="lbl">{esc(row_label)}</text>')
        x = plot_x
        tot = sum(s[1] for s in segs)
        for j, (key, share, _label) in enumerate(segs):
            w = plot_w * share / 100.0
            color = colors[j % len(colors)]
            if w >= 20:
                out.append(f'<rect x="{x:.1f}" y="{y + 8}" width="{w:.1f}" height="24" rx="3" fill="{color}"/>')
                out.append(f'<text x="{x + w / 2:.1f}" y="{y + 26}" text-anchor="middle" class="seg">{share:.0f}%</text>')
            else:
                out.append(f'<rect x="{x:.1f}" y="{y + 8}" width="{max(w, 3):.1f}" height="24" rx="3" fill="{color}"/>')
            x += w
        out.append(f'<text x="{plot_x + plot_w + 6}" y="{y + 26}" class="seg2">{esc(n_label)}</text>')
    out.append("</svg>")
    return "".join(out)


def svg_vbar(items, *, width=680, height=260, title=""):
    n = len(items)
    pad_l, pad_b, pad_t = 46, 34, 10
    plot_w = width - pad_l - 12
    plot_h = height - pad_t - pad_b
    max_v = max(v for _, v in items) or 1
    rows = []
    for i, (label, val) in enumerate(items):
        x = pad_l + plot_w * i / n
        bw = plot_w / n * 0.62
        bh = int(plot_h * val / max_v)
        y = pad_t + plot_h - bh
        rows.append(
            f'<g><rect x="{x:.1f}" y="{y}" width="{bw:.1f}" height="{bh}" rx="3" fill="#2563EB"/>'
            f'<text x="{x + bw / 2:.1f}" y="{y - 6}" text-anchor="middle" class="seg">{val}</text>'
            f'<text x="{x + bw / 2:.1f}" y="{pad_t + plot_h + 20}" text-anchor="middle" class="axis">{esc(label)}</text></g>'
        )
    return (f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" class="chart" '
            f'role="img" aria-label="{esc(title)}">' + "".join(rows) + "</svg>")


def seller_chart():
    items = [(f"{PROD_CN[k]}  {PRICE_STR[k]}", MS[k]["count"], "#2563EB") for k in TOP_SELLERS]
    items.append(("都不买", MS["none_of_these"]["count"], "#CBD5E1"))
    return svg_hbar(items, label_w=210, value_fmt="{v} 人", title="各商品得票")


def price_bracket():
    # group by price tier
    tiers = {}
    for k in ORDER:
        if k == "none_of_these":
            continue
        t = P[k]["tier"]
        tiers.setdefault(t, [0, []])
        tiers[t][0] += MS[k]["count"]
        tiers[t][1].append(k)
    names = {"低": "低价带 $12.99–15.50", "中": "中价带 $19.97–25.70", "中高": "中高价带 $28.60–29.30"}
    items = [(names[t], v, "#10B981" if t == "低" else "#F59E0B" if t == "中" else "#8B5CF6")
             for t, (v, ks) in sorted(tiers.items(), key=lambda kv: -kv[1][0])]
    return svg_hbar(items, label_w=230, value_fmt="{v} 人", title="按价格带汇总得票")


def segment_chart(dim_key, dim_label, top_n=6):
    dim = {"age": AGE_X, "econ": ECON_X, "gender": GENDER_X, "socio": SOCIO_X}[dim_key]
    segs = sorted(dim.keys(), key=lambda s: -sum(v["count"] for v in dim[s].values()))[:8]
    top = TOP_SELLERS[:top_n]
    rows = []
    for s in segs:
        tot = sum(v["count"] for v in dim[s].values()) or 1
        segs_rows = [(k, round(dim[s][k]["share_pct"], 1), PROD_CN[k]) for k in top]
        other = 100 - sum(sr[1] for sr in segs_rows)
        if other > 0.5:
            segs_rows.append(("__other__", round(other, 1), "其他/都不买"))
        rows.append((f"{s} (n={tot})", segs_rows, ""))
    return svg_stacked_pct(rows, title=f"选择 × {dim_label}")


def kpi_cards():
    top0 = TOP_SELLERS[0]
    cards = [
        ("1000", "虚拟消费者（全部北美）"),
        (f"{PRICE_STR[top0]}", f"销冠 {PROD_CN[top0]} 单价"),
        (f"{MS[top0]['share_pct']}%", f"{PROD_CN[top0]} 市场份额"),
        (f"{NONE_RATE}%", "「都不买」占比"),
        (f"{SAMPLE['reward_rate'] * 100:.0f}%", "数据通过率"),
        (f"${PRICE['median']:.2f}", "成交价中位数"),
    ]
    cards2 = [
        ("$0.62", "API 成本（1000 人）"),
        ("25m17s", "全量运行耗时"),
        ("20", "并行度"),
        ("24m→", "pilot→全量节奏"),
    ]
    k1 = "".join(f'<div class="kpi"><div class="v">{esc(v)}</div><div class="l">{esc(l)}</div></div>' for v, l in cards)
    k2 = "".join(f'<div class="kpi"><div class="v">{esc(v)}</div><div class="l">{esc(l)}</div></div>' for v, l in cards2)
    return f'<div class="kpis">{k1}</div><div class="kpis">{k2}</div>'


def version_compare():
    """v1 (with recommendation badges) vs current (cleaned) market share."""
    v1_path = REPO / "results" / "toilet-brush-demo" / "backup_v1_with_badges" / "toilet_brush_summary.json"
    if not v1_path.exists():
        return "<p class='note'>未找到 v1 对比数据（backup_v1_with_badges/），跳过版本对比。</p>"
    try:
        v1 = json.loads(v1_path.read_text(encoding="utf-8"))
    except Exception:
        return "<p class='note'>v1 对比数据读取失败，跳过版本对比。</p>"
    v1_ms = v1["market_share"]
    rows = []
    for k in ORDER:
        if k == "none_of_these":
            continue
        cur = MS[k]["share_pct"]
        old = v1_ms[k]["share_pct"]
        delta = cur - old
        arrow = "▲" if delta > 0.05 else ("▼" if delta < -0.05 else "—")
        rows.append(f"<tr><td>{esc(PROD_CN[k])}</td><td>{PRICE_STR[k]}</td>"
                    f"<td>{old:.1f}%</td><td>{cur:.1f}%</td><td>{arrow} {delta:+.1f}%</td></tr>")
    return f"""
    <table>
      <thead><tr><th>商品</th><th>参考价</th><th>v1（含推荐标识）</th><th>v2（净化货架）</th><th>变化</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    <p class='note'>v1 货架在 Clorox/OXO 卖点中含 "Amazon's Choice"、"No.1 Top Rated" 推荐标识；v2 已全部移除，只保留价格/材质/外观/功能。
    对比可见：移除后 OXO 份额回落（81.3%→77.7%），JIGA/Clorox 等回升，0 票商品从 4 款减少到 2 款 —— 推荐标识有真实放大效应，净化后数据更客观。</p>"""


def insights():
    items = [
        ("货架描述需统一口径", "推荐性标识（Amazon's Choice / Top Rated）会显著放大对应商品的份额，对比不同货架/竞品前必须统一净化，否则结论失真。"),
        ("「隐藏+防积水+紧凑」是北美强需求", "OXO 即使去掉推荐标识仍以 77.7% 领先，核心卖点（隐藏式收纳、防积水托盘、小浴室适配、品牌信任）是真实需求锚点。"),
        ("低价价值型消费者真实存在", "$12.99–13.99 价格带的 JIGA(11.8%)+Clorox(8.0%) 合计约 20%，「三支装/抗菌/性价比」卖点能吸引预算敏感人群。"),
        ("0 票商品是定位问题", "mDesign/Asobeage 无人购买的原因是同质化（与低价硅胶款相似但更贵）或卖点不突出（见证据链），建议差异化定价或强化卖点。"),
        ("模拟可用于选品与定价预判", "本方法可在 25 分钟、约 $0.6 成本内预判新品/货架的相对份额结构，适合做假设检验；结论需真实市场验证后再决策。"),
    ]
    return "<ol>" + "".join(f"<li><b>{esc(t)}</b>：{esc(d)}</li>" for t, d in items) + "</ol>"


def product_cards():
    out = []
    for rank, k in enumerate(TOP_SELLERS, 1):
        img, look = IMG[k]
        rev = REV.get(k, {})
        kw = rev.get("keywords", {})
        kw_str = "、".join(f"{a} {b['pct']:.0f}%" for a, b in sorted(kw.items(), key=lambda x: -x[1]["pct"])[:4]) if kw else "—"
        cons = CONS.get(k, {})
        went = "、".join(f"{PROD_CN[x]} {y}" for x, y in list(cons.get("went_to", {}).items())[:3]) or "—"
        img_tag = f'<img src="{esc(img)}" alt="{esc(PROD_CN[k])}">' if img else '<div class="noimg">无商品图</div>'
        out.append(f"""
        <div class="pcard {'winner' if rank == 1 else ''}">
          <div class="pimg">{img_tag}</div>
          <div class="pbody">
            <div class="prank">#{rank} · {MS[k]['share_pct']}% 份额（{MS[k]['count']} 票）</div>
            <div class="pname">{esc(PROD_CN[k])}</div>
            <div class="pprice">参考价 {PRICE_STR[k]} USD · {esc(P[k]['material'])}</div>
            <div class="plook">外观：{esc(look)}</div>
            <div class="psell">卖点：{esc(P[k]['selling'])}</div>
            <div class="pkw">理由关键词：{kw_str}</div>
            <div class="pwent">未买者转投：{went}</div>
          </div>
        </div>""")
    return "".join(out)


def zero_vote_evidence():
    out = []
    zeros = [k for k in ORDER if k != "none_of_these" and MS[k]["count"] == 0]
    if not zeros:
        return "<p>本轮模拟没有 0 票商品。</p>"
    for k in zeros:
        cons = CONS.get(k, {})
        n_cons = cons.get("considered_by", 0)
        samples = cons.get("sample_rationales", [])
        block = f'<div class="zitem"><b>{esc(PROD_CN[k])}</b>（{PRICE_STR[k]}）— 0 票；被 {n_cons} 人考虑过，最终放弃。'
        if samples:
            block += "<ul>" + "".join(f"<li>“{esc(s)}”</li>" for s in samples) + "</ul>"
        block += "</div>"
        out.append(block)
    return "".join(out)


def rationale_samples():
    rows_csv = list(__import__("csv").DictReader(
        open(REPO / "results" / "toilet-brush-demo" / "toilet_brush_raw.csv", encoding="utf-8-sig")))
    out = []
    shown = set()
    skipped = {"no persona-specific answer", "neutral answer", "generic answer"}
    for k in TOP_SELLERS[:4]:
        picked = [r for r in rows_csv
                  if r["choice"] == k and r["rationale"]
                  and not any(s in r["rationale"].lower() for s in skipped)][:2]
        for r in picked:
            out.append(f'<div class="rs"><span class="rsk">{esc(PROD_CN[k])} · {esc(r.get("age_bracket") or "?")} · {esc(r.get("economic_motivation") or "?")}</span>'
                       f'<div class="rst">“{esc(r["rationale"])}”</div></div>')
    return "".join(out)


def notes():
    rows_csv = list(__import__("csv").DictReader(
        open(REPO / "results" / "toilet-brush-demo" / "toilet_brush_raw.csv", encoding="utf-8-sig")))
    age_dist = "、".join(f"{k} {v}人" for k, v in sorted(SAMPLE["age"].items(), key=lambda x: -x[1]))
    econ_dist = "、".join(f"{k} {v}人" for k, v in sorted(SAMPLE["econ"].items(), key=lambda x: -x[1]))
    gender = "、".join(f"{k} {v}人" for k, v in sorted(SAMPLE["gender"].items(), key=lambda x: -x[1]))
    socio = "、".join(f"{k} {v}人" for k, v in sorted(SAMPLE["socio"].items(), key=lambda x: -x[1]))
    n = len(rows_csv)
    cfg = json.loads((REPO / "results" / "toilet-brush-demo" / "persona_profile_config.json").read_text(encoding="utf-8"))
    cfg_html = (
        "<h3>本次数据源 Profile 配置（persona_strategy.json · datasetProfile）</h3>"
        "<ul>"
        "<li><b>hard_filter</b>：region → North America 权重 1.00 —— 抽样时对北美做硬性过滤（等效于 dimensionFilters.region），保证 1000 人全部来自北美。"
        "<li><b>observed_review_style</b>：cog_verbosity 观测分布 Terse 16.1% / Concise 40.7% / Balanced 29.2% / Wordy 11.7% / Rambling 1.9% / 缺失 0.3% —— 数据集中「语言啰嗦度」的真实分布，来自商品评论来源的人格。"
        "<li><b>soft_or_conditional_only</b>：primary_language=English（仅当有语言证据时赋英文）；economic_motivation / pref_quality_vs_quantity / lstyle_shopping_style 仅在存在对应证据（价格取向、品质取向、比价或复购行为）时才赋值 —— 这解释了本批数据中部分人格的 economic_motivation 等字段为空：不是采样错误，是数据集的条件赋值规则。"
        "<li><b>missing_by_default</b>：age_bracket / gender_identity / urbanicity / socioeconomic_band / household_and_family / political_and_religious / personality_and_health 等维度默认缺失 —— 数据集对部分人格不填充这些维度，报告中相应分群显示为 unknown 属正常现象。"
        "</ul>"
        "<p class='note'>完整配置原文见 <code>results/persona_profile_config.json</code> 与 task 的 <code>persona_strategy.json</code>（datasetProfile 节点）。"
        "本次运行的货架为<b>净化版</b>：已移除商品卖点中的推荐性标识（Clorox 的 Amazon's Choice、OXO 的 No.1 Top Rated），"
        "确保货架只含价格、材质、外观、功能等客观属性。旧版（含推荐标识）结果备份在 results/backup_v1_with_badges/。</p>"
    )
    return f"""
    <ul>
      <li><b>样本</b>：{n} 位北美虚拟消费者（region=North America，seed 42 随机抽样），年龄段分布 {age_dist}；经济动机 {econ_dist}；性别 {gender}；社经层级 {socio}。</li>
      <li><b>货架</b>：Top10 马桶刷榜单（reviews.guide 2026-09）对应的真实在售商品，价格为美亚/第三方比价站参考价，部分由新加坡站按 1 SGD≈0.7855 USD 换算；榜单第 6 名 Holikme 美亚暂时无货，以同品类在售的 Ibergrif M34152 替代并在货架注明。</li>
      <li><b>外观描述</b>：每款商品的外观描述（look & design）基于官方商品图撰写，为客观描述。</li>
      <li><b>模型</b>：DeepSeek deepseek-chat（官方 API），人格由 MatrAIx-Persona-1M 数据集提供；每题附 2–3 句购买理由。</li>
      <li><b>方法</b>：pilot 20 人验证 → 全量 1000 人，并行 20，通过率 {SAMPLE['reward_rate']*100:.0f}%（verifier 校验问卷完整性与选项合法性）。</li>
      <li><b>说明</b>：结果为 AI 人格模拟，反映的是"若 1000 位具有北美人口特征的人面对该货架，模型预期的选择分布"，可用于相对比较与假设检验，不代表真实市场调研。</li>
    </ul>
    {cfg_html}"""


HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>马桶刷「购物式选择」模拟报告 · 北美 1000 人</title>
<style>
:root{--ink:#1f2329;--mut:#646a73;--line:#e5e6eb;--blue:#2563EB;--bg:#f5f6f8}
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;margin:0;background:var(--bg);color:var(--ink);line-height:1.6}
.wrap{max-width:1060px;margin:0 auto;padding:28px 18px 80px}
.hero{background:linear-gradient(135deg,#1e3a8a,#2563EB);color:#fff;border-radius:14px;padding:28px 30px;margin-bottom:22px}
.hero h1{margin:0 0 8px;font-size:24px}
.hero .sub{opacity:.85;font-size:13px}
.badge{display:inline-block;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.35);border-radius:20px;padding:2px 12px;font-size:12px;margin:4px 6px 0 0}
h2{font-size:18px;margin:30px 0 12px;padding-left:10px;border-left:4px solid var(--blue)}
.card{background:#fff;border-radius:10px;padding:18px 20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.concl{font-size:14px;margin:0}
.concl li{margin:8px 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:8px}
.kpi{background:#fff;border-radius:10px;padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.kpi .v{font-size:24px;font-weight:700;color:var(--blue)}
.kpi .l{font-size:12px;color:var(--mut);margin-top:2px}
.chart{width:100%;height:auto}
.lbl{font-size:12px;fill:#333}
.val{font-size:12px;fill:var(--blue);font-weight:600}
.seg{font-size:11px;fill:#fff;font-weight:600}
.seg2{font-size:12px;fill:var(--mut)}
.axis{font-size:11px;fill:var(--mut)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:820px){.grid2{grid-template-columns:1fr}}
.pgrid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:820px){.pgrid{grid-template-columns:1fr}}
.pcard{display:flex;gap:14px;background:#fff;border-radius:10px;padding:14px;box-shadow:0 1px 3px rgba(0,0,0,.06);border:1px solid var(--line)}
.pcard.winner{border:2px solid var(--blue);background:#f8faff}
.pimg{flex:0 0 120px}
.pimg img{width:120px;height:120px;object-fit:contain;background:#fff;border-radius:8px;border:1px solid var(--line)}
.noimg{width:120px;height:120px;display:flex;align-items:center;justify-content:center;background:#f2f3f5;border-radius:8px;color:var(--mut);font-size:12px}
.pbody{flex:1;font-size:13px}
.prank{font-size:12px;color:var(--blue);font-weight:600}
.pname{font-size:15px;font-weight:700;margin:2px 0}
.pprice{color:var(--mut);font-size:12px}
.plook,.psell,.pkw,.pwent{margin-top:3px;font-size:12px;color:#444}
.zitem{background:#fff7f7;border:1px solid #fecaca;border-radius:8px;padding:10px 14px;margin:8px 0;font-size:13px}
.zitem ul{margin:6px 0 0;padding-left:18px;color:#555;font-size:12px}
.rs{border-bottom:1px dashed var(--line);padding:8px 0}
.rsk{font-size:12px;color:var(--blue);font-weight:600}
.rst{font-size:13px;margin-top:2px}
.note{font-size:12px;color:var(--mut)}
.foot{margin-top:30px;color:var(--mut);font-size:12px;border-top:1px solid var(--line);padding-top:14px}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right}
th:first-child,td:first-child{text-align:left}
</style></head><body><div class="wrap">

<div class="hero">
  <h1>马桶刷「购物式选择」模拟报告</h1>
  <div class="sub">MatrAIx-Persona-1M × DeepSeek · 北美人群 1000 人 · 10 款真实在售马桶刷 + 「都不买」· 模拟生成时间 2026-09-16</div>
  <div><span class="badge">人群：北美</span><span class="badge">货架：10 款 + 都不买</span><span class="badge">模型：deepseek-chat</span><span class="badge">并行：20</span></div>
</div>

<div class="card"><h2 style="margin-top:0">一图看懂（核心结论）</h2>
<ul class="concl">
  <li><b>销冠：{TOP0_NAME}（{TOP0_PRICE}）</b>，拿下 <b>{TOP0_SHARE}%</b> 份额——北美虚拟消费者最买单的关键词是「隐藏式收纳 + 防积水 + 紧凑占位」。</li>
  <li><b>价格不是唯一决定因素</b>：$19.97 的 OXO 击败了 4 款更便宜的硅胶款；同时 $12.99–13.99 的价格带合计仍拿到 {LOW_SHARE}% 份额，说明「低价务实派」真实存在。</li>
  <li><b>「都不买」占 {NONE_RATE}%</b>：{NONE_CNT} 位消费者在 10 款中没找到想要的，主要理由是「已有/不需要/都不够好」。</li>
  <li><b>成交价中位数 ${PRICE_MEDIAN}</b>，平均可接受价位档 {THR_AVG}/5；经济动机为「Cost-sensitive」的人群平均可接受档最低。</li>
  <li><b>0 票商品存在</b>：{ZERO_LIST} 无人购买——下方证据链展示"被考虑过但被放弃"的真实理由，说明是「定位问题」而非「曝光问题」。</li>
</ul>
</div>

<div class="kpis">{KPIS}</div>

<div class="card"><h2>市场份额</h2>{SHARE_CHART}
<p class="note">按得票排序。份额 = 得票 / 1000。价格带：低价 $12.99–15.50 · 中价 $19.97–25.70 · 中高价 $28.60–29.30。</p>
</div>

<div class="card"><h2>版本对比：货架净化前后的变化（数据完整性检查）</h2>{VERSION_COMPARE}</div>

<div class="grid2">
<div class="card"><h2>价格带汇总</h2>{PRICE_BRACKET}</div>
<div class="card"><h2>最看重属性</h2>{FEAT_CHART}
<p class="note">购买理由中提及的决策因子占比（可多因素提及）。</p></div>
</div>

<h2>10 款商品表现（含外观与理由画像）</h2>
<div class="pgrid">{PRODUCT_CARDS}</div>

<h2>分群：谁在买什么</h2>
<div class="card"><h3 style="margin-top:0">选择 × 年龄段</h3>{SEG_AGE}</div>
<div class="card"><h3>选择 × 经济动机</h3>{SEG_ECON}</div>
<div class="grid2">
<div class="card"><h3 style="margin-top:0">选择 × 性别</h3>{SEG_GENDER}</div>
<div class="card"><h3>选择 × 社经层级</h3>{SEG_SOCIO}</div>
</div>

<h2>0 票商品证据链（为什么没人买）</h2>
<div class="card">{ZERO_EVIDENCE}
<p class="note">证据链方法：在所有「未选择该款」的问卷理由中检索提及该商品/其关键特征的文本，统计"被考虑过"的人数，并摘录典型的放弃理由。</p></div>

<h2>真实购买理由摘录</h2>
<div class="card">{RATIONALES}</div>

<h2>对业务的启示（建议）</h2>
<div class="card">{INSIGHTS}</div>

<h2>附注：口径、方法与限制</h2>
<div class="card note">{NOTES}</div>

<div class="foot">模拟数据文件（results/toilet-brush-demo/）：toilet_brush_raw.csv（1000 行，含每题答案、理由、人格维度）· toilet_brush_summary.json（全量统计）· assets/（10 张商品图）· backup_v1_with_badges/（含推荐标识的旧版结果）· 复现：DEMO_REPRODUCE.md（马桶刷章节）· 全部产物索引：results/README.md</div>
</div></body></html>"""


def main() -> None:
    top0 = TOP_SELLERS[0]
    zeros = [PROD_CN[k] for k in ORDER if k != "none_of_these" and MS[k]["count"] == 0]
    low_keys = [k for k in ORDER if k != "none_of_these" and P[k]["tier"] == "低"]
    low_share = sum(MS[k]["share_pct"] for k in low_keys)
    feats = sorted(FEAT.items(), key=lambda x: -x[1])
    feat_names = {"price": "价格/性价比", "cleaning": "清洁力/刷头设计", "hygiene": "卫生/快干",
                  "design": "外观设计", "brand": "品牌信任", "material": "材质耐用"}
    html_out = (
        HTML
        .replace("{TOP0_NAME}", PROD_CN[top0])
        .replace("{TOP0_PRICE}", PRICE_STR[top0])
        .replace("{TOP0_SHARE}", f"{MS[top0]['share_pct']}")
        .replace("{LOW_SHARE}", f"{low_share:.1f}")
        .replace("{NONE_RATE}", f"{NONE_RATE}")
        .replace("{NONE_CNT}", f"{MS['none_of_these']['count']}")
        .replace("{PRICE_MEDIAN}", f"{PRICE['median']:.2f}")
        .replace("{THR_AVG}", f"{THR['avg']}")
        .replace("{ZERO_LIST}", "、".join(zeros) if zeros else "无")
        .replace("{KPIS}", kpi_cards())
        .replace("{SHARE_CHART}", seller_chart())
        .replace("{VERSION_COMPARE}", version_compare())
        .replace("{PRICE_BRACKET}", price_bracket())
        .replace("{FEAT_CHART}", svg_vbar([(feat_names.get(k, k), v) for k, v in feats], title="最看重属性"))
        .replace("{PRODUCT_CARDS}", product_cards())
        .replace("{SEG_AGE}", segment_chart("age", "年龄段"))
        .replace("{SEG_ECON}", segment_chart("econ", "经济动机"))
        .replace("{SEG_GENDER}", segment_chart("gender", "性别"))
        .replace("{SEG_SOCIO}", segment_chart("socio", "社经层级"))
        .replace("{ZERO_EVIDENCE}", zero_vote_evidence())
        .replace("{RATIONALES}", rationale_samples())
        .replace("{INSIGHTS}", insights())
        .replace("{NOTES}", notes())
    )
    OUT.write_text(html_out, encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
