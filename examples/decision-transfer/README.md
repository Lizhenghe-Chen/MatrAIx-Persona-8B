# 下一阶段：不提前知道答案，也能预测新选择吗？

**状态：瑞士六品类正式筛查已跑完——加入真实资料有效（+8.8%），但换成别人的资料更有效（+20.2%），本人资料反而显著差于错配资料，未通过门槛。美国商品产地未准入。**

[看结果](reports/results.html) · [结果记录](docs/结果记录.md) · [准备说明](reports/index.html) · [核心研究方案](docs/核心研究方案.md) · [执行规程](docs/执行规程.md) · [历史冻结说明](archive/README.md) · [候选数据检查](data/candidates.json)

**接手请先读：[交接文档](docs/交接文档.md) · [准入进度](docs/准入进度.md)。**

已实现准入复算、抽样与供体分配、原生人格快照、四组请求冻结、预算闸门与断点续跑、逐人 Brier 评分（26项测试）。

## 这次只想弄清楚一件事

能否用可以反复使用的真人信息，预测没有提前提供答案的新问题？例如，真实的需求、约束或偏好资料，是否比只有年龄学历更有帮助；换一个商品品类后是否仍有用。

不把“每次先取得同题答案再混合”作为本阶段的主优化。不存在已承诺的70分；采用看实测指标，不看主观评分。

## 文件放在哪里

| 位置 | 用途 |
|---|---|
| `archive/` | 旧实验的冻结版本、文件哈希与恢复说明 |
| `docs/` | 本阶段方案、准备日志、旧证据使用注意事项 |
| `data/` | 候选源数据索引；`reference/`只有4份小型旧汇总副本，不能混进新成绩 |
| `src/` | 本阶段独立准备及核验代码，不修改旧脚本 |
| `tests/` | 文件隔离、恢复校验等必要检查 |
| `reports/` | 本阶段报告；准备状态与技术检查先行，效果结论只来自 Pro 正式成绩 |

旧实验完整保留在 `../sim-to-real/`，冻结提交为 `775db9dc1dde56b9f94d5ea99c250d5ae10e540a`，标记为 `experiments-frozen-2026-11-13-v1`。新代码、新运行、新报告都不写入旧目录。

原始数据继续由 `MATRAIX_DATA_ROOT` 指向共享盘。逐人材料（人员划分、答案、请求、画像坐标、调用台账）放在 `~/.local/share/matraix-decision-transfer/work/`，不随 Git。密钥只在 `~/.config/matraix-decision-lab/credentials.json`。

## 当前已做与未做

已做：旧文件全量哈希与恢复校验；瑞士原题、时点、量表映射与逐人关联全部复核通过；美国产地字段口径查清但题面无法对上数据列，判为不合格；48+4 评估人员、52 名供体确定；四臂请求冻结并与答案分离；Qwen 技术试跑 31 次；Pro 正式 216 次调用、$0.62，四臂 Brier 与配对区间已出。

未做（按门槛不做）：服装/食品的品类外推；任何扩样或换指标；新的信息类型实验（需另立版本）。

## 核验命令（不调用模型）

从 MatrAIx 仓库根目录：

```sh
.venv/bin/python -m unittest discover -s examples/decision-transfer/tests
.venv/bin/python examples/decision-transfer/src/check_protocol.py
.venv/bin/python examples/decision-transfer/src/verify.py
.venv/bin/python examples/decision-transfer/src/admission.py --check
```

运行与出分：`run.py --model pro --set formal`，然后 `score.py --model pro --which formal`。两者都只读本机冻结文件与台账。

核对所有本机私有材料和共享盘原件可运行 `freeze.py verify --local`，会读取约8 GiB数据。不要为了查看报告运行 `freeze.py create` 或 `prepare.py`：它们只用于首次建立快照，存在时会拒绝覆盖。
