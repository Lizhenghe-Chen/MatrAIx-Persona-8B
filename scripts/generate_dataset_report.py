# -*- coding: utf-8 -*-
"""生成 MatrAIx Persona 1M 数据集数据源分析报告（HTML 单文件，内联 SVG 图表）。"""
import html, json

OUT = "results/dataset_source_analysis.html"
ESC = html.escape

# ---------- 数据（全部来自官方文档或实际数据，见报告脚注） ----------
SOURCES = [
    ("synthetic", "Full-DAG 合成人格", 400000, "990 / 990", "本项目内生成；依赖感知的合成生成（DAG）"),
    ("wiki", "维基百科人物词条", 323438, "388", "正则+LLM 抽取的人物画像属性"),
    ("stackoverflow", "Stack Overflow 开发者问卷", 113120, "68", "年度开发者调查（2023 系）"),
    ("amazon", "Amazon 商品评论", 97915, "16", "Amazon Reviews 2023（McAuley Lab）抽取"),
    ("gss", "GSS 综合社会调查", 63532, "12", "NORC 综合社会调查（美国）"),
    ("prism", "PRISM 对齐数据", 1487, "144", "对齐研究文本（Human+Model 混合）"),
    ("real_human_survey", "真人问卷（MatrAIx 自采）", 355, "990", "知情同意采集，<18 岁已剔除"),
]
SOURCE_TOTAL = 999847
HUMAN = 599847

CATS = [
    ("人口与背景", 52, "年龄、地区、性别、城乡、人生阶段、家庭、文化归属"),
    ("语言与沟通", 90, "母语、多语、英语水平、沟通风格"),
    ("专业与技能", 356, "144 专业领域、64 技能、69 工具、44 编程、学习"),
    ("人格与心理", 215, "大五人格、MBTI、性格特征、价值观、世界观、情绪、风险"),
    ("职业与行业", 55, "职业角色、51 个行业"),
    ("行为与习惯", 69, "时间、偏好、工作行为、习惯"),
    ("健康", 29, "体能、生活方式、身体状况"),
    ("兴趣与媒介", 358, "话题、文化、媒体、饮食、运动、爱好"),
    ("开发者专项", 66, "AI 工作流、代码维护、开源行为、智能体采用等"),
]
CAT_TOTAL = 1290

CALIB = {
    "age_bracket": (704641, 295359, 0.0749, "UN WPP 2024"),
    "region": (874653, 125347, 14.0047, "UN WPP 2024"),
    "gender_identity": (774736, 225264, 0.0375, "UN + World Bank"),
    "urbanicity": (582321, 417679, 0.0478, "UN + World Bank"),
}

AGE = [("Under 5",8.4),("5-12",13.0),("13-17",8.2),("18-24",10.6),("25-34",14.5),("35-44",13.3),("45-54",11.5),("55-64",10.5),("65-74",6.1),("75-84",2.8),("85+",1.1)]
REGION = [("North America",18.8),("South Asia",18.4),("East Asia",14.1),("Sub-Saharan Africa",12.2),("Western Europe",11.7),("Latin America",6.8),("Southeast Asia",6.4),("MENA",5.4),("Eastern Europe",4.9),("Oceania",1.4)]
GENDER = [("Man",49.8),("Woman",49.5),("Non-binary",0.3),("Self-described",0.2),("Prefer not to say",0.2)]
URBAN = [("Rural",34.5),("Dense urban",24.5),("Suburban",21.0),("Small town",18.5),("Nomadic / remote",1.5)]

# sample.parquet 非校准维度分布（999 人解码样本）
SAMPLE_SOCIO = [("Lower-middle",24.9),("Middle",23.8),("Low income",19.9),("Upper-middle",17.5),("High income",9.3)]
SAMPLE_MOTIV = [("Cost-sensitive",45.5),("Value-driven",34.9),("Indifferent",12.4),("Premium-seeking",5.2)]

PARQUET_COLS = [
    ("source", "数据来源（wiki / stackoverflow / amazon / gss / prism / real_human_survey / synthetic）"),
    ("source_row_index", "在来源中的原始行号"),
    ("source_record_id", "来源记录 ID（可回溯到上游）"),
    ("attributes", "645 字节 4-bit 打包的 1,290 个属性编码（核心负载）"),
    ("null_bitmap", "缺失位图：置位=该维度缺失（稀疏行）"),
    ("attribute_overrides", "超出码本范围的精确取值（覆盖编码）"),
    ("has_description / description_count / descriptions", "字段级自然语言描述（42.26% 的行有）"),
    ("grounding", "逐字段证据、置信度、赋值类型（可追溯）"),
    ("metadata_json", "来源特定元数据"),
    ("populated_attribute_count", "该行实际填充的属性数（平均 656/1290）"),
]

# ---------- SVG 工具 ----------
def hbar(data, maxv, color, width=560, label_w=190, height=18, gap=4, unit="%"):
    """data: [(label, value, note?)] 横向条形图"""
    rows = []
    for i, (label, value) in enumerate(data):
        w = int(max(6, value / maxv * (width - label_w - 90)))
        y = 14 + i * (height + gap)
        rows.append(f'<text x="{label_w-10}" y="{y+13}" text-anchor="end" font-size="13" fill="#334155">{ESC(label)}</text>')
        rows.append(f'<rect x="{label_w}" y="{y}" width="{w}" height="{height}" rx="3" fill="{color}"/>')
        rows.append(f'<text x="{label_w+w+8}" y="{y+13}" font-size="12.5" fill="#0f172a" font-weight="600">{value}{unit}</text>')
    return f'<svg viewBox="0 0 {width} {28+len(data)*(height+gap)}" width="100%" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="bar chart">' + "".join(rows) + "</svg>"

def hbar_num(data, maxv, color, width=560, label_w=200, height=18, gap=4):
    rows = []
    for i, (label, value) in enumerate(data):
        w = int(max(6, value / maxv * (width - label_w - 110)))
        y = 14 + i * (height + gap)
        rows.append(f'<text x="{label_w-10}" y="{y+13}" text-anchor="end" font-size="13" fill="#334155">{ESC(label)}</text>')
        rows.append(f'<rect x="{label_w}" y="{y}" width="{w}" height="{height}" rx="3" fill="{color}"/>')
        rows.append(f'<text x="{label_w+w+8}" y="{y+13}" font-size="12.5" fill="#0f172a" font-weight="600">{value:,}</text>')
    return f'<svg viewBox="0 0 {width} {28+len(data)*(height+gap)}" width="100%" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="bar chart">' + "".join(rows) + "</svg>"

def donut(data, color_fn, size=190, label_cx=95):
    """data: [(label, value)] 环形图"""
    total = sum(v for _, v in data)
    import math
    parts = []
    start = -90.0
    cx = cy = size / 2
    r = size * 0.36
    for i, (label, value) in enumerate(data):
        frac = value / total
        ang = frac * 360
        end = start + ang
        large = 1 if ang > 180 else 0
        x1 = cx + r * math.cos(math.radians(start)); y1 = cy + r * math.sin(math.radians(start))
        x2 = cx + r * math.cos(math.radians(end));   y2 = cy + r * math.sin(math.radians(end))
        if abs(frac - 1.0) < 1e-9:
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color_fn(i)}"/>')
        else:
            parts.append(f'<path d="M {x1:.1f} {y1:.1f} A {r} {r} 0 {large} 1 {x2:.1f} {y2:.1f}" fill="none" stroke="{color_fn(i)}" stroke-width="{r}" />')
        start = end
    return f'<svg viewBox="0 0 {size} {size}" width="100%" style="max-width:{size}px" xmlns="http://www.w3.org/2000/svg" role="img">' + "".join(parts) + "</svg>"

PALETTE = ["#2563eb", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#64748b", "#14b8a6", "#f97316", "#6366f1", "#84cc16", "#ec4899"]

def legend(data, color_fn, cols=2):
    items = []
    n = len(data)
    per = (n + cols - 1) // cols
    for i, (label, value) in enumerate(data):
        items.append(f'<div style="display:flex;align-items:center;gap:6px;margin:3px 10px 3px 0;min-width:150px"><span style="width:12px;height:12px;border-radius:3px;background:{color_fn(i)};flex:none"></span><span style="font-size:12.5px;color:#334155">{ESC(label)} · {value:,.0f}（{value/999847*100:.1f}%）</span></div>')
    return f'<div style="display:flex;flex-wrap:wrap;justify-content:center">{ "".join(items) }</div>'

# ---------- 页面 ----------
PAGE = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MatrAIx Persona 1M 数据集 · 数据源分析报告</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%232563eb'/%3E%3Ccircle cx='16' cy='13' r='6' fill='white'/%3E%3Crect x='9' y='20' width='14' height='4' rx='2' fill='white' opacity='0.85'/%3E%3C/svg%3E">
<link rel="stylesheet" href="https://miaoda.feishu.cn/fonts/css2?family=Noto+Sans+SC:wght@300;400;500;600;700;900&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
  :root {{
    --ink:#0f172a; --sub:#475569; --mut:#94a3b8; --line:#e2e8f0;
    --bg:#f8fafc; --card:#ffffff; --brand:#2563eb; --brand2:#0ea5e9;
    --good:#10b981; --warn:#f59e0b; --bad:#ef4444;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:"Noto Sans SC",-apple-system,"PingFang SC","Microsoft YaHei",sans-serif; background:var(--bg); color:var(--ink); line-height:1.7; }}
  .wrap {{ max-width:1060px; margin:0 auto; padding:0 24px 80px; }}
  .hero {{ background:linear-gradient(135deg,#1e3a8a 0%,#2563eb 55%,#0ea5e9 100%); color:#fff; border-radius:0 0 28px 28px; padding:56px 24px 44px; text-align:center; }}
  .hero .tag {{ display:inline-block; background:rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.35); padding:4px 14px; border-radius:999px; font-size:12.5px; letter-spacing:1px; margin-bottom:18px; }}
  .hero h1 {{ font-size:clamp(26px,4vw,40px); font-weight:900; letter-spacing:.5px; }}
  .hero .sub {{ margin-top:12px; font-size:clamp(14px,2vw,17px); opacity:.92; max-width:760px; margin-left:auto; margin-right:auto; }}
  .hero .meta {{ margin-top:18px; font-size:12.5px; opacity:.8; }}
  .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:14px; margin-top:-34px; padding:0 24px; max-width:1060px; margin-left:auto; margin-right:auto; position:relative; z-index:2; }}
  .stat {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px 14px; text-align:center; box-shadow:0 8px 24px rgba(15,23,42,.06); }}
  .stat .n {{ font-size:clamp(22px,3vw,30px); font-weight:900; color:var(--brand); font-family:"JetBrains Mono","Noto Sans SC",monospace; }}
  .stat .l {{ font-size:12.5px; color:var(--sub); margin-top:4px; }}
  section {{ background:var(--card); border:1px solid var(--line); border-radius:16px; padding:30px 30px; margin-top:26px; }}
  h2 {{ font-size:22px; font-weight:800; display:flex; align-items:center; gap:10px; margin-bottom:6px; }}
  h2 .no {{ background:var(--brand); color:#fff; width:28px; height:28px; border-radius:8px; display:inline-flex; align-items:center; justify-content:center; font-size:14px; flex:none; }}
  h3 {{ font-size:16px; font-weight:700; margin:22px 0 10px; color:#1e293b; }}
  .lead {{ color:var(--sub); font-size:14.5px; margin-bottom:16px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13.5px; margin:12px 0; }}
  th {{ background:#f1f5f9; text-align:left; padding:9px 12px; font-weight:600; color:#334155; }}
  td {{ padding:9px 12px; border-bottom:1px solid var(--line); vertical-align:top; }}
  tr:hover td {{ background:#f8fafc; }}
  .pill {{ display:inline-block; padding:1px 9px; border-radius:999px; font-size:11.5px; font-weight:600; }}
  .pill.blue {{ background:#dbeafe; color:#1d4ed8; }}
  .pill.green {{ background:#d1fae5; color:#047857; }}
  .pill.amber {{ background:#fef3c7; color:#b45309; }}
  .pill.red {{ background:#fee2e2; color:#b91c1c; }}
  code {{ font-family:"JetBrains Mono",ui-monospace,monospace; background:#f1f5f9; border:1px solid var(--line); border-radius:5px; padding:1px 6px; font-size:12.5px; }}
  pre {{ background:#0f172a; color:#e2e8f0; border-radius:12px; padding:16px 18px; overflow-x:auto; font-size:12.5px; line-height:1.6; margin:12px 0; }}
  pre code {{ background:none; border:none; color:inherit; padding:0; }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:22px; }}
  .grid2x {{ display:grid; grid-template-columns:1fr 1fr; gap:22px; }}
  @media (max-width:760px) {{ .grid2, .grid2x {{ grid-template-columns:1fr; }} section {{ padding:22px 18px; }} }}
  .note {{ background:#f8fafc; border-left:3px solid var(--brand); border-radius:0 10px 10px 0; padding:12px 16px; font-size:13.5px; color:var(--sub); margin:14px 0; }}
  .warn {{ background:#fffbeb; border-left:3px solid var(--warn); border-radius:0 10px 10px 0; padding:12px 16px; font-size:13.5px; color:#92400e; margin:14px 0; }}
  .foot {{ color:var(--mut); font-size:12px; margin-top:30px; text-align:center; }}
  .two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
  @media (max-width:760px) {{ .two-col {{ grid-template-columns:1fr; }} }}
  .kpi-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }}
  @media (max-width:760px) {{ .kpi-grid {{ grid-template-columns:repeat(2,1fr); }} }}
  .kpi {{ border:1px solid var(--line); border-radius:12px; padding:14px; text-align:center; }}
  .kpi .v {{ font-size:20px; font-weight:800; color:var(--brand); font-family:"JetBrains Mono",monospace; }}
  .kpi .k {{ font-size:12px; color:var(--sub); margin-top:3px; }}
</style>
</head>
<body>
<div class="hero">
  <span class="tag">数据源分析报告 · DATA SOURCE ANALYSIS</span>
  <h1>MatrAIx Persona 1M 数据集</h1>
  <div class="sub">近 100 万个虚拟人格，每人由 1,290 个结构化属性描述——60% 来自真实记录（维基百科、开发者问卷、商品评论、社会调查等），40% 由合成生成。本报告结合官方数据卡与实际数据文件，讲清「里面到底有什么、长什么样、怎么用、边界在哪」。</div>
  <div class="meta">本地数据路径：persona/datasets/matraix-persona-1m/release · HuggingFace：MatrAIx2026/MatrAIx_Persona_1M_Public_Release · 报告日期：2026-09-16</div>
</div>

<div class="stats">
  <div class="stat"><div class="n">999,847</div><div class="l">人格数量（≈1M）</div></div>
  <div class="stat"><div class="n">1,290</div><div class="l">结构化属性维度</div></div>
  <div class="stat"><div class="n">60 : 40</div><div class="l">真实衍生 : 合成</div></div>
  <div class="stat"><div class="n">4.17 GB</div><div class="l">数据体积（10 个分片）</div></div>
</div>

<div class="wrap">

<section>
  <h2><span class="no">1</span>这个数据集是什么</h2>
  <p class="lead">MatrAIx 是一个「先模拟、后现实」的群体级人格基础设施：把采样出的人格记录实例化为 LLM 智能体，在四类环境（Survey 问卷 / AI Chatbot 对话 / Web 网页 / App 桌面与移动应用）里跑可复现任务。Persona 1M 就是这套系统的基础数据资产。</p>
  <div class="kpi-grid">
    <div class="kpi"><div class="v">4 类</div><div class="k">任务环境（Survey/Chatbot/Web/App）</div></div>
    <div class="kpi"><div class="v">7 个</div><div class="k">数据来源（6 真实 + 1 合成）</div></div>
    <div class="kpi"><div class="v">422,590</div><div class="k">带自然语言描述的人格（42.26%）</div></div>
    <div class="kpi"><div class="v">656 / 1,290</div><div class="k">平均每个实有人格填充的属性数</div></div>
  </div>
  <div class="note"><b>设计定位</b>：每个「人」被拆成 1,290 个<b>分类维度</b>（年龄、地区、职业、技能、价值观、大五人格、兴趣……），每个维度取一个离散值。人格 = 这些维度值的组合。它服务于用户研究、产品评估、市场模拟等场景——<b>不能替代真实人群证据</b>。</div>
</section>

<section>
  <h2><span class="no">2</span>来源构成：6 个真实来源 + 1 路合成</h2>
  <p class="lead">599,847 条人格直接由真实记录衍生（人类数据接地 grounding），400,000 条由「依赖感知的合成生成」（Full-DAG，图结构生成，保证维度间逻辑一致）。</p>
  <div class="grid2">
    <div>
      <h3>各来源人格数量</h3>
      {hbar_num([(n, v) for n, _, v, _, _ in SOURCES], 400000, "#2563eb")}
    </div>
    <div>
      <h3>来源占比</h3>
      {legend([(n, v) for n, _, v, _, _ in SOURCES], lambda i: PALETTE[i])}
      <div style="text-align:center;margin-top:8px">{donut([(n, v) for n, _, v, _, _ in SOURCES], lambda i: PALETTE[i])}</div>
    </div>
  </div>
  <table>
    <tr><th>来源</th><th>说明</th><th>行数</th><th>占比</th><th>中位填充属性</th></tr>
    {''.join(f'<tr><td><code>{n}</code></td><td>{ESC(note)}</td><td>{v:,}</td><td>{v/999847*100:.1f}%</td><td>{med}</td></tr>' for n, note, v, med, _ in SOURCES)}
  </table>
  <div class="note"><b>填充度差异巨大是有意设计</b>：合成人格与真人问卷「齐全」（990/990），一条 Amazon 评论只能支撑约 16 个属性。缺失 = 来源不支持，<b>不做插补</b>。</div>
</section>

<section>
  <h2><span class="no">3</span>维度体系：1,290 个属性怎么组织的</h2>
  <p class="lead">1,290 个维度按 43 个子类组织，归并为 9 大族。覆盖「背景 → 心理 → 能力 → 行为」整个人类画像。</p>
  <table>
    <tr><th>大族</th><th>维度数</th><th>占比</th><th>包含（子类）</th></tr>
    {''.join(f'<tr><td><b>{ESC(n)}</b></td><td>{v:,}</td><td>{v/1290*100:.1f}%</td><td style="color:#475569">{ESC(d)}</td></tr>' for n, v, d in CATS)}
  </table>
  <h3>9 大族构成（维度数）</h3>
  {hbar_num([(n, v) for n, v, _ in CATS], 358, "#0ea5e9")}
  <div class="note"><b>开发者专项值得注意</b>：66 个维度专为 AI 时代设计（智能体采用、AI 工作流、开源行为等），这也是本仓库做「AI 产品用户模拟」的底气来源。</div>
</section>

<section>
  <h2><span class="no">4</span>数据结构：怎么存储与读取</h2>
  <p class="lead">数据以 <b>Zstandard 压缩的 Parquet</b> 分片存储，10 个分片（9×100,000 + 1×99,847 行）。属性经过<b>比特级打包</b>：每人的 1,290 个属性压缩成 645 字节（每个维度 4-bit 编码，最多 16 个取值）。</p>
  <div class="two-col">
    <div>
      <h3>Parquet 12 列</h3>
      <table>
        {''.join(f'<tr><td><code>{ESC(c)}</code></td><td style="font-size:12.5px;color:#475569">{ESC(d)}</td></tr>' for c, d in PARQUET_COLS)}
      </table>
    </div>
    <div>
      <h3>配套索引（快速筛选）</h3>
      <p style="font-size:13.5px;color:#475569">不用扫 4GB 也能按属性找人：<code>indexes/postings.sqlite</code>（2.6 GB）把每个「维度=取值」映射到全局行号。</p>
      <table>
        <tr><td>postings 条目数</td><td><b>10,617</b> 个 (维度, 取值) → 行号倒排</td></tr>
        <tr><td>字段数</td><td>1,291（1,290 维度 + 1）</td></tr>
        <tr><td>样例查询</td><td><code>age_bracket='25-34'</code> → 直接拿到所有行 ID</td></tr>
        <tr><td>schema</td><td><code>postings(field_id, value, row_ids BLOB, count)</code></td></tr>
      </table>
      <h3>官方解码示例（pyarrow）</h3>
      <pre><code>import json, pyarrow.parquet as pq
schema = json.load(open("persona_codes.schema.json"))["columns"]
t = pq.read_table("data/persona-1m-0000.parquet")

def decode(attributes, null_bitmap):
    out = {{}}
    for i, col in enumerate(schema):
        if null_bitmap and (null_bitmap[i//8] >> (i%8)) & 1:
            continue                        # 置位 = 缺失
        code = (attributes[i//2] & 0x0F) if i%2==0 else (attributes[i//2] >> 4)
        if code < len(col["values"]):
            out[col["id"]] = col["values"][code]
    return out</code></pre>
    </div>
  </div>
</section>

<section>
  <h2><span class="no">5</span>数据画像：真实分布长什么样</h2>
  <p class="lead">四个关键维度按 2024 年全球人口结构做过校准（age/region 目标来自 UN WPP 2024，gender/urbanicity 来自 UN + World Bank）。以下是<b>全量数据实际达成</b>的分布。</p>
  <h3>年龄分布（已知 704,641 行）</h3>
  {hbar(AGE, 14.5, "#2563eb")}
  <h3>地区分布（已知 874,653 行）</h3>
  {hbar(REGION, 18.8, "#0ea5e9")}
  <div class="grid2">
    <div>
      <h3>性别（已知 774,736 行）</h3>
      {hbar(GENDER, 50, "#10b981")}
      <h3>城乡（已知 582,321 行）</h3>
      {hbar(URBAN, 34.5, "#f59e0b")}
    </div>
    <div>
      <h3>收入层级（999 人解码样本）</h3>
      {hbar(SAMPLE_SOCIO, 25, "#8b5cf6")}
      <h3>消费心态（999 人解码样本）</h3>
      {hbar(SAMPLE_MOTIV, 45.5, "#ec4899")}
      <p style="font-size:12.5px;color:#94a3b8;margin-top:6px">* 收入/消费心态未参与官方校准，此处用官方 sample.parquet（999 人解码样本）估算，仅作画像参考。</p>
    </div>
  </div>
</section>

<section>
  <h2><span class="no">6</span>质量与校准：误差多大、覆盖多广</h2>
  <p class="lead">构建是确定性的（seed=20260720），官方 RESULTS.md 报告了每个校准维度「目标 vs 达成」的最大绝对误差。</p>
  <table>
    <tr><th>维度</th><th>已知行数</th><th>缺失行数</th><th>最大绝对误差</th><th>校准目标来源</th><th>评价</th></tr>
    <tr><td><code>age_bracket</code></td><td>704,641</td><td>295,359</td><td>0.0749%</td><td>UN WPP 2024</td><td><span class="pill green">优秀</span></td></tr>
    <tr><td><code>gender_identity</code></td><td>774,736</td><td>225,264</td><td>0.0375%</td><td>UN + World Bank</td><td><span class="pill green">优秀</span></td></tr>
    <tr><td><code>urbanicity</code></td><td>582,321</td><td>417,679</td><td>0.0478%</td><td>UN + World Bank</td><td><span class="pill green">优秀</span></td></tr>
    <tr><td><code>region</code></td><td>874,653</td><td>125,347</td><td><b>14.0047%</b></td><td>UN WPP 2024</td><td><span class="pill red">偏差大</span></td></tr>
  </table>
  <div class="warn"><b>地区维度的坑</b>：North America 目标 4.8%，实得 18.8%（差 14 个百分点）——因为维基百科词条天然偏向欧美人物。做地区相关分析时<b>务必按已知人口结构加权</b>，或使用 cohort 抽样按目标分布重采样。</div>
  <h3>描述覆盖与审计</h3>
  <p style="font-size:14px;color:#475569">422,590 行（42.26%）带有字段级自然语言描述（由模型生成；合成人格不带描述）。官方随包提供 <code>audit.json</code>（残差诊断、逐类目标/达成、来源统计）、<code>calibration_targets.json</code>（校准契约）、<code>RESULTS.md</code>（构建结果摘要），复现口径完整。</p>
</section>

<section>
  <h2><span class="no">7</span>一条真实人格长什么样</h2>
  <p class="lead">从 parquet 分片第 2 行解码（来源：维基百科，169 个属性），展示核心字段：</p>
  <div class="grid2">
    <div>
      <table>
        <tr><th>维度</th><th>取值</th></tr>
        <tr><td>age_bracket</td><td>45-54</td></tr>
        <tr><td>region</td><td>Eastern Europe</td></tr>
        <tr><td>gender_identity</td><td>Man</td></tr>
        <tr><td>urbanicity</td><td>Nomadic / remote</td></tr>
        <tr><td>socioeconomic_band</td><td>High income</td></tr>
        <tr><td>life_stage</td><td>Mid-life</td></tr>
        <tr><td>economic_motivation</td><td>Premium-seeking</td></tr>
        <tr><td>其他</td><td style="color:#94a3b8">共 169 个属性（技能、兴趣、人格等略）</td></tr>
      </table>
    </div>
    <div>
      <h3>逐字段证据（grounding）</h3>
      <pre><code>{{"field_index": 0,
 "evidence": "c. 406 – 453",
 "confidence": 0.7,
 "assignment_type": "structured_claim"}}</code></pre>
      <p style="font-size:13px;color:#475569">每个属性都带「证据原文 + 置信度 + 赋值类型」，可回溯到来源文本——这是「人类数据接地」的可审计性设计。</p>
      <h3>运行时格式（YAML）</h3>
      <pre><code>persona_id: 0004
version: 1.0
source: wiki
display_name: Sienna Carter
dimensions:
  region: North America
  gender_identity: Man
  domain: Public Sector
  highest_education: No formal
  ...
provenance:
  parent_pool: persona/datasets/matraix-persona-1m
  origin_persona_id: wiki-e14eaddc0b8d
  origin_source_row_index: 281061</code></pre>
    </div>
  </div>
</section>

<section>
  <h2><span class="no">8</span>配套文件：一个数据集 = 一套完整工具链</h2>
  <table>
    <tr><th>路径</th><th>内容</th><th>大小</th></tr>
    <tr><td><code>release/data/persona-1m-0000..0009.parquet</code></td><td>人格主体（10 分片，Zstd Parquet）</td><td>3.9 GB</td></tr>
    <tr><td><code>release/indexes/postings.sqlite</code></td><td>「维度=取值 → 全局行号」倒排索引</td><td>2.6 GB</td></tr>
    <tr><td><code>release/persona_codes.schema.json</code></td><td>码本：1,290 字段、取值与打包规格</td><td>—</td></tr>
    <tr><td><code>release/manifest.json</code></td><td>分片行数 / 字节 / SHA-256 / 来源统计</td><td>—</td></tr>
    <tr><td><code>release/README.md</code> · <code>RESULTS.md</code></td><td>官方数据卡 · 校准结果</td><td>—</td></tr>
    <tr><td><code>release/calibration_targets.json</code> · <code>audit.json</code></td><td>校准契约 · 审计报告</td><td>—</td></tr>
    <tr><td><code>release/sample/sample.parquet</code></td><td>999 人 × 990 属性解码版（Dataset Viewer 展示用，非发布主体）</td><td>—</td></tr>
    <tr><td><code>persona/datasets/matraix-persona-dev-sample/</code></td><td>~200 条 YAML 人格（冒烟测试用）</td><td>3.2 MB</td></tr>
    <tr><td><code>persona/datasets/validation-subset/</code></td><td>验证子集（YAML）</td><td>1.5 MB</td></tr>
    <tr><td><code>persona/schema/dimensions.json</code> 等</td><td>官方 taxonomy（维度/类别/映射）</td><td>—</td></tr>
  </table>
</section>

<section>
  <h2><span class="no">9</span>怎么用：三种打开方式</h2>
  <div class="grid2">
    <div>
      <h3>① 解码读取（官方推荐）</h3>
      <pre><code>person = decode(t["attributes"][1].as_py(),
                t["null_bitmap"][1].as_py())
person.get("age_bracket")
# -> "45-54"   （用 .get 不用 []，行是稀疏的）</code></pre>
      <h3>② 索引快速筛选</h3>
      <pre><code># 找所有「25-34 岁」的人，不用扫 4GB
SELECT value, count FROM postings
WHERE field_id = 'age_bracket';</code></pre>
    </div>
    <div>
      <h3>③ 采样运行（本 demo 用法）</h3>
      <pre><code>python scripts/generate_water_bottle_job.py \\
  1000 20 survey-water-bottle-choice-v2-n1000
# 从数据集采样 1000 人格 →
# 实例化为 LLM 智能体（DeepSeek）→ 跑问卷任务</code></pre>
      <p style="font-size:13px;color:#475569">抽样会输出 YAML 人格文件（含 dimensions + provenance），并按校准目标做分层采样；本仓库 <code>cohorts/</code> 目录即抽样结果。</p>
    </div>
  </div>
  <div class="note"><b>本 demo 的经验</b>：用 999,847 人数据集采样出 1,000 人格做「保温杯选购」问卷，成本 ¥4.5 / 34 分钟（20 并发），报告里所有分群（地区/性别/人生阶段/收入）都来自这些人格属性。</div>
</section>

<section>
  <h2><span class="no">10</span>边界与合规：必须知道的限制</h2>
  <div class="warn"><b>许可红线（研究专用）</b>：数据集仅限<b>非商业研究用途</b>，任何商用、付费托管服务均不允许；子集（包括 40 万合成人格）不因提取而获得新的许可。上游来源许可各自适用（维基 CC BY-SA 4.0、SO 问卷 ODbL、Amazon 研究用途、PRISM CC BY / CC BY-NC 等）。</div>
  <table>
    <tr><th>官方明示的限制</th><th>含义</th></tr>
    <tr><td>不是任何人群的代表性样本</td><td>校准只对齐一维边际，不保证联合分布；来源选择偏差仍在</td></tr>
    <tr><td>「人类接地」≠「已核验」</td><td>维基/Amazon/SO/PRISM 属性是模型抽取的，可能有抽取错误；描述是模型生成的</td></tr>
    <tr><td>60/40 人机比例是设计选择</td><td>不代表真实世界的人机比例</td></tr>
    <tr><td>未成年记录已移除</td><td>原 508 条真人问卷中 153 条 <18 岁被剔除，故总数是 999,847 而非 1,000,000</td></tr>
  </table>
  <p style="font-size:13.5px;color:#475569">责任使用（论文 Appendix N）：不得冒充真实个人、不得把数据归因到可识别的人、不得尝试再识别、不得针对个人或受保护群体。官方数据卡版本化 + 文件哈希，删除记录会留档。论文：<a href="https://arxiv.org/abs/2608.04205" style="color:#2563eb">arXiv:2608.04205</a></p>
</section>

<section>
  <h2><span class="no">11</span>快速参考（30 秒速览）</h2>
  <div class="grid2">
    <div>
      <h3>一句话</h3>
      <p style="font-size:14px;color:#475569">999,847 个结构化虚拟人格 × 1,290 维度，6 个真实来源（60%）+ 合成（40%），研究用途，配套解码器与索引。</p>
      <h3>关键数字</h3>
      <table>
        <tr><td>总数</td><td>999,847（9×100k + 1×99,847）</td></tr>
        <tr><td>维度</td><td>1,290 分类维度 / 43 子类 / 9 大族</td></tr>
        <tr><td>体积</td><td>4.17 GB（data）+ 2.6 GB（索引）</td></tr>
        <tr><td>编码</td><td>4-bit 打包，每行 645 字节</td></tr>
        <tr><td>平均填充</td><td>656 / 1,290</td></tr>
        <tr><td>带描述</td><td>422,590 行（42.26%）</td></tr>
        <tr><td>校准 seed</td><td>20260720（确定性构建）</td></tr>
      </table>
    </div>
    <div>
      <h3>四维校准误差</h3>
      <table>
        <tr><th>维度</th><th>最大误差</th></tr>
        <tr><td>age_bracket</td><td>0.07% <span class="pill green">优秀</span></td></tr>
        <tr><td>gender_identity</td><td>0.04% <span class="pill green">优秀</span></td></tr>
        <tr><td>urbanicity</td><td>0.05% <span class="pill green">优秀</span></td></tr>
        <tr><td>region</td><td>14.00% <span class="pill red">需加权</span></td></tr>
      </table>
      <h3>官方文档入口</h3>
      <p style="font-size:13.5px;color:#475569">
        · 数据卡：<code>release/README.md</code><br>
        · 构建结果：<code>release/RESULTS.md</code><br>
        · 手册：<code>docs/persona/README.md</code><br>
        · 流水线：<code>docs/persona/pipeline.md</code><br>
        · HuggingFace：<a href="https://huggingface.co/datasets/MatrAIx2026/MatrAIx_Persona_1M_Public_Release" style="color:#2563eb">MatrAIx_Persona_1M_Public_Release</a>
      </p>
    </div>
  </div>
</section>

<div class="foot">本报告所有数字均来自官方数据卡（release/README.md、RESULTS.md、manifest.json、audit.json）与本地实际数据文件（parquet 解码、SQLite 查询、sample.parquet）· 生成：scripts/generate_dataset_report.py · MatrAIx Persona 1M 数据集 · 仅供非商业研究使用</div>
</div>
</body>
</html>
"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(PAGE)
print("wrote", OUT, len(PAGE), "bytes")
