# 集中报告目录

从 [主报告](overview.html) 开始。每张对照图旁有对应的证据按钮。[重点报告](overview.html#html-reports)提供四个阅读入口，分别查复验与剩余误差、真人原题、购买记录和项目原始证据。这个清单与[报告中心](index.html)同步。

主报告和四份重点报告各有一个可核对的读题例子。先看真人怎么选、项目怎么估、改后差多少，再展开精确数值、评分方法和出处。逐题页在每道题里也选一个选项带读。

较早的报告、故事版、演示和模板可在[历史归档与全部资料](catalog.html)按名称和格式查找。两篇仅在本机存档的论文网页提供 PMC 在线全文。部分历史页面仍有搬迁前的链接，现用的实验明细和来源见主报告。

| 文件 | 用途 |
|---|---|
| [overview.html](overview.html) | 三张 ECharts 对照图、真人样本、改善区间与采用建议 |
| [bottleneck.html](bottleneck.html) | 发现的问题、已验证的原因、改法、提升和仍待验证的因素 |
| [question-cases.html](question-cases.html) | 按研究展开 9 套历轮题例、末轮食品标签和豆腐实例，也可查其余 6 套历轮研究的逐人评分 |
| [purchase-evidence.html](purchase-evidence.html) | 本人历史数据的 12 组改善区间和同资料比较 |
| [project-evidence.html](project-evidence.html) | 从真人问卷和人物卡的对照入手，下方可核对项目独立审阅原文 |
| [catalog.html](catalog.html) | HTML、Word、Markdown 和 PDF 的可搜索索引 |
| [data/question-cases-v1.json](data/question-cases-v1.json) | 逐题聚合比例和来源哈希，无个体资料 |
| [data/catalog.json](data/catalog.json) | 分类、用途和重点报告来源哈希 |

## 维护

先从 [最终报告生成器](../decision-transfer/src/build_final.py) 更新总报告，再生成集中目录。前台图表内嵌仓库已有的 ECharts，打开文件时无需联网。外部数据和论文链接点击后需要联网。

```sh
.venv/bin/python examples/decision-transfer/src/build_final.py
.venv/bin/python examples/reports/src/build.py
.venv/bin/python examples/decision-transfer/src/verify.py
```

已有聚合案例足够重建页面。需要重新导出时，可在有权限的原机器运行 `.venv/bin/python examples/reports/src/collect_cases.py`。脚本只读取冻结材料，输出聚合比例。历史四组案例和研究均值与已公布结果核对，另五套引用各自冻结的逐题比例。旧评分记录的方案哈希与现存方案文件哈希不同，二者均登记于聚合数据的来源记录。此报告整理使用已完成的配对对照。

购买阶段旧图区间左侧曾被截在零点，且图注误把「误差下降量」写为越低越好。集中版用原聚合结果重绘跨零区间，分别标注误差越低越好与误差下降量越高越好。
