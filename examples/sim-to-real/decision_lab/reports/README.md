# 生成结果

本目录存放由已冻结检查点复算出的评分与离线报告，不是私有原始材料。

| 文件 | 来源 |
|---|---|
| `individual-<study>.json` | `python -m decision_lab.evaluation.evaluate_study <研究目录> --kind <dryer\|swiss> --calibration <研究目录>/calibration-v1.json` |
| `population-<study>.json` | `python -m decision_lab.evaluation.evaluate_population <研究目录> --kind <dryer\|swiss>` |
| `adoption-summary.json` | `python -m decision_lab.reporting.adoption_summary <个体评分…>` |
| `individual-<study>.html` | `python -m decision_lab.reporting.study_report` |
| `population-<study>.html` | `python -m decision_lab.reporting.population_report` |
| `aggregate.html` | `python -m decision_lab.reporting.aggregate_report` |

评分命令只读取本机检查点与冻结参数，不调用模型、不产生费用。已存在的文件不会被覆盖：重算时换新文件名，保留旧的冻结成绩。

这里只放可公开的汇总数字。逐人答卷、请求原文和逐人关联仍留在 `~/.local/share/matraix-decision-lab/`，不进入本仓库。
