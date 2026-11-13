# 报告目录

两个页面，同一份冻结数据，用途不同：

| 文件 | 读者 | 内容 |
|---|---|---|
| [story.html](story.html) | 领导、非技术读者 | 叙事版：一个真实场景进、同一个场景出；三轮排除、真实原因、可交付方案、外部验证、诚实边界 |
| [index.html](index.html) | 要核对数字的人 | 技术版：逐套明细、95% 区间、13 道题的分布切换、冻结证据 |
| [cards.html](cards.html) | 要逐题看分布的人 | 两级抽屉：研究 → 题目。展开即三色分组柱状图（真人 / 原版 / 优化），收起时每道题带迷你分布条 |

两页的数字都由同一批 `decision_lab/reports/cross-study-v1/*.json` 填入，改一处必须同时重建两页；
`verify.py` 会逐条比对页面文字与冻结数据的一致性。都不是手填数字。

## 文件用途

| 文件 | 用途 |
|---|---|
| [story.html](story.html) · [index.html](index.html) | 两个可单独拷贝、离线打开的页面；图表全部内联，零外部请求 |
| [evidence.json](evidence.json) | 从冻结评分抽取的聚合数字与来源 SHA-256；没有逐人编号、完整请求或答案关联 |
| [build.py](build.py) · [build_story.py](build_story.py) · [build_cards.py](build_cards.py) | 分别生成技术版、故事版、逐题版；不调用模型 |
| [notes.py](notes.py) | 三页共用的一段说明：六套联合分析/打分任务为何没有逐题分布，以及“至少 20 人”门槛的抽样噪底（固定种子实算） |
| [report.html.tmpl](report.html.tmpl) | 可维护的中文说明模板 |
| [style.css](style.css)、[charts.js](charts.js)、[charts_clean.js](charts_clean.js)、[charts_story.js](charts_story.js) | 版式与图表，生成时内嵌，阅读不依赖外网 |
| [verify.py](verify.py)、[smoke.cjs](smoke.cjs)、[smoke_story.cjs](smoke_story.cjs)、[smoke_cards.cjs](smoke_cards.cjs) | 来源及链接核验、三页的浏览器交互与移动版检查 |

## 离线重建

在 MatrAIx 仓库根目录运行，Python 3.12 标准库即可。默认只用随 Git 的聚合证据，不需要原始数据、密钥或共享盘。

```sh
python3 examples/sim-to-real/reports/build.py
python3 examples/sim-to-real/reports/build_story.py
python3 examples/sim-to-real/reports/verify.py
node examples/sim-to-real/reports/smoke.cjs
node examples/sim-to-real/reports/smoke_story.cjs
node examples/sim-to-real/reports/smoke_cards.cjs
```

`smoke.cjs` 使用 Node.js 22+ 和本机 Chrome；非默认路径可设 `CHROME_BIN`。截图只写临时目录，不进入实验档案。

仅在要从冻结评分重新抽取时使用 `build.py --collect`。这还需要本机 `~/.local/share/matraix-decision-lab/analysis-v1/individual-{dryer,swiss}.json`；它们约 82 MB 的原分析包保留原位。公开导出的 `local-analysis/` 来源名称是相对标识，不是可独立复算逐人评分的替代文件。`verify.py --local-sources` 会核验这些本机源文件。

## 逐题页的颜色规则

`cards.html` 有两类数字，刻意不用同一套颜色：

| 数字 | 规则 |
|---|---|
| 误差 TV（越低越好，有客观好坏） | **赢家青绿** + `▼`，输家灰色；差异 < 2 个百分点标 `≈`。逐题明细里不用红色，避免整页红噪音 |
| 结论标签（优化更准 / 原版更准） | **优化更准＝绿**，**原版更准＝红**。这是唯一用红绿表好坏的地方 |
| 「原版−真人」逐选项偏差 | **暖色＝高估，冷色＝低估**，只表示方向，不表示好坏 |

2 个百分点的门槛沿用项目预注册的判定标准。颜色只是辅助：`▼ / ≈ / + / −` 与文字标签本身就是信息，灰度打印或色觉障碍下仍可读。

## 图表怎么来

页面里所有图表都由**已评分的本地文件**生成，不手填数字：

| 图表 | 数据来源 | 生成方式 |
|---|---|---|
| 前段条形图、区间图、分布条 | `evidence.json` | `build.py` 内联 SVG（`charts.js`） |
| clean-v1 的五个图（相对等分改善、题卡散点、构成环图、评分分布、差异保留率） | `decision_lab/reports/cross-study-v1/clean-v1-diagnostics.json` | ECharts（`charts_clean.js`） |
| 故事版三张图（AI vs 查表、实测交叉点、外部验证） | `cluster-summary.json`、`blend-qwen.json`、`external-v2-results.json` | ECharts（`charts_story.js`） |

`clean-v1-diagnostics.json` 由 `PYTHONPATH=examples/sim-to-real .venv/bin/python -m decision_lab.cross_study.clean_diagnostics` 从本机检查点重算。ECharts 已本地化在 `vendor/echarts.min.js`，并在构建时**内联进 `index.html`**——页面仍是单文件、离线可开、零外部请求（`smoke.cjs` 会断言这一点）。改动图表脚本后必须重跑 `node smoke.cjs`。

## 内容维护规则

1. 数字从已评分结果抽取，保留哈希；不要以新调用覆盖旧结果。
2. 文字中的数值、范围和前后方向须与聚合证据一致。发布前检查逐题分布、全部均值、各项区间及反例。
3. 分布误差（百分点）、属性比例误差（百分点）与 Brier（个人概率误差分数）分开。只在同一实验内部比较改前改后。
4. 同一研究反复使用、三次模型重复、开发集探索，都不计成新的独立研究。真人统计多用过训练答案的优势要说明。
5. 模型、提示、背景、输出方式的分别有效，不等于它们拼起来的组合已经被整体验证。
6. 暂未支持的合成人格与两次选择输入仍保留证据。不得删掉失败实验以制造一致成功印象。

来源索引见报告末尾；全量历史见 [study](../study/README.md)，当前框架见 [decision_lab](../decision_lab/README.md)，持续采用建议见 [推荐配置](../decision_lab/docs/推荐配置.md)。
