# 购物预测实验

[五轮实验统一报告](../index.html)按研究过程覆盖全部已完成实验，包含早期模型、人格、提示和电商数据。本目录原来的 [index.html](index.html) 同步展示完整报告，保留旧入口可用。图表使用本地 ECharts，支持离线切换。

[第五轮完整技术图表](technical-details.html)保留开发集、正式评估、分组、概率校准和诊断视图；[前四轮技术附录](../historical-details.html)保留历史细节。既有评分不修改，本次新增的输入对齐统计分析单独保存方案和结果，未新增模型请求。报告输入清单与校验值见[报告展示核验](报告展示核验.json)。

逐人样本、真实答案、预测和运行失败详情存入忽略目录 `本机运行/`。发布的 JSON 只包含总体及逐题汇总。

从仓库根目录运行 `.venv/bin/python examples/sim-to-real/retail_report.py`，统一生成主报告、旧入口兼容页面与两份技术附录。Python 需 3.10 以上，主项目环境为 3.12；报告生成仅用标准库与聚合结果。阅读版主模板为 `retail_reader_template.html`，历史章节与图表为 `retail_history_template.html`、`retail_history_charts.js`。重构日期为 2026-11-10。

## 冻结与调整记录

- Pew 仅取网络样本。固定 13 个面向所有受访者的问项及原选项，按受访者随机划分 48 人开发、240 人评估和其余统计参照。由最初的按年龄学历配额调整为简单随机抽样，避免人为改变各组份额。评分仍使用原权重，并限定为同一批有效受访者。
- Pew 开发集以六组比较背景、答案形式、选项倒序和附加背景交换。正式四组保留原顺序和主对照。单选校验允许规范的数字字符串。保留修复前的检查点及冻结清单，修复后的运行只重试缺失结果。另做了一次独立的协议探测，探测答卷未入库、未评分。
- 运动鞋按四种原设计分别抽取 12 人开发、60 人评估。为控制单次请求长度，每人从 20 对中固定抽取 8 对，保留原题序、左右位置与属性顺序。第一波背景按作者规则关联。比较基础背景、较完整的人口背景、前置实测态度与概率输出。
- Amazon 以 2022-10-01 为预测时点，目标为 2022 年第四季度。历史输入覆盖 2020 年至预测日前。账户入选仅依赖既有历史。开发 60 个、独立评估 500 个。品类词表从参照账户历史生成，历史先验来自参照账户 2020 和 2021 年第四季度。早期探索发现同季度参照先验违反预测时点限制，已替换并在本机保留旧冻结文件以供审计，旧结果不用于报告。
- Amazon 第一项任务是预测各品类是否购买。价格带、支出结构和同款复购沿用同一时间与账户切分，分别预测每账户的商品单价带分布、品类支出占比、是否至少再买一款历史商品。每个账户等权。价格与支出设无有效记录的类别；复购在本地比较历史与目标季度的商品编号。模型对照比较仅给历史与附加历史频率估计，另外在开发集冻结模型与统计预测的混合权重。

## 续跑入口

从 `examples/sim-to-real` 运行，Python 环境需有 httpx、numpy、pyreadstat，准备运动鞋还需 pandas、pyreadr，拟合统计模型及校准需 scikit-learn。所有真人关联请求固定走内网 Qwen。运行前检查是否已有同一数据库的任务，避免重复请求。

```sh
python retail_pew.py pilot
python retail_pew_score.py pilot
python retail_pew.py formal
python retail_pew_score.py formal
python retail_pew_draw.py
python retail_pew_calibration.py pilot
python retail_pew_calibration.py formal
python retail_amazon.py
python retail_amazon_model.py development
python retail_amazon_score.py development
python retail_amazon_model.py test
python retail_amazon_score.py test
python retail_amazon_mix.py prepare
python retail_amazon_mix.py run development
python retail_amazon_mix.py score development
python retail_amazon_mix.py run test
python retail_amazon_mix.py score test
python retail_amazon_repeat_diagnostics.py
python retail_shoes_prepare.py
python retail_shoes_model.py development
python retail_shoes_score.py development
python retail_shoes_model.py test
python retail_shoes_score.py test
python retail_audit.py
python retail_report.py
```

运动鞋统计模型由独立的 2,785 人拟合。运动鞋单选校准在开发集估计七档预测评分对应的真人评分分布，并锁定同统计模型的组合权重。Pew 校准用开发集上的完整背景统计预测拟合每题截距偏移，并用开发集真实答案拟合一个组合权重。Amazon 补充任务也仅在开发集选择历史基线和组合权重。开发结果用于提出假设。独立样本结论和适用范围已写入优化文档。

## 运行环境与复算细节

- 模型 ID 为 `Qwen/Qwen3.8-27B`，关闭思考，温度 0.7、top_p 1。Pew 和 Amazon 最多输出 768 token，运动鞋最多 1,536 token。每次请求最多尝试三次，逐组保留有效记录及失败原因。
- 执行和主评分环境为 Python 3.12.12、httpx 0.28.1、NumPy 2.5.4、pyreadstat 1.3.7。运动鞋统计评分环境为 Python 3.12.12、pandas 3.0.3、pyreadr 0.5.9、scikit-learn 1.9.1、NumPy 2.5.0。
- 区间以受访者或账户为重抽样单位，使用 2,000 次配对重抽样。运动鞋按原四个设计在组内重抽。校准与组合系数在重抽时保持冻结，因此区间反映评估样本波动。
- `运行核验.json` 检查输入文件哈希、Pew 和运动鞋运行器版本、样本不交叉、Amazon 的预测时点、有效答卷格式、各组完成率和正式评分人数。失败次数来自当前检查点，早期 Pew 格式问题留在本机旧检查点。
- 单项价格带和支出构成每个账户等权。复购用非空商品编号与历史比对。Amazon 品类预测、价格／支出构成、问卷多选项的误差定义各自独立，按相同任务比较。

## 结果文件与研究问题

### 本次补充：运动鞋可见输入对齐

这是对已看过的 240 名评估受访者的事后敏感性分析，不是新独立样本。移除统计方法中的设计标签与设计交互项，输入两款鞋各 10 项公开属性、左右位置，分别加入与模型一致的基础人口背景、补充人口背景和实测态度。仍使用独立的 2,785 名训练受访者，不在评估样本调参。

补充人口背景条件下，模型分布误差 14.79，统计方法 2.16；逐人概率误差为 0.8726 与 0.8253。统计优势保留，但环保材质与缓震的评分增益被估为 0.96 与 0.77 分，低于真人的 1.61 与 1.33 分。属性敏感性仍需单独验收。三种拟合均收敛，原模型分数复算一致；预测数组只存本机运行目录。

[补充方案](shoes-input-parity-protocol.json) · [结果与配对区间](shoes-input-parity-score.json)。从仓库根目录复算：

```sh
uv run --python .venv/bin/python --with pyreadr==0.5.9 --with scikit-learn==1.9.1 --with pandas==3.0.3 --with numpy==2.5.0 python examples/sim-to-real/retail_shoes_input_parity.py
```

### 正式结果索引

| 问题 | 独立评估与证据 |
|---|---|
| 概率输出是否缓解问卷全票，真人背景是否提高准确度 | [Pew 配对与逐题结果](pew-formal-score.json)和[概率校准结果](pew-formal-calibration.json)。选项顺序与附加背景交换见[开发集对照](pew-pilot-score.json) |
| 每个虚拟人仍要选一个答案时，如何保留分歧 | [Pew 抽答敏感性分析](pew-answer-sampling-sensitivity.json)，对同一批预测重复抽答 1,000 次 |
| 运动鞋能否同时保留评分分布与属性敏感度 | 运动鞋评分文件包含七档分布、配对比较和只变单项属性的对照。见[运动鞋独立评估](shoes-test-score.json)和[开发集](shoes-development-score.json) |
| 模型是否提升实际购买预测 | [Amazon 品类预测](amazon-test-score.json)和[消费结构与复购](amazon-mix-test-score.json)，附[复购误差分解](amazon-repeat-diagnostics.json) |
| 哪些做法已通过验证 | [优化文档](../05_优化记录/优化文档.md)，区分群体分布、逐人预测和业务使用边界 |
