"""Offline, reader-facing report for the fixed internal replication."""
from html import escape
import json
from pathlib import Path
import re

ROOT=Path(__file__).parent
OUT=ROOT/'study/10_匹配与商品复验'
NAMES={'coarse':'只匹配年龄与学历','matched':'再匹配性别与收入','matched_traits':'再加四项合成人格',
       'choice':'每题只选一项','probability':'给各选项概率','statistics':'其他真人训练的统计方法',
       'qwen':'内网 Qwen','pro':'DeepSeek Pro'}


def label(key):
    return ' · '.join(NAMES.get(x,x) for x in key.split('/'))


def executive(data):
    match=data['matching'];p=data['products']
    before=match['summary']['qwen/matched']['mean_run_tv_pp']
    after=match['summary']['pro/matched']['mean_run_tv_pp']
    origin=p['origin']['summary'];pack=p['packaging']['summary']
    return f'''<div class="callout blue" id="latest-conclusion"><strong>第六轮复验更新了哪些判断？</strong>
<p><strong>人口分布对齐仍不够，换模型的影响更大。</strong>同样输出概率、同样匹配年龄学历性别收入，Qwen 的13题平均误差为 {before:.2f}，Pro 为 {after:.2f} 个百分点，三次运行均改善。补齐人群匹配没有明显降低误差；追加四项合成人格也未达到2点采用门槛。</p>
<p><strong>概率输出应按任务验收。</strong>产地选择从 {origin['choice']['mean_run_tv_pp']:.2f} 到 {origin['probability']['mean_run_tv_pp']:.2f}，变化不明确；包装选择从 {pack['choice']['mean_run_tv_pp']:.2f} 到 {pack['probability']['mean_run_tv_pp']:.2f}。其他真人训练的统计方法分别为 {origin['statistics']['mean_run_tv_pp']:.2f} 和 {pack['statistics']['mean_run_tv_pp']:.2f}，仍更接近真人。产品任务只测试了内网 Qwen，不能把这里的不足推断为 Pro 的成绩。</p>
<p class="note">本轮沿用已有公开真人数据，每个条件重跑三次。它补强了方法比较，没有增加独立真人样本。<a href="#revalidation">逐题分布、三次结果和采用判断</a>。</p></div>'''


def section():
    from retail_reader_report import table
    from retail_report import QUESTIONS
    path=OUT/'results.json'
    if not path.exists():
        return '<section class="section" id="revalidation"><h2>第六轮：人群匹配与商品决策复验正在运行</h2><p>方案和技术试跑已冻结。结果完成前不用于采用建议。旧实验有问题的权重对照已从常规选择器撤下，负面结果仍保留。</p><a href="../10_匹配与商品复验/protocol.json">查看冻结方案</a></section>'
    data=json.loads(path.read_text());protocol=json.loads((OUT/'protocol.json').read_text())
    match=data['matching'];product=data['products'];names={k:label(k) for k in match['summary']}
    endpoint=lambda v:f'{v:+.3f}' if 0<abs(v)<.005 else f'{v:+.2f}'
    row=lambda a:f"{a['gain_pp']:+.2f}（{endpoint(a['ci95'][0])} 至 {endpoint(a['ci95'][1])}）"
    verdict=lambda a:('三次均改善，达到本任务门槛' if a['passes'] else
                     '有小幅改善，但不足2点' if a['ci95'][0]>0 else
                     '平均误差上升，未通过' if a['ci95'][1]<0 else '变化方向尚不明确')
    matching_rows=[[names[k],f"{v['mean_run_tv_pp']:.2f}",*[f'{x:.2f}' for x in v['tv_by_run_pp']]] for k,v in match['summary'].items()]
    matching_table=table(['模型与背景','三次平均误差','第1次','第2次','第3次'],matching_rows,'每次分别计算13题平均分布误差，再平均三次；单位百分点，越低越好。')
    match_pairs=table(['只改变什么','平均误差减少（95%区间）','每次运行的改善','判断'],[
        [escape(names[x['before']]+' → '+names[x['after']]),row(x),' / '.join(f'{v:+.2f}' for v in x['gain_by_run_pp']),verdict(x)] for x in match['comparisons']])
    products_rows=[];product_pairs=[]
    for survey,title in [('origin','产地、价格与评分选择'),('packaging','包装选择与拒买')]:
        d=product[survey]
        for k,v in d['summary'].items():
            products_rows.append([title,NAMES[k],f"{v['mean_run_tv_pp']:.2f}",' / '.join(f'{x:.2f}' for x in v['tv_by_run_pp']),f"{v['accuracy_pct']:.1f}%",f"{v['brier']:.4f}"])
        for x in d['comparisons']:
            product_pairs.append([title,NAMES[x['before']]+' → '+NAMES[x['after']],row(x),verdict(x)])
    product_table=table(['任务','方法','三次平均分布误差','三次各自误差','逐人正确率','逐人概率误差'],products_rows,
                        '分布误差以百分点计；逐人概率误差为各选项平方误差之和，越低越好。正确率对每次回答取最高概率选项；每人先平均自己的题。两个任务不合成总分。')
    product_pair_table=table(['任务','只改变什么','平均误差减少（95%区间）','判断'],product_pairs)
    refusal=product['packaging'];refusal_rows=[['真人实际选择',f"{refusal['human_opt_out_pct']:.1f}%",'参照值']]
    for key,v in refusal['summary'].items():
        refusal_rows.append([NAMES[key],f"{v['opt_out_pct']:.1f}%",f"{v['opt_out_recall_pct']:.1f}%"])
    refusal_table=table(['方法','预估都不买的比例','真实拒买被识别的比例'],refusal_rows,
                        '“识别”按最高概率选项判断。一个方法可以估准总体拒买比例，却仍认不准具体哪些人拒买。')
    attribute_names={'China':'选中国产品','United States':'选美国产品','cheaper':'选便宜款','higher-rated':'选高评分款'}
    attribute_table=table(['同类商品二选一','真人实际比例','只选一项','给各项概率'],[
        [attribute_names[a['question']],*[f'{v:.1f}%' for v in (a['human_pct'][0],a['predicted_pct'][0],b['predicted_pct'][0])]]
        for a,b in zip(product['origin']['items']['choice'],product['origin']['items']['probability'])],
        '各属性只统计能区分两款商品的题目，四行的分母不同；这不是同一道题的四个选项，不能相加。模型列为三次平均比例。')
    concentration=table(['方法','至少95%选同一项的卡数','至少99%的卡数','100%的卡数'],[
        [NAMES[c],*[' / '.join(str(r[str(t)]) for r in v['concentration_by_run']) for t in (95,99,100)]]
        for c,v in product['packaging']['summary'].items()],
        '包装任务共16张可比较卡；每格按第1／2／3次列出。概率方法统计汇总概率，不把它强行变成每人一票。')
    gains={m:next(x for x in match['comparisons'] if x['before']==m+'/coarse' and x['after']==m+'/matched') for m in ('qwen','pro') if m+'/coarse' in match['summary']}
    change=lambda v:f"误差{'减少' if v>=0 else '增加'} {abs(v):.2f} 点"
    matching_find='；'.join(f"{NAMES[m]} {change(x['gain_pp'])}，{verdict(x)}" for m,x in gains.items())
    format_find='；'.join(f"{title}{change(product[s]['comparisons'][0]['gain_pp'])}，{verdict(product[s]['comparisons'][0])}" for s,title in [('origin','商品产地选择'),('packaging','包装与拒买')])
    best=min(match['summary'],key=lambda k:match['summary'][k]['mean_run_tv_pp'])
    direct=[x for x in match['comparisons'] if x['before'].startswith('qwen/') and x['after'].startswith('pro/')]
    model_pair=next(x for x in direct if x['before']=='qwen/matched')
    model_find=f"同样匹配四项人口背景、同样给概率，Qwen 误差 {match['summary']['qwen/matched']['mean_run_tv_pp']:.2f}，Pro 为 {match['summary']['pro/matched']['mean_run_tv_pp']:.2f}；减少 {model_pair['gain_pp']:.2f} 点，三次均改善"
    payload={'result':data,'names':names,'labels':NAMES,'questions':QUESTIONS}
    return f'''<section class="section" id="revalidation"><p class="section-label">第六轮 · 对照事先确定、字段修正留痕 · 每个条件独立生成三次</p>
<h2>换模型有收益；概率改善了包装选择，却没有改善产地选择</h2>
<p class="lead">这次补齐人口分布匹配、比较两种模型，并把商品任务的单选改为概率。<strong>共7,200份正式答卷，每个条件运行三次。</strong>结论以三次平均和逐题表现共同判断。</p>
<div class="callout warn"><strong>证据范围：</strong>沿用已研究过的真人数据，是内部复验，不是新增独立真人验证。商品任务各240人。官方 MatrAIx 8B 权重仍未单独评测。</div>
<details><summary>本轮也发现并修正了一处问题：高中及以下标签漏映射</summary><p>运行中的覆盖核对发现，Pew 原标签“H.S. graduate or less”与初版映射表写法不一致，误排除了610条有效背景记录。发现后立即停止，修正映射并重建匹配目标；完整有效参照从3,517人恢复到4,090人。修正发生在查看正式结果分数之前。</p><p>输入发生变化的285份正式答卷、10份技术试跑作废，不进入分析。其余仅在请求全文哈希完全相同时复用；任何字段或问题变化均重新生成，没有依据预测好坏选择答卷。如今任何未识别的非缺失标签都会直接报错，不再静默排除。<a href="../10_匹配与商品复验/mapping-correction.json">修正、作废与复用清单</a> · <a href="../10_匹配与商品复验/eligibility-audit.json">完整纳入与排除核对</a>。</p></details>
<div class="three"><article class="card"><h3>人群匹配有用吗？</h3><p>{matching_find}。</p><p class="note">这里只检验共同可对齐的年龄、学历、性别、收入四项；不称为完整人格匹配。</p></article>
<article class="card"><h3>概率输出能帮选品吗？</h3><p>{format_find}。</p><p class="note">两种任务分别判断；单题和拒买的实际比例见下方。</p></article>
<article class="card"><h3>模型应该怎样选？</h3><p>{model_find or '尚无完整的两模型比较'}。</p><p class="note">平均分最低的组合是 {names[best]}，但最低点估计不自动等于差异明确，更不等于适用于所有任务。</p></article></div>
<p><strong>四项合成人格的结果：</strong>在同一批四项匹配画像上，再加决策风格、风险容忍度、核心价值观、尽责性，Qwen 的误差只减少 {match['comparisons'][2]['gain_pp']:.2f} 点，Pro 减少 {match['comparisons'][3]['gain_pp']:.2f} 点；均未达到2点门槛。Pro 有稳定的小幅改善，但这四项人格仍是生成设定，不是真人的测量，不能据此声称还原了真实人格。</p>
<p><strong>读图方法：</strong>“分布误差”比较整群人的选项比例，越小越好。真人60%选择某款，模型估计70%，二选一误差就是10个百分点。它不同于猜中某个具体受访者答案的“逐人正确率”。</p>
<details><summary>数据怎么来、如何实施、匹配到什么程度？</summary>
<h3>数据、实施与边界</h3>
<div class="table-wrap"><table><thead><tr><th>实验</th><th>输入与真人参照</th><th>控制了什么</th></tr></thead><tbody>
<tr><td>人群匹配</td><td>Pew Wave 13：4,317名网络受访者中，保留四项背景可对齐、13题均有有效答案的 {match['reference_people']:,} 人，按官方权重建立参照。每组240条原生生成的北美画像。</td><td>各组都展示相同四项字段，所有组和模型使用完全相同的分析权重，均输出各项概率。先比较如何选人，再在四项匹配组加四项合成人格。</td></tr>
<tr><td>商品选择与拒买</td><td>产地和包装实验各240人；与原来的统计训练样本保持分离。保留商品卡、贴题真人背景与问题顺序。</td><td>同一人仅改变输出一个选项还是各项概率，其余提示一致；真实背景仅发内网 Qwen。</td></tr>
<tr><td>三次重复运行</td><td>同样输入、非思考模式、温度0.7、top_p=1、最多1,536个输出token；每个条件生成三次。</td><td>全部三次都计入结果，没有挑最好的一次。正式答卷 {protocol['formal_requests']:,} 份；104份技术试跑不评分。</td></tr>
</tbody></table></div>
<p><strong>不能冒称更细的匹配：</strong>两边收入档只能可靠合并为“低于10万美元／至少10万美元”，年龄合并为“18–64／65岁及以上”，学历为“本科以下／本科及以上”。源问卷的二元性别标签按操作规则对应合成标签，这不是把性别认同与生理性别视为同一测量。原生地区只能固定北美，美国是共同调查情境；没有匹配美国各地区。</p>
<p><strong>为什么没有再跑一组四项完全相同的“真人背景”？</strong>在这四个粗字段上，多维匹配后的可见背景已经与对应类别相同；不论标签叫合成还是实际，模型看到的文本相同。额外复制一组不能检验画像的真实程度。这里比较的是人群分布和额外人格提示。</p>
<p>合成人群没有对应真人，因此匹配实验不计算逐人正确率；商品实验有真实对应受访者，会同时报告比例与逐人指标。</p></details>
<h3>1. 人群组成是否真的更接近</h3><p>只匹配年龄学历时，四项背景组合的分布与真人相差 <strong>{match['joint_distribution_distance_pp']:.2f}</strong> 个百分点；多维匹配后的加权组合分布与目标一致，这是设计保证，不是模型预测成绩。粗化后，两组各有 {match['unique_visible_backgrounds']['coarse']}、{match['unique_visible_backgrounds']['matched']} 种可见背景；240条画像不等于240种不同文本背景。</p>
<div id="rvDemographics" class="rv-chart" style="height:390px" role="img" aria-label="合成人群与目标人口构成"></div><p class="note">图中每个年龄、学历、性别、收入分类的占比单独比较，不跨字段加总。绿色是目标真人比例，紫色是只匹配年龄学历的合成比例。</p>
<h3>2. 同样的问题，不同匹配、人格和模型的平均误差</h3>
<div id="rvMatchingOverall" class="rv-chart" style="height:370px" role="img" aria-label="匹配与模型平均误差"></div>{matching_table}{match_pairs}
<p class="note">柱越短越接近真人。比较表中的正数表示改善，负数表示变差；95%区间跨过零时，变化方向尚不明确。“达到门槛”还要求改善至少2点，并且三次运行都改善。这里的判定是单项对照的研究标准，多项比较未作整体错误率校正。</p>
<label for="rvMatchingContrast">选择要比较的改动</label><select id="rvMatchingContrast"></select>
<div id="rvMatchingItems" class="rv-chart" style="height:650px" role="img" aria-label="匹配实验全部题目的误差"></div>
<label for="rvMatchingQuestion">查看某一道题的实际答案分布</label><select id="rvMatchingQuestion"></select><p id="rvMatchingOriginal" class="note"></p>
<div id="rvMatchingDistribution" class="rv-chart" style="height:370px" role="img" aria-label="匹配实验真人与模型选项分布"></div><div id="rvMatchingOptions"></div>
<p class="note">误差图显示每次先评分、再平均三次的主指标；选项分布图显示三次平均比例。两种计算顺序不同，不能用合并比例的误差替换主指标。概率不是受访者本人报告的心理概率。</p>
<h3>3. 商品任务：输出概率是否真的改善选择</h3>
<div id="rvProductOverall" class="rv-chart" style="height:370px" role="img" aria-label="商品任务平均误差"></div>{product_table}{product_pair_table}
<p class="note">“其他真人训练的统计方法”不调用大模型：用正式评估以外的真人选择，学习价格、产地、包装及可用背景与选项的关系，再预测这240人。它没有看这240人的目标题答案。“给概率”保留模型对多个选项的犹豫，不能理解为真人自己报告了这些概率。</p>
<h4>为什么产地选择没有整体改善？</h4>{attribute_table}
<p>概率输出修正了“几乎总选高评分款”的倾向，却在中国产、美国产、便宜款三项比例上离真人更远。这些偏差互相抵消，四项平均误差没有降低。因此不能因为答案变得不极端，就认定选品更准确。</p>
<label for="rvProductSurvey">选择商品实验</label><select id="rvProductSurvey"><option value="origin">产地、价格和评分</option><option value="packaging">包装和拒买</option></select>
<label for="rvProductContrast">选择比较方法</label><select id="rvProductContrast"><option value="choice">只选一项与给概率</option><option value="statistics">真人统计参照与给概率</option></select>
<div id="rvProductItems" class="rv-chart" style="height:560px" role="img" aria-label="商品任务全部题组误差"></div>
<label for="rvProductQuestion">查看一个属性选择或商品卡</label><select id="rvProductQuestion"></select><div id="rvProductCard"></div>
<div id="rvProductDistribution" class="rv-chart" style="height:370px" role="img" aria-label="商品选择实际分布"></div><div id="rvProductOptions"></div>
<p class="note">产地比较选择中国产、美国产、较便宜款、较高评分款的比例，只纳入该属性能够区分两款的题。包装按16张选择卡评分，包含“都不买”。统计方法学习了其他真人答案，因此仍不是纯模型架构对决。</p>
<h3>4. 重点检查“都不买”，避免高估需求</h3><div id="rvRefusal" class="rv-chart" style="height:340px" role="img" aria-label="真人与模型拒买比例"></div>{refusal_table}
<p><strong>改善的是总体比例，识别人还很弱。</strong>拒买估计从 {refusal['summary']['choice']['opt_out_pct']:.1f}% 升至 {refusal['summary']['probability']['opt_out_pct']:.1f}%，更接近真人的 {refusal['human_opt_out_pct']:.1f}%。但取最高概率作为答案时，只识别出 {refusal['summary']['probability']['opt_out_recall_pct']:.1f}% 的真实拒买选择；逐人正确率为 {refusal['summary']['probability']['accuracy_pct']:.1f}%，原单选为 {refusal['summary']['choice']['accuracy_pct']:.1f}%，其变化区间跨零。不能据此认定已经能找准“不想买的人”。</p>
<details><summary>检查是否仍出现近乎全票，以及重复运行是否一致</summary>{concentration}<p>匹配问卷的六个模型／背景组合、每组13题，在三次概率输出中都没有达到95%的单项集中度。不过它们依然存在10–16点平均分布误差，说明不再全票只是基本检查，不等于预测合格。</p><p>包装16张卡里，概率输出有14张误差下降，仍有2张变差。上方选择卡工作台保留所有卡，不只展示改善的例子。</p></details>
<h3>哪些旧结论撤下，哪些继续保留？</h3><p><strong>撤下：</strong>从主报告的常规对照选择器移除早期混用权重的“只给情境→加画像”比较，不再将其作为纯画像增益。原记录仍供审查追溯，统一权重复算另存。<strong>保留：</strong>回答过度一致、拒买偏低、跨任务不稳定、未超过统计参照等有证据支持的负面发现。审查未证明整份数据或完整实验无效，因此不删除原数据。</p>
<div class="callout blue"><strong>怎样看待本轮：</strong>只在某个任务达到“平均改善至少2点、区间高于零、三次均有改善”时，才把改动记录为该任务的内部复验结果。匹配精度更高不保证预测更准；群体比例更准不保证识别具体消费者。下一步仍需要没有参与这些研究的新调查、独立用户或新时间窗验证。</div>
<details><summary>区间、缺失与复算说明</summary><p>2,000次重抽样按人保留其全部商品选择；合成实验按固定人口组合抽样。两种合成人群独立重抽，使用同一画像的模型与人格对照配对重抽。合成实验以真人参照为固定值；商品实验同步重抽真人答案和对应预测。区间以已生成的三次答卷、既定训练集为条件，不能覆盖全部模型随机性、重新训练统计方法的不确定性或官方复杂调查抽样误差。三次结果分别保留，不据某次结果调整样本、提示或匹配字段。</p>
<p>每个条件、每次运行达到98%完成率后，只在共同完成的对象上比较。发生失败可按检查点续跑，真实背景不改投云端。模型输入仅包括允许字段与问题，答案、权重和原受访者编号不发送。</p>
<p>本次最终完成7,200／7,200份正式答卷与104／104份技术试跑。6次返回不符合格式的尝试（5次概率越界，1次非法单选）按既定规则重试后成功；没有最终缺失答卷。统计参照只拟合一次，表格中三次相同的值表示同一参照，没有把它算作三次独立训练。</p>
<pre>uv run --python .venv/bin/python --with pyreadstat==1.3.7 --with httpx --with numpy==2.5.0 python examples/sim-to-real/revalidation.py prepare
.venv/bin/python examples/sim-to-real/revalidation_score.py
.venv/bin/python examples/sim-to-real/retail_report.py</pre>
<p class="source"><a href="../10_匹配与商品复验/protocol.json">冻结方案与数据哈希</a> · <a href="../10_匹配与商品复验/results.json">逐题、逐次与区间结果</a> · <a href="../10_匹配与商品复验/scoring-checks.json">评分与选项映射检查</a> · <a href="../10_匹配与商品复验/experiment-status.json">旧实验处置记录</a> · <a href="https://www.pewresearch.org/dataset/american-trends-panel-wave-13/">Pew 原始调查</a> · <a href="https://itemresponsewarehouse.org/tables/bankert_2023_consumer_origin/">产地实验</a> · <a href="https://itemresponsewarehouse.org/tables/staples_2020_beer_eco_labels/">包装实验</a></p></details>
<script id="rv-data" type="application/json">{json.dumps(payload,ensure_ascii=False).replace('<',chr(92)+'u003c')}</script>
<script>{(ROOT/'revalidation_charts.js').read_text()}</script>
</section>'''


def write_standalone(fragment):
    template=(ROOT/'retail_reader_template.html.tmpl').read_text()
    css=re.search(r'<style>(.*?)</style>',template,re.S).group(1)
    page=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MatrAIx 第六轮：匹配与商品复验</title><style>{css}</style><script src="../08_购物预测/vendor/echarts.min.js"></script></head><body><main><p><a href="../index.html">返回全部实验报告</a></p>{fragment}</main></body></html>'''
    (OUT/'index.html').write_text(page)


if __name__=='__main__':
    write_standalone(section())
