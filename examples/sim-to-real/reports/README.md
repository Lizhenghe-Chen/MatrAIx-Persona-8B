# 实验总报告与可分享证据

**阅读入口：[AI 怎样才能更接近真人选择？](index.html)**。涵盖历史问卷、模型与提示、购物、统计校准、两套家电正式测试，以及两次真实选择的最新筛查。它解释已完成的实验，不发起模型请求。

## 文件用途

| 文件 | 用途 |
|---|---|
| [index.html](index.html) | 可单独拷贝、离线打开的最终报告；包括柱状图、区间图和 13 道题的分布切换 |
| [evidence.json](evidence.json) | 从冻结评分抽取的聚合数字与来源 SHA-256；没有逐人编号、完整请求或答案关联 |
| [build.py](build.py) | 抽取来源、验证分布和数值关系、生成报告；不调用模型 |
| [report.html.tmpl](report.html.tmpl) | 可维护的中文说明模板 |
| [style.css](style.css)、[charts.js](charts.js) | 版式与交互，生成时内嵌，阅读不依赖外网 |
| [verify.py](verify.py)、[smoke.cjs](smoke.cjs) | 来源及链接核验、实际浏览器交互与移动版检查 |

## 离线重建

在 MatrAIx 仓库根目录运行，Python 3.12 标准库即可。默认只用随 Git 的聚合证据，不需要原始数据、密钥或共享盘。

```sh
python3 examples/sim-to-real/reports/build.py
python3 examples/sim-to-real/reports/verify.py
node examples/sim-to-real/reports/smoke.cjs
```

`smoke.cjs` 使用 Node.js 22+ 和本机 Chrome；非默认路径可设 `CHROME_BIN`。截图只写临时目录，不进入实验档案。

仅在要从冻结评分重新抽取时使用 `build.py --collect`。这还需要本机 `~/.local/share/matraix-decision-lab/analysis-v1/individual-{dryer,swiss}.json`；它们约 82 MB 的原分析包保留原位。公开导出的 `local-analysis/` 来源名称是相对标识，不是可独立复算逐人评分的替代文件。`verify.py --local-sources` 会核验这些本机源文件。

## 图表怎么来

页面里所有图表都由**已评分的本地文件**生成，不手填数字：

| 图表 | 数据来源 | 生成方式 |
|---|---|---|
| 前段条形图、区间图、分布条 | `evidence.json` | `build.py` 内联 SVG（`charts.js`） |
| clean-v1 的五个图（相对等分改善、题卡散点、构成环图、评分分布、差异保留率） | `decision_lab/reports/cross-study-v1/clean-v1-diagnostics.json` | ECharts（`charts_clean.js`） |

`clean-v1-diagnostics.json` 由 `PYTHONPATH=examples/sim-to-real .venv/bin/python -m decision_lab.cross_study.clean_diagnostics` 从本机检查点重算。ECharts 已本地化在 `vendor/echarts.min.js`，并在构建时**内联进 `index.html`**——页面仍是单文件、离线可开、零外部请求（`smoke.cjs` 会断言这一点）。改动图表脚本后必须重跑 `node smoke.cjs`。

## 内容维护规则

1. 数字从已评分结果抽取，保留哈希；不要以新调用覆盖旧结果。
2. 文字中的数值、范围和前后方向须与聚合证据一致。发布前检查逐题分布、全部均值、各项区间及反例。
3. 分布误差（百分点）、属性比例误差（百分点）与 Brier（个人概率误差分数）分开。只在同一实验内部比较改前改后。
4. 同一研究反复使用、三次模型重复、开发集探索，都不计成新的独立研究。真人统计多用过训练答案的优势要说明。
5. 模型、提示、背景、输出方式的分别有效，不等于它们拼起来的组合已经被整体验证。
6. 暂未支持的合成人格与两次选择输入仍保留证据。不得删掉失败实验以制造一致成功印象。

来源索引见报告末尾；全量历史见 [study](../study/README.md)，新框架见 [decision_lab](../decision_lab/README.md)，持续采用建议见 [优化文档](../study/05_优化记录/优化文档.md)。
