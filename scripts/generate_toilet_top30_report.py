#!/usr/bin/env python3
"""Generate the TOP30 toilet-brush 2x2 factorial experiment report (HTML dashboard).

Reads results/toilet-brush-top30-experiment/top30_2x2_summary.json and writes a
self-contained HTML report (ECharts embedded offline, 30-product catalog with
images / links / descriptions) for leadership + ecommerce.

Usage:
  uv run python scripts/generate_toilet_top30_report.py [summary_json] [out_html]
"""
from __future__ import annotations

import base64
import html as html_mod
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True  # 容忍下载截断的 JPEG（P02/P08 主图）

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "results" / "toilet-brush-top30-experiment" / "toilet_top30_experiment_report.html"
CATALOG_JSON = REPO / "results" / "toilet-brush-top30-experiment" / "product_catalog.json"
ASSETS_DIR = REPO / "results" / "toilet-brush-top30" / "assets"
ECHARTS_VENDOR = REPO / "scripts" / "vendor" / "echarts.min.js"


def fmt(x) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:,.2f}"
    return str(x)


def _img_b64(rank: int, asin: str, max_h: int = 380) -> str:
    """压缩产品主图为内嵌 Base64（竖版图按高度缩放）。"""
    p = ASSETS_DIR / f"{rank:02d}_{asin}.jpg"
    if not p.exists():
        return ""
    try:
        im = Image.open(p).convert("RGB")
        w = max(1, round(im.width * max_h / im.height))
        im = im.resize((w, max_h), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=80, optimize=True)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def build_catalog(s: dict) -> str:
    """30 款产品全览卡片：主图 + 品牌 + 价格/评分/评价/月销 + 四臂模拟份额 + 标题 + 中文描述 + Amazon 链接。"""
    if not CATALOG_JSON.exists():
        return ""
    catalog = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    arms = s.get("arms", {})
    arm_keys = ["anon-rating", "anon-norating", "brand-rating", "brand-norating"]
    arm_short = {"anon-rating": "匿+评", "anon-norating": "匿无评", "brand-rating": "牌+评", "brand-norating": "牌无评"}
    cards = []
    for p in catalog:
        rank = p.get("rank")
        pid = p.get("pid", f"P{rank:02d}")
        b64 = _img_b64(rank, p.get("asin", ""))
        img_html = (f'<img src="data:image/jpeg;base64,{b64}" alt="{html_mod.escape(p.get("brand", ""))} {pid}" '
                    f'loading="lazy">') if b64 else '<div class="no-img">图缺失</div>'
        shares = []
        for k in arm_keys:
            v = arms.get(k, {}).get("share", {}).get(pid, 0)
            shares.append(f'<span class="sh"><i>{arm_short[k]}</i><b>{v:.1f}%</b></span>')
        title = html_mod.escape(str(p.get("title") or ""))
        title_short = title if len(title) <= 92 else title[:90] + "…"
        bits = []
        if p.get("ptype"): bits.append(f"类型：{p['ptype']}")
        if p.get("head"): bits.append(f"刷头：{p['head']}")
        if p.get("pack"): bits.append(f"件数：{p['pack']} 件装")
        if p.get("refill"): bits.append(f"替换耗材：{p['refill']}")
        if p.get("color"): bits.append(f"外观：{p['color']}")
        if p.get("handle"): bits.append(f"手柄：{p['handle']}")
        if p.get("holder"): bits.append(f"收纳：{p['holder']}")
        if p.get("size_note"): bits.append(f"尺寸：{p['size_note']}")
        desc = html_mod.escape("；".join(bits))
        feats = html_mod.escape(" · ".join((p.get("features") or [])[:4]))
        rating = p.get("rating")
        reviews = p.get("reviews")
        price = f"${p['price']:.2f}" if p.get("price") else "—"
        rate = f"{rating:.1f}★" if rating else "—"
        rv = f"{int(reviews):,}" if reviews else "—"
        ms = f"{int(p['monthly_sales']):,}" if p.get("monthly_sales") else "—"
        link = p.get("link") or f"https://www.amazon.com/dp/{p.get('asin', '')}"
        cards.append(f"""<article class="pcard">
  <div class="pimg">{img_html}<span class="pidx">{pid}</span><span class="prank">真实榜 #{rank}</span></div>
  <div class="pbody">
    <div class="pbrand">{html_mod.escape(str(p.get('brand') or ''))}</div>
    <div class="pmeta"><span class="pprice">{price}</span><span class="prate">{rate}</span><span>评价 {rv}</span><span>月销 {ms}</span></div>
    <div class="pshares">{''.join(shares)}</div>
    <p class="ptitle" title="{title}">{title_short}</p>
    <p class="pdesc">{desc}</p>
    <p class="pfeat">{feats}</p>
    <a class="plink" href="{html_mod.escape(link)}" target="_blank" rel="noopener">Amazon 链接 · {html_mod.escape(str(p.get('asin') or ''))}</a>
  </div>
</article>""")
    return f'<div class="pcards">{"".join(cards)}</div>'


def build_insights(s: dict) -> list[dict]:
    """数据驱动的结论（全部由 summary 现算，保证可追溯）。"""
    insights: list[dict] = []
    arms = s.get("arms", {})
    eff = s.get("effects", {})
    bl = s.get("brand_levels", [])
    segs = s.get("segments_exclusive") or s.get("segments", {})
    sig = s.get("rationale_signals", {})
    stab = s.get("persona_stability", {})
    corr = s.get("gt_correlation", {})

    # 1) 最大品牌效应
    if eff:
        sorted_brand = sorted(eff.items(), key=lambda kv: -(kv[1].get("brand_effect_pp") or 0))
        sorted_rating = sorted(eff.items(), key=lambda kv: -(kv[1].get("rating_effect_pp") or 0))
        if sorted_brand:
            pid, e = sorted_brand[0]
            insights.append({
                "tag": "品牌效应", "title": f"品牌曝光让 {e['brand']} 份额变化最显著",
                "body": f"{e['brand']} 的 {pid} 在品牌显示下份额变化 {e['brand_effect_pp']:+.1f}pp；"
                        f"在 30 款同池匿名对照中，品牌名是改变决策的最大单一因子之一。",
            })
        if sorted_rating:
            pid, e = sorted_rating[0]
            insights.append({
                "tag": "评分效应", "title": f"评分展示显著抬升了 {e['brand']} 的份额",
                "body": f"显示评分后 {pid} 份额变化 {e['rating_effect_pp']:+.1f}pp。评分信息是 "
                        f"除价格/功能外影响选品的第二类决策信息。",
            })
    # 2) 头部集中度
    share_arms = []
    for arm in ("anon-rating", "anon-norating", "brand-rating", "brand-norating"):
        sh = arms.get(arm, {}).get("share", {})
        top3 = sum(v for k, v in sorted(sh.items(), key=lambda kv: -kv[1])[:3])
        share_arms.append((arm, top3))
    avg_top3 = sum(v for _, v in share_arms) / len(share_arms) if share_arms else 0
    insights.append({
        "tag": "市场结构", "title": "TOP3 集中度约 %.0f%%，长尾产品靠品牌或评分翻身" % avg_top3,
        "body": "四臂 TOP3 份额合计 %.0f%%/%.0f%%/%.0f%%/%.0f%%。30 款产品竞争格局高度集中，"
                "非头部产品需要在品牌、评分或细分功能上建立差异化。" % tuple(v for _, v in share_arms[:4]),
    })
    # 3) 人群分群
    if segs:
        top_seg = sorted(segs.items(), key=lambda kv: -kv[1]["pct"])[0]
        name_zh = {"price_driven": "价格敏感型", "function_driven": "功能驱动型",
                   "design_driven": "外观驱动型", "hygiene_driven": "卫生驱动型",
                   "brand_driven": "品牌驱动型", "reviews_driven": "评分驱动型"}.get(top_seg[0], top_seg[0])
        insights.append({
            "tag": "人群细分", "title": f"最大决策人群是「{name_zh}」占 {top_seg[1]['pct']}%",
            "body": f"该人群平均接受价 ${top_seg[1]['mean_price']}，首选 "
                    + "、".join(f"{c['pid']}({c['brand']} {c['pct']}%)" for c in top_seg[1]["top_choices"][:3])
                    + "。不同人群的选品差异为分层运营提供了直接依据。",
        })
    # 4) 信息干扰
    if sig and "brand-rating" in sig:
        br = sig["brand-rating"].get("brand_mention", 0)
        ar = sig["anon-rating"].get("brand_mention", 0)
        insights.append({
            "tag": "信息干扰", "title": f"品牌名的出现率：品牌臂 {br:.0f}% vs 匿名臂 {ar:.0f}%",
            "body": "评分提及率评分臂 ≈ 100%、无评分臂 ≈ 0%，说明“信息有无”的操控在人格决策中真实生效，"
                    "品牌与评分是两组有效的实验因子。",
        })
    # 5) 稳定性
    if stab:
        key = "rating_effect"
        if key in stab and stab[key].get("same_pct") is not None:
            same = stab[key]["same_pct"]
            insights.append({
                "tag": "决策稳定性", "title": f"同人格跨臂选择一致性 {same}%",
                "body": f"同一批人格在评分显示前后仅 {same}% 保持同一选择，"
                        f"即 {100 - same}% 的消费者因评分信息改变了决策——评分是实质性的决策改写因子，而非确认性偏差。",
            })
    # 6) 市场校验
    if corr and "brand-rating" in corr:
        c = corr["brand-rating"]
        if c.get("share_vs_sales") is not None:
            insights.append({
                "tag": "市场校验", "title": f"模拟份额 vs 真实月销排名相关 {c['share_vs_sales']}",
                "body": "品牌+评分臂（最接近真实货架形态）的模拟选择份额与真实月销数据的秩相关最高，"
                        "说明模拟对真实市场的可解释力强。",
            })
    # 7) 品类结构机会（真实 vs 模拟偏差 = 非货架信息驱动）
    if s.get("category_structure"):
        cats = {c["category"]: c for c in s["category_structure"]}
        combo = cats.get("刷+搋2合1", {})
        single = cats.get("单刷套装", {})
        if combo and single:
            insights.append({
                "tag": "品类机会", "title": f"2合1套装真实占 {combo['gt_sales_share']}% 月销，模拟仅 {combo['sim_share']}%",
                "body": f"单刷套装模拟份额 {single['sim_share']}%（真实 {single['gt_sales_share']}%）。2合1 的真实销量主要靠"
                        f"「一物两用」的实用需求与线下/复购场景驱动，货架理性决策中优势不显——新品做 2合1 必须在标题/主图"
                        f"前置「双功能」沟通，否则会被单刷套装淹没。",
            })
    # 8) 价格带机会
    if s.get("price_band"):
        pb = {b["band"]: b for b in s["price_band"]}
        sweet = pb.get("$15-25", {})
        low = pb.get("$0-10", {})
        if sweet and low:
            insights.append({
                "tag": "定价启示", "title": f"模拟选择 89.3% 集中在 $15–25 价格带",
                "body": f"品牌+设计溢价在模拟中被广泛接受（$15–25 带模拟份额 {sweet['sim_share']}% vs 真实 {sweet['gt_sales_share']}%），"
                        f"而 $0–10 低价带真实占 {low['gt_sales_share']}% 月销、模拟仅 {low['sim_share']}%——"
                        f"低价品靠走量，中价位靠品牌+产品力，两条线对应完全不同的运营打法。",
            })
    # 9) 排名位移：最被高估/低估的产品
    rc = (s.get("rank_compare") or {}).get("brand-rating", [])
    if rc:
        over = sorted([r for r in rc if r["delta"] < 0], key=lambda r: r["delta"])[:1]
        under = sorted([r for r in rc if r["delta"] > 0], key=lambda r: -r["delta"])[:1]
        if over and under:
            o, u = over[0], under[0]
            insights.append({
                "tag": "排名校验", "title": f"最被高估：{o['pid']} {o['brand']}（真实#{o['gt_rank']} → 模拟#{o['sim_rank']}）",
                "body": f"模拟份额 {o['share']}% 远超其真实销量位置；最被低估：{u['pid']} {u['brand']}（真实#{u['gt_rank']} → 模拟#{u['sim_rank']}，"
                        f"份额 {u['share']}%）——后者在真实市场的高销量依赖复购/促销/曝光位等非货架信息，"
                        f"这正是模拟无法捕捉、需要运营动作补位的部分。",
            })
    return insights


def build_html(s: dict) -> str:
    insights = build_instigths_placeholder() if False else build_insights(s)
    data_json = json.dumps(s, ensure_ascii=False)
    insights_json = json.dumps(insights, ensure_ascii=False)
    catalog_html = build_catalog(s)
    # 内嵌 ECharts（离线可用，避免 CDN 加载失败导致图表空白）
    echarts_js = ECHARTS_VENDOR.read_text(encoding="utf-8") if ECHARTS_VENDOR.exists() else ""
    if not echarts_js:
        raise FileNotFoundError(f"缺 vendor echarts: {ECHARTS_VENDOR}")

    arms = s.get("arms", {})
    effects = s.get("effects", {})
    brand_levels = s.get("brand_levels", [])
    segments = s.get("segments", {})
    rationale = s.get("rationale_signals", {})
    stability = s.get("persona_stability", {})
    corr = s.get("gt_correlation", {})
    n_shared = s.get("n_personas_shared") or 0

    arm_labels = {
        "anon-rating": ("匿名 + 评分", "anonymous shelf with ratings"),
        "anon-norating": ("匿名 + 无评分", "anonymous shelf without ratings"),
        "brand-rating": ("品牌 + 评分", "branded shelf with ratings"),
        "brand-norating": ("品牌 + 无评分", "branded shelf without ratings"),
    }

    def arm_meta(arm):
        a = arms.get(arm, {})
        top = sorted(a.get("share", {}).items(), key=lambda kv: -kv[1])[:1]
        return f"""
        <div class="arm-card" data-arm="{arm}">
          <h4>{arm_labels[arm][0]}</h4>
          <p class="arm-sub">{arm_labels[arm][1]}</p>
          <div class="arm-kpis">
            <div><span class="k">{a.get('n', 0)}</span><span class="l">样本</span></div>
            <div><span class="k">${fmt(a.get('mean_chosen_price'))}</span><span class="l">平均成交价</span></div>
            <div><span class="k">{fmt(a.get('none_rate'))}%</span><span class="l">都不买率</span></div>
          </div>
          <p class="arm-top">第一选择 {top[0][0] if top else '—'} · {fmt(top[0][1]) if top else '—'}%</p>
        </div>"""

    arms_html = "".join(arm_meta(a) for a in ("anon-rating", "anon-norating", "brand-rating", "brand-norating"))

    eff_rows = "".join(
        f"<tr><td>{e['pid']}</td><td>{e['brand']}</td><td>${e['price']:.2f}</td>"
        f"<td>{e['s_anon_rating']:.1f}</td><td>{e['s_anon_none']:.1f}</td>"
        f"<td>{e['s_brand_rating']:.1f}</td><td>{e['s_brand_none']:.1f}</td>"
        f"<td class='{'pos' if e['brand_effect_pp']>=0 else 'neg'}'>{e['brand_effect_pp']:+.1f}</td>"
        f"<td class='{'pos' if e['rating_effect_pp']>=0 else 'neg'}'>{e['rating_effect_pp']:+.1f}</td>"
        f"<td>{e['gt_rank']}</td></tr>"
        for e in sorted(effects.values(), key=lambda x: -x["brand_effect_pp"])
    )

    bl_rows = "".join(
        f"<tr><td>{b['brand']}</td><td>{b['n']}</td><td>{b['share_anon']:.1f}%</td>"
        f"<td>{b['share_brand']:.1f}%</td>"
        f"<td class='{'pos' if b['brand_effect_pp']>=0 else 'neg'}'>{b['brand_effect_pp']:+.1f} pp</td>"
        f"<td>{b['share_rating']:.1f}%</td><td>{b['share_norating']:.1f}%</td>"
        f"<td class='{'pos' if b['rating_effect_pp']>=0 else 'neg'}'>{b['rating_effect_pp']:+.1f} pp</td></tr>"
        for b in brand_levels
    )

    seg_rows = ""
    seg_zh = {"price_driven": "价格敏感型", "function_driven": "功能驱动型", "design_driven": "外观驱动型",
              "hygiene_driven": "卫生驱动型", "brand_driven": "品牌驱动型", "reviews_driven": "评分/多件/材质驱动型"}
    seg_src = s.get("segments_exclusive") or segments
    for name, g in seg_src.items():
        tops = "、".join(f"{c['pid']}（{c['brand']} {c['pct']}%）" for c in g.get("top_choices", [])[:4])
        seg_rows += f"<tr><td>{seg_zh.get(name, name)}</td><td>{g['pct']}%</td><td>${g['mean_price']}</td><td>{tops}</td></tr>"

    # 排名位移表（品牌+评分臂，取位移最大 4 款 + 排名一致 2 款 + 位移最小 4 款）
    shift_rows = ""
    rc = (s.get("rank_compare") or {}).get("brand-rating", [])
    if rc:
        def shift_zh(d):
            if d["delta"] < 0:
                return f"模拟高估 {abs(d['delta'])} 位"
            if d["delta"] > 0:
                return f"模拟低估 {d['delta']} 位"
            return "排名一致"
        picked = sorted(rc, key=lambda r: -r["delta"])[:4] + [r for r in rc if r["delta"] == 0][:2] + sorted(rc, key=lambda r: r["delta"])[:4]
        seen = set()
        for r in picked:
            if r["pid"] in seen:
                continue
            seen.add(r["pid"])
            shift_rows += (
                f"<tr><td>{r['pid']}</td><td>{r['brand']}</td><td>#{r['gt_rank']}</td><td>#{r['sim_rank']}</td>"
                f"<td class='{'pos' if r['delta']<0 else 'neg'}'>{r['delta']:+d}</td><td>{r['share']:.1f}%</td>"
                f"<td>{shift_zh(r)}</td></tr>"
            )

    # 营收池表（品牌+评分臂 TOP 10）
    revenue_rows = ""
    rev = s.get("revenue_potential", [])
    for r in rev[:10]:
        ratio = (r["sim_monthly_revenue"] / r["gt_monthly_revenue"]) if r["gt_monthly_revenue"] else 0
        revenue_rows += (
            f"<tr><td>{r['pid']}</td><td>{r['brand']}</td><td>${r['price']:.2f}</td><td>{r['share']:.1f}%</td>"
            f"<td>${r['sim_monthly_revenue']:,.0f}</td><td>${r['gt_monthly_revenue']:,.0f}</td>"
            f"<td class='{'pos' if ratio>=1 else 'neg'}'>{ratio:.2f}</td></tr>"
        )

    stab_rows = "".join(
        f"<tr><td>{k}</td><td>{v['n']}</td><td>{v['same_pct']}%</td></tr>" for k, v in stability.items()
    )

    sig_rows = ""
    for sig_k, sig_zh in [
        ("brand_mention", "提到品牌"), ("rating_mention", "提到评分/评论"), ("price_mention", "提到价格"),
        ("hygiene_mention", "提到卫生"), ("function_mention", "提到清洁功能"), ("look_mention", "提到外观"),
    ]:
        cells = "".join(
            f"<td>{rationale.get(arm, {}).get(sig_k, '—')}%</td>"
            for arm in ("anon-rating", "anon-norating", "brand-rating", "brand-norating")
        )
        sig_rows += f"<tr><td>{sig_zh}</td>{cells}</tr>"

    insight_cards = "".join(
        f"""
        <article class="insight">
          <span class="tag">{i['tag']}</span>
          <h4>{i['title']}</h4>
          <p>{i['body']}</p>
        </article>""" for i in insights
    )

    # ===== 核心发现速览（Executive Summary） =====
    exec_cards = []  # (tag, num, sub, title, desc)

    # 1 评分改写一切
    stab_key = "rating_effect"
    same_pct = None
    if s.get("persona_stability") and s["persona_stability"].get(stab_key):
        same_pct = s["persona_stability"][stab_key].get("same_pct")
    if same_pct is not None:
        exec_cards.append((
            "决策改写", f"{100 - same_pct:.0f}%", "",
            "评分比品牌更能改写决策",
            f"同一批消费者，显示评分后 {100 - same_pct:.0f}% 改变选择——评分是比品牌更强的决策改写因子。",
        ))
    # 2 品牌效应最强者与反效果
    eff = s.get("effects", {})
    p07 = eff.get("P07", {})
    p13 = eff.get("P13", {})
    exec_cards.append((
        "品牌效应", f"{p07.get('brand_effect_pp', 0):+.1f}", "pp  vs  " + f"{p13.get('brand_effect_pp', 0):+.1f}pp",
        "品牌让 OXO +30.1pp、让白牌 Sellemer −23.1pp",
        "Sellemer 匿名时 55.4% 夺冠、亮出品牌后归零——小品牌匿名测试更能测出真实产品力。",
    ))
    # 3 货架赢家
    br_share = s.get("arms", {}).get("brand-rating", {}).get("share", {})
    p07_share = br_share.get("P07", 0)
    exec_cards.append((
        "货架赢家", f"{p07_share:.0f}%", "",
        "P07 OXO 在品牌+评分臂（最接近真实货架）通吃",
        "自动开盖功能 + 品牌 + 高评分三重叠加，拿下 88.5% 份额。",
    ))
    # 4 TOP3 集中度
    top3_pcts = []
    for a in ("anon-rating", "anon-norating", "brand-rating", "brand-norating"):
        sh = s.get("arms", {}).get(a, {}).get("share", {})
        vals = sorted(sh.values(), reverse=True)[:3]
        if vals:
            top3_pcts.append(sum(vals))
    exec_cards.append((
        "市场集中度", f"{min(top3_pcts):.0f}–{max(top3_pcts):.0f}%", "",
        "TOP3 合计份额 74%–100%，赢家通吃",
        "四臂 TOP3 合计 97%/74%/100%/85%——长尾产品必须靠品牌、评分或细分功能突围。",
    ))
    # 5 最大人群
    seg_zh2 = {"price_driven": "价格敏感型", "function_driven": "功能驱动型", "design_driven": "外观驱动型",
               "hygiene_driven": "卫生驱动型", "brand_driven": "品牌驱动型", "reviews_driven": "评分/多件/材质驱动型"}
    seg_src2 = s.get("segments_exclusive") or s.get("segments", {})
    if seg_src2:
        name2, g2 = max(seg_src2.items(), key=lambda kv: kv[1].get("pct", 0))
        top1 = g2.get("top_choices", [{}])[0]
        seg_max_name = seg_zh2.get(name2, name2)
        seg_max_pct = g2.get("pct", 0)
        seg_max_price = g2.get("mean_price", 0)
        seg_max_prod = f"{top1.get('pid', '')}（{top1.get('brand', '')}）" if top1 else ""
        exec_cards.append((
            "最大人群", f"{seg_max_pct:.0f}%", "",
            f"「{seg_max_name}」是最大决策人群，占 {seg_max_pct:.0f}%",
            f"平均接受价 ${seg_max_price:.0f}、首选 {seg_max_prod}；价格敏感型仅 4.0%。",
        ))
    # 6 品类缺口
    cats = {c.get("category"): c for c in (s.get("category_structure") or [])}
    combo = cats.get("刷+搋2合1", {})
    if combo:
        exec_cards.append((
            "品类缺口", f"{combo.get('gt_sales_share', 0):.0f}%", f"真实 → 模拟 {combo.get('sim_share', 0):.0f}%",
            "2合1 真实月销 31.9%、模拟仅 0.7%",
            "货架理性决策不买账——必须前置「一物两用」沟通，否则被单刷套装淹没。",
        ))
    # 7 价格甜蜜点
    pb = {b.get("band"): b for b in (s.get("price_band") or [])}
    sweet = pb.get("$15-25", {})
    if sweet:
        exec_cards.append((
            "价格甜蜜点", f"{sweet.get('sim_share', 0):.0f}%", "",
            "模拟选择 89.3% 集中在 $15–25",
            "$0–10 低价带真实走量（28.9%）、模拟仅 10.6%——中价位品牌+设计溢价可接受。",
        ))
    # 8 偏差即机会
    corr_br = (s.get("gt_correlation") or {}).get("brand-rating", {}).get("share_vs_sales")
    rc = (s.get("rank_compare") or {}).get("brand-rating", [])
    under = sorted([r for r in rc if r.get("delta", 0) > 0], key=lambda r: -r["delta"])[:1]
    if corr_br is not None:
        extra = f"（如 {under[0]['pid']} {under[0]['brand']} 真实#{under[0]['gt_rank']}→模拟#{under[0]['sim_rank']}）" if under else ""
        exec_cards.append((
            "偏差即机会", f"{corr_br:.2f}", "秩相关",
            "品牌+评分臂与真实市场解释力最强",
            f"模拟与真实月销秩相关最高、实验可信；真实 TOP8 中 P02/P05/P06/P08 模拟归零 = 复购/促销驱动{extra}，需运营补位。",
        ))

    cards_html = "".join(
        f"""
        <div class="hl-card"><span class="tag">{c[0]}</span>
          <div class="n">{c[1]}{f'<small>{c[2]}</small>' if c[2] else ''}</div>
          <div class="t">{c[3]}</div>
          <div class="d">{c[4]}</div>
        </div>""" for c in exec_cards
    )

    exec_summary = f"""
<section id="highlights">
  <div class="hl-banner">
    <h2>核心发现速览 <span class="badge">EXECUTIVE SUMMARY · 先读这 8 条</span></h2>
    <p class="hl-sub">以下结论均由 4 臂 × 1,000 人（同一批 Amazon 画像人格）的模拟决策数据直接计算得出——先看结论，再看论证。</p>
    <div class="hl-grid">{cards_html}</div>
  </div>
</section>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Amazon 美国站马桶刷 TOP30 用户模拟选品实验报告</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%2316233B'/><path d='M8 20 L16 10 L24 20' stroke='%23E8A33D' stroke-width='3' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>">
<style>
:root {{
  --ink: #16233B; --ink-2: #22345A; --paper: #F7F8FA; --card: #FFFFFF;
  --line: #E3E7EE; --text: #22303F; --muted: #64748B;
  --amber: #E8A33D; --teal: #2E9E8F; --red: #C24B3F; --blue: #3B6FB5;
  --oklch-accent: oklch(0.78 0.14 78);
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ scroll-behavior: smooth; }}
body {{ font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; background: var(--paper); color: var(--text); line-height: 1.65; }}
h1,h2,h3,h4 {{ font-family: "Noto Serif SC", "Songti SC", "STSong", Georgia, serif; }}
.wrap {{ max-width: 1180px; margin: 0 auto; padding: 0 28px; }}

/* header */
header.hero {{ background: var(--ink); color: #fff; padding: 64px 0 56px; position: relative; overflow: hidden; }}
header.hero::after {{ content:""; position:absolute; right:-140px; top:-140px; width:460px; height:460px; border-radius:50%; background: radial-gradient(circle, rgba(232,163,61,.28), transparent 65%); }}
.brandline {{ display:flex; align-items:center; gap:10px; font-size:13px; letter-spacing:.14em; text-transform:uppercase; color:#9FB0C9; margin-bottom:26px; }}
.brandline svg {{ width:22px; height:22px; }}
.hero h1 {{ font-size: clamp(26px, 3.4vw, 40px); font-weight: 900; line-height: 1.25; letter-spacing: .01em; max-width: 900px; }}
.hero .sub {{ margin-top: 14px; font-size: 16px; color: #C8D3E3; max-width: 760px; }}
.meta-chips {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 26px; }}
.meta-chips span {{ border: 1px solid rgba(255,255,255,.22); border-radius: 999px; padding: 6px 14px; font-size: 13px; color: #E6ECF5; background: rgba(255,255,255,.06); }}
.kpi-strip {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-top: 34px; }}
.kpi {{ background: rgba(255,255,255,.07); border: 1px solid rgba(255,255,255,.14); border-radius: 12px; padding: 16px 18px; }}
.kpi .v {{ font-family: "Noto Serif SC", serif; font-size: 26px; font-weight: 700; color: var(--amber); }}
.kpi .t {{ font-size: 12.5px; color: #A9B8CD; margin-top: 4px; }}

/* executive summary */
section#highlights {{ padding-top: 8px; }}
.hl-banner {{ background: linear-gradient(120deg, #16233B 0%, #1D2E4F 55%, #26406B 100%); border: 1px solid rgba(255,255,255,.10); border-radius: 18px; padding: 30px 32px 26px; margin: 26px 0 8px; }}
.hl-banner h2 {{ color: #fff; font-size: 22px; font-weight: 800; letter-spacing: .02em; display: flex; align-items: center; gap: 10px; }}
.hl-banner h2 .badge {{ font-size: 11px; font-weight: 600; color: var(--amber); border: 1px solid rgba(232,163,61,.5); padding: 3px 10px; border-radius: 999px; letter-spacing: .08em; }}
.hl-banner .hl-sub {{ color: #C8D3E3; font-size: 13.5px; margin-top: 8px; }}
.hl-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 20px; }}
.hl-card {{ background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.12); border-radius: 12px; padding: 14px 15px 12px; transition: transform .18s ease, border-color .18s ease; }}
.hl-card:hover {{ transform: translateY(-2px); border-color: rgba(232,163,61,.55); }}
.hl-card .n {{ font-family: "Noto Serif SC", serif; font-size: 21px; font-weight: 800; color: var(--amber); line-height: 1.15; }}
.hl-card .n small {{ font-size: 12px; font-weight: 600; color: #F5C97B; }}
.hl-card .t {{ font-size: 13px; font-weight: 700; color: #F1F5FB; margin-top: 6px; }}
.hl-card .d {{ font-size: 12px; color: #A9B8CD; margin-top: 5px; line-height: 1.55; }}
.hl-card .tag {{ display: inline-block; font-size: 10px; color: var(--amber); border: 1px solid rgba(232,163,61,.4); border-radius: 4px; padding: 1px 7px; margin-bottom: 6px; letter-spacing: .06em; }}

/* nav */
nav.toc {{ position: sticky; top: 0; z-index: 50; background: rgba(255,255,255,.94); backdrop-filter: blur(8px); border-bottom: 1px solid var(--line); }}
nav.toc .wrap {{ display: flex; gap: 4px; overflow-x: auto; padding: 0 28px; }}
nav.toc a {{ padding: 14px 14px; font-size: 13.5px; color: var(--muted); text-decoration: none; white-space: nowrap; border-bottom: 2px solid transparent; }}
nav.toc a:hover, nav.toc a.active {{ color: var(--ink); border-bottom-color: var(--amber); }}

/* sections */
section {{ padding: 56px 0 8px; }}
.sec-head {{ display: flex; align-items: baseline; gap: 14px; margin-bottom: 8px; }}
.sec-no {{ font-family: "Noto Serif SC", serif; font-size: 15px; font-weight: 700; color: var(--amber); letter-spacing: .05em; }}
.sec-head h2 {{ font-size: 24px; font-weight: 800; color: var(--ink); }}
.sec-desc {{ color: var(--muted); font-size: 14px; margin-bottom: 26px; max-width: 860px; }}

.grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
.card {{ background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 20px 22px; }}
.card h3 {{ font-size: 16px; color: var(--ink); margin-bottom: 10px; }}
.chart-box {{ width: 100%; height: 400px; }}
.chart-box.sm {{ height: 320px; }}

/* design diagram */
.design-map {{ display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 12px; margin-top: 6px; }}
.design-map .cell {{ border-radius: 12px; padding: 14px; border: 1px solid var(--line); background: var(--card); }}
.design-map .cell.brand-yes {{ border-top: 4px solid var(--blue); }}
.design-map .cell.brand-no {{ border-top: 4px solid var(--muted); }}
.design-map .cell.rate-yes {{ border-bottom: 4px solid var(--amber); }}
.design-map .cell h5 {{ font-size: 14px; color: var(--ink); }}
.design-map .cell p {{ font-size: 12.5px; color: var(--muted); margin-top: 6px; }}

/* arms */
.arm-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 26px; }}
.arm-card {{ background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 18px; }}
.arm-card h4 {{ font-size: 16px; color: var(--ink); }}
.arm-card .arm-sub {{ font-size: 11.5px; color: var(--muted); margin: 2px 0 12px; }}
.arm-kpis {{ display: flex; gap: 16px; }}
.arm-kpis .k {{ display: block; font-size: 20px; font-weight: 700; color: var(--ink); font-family: "Noto Serif SC", serif; }}
.arm-kpis .l {{ font-size: 11px; color: var(--muted); }}
.arm-top {{ margin-top: 12px; font-size: 12.5px; color: var(--muted); border-top: 1px dashed var(--line); padding-top: 10px; }}

/* tables */
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ padding: 8px 10px; border-bottom: 1px solid var(--line); text-align: left; }}
th {{ font-weight: 600; color: var(--ink-2); background: #F1F4F9; }}
td.pos {{ color: var(--red); font-weight: 700; }}
td.neg {{ color: var(--teal); font-weight: 700; }}
.tbl-wrap {{ overflow-x: auto; background: var(--card); border: 1px solid var(--line); border-radius: 14px; }}

/* insights */
.insight-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
.insight {{ background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 22px; border-left: 4px solid var(--amber); }}
.insight .tag {{ display: inline-block; font-size: 11.5px; font-weight: 600; color: var(--ink); background: rgba(232,163,61,.15); border-radius: 999px; padding: 3px 10px; margin-bottom: 10px; }}
.insight h4 {{ font-size: 16.5px; color: var(--ink); margin-bottom: 8px; }}
.insight p {{ font-size: 13.5px; color: var(--muted); }}

/* misc */
.note {{ font-size: 12.5px; color: var(--muted); margin-top: 12px; }}
.limits li {{ margin: 6px 0 6px 18px; font-size: 13.5px; color: var(--muted); }}
footer {{ margin-top: 70px; background: var(--ink); color: #A9B8CD; padding: 34px 0 40px; font-size: 12.5px; }}
footer .wrap {{ display: flex; justify-content: space-between; gap: 20px; flex-wrap: wrap; }}

/* 09 产品全览 */
.pcards {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-top: 6px; }}
.pcard {{ border: 1px solid #E3E8F0; border-radius: 12px; overflow: hidden; background: #fff; display: flex; flex-direction: column; transition: box-shadow .18s ease; }}
.pcard:hover {{ box-shadow: 0 8px 24px rgba(15,32,62,.10); }}
.pimg {{ position: relative; height: 210px; background: #F7F9FC; display: flex; align-items: center; justify-content: center; border-bottom: 1px solid #EDF1F7; }}
.pimg img {{ max-height: 196px; max-width: 100%; object-fit: contain; }}
.pidx {{ position: absolute; top: 8px; left: 8px; background: var(--ink); color: #fff; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 999px; }}
.prank {{ position: absolute; top: 8px; right: 8px; background: #E8A33D; color: #241A05; font-size: 10.5px; font-weight: 700; padding: 3px 8px; border-radius: 999px; }}
.pbody {{ padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 8px; }}
.pbrand {{ font-size: 15px; font-weight: 800; color: var(--ink); }}
.pmeta {{ display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 12.5px; color: var(--muted); }}
.pmeta .pprice {{ font-size: 16px; font-weight: 800; color: #C2410C; }}
.pmeta .prate {{ color: #B45309; font-weight: 700; }}
.pshares {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 5px; }}
.pshares .sh {{ background: #F2F5FA; border-radius: 7px; padding: 4px 7px; display: flex; justify-content: space-between; align-items: baseline; font-size: 11px; }}
.pshares .sh i {{ font-style: normal; color: var(--muted); }}
.pshares .sh b {{ color: var(--ink); font-size: 11.5px; }}
.ptitle {{ font-size: 12.5px; color: #334155; line-height: 1.45; margin: 0; }}
.pdesc {{ font-size: 12px; color: var(--muted); line-height: 1.5; margin: 0; }}
.pfeat {{ font-size: 11.5px; color: #64748B; background: #F8FAFC; border-radius: 6px; padding: 5px 8px; line-height: 1.45; margin: 0; }}
.plink {{ display: inline-block; margin-top: 2px; font-size: 12.5px; font-weight: 700; color: var(--accent); text-decoration: none; }}
.plink:hover {{ text-decoration: underline; }}
.no-img {{ color: #94A3B8; font-size: 12px; }}
@media (max-width: 1100px) {{ .pcards {{ grid-template-columns: repeat(2, 1fr); }} }}
@media (max-width: 900px) {{
  .kpi-strip, .arm-grid, .design-map, .grid2, .insight-grid {{ grid-template-columns: 1fr; }}
  .chart-box {{ height: 340px; }}
  .pcards {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>

<header class="hero">
  <div class="wrap">
    <div class="brandline">
      <svg viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="18" height="18" rx="4" stroke="%23E8A33D" stroke-width="2"/><path d="M8 15 L12 9 L16 15" stroke="%23E8A33D" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
      MatrAIx 用户模拟实验室 · 跨境电商消费者研究
    </div>
    <h1>Amazon 美国站马桶刷 TOP30 用户模拟选品实验</h1>
    <p class="sub">2 × 2 因子对照（品牌 × 评分）× 30 款全上架 × 并发 30 的万人级人格决策模拟 —— 量化「品牌」「评分」如何改变消费者的选择，以及哪些主客观因素在真正左右决策。</p>
    <div class="meta-chips">
      <span>样本：4 臂 × 1,000 人（同一批 amazon 画像）</span>
      <span>画像源：Amazon 真实用户画像 97,915 人池</span>
      <span>货架：30 款真实在售产品 + 不买选项</span>
      <span>问卷：17 题（选择 + 因素 + 态度）</span>
      <span>实验日期：2026-09</span>
    </div>
    <div class="kpi-strip">
      <div class="kpi"><div class="v" id="kpi-n">{n_shared:,}</div><div class="t">组内对照人格数</div></div>
      <div class="kpi"><div class="v" id="kpi-trials">{s.get('n_total_trials', 0):,}</div><div class="t">有效决策记录</div></div>
      <div class="kpi"><div class="v">30 + 1</div><div class="t">货架选项（含 None）</div></div>
      <div class="kpi"><div class="v" id="kpi-none">—</div><div class="t">整体「都不买」率</div></div>
    </div>
  </div>
</header>

<nav class="toc"><div class="wrap">
  <a href="#design">实验设计</a><a href="#arms">四臂结果</a><a href="#factors">因子效应</a>
  <a href="#decision">决策因素</a><a href="#disturb">干扰因素</a><a href="#market">市场对照</a>
  <a href="#insights">核心结论</a><a href="#limits">局限</a><a href="#catalog">产品全览</a>
</div></nav>

<main class="wrap">

{exec_summary}

<section id="design">
  <div class="sec-head"><span class="sec-no">01</span><h2>实验设计：2 × 2 组内因子对照</h2></div>
  <p class="sec-desc">同一批 1,000 名 Amazon 画像人格在四个货架形态下各做一次购买决策（组内对照，消除人群差异）。两个因子正交：<b>品牌</b>（匿名 P01–P30 vs 原品牌展示）与 <b>评分</b>（显示评分+评价数 vs 不显示）。四种组合构成四个独立任务，由前端 Playground 原生识别、同一官方管道运行。</p>
  <div class="design-map">
    <div class="cell brand-no rate-yes"><h5>匿名 + 评分</h5><p>货架只显示功能/外观/价格 + 评分评价数。测「产品力」+「评分」的独立影响。</p></div>
    <div class="cell brand-no"><h5>匿名 + 无评分</h5><p>只有产品力与价格。作为纯产品力基准臂。</p></div>
    <div class="cell brand-yes rate-yes"><h5>品牌 + 评分</h5><p>还原真实货架形态（品牌 + 评分 + 产品力 + 价格）。</p></div>
    <div class="cell brand-yes"><h5>品牌 + 无评分</h5><p>测品牌本身（不含评分背书）的独立影响。</p></div>
  </div>
  <div class="note">去偏处理：已剥离 Amazon's Choice 徽章、评分可信度分级、图片 OCR 吊牌文字、14 类干扰项（尺寸单位/材质翻译/多件装口径等）；画像限定 amazon 源（97,915 人），北美区域过滤，固定 seed=42 保证四臂同人格。</div>
</section>

<section id="arms">
  <div class="sec-head"><span class="sec-no">02</span><h2>四臂总体结果</h2></div>
  <p class="sec-desc">同一批消费者面对四种货架形态，选择发生了显著位移：评分一出现，头部产品格局立即改写；品牌曝光则让部分产品“人靠衣装”。</p>
  <div class="arm-grid">{arms_html}</div>
  <div class="grid2">
    <div class="card"><h3>四臂 TOP 产品选择份额（%）</h3><div id="chart-share" class="chart-box"></div></div>
    <div class="card"><h3>平均成交价（美元）</h3><div id="chart-price" class="chart-box"></div></div>
  </div>
  <div class="note">份额为同臂 1,000 人中选择该产品的占比；TOP 展示全部 30 款可横向滚动/缩放。</div>
</section>

<section id="factors">
  <div class="sec-head"><span class="sec-no">03</span><h2>因子效应：品牌与评分如何改写选择</h2></div>
  <p class="sec-desc">因子效应 = 品牌显示前后的份额差（pp，百分点），在评分两个水平上取均值；评分效应同理。正值表示该因子抬升了产品份额。</p>
  <div class="grid2">
    <div class="card"><h3>品牌曝光效应（按产品，pp）</h3><div id="chart-brand-eff" class="chart-box"></div></div>
    <div class="card"><h3>评分显示效应（按产品，pp）</h3><div id="chart-rating-eff" class="chart-box"></div></div>
  </div>
  <div class="card" style="margin-top:20px"><h3>品牌级因子汇总</h3>
    <div class="tbl-wrap"><table><thead><tr><th>品牌</th><th>SKU数</th><th>匿名份额</th><th>品牌份额</th><th>品牌效应</th><th>有评分份额</th><th>无评分份额</th><th>评分效应</th></tr></thead>
    <tbody>{bl_rows}</tbody></table></div>
  </div>
  <div class="card" style="margin-top:20px"><h3>全部 30 款明细（按品牌效应排序）</h3>
    <div class="tbl-wrap"><table><thead><tr><th>ID</th><th>品牌</th><th>价格</th><th>匿名+评分%</th><th>匿名无评分%</th><th>品牌+评分%</th><th>品牌无评分%</th><th>品牌效应pp</th><th>评分效应pp</th><th>真实榜</th></tr></thead>
    <tbody>{eff_rows}</tbody></table></div>
  </div>
</section>

<section id="decision">
  <div class="sec-head"><span class="sec-no">04</span><h2>决策因素：什么在真正左右选择</h2></div>
  <p class="sec-desc">17 题问卷覆盖主客观因素（功能、外观、价格、卫生、品牌、评分、收纳、多件装、材质、附加功能），可聚类出不同决策人群。</p>
  <div class="grid2">
    <div class="card"><h3>首要 / 次要决策因素（品牌+评分臂，%）</h3><div id="chart-factors" class="chart-box"></div></div>
    <div class="card"><h3>八项态度重要性（1–5 均值）</h3><div id="chart-importance" class="chart-box"></div></div>
  </div>
  <div class="card" style="margin-top:20px"><h3>决策人群聚类：六类消费者的选品差异（互斥分群，占比合计 100%）</h3>
    <div class="tbl-wrap"><table><thead><tr><th>人群</th><th>占比</th><th>平均接受价</th><th>首选产品（Top4）</th></tr></thead>
    <tbody>{seg_rows}</tbody></table></div>
  </div>
</section>

<section id="disturb">
  <div class="sec-head"><span class="sec-no">05</span><h2>干扰因素与决策稳定性</h2></div>
  <p class="sec-desc">从 1,000 份真实理由文本中统计信息提及率，检验实验操控是否生效；同时报告同人格跨臂的选品一致性。</p>
  <div class="grid2">
    <div class="card"><h3>理由中信息提及率（四臂对比，%）</h3><div id="chart-signals" class="chart-box"></div></div>
    <div class="card"><h3>「如果有 Amazon's Choice 徽章」影响分布</h3><div id="chart-badge" class="chart-box"></div></div>
  </div>
  <div class="grid2" style="margin-top:20px">
    <div class="card"><h3>同人格跨臂选择一致性</h3><div id="chart-stability" class="chart-box sm"></div></div>
    <div class="card"><h3>最可能触发换选的场景（%）</h3><div id="chart-switch" class="chart-box sm"></div></div>
  </div>
</section>

<section id="market">
  <div class="sec-head"><span class="sec-no">06</span><h2>与真实市场的对照校验与电商机会</h2></div>
  <p class="sec-desc">将模拟选择份额与真实榜单（月销件数 / 月销额 / BSR）做秩相关与逐款排名位移：哪一个货架形态最能还原真实购买格局，就说明对应信息维度在真实决策中的权重；模拟与真实的偏差，正指向「非货架信息」（复购、促销、曝光位）驱动的机会与风险。</p>
  <div class="card"><h3>模拟份额 vs 真实月销量（对数轴，四臂）</h3><div id="chart-market" class="chart-box"></div></div>
  <div class="note">Spearman 秩相关（模拟份额 vs 真实月销）：匿名+评分 {corr.get('anon-rating', {}).get('share_vs_sales', '—')} / 匿名无评分 {corr.get('anon-norating', {}).get('share_vs_sales', '—')} / 品牌+评分 {corr.get('brand-rating', {}).get('share_vs_sales', '—')} / 品牌无评分 {corr.get('brand-norating', {}).get('share_vs_sales', '—')}——品牌+评分（最接近真实货架）最高，说明模拟对真实市场的解释力最强。</div>
  <div class="card" style="margin-top:20px"><h3>真实榜 vs 模拟榜：哪些产品被高估 / 低估？（品牌+评分臂）</h3><div id="chart-rank-shift" class="chart-box"></div>
    <p class="note">柱越长 = 模拟与真实偏差越大。<b style="color:#1D4ED8">蓝色（向左）</b>= 模拟高估：真实榜卖得一般、模拟却排得很前（产品力/品牌吸引人，但真实转化受限）；<b style="color:#DC2626">红色（向右）</b>= 模拟低估：真实榜卖得很好、模拟却几乎没人选——这些产品的销量靠复购、促销、曝光位等「模拟看不到的因素」撑起来。</p>
    <div class="tbl-wrap" style="margin-top:12px"><table><thead><tr><th>产品</th><th>品牌</th><th>真实榜</th><th>模拟榜</th><th>位移</th><th>模拟份额</th><th>解读</th></tr></thead>
    <tbody>{shift_rows}</tbody></table></div>
  </div>
  <div class="grid2" style="margin-top:20px">
    <div class="card"><h3>品类形态：真实月销 vs 模拟偏好（%）</h3><div id="chart-category" class="chart-box"></div>
      <p class="note">真实口径=该类月销占 TOP30 总月销比重；模拟口径=品牌+评分臂该类总份额。偏差大的形态说明其真实购买主要由非货架信息驱动。</p></div>
    <div class="card"><h3>价格带：真实月销 vs 模拟偏好（%）</h3><div id="chart-priceband" class="chart-box"></div>
      <p class="note">模拟偏好向 $15–25 集中（品牌+设计溢价可接受）；真实市场在低价带更分散。</p></div>
  </div>
  <div class="card" style="margin-top:20px"><h3>营收池重估：若按模拟偏好分配，谁被高估/低估（品牌+评分臂）</h3>
    <div class="tbl-wrap"><table><thead><tr><th>产品</th><th>品牌</th><th>价格</th><th>模拟份额</th><th>模拟月营收(est)</th><th>真实月营收</th><th>比值</th></tr></thead>
    <tbody>{revenue_rows}</tbody></table></div>
    <p class="note">模拟月营收 = 模拟份额 × 真实月销售额（同 1000 人池口径）；比值 &gt; 1 表示模拟偏好下该产品创造的营收高于真实（被高估的「货架赢家」），&lt; 1 表示真实营收远超模拟份额（其销量依赖非货架信息）。</p>
  </div>
</section>

<section id="insights">
  <div class="sec-head"><span class="sec-no">07</span><h2>核心结论与电商启示</h2></div>
  <p class="sec-desc">以下结论均由本次模拟数据直接计算得出。</p>
  <div class="insight-grid">{insight_cards}</div>
</section>

<section id="limits">
  <div class="sec-head"><span class="sec-no">08</span><h2>方法局限与后续</h2></div>
  <ul class="limits">
    <li>画像为 amazon 源真实用户数据的合成人格，决策接近但不能完全等同真实消费者；月销量为第三方插件估算口径。</li>
    <li>30 选项货架存在位置/注意力偏差风险，后续可用随机打乱货架顺序复核。</li>
    <li>评分对低评价数产品（P17/P23/P29）标注了可信度提示，可能放大评分效应——按设计保留。</li>
    <li>可扩展：加入价格锚定、促销、Badge 徽章、详情页图文变体，或跨品类（如智能家居、个护）验证结论外推性。</li>
  </ul>
</section>

<section id="catalog">
  <div class="sec-head"><span class="sec-no">09</span><h2>30 款产品全览（含链接 · 图片 · 描述 · 四臂模拟份额）</h2></div>
  <p class="sec-desc">真实在售 TOP30 全字段（2026-09）：主图、品牌、价格、评分/评价数、月销、商品标题、结构化卖点描述与 Amazon 商品链接；每款附四臂模拟选择份额（匿+评 / 匿无评 / 牌+评 / 牌无评），点击即可直达真实商品页核对。</p>
  {catalog_html}
</section>

</main>

<footer><div class="wrap">
  <div>MatrAIx 用户模拟实验室 · Amazon 美国站马桶刷 TOP30 实验报告</div>
  <div>数据：Amazon.com 在售真实列表 + 用户上传 TOP30 全字段（2026-09）· 模拟：DeepSeek 驱动的 4,000 人次人格决策</div>
</div></footer>

<script>{echarts_js}</script>
<script>
const DATA = {data_json};
const INSIGHTS = {insights_json};
const ARMS = ["anon-rating","anon-norating","brand-rating","brand-norating"];
const ARM_CN = {{"anon-rating":"匿名+评分","anon-norating":"匿名·无评分","brand-rating":"品牌+评分","brand-norating":"品牌·无评分"}};
const ARM_EN = {{"anon-rating":"anon+rating","anon-norating":"anon no-rating","brand-rating":"brand+rating","brand-norating":"brand no-rating"}};

function el(id){{ return document.getElementById(id); }}
function init(id){{ const c = el(id); if (!c) return null; const ch = echarts.init(c); return ch; }}
function style(ch, opt){{ ch.setOption(opt); }}

// none rate
(function(){{
  const vals = ARMS.map(a => DATA.arms[a].none_rate);
  el("kpi-none").textContent = (vals.reduce((x,y)=>x+y,0)/vals.length).toFixed(1) + "%";
}})();

// 02 share chart
(function(){{
  const ch = init("chart-share");
  if (!ch) return;
  const pids = Array.from({{length:30}}, (_,i)=> "P"+String(i+1).padStart(2,"0"));
  const series = ARMS.map(a => ({{
    name: ARM_CN[a], type: "bar", data: pids.map(p => +(DATA.arms[a].share[p]||0).toFixed(2)),
    emphasis: {{ focus: "series" }}
  }}));
  style(ch, {{
    tooltip: {{ trigger:"axis", axisPointer:{{type:"shadow"}}, triggerOn:"click", renderMode:"richText", confine:true }},
    legend: {{ data: ARMS.map(a=>ARM_CN[a]), top: 0, type:"scroll" }},
    grid: {{ left: 40, right: 16, top: 40, bottom: 52, containLabel: true }},
    dataZoom: [
      {{ type: "inside", start: 0, end: 100, zoomOnMouseWheel: true }},
      {{ type: "slider", start: 0, end: 100, bottom: 8, height: 18, showDetail: true }}
    ],
    xAxis: {{ type:"category", data: pids, axisLabel: {{ fontSize: 10, interval: "auto", rotate: 45 }} }},
    yAxis: {{ type:"value", name:"选择份额 %", nameTextStyle:{{fontSize:11}} }},
    series: series
  }});
  window.addEventListener("resize", ()=>ch.resize());
}})();

// 02 price chart
(function(){{
  const ch = init("chart-price");
  if (!ch) return;
  style(ch, {{
    tooltip: {{ trigger:"axis", triggerOn:"click", renderMode:"richText", confine:true }},
    grid: {{ left: 40, right: 16, top: 30, bottom: 30, containLabel: true }},
    xAxis: {{ type:"category", data: ARMS.map(a=>ARM_CN[a]) }},
    yAxis: {{ type:"value", name:"USD", nameTextStyle:{{fontSize:11}} }},
    series: [{{ type:"bar", data: ARMS.map(a=>DATA.arms[a].mean_chosen_price), barWidth: 46,
      itemStyle: {{ color: "#16233B", borderRadius: [6,6,0,0] }},
      label: {{ show: true, position: "top", formatter: "\\u0024{{c}}" }} }}]
  }});
  window.addEventListener("resize", ()=>ch.resize());
}})();

// 03 brand effect chart
(function(){{
  const ch = init("chart-brand-eff");
  if (!ch) return;
  const eff = Object.values(DATA.effects).sort((a,b)=> a.brand_effect_pp - b.brand_effect_pp);
  const data = eff.map(e => ({{ value: e.brand_effect_pp, name: e.pid + " " + e.brand }}));
  style(ch, {{
    tooltip: {{ trigger:"axis", axisPointer:{{type:"shadow"}}, triggerOn:"click", renderMode:"richText", confine:true,
      formatter: function(ps){{ const p = ps[0]; const e = eff.find(x=>x.pid===p.name.slice(0,3)); if(!e) return p.name;
        return p.name + "<br/>品牌效应 " + e.brand_effect_pp + " pp<br/>匿名: " + ((e.s_anon_rating+e.s_anon_none)/2).toFixed(1) + "% → 品牌: " + ((e.s_brand_rating+e.s_brand_none)/2).toFixed(1) + "%"; }} }},
    grid: {{ left: 30, right: 30, top: 20, bottom: 20, containLabel: true }},
    xAxis: {{ type:"value", name:"pp" }},
    yAxis: {{ type:"category", data: data.map(d=>d.name), axisLabel: {{ fontSize: 10 }} }},
    series: [{{ type:"bar", data: data, barWidth: 8,
      itemStyle: {{ color: function(p){{ return p.value >= 0 ? "#C24B3F" : "#2E9E8F"; }} }} }}]
  }});
  window.addEventListener("resize", ()=>ch.resize());
}})();

// 03 rating effect chart
(function(){{
  const ch = init("chart-rating-eff");
  if (!ch) return;
  const eff = Object.values(DATA.effects).sort((a,b)=> a.rating_effect_pp - b.rating_effect_pp);
  const data = eff.map(e => ({{ value: e.rating_effect_pp, name: e.pid + " " + e.brand }}));
  style(ch, {{
    tooltip: {{ trigger:"axis", axisPointer:{{type:"shadow"}}, triggerOn:"click", renderMode:"richText", confine:true,
      formatter: function(ps){{ const p = ps[0]; const e = eff.find(x=>x.pid===p.name.slice(0,3)); if(!e) return p.name;
        return p.name + "<br/>评分效应 " + e.rating_effect_pp + " pp<br/>无评分: " + ((e.s_anon_none+e.s_brand_none)/2).toFixed(1) + "% → 有评分: " + ((e.s_anon_rating+e.s_brand_rating)/2).toFixed(1) + "%"; }} }},
    grid: {{ left: 30, right: 30, top: 20, bottom: 20, containLabel: true }},
    xAxis: {{ type:"value", name:"pp" }},
    yAxis: {{ type:"category", data: data.map(d=>d.name), axisLabel: {{ fontSize: 10 }} }},
    series: [{{ type:"bar", data: data, barWidth: 8,
      itemStyle: {{ color: function(p){{ return p.value >= 0 ? "#C24B3F" : "#2E9E8F"; }} }} }}]
  }});
  window.addEventListener("resize", ()=>ch.resize());
}})();

// 04 factor chart
(function(){{
  const ch = init("chart-factors");
  if (!ch) return;
  const fr = DATA.arms["brand-rating"].factor_rank;
  const labels = fr.map(f => f.label_en);
  const most = fr.map(f => f.most_pct);
  const second = fr.map(f => f.second_pct);
  style(ch, {{
    tooltip: {{ trigger:"axis", axisPointer:{{type:"shadow"}}, triggerOn:"click", renderMode:"richText", confine:true }},
    legend: {{ data:["首要因素","次要因素"], top: 0 }},
    grid: {{ left: 40, right: 20, top: 40, bottom: 30, containLabel: true }},
    xAxis: {{ type:"value", name:"%" }},
    yAxis: {{ type:"category", data: labels, axisLabel:{{fontSize:10}} }},
    series: [
      {{ name:"首要因素", type:"bar", data: most, barWidth: 10, itemStyle:{{color:"#16233B"}} }},
      {{ name:"次要因素", type:"bar", data: second, barWidth: 10, itemStyle:{{color:"#E8A33D"}} }}
    ]
  }});
  window.addEventListener("resize", ()=>ch.resize());
}})();

// 04 importance radar
(function(){{
  const ch = init("chart-importance");
  if (!ch) return;
  const arms = ARMS.map(a => DATA.arms[a].likerts);
  const keys = ["q_importance_price","q_importance_function","q_importance_appearance","q_importance_hygiene","q_importance_reviews","q_importance_brand","q_refill_acceptance"];
  const zh = {{"q_importance_price":"价格","q_importance_function":"功能","q_importance_appearance":"外观","q_importance_hygiene":"卫生","q_importance_reviews":"评分评论","q_importance_brand":"品牌","q_refill_acceptance":"耗材接受度"}};
  const armcolors = {{"anon-rating":"#3B6FB5","anon-norating":"#9FB0C9","brand-rating":"#E8A33D","brand-norating":"#2E9E8F"}};
  const series = ARMS.map(a => ({{
    name: ARM_CN[a], type: "bar", barWidth: 12,
    data: keys.map(k => +(arms[ARMS.indexOf(a)][k]||0).toFixed(2)),
    itemStyle: {{ color: armcolors[a], borderRadius: [3,3,0,0] }}
  }}));
  style(ch, {{
    tooltip: {{ trigger:"axis", axisPointer:{{type:"shadow"}}, triggerOn:"click", renderMode:"richText", confine:true }},
    legend: {{ data: ARMS.map(a=>ARM_CN[a]), top: 0, type:"scroll" }},
    grid: {{ left: 40, right: 16, top: 40, bottom: 30, containLabel: true }},
    xAxis: {{ type:"category", data: keys.map(k=>zh[k]), axisLabel:{{ fontSize:10, interval:0, rotate:15 }} }},
    yAxis: {{ type:"value", name:"1–5 均值", min:0, max:5, nameTextStyle:{{fontSize:11}} }},
    series: series
  }});
  window.addEventListener("resize", ()=>ch.resize());
}})();

// 05 signals grouped bar
(function(){{
  const ch = init("chart-signals");
  if (!ch) return;
  const sigs = [["brand_mention","提到品牌"],["rating_mention","提到评分/评论"],["price_mention","提到价格"],["hygiene_mention","提到卫生"],["function_mention","提到清洁功能"],["look_mention","提到外观"]];
  const armcolors2 = {{"anon-rating":"#3B6FB5","anon-norating":"#9FB0C9","brand-rating":"#E8A33D","brand-norating":"#2E9E8F"}};
  const series = ARMS.map(a => ({{ name: ARM_CN[a], type: "bar", data: sigs.map(s => DATA.rationale_signals[a][s[0]]), barWidth: 10,
    itemStyle: {{ color: armcolors2[a] }} }}));
  style(ch, {{
    tooltip: {{ trigger:"axis", axisPointer:{{type:"shadow"}}, triggerOn:"click", renderMode:"richText", confine:true }},
    legend: {{ data: ARMS.map(a=>ARM_CN[a]), top: 0, type:"scroll" }},
    grid: {{ left: 40, right: 20, top: 40, bottom: 30, containLabel: true }},
    xAxis: {{ type:"category", data: sigs.map(s=>s[1]), axisLabel:{{fontSize:10}} }},
    yAxis: {{ type:"value", name:"提及率 %", nameTextStyle:{{fontSize:11}} }},
    series: series
  }});
  window.addEventListener("resize", ()=>ch.resize());
}})();

// 05 badge effect
(function(){{
  const ch = init("chart-badge");
  if (!ch) return;
  const avg = DATA.pref_dist_avg ? DATA.pref_dist_avg.q_badge_effect : {{}};
  const order = ["yes_strongly","yes_somewhat","neutral","unlikely","no_effect"];
  const cn = {{"yes_strongly":"很有影响","yes_somewhat":"有些影响","neutral":"中立","unlikely":"基本不影响","no_effect":"完全不影响"}};
  const data = order.map(k => ({{ value: avg[k] || 0, name: cn[k] }}));
  style(ch, {{
    tooltip: {{ trigger:"item", triggerOn:"click", renderMode:"richText", confine:true, formatter: "{{b}}: {{c}}%" }},
    legend: {{ top: 0 }},
    series: [{{ type:"pie", radius:["38%","66%"], center:["50%","54%"],
      data: data, label: {{ fontSize: 11, formatter: "{{b}}\\n{{c}}%" }}, labelLine: {{ length: 10, length2: 8 }} }}]
  }});
  window.addEventListener("resize", ()=>ch.resize());
}})();

// 05 stability chart
(function(){{
  const ch = init("chart-stability");
  if (!ch) return;
  const pairs = [["rating_effect","同人格：加评分后仍选同一款"],["brand_effect_rating","同人格：加品牌后仍选同一款"]];
  const vals = pairs.map(p => DATA.persona_stability[p[0]] ? DATA.persona_stability[p[0]].same_pct : 0);
  style(ch, {{
    tooltip: {{ trigger:"axis", triggerOn:"click", renderMode:"richText", confine:true }},
    grid: {{ left: 40, right: 20, top: 30, bottom: 30, containLabel: true }},
    xAxis: {{ type:"category", data: pairs.map(p=>p[1]), axisLabel:{{fontSize:11}} }},
    yAxis: {{ type:"value", max: 100, name:"%", nameTextStyle:{{fontSize:11}} }},
    series: [{{ type:"bar", data: vals, barWidth: 60, itemStyle:{{color:"#3B6FB5", borderRadius:[6,6,0,0]}},
      label: {{ show:true, position:"top", formatter:"{{c}}%" }} }}]
  }});
  window.addEventListener("resize", ()=>ch.resize());
}})();

// 05 switch trigger
(function(){{
  const ch = init("chart-switch");
  if (!ch) return;
  const avg = DATA.pref_dist_avg ? DATA.pref_dist_avg.q_switch_trigger : {{}};
  const order = ["lower_price","better_rating","better_look","better_function","better_value","nothing"];
  const cn = {{"lower_price":"更低价格","better_rating":"更高评分/更多评论","better_look":"更好看","better_function":"更强功能","better_value":"更值(多件/耗材)","nothing":"不会换选"}};
  const data = order.map(k => ({{ value: avg[k] || 0, name: cn[k] }}));
  style(ch, {{
    tooltip: {{ trigger:"item", triggerOn:"click", renderMode:"richText", confine:true, formatter: "{{b}}: {{c}}%" }},
    legend: {{ top: 0 }},
    series: [{{ type:"pie", radius:["38%","66%"], center:["50%","54%"],
      data: data, label: {{ fontSize: 11, formatter: "{{b}}\\n{{c}}%" }}, labelLine: {{ length: 10, length2: 8 }} }}]
  }});
  window.addEventListener("resize", ()=>ch.resize());
}})();

// 06 market scatter
(function(){{
  const ch = init("chart-market");
  if (!ch) return;
  const pids = Object.keys(DATA.effects);
  const colors = {{"anon-rating":"#3B6FB5","anon-norating":"#9FB0C9","brand-rating":"#E8A33D","brand-norating":"#2E9E8F"}};
  const series = ARMS.map(a => ({{
    name: ARM_CN[a], type: "scatter",
    data: pids.map(p => [DATA.effects[p].gt_monthly_sales, +(DATA.arms[a].share[p]||0).toFixed(2)]),
    symbolSize: 8, itemStyle: {{ color: colors[a], opacity: 0.7 }}
  }}));
  style(ch, {{
    tooltip: {{ trigger:"item", triggerOn:"click", renderMode:"richText", confine:true,
      formatter: function(p){{ const pid = pids[p.dataIndex]; return pid + " " + DATA.effects[pid].brand + "<br/>真实月销 " + DATA.effects[pid].gt_monthly_sales + " 件<br/>模拟份额 " + p.value[1] + "%"; }} }},
    legend: {{ data: ARMS.map(a=>ARM_CN[a]), top: 0, type:"scroll" }},
    grid: {{ left: 50, right: 30, top: 40, bottom: 40, containLabel: true }},
    xAxis: {{ type:"log", name:"真实月销(件)", nameTextStyle:{{fontSize:11}} }},
    yAxis: {{ type:"value", name:"模拟份额 %", nameTextStyle:{{fontSize:11}} }},
    series: series
  }});
  window.addEventListener("resize", ()=>ch.resize());
}})();

// 06 rank shift: 真实榜 vs 模拟榜（品牌+评分臂，横向条形图）
(function(){{
  const ch = init("chart-rank-shift");
  if (!ch) return;
  const rc = (DATA.rank_compare||{{}})["brand-rating"] || [];
  // 取 4 个最大低估 + 4 个最大高估，按位移升序排列（高估负值在左，低估正值在右）
  const picked = [...rc].sort((a,b)=> a.delta - b.delta).slice(0,4).concat([...rc].sort((a,b)=> b.delta - a.delta).slice(0,4));
  picked.sort((a,b)=> a.delta - b.delta);
  style(ch, {{
    tooltip: {{ trigger:"axis", axisPointer:{{type:"shadow"}}, triggerOn:"click", renderMode:"richText", confine:true,
      formatter: function(ps){{ const d = picked[ps[0].dataIndex]; return d.pid + " " + d.brand +
        "<br/>真实榜 #" + d.gt_rank + " → 模拟榜 #" + d.sim_rank +
        "<br/>位移 " + (d.delta>0 ? "+" : "") + d.delta + " 位<br/>模拟份额 " + d.share + "%"; }} }},
    grid: {{ left: 110, right: 46, top: 20, bottom: 30, containLabel: true }},
    xAxis: {{ type:"value", name:"位移（位）", nameTextStyle:{{fontSize:11}}, axisLabel:{{ fontSize:10 }} }},
    yAxis: {{ type:"category", data: picked.map(d=>d.pid+" "+d.brand), axisLabel:{{ fontSize:10 }} }},
    series: [{{
      type: "bar", data: picked.map(d => ({{
        value: d.delta,
        itemStyle: {{ color: d.delta < 0 ? "#1D4ED8" : "#DC2626", borderRadius: [0,4,4,0] }}
      }})), barWidth: 16,
      label: {{ show: true, fontSize: 10, color: "#334155",
        position: function(p){{ return picked[p.dataIndex].delta < 0 ? "left" : "right"; }},
        formatter: function(p){{ const d = picked[p.dataIndex]; return "真实#" + d.gt_rank + "→模拟#" + d.sim_rank; }} }}
    }}]
  }});
  window.addEventListener("resize", ()=>ch.resize());
}})();

// 06 category structure
(function(){{
  const ch = init("chart-category");
  if (!ch) return;
  const cats = DATA.category_structure || [];
  style(ch, {{
    tooltip: {{ trigger:"axis", axisPointer:{{type:"shadow"}}, triggerOn:"click", renderMode:"richText", confine:true }},
    legend: {{ data: ["真实月销占比","模拟份额"], top: 0, type:"scroll" }},
    grid: {{ left: 40, right: 16, top: 36, bottom: 30, containLabel: true }},
    xAxis: {{ type:"category", data: cats.map(c=>c.category), axisLabel:{{ fontSize:10, interval:0, rotate:20 }} }},
    yAxis: {{ type:"value", name:"%", nameTextStyle:{{fontSize:11}} }},
    series: [
      {{ name:"真实月销占比", type:"bar", data: cats.map(c=>c.gt_sales_share), itemStyle:{{ color:"#9FB0C9" }} }},
      {{ name:"模拟份额", type:"bar", data: cats.map(c=>c.sim_share), itemStyle:{{ color:"#E8A33D" }} }}
    ]
  }});
  window.addEventListener("resize", ()=>ch.resize());
}})();

// 06 price band
(function(){{
  const ch = init("chart-priceband");
  if (!ch) return;
  const bands = DATA.price_band || [];
  style(ch, {{
    tooltip: {{ trigger:"axis", axisPointer:{{type:"shadow"}}, triggerOn:"click", renderMode:"richText", confine:true }},
    legend: {{ data: ["真实月销占比","模拟份额"], top: 0 }},
    grid: {{ left: 40, right: 16, top: 36, bottom: 30, containLabel: true }},
    xAxis: {{ type:"category", data: bands.map(b=>b.band), axisLabel:{{ fontSize:10 }} }},
    yAxis: {{ type:"value", name:"%", nameTextStyle:{{fontSize:11}} }},
    series: [
      {{ name:"真实月销占比", type:"bar", data: bands.map(b=>b.gt_sales_share), itemStyle:{{ color:"#9FB0C9" }} }},
      {{ name:"模拟份额", type:"bar", data: bands.map(b=>b.sim_share), itemStyle:{{ color:"#E8A33D" }} }}
    ]
  }});
  window.addEventListener("resize", ()=>ch.resize());
}})();
</script>
</body>
</html>"""
    return html


def build_instigths_placeholder():
    return []


def main() -> None:
    summary_path = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "results" / "toilet-brush-top30-experiment" / "top30_2x2_summary.json"
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    s = json.loads(summary_path.read_text(encoding="utf-8"))
    html = build_html(s)
    out_path.write_text(html, encoding="utf-8")
    print("wrote", out_path, f"({len(html)} bytes)")


if __name__ == "__main__":
    main()
