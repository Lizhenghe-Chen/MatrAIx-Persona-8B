# 历史实验代码（冻结参照）

原根目录脚本和模板已移到这里。**顶层不再有同名符号链接**：唯一的代码依赖是 `decision_lab/cross_study/targets.py`，它把本目录加入 `sys.path`，只读取 `optimize_profiles`、`instruments`、`experiment`、`retail_pew` 四个数据读取器。目录内的 `study` 与 `data_sources.py` 两个相对链接用于让历史脚本照原样运行，不复制数据。新实验在 `../decision_lab/` 开发。

`migration.json` 记录迁移前文件内容哈希。除 experiment.py 的项目根目录定位改为查找 pyproject.toml 外，迁移不改历史算法。历史数据的限制和参数保持原样，不能将其运行入口用于新的云端真人数据实验。

旧命令、报告与文献链接保留。目录中的代码不代表新实验已经通过验收。

[首轮与历史运行说明](首轮与历史运行说明.md)保留旧总说明；当前所有实验与结论从[总导航](../README.md)进入。
