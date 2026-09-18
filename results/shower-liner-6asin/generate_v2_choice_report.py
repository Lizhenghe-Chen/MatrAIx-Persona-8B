#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2 choice report (6asin + display-position) — A=我方视角, self-contained HTML."""
import base64, json, os

ROOT = "/Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B"
ASSETS = os.path.join(ROOT, "results/shower-liner-6asin/assets")
ECHARTS = os.path.join(ROOT, "playbooks/amazon-buyer-simulation/assets/echarts.min.js")
OUT = os.path.join(ROOT, "results/shower-liner-6asin-v2/shower_liner_v2_choice_report.html")

# 编号 | 短名 | 品牌 | 价格 | 评分 | 评价 | 真实BSR | 特征 | 图片 | 份额(v2) | ASIN | 状态
products = [
    dict(num="①", code="A", name="祖母绿", brand="AmazerBath", price="$18.99", rating="4.5★",
         reviews="4,156", rank="第 27 名", feat="最贵，但评价最多；页面显示配送受限、没有购买按钮",
         img="B0CGLZ56JC.jpg", share=16.6, asin="B0CGLZ56JC",
         status="配送受限", status_cls="warn", ours=True,
         reject=[("价格太贵", "83.4%（834 人）"), ("不喜欢外观", "27.0%"), ("怕买不到/配送", "22.5%"), ("透明度不符", "20.3%")]),
    dict(num="②", code="B", name="蓝波纹", brand="jssablo", price="$7.19", rating="4.4★",
         reviews="1,872", rank="第 41 名", feat="便宜、评价多，正常现货",
         img="B0C9MCD5WL.jpg", share=18.7, asin="B0C9MCD5WL",
         status="现货", status_cls="ok", ours=False,
         reject=[("不喜欢外观", "67.4%"), ("觉得太便宜不可信", "38.8%"), ("品牌不熟", "24.2%"), ("评分不够高", "16.8%")]),
    dict(num="③", code="C", name="水立方", brand="LQFMEHOT", price="$7.09", rating="4.6★",
         reviews="974", rank="第 124 名", feat="全场最便宜 + 评分最高，正常现货",
         img="B0C2GTPSFR.jpg", share=63.2, asin="B0C2GTPSFR",
         status="现货", status_cls="ok", ours=False,
         reject=[("品牌不熟", "33.4%"), ("觉得太便宜不可信", "24.7%"), ("不喜欢外观", "19.2%"), ("评价不够多", "16.6%")]),
    dict(num="④", code="D", name="鹅卵石", brand="Laumyasof", price="$9.99", rating="4.4★",
         reviews="16", rank="第 129 名", feat="2 件装，但评价只有 16 条（新上架）",
         img="B0GYWQQ2K3.jpg", share=0.0, asin="B0GYWQQ2K3",
         status="现货·新品", status_cls="warn", ours=False,
         reject=[("评价太少", "99.1%"), ("怀疑材质", "79.7%"), ("不想要2件装", "47.5%"), ("不喜欢外观", "8.8%")]),
    dict(num="⑤", code="E", name="纯黑", brand="Dependable", price="$9.99", rating="4.3★",
         reviews="116", rank="第 203 名", feat="黑色基础款，只剩 10 件",
         img="B0D212C4XS.jpg", share=1.5, asin="B0D212C4XS",
         status="仅剩 10 件", status_cls="warn", ours=False,
         reject=[("不喜欢外观", "93.9%"), ("怕没货/配送", "57.7%"), ("评价太少", "50.0%"), ("评分不够高", "20.1%")]),
    dict(num="⑥", code="F", name="波点", brand="MuuXii", price="无价", rating="4.4★",
         reviews="10", rank="第 856 名", feat="页面显示暂时缺货、没有价格",
         img="B0FSRN9YTK.jpg", share=0.0, asin="B0FSRN9YTK",
         status="缺货", status_cls="bad", ours=False,
         reject=[("评价太少", "97.7%"), ("缺货/配送", "93.2%"), ("尺寸不合适", "33.9%"), ("透明度不符", "4.3%")]),
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

# ---- data into JS ----
DATA = {
    "share": {p["code"]: p["share"] for p in products},
    "factor_most": {"price_value": 55.0, "reviews": 21.9, "rating": 17.2, "material": 2.8, "magnet": 1.9, "appearance": 1.0, "waterproof": 0.2},
    "importance": {"reviews": 4.89, "price": 4.61, "image": 4.33, "attr": 4.10, "trust": 4.09, "title": 3.98, "bullets": 3.86, "aplus": 1.99},
    "redline": {"unavailable": 100.0, "material_unclear": 98.7, "blur_image": 96.2, "no_price": 91.7, "no_size": 91.3, "low_rating": 83.3, "few_reviews": 64.1, "no_bullets": 11.1},
    "switch_trigger": {"better_rating": 66.3, "better_function": 15.1, "lower_price": 8.1, "nothing": 5.2, "better_value": 4.9, "better_look": 0.4},
    "badge_effect": {"yes_somewhat": 91.3, "neutral": 3.9, "unlikely": 3.8, "yes_strongly": 0.9, "no_effect": 0.1},
    "page_buy": {"page1": 96.4, "page2": 3.6},
    "display_position": {"not_at_all": 0.9, "slightly": 90.5, "moderately": 8.6, "very_much": 0.0, "extremely": 0.0},
    # 选 A 的人最看重因素（n=166）
    "amotivation": {"reviews": 76.0, "material": 16.0, "price_value": 5.0, "rating": 2.0, "other": 1.0},
}
DATA_JSON = json.dumps(DATA, ensure_ascii=False)

# quick table rows
qrows = "".join(
    f'<tr{" style=\"background:#fdecea\"" if p["ours"] else ""}>'
    f'<td>{p["num"]}</td><td>{p["name"]}</td><td>{p["brand"]}'
    f'{" <span class=\"ours-tag\">我方</span>" if p["ours"] else ""}</td>'
    f'<td>{p["price"]}</td><td>{p["rating"]}</td><td>{p["reviews"]}</td>'
    f'<td>{p["rank"]}</td><td>{p["feat"]}</td></tr>'
    for p in products)

# product cards
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

# reject table rows
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
<title>浴帘内衬买家测试报告 · ① 祖母绿（我方）视角 · n=1000</title>
<style>{CSS}</style></head><body>

<header class="hero"><div class="hero-inner">
  <div class="kicker">AMAZON US · 浴帘内衬 · 货架选择实验（v2）</div>
  <h1>6 款浴帘内衬，1000 位买家选哪个？——我方 ① 祖母绿 的位置在哪里</h1>
  <div class="sub">让 1000 位模拟买家在亚马逊搜索结果里挑浴帘内衬：选 1 款、说理由、说明为什么不选其他 5 款，并额外回答「搜索结果展示位置对购买决策的影响」。下面用最简单的图告诉你——谁赢了、为什么、我方 ① 祖母绿 下一步该做什么。</div>
  <div class="chips"><span>n = 1,000 位美国买家</span><span>6 款真实商品</span><span>我方 = ① 祖母绿（AmazerBath）</span><span>v2 含展示位置题</span></div>
  <div class="kpi-row">
    <div class="kpi"><div class="lbl">大家最想买</div><div class="v">③ 水立方 63.2%</div><div class="s">$7.09 + 4.6★，一家独大</div></div>
    <div class="kpi"><div class="lbl">我方 ① 祖母绿</div><div class="v">16.6%（第 3 名）</div><div class="s">与 ② 蓝波纹 18.7% 基本接近</div></div>
    <div class="kpi"><div class="lbl">选我方的人最看重</div><div class="v">评价 76%</div><div class="s">仅 5% 最看重价格</div></div>
    <div class="kpi"><div class="lbl">展示位置影响</div><div class="v">90.5% 说"一点点"</div><div class="s">无人认为"很大/极其严重"</div></div>
  </div>
</div></header>

<main>

<section id="s0"><div class="hl-banner"><h2>先看结论（5 句话）</h2>
<div class="hl-grid">
  <div class="hl-card"><div class="n">① 赢家是 ③ 水立方，我方排第三</div>
    <p>③ 以 $7.09 + 4.6★ 拿走 63.2%；我方 ① 16.6%，与 ② 蓝波纹（18.7%）只差 2.1 个百分点，同属第二梯队。</p>
    <div class="ev">数据：选择分布 n=1000</div></div>
  <div class="hl-card"><div class="n">② 我方的核心资产是"评价"</div>
    <p>选我方的 166 人里 76% 最看重评价（4,156 条/4.5★），仅 5% 看价格。我方吸引的是"重证据"人群，不是价格敏感人群。</p>
    <div class="ev">数据：选 A 者第一考量 n=166</div></div>
  <div class="hl-card"><div class="n">③ 我方最该先修的不是产品，是"买不了"</div>
    <p>未选我方的 834 人中，22.5% 提到"无购买按钮/配送受限"——这是用户想买却买不到的硬门槛。</p>
    <div class="ev">数据：availability 提及率 n=834</div></div>
  <div class="hl-card"><div class="n">④ 价格是最集中的负面提及，但不等于流失原因</div>
    <p>83.4% 未选我方的人嫌 $18.99 贵。但选我方的人仅 5% 看价格——"嫌贵"是大盘现象，不代表降价一定能拉新客。</p>
    <div class="ev">数据：reject_A price_too_high 83.4%</div></div>
  <div class="hl-card"><div class="n">⑤ 搜索排名位次不是当前杠杆</div>
    <p>90.5% 的人认为展示位置只有"一点点"影响，无人选"很大/极其严重"。在购买按钮和价格叙事解决前，卡位排名投入产出比低。</p>
    <div class="ev">数据：display_position n=1000</div></div>
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
  <div class="sec-desc">n=1,000 名美国亚马逊买家。</div>
  <div class="card">
    <ul>
      <li><b>整体价格敏感：</b>55.0% 的人把"价格/性价比"列为第一考量，21.9% 看重评价，17.2% 看重评分。</li>
      <li><b>但选我方的人例外：</b>选 ① 的 166 人里，76% 最看重评价，仅 5% 看价格——我方客群与大盘价格敏感人群不同。</li>
      <li>年龄、性别、收入、家庭结构等人口统计维度当前数据未覆盖，不做画像推断。</li>
    </ul>
  </div>
</section>

<section id="s2">
  <div class="sec-head"><span class="sec-no">2</span><h2>测试怎么做的</h2></div>
  <div class="card">
    <div class="callout">每位买家看到 6 款产品卡片（价格、评分、评价数、图片、描述、库存状态），依次完成：<b>① 选 1 款并说理由 → ② 对其余 5 款分别说拒绝原因（多选）→ ③ 给商品页 8 个部分打重要性分 → ④ 回答哪些情况会直接不买 → ⑤ 回答展示位置对购买决策的影响程度</b>。</div>
    <p style="font-size:13px;color:var(--muted);margin:8px 0 0;">观察的是"静态货架"上的第一选择：不加广告、不靠排名提示，纯看商品本身。多选题百分比 = 选该原因的人数 ÷ 1000。</p>
  </div>
</section>

<section id="s3">
  <div class="sec-head"><span class="sec-no">3</span><h2>结果：谁赢谁输</h2></div>
  <div class="sec-desc">一张图看懂首选份额。1000 人每人选 1 款。</div>
  <div class="card"><h3>大家第一选择的比例</h3>
    <div class="fig sm" id="fig_share"></div>
    <div class="takeaway"><b>一句话：</b>③ 水立方拿走 63.2%；② 蓝波纹 18.7% 和我方 ① 16.6% 基本接近；⑤ 纯黑 1.5%；④⑥ 无人选。</div>
  </div>
  <div class="card"><h3>真实 BSR 排名 vs 大家的选择（排得靠前 ≠ 大家想买）</h3>
    <div class="fig sm" id="fig_rank"></div>
    <div class="takeaway"><b>一句话：</b>真实 BSR 最靠前的是我方 ①（第 27 名），但模拟首选只有 16.6%；③ 水立方真实 BSR 第 124 名，却是首选冠军。<b>真实排名是"销量+流量"算出来的，不完全等于"买家在纯货架对比下真的想要"。</b></div>
  </div>
</section>

<section id="s4">
  <div class="sec-head"><span class="sec-no">4</span><h2>为什么选、为什么不选</h2></div>
  <div class="sec-desc">全部来自买家勾选的选项和开放理由。</div>

  <div class="card"><h3>选我方 ① 的人，最看重什么（n=166）</h3>
    <div class="fig sm" id="fig_amotivation" style="height:280px"></div>
    <div class="takeaway"><b>一句话：</b>选我方的人 76% 由"评价"驱动，16% 看重材质安全，仅 5% 看价格——<b>我方的客群要的是"靠谱耐用"，不是便宜。</b></div>
  </div>

  <div class="card"><h3>为什么没选我方 ①（n=834，多选）</h3>
    <div class="fig sm" id="fig_areject" style="height:300px"></div>
    <div class="takeaway"><b>一句话：</b>83.4% 嫌贵、22.5% 因"买不到/配送受限"放弃、27.0% 不喜欢外观、20.3% 嫌透明度不符。<b>"嫌贵"是高频提及，但选我方的人不看价格——这说明价格主要挡的是大盘人群，而非我方已有客群。</b></div>
  </div>

  <div class="card"><h3>每款产品被拒绝的主要原因（占比 = 人数 ÷ 1000）</h3>
    <table>
      <tr><th style="width:140px;">产品</th><th>买家不选它的主要原因</th></tr>
      {rrows}
    </table>
    <div class="takeaway"><b>一句话：</b>我方 ① 死在"太贵 + 买不到"；③ 水立方的弱点只是"品牌不熟"；④⑥ 死在"评价太少/缺货"。</div>
  </div>

  <div class="card"><h3>买浴帘时最看重什么（第一因素，n=1000）</h3>
    <div class="fig sm" id="fig_factor" style="height:300px"></div>
    <div class="takeaway"><b>一句话：</b>大盘 55% 看价格，但选我方的人只有 5% 看价格——<b>我方在价格战场上不占优，但在"评价信任"战场上是头部。</b></div>
  </div>

  <div class="card"><h3>商品页 8 个部分，哪个最重要（5 分制）</h3>
    <div class="fig sm" id="fig_importance" style="height:320px"></div>
    <div class="takeaway"><b>一句话：</b>评价内容 4.89、价格展示 4.61、主图 4.33 最高；A+ 图文页 1.99 垫底。<b>做页面的钱先花在评价、价格、主图上。</b></div>
  </div>

  <div class="card"><h3>哪些情况会让买家直接不买（一票否决）</h3>
    <div class="fig sm" id="fig_redline" style="height:320px"></div>
    <div class="takeaway"><b>一句话：</b>缺货 100%、材质不明 98.7%、图片模糊 96.2%、没标价格 91.7%——<b>这四条是及格线。我方 ① 目前卡在"缺货/配送受限"这条红线上。</b></div>
  </div>

  <div class="card"><h3>愿意翻到第几页购买</h3>
    <div class="fig sm" id="fig_page" style="height:260px"></div>
    <div class="takeaway"><b>一句话：</b>96.4% 的人只在第 1 页购买。</div>
  </div>

  <div class="card"><h3>什么情况会让买家改选别家</h3>
    <div class="fig sm" id="fig_switch" style="height:300px"></div>
    <div class="takeaway"><b>一句话：</b>66.3% 的人会因"别家评分更高"而换选——评分是硬杠杆。</div>
  </div>

  <div class="card"><h3>新题：搜索结果展示位置对购买决策的影响程度（n=1000）</h3>
    <div class="fig sm" id="fig_position" style="height:280px"></div>
    <div class="takeaway"><b>一句话：</b>90.5% 选"一点点"，8.6%"中等"，0.9%"完全没影响"，<b>无人选"很大/极其严重"</b>。无论最终选 ①②③，分布几乎一致。<b>位置是结果不是杠杆——先解决价格叙事和购买按钮，再谈卡位。</b></div>
  </div>

  <div class="card"><h3>买家原话（节选）</h3>
    <div class="quote">"我被便宜薄内衬用坏、发霉坑过，所以宁愿多花一点，选有 4,156 条评价、4.5★ 的那款……BPA-free、无味、黄铜气眼、加重底。" <span style="color:var(--muted);font-size:11.5px;">—— 选我方 ① 的买家</span></div>
    <div class="quote">"每天挂在潮湿浴室、直接碰水的东西，4,156 条评价和 4.5★ 让我确信它真的耐用。" <span style="color:var(--muted);font-size:11.5px;">—— 选我方 ① 的买家</span></div>
    <div class="quote">"① 看起来不错但太贵了，$18.99 比其他家贵一倍多，$7 的 ③ 评分还更高。" <span style="color:var(--muted);font-size:11.5px;">—— 未选我方的买家</span></div>
  </div>
</section>

<section id="s5">
  <div class="sec-head"><span class="sec-no">5</span><h2>对我方 ① 意味着什么</h2></div>
  <div class="sec-desc">不重复数据，只做集中诊断。</div>
  <div class="grid2">
    <div class="card"><h3><span class="tag tag-good">KEEP</span> 已被验证的优势</h3>
      <p><b>评价资产：</b>4,156 条评价、4.5★ 是我方相对所有竞品最厚的信任状，选我方的人 76% 由评价驱动。继续积累评价、在 listing 前置。</p>
      <p><b>高端客群成立：</b>选我方的人仅 5% 看价格，说明"耐用 + BPA-free + 黄铜气眼"的高端定位有真实买单人群，不必盲目降价跟随 ③。</p>
    </div>
    <div class="card"><h3><span class="tag tag-fix">FIX</span> 有较充分证据的问题</h3>
      <p><b>购买按钮缺失（22.5% 未选者提及）：</b>采集时页面 no featured offer、配送受限。这是"想买买不到"的硬门槛，优先级高于价格讨论。</p>
      <p><b>高价在大盘中的接受度：</b>83.4% 未选者嫌贵。但选我方的人不看价格——问题不是"降价"，而是"价格敏感人群看不到我方价值"。</p>
    </div>
    <div class="card"><h3><span class="tag tag-test">TEST</span> 信号出现但证据不足</h3>
      <p><b>外观/透明度：</b>27.0% 不喜欢外观、20.3% 嫌透明度不符。但样本有限，且未与"是否选我方"直接挂钩，不建议为此改款。</p>
      <p><b>"买不到"流失的可回收量：</b>22.5% 因 availability 放弃，恢复购买按钮后有多少人会回来，当前数据无法回答。</p>
    </div>
    <div class="card"><h3><span class="tag tag-good">BASELINE</span> 大盘及格线</h3>
      <p>缺货/材质不明/图片模糊/没标价格，90%+ 的人会直接放弃。我方目前卡在"配送受限"这条红线上——这不是优化项，是生存项。</p>
    </div>
  </div>
</section>

<section id="s6">
  <div class="sec-head"><span class="sec-no">6</span><h2>下一步怎么做（按把握大小排序）</h2></div>
  <div class="card">
    <table>
      <tr><th style="width:90px;">把握</th><th style="width:220px;">做什么</th><th>为什么 / 依据</th></tr>
      <tr class="our-row"><td><span class="tag tag-do">马上做</span></td><td><b>恢复 ① 的 Featured Offer / 可下单状态</b></td><td>22.5% 未选者因"无购买按钮/配送受限"直接放弃。这是唯一"用户想买却买不到"的环节，不需要改产品或定价。<br><b>依据：</b>reject_A availability 22.5%（n=834）。</td></tr>
      <tr class="our-row"><td><span class="tag tag-do">马上做</span></td><td><b>Listing 前置"4,156 评价 + 4.5★ + BPA-free"信任状</b></td><td>选我方的人 76% 由评价驱动、仅 5% 看价格。把信任状和材质故事放在首图/标题/首条 bullet，比降价更能守住已有客群。<br><b>依据：</b>选 A 者第一考量 n=166；importance_reviews 4.89/5 全场最高。</td></tr>
      <tr><td><span class="tag tag-try">试试看</span></td><td><b>测试 $9.99 引流款（变体或新链接）</b></td><td>83.4% 嫌贵，但我方核心客群不看价格。用一个共享评价资产的引流款覆盖价格敏感人群（大盘 55%），不动 $18.99 高端款。<br><b>依据：</b>reject_A price_too_high 83.4%；factor_most price_value 55% vs 选 A 者 5%。</td></tr>
      <tr><td><span class="tag tag-try">试试看</span></td><td><b>恢复购买按钮后复测选择率</b></td><td>量化 22.5% availability 流失中可回收的部分，确认"买得到"本身能带来多少选择率提升。<br><b>依据：</b>当前数据无法回答"能买到后转化率"。</td></tr>
      <tr><td><span class="tag tag-watch">先观望</span></td><td><b>搜索排名位次卡位</b></td><td>90.5% 的人认为展示位置只有"一点点"影响，无人选"很大/极其严重"。在购买按钮和价格叙事解决前，不建议把预算投在卡位排名上。<br><b>依据：</b>display_position n=1000。</td></tr>
      <tr><td><span class="tag tag-watch">先观望</span></td><td><b>为外观/透明度改款</b></td><td>27.0% 不喜欢外观、20.3% 嫌透明度不符，但未与"是否选我方"直接挂钩，样本有限。暂不为此改款。<br><b>依据：</b>reject_A look 27.0% / transparency 20.3%。</td></tr>
    </table>
    <div style="font-size:12.5px;color:var(--muted);margin-top:8px;">
      注："试试看"来自本次数据信号，需下一轮验证；本次为静态货架选择实验，不能证明"改了价格/按钮就一定提升销量"。
      百分比均基于对应题项有效回答人数；多选题百分比为提及率（人数÷1000），不等于购买驱动力；未做统计显著性检验。
    </div>
  </div>
</section>

<div class="footer">浴帘内衬 v2 货架选择报告 · 我方 = ① 祖母绿（AmazerBath） · n=1000 · 2026-09-18<br>
所有数字来自原始答卷，可追溯核对 · ECharts 内嵌、离线可开</div>
</main>

<script>{ECHARTS_JS}</script>
<script>
const DATA = {DATA_JSON};
const LBL = {{A:"① 祖母绿（我方）",B:"② 蓝波纹",C:"③ 水立方",D:"④ 鹅卵石",E:"⑤ 纯黑",F:"⑥ 波点"}};
const RANK = {{A:27,B:41,C:124,D:129,E:203,F:856}};
function fig(id){{return document.getElementById(id);}}

// share horizontal bar
(function(){{const c=fig("fig_share");if(!c)return;const chart=echarts.init(c);
const order=["C","B","A","E","D","F"];
chart.setOption({{tooltip:{{trigger:"axis",formatter:function(ps){{const p=ps[0];return p.name+"："+p.value+"%（"+Math.round(p.value)+" 人）";}}}},
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

// A motivation pie
(function(){{const c=fig("fig_amotivation");if(!c)return;const chart=echarts.init(c);
chart.setOption({{tooltip:{{trigger:"item",formatter:"{{b}}：{{c}}%"}},
legend:{{bottom:0,textStyle:{{fontSize:11}}}},
series:[{{type:"pie",radius:["40%","68%"],center:["50%","46%"],
data:[{{name:"评价（reviews）",value:76,itemStyle:{{color:"#C24B3F"}}}},{{name:"材质安全",value:16,itemStyle:{{color:"#E8A33D"}}}},{{name:"价格/性价比",value:5,itemStyle:{{color:"#9FB0C8"}}}},{{name:"其他",value:3,itemStyle:{{color:"#D1D5DB"}}}}],
label:{{formatter:"{{b}} {{c}}%"}}}}]}});
}})();

// A reject horizontal bar
(function(){{const c=fig("fig_areject");if(!c)return;const chart=echarts.init(c);
chart.setOption({{tooltip:{{trigger:"axis",formatter:function(ps){{const p=ps[0];return p.name+"："+p.value+"%";}}}},
grid:{{left:120,right:44,top:10,bottom:20,containLabel:true}},
xAxis:{{type:"value",max:90,axisLabel:{{formatter:"{{value}}%"}}}},
yAxis:{{type:"category",inverse:true,data:["透明度不符","不喜欢外观","怕买不到/配送","价格太贵"],axisLabel:{{fontSize:13}}}},
series:[{{type:"bar",data:[{{value:20.3,itemStyle:{{color:"#9FB0C8"}}}},{{value:27.0,itemStyle:{{color:"#9FB0C8"}}}},{{value:22.5,itemStyle:{{color:"#E8A33D"}}}},{{value:83.4,itemStyle:{{color:"#C24B3F"}}}}],barWidth:22,
label:{{show:true,position:"right",formatter:"{{c}}%",fontWeight:"bold"}}}}]}});
}})();

// factor most
(function(){{const c=fig("fig_factor");if(!c)return;const chart=echarts.init(c);
const cn={{price_value:"价格/价值",reviews:"评价内容",rating:"评分",material:"材质",magnet:"磁吸配重",appearance:"外观",waterproof:"防水"}};
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

// redline
(function(){{const c=fig("fig_redline");if(!c)return;const chart=echarts.init(c);
const cn={{unavailable:"缺货",material_unclear:"材质不明",blur_image:"图片模糊",no_price:"没标价格",no_size:"没标尺寸",low_rating:"评分低",few_reviews:"评价太少",no_bullets:"没有五点描述"}};
const d=DATA.redline;const order=Object.keys(d).filter(k=>d[k]>0).sort((a,b)=>d[b]-d[a]);
chart.setOption({{tooltip:{{trigger:"axis",formatter:function(ps){{const p=ps[0];return p.name+"："+p.value+"%";}}}},
grid:{{left:10,right:48,top:10,bottom:20,containLabel:true}},xAxis:{{type:"value",max:100,axisLabel:{{formatter:"{{value}}%"}}}},
yAxis:{{type:"category",inverse:true,data:order.map(k=>cn[k]),axisLabel:{{fontSize:12.5}}}},
series:[{{type:"bar",data:order.map(k=>({{value:d[k],itemStyle:{{color:d[k]>=90?"#C24B3F":(d[k]>=60?"#E8A33D":"#9FB0C8")}}}})),barWidth:20,
label:{{show:true,position:"right",formatter:"{{c}}%",fontSize:12}}}}]}});
}})();

// page buy
(function(){{const c=fig("fig_page");if(!c)return;const chart=echarts.init(c);
const d=DATA.page_buy;const keys=Object.keys(d);
chart.setOption({{tooltip:{{trigger:"item",formatter:"{{b}}：{{c}}%"}},
grid:{{left:10,right:20,top:14,bottom:20,containLabel:true}},
xAxis:{{type:"category",data:keys.map(k=>k.replace("page","第")+"页")}},
yAxis:{{type:"value",max:100,axisLabel:{{formatter:"{{value}}%"}}}},
series:[{{type:"bar",data:keys.map(k=>({{value:d[k],itemStyle:{{color:k==="page1"?"#E8A33D":"#9FB0C8"}}}})),barWidth:44,
label:{{show:true,position:"top",formatter:"{{c}}%",fontWeight:"bold"}}}}]}});
}})();

// switch trigger pie
(function(){{const c=fig("fig_switch");if(!c)return;const chart=echarts.init(c);
const cn={{better_rating:"别家评分更高",better_function:"别家功能更好",lower_price:"别家更便宜",better_value:"别家更划算",nothing:"都不会换",better_look:"别家更好看"}};
const d=DATA.switch_trigger;const order=["better_rating","better_function","lower_price","better_value","nothing","better_look"];
chart.setOption({{tooltip:{{trigger:"item",formatter:"{{b}}：{{c}}%"}},
legend:{{bottom:0,textStyle:{{fontSize:11}}}},
series:[{{type:"pie",radius:["38%","64%"],center:["50%","44%"],
data:order.map(k=>({{name:cn[k],value:d[k]||0}})),label:{{fontSize:11,formatter:"{{b}} {{d}}%"}}}}]}});
}})();

// display position
(function(){{const c=fig("fig_position");if(!c)return;const chart=echarts.init(c);
chart.setOption({{tooltip:{{trigger:"item",formatter:"{{b}}：{{c}}%"}},
legend:{{bottom:0,textStyle:{{fontSize:11}}}},
series:[{{type:"pie",radius:["40%","68%"],center:["50%","46%"],
data:[
{{name:"完全没有影响",value:0.9,itemStyle:{{color:"#D1D5DB"}}}},
{{name:"一点点",value:90.5,itemStyle:{{color:"#5B8FF9"}}}},
{{name:"中等",value:8.6,itemStyle:{{color:"#E8A33D"}}}},
{{name:"很大 / 极其严重",value:0,itemStyle:{{color:"#C24B3F"}}}}],
label:{{formatter:"{{b}} {{c}}%"}}}}]}});
}})();
</script>
</body></html>
"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)
print("written:", OUT, len(HTML), "bytes")
