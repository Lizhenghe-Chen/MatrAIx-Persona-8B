# 千人人格「购物式选购」Demo 设计方案

> 用 MatrAIx Persona 1M 人格池 + DeepSeek API，模拟约 1000 名消费者在真实竞品货架前的选购行为：
> 每个人格像逛电商一样从 6 款保温杯中挑一款（或都不买），输出结构化理由；聚合后得到市场份额、分群偏好、价格敏感度等洞察。
> 品类可换（猫爬架、电动牙刷等），本方案以「保温杯」为默认品类，设计本身品类无关。

---

## 1. Demo 目标

- 演示 MatrAIx 的完整能力闭环：**人格采样 → 任务执行 → 校验 → 聚合洞察**
- 展示 DeepSeek 作为人格模型（模拟用户大脑）跑 1000 人规模选购
- 输出一份可读的「虚拟市场调研」结果：谁买什么、为什么、价格上限在哪

## 2. 品类与货架（默认：保温杯，6 款）

| # | 产品 | 容量 | 核心卖点 | 参考价 | 价格带 |
|---|------|------|----------|--------|--------|
| 1 | 富光 316 基础保温杯 | 500ml | 平价国民款，基础真空保温，密封稳定 | ¥39.9 | 入门 |
| 2 | Nalgene Sustain 32oz | 946ml | 轻量环保（50% 再生 Tritan），运动户外，不保温 | ≈¥119（$17） | 入门-中 |
| 3 | 杯具熊 316 保温杯 | 600ml | 百元档综合最优：316/316L 内胆、无尾真空 | ¥129 | 中 |
| 4 | 米家保温杯 | 500ml | 316 不锈钢、性价比国民品牌 | ¥179 | 中 |
| 5 | 象印 SM-SZ 系列 | 480ml | 日系高端，保温第一梯队，内胆防粘涂层 | ≈¥229 | 高端 |
| 6 | Stanley Quencher H2.0 | 1.18L | 全球网红潮流款，大容量吸管杯 | ≈¥319（$45） | 高端 |

- 备选：YETI Rambler（≈¥280，户外耐用）、虎牌 / 乐扣乐扣（200+ 高端带）
- **价格口径**：2026-09 公开评测 / 电商参考价，USD 按 7.1 折算；正式跑批前按实时价校准（写进 `input/context.md`）
- 货架设计原则：覆盖「入门/中/高端」价格带 × 「保温性能/环保/颜值/品牌/容量」差异化卖点，让人格有真实可权衡的空间

## 3. 人格采样（Persona 1M，已导入 ✓）

- 池子：`persona/datasets/matraix-persona-1m`（release/cohorts 已就位）
- 实测可用分层字段（schema 1290 维中的关键字段）：
  - `age_bracket`、`region`、`gender_identity`、`life_stage`
  - `socioeconomic_band`、`demo_household_income`、`demo_employment_status`
  - `economic_motivation`（Cost-sensitive / Value-driven / Premium-seeking / Indifferent）
- **默认方案**：全球人口分层采样 1000 人（`age_bracket × economic_motivation × region` 分层），体现 Persona 1M「世界人口」特色
- **备选方案**：中国市场定向（`region` 筛选 + `economic_motivation` 分层）
- 采样由任务自带 `persona_strategy.json` 定义（dimensionFilters + stratified sampling），命令行 `--filter / --stratify / --seed` 可覆盖

## 4. 选购任务设计（仿现有 price-sensitivity 模板）

参考模板（仓库已有，同类型可直接套）：`application/tasks/survey_price-sensitivity-hasbro-gaming-candy-land`

新建任务：`application/tasks/survey_water-bottle-choice/`

| 文件 | 内容 |
|------|------|
| `task.toml` | type=survey, domain=commerce（同 Hasbro 模板） |
| `instruction.md` | 购物场景说明 + 货架卡片 + 作答要求（仿模板措辞） |
| `input/context.md` | 6 款产品卡：名称 / 容量 / 材质 / 卖点 / 价格 / 参考评分 |
| `input/questionnaire.yaml` | 见下 |
| `persona_strategy.json` | 分层筛选 + sampleSize=1000（pilot 时改 20） |
| `tests/` | verifier：校验 choice 合法、reason 非空 |

问卷（questionnaire.yaml）核心题：
- `q_choice`：单选，7 选项 = 6 款产品 + 「都不买」（购物式强制选择，允许弃购）
- `q_reason`：开放式必填，给 2-3 句理由（模拟真实购买心理）
- `q_price_threshold`：likert，当前价格是否可接受
- `q_feature_priority`：单选，最看重什么（保温性能 / 颜值 / 价格 / 品牌 / 容量 / 环保）
- `q_purchase_likelihood`：likert，真实购买意愿

每人格输出 `survey_result.json`（结构化 JSON），可直接聚合。

## 5. 技术路径（DeepSeek 接入三选一）

| 方案 | 命令 / 配置 | 说明 |
|------|------------|------|
| ① 原生任务（推荐） | `--model-name deepseek/deepseek-chat` + `DEEPSEEK_API_KEY` | LiteLLM 兼容 id，官方文档称其他兼容 id 在设置对应 key 后可用；**pilot 先行验证** |
| ② 文档保证 | `--model-name dashscope/deepseek-v4-pro` + `DASHSCOPE_API_KEY` | 阿里云百炼托管 DeepSeek，在官方支持模型列表内 |
| ③ 混合保底 | 人格用 Persona 1M YAML，Python 直连 DeepSeek OpenAI 兼容接口 | 完全可控，聚合逻辑不变，产物格式对齐 |

**Pilot 命令（20 人，验证解析率 / 成本 / 时长）**：

```bash
export DEEPSEEK_API_KEY="sk-..."
uv run python application/scripts/generate_application_job.py \
  --task application/tasks/survey_water-bottle-choice \
  --execution-mode auto \
  --dataset persona/datasets/matraix-persona-1m \
  --sample-size 20 --seed 42 \
  --model-name deepseek/deepseek-chat
uv run matraix run -c configs/jobs/application-task-job-recipe/<generated>.yaml --max-cost-usd 2
```

**全量（1000 人）**：`--sample-size 1000`，YAML 中 `n_concurrent_trials=10~20` 并发。

## 6. 成本与耗时（估算，以官网实时价为准）

- 每人格上下文约 1.5-2.5k tokens → 1000 人 ≈ 2-2.5M tokens
- DeepSeek-chat 量级：输入约 ¥1-2/M、输出约 ¥2-8/M → **全程预计 ¥5-20**
- 时间：pilot 20 人 <10min；1000 人并发 10-20 → 1-3h
- 成本闸：`--max-cost-usd` 设上限，防止失控

## 7. 聚合与产出

- **市场份额**：6 款 + 「不购买」分布（总览）
- **分群交叉**：按 `age_bracket / economic_motivation / region / socioeconomic_band` 交叉
- **价格敏感度**：选择分布 vs 价格带、「不购买」率、价格阈值分布
- **理由聚类**：LLM/关键词归类（保温性能 / 颜值 / 价格 / 品牌 / 容量 / 环保）
- **人-货匹配矩阵**：哪类人格选哪款
- 交付物：raw CSV/JSON + HTML 仪表盘（ECharts）+ 1 页结论

导出命令：`uv run matraix results <job> --format json,csv -o exports/`，`--group-by age_bracket` 可加分群。

## 8. 里程碑

| 阶段 | 内容 | 预估 |
|------|------|------|
| M1 | smoke + 1 人单跑（验证 DeepSeek 模型解析） | 0.5h |
| M2 | 任务落地（仿 Hasbro 模板）+ 20 人 pilot | 1h |
| M3 | 1000 人全量跑批（并发 + 成本闸） | 1-2h |
| M4 | 导出 + 聚合脚本 + 仪表盘 | 1h |

## 9. 风险与对策

| 风险 | 对策 |
|------|------|
| DeepSeek 模型 id 不被识别 | 按 ①→②→③ 降级，pilot 阶段提前暴露 |
| JSON / verifier 失败 | 重试上限 + 解析率监控（目标 >98%） |
| 人格趋同（模式崩塌，都选最便宜/最贵） | 货架顺序打乱、temperature 0.7、seed 采样、结果与人格属性相关性校验 |
| 价格时效性 | 跑批前校准 `context.md` |
| 模拟 ≠ 真实 | 结论定位为「假设生成」，不做真实市场断言（MatrAIx 官方亦如此声明） |

## 10. 待确认决策

1. **品类**：保温杯（默认）还是换猫爬架 / 其他？设计已品类无关，换品类只需重写 `context.md` 货架
2. **人群口径**：全球分层（默认）vs 中国市场定向？
3. **货架**：6 款是否 OK？是否加入 YETI / 虎牌？
4. **节奏**：先 pilot 20 再全量 1000（默认）？
