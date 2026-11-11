"""Offline, plain-language report for the frozen two-choice screen."""
import html
import json
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
NAMES={'dryer':'四国烘干机','swiss':'瑞士家电'}
LABELS={'background':'只有真实背景','own':'背景＋本人两次选择','other':'背景＋别人两次选择','statistics':'历史真人数据训练的统计模型'}
COLORS={'background':'#637381','own':'#137b68','other':'#b36b2c','statistics':'#6d63a8'}
E=lambda s:html.escape(str(s))


def bars(study):
    methods=study['methods'];maximum=max(m['brier']*100 for m in methods.values())*1.15
    parts=['<svg viewBox="0 0 760 260" role="img" aria-label="四种方法的预测概率误差，越低越好">']
    for tick in range(6):
        x=270+400*tick/5
        parts.append(f'<line x1="{x}" y1="25" x2="{x}" y2="225" stroke="#e3e8e6"/><text x="{x}" y="249" text-anchor="middle" font-size="13">{maximum*tick/5:.0f}</text>')
    for i,arm in enumerate(LABELS):
        y=38+i*49;value=methods[arm]['brier']*100
        parts.append(f'<text x="0" y="{y+20}" font-size="16">{LABELS[arm]}</text><rect x="270" y="{y}" width="{400*value/maximum:.2f}" height="29" rx="4" fill="{COLORS[arm]}"/><text x="{280+400*value/maximum:.2f}" y="{y+21}" font-size="16">{value:.2f}</text>')
    return ''.join(parts)+'</svg>'


def intervals(study):
    cs=study['comparisons'];xs=[0]+[100*v for c in cs.values() for v in c['improvement_95_ci']]
    low,high=min(xs),max(xs);span=max(high-low,1);low-=span*.15;high+=span*.15
    def pos(v):return 270+400*(v-low)/(high-low)
    out=['<svg viewBox="0 0 760 190" role="img" aria-label="本人记录的改善幅度及百分之九十五区间，零右侧表示改善">']
    out.append(f'<line x1="{pos(0):.2f}" y1="15" x2="{pos(0):.2f}" y2="143" stroke="#555" stroke-dasharray="4 4"/>')
    for i,(arm,c) in enumerate(cs.items()):
        y=45+i*65;a,b=[100*x for x in c['improvement_95_ci']];v=100*c['improvement']
        title='相对只有背景' if arm=='background' else '相对别人记录'
        out.append(f'<text x="0" y="{y}" font-size="16">本人记录，{title}</text><line x1="{pos(a):.2f}" x2="{pos(b):.2f}" y1="{y-6}" y2="{y-6}" stroke="#137b68" stroke-width="4"/><circle cx="{pos(v):.2f}" cy="{y-6}" r="6" fill="#137b68"/><text x="270" y="{y+22}" font-size="13">改善 {v:+.2f} 误差点；区间 [{a:+.2f}, {b:+.2f}]</text>')
    out.append(f'<text x="270" y="173" font-size="13">← 更差</text><text x="{pos(0):.2f}" y="173" text-anchor="middle" font-size="13">0</text><text x="670" y="173" text-anchor="end" font-size="13">更好 →</text>')
    return ''.join(out)+'</svg>'


def plain_option(text):
    translations={'CHF ':'瑞士法郎 ','CAD ':'加元 ','USD ':'美元 ','GBP ':'英镑 ','cu ft':'立方英尺',' kg':' 千克','Neither':'都不买','Tumble dryer':'烘干机','Smartphone':'手机','Washing machine':'洗衣机','TV ':'电视 ',
        'Brand:':'品牌：','Established':'成熟品牌','New':'新品牌','Capacity:':'容量：','10 year Energy Cost:':'十年用电费用：',
        'Customer rating:':'顾客评分：','stars':'星','Price:':'价格：','Functional life:':'使用寿命：','years':'年',
        'Env. production impact:':'生产环境影响：','Energy efficiency:':'能效：','Recyclability:':'可回收性：',
        'Repairability:':'可维修性：','Not repairable at all':'完全不可维修','Not recyclable':'不可回收',
        'Recyclable':'可回收','Very low':'很低','Very high':'很高','Medium':'中等','Low':'低','High':'高'}
    for a,b in translations.items():text=text.replace(a,b)
    return text


def example(case):
    out=['<p>按冻结顺序展示第一位评估对象的第一道预测题，未按成功与否挑选。为避免暴露个人记录的关联关系，这里不显示身份编号和个人背景原值。中文为阅读辅助，模型收到原始英文。</p>']
    for key,title in [('own_observations','AI 获得的本人两次选择'),('other_observations','错配对照获得的别人两次选择')]:
        out.append(f'<details><summary>{title}</summary>')
        for i,obs in enumerate(case[key]):
            out.append(f'<h4>已知题 {i+1}</h4><ul>')
            for j,opt in enumerate(obs['options']):out.append('<li>'+E(plain_option(opt))+(' <strong>← 当时选了这一项</strong>' if opt==obs['selected_option_text'] else '')+'</li>')
            out.append('</ul>')
        out.append('</details>')
    out.append('<h4>接下来预测另一道题：真人实际上选了什么？</h4>')
    for i,opt in enumerate(case['options']):
        out.append('<div class="option"><p>'+E(plain_option(opt))+(' <strong>← 真人实际选择</strong>' if i==case['actual_choice'] else '')+'</p>')
        for arm in ['background','own','other']:
            p=case['predictions'][arm]
            if p is None:continue
            out.append(f'<div class="prob"><span>{LABELS[arm]}</span><div class="track"><div style="width:{p[i]*100:.2f}%;background:{COLORS[arm]}"></div></div><b>{p[i]*100:.1f}%</b></div>')
        out.append('</div>')
    out.append('<details><summary>核对实际英文题面</summary><p>'+E(case['context'])+'</p><p>'+E(case['question'])+'</p><ul>'+''.join('<li>'+E(x)+'</li>' for x in case['options'])+'</ul></details>')
    return ''.join(out)


def generate():
    data=json.loads((BASE/'reports/choice-history-result.json').read_text())
    passed=data['recommend_independent_replication']
    people=data['planned_people']; aborted=data['aborted_run']; cap=data['global_attempt_cap']
    verdict='值得做一次小型独立复验，尚不能宣布优化成功。' if passed else '本轮没有达到继续门槛，暂不扩大测试或继续调提示。'
    table=[]; sections=[]; md=[]
    dm=data['studies']['dryer']['methods']
    refusal_note=f"烘干机的拒买识别为：只有背景 {dm['background']['refusal_hits']}/{dm['background']['refusal_true_tasks']}，加入本人记录 {dm['own']['refusal_hits']}/{dm['own']['refusal_true_tasks']}。这是辅助指标，不能替代整体误差和继续门槛。"
    cause_note='原因尚未查明。两条记录的信息量、模型如何利用记录、选择本身的波动，本轮没有进一步区分，因此不把任何一种解释写成已证实原因。'
    interpretation=('两项研究中，加入本人记录后的平均误差都更高，但区间都跨过零；目前没有证实整体改善，也不能断言必然有害。' if all(x['comparisons']['background']['improvement']<0 for x in data['studies'].values()) else '依据两项研究各自的误差与区间判断，不用平均结果掩盖差异。')
    for kind,s in data['studies'].items():
        c=s['comparisons']['background'];d=s['comparisons']['other'];m=s['methods']
        change=f"{c['relative_improvement']*100:+.1f}%"
        detail=('概率误差降低' if c['improvement']>0 else '概率误差增加')+f" {abs(c['relative_improvement'])*100:.1f}%"
        matched='本次误差低于' if d['improvement']>0 else '本次误差不低于'
        sentence=f"{NAMES[kind]}：加本人记录后，{detail}；{matched}别人记录。"
        table.append(f'<tr><td>{NAMES[kind]}</td><td>{m["background"]["brier"]*100:.2f}</td><td>{m["own"]["brier"]*100:.2f}</td><td>{detail}</td><td>{"通过筛查" if s["screening_point_gate"] else "未通过"}</td></tr>')
        lo,hi=c['relative_improvement_95_ci']; uncertainty='区间跨过零，改善或退化的方向仍不确定。' if lo<=0<=hi else ('区间完全高于零，这项比较支持改善。' if lo>0 else '区间完全低于零，这项比较支持退化。')
        rows=''.join(f'<tr><td>{LABELS[a]}</td><td>{v["brier"]*100:.2f}</td><td>{v["accuracy"]*100:.1f}%</td><td>{"—" if v["refusal_recall"] is None else str(v["refusal_hits"])+"/"+str(v["refusal_true_tasks"])+"（"+format(v["refusal_recall"]*100,".1f")+"%）"}</td></tr>' for a,v in m.items())
        sections.append(f'<section id="{kind}"><h2>{NAMES[kind]}：前后到底差多少？</h2><p class="lead">{sentence}</p><p>相对改善的 95% 区间为 [{lo*100:+.1f}%, {hi*100:+.1f}%]。{uncertainty}</p><p>{s["people"]} 人，每人两道未展示的题，共 {s["tasks"]} 道选择。三组使用相同人和相同预测题。</p><h3>误差越低越好</h3>{bars(s)}<p class="note">图中“误差点”＝Brier 分数×100，不是错误率。所有方法都按同一套题计分。统计模型仅作参考：它用过其他真人的训练答案，也曾用本开发集合选择参数，没有使用这两条本人记录。</p><h3>本人记录的优势是否确定？</h3>{intervals(s)}<p class="note">圆点是估计改善，横线是按人重抽样的 95% 区间。横线跨过零，表示当前小样本无法确定改善方向；不能把它解释成“已经证明无作用”。</p><div class="scroll"><table><thead><tr><th>方法</th><th>概率误差点 ↓</th><th>选中真人答案 ↑</th><th>识别出真的拒买者 ↑</th></tr></thead><tbody>{rows}</tbody></table></div><p class="note">正确率按最高概率选项计算；并列时按原选项顺序取第一项。瑞士原题没有“都不买”，因此不计算拒买识别率。</p><details class="case"><summary>看一个真实例子：给了哪些记录，预测怎样变化？</summary>{example(data["examples"][kind])}</details></section>')
        md.extend([f'## {NAMES[kind]}',sentence,f'只有背景：{m["background"]["brier"]*100:.2f} 误差点；本人记录：{m["own"]["brier"]*100:.2f}；别人记录：{m["other"]["brier"]*100:.2f}。',f'相对改善的 95% 区间 [{lo*100:+.1f}%, {hi*100:+.1f}%]。{uncertainty}',f'本人相对别人记录的绝对改善为 {d["improvement"]*100:+.2f} 误差点，95% 区间 [{d["improvement_95_ci"][0]*100:+.2f}, {d["improvement_95_ci"][1]*100:+.2f}]。',''])
    usage=data['execution']; cov=data['coverage']
    exclusions='；'.join(f'{NAMES[k]}原开发集合 {v["development_people"]} 人，合格 {v["eligible_people"]} 人，排除 {v["development_people"]-v["eligible_people"]} 人' for k,v in cov.items())
    html_text='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>两次真实选择，能否让 AI 更懂本人？</title><style>
    :root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f3f5f1;color:#20342e;font:17px/1.75 system-ui,-apple-system,"PingFang SC",sans-serif}main{max-width:1060px;margin:auto;padding:28px 22px 60px}header,section{background:#fff;border:1px solid #dce5df;border-radius:16px;padding:28px;margin-bottom:22px}h1{font-size:32px;line-height:1.4}h2{font-size:25px}h3{margin-top:28px}h4{margin-bottom:8px}.tag{font-size:14px;color:#536b60}.lead{font-size:20px;font-weight:600}.verdict{background:#eaf2ec;border-left:5px solid #137b68;padding:16px 20px}.note{font-size:14px;color:#596b62}table{width:100%;border-collapse:collapse;white-space:nowrap}th,td{text-align:left;border-bottom:1px solid #dce5df;padding:12px 14px 12px 0}th{background:#f3f7f4}.scroll{overflow:auto}a{color:#176f5e}nav{display:flex;gap:18px;flex-wrap:wrap}svg{width:100%;height:auto}svg text{fill:#233d32;font-family:system-ui,sans-serif}details{padding:14px;border:1px solid #d9e3dc;border-radius:9px;margin-top:14px}summary{cursor:pointer;font-weight:600}.option{padding:12px 0;border-bottom:1px solid #ddd}.prob{display:grid;grid-template-columns:210px 1fr 65px;align-items:center;gap:10px;font-size:14px}.track{background:#e5ebe7;height:12px;border-radius:4px;overflow:hidden}.track div{height:100%}code{overflow-wrap:anywhere;font-size:12px}li{margin:9px 0}.steps{padding-left:24px}@media(max-width:650px){main{padding:12px}header,section{padding:18px}h1{font-size:26px}h2{font-size:22px}.prob{grid-template-columns:1fr 65px}.prob span{grid-column:1/-1}.lead{font-size:18px}svg{min-width:610px}.chart{overflow-x:auto}}
    </style><main>'''
    html_text+=f'<header><p class="tag">探索性快速验证 · 2026-11-11 · 固定 DeepSeek Pro</p><h1>看过你两次选择，<br>AI 会不会更懂你？</h1><p>这次不增加虚构人设，只给模型看两次真实选择，再预测同一个人的另外两次选择。我们还故意换成别人的记录，检查模型是否真的利用了个人差异。</p><p class="verdict"><strong>本轮决定：{verdict}</strong></p><nav><a href="#results">先看结果</a><a href="#design">实验怎么做</a><a href="#dryer">烘干机图表</a><a href="#swiss">瑞士家电图表</a><a href="#limits">结论边界与材料</a></nav></header>'
    html_text+=f'<section id="results"><h2>先看结论：有没有改善？</h2><p>{interpretation}</p><div class="scroll"><table><thead><tr><th>研究</th><th>只有背景 ↓</th><th>加本人记录 ↓</th><th>加记录后的误差变化</th><th>是否值得继续</th></tr></thead><tbody>{"".join(table)}</tbody></table></div><p class="note">前两列是概率误差点，越低越好；下方区间以改善为正、变差为负。筛查门槛在运行前固定：两套都降低至少 2%，且本人记录都优于别人记录。通过筛查也不等于获得独立验证。</p></section>'
    html_text+=f'<section id="design"><h2>实验怎么做：相同题目，只换提供的信息</h2><ol class="steps"><li>每套固定抽取 {people} 名真人，每人抽两次已知选择和另外两道预测题。不根据答案好不好预测来挑人或挑题。</li><li>三个对照分别是：只有真实背景；背景加本人记录；背景加同年龄学历粗分组、同研究分层的别人记录。</li><li>给模型完整商品信息、原英文题面及已知记录。预测题的真人答案不发送给模型，只在本地用于评分。</li><li>固定同一模型和提示，不微调、不调整温度、不根据分数反复修改。每人两题先取平均，再汇总研究结果。</li></ol><p>{exclusions}。烘干机排除 9 人因年龄学历无法映射、1 人没有合格供体；瑞士排除 34 人因年龄学历无法映射。合格人群按原研究分层比例抽样，没有放宽错配条件。</p><p>另有每套 4 人用于格式试跑，不计入结果。正式评估 {people*12} 次，试跑 24 次；每次只预测一道题。</p><details><summary>“概率误差”为什么比只看答对更合适？</summary><p>假设最后真人选了甲。预测甲有 60% 的可能，比只给甲 10% 的预测更接近事实。Brier 评分比较所有选项概率与实际选择，越低越好；它不会把两种预测都简单归为“猜中／猜错”。图表为了易读乘以 100，但它仍不是错误率或百分点。</p><p>把概率最高项当作单选另算正确率。两种指标回答不同问题，不能混为一谈。</p></details></section>'
    html_text+=''.join(sections).replace('<svg','<div class="chart"><svg').replace('</svg>','</svg></div>')
    html_text+=f'<section id="limits"><h2>最终判断与下一步</h2><p>{refusal_note}</p><p>{cause_note}</p><p class="verdict"><strong>{verdict}</strong></p><p>这是两项已有家电研究的小样本筛查。它只能评价这两次选择记录、当前提示与固定模型的作用。没有证明所有历史行为都无用，也没有证明模拟器已经能替代真人。</p><ul><li>原开发数据之前已用于研究，不能把本轮称为全新独立测试。</li><li>题目是随机划分，未证明历史时间顺序；预测的是没展示过的题，不是未来购买。</li><li>两条记录属于真实问卷中的商品选择，不是模型猜出来的经历，也不是实际支付订单。</li><li>统计参照用过其他真人训练答案，也曾用本开发集合选择参数，没有使用这两条个人记录；本轮不声称公平比较了全部算法。</li><li>错配记录只用于诊断；供体可能重复。区间以固定供体和固定模型答卷为条件，未单独估计供体分配和重复调用的波动。</li><li>模型最高概率并列时取原顺序第一项；保留该规则和并列计数，避免事后改成更有利答案。</li></ul><h3>一次输入问题，以及如何处理</h3><p>最初批次的已知选择使用数字，却未明确编号起点。发现可能误解后暂停，作废 {aborted["attempts"]} 次请求，未计算效果分数。新版直接给出被选商品的完整文本，重新冻结并试跑；旧记录保留审计，不混入本轮结果。</p><h3>执行与可追溯材料</h3><p>完成 {usage["complete"]} 次，共发起 {usage["attempts"]} 次，重试 {usage["retries"]} 次。输入 {usage["prompt_tokens"]:,} token、输出 {usage["completion_tokens"]:,} token。按高峰价、输入无缓存估算成功请求费用为 ${usage["peak_no_cache_usage_estimate_usd"]:.3f}；保守费用预留 ${usage["reserved_usd"]:.3f}，两者都不是账单。旧批次按相同口径估算 ${aborted["peak_no_cache_usage_estimate_usd"]:.3f}，保守预留 ${aborted["reserved_usd"]:.3f}。连同作废批次共 {usage["attempts"]+aborted["attempts"]} 次请求，成功请求费用合计估算 ${usage["peak_no_cache_usage_estimate_usd"]+aborted["peak_no_cache_usage_estimate_usd"]:.3f}，保守预留合计 ${usage["reserved_usd"]+aborted["reserved_usd"]:.3f}。总请求上限为 {cap} 次，总费用上限为 10 美元。</p><p><a href="choice-history-result.json">汇总数据与区间</a> · <a href="../specs/pilots/choice-history-protocol.json">运行前冻结方案</a> · <a href="../docs/两次选择快速验证.md">文字结论</a></p><p>模型：{E(data["model"]["model"])}；服务指纹：<code>{E(data["model"]["system_fingerprint"])}</code>。输入哈希：<code>{data["input_sha256"]}</code></p><p>来源：<a href="https://zenodo.org/records/10046247">烘干机作者数据</a>、<a href="https://doi.org/10.1007/s10603-023-09556-5">研究论文</a>；<a href="https://doi.org/10.7910/DVN/YKVLTR">瑞士家电作者数据</a>、<a href="https://doi.org/10.1016/j.jclepro.2024.143968">研究论文</a>。<a href="https://api-docs.deepseek.com/quick_start/pricing/">模型与价格说明</a>。</p></section></main></html>'
    (BASE/'reports/choice-history.html').write_text(html_text)
    intro=['# 两次真实选择，能否让 AI 更懂本人？','',f'**本轮决定：{verdict}**','',
           f'这是探索性快速筛查：两项已有家电研究，每套 {people} 人，每人两道已知选择与另外两道预测题，比较只有背景、本人记录、别人记录。既有开发数据不称为全新独立测试。',
           interpretation, '完整图表和示例见[离线图解报告](../reports/choice-history.html)。概率误差点＝Brier×100，不是错误率。','']
    ending=['## 怎样解释、是否继续',verdict,refusal_note,cause_note,'没有通过筛查不等于证明所有行为信息都无用。这里只检验两条同研究商品选择记录，不做人格因果解释，不宣称未来购买、纯合成人群或完整原版 MatrAIx 的效果。',
        '统计模型只作为参考：它使用其他真人训练答案，也曾用本开发集合选择参数，未使用这两条本人记录；不是同信息算法排名。',
        '筛查门槛在评分前冻结：两套研究本人记录相对只有背景的 Brier 均下降至少 2%，并且均优于别人记录。95% 区间跨零时只能标为不确定。','',
        '## 运行与复算',f'连同作废批次共发起 {usage["attempts"]+aborted["attempts"]} 次请求，按高峰无缓存价格估算成功请求费用合计 ${usage["peak_no_cache_usage_estimate_usd"]+aborted["peak_no_cache_usage_estimate_usd"]:.3f}，并非账单。',f'最初批次因已知选择的数字编号起点不明确，在效果评分前作废 {aborted["attempts"]} 次请求。新版直接提供被选商品文本，旧记录保留审计，不混入结果。总请求上限 {cap} 次，总预算仍为 10 美元。',f'成功 {usage["complete"]} 次，尝试 {usage["attempts"]} 次，重试 {usage["retries"]} 次。成功请求按高峰、无缓存价格估算 ${usage["peak_no_cache_usage_estimate_usd"]:.3f}；保守费用预留 ${usage["reserved_usd"]:.3f}，不是实际账单。',
        '私有冻结输入、供体映射和 SQLite 检查点位于 `~/.local/share/matraix-decision-lab/choice-history-v2`，不随 Git。公开汇总不含真人编号、密钥及完整背景记录。',
        '代码入口：`python -m decision_lab.studies.choice_history <prepare|pilot|evaluation>`；评分：`python -m decision_lab.evaluation.choice_history`；报告：`python -m decision_lab.reporting.choice_history`。从 sim-to-real 目录执行；已有冻结或评分禁止覆盖。评分命令加 `--check` 可不调用模型地核验已有结果；报告可从汇总 JSON 重建。',
        '[冻结方案](../specs/pilots/choice-history-protocol.json) · [汇总结果](../reports/choice-history-result.json)',
        '[烘干机作者数据](https://zenodo.org/records/10046247) · [瑞士家电作者数据](https://doi.org/10.7910/DVN/YKVLTR)']
    (BASE/'docs/两次选择快速验证.md').write_text('\n\n'.join(x for x in intro+md+ending if x)+'\n')


if __name__=='__main__':generate()
