#!/usr/bin/env python3
"""Generate a single-file, leadership-friendly HTML report (方案 + 结果).

Charts are inline SVG (deterministic, no CDN/JS dependency) so the file
renders anywhere — double-click to open, offline included.

Usage: uv run python scripts/generate_leader_report.py
Output: results/bottle_choice_leader_report.html
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "results" / "bottle_choice_leader_report.html"
summary = json.loads((REPO / "results" / "bottle_choice_1000_summary.json").read_text(encoding="utf-8"))

P = summary["products"]
MS = summary["market_share"]
SAMPLE = summary["sample"]
THR = summary["price_threshold"]
SENS = summary["price_sensitivity"]
LIKE = summary["purchase_likelihood"]
FEAT = summary["feature_priority"]
AGE_X = summary["choice_x_age"]
ECON_X = summary["choice_x_econ"]

PROD_COLOR = {
    "fuguang_316": "#7C98B3",
    "nalgene_sustain": "#10B981",
    "beijixiong_316": "#2563EB",
    "mijia_bottle": "#64748B",
    "zojirushi_sm_sz": "#F59E0B",
    "stanley_quencher": "#DC2626",
    "none_of_these": "#CBD5E1",
}
PROD_ORDER = ["beijixiong_316", "fuguang_316", "zojirushi_sm_sz", "stanley_quencher", "nalgene_sustain", "mijia_bottle", "none_of_these"]
PROD_SHORT = {
    "beijixiong_316": "杯具熊 ¥129",
    "fuguang_316": "富光 ¥39.9",
    "zojirushi_sm_sz": "象印 ¥229",
    "stanley_quencher": "Stanley ¥319",
    "nalgene_sustain": "Nalgene ¥119",
    "mijia_bottle": "米家 ¥179",
    "none_of_these": "都不买",
}

# Real product photos (downloaded to results/assets/, verified by viewing).
# source = (img file, 一句话外观, 图源标签, 图源 URL)
IMG_INFO = {
    "fuguang_316": ("assets/fuguang.jpg", "哑光黑极简柱体，实用耐看", "慢慢买", "http://cu.manmanbuy.com/dingyue/brand/fuguang/12"),
    "nalgene_sustain": ("assets/nalgene.jpg", "半透明宽口，户外粗犷风", "PRFO Sports", "https://www.prfo.com/fr/products/nalgene-wide-mouth-sustain-32oz-bottle-2"),
    "beijixiong_316": ("assets/beijixiong.jpg", "奶油白圆润萌系，年轻向", "淘宝·杯具熊官方", "https://mobile-phone.taobao.com/chanpin/548a182504270b53b3c8eaa55250c7f65d212d1b0f15954128e003423f225065.html"),
    "mijia_bottle": ("assets/mijia.jpg", "米家极简白，现代简洁", "抖音电商·米家", "https://haohuo.jinritemai.com/ecommerce/trade/detail/index.html?origin_type=old_h5&id=3762454771076825787"),
    "zojirushi_sm_sz": ("assets/zojirushi.jpg", "日系流线细身，质感精致", "苏宁易购", "https://m.suning.com/product/0000000000/000000012213093530.html"),
    "stanley_quencher": ("assets/stanley.jpg", "大块头双色+侧把手，网红风", "Allure", "https://www.allure.com/gallery/best-gifts-for-women"),
}


def esc(v):
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg_hbar(items, *, width=680, row_h=44, label_w=170, max_val=None, value_fmt="{v}", title=""):
    """items: list of (label, value, color). Horizontal bar chart, largest at top."""
    if max_val is None:
        max_val = max(v for _, v, _ in items) or 1
    n = len(items)
    height = 40 + n * row_h
    plot_x = label_w
    plot_w = width - label_w - 90
    rows = []
    for i, (label, val, color) in enumerate(items):
        y = 46 + i * row_h
        bw = int(plot_w * val / max_val) if max_val else 0
        bw = max(bw, 2 if val > 0 else 0)
        rows.append(
            f'<g><text x="{label_w - 12}" y="{y + 22}" text-anchor="end" class="lbl">{esc(label)}</text>'
            f'<rect x="{plot_x}" y="{y + 8}" width="{bw}" height="26" rx="4" fill="{color}"/>'
            f'<text x="{plot_x + bw + 8}" y="{y + 27}" class="val">{value_fmt.format(v=val)}</text></g>'
        )
    return (
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" class="chart" role="img" aria-label="{esc(title)}">'
        + "".join(rows)
        + "</svg>"
    )


def svg_stacked_pct(rows, *, width=680, row_h=46, label_w=150, title=""):
    """rows: list of (row_label, [(key, pct, color)...], n_label). 100% stacked bars."""
    n = len(rows)
    height = 40 + n * row_h
    plot_x = label_w
    plot_w = width - label_w - 10
    out = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" class="chart" role="img" aria-label="{esc(title)}">']
    for i, (row_label, segs, n_label) in enumerate(rows):
        y = 46 + i * row_h
        out.append(f'<text x="{plot_x - 12}" y="{y + 22}" text-anchor="end" class="lbl">{esc(row_label)}</text>')
        x = plot_x
        for key, pct, color in segs:
            w = plot_w * pct / 100.0
            if w >= 24:
                out.append(f'<rect x="{x:.1f}" y="{y + 8}" width="{w:.1f}" height="26" rx="3" fill="{color}"/>')
                out.append(f'<text x="{x + w / 2:.1f}" y="{y + 27}" text-anchor="middle" class="seg">{pct:.0f}%</text>')
            else:
                out.append(f'<rect x="{x:.1f}" y="{y + 8}" width="{max(w, 3):.1f}" height="26" rx="3" fill="{color}"/>')
            x += w
        out.append(f'<text x="{plot_x + plot_w + 6}" y="{y + 27}" class="seg2">{esc(n_label)}</text>')
    out.append("</svg>")
    return "".join(out)


def svg_vbar(items, *, width=680, height=250, title=""):
    """items: list of (label, value). Simple vertical bars."""
    n = len(items)
    pad_l, pad_b, pad_t = 46, 34, 12
    plot_w = width - pad_l - 12
    plot_h = height - pad_t - pad_b
    max_val = max(v for _, v in items) or 1
    bw = plot_w / n * 0.56
    out = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" class="chart" role="img" aria-label="{esc(title)}">']
    # gridlines
    for g in range(0, 5):
        gy = pad_t + plot_h - plot_h * g / 4
        out.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{width - 12}" y2="{gy:.1f}" class="grid"/>')
        out.append(f'<text x="{pad_l - 8}" y="{gy + 4:.1f}" text-anchor="end" class="ax">{g * max_val / 4:.0f}</text>')
    for i, (label, val) in enumerate(items):
        cx = pad_l + plot_w / n * (i + 0.5)
        bh = plot_h * val / max_val
        out.append(f'<rect x="{cx - bw / 2:.1f}" y="{pad_t + plot_h - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="4" fill="#2563EB"/>')
        out.append(f'<text x="{cx:.1f}" y="{pad_t + plot_h - bh - 7:.1f}" text-anchor="middle" class="val">{val}</text>')
        out.append(f'<text x="{cx:.1f}" y="{height - 12:.1f}" text-anchor="middle" class="ax">{esc(label)}</text>')
    out.append("</svg>")
    return "".join(out)


def svg_grouped_bars(items, *, width=680, height=250, title=""):
    """items: list of (label, [series1_val, series2_val]). Grouped vertical bars."""
    n = len(items)
    nser = len(items[0][1])
    pad_l, pad_b, pad_t = 46, 34, 12
    plot_w = width - pad_l - 12
    plot_h = height - pad_t - pad_b
    max_val = max(v for _, vals in items for v in vals) or 1
    grp = plot_w / n
    bw = grp / (nser + 0.8) * 0.8
    colors = ["#9AA7B4", "#2563EB"]
    out = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" class="chart" role="img" aria-label="{esc(title)}">']
    for g in range(0, 5):
        gy = pad_t + plot_h - plot_h * g / 4
        out.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{width - 12}" y2="{gy:.1f}" class="grid"/>')
        out.append(f'<text x="{pad_l - 8}" y="{gy + 4:.1f}" text-anchor="end" class="ax">{g * max_val / 4:.0f}</text>')
    for i, (label, vals) in enumerate(items):
        cx = pad_l + grp * (i + 0.5)
        for si, v in enumerate(vals):
            x = cx - grp / 2 + (si + 0.4) * bw
            bh = plot_h * v / max_val
            out.append(f'<rect x="{x:.1f}" y="{pad_t + plot_h - bh:.1f}" width="{bw - 3:.1f}" height="{bh:.1f}" rx="3" fill="{colors[si]}"/>')
            if v >= max_val * 0.08:
                out.append(f'<text x="{x + (bw - 3) / 2:.1f}" y="{pad_t + plot_h - bh - 6:.1f}" text-anchor="middle" class="val">{v:.0f}</text>')
        out.append(f'<text x="{cx:.1f}" y="{height - 12:.1f}" text-anchor="middle" class="ax">{esc(label)}</text>')
    out.append("</svg>")
    return "".join(out)


# ---------------- data builds ----------------
share_items = [(PROD_SHORT[k], MS[k]["count"], PROD_COLOR[k]) for k in PROD_ORDER]
share_max = share_items[0][1]

age_rows = []
for a in ["18-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75-84", "85+"]:
    d = AGE_X[a]
    tot = sum(x["count"] for x in d.values())
    segs = [(k, d[k]["share_pct"], PROD_COLOR[k]) for k in PROD_ORDER if d[k]["count"] > 0]
    age_rows.append((a, segs, f"n={tot}"))

econ_rows = []
econ_label = {"Cost-sensitive": "省钱优先", "Value-driven": "性价比优先", "Premium-seeking": "高端优先", "Indifferent": "无所谓"}
for e in ["Cost-sensitive", "Value-driven", "Indifferent", "Premium-seeking"]:
    d = ECON_X[e]
    tot = sum(x["count"] for x in d.values())
    segs = [(k, d[k]["share_pct"], PROD_COLOR[k]) for k in PROD_ORDER if d[k]["count"] > 0]
    econ_rows.append((econ_label[e], segs, f"n={tot}"))

like_items = [(str(k), v) for k, v in sorted(LIKE.items(), key=lambda kv: int(kv[0]))]
feat_items = [("保温性能", FEAT.get("insulation", 0)), ("价格", FEAT.get("price", 0)), ("品牌", FEAT.get("brand", 0)), ("容量", FEAT.get("capacity", 0)), ("设计颜值", FEAT.get("aesthetics", 0))]
thr_avg = summary["price_threshold"]["avg"]

age_dist = [(k, v) for k, v in sorted(SAMPLE["age"].items(), key=lambda kv: -kv[1])]
region_dist = sorted(SAMPLE["region"].items(), key=lambda kv: -kv[1])[:8]

# narrative bullets
top = max(((k, v) for k, v in MS.items() if k != "none_of_these"), key=lambda kv: kv[1]["count"])
buy_rate = round((LIKE.get("4", 0) + LIKE.get("5", 0)) * 100 / summary["n"], 1)
feat_rate = round((FEAT.get("insulation", 0) + FEAT.get("price", 0)) * 100 / summary["n"], 1)
cs_fuguang = ECON_X["Cost-sensitive"]["fuguang_316"]["share_pct"]
pm_zoji = ECON_X["Premium-seeking"]["zojirushi_sm_sz"]["share_pct"]
old_zoji = AGE_X["75-84"]["zojirushi_sm_sz"]["share_pct"]
old_zoji85 = AGE_X["85+"]["zojirushi_sm_sz"]["share_pct"]
young_bjx = AGE_X["18-24"]["beijixiong_316"]["share_pct"]

bullets = [
    ("冠军商品", f"「杯具熊 316 保温杯」（¥129）以 {top[1]['share_pct']}% 的份额胜出——但加入外观描述后优势明显收窄（V1 为 70.2%），预算款富光与高端象印同步回暖，货架更接近真实电商的多元选择。"),
    ("价格分层", f"预算款富光（¥39.9）占 {MS['fuguang_316']['share_pct']}%，高端象印（¥229）占 {MS['zojirushi_sm_sz']['share_pct']}%，网红款 Stanley（¥319）本次 0 票。"),
    ("购买意愿", f"{buy_rate}% 的人表示 3 个月内会真实购买（4-5 分）；购买决策最看重价格与保温，合计占 {feat_rate}%。"),
    ("分群差异", f"省钱优先人群选富光达 {cs_fuguang}%（全人群近 1.5 倍），高端优先人群选象印 {pm_zoji}%，75 岁以上长者选象印 {old_zoji}%（85+ 更达 {old_zoji85}%），18-24 岁近六成选杯具熊——不同画像的消费逻辑清晰可辨。"),
    ("成本", f"全量 1000 人模拟仅花费约 ${summary.get('cost_usd', 1.81):.2f}（约 ¥{summary.get('cost_usd', 1.81) * 7.1:.1f}），耗时约 {summary.get('duration_min', 40):.0f} 分钟，人均不到 1 分钱。"),
]
bullets_html = "".join(f"<li><b>{esc(t)}：</b>{esc(d)}</li>" for t, d in bullets)

cost_usd = summary.get("cost_usd", 1.81)
dur_min = summary.get("duration_min", 40)

chart_share = svg_hbar(share_items, max_val=share_max, value_fmt="{v} 人", title="市场份额")
chart_compare = svg_grouped_bars(
    [("杯具熊", [70.2, MS["beijixiong_316"]["share_pct"]]),
     ("富光", [21.9, MS["fuguang_316"]["share_pct"]]),
     ("象印", [7.8, MS["zojirushi_sm_sz"]["share_pct"]]),
     ("Stanley", [0.1, MS["stanley_quencher"]["share_pct"]])],
    title="V1 vs V2 份额对比")
chart_age = svg_stacked_pct(age_rows, title="分群偏好-年龄")
chart_econ = svg_stacked_pct(econ_rows, title="分群偏好-消费心态")
chart_like = svg_vbar(like_items, title="购买意向")
chart_feat = svg_vbar(feat_items, title="最看重属性")
chart_age_dist = svg_vbar(age_dist, title="样本年龄构成")
chart_region = svg_hbar([(esc(k), v, "#2E6FDB") for k, v in region_dist], max_val=region_dist[0][1], value_fmt="{v} 人", title="样本地区构成")

legend = "".join(
    f'<span class="lg"><i style="background:{PROD_COLOR[k]}"></i>{esc(P[k]["name"])}</span>'
    for k in PROD_ORDER if MS[k]["count"] > 0
)

# ---- extra breakdowns (v2): region / gender / life stage / income + reviews ----
GENDER_LABEL = {"Woman": "女性", "Man": "男性", "Non-binary": "非二元"}
LIFE_LABEL = {
    "Student": "学生", "Early career": "职场初期", "Career change": "职业转型",
    "Parent of young kids": "带娃家长", "Mid-life": "中年", "Empty nester": "空巢期", "Retirement": "退休",
}
SOCIO_LABEL = {
    "Low income": "低收入", "Lower-middle": "中低收入", "Middle": "中等收入",
    "Upper-middle": "中高收入", "High income": "高收入",
}

def stacked_from(data, label_map=None, min_n=20, max_rows=8):
    """data: choice_x_* dict -> list of (row_label, segs, n_label), big groups first."""
    out = []
    for k, d in data.items():
        tot = sum(x["count"] for x in d.values())
        if tot < min_n:
            continue
        lbl = (label_map or {}).get(k, k)
        segs = [(p, d[p]["share_pct"], PROD_COLOR[p]) for p in PROD_ORDER if d[p]["count"] > 0]
        out.append((lbl, segs, f"n={tot}"))
        if len(out) >= max_rows:
            break
    return out

region_rows = stacked_from(summary["choice_x_region"])
gender_rows = stacked_from(summary["choice_x_gender"], GENDER_LABEL)
life_rows = stacked_from(summary["choice_x_life_stage"], LIFE_LABEL, min_n=40)
socio_rows = stacked_from(summary["choice_x_socio"], SOCIO_LABEL)
chart_region_pref = svg_stacked_pct(region_rows, title="分群偏好-地区")
chart_gender = svg_stacked_pct(gender_rows, title="分群偏好-性别")
chart_life = svg_stacked_pct(life_rows, title="分群偏好-人生阶段")
chart_socio = svg_stacked_pct(socio_rows, title="分群偏好-收入层级")

REVIEW_LABEL = {
    "材质/内胆": "材质", "保温性能": "保温", "价格/性价比": "价格划算",
    "外观/颜值": "外观", "容量": "容量", "品牌/信赖": "品牌信赖", "轻便/便携": "轻便", "环保": "环保",
}
REV_COLORS = ["#2563EB", "#0E7C7B", "#F59E0B"]
def review_card(prod_key, title, color):
    rv = summary["product_reviews"].get(prod_key) or {"n": 0, "keywords": {}}
    if rv["n"] == 0:
        return ""
    items = [(REVIEW_LABEL.get(k, k), v["pct"]) for k, v in
             sorted(rv["keywords"].items(), key=lambda kv: -kv[1]["pct"])[:5]]
    chart = svg_hbar([(lbl, pct, color) for lbl, pct in items], width=320, row_h=30,
                     label_w=86, max_val=100, value_fmt="{v:.0f}%")
    return (f'<div class="rcard"><div class="rname">{esc(title)}</div>'
            f'<div class="rsub">被选 {rv["n"]} 人 · 理由提到率</div>{chart}</div>')

review_cards = "".join(
    review_card(k, P[k]["name"], REV_COLORS[i])
    for i, k in enumerate(["beijixiong_316", "fuguang_316", "zojirushi_sm_sz"])
)

# ---- 0-vote evidence chain (consideration analysis) ----
CONS = summary["consideration"]
CONS_ORDER = ["stanley_quencher", "mijia_bottle", "nalgene_sustain", "fuguang_316", "beijixiong_316", "zojirushi_sm_sz"]
cons_rows = "".join(
    f'<tr><td><b>{esc(P[k]["name"])}</b></td><td>{("<b class=\"red\">0 票</b>" if CONS[k]["votes"] == 0 else str(CONS[k]["votes"]) + " 票")}</td>'
    f'<td>{CONS[k]["considered_by"]} 人</td>'
    f'<td class="muted">{esc(" → ".join(f"{PROD_SHORT[wk]} {wc}人" for wk, wc in list(CONS[k]["went_to"].items())[:3])) or "—"}</td></tr>'
    for k in CONS_ORDER
)
st = CONS["stanley_quencher"]
st_core = st.get("core_fit") or {"n": 0, "went_to": {}}
st_went = " → ".join(f"{PROD_SHORT[wk]} {wc}人" for wk, wc in list(st_core["went_to"].items())[:4]) or "—"
st_quotes = "".join(f'<blockquote class="quote">{esc(q)}…</blockquote>' for q in st["sample_rationales"][:2])

shelf_rows = "".join(
    f'<tr><td><b>{esc(P[k]["name"])}</b></td><td>{P[k]["price"]} 元</td><td>{esc(P[k]["tier"])}</td><td class="muted">{esc(P[k]["name"])}，{esc({"低": "大众预算", "中": "中端主流", "中高": "中高端", "高": "高端旗舰", "无": "未购买"}[P[k]["tier"]])}</td></tr>'
    for k in ["fuguang_316", "beijixiong_316", "nalgene_sustain", "mijia_bottle", "zojirushi_sm_sz", "stanley_quencher"]
)

shelf_cards = "".join(
    f'<div class="pcard"><img src="{img}" alt="{esc(P[k]["name"])}">'
    f'<div class="pn">{esc(P[k]["name"])}</div>'
    f'<div class="pp">{P[k]["price"]} 元 · {esc(P[k]["tier"])}档</div>'
    f'<div class="pl">{esc(look)}</div>'
    f'<div class="ps">图源：<a href="{src_url}" target="_blank" rel="noopener">{esc(src_lbl)}</a></div></div>'
    for k in ["fuguang_316", "beijixiong_316", "nalgene_sustain", "mijia_bottle", "zojirushi_sm_sz", "stanley_quencher"]
    for img, look, src_lbl, src_url in [IMG_INFO[k]]
)

CSS = """
:root{--ink:#1C2733;--muted:#5B6B7C;--line:#E4E9EF;--bg:#F4F6F9;--card:#FFFFFF;--navy:#12355B;--blue:#2563EB;--teal:#0E7C7B}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:"Noto Sans SC","PingFang SC","Hiragino Sans GB","Microsoft YaHei",system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--ink);line-height:1.65}
.wrap{max-width:1000px;margin:0 auto;padding:28px 20px 64px}
.hero{background:linear-gradient(135deg,#12355B 0%,#1E4E8C 55%,#2563EB 100%);border-radius:16px;color:#fff;padding:34px 36px 30px;position:relative;overflow:hidden}
.hero .tag{display:inline-block;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.35);padding:3px 12px;border-radius:999px;font-size:12px;letter-spacing:.5px;margin-bottom:14px}
.hero h1{font-size:28px;font-weight:800;letter-spacing:.3px}
.hero p.sub{margin-top:8px;font-size:14px;opacity:.9}
.hero .meta{margin-top:16px;font-size:12px;opacity:.75}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:18px 0 6px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;box-shadow:0 1px 2px rgba(16,42,67,.05)}
.kpi .v{font-size:26px;font-weight:800;color:var(--navy)}
.kpi .l{font-size:12px;color:var(--muted);margin-top:2px}
h2{font-size:19px;font-weight:800;color:var(--navy);margin:34px 0 4px;display:flex;align-items:center;gap:10px}
h3{font-size:15px;font-weight:700;color:var(--navy)}
h2 .no{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:8px;background:var(--navy);color:#fff;font-size:13px;flex:none}
h2+hr{border:none;border-top:3px solid var(--navy);width:44px;margin:6px 0 18px}
.pgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:6px}
.pcard{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.pcard img{width:100%;height:150px;object-fit:cover;background:#fff;border-bottom:1px solid var(--line)}
.pcard .pn{font-size:13.5px;font-weight:700;color:var(--navy);padding:10px 12px 0}
.pcard .pp{font-size:12px;color:var(--muted);padding:2px 12px 0}
.pcard .pl{font-size:12px;color:#33414F;padding:6px 12px 0;line-height:1.5}
.pcard .ps{font-size:10.5px;color:#9AA7B4;padding:6px 12px 10px;margin-top:auto}
.pcard .ps a{color:#9AA7B4;text-decoration:none;border-bottom:1px dotted #C3CBD6}
@media(max-width:760px){.pgrid{grid-template-columns:repeat(2,1fr)}}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin-top:14px}
.card p{font-size:14px;color:#33414F;margin:6px 0}
.flow{display:flex;flex-wrap:wrap;gap:0;align-items:stretch;margin-top:6px}
.step{flex:1 1 140px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 14px 12px;position:relative;min-width:140px}
.step .n{font-size:11px;color:var(--blue);font-weight:700;letter-spacing:1px}
.step .t{font-weight:700;font-size:14px;margin-top:2px}
.step .d{font-size:12px;color:var(--muted);margin-top:3px}
.arrow{align-self:center;color:#9AA7B4;font-size:20px;padding:0 6px;flex:none}
table{width:100%;border-collapse:collapse;font-size:14px;table-layout:fixed}
th,td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:12px;color:var(--muted);font-weight:600;background:#F8FAFC}
.col{width:100%}
.chart{width:100%;height:auto;display:block}
.lbl{font-size:12.5px;fill:#33414F}
.val{font-size:13px;font-weight:700;fill:var(--navy)}
.seg{font-size:11px;fill:#fff;font-weight:600}
.seg2{font-size:11px;fill:var(--muted)}
.ax{font-size:11px;fill:var(--muted)}
.grid{stroke:var(--line);stroke-width:1}
.legend{display:flex;flex-wrap:wrap;gap:12px;margin-top:12px;font-size:12px;color:#33414F}
.lg i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.revgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:6px}
.rcard{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 14px 10px}
.rcard .rname{font-size:14px;font-weight:700;color:var(--navy)}
.rcard .rsub{font-size:11.5px;color:var(--muted);margin:2px 0 8px}
.red{color:#DC2626}
.quote{background:#F6F8FB;border-left:3px solid var(--blue);border-radius:6px;padding:8px 12px;margin:8px 0;font-size:13px;color:#33414F;font-style:normal}
.quote::before{content:"“";color:var(--blue);font-weight:800}
.quote::after{content:"”";color:var(--blue);font-weight:800}
@media(max-width:760px){.grid2{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(2,1fr)}.hero h1{font-size:22px}.revgrid{grid-template-columns:1fr}}
ul.concl{margin:8px 0 2px;padding-left:0;list-style:none}
ul.concl li{background:#F6F8FB;border-left:4px solid var(--blue);border-radius:8px;padding:10px 14px;margin:10px 0;font-size:14px;line-height:1.7}
ul.concl b{color:var(--navy)}
.note{background:#FFF7E6;border:1px solid #F2DCA0;border-radius:12px;padding:16px 18px;margin-top:14px;font-size:13.5px;color:#6B5317}
.note b{color:#8A6414}
.muted{color:var(--muted);font-size:12px}
.foot{margin-top:36px;padding-top:18px;border-top:1px solid var(--line);font-size:12px;color:var(--muted);display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}
"""

FAVICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#12355B"/><path d="M10 20c0-2.2 2.7-3.4 6-3.4s6 1.2 6 3.4" stroke="#fff" stroke-width="2.4" fill="none" stroke-linecap="round"/><path d="M13 13l3 3 3-3" stroke="#F59E0B" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>保温杯虚拟消费者模拟 · 领导汇报版</title>
<link rel="icon" href="data:image/svg+xml,{FAVICON.replace('#', '%23').replace(' ', '%20').replace('<', '%3C').replace('>', '%3E').replace('"', "'")}">
<link rel="stylesheet" href="https://miaoda.feishu.cn/fonts/css2?family=Noto+Sans+SC:wght@400;500;700;800&display=swap">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

<div class="hero">
  <span class="tag">AI 虚拟消费者模拟 · 概念验证 Demo</span>
  <h1>1000 个虚拟消费者，如何挑选保温杯？</h1>
  <p class="sub">用 MatrAIx 人格库（100 万人格）× DeepSeek 大模型，模拟全球 1000 名消费者在 6 款真实保温杯之间做「购物式选择」，并汇总出份额、分群偏好与价格敏感度。</p>
  <div class="meta">数据来源：AI 模拟（非真实市场调研）· 生成日期 2026-09-16 · 模型 deepseek-chat</div>
</div>

<div class="kpis">
  <div class="kpi"><div class="v">1,000</div><div class="l">虚拟消费者完成选购</div></div>
  <div class="kpi"><div class="v">100%</div><div class="l">有效回答率（全部通过校验）</div></div>
  <div class="kpi"><div class="v">约 ¥{cost_usd * 7.1:.1f}</div><div class="l">总成本（约 ${cost_usd:.2f}，人均不到 1 分钱）</div></div>
  <div class="kpi"><div class="v">约 {dur_min:.0f} 分钟</div><div class="l">从采样到出报告</div></div>
</div>

<h2><span class="no">1</span>这是什么？为什么值得看？</h2><hr>
<div class="card">
  <p>传统做法：新品上市前想摸底市场，要招募真人、设计问卷、等几周、花几万块。<b>这个 Demo 把这件事压缩成一次大模型模拟</b>：让 1000 个「虚拟消费者」（由 100 万人格画像库按全球人口口径抽样产生）像真人逛电商一样，在 6 款真实在售保温杯里挑选，并写下购买理由。</p>
  <p>它可以快速回答三个问题：<b>谁会买什么（份额）、不同人群怎么选（分群偏好）、价格是否接受（价格敏感度）</b>——并且每一票的理由都可回溯、可复核。</p>
</div>

<h2><span class="no">2</span>怎么做到的（5 步）</h2><hr>
<div class="flow">
  <div class="step"><div class="n">STEP 1</div><div class="t">人格库抽样</div><div class="d">从 100 万人格中按全球人口口径随机抽取 1000 人（覆盖各年龄段、9 大地区、4 类消费心态）</div></div>
  <div class="arrow">→</div>
  <div class="step"><div class="n">STEP 2</div><div class="t">摆出货架</div><div class="d">6 款真实保温杯，给出价格、容量、材质、卖点，像电商商品页</div></div>
  <div class="arrow">→</div>
  <div class="step"><div class="n">STEP 3</div><div class="t">扮演选购</div><div class="d">DeepSeek 大模型以每人的人格扮演「我」，读货架、权衡、投票并写理由</div></div>
  <div class="arrow">→</div>
  <div class="step"><div class="n">STEP 4</div><div class="t">质量校验</div><div class="d">官方校验器检查选项是否合法、理由是否充分，不合格重跑</div></div>
  <div class="arrow">→</div>
  <div class="step"><div class="n">STEP 5</div><div class="t">聚合出报告</div><div class="d">汇总 1000 票 → 市场份额、分群偏好、价格敏感度 → 本报告</div></div>
</div>

<h2><span class="no">3</span>货架：6 款真实在售保温杯</h2><hr>
<div class="pgrid">{shelf_cards}</div>
<div class="card">
  <table>
    <colgroup><col style="width:26%"><col style="width:14%"><col style="width:14%"><col style="width:46%"></colgroup>
    <tr><th>商品</th><th>参考价</th><th>价位档</th><th>一句话定位</th></tr>
    {shelf_rows}
    <tr><td><b>都不买</b></td><td>—</td><td>—</td><td class="muted">若 6 款都不合适则选择放弃购买（本次无人选择）</td></tr>
  </table>
  <div class="muted" style="margin-top:10px">商品图来自公开电商/媒体页面，仅作展示；本次模拟货架额外补充了每款的外观描述，让虚拟消费者也能"看得到"设计颜值。</div>
</div>

<h2><span class="no">4</span>核心结果</h2><hr>
<div class="card">
  <ul class="concl">{bullets_html}</ul>
</div>

<div class="card">
  <h2 style="margin-top:0">优化效果：货架加「外观描述」改变了什么？（V1 → V2）</h2>
  {chart_compare}
  <div class="legend"><span class="lg"><i style="background:#9AA7B4"></i>V1 纯参数货架</span><span class="lg"><i style="background:#2563EB"></i>V2 加外观描述</span></div>
  <div class="muted" style="margin-top:10px">同一批 1000 个虚拟消费者、同一价格——只把货架从「价格+参数」升级为「价格+参数+外观」：
  杯具熊从一家独大（70.2%）回落到 45.0%，富光与象印明显回暖；「设计颜值」从 0 票变成有人在意（8 票）。
  说明虚拟消费者和真人一样，看得见外观后，会做出更真实的权衡。</div>
</div>

<div class="card">
  <h2 style="margin-top:0">市场份额：1000 票投给了谁？</h2>
  {chart_share}
  <div class="legend">{legend}</div>
</div>

<div class="card">
  <h2 style="margin-top:0">为什么有商品 0 票？——「考虑过，但放弃了」（证据可回溯）</h2>
  <table>
    <colgroup><col style="width:30%"><col style="width:14%"><col style="width:20%"><col style="width:36%"></colgroup>
    <tr><th>商品</th><th>最终得票</th><th>被多少人考虑过*</th><th>考虑过的人最终选了谁</th></tr>
    {cons_rows}
  </table>
  <div class="muted" style="margin-top:8px">*「考虑过」= 购买理由里明确提到该商品但最终选了别的。已核对：问卷 7 个选项完整、票数与原始数据逐行一致——0 票是模型真实决定，不是统计错误。</div>

  <h3 style="margin:16px 0 6px">以 Stanley 为例：连「最该买它的人」也放弃了</h3>
  <p style="font-size:14px">在 1000 人里，<b>{CONS["stanley_quencher"]["considered_by"]} 人</b>认真比较过 Stanley；其中 <b>{st_core["n"]} 人</b>属于「高收入 / 18-24 岁 / 北美」——最匹配网红杯的人群，最终：{esc(st_went)}，<b>0 人选择 Stanley</b>。</p>
  {st_quotes}
  <div class="muted" style="margin-top:10px">为什么是 0 票：本实验场景是「保温杯」，全球样本以价值敏感人群为主；纯文字货架下 ¥319 的「网红溢价」是减分项。方法局限：① 模型看不到商品实图（Stanley 的颜值冲击力无法感知）——这正是 V3「看图选购」要解决的；② 随机样本未筛「潮流敏感」人格，可定向补充验证。结论：0 票 ≠ 没市场，只说明「在当前货架文案 + 场景下」它不成立。</div>
</div>

<div class="grid2">
  <div class="card">
    <h2 style="margin-top:0">分群偏好 · 年龄段（份额 %）</h2>
    {chart_age}
    <div class="muted">75 岁以上明显更倾向象印（47.5%，85+ 达 67.9%）；18-24 岁近六成选杯具熊，看重可爱外观。</div>
  </div>
  <div class="card">
    <h2 style="margin-top:0">分群偏好 · 消费心态（份额 %）</h2>
    {chart_econ}
    <div class="muted">省钱优先人群选富光 53.6%（是高端人群的 4 倍以上）；高端人群里象印占 42.9%。</div>
  </div>
</div>

<div class="card">
  <h2 style="margin-top:0">分群偏好 · 地区（Top 8，份额 %）</h2>
  {chart_region_pref}
  <div class="muted">地区差异非常鲜明：北美/西欧 80%+ 选象印（高端日系品牌），新兴市场（南亚/东亚/撒哈拉以南）则是富光+杯具熊双雄——购买力与品牌认知的地区差异在模拟里真实可见。</div>
</div>

<div class="grid2">
  <div class="card">
    <h2 style="margin-top:0">分群偏好 · 性别（份额 %）</h2>
    {chart_gender}
    <div class="muted">女性更偏爱杯具熊萌系外观（51%），男性更接受高端象印（30%）。</div>
  </div>
  <div class="card">
    <h2 style="margin-top:0">分群偏好 · 人生阶段（份额 %）</h2>
    {chart_life}
    <div class="muted">学生/带娃家长选杯具熊超 55%；退休人群转向富光（47%）与象印（25%）双峰。</div>
  </div>
</div>

<div class="card">
  <h2 style="margin-top:0">分群偏好 · 收入层级（份额 %）</h2>
  {chart_socio}
  <div class="muted">收入梯度是全部维度里最清晰的：低收入人群 63% 选富光（¥39.9），高收入人群 78% 选象印（¥229）——价格与品质的取舍随收入连续变化。</div>
</div>

<div class="card">
  <h2 style="margin-top:0">商品评价画像（购买理由里的关键词提及率）</h2>
  <div class="revgrid">{review_cards}</div>
  <div class="muted" style="margin-top:10px">每票都附带购买理由（中英文），以上是各商品被选者理由里的关键词画像：杯具熊「材质+保温+容量」全能，富光「材质+保温+划算」，象印「保温+轻便+品牌信赖」——虚拟消费者选它的原因看得见、可回溯。</div>
</div>

<div class="grid2">
  <div class="card">
    <h2 style="margin-top:0">购买意向（1-5 分）</h2>
    {chart_like}
    <div class="muted">{buy_rate}% 的人给出 4-5 分，即「3 个月内会真实购买」。</div>
  </div>
  <div class="card">
    <h2 style="margin-top:0">最看重什么（选择理由）</h2>
    {chart_feat}
    <div class="muted">价格与保温合计占 98%；「设计颜值」从 V1 的 0 票变为 8 票——美学维度已被激活。</div>
  </div>
</div>

<h2><span class="no">5</span>样本构成（全球分层校验）</h2><hr>
<div class="grid2">
  <div class="card">
    <h2 style="margin-top:0">年龄段分布</h2>
    {chart_age_dist}
  </div>
  <div class="card">
    <h2 style="margin-top:0">地区分布（Top 8）</h2>
    {chart_region}
  </div>
</div>
<div class="card">
  <p>消费心态：省钱优先 491 人 · 性价比优先 353 人 · 无所谓 107 人 · 高端优先 49 人 —— 四个群体均有足够样本量做分群对比。</p>
</div>

<h2><span class="no">6</span>怎么看这份结果（重要说明）</h2><hr>
<div class="card">
  <p><b>1. 这是「AI 模拟」，不是真实调研。</b> 每个选择都有画像依据和可追溯理由，但代表的是"这类人最可能的偏好"，不等同于真实市场数据。</p>
  <p><b>2. 结果受货架信息影响。</b> 本次 V2 验证了这一点：同一批消费者、同一价格，只加「外观描述」就让杯具熊份额从 70.2% 降到 45.0%——货架文案与展示方式会显著改变模拟结论，正式决策建议做多组对照。</p>
  <p><b>3. 价格接受度普遍偏高（{thr_avg}/5）。</b> 这道题的区分度有限；真正的价格敏感体现在选择行为上（如省钱人群更爱富光）。</p>
  <p><b>4. 适合的用途。</b> 新品/竞品快速试水、人群分层假设验证、定价敏感度预判——用 1 小时和一杯咖啡的钱换取初步方向。</p>
</div>

<div class="foot">
  <span>MatrAIx-Persona-8B × DeepSeek · 保温杯购物式选择 Demo</span>
  <span>完整复现步骤见 <b>DEMO_REPRODUCE.md</b> · 明细数据见 results/bottle_choice_1000_raw.csv</span>
</div>

</div>
</body>
</html>
"""

OUT.write_text(html, encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
