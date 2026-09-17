# MatrAIx × DeepSeek 保温杯购物模拟 Demo —— 复现操作文档

> 一句话：用 1000 个 AI「虚拟消费者」（人格画像库 Persona 1M）× DeepSeek 大模型，
> 让他们像逛电商一样在 6 款真实保温杯里挑选，再汇总出「谁会买什么、为什么、能接受什么价位」。

---

## 1. 这是什么（给领导的一页）

| 项目 | 内容 |
| --- | --- |
| 模拟对象 | 全球分层随机采样的 **1000 个虚拟消费者**（覆盖 18 岁+ 各年龄段、9 大地区、4 类消费心态） |
| 扮演引擎 | DeepSeek `deepseek-chat`（每个虚拟消费者用 1 次调用完成选择并说明理由） |
| 货架商品 | 6 款真实在售保温杯 +「都不买」（富光 ¥39.9 / Nalgene ¥119 / 杯具熊 ¥129 / 米家 ¥179 / 象印 ¥229 / Stanley ¥319） |
| 产出 | 市场份额、分群偏好（年龄 × 消费心态）、价格敏感度、购买意向，全部呈现在一个网页仪表盘上 |
| 成本 | 全量 1000 人约 **¥10 左右**（实测 $1.5 上下），pilot 20 人约 ¥0.25，单人多约 2 秒 |

**它为什么有用**：传统调研要招募真人、等几周、花几万块；这个 demo 把「新品/竞品上市前试水」
压缩成一条命令、半小时、一杯咖啡的钱，且每一票都带可回溯的购买理由。

---

## 2. 工作原理（怎么跑的）

```
Persona 1M 人格库（100 万人格，含年龄/地区/收入/消费心态等维度）
        │  ① 全球分层随机采样（先过滤成人，再随机抽 1000，后验分层校验）
        ▼
   1000 个虚拟消费者档案（每人约 5KB：性格、消费观、生活习惯）
        │  ② 每个档案注入「电商货架」任务（6 款杯子的卖点+价格 + 问卷）
        ▼
   DeepSeek 大模型逐人扮演：像真人一样权衡 → 投票 + 写理由
        │  ③ 官方校验器（verifier）检查：选项是否合法、理由是否充分
        ▼
   1000 条有效投票
        │  ④ 聚合脚本：市场份额 / 分群偏好 / 价格敏感度 / 购买意向
        ▼
   网页仪表盘（单文件 HTML，浏览器直接打开）
```

关键设计决策（已在 DEMO_PLAN.md 中与用户确认）：
- **采样**：全球分层 = 先按人口口径过滤（成人、全消费心态），再随机 1000 人，分析时按年龄/消费心态后验分层 —— 期望上等价于全球人口比例，且能保证 1000 人全部可采样。
- **货架**：6 款 = 3 档价格 × 本土/国际品牌混搭，价格取 2026-09 电商实价。
- **质量门**：每票必须选 7 个合法选项之一且理由 ≥10 字符，否则该票作废重跑（实测通过率 100%）。

---

## 3. 环境准备（一次性）

| 前置 | 说明 | 状态 |
| --- | --- | --- |
| 仓库 | `MatrAIx-Persona-8B`（含 Persona 1M 数据与 8.3B 人格模型工具链） | ✅ 已就绪 |
| Python 环境 | `uv` + 仓库 `.venv`（`uv sync` 一次即可） | ✅ 已就绪 |
| 人格库 | `persona/datasets/matraix-persona-1m/`（约 100 万条 + SQLite 索引） | ✅ 已就绪 |
| DeepSeek Key | 在 https://platform.deepseek.com/ 创建，填进仓库根目录 `.env` | ⬜ 需自备 |

`.env` 内容（一行即可，已 gitignore 不会提交）：
```bash
DEEPSEEK_API_KEY='sk-你的key'
```

---

## 4. 三步复现（复制即可运行）

所有命令在仓库根目录执行。**务必先加载 key**：
```bash
cd <仓库根目录>
set -a && source .env && set +a
export MATRIX_SURVEY_TASK_PATH=application/tasks/survey_water-bottle-choice
```

### 第 0 步：冒烟测试（10 秒，不花钱，验证任务本身没问题）
```bash
uv run matraix smoke application/tasks/survey_water-bottle-choice
# 期望输出：Smoke: ok
```

### 第 1 步：1 人试跑（约 30 秒，验证 DeepSeek 打通）
```bash
uv run matraix run -c configs/jobs/application-task-job-recipe/survey-water-bottle-choice-age-bracket-economic-motivation-n1.yaml --max-cost-usd 1
# 期望：1/1 通过，reward=1，成本 ~$0.0005
```

### 第 2 步：20 人 pilot（约 1 分钟，看解析率与成本）
```bash
uv run matraix run -c configs/jobs/application-task-job-recipe/survey-water-bottle-choice-age-bracket-economic-motivation-n20.yaml --max-cost-usd 1
# 期望：20/20 通过，reward 均值 1.0，成本 ~$0.03
```

### 第 3 步：1000 人全量（约 30 分钟，成本闸 $2 兜底）
```bash
# 3a. 生成 1000 人 job 配置（官方服务路径，见「常见问题①」）
uv run python scripts/generate_water_bottle_job.py 1000 10

# 3b. 运行
uv run matraix run -c configs/jobs/application-task-job-recipe/survey-water-bottle-choice-n1000.yaml --max-cost-usd 2
# 期望：1000/1000 通过，成本 ~$1.5，产物在 jobs/survey-water-bottle-choice-n1000/
```

### 第 4 步：聚合 + 生成仪表盘（秒级）
```bash
uv run python scripts/aggregate_bottle_results.py
# 产出（results/ 目录）：
#   bottle_choice_1000_raw.csv           —— 1000 人逐票明细（可 Excel 打开）
#   bottle_choice_1000_summary.json      —— 结构化聚合结果（可二次分析）
#   bottle_choice_1000_dashboard.html    —— ⭐ 领导展示用网页仪表盘
```

**给领导看**：双击打开 `results/water-bottle-demo/bottle_choice_1000_dashboard.html`（无需联网环境变量，图表为网页内嵌）。
仪表盘包含：① 核心 KPI 卡片（样本数/通过率/中位选择价/平均可接受价档）② 市场份额饼图
③ 价格敏感度（可接受价位 × 消费心态）④ 购买意向分布 ⑤ 分群偏好（选择 × 年龄段/经济动机的堆叠条形图）
⑥ 最看重属性 ⑦ 样本构成校验表。

---

## 5. 关键文件清单

| 文件 | 作用 |
| --- | --- |
| `application/tasks/survey_water-bottle-choice/` | 任务定义（货架文案+问卷+校验规则+采样策略），完整自包含 |
| `├─ input/context.md` | 货架：6 款杯子的真实卖点与价格 |
| `├─ input/questionnaire.yaml` | 问卷：选哪款 / 可接受价位档 / 最看重属性 / 购买意向 / 理由 |
| `├─ tests/` | 校验器（verifier）：选项合法 + 理由充分，奖励 reward=1 |
| `├─ persona_strategy.json` | 采样策略：全球成人过滤 + 随机 1000 |
| `configs/jobs/application-task-job-recipe/*.yaml` | 已生成好的 1 人 / 20 人 / 1000 人三个 job 配置 |
| `scripts/generate_water_bottle_job.py` | 1000 人 job 生成器（绕过 CLI 预览截断，走官方 Playground 服务） |
| `scripts/aggregate_bottle_results.py` | 聚合 + 仪表盘生成 |
| `jobs/survey-water-bottle-choice-n1000/` | 全量运行产物（每票含问卷结果 + 购买理由 + 人格档案） |
| `results/` | 交付物：CSV 明细 + JSON 聚合 + HTML 仪表盘 |
| `DEMO_PLAN.md` | 设计文档（需求、货架选择依据、采样口径） |

---

## 6. 常见问题

**① 为什么生成 1000 人 job 不用官方 CLI 的 `--sample-size 1000`？**
官方 CLI 在 1M 人格池上会把 >100 的采样截断为 32 人预览（UI 预览上限）。
`scripts/generate_water_bottle_job.py` 复用了官方 Playground 后端的同一套服务
（`sample_pool(include_persona_ids=True)`），生成结果与 UI 一致 —— 这是官方路径，不是绕过。

**② Key 没填/填错？**
`grep DEEPSEEK_API_KEY .env`，确认非空；运行时报 `Credential: DEEPSEEK_API_KEY missing` 即未加载。

**③ 想换模型？**
任务与 job 配置均支持 `deepseek/deepseek-chat`（当前）与 `dashscope/deepseek-v4-pro`，
改 job YAML 里的 `model_name` 即可。

**④ 跑一半断网/超预算？**
`--max-cost-usd` 是硬闸，超了自动停。重跑相同 job 会复用已完成 trial（断点续跑）。

**⑤ 想换品类？**
复制 `application/tasks/survey_water-bottle-choice/` 为 `survey_xxx-choice/`，
改 `input/context.md` 的货架与 `questionnaire.yaml`，重新 smoke → pilot → 全量即可。

---

## 7. 本次实测结果摘要（2026-09-16）

| 阶段 | 结果 | 成本 |
| --- | --- | --- |
| smoke | ok | $0 |
| 1 人试跑 | 1/1 通过，reward=1（Casey Brooks 选杯具熊，理由合理） | $0.0005 |
| 20 人 pilot | 20/20 通过，reward 均值 1.0，44 秒 | $0.033 |
| 1000 人全量 | **1000/1000 通过，reward 均值 1.0**（1 个偶发 JSONDecodeError 已用 `harbor jobs resume -f` 重跑补上） | **$1.81（≈¥13）** |

**核心结果**（详见仪表盘）：杯具熊 316 ¥129 以 70.2% 份额领跑，富光 ¥39.9 21.9%，象印 ¥229 7.8%；
「都不买」0%；全球分层样本构成健康（9 大地区 / 6 个年龄段 / 4 类消费心态全覆盖）。
> 提示：结果受货架文案影响明显（杯具熊卖点文案最具说服力），用于决策时建议换多组文案做对照。

---

## 8. V2 优化：货架加外观描述 + 报告附真实商品图（2026-09-16）

**为什么做**：V1 的货架只有价格/参数/卖点，没有外观描述 —— 问卷里「设计颜值」得票为 0 正是
因为模型根本没机会感知外观。V2 给每款杯子补上「外观/设计」描述（激活美学维度），
并把 6 款真实商品图贴进领导汇报版，让报告一眼可信。

**改动清单**：
1. `application/tasks/survey_water-bottle-choice/input/context.md` —— 货架表新增
   `Look & design` 列（6 款逐一描述：富光哑光黑极简柱体 / Nalgene 半透明宽口 / 杯具熊奶油粉圆润萌系 /
   米家极简白 / 象印日系拉丝银纤细 / Stanley 双色大块头+侧把手）。
2. `scripts/generate_water_bottle_job.py` —— 支持第 3 个参数 `job_slug`（传 `--name`/`--job-name`），
   确保 V2 用全新 job 目录、不复用 V1 旧 trial（货架变了，旧票不能复用）。
3. `results/water-bottle-demo/assets/*.jpg` —— 6 款真实商品图（已下载并逐张人工核验：内容对得上、清晰、无水印；
   来源标注在报告卡片下方）。
4. `scripts/generate_leader_report.py` —— 货架区新增商品图卡片（图片+名称+价格+外观一句话+图源），
   成本/耗时改为从 summary 动态读取。
5. `scripts/finalize_v2_summary.py` —— 把官方成本（`jobs/<job>/_matraix_budget.json` 的 `spent_usd`）
   与耗时写入 summary.json，供报告展示真实成本。

**V2 复现命令**（在第 4 节「第 3 步」之后执行）：
```bash
# 1) 生成 V2 1000 人 job（新名字 → 全新 trial；并发 20 打满 DeepSeek 限额）
uv run python scripts/generate_water_bottle_job.py 1000 20 survey-water-bottle-choice-v2-n1000

# 2) 运行（后台跑，日志 /tmp/bottle_v2_run.log）
nohup uv run matraix run -c configs/jobs/application-task-job-recipe/survey-water-bottle-choice-v2-n1000.yaml \
  --max-cost-usd 3 > /tmp/bottle_v2_run.log 2>&1 &

# 3) 聚合 V2 结果
uv run python scripts/aggregate_bottle_results.py jobs/survey-water-bottle-choice-v2-n1000

# 4) 写入真实成本/耗时
uv run python scripts/finalize_v2_summary.py jobs/survey-water-bottle-choice-v2-n1000 results/water-bottle-demo/bottle_choice_1000_summary.json

# 5) 重生成领导汇报版（含商品图，需与 results/water-bottle-demo/assets/ 同目录）
uv run python scripts/generate_leader_report.py
# 自检：python3 <html-skill>/scripts/shot.py results/water-bottle-demo/bottle_choice_leader_report.html
```

**V2 实测结果**（2026-09-16 跑批完成，1000/1000 通过，reward 均值 1.0）：
| 项 | V1（纯参数货架） | V2（+外观描述） | 变化 |
| --- | --- | --- | --- |
| 杯具熊 ¥129 | 70.2% | 45.0% | 一家独大 → 回落 |
| 富光 ¥39.9 | 21.9% | 36.0% | 明显回暖 |
| 象印 ¥229 | 7.8% | 19.0% | 明显回暖 |
| Stanley ¥319 | 0.1% | 0.0% | 仍无人问津 |
| 「设计颜值」得票 | 0 票 | 8 票 | 美学维度激活 |
| 成本 | $1.81（≈¥13） | **$0.63（≈¥4.5）** | 更省 |
| 耗时 | 约 40 分钟 | **约 34 分钟** | 更快 |

> 关键洞察：同一批 1000 个虚拟消费者、同一价格，只把货架升级为「价格+参数+外观」，
> 份额就从「一家独大」变成「三足鼎立」——说明模拟消费者和真人一样，**看得见外观后会做更真实的权衡**；
> 报告里的商品图让领导一眼看到「他们到底在选什么」。
> 提示：V2 并发提到 20，实测吞吐约 36 人/分钟 —— 瓶颈在 DeepSeek API 每分钟限额，
> 继续加并发不会更快（会表现为排队/重试）。

**报告分群维度（V2 全量）**：除年龄段/消费心态外，聚合脚本还输出
`choice_x_region / choice_x_gender / choice_x_life_stage / choice_x_socio`（地区/性别/人生阶段/收入层级交叉偏好）
与 `product_reviews`（每款商品购买理由的关键词提及率，中英双语模式）。
另有 `consideration`（0 票商品证据链：被多少人点名考虑过、放弃后选了谁、典型理由原文）。
全部无需重跑模拟，`aggregate_bottle_results.py` 一次算齐，领导汇报版已内置这些图表与解读。

---

## 马桶刷 demo（北美 1000 人 · 10 款真实在售商品）

> 与保温杯 demo 同框架：把「10 款马桶刷 + 都不买」放上货架，请 1000 位**北美**虚拟消费者（Persona-1M，region=North America 过滤）用 deepseek-chat 做购物式选择，每题附 2–3 句购买理由。

### 0) 前置（一次即可）
```bash
cd /Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B
uv sync                      # 已配好的环境，pyarrow 等依赖已就绪
# .env 里配 DEEPSEEK_API_KEY='sk-...'（官方 DeepSeek API key）
```

### 1) 商品数据（已收集，含图片客观描述）
- `results/toilet-brush-demo/toilet_brush_top10.json` / `.csv`：Top10 榜单（reviews.guide 2026-09）对应真实在售商品，
  字段含 name / description / image_description（看图撰写的英文客观外观描述）/ price_usd_ref / rating / review_count / source_url / image。
- 图片：`results/toilet-brush-demo/assets/*.jpg`（10 张，已下载转码）。
- 注意：榜单第 6 名 Holikme 美亚主款 Currently unavailable，货架以同品类在售的 Ibergrif M34152 替代并注明。

### 2) 货架与问卷（已建好）
```text
application/tasks/survey_toilet-brush-choice/
  instruction.md / input/context.md / input/questionnaire.yaml
  persona_strategy.json（dimensionFilters: region=["North America"], sampleSize 1000）
  task.toml / reporting.json / tests/（test_state.py 校验 q_choice 合法选项+理由非空）
```
货架 10 款（USD 参考价）：Clorox $15.50 · mDesign $29.30 · BOOMJOY $12.99 · Sellemer $12.99 ·
OXO $19.97 · Ibergrif $13.90 · IXO $28.60 · nacena $23.50 · Asobeage $25.70 · JIGA $13.99，加「都不买」。

### 3) 生成 job（官方 CLI 流程，region 过滤）
```bash
uv run python scripts/generate_toilet_brush_job.py 20 10 survey-toilet-brush-choice-pilot-n20   # pilot 20
uv run python scripts/generate_toilet_brush_job.py 1000 20 survey-toilet-brush-choice-n1000     # 全量 1000
```
脚本复用了 `generate_water_bottle_job.py` 的官方采样链路（monkeypatch 仅解决 >100 采样被截断的问题），
并加 `--filter region=North America`；生成的 job 在 `configs/jobs/application-task-job-recipe/`。

### 4) 运行
```bash
set -a && . ./.env && set +a        # matraix run 不自动读 .env，必须先导出
uv run matraix run -c configs/jobs/application-task-job-recipe/survey-toilet-brush-choice-pilot-n20.yaml
uv run matraix run -c configs/jobs/application-task-job-recipe/survey-toilet-brush-choice-n1000.yaml
```
实测：pilot 20 人 31s（通过率 100%）；全量 1000 人 **24m35s**、**1000/1000 通过**、并发 20（吞吐约 40 人/分钟，DeepSeek 限额 20 RPM 上限附近）。

### 5) 聚合与报告
```bash
uv run python scripts/aggregate_toilet_results.py jobs/survey-toilet-brush-choice-n1000 results
uv run python scripts/generate_toilet_leader_report.py
```
产出（都在 `results/`）：
- `toilet_brush_raw.csv`：1000 行，含每题答案、购买理由原文、persona 维度（age/econ/region/gender/socio/urban）
- `toilet_brush_summary.json`：份额、分群交叉、理由关键词、0 票证据链、价格敏感度
- `toilet_brush_dashboard.html`：ECharts 交互看板
- `toilet_brush_leader_report.html`：给领导的单文件报告（中文，内联 SVG，含 10 款商品图、理由摘录、0 票证据链）

### 6) 结果速览（2026-09-16 实测）
| 指标 | 值 |
| --- | --- |
| 样本 | 1000 人，全部 North America |
| 通过率 | 100% |
| 销冠 | OXO Hideaway Compact（$19.97）81.3% |
| 第二梯队 | Clorox 9.0% · JIGA 3-Pack 9.0% |
| 0 票 | mDesign / Ibergrif / nacena / Asobeage（证据链见报告） |
| 都不买 | 0.0% |
| 成交价中位数 | $19.97 |
| 成本/耗时 | ≈$0.6 / 24m35s |

> 观察：当货架描述里有一款卖点完整、品牌信任强的商品（OXO：隐藏式+防积水+紧凑+Top Rated）时，
> 模型人格会强烈收敛于它（81%）；4 款 0 票商品多为「同质化硅胶款但价格更高」或「价格高且卖点弱」——
> 报告用证据链（被考虑人数+放弃理由原文）说明这是定位问题而非曝光问题。
> 若想分散投票，可给货架描述做「差异化卖点」设计（参考保温杯 V2 的教训：外观信息能显著改变份额结构）。

### 6b) 数据源 Profile 配置与货架净化（2026-09-16 更新）
- **货架净化**：从商品卖点中移除推荐性标识（Clorox "Amazon's Choice"、OXO "No.1 Top Rated"），
  货架只保留价格/材质/外观/功能等客观属性；含推荐标识的旧结果备份在 `results/toilet-brush-demo/backup_v1_with_badges/`。
- **数据源 Profile 配置**：写入 `persona_strategy.json` 的 `datasetProfile` 节点（及 `results/toilet-brush-demo/persona_profile_config.json`）：
  `hard_filter.region.North America=1.00`（等效 dimensionFilters 的北美硬过滤）、
  `observed_review_style.cog_verbosity`（Terse 16.1%/Concise 40.7%/Balanced 29.2%/Wordy 11.7%/Rambling 1.9%）、
  `soft_or_conditional_only`（primary_language=English 及经济/品质/购物风格维度仅在存在证据时赋值）、
  `missing_by_default`（age/gender/urbanicity/socio 等维度默认缺失——解释分群中的 unknown）。
  报告附注已内置配置说明；本配置不改变官方采样 schema，仅作为数据源口径记录。
