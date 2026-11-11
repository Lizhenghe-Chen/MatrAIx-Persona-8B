# 生成结果

**面向普通读者，优先打开 [通俗图解报告 reader.html](reader.html)**：结论、实验故事、全部方法平均值、全部个体测试商品组合的交互分布与分群图。由 `decision_lab.reporting.reader_report` 从最终评分文件生成，不调用模型；原页面保留作技术参考。

本目录存放由已冻结检查点复算出的评分与离线报告，以及最终核验记录。不是私有原始材料。

| 文件 | 来源 |
|---|---|
| `aggregate.html` | `python -m decision_lab.reporting.aggregate_report`，跨两项研究的唯一汇总页 |
| `individual-<study>.html` | `python -m decision_lab.reporting.study_report`（`--max-cards 120`） |
| `population-<study>.html` | `python -m decision_lab.reporting.population_report`（`--max-cards 120`） |
| `<study>-verification.json` | `python -m decision_lab.evaluation.execution_snapshot`，逐条重算请求哈希、完整性、服务身份与完成度 |
| `adoption-summary.json` | `python -m decision_lab.reporting.adoption_summary`，按对照区分是否达到门槛 |

评分命令只读本机检查点与冻结参数，不调用模型、不产生费用。已存在的文件不会被覆盖：重算时换新文件名。

**完整评分 JSON 不在这里。** 它们含逐卡明细，瑞士个体文件约 51 MB，加总约 82 MB，放在
`/Users/bunnychen/.local/share/matraix-decision-lab/analysis-v1/`，可用上面的命令几秒内重算：

```sh
python -m decision_lab.evaluation.evaluate_study <研究目录> --kind <dryer|swiss> \
  --calibration <研究目录>/calibration-v1.json --output individual-<study>.json
python -m decision_lab.evaluation.evaluate_population <研究目录> --kind <dryer|swiss> \
  --output population-<study>.json
```

逐题卡片图默认展示每组真人样本量最大的 120 个商品组合；完整分组数字在评分 JSON 中，页面会说明省略了多少。
逐人答卷、请求原文和逐人关联仍留在私有目录，不进入本仓库。
