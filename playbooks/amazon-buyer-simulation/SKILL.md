---
name: amazon-buyer-simulation
description: >-
  Run MatrAIx Persona-8B "million-buyer product simulation" experiments on Amazon (or other
  marketplace) category data: turn a full-field product export (Excel/CSV + main images) into
  official-pipeline survey tasks, run 1000 AI buyer personas (shelf-choice and/or decision-journey
  experiments), aggregate the votes + open-text reasons, and produce plain-language Chinese HTML
  reports for e-commerce leaders. Use when the user provides an Amazon product spreadsheet (ASIN
  full-field export / TOP-N list / specified ASINs) and asks to simulate buyers choosing products,
  build a survey/task config, run personas at scale, compare simulated share vs real rank, analyze
  rejection reasons / decision factors / listing optimization, or generate a buyer-test report.
  Covers task construction, persona sampling (amazon source, region filter), nohup batch running,
  result aggregation, and report generation — end to end.
license: Proprietary — internal use only
---

# Amazon 买家模拟选品实验（MatrAIx Persona-8B）

把「Amazon 全字段商品表 + 主图」变成「1000 个 AI 买家投票 + 可追溯理由 + 大白话中文报告」的端到端链路。
**这是一条官方管道（official pipeline）的复用方法，不是新框架**：所有运行都走 MatrAIx 既有的 task / job / harbor / survey-eval 服务，脚本只做配置生成与结果聚合。

## 何时触发

用户给出 Amazon（或其他电商）商品数据（Excel/CSV：ASIN、标题、价格、评分、评价数、类目排名、库存状态、图片链接），并要求：
- 让 N 个（通常 1000）模拟买家在这些商品里选择、说理由、说为什么不选其他款；
- 模拟购物决策旅程（第一眼点谁→看什么→买不买→转投谁→兜底买谁）；
- 比较模拟份额与真实类目排名、分析拒绝原因/决策因素/翻页容忍度/Listing 要素；
- 产出给领导和电商人员看的报告。

## 链路总览（5 阶段，每阶段都有已验证的参考脚本）

```
①数据准备  Excel/CSV + 主图 ──► products 数据 + assets/*.jpg（图片识别成外观描述）
②构建任务  ──► application/tasks/survey_<slug>/ 与 survey_<slug>-journey/（官方 task 9 文件布局）
③生成 Job  ──► configs/jobs/.../<slug>-n1000.yaml（官方采样服务，amazon 源 + 区域过滤 + seed）
④运行      smoke → n1 → n20 pilot → nohup n1000（并发 30，断点续跑）
⑤聚合报告  jobs/<job>/*/artifacts/app/output/survey_result.json
           ──► summary.json + raw.csv ──► 两份大白话 HTML 报告
```

参考实现（本品类已跑通、0 错误，换品类时**复制改造，不要从零写**）：

| 阶段 | 参考脚本/文件 | 换品类时改什么 |
| --- | --- | --- |
| ①数据 | `results/shower-liner-6asin/assets/*.jpg`、`products.example.json`（本目录） | 换成自己品类的产品 JSON 与主图 |
| ②任务 | `results/shower-liner-6asin/build_task.py`、`build_journey_task.py` | 顶部 `PRODUCTS` 字典、`task.toml` 的 name/tags、问卷题 |
| ③Job | `scripts/generate_shower_liner_jobs.py`、`generate_shower_liner_journey_jobs.py` | 脚本里的 `task=` 路径与 `slug`；参数 n/concurrent/seed 走命令行 |
| ④运行 | 本文「阶段④」命令 | 换 job yaml 路径；一律 nohup |
| ⑤聚合 | `results/shower-liner-6asin/aggregate_shower_liner_experiment.py` | `PRODUCT_META`、两个 job 目录、题目 ID 映射 |
| ⑤报告 | `results/shower-liner-6asin/generate_shower_liner_reports_v2.py` | 顶部 `products` 数组、DATA 指标映射、结论文案 |

## 输入要求（先核对，缺了先补，不要猜）

- **商品表必填**：ASIN、品牌、英文标题、价格（缺货可为空但要标注）、星级、评价数、**真实类目排名**、库存/配送状态（In Stock / Only N left / Currently unavailable / no Featured Offer）、材质、规格、件数、核心卖点、主图 URL。
- **主图必须下载并逐张肉眼核验**：内容对得上、清晰、无水印/防盗链占位；并**据图写一段客观外观描述**（颜色/纹理/透明度/场景/配件），填进货架 `look` 字段——外观维度不激活，买家就无法对外观投票（保温杯 V1 的教训：没有外观描述时「设计颜值」得票为 0）。
- 缺货/无价/新品**如实标注**，它们是「一票否决」证据，不得伪装成正常商品。
- 输入字段口径见 `products.example.json` 顶部 `_schema`。

## 阶段① 数据准备

1. 用 sheet 能力读 Excel 全部子表（常见：ASIN 总览 / 全属性明细 / 图片链接 / 口径与缺口）。
2. 建实验目录 `results/<category-slug>/` 与 `assets/`，下载主图（文件名用 ASIN），逐张 `Read` 核验并写外观描述。
3. 整理成产品清单，给每款分配**连续字母选项 A/B/C…** 和一个 **2-4 字中文短名**（最好带颜色/外观，如「水立方」），报告全篇用「① 水立方」这种「圈号数字+短名」统一指代。

## 阶段② 构建官方任务（两类标准实验）

每个实验是 `application/tasks/survey_<slug>[/−journey]/` 目录，固定 9 个文件：
`task.toml`、`instruction.md`、`input/context.md`、`input/questionnaire.yaml`、`persona_strategy.json`、`reporting.json`、`tests/{test_state.py,test.sh,verifier_env.sh}`。

- **实验一·货架选择（choice）**：选 1 款+理由；对**每一款未选商品**单独问拒绝原因（多选）；翻到第几页还愿浏览/购买；第一/第二决策因素；Listing 8 要素重要性 Likert 1-5；一票否决项；材质/透明度偏好；徽章效应；切换诱因；价格接受度；购买意向。浴帘版 26 题。
- **实验二·决策旅程（journey）**：q_first_click → q_click_info（多选≤3）→ q_buy_decision → q_consider_other → q_next_choice → q_fallback，**6 个决策题全部 `askRationale: true`**；再加 q_page_search、q_overall_factor。浴帘版 8 题。

题目/选项设计细则与可复用题库见 `references/questionnaire_design.md`。

关键约束：
- `questionnaire.yaml`：`schemaVersion:'1.0'`、每题 `id/type(single_choice|multi_choice|likert)/required`；likert 用 `minValue/maxValue`；产品选项末位固定加 `none_of_these`。
- `task.toml`：`[task].name = "application/survey_<slug>"`、`type="survey"`、`[environment].definition = "application/shared-survey-form"`。
- `persona_strategy.json`：`sources:["amazon"]`、`dimensionFilters.region:["North America"]`（美亚）、random 采样；保留 datasetProfile 口径（见参考实现）。
- `tests/test_state.py`：choice 版校验 q_choice 合法且理由≥10 字符；journey 版校验 6 个决策题有答案且理由≥10 字符；`ALLOWED_CHOICES` 必须与问卷选项一致。
- **复制参考脚本的必改项**：build 脚本顶部写死了 `ROOT` 绝对路径、`TASK` 名、`PRODUCTS`、task.toml name/tags，换机器/品类全部要改；**先跑 choice 的 build 再跑 journey**（journey 脚本读取 choice 已生成的 test_state.py 改写），产品数≠6 时还要改 journey 脚本里硬编码的 A-F 字母块。完整逐脚本清单见 `TROUBLESHOOTING.md` 第〇节。
- 构建后**冒烟**：`uv run matraix smoke application/tasks/survey_<slug>`，期望 `Smoke: ok`。

## 阶段③ 生成 Job（官方采样服务）

不要用 CLI 的 `--sample-size 1000`（>100 会被 UI 预览截断为 32）。用复用官方
`PersonaPoolService.sample_pool(..., include_persona_ids=True)` 的生成脚本（与 UI 同路径，是官方路径不是绕过）：

```bash
.venv/bin/python scripts/generate_shower_liner_jobs.py <n> <concurrent> <seed>
# 通用形态见脚本：--task application/tasks/survey_<slug> --sources amazon --filter region=North America
```

产出 `configs/jobs/application-task-job-recipe/<slug>-n<n>.yaml`（含 1000 个 persona agent + tasks）和同名 `.meta.json`。
默认：n=1000、**并发 30**、seed=42、model `deepseek/deepseek-chat`、amazon 源、North America。两个实验各生成一份。

## 阶段④ 运行（阶梯 + nohup 后台）

```bash
cd <repo>; set -a && . ./.env && set +a     # matraix run 不自动读 .env，必须先导出 DEEPSEEK_API_KEY
# 0) 冒烟      uv run matraix smoke application/tasks/survey_<slug>
# 1) n=1 试跑  uv run matraix run -c configs/.../<slug>-n1.yaml   --max-cost-usd 1
# 2) n=20 pilot uv run matraix run -c configs/.../<slug>-n20.yaml --max-cost-usd 2   # 看解析率/成本
# 3) n=1000 全量，务必 nohup 脱离会话（agent 后台会被下一轮对话回收！）
export MATRIX_SURVEY_TASK_PATH=application/tasks/survey_<slug>
nohup .venv/bin/matraix run -c configs/jobs/application-task-job-recipe/<slug>-n1000.yaml \
  --max-cost-usd 12 > logs/<slug>.log 2>&1 &
```

- 多个实验串行：写一个 queue shell（参考 `scripts/run_shower_liner_queue.sh` 的 `run_job` 函数，每 job 前 `rm -f jobs/<job>/lock.json`），整体 `nohup bash xxx.sh &`。
- **断点续跑**：重跑同一 yaml 会复用已完成 trial；续跑前先清理缺 `config.json` 的不完整 trial 目录（否则启动即崩）。
- 进度核对：数 `jobs/<job>/*/artifacts/app/output/survey_result.json` 的份数；完成数应 = n，且 0 errored。
- **官方管道识别验证**：`curl -s http://127.0.0.1:8765/api/survey-eval/instruments` 应含问卷 id；`/api/survey-eval/harbor-tasks` 应含任务。
- 长任务一律 nohup；杀进程用精确 PID（`ps` 找 PID 再 `kill`），**不要 `pkill -f`**（会误杀同名新队列）。
- 全部坑见 `TROUBLESHOOTING.md`。

## 阶段⑤ 聚合与报告

聚合（参考 `aggregate_shower_liner_experiment.py`）：
- 读 `jobs/<job>/*/artifacts/app/output/survey_result.json`，每份含 `answers:[{questionId,value,rationale}]`。
- 单选题算份额%，多选题算提及%（分母=有效回答 n，多选和可>100%），likert 算均分（**加权均值要用分值×人数，别把选项 key 当数字求和**）。
- 输出 `results/<slug>-experiment/summary.json` + 两份原始答卷 CSV（**utf-8-sig 带 BOM**，Excel 直接打开不乱码；journey 理由列后缀是 `_why`）。复制脚本后必改 `ROOT/OUT/PRODUCT_META/OPTION_ORDER`。
- **聚合脚本不产出开放题主题词频**；报告词频图需另对 raw CSV 的 `*_why` 列做词典归类（外观/价格/评价/评分/材质/功能/品牌/库存配送），同一人同主题只计一次，可粘贴片段见 `references/report_standard.md` 第八节；词频=被提及程度，不等于重要性或因果。

报告（参考 `generate_shower_liner_reports_v2.py`，规范见 `references/report_standard.md`）：
- **一个实验一份独立 HTML**（货架选择、决策旅程分开，不要合成一份）。
- 大白话、简单图表（只用横向条形/简单柱状/环形；不用漏斗/热力/堆叠/双轴）、每张图一句人话结论。
- 开头放 3-5 条核心结论（结论+核心数据）；紧跟「先认识这 N 款产品」速查表（圈号编号+品牌+价格+评分+评价数+真实排名+一句话特征），全篇编号统一。
- 必含：真实排名 vs 模拟份额对比、每款拒绝原因 Top、决策因素、Listing 要素重要性、一票否决、翻页容忍、首点 vs 兜底、买不买、转投流向、开放理由词频、少量买家原话（英文原文+中文大意）。
- **数据来源分清自动/手填**：份额、因素、重要性、红线、旅程占比、买家原话随 summary.json 自动更新；产品卡数组（含 share 角标）、主题词频、核心结论与建议文案需手填。ECharts 用本技能自带的 `assets/echarts.min.js`（原脚本从马桶刷报告 HTML 提取，缺文件会静默空库、图全不渲染）。
- 产品卡：主图 base64 内嵌、圈号编号、首选份额角标、价格/评分/评价/排名、状态色、Amazon 链接。
- 证据分级与表达：只基于实际数据；缺失维度明说「当前数据未覆盖」；高频提及≠因果；普通比例差不写「显著」；建议分「马上做/试试看/先观望」。
- **交付前自检（必做）**：用 html skill 的 `scripts/shot.py <html>` 渲染，确认 0 console error、canvas 数与图数一致、产品卡数=N、无 clippedText；清理 `_shots/`。

## 硬性质量门

1. 任务走官方布局，smoke 通过，后端 instruments/harbor-tasks 能识别。
2. 全量 n 份答卷齐全、0 errored（不完整 trial 已清理/续跑补齐）。
3. 每个百分比标得出分母 n；多选/likert/开放题口径不混。
4. 报告数字全部能回溯到 summary/CSV；不编造排名、库存、Buy Box、销量、因果。
5. 两份报告各自独立、编号全篇一致、简单图表、自检 0 错误后再交付。
