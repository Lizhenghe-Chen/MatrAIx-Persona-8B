# MatrAIx 真人决策模拟实验

**一句话结论：AI 不能替代真人问卷，但能让很小的样本更值钱。**

## 先读哪一份

| 读者 | 入口 |
|---|---|
| 领导 / 非技术读者 | [故事版报告](reports/story.html) —— 问题、三轮排除、原因、方案、外部验证，首尾呼应 |
| 要核对数字 | [技术版报告](reports/index.html) —— 逐套明细、95% 区间、冻结证据 |
| 要知道"采用什么" | [推荐配置](decision_lab/docs/推荐配置.md) |
| 要接手 / 复现 | [交接先读](decision_lab/交接先读.md) · [复算与复用指南](decision_lab/docs/复算与复用指南.md) |
| 要查历史轮次 | [历史逐题证据](study/evidence.html) · [按轮次导航](study/00_导航/从这里开始.md) |
| 要查论文与源数据 | [文献综述](study/11_文献综述/综述.md) · [新数据准入审查](decision_lab/docs/数据审查发现.md) |

## 三条结论

1. **14 套研究全部输给"同信息统计参照"**（同样的题卡、同样来源的答案，只会数数），无一例外，区间全部低于零。
2. **输的原因是信息不是在措辞**：改提示框架、做输出校准、把历史分布直接喂给模型，都没能让它超过查表。
3. **唯一可交付的用法**：小样本实测 + AI 按 `w = k/(k+20)` 混合。
   9 套研究 88 张卡汇总 **+5.57pp [+3.88, +7.28]**，8/9 套为正，个体误差同时改善。
   它的价值集中在冷启动：5 份实测时误差从 23.4 降到 10.2pp；40 份时实测已经超过 AI。

## 目录分工

| 目录 | 内容 |
|---|---|
| `reports/` | 两个报告（故事版 / 技术版）与离线构建工具，纯 Git 即可重建 |
| `decision_lab/` | 当前框架：数据适配、冻结方案、正式实验、评分与校验；`docs/` 是文档，`docs/archive/` 是过程留存 |
| `study/` | 历史各轮方案、评分与报告、持续优化记录、文献综述；原路径不变 |
| `legacy/` | 历史运行脚本与模板。**不可从顶层直接 import**；只有 `decision_lab` 通过显式路径读取其中 4 个数据读取器 |
| `archive/` | 归档说明与分类清单 |

顶层只有这四个目录和三个入口文件（`README.md`、`archive_inventory.py`、`data_sources.py`）。以前顶层那批同名符号链接已删除：它们是 `legacy/` 的兼容入口，现在由代码显式指向 `legacy/`，不再需要。

## 保存边界

公开报告、聚合结果、代码、小型许可允许的资料随 Git。大型原始数据由 `MATRAIX_DATA_ROOT` 指向共享盘的“多地区选品源数据”；逐人关联、完整真人请求与检查点仍留本机，不能因文件小就纳入公开仓库。私有材料目录为 `~/.local/share/matraix-decision-lab/`；来源恢复及许可见 [归档说明](study/00_导航/文件归档说明.md)。

## 不调用模型的维护命令

从 MatrAIx 仓库根目录运行：

```sh
python3 examples/sim-to-real/reports/build.py         # 技术版
python3 examples/sim-to-real/reports/build_story.py   # 故事版
python3 examples/sim-to-real/reports/verify.py        # 两页与冻结数据一致性
node examples/sim-to-real/reports/smoke.cjs           # 技术版浏览器检查
node examples/sim-to-real/reports/smoke_story.cjs     # 故事版浏览器检查
python3 examples/sim-to-real/archive_inventory.py check
```

两个报告都能仅凭 Git 聚合档案重建；完整逐人评分还需要本机冻结检查点。
历史报告仍可通过 `python3 examples/sim-to-real/legacy/retail_report.py` 重建。
不要为查看报告运行实验的 `prepare` 或 `run` 命令。

## 冻结与归档

报告按文件哈希冻结，最新为 `archive/accepted-report-v29.json`（每版记录变更说明与全部被冻结文件的 SHA-256）。
[归档说明](archive/README.md)区分可清理缓存、保留证据与需先核验副本的大型源包；[分类清单](archive/catalog.json)保留文件原路径。
