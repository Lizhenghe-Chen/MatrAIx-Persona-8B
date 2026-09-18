#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成两份「大白话·简单图表·编号对应」报告 v2：
1) shower_liner_choice_report.html   —— 实验一·货架选择（n=1000）
2) shower_liner_journey_report.html  —— 实验二·决策旅程（n=1000）
原则：语言通俗、只用横向条形/简单柱状/环形、商品用 ①②③④⑤⑥ 编号全篇统一、每个结论一句话说清。
"""
import base64, json, os, re

ROOT = "/Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B"
SUMMARY = os.path.join(ROOT, "results/shower-liner-6asin-experiment/shower_liner_summary.json")
ASSETS = os.path.join(ROOT, "results/shower-liner-6asin/assets")
OUT_DIR = os.path.join(ROOT, "results/shower-liner-6asin-experiment")
TOILET_REPORT = os.path.join(ROOT, "results/toilet-brush-top30-experiment/toilet_top30_experiment_report.html")

s = json.load(open(SUMMARY))

# 编号 | 中文名 | 品牌 | 价格 | 评分 | 评价 | 真实排名 | 一句话特征 —— 全报告统一口径
products = [
    dict(num="①", code="A", name="祖母绿", brand="AmazerBath", price="$18.99", rating="4.5★", reviews="4,156",
         rank="第 27 名", feat="最贵，但评价最多（4,156 条），页面显示配送受限、没有 Featured Offer",
         img="B0CGLZ56JC.jpg", share=60.0 if False else 20.8, asin="B0CGLZ56JC",
         link="https://www.amazon.com/dp/B0CGLZ56JC", status="配送受限", status_cls="warn",
         reject=[("价格太贵", "79.2%（792 人）"), ("外观不喜欢", "23.8%"), ("怕买不到/配送", "23.7%"), ("太透明", "18.0%")]),
    dict(num="②", code="B", name="蓝波纹", brand="jssablo", price="$7.19", rating="4.4★", reviews="1,872",
         rank="第 41 名", feat="便宜，评价多（1,872 条），正常现货",
         img="B0C9MCD5WL.jpg", share=17.9, asin="B0C9MCD5WL",
         link="https://www.amazon.com/dp/B0C9MCD5WL", status="现货", status_cls="ok",
         reject=[("外观不喜欢", "66.9%"), ("觉得太便宜不可信", "40.9%"), ("品牌不熟", "25.0%"), ("评分不够高", "19.2%")]),
    dict(num="③", code="C", name="水立方", brand="LQFMEHOT", price="$7.09", rating="4.6★", reviews="974",
         rank="第 124 名", feat="全场最便宜 + 评分最高（4.6★），正常现货，评价近千条",
         img="B0C2GTPSFR.jpg", share=60.0, asin="B0C2GTPSFR",
         link="https://www.amazon.com/dp/B0C2GTPSFR", status="现货", status_cls="ok",
         reject=[("品牌不熟", "36.0%"), ("觉得太便宜不可信", "25.7%"), ("外观不喜欢", "21.0%"), ("评价不够多", "18.6%")]),
    dict(num="④", code="D", name="鹅卵石", brand="Laumyasof", price="$9.99", rating="4.4★", reviews="16",
         rank="第 129 名", feat="2 件装，但评价只有 16 条（新上架），大家不敢买",
         img="B0GYWQQ2K3.jpg", share=0.0, asin="B0GYWQQ2K3",
         link="https://www.amazon.com/dp/B0GYWQQ2K3", status="现货·新品", status_cls="warn",
         reject=[("评价太少", "98.2%"), ("怀疑材质", "82.1%"), ("不想要2件装", "45.5%"), ("外观不喜欢", "8.6%")]),
    dict(num="⑤", code="E", name="纯黑", brand="Dependable", price="$9.99", rating="4.3★", reviews="116",
         rank="第 203 名", feat="黑色无花纹基础款，评价不多（116 条），只剩 10 件",
         img="B0D212C4XS.jpg", share=1.3, asin="B0D212C4XS",
         link="https://www.amazon.com/dp/B0D212C4XS", status="仅剩 10 件", status_cls="warn",
         reject=[("外观不喜欢", "92.5%"), ("怕没货/配送", "59.6%"), ("评价太少", "46.6%"), ("评分不够高", "20.7%")]),
    dict(num="⑥", code="F", name="波点", brand="MuuXii", price="无价", rating="4.4★", reviews="10",
         rank="第 856 名", feat="页面显示「暂时缺货」，没有价格，评价只有 10 条",
         img="B0FSRN9YTK.jpg", share=0.0, asin="B0FSRN9YTK",
         link="https://www.amazon.com/dp/B0FSRN9YTK", status="缺货", status_cls="bad",
         reject=[("评价太少", "96.7%"), ("缺货/配送", "89.7%"), ("尺寸不合适", "31.0%"), ("太透明", "4.5%")]),
]

def b64(path):
    with open(path, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()

for p in products:
    p["img_b64"] = b64(os.path.join(ASSETS, p["img"]))
    p["label"] = p["num"] + " " + p["name"]          # 图表/正文统一叫法，如「③ 水立方」
    p["label_full"] = f'{p["num"]} {p["name"]}（{p["brand"]}）'

toilet_html = open(TOILET_REPORT).read()
m = re.search(r"<script>(\s*/\*.*?Licensed to the Apache.*?)</script>", toilet_html, re.S)
ECHARTS_JS = m.group(1) if m else ""

c = s["choice"]; j = s["journey"]
DATA = {
    "products": products,
    "choice": {
        "share": c["share_pct"], "page_buy": c["page_buy_pct"],
        "factor_most": c["factor_most_pct"], "importance": c["importance_mean_1to5"],
        "redline": c["redline_pct"], "switch_trigger": c["switch_trigger_pct"],
        "badge_effect": c["badge_effect_pct"], "price_accept_mean": c["price_accept_mean"],
    },
    "journey": {
        "first_click": j["first_click_pct"], "click_info": j["click_info_pct"],
        "buy_decision": j["buy_decision_pct"], "consider_other": j["consider_other_pct"],
        "next_choice": j["next_choice_pct"], "fallback": j["fallback_pct"],
        "page_search": j["page_search_pct"], "overall_factor": j["overall_factor_pct"],
        "buy_yes": j["buy_yes_pct"],
    },
    "reasons": {
        "clickA": {"外观好看、高级": 2187, "有磁吸/配重": 860, "评价多": 793, "材质安全": 717, "品牌可信": 621},
        "fallbackC": {"材质安全": 1175, "评分高": 1037, "有磁吸/配重": 943, "价格便宜": 887, "评价多": 857},
        "switchC": {"评分高": 1102, "外观好看": 706, "评价多": 608, "价格便宜": 607, "有现货": 376},
        "notbuy": {"担心缺货/配送": 140, "价格不值": 36, "外观不喜欢": 19, "担心材质": 16},
    },
    "quotes": {
        "first_click": j["sample_first_click_reasons"],
        "fallback": j["sample_fallback_reasons"],
        "buy": j["sample_buy_reasons"],
    },
}
DATA_JSON = json.dumps(DATA, ensure_ascii=False)

CSS = r"""
:root { --ink:#16233B; --paper:#F7F8FA; --card:#FFFFFF; --line:#E3E7EE; --text:#22303F; --muted:#64748B; --amber:#E8A33D; --teal:#2E9E8F; --red:#C24B3F; --blue:#3B6FB5; }
* { box-sizing:border-box; }
body { margin:0; font-family:"Noto Sans SC","PingFang SC","Microsoft YaHei",system-ui,sans-serif; background:var(--paper); color:var(--text); line-height:1.75; font-size:15px; }
h1,h2,h3,h4 { font-family:"Noto Serif SC","Songti SC","STSong",Georgia,serif; margin:0; }
header.hero { background:var(--ink); color:#fff; padding:50px 24px 42px; }
.hero-inner { max-width:1120px; margin:0 auto; }
.hero .kicker { font-size:12px; letter-spacing:.12em; color:var(--amber); font-weight:600; }
.hero h1 { font-size:clamp(22px,3vw,34px); font-weight:900; line-height:1.3; margin:10px 0 8px; }
.hero .sub { font-size:14.5px; color:#C8D3E3; max-width:900px; margin-bottom:16px; }
.meta-chips span { display:inline-block; border:1px solid rgba(255,255,255,.22); border-radius:999px; padding:4px 12px; font-size:12px; color:#E6ECF5; background:rgba(255,255,255,.06); margin:0 6px 6px 0; }
.kpi-row { display:grid; grid-template-columns:repeat(auto-fit,minmax(175px,1fr)); gap:10px; margin-top:18px; }
.kpi { background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.15); border-radius:12px; padding:12px 14px; }
.kpi .lbl { font-size:12px; color:#B9C6DA; }
.kpi .v { font-family:"Noto Serif SC",serif; font-size:21px; font-weight:700; color:var(--amber); margin-top:2px; }
.kpi .s { font-size:11.5px; color:#8FA0BC; margin-top:2px; }
nav.toc { position:sticky; top:0; z-index:50; background:#fff; border-bottom:1px solid var(--line); }
.toc-inner { max-width:1120px; margin:0 auto; display:flex; gap:2px; overflow-x:auto; padding:0 8px; }
nav.toc a { padding:12px 12px; font-size:13px; color:var(--muted); text-decoration:none; white-space:nowrap; border-bottom:2px solid transparent; }
nav.toc a:hover { color:var(--ink); border-bottom-color:var(--amber); }
main { max-width:1120px; margin:0 auto; padding:28px 18px 60px; }
section { margin-top:40px; }
.sec-head { display:flex; align-items:baseline; gap:10px; margin-bottom:6px; }
.sec-no { font-family:"Noto Serif SC",serif; font-size:14px; font-weight:700; color:var(--amber); letter-spacing:.05em; }
.sec-head h2 { font-size:21px; font-weight:800; color:var(--ink); }
.sec-desc { color:var(--muted); font-size:13.5px; margin-bottom:18px; max-width:920px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px 20px; margin-bottom:14px; }
.card h3 { font-size:16px; color:var(--ink); margin-bottom:6px; }
.card .fig { width:100%; height:380px; }
.card .fig.sm { height:320px; }
.card .takeaway { font-size:14px; color:#33415C; background:#F4F7FB; border-left:3px solid var(--amber); padding:8px 14px; border-radius:0 8px 8px 0; margin-top:10px; }
.card .takeaway b { color:var(--ink); }
.grid2 { display:grid; grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); gap:14px; }
.hl-banner { background:linear-gradient(120deg,#16233B 0%,#1D2E4F 55%,#26406B 100%); border-radius:18px; padding:26px 26px 20px; }
.hl-banner h2 { color:#fff; font-size:19px; }
.hl-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(270px,1fr)); gap:12px; margin-top:14px; }
.hl-card { background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.12); border-radius:12px; padding:13px 14px 11px; }
.hl-card .n { font-family:"Noto Serif SC",serif; font-size:17px; font-weight:800; color:var(--amber); line-height:1.25; }
.hl-card p { color:#DDE5F2; font-size:13.5px; margin:6px 0 0; }
.hl-card .ev { color:#9FB3D0; font-size:12px; margin-top:6px; }
table { width:100%; border-collapse:collapse; font-size:13.5px; }
th, td { border-bottom:1px solid var(--line); padding:8px 9px; text-align:left; vertical-align:top; }
th { background:#F2F5F9; font-weight:600; color:var(--ink-2); }
.prod-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(330px,1fr)); gap:14px; }
.prod-card { background:var(--card); border:1px solid var(--line); border-radius:14px; overflow:hidden; display:flex; flex-direction:column; }
.prod-card .ph { position:relative; aspect-ratio:1/1; background:#EEF1F5; }
.prod-card .ph img { width:100%; height:100%; object-fit:cover; }
.prod-card .ph .no { position:absolute; top:10px; left:10px; background:rgba(22,35,59,.9); color:#fff; width:34px; height:34px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:17px; font-weight:700; }
.prod-card .ph .share { position:absolute; top:10px; right:10px; background:var(--amber); color:#16233B; font-weight:700; font-size:13px; padding:3px 10px; border-radius:999px; }
.prod-card .bd { padding:13px 15px 15px; display:flex; flex-direction:column; gap:6px; flex:1; }
.prod-card .bd .pname { font-size:16px; font-weight:700; color:var(--ink); }
.prod-card .bd .meta { font-size:12.5px; color:var(--muted); }
.prod-card .bd .feat { font-size:13px; color:#33415C; }
.prod-card .bd .status { font-size:12.5px; font-weight:700; }
.prod-card .bd .status.ok { color:var(--teal); } .prod-card .bd .status.warn { color:#B07A1A; } .prod-card .bd .status.bad { color:var(--red); }
.prod-card .bd a { font-size:12px; color:var(--blue); text-decoration:none; word-break:break-all; }
.quick-table td:first-child { font-weight:700; color:var(--ink); white-space:nowrap; }
.tag-do { display:inline-block; background:#E4F3F0; color:#1D6B5F; font-size:12px; font-weight:700; padding:2px 10px; border-radius:999px; }
.tag-try { display:inline-block; background:#FFF4E0; color:#9A6B12; font-size:12px; font-weight:700; padding:2px 10px; border-radius:999px; }
.tag-watch { display:inline-block; background:#E8EEFB; color:#2D5BA8; font-size:12px; font-weight:700; padding:2px 10px; border-radius:999px; }
.tag-good { display:inline-block; background:#E4F3F0; color:#1D6B5F; font-size:12px; font-weight:700; padding:2px 10px; border-radius:999px; }
.tag-fix { display:inline-block; background:#FBE9E5; color:#A43C30; font-size:12px; font-weight:700; padding:2px 10px; border-radius:999px; }
.tag-tell { display:inline-block; background:#E8EEFB; color:#2D5BA8; font-size:12px; font-weight:700; padding:2px 10px; border-radius:999px; }
.tag-test { display:inline-block; background:#FFF4E0; color:#9A6B12; font-size:12px; font-weight:700; padding:2px 10px; border-radius:999px; }
.quote { border-left:3px solid var(--amber); background:#FBF7EF; padding:11px 15px; margin:9px 0; font-size:13px; color:#4A5568; border-radius:0 8px 8px 0; }
.quote .src { color:var(--muted); font-size:11.5px; margin-top:5px; }
.callout { background:#F0F6F4; border:1px solid #CFE3DD; border-radius:12px; padding:12px 16px; font-size:14px; color:#24453F; margin:8px 0; }
.footer { border-top:1px solid var(--line); margin-top:52px; padding:22px 18px 32px; text-align:center; color:var(--muted); font-size:12.5px; }
@media (max-width:720px) { main { padding:18px 12px 48px; } .card .fig { height:320px; } .grid2, .prod-grid { grid-template-columns:1fr; } }
"""

# ============ 产品速查表（两报告共用） ============
QUICK_TABLE = """
<section id="s_products" style="margin-top:26px;">
  <div class="card"><h3>先认识这 6 款产品（编号全篇通用，方便对照）</h3>
    <table class="quick-table">
      <tr><th>编号</th><th>产品</th><th>品牌</th><th>价格</th><th>评分</th><th>评价数</th><th>真实排名</th><th>一句话特征</th></tr>
      @ROWS@
    </table>
    <div style="font-size:12.5px;color:var(--muted);margin-top:8px;">数据采集时间：2026-09-17（Amazon 美国站实时页面）。后面所有图表里的「①祖母绿」「③水立方」都指上面这一行。</div>
  </div>
</section>
"""
QUICK_ROWS = "".join(
    f'<tr><td>{p["num"]}</td><td>{p["name"]}</td><td>{p["brand"]}</td><td>{p["price"]}</td><td>{p["rating"]}</td><td>{p["reviews"]}</td><td>{p["rank"]}</td><td>{p["feat"]}</td></tr>'
    for p in products)

TOC = """<nav class="toc"><div class="toc-inner"><a href="#s0">先看结论</a><a href="#s_products">认识 6 款产品</a><a href="#s1">测试的是谁</a><a href="#s2">测试怎么做的</a><a href="#s3">结果：谁赢谁输</a><a href="#s4">原因：为什么</a><a href="#s5">对卖家的启示</a><a href="#s6">建议怎么做</a><a href="#s7">产品详情</a></div></nav>"""

FOOTER = """<div class="footer">@TITLE@ · @TOTAL@<br>@META@ · 聚合时间 2026-09-17 · 所有数字均来自原始答卷，可追溯核对</div>"""

# ================================================================
# 报告一：货架选择
# ================================================================
HERO_A = """
<header class="hero"><div class="hero-inner">
  <div class="kicker">AMAZON US · 浴帘内衬 · 实验一：货架选择</div>
  <h1>6 款浴帘内衬，1000 位买家会选哪个？</h1>
  <div class="sub">让 1000 位模拟买家在亚马逊搜索结果的货架上挑选浴帘内衬：选 1 款、说明理由、并说出为什么不要其他 5 款。下面用最简单的图告诉你——谁卖得最好、为什么、以及商品页面哪里最影响下单。</div>
  <div class="meta-chips"><span>参加人数：1,000 位</span><span>问了 26 道题</span><span>6 款真实在售商品</span><span>运行无错误</span></div>
  <div class="kpi-row">
    <div class="kpi"><div class="lbl">大家最想买</div><div class="v">③ 水立方</div><div class="s">60.0% 人选它（$7.09）</div></div>
    <div class="kpi"><div class="lbl">排第二、第三</div><div class="v">①祖母绿 20.8%</div><div class="s">②蓝波纹 17.9%</div></div>
    <div class="kpi"><div class="lbl">只在第 1 页购买</div><div class="v">97.7%</div><div class="s">排不进首页 = 没生意</div></div>
    <div class="kpi"><div class="lbl">最看重什么</div><div class="v">价格 + 评价</div><div class="s">价格第一（52.2%），评价第二</div></div>
  </div>
</div></header>
"""

CORE_A = """
<section id="s0">
<div class="hl-banner"><h2>先看结论（5 句话）</h2>
  <div class="hl-grid">
    <div class="hl-card"><div class="n">① 赢家是「③ 水立方」</div><p>又便宜（$7.09）评分又最高（4.6★），六成人选它。便宜 + 口碑好，就是买家最吃的组合。</p><div class="ev">数据：60.0% 人选它（n=1000）</div></div>
    <div class="hl-card"><div class="n">② 排名靠前 ≠ 大家想买</div><p>③ 水立方在亚马逊真实排名只排第 124 名（6 款里算靠后），却是大家的首选；真实排名第一的 ① 祖母绿（第 27 名）只有 20.8% 人选。</p><div class="ev">数据：真实排名 vs 模拟首选</div></div>
    <div class="hl-card"><div class="n">③ 买家不买，主要是 4 个原因</div><p>太贵（①被79%的人拒绝）、不好看（②被67%、⑤被93%的人拒绝）、评价太少（④⑥被96%+拒绝）、怕没货（⑤⑥被拒）。</p><div class="ev">数据：每款拒绝原因统计</div></div>
    <div class="hl-card"><div class="n">④ 商品页最要紧的 3 样</div><p>评价内容（4.88/5）、价格展示（4.55）、主图（4.32）。A+ 图文页最不重要（1.99/5）。</p><div class="ev">数据：8 项页面要素重要性打分</div></div>
    <div class="hl-card"><div class="n">⑤ 一句话建议</div><p>先把「缺货、材质不明、图片模糊、没标价格」这四个硬伤补上（90%+ 的人会直接放弃）；再想办法把评分做到 4.6 以上——评分高 0.1 分，就有 64.9% 的人愿意改选你。</p><div class="ev">数据：切换诱因 64.9%</div></div>
  </div>
</div>
</section>
"""

DID_A = """
<section id="s2">
  <div class="sec-head"><span class="sec-no">2</span><h2>测试怎么做的</h2></div>
  <div class="sec-desc">让 1,000 位模拟买家「逛货架」，就像在亚马逊搜索「浴帘内衬」后看到的页面一样。</div>
  <div class="card">
    <div class="callout">每位买家依次完成：<b>① 从 6 款里选 1 款并说理由 → ② 没选的 5 款，每款都要说出为什么不要 → ③ 商品排在第几页还愿意看/买 → ④ 给商品页 8 个部分的重要程度打分 → ⑤ 回答哪些情况会直接不买</b></div>
    <p style="font-size:13.5px;margin:10px 0 0;color:var(--muted);">观察的是「静态货架」上的第一选择：不加广告、不靠排名提示，纯看商品本身（价格、评分、评价数、图片、描述）谁更能打动买家。多选题的百分比 = 选的人数 ÷ 1000。</p>
  </div>
</section>
"""

CHOSE_A = """
<section id="s3">
  <div class="sec-head"><span class="sec-no">3</span><h2>结果：谁赢谁输</h2></div>
  <div class="sec-desc">一张图看懂 6 款产品的「首选比例」。1000 位买家每人选 1 款。</div>
  <div class="card"><h3>大家第一选择的比例（每人只选一款）</h3>
    <div class="fig sm" id="fig_share"></div>
    <div class="takeaway"><b>一句话：</b>③ 水立方一家拿走 60%；① 祖母绿和 ② 蓝波纹各拿两成左右；④ 鹅卵石、⑥ 波点没人选，⑤ 纯黑只有 1.3%。</div>
  </div>
  <div class="card"><h3>真实排名 vs 大家的选择（排得靠前，不代表大家想买）</h3>
    <div class="fig sm" id="fig_rank"></div>
    <div class="takeaway"><b>一句话：</b>亚马逊真实排名最靠前的是 ① 祖母绿（第 27 名），但大家首选最多的是 ③ 水立方（真实排名只到第 124 名）。<b>真实排名是「销量+流量」算出来的，不完全等于「买家真的想要」。</b></div>
  </div>
  <div class="card"><h3>购买意向与价格接受度</h3>
    <div class="grid2">
      <div class="fig sm" id="fig_intent"></div>
      <div class="fig sm" id="fig_price"></div>
    </div>
    <div class="takeaway"><b>一句话：</b>83.4% 的买家给「购买意向」打了 4 分（满分 5）；79.9% 的人完全接受 $7~$10 这个价位。真正「价格失血」的只有 ① 祖母绿的 $18.99。</div>
  </div>
</section>
"""

WHY_A = """
<section id="s4">
  <div class="sec-head"><span class="sec-no">4</span><h2>原因：为什么选、为什么不选</h2></div>
  <div class="sec-desc">下面是每个问题的原因，全部来自买家自己写的话和勾选的选项。</div>

  <div class="card"><h3>不选每款商品的原因（每款列出被拒绝最多的 4 个理由）</h3>
    <table>
      <tr><th style="width:120px;">商品</th><th>买家不选它的主要原因（占比 = 选了该原因的人数 ÷ 1000）</th></tr>
      @REJECT_ROWS@
    </table>
    <div class="takeaway"><b>一句话：</b>④⑤⑥ 主要死在「评价太少 / 缺货」；②⑤ 主要死在「外观」；① 主要死在「价格太贵」。<b>每款商品的死因都很明确，改起来就知道往哪使劲。</b></div>
  </div>

  <div class="card"><h3>买浴帘时，最看重什么（第一重要的因素）</h3>
    <div class="fig sm" id="fig_factor"></div>
    <div class="takeaway"><b>一句话：</b>五成以上买家把「价格/价值」排第一，其次「评价内容」「评分」——<b>又便宜、口碑又好，就是购买核心。</b></div>
  </div>

  <div class="card"><h3>商品页 8 个部分，哪个最重要（5 分制打分）</h3>
    <div class="fig sm" id="fig_importance"></div>
    <div class="takeaway"><b>一句话：</b>买家最看重「评价内容」（4.88）、「价格展示」（4.55）、「主图」（4.32）；A+ 图文页最不被看重（1.99）。<b>做页面的钱，先花在评价、价格、主图上。</b></div>
  </div>

  <div class="card"><h3>哪些情况会让买家直接不买（一票否决）</h3>
    <div class="fig sm" id="fig_redline"></div>
    <div class="takeaway"><b>一句话：</b>「缺货」100% 的人直接放弃；「材质不明」97.3%、「图片模糊」94.0%、「没标价格」91.6%。<b>这四条是及格线，不达标连被比较的机会都没有。</b></div>
  </div>

  <div class="card"><h3>愿意翻到第几页购买</h3>
    <div class="fig sm" id="fig_page"></div>
    <div class="takeaway"><b>一句话：</b>97.7% 的买家只在第 1 页购买——<b>进不了搜索结果第一页，基本等于没有生意。</b></div>
  </div>

  <div class="card"><h3>什么情况会让买家改主意（换一家买）</h3>
    <div class="fig sm" id="fig_switch"></div>
    <div class="takeaway"><b>一句话：</b>64.9% 的买家说「如果别家评分更高，我就换」——<b>评分 4.4 和 4.6 之间，差的就是订单。</b></div>
  </div>
</section>
"""

US_A = """
<section id="s5">
  <div class="sec-head"><span class="sec-no">5</span><h2>对卖家的启示：谁赢在哪、输在哪</h2></div>
  <div class="sec-desc">6 款都是市场上真实在卖的商品，没有预设「我方」。按「做得好的 / 要改进的 / 没被发现的亮点 / 值得试试的」四个标签看每款。</div>
  <div class="grid2">
    <div class="card"><h3>③ 水立方 —— 本场赢家</h3>
      <p><span class="tag-good">做得好的</span> 最便宜 + 评分最高，这套组合被验证是货架最优解：60% 首选、72.5% 兜底。</p>
      <p><span class="tag-fix">要改进的</span> 唯一短板是「品牌不熟」（36% 人提）。</p>
      <p><span class="tag-tell">没被发现的亮点</span> 它的花纹其实挺好看（首点第二），但主图没突出质感。</p>
    </div>
    <div class="card"><h3>① 祖母绿 —— 吸引眼球，但太贵</h3>
      <p><span class="tag-good">做得好的</span> 评价最多（4,156 条）+ 高级感外观，65.5% 的人第一眼想点它。</p>
      <p><span class="tag-fix">要改进的</span> 79.2% 的人因「太贵」放弃；页面还显示配送受限。</p>
      <p><span class="tag-test">值得试试的</span> 主打「2 合 1 省钱、耐用」的价值故事，或做降价变体，把眼球变成订单。</p>
    </div>
    <div class="card"><h3>② 蓝波纹 —— 性价比不错，输在外观</h3>
      <p><span class="tag-good">做得好的</span> $7.19 + 1,872 条评价，拿到 17.9% 份额，是很多人的第二选择。</p>
      <p><span class="tag-fix">要改进的</span> 66.9% 的人觉得外观不好看；40.9% 觉得「太便宜不可信」。</p>
    </div>
    <div class="card"><h3>⑤ 纯黑 —— 外观和库存双输</h3>
      <p><span class="tag-fix">要改进的</span> 92.5% 的人觉得黑色无花纹不好看；只剩 10 件也让 59.6% 的人不敢买。</p>
      <p><span class="tag-test">值得试试的</span> 只有 1.3% 的人选它，样本太小，不能说「黑色浴帘没市场」，但方向确实不乐观。</p>
    </div>
    <div class="card"><h3>④ 鹅卵石 —— 新品的信任难关</h3>
      <p><span class="tag-fix">要改进的</span> 评价只有 16 条，98.2% 的人因评价太少拒绝——<b>新品起步最难的就是让人敢买</b>。</p>
      <p><span class="tag-try">先试试</span> 2 件装 $9.99 让人怀疑材质，可以先从「单件低价」积累评价。</p>
    </div>
    <div class="card"><h3>⑥ 波点 —— 缺货就没有一切</h3>
      <p><span class="tag-fix">要改进的</span> 页面显示缺货、没价格、评价只有 10 条——0% 的人选它。</p>
      <p style="font-size:12.5px;color:var(--muted);">注：缺货商品被 100% 的人一票否决，它的数据不能代表真实市场表现。</p>
    </div>
  </div>
</section>
"""

NEXT_A = """
<section id="s6">
  <div class="sec-head"><span class="sec-no">6</span><h2>建议怎么做（按把握大小排序）</h2></div>
  <div class="card">
    <table>
      <tr><th style="width:90px;">把握</th><th style="width:190px;">做什么</th><th>为什么 / 依据</th></tr>
      <tr><td><span class="tag-do">马上做</span></td><td><b>补上 4 条及格线</b></td><td>缺货、材质不明、图片模糊、没标价格，90%+ 的人会直接放弃。先保证「有货、材质说清、图清晰、价格醒目」。</td></tr>
      <tr><td><span class="tag-do">马上做</span></td><td><b>把评分做到 4.6 以上</b></td><td>64.9% 的人会因评分更高而换选；③（4.6★）vs ②（4.4★）同价位，份额是 60% vs 17.9%。做好评激励和售后。</td></tr>
      <tr><td><span class="tag-try">试试看</span></td><td><b>验证「徽章」的真实效果</b></td><td>91.1% 的人说徽章（Best Seller 等）会影响选择，但「嘴上说」不等于「真下单」，建议小范围 A/B 测试。</td></tr>
      <tr><td><span class="tag-try">试试看</span></td><td><b>新品先攒评价</b></td><td>评价少于 50 条的产品 82%+ 被直接淘汰。新品先用 Vine 评论计划 + 低价跑量把评价数冲到 200+。</td></tr>
      <tr><td><span class="tag-try">试试看</span></td><td><b>① 祖母绿讲「价值故事」</b></td><td>65.5% 的人第一眼想点它，但 79.2% 被价格劝退。试试主打「2 合 1 省一件 + 更耐用」，让 $18.99 显得值。</td></tr>
      <tr><td><span class="tag-watch">先观望</span></td><td><b>A+ 图文页先别投钱</b></td><td>重要性只有 1.99/5（垫底），买家基本不靠它做决定。钱先花在评价、价格、主图上。</td></tr>
    </table>
    <div style="font-size:12.5px;color:var(--muted);margin-top:8px;">注：「试试看」的建议来自本次数据的信号，需要再做实验验证；本次数据还不能直接证明「改了价格就一定提升销量」。</div>
  </div>
</section>
"""

JS_A = """
const CODES = ["A","B","C","D","E","F"];
const LBL = {A:"① 祖母绿", B:"② 蓝波纹", C:"③ 水立方", D:"④ 鹅卵石", E:"⑤ 纯黑", F:"⑥ 波点"};
const RANK = {A:27, B:41, C:124, D:129, E:203, F:856};
function fig(id){ return document.getElementById(id); }

(function(){ const c=fig("fig_share"); if(!c)return; const chart=echarts.init(c);
  const order=["C","A","B","E","D","F"];
  chart.setOption({tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  grid:{left:10,right:44,top:10,bottom:20,containLabel:true}, xAxis:{type:"value",max:70,axisLabel:{formatter:"{value}%",fontSize:13}},
  yAxis:{type:"category",inverse:true,data:order.map(k=>LBL[k]),axisLabel:{fontSize:14}},
  series:[{type:"bar",data:order.map(k=>({value:DATA.choice.share[k]||0,itemStyle:{color:k==="C"?"#E8A33D":"#9FB0C8"}})),barWidth:28,
    label:{show:true,position:"right",formatter:function(p){return p.value+"%";},fontSize:14,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_rank"); if(!c)return; const chart=echarts.init(c);
  const order=["A","B","C","D","E","F"];
  chart.setOption({tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"<br/>真实排名："+RANK[p.dataIndex]+" 名<br/>首选比例："+(DATA.choice.share[p.dataIndex]||0)+"%";}},
  grid:{left:10,right:20,top:14,bottom:20,containLabel:true},
  xAxis:{type:"category",data:order.map(k=>LBL[k]),axisLabel:{fontSize:13,interval:0}},
  yAxis:{type:"value",max:100,axisLabel:{formatter:"{value}%",fontSize:13}},
  series:[{type:"bar",data:order.map(k=>DATA.choice.share[k]||0),barWidth:34,
    itemStyle:{color:function(p){return p.dataIndex===2?"#E8A33D":"#3B6FB5";}},
    label:{show:true,position:"top",formatter:function(p){return (p.value||0)+"%";},fontSize:13,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_intent"); if(!c)return; const chart=echarts.init(c);
  chart.setOption({title:{text:"购买意向（满分 5 分，n=1000）",left:"center",textStyle:{fontSize:14,color:"#16233B"}},
  tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  legend:{bottom:0,textStyle:{fontSize:12}},
  series:[{type:"pie",radius:["40%","66%"],center:["50%","45%"],data:[
    {name:"5 分：很可能买",value:14.7,itemStyle:{color:"#2E9E8F"}},{name:"4 分：想买",value:83.4,itemStyle:{color:"#3B6FB5"}},{name:"3 分：一般",value:1.9,itemStyle:{color:"#E8A33D"}}],
    label:{fontSize:12,formatter:"{b} {d}%"}}]});
})();

(function(){ const c=fig("fig_price"); if(!c)return; const chart=echarts.init(c);
  chart.setOption({title:{text:"价格接受度（满分 5 分，n=1000）",left:"center",textStyle:{fontSize:14,color:"#16233B"}},
  tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  legend:{bottom:0,textStyle:{fontSize:12}},
  series:[{type:"pie",radius:["40%","66%"],center:["50%","45%"],data:[
    {name:"5 分：完全接受",value:79.9,itemStyle:{color:"#2E9E8F"}},{name:"4 分：基本接受",value:18.4,itemStyle:{color:"#3B6FB5"}},{name:"3 分：勉强",value:1.7,itemStyle:{color:"#E8A33D"}}],
    label:{fontSize:12,formatter:"{b} {d}%"}}]});
})();

(function(){ const c=fig("fig_factor"); if(!c)return;
  const cn={price_value:"价格/价值",reviews:"评价内容",rating:"评分",material:"材质",magnet:"磁吸配重",appearance:"外观"};
  const d=DATA.choice.factor_most; const order=Object.keys(d).sort(function(a,b){return d[b]-d[a];});
  const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const p=ps[0];return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  grid:{left:10,right:44,top:10,bottom:20,containLabel:true}, xAxis:{type:"value",max:60,axisLabel:{formatter:"{value}%",fontSize:13}},
  yAxis:{type:"category",inverse:true,data:order.map(k=>cn[k]),axisLabel:{fontSize:14}},
  series:[{type:"bar",data:order.map(k=>({value:d[k],itemStyle:{color:k==="price_value"?"#E8A33D":"#3B6FB5"}})),barWidth:24,
    label:{show:true,position:"right",formatter:function(p){return p.value+"%";},fontSize:13,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_importance"); if(!c)return;
  const cn={reviews:"评价内容",price:"价格展示",image:"主图",trust:"信任标识",attr:"属性表",title:"标题",bullets:"五点描述",aplus:"A+ 图文页"};
  const d=DATA.choice.importance; const order=Object.keys(d).sort(function(a,b){return d[b]-d[a];});
  const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const p=ps[0];return p.name+"：均分 "+p.value+" / 5";}},
  grid:{left:10,right:48,top:10,bottom:20,containLabel:true}, xAxis:{type:"value",max:5,axisLabel:{fontSize:13}},
  yAxis:{type:"category",inverse:true,data:order.map(k=>cn[k]),axisLabel:{fontSize:14}},
  series:[{type:"bar",data:order.map(k=>({value:d[k],itemStyle:{color:k==="aplus"?"#C6CFDC":(k==="reviews"?"#E8A33D":"#3B6FB5")}})),barWidth:22,
    label:{show:true,position:"right",formatter:function(p){return p.value.toFixed(2);},fontSize:13,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_redline"); if(!c)return;
  const cn={unavailable:"缺货",material_unclear:"材质不明",blur_image:"图片模糊",no_price:"没标价格",no_size:"没标尺寸",low_rating:"评分低",few_reviews:"评价太少",no_bullets:"没有五点描述",brand_unfamiliar:"品牌不熟",none:"都没有"};
  const d=DATA.choice.redline; const order=Object.keys(d).filter(k=>d[k]>0).sort(function(a,b){return d[b]-d[a];});
  const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const p=ps[0];return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  grid:{left:10,right:48,top:10,bottom:20,containLabel:true}, xAxis:{type:"value",max:100,axisLabel:{formatter:"{value}%",fontSize:13}},
  yAxis:{type:"category",inverse:true,data:order.map(k=>cn[k]),axisLabel:{fontSize:14}},
  series:[{type:"bar",data:order.map(k=>({value:d[k],itemStyle:{color:d[k]>=90?"#C24B3F":(d[k]>=60?"#E8A33D":"#9FB0C8")}})),barWidth:22,
    label:{show:true,position:"right",formatter:function(p){return p.value+"%";},fontSize:12.5,color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_page"); if(!c)return;
  const d=DATA.choice.page_buy; const keys=Object.keys(d);
  const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  grid:{left:10,right:20,top:14,bottom:20,containLabel:true},
  xAxis:{type:"category",data:keys.map(k=>k.replace("page","第")+"页"),axisLabel:{fontSize:14}},
  yAxis:{type:"value",max:100,axisLabel:{formatter:"{value}%",fontSize:13}},
  series:[{type:"bar",data:keys.map(k=>d[k]||0),barWidth:44,itemStyle:{color:function(p){return p.dataIndex===0?"#E8A33D":"#9FB0C8";}},
    label:{show:true,position:"top",formatter:function(p){return p.value+"%";},fontSize:14,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_switch"); if(!c)return;
  const cn={better_rating:"别家评分更高",better_function:"别家功能更好",lower_price:"别家更便宜",better_value:"别家更划算",nothing:"都不会换",better_look:"别家更好看"};
  const d=DATA.choice.switch_trigger; const order=["better_rating","better_function","lower_price","better_value","nothing","better_look"];
  const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  legend:{bottom:0,textStyle:{fontSize:11}},
  series:[{type:"pie",radius:["38%","64%"],center:["50%","44%"],data:order.map(k=>({name:cn[k],value:d[k]||0})),label:{fontSize:11.5,formatter:"{b} {d}%"}}]});
})();
"""

# ================================================================
# 报告二：决策旅程
# ================================================================
HERO_B = """
<header class="hero"><div class="hero-inner">
  <div class="kicker">AMAZON US · 浴帘内衬 · 实验二：决策旅程</div>
  <h1>从看到搜索页到买下，1000 位买家经历了什么？</h1>
  <div class="sub">1000 位模拟买家完整走一遍「搜索 → 第一眼点谁 → 点进后看什么 → 买不买 → 要不要看别的 → 最后买谁」的流程，每走一步都说明理由。用最直白的图告诉你，流量是怎么进来的、又是在哪一步流失的。</div>
  <div class="meta-chips"><span>参加人数：1,000 位</span><span>8 步决策，每步都要说理由</span><span>6 款真实在售商品</span><span>运行无错误</span></div>
  <div class="kpi-row">
    <div class="kpi"><div class="lbl">第一眼最想点</div><div class="v">① 祖母绿 65.5%</div><div class="s">外观高级 + 评价最多</div></div>
    <div class="kpi"><div class="lbl">点进后必看</div><div class="v">材质安全 99.8%</div><div class="s">评价内容 99.5%</div></div>
    <div class="kpi"><div class="lbl">最后兜底买</div><div class="v">③ 水立方 72.5%</div><div class="s">又便宜口碑又好</div></div>
    <div class="kpi"><div class="lbl">立即下单的人</div><div class="v">只有 0.7%</div><div class="s">99.7% 会再看看别的</div></div>
  </div>
</div></header>
"""

CORE_B = """
<section id="s0">
<div class="hl-banner"><h2>先看结论（5 句话）</h2>
  <div class="hl-grid">
    <div class="hl-card"><div class="n">① 第一眼看中的，不是最后买的</div><p>65.5% 的人第一眼想点开 ① 祖母绿（好看+评价多），但比到最后，72.5% 的人会买 ③ 水立方（便宜+评分高）。</p><div class="ev">数据：首点 65.5% vs 兜底 72.5%</div></div>
    <div class="hl-card"><div class="n">② 第一眼靠「好看」，下单靠「划算」</div><p>点开 ① 的理由里「外观」被提了 2,187 次；最后选 ③ 的理由里全是「材质安全、评分高、价格便宜」。<b>引流和转化是两回事。</b></p><div class="ev">数据：开放理由主题统计</div></div>
    <div class="hl-card"><div class="n">③ 几乎没有人会当场下单</div><p>立即购买只有 0.7%；99.7% 的人看完会再去看别家。<b>你的商品旁边，永远是别的商品在抢人。</b></p><div class="ev">数据：buy_now 0.7% / consider_other 99.7%</div></div>
    <div class="hl-card"><div class="n">④ 最后大家都流向 ③ 水立方</div><p>不管一开始点的是 ① 还是 ②，比完一圈后 71.8% 转向 ③，72.5% 兜底也选 ③。</p><div class="ev">数据：next_choice 71.8% / fallback 72.5%</div></div>
    <div class="hl-card"><div class="n">⑤ 下单前最怕「买不到/送不到」</div><p>不买的人，理由里「担心缺货/配送」被提了 140 次（最多）。商品详情页的配送提示，直接把人推去「再看看」。</p><div class="ev">数据：notbuy 理由词频</div></div>
  </div>
</div>
</section>
"""

DID_B = """
<section id="s2">
  <div class="sec-head"><span class="sec-no">2</span><h2>测试怎么做的</h2></div>
  <div class="sec-desc">让 1,000 位模拟买家按真实购物的顺序，一步步走完整个决策过程。</div>
  <div class="card">
    <div class="callout">每位买家依次回答 8 步：<b>① 搜索后第一眼最想点进哪个 → ② 点进后最想看什么信息 → ③ 看完买不买 → ④ 退出后会不会再看别的 → ⑤ 再看的话看哪个 → ⑥ 全都没买的话，最后买哪个 → ⑦ 搜索时翻到第几页 → ⑧ 什么因素最重要</b>。每一步都要写下理由。</div>
    <p style="font-size:13.5px;margin:10px 0 0;color:var(--muted);">观察的是「动态旅程」：从曝光到最终决策，看清流量在每一步怎么流动、怎么流失。百分比 = 人数 ÷ 1000。</p>
  </div>
</section>
"""

CHOSE_B = """
<section id="s3">
  <div class="sec-head"><span class="sec-no">3</span><h2>结果：谁赢谁输</h2></div>
  <div class="card"><h3>第一眼想点谁 vs 最后兜底买谁</h3>
    <div class="fig sm" id="fig_first_final"></div>
    <div class="takeaway"><b>一句话：</b>① 祖母绿赢在「第一眼」（65.5%），③ 水立方赢在「最后」（72.5%）。<b>好看吸引点击，划算赢得订单。</b></div>
  </div>
  <div class="card"><h3>看完详情页，买还是不买</h3>
    <div class="fig sm" id="fig_buy"></div>
    <div class="takeaway"><b>一句话：</b>66.2% 的人「倾向买」，但当场下单的只有 0.7%；再问一步，明确说会买的也只有 6.7%。<b>绝大多数人处于「先加购、再比一比」的状态。</b></div>
  </div>
  <div class="card"><h3>退出后，会考虑别家吗？会考虑哪家？</h3>
    <div class="grid2">
      <div class="fig sm" id="fig_consider"></div>
      <div class="fig sm" id="fig_next"></div>
    </div>
    <div class="takeaway"><b>一句话：</b>99.7% 的人会再看别家；其中 71.8% 会去看 ③ 水立方。<b>货架上的相邻竞品，就是最大的流量拦截者。</b></div>
  </div>
</section>
"""

WHY_B = """
<section id="s4">
  <div class="sec-head"><span class="sec-no">4</span><h2>原因：每一步为什么</h2></div>
  <div class="sec-desc">原因全部来自买家写下的理由（主题归类）和勾选的选项。</div>

  <div class="card"><h3>为什么第一眼点 ① 祖母绿（理由出现次数，共 655 人）</h3>
    <div class="fig sm" id="fig_why_a"></div>
    <div class="takeaway"><b>一句话：</b>「外观好看、高级」被提了 2,187 次——第一眼的吸引力主要来自<b>好看 + 评价多</b>，这时没人看价格。</div>
  </div>

  <div class="card"><h3>点进商品页后，最想看什么</h3>
    <div class="fig sm" id="fig_info"></div>
    <div class="takeaway"><b>一句话：</b>99.8% 的人先看「材质安不安全」，99.5% 看「评价怎么说」——<b>材质和口碑，是详情页的第一信息需求。</b></div>
  </div>

  <div class="card"><h3>为什么不买（不买的人写的理由，共 104 人）</h3>
    <div class="fig sm" id="fig_notbuy"></div>
    <div class="takeaway"><b>一句话：</b>「担心缺货/配送」被提了 140 次（最多）——<b>怕买不到、怕送不到，是临门一脚最大的绊脚石。</b></div>
  </div>

  <div class="card"><h3>为什么最后都转向 ③ 水立方（理由出现次数）</h3>
    <div class="grid2">
      <div class="fig sm" id="fig_switchc"></div>
      <div class="fig sm" id="fig_fallbackc"></div>
    </div>
    <div class="takeaway"><b>一句话：</b>转向 ③ 的理由，评分高（1,102 次）排第一；兜底选 ③ 的理由里「材质安全、评分高、有磁吸、便宜、评价多」全面占优——<b>它是六款里唯一「又便宜又全面」的选择。</b></div>
  </div>

  <div class="card"><h3>搜索时翻到第几页 + 整体最看重什么</h3>
    <div class="grid2">
      <div class="fig sm" id="fig_pagesearch"></div>
      <div class="fig sm" id="fig_overall"></div>
    </div>
    <div class="takeaway"><b>一句话：</b>79% 的人只看搜索结果第 1 页；整体决策时 53.3% 把「评价」排第一。<b>首页 + 好评价 = 生意的基本盘。</b></div>
  </div>

  <div class="card"><h3>买家原话（从 1000 份答卷里挑的典型说法）</h3>
    <div class="quote">The emerald-green ... looks higher-end than the others, and 4.5 stars with over 4,000 reviews makes it feel like the safest, most reliable option to click first.<div class="src">——点 ① 祖母绿的买家：「看起来高级，4,000 多条评价让我觉得最靠谱，所以先点它」</div></div>
    <div class="quote">The LQFMEHOT liner stands out with the highest star rating (4.6) ... At $7.09 with 974 reviews, it looks like a strong value without the reliability risk.<div class="src">——点 ③ 水立方的买家：「评分最高又最便宜，近千条评价，怎么看都是稳的」</div></div>
    <div class="quote">...the page shows a delivery notice with no featured offer, so I'd add it to my cart and check other options before committing.<div class="src">——看 ① 详情页的买家：「页面显示配送受限，我先加购物车，再去看看别家再定」</div></div>
    <div class="quote">It has the best combination of rating (4.6) and review volume (974) among the affordable options ... At $7.09 the risk is minimal.<div class="src">——兜底选 ③ 的买家：「便宜 + 评分高 + 评价多，就算不满意损失也小」</div></div>
    <div style="font-size:12.5px;color:var(--muted);margin-top:6px;">说明：原话为问卷英文原文，括号里是中文大意；个别买家的说法是定性参考，不代表全体。</div>
  </div>
</section>
"""

US_B = """
<section id="s5">
  <div class="sec-head"><span class="sec-no">5</span><h2>对卖家的启示：流量从哪来、在哪流失</h2></div>
  <div class="sec-desc">从「引流、转化、流失、临门一脚」四个环节看，每一环都有明确的改进点。</div>
  <div class="grid2">
    <div class="card"><h3>引流环节 · ① 祖母绿模式（高价高口碑）</h3>
      <p><span class="tag-good">做得好的</span> 评价多 + 外观高级 = 点击引擎：4,156 条评价吸引 65.5% 的人第一眼点它。</p>
      <p><span class="tag-fix">要改进的</span> 但点击没变成订单：79.2% 的人在货架阶段因太贵放弃；详情页还显示配送受限。</p>
      <p><span class="tag-test">值得试试的</span> 如果您也有这种高价 SKU：先解决配送/Featured Offer，再验证「2 合 1 省钱」的价值故事能否留住点击的人。</p>
    </div>
    <div class="card"><h3>转化环节 · ③ 水立方模式（性价比全能）</h3>
      <p><span class="tag-good">做得好的</span> 首点 26.3% → 转投 71.8% → 兜底 72.5%——它是所有人比完一圈后的「最终归宿」：最便宜 + 评分最高 + 评价近千。</p>
      <p><span class="tag-tell">没被发现的亮点</span> 它的花纹其实好看（第一眼能排第二），但主图没突出——强化主图质感，首点比例还有提升空间。</p>
    </div>
    <div class="card"><h3>流失环节 · 全货架</h3>
      <p><span class="tag-fix">要改进的</span> 99.7% 的人看完会再比较、71.8% 流向 ③——<b>货架上的高性价比邻居就是最大竞争者</b>。您的商品如果在 $7~$10 且评分 ≤4.4，正在被 ③② 抢人。</p>
      <p><span class="tag-good">做得好的</span> 「材质安全 + 评价」是详情页必看（99.8%/99.5%）——已经把材质和评价写清楚的商品，信息层不失分。</p>
    </div>
    <div class="card"><h3>临门一脚 · 配送与库存</h3>
      <p><span class="tag-fix">要改进的</span> 不买理由里「担心缺货/配送」最多（140 次）；① 的配送提示让人「加购不付款」、⑤ 的「仅剩 10 件」让人不敢买。</p>
      <p><span class="tag-good">做得好的</span> ③② 的「现货 + 正常配送」是它们被信任的隐性原因——<b>确定能买到，本身就是转化率。</b></p>
    </div>
  </div>
</section>
"""

NEXT_B = """
<section id="s6">
  <div class="sec-head"><span class="sec-no">6</span><h2>建议怎么做（按把握大小排序）</h2></div>
  <div class="card">
    <table>
      <tr><th style="width:90px;">把握</th><th style="width:200px;">做什么</th><th>为什么 / 依据</th></tr>
      <tr><td><span class="tag-do">马上做</span></td><td><b>把「能买到、送得到」写清楚</b></td><td>不买理由里「担心缺货/配送」最多；① 的配送提示把人推向「加购再比」。确保正常库存、明确配送时效。</td></tr>
      <tr><td><span class="tag-do">马上做</span></td><td><b>主图直接放「材质 + 评价」</b></td><td>99.8% 的人点进后先看材质安全、99.5% 看评价——主图首屏展示「EVA 环保无味」和评价数，缩短信息路径。</td></tr>
      <tr><td><span class="tag-try">试试看</span></td><td><b>拦截「再比较」环节</b></td><td>99.7% 的人会再比较、71.8% 流向 ③。对高流失商品试「比价优惠/组合购」，或在广告上拦截竞品流量词。</td></tr>
      <tr><td><span class="tag-try">试试看</span></td><td><b>高价 SKU 做转化试验</b></td><td>① 吸引 65.5% 点击但兜底只有 21.1%。试「2 合 1 省钱」叙事 + 配送确定性，看点击能不能变订单。</td></tr>
      <tr><td><span class="tag-watch">先观望</span></td><td><b>低价新品先解决「没人敢买」</b></td><td>④ 因评价太少（16 条）被 98.2% 的人拒绝。新品先做 Vine/早期评论，观察 30 天评价增速与份额的关系。</td></tr>
    </table>
    <div style="font-size:12.5px;color:var(--muted);margin-top:8px;">注：「试试看」的建议来自本次数据信号，需再验证；本次数据不能直接证明「改了配送就一定能提升销量」。</div>
  </div>
</section>
"""

JS_B = """
const CODES = ["A","B","C"];
const LBL = {A:"① 祖母绿", B:"② 蓝波纹", C:"③ 水立方"};
function fig(id){ return document.getElementById(id); }

(function(){ const c=fig("fig_first_final"); if(!c)return; const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true},
  legend:{data:["第一眼想点进","最后兜底买"],bottom:0,textStyle:{fontSize:13}},
  grid:{left:10,right:20,top:14,bottom:40,containLabel:true},
  xAxis:{type:"category",data:CODES.map(k=>LBL[k]),axisLabel:{fontSize:14}},
  yAxis:{type:"value",max:80,axisLabel:{formatter:"{value}%",fontSize:13}},
  series:[{name:"第一眼想点进",type:"bar",data:CODES.map(k=>DATA.journey.first_click[k]),barWidth:34,itemStyle:{color:"#3B6FB5"},label:{show:true,position:"top",formatter:function(p){return p.value+"%";},fontSize:13,fontWeight:"bold",color:"#33415C"}},
    {name:"最后兜底买",type:"bar",data:CODES.map(k=>DATA.journey.fallback[k]),barWidth:34,itemStyle:{color:"#E8A33D"},label:{show:true,position:"top",formatter:function(p){return p.value+"%";},fontSize:13,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_buy"); if(!c)return; const chart=echarts.init(c);
  const raw=DATA.journey.buy_decision;
  const labels={likely_buy:"倾向买",undecided:"犹豫",not_buy:"不买",buy_now:"当场买"};
  const cols={likely_buy:"#2E9E8F",undecided:"#E8A33D",not_buy:"#C24B3F",buy_now:"#16233B"};
  chart.setOption({tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  legend:{bottom:0,textStyle:{fontSize:12}},
  series:[{type:"pie",radius:["40%","66%"],center:["50%","45%"],data:Object.keys(raw).map(k=>({name:labels[k],value:raw[k],itemStyle:{color:cols[k]}})),label:{fontSize:12,formatter:"{b} {d}%"}}]});
})();

(function(){ const c=fig("fig_consider"); if(!c)return;
  const raw=DATA.journey.consider_other;
  const labels={yes:"会再看别的",maybe:"可能会",no:"不会"};
  const cols={yes:"#2E9E8F",maybe:"#E8A33D",no:"#C24B3F"};
  const chart=echarts.init(c);
  chart.setOption({title:{text:"退出后会不会再看别的（n=1000）",left:"center",textStyle:{fontSize:14,color:"#16233B"}},
  tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  legend:{bottom:0,textStyle:{fontSize:12}},
  series:[{type:"pie",radius:["40%","66%"],center:["50%","45%"],data:Object.keys(raw).map(k=>({name:labels[k]||k,value:raw[k],itemStyle:{color:cols[k]||"#9FB0C8"}})),label:{fontSize:12,formatter:"{b} {d}%"}}]});
})();

(function(){ const c=fig("fig_next"); if(!c)return;
  const d=DATA.journey.next_choice; const order=["C","B","A","D","F","E"].filter(k=>d[k]!=null);
  const L={A:"① 祖母绿",B:"② 蓝波纹",C:"③ 水立方",D:"④ 鹅卵石",E:"⑤ 纯黑",F:"⑥ 波点",none_of_these:"都不看"};
  const chart=echarts.init(c);
  chart.setOption({title:{text:"会去看哪一家（n=1000）",left:"center",textStyle:{fontSize:14,color:"#16233B"}},
  tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const p=ps[0];return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  grid:{left:10,right:44,top:30,bottom:20,containLabel:true}, xAxis:{type:"value",max:80,axisLabel:{formatter:"{value}%",fontSize:13}},
  yAxis:{type:"category",inverse:true,data:order.map(k=>L[k]||k),axisLabel:{fontSize:14}},
  series:[{type:"bar",data:order.map(k=>({value:d[k]||0,itemStyle:{color:k==="C"?"#E8A33D":"#3B6FB5"}})),barWidth:26,
    label:{show:true,position:"right",formatter:function(p){return p.value+"%";},fontSize:13,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_why_a"); if(!c)return;
  const d=DATA.reasons.clickA; const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const p=ps[0];return p.name+"：提到 "+p.value+" 次（655 人里）";}},
  grid:{left:10,right:48,top:10,bottom:20,containLabel:true}, xAxis:{type:"value",axisLabel:{fontSize:13}},
  yAxis:{type:"category",inverse:true,data:Object.keys(d),axisLabel:{fontSize:14}},
  series:[{type:"bar",data:Object.values(d),barWidth:24,itemStyle:{color:"#3B6FB5"},label:{show:true,position:"right",fontSize:13,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_info"); if(!c)return;
  const cn={material_safety:"材质/安不安全",reviews:"评价怎么说",specs:"规格尺寸",delivery:"配送信息",more_images:"更多图片",bullets:"五点描述",description:"长描述"};
  const d=DATA.journey.click_info; const order=Object.keys(d).sort(function(a,b){return d[b]-d[a];});
  const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const p=ps[0];return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  grid:{left:10,right:48,top:10,bottom:20,containLabel:true}, xAxis:{type:"value",max:100,axisLabel:{formatter:"{value}%",fontSize:13}},
  yAxis:{type:"category",inverse:true,data:order.map(k=>cn[k]),axisLabel:{fontSize:14}},
  series:[{type:"bar",data:order.map(k=>({value:d[k],itemStyle:{color:d[k]>=90?"#E8A33D":"#3B6FB5"}})),barWidth:24,
    label:{show:true,position:"right",formatter:function(p){return p.value+"%";},fontSize:13,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_notbuy"); if(!c)return;
  const d=DATA.reasons.notbuy; const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const p=ps[0];return p.name+"：提到 "+p.value+" 次（104 人里）";}},
  grid:{left:10,right:48,top:10,bottom:20,containLabel:true}, xAxis:{type:"value",axisLabel:{fontSize:13}},
  yAxis:{type:"category",inverse:true,data:Object.keys(d),axisLabel:{fontSize:14}},
  series:[{type:"bar",data:Object.values(d),barWidth:24,itemStyle:{color:"#C24B3F"},label:{show:true,position:"right",fontSize:13,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_switchc"); if(!c)return;
  const d=DATA.reasons.switchC; const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const p=ps[0];return p.name+"：提到 "+p.value+" 次";}},
  grid:{left:10,right:48,top:10,bottom:20,containLabel:true}, xAxis:{type:"value",axisLabel:{fontSize:13}},
  yAxis:{type:"category",inverse:true,data:Object.keys(d),axisLabel:{fontSize:14}},
  series:[{type:"bar",data:Object.values(d),barWidth:24,itemStyle:{color:"#E8A33D"},label:{show:true,position:"right",fontSize:13,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_fallbackc"); if(!c)return;
  const d=DATA.reasons.fallbackC; const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const p=ps[0];return p.name+"：提到 "+p.value+" 次（725 人里）";}},
  grid:{left:10,right:48,top:10,bottom:20,containLabel:true}, xAxis:{type:"value",axisLabel:{fontSize:13}},
  yAxis:{type:"category",inverse:true,data:Object.keys(d),axisLabel:{fontSize:14}},
  series:[{type:"bar",data:Object.values(d),barWidth:24,itemStyle:{color:"#2E9E8F"},label:{show:true,position:"right",fontSize:13,fontWeight:"bold",color:"#33415C"}}]});
})();

(function(){ const c=fig("fig_pagesearch"); if(!c)return;
  const d=DATA.journey.page_search; const chart=echarts.init(c);
  chart.setOption({title:{text:"搜索时翻到第几页（n=1000）",left:"center",textStyle:{fontSize:14,color:"#16233B"}},
  tooltip:{trigger:"item",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(p){return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  legend:{bottom:0,textStyle:{fontSize:12}},
  series:[{type:"pie",radius:["40%","66%"],center:["50%","45%"],data:Object.keys(d).map(k=>({name:k.replace("page","第")+"页",value:d[k],itemStyle:{color:k==="page1"?"#3B6FB5":"#9FB0C8"}})),label:{fontSize:12,formatter:"{b} {d}%"}}]});
})();

(function(){ const c=fig("fig_overall"); if(!c)return;
  const cn={reviews:"评价",material:"材质",price_value:"价格/价值",rating:"评分",appearance:"外观",listing:"页面表达"};
  const d=DATA.journey.overall_factor; const order=Object.keys(d).sort(function(a,b){return d[b]-d[a];});
  const chart=echarts.init(c);
  chart.setOption({tooltip:{trigger:"axis",triggerOn:"mousemove|click",renderMode:"richText",confine:true,formatter:function(ps){const p=ps[0];return p.name+"："+p.value+"%（"+Math.round(p.value/100*1000)+" 人）";}},
  grid:{left:10,right:48,top:10,bottom:20,containLabel:true}, xAxis:{type:"value",max:60,axisLabel:{formatter:"{value}%",fontSize:13}},
  yAxis:{type:"category",inverse:true,data:order.map(k=>cn[k]),axisLabel:{fontSize:14}},
  series:[{type:"bar",data:order.map(k=>({value:d[k],itemStyle:{color:k==="reviews"?"#E8A33D":"#3B6FB5"}})),barWidth:24,
    label:{show:true,position:"right",formatter:function(p){return p.value+"%";},fontSize:13,fontWeight:"bold",color:"#33415C"}}]});
})();
"""

PROD_CARDS_JS = """
(function(){
  const grid = document.getElementById("prod_grid");
  if(!grid) return;
  DATA.products.forEach(p => {
    const el = document.createElement("div");
    el.className = "prod-card";
    el.innerHTML = `
      <div class="ph"><img src="${p.img_b64}" alt="${p.name}">
        <span class="no">${p.num}</span><span class="share">首选 ${p.share}%</span></div>
      <div class="bd">
        <div class="pname">${p.num} ${p.name}（${p.brand}）</div>
        <div class="meta">${p.price} · ${p.rating} · ${p.reviews} 条评价 · 真实排名 ${p.rank}</div>
        <div class="feat">${p.feat}</div>
        <div class="status ${p.status_cls}">状态：${p.status}</div>
        <a href="${p.link}" target="_blank" rel="noopener">${p.link}</a>
      </div>`;
    grid.appendChild(el);
  });
})();
"""

def build(title, hero, core, did, chose, why, us, nxt, js, total, meta):
    quick = QUICK_TABLE.replace("@ROWS@", QUICK_ROWS)
    reject_rows = "".join(
        "<tr><td>" + p["num"] + " " + p["name"] + "</td><td>" +
        "；".join(f'{label}（{pct}）' for label, pct in p["reject"]) + "</td></tr>"
        for p in products)
    why = why.replace("@REJECT_ROWS@", reject_rows)
    prods = """<section id="s7"><div class="sec-head"><span class="sec-no">7</span><h2>6 款产品详情</h2></div>
    <div class="sec-desc">点链接可直接跳到亚马逊商品页。编号与前面所有图表一致。</div>
    <div class="prod-grid" id="prod_grid"></div></section>"""
    footer = FOOTER.replace("@TITLE@", "Amazon 美国站 · 浴帘内衬 6 款竞品 · 买家模拟实验").replace("@TOTAL@", total).replace("@META@", meta)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title><style>{CSS}</style></head>
<body>
{hero}
{TOC}
<main>
{core}
{quick}
<section id="s1">
  <div class="sec-head"><span class="sec-no">1</span><h2>测试的是谁</h2></div>
  <div class="card">
    <div class="grid2">
      <div><h3 style="margin-bottom:8px;">人群设定</h3>
        <table>
          <tr><th style="width:110px;">项目</th><th>设定</th></tr>
          <tr><td>画像来源</td><td>Amazon 购物者画像（北美）</td></tr>
          <tr><td>地区</td><td>North America（美亚目标市场）</td></tr>
          <tr><td>样本量</td><td>1,000 人（另有 1,000 人参加另一个实验）</td></tr>
          <tr><td>购物场景</td><td>搜索「浴帘/浴帘内衬」，有明确购买意图</td></tr>
        </table>
        <div style="font-size:12.5px;color:var(--muted);margin-top:6px;">本次数据没有收集年龄、性别、家庭人数等人口信息，结论都基于购物行为。</div>
      </div>
      <div><h3 style="margin-bottom:8px;">这群人的特点</h3>
        <ul style="padding-left:18px;font-size:14px;margin:4px 0;">
          <li><b>要便宜，但更怕不靠谱</b>：52.2% 把价格排第一，但 99.5% 点进后先看评价。</li>
          <li><b>不急，货比三家</b>：当场下单的只有 0.7%，99.7% 会再看别家。</li>
          <li><b>信息不全就不买</b>：缺货、材质不明、图模糊、没标价格，90%+ 直接放弃。</li>
          <li><b>材质有硬要求</b>：100% 要 EVA（环保无味），96.9% 喜欢半透明。</li>
        </ul>
        <div style="font-size:12.5px;color:var(--muted);margin-top:6px;">以上来自问卷数据统计，不是猜测。</div>
      </div>
    </div>
  </div>
</section>
{did}
{chose}
{why}
{us}
{nxt}
{prods}
</main>
{footer}
<script>{ECHARTS_JS}</script>
<script>
const DATA = {DATA_JSON};
{js}
{PROD_CARDS_JS}
</script>
</body></html>
"""

open(os.path.join(OUT_DIR, "shower_liner_choice_report.html"), "w").write(build(
    title="Amazon 美国站 · 浴帘内衬 6 款竞品 · 货架选择实验（1000 位买家）",
    hero=HERO_A, core=CORE_A, did=DID_A, chose=CHOSE_A, why=WHY_A, us=US_A, nxt=NEXT_A, js=JS_A,
    total="货架选择实验（n=1,000）", meta="1000 位买家 · 26 道题 · 运行无错误"))

open(os.path.join(OUT_DIR, "shower_liner_journey_report.html"), "w").write(build(
    title="Amazon 美国站 · 浴帘内衬 6 款竞品 · 决策旅程实验（1000 位买家）",
    hero=HERO_B, core=CORE_B, did=DID_B, chose=CHOSE_B, why=WHY_B, us=US_B, nxt=NEXT_B, js=JS_B,
    total="决策旅程实验（n=1,000）", meta="1000 位买家 · 8 步决策 · 运行无错误"))

print("written: shower_liner_choice_report.html + shower_liner_journey_report.html")
