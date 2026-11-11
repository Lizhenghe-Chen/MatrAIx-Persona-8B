"""Offline population report; never imply synthetic/real individual pairing."""
import argparse,json,html
from pathlib import Path
from .report_sources import section as source_section
from .study_report import EVENTS

LABELS={'demographics':'只匹配年龄与学历','personality':'增加 MatrAIx 合成人格','shuffled':'在同背景人群中打乱人格'}

def render(data):
    if data.get('status')!='complete_population_distribution_analysis' or data.get('individual_accuracy_computed') is not False:
        raise ValueError('Complete, separate-population evidence required')
    esc=lambda value:html.escape(str(value))
    def bars(human,model):
        return ''.join(f'<div class="row"><span>{label}</span><div class="track"><div class="bar {style}" style="width:{value*100:.3f}%"></div></div><b>{value*100:.1f}%</b></div>' for label,value,style in [('真人',human,'human'),('虚拟人预测',model,'')])
    comparison=data['primary_distribution_comparison']
    if comparison is None:
        finding='本研究的相同商品组合人数较少，逐题分布只作描述，不据此判定合成人格有效。'
    elif comparison['improvement_95_ci'] is None:
        finding='重抽样时部分商品组合缺少覆盖，未给出可靠区间；不能宣布达到采用门槛。'
    else:
        low,high=comparison['improvement_95_ci']
        verdict='达到预设改善门槛' if comparison['passes_2pp_gate'] else '未达到预设改善门槛'
        finding=f'加入合成人格后，分布误差下降 {comparison["improvement_pp"]:+.2f} 个百分点，95% 区间 [{low:+.2f}, {high:+.2f}]；{verdict}。下降为负表示变差。'
    tables=[];properties=[];cards=[]
    for name,method in data['methods'].items():
        tables.append(f'<tr><td>{LABELS[name]}</td><td>{method["mean_tv_pp"]:.2f}</td></tr>')
        events=[]
        for key,value in data['property_choices'][name].items():
            human=data['property_choices']['human'][key]
            events.append(f'<h4>{EVENTS[key]}</h4>{bars(human["share"],value["share"])}<p>真人 {human["people"]} 人；虚拟人 {value["people"]} 人。仅纳入该属性能区分商品的题目。</p>')
        properties.append(f'<details><summary>{LABELS[name]}</summary>{"".join(events)}</details>')
        entries=[]
        for number,card in enumerate(method['cards'],1):
            choices=''.join(f'<h4>{esc(option)}</h4>{bars(h,m)}' for option,h,m in zip(card['options'],card['human'],card['model']))
            warning='真人样本少于 20 人，仅作描述。' if card['small_human_group'] else ''
            entries.append(f'<details><summary>商品组合 {number}：误差 {card["tv_pp"]:.2f} 个百分点</summary><p>真人 {card["human_people"]} 人，虚拟人 {card["synthetic_people"]} 人。{warning}</p>{choices}</details>')
        cards.append(f'<details><summary>{LABELS[name]}：全部商品组合</summary>{"".join(entries)}</details>')
    effect_rows=[]
    for contrast,events in data.get('property_comparisons',{}).items():
        label='增加合成人格' if contrast=='add_personality' else '打乱人格与原分配比较（诊断）'
        for event,result in events.items():
            interval=result['improvement_95_ci']
            ci='覆盖不足，不报告区间' if interval is None else f'[{interval[0]:+.2f}, {interval[1]:+.2f}]'
            effect_rows.append(f'<tr><td>{label}</td><td>{EVENTS[event]}</td><td>{result["absolute_error_reduction_pp"]:+.2f}</td><td>{ci}</td></tr>')
    property_effects='<table><tr><th>比较</th><th>选择比例</th><th>误差减少（百分点）</th><th>95% 区间</th></tr>'+''.join(effect_rows)+'</table>' if effect_rows else '<p>本文件未包含属性比例区间，不能据比例点估计宣布改善。</p>'
    groups=[]
    for field,values in data['subgroups'].items():
        rows=''.join(f'<tr><td>{esc(value)}</td><td>{LABELS[name]}</td><td>{result["mean_tv_pp"]:.2f}</td></tr>' for value,methods in values.items() for name,result in methods.items())
        label={'age_bracket':'年龄段','education_group':'学历组'}.get(field,field)
        groups.append(f'<details><summary>{label}</summary><table><tr><th>人群</th><th>设置</th><th>分布误差（百分点）</th></tr>{rows}</table></details>')
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>合成人群：能否复现真人选择</title>
<style>body{{font:17px/1.7 system-ui;max-width:1050px;margin:auto;padding:24px;background:#fafaf6;color:#20352f}}section,details{{background:white;border:1px solid #d9e1db;border-radius:10px;padding:18px;margin:18px 0}}summary{{cursor:pointer;font-weight:bold}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:10px;border-bottom:1px solid #ddd}}.row{{display:grid;grid-template-columns:110px 1fr 70px;gap:10px;align-items:center}}.track{{background:#e7ece8;height:20px}}.bar{{height:100%;background:#6651a8}}.human{{background:#26745d}}@media(max-width:600px){{body{{padding:10px}}table{{display:block;overflow:auto}}}}</style>
<h1>虚拟人群，能否选出接近真人的结果？</h1><section><h2>先说结论</h2><p>{finding}</p><p>本页只评价人群比例，不计算“这个虚拟人猜中了哪个真人”。它也不能证明虚拟人的人格是真人的实际人格。</p></section>
{source_section(data['kind'])}
<section><h2>人群从哪里来，怎样比较</h2><p>真人参照来自原调查中留出的 {data['human_people']} 人。另生成 {data['synthetic_people']} 名虚拟人，匹配研究分组、年龄段和学历的分布，并分配原研究实际出现的商品题面。虚拟人没有配套的真人答案。</p><p>三组使用相同的人群与题面：第一组只给年龄学历；第二组再给生成的人格属性；第三组在相同背景层内打乱整块人格。人格不是对这些真人的实测信息，不能把它写成事实。打乱组是诊断，不是人格的因果效应实验。</p></section>
<section><h2>整体比例相差多少</h2><p>分布误差越低越好。例如二选一时真人 40% 选甲、虚拟人预测 55%，误差为 15 个百分点。先在每个研究分组内平均商品组合，再按真人样本人数汇总；不把不同商品的 A、B 位置混在一起。</p><table><tr><th>给虚拟人的信息</th><th>分布误差（百分点）</th></tr>{''.join(tables)}</table><p>瑞士家电的这一汇总只作描述，不能代替正式采用判定。</p></section>
<section><h2>价格、性能和不购买的具体比例</h2><p>绿色表示真人，紫色表示虚拟人预测。保留完整概率汇总，未强行把每人变成一个确定答案。下表分别比较每种选择比例的绝对误差，正数表示更接近真人。区间跨 0 表示改善仍不明确；不作跨属性的合并采用判定，也不解释为价格或性能的因果效应。</p>{property_effects}{''.join(properties)}</section>
<section><h2>逐题看差在哪里</h2><p>保留原题语言和商品属性。人数较少的组合尤其容易波动。</p>{''.join(cards)}</section>
<section><h2>分人群查看</h2><p>这些结果用于发现问题，不从中挑最好的人群代表总体。below_bachelor 表示本科以下；bachelor_plus 表示本科及以上。</p>{''.join(groups)}</section>
<section><h2>最终应怎样使用</h2><p>{finding}</p><p>区间只衡量重新抽取虚拟人的波动，真人调查比例被当作固定参照，未包括真人抽样误差、模型版本变化或题面转写误差。单项研究不能证明跨行业通用，也不能代表真实购买转化率。请结合个体预测报告与来源审查阅读。</p></section></html>'''

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('analysis',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output.write_text(render(json.loads(args.analysis.read_text())))
