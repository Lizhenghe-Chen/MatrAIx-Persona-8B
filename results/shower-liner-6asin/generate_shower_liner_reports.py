#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成两份独立报告：
1) shower_liner_choice_report.html   —— 实验一·货架选择（n=1000）
2) shower_liner_journey_report.html  —— 实验二·决策旅程（n=1000）
共用视觉体系（深蓝+琥珀）与产品档案；各自聚焦本实验的数据与结论。
"""
import base64, json, os, re

ROOT = "/Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B"
SUMMARY = os.path.join(ROOT, "results/shower-liner-6asin-experiment/shower_liner_summary.json")
ASSETS = os.path.join(ROOT, "results/shower-liner-6asin/assets")
OUT_DIR = os.path.join(ROOT, "results/shower-liner-6asin-experiment")
TOILET_REPORT = os.path.join(ROOT, "results/toilet-brush-top30-experiment/toilet_top30_experiment_report.html")

s = json.load(open(SUMMARY))

# ---------- 产品档案 ----------
products = [
    dict(code="A", asin="B0CGLZ56JC", brand="AmazerBath", name="祖母绿·半透明 EVA 2 合 1",
         price="$18.99", rating="4.5★", reviews="4,156", rank="#27",
         desc="100% EVA 半透明祖母绿重型浴帘内衬，黄铜扣眼 12 个 + 3 个配重石，72x72，奢华 2 合 1。页面无 featured offer（仅配送提示）。",
         status="配送受限 · 无 Featured Offer", link="https://www.amazon.com/dp/B0CGLZ56JC",
         img="B0CGLZ56JC.jpg", share=20.8,
         reject=[["price_too_high",792],["look",238],["availability",237],["transparency",180]]),
    dict(code="B", asin="B0C9MCD5WL", brand="jssablo", name="蓝·3D 水波纹",
         price="$7.19", rating="4.4★", reviews="1,872", rank="#41",
         desc="100% 防水 EVA 蓝色 3D 水波纹，底部 3 个重型磁铁 + 12 个防锈扣眼，72x72。现货在售。",
         status="In Stock 现货", link="https://www.amazon.com/dp/B0C9MCD5WL",
         img="B0C9MCD5WL.jpg", share=17.9,
         reject=[["look",669],["price_suspicious",409],["brand",250],["rating",192]]),
    dict(code="C", asin="B0C2GTPSFR", brand="LQFMEHOT", name="蓝·3D 水立方（Art Deco）",
         price="$7.09", rating="4.6★", reviews="974", rank="#124",
         desc="EVA 蓝色 3D 水立方纹理（Art Deco 风），12 个防锈金属扣眼 + 配重磁铁，72x72。6 款中评分最高、价格最低。现货在售。",
         status="In Stock 现货", link="https://www.amazon.com/dp/B0C2GTPSFR",
         img="B0C2GTPSFR.jpg", share=60.0,
         reject=[["brand",360],["price_suspicious",257],["look",210],["few_reviews",186]]),
    dict(code="D", asin="B0GYWQQ2K3", brand="Laumyasof", name="绿·3D 鹅卵石 2 件装",
         price="$9.99", rating="4.4★", reviews="16", rank="#129",
         desc="2 件装绿色 3D 鹅卵石 EVA 浴帘内衬，72x72，防锈金属扣眼 + 配重磁铁。新品，评价极少。",
         status="In Stock 现货 · 新品", link="https://www.amazon.com/dp/B0GYWQQ2K3",
         img="B0GYWQQ2K3.jpg", share=0.0,
         reject=[["few_reviews",982],["material",821],["pack",455],["look",86]]),
    dict(code="E", asin="B0D212C4XS", brand="Dependable", name="纯黑·基础款",
         price="$9.99", rating="4.3★", reviews="116", rank="#203",
         desc="EVA 纯黑浴帘内衬，72x72，3 个磁铁 + 金属扣眼。无图案基础款。库存紧张。",
         status="仅剩 10 件", link="https://www.amazon.com/dp/B0D212C4XS",
         img="B0D212C4XS.jpg", share=1.3,
         reject=[["look",925],["availability",596],["few_reviews",466],["rating",207]]),
    dict(code="F", asin="B0FSRN9YTK", brand="MuuXii", name="透明波点",
         price="无价", rating="4.4★", reviews="10", rank="#856",
         desc="EVA 透明波点（含挂钩）71x71，12 个防锈扣眼 + 3 个配重磁铁。Currently unavailable，页面无价格。",
         status="Currently unavailable", link="https://www.amazon.com/dp/B0FSRN9YTK",
         img="B0FSRN9YTK.jpg", share=0.0,
         reject=[["few_reviews",967],["availability",897],["size",310],["transparency",45]]),
]

def b64(path):
    with open(path, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()

for p in products:
    p["img_b64"] = b64(os.path.join(ASSETS, p["img"]))

toilet_html = open(TOILET_REPORT).read()
m = re.search(r"<script>(\s*/\*.*?Licensed to the Apache.*?)</script>", toilet_html, re.S)
ECHARTS_JS = m.group(1) if m else ""

c = s["choice"]; j = s["journey"]
RANK_TRUTH = {"A": 27, "B": 41, "C": 124, "D": 129, "E": 203, "F": 856}

DATA = {
    "products": products, "rank_truth": RANK_TRUTH,
    "choice": {
        "share": c["share_pct"], "reject_top": c["reject_top_reasons"],
        "page_browse": c["page_browse_pct"], "page_buy": c["page_buy_pct"],
        "factor_most": c["factor_most_pct"], "factor_second": c["factor_second_pct"],
        "importance": c["importance_mean_1to5"], "redline": c["redline_pct"],
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
DATA_JSON = json.dumps(DATA, ensure_ascii=False)

CSS = r"""
:root { --ink:#16233B; --ink-2:#22345A; --paper:#F7F8FA; --card:#FFFFFF; --line:#E3E7EE; --text:#22303F; --muted:#64748B; --amber:#E8A33D; --teal:#2E9E8F; --red:#C24B3F; --blue:#3B6FB5; }
* { box-sizing:border-box; }
body { margin:0; font-family:"Noto Sans SC","PingFang SC","Microsoft YaHei",system-ui,sans-serif; background:var(--paper); color:var(--text); line-height:1.7; }
h1,h2,h3,h4 { font-family:"Noto Serif SC","Songti SC","STSong",Georgia,serif; margin:0; }
header.hero { background:var(--ink); color:#fff; padding:56px 24px 48px; position:relative; overflow:hidden; }
header.hero::before { content:""; position:absolute; right:-120px; top:-120px; width:440px; height:440px; border-radius:50%; background:radial-gradient(circle, rgba(232,163,61,.30), transparent 65%); }
.hero-inner { max-width:1180px; margin:0 auto; position:relative; z-index:1; }
.hero .kicker { font-size:13px; letter-spacing:.14em; color:var(--amber); font-weight:600; }
.hero h1 { font-size:clamp(23px,3.1vw,36px); font-weight:900; line-height:1.3; margin:12px 0 10px; max-width:980px; }
.hero .sub { font-size:15px; color:#C8D3E3; max-width:840px; margin-bottom:20px; }
.meta-chips { display:flex; flex-wrap:wrap; gap:9px; }
.meta-chips span { border:1px solid rgba(255,255,255,.22); border-radius:999px; padding:5px 13px; font-size:12.5px; color:#E6ECF5; background:rgba(255,255,255,.06); }
.kpi-row { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin-top:24px; }
.kpi { background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.14); border-radius:12px; padding:13px 15px; }
.kpi .lbl { font-size:12px; color:#B9C6DA; }
.kpi .v { font-family:"Noto Serif SC",serif; font-size:22px; font-weight:700; color:var(--amber); margin-top:2px; }
.kpi .s { font-size:11.5px; color:#8FA0BC; margin-top:2px; }
nav.toc { position:sticky; top:0; z-index:50; background:rgba(255,255,255,.95); backdrop-filter:blur(8px); border-bottom:1px solid var(--line); }
.toc-inner { max-width:1180px; margin:0 auto; display:flex; gap:2px; overflow-x:auto; padding:0 8px; }
nav.toc a { padding:13px 13px; font-size:13px; color:var(--muted); text-decoration:none; white-space:nowrap; border-bottom:2px solid transparent; }
nav.toc a:hover { color:var(--ink); border-bottom-color:var(--amber); }
main { max-width:1180px; margin:0 auto; padding:32px 20px 70px; }
section { margin-top:44px; }
.sec-head { display:flex; align-items:baseline; gap:12px; margin-bottom:6px; }
.sec-no { font-family:"Noto Serif SC",serif; font-size:14px; font-weight:700; color:var(--amber); letter-spacing:.06em; }
.sec-head h2 { font-size:22px; font-weight:800; color:var(--ink); }
.sec-desc { color:var(--muted); font-size:13.5px; margin-bottom:20px; max-width:920px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px 20px; margin-bottom:16px; }
.card h3 { font-size:16px; color:var(--ink); margin-bottom:8px; }
.card .fig { width:100%; height:400px; }
.card .fig.sm { height:330px; }
.card .note { font-size:12.5px; color:var(--muted); margin-top:6px; }
.grid2 { display:grid; grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); gap:16px; }
.hl-banner { background:linear-gradient(120deg,#16233B 0%,#1D2E4F 55%,#26406B 100%); border:1px solid rgba(255,255,255,.10); border-radius:18px; padding:28px 28px 22px; margin:8px 0 4px; }
.hl-banner h2 { color:#fff; font-size:20px; display:flex; align-items:center; gap:10px; }
.hl-banner h2 .badge { font-size:11px; font-weight:600; color:var(--amber); border:1px solid rgba(232,163,61,.5); padding:3px 10px; border-radius:999px; letter-spacing:.08em; }
.hl-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(290px,1fr)); gap:12px; margin-top:16px; }
.hl-card { background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.12); border-radius:12px; padding:13px 14px 11px; }
.hl-card .n { font-family:"Noto Serif SC",serif; font-size:18px; font-weight:800; color:var(--amber); line-height:1.2; }
.hl-card .tag { display:inline-block; font-size:10px; color:var(--amber); border:1px solid rgba(232,163,61,.4); border-radius:4px; padding:1px 7px; margin:5px 0 4px; letter-spacing:.06em; }
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
.table th, .table td { border-bottom:1px solid var(--line); padding:9px 10px; text-align:left; vertical-align:top; }
.table th { background:#F2F5F9; font-weight:600; color:var(--ink-2); }
.tag-k { display:inline-block; background:#E4F3F0; color:#1D6B5F; font-size:11px; font-weight:700; padding:2px 10px; border-radius:999px; }
.tag-f { display:inline-block; background:#FBE9E5; color:#A43C30; font-size:11px; font-weight:700; padding:2px 10px; border-radius:999px; }
.tag-t { display:inline-block; background:#FFF4E0; color:#9A6B12; font-size:11px; font-weight:700; padding:2px 10px; border-radius:999px; }
.tag-e { display:inline-block; background:#E8EEFB; color:#2D5BA8; font-size:11px; font-weight:700; padding:2px 10px; border-radius:999px; }
.quote { border-left:3px solid var(--amber); background:#FBF7EF; padding:12px 16px; margin:10px 0; font-size:13px; color:#4A5568; border-radius:0 8px 8px 0; }
.quote .src { color:var(--muted); font-size:11.5px; margin-top:6px; }
.callout { background:#F0F6F4; border:1px solid #CFE3DD; border-radius:12px; padding:13px 17px; font-size:13.5px; color:#24453F; margin:10px 0; }
.note-line { font-size:12px; color:var(--muted); }
.footer { border-top:1px solid var(--line); margin-top:56px; padding:24px 20px 36px; text-align:center; color:var(--muted); font-size:12.5px; }
@media (max-width:720px) { main { padding:20px 13px 54px; } .card .fig { height:330px; } .grid2, .prod-grid { grid-template-columns:1fr; } }
"""

PROD_CARDS_JS = r"""
(function(){
  const grid = document.getElementById("prod_grid");
  if(!grid) return;
  DATA.products.forEach(p => {
    const el = document.createElement("div");
    el.className = "prod-card";
    const stCls = p.status.indexOf("unavailable")>=0 || p.status.indexOf("剩")>=0 ? "warn" : (p.status.indexOf("现货")>=0 ? "ok" : "warn");
    el.innerHTML = `
      <div class="ph"><img src="${p.img_b64}" alt="${p.brand} ${p.name}">
        <span class="rank-badge">类目 ${p.rank}</span><span class="share-badge">首选 ${p.share}%</span></div>
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
"""

TOC = r"""
<nav class="toc"><div class="toc-inner"><a href="#s0">核心结论</a><a href="#s1">这些买家是谁</a><a href="#s2">他们做了什么</a><a href="#s3">最后选了谁</a><a href="#s4">为什么选/不选</a><a href="#s5">对卖家的含义</a><a href="#s6">下一步做什么</a><a href="#s7">产品档案</a></div></nav>
"""

WHO_SEC = r"""
<section id="s1">
  <div class="sec-head"><span class="sec-no">01</span><h2>这些买家是谁</h2></div>
  <div class="sec-desc">测试人群基于 Amazon 购物者画像生成，覆盖北美地区，模拟「搜索 → 浏览货架 → 进详情 → 决策」的完整购物者。</div>
  <div class="grid2">
    <div class="card"><h3>人群构成（画像级，非人口统计）</h3>
      <table class="table">
        <tr><th>维度</th><th>设定</th><th>说明</th></tr>
        <tr><td>画像来源</td><td>Amazon 购物者画像</td><td>使用 Amazon 购物者行为画像</td></tr>
        <tr><td>地区</td><td>North America</td><td>符合美亚目标市场</td></tr>
        <tr><td>样本规模</td><td>1,000 人</td><td>本实验 1,000 人（另有 1,000 人参与决策旅程实验）</td></tr>
        <tr><td>购买场景</td><td>搜索「浴帘/浴帘内衬」</td><td>有明确购买意图，进入货架浏览</td></tr>
      </table>
      <div class="note">当前数据未覆盖年龄、性别、家庭构成等人口统计字段；以下结论均基于购物行为场景而非人群标签。</div>
    </div>
    <div class="card"><h3>这是一群什么样的买家</h3>
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
"""

PROD_SEC = r"""
<section id="s7">
  <div class="sec-head"><span class="sec-no">07</span><h2>6 款产品档案</h2></div>
  <div class="sec-desc">2026-09-17 采集自 Amazon 美国站；价格/评分/评价数/排名/状态均为页面实时值。点击链接可直接跳转商品页。</div>
  <div class="prod-grid" id="prod_grid"></div>
</section>
"""

FOOTER = r"""
<div class="footer">Amazon 美国站 · 浴帘内衬 6 款竞品 · 买家模拟选品实验报告（@TOTAL@）<br>@META@ · 聚合时间 2026-09-17 · 本报告所有数据均可追溯至原始答卷</div>
"""

# ============================================================
# 报告 A · 货架选择
# ============================================================
HERO_A = r"""
<header class="hero"><div class="hero-inner">
  <div class="kicker">AMAZON US · SHOWER CURTAIN LINERS · 实验一：货架选择</div>
  <h1>浴帘内衬 6 款竞品 · 货架选择实验报告</h1>
  <div class="sub">1,000 名北美 Amazon 购物者画像，在搜索结果的 6 款真实在售产品货架上：选 1 款并说明理由、对每款未选产品给出拒绝原因、回答页数容忍度与 Listing 要素重要性。回答：货架上谁赢、为什么赢、什么 Listing 要素真正影响下单。</div>
  <div class="meta-chips"><span>样本 n=1,000</span><span>26 题</span><span>6 款真实在售 ASIN</span><span>并发 30 · 0 错误</span></div>
  <div class="kpi-row">
    <div class="kpi"><div class="lbl">货架最终首选</div><div class="v">C · 60.0%</div><div class="s">LQFMEHOT $7.09 / 4.6★ / 974 评</div></div>
    <div class="kpi"><div class="lbl">第二/第三</div><div class="v">A 20.8% · B 17.9%</div><div class="s">E 1.3% · D/F 无人选择</div></div>
    <div class="kpi"><div class="lbl">只在第 1 页购买</div><div class="v">97.7%</div><div class="s">首页可见性 = 生死线</div></div>
    <div class="kpi"><div class="lbl">首要决策因素</div><div class="v">价格/价值 52.2%</div><div class="s">第二因素：评价 40.8%</div></div>
    <div class="kpi"><div class="lbl">Listing 最重要要素</div><div class="v">评价内容 4.88/5</div><div class="s">A+ 内容 1.99/5 垫底</div></div>
  </div>
</div></header>
"""

CORE_A = r"""
<section id="s0">
<div class="hl-banner"><h2><span class="badge">核心结论</span> 一句话看懂货架实验</h2>
  <div class="hl-grid">
    <div class="hl-card"><div class="tag">最终赢家</div><div class="n">C 拿走 60% 首选</div><p>LQFMEHOT（$7.09 · 4.6★ · 974 评）以「全场最低价 + 最高评分」组合在货架上断层第一：60.0% 首选、72.5% 兜底、71.8% 转投去向。</p><div class="ev">证据：选择份额 60.0%（n=1000）</div></div>
    <div class="hl-card"><div class="tag">排名反差</div><div class="n">真实排名 ≠ 用户偏好</div><p>C 真实类目排名仅 #124（6 款中靠后），模拟却 60% 首选；真实排名最高的 A（#27）模拟仅 20.8%。真实排名由销量/流量权重决定，未如实反映用户偏好。</p><div class="ev">证据：源表类目排名 vs 模拟份额</div></div>
    <div class="hl-card"><div class="tag">购买引擎</div><div class="n">价格 × 评分 × 千评</div><p>第一决策因素「价格/价值」52.2%、第二「评价」40.8%；Listing 要素重要性最高分「评价内容」4.88/5。评价过少（&lt;50 评）的产品 82%+ 被直接淘汰。</p><div class="ev">证据：factor_most 52.2% / importance 4.88</div></div>
    <div class="hl-card"><div class="tag">四大闸门</div><div class="n">价格·外观·评价·库存</div><p>A 死于价格（792 人）、B 死于外观（669 人）、D/F 死于评价太少（982/967 人）、E 死于外观+库存告急。每款产品都有明确的「死因」。</p><div class="ev">证据：每款拒绝原因 Top4（n=1000）</div></div>
    <div class="hl-card"><div class="tag">生死线</div><div class="n">首页可见性 + 信息红线</div><p>97.7% 只在第 1 页购买。无货 100% 一票否决、材质不明 97.3%、图片模糊 94.0%、无价格 91.6%——不达标连被比较的资格都没有。</p><div class="ev">证据：page_buy 97.7% / redline 100%</div></div>
  </div>
</div>
</section>
"""

DID_A = r"""
<section id="s2">
  <div class="sec-head"><span class="sec-no">02</span><h2>他们做了什么</h2></div>
  <div class="sec-desc">货架选择实验（26 题）：模拟买家在搜索结果货架上同时看到 6 款真实产品，完成一轮完整的「比货架」决策。</div>
  <div class="card"><h3>任务流程</h3>
    <div class="callout">浏览货架（6 款，真实价格/评分/评价数/库存/主图）→ 选 1 款并说明理由 → 对每款未选产品给出拒绝原因（16 个候选原因多选）→ 回答页数容忍度（浏览/购买）→ 评价 8 项 Listing 要素重要性 → 红线清单 → 材质/透明度偏好 → 徽章效应 → 切换诱因 → 价格接受度 → 购买意向</div>
    <div class="note">观察口径：静态货架上的「第一选择」与拒绝理由；多选题百分比 = 选中人数 / 1,000。</div>
  </div>
</section>
"""

CHOSE_A = r"""
<section id="s3">
  <div class="sec-head"><span class="sec-no">03</span><h2>最后大家选了谁</h2></div>
  <div class="sec-desc">百分点差异为描述性结果，未做统计显著性检验。</div>
  <div class="grid2">
    <div class="card"><h3>货架首选份额（n=1,000）</h3>
      <div class="fig sm" id="fig_share"></div>
      <div class="note">C 独占六成；A/B 瓜分近四成；E 仅 1.3%；D、F 无人选择——「一超两强三淘汰」格局。</div>
    </div>
    <div class="card"><h3>真实排名 vs 模拟偏好（n=1,000）</h3>
      <div class="fig sm" id="fig_rank"></div>
      <div class="note">真实类目排名（#Shower Curtain Liners）2026-09-17 采集。模拟首选 C 真实排名 #124 却 60% 第一；真实第一 A（#27）模拟仅 20.8%。</div>
    </div>
  </div>
  <div class="card"><h3>购买意向与价格接受（n=1,000）</h3>
    <div class="grid2">
      <div class="fig sm" id="fig_intent"></div>
      <div class="fig sm" id="fig_price"></div>
    </div>
    <div class="note">购买意向分布：多数买家会考虑购买；价格接受度均值 4.78/5（799 人选「完全接受当前价位」）——$7–$10 价位带被普遍接受，$18.99 是唯一「价格失血」点。</div>
  </div>
</section>
"""

WHY_A = r"""
<section id="s4">
  <div class="sec-head"><span class="sec-no">04</span><h2>为什么选 / 为什么不选 · 用户真正关注什么</h2></div>
  <div class="sec-desc">①开放理由按主题归纳（词频为「提及次数」）；②拒绝原因为 16 选多选，百分比 = 选中人数/1000。注意区分「被高频提及」与「有证据表明影响选择」。</div>

  <div class="sec-head" style="margin-top:24px;"><span class="sec-no">4.1</span><h3 style="font-size:17px;">为什么不选：每款产品的拒绝原因（四大淘汰闸门）</h3></div>
  <div class="card"><div class="fig" id="fig_reject"></div>
    <div class="note">A 死于价格（792 人）、B 死于外观（669 人）、C 死于品牌陌生（360 人）、D/F 死于评价太少（982/967 人）、E 死于外观+库存告急。拒绝原因清晰可归因到具体 Listing 短板。</div>
  </div>

  <div class="sec-head" style="margin-top:24px;"><span class="sec-no">4.2</span><h3 style="font-size:17px;">用户真正关注什么：四大证据面</h3></div>
  <div class="grid2">
    <div class="card"><h3>决策因素（第一 / 第二，n=1000）</h3>
      <div class="fig sm" id="fig_factor"></div>
      <div class="note">第一因素「价格/价值」52.2%，第二因素「评价」40.8%——价格是门槛，评价是背书。</div>
    </div>
    <div class="card"><h3>Listing 要素重要性（1–5 分，n=1000）</h3>
      <div class="fig sm" id="fig_importance"></div>
      <div class="note">评价内容 4.88 最高、价格展示 4.55、主图 4.32；A+ 内容仅 1.99 垫底。</div>
    </div>
    <div class="card"><h3>Listing 红线（n=1000）</h3>
      <div class="fig sm" id="fig_redline"></div>
      <div class="note">「无货」100% 一票否决；材质不明 97.3%、图片模糊 94.0%、无价格 91.6%、无尺寸 89.6%。</div>
    </div>
    <div class="card"><h3>页数容忍 · 浏览 vs 购买（n=1000）</h3>
      <div class="fig sm" id="fig_page"></div>
      <div class="note">95.4% 愿翻到第 2 页浏览，但 97.7% 只在第 1 页购买——「浏览可以多翻，下单只看首页」。</div>
    </div>
  </div>

  <div class="sec-head" style="margin-top:24px;"><span class="sec-no">4.3</span><h3 style="font-size:17px;">外部信号：什么会改变决策</h3></div>
  <div class="grid2">
    <div class="card"><h3>切换诱因（n=1000）</h3>
      <div class="fig sm" id="fig_switch"></div>
      <div class="note">64.9% 表示「竞品评分更高」会切换——评分的小数点差距可能就是订单归属。</div>
    </div>
    <div class="card"><h3>徽章影响（n=1000）</h3>
      <div class="fig sm" id="fig_badge"></div>
      <div class="note">91.1% 自述徽章会「有点/明显」影响选择——自述层面价值高，真实拉动建议 A/B 验证。</div>
    </div>
  </div>

  <div class="sec-head" style="margin-top:24px;"><span class="sec-no">4.4</span><h3 style="font-size:17px;">材质与透明度偏好（产品力硬门槛）</h3></div>
  <div class="grid2">
    <div class="card"><h3>材质偏好（n=1000）</h3>
      <div class="fig sm" id="fig_material"></div>
      <div class="note">100% 要求 EVA（环保无味）——材质陈述是入场券，非 EVA 直接出局。</div>
    </div>
    <div class="card"><h3>透明度偏好（n=1000）</h3>
      <div class="fig sm" id="fig_trans"></div>
      <div class="note">96.9% 偏好半透明——「半透明 + 可遮挡」的平衡是主流需求。</div>
    </div>
  </div>
</section>
"""

US_A = r"""
<section id="s5">
  <div class="sec-head"><span class="sec-no">05</span><h2>对卖家的含义：谁赢在哪、输在哪</h2></div>
  <div class="sec-desc">本测试未预设「我方产品」，6 款均为美国站真实在售竞品；按卖家角色诊断（KEEP=已验证优势 / FIX=有较充分证据的问题 / TELL=有价值但未被感知 / TEST=出现信号但证据不足）。</div>
  <div class="grid2">
    <div class="card"><h3>C · LQFMEHOT（赢家）</h3>
      <p><span class="tag-k">KEEP</span> 价格卡位（$7.09 最低）+ 评分最高（4.6★）+ 千评组合是货架最优解：60% 首选、72.5% 兜底。</p>
      <p><span class="tag-f">FIX</span> 「品牌陌生」是最大拒绝理由（360 人）——品牌信任是唯一短板。</p>
      <p><span class="tag-t">TELL</span> 它的 Art Deco 外观本身有吸引力（首点 26.3% 第二），但未被充分感知为「好看」——主图可强化纹理质感。</p>
    </div>
    <div class="card"><h3>A · AmazerBath（高价高信任）</h3>
      <p><span class="tag-k">KEEP</span> 4,156 评论 + 4.5★ 信任信号极强：首点 65.5%，份额 20.8% 第二。</p>
      <p><span class="tag-f">FIX</span> 价格拒绝 792 人（79.2%）——$18.99 相对 $7 竞品无价值感支撑；无 Featured Offer 直接降低下单意愿。</p>
      <p><span class="tag-e">TEST</span> 若补充「高质耐用/2合1省钱」价值叙事或变体降价，能否把点击优势转化为份额，值得验证。</p>
    </div>
    <div class="card"><h3>B · jssablo（性价比跟跑者）</h3>
      <p><span class="tag-k">KEEP</span> $7.19 + 1,872 评的性价比组合拿到 17.9% 份额，是第二选择者（26.1% 转投去向为 B）。</p>
      <p><span class="tag-f">FIX</span> 外观拒绝 669 人（66.9%）是最大短板；「价格存疑」409 人表明低价+低知名品牌引发质量疑虑。</p>
    </div>
    <div class="card"><h3>E · Dependable（纯黑基础款）</h3>
      <p><span class="tag-f">FIX</span> 外观拒绝 925 人（92.5%）——纯黑无图案被普遍视为单调；库存告急（596 人担忧）直接劝退。</p>
      <p><span class="tag-e">TEST</span> 当前样本仅 1.3% 选择，不足以下「黑色浴帘无市场」的结论，但方向不乐观。</p>
    </div>
    <div class="card"><h3>D · Laumyasof（新品 2 件装）</h3>
      <p><span class="tag-f">FIX</span> 评价仅 16 条：982 人（98.2%）因评价少拒绝——新品信任门槛极高；821 人质疑材质（2 件装 $9.99 引发「便宜没好货」联想）。</p>
      <p><span class="tag-k">KEEP</span> 无（当前样本中未建立可验证优势）。</p>
    </div>
    <div class="card"><h3>F · MuuXii（无货）</h3>
      <p><span class="tag-f">FIX</span> Currently unavailable + 无价格：897 人因库存/配送拒绝、967 人因评价少拒绝——0% 份额的直接原因。</p>
      <p><span class="note-line">注：无货产品被 100% 一票否决（红线），其数据不构成有效市场信号。</span></p>
    </div>
  </div>
</section>
"""

NEXT_A = r"""
<section id="s6">
  <div class="sec-head"><span class="sec-no">06</span><h2>下一步应该做什么</h2></div>
  <div class="sec-desc">按证据强度分级：ACT=证据较充分可直接行动；TEST=方向值得关注但需先验证；WATCH=弱信号暂不投入。</div>
  <div class="card">
    <table class="table">
      <tr><th style="width:64px;">级别</th><th style="width:190px;">做什么</th><th>为什么 / 依据</th></tr>
      <tr><td><span class="tag-k">ACT</span></td><td><b>守住信息完整红线</b></td><td>无货 100%、材质不明 97.3%、图片模糊 94.0%、无价格 91.6% 一票否决——所有 listing 必须先通过这四条及格线。F 的 0% 与 A 的配送提示流失即为反例。</td></tr>
      <tr><td><span class="tag-k">ACT</span></td><td><b>验证「评分 +0.1」的订单价值</b></td><td>64.9% 表示评分更高的竞品会触发切换；C（4.6★）vs B（4.4★）同价位下份额 60% vs 17.9%。对 4.4→4.6 区间的评分营销做投入产出测算。</td></tr>
      <tr><td><span class="tag-t">TEST</span></td><td><b>A/B 验证徽章对转化的真实拉动</b></td><td>91.1% 自述受徽章影响，但自述≠真实转化。主图/标题徽章元素前后对照实验。</td></tr>
      <tr><td><span class="tag-t">TEST</span></td><td><b>新品信任破局测试</b></td><td>D（16 评）98.2% 因评价少被拒。验证「Vine 评论计划 + 低价跑量」能否把评价数拉到 200+ 进入比较圈。</td></tr>
      <tr><td><span class="tag-t">TEST</span></td><td><b>A 的高价价值叙事测试</b></td><td>79.2% 因价格拒绝 A，但 65.5% 首点证明吸引力。验证「2合1省一件」+「高级材质耐用叙事」能否让 $18.99 自成一档。</td></tr>
      <tr><td><span class="tag-e">WATCH</span></td><td><b>A+ 内容投入暂缓</b></td><td>A+ 重要性 1.99/5 全场垫底——当前样本中用户不靠 A+ 做决策。</td></tr>
    </table>
    <div class="note">注：「A/B 验证」「测试」类建议基于当前样本信号强度分级，需后续实验确认；当前数据不足以支持因果判断。</div>
  </div>
</section>
"""

JS_A = r"""
const PALETTE = ["#E8A33D","#2E9E8F","#3B6FB5","#C24B3F","#8A6FB0","#7A8CA8"];
const CODES = ["A","B","C","D","E","F"];
const SHORT = {A:"A 祖母绿", B:"B 蓝波纹", C:"C 水立方", D:"D 鹅卵石2件", E:"E 纯黑", F:"F 透明波点"};
const REJ_CN = {price_too_high:"价格过高", look:"外观不满意", availability:"库存/配送", transparency:"透明度不合适", brand:"品牌陌生", material:"材质存疑", pack:"2件装不适用", few_reviews:"评价数太少", price_suspicious:"低价存疑", rating:"评分不足", review_concern:"评论内容顾虑", size:"尺寸不符", info_incomplete:"信息不全", missing_magnet:"无磁吸"};
function fig(id){ return document.getElementById(id); }

(function(){ const c=fig("fig_share"); if(!c)return; const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  legend:{bottom:0,textStyle:{fontSize:12}}, grid:{left:10,right:30,top:8,bottom:44,containLabel:true},
  xAxis:{type:"value",max:70,axisLabel:{formatter:"{value}%",fontSize:12}},
  yAxis:{type:"category",data:CODES.map(k=>SHORT[k]),inverse:true,axisLabel:{fontSize:12}},
  series:[{type:"bar",data:CODES.map(k=>({value:DATA.choice.share[k]||0,itemStyle:{color:k==="C"?PALETTE[0]:"#9FB0C8"}})),barWidth:26,
    label:{show:true,position:"right",formatter:function(p){return p.value+"%";},fontSize:12,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_rank"); if(!c)return; const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const i=ps[0].dataIndex,k=CODES[i];return SHORT[k]+"<br/>真实类目排名：#"+DATA.rank_truth[k]+"（越小越靠前）<br/>模拟首选份额："+(DATA.choice.share[k]||0)+"%";}},
  legend:{data:["真实类目排名（越小越靠前）","模拟首选份额 %"],bottom:0,textStyle:{fontSize:12}},
  grid:{left:10,right:30,top:14,bottom:44,containLabel:true},
  xAxis:{type:"category",data:CODES.map(k=>SHORT[k]),axisLabel:{fontSize:12}},
  yAxis:[{type:"value",name:"真实排名",nameTextStyle:{fontSize:11},inverse:true,min:0,max:900,axisLabel:{fontSize:11,formatter:function(v){return "#"+v;}}},
         {type:"value",name:"模拟份额%",nameTextStyle:{fontSize:11},max:70,axisLabel:{fontSize:11,formatter:"{value}%"}}],
  series:[{name:"真实类目排名（越小越靠前）",type:"bar",data:CODES.map(k=>DATA.rank_truth[k]),yAxisIndex:0,barWidth:22,itemStyle:{color:"#9FB0C8"},label:{show:true,position:"top",formatter:function(p){return "#"+p.value;},fontSize:11,color:"#64748B"}},
    {name:"模拟首选份额 %",type:"bar",data:CODES.map(k=>DATA.choice.share[k]||0),yAxisIndex:1,barWidth:22,itemStyle:{color:function(p){return p.dataIndex===2?PALETTE[0]:"#3B6FB5";}},label:{show:true,position:"top",formatter:function(p){return p.value+"%";},fontSize:11,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_intent"); if(!c)return; const chart=echarts.init(c);
  chart.setOption({title:{text:"购买意向（n=1000）",left:"center",textStyle:{fontSize:14,color:"#16233B"}},
  tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  legend:{bottom:0,textStyle:{fontSize:11}}, series:[{type:"pie",radius:["36%","62%"],center:["50%","46%"],data:[
    {name:"5 分（很可能买）",value:14.7,itemStyle:{color:"#2E9E8F"}},{name:"4 分",value:83.4,itemStyle:{color:"#3B6FB5"}},{name:"3 分",value:1.9,itemStyle:{color:"#E8A33D"}}],label:{fontSize:11,formatter:"{b} {d}%"}}]});
})();

(function(){ const c=fig("fig_price"); if(!c)return; const chart=echarts.init(c);
  chart.setOption({title:{text:"价格接受度（n=1000）",left:"center",textStyle:{fontSize:14,color:"#16233B"}},
  tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  legend:{bottom:0,textStyle:{fontSize:11}}, series:[{type:"pie",radius:["36%","62%"],center:["50%","46%"],data:[
    {name:"5 分（完全接受）",value:79.9,itemStyle:{color:"#2E9E8F"}},{name:"4 分",value:18.4,itemStyle:{color:"#3B6FB5"}},{name:"3 分",value:1.7,itemStyle:{color:"#E8A33D"}}],label:{fontSize:11,formatter:"{b} {d}%"}}]});
})();

(function(){ const c=fig("fig_reject"); if(!c)return;
  const names={A:"A 祖母绿（$18.99）",B:"B 蓝波纹（$7.19）",C:"C 水立方（$7.09）",D:"D 鹅卵石2件（$9.99）",E:"E 纯黑（$9.99）",F:"F 透明波点（无货）"};
  const reasonKeys=[]; const seen={};
  CODES.forEach(k=>{(DATA.choice.reject_top[k]||[]).forEach(function(r){const cn=REJ_CN[r[0]]||r[0]; if(!seen[cn]){seen[cn]=true;reasonKeys.push(cn);}});});
  const series=CODES.map(function(k){return {name:names[k],type:"bar",stack:"total",data:reasonKeys.map(function(cn){const f=(DATA.choice.reject_top[k]||[]).find(function(r){return (REJ_CN[r[0]]||r[0])===cn;});return f?f[1]:0;}),itemStyle:{color:PALETTE[CODES.indexOf(k)]}};});
  const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){let h=ps[0].axisValue+"<br/>";ps.forEach(function(p){if(p.value>0)h+=p.marker+p.seriesName+"："+p.value+" 人<br/>";});return h;}},
  legend:{type:"scroll",bottom:0,textStyle:{fontSize:11}}, grid:{left:10,right:20,top:14,bottom:52,containLabel:true},
  xAxis:{type:"category",data:reasonKeys,axisLabel:{fontSize:11.5,interval:0}}, yAxis:{type:"value",max:1000,axisLabel:{fontSize:12}},
  series:series});
})();

(function(){ const c=fig("fig_factor"); if(!c)return;
  const order=["price_value","reviews","rating","material","magnet","appearance"];
  const cn={price_value:"价格/价值",reviews:"评价内容",rating:"评分",material:"材质",magnet:"磁吸配重",appearance:"外观"};
  const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){let h=ps[0].name+"<br/>";ps.forEach(function(p){h+=p.marker+p.seriesName+"："+p.value+"%<br/>";});return h;}},
  legend:{data:["第一决策因素","第二决策因素"],bottom:0,textStyle:{fontSize:12}}, grid:{left:10,right:20,top:14,bottom:44,containLabel:true},
  xAxis:{type:"category",data:order.map(k=>cn[k]),axisLabel:{fontSize:11.5}}, yAxis:{type:"value",max:60,axisLabel:{formatter:"{value}%",fontSize:12}},
  series:[{name:"第一决策因素",type:"bar",data:order.map(k=>DATA.choice.factor_most[k]||0),barWidth:24,itemStyle:{color:"#E8A33D"},label:{show:true,position:"top",formatter:function(p){return p.value+"%";},fontSize:11,color:"#33415C"}},
    {name:"第二决策因素",type:"bar",data:order.map(k=>DATA.choice.factor_second[k]||0),barWidth:24,itemStyle:{color:"#2E9E8F"},label:{show:true,position:"top",formatter:function(p){return p.value+"%";},fontSize:11,color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_importance"); if(!c)return;
  const cn={title:"标题",image:"主图",bullets:"五点描述",aplus:"A+ 内容",attr:"属性表",price:"价格展示",reviews:"评价内容",trust:"信任标识"};
  const d=DATA.choice.importance; const keys=Object.keys(d).sort(function(a,b){return d[b]-d[a];});
  const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const p=ps[0];return p.name+"：均分 "+p.value+" / 5";}},
  grid:{left:10,right:46,top:10,bottom:20,containLabel:true}, xAxis:{type:"value",max:5,axisLabel:{fontSize:12}},
  yAxis:{type:"category",inverse:true,data:keys.map(k=>cn[k]),axisLabel:{fontSize:12}},
  series:[{type:"bar",data:keys.map(k=>({value:d[k],itemStyle:{color:k==="aplus"?"#C6CFDC":(k==="reviews"?"#E8A33D":"#3B6FB5")}})),barWidth:22,
    label:{show:true,position:"right",formatter:function(p){return p.value.toFixed(2);},fontSize:12,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_redline"); if(!c)return;
  const cn={unavailable:"无货",material_unclear:"材质不明",blur_image:"图片模糊",no_price:"无价格",no_size:"无尺寸",low_rating:"评分低",few_reviews:"评价太少",no_bullets:"无五点描述",brand_unfamiliar:"品牌陌生",none:"无"};
  const d=DATA.choice.redline; const keys=Object.keys(d).filter(k=>d[k]>0).sort(function(a,b){return d[b]-d[a];});
  const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const p=ps[0];return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  grid:{left:10,right:46,top:10,bottom:20,containLabel:true}, xAxis:{type:"value",max:100,axisLabel:{formatter:"{value}%",fontSize:12}},
  yAxis:{type:"category",inverse:true,data:keys.map(k=>cn[k]||k),axisLabel:{fontSize:12}},
  series:[{type:"bar",data:keys.map(k=>({value:d[k],itemStyle:{color:d[k]>=90?"#C24B3F":(d[k]>=60?"#E8A33D":"#9FB0C8")}})),barWidth:22,
    label:{show:true,position:"right",formatter:function(p){return p.value+"%";},fontSize:11.5,color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_page"); if(!c)return;
  const browse=DATA.choice.page_browse, buy=DATA.choice.page_buy; const keys=Object.keys(browse);
  const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){let h=ps[0].name+"<br/>";ps.forEach(function(p){h+=p.marker+p.seriesName+"："+p.value+"%<br/>";});return h;}},
  legend:{data:["愿意浏览","愿意购买"],bottom:0,textStyle:{fontSize:12}}, grid:{left:10,right:20,top:14,bottom:44,containLabel:true},
  xAxis:{type:"category",data:keys.map(k=>k.replace("page","第")+"页"),axisLabel:{fontSize:12}}, yAxis:{type:"value",max:100,axisLabel:{formatter:"{value}%",fontSize:12}},
  series:[{name:"愿意浏览",type:"bar",data:keys.map(k=>browse[k]),barWidth:26,itemStyle:{color:"#9FB0C8"},label:{show:true,position:"top",formatter:function(p){return p.value+"%";},fontSize:11,color:"#33415C"}},
    {name:"愿意购买",type:"bar",data:keys.map(k=>buy[k]||0),barWidth:26,itemStyle:{color:"#E8A33D"},label:{show:true,position:"top",formatter:function(p){return p.value+"%";},fontSize:11,color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_switch"); if(!c)return;
  const cn={better_rating:"竞品评分更高",better_function:"功能更好",lower_price:"价格更低",better_value:"性价比更高",nothing:"什么都不换",better_look:"更好看"};
  const d=DATA.choice.switch_trigger; const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  legend:{bottom:0,textStyle:{fontSize:11}}, series:[{type:"pie",radius:["36%","62%"],center:["50%","44%"],data:Object.keys(d).map(k=>({name:cn[k]||k,value:d[k]})),label:{fontSize:11,formatter:"{b} {d}%"},labelLine:{length:12,length2:6}}]});
})();

(function(){ const c=fig("fig_badge"); if(!c)return;
  const cn={yes_somewhat:"有影响（部分）",yes_strongly:"影响很大",neutral:"中立",unlikely:"不太影响",no_effect:"完全不影响"};
  const d=DATA.choice.badge_effect; const order=["yes_somewhat","yes_strongly","neutral","unlikely","no_effect"];
  const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  legend:{bottom:0,textStyle:{fontSize:11}}, series:[{type:"pie",radius:["36%","62%"],center:["50%","44%"],data:order.map(k=>({name:cn[k],value:d[k]||0})),label:{fontSize:11,formatter:"{b} {d}%"},labelLine:{length:12,length2:6}}]});
})();

(function(){ const c=fig("fig_material"); if(!c)return;
  const d=DATA.choice.material_pref; const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%";}},
  legend:{bottom:0,textStyle:{fontSize:11}}, series:[{type:"pie",radius:["38%","64%"],center:["50%","45%"],data:Object.keys(d).map(k=>({name:k==="eva"?"EVA（环保无味）":k,value:d[k],itemStyle:{color:"#2E9E8F"}})),label:{fontSize:12,formatter:"{b} {d}%"}}]});
})();

(function(){ const c=fig("fig_trans"); if(!c)return;
  const cn={semi:"半透明",fully_transparent:"全透明",blackout:"全遮光"};
  const d=DATA.choice.transparency_pref; const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  legend:{bottom:0,textStyle:{fontSize:11}}, series:[{type:"pie",radius:["38%","64%"],center:["50%","45%"],data:Object.keys(d).map(k=>({name:cn[k]||k,value:d[k]})),label:{fontSize:12,formatter:"{b} {d}%"}}]});
})();
"""

# ============================================================
# 报告 B · 决策旅程
# ============================================================
HERO_B = r"""
<header class="hero"><div class="hero-inner">
  <div class="kicker">AMAZON US · SHOWER CURTAIN LINERS · 实验二：决策旅程</div>
  <h1>浴帘内衬 6 款竞品 · 决策旅程实验报告</h1>
  <div class="sub">1,000 名北美 Amazon 购物者画像，完整走完「搜索 → 首点 → 查看详情 → 买/不买 → 是否转投 → 兜底」决策链，每个决策点都给出理由。回答：第一眼点进谁、详情页看什么、最终买不买、为什么转投、全部落空时买谁。</div>
  <div class="meta-chips"><span>样本 n=1,000</span><span>8 题 · 每题必答理由</span><span>6 款真实在售 ASIN</span><span>并发 30 · 0 错误</span></div>
  <div class="kpi-row">
    <div class="kpi"><div class="lbl">第一眼最想点进</div><div class="v">A · 65.5%</div><div class="s">AmazerBath 祖母绿（4,156 评）</div></div>
    <div class="kpi"><div class="lbl">点进后必看</div><div class="v">材质安全 99.8%</div><div class="s">评价内容 99.5%</div></div>
    <div class="kpi"><div class="lbl">全部落空时兜底</div><div class="v">C · 72.5%</div><div class="s">性价比+最高评分=终极安全牌</div></div>
    <div class="kpi"><div class="lbl">明确立即购买</div><div class="v">仅 0.7%</div><div class="s">99.7% 退出后会再看其他</div></div>
    <div class="kpi"><div class="lbl">搜索只翻第 1 页</div><div class="v">79.0%</div><div class="s">首页曝光 = 触达前提</div></div>
  </div>
</div></header>
"""

CORE_B = r"""
<section id="s0">
<div class="hl-banner"><h2><span class="badge">核心结论</span> 一句话看懂决策旅程</h2>
  <div class="hl-grid">
    <div class="hl-card"><div class="tag">点击赢家 ≠ 最终赢家</div><div class="n">首点 A 65.5% → 兜底 C 72.5%</div><p>第一眼被 A（$18.99 / 4,156 评）吸引，但完整决策后大多数人转投 C（$7.09 / 4.6★）。引流与转化是两条逻辑。</p><div class="ev">证据：首点 A 65.5% vs 兜底 C 72.5%（n=1000）</div></div>
    <div class="hl-card"><div class="tag">点击靠「面」</div><div class="n">外观 + 评论信任驱动首点</div><p>首点 A 的理由中「外观」提及 2,187 次（n=655），其次磁吸配重 860、评价数 793——视觉高级感 + 评论多 = 第一眼吸引力。</p><div class="ev">证据：首点理由主题词频（开放题归纳）</div></div>
    <div class="hl-card"><div class="tag">购买靠「里」</div><div class="n">材质 · 评分 · 价格 · 千评</div><p>兜底 C 的理由中「材质安全」1,175、「评分」1,037、「磁吸配重」943、「价格价值」887、「评价数」857——功能+价格+信任全面满足。</p><div class="ev">证据：兜底理由主题词频（n=725）</div></div>
    <div class="hl-card"><div class="tag">犹豫型为主</div><div class="n">立即购买仅 0.7% · 最终 6.7%</div><p>66.2% 倾向购买但 99.7% 退出后还会看其他——货架上的相邻竞品就是最大流量流失点；转投去向 C 71.8%。</p><div class="ev">证据：buy_decision / consider_other / next_choice（n=1000）</div></div>
    <div class="hl-card"><div class="tag">下单阻力</div><div class="n">配送 + 无 Featured Offer</div><p>不购买者理由中「库存/配送」140 次提及居首；A 详情页的配送提示使买家「加购再比较」而非直接下单——履约确定性是下单临门一脚。</p><div class="ev">证据：notbuy 理由词频 / 买家原话</div></div>
  </div>
</div>
</section>
"""

DID_B = r"""
<section id="s2">
  <div class="sec-head"><span class="sec-no">02</span><h2>他们做了什么</h2></div>
  <div class="sec-desc">决策旅程实验（8 题，每题必答理由）：模拟买家从搜索结果开始，逐步走完一次完整的购买决策链。</div>
  <div class="card"><h3>任务流程（逐步决策链）</h3>
    <div class="callout">搜索「浴帘内衬」→ 看到 6 款产品：<b>① 第一眼最想点进哪个</b>（理由）→ <b>② 点进后最想查看什么信息</b>（多选≤3）→ <b>③ 是否购买 / 犹豫 / 放弃</b>（理由）→ <b>④ 退出后是否考虑其他</b>（理由）→ <b>⑤ 考虑哪款</b>（理由）→ <b>⑥ 全部未买时兜底选哪款</b>（理由）→ ⑦ 搜索页翻页意愿 → ⑧ 整体决策因素</div>
    <div class="note">观察口径：从首点、信息偏好到最终兜底的完整决策链；开放题理由为主题归纳的定性证据。</div>
  </div>
</section>
"""

CHOSE_B = r"""
<section id="s3">
  <div class="sec-head"><span class="sec-no">03</span><h2>最后大家选了谁</h2></div>
  <div class="sec-desc">百分点差异为描述性结果，未做统计显著性检验。</div>
  <div class="grid2">
    <div class="card"><h3>首点 vs 兜底（n=1,000）</h3>
      <div class="fig sm" id="fig_first_final"></div>
      <div class="note">首点 A 65.5%（视觉+评论信任），完整决策后兜底 C 72.5%。「第一眼赢家」和「最终赢家」不是同一款。</div>
    </div>
    <div class="card"><h3>购买决策分布（n=1,000）</h3>
      <div class="fig sm" id="fig_buy"></div>
      <div class="note">66.2% 倾向购买、22.7% 犹豫，但<b>明确立即购买仅 0.7%</b>；进一步询问中明确会买的只有 6.7%。</div>
    </div>
  </div>
  <div class="card"><h3>决策漏斗（1000 人完整转化链）</h3>
    <div class="fig" id="fig_funnel"></div>
    <div class="note">首点 65.5% 集中 A → 99.8% 必看材质安全 → 66.2% 倾向购买 → 仅 0.7% 立即购买 → 99.7% 再看其他 → 转投 C 71.8% → 兜底 C 72.5%。整条链上「立即转化」极薄，多数决策在「再比较」中完成。</div>
  </div>
  <div class="card"><h3>首点 → 兜底 交叉（n=1,000）</h3>
    <div class="fig" id="fig_cross"></div>
    <div class="note">首点 A 的人 73.9% 最终兜底 C；首点 C 的人 70.3% 仍选 C；首点 B 的人 68.3% 转投 C——C 是各入口共同的「最终归宿」。</div>
  </div>
</section>
"""

WHY_B = r"""
<section id="s4">
  <div class="sec-head"><span class="sec-no">04</span><h2>为什么选 / 为什么不选 · 用户真正关注什么</h2></div>
  <div class="sec-desc">理由为主题归纳（词频=提及次数，n=各决策人数）；多选题百分比 = 选中人数/1000。注意区分「被高频提及」与「有证据表明影响选择」。</div>

  <div class="sec-head" style="margin-top:24px;"><span class="sec-no">4.1</span><h3 style="font-size:17px;">为什么点进 A：外观 + 评论信任（点击靠「面」）</h3></div>
  <div class="card"><div class="fig sm" id="fig_why_a"></div>
    <div class="note">首点 A 的理由中「外观」提及 2,187 次（n=655）——祖母绿高级感 + 4,000+ 评论的信任信号是点击引擎；价格不是点击时考虑的因素。</div>
  </div>

  <div class="sec-head" style="margin-top:24px;"><span class="sec-no">4.2</span><h3 style="font-size:17px;">点进后看什么：材质安全与评价是必看项</h3></div>
  <div class="card"><div class="fig sm" id="fig_info"></div>
    <div class="note">99.8% 必看「材质/安全性」，99.5% 必看「评价内容」，61.3% 看规格尺寸，26.0% 关注配送——材质与口碑是详情页的「第一信息需求」。</div>
  </div>

  <div class="sec-head" style="margin-top:24px;"><span class="sec-no">4.3</span><h3 style="font-size:17px;">为什么买 / 不买：倾向购买但被什么拦住</h3></div>
  <div class="grid2">
    <div class="card"><h3>不购买者的理由（n=104）</h3>
      <div class="fig sm" id="fig_notbuy"></div>
      <div class="note">不购买理由中「库存/配送」140 次提及居首（A 的配送受限 + E 的仅剩 10 件是典型触发），其次价格价值 36——履约确定性是最大下单障碍。</div>
    </div>
    <div class="card"><h3>考虑其他产品的理由（n=997）</h3>
      <div class="fig sm" id="fig_consider"></div>
      <div class="note">99.7% 会再考虑其他：主要为了「比价」「比评分」——这是亚马逊货架的天然行为，也是竞品拦截你的窗口。</div>
    </div>
  </div>

  <div class="sec-head" style="margin-top:24px;"><span class="sec-no">4.4</span><h3 style="font-size:17px;">转投与兜底：为什么都流向 C</h3></div>
  <div class="grid2">
    <div class="card"><h3>转投 C 的理由（n=718）</h3>
      <div class="fig sm" id="fig_switchc"></div>
      <div class="note">转投 C 的理由中「评分」1,102 次提及居首，其次外观 706、评价数 608、价格价值 607——C 在评分维度上是「比较后的赢家」。</div>
    </div>
    <div class="card"><h3>兜底 C 的理由（n=725）</h3>
      <div class="fig sm" id="fig_fallbackc"></div>
      <div class="note">兜底 C 的理由「材质安全」1,175、「评分」1,037、「磁吸配重」943、「价格价值」887、「评价数」857——六款中唯一全面满足功能+价格+信任的产品。</div>
    </div>
  </div>

  <div class="sec-head" style="margin-top:24px;"><span class="sec-no">4.5</span><h3 style="font-size:17px;">搜索习惯与整体决策因素</h3></div>
  <div class="grid2">
    <div class="card"><h3>搜索翻页意愿（n=1,000）</h3>
      <div class="fig sm" id="fig_pagesearch"></div>
      <div class="note">79.0% 只看搜索结果第 1 页——首页曝光是触达前提，第 2 页仅 21.0%。</div>
    </div>
    <div class="card"><h3>整体决策因素（n=1,000）</h3>
      <div class="fig sm" id="fig_overall"></div>
      <div class="note">「评价内容」53.3% 为整体决策第一因素，其次价格价值 22.1%、评分 13.6%、材质 10.1%——口碑是所有环节的主线。</div>
    </div>
  </div>

  <div class="sec-head" style="margin-top:24px;"><span class="sec-no">4.6</span><h3 style="font-size:17px;">买家原话（定性证据）</h3></div>
  <div class="card">
    <div class="quote">The emerald-green semi-transparent liner with brass grommets and weighted stones looks higher-end than the others, and 4.5 stars with over 4,000 reviews makes it feel like the safest, most reliable option to click first.<div class="src">— 首点选 A 的买家：外观 + 4,000+ 评论 = 点击理由</div></div>
    <div class="quote">The LQFMEHOT liner stands out with the highest star rating (4.6) among the affordable options, plus a distinctive Art-Deco water-wave texture that reads as more considered than a plain liner. At $7.09 with 974 reviews, it looks like a strong value without the reliability risk of the very-low-review listings.<div class="src">— 首点选 C 的买家：最高评分 + 最低价 = 「无风险的划算」</div></div>
    <div class="quote">It has the best combination of rating (4.6) and review volume (974) among the affordable options, plus magnets and a tear-proof header for durability. At $7.09 the risk is minimal if it disappoints.<div class="src">— 兜底选 C 的买家：评分×评价数×低价的低风险组合</div></div>
    <div class="quote">The material and weighted bottom look good, but the page shows a delivery notice with no featured offer, so I'd add it to my cart and check other options before committing.<div class="src">— 看 A 详情页的买家：无 Featured Offer 触发「先加购再比较」</div></div>
    <div class="quote">Strong reviews and a solid material story make it a real contender, but the page showing no featured offer and only a delivery notice makes me want to check availability before committing.<div class="src">— 看 A 详情页的买家 2：配送不确定性是下单最大阻力</div></div>
    <div class="note">以上为英文原话直引（问卷原文）；原话属定性证据，不作群体结论的唯一依据。</div>
  </div>
</section>
"""

US_B = r"""
<section id="s5">
  <div class="sec-head"><span class="sec-no">05</span><h2>对卖家的含义：从旅程看转化机会</h2></div>
  <div class="sec-desc">以决策链各环节为视角（KEEP=已验证优势 / FIX=有较充分证据的问题 / TELL=有价值但未被感知 / TEST=出现信号但证据不足）。</div>
  <div class="grid2">
    <div class="card"><h3>引流端 · A 模式（高价高信任）</h3>
      <p><span class="tag-k">KEEP</span> 评论数 + 高级外观是「点击引擎」：4,156 评吸引 65.5% 首点——高评论 SKU 的引流价值已验证。</p>
      <p><span class="tag-f">FIX</span> 但引流不转化：79.2% 在货架阶段因价格放弃；详情页配送提示进一步把「可能买」拖成「加购再比较」。</p>
      <p><span class="tag-e">TEST</span> 若 A 是您的高价 SKU：验证补充配送确定性（Prime/Featured Offer）能否把 26.0% 的配送关注转化为下单。</p>
    </div>
    <div class="card"><h3>转化端 · C 模式（性价比全能）</h3>
      <p><span class="tag-k">KEEP</span> 首点 26.3%、转投 71.8%、兜底 72.5%——C 是各入口共同的「最终归宿」：低价+最高评分+千评的组合在比较环节全面胜出。</p>
      <p><span class="tag-t">TELL</span> 它的 Art Deco 外观在首点阶段只有 26.3%（输给 A 的高级感）——主图强化纹理质感表达，可提升首点份额。</p>
    </div>
    <div class="card"><h3>流失点 · 全货架</h3>
      <p><span class="tag-f">FIX</span> 99.7% 退出后会再比较、71.8% 流向 C——货架上的高性价比竞品就是最大拦截者。您的 SKU 若在 $7–$10 价位且评分 ≤4.4，正被 C/B 拦截。</p>
      <p><span class="tag-k">KEEP</span> 「材质安全 + 评价」是详情页必看信息（99.8%/99.5%）——已完整呈现的 listing 在信息层不失分。</p>
    </div>
    <div class="card"><h3>临门一脚 · 履约确定性</h3>
      <p><span class="tag-f">FIX</span> 不购买理由「库存/配送」140 次提及居首；A 的配送提示使买家加购但不确认。库存告急（E）与配送受限（A）都在决策末端杀死订单。</p>
      <p><span class="tag-k">KEEP</span> C/B 的「In Stock + 正常配送」是兜底高分的隐性支撑——履约确定性本身就是转化率。</p>
    </div>
  </div>
</section>
"""

NEXT_B = r"""
<section id="s6">
  <div class="sec-head"><span class="sec-no">06</span><h2>下一步应该做什么</h2></div>
  <div class="sec-desc">按证据强度分级：ACT=证据较充分可直接行动；TEST=方向值得关注但需先验证；WATCH=弱信号暂不投入。</div>
  <div class="card">
    <table class="table">
      <tr><th style="width:64px;">级别</th><th style="width:200px;">做什么</th><th>为什么 / 依据</th></tr>
      <tr><td><span class="tag-k">ACT</span></td><td><b>消除履约不确定性</b></td><td>不购买理由「库存/配送」140 次提及居首；A 的配送提示把买家推向「加购再比较」。确保 Prime 配送/正常库存展示，或在详情页明确配送时效。</td></tr>
      <tr><td><span class="tag-k">ACT</span></td><td><b>主图强化「材质安全 + 评论」信号</b></td><td>99.8% 点进后必看材质安全、99.5% 看评价——主图首屏直接呈现 EVA 环保/无味/防霉与评论数徽章，缩短信息获取路径。</td></tr>
      <tr><td><span class="tag-t">TEST</span></td><td><b>验证「再比较」环节的拦截策略</b></td><td>99.7% 退出后会再比较、71.8% 流向 C——对高流失 SKU 测试「购买前比价券/组合优惠」，或在广告上拦截「C 的流量词」。</td></tr>
      <tr><td><span class="tag-t">TEST</span></td><td><b>高价 SKU 的转化试验</b></td><td>A 吸引 65.5% 首点但最终兜底仅 21.1%——验证「2合1省钱」价值叙事 + 配送确定性后，高价 SKU 能否把点击优势转化为份额。</td></tr>
      <tr><td><span class="tag-e">WATCH</span></td><td><b>低价新品的信任建设节奏</b></td><td>D（16 评）98.2% 因评价少被拒——新品在比较环节几乎无机会；Vine/早期评论计划是前提，可观察 30 天评价增速与份额关系。</td></tr>
    </table>
    <div class="note">注：「测试」「验证」类建议基于当前样本信号强度分级，需后续实验确认；当前数据不足以支持因果判断。</div>
  </div>
</section>
"""

JS_B = r"""
const CODES = ["A","B","C","D","E","F"];
const SHORT = {A:"A 祖母绿", B:"B 蓝波纹", C:"C 水立方", D:"D 鹅卵石2件", E:"E 纯黑", F:"F 透明波点"};
const PALETTE = ["#E8A33D","#2E9E8F","#3B6FB5","#C24B3F","#8A6FB0","#7A8CA8"];
function fig(id){ return document.getElementById(id); }

(function(){ const c=fig("fig_first_final"); if(!c)return; const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true},
  legend:{data:["首点（第一眼想点进）","兜底（全没买最终会买）"],bottom:0,textStyle:{fontSize:12}},
  grid:{left:10,right:20,top:14,bottom:44,containLabel:true},
  xAxis:{type:"category",data:["A","B","C"].map(k=>SHORT[k]),axisLabel:{fontSize:12}},
  yAxis:{type:"value",max:80,axisLabel:{formatter:"{value}%",fontSize:12}},
  series:[{name:"首点（第一眼想点进）",type:"bar",data:["A","B","C"].map(k=>DATA.journey.first_click[k]),barWidth:26,itemStyle:{color:"#3B6FB5"},label:{show:true,position:"top",formatter:function(p){return p.value+"%";},fontSize:12,fontWeight:"bold",color:"#33415C"}},
    {name:"兜底（全没买最终会买）",type:"bar",data:["A","B","C"].map(k=>DATA.journey.fallback[k]),barWidth:26,itemStyle:{color:"#E8A33D"},label:{show:true,position:"top",formatter:function(p){return p.value+"%";},fontSize:12,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_buy"); if(!c)return; const chart=echarts.init(c);
  const raw=DATA.journey.buy_decision;
  const labels={likely_buy:"倾向购买",undecided:"犹豫不决",not_buy:"不购买",buy_now:"立即购买"};
  const cols={likely_buy:"#2E9E8F",undecided:"#E8A33D",not_buy:"#C24B3F",buy_now:"#16233B"};
  chart.setOption({tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  legend:{bottom:0,textStyle:{fontSize:12}},
  series:[{type:"pie",radius:["38%","66%"],center:["50%","46%"],data:Object.keys(raw).map(k=>({name:labels[k],value:raw[k],itemStyle:{color:cols[k]}})),label:{fontSize:12,formatter:"{b} {d}%"},labelLine:{length:14,length2:8}}]});
})();

(function(){ const c=fig("fig_funnel"); if(!c)return; const chart=echarts.init(c);
  const stages=[
    {name:"搜索后看到 6 款产品", value:100},
    {name:"最想点进 A（首点）", value:65.5},
    {name:"点进后必看材质安全/评价", value:99.8},
    {name:"倾向购买", value:66.2},
    {name:"立即购买", value:0.7},
    {name:"退出后再看其他产品", value:99.7},
    {name:"转投 C", value:71.8},
    {name:"兜底选 C", value:72.5}
  ];
  chart.setOption({tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%（n=1000）";}},
  series:[{type:"funnel",left:"8%",right:"14%",top:10,bottom:16,minSize:"12%",maxSize:"100%",sort:"none",gap:2,
    label:{position:"inside",formatter:function(p){return p.name+"\n"+p.value+"%";},fontSize:12,color:"#fff"},
    data:stages.map(function(s,i){return {name:s.name,value:s.value,itemStyle:{color:["#16233B","#3B6FB5","#2E9E8F","#2E9E8F","#E8A33D","#C24B3F","#E8A33D","#E8A33D"][i]}};})}]});
})();

(function(){ const c=fig("fig_cross"); if(!c)return;
  const keys=["A","B","C"]; const cn={A:"A 祖母绿",B:"B 蓝波纹",C:"C 水立方"};
  const data=[]; keys.forEach(function(r){keys.forEach(function(k){data.push([k,r,DATA.journey.cross[r][k]]);});});
  const chart=echarts.init(c);
  chart.setOption({tooltip:{position:"top",formatter:function(p){return "首点 "+cn[p.value[1]]+" → 兜底 "+cn[p.value[0]]+"："+p.value[2]+"%";}},
  grid:{left:70,right:20,top:10,bottom:60,containLabel:false},
  xAxis:{type:"category",data:keys.map(k=>"兜底 "+cn[k]),splitArea:{show:true},axisLabel:{fontSize:12}},
  yAxis:{type:"category",data:keys.map(k=>"首点 "+cn[k]),splitArea:{show:true},axisLabel:{fontSize:12}},
  visualMap:{min:0,max:80,calculable:false,orient:"horizontal",left:"center",bottom:0,text:["80%","0%"],textStyle:{fontSize:11},inRange:{color:["#F7F8FA","#FBE3D5","#E8A33D"]}},
  series:[{type:"heatmap",data:data,label:{show:true,formatter:function(p){return p.value[2]+"%";},fontSize:12,fontWeight:"bold",color:"#16233B"}}]});
})();

(function(){ const c=fig("fig_why_a"); if(!c)return;
  const d=DATA.reasons.clickA; const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const p=ps[0];return p.name+"：提及 "+p.value+" 次（n=655）";}},
  grid:{left:10,right:44,top:10,bottom:20,containLabel:true}, xAxis:{type:"value",axisLabel:{fontSize:12}},
  yAxis:{type:"category",inverse:true,data:Object.keys(d),axisLabel:{fontSize:12}},
  series:[{type:"bar",data:Object.values(d),barWidth:22,itemStyle:{color:"#3B6FB5"},label:{show:true,position:"right",fontSize:12,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_info"); if(!c)return;
  const cn={material_safety:"材质/安全",reviews:"评价内容",specs:"规格尺寸",delivery:"配送信息",more_images:"更多图片",bullets:"五点描述",description:"长描述"};
  const d=DATA.journey.click_info; const keys=Object.keys(d).sort(function(a,b){return d[b]-d[a];});
  const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const p=ps[0];return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  grid:{left:10,right:46,top:10,bottom:20,containLabel:true}, xAxis:{type:"value",max:100,axisLabel:{formatter:"{value}%",fontSize:12}},
  yAxis:{type:"category",inverse:true,data:keys.map(k=>cn[k]||k),axisLabel:{fontSize:12}},
  series:[{type:"bar",data:keys.map(k=>({value:d[k],itemStyle:{color:d[k]>=90?"#E8A33D":"#3B6FB5"}})),barWidth:22,
    label:{show:true,position:"right",formatter:function(p){return p.value+"%";},fontSize:11.5,color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_notbuy"); if(!c)return;
  const d=DATA.reasons.notbuy; const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const p=ps[0];return p.name+"：提及 "+p.value+" 次（n=104）";}},
  grid:{left:10,right:44,top:10,bottom:20,containLabel:true}, xAxis:{type:"value",axisLabel:{fontSize:12}},
  yAxis:{type:"category",inverse:true,data:Object.keys(d),axisLabel:{fontSize:12}},
  series:[{type:"bar",data:Object.values(d),barWidth:22,itemStyle:{color:"#C24B3F"},label:{show:true,position:"right",fontSize:12,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_consider"); if(!c)return;
  const raw=DATA.journey.consider_other;
  const labels={yes:"会考虑",maybe:"可能会",no:"不会"};
  const cols={yes:"#2E9E8F",maybe:"#E8A33D",no:"#C24B3F"};
  const chart=echarts.init(c);
  chart.setOption({title:{text:"退出后是否考虑其他（n=1000）",left:"center",textStyle:{fontSize:14,color:"#16233B"}},
  tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  legend:{bottom:0,textStyle:{fontSize:11}},
  series:[{type:"pie",radius:["38%","64%"],center:["50%","45%"],data:Object.keys(raw).map(k=>({name:labels[k]||k,value:raw[k],itemStyle:{color:cols[k]||"#9FB0C8"}})),label:{fontSize:12,formatter:"{b} {d}%"}}]});
})();

(function(){ const c=fig("fig_switchc"); if(!c)return;
  const d=DATA.reasons.switchC; const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const p=ps[0];return p.name+"：提及 "+p.value+" 次（n=718）";}},
  grid:{left:10,right:44,top:10,bottom:20,containLabel:true}, xAxis:{type:"value",axisLabel:{fontSize:12}},
  yAxis:{type:"category",inverse:true,data:Object.keys(d),axisLabel:{fontSize:12}},
  series:[{type:"bar",data:Object.values(d),barWidth:22,itemStyle:{color:"#E8A33D"},label:{show:true,position:"right",fontSize:12,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_fallbackc"); if(!c)return;
  const d=DATA.reasons.fallbackC; const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const p=ps[0];return p.name+"：提及 "+p.value+" 次（n=725）";}},
  grid:{left:10,right:44,top:10,bottom:20,containLabel:true}, xAxis:{type:"value",axisLabel:{fontSize:12}},
  yAxis:{type:"category",inverse:true,data:Object.keys(d),axisLabel:{fontSize:12}},
  series:[{type:"bar",data:Object.values(d),barWidth:22,itemStyle:{color:"#2E9E8F"},label:{show:true,position:"right",fontSize:12,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_pagesearch"); if(!c)return;
  const d=DATA.journey.page_search; const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  legend:{bottom:0,textStyle:{fontSize:11}},
  series:[{type:"pie",radius:["38%","64%"],center:["50%","45%"],data:Object.keys(d).map(k=>({name:k.replace("page","第")+"页",value:d[k],itemStyle:{color:k==="page1"?"#3B6FB5":"#9FB0C8"}})),label:{fontSize:12,formatter:"{b} {d}%"}}]});
})();

(function(){ const c=fig("fig_overall"); if(!c)return;
  const cn={reviews:"评价内容",material:"材质",price_value:"价格/价值",rating:"评分",appearance:"外观",listing:"Listing 表达"};
  const d=DATA.journey.overall_factor; const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const p=ps[0];return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  grid:{left:10,right:44,top:10,bottom:20,containLabel:true}, xAxis:{type:"value",max:60,axisLabel:{formatter:"{value}%",fontSize:12}},
  yAxis:{type:"category",inverse:true,data:Object.keys(d).sort(function(a,b){return d[b]-d[a];}).map(k=>cn[k]||k),axisLabel:{fontSize:12}},
  series:[{type:"bar",data:Object.keys(d).sort(function(a,b){return d[b]-d[a];}).map(k=>({value:d[k],itemStyle:{color:k==="reviews"?"#E8A33D":"#3B6FB5"}})),barWidth:22,
    label:{show:true,position:"right",formatter:function(p){return p.value+"%";},fontSize:11.5,fontWeight:"bold",color:"#33415C"}}]});
})();
"""

def build_report(title, hero, core, did, chose, why, us, nxt, js, meta_line, total):
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title><style>{CSS}</style></head>
<body>
{hero}
{TOC}
<main>
{core}
{WHO_SEC}
{did}
{chose}
{why}
{us}
{nxt}
{PROD_SEC}
</main>
{FOOTER.replace("@TOTAL@", total).replace("@META@", meta_line)}
<script>{ECHARTS_JS}</script>
<script>
const DATA = {DATA_JSON};
{js}
{PROD_CARDS_JS}
</script>
</body></html>
"""

build_report(
    title="Amazon 美国站 · 浴帘内衬 6 款竞品 · 货架选择实验报告（n=1,000）",
    hero=HERO_A, core=CORE_A, did=DID_A, chose=CHOSE_A, why=WHY_A, us=US_A, nxt=NEXT_A, js=JS_A,
    meta_line="货架选择实验 n=1,000（26 题 · 0 错误）",
    total="货架选择实验（n=1,000）",
)
open(os.path.join(OUT_DIR, "shower_liner_choice_report.html"), "w").write(
    build_report(
        title="Amazon 美国站 · 浴帘内衬 6 款竞品 · 货架选择实验报告（n=1,000）",
        hero=HERO_A, core=CORE_A, did=DID_A, chose=CHOSE_A, why=WHY_A, us=US_A, nxt=NEXT_A, js=JS_A,
        meta_line="货架选择实验 n=1,000（26 题 · 0 错误）",
        total="货架选择实验（n=1,000）",
    )
)

open(os.path.join(OUT_DIR, "shower_liner_journey_report.html"), "w").write(
    build_report(
        title="Amazon 美国站 · 浴帘内衬 6 款竞品 · 决策旅程实验报告（n=1,000）",
        hero=HERO_B, core=CORE_B, did=DID_B, chose=CHOSE_B, why=WHY_B, us=US_B, nxt=NEXT_B, js=JS_B,
        meta_line="决策旅程实验 n=1,000（8 题 · 每题必答理由 · 0 错误）",
        total="决策旅程实验（n=1,000）",
    )
)
print("written: shower_liner_choice_report.html + shower_liner_journey_report.html")
