# -*- coding: utf-8 -*-
"""生成飞书文档版数据源分析报告：html5-block 图表组件 + 文档 XML。"""
import os, html

DIR = "draft_dea6be97_folder"
os.makedirs(DIR, exist_ok=True)
E = html.escape

# 藏青主色体系（strategy-and-analysis）
PRIMARY = "#1A2B4A"; SUB = "#758092"; LINE = "#DDE0E4"; BG = "#FFFFFF"; ACC = "#3E5C9A"

def widget(name, desc, body):
    """生成标准 html5-block 单文件"""
    content = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="use-iframe" content="true">
<meta name="html-box-height-mode" content="auto">
<meta name="description" content="{E(desc)}">
<title></title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif; background:{BG}; color:{PRIMARY}; width:100%; }}
  .card {{ border:1px solid {LINE}; border-radius:12px; padding:16px 18px; margin-bottom:12px; }}
  .h {{ font-size:14px; font-weight:700; margin-bottom:10px; color:{PRIMARY}; }}
  .kpis {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:8px; }}
  @media (max-width:600px) {{ .kpis {{ grid-template-columns:repeat(2,1fr); }} }}
  .kpi {{ background:#F4F6FA; border-radius:10px; padding:12px 8px; text-align:center; }}
  .kpi .v {{ font-size:20px; font-weight:800; color:{PRIMARY}; font-family:ui-monospace,monospace; }}
  .kpi .k {{ font-size:11px; color:{SUB}; margin-top:2px; }}
  table {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
  th {{ background:#EEF1F6; text-align:left; padding:7px 9px; color:{PRIMARY}; }}
  td {{ padding:7px 9px; border-bottom:1px solid {LINE}; vertical-align:top; color:#334155; }}
  .bar-row {{ display:flex; align-items:center; gap:10px; margin:7px 0; font-size:12.5px; }}
  .bar-label {{ width:150px; flex:none; text-align:right; color:{SUB}; }}
  .bar-track {{ flex:1; background:#EEF1F6; border-radius:4px; height:16px; overflow:hidden; }}
  .bar-fill {{ height:100%; background:{PRIMARY}; border-radius:4px; }}
  .bar-val {{ width:70px; flex:none; font-weight:700; color:{PRIMARY}; }}
  .note {{ font-size:11.5px; color:{SUB}; margin-top:6px; }}
  ul {{ padding-left:18px; font-size:13px; color:#334155; }}
  li {{ margin:5px 0; }}
</style>
</head>
<body>
{body}
</body>
</html>"""
    p = os.path.join(DIR, name)
    open(p, "w", encoding="utf-8").write(content)
    print("widget:", name, len(content), "B")

def bar_rows(data, maxv, fmt="{:.1f}%"):
    rows = []
    for label, v in data:
        pct = v / maxv * 100
        rows.append(f'<div class="bar-row"><div class="bar-label">{E(label)}</div><div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%"></div></div><div class="bar-val">{fmt.format(v)}</div></div>')
    return "".join(rows)

# ---------- 1 一图看懂 ----------
widget("w_overview.html", "数据集一图看懂：规模、构成、质量与用法",
f"""<div class="card">
  <div class="h">MatrAIx Persona 1M：近 100 万虚拟人格 × 1,290 维度</div>
  <div class="kpis">
    <div class="kpi"><div class="v">999,847</div><div class="k">人格数量</div></div>
    <div class="kpi"><div class="v">1,290</div><div class="k">属性维度</div></div>
    <div class="kpi"><div class="v">60 : 40</div><div class="k">真实 : 合成</div></div>
    <div class="kpi"><div class="v">42.26%</div><div class="k">带描述占比</div></div>
  </div>
  <div class="kpis">
    <div class="kpi"><div class="v">656/1290</div><div class="k">平均填充属性</div></div>
    <div class="kpi"><div class="v">0.07%</div><div class="k">校准最优误差(age)</div></div>
    <div class="kpi"><div class="v">14.0%</div><div class="k">校准最大误差(region)</div></div>
    <div class="kpi"><div class="v">4.17 GB</div><div class="k">数据体积</div></div>
  </div>
  <div class="note">来源：release/manifest.json、RESULTS.md、README.md（官方数据卡）</div>
</div>""")

# ---------- 2 来源构成 ----------
widget("w_sources.html", "来源构成：6 真实来源 + 1 合成，599,847 真实衍生 + 400,000 合成",
f"""<div class="card">
  <div class="h">各来源人格数量（合计 999,847）</div>
  {bar_rows([("synthetic 合成", 400000), ("wiki 维基百科", 323438), ("stackoverflow 开发者问卷", 113120), ("amazon 商品评论", 97915), ("gss 社会调查", 63532), ("prism 对齐数据", 1487), ("real_human_survey 真人问卷", 355)], 400000, fmt="{:,}")}
  <div class="note">填充度差异是有意设计：合成人格 990/990 齐全；一条 Amazon 评论仅支撑约 16 个属性。缺失 = 来源不支持，不做插补。</div>
</div>""")

# ---------- 3 维度体系 ----------
widget("w_dims.html", "维度体系：1,290 维度归并为 9 大族",
f"""<div class="card">
  <div class="h">9 大族维度数（合计 1,290，43 个子类）</div>
  {bar_rows([("兴趣与媒介", 358), ("专业与技能", 356), ("人格与心理", 215), ("语言与沟通", 90), ("行为与习惯", 69), ("开发者专项", 66), ("职业与行业", 55), ("人口与背景", 52), ("健康", 29)], 358, fmt="{:,}")}
  <div class="note">覆盖「背景 → 心理 → 能力 → 行为」整个人类画像；含 66 个 AI 时代开发者专项维度（智能体采用、AI 工作流等）。</div>
</div>""")

# ---------- 4 数据结构 ----------
widget("w_storage.html", "数据结构：4-bit 打包 + 倒排索引",
f"""<div class="card">
  <div class="h">存储与读取方式</div>
  <table>
    <tr><th>层</th><th>说明</th></tr>
    <tr><td>Parquet 分片</td><td>10 个 Zstd 分片（9×100,000 + 1×99,847），共 4.17 GB</td></tr>
    <tr><td>属性编码</td><td>每人 1,290 维 → 645 字节 4-bit 打包（每维 ≤16 取值）</td></tr>
    <tr><td>缺失位图</td><td>null_bitmap 置位 = 该维缺失；行稀疏，缺失不插补</td></tr>
    <tr><td>证据链</td><td>grounding 逐字段记录证据原文、置信度、赋值类型</td></tr>
    <tr><td>倒排索引</td><td>postings.sqlite（2.6 GB）：10,617 个「维度=取值」→ 全局行号，免扫全量筛选</td></tr>
  </table>
  <div class="note">官方提供 pyarrow 解码示例（persona_codes.schema.json 为 1,290 字段码本）。</div>
</div>""")

# ---------- 5 数据画像 ----------
widget("w_profile.html", "数据画像：关键维度分布（按 2024 全球人口校准）",
f"""<div class="card">
  <div class="h">地区分布（已知 874,653 行）</div>
  {bar_rows([("North America", 18.8), ("South Asia", 18.4), ("East Asia", 14.1), ("Sub-Saharan Africa", 12.2), ("Western Europe", 11.7), ("Latin America", 6.8), ("Southeast Asia", 6.4), ("MENA", 5.4), ("Eastern Europe", 4.9), ("Oceania", 1.4)], 18.8)}
  <div class="h" style="margin-top:14px">年龄分布（已知 704,641 行）</div>
  {bar_rows([("25-34", 14.5), ("5-12", 13.0), ("35-44", 13.3), ("45-54", 11.5), ("18-24", 10.6), ("55-64", 10.5), ("Under 5", 8.4), ("13-17", 8.2), ("65-74", 6.1), ("75-84", 2.8), ("85+", 1.1)], 14.5)}
  <div class="note">性别（已知 774,736 行）：Man 49.8% / Woman 49.5% / 其他 0.7%；城乡（已知 582,321 行）：Rural 34.5% / Dense urban 24.5% / Suburban 21.0% / Small town 18.5% / Nomadic 1.5%。</div>
</div>""")

# ---------- 6 质量校准 ----------
widget("w_calib.html", "质量与校准：四维误差对比",
f"""<div class="card">
  <div class="h">四维校准最大绝对误差（目标 = 2024 全球人口边际）</div>
  {bar_rows([("age_bracket 年龄", 0.0749), ("gender_identity 性别", 0.0375), ("urbanicity 城乡", 0.0478), ("region 地区", 14.0047)], 14.0047, fmt="{:.2f}%")}
  <div class="note">age / gender / urbanicity 误差 &lt;0.08%，接近完美；region 偏差 14.0%（北美 18.8% vs 目标 4.8%），源于维基词条偏欧美——做地区分析务必加权或按 cohort 重采样。误差以已知行计，不覆盖缺失行。</div>
</div>""")

# ---------- 7 真实人格 ----------
widget("w_persona.html", "一条真实人格示例（wiki 来源，169 属性）",
f"""<div class="card">
  <div class="h">parquet 解码示例（第 2 行，来源 wiki）</div>
  <table>
    <tr><th>维度</th><th>取值</th></tr>
    <tr><td>age_bracket</td><td>45-54</td></tr>
    <tr><td>region</td><td>Eastern Europe</td></tr>
    <tr><td>gender_identity</td><td>Man</td></tr>
    <tr><td>urbanicity</td><td>Nomadic / remote</td></tr>
    <tr><td>socioeconomic_band</td><td>High income</td></tr>
    <tr><td>economic_motivation</td><td>Premium-seeking</td></tr>
    <tr><td>life_stage</td><td>Mid-life</td></tr>
  </table>
  <div class="note">grounding 证据：{{"field_index": 0, "evidence": "c. 406 – 453", "confidence": 0.7, "assignment_type": "structured_claim"}}——每个属性可回溯到来源文本。</div>
</div>""")

# ---------- 8 配套文件 ----------
widget("w_files.html", "配套文件：一个数据集 = 完整工具链",
f"""<div class="card">
  <div class="h">发布包与本地配套</div>
  <table>
    <tr><th>文件</th><th>内容</th><th>大小</th></tr>
    <tr><td>data/persona-1m-0000..0009.parquet</td><td>人格主体（10 分片）</td><td>3.9 GB</td></tr>
    <tr><td>indexes/postings.sqlite</td><td>倒排索引</td><td>2.6 GB</td></tr>
    <tr><td>persona_codes.schema.json</td><td>1,290 字段码本</td><td>—</td></tr>
    <tr><td>manifest.json / RESULTS.md / audit.json / calibration_targets.json</td><td>分片哈希、构建结果、审计、校准契约</td><td>—</td></tr>
    <tr><td>sample/sample.parquet</td><td>999 人 × 990 维解码版（展示用）</td><td>—</td></tr>
    <tr><td>matraix-persona-dev-sample / validation-subset</td><td>YAML 冒烟/验证子集</td><td>3.2 / 1.5 MB</td></tr>
  </table>
  <div class="note">本地路径：persona/datasets/matraix-persona-1m/release/；HuggingFace：MatrAIx2026/MatrAIx_Persona_1M_Public_Release。</div>
</div>""")

# ---------- 9 用法 ----------
widget("w_usage.html", "三种打开方式",
f"""<div class="card">
  <div class="h">① 解码读取（官方推荐 pyarrow）→ ② 索引筛选 → ③ 采样实例化 LLM</div>
  <table>
    <tr><th>方式</th><th>做法</th><th>适用</th></tr>
    <tr><td>解码读取</td><td>pyarrow + persona_codes.schema.json 解码 attributes/null_bitmap</td><td>全量分析、抽样构建</td></tr>
    <tr><td>索引筛选</td><td>SQLite postings 按「维度=取值」取全局行号</td><td>免扫 4GB 的条件筛选</td></tr>
    <tr><td>采样运行</td><td>按校准目标分层采样 → YAML 人格 → 实例化为 LLM 智能体跑任务</td><td>用户研究 / 产品评估（本 demo 用法）</td></tr>
  </table>
  <div class="note">本仓库保温杯 demo：采样 1,000 人格跑问卷，成本约 ¥4.5、34 分钟（20 并发），分群画像全部来自人格属性。</div>
</div>""")

# ---------- 10 边界合规 ----------
widget("w_limits.html", "边界与合规：官方明示限制",
f"""<div class="card">
  <div class="h">必须知道的 4 条限制与 1 条许可红线</div>
  <table>
    <tr><th>限制</th><th>含义</th></tr>
    <tr><td>非代表性样本</td><td>校准只对齐一维边际，不保证联合分布；来源选择偏差仍在</td></tr>
    <tr><td>「人类接地」≠「已核验」</td><td>抽取属性可能有误；描述为模型生成</td></tr>
    <tr><td>60/40 人机比例是设计选择</td><td>不代表真实比例</td></tr>
    <tr><td>未成年记录已移除</td><td>153 条 &lt;18 岁剔除，总数 999,847</td></tr>
  </table>
  <div class="note" style="margin-top:8px;color:#92400e;background:#FDF6EC;padding:10px 12px;border-radius:8px;border:1px solid #F0DCC0"><b>许可红线</b>：仅限非商业研究用途；子集不因提取获得新许可；上游来源许可各自适用；不得冒充真实个人、再识别或针对个人/受保护群体（论文 Appendix N）。</div>
</div>""")

# ---------- 11 快速参考 ----------
widget("w_ref.html", "快速参考：30 秒速览",
f"""<div class="card">
  <div class="h">关键数字速查</div>
  <table>
    <tr><td>总数</td><td>999,847（9×100k + 1×99,847）</td></tr>
    <tr><td>维度</td><td>1,290 分类维度 / 43 子类 / 9 大族</td></tr>
    <tr><td>编码</td><td>4-bit 打包，每行 645 字节</td></tr>
    <tr><td>平均填充</td><td>656 / 1,290（缺失不插补）</td></tr>
    <tr><td>带描述</td><td>422,590 行（42.26%）</td></tr>
    <tr><td>确定性</td><td>seed=20260720，可复现构建</td></tr>
  </table>
</div>""")

# ---------- 文档 XML ----------
xml = f"""<title>MatrAIx Persona 1M 数据集 · 数据源分析报告</title>

<callout background-color="light-blue" border-color="blue"><p><b>一句话结论</b>：这是「近 100 万虚拟人格 × 1,290 个属性维度」的群体画像数据集——60% 由 6 类真实记录衍生（维基百科、开发者问卷、商品评论、社会调查、对齐数据、真人问卷），40% 为合成生成，仅供<b>非商业研究</b>使用。</p><ul><li><b>规模与结构</b>：999,847 条人格、1,290 维、4.17 GB（10 个 Parquet 分片）；每条人格平均填充 656 个属性，缺失不做插补。</li><li><b>质量</b>：年龄/性别/城乡按 2024 全球人口校准，误差 &lt;0.08%；<b>地区维度偏差 14 个百分点</b>（欧美占比偏高），地区分析必须加权或重采样。</li><li><b>用法</b>：pyarrow 解码读取 + SQLite 倒排索引筛选 + 按校准目标分层采样实例化为 LLM 智能体；本 demo 已用它采样 1,000 人完成保温杯选购问卷。</li></ul></callout>

<h1>一图看懂</h1>
<html5-block path="@./{DIR}/w_overview.html"></html5-block>

<h1 seq="auto">数据集是什么</h1>
<p>MatrAIx 是「先模拟、后现实」的群体级人格基础设施：把采样的人格记录实例化为 LLM 智能体，在 Survey 问卷、AI Chatbot 对话、Web 网页、App 桌面与移动四类环境中跑可复现任务。Persona 1M 是这套系统的基础数据资产，也是本仓库所有模拟实验（如保温杯选购 demo）的人格来源。</p>
<p>每个「人」被拆成 1,290 个分类维度（年龄、地区、职业、技能、价值观、大五人格、兴趣等），每维取一个离散值，人格 = 这些维度值的组合。官方论文（arXiv:2608.04205）将其定位为"用 83 亿人格智能体模拟世界"愿景的第一阶段资产，<b>不能替代真实人群证据</b>。</p>
<html5-block path="@./{DIR}/w_overview.html"></html5-block>

<h1 seq="auto">来源构成：6 个真实来源 + 1 路合成</h1>
<p>599,847 条人格（60%）由真实记录衍生，属性带逐字段证据链（grounding）；400,000 条（40%）由「依赖感知的合成生成」（Full-DAG）产生，保证维度间逻辑一致。</p>
<table>
<colgroup><col width="28%"/><col width="42%"/><col width="12%"/><col width="18%"/></colgroup>
<thead><tr><th><p>来源</p></th><th><p>说明</p></th><th><p>行数</p></th><th><p>中位填充属性</p></th></tr></thead>
<tbody>
<tr><td><p>synthetic</p></td><td><p>Full-DAG 合成人格</p></td><td><p>400,000</p></td><td><p>990 / 990</p></td></tr>
<tr><td><p>wiki</p></td><td><p>维基百科人物词条</p></td><td><p>323,438</p></td><td><p>388</p></td></tr>
<tr><td><p>stackoverflow</p></td><td><p>年度开发者问卷</p></td><td><p>113,120</p></td><td><p>68</p></td></tr>
<tr><td><p>amazon</p></td><td><p>Amazon 商品评论（McAuley Lab）</p></td><td><p>97,915</p></td><td><p>16</p></td></tr>
<tr><td><p>gss</p></td><td><p>NORC 综合社会调查</p></td><td><p>63,532</p></td><td><p>12</p></td></tr>
<tr><td><p>prism</p></td><td><p>PRISM 对齐数据</p></td><td><p>1,487</p></td><td><p>144</p></td></tr>
<tr><td><p>real_human_survey</p></td><td><p>知情同意真人问卷（&lt;18 岁已剔除）</p></td><td><p>355</p></td><td><p>990</p></td></tr>
</tbody>
</table>
<p>填充度差异巨大是有意设计：合成人格与真人问卷「齐全」，一条 Amazon 评论只能支撑约 16 个属性。<b>缺失 = 来源不支持，不做插补</b>。</p>
<html5-block path="@./{DIR}/w_sources.html"></html5-block>

<h1 seq="auto">维度体系：1,290 个属性怎么组织</h1>
<p>1,290 个维度按 43 个子类组织、归并为 9 大族，覆盖「背景 → 心理 → 能力 → 行为」整个人类画像。值得注意：66 个「开发者专项」维度专为 AI 时代设计（智能体采用、AI 工作流、开源行为等），这也是本仓库做 AI 产品用户模拟的底气。</p>
<table>
<colgroup><col width="20%"/><col width="14%"/><col width="66%"/></colgroup>
<thead><tr><th><p>大族</p></th><th><p>维度数</p></th><th><p>包含（子类）</p></th></tr></thead>
<tbody>
<tr><td><p>人口与背景</p></td><td><p>52</p></td><td><p>年龄、地区、性别、城乡、人生阶段、家庭、文化归属</p></td></tr>
<tr><td><p>语言与沟通</p></td><td><p>90</p></td><td><p>母语、多语、英语水平、沟通风格</p></td></tr>
<tr><td><p>专业与技能</p></td><td><p>356</p></td><td><p>144 专业领域、64 技能、69 工具、44 编程、学习</p></td></tr>
<tr><td><p>人格与心理</p></td><td><p>215</p></td><td><p>大五人格、MBTI、性格特征、价值观、世界观、情绪、风险</p></td></tr>
<tr><td><p>职业与行业</p></td><td><p>55</p></td><td><p>职业角色、51 个行业</p></td></tr>
<tr><td><p>行为与习惯</p></td><td><p>69</p></td><td><p>时间、偏好、工作行为、习惯</p></td></tr>
<tr><td><p>健康</p></td><td><p>29</p></td><td><p>体能、生活方式、身体状况</p></td></tr>
<tr><td><p>兴趣与媒介</p></td><td><p>358</p></td><td><p>话题、文化、媒体、饮食、运动、爱好</p></td></tr>
<tr><td><p>开发者专项</p></td><td><p>66</p></td><td><p>AI 工作流、代码维护、开源行为、智能体采用等</p></td></tr>
</tbody>
</table>
<html5-block path="@./{DIR}/w_dims.html"></html5-block>

<h1 seq="auto">数据结构：怎么存储与读取</h1>
<p>数据以 Zstandard 压缩的 Parquet 分片存储，属性经过比特级打包：每人的 1,290 维压缩成 645 字节（4-bit 编码，每维最多 16 个取值）。配套 2.6 GB 的 SQLite 倒排索引，按「维度=取值」直接拿到全局行号，无需扫描 4 GB 主文件。</p>
<table>
<colgroup><col width="34%"/><col width="66%"/></colgroup>
<thead><tr><th><p>Parquet 列</p></th><th><p>说明</p></th></tr></thead>
<tbody>
<tr><td><p>source / source_row_index / source_record_id</p></td><td><p>来源与原始记录定位（可回溯到上游）</p></td></tr>
<tr><td><p>attributes</p></td><td><p>645 字节 4-bit 打包的 1,290 个属性编码（核心负载）</p></td></tr>
<tr><td><p>null_bitmap</p></td><td><p>缺失位图：置位 = 该维缺失（行稀疏）</p></td></tr>
<tr><td><p>attribute_overrides</p></td><td><p>超出码本范围的精确取值（覆盖编码）</p></td></tr>
<tr><td><p>has_description / description_count / descriptions</p></td><td><p>字段级自然语言描述（42.26% 的行有）</p></td></tr>
<tr><td><p>grounding</p></td><td><p>逐字段证据、置信度、赋值类型（可追溯）</p></td></tr>
<tr><td><p>metadata_json / populated_attribute_count</p></td><td><p>来源元数据 / 该行实际填充属性数（平均 656/1290）</p></td></tr>
</tbody>
</table>
<html5-block path="@./{DIR}/w_storage.html"></html5-block>

<h1 seq="auto">数据画像：真实分布长什么样</h1>
<p>四个关键维度按 2024 年全球人口结构校准（年龄/地区目标来自 UN WPP 2024；性别/城乡来自 UN + World Bank），以下是全量数据实际达成的分布。收入层级与消费心态未参与校准，此处用官方 sample.parquet（999 人解码样本）估算，仅作画像参考。</p>
<table>
<colgroup><col width="18%"/><col width="82%"/></colgroup>
<thead><tr><th><p>维度</p></th><th><p>分布（占比从高到低）</p></th></tr></thead>
<tbody>
<tr><td><p>年龄</p></td><td><p>25-34 14.5% / 5-12 13.0% / 35-44 13.3% / 45-54 11.5% / 18-24 10.6% / 55-64 10.5% / Under 5 8.4% / 13-17 8.2% / 65-74 6.1% / 75-84 2.8% / 85+ 1.1%</p></td></tr>
<tr><td><p>地区</p></td><td><p>北美 18.8% / 南亚 18.4% / 东亚 14.1% / 撒哈拉以南非洲 12.2% / 西欧 11.7% / 拉美 6.8% / 东南亚 6.4% / 中东北非 5.4% / 东欧 4.9% / 大洋洲 1.4%</p></td></tr>
<tr><td><p>性别</p></td><td><p>Man 49.8% / Woman 49.5% / 非二元 0.3% / 自述 0.2% / 不愿透露 0.2%</p></td></tr>
<tr><td><p>城乡</p></td><td><p>Rural 34.5% / Dense urban 24.5% / Suburban 21.0% / Small town 18.5% / Nomadic 1.5%</p></td></tr>
<tr><td><p>收入（样本）</p></td><td><p>Lower-middle 24.9% / Middle 23.8% / Low income 19.9% / Upper-middle 17.5% / High income 9.3%</p></td></tr>
<tr><td><p>消费心态（样本）</p></td><td><p>Cost-sensitive 45.5% / Value-driven 34.9% / Indifferent 12.4% / Premium-seeking 5.2%</p></td></tr>
</tbody>
</table>
<html5-block path="@./{DIR}/w_profile.html"></html5-block>

<h1 seq="auto">质量与校准：误差多大、覆盖多广</h1>
<p>构建是确定性的（seed=20260720），官方 RESULTS.md 报告了每个校准维度「目标 vs 达成」的最大绝对误差。<b>三个维度接近完美，地区维度偏差显著</b>——北美 18.8% 对目标 4.8%，根因是维基百科词条天然偏向欧美人物。做地区相关分析务必按已知人口结构加权，或使用 cohort 抽样按目标分布重采样（误差均以已知行为分母）。</p>
<table>
<colgroup><col width="22%"/><col width="14%"/><col width="14%"/><col width="18%"/><col width="20%"/><col width="12%"/></colgroup>
<thead><tr><th><p>维度</p></th><th><p>已知行数</p></th><th><p>缺失行数</p></th><th><p>最大绝对误差</p></th><th><p>目标来源</p></th><th><p>评价</p></th></tr></thead>
<tbody>
<tr><td><p>age_bracket</p></td><td><p>704,641</p></td><td><p>295,359</p></td><td><p>0.0749%</p></td><td><p>UN WPP 2024</p></td><td><p>优秀</p></td></tr>
<tr><td><p>gender_identity</p></td><td><p>774,736</p></td><td><p>225,264</p></td><td><p>0.0375%</p></td><td><p>UN + World Bank</p></td><td><p>优秀</p></td></tr>
<tr><td><p>urbanicity</p></td><td><p>582,321</p></td><td><p>417,679</p></td><td><p>0.0478%</p></td><td><p>UN + World Bank</p></td><td><p>优秀</p></td></tr>
<tr><td><p>region</p></td><td><p>874,653</p></td><td><p>125,347</p></td><td><p>14.0047%</p></td><td><p>UN WPP 2024</p></td><td><p>需加权</p></td></tr>
</tbody>
</table>
<p>描述覆盖：422,590 行（42.26%）带字段级自然语言描述（模型生成，合成人格不带）。官方随包提供 audit.json（残差诊断、逐类目标/达成、来源统计）与 calibration_targets.json（校准契约），复现口径完整。</p>
<html5-block path="@./{DIR}/w_calib.html"></html5-block>

<h1 seq="auto">一条真实人格长什么样</h1>
<p>从 parquet 分片第 2 行解码（来源：维基百科，169 个属性）。每个属性都带「证据原文 + 置信度 + 赋值类型」，可回溯到来源文本——这是「人类数据接地」的可审计性设计。</p>
<table>
<colgroup><col width="30%"/><col width="70%"/></colgroup>
<thead><tr><th><p>维度</p></th><th><p>取值</p></th></tr></thead>
<tbody>
<tr><td><p>age_bracket</p></td><td><p>45-54</p></td></tr>
<tr><td><p>region</p></td><td><p>Eastern Europe</p></td></tr>
<tr><td><p>gender_identity</p></td><td><p>Man</p></td></tr>
<tr><td><p>urbanicity</p></td><td><p>Nomadic / remote</p></td></tr>
<tr><td><p>socioeconomic_band</p></td><td><p>High income</p></td></tr>
<tr><td><p>economic_motivation</p></td><td><p>Premium-seeking</p></td></tr>
<tr><td><p>life_stage</p></td><td><p>Mid-life</p></td></tr>
</tbody>
</table>
<p>grounding 示例：<code>{{"field_index": 0, "evidence": "c. 406 – 453", "confidence": 0.7, "assignment_type": "structured_claim"}}</code>。运行时则使用 YAML 格式（persona_id / dimensions / provenance），由采样器从数据集生成。</p>
<html5-block path="@./{DIR}/w_persona.html"></html5-block>

<h1 seq="auto">配套文件：一个数据集 = 一套完整工具链</h1>
<table>
<colgroup><col width="44%"/><col width="44%"/><col width="12%"/></colgroup>
<thead><tr><th><p>路径</p></th><th><p>内容</p></th><th><p>大小</p></th></tr></thead>
<tbody>
<tr><td><p>release/data/persona-1m-0000..0009.parquet</p></td><td><p>人格主体（10 分片，Zstd）</p></td><td><p>3.9 GB</p></td></tr>
<tr><td><p>release/indexes/postings.sqlite</p></td><td><p>「维度=取值 → 全局行号」倒排索引</p></td><td><p>2.6 GB</p></td></tr>
<tr><td><p>release/persona_codes.schema.json</p></td><td><p>码本：1,290 字段、取值与打包规格</p></td><td><p>—</p></td></tr>
<tr><td><p>release/manifest.json</p></td><td><p>分片行数 / 字节 / SHA-256 / 来源统计</p></td><td><p>—</p></td></tr>
<tr><td><p>release/README.md · RESULTS.md</p></td><td><p>官方数据卡 · 校准结果</p></td><td><p>—</p></td></tr>
<tr><td><p>release/calibration_targets.json · audit.json</p></td><td><p>校准契约 · 审计报告</p></td><td><p>—</p></td></tr>
<tr><td><p>release/sample/sample.parquet</p></td><td><p>999 人 × 990 属性解码版（Dataset Viewer 展示用）</p></td><td><p>—</p></td></tr>
<tr><td><p>matraix-persona-dev-sample / validation-subset</p></td><td><p>YAML 冒烟测试与验证子集</p></td><td><p>3.2 / 1.5 MB</p></td></tr>
<tr><td><p>persona/schema/dimensions.json 等</p></td><td><p>官方 taxonomy（维度/类别/映射）</p></td><td><p>—</p></td></tr>
</tbody>
</table>
<html5-block path="@./{DIR}/w_files.html"></html5-block>

<h1 seq="auto">怎么用：三种打开方式</h1>
<p>官方推荐用 pyarrow 解码读取（不要用 datasets 库，打包格式无法解析）；需要条件筛选时走 SQLite 索引；做用户模拟时按校准目标分层采样，实例化为 LLM 智能体跑任务——即本仓库保温杯 demo 的做法。</p>
<pre lang="python" caption="解码读取（官方示例）"><code>import json, pyarrow.parquet as pq
schema = json.load(open("persona_codes.schema.json"))["columns"]
t = pq.read_table("data/persona-1m-0000.parquet")
def decode(attributes, null_bitmap):
    out = {{}}
    for i, col in enumerate(schema):
        if null_bitmap and (null_bitmap[i // 8] &gt;&gt; (i % 8)) &amp; 1:
            continue
        code = (attributes[i // 2] &amp; 0x0F) if i % 2 == 0 else (attributes[i // 2] &gt;&gt; 4)
        if code &lt; len(col["values"]):
            out[col["id"]] = col["values"][code]
    return out
person = decode(t["attributes"][1].as_py(), t["null_bitmap"][1].as_py())
person.get("age_bracket")   # 用 .get 不用 []：行是稀疏的</code></pre>
<html5-block path="@./{DIR}/w_usage.html"></html5-block>

<h1 seq="auto">边界与合规：必须知道的限制</h1>
<p>官方数据卡明确列出 4 条限制与 1 条许可红线。使用者尤其注意：这不是任何人群的代表性样本（校准只对齐一维边际）；「人类接地」不等于「已核验」（抽取属性可能有误）；数据集<b>仅限非商业研究用途</b>，子集（包括 40 万合成人格）不因提取而获得新的许可。</p>
<table>
<colgroup><col width="30%"/><col width="70%"/></colgroup>
<thead><tr><th><p>官方明示的限制</p></th><th><p>含义</p></th></tr></thead>
<tbody>
<tr><td><p>不是代表性样本</p></td><td><p>校准只对齐一维边际，不保证联合分布；来源选择偏差仍在</p></td></tr>
<tr><td><p>「人类接地」≠「已核验」</p></td><td><p>维基/Amazon/SO/PRISM 属性为模型抽取，可能有抽取错误；描述为模型生成</p></td></tr>
<tr><td><p>60/40 人机比例是设计选择</p></td><td><p>不代表真实世界的人机比例</p></td></tr>
<tr><td><p>未成年记录已移除</p></td><td><p>原 508 条真人问卷中 153 条 &lt;18 岁被剔除，故总数为 999,847</p></td></tr>
</tbody>
</table>
<html5-block path="@./{DIR}/w_limits.html"></html5-block>

<h1 seq="auto">快速参考（30 秒速览）</h1>
<p>一句话：999,847 个结构化虚拟人格 × 1,290 维度，6 个真实来源（60%）+ 合成（40%），研究用途，配套解码器与索引。关键数字与四维校准误差速查见下表与下图。</p>
<table>
<colgroup><col width="30%"/><col width="70%"/></colgroup>
<thead><tr><th><p>项目</p></th><th><p>值</p></th></tr></thead>
<tbody>
<tr><td><p>总数 / 维度 / 编码</p></td><td><p>999,847 / 1,290（43 子类 9 大族）/ 4-bit 打包每行 645 字节</p></td></tr>
<tr><td><p>体积 / 平均填充 / 带描述</p></td><td><p>4.17 GB + 2.6 GB 索引 / 656 / 1,290 / 422,590 行（42.26%）</p></td></tr>
<tr><td><p>校准 seed / 许可</p></td><td><p>20260720（确定性构建）/ 非商业研究用途</p></td></tr>
</tbody>
</table>
<html5-block path="@./{DIR}/w_ref.html"></html5-block>

<h1>参考来源</h1>
<p>本报告所有数字均来自官方文档与本地实际数据文件，正文未逐一标注处均可在以下来源核验：</p>
<ol>
<li><a href="https://github.com/MatrAIx-ai/MatrAIx-Persona-8B/tree/main/persona/datasets/matraix-persona-1m/release">MatrAIx Persona 1M 官方数据卡（release/README.md、RESULTS.md、manifest.json、audit.json、calibration_targets.json）</a>，2026-07-21 发布，获取日期 2026-09-16</li>
<li><a href="https://huggingface.co/datasets/MatrAIx2026/MatrAIx_Persona_1M_Public_Release">HuggingFace：MatrAIx_Persona_1M_Public_Release</a>，获取日期 2026-09-16</li>
<li><a href="https://arxiv.org/abs/2608.04205">MatrAIx: Simulating the World with 8.3 Billion Persona Agents（arXiv:2608.04205）</a>，2026-08-04</li>
<li><a href="https://github.com/MatrAIx-ai/MatrAIx-Persona-8B">MatrAIx-Persona-8B 仓库 README 与 docs/persona</a>，获取日期 2026-09-16</li>
</ol>"""

p = os.path.join(DIR, "draft.xml")
open(p, "w", encoding="utf-8").write(xml)
print("XML written:", p, len(xml), "B")
