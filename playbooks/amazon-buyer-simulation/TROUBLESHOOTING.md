# 踩坑手册（全部来自真实运行与一次逐文件可复现性审计，复现时优先对照）

## 〇、复制参考脚本：逐文件必改清单（最重要）

参考脚本是浴帘品类的**已验证实例**，但为快速落地写了硬编码。换品类/换机器时按下表改，漏一处就跑不通或数字不更新。所有脚本默认仓库根为 `/Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B`，**换机器先全局替换这个绝对路径**（job 生成脚本用 `Path(__file__).parents[1]` 自适应，是例外）。

| 脚本 | 必改项 |
| --- | --- |
| `results/.../build_task.py`（货架） | ① `ROOT` 绝对路径；② `TASK` 目录名 `survey_<slug>`；③ 整个 `PRODUCTS` 字典（字段：asin/brand/name/material/look/points/price/rating/reviews/rank/size/pack/avail）；④ `task.toml` 模板里的 `name="application/survey_<slug>"` 与 tags；⑤ 品类词与品类专属题 |
| `results/.../build_journey_task.py`（旅程） | 同上；**另有两个耦合坑**：① 它读取「货架任务已生成的 `tests/test_state.py`」再正则改写，所以**必须先成功跑过 build_task.py**；② 校验器 `ALLOWED_CHOICES` 字母块在脚本里**硬编码为 A-F**，产品数≠6 时必须改成实际字母（A..N + none_of_these），否则 journey 校验失败 |
| `scripts/generate_*_jobs.py` | 只改脚本内 `task=` 路径与 `slug=`；n/concurrent/seed 走位置参数。路径自适应无需改 ROOT |
| `results/.../aggregate_shower_liner_experiment.py` | ① `ROOT`、`OUT`（注意浴帘输出目录是 `results/shower-liner-6asin-experiment/`，带 `-experiment` 后缀，与 assets 所在的 `.../shower-liner-6asin/` 是两个目录）；② `PRODUCT_META`、`OPTION_ORDER`（字母+none_of_these）；③ 题目 ID 若增删过问卷要同步；job 目录可用 `--choice-dir/--journey-dir` 覆盖 |
| `results/.../generate_shower_liner_reports_v2.py` | ① 顶部 `ROOT/SUMMARY/ASSETS/OUT_DIR`；② `TOILET_REPORT`（见下条 ECharts 坑，建议改指 `playbooks/amazon-buyer-simulation/assets/echarts.min.js`）；③ 整个 `products` 展示数组（编号/中文名/价格/评分/评价/排名/特征/img/asin，**含每张产品卡的 `share=` 是手写数字，不会随 summary 更新，要手填**）；④ `DATA["reasons"]` 词频（见聚合缺口）；⑤ HTML 模板里的核心结论、建议表等中文案 |

**哪些会自动更新、哪些必须手填（报告阶段）**：份额/因素/重要性/红线/切换/徽章/旅程各环节占比/买家原话（`sample_*_reasons`）都从 `summary.json` 自动读（字段名已对齐，勿改 summary 键名）；**必须手填**的是产品卡 `products`、`DATA["reasons"]` 主题词频、核心结论与建议文案。

## 一、运行 / 进程

1. **普通后台会被对话轮次回收**：agent 的 run_in_background、`&` 前台 shell 在下一轮对话会被清理，job 停在几十份。**长任务一律 `nohup cmd > logs/x.log 2>&1 &`**，脱离会话。
2. **不要 `pkill -f matraix` / `pkill -f <脚本名>`**：会误杀同名新 nohup 队列。要停就 `ps aux | grep <job-slug>` 找具体 PID，`kill <PID>`。
3. **续跑启动即崩**：常因存在缺 `config.json` 的不完整 trial 目录。删掉这些残缺目录（保留有 survey_result.json 的完整 trial），再重跑同一 yaml（自动断点续跑）。
4. **删 job 目录前先停 matraix**；改了 task（货架/题目）后必须用**新 slug 重新生成 job**——旧 trial 按内容缓存，复用旧 job 不加载新题。
5. 每 job 启动前 `rm -f jobs/<job>/lock.json`，避免残留锁阻塞。
6. 运行前必须 `set -a && . ./.env && set +a` 导出 `DEEPSEEK_API_KEY`；`matraix run` 不自动读 .env。
7. Python 用仓库 `.venv/bin/python`（有 pyyaml/pyarrow）；HTML 截图自检用系统 `python3`（有 playwright），.venv 里没有。

## 二、采样 / 官方管道

8. **CLI `--sample-size` >100 会被截断为 32**（UI 预览限制）。n=1000 必须走复用官方 `PersonaPoolService.sample_pool(..., include_persona_ids=True)` 的生成脚本（与 UI 同一条官方服务路径，不是绕过）。
9. 任务必须是官方 9 文件 survey 布局且 `task.toml` 的 name 与目录名一致，否则后端 `/api/survey-eval/instruments`、`/api/survey-eval/harbor-tasks` 识别不到。改完用 `curl -s http://127.0.0.1:8765/api/survey-eval/instruments` 核对。
10. 生成 job yaml 时单选选项是 `{id,label}` 对象列表，别把 dict 解包成 `(key,value)`（曾致 q_next_choice/q_fallback 选项错误）。生成后务必 smoke + n=1 验证。

## 三、问卷 / 校验器

11. `tests/test_state.py` 的 `ALLOWED_CHOICES` 必须与问卷产品选项（A..N + none_of_these）完全一致；journey 版校验 q_first_click/q_next_choice/q_fallback 值在该集合内，且 6 个决策题 rationale≥10 字符。**产品数变化时，choice 与 journey 两个校验器的字母集合都要改**（journey 的字母块在 build_journey_task.py 里硬编码，见〇-②）。
12. likert 题字段是 `minValue/maxValue`（1-5），不是 scale/min/max。
13. 多选选项末位放 `none`/`already_chosen` 互斥项；产品拒绝题首项固定 `already_chosen = This is the one I chose`。
14. 外观维度必须靠主图识别写进 `context.md` 的 look 列，否则买家不会对外观投票（保温杯 V1「设计颜值」得票 0 的教训）。

## 四、聚合

15. 答卷在 `jobs/<job>/<trial>/artifacts/app/output/survey_result.json`，结构 `answers:[{questionId,value,rationale}]`；value 单选取标量、多选取 list。
16. 导出 raw CSV 理由列后缀是 **`_why`**（不是 `_rationale`）；CSV 用 **utf-8-sig（带 BOM）**，否则 Excel 打开中文乱码。
17. likert 均分按「分值×人数」加权再除以总人数；**不能把 dict.keys() 当数字求和**（曾致 price_accept_mean 算错）。
18. 百分比分母 = 该题有效回答人数，不一定等于 n；多选题提及率可 >100%。
19. **主题词频是链路缺口**：aggregate 脚本**不产出**开放题理由的主题词频，summary 里没有该字段；浴帘报告 `DATA["reasons"]` 的 4 组词频是另算后手填的。复现时要么对 raw CSV 的 `*_why` 列用关键词词典自行归类（参考 `references/report_standard.md` 末尾代码片段），要么不放词频图、改为引用买家原话。词频=被提及程度，同一人同主题只计一次，不等于重要性或因果。

## 五、报告 / HTML

20. **ECharts 外部依赖**：浴帘报告脚本从马桶刷报告 HTML 正则提取 ECharts（`TOILET_REPORT`）；该文件缺失时 `ECHARTS_JS=""` 且**静默不报错，所有图不渲染**。复现时改指本技能自带的 `playbooks/amazon-buyer-simulation/assets/echarts.min.js`（已备好，1MB 离线库），或从任意历史报告提取同款内嵌块。
21. ECharts 里多选拒绝原因是对象（dict），直接遍历，**别当数组 `.find()`**——曾因此 JS 中断、后续所有图不渲染。
22. 图表只用横向条形/简单柱状/环形；漏斗、热力、堆叠、双轴在面向领导的报告里一律不用。
23. 主图在 HTML 里 base64 内嵌（脚本 `b64()`）或同目录 assets 相对路径；过期签名图片 URL 不可用。
24. 交付前只用 html skill 的 `scripts/shot.py` 自检（桌面+移动 full-page），看 consoleErrors / canvas 数 / clippedText / responsiveChartIssues；不要用 artifact-preview 检 HTML，也不要自己开浏览器 debug。
25. 一个实验一份 HTML，不要把货架选择和决策旅程塞进一份长报告。

## 六、成本 / 规模参考（浴帘 n=1000，仅供量级）

- 单实验 n=1000（26/8 题）、并发 30，全量数十分钟级；`--max-cost-usd` 单实验给 12 美元上限足够，实际以 `jobs/<job>/_matraix_budget.json` 的 spent_usd 为准。
- 先 n=1 再 n=20 pilot，确认 reward=1、成本与解析率正常，再放 n=1000，避免大规模返工。
