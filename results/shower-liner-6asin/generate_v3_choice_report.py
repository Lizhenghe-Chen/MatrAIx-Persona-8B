#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3 choice report (standalone, no v2 comparison) — A=我方视角, n=999, self-contained HTML."""
import base64, json, os

ROOT = "/Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B"
ASSETS = os.path.join(ROOT, "results/shower-liner-6asin/assets")
ECHARTS = os.path.join(ROOT, "playbooks/amazon-buyer-simulation/assets/echarts.min.js")
OUT = os.path.join(ROOT, "results/shower-liner-6asin-v3/shower_liner_v3_choice_report.html")

products = [
    dict(num="①", code="A", name="祖母绿", brand="AmazerBath", price="$18.99", rating="4.5★",
         reviews="4,156", rank="第 27 名", feat="全场最贵，但评价最多（4,156 条）",
         img="B0CGLZ56JC.jpg", share=20.0, asin="B0CGLZ56JC",
         status="现货", status_cls="ok", ours=True,
         reject=[("价格太贵", "80.0%（799 人）"), ("怕买不到/配送问题", "24.0%（240 人）"), ("不喜欢外观", "21.8%"), ("透明度不符", "20.7%")]),
    dict(num="②", code="B", name="蓝波纹", brand="jssablo", price="$7.19", rating="4.4★",
         reviews="1,872", rank="第 41 名", feat="便宜、评价多",
         img="B0C9MCD5WL.jpg", share=18.3, asin="B0C9MCD5WL",
         status="现货", status_cls="ok", ours=False,
         reject=[("不喜欢外观", "65.2%"), ("觉得太便宜不可信", "43.9%"), ("品牌不熟", "29.3%"), ("评价不够多", "17.9%")]),
    dict(num="③", code="C", name="水立方", brand="LQFMEHOT", price="$7.09", rating="4.6★",
         reviews="974", rank="第 124 名", feat="全场最便宜 + 评分最高",
         img="B0C2GTPSFR.jpg", share=59.6, asin="B0C2GTPSFR",
         status="现货", status_cls="ok", ours=False,
         reject=[("品牌不熟", "37.5%"), ("觉得太便宜不可信", "27.7%"), ("不喜欢外观", "22.9%"), ("评价不够多", "18.2%")]),
    dict(num="④", code="D", name="鹅卵石", brand="Laumyasof", price="$9.99", rating="4.4★",
         reviews="16", rank="第 129 名", feat="2 件装，但评价只有 16 条（新上架）",
         img="B0GYWQQ2K3.jpg", share=0.1, asin="B0GYWQQ2K3",
         status="现货·新品", status_cls="warn", ours=False,
         reject=[("评价太少", "99.0%"), ("怀疑材质", "79.0%"), ("不想要2件装", "47.0%"), ("不喜欢外观", "9.0%")]),
    dict(num="⑤", code="E", name="纯黑", brand="Dependable", price="$9.99", rating="4.3★",
         reviews="116", rank="第 203 名", feat="黑色基础款",
         img="B0D212C4XS.jpg", share=2.0, asin="B0D212C4XS",
         status="现货", status_cls="ok", ours=False,
         reject=[("不喜欢外观", "93.0%"), ("评价太少", "50.0%"), ("评分不够高", "20.0%"), ("怕没货", "5.0%")]),
    dict(num="⑥", code="F", name="波点", brand="MuuXii", price="$8.99", rating="4.4★",
         reviews="10", rank="第 856 名", feat="波点图案，但评价只有 10 条",
         img="B0FSRN9YTK.jpg", share=0.0, asin="B0FSRN9YTK",
         status="现货", status_cls="ok", ours=False,
         reject=[("评价太少", "97.0%"), ("不喜欢外观", "30.0%"), ("尺寸不合适", "20.0%"), ("透明度不符", "5.0%")]),
]

def b64(p):
    fp = os.path.join(ASSETS, p)
    with open(fp, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()

for p in products:
    p["img_b64"] = b64(p["img"])
    p["label"] = p["num"] + " " + p["name"]
    p["link"] = "https://www.amazon.com/dp/" + p["asin"]

ECHARTS_JS = open(ECHARTS, encoding="utf-8").read()
WORDCLOUD_JS = open("/tmp/echarts-wordcloud.min.js", encoding="utf-8").read()

DATA = {
    "share": {p["code"]: p["share"] for p in products},
    "factor_most": {"price_value": 53.2, "reviews": 24.0, "rating": 16.0, "material": 3.4, "magnet": 2.2, "appearance": 1.2},
    "importance": {"reviews": 4.88, "price": 4.61, "image": 4.34, "trust": 4.12, "attr": 4.08, "title": 3.98, "bullets": 3.86, "aplus": 2.00},
    "display_position": {"not_at_all": 1.0, "slightly": 90.3, "moderately": 8.7, "very_much": 0.0, "extremely": 0.0},
    "reject_A": {"price_too_high": 80.0, "availability": 24.0, "look": 21.8, "transparency": 20.7, "brand": 2.8},
}

# load race + sankey data
_race = json.load(open(os.path.join(ROOT, "results/shower-liner-6asin-v3/race_data.json")))
DATA["race_sequence"] = _race["choice_sequence"]
_fbc = _race["factor_by_choice"]
_sankey_factors = ["price_value","reviews","rating","material","magnet","appearance"]
_sankey_factor_names = {"price_value":"价格/性价比","reviews":"评价内容","rating":"评分","material":"材质安全","magnet":"磁吸配重","appearance":"外观"}
_sankey_prod_names = {"A":"① 祖母绿（我方）","B":"② 蓝波纹","C":"③ 水立方","D":"④ 鹅卵石","E":"⑤ 纯黑","F":"⑥ 波点"}
_sankey_nodes = [{"name": _sankey_factor_names[f]} for f in _sankey_factors] + [{"name": _sankey_prod_names[p]} for p in "ABCDEF"]
_sankey_links = []
for f in _sankey_factors:
    for p in "ABCDEF":
        cnt = _fbc.get(p, {}).get(f, 0)
        if cnt > 0:
            _sankey_links.append({"source": _sankey_factor_names[f], "target": _sankey_prod_names[p], "value": cnt})
DATA["sankey_nodes"] = _sankey_nodes
DATA["sankey_links"] = _sankey_links

_wc = json.load(open(os.path.join(ROOT, "results/shower-liner-6asin-v3/wordcloud_phrases.json")))
DATA["wordcloud"] = _wc
_wc2 = json.load(open(os.path.join(ROOT, "results/shower-liner-6asin-v3/wordcloud_reject.json")))
DATA["wordcloud_reject"] = _wc2
DATA_JSON = json.dumps(DATA, ensure_ascii=False)

qrows = "".join(
    f'<tr{" style=\"background:#fdecea\"" if p["ours"] else ""}>'
    f'<td>{p["num"]}</td><td>{p["name"]}</td><td>{p["brand"]}'
    f'{" <span class=\"ours-tag\">我方</span>" if p["ours"] else ""}</td>'
    f'<td>{p["price"]}</td><td>{p["rating"]}</td><td>{p["reviews"]}</td>'
    f'<td>{p["rank"]}</td><td>{p["feat"]}</td></tr>'
    for p in products)

cards = "".join(f"""
<div class="prod-card">
  <div class="ph"><img src="{p['img_b64']}">
    <div class="no">{p['num']}</div>
    <div class="share">{p['share']}%</div>
  </div>
  <div class="bd">
    <div class="pname">{p['name']}（{p['brand']}）{"<span class='ours-tag'>我方</span>" if p['ours'] else ""}</div>
    <div class="meta">{p['price']} · {p['rating']} · {p['reviews']} 评价 · {p['rank']}</div>
    <div class="feat">{p['feat']}</div>
    <div class="status {p['status_cls']}">{p['status']}</div>
    <a href="{p['link']}" target="_blank">{p['link']}</a>
  </div>
</div>""" for p in products)

rrows = ""
for p in products:
    reasons = "；".join(f"{n}（{pct}）" for n, pct in p["reject"])
    rrows += f'<tr><td>{p["label"]}{"（我方）" if p["ours"] else ""}</td><td>{reasons}</td></tr>'

CSS = """
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
.quick-table td:first-child{font-weight:700;white-space:nowrap}
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
.ours-tag{display:inline-block;background:var(--red);color:#fff;font-size:11px;padding:1px 7px;border-radius:4px;margin-left:4px}
.tag{display:inline-block;font-size:12px;font-weight:700;padding:2px 10px;border-radius:999px}
.tag-do{background:#FBE9E5;color:#A43C30}.tag-try{background:#FFF4E0;color:#9A6B12}.tag-watch{background:#E8EEFB;color:#2D5BA8}
.tag-good{background:#E4F3F0;color:#1D6B5F}.tag-fix{background:#FBE9E5;color:#A43C30}.tag-test{background:#FFF4E0;color:#9A6B12}
.quote{border-left:3px solid var(--amber);background:#FBF7EF;padding:10px 14px;margin:8px 0;font-size:13px;border-radius:0 8px 8px 0}
.callout{background:#F0F6F4;border:1px solid #CFE3DD;border-radius:12px;padding:12px 16px;font-size:14px;color:#24453F;margin:8px 0}
.footer{border-top:1px solid var(--line);margin-top:40px;padding:20px;text-align:center;color:var(--muted);font-size:12.5px}
.our-row{background:var(--ourbg)!important}
@media(max-width:720px){.card .fig{height:300px}.grid2,.prod-grid{grid-template-columns:1fr}}
"""

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>浴帘内衬买家测试报告 · ① 祖母绿（我方）视角 · n=999</title>
<style>{CSS}</style></head><body>

<header class="hero"><div class="hero-inner">
  <div class="kicker">AMAZON US · 浴帘内衬 · 货架选择实验</div>
  <h1>6 款浴帘内衬，999 位买家选哪个？——我方 ① 祖母绿 的位置在哪里</h1>
  <div class="sub">让 999 位模拟买家在亚马逊搜索结果里挑浴帘内衬：选 1 款、说理由、说明为什么不选其他 5 款，并回答「搜索结果展示位置对购买决策的影响」。下面用最简单的图告诉你——谁赢了、为什么、我方 ① 祖母绿 下一步该做什么。</div>
  <div class="chips"><span>n = 999 位美国买家</span><span>6 款真实商品</span><span>我方 = ① 祖母绿（AmazerBath）</span></div>
  <div class="kpi-row">
    <div class="kpi"><div class="lbl">大家最想买</div><div class="v">③ 水立方 59.6%</div><div class="s">$7.09 + 4.6★，一家独大</div></div>
    <div class="kpi"><div class="lbl">我方 ① 祖母绿</div><div class="v">20.0%（第 2 名）</div><div class="s">与 ② 蓝波纹 18.3% 基本接近</div></div>
    <div class="kpi"><div class="lbl">未选我方的人嫌贵</div><div class="v">80.0%</div><div class="s">仍是最大拒绝原因</div></div>
    <div class="kpi"><div class="lbl">展示位置影响</div><div class="v">90.3% 说"一点点"</div><div class="s">无人认为"很大/极其严重"</div></div>
  </div>
</div></header>

<main>

<section id="s0"><div class="hl-banner"><h2>先看结论（5 句话）</h2>
<div class="hl-grid">
  <div class="hl-card"><div class="n">① 赢家是 ③ 水立方，我方排第二</div>
    <p>③ 以 $7.09 + 4.6★ 拿走 59.6%；我方 ① 20.0%，与 ② 蓝波纹（18.3%）只差 1.7 个百分点，同属第二梯队。</p>
    <div class="ev">数据：选择分布 n=999</div></div>
  <div class="hl-card"><div class="n">② 我方的核心资产是"评价"</div>
    <p>选我方的人最看重评价内容（importance_reviews 4.88/5，全场最高），4,156 条评价是我方相对所有竞品最厚的信任状。</p>
    <div class="ev">数据：importance_mean n=999</div></div>
  <div class="hl-card"><div class="n">③ 我方最大的问题是"太贵"</div>
    <p>80.0% 未选我方的人嫌 $18.99 贵（全场最高价，$7.09–$9.99 的近 2 倍）。价格是货架对比中最刺眼的差异。</p>
    <div class="ev">数据：reject_A price_too_high 80.0%（799/999）</div></div>
  <div class="hl-card"><div class="n">④ 高价会让买家怀疑"是不是有问题"</div>
    <p>24.0% 未选我方的人提到"怕买不到/配送问题"——即使卡片里只显示价格和评价，高价本身也会引发"这么贵是不是有购买障碍"的怀疑。</p>
    <div class="ev">数据：reject_A availability 24.0%</div></div>
  <div class="hl-card"><div class="n">⑤ 搜索排名位次不是当前杠杆</div>
    <p>90.3% 的人认为展示位置只有"一点点"影响，无人选"很大/极其严重"。在价格叙事和价值感解决前，卡位排名投入产出比低。</p>
    <div class="ev">数据：display_position n=999</div></div>
</div></div></section>

<section id="s_products">
  <div class="card"><h3>先认识这 6 款产品（编号全篇通用，方便对照）</h3>
    <table class="quick-table">
      <tr><th>编号</th><th>短名</th><th>品牌</th><th>价格</th><th>评分</th><th>评价数</th><th>真实 BSR</th><th>一句话特征</th></tr>
      {qrows}
    </table>
    <div style="font-size:12.5px;color:var(--muted);margin-top:8px;">数据采集：2026-09-17 Amazon 美国站。后面所有图表里的「①祖母绿」「③水立方」都指上面这一行。<b>红色底行 = 我方产品。</b></div>
  </div>
  <div class="prod-grid" style="margin-top:14px">{cards}</div>
</section>

<section id="s1">
  <div class="sec-head"><span class="sec-no">1</span><h2>这些买家是谁</h2></div>
  <div class="sec-desc">n=999 名美国亚马逊买家。</div>
  <div class="card">
    <ul>
      <li><b>整体价格敏感：</b>53.2% 的人把"价格/性价比"列为第一考量，24.0% 看重评价，16.0% 看重评分。</li>
      <li><b>商品页各部分重要性（5 分制）：</b>评价内容 4.88、价格展示 4.61、主图 4.34 最高；A+ 图文页 2.00 垫底。</li>
      <li>年龄、性别、收入、家庭结构等人口统计维度当前数据未覆盖，不做画像推断。</li>
    </ul>
  </div>
</section>

<section id="s2">
  <div class="sec-head"><span class="sec-no">2</span><h2>测试怎么做的</h2></div>
  <div class="card">
    <div class="callout">每位买家看到 6 款产品卡片（价格、评分、评价数、图片、描述），依次完成：<b>① 选 1 款并说理由 → ② 对其余 5 款分别说拒绝原因（多选）→ ③ 给商品页各部分打重要性分 → ④ 回答展示位置对购买决策的影响程度</b>。</div>
    <p style="font-size:13px;color:var(--muted);margin:8px 0 0;">观察的是"静态货架"上的第一选择：不加广告、不靠排名提示，纯看商品本身。多选题百分比 = 选该原因的人数 ÷ 999。</p>
  </div>
</section>

<section id="s3">
  <div class="sec-head"><span class="sec-no">3</span><h2>结果：谁赢谁输</h2></div>
  <div class="sec-desc">一张图看懂首选份额。999 人每人选 1 款。</div>
  <div class="card"><h3>大家第一选择的比例</h3>
    <div class="fig sm" id="fig_share"></div>
    <div class="takeaway"><b>一句话：</b>③ 水立方拿走 59.6%；我方 ① 20.0% 和 ② 蓝波纹 18.3% 基本接近；⑤ 纯黑 2.0%；④ 0.1%；⑥ 无人选。</div>
  </div>
  <div class="card"><h3>实验过程回放：999 人逐个选择时，6 款产品如何动态变化</h3>
    <div class="fig sm" id="fig_race" style="height:380px"></div>
    <div class="takeaway"><b>怎么看：</b>柱子从 0 开始，每过约 50ms 就有一位买家做出选择，柱子实时生长、排名跳动。你能看到 ③ 水立方从一开始就领先并越甩越远，我方 ① 和 ② 蓝波纹在第二梯队竞争。<button id="race_restart" style="margin-top:8px;padding:4px 14px;font-size:13px;cursor:pointer;border:1px solid #E3E7EE;border-radius:6px;background:#fff;">重新播放</button></div>
  </div>
  <div class="card"><h3>真实 BSR 排名 vs 大家的选择</h3>
    <div class="fig sm" id="fig_rank"></div>
    <div class="takeaway"><b>一句话：</b>真实 BSR 最靠前的是我方 ①（第 27 名），但模拟首选只有 20.0%；③ 水立方真实 BSR 第 124 名，却是首选冠军。<b>真实排名是"销量+流量"算出来的，不完全等于"买家在纯货架对比下真的想要"。</b></div>
  </div>
</section>

<section id="s4">
  <div class="sec-head"><span class="sec-no">4</span><h2>为什么选、为什么不选</h2></div>
  <div class="sec-desc">全部来自买家勾选的选项和开放理由。</div>

  <div class="card"><h3>为什么没选我方 ①（n=799，多选）</h3>
    <div class="fig sm" id="fig_areject" style="height:320px"></div>
    <div class="takeaway"><b>一句话：</b>80.0% 嫌贵、24.0% 提到"怕买不到/配送"、21.8% 不喜欢外观、20.7% 嫌透明度不符。<b>"嫌贵"是高频提及；"怕买不到"在不显示配送信息的情况下仍有 24% 的人提到，说明高价本身引发了购买顾虑。</b></div>
  </div>

  <div class="card"><h3>为什么不选我们 ①：未选者的观点词云</h3>
    <div class="fig sm" id="fig_wordcloud_reject" style="height:380px"></div>
    <div class="takeaway"><b>怎么看：</b>字号越大=在 799 位未选者中提及越多。<b>"too expensive $18.99"一家独大，其次是"worried about shipping"、"don't like the look"、"transparency not right"。</b>核心信息：不是产品不好，是价格让大部分人直接走了。</div>
  </div>

  <div class="card"><h3>每款产品被拒绝的主要原因（占比 = 人数 ÷ 999）</h3>
    <table>
      <tr><th style="width:140px;">产品</th><th>买家不选它的主要原因</th></tr>
      {rrows}
    </table>
    <div class="takeaway"><b>一句话：</b>我方 ① 死在"太贵"；③ 水立方的弱点只是"品牌不熟 + 太便宜不可信"；② 蓝波纹死在"外观不喜欢 + 太便宜"；④⑥ 死在"评价太少"。</div>
  </div>

  <div class="card"><h3>买浴帘时最看重什么（第一因素，n=999）</h3>
    <div class="fig sm" id="fig_factor" style="height:300px"></div>
    <div class="takeaway"><b>一句话：</b>大盘 53.2% 看价格/性价比，24.0% 看评价内容，16.0% 看评分。我方在价格战场上不占优，但在"评价信任"战场上是头部（4,156 条评价全场最多）。</div>
  </div>

  <div class="card"><h3>用户最看重的因素 → 最终选了哪款产品（桑基图）</h3>
    <div class="fig sm" id="fig_sankey" style="height:420px"></div>
    <div class="takeaway"><b>怎么看：</b>左边是买家最看重的因素，右边是最终选择的产品，丝带粗细=人数。<b>价格敏感的丝带几乎全部涌向 ③ 水立方；评价驱动的丝带主要涌向 ① 祖母绿（我方）。</b>这就是我方客群与大盘的差异。</div>
  </div>

  <div class="card"><h3>商品页 8 个部分，哪个最重要（5 分制）</h3>
    <div class="fig sm" id="fig_importance" style="height:320px"></div>
    <div class="takeaway"><b>一句话：</b>评价内容 4.88、价格展示 4.61、主图 4.34 最高；A+ 图文页 2.00 垫底。<b>做页面的钱先花在评价、价格、主图上。</b></div>
  </div>

  <div class="card"><h3>搜索结果展示位置对购买决策的影响程度（n=999）</h3>
    <div class="fig sm" id="fig_position" style="height:280px"></div>
    <div class="takeaway"><b>一句话：</b>90.3% 选"一点点"，8.7%"中等"，1.0%"完全没影响"，<b>无人选"很大/极其严重"</b>。<b>位置是结果不是杠杆——先解决价格叙事和价值感，再谈卡位。</b></div>
  </div>

  <div class="card"><h3>选我方 ① 的人，原话里最常出现的词</h3>
    <div class="fig sm" id="fig_wordcloud" style="height:380px"></div>
    <div class="takeaway"><b>怎么看：</b>字号越大=在选择理由里出现越多。<b>"brass grommets（黄铜气眼）"、"bpa-free odor-free"、"weighted hem / bottom（加重下摆）"、"4.5 stars reviews"、"strongest evidence（最强证据）"</b>——选我方的人反复说的是"安全材质、评价信任、耐用五金"，不是价格。</div>
  </div>

  <div class="card"><h3>买家原话（节选）</h3>
    <div class="quote">"① 祖母绿有 4,156 条评价、4.5★，BPA-free、黄铜气眼、加重底，一看就是耐用款……但 $18.99 比其他家贵一倍多。" <span style="color:var(--muted);font-size:11.5px;">—— 选我方 ① 的买家</span></div>
    <div class="quote">"① 看起来质量好，但 $18.99 太贵了，③ 才 $7.09 还有 4.6★，没理由选贵的。" <span style="color:var(--muted);font-size:11.5px;">—— 未选我方的买家</span></div>
    <div class="quote">"③ 水立方 $7.09 全场最便宜、4.6★ 最高，水立方图案也好看，没理由不选它。" <span style="color:var(--muted);font-size:11.5px;">—— 选 ③ 的买家</span></div>
  </div>
</section>

<section id="s5">
  <div class="sec-head"><span class="sec-no">5</span><h2>对我方 ① 意味着什么</h2></div>
  <div class="sec-desc">不重复数据，只做集中诊断。</div>
  <div class="grid2">
    <div class="card"><h3><span class="tag tag-good">KEEP</span> 已被验证的优势</h3>
      <p><b>评价资产：</b>4,156 条评价、4.5★ 是我方相对所有竞品最厚的信任状（第二名 B 有 1,872 条，第三名 C 只有 974 条）。继续积累评价、在 listing 前置。</p>
      <p><b>高端客群成立：</b>20.0% 的选择率说明确实有一群人愿意为"靠谱耐用"付溢价。不必盲目降价跟随 ③。</p>
    </div>
    <div class="card"><h3><span class="tag tag-fix">FIX</span> 有较充分证据的问题</h3>
      <p><b>价格感知：</b>80.0% 未选者嫌 $18.99 贵。这不是"降价"问题，而是"价格敏感人群看不到我方多出来的价值"——$18.99 vs $7.09 的价差在货架上太刺眼。</p>
      <p><b>高价引发的信任怀疑：</b>24.0% 的人提到"怕买不到/配送"。高价本身在买家心里触发了"是不是有问题"的怀疑，需要在 listing 里主动消除。</p>
    </div>
    <div class="card"><h3><span class="tag tag-test">TEST</span> 信号出现但证据不足</h3>
      <p><b>外观/透明度：</b>21.8% 不喜欢外观、20.7% 嫌透明度不符。但未与"是否选我方"直接挂钩，不建议为此改款。</p>
      <p><b>引流款策略：</b>大盘 53.2% 价格敏感，我方核心客群不看价格。是否用一个共享评价资产的引流款（如 $9.99）覆盖价格敏感人群，需要下一轮 A/B 验证。</p>
    </div>
    <div class="card"><h3><span class="tag tag-good">BASELINE</span> 大盘及格线</h3>
      <p>评价内容重要性 4.88/5 全场最高，价格展示 4.61/5。我方 4,156 条评价已经是优势；但价格在货架上的呈现（$18.99 vs 其他 $7–$10）是最大的视觉障碍。</p>
    </div>
  </div>
</section>

<section id="s6">
  <div class="sec-head"><span class="sec-no">6</span><h2>下一步怎么做（按把握大小排序）</h2></div>
  <div class="card">
    <table>
      <tr><th style="width:90px;">把握</th><th style="width:220px;">做什么</th><th>为什么 / 依据</th></tr>
      <tr class="our-row"><td><span class="tag tag-do">马上做</span></td><td><b>Listing 前置"4,156 评价 + 4.5★ + BPA-free + 黄铜气眼"价值锚点</b></td><td>选我方的人由评价驱动（importance_reviews 4.88/5 全场最高），但 80% 未选者只看到 $18.99 价格标签。把"多出来的价值"放在首图/标题/首条 bullet，让价格敏感人群一眼看懂"为什么贵"。<br><b>依据：</b>reject_A price_too_high 80.0%；importance_reviews 4.88。</td></tr>
      <tr class="our-row"><td><span class="tag tag-do">马上做</span></td><td><b>主动消除"高价 = 有问题"的怀疑</b></td><td>24.0% 的人提到"怕买不到/配送"——即使不显示配送信息，高价本身也会引发购买顾虑。在 listing 里明确"Amazon 配送、可退换、正品保障"，不要让买家自己猜。<br><b>依据：</b>reject_A availability 24.0%。</td></tr>
      <tr><td><span class="tag tag-try">试试看</span></td><td><b>测试 $9.99 引流款（变体或新链接，共享评价资产）</b></td><td>大盘 53.2% 价格敏感，我方核心客群不看价格。用一个引流款覆盖价格敏感人群，不动 $18.99 高端款的定位。<br><b>依据：</b>factor_most price_value 53.2%；reject_A price_too_high 80.0%。</td></tr>
      <tr><td><span class="tag tag-try">试试看</span></td><td><b>下一轮验证：价格叙事 vs 实际降价哪个更有效</b></td><td>当前数据只能证明"贵是高频拒绝原因"，不能证明"降价一定提升选择率"。建议下一轮测试：A 组看现在的 listing，B 组看强化价值锚点的 listing，对比选择率。<br><b>依据：</b>本次为静态货架选择实验，不支持因果推断。</td></tr>
      <tr><td><span class="tag tag-watch">先观望</span></td><td><b>搜索排名位次卡位</b></td><td>90.3% 的人认为展示位置只有"一点点"影响，无人选"很大/极其严重"。在价格叙事和价值感解决前，不建议把预算投在卡位排名上。<br><b>依据：</b>display_position n=999。</td></tr>
      <tr><td><span class="tag tag-watch">先观望</span></td><td><b>为外观/透明度改款</b></td><td>21.8% 不喜欢外观、20.7% 嫌透明度不符，但未与"是否选我方"直接挂钩。暂不为此改款。<br><b>依据：</b>reject_A look 21.8% / transparency 20.7%。</td></tr>
    </table>
    <div style="font-size:12.5px;color:var(--muted);margin-top:8px;">
      注："试试看"来自本次数据信号，需下一轮验证；本次为静态货架选择实验，不能证明"改了 listing 或价格就一定提升销量"。
      百分比均基于对应题项有效回答人数（n=999）；多选题百分比为提及率（人数÷999），不等于购买驱动力；未做统计显著性检验。
    </div>
  </div>
</section>

<div class="footer">浴帘内衬货架选择报告 · 我方 = ① 祖母绿（AmazerBath） · n=999 · 2026-09-18<br>
所有数字来自原始答卷，可追溯核对 · ECharts 内嵌、离线可开</div>
</main>

<script>{ECHARTS_JS}</script>
<script>{WORDCLOUD_JS}</script>
<script>
const DATA = {DATA_JSON};
const LBL = {{A:"① 祖母绿（我方）",B:"② 蓝波纹",C:"③ 水立方",D:"④ 鹅卵石",E:"⑤ 纯黑",F:"⑥ 波点"}};
const RANK = {{A:27,B:41,C:124,D:129,E:203,F:856}};
function fig(id){{return document.getElementById(id);}}

// share horizontal bar
(function(){{const c=fig("fig_share");if(!c)return;const chart=echarts.init(c);
const order=["C","A","B","E","D","F"];
chart.setOption({{tooltip:{{trigger:"axis",formatter:function(ps){{const p=ps[0];return p.name+"："+p.value+"%（"+Math.round(p.value*9.99/100)+" 人）";}}}},
grid:{{left:10,right:44,top:10,bottom:20,containLabel:true}},xAxis:{{type:"value",max:70,axisLabel:{{formatter:"{{value}}%"}}}},
yAxis:{{type:"category",inverse:true,data:order.map(k=>LBL[k]),axisLabel:{{fontSize:14}}}},
series:[{{type:"bar",data:order.map(k=>({{value:DATA.share[k],itemStyle:{{color:k==="C"?"#E8A33D":(k==="A"?"#C24B3F":"#9FB0C8")}}}})),barWidth:26,
label:{{show:true,position:"right",formatter:"{{c}}%",fontWeight:"bold"}}}}]}});
}})();

// rank vs share
(function(){{const c=fig("fig_rank");if(!c)return;const chart=echarts.init(c);
const order=["A","B","C","D","E","F"];
chart.setOption({{tooltip:{{trigger:"axis",formatter:function(ps){{const p=ps[0];return p.name+"<br/>真实 BSR：第 "+RANK[p.dataIndex]+" 名<br/>模拟首选："+p.value+"%";}}}},
legend:{{bottom:0,data:["模拟首选率%"]}},
grid:{{left:10,right:20,top:20,bottom:40,containLabel:true}},
xAxis:{{type:"category",data:order.map(k=>LBL[k]),axisLabel:{{fontSize:12,interval:0}}}},
yAxis:{{type:"value",max:70,axisLabel:{{formatter:"{{value}}%"}}}},
series:[{{name:"模拟首选率%",type:"bar",data:order.map(k=>({{value:DATA.share[k],itemStyle:{{color:k==="A"?"#C24B3F":(k==="C"?"#E8A33D":"#3B6FB5")}}}})),barWidth:32,
label:{{show:true,position:"top",formatter:"{{c}}%",fontWeight:"bold"}}}}]}});
}})();

// A reject horizontal bar
(function(){{const c=fig("fig_areject");if(!c)return;const chart=echarts.init(c);
chart.setOption({{tooltip:{{trigger:"axis",formatter:function(ps){{const p=ps[0];return p.name+"："+p.value+"%";}}}},
grid:{{left:120,right:44,top:10,bottom:20,containLabel:true}},
xAxis:{{type:"value",max:90,axisLabel:{{formatter:"{{value}}%"}}}},
yAxis:{{type:"category",inverse:true,data:["品牌不熟","透明度不符","不喜欢外观","怕买不到/配送","价格太贵"],axisLabel:{{fontSize:13}}}},
series:[{{type:"bar",data:[{{value:2.8,itemStyle:{{color:"#9FB0C8"}}}},{{value:20.7,itemStyle:{{color:"#9FB0C8"}}}},{{value:21.8,itemStyle:{{color:"#9FB0C8"}}}},{{value:24.0,itemStyle:{{color:"#E8A33D"}}}},{{value:80.0,itemStyle:{{color:"#C24B3F"}}}}],barWidth:22,
label:{{show:true,position:"right",formatter:"{{c}}%",fontWeight:"bold"}}}}]}});
}})();

// factor most
(function(){{const c=fig("fig_factor");if(!c)return;const chart=echarts.init(c);
const cn={{price_value:"价格/价值",reviews:"评价内容",rating:"评分",material:"材质",magnet:"磁吸配重",appearance:"外观"}};
const d=DATA.factor_most;const order=Object.keys(d).sort((a,b)=>d[b]-d[a]);
chart.setOption({{tooltip:{{trigger:"axis",formatter:function(ps){{const p=ps[0];return p.name+"："+p.value+"%";}}}},
grid:{{left:10,right:44,top:10,bottom:20,containLabel:true}},xAxis:{{type:"value",max:60,axisLabel:{{formatter:"{{value}}%"}}}},
yAxis:{{type:"category",inverse:true,data:order.map(k=>cn[k]),axisLabel:{{fontSize:13}}}},
series:[{{type:"bar",data:order.map(k=>({{value:d[k],itemStyle:{{color:k==="price_value"?"#E8A33D":"#3B6FB5"}}}})),barWidth:20,
label:{{show:true,position:"right",formatter:"{{c}}%",fontWeight:"bold"}}}}]}});
}})();

// importance
(function(){{const c=fig("fig_importance");if(!c)return;const chart=echarts.init(c);
const cn={{reviews:"评价内容",price:"价格展示",image:"主图",attr:"属性表",trust:"信任标识",title:"标题",bullets:"五点描述",aplus:"A+ 图文页"}};
const d=DATA.importance;const order=Object.keys(d).sort((a,b)=>d[b]-d[a]);
chart.setOption({{tooltip:{{trigger:"axis",formatter:function(ps){{const p=ps[0];return p.name+"："+p.value+" / 5";}}}},
grid:{{left:10,right:48,top:10,bottom:20,containLabel:true}},xAxis:{{type:"value",max:5}},
yAxis:{{type:"category",inverse:true,data:order.map(k=>cn[k]),axisLabel:{{fontSize:13}}}},
series:[{{type:"bar",data:order.map(k=>({{value:d[k],itemStyle:{{color:k==="aplus"?"#C6CFDC":(k==="reviews"?"#E8A33D":"#3B6FB5")}}}})),barWidth:20,
label:{{show:true,position:"right",formatter:function(p){{return p.value.toFixed(2);}},fontWeight:"bold"}}}}]}});
}})();

// display position
(function(){{const c=fig("fig_position");if(!c)return;const chart=echarts.init(c);
chart.setOption({{tooltip:{{trigger:"item",formatter:"{{b}}：{{c}}%"}},
legend:{{bottom:0,textStyle:{{fontSize:11}}}},
series:[{{type:"pie",radius:["40%","68%"],center:["50%","46%"],
data:[
{{name:"完全没有影响",value:1.0,itemStyle:{{color:"#D1D5DB"}}}},
{{name:"一点点",value:90.3,itemStyle:{{color:"#5B8FF9"}}}},
{{name:"中等",value:8.7,itemStyle:{{color:"#E8A33D"}}}},
{{name:"很大 / 极其严重",value:0,itemStyle:{{color:"#C24B3F"}}}}],
label:{{formatter:"{{b}} {{c}}%"}}}}]}});
}})();

// ===== Bar Chart Race =====
(function(){{
const c=fig("fig_race");if(!c)return;
const seq=DATA.race_sequence;
const prods=["C","B","A","E","D","F"];
const colors={{"A":"#C24B3F","B":"#3B6FB5","C":"#E8A33D","D":"#9FB0C8","E":"#5B8FF9","F":"#6B7B8D"}};
const counts={{"A":0,"B":0,"C":0,"D":0,"E":0,"F":0}};
const chart=echarts.init(c);
let idx=0,timer=null;
function render(){{
  const arr=prods.map(k=>({{name:LBL[k],value:counts[k],key:k}})).sort((a,b)=>b.value-a.value);
  chart.setOption({{
    tooltip:{{trigger:"axis",axisPointer:{{type:"shadow"}},formatter:function(ps){{const p=ps[0];return p.name+"："+p.value+" 人";}}}},
    grid:{{left:10,right:50,top:10,bottom:24,containLabel:true}},
    xAxis:{{type:"value",max:700,axisLabel:{{formatter:"{{value}} 人"}}}},
    yAxis:{{type:"category",inverse:true,data:arr.map(d=>d.name),axisLabel:{{fontSize:13}}}},
    series:[{{type:"bar",data:arr.map(d=>({{value:d.value,itemStyle:{{color:colors[d.key]}}}})),barWidth:24,
      label:{{show:true,position:"right",formatter:"{{c}} 人",fontWeight:"bold"}},
      animationDurationUpdate:300,animationDuration:300}}],
    graphic:[{{type:"text",right:60,top:8,style:{{text:"第 "+idx+" / "+seq.length+" 人",fontSize:14,fontWeight:"bold",fill:"#64748B"}}}}]
  }});
}}
function play(){{
  if(timer)clearInterval(timer);
  prods.forEach(k=>counts[k]=0);idx=0;
  render();
  timer=setInterval(()=>{{
    for(let i=0;i<8 && idx<seq.length;i++){{counts[seq[idx]]++;idx++;}}
    render();
    if(idx>=seq.length){{clearInterval(timer);timer=null;}}
  }},60);
}}
document.getElementById("race_restart").onclick=play;
play();
}})();

// ===== Sankey =====
(function(){{
const c=fig("fig_sankey");if(!c)return;
chart=echarts.init(c);
chart.setOption({{
  tooltip:{{trigger:"item",triggerOn:"mousemove"}},
  series:[{{type:"sankey",left:20,right:120,top:20,bottom:20,
    nodeWidth:18,nodeGap:14,
    data:DATA.sankey_nodes,
    links:DATA.sankey_links,
    emphasis:{{focus:"adjacency"}},
    lineStyle:{{color:"gradient",curveness:0.5,opacity:0.45}},
    label:{{fontSize:12}},
    levels:[
      {{depth:0,itemStyle:{{color:"#5B8FF9"}}}},
      {{depth:1,itemStyle:{{color:"#E8A33D"}}}}
    ]
  }}]
}});
}})();

// ===== Word Cloud (chosen A) =====
(function(){{
const c=fig("fig_wordcloud");if(!c)return;
const chart=echarts.init(c);
chart.setOption({{
  tooltip:{{show:true,formatter:function(p){{return p.name+"："+p.value+" 次";}}}},
  series:[{{type:"wordCloud",
    shape:"circle",
    left:"center",top:"center",
    width:"95%",height:"95%",
    sizeRange:[11,40],
    rotationRange:[-20,20],
    gridSize:8,
    drawOutOfBound:false,
    textStyle:{{fontFamily:"sans-serif",fontWeight:"bold",
      color:function(){{return "hsl("+Math.round(Math.random()*360)+",45%,"+(35+Math.random()*25)+"%)";}}
    }},
    emphasis:{{textStyle:{{textShadowBlur:8,textShadowColor:"#333"}}}},
    data:DATA.wordcloud
  }}]
}});
}})();

// ===== Word Cloud (reject A) =====
(function(){{
const c=fig("fig_wordcloud_reject");if(!c)return;
const chart=echarts.init(c);
chart.setOption({{
  tooltip:{{show:true,formatter:function(p){{return p.name+"："+p.value+" 人提及";}}}},
  series:[{{type:"wordCloud",
    shape:"circle",
    left:"center",top:"center",
    width:"95%",height:"95%",
    sizeRange:[11,40],
    rotationRange:[-20,20],
    gridSize:8,
    drawOutOfBound:false,
    textStyle:{{fontFamily:"sans-serif",fontWeight:"bold",
      color:function(){{return "hsl("+Math.round(Math.random()*360)+",55%,"+(35+Math.random()*25)+"%)";}}
    }},
    emphasis:{{textStyle:{{textShadowBlur:8,textShadowColor:"#333"}}}},
    data:DATA.wordcloud_reject
  }}]
}});
}})();
</script>
</body></html>
"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)
print("written:", OUT, len(HTML), "bytes")
