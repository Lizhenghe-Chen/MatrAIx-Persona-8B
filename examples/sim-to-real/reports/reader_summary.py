"""Shared plain-language interpretation; scores are editorial, evidence is loaded."""
import json
from pathlib import Path

def render():
    root=Path(__file__).resolve().parent
    data=json.loads((root.parent/'decision_lab/reports/cross-study-v1/cluster-summary.json').read_text())
    rows={r['study']:r for r in data['rows']}
    names=[('origin','商品产地、价格与评分','购物选品中优先探索'),('pew168','诈骗风险判断','通用问卷中相对较好'),('tshirt','T恤商品选择','值得继续验证'),('pew13','一般购物看法','适合探索群体倾向'),('swiss','家电规格选择','有信息，仍不够准'),('german','德国番茄包装','仍明显落后于统计参照'),('pew111','网购与达人购物','有信息，但优势有限'),('drone','无人机配送','接近等概率预测'),('shoes','运动鞋意愿打分','未超过等概率预测'),('packaging','包装与都不买','当前明显薄弱')]
    table=''
    for key,name,note in names:
        r=rows[key];v=100*r['ai_over_uniform']
        table+=f'<tr><th>{name}</th><td>{v:+.1f}%</td><td>{note}</td></tr>'
    return '''<section id="plain-assessment"><span class="number">白话总评 · 2026-11-13</span>
<h2>从“只能谨慎参考”，进步到“可辅助研究”；还不能代替真人</h2>
<div class="grid2"><article class="card"><h3>优化前：约35／100分</h3><p>容易把有分歧的问题答成近乎全票。可以帮助提出想法，不宜把模拟比例直接当作市场事实。</p></article><article class="card"><h3>优化后：约55／100分</h3><p>保留概率、采用已测表现更好的模型后，多项人群比例预测改善。可以辅助研究，重要决策仍需真人数据校验。</p></article></div>
<p class="callout warn"><strong>这两个分数是主观综合评价，不是准确率、置信度或实验计算结果。</strong>20分差距不能写成“准确率提升20%”。“优化前”指已测的旧提示、单选等流程参照，不是对官方MatrAIx 8B权重或整个产品的完整评分。</p>
<h3>到底提升了什么？</h3><p>假如真人中六成人选甲、四成人选乙，旧方法可能让几乎所有虚拟人都选甲；优化后更可能接近六四开。<strong>它更会估计“多少人选什么”，还没有充分证明更会判断“张三选甲、李四选乙”。</strong></p>
<p>最明确的收益来自保留各选项概率并合理汇总，以及已测条件下的模型选择。不能把这些收益主要归功于“合成人格变得更真实”。有真人历史答案时，直接统计同类人的选择通常仍然更准。</p>
<h3>哪个方向最好？先区分两个问题</h3><p><strong>优化幅度大：</strong>早期一般购物看法问卷的分布误差从43.41降至18.08个百分点。但误差降低很多，不等于已经很准确。</p><p><strong>在已测购物任务中更有预测信息：</strong>商品产地、价格、评分明确的选择题，以及T恤商品选择相对突出。它们仍没有超过对应的真人数据统计参照。</p>
<div class="table-wrap"><table><caption>当前统一对照中的部分领域：比“各选项等概率”少错多少？</caption><thead><tr><th>任务</th><th>个人概率误差的相对改善</th><th>怎么用大白话理解</th></tr></thead><tbody>'''+table+'''</tbody></table></div>
<p class="small">数字直接读取冻结的cluster-summary.json。正数表示比各选项等概率更准，负数表示更差；不是答对率。不同研究的样本、选项数、难度和信息条件不同，这只是当前任务的表现概览，不是普遍成立的领域排行榜。表格列出部分领域，不替代完整研究表。</p>
<h3>为什么属性明确的商品题可能更适合？</h3><p>价格、产地、评分等比较依据直接摆在题面上；“会不会买、给几分、是否都不买”还依赖真实需求、预算、已有商品和个人经历。<strong>这是合理解释，尚不是本实验确认的因果机制。</strong></p>
<h3>两个容易误会的地方</h3><p><strong>运动鞋：</strong>早期人群分布误差明显改善，后续个人预测却没有超过等概率参照。因此不能仅凭“改进幅度大”就推荐它。</p><p><strong>包装与拒买：</strong>保留概率缓解过拒买比例低估，但后续测试仍然薄弱。不能据此预测哪些消费者一定不买。</p>
<h3>现在建议怎么用？</h3><ol><li><strong>优先探索属性明确的商品方案比较：</strong>比较价格、产地、评分、规格组合，先做相对偏好研究。</li><li><strong>一般购物态度用于提出假设：</strong>保留概率，再用小规模真人样本检查方向与比例。</li><li><strong>有历史真人数据，先建立统计参照：</strong>不要因为人格模拟听起来先进，就舍弃更准确的简单方法。</li><li><strong>暂不直接承担：</strong>个人购买预测、拒买识别、实际销量或转化率预测。这些用途证据仍不足。</li></ol>
<p class="callout"><strong>最终结论：</strong>优化后的方法更值得作为研究辅助，但“更好的群体比例估计”与“更懂对应的真人”之间仍有距离。当前最稳妥的定位是帮助比较方案、提出假设，并接受真人数据检验。</p>
<p class="source">核查：<a href="index.html#all-studies">全部研究对照</a> · <a href="index.html#probability">优化前后分布误差</a> · <a href="index.html#anchor">给AI相同历史比例后的测试</a> · <a href="../decision_lab/reports/cross-study-v1/cluster-summary.json">冻结数据</a></p></section>'''
