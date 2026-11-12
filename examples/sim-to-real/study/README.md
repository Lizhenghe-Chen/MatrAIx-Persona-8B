# MatrAIx 真人对照实验档案

> **当前总入口：[全部实验的通俗报告](../reports/index.html)（2026-11-12）**。它包含后续家电正式测试及最新两次选择筛查。下文仅为历史阶段档案，文中的“最新”“本轮”均限于该阶段，不覆盖后续研究。

[LLM真人模拟文献综述（Markdown）](11_文献综述/综述.md)持续整理外部论文证据、参数与后续实验方向；与已经跑完的实验成绩分开。

[通俗故事版报告](index.html)先解释为什么做实验、第一次哪里答偏、后来怎样改、前后差多少，以及现在怎么用。主要结论配横向条形图，术语在出现时解释。[六轮完整证据](evidence.html)保留九份真实来源、各轮平均指标、全部逐题交互和运动鞋可见输入对齐分析；后者明确标为事后补充。第六轮三次重复运行属于已有数据内部复验。这次重组只改变呈现，不重跑模型、不改变评分。[调研与决策](调研与决策.md)记录研究过程及未纳入评分的候选数据。[档案导航](00_导航/从这里开始.md)按轮次链接评分、方案、图表和数据。

[购物与选品数据候选清单](07_购物数据候选/index.html)保留 2026 年 11 月 10 日调研时的数据来源、下载状态和适用边界。此后运动鞋、Pew Wave 13 和 Amazon 已用于第五轮，实验结论以统一报告为准。较小的公开数据与问卷现已纳入 Git，许可依据见[来源与许可](07_购物数据候选/来源与许可/README.md)。[文件归档说明](00_导航/文件归档说明.md)说明保留位置、体积限制、原始文件恢复和换电脑后的复算范围；[完整文件清单](00_导航/文件清单.json)逐项记录大小、校验值与是否随 Git 保存。

原[购物预测阅读版入口](08_购物预测/index.html)同步展示故事版，旧章节链接会进入完整证据的对应位置。历史阶段故事入口为本目录的 `index.html`；全项目当前总入口见页面顶部。进一步诊断保留为[前四轮技术附录](historical-details.html)与[第五轮技术图表](08_购物预测/technical-details.html)，运行口径见[购物预测实验记录](08_购物预测/README.md)。

## 数据保存范围

| 位置 | 内容 |
|---|---|
| 共享盘数据源总库 | 历史真人调查、商品选择、完整运动鞋复算包、Amazon 购买明细、加拿大完整包、多地区选品数据和 Persona 1M |
| 随 Git 保存 | 代码、冻结方案、合成答卷、小型公开来源副本、汇总结果、报告和校验值 |
| 项目本机运行目录 | 带真人伪编号的样本索引、逐人模型答卷和 SQLite 检查点 |

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
| 三模型与背景优化 | 挂载共享盘总库，并恢复本机检查点。运行 `optimize.py models score --study "$study"` 或 `optimize.py profiles score --study "$study"`。 |
| 北美电商选品 | 使用 `pyreadstat==1.3.7` 读 SPSS，数据和检查点见[电商索引](06_北美电商选品/数据索引.md)。运行 `shopping.py score "$study/06_北美电商选品"`。 |
| 匹配与商品内部复验 | [第六轮记录](10_匹配与商品复验/README.md)提供三次生成、字段修正及复算命令；纯合成答卷可仅凭 Git 归档重新评分。 |
| 购物预测及补充分析 | [第五轮记录](08_购物预测/README.md)列出各项开发、正式评分、校准和运动鞋输入对齐复算命令。公开汇总随 Git，逐人运行材料另在本机。 |

原始数据统一从[共享盘数据源总索引](file:///Volumes/%E5%85%83%E5%AE%87%E5%AE%99%E8%81%94%E5%90%88%E5%88%9B%E6%96%B0%E5%AE%9E%E9%AA%8C%E5%AE%A4/%E5%AE%9E%E9%AA%8C%E6%95%B0%E6%8D%AE/MatrAIx%E5%A4%9A%E5%9C%B0%E5%8C%BA%E9%80%89%E5%93%81%E6%BA%90%E6%95%B0%E6%8D%AE/README.md)读取。共享盘挂载位置不同的电脑可设置 `MATRAIX_DATA_ROOT`，指向包含 README.md 的总目录。 三份 Pew 源包分别为 [Wave 168](file:///Volumes/%E5%85%83%E5%AE%87%E5%AE%99%E8%81%94%E5%90%88%E5%88%9B%E6%96%B0%E5%AE%9E%E9%AA%8C%E5%AE%A4/%E5%AE%9E%E9%AA%8C%E6%95%B0%E6%8D%AE/MatrAIx%E5%A4%9A%E5%9C%B0%E5%8C%BA%E9%80%89%E5%93%81%E6%BA%90%E6%95%B0%E6%8D%AE/00_%E5%8E%86%E5%8F%B2%E9%80%9A%E7%94%A8%E9%97%AE%E5%8D%B7/Pew-W168.zip)、[Wave 111](file:///Volumes/%E5%85%83%E5%AE%87%E5%AE%99%E8%81%94%E5%90%88%E5%88%9B%E6%96%B0%E5%AE%9E%E9%AA%8C%E5%AE%A4/%E5%AE%9E%E9%AA%8C%E6%95%B0%E6%8D%AE/MatrAIx%E5%A4%9A%E5%9C%B0%E5%8C%BA%E9%80%89%E5%93%81%E6%BA%90%E6%95%B0%E6%8D%AE/06_%E5%8E%86%E5%8F%B2%E5%8C%97%E7%BE%8E%E7%94%B5%E5%95%86/Pew-W111.zip) 和 [Wave 13](file:///Volumes/%E5%85%83%E5%AE%87%E5%AE%99%E8%81%94%E5%90%88%E5%88%9B%E6%96%B0%E5%AE%9E%E9%AA%8C%E5%AE%A4/%E5%AE%9E%E9%AA%8C%E6%95%B0%E6%8D%AE/MatrAIx%E5%A4%9A%E5%9C%B0%E5%8C%BA%E9%80%89%E5%93%81%E6%BA%90%E6%95%B0%E6%8D%AE/08_%E8%B4%AD%E7%89%A9%E7%A0%94%E7%A9%B6%E4%B8%8E%E5%80%99%E9%80%89/Pew_Wave13/American-Trends-Panel-Wave-13-Dec-15.zip)。实验输出仍写入原运行目录。旧清单记录的文件名和哈希用于核验历史输入。若浅克隆缺少迁移前版本，先获取完整历史再对照旧清单。
