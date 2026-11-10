# 新一轮决策模拟实验

本目录是与历史实验隔离的新实现。**目前是数据入场审查和框架基础阶段，尚未完成模型执行、校准、正式评分和报告模块；没有新实验结果。** 不把历史成绩并入本轮。

固定 DeepSeek Pro；真人实测与合成人群分轨，冷启动与少量数据校准分别验收。匿名背景可按用户授权发送官方云端，但每套数据仍须完成来源许可和字段白名单审查。

## 已可用的入口

从 `examples/sim-to-real` 运行：

```sh
python -m decision_lab check --input prepared-study.json
python -m decision_lab freeze --input prepared-study.json --output frozen.json
python -m decision_lab verify --input archive.json
python -m unittest decision_lab.test_core
```

`score` 已支持本地概率评分；`run`、`report` 当前明确返回未实现，不会生成模拟成绩。`freeze` 拒绝覆盖已有划分，且要求五项审查全部通过。未通过审查不能以演示数据代替正式实验。

标准化输入的每条记录包含 person（仅本地）、task、stratum、question、options、context、background、answer（仅评分侧）。background 必须由数据适配器按核准映射产生，不能将原始记录直接送入API。request_payload 只构造明确允许的字段；字段名检查只是附加防护，不能替代内容与来源审查。

默认按人划分60%训练、20%开发、20%测试，固定种子20261109；同一人的重复任务不可分离。过小分层明确报错，需在冻结前重新设计，不自动删除受访者。

## 下一道关口

1. 根据 `source-audit.json` 核对四套候选的题面、背景测量时间、缺失编码、权重与实际备选集。
2. 重建作者描述统计并审查云端用途许可，生成逐套数据卡。
3. 冻结历史开发题、诊断配置及新研究留出方案，再实现统计参照和模型试跑。
4. 完成运行/校准/评分/报告模块及费用估计后才能正式执行。

研究采用标准仍为用户批准计划：Brier相对改善至少2%，或分布误差下降至少2个百分点，配对95%区间高于零；两项标准分别使用。跨研究不能把同一研究的国家当作独立复现。每单元完成率至少98%，失败不能补默认答案。

依赖：Python3.12；源格式审查使用pandas、openpyxl、pyreadstat；后续统计模型使用scipy、scikit-learn。原始文件只读，不运行Excel宏或作者脚本。

评分模块要求显式的语义一致题组，不允许把随机展示的A/B直接当成跨选择卡的同一选项。按人先平均后使用调查权重；配对重抽样按受访者及分层进行。正式缺失分析、跨研究汇总和采用判定仍待接入。
