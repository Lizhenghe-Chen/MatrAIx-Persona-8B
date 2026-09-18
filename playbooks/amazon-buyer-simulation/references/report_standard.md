# 大白话报告标准（面向领导与电商业务人员）

标杆实现：`results/shower-liner-6asin/generate_shower_liner_reports_v2.py` 产出的两份 HTML。
目标：领导和各层级人员**不看教程也能一眼懂**，数字可回溯，结论不夸大。

## 一、形态

- **一个实验一份独立 HTML**：`<slug>_choice_report.html`（货架选择）、`<slug>_journey_report.html`（决策旅程），不合并。
- 单文件自包含：CSS/JS 内联，ECharts 库内嵌（从历史报告提取，离线可开），主图 base64 内嵌。
- 结论**放最前面**，产品速查表紧随其后；先给答案，再给证据。

## 二、编号与定位（最重要，全篇统一）

- 每款产品分配连续字母 A/B/C… 和 2-4 字中文短名（带颜色/外观，如「水立方」）。
- 报告全篇用「圈号数字 + 短名」：① 祖母绿、② 蓝波纹、③ 水立方……图、表、正文、产品卡一律一致。
- 报告开头放「先认识这 N 款产品」速查表，每行：编号 | 品牌+短名 | 价格 | 评分/评价数 | 真实类目排名 | 一句话特征（含缺货/新品/低价等状态）。
- 产品卡：主图 + 圈号编号 + 首选份额角标 + 价格/评分/评价数/排名 + 状态色标签（现货绿 / 配送受限或新品黄 / 缺货红）+ Amazon 链接。
- 目的：任何人看到正文「③」都能立刻在速查表/产品卡定位到是哪款。

## 三、语言

- 大白话标题与结论，例如「1000 人里有 600 人选了 ③」「真实排名最靠前的 ①，只有约 1/5 的人买」。
- 每张图配**一句人话结论**（图上方或标题下），不堆术语；英文买家原话给「英文原文 + 中文大意」。
- 行动建议用三档中文标签：**马上做（ACT）/ 试试看（TEST）/ 先观望（WATCH）**。
- 不用：漏斗、热力、堆叠、双轴、雷达等复杂图；不用「显著」「碾压」「完胜」等强词。

## 四、只用三种简单图

| 图型 | 用途 |
| --- | --- |
| 横向条形 | 份额/提及率排行（产品对比、因素、红线、拒绝原因）——最常用 |
| 简单柱状 | 少量分类对比（买不买分布、翻页） |
| 环形 | 单一构成占比（购买决策、价格接受度） |

- 排行按数值降序；数据标签直接显示百分比/人数；颜色克制，突出重点款（如赢家）。
- 多选拒绝原因在 JS 里是对象，直接遍历，勿当数组 `.find()`（曾导致后续图全不渲染）。

## 五、必含内容

**货架选择报告**：① 核心结论 3-5 条；② 产品速查表 + 产品卡；③ 最终首选份额（含「都不买」）；④ **真实类目排名 vs 模拟份额对比**（回答「第一名是不是第一名」）；⑤ 每款拒绝原因 Top（多选%）；⑥ 第一/第二决策因素；⑦ Listing 8 要素重要性均分；⑧ 一票否决项提及率；⑨ 浏览页/购买页容忍；⑩ 徽章效应、切换诱因、材质/功能偏好、价格接受度、购买意向；⑪ 买家原话；⑫ 行动建议表。

**决策旅程报告**：① 核心结论；② 速查表/产品卡；③ 第一眼点击 vs 被迫兜底份额（对比「吸引点击」与「真正兜底」）；④ 买不买分布；⑤ 是否考虑其他款；⑥ 下一家看谁/转投流向；⑦ 第一眼最想点款的理由词频；⑧ 点进去必看什么（多选）；⑨ 不立刻买的理由词频；⑩ 翻页深度；⑪ 全程最看重因素；⑫ 买家原话与建议。

## 六、证据分级（宁少勿编）

- **数据事实**（人数/占比/均分/排名/原话）可直接陈述。
- **数据模式**用「略高/略低/当前样本中呈现…趋势」，不写「明显领先/显著更高」。
- **关联**只说「某因素与最终选择存在一定关系」，**不写因果**（除非实验设计支持）；高频提及 ≠ 购买驱动。
- 无统计检验不写「统计显著」；小分群不下稳定结论。
- 缺数据就写「当前数据未覆盖 / 当前数据不足以支持进一步判断」，不用常识补齐，不把缺失解释成「没差异」。
- 每个百分比标得分母 n；多选与单选口径分开；均分用分值×人数加权。

## 七、交付前自检（必做）

用 html skill：`python3 <html-skill>/scripts/shot.py <报告.html>`（系统 python3，含 playwright）。
- consoleErrors = 0；canvas 数 = 设计图数（choice 9、journey 11 为浴帘实例，按实际）；产品卡数 = N。
- 无 clippedText、无文字溢出；移动端图表占宽正常（responsiveChartIssues 为空）。
- 抽查 3 个图的数字与 summary.json 一致；链接为 `https://www.amazon.com/dp/<ASIN>`。
- 自检完删除 `_shots/`。HTML 不要用 artifact-preview。

## 八、复现必看：哪些自动、哪些手填、依赖在哪

- **自动（读 summary.json，勿改其键名）**：各产品份额、拒绝原因占比、因素、Listing 重要性均分、红线、切换诱因、徽章效应、旅程首点/查看项/买不买/转投/兜底/翻页占比、买家原话 `sample_*_reasons`。
- **手填**：报告脚本顶部 `products` 展示数组（编号/中文名/价格/评分/评价/排名/特征/img/asin，**产品卡角标 `share` 是手写数字，不随 summary 更新**）、核心结论、对卖家的启示、行动建议表。
- **ECharts 库**：浴帘脚本从马桶刷报告 HTML 正则提取，缺文件会静默得到空库、图全不渲染。复现改为读本技能自带的 `playbooks/amazon-buyer-simulation/assets/echarts.min.js`：
  ```python
  ECHARTS_JS = open("<repo>/playbooks/amazon-buyer-simulation/assets/echarts.min.js", encoding="utf-8").read()
  ```
- **开放题主题词频（summary 不含，需自算）**：对 raw CSV 的 `*_why` 理由列按关键词词典归类计数，同一人同一主题只计一次，再手填进 `DATA["reasons"]`。可粘贴片段：
  ```python
  import pandas as pd
  df = pd.read_csv("survey_journey_raw.csv", encoding="utf-8-sig")
  THEME = {  # 主题 -> 关键词（小写匹配，按品类扩充）
      "外观": ["look","color","colour","design","pattern","nice","pretty","style","texture"],
      "价格": ["price","cheap","expensive","value","affordable","deal","cost"],
      "评价": ["review","rating","star","feedback","comment"],
      "材质安全": ["material","eva","pvc","safe","odor","smell","bpa","quality"],
      "功能": ["magnet","weighted","waterproof","dry","mold","hook","grommet"],
      "品牌": ["brand","trust","know","reputable","familiar"],
      "库存配送": ["stock","unavailable","delivery","ship","prime","buy box"],
  }
  def themes(text):
      t = str(text).lower(); return {k for k, ws in THEME.items() if any(w in t for w in ws)}
  def count(col):
      out = {}
      for txt in df[col].dropna():
          for k in themes(txt): out[k] = out.get(k, 0) + 1
      return dict(sorted(out.items(), key=lambda x: -x[1]))
  print(count("q_first_click_why"))   # 列名以实际 raw CSV 为准（理由列后缀 _why）
  ```
  词频只表示「多少人提到」，不代表重要性，更不能写成购买因果；关键词归类是近似方法，报告里注明为开放题定性归纳。
