"""Present the matching audit without changing frozen experiment results."""
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).parent
FILE = ROOT / 'study/09_方法审查/audit-results.json'


def section():
    from retail_reader_report import table
    data = json.loads(FILE.read_text())
    synthetic = data['synthetic']
    labels = ['18–64 岁，本科以下', '18–64 岁，本科及以上', '65 岁及以上，本科以下', '65 岁及以上，本科及以上']
    rows, bars = [], []
    for i, key in enumerate(synthetic['target_stratum_pct']['shed']):
        values = [synthetic['target_stratum_pct'][s][key] for s in ('shed','pew','anes')]
        rows.append([labels[i], '25.0%', *[f'{v:.1f}%' for v in values]])
        bars.append(f'<div style="margin:18px 0"><strong>{labels[i]}</strong>' + ''.join(
            f'<div class="note">{label}：{value:.1f}%</div><div style="height:10px;background:#edf0ee;border-radius:4px">'
            f'<div style="height:100%;width:{value}%;background:{color};border-radius:4px"></div></div>'
            for label,value,color in [('抽到的合成画像',25,'#8061a6'),('SHED 加权真人',values[0],'#1b7960')])+'</div>')
    matching = table(['年龄与学历组合','合成画像原始占比','SHED 真人','Pew 诈骗调查真人','ANES 真人'],rows,
                     '原始抽样是每组一样多；后面三列是各调查符合纳入条件的加权分布。合成画像的背景组和人格组按这些比例汇总。')
    models = synthetic['rounds']['models']
    changes=[]
    for prefix,label in [('flash','DeepSeek Flash'),('pro','DeepSeek Pro'),('qwen','内网 Qwen')]:
        pair=next(p for p in models['comparisons'] if p['before']==prefix+'-A' and p['after']==prefix+'-B')
        old=pair['methods']['original'];new=pair['methods']['common_population_weight']
        ci=lambda x:f"{x['ci95'][0]:+.2f} 至 {x['ci95'][1]:+.2f}"
        judgment=('平均改善；但诈骗题退化，仍未通过跨问卷门槛' if prefix=='flash' else
                  '改善或退化尚不明确' if prefix=='pro' else '应从“平均明确退化”改为“方向尚不明确”；公共支出题仍退化')
        changes.append([label,f"{old['gain_pp']:+.2f}<br>区间 {ci(old)}",f"{new['gain_pp']:+.2f}<br>区间 {ci(new)}",judgment])
    corrected=table(['加上年龄学历，是否改善？','原汇总口径','两组使用相同权重','审查后的解释'],changes,
                    '数字为误差减少的百分点，正数更好；括号对应 95% 区间。答卷、真人参照和 2,000 次重抽样完全相同，只更换汇总权重。')
    profile=data['real_profiles']
    verified=sum(v['item_scores_recomputed'] for v in synthetic['rounds'].values())+sum(v['item_scores_recomputed'] for v in profile.values())+data['later']['pew13']['item_scores_recomputed']
    pew=data['later']['pew13']['margins_against_eligible_source']
    shoe=data['later']['shoes']['margins_against_eligible_source']
    pew_low=sum(x['source_pct'] for x in pew['Income']['categories'] if x['label'] in ('20 to under $30,000','30 to under $40,000'))
    sample_low=sum(x['evaluated_pct'] for x in pew['Income']['categories'] if x['label'] in ('20 to under $30,000','30 to under $40,000'))
    neff='、'.join(f"{label} 约 {profile[s]['effective_sample_size_before_item_missingness']:.0f} 人" for s,label in [('shed','SHED'),('pew','Pew'),('anes','ANES')])
    first=synthetic['rounds']['first']['overall']
    max_shift=max(abs(v['original']-v['common_valid_item_weight']) for v in first.values() if v is not first['A'])
    return f'''<section class="section" id="matching-audit">
<p class="section-label">方法审查 · 2026-11-10 · 原答卷复算，没有新增模型请求</p>
<h2>画像有没有尽量匹配真人？只匹配了一部分，不能说已经完整匹配</h2>
<div class="callout warn"><strong>需要收紧的结论：</strong>前两轮只做了年龄与学历四组的匹配，没有匹配收入、性别、地区、购物经历与人格的联合分布。第三轮以后的真人背景来自本人原记录，但“背景对应本人”不等于“抽中的人代表整个美国市场”。这些实验没有测到完整人群匹配后的性能上限。</div>
<h3>1. 前两轮：抽样比例不同，评分时再调整每组的分量</h3>
<p>首轮 1,200 条合成画像，每组 300 条；模型对比每组 60 条，共 240 条。这样能让每个组都有足够案例，但原始画像中 65 岁及以上占 50%，并不接近三份调查的约 22%。<strong>加权</strong>就是让各组在最终平均值中占不同的分量，不是更改个体答案或补齐这个人的收入、人格。</p>
{matching}
<details><summary>用条形图看原始画像和 SHED 人群差在哪</summary><figure><h3>相同的 0–100% 刻度，各组并非都占四分之一</h3>{''.join(bars)}<figcaption>紫色为抽样占比，绿色为官方权重下的真人占比。上述表格提供全部准确数值；Pew、ANES 各自使用自己的目标比例。</figcaption></figure></details>
<p>四项人格只由 MatrAIx 生成，没有真人实测的决策风格、风险容忍度、价值观、尽责性分布可供校准。第三轮的额外人格也是在同年龄学历组内随机配给真人。因此，额外人格收益小，<strong>只能说明这套随机合成提示没有稳定增益，不能说明真实人格没有用。</strong></p>
<h3>2. 找到一处比较口径问题，已经复算</h3>
<p>早期“只给情境”组直接平均，“加年龄学历”和“再加人格”两组按真人分组比例加权。用它们评价“加背景的作用”，混入了汇总方式的差异。下表把同一批原答卷改用相同权重，结果另存为审查补充，不覆盖历史记录。</p>
{corrected}
<p><strong>影响范围：</strong>Qwen 的平均变化不能再说成明确变差。三模型在相同输入条件下的优劣顺序没有因此颠倒；“加人格”前后本来就使用相同权重，主比较未受这处差异影响。首轮人格增益仍为 <strong>5.58</strong> 点，但仍集中于公共支出题。</p>
<p class="note">另检查了逐题无效／插补答案带来的分组比例变化：让模拟与真人在每一道题使用相同的有效答案分组权重后，首轮背景组、人格组的综合误差改变均小于 {max_shift:.3f} 点；第二轮这些组改变均小于 0.008 点。这项细节没有改变主要判断。修正后的所有逐题分数见审查数据。</p>
<h3>3. 真人背景确实来自本人，但抽样代表性仍有限</h3>
<div class="table-wrap"><table><thead><tr><th>实验</th><th>审查确认了什么</th><th>仍不能声称什么</th></tr></thead><tbody>
<tr><td>第三轮，三份通用问卷</td><td>重新读取源包，按冻结种子重抽样，与正式名单完全一致；年龄、学历及贴题背景由原字段转换。正式样本与试跑不重叠。</td><td>240 人不是 240 个等信息量案例。权重不同，用“权重有效样本量”作粗略诊断为 {neff}；这不是完整复杂抽样设计效应。</td></tr>
<tr><td>第四轮，商品与网购</td><td>原记录、抽样名单与商品卡对应关系可重建。三份的正式、试跑、统计训练集合互不重叠。</td><td>实际学历分界是“大专及以上”，因为包装源数据把 AA／BA 合并；不是原计划的本科分界。产地四组人数为 72／60／48／60。Pew 附加字段实际为收入、上网频率，不是就业。这些调整已在执行方案记录。</td></tr>
<tr><td>第五轮，Pew 购物问卷</td><td>使用对应真人的五项背景；按原官方权重评分。选中 240 人与原网络样本的年龄、学历分布接近。</td><td>未进一步平衡收入。年收入 2万–4万美元在符合条件源样本中占 {pew_low:.1f}%，评估样本加权后占 {sample_low:.1f}%。收入分布差距为 {pew['Income']['distance_pp']:.2f} 点。</td></tr>
<tr><td>第五轮，运动鞋与 Amazon</td><td>运动鞋原两波背景、商品属性、答案和抽样重新关联后与冻结文件一致。Amazon 按过去记录预测未来，未用 MatrAIx 合成人格。</td><td>运动鞋按四种实验设计均衡抽样，不按全国人口配额；家庭收入分布与原研究样本相差 {shoe['Household income']['distance_pp']:.2f} 点。Amazon 只覆盖愿意提供订单且历史充足的账户。</td></tr>
</tbody></table></div>
<p class="note">这里的“分布差距”是各档占比差的绝对值加总后除以二；不是每个档位都偏了这么多。以上来源样本也是特定调查或研究样本，不自动等于美国全体消费者。</p>
<h3>4. 这次查过什么，还有哪些证据不足</h3>
<ul>
<li><strong>分数复核：</strong>从原答卷独立计算了 {verified} 个“题目 × 设置”的分布误差：首轮 54 个、模型比较 162 个、真人背景 144 个、最新 Pew 52 个。最大偏差小于 0.00000001 点；不包括所有统计模型、全部置信区间和 Amazon 数值的独立重算。</li>
<li><strong>答案隔离：</strong>在第三轮背景构造和第四轮完整提示中，把目标答案、调查权重换成明显不同的值，输入不变；同一真人仍使用对应背景。原问卷跳题字段只决定展示资格。该检查不证明模型训练时没见过公开题目。</li>
<li><strong>分割说明：</strong>第三轮 SHED 的 48 名试跑者包含在统计参照训练记录中，但不包含正式 240 人。没有正式答案泄漏；不能把这一轮写成三个集合全部互斥。第四轮及第五轮冻结划分为互斥集合。</li>
<li><strong>不确定性：</strong>多数条件每人只生成一次；重抽样区间没有计入重新调用模型的随机波动、模型版本漂移和多次探索的选择偏差。真人实验的区间也不是完整复现官方分层、整群抽样后的全国人口置信区间。</li>
<li><strong>比较公平性：</strong>统计方法使用其他真人的同题答案训练，模型通常没有做同样专项训练；部分早期商品统计方法还有额外设计信息。运动鞋已补做输入字段对齐检查，其他任务仍需逐项说明，不能把差异全归因模型架构。</li>
<li><strong>问卷还原：</strong>任务保留了目标题和商品属性，但不等于完整复制真人界面、上下文和作答流程。产地左右位置是固定随机重建；这类差异可能影响选择。没有独立新问卷／新季度的完整再验证。</li>
</ul>
<div class="callout blue"><strong>审查后的判断：</strong>现有实验足以发现“这些固定方案会过度集中、遗漏拒买、未稳定超过真人统计”及若干有效改进；不足以断言“MatrAIx 在充分匹配后仍无用”。后续应把“真实本人背景预测”和“合成人群匹配模拟”分开，后者至少先核对年龄、学历、性别、收入、地区及关键购物经历的分布，报告共同分布和覆盖缺口，再比较完全相同的提示、输出方式与权重。</div>
<details><summary>来源、复算命令与审查边界</summary>
<p><a href="../09_方法审查/audit-results.json">聚合审查数据及逐题重算</a> · <a href="../../audit_matching.py">独立审查代码</a> · <a href="../01_首轮归档/reference.json">首轮真人参照</a> · <a href="../03_提示与背景/固定方案.md">真人背景方案</a> · <a href="../06_北美电商选品/固定方案.md">商品实验执行方案</a>。</p>
<p>ANES 最初提到的 2,308 人包括 245 名纸笔受访者；实际使用网页样本选前权重的 2,063 人，再排除年龄或学历不可用，剩 1,927 人。选前权重没有误用成选后权重。<a href="https://electionstudies.org/wp-content/uploads/2026/04/anes_timeseries_2024_userguidecodebook_accessible_html.html">官方代码本及样本构成</a>。</p>
<p>旧运行核验实际检查文件、哈希、完成率与人数对应，没有独立重算全部分数。此次将其字段改名为“评分文件与覆盖核验”，并把本次真正独立复算的范围另列，避免过度表述。完整冻结结果未改写。</p>
<pre>uv run --python .venv/bin/python --with pyreadstat==1.3.7 --with pyreadr==0.5.9 --with scikit-learn==1.9.1 --with pandas==3.0.3 --with numpy==2.5.0 --with httpx python examples/sim-to-real/audit_matching.py
.venv/bin/python examples/sim-to-real/retail_report.py</pre>
<p>复算需要本机受访者关联文件及登录下载的原始数据包；共享版只包含聚合结果和代码。未调用云端或内网模型，未更改冻结画像、原始答案或正式评分。</p></details>
</section>'''


def write_standalone(fragment, css):
    # Fragment links are relative to 08_购物预测; both folders share a parent.
    page=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MatrAIx 画像匹配与方法审查</title><style>{css}</style></head><body><main><p><a href="../index.html">返回全部实验报告</a></p>{fragment}</main></body></html>'''
    (FILE.parent/'index.html').write_text(page)
