# MatrAIx 真人决策模拟实验

**先读：[AI 怎样才能更接近真人选择？——全部已完成实验总报告](reports/index.html)。**

报告按“发现的问题 → 改了什么 → 前后差多少 → 哪些仍没通过”组织。包含模型、提示、背景、概率输出、真人统计校准与最新两次选择筛查；各轮独立呈现，不把不同任务揉成一个分数。

## 按目的找文件

| 想做什么 | 入口 |
|---|---|
| 查新一轮19套跨研究验证 | [开跑准备与数据准入](decision_lab/reports/cross-study-v1/index.html) · [实施状态](decision_lab/cross_study/README.md)（尚无正式效果结论） |
| 给领导和非技术读者看结果 | [离线 HTML 总报告](reports/index.html) |
| 查哪些优化可以采用 | [持续维护的优化文档](study/05_优化记录/优化文档.md) |
| 查最新两次选择筛查 | [图解报告](decision_lab/reports/choice-history.html) · [结论与复算](decision_lab/docs/两次选择快速验证.md) |
| 查两套家电正式研究 | [图解与逐卡结果](decision_lab/reports/reader.html) · [框架当前状态](decision_lab/交接先读.md) |
| 查历史问卷、购物和订单实验 | [历史逐题证据](study/evidence.html) · [按轮次导航](study/00_导航/从这里开始.md) |
| 复用代码、重新评分 | [新框架说明](decision_lab/README.md) · [复算指南](decision_lab/docs/复算与复用指南.md) |
| 查论文和源数据 | [文献综述](study/11_文献综述/综述.md) · [历史数据索引](study/数据/实验数据索引.md) · [新数据准入审查](decision_lab/docs/数据审查发现.md) |

## 目录分工

- `reports/`：跨实验总报告、可分享的聚合证据及离线生成工具。
- `decision_lab/`：可复用框架、数据适配、冻结方案、家电正式实验和最新筛查。代码按职责分包。
- `study/`：历史各轮方案、评分与报告，持续优化记录、文献综述。原路径保持不变。
- `legacy/`：历史运行脚本、模板与旧实施文档。根目录同名符号链接是兼容入口，不是重复副本。
- `archive_inventory.py`：全档案文件大小与 SHA-256 核验。

2026-11-12 的整理只调整入口与说明、增加总报告；没有重跑实验、变更评分或删除负面结果。旧总说明已移至 [首轮与历史运行说明](legacy/首轮与历史运行说明.md)，新框架长篇实施过程已移至 [实施沿革](decision_lab/docs/实施沿革.md)。

## 保存边界

公开报告、聚合结果、代码、小型许可允许的资料随 Git。大型原始数据由 `MATRAIX_DATA_ROOT` 指向共享盘的“多地区选品源数据”；逐人关联、完整真人请求与检查点仍留本机，不能因文件小就纳入公开仓库。私有材料目录为 `~/.local/share/matraix-decision-lab/`；来源恢复及许可见 [归档说明](study/00_导航/文件归档说明.md)。

## 不调用模型的维护命令

从 MatrAIx 仓库根目录运行：

```sh
python3 examples/sim-to-real/reports/build.py
python3 examples/sim-to-real/reports/verify.py
python3 examples/sim-to-real/archive_inventory.py check
```

总报告可仅凭 Git 聚合档案重建。完整逐人评分还需要本机冻结检查点；历史报告仍可通过 `python3 examples/sim-to-real/retail_report.py` 重建。不要为查看报告运行实验的 `prepare` 或 `run` 命令。

## 已认可结论与归档决策

当前报告已按提交及文件哈希冻结为 `2026-11-12-approved-v1`。[归档说明与待决策清单](archive/README.md)区分可清理缓存、保留证据，以及需先核验副本的大型源包；[分类清单](archive/catalog.json)保留文件原路径。
