# 电商/网购 真实问卷调查数据集清单（用于 MatrAIx-Persona-8B 对比验证）

## A. 真实问卷原始数据（最推荐：有受访者逐题回答 + 人口学属性）

| # | 数据集 | 样本量 | 内容 | 格式 | 获取方式 |
|---|--------|--------|------|------|----------|
| A1 | Online Shopping Behavior (Mendeley Data, DOI:10.17632/t8zbf8hr4k.1) | 306 | 促销/社交媒体/名人代言/购买决策量表，含 RAW 原始数据 + PLS-SEM 分析文件 | xlsx | https://data.mendeley.com/datasets/t8zbf8hr4k 免费直下 |
| A2 | BNPL 在线冲动购买行为 (Mendeley Data, Data in Brief 2024) | 810 (有效806) | S-O-R 模型量表：冲动购买、促销刺激、社会影响、幸福感、自控力、规范评估；含问卷原文+人口学 | xlsx + csv | https://data.mendeley.com （搜 "online impulsive buying BNPL"）免费直下 |
| A3 | 尼日利亚大型超市消费者购买行为 (Kaggle DSV/4972216) | 1,272 | Likert 5点量表 + 人口学；PLOS ONE 论文背书 | csv | https://doi.org/10.34740/KAGGLE/DSV/4972216 |
| A4 | Subsistence Retail Consumer Data (Mendeley, DOI:10.17632/5z37z85jck.1) | 281 | 南非零售消费者：便利性/价格敏感度/感知质量/信任/感知价值 | xlsx | https://data.mendeley.com/datasets/5z37z85jck/1 |
| A5 | CFPS 中国家庭追踪调查 2020（北大 ISSS） | 约16,000户/数万人 | 全国代表性样本，成人问卷含网购、移动支付模块；真正"中国真实人群"基准 | Stata/SAS | https://cfpsdata.pku.edu.cn 或 https://opendata.pku.edu.cn/dataverse/CFPS ，免费注册申请（审核约3个工作日） |

## B. 真实行为日志（真实但非问卷回答，适合做行为层面的辅助验证）

| # | 数据集 | 规模 | 说明 |
|---|--------|------|------|
| B1 | UCI Online Shoppers Purchasing Intention | 12,330 会话 | 点击流特征+是否购买；CC BY 4.0，可 `pip install ucimlrepo` 直接加载 (id=468) 或 CSV 直下 |
| B2 | 淘宝 UserBehavior（阿里天池） | 1亿交互/98.8万用户 | pv/cart/fav/buy 真实行为；CC BY-NC-SA 4.0（限非商用）|

## C. 不推荐用于验证（合成数据或仅有模板）
- Kaggle "Customer Shopping Trends" 3900条 —— 合成数据
- 问卷网/问卷星模板 —— 只有题目没有数据
- Federal Reserve 移动购物问卷 —— 只有汇总表，无个体数据

## 验证建议（persona vs 真实问卷）
1. 边际分布匹配：把 A1/A2 的人口学变量（年龄/性别/收入）作为 persona 条件，生成回答后与真实受访者各题选项分布对比（总变差距离 / KL 散度）。
2. 交叉表验证：persona 生成的"性别×购买意愿"交叉分布 vs 真实数据交叉表。
3. 量表心理测量属性：对 persona 生成数据跑 Cronbach's α、验证性因子分析，与真实数据的信效度对比（A1/A2 论文里有现成基准值）。
4. CFPS(A5) 适合做中国人口学分布校准基准（persona 人口属性先验 vs CFPS 全国分布）。
5. B1/B2 只用于行为序列层面的对比，不能替代问卷回答验证。
