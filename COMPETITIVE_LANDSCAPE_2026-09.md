# 同类与更优项目调研：MatrAIx 竞品/格局 peer-review（2026-09）

> 口径：对照基线为 MatrAIx（1290 维共享人设 schema、依赖感知合成 + 证据感知真实人类锚定、质量过滤后公开 1M 人设、Survey/Chat/Web(Playwright)/App(computer-use) 四环境、MIT、arXiv:2608.04205）。
> 每条关键事实标注【已查证】（一手来源可开）或【一方说法】（公司/论文自述或媒体转述，未独立复算）。规模、许可、机构归属均附 URL。

---

## 0. 一页结论

- **和你最像的，不是"更先进"，而是两条脉络的交汇点**：学术上最同源的是 **Stanford 1000 People**（Park 等，真人访谈蒸馏代理）；工程/数据上最同源的是 **Persona Hub**（腾讯 AI Lab，不是 Anthropic，见下）；商业上最像的是 **Synthetic Users**。
- **真正"比你强一块"的玩家只有一个：Simile**（Smallville 一作 Joon Sung Park 联合 Liang/Bernstein 创办，2026 年 B 轮后估值约 $2B）。它强在"用真人长访谈直接训练行为模型 + 企业真金白银买单"，但它是黑盒闭源——这恰恰是你的生态位。
- **你真正的护城河不是"模拟人"本身，而是三件事同时成立**：1M 级深人设（1290 维）且 **MIT 完全开放**、四环境真实产品落地（尤其 Web Playwright + 原生 App computer-use）、评测闭环（rewardkit + langsmith）。任何单点对手都只占其中一两件。
- **你的两块短板必须补**：① 缺一个"和真人复测对齐 X%"的金标准保真验证（1000 People 有，你没有）；② 缺外部盲测/分布校准（真人偏好盲测、普查边际后分层）。这两块补上之前，护城河是"位置红利"，不是技术不可替代。

---

## 1. 先纠正一个流传很广的事实错误

**"Anthropic Persona Hub（1B personas）"归属不成立。**
- "1B personas" 的唯一出处是 *Scaling Synthetic Data Creation with 1,000,000,000 Personas*，作者 **Tao Ge, Xin Chan, Xiaoyang Wang, Dian Yu, Haitao Mi, Dong Yu**，机构为 **Tencent AI Lab Seattle（腾讯 AI Lab 西雅图）**，**不是 Anthropic**。论文/数据许可 **CC BY-NC-SA 4.0（禁止商用）**，代码仓 github.com/tencent-ailab/persona-hub。【已查证：https://arxiv.org/abs/2406.20094 ；许可页 CC BY-NC-SA 4.0】
- 这反而是个利好：对外材料里主动点破这点，本身就是"你比同行更懂这个领域"的信号。

---

## 2. 分层评价

### 2.1 最相似的项目（问题同源，正面硬碰）

**Stanford "Generative Agent Simulations of 1,000 People"（Park et al., 2024/2025）——你的学术正脉竞品**
- 方法：1052 名美国分层抽样个体，每人 2 小时 AI 语音访谈，把 transcript 蒸馏成"这个人的代理"；用 GSS/Big Five/行为实验对照，代理复现真人答案的准确率 ≈ 真人两周后自己复测的 **85%**。【已查证：https://arxiv.org/abs/2411.10109 ；Stanford HAI】
- 它比你强：**验证标准最硬**——直接和真人重测做 A/B，给出 85% 这种可量化保真度。
- 你比它强：**开放度**。它的个体数据锁在"两级访问"审批墙后（保护隐私）；你直接把 1M 质量过滤人设 MIT 放到 HF。另外 1052 vs 1M 的规模差，以及它只做 survey、你有 Web/App。
- 借鉴：**照它的样子补一个"Persona 1M 与真人复测对齐多少"的金标准指标**——这是你叙事里最缺的一环。

**Persona Hub（腾讯 AI Lab）——人设驱动这条母题的直接对照**
- 方法：Text-to-Persona（让 LLM 猜"谁会读这篇网页"）+ Persona-to-Persona 六度分隔扩散 + 去重；人设仅 **1–2 句自由文本**，无心理/能力/行为字段。名义 10.16 亿条，实际公开仅约 **20 万 + 2025 年 2 月追加的 3.7 亿"专家人设"**。【已查证：arXiv:2406.20094；github.com/tencent-ailab/persona-hub】
- 它比你强：**生态先发**——已被大量论文和 CAMEL.AI 框架当默认人设种子库；方法极简、可无限横向扩。
- 你比它强：人设深度差一个量级（1–2 句 vs 1290 维）、有真实人类锚定、是评测基础设施而非造数据的种子库、**MIT vs NC 非商用**。
- 借鉴：想清楚"为什么更细的 PersonaHub 不够"——把 Persona 1M 讲成下游可复用的默认采样源。

**Synthetic Users（syntheticusers.com）——商业上最像你**
- AI 主持的结构化合成访谈，多 agent 降"单一人声"感；RAG 选项把人设锚定到客户第一方数据（和你的 grounding 对位）。【已查证：https://www.syntheticusers.com/pricing 】
- 它比你强：**产品化**——提问到出洞察约 6 分钟、按次计费、非研究人员可用；一方称累计 3 万+ 会话、$11/研究 vs 真人 panel ~$200。【一方说法】
- 你比它强：**运行环境**（它只做访谈/问卷，不做 Web 点击流和 App 行为）、人设资产（1M 公开、可审计 vs 它的自描述 persona）、开源可复现（它的 85–92% parity 是黑盒自报）。
- 借鉴：学它"按次计费、快速出报告"的产品叙事，把 Playground 包装成非技术团队能用的形态。

### 2.2 真正"更好一块"的项目

**Simile —— 2026 年这个赛道的绝对头部，最需要正视的更强玩家**
- 创始人：Joon Sung Park（Smallville 一作）+ Percy Liang + Michael Bernstein。做 agentic twins：用授权长访谈和行为数据训练"真人数字分身"。核心模型用 1000 名代表性参与者的 2 小时访谈训练，再用新响应验证；与 Gallup 合作纳入数百万人数据。【一方说法/多源交叉：https://www.unite.ai/simile-raises-more-than-200-million-at-a-2-billion-valuation-to-scale-human-behavior-simulations/ 】
- 规模与采用：CVS Health 部署最多 **40 万 twins**、基于 290 万条授权响应；Deloitte 替代焦点小组、Wealthfront 扩大定性研究 15 倍。融资：2026-02 A 轮 $100M（估值 $1B），2026-07 B 轮 $200M（估值 $2B），Greenoaks 领投。准确率自称 85–99%，**全是自测、未经独立审计**，TechCrunch 公开质疑。【一方说法：https://theailandscape.com/startups/simile/ 】
- 它确实比你强在：① **证据锚定的深度**（直接拿真人长访谈训练模型，你的 grounding 还停在人设文本层）；② 企业付费与部署规模；③ 学术正统叙事。
- 你仍领先：**开源透明**（它是黑盒，数字不可复现；你的 1M 人设 MIT 可独立审计，这在学术/政府/医疗场景是硬优势）、环境异构（它的 twins 本质是"被调查者"，你还能跑 App computer-use）、可组合（你是基础设施，它是端到端闭环）。
- 判断：**不要和它在"预测消费者"这条路上硬碰**（资金/数据/招牌都输）。守住"可复现、可审计、跨环境的开源评测标准"这个生态位。

**其他"单点比你强"的项目（不必焦虑，但要认账）**
- **Stanford 1000 People**：科学严谨性（真人 A/B 验证）——见上。
- **AgentSociety（清华 FIB Lab，李勇团队）**：**分布式工程成熟度与社区运营**——Ray 分布式、DuckDB 实验 replay、PyPI 持续发版（2026-09 仍在更新）、官方 Challenge；10k+ agent、500 万次交互。【已查证：https://arxiv.org/abs/2502.08691 ；https://github.com/tsinghua-fib-lab/agentsociety ；Apache-2.0（带 commercial 例外）】
- **Google DeepMind Concordia**：**架构通用性**——GM（裁判）+ 可插拔 Component 抽象，把"环境如何裁决 agent 动作后果"做成一等公民。【已查证：https://github.com/google-deepmind/concordia ；Apache-2.0】
- **SOTOPIA（CMU, ICLR 2024 Spotlight）**：**评测维度体系**——SOTOPIA-Eval 七维（goal completion / believability / knowledge / secret / relationship / social rules / benefits）。【已查证：https://arxiv.org/abs/2310.11667 ；MIT】
- **Persona Hub**：生态默认地位——见上。
- **RTI 国家合成人口 2019（SynthPop）**：**分布保真与地理显式**——3.03 亿个体/1.2 亿户，从真实 ACS/普查 microdata 做 IPF/迭代拟合。【已查证：Scientific Data；代码 rti_synth_pop】
- **LMSYS Chatbot Arena / MT-Bench**：**真实人类偏好信号**（注意：LMSYS 官方并无"人设驱动评测"这一维，大多是下游研究者拿 PersonaHub 当 system prompt，别夸大它和你的关系）。

### 2.3 可以直接借鉴的具体做法（按优先级）

1. **补金标准保真验证**（最缺）：学 1000 People，做"Persona 1M 与真人复测对齐 X%"的量化 A/B，而不只是质量过滤。
2. **响应分布对齐**：把 DSA 式分布对齐微调（arXiv:2510.21977，真实标注需求最多降 69%）和 Restricted Generation（限制式打分优于自由生成）接进 Survey 运行器——这比继续加人设维度更能提升 fidelity，也能正面回应"合成响应方差过小"的老批评。
3. **外部盲测层**：学 LMSYS Arena，把高/低人设依从的对话抽一批给真人盲判，作为外部效度证据。
4. **普查边际后分层**：学 RTI，对照 ACS/真实普查边际做人设人群结构校准，补强"代表性"软肋。
5. **多维度 rubric**：把 rewardkit 从"任务完成率 + 人工打分"升级到 SOTOPIA-Eval 式 believability / social rules 等多维度。
6. **环境抽象**：学 Concordia 的 GM/Component，把四类环境从各写各的，变成"环境裁决"一等组件。
7. **成本工程预案**：学 Light Society 的 mixture-of-models（关键个体走 full LLM、长尾走 distilled），未来扩规模时压成本。
8. **行为级 fidelity 自我审计**：主动引用 arXiv:2605.18302（实测 53% 任务上合成点击分布与真人显著不同），给出你自己在点击流/A/B 上与真人分布的对齐数字——现在不做，审稿人也会逼你做。

---

## 3. 横向对比表

| 项目 | 真实锚定 | 人设/个体规模 | 完全开放数据 | 产品环境 | 许可 |
|---|---|---|---|---|---|
| **MatrAIx** | 有（evidence grounding） | **1M 深人设(1290维)** | **是（HF, MIT）** | **Survey/Chat/Web/App(含computer-use)** | **MIT** |
| 1000 People (Stanford) | 强（2h 访谈/人） | 1,052 | 否（个体数据审批墙） | 仅 survey | 受限 API |
| Persona Hub (腾讯) | 无（从网页文本猜） | 名义 10 亿，公开约 20万+3.7亿 | 部分 | 无（造数据种子库） | CC BY-NC-ND**NC**（禁商用） |
| Simile | 极强（真人访谈训练模型） | 企业级（CVS 40万 twins） | 否（黑盒） | 被调查者/访谈 | 闭源 |
| Synthetic Users | 可选（RAG 接客户数据） | 一方称 3万+ 会话 | 否（SaaS 黑盒） | 访谈/问卷 | 闭源 |
| Generative Agents (Smallville) | 无 | 25 | 代码，非标准许可 | 仅自家 2D 沙盒 | research code |
| AgentSociety (清华) | 人口/网络统计 | 10k+ | 是 | 城市环境（非产品） | Apache-2.0(带例外) |
| Concordia (DeepMind) | 不预设 | 不限（空引擎） | 是 | 引擎（可接三类） | Apache-2.0 |
| SOTOPIA (CMU) | 无 | 数百场景 | 是 | 文本对话 | MIT |
| OASIS (CAMEL) | 无 | 标称 100 万 | 是 | 社交媒体模拟 | 开源 |
| Light Society | WVS 人口画像锚定 | ~10万模板→标称10亿 | 未公开人设库 | 实验 | 未核实 |
| RTI SynthPop | 真实普查 | 3.03 亿个体 | 代码开源（商用另议） | 无（静态属性表） | 非商用免费 |

---

## 4. 逐个速写（梯队）

**第一梯队·正面竞品**
- Stanford 1000 People：问题/方法同源，验证最硬，但锁数据、只做 survey、规模小。
- Persona Hub：母题同源、生态最大，但人设浅、无锚定、NC 许可、不做评测。
- Simile：资金/数据/落地最强，但闭源黑盒——错位竞争，别硬拼。
- Synthetic Users：产品化最好，但环境单一、闭源。

**第二梯队·学术工程参照（可借鉴、非威胁）**
- AgentSociety：分布式 + 社区运营标杆。
- Concordia：环境/裁判抽象标杆。
- SOTOPIA：评测 rubric 标杆。
- Generative Agents / AI Town：认知架构祖师爷 + 玩具化 starter（MIT，~8.8–10k stars），不做规模化与产品评测。
- OASIS（CAMEL，标称百万社媒用户）：有"推荐算法回流影响行为"的反馈环思路，但人是兴趣标签群体、不做个体画像。
- Light Society：标称 10 亿 agent，但实为约 10 万条 WVS profile 复用——"十亿个一样的人 vs 一百万个不一样的人"可作你的对外对比叙事。

**第三梯队·思想上游 / 背景**
- Aher et al. 2023（Turing Experiment，ICML）：LLM 模拟人类被试的开山，人设极薄、纯问卷。【已查证：https://proceedings.mlr.press/v202/aher23a.html 】
- Argyle et al. 2023（"Out of One, Many"，Political Analysis）：真实 backstory 条件化 LLM 的源头，你的 grounding 思路与之同源。【已查证：https://doi.org/10.1017/pan.2022.46 】
- RTI SynthPop / 英国 synthpop / SynthPop++：统计式合成人口，方法与你本质不同（静态分布表 vs 可对话带心理能力维度的个体），借鉴其普查边际校准即可。

---

## 5. 已剔除 / 降温的项目（核实后不纳入）

- **Latent.ai**：**已停摆**——当前域名跳转 Afternic 出售页。剔除。
- **UserLane**：**不属于本赛道**——是企业软件"应用内引导/产品分析"平台，不是合成用户研究。剔除。
- **Hunch**：未查到与"合成用户"对应的活跃实体，不编造。剔除。
- **AgentVerse（OpenBMB）**：多代理协作完成任务（写码/做研究），非人设驱动社会模拟。剔除。
- **AgentSims**：早期小镇沙盒，2023 年后无实质更新。剔除。
- **InclusionAI 人设数据集**：查无实据（InclusionAI 实为蚂蚁模型实验室）。剔除。
- **"Sandia 合成人口"**：降温——Sandia 相关工作是 ABM 的贝叶斯标定，不是人口生成；统计式合成人口正统是 RTI/ORNL/IPF。
- **一堆低价 persona 生成器**（Delve AI / Gins.ai / Uxia / Deepsona 等）：ChatGPT 套壳 + 模板，无公开验证，列噪音即可。

---

## 6. 护城河判断（说人话）

你的护城河是三个交集同时成立，而任何单点对手都没同时做到：
1. **1M 级深人设（1290 维）+ MIT 完全开放**（1000 People 精细但锁数据；Persona Hub 开放但浅；Light Society 量大但模板化）；
2. **四类真实产品环境，尤其 Web Playwright + 原生 App computer-use**（学术圈全部停在沙盒/对话/survey，没人真跑"人在你产品里怎么走流程"）；
3. **评测闭环（rewardkit + langsmith）**，把模拟直接接进产品实验/上线流程。

但要清醒：这是**位置红利**。一旦 1000 People 那条线（Park/Bernstein）放开数据或加 Web/App 环境，或 AgentSociety 从城市转向产品评测，空位会被快速填上。**现在最该做的不是继续堆人设数量，而是把"Persona 1M 的保真度验证"和"产品环境下可复现的评测基准"做成别人搬不走的硬证据。** 尤其 Simile 的存在让"合成人是否可信"赌注极大，未来 12 个月必有大规模独立审计——抢先把"如何审计合成人 fidelity"做成开放基准，是把对手闭源软肋变成你护城河的窗口。

---

## 7. 待确认的遗留项（未查到确凿证据，未编造）

- DeepPersona（arXiv:2511.07338，"深人设"方向，疑似撞型）的实际规模与开源状态。
- NVIDIA 自称的"100 万记录 / 600 万人设 / 6+16 字段"合成数据集的独立复核（来源为技术宣讲稿，一方说法）。
- PersonaHub 完整 10 亿集是否已对学术完全开放（当前只确认到约 20 万 + 3.7 亿专家）。
- Simile 的 85–99% 准确率与 CVS 40 万 twins 等关键数字均为公司自述，未经独立审计。
