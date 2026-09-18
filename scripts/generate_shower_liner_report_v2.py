#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2: Rebuild the shower-liner click-journey report following the v3 choice-report
visual language (dark hero + KPI row, numbered product cards, takeaway boxes,
tag cards, clean numbered sections)."""

from __future__ import annotations
import json, base64
from pathlib import Path

ROOT = Path("/Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B")
SRC = ROOT / "results/shower-liner-journey"
OUT = ROOT / "results/shower-liner-journey" / "shower_liner_journey_report.html"
ECHARTS = (ROOT / "scripts/vendor/echarts.min.js").read_text(encoding="utf-8")

S = json.loads((SRC / "summary.json").read_text(encoding="utf-8"))
RACE = json.loads((SRC / "race_stages.json").read_text(encoding="utf-8"))
SCATTER = json.loads((SRC / "scatter.json").read_text(encoding="utf-8"))
SANKEY_CLICK = json.loads((SRC / "sankey_click.json").read_text(encoding="utf-8"))

ASSETS = ROOT / "results/shower-liner-6asin" / "assets"
ASINS = {"A": "B0CGLZ56JC", "B": "B0C9MCD5WL", "C": "B0C2GTPSFR",
         "D": "B0GYWQQ2K3", "E": "B0D212C4XS", "F": "B0FSRN9YTK"}

PROD = {
    "A": {"brand": "AmazerBath", "name": "AmazerBath Rainbow Emerald EVA Shower Curtain Liner 72×72",
          "price": "$18.99", "rating": "4.5★ · 4,156 评", "mat": "100% EVA · 黄铜扣眼",
          "look": "半透明祖母绿 EVA，自然垂坠，12 黄铜扣眼+配重；明亮现代浴室场景",
          "points": "豪华触感 EVA · BPA-free 无味环保 · 防锈黄铜扣眼 · 双层加固挂头 · 底部配重防飘 · 防水速干",
          "status": ("warn", "点击王 + 偏好王，成交洼地：$18.99 挡单")},
    "B": {"brand": "jssablo", "name": "jssablo Blue Cube 3D EVA Magnetic Liner 72×72",
          "price": "$7.19", "rating": "4.4★ · 1,872 评", "mat": "70% EVA",
          "look": "深蓝渐变→透明 3D 立方格纹；金属扣眼+配重底；现代浴室",
          "points": "3D 立方纹理 · 12 金属扣眼 · 底部 3 磁吸贴浴缸 · 防水 · 易冲洗",
          "status": ("ok", "性价比次选：二次点击 38.3%，但低价反被怀疑质量")},
    "C": {"brand": "LQFMEHOT", "name": "LQFMEHOT EVA Blue Water-Wave Art Deco 72×72",
          "price": "$7.09", "rating": "4.6★ · 974 评", "mat": "EVA 轻量",
          "look": "深蓝→透蓝水波纹 Art Deco 纹理；金属扣眼+配重底；白浴缸深色瓷砖",
          "points": "水波纹图案 · 防水光滑面 · 底部 3 重磁铁 · 防撕裂挂头+防锈金属扣 · 无味 EVA",
          "status": ("ok", "低价 + 最高星级 4.6：二次点击第一，同样被低价质量怀疑拖累")},
    "D": {"brand": "Laumyasof", "name": "Laumyasof 2-Pack Green 3D Pebble EVA 72×72",
          "price": "$9.99", "rating": "4.4★ · 16 评", "mat": "EVA（薄）· 2 件装",
          "look": "半透明绿 3D 鹅卵石纹理；图上标 2 PACK；白瓷砖浴室",
          "points": "2 件装价值 · 3D 鹅卵石设计 · 12 防锈扣眼 · 底部 3 磁吸 · 拒水速干",
          "status": ("bad", "首点 0%：16 条评论撑不起第一眼信任")},
    "E": {"brand": "Dependable", "name": "Dependable Industries EVA Black Modern 72×72",
          "price": "$9.99", "rating": "4.3★ · 116 评", "mat": "EVA · PVC-free",
          "look": "纯黑无图案极简；银色金属扣眼；白底影棚图",
          "points": "防水防溅 · 底部 3 配重磁吸 · 加固扣眼 · 易擦拭 · 标准 72×72 · PVC-free",
          "status": ("bad", "存在感最低：外观太素 + 评论量不足，首点 0.2%")},
    "F": {"brand": "MuuXii", "name": "MuuXii EVA Clear Polka-Dot with Hooks 71×71",
          "price": "$7.99*", "rating": "4.4★ · 10 评", "mat": "EVA 防水",
          "look": "浅蓝透明底+波点；附 12 个白色塑料挂钩；明亮浴室",
          "points": "全透明透光 · 底部 3 磁吸 · 附 12 挂钩 · 易冲洗 · 轻量",
          "status": ("bad", "首点 0%：评论太少 + 尺寸 71×71 存疑；价格为实验补价")},
}

L = {
    "first": "首点", "second": "第2次点击", "third": "第3次点击", "fallback": "兜底最想买", "buy": "最终成交",
    "A": "A AmazerBath", "B": "B jssablo", "C": "C LQFMEHOT", "D": "D Laumyasof", "E": "E Dependable", "F": "F MuuXii",
    "review_count": "评论数量多(社会证明)", "material_word": "材质词(无味/BPA-free)", "imagine_look": "能想象装进浴室效果",
    "star_rating": "星级高", "main_image": "主图/场景图吸睛", "color_pattern": "颜色/花纹/3D纹理突出",
    "price": "卡片价格划算", "title_keyword": "标题命中需求词", "brand": "认识/信任品牌",
    "pack_value": "件装/赠挂钩价值", "magnets": "磁吸/配重卖点", "right_size": "尺寸合适", "other": "其他",
    "reviews_photos": "带图/视频评论", "negative_reviews": "差评与抱怨", "bullets": "五点卖点",
    "material_cert": "材质与安全认证", "size_specs": "尺寸/规格表", "zoom_images": "放大图片看质感",
    "main_video": "主图视频/演示", "aplus": "A+品牌内容", "qa": "问答Q&A",
    "price_deal": "价格/优惠", "delivery_returns": "配送与退换", "seller": "卖家信息",
    "want_compare": "没毛病，想再比比", "price_too_high": "价格太贵", "price_suspicious": "太便宜担心质量",
    "transparency": "透明度不合需求", "material": "材质不放心", "no_concern": "没有顾虑，会买",
    "few_reviews": "评论太少", "brand_unfamiliar": "品牌陌生", "look": "外观不合眼缘",
    "size": "尺寸存疑", "missing_magnet": "缺磁吸/配重", "pack": "件装不对", "info_incomplete": "页面信息不全",
    "review_concern": "评论有疑虑", "rating": "评分不够",
    "timing": "只是先逛逛，不急着买", "reviews_trust": "评论太少/参差，信任不足",
    "look_compromise": "外观只是妥协", "info_gap": "listing 没解答我的疑问",
    "page1": "只看第1页", "page2": "会翻到第2页", "page3": "会翻到第3页",
    "page4_5": "会翻到4-5页", "beyond": "可能超过5页", "unsure": "不确定",
    "reviews": "评论数与评论内容", "price_value": "价格/性价比", "appearance": "外观",
    "magnet": "磁吸/配重", "size_fit": "尺寸", "waterproof": "防水防霉", "rating": "星级",
    "brand": "品牌信任", "pack": "件装/挂钩价值", "listing": "listing完整度",
    "material_unclear": "材质不明", "blur_image": "主图模糊/像假图", "low_rating": "评分<4.0",
    "no_size": "无尺寸信息", "mismatch_title": "标题与图不符/堆词", "no_bullets": "无五点/描述薄",
    "no_aplus": "无A+/视频", "none": "以上都不至于排除",
    "eva": "EVA", "peva": "PEVA", "pvc": "PVC", "polyester": "聚酯纤维", "cloth": "棉布", "no_preference": "无偏好",
    "fully_transparent": "全透明", "semi": "半透明", "blackout": "遮光",
    "yes_strongly": "会，很大影响", "yes_somewhat": "会，有些影响", "neutral": "中立",
    "unlikely": "可能不会", "no_effect": "完全不影响",
    "lower_price": "更低价格", "better_rating": "更高评分/更多评论", "better_look": "更好看",
    "better_function": "功能更强(磁吸/防水)", "better_value": "更值(2件装/挂钩)", "better_listing": "页面更清晰完整",
    "nothing": "不会换", "final_purchase": "最终下单款", "fallback_favorite": "最想买但没下单",
    "skip_ordered": "已在前序下单", "add_cart": "加入购物车，继续比", "not_buy": "不买，返回搜索", "buy_now": "直接下单",
    "yes_more": "会，返回继续看别的", "no_ordered": "不会，现在下单第一个", "no_leave": "不会，什么都不买离开",
}

def img_b64(oid):
    p = ASSETS / f"{ASINS[oid]}.jpg"
    return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()

def pct_list(items):
    return [(k, v["pct"]) for k, v in items]

def top(d, n=99):
    return list(d.items())[:n]

# ---------- 预计算 ----------
ALIGN = S["alignment"]
RACE_L = ["首点", "第2次点击", "第3次点击", "兜底最想买", "最终成交"]
RACE_S = {oid: [RACE.get(s, {}).get(oid, 0) for s in ("first", "second", "third", "fallback", "buy")]
          for oid in "ABCDEF"}
DRIVERS = pct_list(S["click_drivers"].items())
DETAIL = pct_list(S["detail_info"].items())
NOTBUY1 = pct_list(S["notbuy_first"].items())
BLOCKER = pct_list(S["fallback_blocker"].items())
REDLINE = pct_list(S["listing_redline"].items())
FACTOR1 = pct_list(S["factor_most"].items())
FACTOR2 = pct_list(S["factor_second"].items())
LIKE = [(k.replace("q_importance_", ""), v) for k, v in S["likert_means"].items() if k.startswith("q_importance_")]
LIKE_NAMES = {"title": "标题完整度", "image": "主图清晰度", "bullets": "五点卖点", "aplus": "A+/视频",
              "attr": "属性规格表", "price": "价格性价比", "reviews": "评分与评论", "trust": "品牌与认证"}
PAGE_BROWSE = S["page_browse"]
PAGE_BUY = S["page_buy"]

REASON_LABEL = {"price_too_high": "价格太贵", "transparency": "透明度不合需求", "price_suspicious": "太便宜担心质量",
                "look": "外观不合眼缘", "brand": "品牌陌生", "material": "材质不放心", "few_reviews": "评论太少",
                "pack": "件装不对", "size": "尺寸存疑", "info_incomplete": "页面信息不全", "missing_magnet": "缺磁吸/配重",
                "review_concern": "评论有疑虑", "rating": "评分不够", "other": "其他"}

# 桑基2：产品 → 被拒理由
SK_NODES, SK_LINKS = [], []
seen = set()
for oid in "ABCDEF":
    if oid not in seen:
        seen.add(oid); SK_NODES.append({"name": oid})
    for k, v in S["reject_reasons"][oid].items():
        if k in ("final_purchase", "fallback_favorite"):
            continue
        if k not in seen:
            seen.add(k); SK_NODES.append({"name": k})
        SK_LINKS.append({"source": oid, "target": k, "value": v["n"]})

# 散点分组
SCAT_GROUPS = {"A": [], "B": [], "C": [], "D": [], "E": [], "F": [], "none": []}
for px, py, fb in SCATTER:
    SCAT_GROUPS[fb if fb in SCAT_GROUPS else "none"].append([px, py])

# ============ HTML 骨架 ============
def hero_kpis():
    return f"""
      <div class="kpi-row">
        <div class="kpi"><div class="lbl">有效样本</div><div class="v">1,000</div><div class="s">Amazon 北美画像 · 通过率 100%</div></div>
        <div class="kpi"><div class="lbl">首点集中度</div><div class="v">94.2%</div><div class="s">942 人第一眼点进 A（AmazerBath）</div></div>
        <div class="kpi"><div class="lbl">前三款直接下单率</div><div class="v">2.3%</div><div class="s">23/1000 在浏览 3 款内直接购买</div></div>
        <div class="kpi"><div class="lbl">兜底回流</div><div class="v">83.5%</div><div class="s">不买之后最想买的仍是 A</div></div>
      </div>"""

def highlights():
    items = [
        ("点击 ≠ 成交", "首点 A 占 94.2%，但 A 直接下单仅 0.9%；97.7% 的人看完 3 款仍未下单——高点击和高转化是两回事。", "首点 94.2% · 直接下单 2.3% · 兜底回流 A 83.5%"),
        ("下单只认第 1 页", "99.2% 的人只在搜索第 1 页下单；浏览可以翻到第 2 页（93.9%）——第 1 页位置 = 生死线。", "购买页1容忍度 99.2% vs 浏览页2容忍度 93.9%"),
        ("价格是最后一道坎", "85.1% 把 A 列为最想买，却因价格/性价比犹豫——不是买不起，是下不了决心。", "价格接受度均分 3.21/5 · 兜底阻碍价格 85.1%"),
        ("低价反而劝退", "B/C 两款 $7 级产品被 76-78% 的人以“太便宜担心质量/气味”拒绝——低价没有信任背书就是负资产。", "B 78.1% · C 76.0% 因价格可疑被拒"),
        ("评论是第一资产", "评论数是点击第一驱动（97.5%），60.5% 把评论列为整个旅程首要因素；D/F 因评论太少被 99.2% 排除。", "评论因素首要 60.5% · 点击驱动评论数 97.5%"),
        ("listing 三条红线一票否决", "材质不明、主图模糊/像假图、评分<4.0，各被 99% 的人列为直接排除条件。", "三条红线命中率 99.1%-99.2%"),
    ]
    cards = "".join(
        f'<div class="hl-card"><div class="n">{t}</div><p>{d}</p><div class="ev">{e}</div></div>'
        for t, d, e in items)
    return f'<div class="hl-banner"><h2>先看结论 · 6 句话</h2><div class="hl-grid">{cards}</div></div>'

def product_cards():
    cards = ""
    for oid in "ABCDEF":
        p = PROD[oid]
        al = next(x for x in ALIGN if x["option"] == oid)
        rej = S["reject_reasons"][oid]
        top1 = [(k, v["pct"]) for k, v in rej.items() if k not in ("final_purchase", "fallback_favorite")][:1]
        rej_txt = f"被拒主因：{REASON_LABEL.get(top1[0][0], top1[0][0])} {top1[0][1]}%" if top1 else ""
        st_cls, st_txt = p["status"]
        cards += f"""
        <div class="prod-card">
          <div class="ph">
            <img src="{img_b64(oid)}" alt="{p['brand']}">
            <div class="no">{oid}</div>
            <div class="share">首点 {al['first_click_pct']}%</div>
          </div>
          <div class="bd">
            <div class="pname">{oid} · {p['brand']}</div>
            <div class="meta">价格 {p['price']} · {p['rating']} · {p['mat']}</div>
            <div class="feat">{p['look']}</div>
            <div class="feat" style="color:#8a94a6">{p['points']}</div>
            <div class="status {st_cls}">{st_txt}</div>
            <div class="meta">{rej_txt}</div>
            <div class="meta">直接下单 {al['final_buy_pct']}% · 兜底最想买 {al['fallback_fav_pct']}%</div>
            <a href="https://www.amazon.com/dp/{ASINS[oid]}" target="_blank" rel="noopener">Amazon 页面 · ASIN {ASINS[oid]}</a>
          </div>
        </div>"""
    return f'<div class="prod-grid">{cards}</div>'

def personas():
    return """
    <div class="card"><h3>买家是谁</h3>
      <p>1,000 名 <b>Amazon 北美站购物者画像</b>（同一人格池，可与此前马桶刷 TOP30 实验跨实验对比）。画像覆盖：美国/加拿大日常家居采购者、租房与自有住房家庭、按浴室空间和淋浴习惯选购内衬的实用型买家，含价格敏感与品质优先等不同人群。</p>
      <div class="takeaway"><b>为什么可信：</b>人格从亚马逊真实购物语境生成，决策链完整（搜索→首点→详情→比较→兜底），且<b>购买状态（缺货/无价/配送）已被剔除</b>，结果只反映"货架信息 + 价格 + 信任"的纯偏好。</div>
    </div>"""

def methodology():
    return """
    <div class="callout"><b>实验设计：</b>6 款浴帘内衬在搜索第 1 页同场展示（全上架），1000 名买家依次经历 5 个决策节点，每个节点必须给出理由：① 第一眼最想点进哪款？② 详情页先看什么信息？③ 是否购买？不买出于什么顾虑？④ 退出后是否再看别的？看哪款？（可到第 3 次点击）⑤ 全部点完仍不买时，最想买的是哪一款？</div>
    <div class="card"><h3>控制变量与口径</h3>
      <p>· <b>剔除干扰参数：</b>购买状态（库存/可售/配送）不参与任何展示与理由，防止"买不了所以不买"污染归因。<br>
      · <b>F 款补价：</b>F 源数据无价格，按同规格带挂钩 EVA 浴帘市场价补为 <b>$7.99*</b>（受控假设值，非源数据，仅用于本次对照）。<br>
      · <b>成交口径：</b>"直接下单"= 在前 3 次点击任一详情页明确选择 buy_now（严格口径）；"兜底最想买"= 全部浏览后 q_fallback 的选择。<br>
      · 模型 deepseek-chat · seed=42 · 并发 150 · 答卷通过率 100%（0 错误）。</p>
    </div>"""

def quotes_html():
    q = S["quotes_first_click"]
    lines = []
    for oid in "ABCDEF":
        for t in q.get(oid, [])[:1]:
            lines.append(f'<div class="quote"><b>首点 {oid} · {PROD[oid]["brand"]}</b><br>“{t}”</div>')
    fb = S["quotes_fallback"]
    for oid in ["A", "C", "B"]:
        for t in fb.get(oid, [])[:1]:
            lines.append(f'<div class="quote"><b>兜底 {oid} · {PROD[oid]["brand"]}</b><br>“{t}”</div>')
    return '<div class="grid2">' + "".join(lines) + "</div>"

def action_cards():
    items = [
        ("抢第 1 页，保前 3 位", "99.2% 只在第 1 页下单。广告与排名预算优先保住核心词第 1 页曝光，第 2 页只有浏览价值没有转化价值。", "把握：高"),
        ("评论量是第一资产", "评论数驱动点击（97.5%）、决策第一因素（60.5%）、新品红线（<50 评 82% 排除）。新品先拿种子评论+老品带新，突破 50 条线再投流。", "把握：高"),
        ("差评与晒图是转化开关", "99.9% 看带图评论、99.2% 查差评。差评区要有合理解释与卖家回复，晒图决定最后一脚。", "把握：高"),
        ("主图与五点别省", "主图清晰度 4.85/5、材质认证 99% 必查。主图放真实场景+材质细节，五点讲清无味/防水/磁吸。", "把握：高"),
        ("价格带卡在信任盲区", "$7 档被 76-78% 质疑质量；$18.99 档被 98.8% 嫌贵。$9-13 档+价值包装（件装/挂钩/磁吸）是甜区。", "把握：中高"),
        ("降价不如降犹豫", "85.1% 卡在“价格/性价比”而非买不起。用优惠券、套装、包邮降低决策成本，比裸降价更能守住利润。", "把握：中"),
        ("A+/视频优先级最低", "重要性仅 2.04/5。先把评论、主图、五点、属性表做扎实，A+ 是锦上添花不是雪中送炭。", "把握：中"),
        ("别把浏览当购买", "97.7% 看完不买是常态（比较型购物）。用站内 Coupon、到货提醒、复购场景内容把“最想买”转成订单。", "把握：中"),
    ]
    cards = "".join(f'<div class="card"><h3>{i+1}. {t}</h3><p>{d}</p><div class="takeaway"><b>{c}</b></div></div>'
                    for i, (t, d, c) in enumerate(items))
    return cards

def verdict_cards():
    rows = [
        ("KEEP", "good", "高评论 + 高星级 + 主图场景感，是打开第一眼点击的钥匙", "A 首点 94.2%：评论数 97.5% / 星级 91.7% / 主图 90.6% 是点击驱动前三"),
        ("KEEP", "good", "“最想买”的偏好已经建立：A 兜底 83.5%、C/B 合计 14%", "偏好存在但被价格与时机挡住——是转化动作问题，不是货架问题"),
        ("FIX", "fix", "$18.99 的 A 被 98.8% 以“价格太贵”拒绝；$7 的 B/C 被 76-78% 怀疑质量", "价格带两个极端都在丢分，中间 $9-13 是空白甜区"),
        ("FIX", "fix", "新品 D/F（16/10 评）首点 0%、被 99.2% 以“评论太少”排除", "没有评论量就打不进决策圈，新品必须先解决冷启动"),
        ("TEST", "test", "E 纯黑极简有 0.2% 首点 + 0.4% 兜底，被拒理由是外观+评论", "黑/极简在 116 评下立不住；若评论做起来值得再测外观人群"),
        ("TEST", "test", "B/C 二次点击合计 95.1%，但最终成交仅 1.4%", "说明“值得看”≠“值得买”——低价款缺的是质量信任证据（材质认证/晒图）"),
        ("BASELINE", "good", "大盘及格线：评论≥50、星级≥4.5、材质与主图清晰", "红线数据显示材质不明/图糊/评分<4.0 各 99% 一票否决"),
    ]
    cards = ""
    for tag, cls, t, ev in rows:
        cards += f'<div class="card"><h3><span class="tag tag-{cls}">{tag}</span> {t}</h3><div class="sec-desc" style="margin:6px 0 0">{ev}</div></div>'
    return cards

# ============ 图表 JS ============
CHART_JS = r'''
var PALETTE = ['#3B6FB5','#E8A33D','#2E9E8F','#C24B3F','#8E44AD','#16A085','#95A5A6','#F39C12','#2980B9','#D35400'];
var TOOLTIP = {triggerOn:'click', renderMode:'richText', confine:true};
function mk(id, opt){ var c = echarts.init(document.getElementById(id)); c.setOption(opt); return c; }

/* ---- 1. Bar Chart Race ---- */
(function(){
  var stages = __RACE_L__;
  var sm = __RACE_S__;
  var chart = echarts.init(document.getElementById('ch-race'));
  var idx = 0;
  function opt(i){
    var data = [];
    ['A','B','C','D','E','F'].forEach(function(o){ data.push({name:o, value:sm[o][i]}); });
    data.sort(function(a,b){ return b.value - a.value; });
    return {
      title:{text:stages[i] + ' · 各产品份额', left:14, top:8, textStyle:{fontSize:15, fontWeight:700, color:'#16233B'}},
      tooltip:Object.assign({trigger:'item'}, TOOLTIP),
      grid:{left:60, right:70, top:50, bottom:28, containLabel:true},
      xAxis:{type:'value', max:100, axisLabel:{formatter:'{value}%', fontSize:11}, splitLine:{lineStyle:{type:'dashed'}}},
      yAxis:{type:'category', inverse:true, data:data.map(function(d){return d.name;}), axisLabel:{fontSize:13, fontWeight:700, color:'#22303F'}},
      series:[{type:'bar', data:data, barWidth:24,
        itemStyle:{color:function(p){return PALETTE[p.dataIndex];}, borderRadius:[0,6,6,0]},
        label:{show:true, position:'right', formatter:function(p){return p.value+'%';}, fontSize:12, fontWeight:700, color:'#22303F'}}]
    };
  }
  chart.setOption(opt(0));
  setInterval(function(){ idx=(idx+1)%stages.length; chart.setOption(opt(idx), true); }, 1800);
})();

/* ---- 2. 首点/下单/兜底 对比 ---- */
(function(){
  var d = __ALIGN__;
  var names = {A:'A\nAmazerBath',B:'B\njssablo',C:'C\nLQFMEHOT',D:'D\nLaumyasof',E:'E\nDependable',F:'F\nMuuXii'};
  mk('ch-align', {
    title:{text:'首点点击 vs 直接下单 vs 兜底最想买（占全体 %）', left:14, top:8, textStyle:{fontSize:15, fontWeight:700, color:'#16233B'}},
    tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'}}, TOOLTIP),
    legend:{top:36, data:['首点点击','直接下单','兜底最想买']},
    grid:{left:20, right:20, top:74, bottom:24, containLabel:true},
    xAxis:{type:'category', data:d.map(function(x){return names[x.option];}), axisLabel:{fontSize:11, lineHeight:14}},
    yAxis:{type:'value', max:100, axisLabel:{formatter:'{value}%', fontSize:11}},
    series:[
      {name:'首点点击', type:'bar', data:d.map(function(x){return x.first_click_pct;}), barWidth:15, itemStyle:{color:'#3B6FB5', borderRadius:[3,3,0,0]}},
      {name:'直接下单', type:'bar', data:d.map(function(x){return x.final_buy_pct;}), barWidth:15, itemStyle:{color:'#C24B3F', borderRadius:[3,3,0,0]}},
      {name:'兜底最想买', type:'bar', data:d.map(function(x){return x.fallback_fav_pct;}), barWidth:15, itemStyle:{color:'#E8A33D', borderRadius:[3,3,0,0]}}
    ]
  });
})();

/* ---- 3. 桑基：首点 -> 下单 ---- */
(function(){
  var flow = __SANKEY_FLOW__;
  var prod = {A:'A AmazerBath',B:'B jssablo',C:'C LQFMEHOT',D:'D Laumyasof',E:'E Dependable',F:'F MuuXii'};
  var lm = {};
  flow.forEach(function(r){
    var s = '首点 · ' + (prod[r[0]]||r[0]);
    var t = r[1]==='none' ? '未下单' : '下单 · ' + (prod[r[1]]||r[1]);
    var k = s+'|'+t; lm[k]=(lm[k]||0)+1;
  });
  var nodes=[], links=[], seen={};
  Object.keys(lm).forEach(function(k){
    var p=k.split('|');
    [p[0],p[1]].forEach(function(n){ if(!seen[n]){seen[n]=1; nodes.push({name:n});} });
    links.push({source:p[0], target:p[1], value:lm[k]});
  });
  mk('ch-sankey-click', {
    title:{text:'从首点产品到最终下单的流向（n=1000）', left:14, top:8, textStyle:{fontSize:15, fontWeight:700, color:'#16233B'}},
    tooltip:Object.assign({trigger:'item'}, TOOLTIP),
    series:[{type:'sankey', left:30, right:60, top:50, bottom:16,
      data:nodes, links:links, lineStyle:{color:'gradient', curveness:0.5},
      itemStyle:{borderWidth:0}, label:{fontSize:11, color:'#22303F'}, emphasis:{focus:'adjacency'}}]
  });
})();

/* ---- 4. 桑基：被拒理由 ---- */
(function(){
  var nodes = __SK_NODES__;
  var links = __SK_LINKS__;
  var nm = {A:'A AmazerBath',B:'B jssablo',C:'C LQFMEHOT',D:'D Laumyasof',E:'E Dependable',F:'F MuuXii'};
  var rl = __REASON_LABEL__;
  nodes.forEach(function(n){ n.name = nm[n.name]||rl[n.name]||n.name; });
  links.forEach(function(l){ l.source = nm[l.source]||rl[l.source]||l.source; l.target = nm[l.target]||rl[l.target]||l.target; });
  mk('ch-sankey-reject', {
    title:{text:'为什么没选它？每款被拒主因流向（人次）', left:14, top:8, textStyle:{fontSize:15, fontWeight:700, color:'#16233B'}},
    tooltip:Object.assign({trigger:'item'}, TOOLTIP),
    series:[{type:'sankey', left:20, right:130, top:50, bottom:16,
      data:nodes, links:links, lineStyle:{color:'gradient', curveness:0.5},
      itemStyle:{borderWidth:0}, label:{fontSize:11, color:'#22303F'}, emphasis:{focus:'adjacency'}}]
  });
})();

/* ---- 5. 点击驱动 ---- */
(function(){
  var d = __DRIVERS__;
  mk('ch-drivers', {
    title:{text:'什么让 1000 人第一眼点进这款？', left:14, top:8, textStyle:{fontSize:15, fontWeight:700, color:'#16233B'}},
    tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'}}, TOOLTIP),
    grid:{left:20, right:60, top:44, bottom:20, containLabel:true},
    xAxis:{type:'value', max:100, axisLabel:{formatter:'{value}%', fontSize:11}},
    yAxis:{type:'category', inverse:true, data:d.map(function(x){return x[0];}), axisLabel:{fontSize:11, color:'#22303F'}},
    series:[{type:'bar', data:d.map(function(x){return x[1];}), barWidth:15,
      itemStyle:{color:'#3B6FB5', borderRadius:[0,5,5,0]}, label:{show:true, position:'right', formatter:'{c}%', fontSize:11}}]
  });
})();

/* ---- 6. 详情页信息 ---- */
(function(){
  var d = __DETAIL__;
  mk('ch-detail', {
    title:{text:'点进详情页后，先看什么？（选中率）', left:14, top:8, textStyle:{fontSize:15, fontWeight:700, color:'#16233B'}},
    tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'}}, TOOLTIP),
    grid:{left:20, right:60, top:44, bottom:20, containLabel:true},
    xAxis:{type:'value', max:100, axisLabel:{formatter:'{value}%', fontSize:11}},
    yAxis:{type:'category', inverse:true, data:d.map(function(x){return x[0];}), axisLabel:{fontSize:11, color:'#22303F'}},
    series:[{type:'bar', data:d.map(function(x){return x[1];}), barWidth:15,
      itemStyle:{color:'#2E9E8F', borderRadius:[0,5,5,0]}, label:{show:true, position:'right', formatter:'{c}%', fontSize:11}}]
  });
})();

/* ---- 7. 顾虑 ---- */
(function(){
  var nb = __NOTBUY1__; var bl = __BLOCKER__;
  mk('ch-concern', {
    title:{text:'“为什么没下单”的真实顾虑', left:14, top:8, textStyle:{fontSize:15, fontWeight:700, color:'#16233B'}},
    tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'}}, TOOLTIP),
    legend:{top:36, data:['首个产品未下单原因','兜底最想买却未买的阻碍']},
    grid:{left:20, right:20, top:74, bottom:20, containLabel:true},
    xAxis:{type:'value', max:100, axisLabel:{formatter:'{value}%', fontSize:11}},
    yAxis:{type:'category', inverse:true, data:bl.map(function(x){return x[0];}), axisLabel:{fontSize:11, color:'#22303F'}},
    series:[
      {name:'首个产品未下单原因', type:'bar', data:bl.map(function(x){ var f=nb.filter(function(y){return y[0]===x[0];}); return f.length?f[0][1]:0; }), barWidth:13, itemStyle:{color:'#E8A33D'}},
      {name:'兜底最想买却未买的阻碍', type:'bar', data:bl.map(function(x){return x[1];}), barWidth:13, itemStyle:{color:'#C24B3F'}}
    ]
  });
})();

/* ---- 8. 页数容忍度 ---- */
(function(){
  var order = ['page1','page2','page3','page4_5','beyond','unsure'];
  var pl = {page1:'只看第1页', page2:'翻到第2页', page3:'翻到第3页', page4_5:'翻到4-5页', beyond:'超过5页', unsure:'不确定'};
  var pb = __PAGE_BROWSE__; var pby = __PAGE_BUY__;
  mk('ch-page', {
    title:{text:'搜索页数容忍度：浏览 vs 下单（%）', left:14, top:8, textStyle:{fontSize:15, fontWeight:700, color:'#16233B'}},
    tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'}}, TOOLTIP),
    legend:{top:36, data:['仍会浏览','仍会下单']},
    grid:{left:20, right:20, top:74, bottom:24, containLabel:true},
    xAxis:{type:'category', data:order.map(function(k){return pl[k]||k;}), axisLabel:{fontSize:11, interval:0}},
    yAxis:{type:'value', max:100, axisLabel:{formatter:'{value}%', fontSize:11}},
    series:[
      {name:'仍会浏览', type:'bar', data:order.map(function(k){return pb[k]?pb[k].pct:0;}), barWidth:16, itemStyle:{color:'#3B6FB5'}},
      {name:'仍会下单', type:'bar', data:order.map(function(k){return pby[k]?pby[k].pct:0;}), barWidth:16, itemStyle:{color:'#C24B3F'}}
    ]
  });
})();

/* ---- 9. 决策因素 ---- */
(function(){
  var f1 = __FACTOR1__; var f2 = __FACTOR2__;
  mk('ch-factor', {
    title:{text:'整个旅程中，什么最重要？（首要 + 次要）', left:14, top:8, textStyle:{fontSize:15, fontWeight:700, color:'#16233B'}},
    tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'}}, TOOLTIP),
    legend:{top:36, data:['首要因素','次要因素']},
    grid:{left:20, right:20, top:74, bottom:20, containLabel:true},
    xAxis:{type:'value', max:80, axisLabel:{formatter:'{value}%', fontSize:11}},
    yAxis:{type:'category', inverse:true, data:f1.map(function(x){return x[0];}), axisLabel:{fontSize:11, color:'#22303F'}},
    series:[
      {name:'首要因素', type:'bar', data:f1.map(function(x){return x[1];}), barWidth:13, itemStyle:{color:'#3B6FB5'}},
      {name:'次要因素', type:'bar', data:f1.map(function(x){ var f=f2.filter(function(y){return y[0]===x[0];}); return f.length?f[0][1]:0; }), barWidth:13, itemStyle:{color:'#B9C6DA'}}
    ]
  });
})();

/* ---- 10. listing 8 要素 ---- */
(function(){
  var d = __LIKE__; var nm = __LIKE_NAMES__;
  mk('ch-listing', {
    title:{text:'商品页 8 个部分，哪个最重要（5 分制均值）', left:14, top:8, textStyle:{fontSize:15, fontWeight:700, color:'#16233B'}},
    tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'}}, TOOLTIP),
    grid:{left:20, right:60, top:44, bottom:20, containLabel:true},
    xAxis:{type:'value', max:5, axisLabel:{fontSize:11}},
    yAxis:{type:'category', inverse:true, data:d.map(function(x){return nm[x[0]]||x[0];}), axisLabel:{fontSize:11, color:'#22303F'}},
    series:[{type:'bar', data:d.map(function(x){return x[1];}), barWidth:15,
      itemStyle:{color:function(p){return p.value>=4.5?'#C24B3F':(p.value>=4?'#E8A33D':'#B9C6DA');}, borderRadius:[0,5,5,0]},
      label:{show:true, position:'right', formatter:'{c}', fontSize:12, fontWeight:700}}]
  });
})();

/* ---- 11. 红线 ---- */
(function(){
  var d = __REDLINE__;
  mk('ch-redline', {
    title:{text:'listing 红线：出现即一票否决（选中率）', left:14, top:8, textStyle:{fontSize:15, fontWeight:700, color:'#16233B'}},
    tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'}}, TOOLTIP),
    grid:{left:20, right:60, top:44, bottom:20, containLabel:true},
    xAxis:{type:'value', max:100, axisLabel:{formatter:'{value}%', fontSize:11}},
    yAxis:{type:'category', inverse:true, data:d.map(function(x){return x[0];}), axisLabel:{fontSize:11, color:'#22303F'}},
    series:[{type:'bar', data:d.map(function(x){return x[1];}), barWidth:15,
      itemStyle:{color:function(p){return p.value>=90?'#C24B3F':'#E8A33D';}, borderRadius:[0,5,5,0]},
      label:{show:true, position:'right', formatter:'{c}%', fontSize:11}}]
  });
})();

/* ---- 12. 人群散点 ---- */
(function(){
  var g = __SCAT_GROUPS__;
  var colors = {A:'#E8A33D',B:'#3B6FB5',C:'#2E9E8F',D:'#8E44AD',E:'#7F8C8D',F:'#F39C12',none:'#CBD5E1'};
  var names = {A:'偏好 A (AmazerBath)',B:'偏好 B (jssablo)',C:'偏好 C (LQFMEHOT)',D:'偏好 D',E:'偏好 E',F:'偏好 F',none:'未选中'};
  var series = [];
  Object.keys(colors).forEach(function(k){
    series.push({name:names[k], type:'scatter', symbolSize:7,
      data:g[k].map(function(p){ return [Math.max(0.5,Math.min(5.5,p[0]+(Math.random()-0.5)*0.35)), Math.max(0.5,Math.min(5.5,p[1]+(Math.random()-0.5)*0.35))]; }),
      itemStyle:{color:colors[k], opacity:0.55}, emphasis:{itemStyle:{opacity:0.95}}});
  });
  mk('ch-scatter', {
    title:{text:'人群分布：价格接受度 × 购买意向（颜色=最终偏好）', left:14, top:8, textStyle:{fontSize:15, fontWeight:700, color:'#16233B'}},
    tooltip:Object.assign({trigger:'item'}, TOOLTIP),
    legend:{top:36, type:'scroll', textStyle:{fontSize:10}},
    grid:{left:20, right:20, top:80, bottom:42, containLabel:true},
    xAxis:{type:'value', name:'价格接受度 (1=太贵 5=可接受)', min:0.5, max:5.5, nameLocation:'middle', nameGap:28, axisLabel:{fontSize:10}},
    yAxis:{type:'value', name:'购买意向 (1=不会买 5=会买)', min:0.5, max:5.5, nameLocation:'middle', nameGap:34, axisLabel:{fontSize:10}},
    series:series
  });
})();
'''

# ============ 组装 ============
CSS = r'''
:root{--ink:#16233B;--paper:#F7F8FA;--card:#FFF;--line:#E3E7EE;--text:#22303F;--muted:#64748B;
--amber:#E8A33D;--teal:#2E9E8F;--red:#C24B3F;--blue:#3B6FB5;--our:#C24B3F;--ourbg:#FDECEA;}
*{box-sizing:border-box}
body{margin:0;font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif;background:var(--paper);color:var(--text);line-height:1.75;font-size:15px}
h1,h2,h3{margin:0}
.hero{background:var(--ink);color:#fff;padding:40px 24px}
.hero-inner{max-width:1080px;margin:0 auto}
.hero .kicker{font-size:12px;letter-spacing:.12em;color:var(--amber);font-weight:600}
.hero h1{font-size:clamp(22px,3vw,32px);font-weight:900;margin:8px 0}
.hero .sub{font-size:14px;color:#C8D3E3;max-width:900px}
.chips span{display:inline-block;border:1px solid rgba(255,255,255,.22);border-radius:999px;padding:3px 11px;font-size:12px;color:#E6ECF5;margin:4px 6px 0 0}
.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-top:16px}
.kpi{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);border-radius:12px;padding:12px 14px}
.kpi .lbl{font-size:12px;color:#B9C6DA}
.kpi .v{font-size:20px;font-weight:800;color:var(--amber);margin-top:2px}
.kpi .s{font-size:11.5px;color:#8FA0BC;margin-top:2px}
main{max-width:1080px;margin:0 auto;padding:24px 18px 60px}
section{margin-top:36px}
.sec-no{font-size:14px;font-weight:700;color:var(--amber)}
.sec-head h2{font-size:21px;color:var(--ink);display:inline}
.sec-desc{color:var(--muted);font-size:13.5px;margin:4px 0 14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-bottom:14px}
.card h3{font-size:16px;color:var(--ink);margin-bottom:8px}
.card p{font-size:14px;color:#33415C;margin:0}
.fig{width:100%;height:360px}
.fig.sm{height:320px}
.takeaway{font-size:14px;background:#F4F7FB;border-left:3px solid var(--amber);padding:8px 14px;border-radius:0 8px 8px 0;margin-top:10px}
.takeaway b{color:var(--ink)}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}
.hl-banner{background:linear-gradient(120deg,#16233B,#1D2E4F);border-radius:18px;padding:24px}
.hl-banner h2{color:#fff;font-size:18px;margin-bottom:10px}
.hl-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.hl-card{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:13px 14px}
.hl-card .n{font-size:15px;font-weight:800;color:var(--amber);line-height:1.3}
.hl-card p{color:#DDE5F2;font-size:13.5px;margin:6px 0 0}
.hl-card .ev{color:#9FB3D0;font-size:12px;margin-top:6px}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{border-bottom:1px solid var(--line);padding:8px 9px;text-align:left;vertical-align:top}
th{background:#F2F5F9}
.prod-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}
.prod-card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;display:flex;flex-direction:column}
.prod-card .ph{position:relative;aspect-ratio:1/1;background:#EEF1F5}
.prod-card .ph img{width:100%;height:100%;object-fit:cover}
.prod-card .ph .no{position:absolute;top:10px;left:10px;background:rgba(22,35,59,.9);color:#fff;width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:17px;font-weight:700}
.prod-card .ph .share{position:absolute;top:10px;right:10px;background:var(--amber);color:#16233B;font-weight:700;font-size:13px;padding:3px 10px;border-radius:999px}
.prod-card .bd{padding:13px 15px;display:flex;flex-direction:column;gap:6px;flex:1}
.prod-card .pname{font-size:15px;font-weight:700;color:var(--ink)}
.prod-card .meta{font-size:12.5px;color:var(--muted)}
.prod-card .feat{font-size:13px;color:#33415C}
.prod-card .status{font-size:12.5px;font-weight:700}
.prod-card .status.ok{color:var(--teal)}.prod-card .status.warn{color:#B07A1A}.prod-card .status.bad{color:var(--red)}
.prod-card a{font-size:11.5px;color:var(--blue);text-decoration:none;word-break:break-all}
.tag{display:inline-block;font-size:12px;font-weight:700;padding:2px 10px;border-radius:999px}
.tag-good{background:#E4F3F0;color:#1D6B5F}.tag-fix{background:#FBE9E5;color:#A43C30}.tag-test{background:#FFF4E0;color:#9A6B12}
.quote{border-left:3px solid var(--amber);background:#FBF7EF;padding:10px 14px;margin:8px 0;font-size:13px;border-radius:0 8px 8px 0}
.callout{background:#F0F6F4;border:1px solid #CFE3DD;border-radius:12px;padding:12px 16px;font-size:14px;color:#24453F;margin:0 0 14px}
.footer{border-top:1px solid var(--line);margin-top:40px;padding:20px;text-align:center;color:var(--muted);font-size:12.5px}
@media(max-width:720px){.card .fig{height:300px}.grid2,.prod-grid{grid-template-columns:1fr}}
'''

def sec(no, title, desc, body):
    return f"""<section>
  <div class="sec-head"><span class="sec-no">{no}</span> <h2>{title}</h2></div>
  <div class="sec-desc">{desc}</div>
  {body}
</section>"""

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>亚马逊浴帘内衬 6 款 · 点击旅程模拟实验报告（n=1000）</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%2316233B'/%3E%3Cpath d='M16 46 L32 18 L48 46 Z' fill='%23E8A33D'/%3E%3C/svg%3E">
<style>{CSS}</style>
</head>
<body>

<div class="hero"><div class="hero-inner">
  <div class="kicker">USER SIMULATION · AMAZON US · SHOWER LINER</div>
  <h1>浴帘内衬 6 款 · 搜索 → 点击 → 购买旅程模拟</h1>
  <div class="sub">1000 名北美亚马逊画像买家，从搜索第一眼到最终下单，5 个决策节点全程记录理由。回答三个问题：谁赢、为什么、下一步做什么。</div>
  <div class="chips">
    <span>n = 1000 · 通过率 100%</span>
    <span>Amazon 北美画像（与马桶刷实验同一人格池，可对比）</span>
    <span>deepseek-chat · seed 42</span>
    <span>剔除购买状态（库存/无价/配送）</span>
    <span>5 决策节点 · 每个理由必答</span>
    <span>F 款 $7.99* 为受控补价</span>
  </div>
  {hero_kpis()}
</div></div>

<main>

{sec("00", "先看结论", "6 句话，带证据。", highlights())}

{sec("01", "先认识这 6 款产品", "编号 A-F 全篇通用，方便对照。右上角徽章 = 搜索页第一眼点进比例。",
     product_cards())}

{sec("02", "这些买家是谁", "模拟对象画像与可信度依据。", personas())}

{sec("03", "测试怎么做的", "旅程设计、控制变量与口径。", methodology())}

{sec("04", "结果：谁赢谁输", "份额动态回放 + 三层对比 + 两张某基图。",
     f"""
     <div class="card"><h3>决策竞赛回放：5 个决策节点份额动态（Bar Chart Race）</h3>
       <div id="ch-race" class="fig"></div>
       <div class="takeaway"><b>一句话：</b>A 首点 94.2% 开局碾压 → C/B（$7 档）在第 2-3 次点击抢走“查看” → 兜底时偏好又回流 A（83.5%）→ 但成交几乎为 0。注意力和购买力是两套系统。</div>
     </div>
     <div class="card"><h3>首点点击 vs 直接下单 vs 兜底最想买</h3>
       <div id="ch-align" class="fig sm"></div>
       <div class="takeaway"><b>一句话：</b>A 同时是点击王与偏好王，却是成交洼地（0.9%）；D/E/F 全程 0% 首点。9 成成交发生在 A/B/C 三款之间。</div>
     </div>
     <div class="grid2">
       <div class="card"><h3>从首点产品到最终下单的流向</h3>
         <div id="ch-sankey-click" class="fig sm"></div>
         <div class="takeaway"><b>一句话：</b>942 人首点 A，最终只有 23 人（2.3%）在前 3 款内直接下单——977 人全部看完仍未下单。</div>
       </div>
       <div class="card"><h3>为什么没选它？被拒主因流向</h3>
         <div id="ch-sankey-reject" class="fig sm"></div>
         <div class="takeaway"><b>一句话：</b>A 被“价格太贵”堵死（98.8%）；B/C 被“太便宜担心质量”反噬；D/E/F 被“评论太少”出局。三组死因完全不同。</div>
       </div>
     </div>
     """)}

{sec("05", "旅程细节：第一眼与详情页", "买家在每个环节看什么、被什么打动。",
     f"""
     <div class="grid2">
       <div class="card"><h3>什么让 1000 人第一眼点进这款？</h3>
         <div id="ch-drivers" class="fig sm"></div>
         <div class="takeaway"><b>一句话：</b>评论数 97.5% / 材质词 97% / 可想象效果 92.1% —— 第一眼是“信任证据 + 画面感”的战争。</div>
       </div>
       <div class="card"><h3>点进详情页后，先看什么？</h3>
         <div id="ch-detail" class="fig sm"></div>
         <div class="takeaway"><b>一句话：</b>带图评论 99.9% / 差评 99.2% / 五点 99.2% / 材质认证 99.2% —— 几乎人人全查一遍，listing 任何短板都会被看见。</div>
       </div>
     </div>
     """)}

{sec("06", "旅程细节：为什么不买、翻几页", "阻碍决策的两个隐形因素。",
     f"""
     <div class="grid2">
       <div class="card"><h3>“为什么没下单”的真实顾虑</h3>
         <div id="ch-concern" class="fig sm"></div>
         <div class="takeaway"><b>一句话：</b>98.5% 首个产品不买是因为“想再比比”（不是产品差，是决策习惯）；85.1% 最终卡在价格/性价比。</div>
       </div>
       <div class="card"><h3>搜索页数容忍度：浏览 vs 下单</h3>
         <div id="ch-page" class="fig sm"></div>
         <div class="takeaway"><b>一句话：</b>浏览可以翻到第 2 页（93.9%），下单 99.2% 只认第 1 页——第 1 页是生死线，第 2 页只有曝光价值。</div>
       </div>
     </div>
     """)}

{sec("07", "什么决定选择：因素与 listing 优化", "把决策因素落到商品页可改的东西上。",
     f"""
     <div class="grid2">
       <div class="card"><h3>整个旅程中，什么最重要？（首要 + 次要）</h3>
         <div id="ch-factor" class="fig sm"></div>
         <div class="takeaway"><b>一句话：</b>评论是第一因素（60.5% 首选），价格与材质并列第二梯队——先管评论，再管价格策略。</div>
       </div>
       <div class="card"><h3>商品页 8 个部分，哪个最重要（5 分制）</h3>
         <div id="ch-listing" class="fig sm"></div>
         <div class="takeaway"><b>一句话：</b>评分评论 4.98 / 主图 4.85 断层领先，A+/视频仅 2.04 垫底——先补前两项，别急着做品牌故事。</div>
       </div>
     </div>
     <div class="card"><h3>listing 红线：出现即一票否决</h3>
       <div id="ch-redline" class="fig"></div>
       <div class="takeaway"><b>一句话：</b>材质不明、主图模糊/像假图、评分<4.0 各被 99% 的人列为直接排除条件；新品评论<50 也是 82% 的红线。</div>
     </div>
     """)}

{sec("08", "人群分布：谁在嫌贵、谁在观望", "用价格接受度 × 购买意向看 1000 人的站位。",
     f"""
     <div class="card"><h3>价格接受度 × 购买意向（颜色 = 最终偏好）</h3>
       <div id="ch-scatter" class="fig"></div>
       <div class="takeaway"><b>一句话：</b>A 偏好人群集中在“嫌贵（低接受度）但想买（高意向）”的左上区——典型“想要但没下单”；B/C 偏好人群分散在中部。这就是价格策略的目标人群：降价/优惠/价值包装直接命中左上区。</div>
     </div>
     """)}

{sec("09", "对 6 款产品意味着什么", "KEEP / FIX / TEST 分级结论，直接可执行。",
     f'<div class="grid2">{verdict_cards()}</div>')}

{sec("10", "买家原声", "答卷理由摘录，未经修改。", quotes_html())}

{sec("11", "下一步怎么做", "按把握大小排序的 8 条行动建议。", action_cards())}

<div class="footer">
  生成于 2026-09-18 · MatrAIx-Persona-8B 用户模拟选品实验 · 数据源：Amazon.com 全字段明细（2026-09-17）+ 1000 名亚马逊画像买家旅程模拟<br>
  图表可交互：悬停看数值、桑基点击聚焦、竞赛图自动轮播
</div>

</main>
<script>{ECHARTS}</script>
<script>
{CHART_JS
 .replace("__RACE_L__", json.dumps(RACE_L, ensure_ascii=False))
 .replace("__RACE_S__", json.dumps(RACE_S, ensure_ascii=False))
 .replace("__ALIGN__", json.dumps(ALIGN, ensure_ascii=False))
 .replace("__SANKEY_FLOW__", json.dumps(SANKEY_CLICK, ensure_ascii=False))
 .replace("__SK_NODES__", json.dumps(SK_NODES, ensure_ascii=False))
 .replace("__SK_LINKS__", json.dumps(SK_LINKS, ensure_ascii=False))
 .replace("__REASON_LABEL__", json.dumps(REASON_LABEL, ensure_ascii=False))
 .replace("__DRIVERS__", json.dumps(DRIVERS, ensure_ascii=False))
 .replace("__DETAIL__", json.dumps(DETAIL, ensure_ascii=False))
 .replace("__NOTBUY1__", json.dumps(NOTBUY1, ensure_ascii=False))
 .replace("__BLOCKER__", json.dumps(BLOCKER, ensure_ascii=False))
 .replace("__PAGE_BROWSE__", json.dumps(PAGE_BROWSE, ensure_ascii=False))
 .replace("__PAGE_BUY__", json.dumps(PAGE_BUY, ensure_ascii=False))
 .replace("__FACTOR1__", json.dumps(FACTOR1, ensure_ascii=False))
 .replace("__FACTOR2__", json.dumps(FACTOR2, ensure_ascii=False))
 .replace("__LIKE__", json.dumps(LIKE, ensure_ascii=False))
 .replace("__LIKE_NAMES__", json.dumps(LIKE_NAMES, ensure_ascii=False))
 .replace("__REDLINE__", json.dumps(REDLINE, ensure_ascii=False))
 .replace("__SCAT_GROUPS__", json.dumps(SCAT_GROUPS, ensure_ascii=False))}
</script>
</body>
</html>"""

OUT.write_text(html, encoding="utf-8")
print("written:", OUT, f"({OUT.stat().st_size/1024/1024:.2f} MB)")
