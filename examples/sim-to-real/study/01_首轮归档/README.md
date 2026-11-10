# MatrAIx 真人问卷对照实验

同一批 1,200 条 Persona 1M 合成画像参加三套问卷。A 组只看到共同情境，B 组另看到年龄和学历，C 组再看到四个固定人格字段。三份问卷各自以带官方权重的真人答案为参照。

## 输入目录

原始数据统一从[共享盘数据源总索引](file:///Volumes/%E5%85%83%E5%AE%87%E5%AE%99%E8%81%94%E5%90%88%E5%88%9B%E6%96%B0%E5%AE%9E%E9%AA%8C%E5%AE%A4/%E5%AE%9E%E9%AA%8C%E6%95%B0%E6%8D%AE/MatrAIx%E5%A4%9A%E5%9C%B0%E5%8C%BA%E9%80%89%E5%93%81%E6%BA%90%E6%95%B0%E6%8D%AE/README.md)读取。共享盘挂载位置不同的电脑可设置 `MATRAIX_DATA_ROOT`，指向包含 README.md 的总目录。 首轮调查 ZIP 位于 [00_历史通用问卷](file:///Volumes/%E5%85%83%E5%AE%87%E5%AE%99%E8%81%94%E5%90%88%E5%88%9B%E6%96%B0%E5%AE%9E%E9%AA%8C%E5%AE%A4/%E5%AE%9E%E9%AA%8C%E6%95%B0%E6%8D%AE/MatrAIx%E5%A4%9A%E5%9C%B0%E5%8C%BA%E9%80%89%E5%93%81%E6%BA%90%E6%95%B0%E6%8D%AE/00_%E5%8E%86%E5%8F%B2%E9%80%9A%E7%94%A8%E9%97%AE%E5%8D%B7)。Persona 1M 默认读取 [发行版](file:///Volumes/%E5%85%83%E5%AE%87%E5%AE%99%E8%81%94%E5%90%88%E5%88%9B%E6%96%B0%E5%AE%9E%E9%AA%8C%E5%AE%A4/%E5%AE%9E%E9%AA%8C%E6%95%B0%E6%8D%AE/MatrAIx%E5%A4%9A%E5%9C%B0%E5%8C%BA%E9%80%89%E5%93%81%E6%BA%90%E6%95%B0%E6%8D%AE/09_MatrAIx%E7%94%BB%E5%83%8F/Persona-1M%E5%8F%91%E8%A1%8C%E7%89%88)，也可用 `sample --release <目录>` 指定其他发行版。历史正式运行使用冻结的 DAG 画像，重建这批画像用 `sample-dag`。

- SHED 使用 2025 public use CSV。年龄来自 `ppage`，学历来自 `ppeducat`，使用 `weight`，逐题剔除有插补标记的答案。 [数据及变量字典](https://www.federalreserve.gov/consumerscommunities/shed_data.htm) · [问卷](https://www.federalreserve.gov/publications/2026-supplemental-appendixes-report-economic-well-being-us-households-2025-appendix-a.htm)
- Pew 使用 Wave 168。用 `F_AGECAT`、`F_EDUCCAT2` 和 `WEIGHT_W168`，保留题目显式提供的“不确定”。 [数据](https://www.pewresearch.org/dataset/american-trends-panel-wave-168/) · [问卷](https://www.pewresearch.org/wp-content/uploads/sites/20/2025/07/PI_2025.07.31_Scams_Questionnaire.pdf)
- ANES 使用 May 19, 2026 CSV。选前新招募网络样本以 `V240102a > 0` 定义，用 `V241458x` 和 `V241465x` 分层。该样本为 2,063 人，2,308 是包含 245 份纸质答卷的口径。 [数据与问卷](https://electionstudies.org/data-center/2024-time-series-study/)
- 使用四层匹配，18–64 岁与 65 岁及以上分别交叉本科以下与本科及以上。Pew 公共文件的年龄段无法与原四个年龄段精确对齐。每层抽 300 条正式画像和 3 条互斥的试跑画像。

## 复算命令

从 MatrAIx 仓库根目录运行。使用同一已配置的服务商和具体模型版本完成试跑与正式实验。

```sh
uv sync --locked --python 3.12
uv run --no-sync python examples/sim-to-real/experiment.py --work-dir "$study" reference
uv run --no-sync python examples/sim-to-real/experiment.py --work-dir "$study" sample-dag
uv run --no-sync python examples/sim-to-real/experiment.py --work-dir "$study" pilot --model "$model"
uv run --no-sync python examples/sim-to-real/experiment.py --work-dir "$study" formal --model "$model"
uv run --no-sync python examples/sim-to-real/experiment.py --work-dir "$study" score
```

`pilot/` 包含 108 份技术试跑。正式问卷存入 `formal/`，同配置重跑仅重试失败项。统计按三份调查同步重抽样 B/C 共同完成的画像，A 仅用于总体描述。区间表示模拟抽样波动，以真人调查估计为固定参照。逐题与分组结果在 `results.json`，摘要在 `report.md`。公开题目与统计可能曾被底层模型见过。

## 公开版覆盖审计与备选入口

正式发布的 400,000 条合成画像只有 3 条标为北美。本实验的两个本科及以上分层均没有合格画像。`sample` 会保留 `coverage.json` 并停止。若实验改用 MatrAIx 原生 DAG，可执行 `sample-dag`。该入口在生成前固定地区为北美，从 50,000 个生成候选中使用同样的四层配额取样，保存图文件哈希和抽样参数，另写 `dag-coverage.json`。用该入口得到的结论适用于原生生成器，不覆盖公开 1M 的合成人群子集。

## 本次运行记录

使用现有的官方 Persona 1M 目录核对北美覆盖率。正式模拟使用原生 DAG 在生成前固定北美所得的画像，四层各 300 条。模型通过 DeepSeek 官方 API 的 deepseek-flash 调用。2026-11-09 的官方文档对应 DeepSeek-V4.1-Flash-1017。 [模型版本](https://api-docs.deepseek.com/quick_start/pricing/)

共享盘上的 formal 目录是首次运行检查点。续跑保留已完成记录，最终完整的正式答卷与执行配置以 formal-trials.zip 为准。
