#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「Amazon 美国站 · 浴帘内衬 6 款竞品 · 2000 人次买家模拟实验」综合 HTML 报告。
数据源: results/shower-liner-6asin-experiment/shower_liner_summary.json + 原始 CSV（主题词频）
样式: 深蓝主色 + 琥珀强调（沿用马桶刷报告视觉体系）
"""
import base64, json, os, re, sys

ROOT = "/Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B"
SUMMARY = os.path.join(ROOT, "results/shower-liner-6asin-experiment/shower_liner_summary.json")
ASSETS = os.path.join(ROOT, "results/shower-liner-6asin/assets")
OUT = os.path.join(ROOT, "results/shower-liner-6asin-experiment/shower_liner_experiment_report.html")
TOILET_REPORT = os.path.join(ROOT, "results/toilet-brush-top30-experiment/toilet_top30_experiment_report.html")

s = json.load(open(SUMMARY))

# ---------- 产品档案（含描述/链接/图片） ----------
products = [
    dict(code="A", asin="B0CGLZ56JC", brand="AmazerBath", name="祖母绿·半透明 EVA 2 合 1",
         price="$18.99", rating="4.5★", reviews="4,156", rank="#27",
         desc="100% EVA 半透明祖母绿重型浴帘内衬，黄铜扣眼 12 个 + 3 个配重石，72x72，奢华 2 合 1。页面无 featured offer（仅配送提示）。",
         status="配送受限 · 无 Featured Offer", link="https://www.amazon.com/dp/B0CGLZ56JC",
         img="B0CGLZ56JC.jpg", share=20.8, reject_top=[["价格过高",792],["外观",238],["库存/配送",237],["透明度",180]]),
    dict(code="B", asin="B0C9MCD5WL", brand="jssablo", name="蓝·3D 水波纹",
         price="$7.19", rating="4.4★", reviews="1,872", rank="#41",
         desc="100% 防水 EVA 蓝色 3D 水波纹，底部 3 个重型磁铁 + 12 个防锈扣眼，72x72。现货在售。",
         status="In Stock 现货", link="https://www.amazon.com/dp/B0C9MCD5WL",
         img="B0C9MCD5WL.jpg", share=17.9, reject_top=[["外观",669],["价格存疑",409],["品牌",250],["评分",192]]),
    dict(code="C", asin="B0C2GTPSFR", brand="LQFMEHOT", name="蓝·3D 水立方（Art Deco）",
         price="$7.09", rating="4.6★", reviews="974", rank="#124",
         desc="EVA 蓝色 3D 水立方纹理（Art Deco 风），12 个防锈金属扣眼 + 配重磁铁，72x72，防水耐用。6 款中评分最高、价格最低。现货在售。",
         status="In Stock 现货", link="https://www.amazon.com/dp/B0C2GTPSFR",
         img="B0C2GTPSFR.jpg", share=60.0, reject_top=[["品牌",360],["价格存疑",257],["外观",210],["评价数少",186]]),
    dict(code="D", asin="B0GYWQQ2K3", brand="Laumyasof", name="绿·3D 鹅卵石 2 件装",
         price="$9.99", rating="4.4★", reviews="16", rank="#129",
         desc="2 件装绿色 3D 鹅卵石 EVA 浴帘内衬，72x72，防锈金属扣眼 + 配重磁铁。新品，评价极少。",
         status="In Stock 现货 · 新品", link="https://www.amazon.com/dp/B0GYWQQ2K3",
         img="B0GYWQQ2K3.jpg", share=0.0, reject_top=[["评价数少",982],["材质存疑",821],["2件装不适用",455],["外观",86]]),
    dict(code="E", asin="B0D212C4XS", brand="Dependable", name="纯黑·基础款",
         price="$9.99", rating="4.3★", reviews="116", rank="#203",
         desc="EVA 纯黑浴帘内衬，72x72，3 个磁铁 + 金属扣眼。无图案基础款。库存紧张。",
         status="仅剩 10 件", link="https://www.amazon.com/dp/B0D212C4XS",
         img="B0D212C4XS.jpg", share=1.3, reject_top=[["外观",925],["库存/配送",596],["评价数少",466],["评分",207]]),
    dict(code="F", asin="B0FSRN9YTK", brand="MuuXii", name="透明波点",
         price="无价", rating="4.4★", reviews="10", rank="#856",
         desc="EVA 透明波点（含挂钩）71x71，12 个防锈扣眼 + 3 个配重磁铁。Currently unavailable，页面无价格。",
         status="Currently unavailable", link="https://www.amazon.com/dp/B0FSRN9YTK",
         img="B0FSRN9YTK.jpg", share=0.0, reject_top=[["评价数少",967],["库存/配送",897],["尺寸",310],["透明度",45]]),
]

def b64(path):
    with open(path, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()

for p in products:
    p["img_b64"] = b64(os.path.join(ASSETS, p["img"]))

# ---------- 抽取 echarts.min.js（复用马桶刷报告内嵌块） ----------
toilet_html = open(TOILET_REPORT).read()
m = re.search(r"<script>(/\*.*?Licensed to the Apache.*?)</script>", toilet_html, re.S)
if not m:
    m = re.search(r"<script>(\s*/\*.*?)</script>", toilet_html, re.S)
ECHARTS_JS = m.group(1) if m else "/* echarts unavailable */"

# ---------- 聚合数据 ----------
c = s["choice"]; j = s["journey"]
DATA = {
    "meta": s["meta"],
    "products": products,
    "choice": {
        "share": c["share_pct"],
        "reject_top": c["reject_top_reasons"],
        "page_browse": c["page_browse_pct"], "page_buy": c["page_buy_pct"],
        "factor_most": c["factor_most_pct"], "factor_second": c["factor_second_pct"],
        "importance": c["importance_mean_1to5"],
        "redline": c["redline_pct"],
        "material_pref": c["material_pref_pct"], "transparency_pref": c["transparency_pref_pct"],
        "badge_effect": c["badge_effect_pct"], "switch_trigger": c["switch_trigger_pct"],
        "price_accept_mean": c["price_accept_mean"],
    },
    "journey": {
        "first_click": j["first_click_pct"], "click_info": j["click_info_pct"],
        "buy_decision": j["buy_decision_pct"], "buy_yes": j["buy_yes_pct"],
        "consider_other": j["consider_other_pct"], "next_choice": j["next_choice_pct"],
        "fallback": j["fallback_pct"], "page_search": j["page_search_pct"],
        "overall_factor": j["overall_factor_pct"], "cross": j["first_to_fallback_pct"],
    },
    "reasons": {
        "clickA": {"外观": 2187, "磁吸配重": 860, "评价数": 793, "材质安全": 717, "信任品质": 621},
        "fallbackC": {"材质安全": 1175, "评分": 1037, "磁吸配重": 943, "价格价值": 887, "评价数": 857},
        "switchC": {"评分": 1102, "外观": 706, "评价数": 608, "价格价值": 607, "库存配送": 376},
        "notbuy": {"库存配送": 140, "价格价值": 36, "外观": 19, "材质安全": 16},
    },
    "quotes": {
        "first_click": j["sample_first_click_reasons"],
        "fallback": j["sample_fallback_reasons"],
        "buy": j["sample_buy_reasons"],
    },
}

# 真实类目排名（源表）
RANK_TRUTH = {"A": 27, "B": 41, "C": 124, "D": 129, "E": 203, "F": 856}

DATA_JSON = json.dumps(DATA, ensure_ascii=False)
RANK_JSON = json.dumps(RANK_TRUTH)

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Amazon 美国站 · 浴帘内衬 6 款竞品 · 2000 人次买家模拟选品实验报告</title>
<style>
:root {
  --ink:#16233B; --ink-2:#22345A; --paper:#F7F8FA; --card:#FFFFFF;
  --line:#E3E7EE; --text:#22303F; --muted:#64748B;
  --amber:#E8A33D; --teal:#2E9E8F; --red:#C24B3F; --blue:#3B6FB5;
}
* { box-sizing: border-box; }
body { margin:0; font-family:"Noto Sans SC","PingFang SC","Microsoft YaHei",system-ui,sans-serif; background:var(--paper); color:var(--text); line-height:1.7; }
h1,h2,h3,h4 { font-family:"Noto Serif SC","Songti SC","STSong",Georgia,serif; margin:0; }
header.hero { background:var(--ink); color:#fff; padding:60px 24px 52px; position:relative; overflow:hidden; }
header.hero::before { content:""; position:absolute; right:-120px; top:-120px; width:440px; height:440px; border-radius:50%; background:radial-gradient(circle, rgba(232,163,61,.30), transparent 65%); }
header.hero::after { content:""; position:absolute; left:-80px; bottom:-160px; width:380px; height:380px; border-radius:50%; background:radial-gradient(circle, rgba(46,158,143,.22), transparent 65%); }
.hero-inner { max-width:1180px; margin:0 auto; position:relative; z-index:1; }
.hero .kicker { font-size:13px; letter-spacing:.14em; color:var(--amber); font-weight:600; }
.hero h1 { font-size:clamp(24px,3.2vw,38px); font-weight:900; line-height:1.3; margin:12px 0 10px; max-width:980px; }
.hero .sub { font-size:15.5px; color:#C8D3E3; max-width:820px; margin-bottom:22px; }
.meta-chips { display:flex; flex-wrap:wrap; gap:10px; }
.meta-chips span { border:1px solid rgba(255,255,255,.22); border-radius:999px; padding:5px 14px; font-size:12.5px; color:#E6ECF5; background:rgba(255,255,255,.06); }
.kpi-row { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:12px; margin-top:26px; }
.kpi { background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.14); border-radius:12px; padding:14px 16px; }
.kpi .lbl { font-size:12px; color:#B9C6DA; }
.kpi .v { font-family:"Noto Serif SC",serif; font-size:24px; font-weight:700; color:var(--amber); margin-top:2px; }
.kpi .s { font-size:11.5px; color:#8FA0BC; margin-top:2px; }
nav.toc { position:sticky; top:0; z-index:50; background:rgba(255,255,255,.95); backdrop-filter:blur(8px); border-bottom:1px solid var(--line); }
.toc-inner { max-width:1180px; margin:0 auto; display:flex; gap:2px; overflow-x:auto; padding:0 8px; }
nav.toc a { padding:13px 13px; font-size:13px; color:var(--muted); text-decoration:none; white-space:nowrap; border-bottom:2px solid transparent; }
nav.toc a:hover, nav.toc a.active { color:var(--ink); border-bottom-color:var(--amber); }
main { max-width:1180px; margin:0 auto; padding:34px 20px 80px; }
section { margin-top:46px; }
.sec-head { display:flex; align-items:baseline; gap:12px; margin-bottom:6px; }
.sec-no { font-family:"Noto Serif SC",serif; font-size:14px; font-weight:700; color:var(--amber); letter-spacing:.06em; }
.sec-head h2 { font-size:23px; font-weight:800; color:var(--ink); }
.sec-desc { color:var(--muted); font-size:13.5px; margin-bottom:22px; max-width:900px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:20px 22px; margin-bottom:16px; }
.card h3 { font-size:16px; color:var(--ink); margin-bottom:8px; }
.card .fig { width:100%; height:400px; }
.card .fig.sm { height:320px; }
.card .note { font-size:12.5px; color:var(--muted); margin-top:6px; }
.grid2 { display:grid; grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); gap:16px; }
.hl-banner { background:linear-gradient(120deg,#16233B 0%,#1D2E4F 55%,#26406B 100%); border:1px solid rgba(255,255,255,.10); border-radius:18px; padding:30px 30px 24px; margin:10px 0 6px; }
.hl-banner h2 { color:#fff; font-size:21px; display:flex; align-items:center; gap:10px; }
.hl-banner h2 .badge { font-size:11px; font-weight:600; color:var(--amber); border:1px solid rgba(232,163,61,.5); padding:3px 10px; border-radius:999px; letter-spacing:.08em; }
.hl-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:12px; margin-top:18px; }
.hl-card { background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.12); border-radius:12px; padding:14px 15px 12px; }
.hl-card .n { font-family:"Noto Serif SC",serif; font-size:19px; font-weight:800; color:var(--amber); line-height:1.2; }
.hl-card .tag { display:inline-block; font-size:10px; color:var(--amber); border:1px solid rgba(232,163,61,.4); border-radius:4px; padding:1px 7px; margin:6px 0 4px; letter-spacing:.06em; }
.hl-card p { color:#D7E0EF; font-size:13px; margin:0; }
.hl-card .ev { color:#9FB3D0; font-size:11.5px; margin-top:6px; }
.prod-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:16px; }
.prod-card { background:var(--card); border:1px solid var(--line); border-radius:14px; overflow:hidden; display:flex; flex-direction:column; }
.prod-card .ph { position:relative; aspect-ratio:1/1; background:#EEF1F5; }
.prod-card .ph img { width:100%; height:100%; object-fit:cover; }
.prod-card .ph .rank-badge { position:absolute; top:10px; left:10px; background:rgba(22,35,59,.88); color:#fff; font-size:12px; padding:3px 10px; border-radius:999px; }
.prod-card .ph .share-badge { position:absolute; top:10px; right:10px; background:var(--amber); color:#16233B; font-weight:700; font-size:13px; padding:3px 10px; border-radius:999px; }
.prod-card .bd { padding:14px 16px 16px; display:flex; flex-direction:column; gap:8px; flex:1; }
.prod-card .bd .brand { font-size:12px; color:var(--muted); letter-spacing:.04em; }
.prod-card .bd .pname { font-size:16px; font-weight:700; color:var(--ink); line-height:1.4; }
.prod-card .bd .specs { display:flex; flex-wrap:wrap; gap:6px; font-size:12px; }
.prod-card .bd .specs span { background:#F0F3F7; border-radius:6px; padding:2px 9px; color:#33415C; }
.prod-card .bd .desc { font-size:12.5px; color:var(--muted); }
.prod-card .bd .status { font-size:12px; font-weight:600; }
.prod-card .bd .status.ok { color:var(--teal); } .prod-card .bd .status.warn { color:var(--amber); } .prod-card .bd .status.bad { color:var(--red); }
.prod-card .bd a { font-size:12.5px; color:var(--blue); text-decoration:none; word-break:break-all; }
.table { width:100%; border-collapse:collapse; font-size:13px; }
.table th, .table td { border-bottom:1px solid var(--line); padding:9px 10px; text-align:left; }
.table th { background:#F2F5F9; font-weight:600; color:var(--ink-2); }
.tag-k { display:inline-block; background:#E4F3F0; color:#1D6B5F; font-size:11px; font-weight:700; padding:2px 10px; border-radius:999px; }
.tag-f { display:inline-block; background:#FBE9E5; color:#A43C30; font-size:11px; font-weight:700; padding:2px 10px; border-radius:999px; }
.tag-t { display:inline-block; background:#FFF4E0; color:#9A6B12; font-size:11px; font-weight:700; padding:2px 10px; border-radius:999px; }
.tag-e { display:inline-block; background:#E8EEFB; color:#2D5BA8; font-size:11px; font-weight:700; padding:2px 10px; border-radius:999px; }
.quote { border-left:3px solid var(--amber); background:#FBF7EF; padding:12px 16px; margin:10px 0; font-size:13px; color:#4A5568; border-radius:0 8px 8px 0; }
.quote .src { color:var(--muted); font-size:11.5px; margin-top:6px; }
.callout { background:#F0F6F4; border:1px solid #CFE3DD; border-radius:12px; padding:14px 18px; font-size:13.5px; color:#24453F; margin:10px 0; }
.note-line { font-size:12px; color:var(--muted); }
.footer { border-top:1px solid var(--line); margin-top:60px; padding:26px 20px 40px; text-align:center; color:var(--muted); font-size:12.5px; }
@media (max-width:720px) {
  main { padding:22px 14px 60px; }
  .card .fig { height:330px; }
  .grid2 { grid-template-columns:1fr; }
  .prod-grid { grid-template-columns:1fr; }
}
</style>
</head>
<body>

<header class="hero">
  <div class="hero-inner">
    <div class="kicker">AMAZON US · SHOWER CURTAIN LINERS · 买家模拟选品实验</div>
    <h1>浴帘内衬 6 款竞品：2000 人次买家模拟实验报告</h1>
    <div class="sub">基于 Amazon 美国站真实在售 6 个 ASIN 的全字段明细构建货架与决策旅程，由 1000 名北美 Amazon 购物者画像（×2 实验）完成选品决策。回答：买家最终选谁、为什么选、为什么不选、什么因素真正影响下单、下一步做什么。</div>
    <div class="meta-chips">
      <span>货架选择实验 n=1,000</span><span>决策旅程实验 n=1,000</span><span>6 款真实在售 ASIN</span><span>Amazon 北美购物者画像</span><span>并发 30 · 0 错误</span>
    </div>
    <div class="kpi-row">
      <div class="kpi"><div class="lbl">货架最终首选</div><div class="v">C · 60.0%</div><div class="s">LQFMEHOT $7.09 / 4.6★ / 974 评</div></div>
      <div class="kpi"><div class="lbl">搜索后首点产品</div><div class="v">A · 65.5%</div><div class="s">AmazerBath $18.99 / 4.5★ / 4,156 评</div></div>
      <div class="kpi"><div class="lbl">全部未买后的兜底</div><div class="v">C · 72.5%</div><div class="s">性价比+最高评分是终极安全牌</div></div>
      <div class="kpi"><div class="lbl">只在第 1 页购买</div><div class="v">97.7%</div><div class="s">首页可见性 = 生死线</div></div>
      <div class="kpi"><div class="lbl">明确立即购买率</div><div class="v">0.7%</div><div class="s">99.3% 会先比较再决策</div></div>
    </div>
  </div>
</header>

<nav class="toc">
  <div class="toc-inner">
    <a href="#s0">核心结论</a><a href="#s1">这些买家是谁</a><a href="#s2">他们做了什么</a><a href="#s3">最后选了谁</a><a href="#s4">为什么选/不选</a><a href="#s5">对卖家的含义</a><a href="#s6">下一步做什么</a><a href="#s7">产品档案</a>
  </div>
</nav>

<main>

<!-- ============ 0 核心结论 ============ -->
<section id="s0">
<div class="hl-banner">
  <h2><span class="badge">核心结论</span> 一句话看懂这次测试</h2>
  <div class="hl-grid">
    <div class="hl-card"><div class="tag">最终赢家</div><div class="n">C 拿走 60% 首选</div><p>LQFMEHOT（$7.09 · 4.6★ · 974 评）以「全场最低价 + 最高评分」组合碾压货架：60.0% 首选、72.5% 兜底、71.8% 转投去向。真实类目排名仅 #124，说明真实排名并未如实反映用户偏好。</p><div class="ev">证据：货架选择份额 60.0%（n=1000）</div></div>
    <div class="hl-card"><div class="tag">点击 vs 购买分离</div><div class="n">点击靠「面」· 购买靠「里」</div><p>A（$18.99 / 4,156 评）吸引 65.5% 首点——视觉高级感 + 评论数信任信号；但 79.2% 因价格过高拒绝，最终仅 20.8% 份额。引流逻辑与转化逻辑完全不同。</p><div class="ev">证据：首点 A 65.5% vs 份额 A 20.8%</div></div>
    <div class="hl-card"><div class="tag">购买引擎</div><div class="n">价格 × 评分 × 千评</div><p>首要决策因素「价格/价值」52.2%、第二因素「评价」40.8%；Listing 要素重要性评价最高分是「评价内容」4.88/5。低评新品（&lt;50 评）82%+ 被直接淘汰。</p><div class="ev">证据：factor_most 52.2% / importance 4.88</div></div>
    <div class="hl-card"><div class="tag">生死线</div><div class="n">首页可见性 + 信息红线</div><p>97.7% 只在搜索结果第 1 页购买、79.0% 只看搜索第 1 页。无货 100% 一票否决、材质不明 97.3%、图片模糊 94.0%、无价格 91.6%。</p><div class="ev">证据：page_buy 97.7% / redline 100%</div></div>
    <div class="hl-card"><div class="tag">下一步</div><div class="n">先验证「评分+0.1」与徽章</div><p>64.9% 表示若竞品评分更高会切换；91.1% 自述受徽章（Best Seller 等）影响。建议 A/B 验证评分营销与徽章对转化率的真实拉动，同时守住信息完整红线。</p><div class="ev">证据：switch_trigger 64.9% / badge 91.1%</div></div>
  </div>
</div>
</section>

<!-- ============ 1 WHO ============ -->
<section id="s1">
  <div class="sec-head"><span class="sec-no">01</span><h2>这些买家是谁</h2></div>
  <div class="sec-desc">测试人群基于 Amazon 购物者画像生成，覆盖北美地区，模拟「搜索 → 浏览货架 → 进详情 → 决策」的完整购物者。</div>
  <div class="grid2">
    <div class="card"><h3>人群构成（画像级，非人口统计）</h3>
      <div class="table-wrap"><table class="table">
        <tr><th>维度</th><th>设定</th><th>说明</th></tr>
        <tr><td>画像来源</td><td>Amazon 购物者画像</td><td>非匿名随机，使用 Amazon 购物者行为画像</td></tr>
        <tr><td>地区</td><td>North America</td><td>符合美亚目标市场</td></tr>
        <tr><td>样本规模</td><td>1,000 × 2 实验</td><td>货架选择 1,000 人 + 决策旅程 1,000 人</td></tr>
        <tr><td>购买场景</td><td>搜索「浴帘/浴帘内衬」</td><td>有明确购买意图，进入货架浏览</td></tr>
      </table></div>
      <div class="note">当前数据未覆盖年龄、性别、家庭构成等人口统计字段；以下结论均基于购物行为场景而非人群标签。</div>
    </div>
    <div class="card"><h3>这是一群什么样的买家</h3>
      <p>综合各题行为特征，这批买家表现为：</p>
      <ul style="padding-left:18px;font-size:13.5px;margin:8px 0;">
        <li><b>价格敏感但信任驱动</b>：52.2% 把「价格/价值」列为第一决策因素，但 99.5% 点击后必看评价——省钱的前提是先确认靠谱。</li>
        <li><b>谨慎决策型</b>：只有 0.7% 会立即购买，99.3% 至少先比较再决定；99.7% 退出后会考虑其他产品。</li>
        <li><b>信息完整性强迫</b>：无货/无价/材质不明/图片模糊的 listing 会被 90%+ 一票否决，几乎不给第二眼机会。</li>
        <li><b>材质有明确门槛</b>：100% 要求 EVA（环保无味），96.9% 偏好半透明——材质陈述不达标直接出局。</li>
      </ul>
      <div class="note">行为特征来自问卷数据（factor_most / click_info / redline / material_pref 等），非外部推断。</div>
    </div>
  </div>
</section>

<!-- ============ 2 DID WHAT ============ -->
<section id="s2">
  <div class="sec-head"><span class="sec-no">02</span><h2>他们做了什么</h2></div>
  <div class="sec-desc">两个独立实验，同一批产品、同一人群设定，分别从「静态货架」和「动态旅程」两个视角观察购买决策。</div>
  <div class="grid2">
    <div class="card"><h3>实验一 · 货架选择（n=1,000）</h3>
      <p style="font-size:13.5px;margin-bottom:10px;">模拟买家在搜索结果货架上同时看到 6 款产品，回答 26 题：</p>
      <ul style="padding-left:18px;font-size:13.5px;margin:4px 0;">
        <li><b>选 1 款</b> + 说明理由</li>
        <li>每一款未选的，都给出<b>具体拒绝原因</b>（16 个候选原因多选）</li>
        <li>商品出现在<b>第几页</b>仍愿意浏览 / 购买</li>
        <li>8 项 Listing 要素重要性评分（1–5）</li>
        <li>红线清单（何种 Listing 问题直接放弃）、材质/透明度偏好、徽章效应、切换诱因、价格接受度、购买意向</li>
      </ul>
      <div class="note">观察口径：静态货架上的「第一选择」与拒绝理由。</div>
    </div>
    <div class="card"><h3>实验二 · 决策旅程（n=1,000）</h3>
      <p style="font-size:13.5px;margin-bottom:10px;">模拟买家在搜索后看到的完整决策链，8 题逐步推进：</p>
      <ul style="padding-left:18px;font-size:13.5px;margin:4px 0;">
        <li><b>第一眼最想点进哪个</b>（理由）</li>
        <li>点进后<b>最想查看什么信息</b>（多选）</li>
        <li>看完是否<b>购买 / 犹豫 / 放弃</b>（理由）</li>
        <li>退出后<b>是否考虑其他产品</b> → <b>考虑哪款</b>（理由）</li>
        <li>全部未买时的<b>兜底选择</b>（理由）</li>
        <li>搜索时愿意翻到第几页、整体决策因素</li>
      </ul>
      <div class="note">观察口径：从首点、信息偏好到最终兜底的完整决策链。</div>
    </div>
  </div>
  <div class="callout">两组实验共用同一产品货架（6 款真实 ASIN、真实价格/评分/评价数/库存状态/主图），保证两实验结论可交叉对照。</div>
</section>

<!-- ============ 3 CHOSE WHAT ============ -->
<section id="s3">
  <div class="sec-head"><span class="sec-no">03</span><h2>最后大家选了谁</h2></div>
  <div class="sec-desc">货架选择与决策旅程两个视角下的「最终选择」结果。百分点差异为描述性结果，未做统计显著性检验。</div>
  <div class="grid2">
    <div class="card"><h3>货架首选份额（n=1,000）</h3>
      <div class="fig sm" id="fig_share"></div>
      <div class="note">C 独占六成；A/B 瓜分近四成；E 仅 1.3%；D、F 无人选择。货架结果呈现「一超两强三淘汰」格局。</div>
    </div>
    <div class="card"><h3>真实排名 vs 模拟偏好（n=1,000）</h3>
      <div class="fig sm" id="fig_rank"></div>
      <div class="note">真实类目排名（#Shower Curtain Liners）来自 2026-09-17 采集：A#27 最靠前，C#124 靠后。模拟首选 C 却以 60% 断层第一——真实排名与用户偏好并不一致。</div>
    </div>
  </div>
  <div class="grid2">
    <div class="card"><h3>决策旅程 · 首点 vs 兜底（n=1,000）</h3>
      <div class="fig sm" id="fig_first_final"></div>
      <div class="note">首点 A 65.5%（视觉+评论信任），但经历完整决策后，兜底选择 C 72.5%。「第一眼赢家」和「最终赢家」不是同一款。</div>
    </div>
    <div class="card"><h3>购买决策分布（n=1,000）</h3>
      <div class="fig sm" id="fig_buy"></div>
      <div class="note">66.2% 倾向购买、22.7% 犹豫，但<b>明确立即购买仅 0.7%</b>；进一步询问中，明确表示会买的只有 6.7%——绝大多数人会「再看一个」再决定。</div>
    </div>
  </div>
</section>

<!-- ============ 4 WHY & WHAT MATTERS ============ -->
<section id="s4">
  <div class="sec-head"><span class="sec-no">04</span><h2>为什么选 / 为什么不选 · 用户真正关注什么</h2></div>
  <div class="sec-desc">原因分析区：①开放理由按主题归纳（词频为「提及次数」，不代表重要性排序）；②拒绝原因为 16 选多选，百分比 = 选中人数/1000。注意区分「被高频提及」与「有证据表明影响选择」。</div>

  <div class="sec-head" style="margin-top:26px;"><span class="sec-no">4.1</span><h3 style="font-size:18px;">为什么选 C：便宜 + 高分 + 千评，三重满足</h3></div>
  <div class="grid2">
    <div class="card"><h3>兜底 C 的理由主题（n=725）</h3>
      <div class="fig sm" id="fig_why_c"></div>
      <div class="note">C 的兜底理由中「材质安全」「评分」「磁吸配重」「价格价值」「评价数」全面高频——它是六款中唯一同时满足价格、评分、评论数、材质、功能的「全能安全牌」。</div>
    </div>
    <div class="card"><h3>首点 A 的理由主题（n=655）</h3>
      <div class="fig sm" id="fig_why_a"></div>
      <div class="note">首点 A 的理由中「外观」一骑绝尘（2,187 次提及），其次是磁吸配重与评价数——点击由「看起来高级 + 评价多」驱动，与最终购买理由（价格/评分）完全不同。</div>
    </div>
  </div>

  <div class="sec-head" style="margin-top:26px;"><span class="sec-no">4.2</span><h3 style="font-size:18px;">为什么不选：每款产品的拒绝原因</h3></div>
  <div class="sec-desc">六款产品各自排名前 4 的拒绝原因（多选，n=1000）。差异非常清晰：价格、外观、评价数、库存是四大淘汰闸门。</div>
  <div class="card"><div class="fig" id="fig_reject"></div>
    <div class="note">横轴 = 选中该原因的买家数（0–1000）。A 死于价格（792 人）、B 死于外观（669 人）、C 死于品牌陌生（360 人）、D/F 死于评价太少（982/967 人）、E 死于外观+库存告急。</div>
  </div>

  <div class="sec-head" style="margin-top:26px;"><span class="sec-no">4.3</span><h3 style="font-size:18px;">用户真正关注什么：四大证据面</h3></div>
  <div class="grid2">
    <div class="card"><h3>高关注 · 决策因素（第一 / 第二，n=1000）</h3>
      <div class="fig sm" id="fig_factor"></div>
      <div class="note">第一因素「价格/价值」52.2%，第二因素「评价」40.8%——价格是门槛，评价是背书，两者组合构成购买引擎。</div>
    </div>
    <div class="card"><h3>高关注 · Listing 要素重要性（1–5 分，n=1000）</h3>
      <div class="fig sm" id="fig_importance"></div>
      <div class="note">评价内容 4.88 最高、价格展示 4.55、主图 4.32；A+ 内容仅 1.99 垫底——预算优先投评价与价格表达，A+ 投入性价比最低。</div>
    </div>
    <div class="card"><h3>基础门槛 · Listing 红线（n=1000）</h3>
      <div class="fig sm" id="fig_redline"></div>
      <div class="note">「无货」100% 一票否决；材质不明 97.3%、图片模糊 94.0%、无价格 91.6%、无尺寸 89.6%。这些是及格线，不达标连被比较的资格都没有。</div>
    </div>
    <div class="card"><h3>页数容忍 · 浏览 vs 购买（n=1000）</h3>
      <div class="fig sm" id="fig_page"></div>
      <div class="note">95.4% 愿意翻到第 2 页浏览，但 97.7% 只在第 1 页购买——「浏览可以多翻，下单只看首页」。</div>
    </div>
  </div>

  <div class="sec-head" style="margin-top:26px;"><span class="sec-no">4.4</span><h3 style="font-size:18px;">切换与外部信号：什么会改变决策</h3></div>
  <div class="grid2">
    <div class="card"><h3>切换诱因（n=1000）</h3>
      <div class="fig sm" id="fig_switch"></div>
      <div class="note">64.9% 表示「竞品评分更高」会切换——评分小数点差距可能就是订单归属；「功能更好」15.5% 次之。</div>
    </div>
    <div class="card"><h3>徽章影响（n=1000）</h3>
      <div class="fig sm" id="fig_badge"></div>
      <div class="note">91.1% 自述徽章（Best Seller / Amazon's Choice 等）会「有点/明显」影响选择——自述层面徽章转化价值高，真实拉动建议 A/B 验证。</div>
    </div>
  </div>

  <div class="sec-head" style="margin-top:26px;"><span class="sec-no">4.5</span><h3 style="font-size:18px;">买家原话（定性证据）</h3></div>
  <div class="card">
    <div class="quote">The emerald-green semi-transparent liner with brass grommets and weighted stones looks higher-end than the others, and 4.5 stars with over 4,000 reviews makes it feel like the safest, most reliable option to click first.<div class="src">— 首点选 A 的买家（n=655 中的典型）：外观 + 4,000+ 评论 = 点击理由</div></div>
    <div class="quote">The LQFMEHOT liner stands out with the highest star rating (4.6) among the affordable options, plus a distinctive Art-Deco water-wave texture that reads as more considered than a plain liner. At $7.09 with 974 reviews, it looks like a strong value without the reliability risk of the very-low-review listings.<div class="src">— 首点选 C 的买家：最高评分 + 最低价 = 「无风险的划算」</div></div>
    <div class="quote">It has the best combination of rating (4.6) and review volume (974) among the affordable options, plus magnets and a tear-proof header for durability. At $7.09 the risk is minimal if it disappoints.<div class="src">— 兜底选 C 的买家：评分×评价数×低价的低风险组合</div></div>
    <div class="quote">The material and weighted bottom look good, but the page shows a delivery notice with no featured offer, so I'd add it to my cart and check other options before committing.<div class="src">— 看 A 详情页的买家：无 Featured Offer 触发「先加购再比较」，不直接下单</div></div>
    <div class="quote">Strong reviews and a solid material story make it a real contender, but the page showing no featured offer and only a delivery notice makes me want to check availability before committing.<div class="src">— 看 A 详情页的买家 2：配送不确定性是下单最大阻力</div></div>
    <div class="note">以上为英文原话直引（问卷原文），主题归纳见 4.1；原话属定性证据，不作群体结论的唯一依据。</div>
  </div>
</section>

<!-- ============ 5 WHAT ABOUT US ============ -->
<section id="s5">
  <div class="sec-head"><span class="sec-no">05</span><h2>对卖家的含义：谁赢在哪、输在哪</h2></div>
  <div class="sec-desc">本测试未预设「我方产品」，6 款均为美国站真实在售竞品；以下按卖家角色分别诊断（KEEP=已验证优势 / FIX=有较充分证据的问题 / TELL=有价值但未被感知 / TEST=出现信号但证据不足）。</div>
  <div class="grid2">
    <div class="card"><h3>C · LQFMEHOT（赢家）</h3>
      <p><span class="tag-k">KEEP</span> 价格卡位（$7.09 最低）+ 评分最高（4.6★）+ 千评组合已被验证是货架最优解：60% 首选、72.5% 兜底。</p>
      <p><span class="tag-f">FIX</span> 「品牌陌生」仍是其最大拒绝理由（360 人）——品牌信任是唯一短板，差评/信任背书可补。</p>
      <p><span class="tag-t">TELL</span> 它的外观（Art Deco 水立方）本身具备吸引力（首点 26.3% 第二），但未被充分感知为「好看」——主图可强化纹理质感表达。</p>
    </div>
    <div class="card"><h3>A · AmazerBath（高价高信任）</h3>
      <p><span class="tag-k">KEEP</span> 4,156 评论 + 4.5★ 的信任信号极强：吸引 65.5% 首点，20.8% 份额第二。</p>
      <p><span class="tag-f">FIX</span> 价格拒绝 792 人（79.2%）——$18.99 相对 $7 竞品无价值感支撑；无 Featured Offer 使详情页 26% 的人关注配送、直接降低下单意愿。</p>
      <p><span class="tag-e">TEST</span> 若补充「高质耐用/2合1省钱」价值叙事或变体降价，能否把点击优势转化为份额，值得验证。</p>
    </div>
    <div class="card"><h3>B · jssablo（性价比跟跑者）</h3>
      <p><span class="tag-k">KEEP</span> $7.19 + 1,872 评的性价比组合拿到 17.9% 份额，且 26.1% 转投去向为 B（第二选择者）。</p>
      <p><span class="tag-f">FIX</span> 外观拒绝 669 人（66.9%）是最大短板——3D 水波纹在「好看」维度输给 C 的 Art Deco 与 A 的高级感；「价格存疑」409 人表明低价+低知名品牌组合引发质量疑虑。</p>
    </div>
    <div class="card"><h3>E · Dependable（纯黑基础款）</h3>
      <p><span class="tag-f">FIX</span> 外观拒绝 925 人（92.5%）——纯黑无图案在浴帘场景被普遍视为单调；库存告急（596 人担忧）直接劝退。</p>
      <p><span class="tag-e">TEST</span> 当前样本仅 1.3% 选择，不足以下「黑色浴帘无市场」的结论（黑色在部分浴室风格中有需求），但方向不乐观。</p>
    </div>
    <div class="card"><h3>D · Laumyasof（新品 2 件装）</h3>
      <p><span class="tag-f">FIX</span> 评价仅 16 条：982 人（98.2%）因评价少拒绝——新品信任门槛极高；821 人质疑材质（2 件装 $9.99 引发「便宜没好货」联想）。</p>
      <p><span class="tag-k">KEEP</span> 无（当前样本中未建立任何可验证优势）。</p>
    </div>
    <div class="card"><h3>F · MuuXii（无货）</h3>
      <p><span class="tag-f">FIX</span> Currently unavailable + 无价格：897 人因库存/配送拒绝、967 人因评价少拒绝——0% 份额的直接原因。</p>
      <p><span class="note-line">注：无货产品在本实验中被 100% 一票否决（红线），其数据不构成有效市场信号。</span></p>
    </div>
  </div>
</section>

<!-- ============ 6 WHAT SHOULD WE DO ============ -->
<section id="s6">
  <div class="sec-head"><span class="sec-no">06</span><h2>下一步应该做什么</h2></div>
  <div class="sec-desc">建议按证据强度分级：ACT=证据较充分可直接行动；TEST=方向值得关注但需先验证；WATCH=弱信号，暂不投入。</div>
  <div class="card">
    <table class="table">
      <tr><th style="width:70px;">级别</th><th style="width:200px;">做什么</th><th>为什么 / 依据</th></tr>
      <tr><td><span class="tag-k">ACT</span></td><td><b>守住信息完整红线</b></td><td>无货 100%、材质不明 97.3%、图片模糊 94.0%、无价格 91.6% 一票否决——所有 listing 必须先通过这四条及格线，否则进不了比较圈。F 的 0% 与 A 的配送提示流失即为反例。</td></tr>
      <tr><td><span class="tag-k">ACT</span></td><td><b>验证「评分 +0.1」的订单价值</b></td><td>64.9% 表示评分更高的竞品会触发切换；C（4.6★）vs B（4.4★）同价位下份额 60% vs 17.9%。建议对 4.4→4.6 区间的评分营销（好评激励/售后跟进）做投入产出测算。</td></tr>
      <tr><td><span class="tag-t">TEST</span></td><td><b>A/B 验证徽章对转化的真实拉动</b></td><td>91.1% 自述受徽章影响，但自述≠真实转化。建议对主图/标题中的徽章元素做前后对照实验，量化拉动后再决定是否投入获徽章资源。</td></tr>
      <tr><td><span class="tag-t">TEST</span></td><td><b>新品信任破局测试</b></td><td>D（16 评）98.2% 因评价少被拒。建议验证「Vine 评论计划 + 低价跑量」能否在 30 天内把评价数拉到 200+ 从而进入比较圈，或先避开与 C/B 同价位正面对抗。</td></tr>
      <tr><td><span class="tag-t">TEST</span></td><td><b>A 的高价价值叙事测试</b></td><td>79.2% 因价格拒绝 A，但 65.5% 首点证明其吸引力。验证「2合1省一件」+「高级材质耐用叙事」能否让 $18.99 在高价带自成一档，而非与 $7 竞品正面比价。</td></tr>
      <tr><td><span class="tag-e">WATCH</span></td><td><b>A+ 内容投入暂缓</b></td><td>A+ 重要性 1.99/5 全场垫底——当前样本中用户不靠 A+ 做决策。除非后续测试证明其影响，否则预算优先投价格表达、主图清晰度与评价积累。</td></tr>
    </table>
    <div class="note">注：「A/B 验证」「测试」类建议基于当前样本中的信号强度分级，均需后续实验确认；当前数据不足以支持因果判断（如「改价格一定提升转化」）。</div>
  </div>
</section>

<!-- ============ 7 产品档案 ============ -->
<section id="s7">
  <div class="sec-head"><span class="sec-no">07</span><h2>6 款产品档案</h2></div>
  <div class="sec-desc">2026-09-17 采集自 Amazon 美国站；价格/评分/评价数/排名/状态均为页面实时值。点击链接可直接跳转商品页。</div>
  <div class="prod-grid" id="prod_grid"></div>
</section>

</main>

<div class="footer">Amazon 美国站 · 浴帘内衬 6 款竞品 · 买家模拟选品实验报告（2000 人次）<br>
货架选择实验 n=1,000（0 错误） · 决策旅程实验 n=1,000（0 错误） · 聚合时间 2026-09-17 · 本报告所有数据均可追溯至原始答卷</div>

<script>
/* __ECHARTS__ */
</script>
<script>
const DATA = __DATA__;
const RANK_TRUTH = __RANK__;

const PALETTE = ["#E8A33D", "#2E9E8F", "#3B6FB5", "#C24B3F", "#8A6FB0", "#7A8CA8"];
const CODES = ["A","B","C","D","E","F"];
const NAMES = {A:"A · AmazerBath 祖母绿", B:"B · jssablo 蓝水波纹", C:"C · LQFMEHOT 水立方", D:"D · Laumyasof 2件装", E:"E · Dependable 纯黑", F:"F · MuuXii 透明波点"};
const SHORT = {A:"A 祖母绿", B:"B 蓝波纹", C:"C 水立方", D:"D 鹅卵石2件", E:"E 纯黑", F:"F 透明波点"};
const REJ_CN = {price_too_high:"价格过高", look:"外观不满意", availability:"库存/配送", transparency:"透明度不合适", brand:"品牌陌生", material:"材质存疑", pack:"2件装不适用", few_reviews:"评价数太少", price_suspicious:"低价存疑", rating:"评分不足", review_concern:"评论内容顾虑", size:"尺寸不符", info_incomplete:"信息不全", missing_magnet:"无磁吸"};

function fig(id){ return document.getElementById(id); }

/* 3.1 货架首选份额 */
(function(){
  const c = fig("fig_share");
  if(!c) return;
  const data = CODES.map(k => ({name: SHORT[k], value: DATA.choice.share[k] || 0, itemStyle:{color: k==="C" ? PALETTE[0] : "#9FB0C8"}}));
  const chart = echarts.init(c);
  chart.setOption({
    tooltip:{trigger:"item", triggerOn:"mousemove|click", renderMode:"richText", confine:true, formatter:function(p){ return p.name + "：" + p.value + "%（" + Math.round(p.value/100*1000) + " 人）"; }},
    legend:{bottom:0, textStyle:{fontSize:12}},
    grid:{left:10, right:30, top:8, bottom:44, containLabel:true},
    xAxis:{type:"value", max:70, axisLabel:{formatter:"{value}%", fontSize:12}},
    yAxis:{type:"category", data:CODES.map(k=>SHORT[k]), inverse:true, axisLabel:{fontSize:12}},
    series:[{type:"bar", data:data, barWidth:26, label:{show:true, position:"right", formatter:function(p){return p.value+"%";}, fontSize:12, fontWeight:"bold", color:"#33415C"}}]
  });
})();

/* 3.2 真实排名 vs 模拟份额 */
(function(){
  const c = fig("fig_rank");
  if(!c) return;
  const codes = ["A","B","C","D","E","F"];
  const chart = echarts.init(c);
  chart.setOption({
    tooltip:{trigger:"axis", triggerOn:"mousemove|click", renderMode:"richText", confine:true, formatter:function(ps){
      const i = ps[0].dataIndex; const k = codes[i];
      return SHORT[k] + "<br/>真实类目排名：#" + RANK_TRUTH[k] + "（越小越靠前）<br/>模拟首选份额：" + (DATA.choice.share[k]||0) + "%";
    }},
    legend:{data:["真实类目排名（越小越靠前）","模拟首选份额 %"], bottom:0, textStyle:{fontSize:12}},
    grid:{left:10, right:30, top:14, bottom:44, containLabel:true},
    xAxis:{type:"category", data:codes.map(k=>SHORT[k]), axisLabel:{fontSize:12}},
    yAxis:[
      {type:"value", name:"真实排名", nameTextStyle:{fontSize:11}, inverse:true, min:0, max:900, axisLabel:{fontSize:11, formatter:function(v){ return "#" + v; }}},
      {type:"value", name:"模拟份额%", nameTextStyle:{fontSize:11}, max:70, axisLabel:{fontSize:11, formatter:"{value}%"}}
    ],
    series:[
      {name:"真实类目排名（越小越靠前）", type:"bar", data:codes.map(k=>RANK_TRUTH[k]), yAxisIndex:0, barWidth:22, itemStyle:{color:"#9FB0C8"}, label:{show:true, position:"top", formatter:function(p){return "#"+p.value;}, fontSize:11, color:"#64748B"}},
      {name:"模拟首选份额 %", type:"bar", data:codes.map(k=>DATA.choice.share[k]||0), yAxisIndex:1, barWidth:22, itemStyle:{color:function(p){return p.dataIndex===2 ? PALETTE[0] : "#3B6FB5";}}, label:{show:true, position:"top", formatter:function(p){return p.value+"%";}, fontSize:11, fontWeight:"bold", color:"#33415C"}}
    ]
  });
})();

/* 3.3 首点 vs 兜底 */
(function(){
  const c = fig("fig_first_final");
  if(!c) return;
  const chart = echarts.init(c);
  chart.setOption({
    tooltip:{trigger:"axis", triggerOn:"mousemove|click", renderMode:"richText", confine:true},
    legend:{data:["首点（第一眼想点进）","兜底（全没买最终会买）"], bottom:0, textStyle:{fontSize:12}},
    grid:{left:10, right:20, top:14, bottom:44, containLabel:true},
    xAxis:{type:"category", data:["A","B","C"].map(k=>SHORT[k]), axisLabel:{fontSize:12}},
    yAxis:{type:"value", max:80, axisLabel:{formatter:"{value}%", fontSize:12}},
    series:[
      {name:"首点（第一眼想点进）", type:"bar", data:["A","B","C"].map(k=>DATA.journey.first_click[k]), barWidth:26, itemStyle:{color:"#3B6FB5"}, label:{show:true, position:"top", formatter:function(p){return p.value+"%";}, fontSize:12, fontWeight:"bold", color:"#33415C"}},
      {name:"兜底（全没买最终会买）", type:"bar", data:["A","B","C"].map(k=>DATA.journey.fallback[k]), barWidth:26, itemStyle:{color:"#E8A33D"}, label:{show:true, position:"top", formatter:function(p){return p.value+"%";}, fontSize:12, fontWeight:"bold", color:"#33415C"}}
    ]
  });
})();

/* 3.4 购买决策分布 */
(function(){
  const c = fig("fig_buy");
  if(!c) return;
  const chart = echarts.init(c);
  const raw = DATA.journey.buy_decision;
  const labels = {likely_buy:"倾向购买", undecided:"犹豫不决", not_buy:"不购买", buy_now:"立即购买"};
  const cols = {likely_buy:"#2E9E8F", undecided:"#E8A33D", not_buy:"#C24B3F", buy_now:"#16233B"};
  const data = Object.keys(raw).map(k=>({name:labels[k], value:raw[k], itemStyle:{color:cols[k]}}));
  chart.setOption({
    tooltip:{trigger:"item", triggerOn:"mousemove|click", renderMode:"richText", confine:true, formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
    legend:{bottom:0, textStyle:{fontSize:12}},
    series:[{type:"pie", radius:["38%","66%"], center:["50%","46%"], data:data, label:{fontSize:12, formatter:"{b} {d}%"}, labelLine:{length:14, length2:8}}]
  });
})();

/* 4.1 兜底 C 理由 */
(function(){
  const c = fig("fig_why_c");
  if(!c) return;
  const d = DATA.reasons.fallbackC;
  const chart = echarts.init(c);
  chart.setOption({
    tooltip:{trigger:"axis", triggerOn:"mousemove|click", renderMode:"richText", confine:true, formatter:function(ps){const p=ps[0]; return p.name+"：提及 "+p.value+" 次（n=725）";}},
    grid:{left:10, right:40, top:10, bottom:20, containLabel:true},
    xAxis:{type:"value", axisLabel:{fontSize:12}},
    yAxis:{type:"category", inverse:true, data:Object.keys(d), axisLabel:{fontSize:12}},
    series:[{type:"bar", data:Object.values(d), barWidth:22, itemStyle:{color:"#2E9E8F"}, label:{show:true, position:"right", fontSize:12, fontWeight:"bold", color:"#33415C"}}]
  });
})();

/* 4.1 首点 A 理由 */
(function(){
  const c = fig("fig_why_a");
  if(!c) return;
  const d = DATA.reasons.clickA;
  const chart = echarts.init(c);
  chart.setOption({
    tooltip:{trigger:"axis", triggerOn:"mousemove|click", renderMode:"richText", confine:true, formatter:function(ps){const p=ps[0]; return p.name+"：提及 "+p.value+" 次（n=655）";}},
    grid:{left:10, right:40, top:10, bottom:20, containLabel:true},
    xAxis:{type:"value", axisLabel:{fontSize:12}},
    yAxis:{type:"category", inverse:true, data:Object.keys(d), axisLabel:{fontSize:12}},
    series:[{type:"bar", data:Object.values(d), barWidth:22, itemStyle:{color:"#3B6FB5"}, label:{show:true, position:"right", fontSize:12, fontWeight:"bold", color:"#33415C"}}]
  });
})();

/* 4.2 每款拒绝原因 Top4 */
(function(){
  const c = fig("fig_reject");
  if(!c) return;
  const codes = ["A","B","C","D","E","F"];
  const names = {A:"A 祖母绿（$18.99）", B:"B 蓝波纹（$7.19）", C:"C 水立方（$7.09）", D:"D 鹅卵石2件（$9.99）", E:"E 纯黑（$9.99）", F:"F 透明波点（无货）"};
  const chart = echarts.init(c);
  const series = [];
  codes.forEach((k, idx) => {
    series.push({name: names[k], type:"bar", stack:"total", data: CODES.map(j => { const t = DATA.choice.reject_top[k]; const f = t.find(x=>x[0]===j); return null; }).map(()=>0)});
  });
  // 用每款自己的原因列表（自定义 x 轴：原因名）
  const reasonKeys = [];
  const seen = {};
  codes.forEach(k => {
    (DATA.choice.reject_top[k]||[]).forEach(([rk, rv]) => {
      const cn = REJ_CN[rk] || rk;
      if(!seen[cn]) { seen[cn] = true; reasonKeys.push(cn); }
    });
  });
  const series2 = codes.map(k => ({
    name: names[k],
    type: "bar",
    stack: "total",
    data: reasonKeys.map(cn => {
      const f = (DATA.choice.reject_top[k]||[]).find(([rk])=> (REJ_CN[rk]||rk) === cn);
      return f ? f[1] : 0;
    }),
    itemStyle: { color: PALETTE[codes.indexOf(k)] }
  }));
  chart.setOption({
    tooltip:{trigger:"axis", triggerOn:"mousemove|click", renderMode:"richText", confine:true, formatter:function(ps){
      const cn = ps[0].axisValue;
      let html = cn + "<br/>";
      ps.forEach(p=>{ if(p.value>0) html += p.marker + p.seriesName + "：" + p.value + " 人<br/>"; });
      return html;
    }},
    legend:{type:"scroll", bottom:0, textStyle:{fontSize:11}},
    grid:{left:10, right:20, top:14, bottom:52, containLabel:true},
    xAxis:{type:"category", data:reasonKeys, axisLabel:{fontSize:11.5, interval:0}},
    yAxis:{type:"value", max:1000, axisLabel:{fontSize:12}},
    series: series2
  });
})();

/* 4.3 决策因素 */
(function(){
  const c = fig("fig_factor");
  if(!c) return;
  const order = ["price_value","reviews","rating","material","magnet","appearance"];
  const cn = {price_value:"价格/价值", reviews:"评价内容", rating:"评分", material:"材质", magnet:"磁吸配重", appearance:"外观"};
  const chart = echarts.init(c);
  chart.setOption({
    tooltip:{trigger:"axis", triggerOn:"mousemove|click", renderMode:"richText", confine:true, formatter:function(ps){
      let h = ps[0].name + "<br/>";
      ps.forEach(p=>{ h += p.marker + p.seriesName + "：" + p.value + "%<br/>"; });
      return h;
    }},
    legend:{data:["第一决策因素","第二决策因素"], bottom:0, textStyle:{fontSize:12}},
    grid:{left:10, right:20, top:14, bottom:44, containLabel:true},
    xAxis:{type:"category", data:order.map(k=>cn[k]), axisLabel:{fontSize:11.5}},
    yAxis:{type:"value", max:60, axisLabel:{formatter:"{value}%", fontSize:12}},
    series:[
      {name:"第一决策因素", type:"bar", data:order.map(k=>DATA.choice.factor_most[k]||0), barWidth:24, itemStyle:{color:"#E8A33D"}, label:{show:true, position:"top", formatter:function(p){return p.value+"%";}, fontSize:11, color:"#33415C"}},
      {name:"第二决策因素", type:"bar", data:order.map(k=>DATA.choice.factor_second[k]||0), barWidth:24, itemStyle:{color:"#2E9E8F"}, label:{show:true, position:"top", formatter:function(p){return p.value+"%";}, fontSize:11, color:"#33415C"}}
    ]
  });
})();

/* 4.3 Listing 要素重要性 */
(function(){
  const c = fig("fig_importance");
  if(!c) return;
  const cn = {title:"标题", image:"主图", bullets:"五点描述", aplus:"A+ 内容", attr:"属性表", price:"价格展示", reviews:"评价内容", trust:"信任标识"};
  const d = DATA.choice.importance;
  const keys = Object.keys(d).sort((a,b)=>d[b]-d[a]);
  const chart = echarts.init(c);
  chart.setOption({
    tooltip:{trigger:"axis", triggerOn:"mousemove|click", renderMode:"richText", confine:true, formatter:function(ps){const p=ps[0]; return p.name+"：均分 "+p.value+" / 5";}},
    grid:{left:10, right:46, top:10, bottom:20, containLabel:true},
    xAxis:{type:"value", max:5, axisLabel:{fontSize:12}},
    yAxis:{type:"category", inverse:true, data:keys.map(k=>cn[k]), axisLabel:{fontSize:12}},
    series:[{type:"bar", data:keys.map(k=>({value:d[k], itemStyle:{color: k==="aplus" ? "#C6CFDC" : (k==="reviews" ? "#E8A33D" : "#3B6FB5")}})), barWidth:22, label:{show:true, position:"right", formatter:function(p){return p.value.toFixed(2);}, fontSize:12, fontWeight:"bold", color:"#33415C"}}]
  });
})();

/* 4.3 红线 */
(function(){
  const c = fig("fig_redline");
  if(!c) return;
  const cn = {unavailable:"无货", material_unclear:"材质不明", blur_image:"图片模糊", no_price:"无价格", no_size:"无尺寸", low_rating:"评分低", few_reviews:"评价太少", no_bullets:"无五点描述", brand_unfamiliar:"品牌陌生", none:"无"};
  const d = DATA.choice.redline;
  const keys = Object.keys(d).filter(k=>d[k]>0).sort((a,b)=>d[b]-d[a]);
  const chart = echarts.init(c);
  chart.setOption({
    tooltip:{trigger:"axis", triggerOn:"mousemove|click", renderMode:"richText", confine:true, formatter:function(ps){const p=ps[0]; return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
    grid:{left:10, right:46, top:10, bottom:20, containLabel:true},
    xAxis:{type:"value", max:100, axisLabel:{formatter:"{value}%", fontSize:12}},
    yAxis:{type:"category", inverse:true, data:keys.map(k=>cn[k]||k), axisLabel:{fontSize:12}},
    series:[{type:"bar", data:keys.map(k=>({value:d[k], itemStyle:{color: d[k]>=90 ? "#C24B3F" : (d[k]>=60 ? "#E8A33D" : "#9FB0C8")}})), barWidth:22, label:{show:true, position:"right", formatter:function(p){return p.value+"%";}, fontSize:11.5, color:"#33415C"}}]
  });
})();

/* 4.3 页数容忍 */
(function(){
  const c = fig("fig_page");
  if(!c) return;
  const chart = echarts.init(c);
  const browse = DATA.choice.page_browse, buy = DATA.choice.page_buy;
  const keys = Object.keys(browse);
  chart.setOption({
    tooltip:{trigger:"axis", triggerOn:"mousemove|click", renderMode:"richText", confine:true, formatter:function(ps){
      let h = ps[0].name + "<br/>";
      ps.forEach(p=>{ h += p.marker + p.seriesName + "：" + p.value + "%<br/>"; });
      return h;
    }},
    legend:{data:["愿意浏览","愿意购买"], bottom:0, textStyle:{fontSize:12}},
    grid:{left:10, right:20, top:14, bottom:44, containLabel:true},
    xAxis:{type:"category", data:keys.map(k=>k.replace("page","第")+"页"), axisLabel:{fontSize:12}},
    yAxis:{type:"value", max:100, axisLabel:{formatter:"{value}%", fontSize:12}},
    series:[
      {name:"愿意浏览", type:"bar", data:keys.map(k=>browse[k]), barWidth:26, itemStyle:{color:"#9FB0C8"}, label:{show:true, position:"top", formatter:function(p){return p.value+"%";}, fontSize:11, color:"#33415C"}},
      {name:"愿意购买", type:"bar", data:keys.map(k=>buy[k]||0), barWidth:26, itemStyle:{color:"#E8A33D"}, label:{show:true, position:"top", formatter:function(p){return p.value+"%";}, fontSize:11, color:"#33415C"}}
    ]
  });
})();

/* 4.4 切换诱因 */
(function(){
  const c = fig("fig_switch");
  if(!c) return;
  const cn = {better_rating:"竞品评分更高", better_function:"功能更好", lower_price:"价格更低", better_value:"性价比更高", nothing:"什么都不换", better_look:"更好看"};
  const d = DATA.choice.switch_trigger;
  const chart = echarts.init(c);
  chart.setOption({
    tooltip:{trigger:"item", triggerOn:"mousemove|click", renderMode:"richText", confine:true, formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
    legend:{bottom:0, textStyle:{fontSize:11}},
    series:[{type:"pie", radius:["36%","62%"], center:["50%","44%"], data:Object.keys(d).map(k=>({name:cn[k]||k, value:d[k]})), label:{fontSize:11, formatter:"{b} {d}%"}, labelLine:{length:12, length2:6}}]
  });
})();

/* 4.4 徽章影响 */
(function(){
  const c = fig("fig_badge");
  if(!c) return;
  const cn = {yes_somewhat:"有影响（部分）", yes_strongly:"影响很大", neutral:"中立", unlikely:"不太影响", no_effect:"完全不影响"};
  const d = DATA.choice.badge_effect;
  const order = ["yes_somewhat","yes_strongly","neutral","unlikely","no_effect"];
  const chart = echarts.init(c);
  chart.setOption({
    tooltip:{trigger:"item", triggerOn:"mousemove|click", renderMode:"richText", confine:true, formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
    legend:{bottom:0, textStyle:{fontSize:11}},
    series:[{type:"pie", radius:["36%","62%"], center:["50%","44%"], data:order.map(k=>({name:cn[k], value:d[k]||0})), label:{fontSize:11, formatter:"{b} {d}%"}, labelLine:{length:12, length6:6}}]
  });
})();

/* 产品卡片 */
(function(){
  const grid = document.getElementById("prod_grid");
  if(!grid) return;
  DATA.products.forEach(p => {
    const el = document.createElement("div");
    el.className = "prod-card";
    const st = p.status.indexOf("unavailable")>=0 || p.status.indexOf("剩")>=0 ? "warn" : (p.status.indexOf("现货")>=0 ? "ok" : "warn");
    const stCls = st==="ok" ? "ok" : "warn";
    el.innerHTML = `
      <div class="ph">
        <img src="${p.img_b64}" alt="${p.brand} ${p.name}">
        <span class="rank-badge">类目 #${p.rank.replace("#","")}</span>
        <span class="share-badge">首选 ${p.share}%</span>
      </div>
      <div class="bd">
        <div class="brand">${p.brand} · ${p.asin}</div>
        <div class="pname">${p.name}</div>
        <div class="specs"><span>${p.price}</span><span>${p.rating}</span><span>${p.reviews} 评</span><span>类目排名 ${p.rank}</span></div>
        <div class="desc">${p.desc}</div>
        <div class="status ${stCls}">${p.status}</div>
        <a href="${p.link}" target="_blank" rel="noopener">${p.link}</a>
      </div>`;
    grid.appendChild(el);
  });
})();

/* 简单滚动高亮 TOC */
(function(){
  const links = document.querySelectorAll("nav.toc a");
  const map = {};
  links.forEach(a=>{ map[a.getAttribute("href").slice(1)] = a; });
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if(e.isIntersecting){
        links.forEach(a=>a.classList.remove("active"));
        const a = map[e.target.id];
        if(a) a.classList.add("active");
      }
    });
  }, {rootMargin:"-30% 0px -60% 0px"});
  ["s0","s1","s2","s3","s4","s5","s6","s7"].forEach(id=>{ const el=document.getElementById(id); if(el) obs.observe(el); });
})();
</script>
</body>
</html>
"""

HTML = HTML.replace("/* __ECHARTS__ */", ECHARTS_JS)
HTML = HTML.replace("__DATA__", DATA_JSON)
HTML = HTML.replace("__RANK__", RANK_JSON)

with open(OUT, "w") as f:
    f.write(HTML)
print("written:", OUT, len(HTML) // 1024, "KB")
