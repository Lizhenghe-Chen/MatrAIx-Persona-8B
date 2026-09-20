# Amazon 买家模拟选品实验 · 快速复现

把一份 Amazon 全字段商品表（Excel/CSV + 主图）跑成「1000 个 AI 买家投票 + 理由 + 大白话中文双报告」。
本目录是**方法资产（Skill + 提示词 + SOP）**，不是新框架——运行全部复用仓库官方管道，脚本以浴帘品类已跑通的实现为模板复制改造。

- 想让 AI 代理自动执行：把 `AGENT_PROMPT.md` 里的系统提示词喂给它 + 填用户输入模板。
- 想自己/带 AI 手动跑：照本文件 5 步。
- 题目怎么设计：`references/questionnaire_design.md`；报告长什么样：`references/report_standard.md`；报错了：`TROUBLESHOOTING.md`。

## 0. 环境（一次性）

```bash
cd <repo>                                   # MatrAIx-Persona-8B
set -a && . ./.env && set +a                # 导出 DEEPSEEK_API_KEY（matraix run 不自动读 .env）
curl -s http://127.0.0.1:8765/api/survey-eval/instruments >/dev/null && echo backend-ok
```
Python 用 `.venv/bin/python`（有 pyyaml）；HTML 截图自检用系统 `python3`（有 playwright）。

## 1. 数据准备

- 读全 Excel 所有子表（ASIN 总览/全属性/图片链接/口径缺口）。
- 建 `results/<slug>/assets/`，按 ASIN 下主图，**逐张打开核验**，据图写客观外观描述。
- 按 `products.example.json` 的 `_schema` 整理产品清单：字母选项 A/B/C…、中文短名、价格/评分/评价数/真实排名/库存状态/材质/规格/卖点，缺货无价新品如实标。

## 2. 构建两个官方任务

复制浴帘构建脚本并改造。**必改清单（漏一处跑不通）见 `TROUBLESHOOTING.md` 第〇节**，概要：两个脚本顶部的 `ROOT` 绝对路径、`TASK` 目录名、整个 `PRODUCTS` 字典、`task.toml` 模板里的 name/tags、品类词与品类专属题。

```bash
cp results/shower-liner-6asin/build_task.py         results/<slug>/build_task.py
cp results/shower-liner-6asin/build_journey_task.py results/<slug>/build_journey_task.py
# 顺序必须先 choice 后 journey：build_journey_task.py 会读取 choice 已生成的 tests/test_state.py 再改写
.venv/bin/python results/<slug>/build_task.py
.venv/bin/python results/<slug>/build_journey_task.py
# 产品数 ≠ 6 时：除问卷选项外，还要改 build_journey_task.py 里硬编码的 ALLOWED_CHOICES 字母块（A..N + none_of_these）
uv run matraix smoke application/tasks/survey_<slug>          # 期望 Smoke: ok
uv run matraix smoke application/tasks/survey_<slug>-journey  # 期望 Smoke: ok
```

## 3. 生成 Job（官方采样，n=1000/并发30/seed42/amazon/北美）

```bash
cp scripts/generate_shower_liner_jobs.py         scripts/generate_<slug>_jobs.py
cp scripts/generate_shower_liner_journey_jobs.py scripts/generate_<slug>_journey_jobs.py
# 编辑每个脚本里的 task= 路径与 slug= 命名（位置参数为 n concurrent seed）
.venv/bin/python scripts/generate_<slug>_jobs.py         1000 30 42
.venv/bin/python scripts/generate_<slug>_journey_jobs.py 1000 30 42
# 先各跑 n=1、n=20 验证：把位置参数换成 1 / 20 生成小 job
```
> 不要用 CLI 直接 `--sample-size 1000`（>100 被截断为 32）；脚本走官方 sample_pool(include_persona_ids=True)。

## 4. 运行（阶梯 + nohup 后台）

```bash
# n=1、n=20 前台验证 reward=1、解析率 100%、成本正常后再全量
.venv/bin/matraix run -c configs/jobs/application-task-job-recipe/<slug>-n1.yaml   --max-cost-usd 1
.venv/bin/matraix run -c configs/jobs/application-task-job-recipe/<slug>-n20.yaml  --max-cost-usd 2

# 全量：写 queue shell（参考 scripts/run_shower_liner_queue.sh 的 run_job 函数，
#       注意删掉其中已废弃的 rank-* 三行），nohup 串行跑两个实验
nohup bash scripts/run_<slug>_queue.sh > logs/<slug>_queue.log 2>&1 &

# 进度：数答卷份数直到各 =1000
ls jobs/<slug>-n1000/*/artifacts/app/output/survey_result.json 2>/dev/null | wc -l
ls jobs/<slug>-journey-n1000/*/artifacts/app/output/survey_result.json 2>/dev/null | wc -l
```
启动崩溃 → 删缺 `config.json` 的残缺 trial 目录再续跑；重跑同 yaml 自动断点续跑。停进程用精确 PID，禁止 `pkill -f`。

## 5. 聚合 + 双报告

```bash
cp results/shower-liner-6asin/aggregate_shower_liner_experiment.py results/<slug>/aggregate.py
# 必改：ROOT、OUT（浴帘产物落在 results/<slug>-experiment/，注意 -experiment 后缀）、
#       PRODUCT_META、OPTION_ORDER（字母+none_of_these）；题目 ID 若动过问卷要同步。
#       job 目录可用 --choice-dir / --journey-dir 覆盖。
.venv/bin/python results/<slug>/aggregate.py        # 产出 summary.json + survey_*_raw.csv（utf-8-sig）

cp results/shower-liner-6asin/generate_shower_liner_reports_v2.py results/<slug>/gen_reports.py
# 必改：顶部 ROOT/SUMMARY/ASSETS/OUT_DIR；TOILET_REPORT 改为
#       playbooks/amazon-buyer-simulation/assets/echarts.min.js（离线 ECharts，避免依赖马桶刷报告）；
#       products 展示数组（含产品卡 share 角标是手填）、DATA["reasons"] 词频、核心结论与建议文案。
# 说明：份额/因素/重要性/红线/旅程占比/买家原话随 summary.json 自动更新；
#       产品卡、主题词频、结论文案需手填；词频 summary 不产出，按 report_standard.md 第八节片段对 raw CSV 的 *_why 列自算。
.venv/bin/python results/<slug>/gen_reports.py      # 产出两份独立 HTML

# 交付前自检（系统 python3，含 playwright）
python3 <html-skill>/scripts/shot.py results/<slug>-experiment/<slug>_choice_report.html
python3 <html-skill>/scripts/shot.py results/<slug>-experiment/<slug>_journey_report.html
```

## 产物清单

| 产物 | 位置 |
| --- | --- |
| 官方任务 ×2 | `application/tasks/survey_<slug>/`、`survey_<slug>-journey/` |
| Job yaml ×2 | `configs/jobs/application-task-job-recipe/<slug>[-journey]-n1000.yaml` |
| 答卷 ×2000 | `jobs/<slug>[-journey]-n1000/*/artifacts/app/output/survey_result.json` |
| 聚合 | `results/<slug>-experiment/summary.json`、`survey_choice_raw.csv`、`survey_journey_raw.csv`（主图等输入在 `results/<slug>/assets/`） |
| 报告 ×2 | `results/<slug>-experiment/<slug>_choice_report.html`、`<slug>_journey_report.html` |

## 默认口径（用户未另行指定）

两类实验各 n=1000、并发 30、seed 42、`deepseek/deepseek-chat`、amazon 人格源、North America、随机采样；产品选项 A..N+none_of_these；不做排名位置/匿名对照臂。

## 浴帘参考结果（验证链路用，数字勿照搬到新品类）

6 款浴帘各 1000 人、0 错误：③ 水立方（真实排名 #124）拿 60.0% 首选，真实排名最靠前的 ① 祖母绿（#27）仅 20.8%——模拟份额与真实排名并不一致，正是实验价值所在；购买只认搜索第 1 页（97.7%），点进详情页几乎必看材质安全（99.8%）与评价（99.5%），缺货是 100% 一票否决。
