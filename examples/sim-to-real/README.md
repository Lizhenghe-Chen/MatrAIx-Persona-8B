# MatrAIx 真人问卷对照实验

[通俗故事版报告](study/index.html) · [六轮完整证据与逐题图表](study/evidence.html) · [实验档案与复算](study/README.md) · [文件归档说明](study/00_导航/文件归档说明.md)

第一次阅读请打开 `study/index.html`：从真人先答、模型答偏，讲到优化前后和现在怎么用。精确数字、全部六轮和逐题交互保存在 `study/evidence.html`，两页可以互相跳转。旧的 `retail_reader_template.html` 地址会自动跳转；旧章节书签仍可进入完整证据。`.tmpl` 文件是生成用的模板，不作为阅读页面。

这里集中保存本次研究的全部代码和档案。报告串联合成人格、三模型对比、提示与背景优化、电商选品复验、购物概率与实际购买预测；已完成与待研究的数据分别标注。小型公开资料、汇总结果和离线图表随 Git 保存，大型源包和真人关联运行文件保留本机并登记校验值。

## 代码与报告入口

| 任务 | 代码 | 档案 |
|---|---|---|
| 首轮合成人格对照 | `experiment.py`、`instruments.py` | `study/01_首轮归档/` |
| 比模型、提示及背景 | `optimize*.py` | `study/02_模型对比/`、`03_提示与背景/` |
| 北美商品选择、拒买及网购 | `shopping*.py` | `study/06_北美电商选品/` |
| Pew 购物预测、运动鞋、Amazon 真实购买 | `retail_pew*.py`、`retail_shoes*.py`、`retail_amazon*.py` | `study/08_购物预测/` |
| 匹配、模型与商品输出方式三次复验 | `revalidation*.py`、`revalidation_charts.js` | [第六轮说明](study/10_匹配与商品复验/README.md)，合成答卷可仅凭Git归档复算 |
| 复建全部报告 | `retail_report.py`；故事页由 `retail_story_report.py`、`retail_story_template.html.tmpl` 和 `retail_story_charts.js` 生成，完整证据与历史模板以 `retail_reader`、`retail_history` 开头 | `study/index.html` 为故事入口，`study/evidence.html` 保留逐题证据；旧链接继续可用 |
| 实验运行与归档核验 | `retail_audit.py`、`archive_inventory.py` | `study/08_购物预测/运行核验.json`、`study/00_导航/文件清单.json` |

报告重建只需 Python 3.12 标准库与 Git 中的聚合结果：

```sh
python3.12 examples/sim-to-real/retail_report.py
python3.12 examples/sim-to-real/archive_inventory.py check
```

交互图表检查用 Node.js 22 以上和 Chrome：`node examples/sim-to-real/report_smoke_check.cjs`。它会检查全部题目切换、汇总表、22个历史图表与8个复验图表，以及桌面／手机布局，截图输出到临时目录；非 macOS 可通过 `CHROME_BIN` 指定浏览器程序。

完整运行环境、各轮评分与外部文件恢复方法见[档案说明](study/README.md)。下面保留首轮实验的独立复算说明。

首轮用 MatrAIx 原生生成规则抽取同一批 1,200 条北美合成画像，参加三套问卷。A 组只看到共同情境，B 组另看到年龄和学历，C 组再看到四个固定人格字段。三份问卷各自以带官方权重的真人答案为参照。

## 首轮输入目录

在同一个实验目录下准备 `input/shed.zip`、`input/pew.zip` 和 `input/anes.zip`，每个 ZIP 保留官方 CSV。把 Persona 1M 的正式发布目录写入 `input/persona-1m-path.txt`，或在抽样时传入 `--release`。程序校验全部十个分片的 SHA-256 和总行数。真人逐人数据只在本地统计阶段读取，模型请求不包含这些数据。

- SHED 使用 2025 public use CSV。年龄来自 `ppage`，学历来自 `ppeducat`，使用 `weight`，逐题剔除有插补标记的答案。 [数据及变量字典](https://www.federalreserve.gov/consumerscommunities/shed_data.htm) · [问卷](https://www.federalreserve.gov/publications/2026-supplemental-appendixes-report-economic-well-being-us-households-2025-appendix-a.htm)
- Pew 使用 Wave 168。用 `F_AGECAT`、`F_EDUCCAT2` 和 `WEIGHT_W168`，保留题目显式提供的“不确定”。 [数据](https://www.pewresearch.org/dataset/american-trends-panel-wave-168/) · [问卷](https://www.pewresearch.org/wp-content/uploads/sites/20/2025/07/PI_2025.07.31_Scams_Questionnaire.pdf)
- ANES 使用 May 19, 2026 CSV。选前新招募网络样本以 `V240102a > 0` 定义，用 `V241458x` 和 `V241465x` 分层。该样本为 2,063 人，2,308 是包含 245 份纸质答卷的口径。 [数据与问卷](https://electionstudies.org/data-center/2024-time-series-study/)
- 使用四层匹配，18–64 岁与 65 岁及以上分别交叉本科以下与本科及以上。Pew 公共文件的年龄段无法与原四个年龄段精确对齐。每层抽 300 条正式画像和 3 条互斥的试跑画像。

## 复算命令

从 MatrAIx 仓库根目录运行。使用同一已配置的服务商和具体模型版本完成试跑与正式实验。

```sh
uv sync --locked --python 3.12
uv run --no-sync python examples/sim-to-real/experiment.py --work-dir "$study" reference
uv run --no-sync python examples/sim-to-real/experiment.py --work-dir "$study" sample
uv run --no-sync python examples/sim-to-real/experiment.py --work-dir "$study" pilot --model "$model"
uv run --no-sync python examples/sim-to-real/experiment.py --work-dir "$study" formal --model "$model"
uv run --no-sync python examples/sim-to-real/experiment.py --work-dir "$study" score
```

`pilot/` 包含 108 份技术试跑。正式问卷存入 `formal/`，同配置重跑仅重试失败项。统计按三份调查同步重抽样 B/C 共同完成的画像，A 仅用于总体描述。区间表示模拟抽样波动，以真人调查估计为固定参照。逐题与分组结果在 `results.json`，摘要在 `report.md`。公开题目与统计可能曾被底层模型见过。

## 公开版覆盖审计与备选入口

正式发布的 400,000 条合成画像只有 3 条标为北美。本实验的两个本科及以上分层均没有合格画像。`sample` 会保留 `coverage.json` 并停止。若实验改用 MatrAIx 原生 DAG，可执行 `sample-dag`。该入口在生成前固定地区为北美，从 50,000 个生成候选中使用同样的四层配额取样，保存图文件哈希和抽样参数，另写 `dag-coverage.json`。用该入口得到的结论适用于原生生成器，不覆盖公开 1M 的合成人群子集。
