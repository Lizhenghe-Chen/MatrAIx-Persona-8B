# 决策预测实验：真实记录能帮多少

**一句话结论：能稳定带来收益的只有一条——用本人的真实选择或购买记录去更新群体统计。**
12 组留出比较中 8 组的改善区间完全高于零，最高一项把误差从 0.621 降到 0.290。
同一份信息交给语言模型，它反而比统计更新差 0.10～0.13。

先看 [**集中报告目录**](../reports/index.html)或[最终对照报告](../reports/overview.html)。正文的三张 ECharts 柱状图比较方案合用、保留概率和试答加 AI，历轮证据和来源可在附录展开。实际题卡、条件和各组答案分布见[原题对照](../reports/question-cases.html)。

本目录此前的 [阶段总结（离线 HTML）](reports/summary.html) 集中讨论本人真实记录。

## 三个已经站得住的发现

| 发现 | 数字 | 证据强度 |
|---|---|---|
| 两份真实收银记录能大幅改善品牌预测 | 酸奶 0.621 → 0.290（−53%）、番茄酱 0.579 → 0.436（−25%） | 区间高于零 |
| 问卷里两次同类选择也能改善 | 啤酒 −18.1%、奶酪 −10.9%、德国包装 −4.0% | 区间高于零 |
| 把「买不买」与「买哪款」分开算更准 | 超市酸奶 −12.2%、液态奶 −11.0%、意面酱 −3.2% | 区间高于零 |

## 三类效果有限的做法

- **让模型读人格描述**：同样的群体预测和本人记录，Qwen 比统计更新差 0.126（啤酒）与 0.102（奶酪），混入 25% 也变差。
- **跨话题借用资料**：同一组题内部有 +0.02～0.06 的迁移，换到别的话题只剩 +0.006，换到行为题是 −0.15。
- **在几乎没有分歧的题目上做实验**：瑞士四臂那轮 90.3% 的答案集中在同一选项，四个方案全部输给一句「按比例猜」（0.179 vs 最好的 0.272）。该轮记录为设计失误，不作为资料有效性的证据。

## 目录里有什么

| 位置 | 内容 | 是否维护 |
|---|---|---|
| [reports/final.html](reports/final.html) | 全项目最终报告与独立复验 | 是 |
| [docs/末轮复验规程.md](docs/末轮复验规程.md) · [data/final-evidence-v1.json](data/final-evidence-v1.json) | 末轮方案、数据来源与哈希，可用公开汇总结果离线重建 HTML | 是 |
| [data/final-combined-v1.json](data/final-combined-v1.json) | 豆腐组合的事后补算、配对区间及来源 | 是 |
| [reports/summary.html](reports/summary.html) | 本阶段历史总结 | 是 |
| [data/conclusions-v1.json](data/conclusions-v1.json) | 冻结结论：每项比较的基线、改善、区间与源文件哈希 | 是 |
| [docs/核心研究方案.md](docs/核心研究方案.md) | 研究设计与四组比较的原始定义 | 是 |
| [docs/执行规程.md](docs/执行规程.md) | 变量控制、调用上限、统计门槛 | 是 |
| [docs/准入进度.md](docs/准入进度.md) | 两套数据的逐字段准入结论（瑞士通过、美国未通过） | 是 |
| [docs/旧证据使用注意事项.md](docs/旧证据使用注意事项.md) | 旧实验哪些结论不能用、为什么 | 是 |
| [data/](data/) | 结论所依赖的 7 份结果数据 + 准入记录 + 原生模板 | 是 |
| [src/](src/) | 实验、评分和报告生成脚本 | 是 |
| [tests/](tests/) | 26 项不变量测试 | 是 |
| [archive/](archive/) | 旧实验冻结清单 + [2026-11-13 探索批次索引](archive/2026-11-13-exploration/INDEX.md)（84 份过程文档，一句话结论） | 否，只读 |

## 代码：哪些还能用

| 脚本 | 作用 |
|---|---|
| `swiss.py` | 瑞士六品类数据加载、29 项事实渲染、逐人关联校验 |
| `sample.py` | 分层抽样、留出品类、供体匹配（种子 20261109） |
| `personas.py` | 原生人格渲染快照与人口匹配 |
| `payloads.py` | 各实验臂的模型输入构造 |
| `protocol.py` | 请求构造与响应解析（含预测指令） |
| `probabilities.py` | 概率合法性校验 |
| `freeze_inputs.py` | 冻结请求、答案与人员，做泄漏检查 |
| `run.py` | 只允许已批准端点，硬上限，成功不重发 |
| `score.py` | 逐人 Brier、配对重抽样区间、技术摘要 |
| `references.py` | 留一人边际与仅属性统计参照 |
| `admission.py` | 重算准入证据 |
| `diagnostics.py` | 事后诊断（模型是否随资料变动） |
| `freeze.py` | 旧实验冻结清单核验 |
| `check_protocol.py` | 离线请求构造冒烟检查 |
| `build_summary.py` | 生成总报告与冻结结论 |
| `final_inputs.py`、`final_run.py`、`final_score.py` | 冻结末轮输入、执行请求及离线评分 |
| `final_combined.py`、`build_final.py` | 用冻结答卷复算两个方法的组合效果，生成最终报告 |
| `verify.py` | 验收：隔离、哈希、报告链接、冻结数字一致性 |

## 怎么跑

```sh
# 验收（不调用模型）
.venv/bin/python -m unittest discover -s examples/decision-transfer/tests
.venv/bin/python examples/decision-transfer/src/check_protocol.py
.venv/bin/python examples/decision-transfer/src/verify.py

# 用 Git 中的汇总结果重建最终报告与报告中心
.venv/bin/python examples/decision-transfer/src/build_final.py
.venv/bin/python examples/reports/src/build.py
```

正式运行需要先有冻结的请求与人员划分（`freeze_inputs.py`），再按 `run.py --model pro --set formal` 调用；
逐人材料、答案与调用台账只放在 `~/.local/share/matraix-decision-transfer/work/`，不进 Git。

## 阶段研究的适用范围

- 上述本人记录的阶段结果来自数据内部留出；后续正式复验的范围见[最终对照报告](../reports/overview.html)。
- 两套收银数据没有可核验的时间戳，测的是「同一户的另一笔购买」。
- 只覆盖**已有历史记录**的人；新客、换购、跨品类都未验证。
- 各自数据集的百分比不能横向排名，只能看量级。

完整控制条件、单位和区间见[购买预测阶段报告](../reports/purchase-evidence.html)。
