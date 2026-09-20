# 问卷设计指南与可复用题库

两类标准实验的题目结构（以浴帘 6 款为实例，换品类时替换品类词与产品选项，结构与题 ID 保持稳定，聚合脚本即可复用）。

- 产品选项：每款 `{id:"A".., label:"A — <英文标题> (<价格>)"}`，末位固定 `{id:"none_of_these", label:"None of these — I would not buy any of them"}`。
- 题型：`single_choice` / `multi_choice` / `likert`（likert 用 `minValue:1,maxValue:5`）。
- 需要理由的题设 `askRationale: true`。

## 实验一 · 货架选择（choice，浴帘版 26 题）

| 题 ID | 类型 | 问什么 | 选项要点 |
| --- | --- | --- | --- |
| q_choice | single+理由 | 最终买哪款 | A..N + none_of_these |
| q_reject_A … q_reject_N | multi | **每款**为什么没选（选中款选 already_chosen） | 见下方拒绝原因 16 项 |
| q_page_browse | single | 翻到第几页还愿**点进去看** | page1/page2/page3/page4_5/beyond/unsure |
| q_page_buy | single | 翻到第几页还愿**买** | 同上 |
| q_factor_most | single | 第一重要因素 | 见下方因素 12 项 |
| q_factor_second | single | 第二重要因素 | 同上 |
| q_importance_title/image/bullets/aplus/attr/price/reviews/trust | likert×8 | Listing 8 要素重要性（标题/主图/五点/A+/属性规格/价格/评分评价/品牌信任与库存配送） | 1-5 |
| q_listing_redline | multi | 哪些情况**一票否决**直接排除 | 见下方红线 11 项 |
| q_material_pref | single | 材质偏好（品类相关，可换） | 浴帘：eva/peva/pvc/polyester/cloth/no_preference |
| q_transparency_pref | single | 透明度偏好（品类相关，可换） | fully_transparent/semi/blackout/no_preference |
| q_badge_effect | single | Amazon's Choice/Best Seller 徽章影响 | yes_strongly/yes_somewhat/neutral/unlikely/no_effect |
| q_switch_trigger | single | 什么会让你改买别的 | lower_price/better_rating/better_look/better_function/better_value/nothing |
| q_price_acceptance | likert | 所选款价格是否值 | 1-5 |
| q_purchase_intent | likert | 3 个月内真会买 | 1-5 |

**拒绝原因 16 项（q_reject_*）**：already_chosen / price_too_high / price_suspicious（太便宜怕质量差）/ look（外观颜色纹理不喜欢）/ material（材质/安全存疑）/ rating（星级不够）/ few_reviews（评价太少）/ review_concern（评价内容有疑虑）/ brand（品牌陌生不信任）/ size（尺寸规格不清或异常）/ missing_feature（缺磁吸/配重/挂钩等）/ transparency（透明度颜色不符）/ pack（件数不符）/ info_incomplete（描述/图/规格不全）/ availability（缺货/低库存/配送问题）/ other。

**决策因素 12 项（q_factor_*、journey q_overall_factor 共用）**：price_value / material / function（防水防霉速干等，浴帘另列 waterproof、magnet、transparency 时可合并到 function 或拆细）/ appearance / size_fit / rating / reviews / brand / pack / availability / listing（标题图五点规格完整度）/ other。
> 浴帘实例把 function 拆成了 waterproof、magnet、transparency 三项；换品类时按该品类的核心功能维度增删（如保温杯可换保温时长/密封防漏/容量）。

**一票否决 11 项（q_listing_redline）**：unavailable（缺货/配送问题/无 Buy Box）/ no_price / low_rating（<4.0）/ few_reviews（<约50 条）/ no_size / material_unclear / blur_image（主图糊/像假图）/ no_bullets / no_aplus / brand_unfamiliar / none。

## 实验二 · 决策旅程（journey，8 题；前 6 题都要理由）

| 顺序 | 题 ID | 类型 | 问什么 |
| --- | --- | --- | --- |
| 1 | q_first_click | single+理由 | 搜索结果里**第一眼最想点**哪个缩略图（结合外观/价格/评分/评价数/品牌/主图说理由） |
| 2 | q_click_info | multi(≤3)+理由 | 点进去后最想查看什么信息（见下方 12 项） |
| 3 | q_buy_decision | single+理由 | 看完详情页买不买：buy_now / likely_buy（加购继续比）/ undecided / not_buy |
| 4 | q_consider_other | single+理由 | 不立刻买的话，退出后是否看其他款：yes / maybe / no |
| 5 | q_next_choice | single+理由 | 下一个看哪款（上题选 No 则 none_of_these） |
| 6 | q_fallback | single+理由 | 全部点完都没买，**被迫必须选一款**会选谁 |
| 7 | q_page_search | single | 搜索通常翻几页（page1…unsure） |
| 8 | q_overall_factor | single | 整段旅程最终最看重的因素（因素 12 项） |

**点进详情页查看项 12 项（q_click_info）**：more_images（更多实拍/角度图）/ video（视频演示）/ description（完整描述）/ bullets（五点卖点）/ specs（尺寸规格表）/ material_safety（材质与安全）/ reviews（评价文字与买家图）/ qa（问答）/ aplus（A+ 品牌故事/对比）/ delivery（配送时效）/ warranty（退换/保修）/ other。

## 设计原则

- **每个关键决策点都要理由**（askRationale），理由是后续词频与原话引用的来源；校验器要求理由≥10 字符，避免敷衍。
- 客观可核验的选项（价格/评分/评价数/库存/材质/规格）来自货架 context；主观偏好（因素、重要性、红线、徽章、切换诱因）用来做聚类和干扰分析。
- 货架 `context.md` 用统一表格列：Option / Product / Material / **Look & design（据主图识别）** / Key selling points / Price / Rating / Availability。
- 换品类时：改品类词、产品行、品类专属题（材质/功能维度），其余题与 ID 尽量不动，聚合/报告脚本改造成本最低。
- 不要在问卷里塞排名位置/匿名对照等额外臂，除非用户明确要求（本项目曾做过排名位置 a/c/f 三臂，后被用户要求删除）。
