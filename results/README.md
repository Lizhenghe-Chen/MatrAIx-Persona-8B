# 模拟结果总览（results/）

> 基于 MatrAIx-Persona-1M 人格数据集 × DeepSeek API 的「虚拟消费者购物式选择」模拟产物。
> 三个 demo 已按任务归类到子目录，下文为全部文件的索引与打开方式。

## 1. 马桶刷模拟（最新 · 净化货架 + 数据源配置版） — `toilet-brush-demo/`

| 文件 | 内容 | 打开方式 |
|---|---|---|
| `toilet_brush_leader_report.html` | **领导汇报（推荐先看）**：一图看懂、市场份额、版本对比、价格带、商品表现、分群、0 票证据链、理由摘录、业务启示、配置说明 | 浏览器直接打开 |
| `toilet_brush_dashboard.html` | 交互式数据看板（ECharts，可筛选） | 浏览器打开 |
| `toilet_brush_raw.csv` | 1000 人原始数据：每题答案、购买理由、价格/属性/人格维度（utf-8-sig） | Excel / 表格软件 |
| `toilet_brush_summary.json` | 全量统计：市场份额、价格带、分群交叉、0 票证据链等 | 编辑器 / 脚本 |
| `toilet_brush_top10.json` / `.csv` | 货架商品数据（全英文）：名称/价格/材质/卖点/**外观客观描述**/图片/来源 | 编辑器 / 表格 |
| `persona_profile_config.json` | 本次数据源 Profile 配置（hard_filter / observed_review_style / soft_or_conditional_only / missing_by_default） | 编辑器 |
| `assets/` | 10 张商品图（jpg，报告引用） | 图片查看器 |
| `backup_v1_with_badges/` | **旧版（含推荐标识）**结果 4 件套，用于版本对比 | 同上 |

## 2. 保温杯模拟（早期 demo） — `water-bottle-demo/`

| 文件 | 内容 | 打开方式 |
|---|---|---|
| `bottle_choice_leader_report.html` | 领导汇报（6 款保温杯，1000 人） | 浏览器打开 |
| `bottle_choice_1000_dashboard.html` | 交互看板 | 浏览器打开 |
| `bottle_choice_1000_raw.csv` | 1000 人原始数据（含理由） | Excel / 表格 |
| `bottle_choice_1000_summary.json` | 全量统计 | 编辑器 |
| `assets/` | 6 张保温杯商品图 | 图片查看器 |

## 3. 数据源分析 — `data-source-analysis/`

| 文件 | 内容 | 打开方式 |
|---|---|---|
| `dataset_source_analysis.html` | MatrAIx-Persona-1M 数据集构成分析（≈1M 人格、1290 维度、7 个数据源、60:40 真实:合成等） | 浏览器打开 |

## 复现与方案

- 方案设计：仓库根目录 `DEMO_PLAN.md`
- 复现步骤（含 job 生成、pilot→全量、净化与配置说明）：仓库根目录 `DEMO_REPRODUCE.md`
- 任务定义（问卷/货架/人格策略）：`application/tasks/survey_toilet-brush-choice/`、`application/tasks/survey_bottle_choice/`
- 脚本：`scripts/generate_toilet_brush_job.py` / `aggregate_toilet_results.py` / `generate_toilet_leader_report.py`（及保温杯对应脚本）

## 快速上手

1. 给领导看 → 打开 `toilet-brush-demo/toilet_brush_leader_report.html`（或 `water-bottle-demo/bottle_choice_leader_report.html`）
2. 自己看数据 → 打开对应 `*_dashboard.html` 或 `*_raw.csv`
3. 想复现 → 按 `DEMO_REPRODUCE.md` 从 pilot 20 到全量 1000 重跑
