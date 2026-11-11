# 新一轮决策模拟实验

> **2026-11-11 用户要求停止并交接：四条运行均已安全停止。接手请先读[交接先读](交接先读.md)和[状态快照](specs/freezes/交接状态快照.json)。以下实施记录中的“运行中”是停止前历史状态，不代表现在仍在调用。**

本目录是与历史实验隔离的新实现。**当前两项已准入研究（四国烘干机、瑞士家电）正在执行正式调用；开发结果与稳定性诊断已有记录，完整测试效果尚未发布。** 不把历史成绩并入本轮。

先读[进度与交付核对](docs/进度与交付核对.md)了解哪些工作已完成，再读[数据审查发现](docs/数据审查发现.md)了解入场条件与限制。本文后半部分按模块记录实施依据，早期技术试跑不是正式效果结论。

固定 DeepSeek Pro；真人实测与合成人群分轨，冷启动与少量数据校准分别验收。匿名背景可按用户授权发送官方云端，但每套数据仍须完成来源许可和字段白名单审查。

复算、环境版本和模块复用见[复算与复用指南](docs/复算与复用指南.md)。生成报告不需要重新调用模型。

## 目录结构

根目录只保留可直接 `python -m decision_lab.<模块>` 调用的运行内核、研究适配器、评分与报告模块；冻结材料、文档、测试和生成结果各自归入子目录。

| 位置 | 内容 |
|---|---|
| `README.md`、`交接先读.md` | 模块实施记录与当前状态入口；接手先读后者 |
| `docs/` | 进度核对、复算指南、数据审查、准入决定、证据对照、阶段交接 |
| `specs/formal/` | 正式运行的冻结协议、清单、模型配置与服务身份 |
| `specs/pilots/` | 技术试跑与预检的协议和结果 |
| `specs/freezes/` | 开发选参冻结、单元完整性核验、稳定性结果、交接快照 |
| `specs/audits/` | 数据来源、许可、逐人还原、人格覆盖等审查记录 |
| `reports/` | 生成的个体/群体评分 JSON 与离线 HTML 报告 |
| `tests/` | 全部离线测试；`python -m unittest discover -s examples/sim-to-real/decision_lab -t examples/sim-to-real` 会自动发现 |
| 根目录 `*.py` | 运行内核（`core`、`runner`、`provider`、`checkpoint`）、研究适配器、评分与报告模块 |

新增文件按上表归位，不要放回根目录。

## 已可用的入口

从 `examples/sim-to-real` 运行：

```sh
python -m decision_lab check --input prepared-study.json
python -m decision_lab freeze --input prepared-study.json --config frozen-config.json --output frozen.json
python -m decision_lab verify --input archive.json
python -m unittest decision_lab.test_core
```

`score` 已支持本地概率评分；`run` 已接入冻结配置与SQLite检查点；`report` 已支持聚合结果的离线HTML初版，不会自动推断实验成功。`freeze` 拒绝覆盖已有划分，且要求五项审查全部通过。未通过审查不能以演示数据代替正式实验。

标准化输入的每条记录包含 person（仅本地）、task、stratum、question、options、context、background、answer（仅评分侧）。background 必须由数据适配器按核准映射产生，不能将原始记录直接送入API。request_payload 只构造明确允许的字段；字段名检查只是附加防护，不能替代内容与来源审查。

默认按人划分60%训练、20%开发、20%测试，固定种子20261109；同一人的重复任务不可分离。过小分层明确报错，需在冻结前重新设计，不自动删除受访者。

## 当前执行顺序

1. 完成已冻结的真人预测与合成人群调用，保存失败和重试记录。
2. 仅根据完整开发答卷冻结校准参数，不按测试成绩修改方法。
3. 对同一冻结测试集评分，分别报告纯 AI、统计参照和校准路线。
4. 生成逐题、分群和综合中文报告，完成离线页面视觉核验。
5. 候选数据继续做入场审查；不能还原原题的研究不凭猜测纳入。少于三套合格研究时不宣称广泛跨研究复现。

研究采用标准仍为用户批准计划：Brier相对改善至少2%，或分布误差下降至少2个百分点，配对95%区间高于零；两项标准分别使用。跨研究不能把同一研究的国家当作独立复现。每单元完成率至少98%，失败不能补默认答案。

依赖：Python3.12；源格式审查使用pandas、openpyxl、pyreadstat；后续统计模型使用scipy、scikit-learn。原始文件只读，不运行Excel宏或作者脚本。

评分模块要求显式的语义一致题组，不允许把随机展示的A/B直接当成跨选择卡的同一选项。按人先平均后使用调查权重；配对重抽样按受访者及分层进行。正式缺失分析、跨研究汇总和采用判定仍待接入。

## 商品统计参照

`baselines.py` 实现正则化条件Logit。输入是同一选择卡的商品特征矩阵，可包含经审查的背景交互项；不能把位置编号当商品特征。缩放只用训练数据，惩罚参数只用开发集选择。按人归一化重复任务，测试集不得参与选择。该模块已在烘干机和瑞士家电训练/开发集合拟合；开发分数用于选参，不作为独立测试成绩。

## 端点技术试跑

2026-11-10已用纯合成题验证DeepSeek Pro：返回模型标识为 `deepseek-v4-pro`，关闭思考、JSON概率输出通过。具体服务指纹和token用量见 `examples/sim-to-real/decision_lab/specs/formal/endpoint-pilot.json`。这只证明接口兼容，不是正式实验成绩或正式冻结。

本机凭据由用户配置在 `~/.config/matraix-decision-lab/credentials.json`，变量名 `DEEPSEEK_API_KEY`，文件权限0600；不随Git分发、不写入请求日志。实际调用仍从进程变量读取，运行器需显式加载本机凭据。

运行器要求配置与输入共同冻结，明确调用次数和保守费用上限。成功任务不重复调用；中断时状态不明的请求须先核实，避免自动重复计费。失败记录保留，暂未提供自动重试。费用字段为保守预留额，不冒充账单实际收费。

## 校准候选

`calibration.py`在开发集上选择概率温度与统计/LLM凸组合；显式拒绝测试标记及已知测试人员重叠。温度处理保留零概率，不默认补出模型未给出的质量。若混合权重选为0，报告必须写“统计基线被选中”，不能记为LLM优化成功。候选网格已写入各研究冻结方案。

`evaluate_study.py` 与 `study_report.py` 已贯通校准核验、配对区间、分群与逐题报告，并通过人工数据的完整流程测试。正式结果尚待全部答卷完成后生成与视觉验收；程序测试通过不等于实验效果通过。

## 烘干机真实技术试跑

`examples/sim-to-real/decision_lab/specs/pilots/dryer-pilot-protocol.json`固定21名训练集合受访者、每人1道题，分别测试无背景、年龄学历、年龄学历加家庭人数与使用频率，共63次调用。`dryer_pilot.py`保存私有冻结输入、配置和SQLite检查点；从不输出分数或读取测试集合答案作调参。正式实验仍需单独冻结完整对照、规模与方法。

年龄、学历及家庭人数被视为选择时已存在的稳定背景，这是回溯测量假设，不等于已经证明所有背景均在选择前询问。财务宽裕程度未纳入本次白名单。公共题面采取文字转写；视觉展示差异及未纳入的信息条件须在正式报告保留。

本机运行材料位于`~/.local/share/matraix-decision-lab/dryer-text-v1/technical-pilot/`，目录0700、文件0600，不随Git提交。凭据路径仅通过参数指定，不将密钥写入命令或记录。运行结束后须从检查点汇总完成率、概率合法性、模型身份、耗时与token；此处尚不代表试跑已完成。

技术试跑已完成：`examples/sim-to-real/decision_lab/specs/pilots/dryer-pilot-result.json`记录63/63调用成功，21人三种背景条件均完成，无失败或遗留请求；概率合法，模型标识与服务指纹一致。累计调用耗时约70.8秒。未计算准确率、Brier或分布误差，不能据此宣称预测有效。保守费用预留合计约0.373美元，并非实际账单。

## 输出方式和诊断条件

`output_mode=single_choice`要求模型只选一个选项；`probabilities`要求给出完整选项概率。单选结果在评分端转成0/1向量，但保留输出方式标签，这个向量代表一次选择，不能解释为模型自报100%信心。`examples/sim-to-real/decision_lab/specs/pilots/single-choice-pilot.json`记录纯合成接口验证，不是预测效果证据。

`conditions.py`提供整块附加背景错配及可逆的选项排列。错配严格限制在相同基础背景、研究分层和训练/开发/测试集合内。孤立单元保留原值并单独记录，正式诊断必须报告真正被错配的人数，不把未变化者解释为错配干预。字段交换不产生新画像事实，也不证明人格因果效应。选项换序后须映射回原始商品再评分。

## 烘干机统计参照的真实数据拟合

`dryer_baseline.py`从已还原的题面提取价格、容量、星级、品牌、能效展示和拒买指示量。仅使用真人与模型都能看到的信息：北美对照组只使用EnergyStar有无，不读取隐藏的六档能效；国家与信息组交互处理不同货币、单位和展示尺度。欧洲字母等级暂按有序数值编码，这属于简单统计模型的结构假设，不能宣称囊括所有统计方法。

相同三档背景各拟合一个正则化选择模型。868名训练受访者用于拟合，292名开发受访者用于选惩罚强度；292名测试受访者不评分。每人的8道题先等权汇总，避免把重复选择当成独立受访者。模型参数及输入哈希保存在本机，公开报告只导出汇总。该开发步骤服务于校准路线的统计参照，不用于调整冷启动提示词。

`examples/sim-to-real/decision_lab/specs/pilots/dryer-preflight.json`保存开发集统计参照及实际错配覆盖率；它不包含测试成绩。`examples/sim-to-real/decision_lab/specs/formal/dryer-formal-protocol.json`固定下一阶段的一项研究内对照：全部292名测试受访者，每人8题，五个测试条件和一个开发调用条件，共最多14,016次调用，保守费用预留上限120美元。这个上限不是实际费用预测；依据试跑约每次1.1秒，顺序调用约需4.4小时，网络波动会增加耗时。每个单元独立检查点并冻结服务标识。

## 通用技术试跑入口

`technical_pilot.py`从独立JSON协议读取分层人数、背景白名单和入场证据，复用模型调用、输入冻结与检查点。它不限于烘干机；不读取研究专属路径，不在代码中写入密钥。每套最多24人，仅从训练集合抽取，每人一道题，不计算预测成绩。

瑞士协议`examples/sim-to-real/decision_lab/specs/pilots/swiss-pilot-protocol.json`固定三个品类各8人，共24人，三种背景条件共72次调用。`pilot_summary.py`现在按实际研究的人数和选项数核验检查点，不再假定所有问卷都是三选一。

## 少数选择与集中度

`diagnostics.py`按语义相同的选择卡报告各选项真人样本数、正确识别数与召回率；无人选择的选项记为不可计算，不填0。另分别展示取最大概率后的选择集中度和平均概率集中度，避免把0.5/0.5的并列最大值误写成模型确信全票。并列最大值数量单独报告。

当前诊断为未加权计数，适用于本轮无调查权重的商品研究；不能未经调整用于加权问卷。集中度同时给全部题组及至少20人题组的计数，后者是透明展示口径，不代表统计显著性的门槛。逐卡样本量仍须显示，尤其不能将瑞士稀疏组合的一人一票解释成群体共识。

### 正式个体预测评分入口

待所有测试单元完整完成、开发校准结果冻结后，执行：

```sh
PYTHONPATH=examples/sim-to-real .venv/bin/python -m decision_lab.evaluate_study \
  <本机研究目录> --kind dryer --calibration <冻结校准.json> --output <新的评分.json>
```

瑞士研究使用 `--kind swiss`。此入口要求完整答卷、相同测试人员和题目、开发校准结果能复算一致，拒绝覆盖已有输出。比较无背景、基础背景、贴题背景、错配背景、直接单选、同概率取最大项、统计方法及开发集选择的校准混合。按人分层配对重抽样 2,000 次。输出只代表个体预测的主要评分，不替代分群、商品取舍、稳定性和合成人群报告。尚未在完整正式答卷上验收的入口不能标为已完成结果。

### 合成人群与综合汇总入口

合成人群评分不创建虚拟人与真人的逐人配对，只比较固定真人参照下的分布误差：

```sh
PYTHONPATH=examples/sim-to-real .venv/bin/python -m decision_lab.evaluate_population \
  <本机研究目录> --kind dryer --output <新的群体评分.json>
PYTHONPATH=examples/sim-to-real .venv/bin/python -m decision_lab.population_report \
  <群体评分.json> --output <群体报告.html>
```

`aggregate_report.py` 把两项个体评分、两项群体评分与运行账目合成一页离线总报告：

```sh
PYTHONPATH=examples/sim-to-real .venv/bin/python -m decision_lab.aggregate_report \
  --individual <个体评分.json> <个体评分.json> \
  --population <群体评分.json> <群体评分.json> \
  --root dryer=<本机研究目录> --root swiss=<本机研究目录> \
  --development examples/sim-to-real/decision_lab/specs/freezes/dryer-calibration-freeze.json examples/sim-to-real/decision_lab/specs/freezes/swiss-calibration-freeze.json \
  --output <总报告.html>
```

总报告拒绝任何未完成单元、重复研究或不完整的评分文件；它不把不同选项数的题合并成一个总分，也不跨研究合并区间。`--development` 只写入开发集选参记录，明确标注为“不是独立测试成绩”。群体主对照在重抽样丢失题组覆盖时不给区间，报告必须照此写出“未给出可靠区间”，不得改写成达到门槛。
