# MatrAIx 真人对照实验档案

[五轮实验统一报告](index.html)面向不同背景的读者，按研究过程串联合成人格、三模型对比、提示与背景优化、电商选品复验、概率与实际购买预测。九份真实数据、各轮平均指标、前四轮逐题工作台和第五轮逐题图均在同页；新增的运动鞋可见输入对齐分析明确标为事后补充。[调研与决策](调研与决策.md)记录研究过程及未纳入评分的候选数据。[档案导航](00_导航/从这里开始.md)按轮次链接评分、方案、图表和数据。

[购物与选品数据候选清单](07_购物数据候选/index.html)保留 2026 年 11 月 10 日调研时的数据来源、下载状态和适用边界。此后运动鞋、Pew Wave 13 和 Amazon 已用于第五轮，实验结论以统一报告为准。较小的公开数据与问卷现已纳入 Git，许可依据见[来源与许可](07_购物数据候选/来源与许可/README.md)。[文件归档说明](00_导航/文件归档说明.md)说明保留位置、体积限制、原始文件恢复和换电脑后的复算范围；[完整文件清单](00_导航/文件清单.json)逐项记录大小、校验值与是否随 Git 保存。

原[购物预测阅读版入口](08_购物预测/index.html)现展示同一份五轮统一报告，保留旧链接可用。主入口为本目录的 `index.html`。详细诊断分别保留为[前四轮技术附录](historical-details.html)与[第五轮技术图表](08_购物预测/technical-details.html)，运行口径见[购物预测实验记录](08_购物预测/README.md)。

## 数据保存范围

| 随 Git 保存 | 在项目本机工作副本保存 |
|---|---|
| 代码、模型配置、样本生成记录、汇总指标、报告、输入及输出哈希、执行日志 | 三份 Pew 原始 ZIP、含真人伪编号的样本索引和模型答卷、SQLite 检查点 |
| 美联储 SHED、ANES 公共使用版本、Bankert 商品选择公开数据及作者 CC0 原始数据、Purdue 公开选择数据 | Bankert 的出版方问卷补充文件，以及本机共享盘路径 |
| 两项纯合成画像实验的模拟答卷 | Persona 1M 多 GB 分片在共享盘，本项目保存发行清单，路径见本机 `数据/persona-1m-path.txt` |
| 运动鞋、T 恤、循环产品、无人机配送公开清洗表，Amazon 公开受访者表，相关问卷及加拿大问卷和代码本 | Amazon 购买记录压缩表、加拿大完整包、运动鞋完整复制包；均超过本次普通 Git 单文件 20 MiB 上限 |

Pew ATP 有独立的使用条款，官方下载需要账户。复算时取得相应版本并核对清单。真人逐人关联材料按原实验约定保留在本机。同批实验的独立共享盘来源也保留作为来源副本。[Pew 数据获取与条款](https://www.pewresearch.org/short-reads/2021/10/22/how-to-access-pew-research-center-survey-data/) · [ANES 使用条款](https://electionstudies.org/data-center/) · [Bankert 作者数据](https://doi.org/10.7910/DVN/3TGWGG) · [Purdue 作者数据](https://doi.org/10.17632/4z748jnnjs.2)

## 报告和复算

以下命令从仓库根目录执行，使用 Python 3.12。总报告生成只读取聚合结果，离线可运行。

```sh
study="$PWD/examples/sim-to-real/study"
.venv/bin/python "$study/build_report.py"
```

| 实验 | 评分文件与重算方式 |
|---|---|
| 首轮 Flash | 把 [冻结画像](01_首轮归档/cohort.json) 和 [真人参照](01_首轮归档/reference.json) 复制到一个临时实验目录，并在该目录解压 [正式答卷](01_首轮归档/formal-trials.zip) 得到 `formal/`。运行 `experiment.py --work-dir <临时实验目录> score`。 |
| 三模型与背景优化 | 在数据根目录准备两轮清单指定的数据和本机检查点。运行 `optimize.py models score --study "$study"` 或 `optimize.py profiles score --study "$study"`。 |
| 北美电商选品 | 使用 `pyreadstat==1.3.7` 读 SPSS，数据和检查点见[电商索引](06_北美电商选品/数据索引.md)。运行 `shopping.py score "$study/06_北美电商选品"`。 |
| 购物预测及补充分析 | [第五轮记录](08_购物预测/README.md)列出各项开发、正式评分、校准和运动鞋输入对齐复算命令。公开汇总随 Git，逐人运行材料另在本机。 |

三份 Pew 文件分别放在 `数据/pew.zip`（Wave 168）、`06_北美电商选品/数据/pew.zip`（Wave 111）和 `07_购物数据候选/本机数据/Pew_Wave13/American-Trends-Panel-Wave-13-Dec-15.zip`（Wave 13）。源调查文件和历史答卷的哈希见各轮 `manifest.json` 或 `output-sha256.json`。本机材料的路径也是重算程序读取的路径，Git 会忽略这些文件。
