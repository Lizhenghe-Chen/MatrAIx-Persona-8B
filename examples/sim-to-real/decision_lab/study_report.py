"""Offline reader-facing report from completed, provenance-bearing test analysis."""
import argparse,json,html
from pathlib import Path

LABELS={'none':'AI：没有个人背景','basic':'AI：年龄与学历','rich':'AI：增加贴题真实背景','shuffled':'AI：错配附加背景','single':'AI：直接选一个答案','probability_argmax':'AI：从概率中取最大项','statistics_none':'统计模型：商品与情境','statistics_basic':'统计模型：加年龄学历','statistics_rich':'统计模型：加贴题背景','uniform':'各选项机会均等','history':'相同题目的历史比例','calibrated':'开发阶段选定的混合预测'}
EVENTS={'lower_price':'选择较便宜款','higher_customer_rating':'选择评分较高款','longer_functional_life':'选择寿命较长款','refusal':'两款都不买'}

def render(data):
    if data.get('status')!='complete_test_primary_brier_only':raise ValueError('Completed test evidence required')
    esc=lambda x:html.escape(str(x))
    methods=data['methods'];limit=max(v['brier'] for v in methods.values()) or 1
    bars=''.join(f'<div class="barrow"><span>{esc(LABELS[k])}</span><div class="track"><div class="bar" style="width:{100*v["brier"]/limit:.3f}%"></div></div><b>{v["brier"]:.3f}</b></div>' for k,v in methods.items())
    comparisons=[]
    for name,v in data['comparisons'].items():
        a,b=name.split('__to__');lo,hi=v['improvement_95_ci'];relative=v['relative_improvement']
        comparisons.append(f'<tr><td>{esc(LABELS[a])} → {esc(LABELS[b])}</td><td>{v["improvement"]:+.4f}</td><td>{"无法计算" if relative is None else f"{100*relative:+.1f}%"}</td><td>[{lo:+.4f}, {hi:+.4f}]</td><td>{"达到" if v["passes_2_percent_gate"] else "未达到"}</td></tr>')
    events=[]
    for method,summary in data['product_choice_shares'].items():
        lines=[]
        for key,v in summary['events'].items():
            chart=''.join(f'<div class="barrow"><span>{label}</span><div class="track"><div class="bar {cls}" style="width:{100*share:.3f}%"></div></div><b>{100*share:.1f}%</b></div>' for label,share,cls in [('真人',v['human_share'],'human'),('预测',v['model_probability_share'],'')])
            lines.append(f'<h4>{EVENTS[key]}</h4>{chart}<p>{v["people"]} 人，{v["eligible_tasks"]} 道有效题；预测减真人：{v["signed_gap_pp"]:+.1f} 个百分点。</p>')
        events.append(f'<details><summary>{LABELS[method]}</summary>{"".join(lines)}</details>')
    card_sections=[]
    for method,cards in data.get('per_card',{}).items():
        items=[]
        for number,(key,card) in enumerate(cards.items(),1):
            values=''.join(f'<tr><td>{esc(option)}</td><td>{100*human:.1f}%</td><td>{100*model:.1f}%</td></tr>' for option,human,model in zip(card['options'],card['human'],card['model']))
            items.append(f'<details><summary>商品组合 {number} · {card["people"]} 人 · 分布误差 {card["tv_pp"]:.1f} 个百分点</summary><p>{"样本少，仅描述，不作为稳定人群结论。" if card["small_group"] else "完整选项分布，越接近真人越好。"}</p><table><tr><th>商品属性／选项</th><th>真人</th><th>预测</th></tr>{values}</table></details>')
        card_sections.append(f'<details><summary>{LABELS[method]}：逐题分布</summary>{"".join(items)}</details>')
    subgroup=[]
    for method,rows in data['subgroups'].items():
        cells=''.join(f'<tr><td>{esc(r["field"])}</td><td>{esc(r["value"])}</td><td>{r["people"]}</td><td>{r["brier"]:.3f}</td><td>{100*r["accuracy"]:.1f}%</td><td>{"样本少，仅描述" if r["small_group"] else "描述性结果"}</td></tr>' for r in rows)
        subgroup.append(f'<details><summary>{LABELS[method]}：分人群</summary><table><tr><th>字段</th><th>人群</th><th>人数</th><th>概率误差</th><th>单选正确率</th><th>限制</th></tr>{cells}</table></details>')
    title='烘干机选择' if data['kind']=='dryer' else '瑞士家电选择'
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}：正式测试</title>
<style>body{{font:17px/1.7 system-ui,sans-serif;max-width:1100px;margin:auto;padding:28px;color:#20352f;background:#fafaf6}}h1,h2{{line-height:1.3}}section,details{{background:white;padding:22px;margin:20px 0;border:1px solid #d9e1db;border-radius:12px}}.barrow{{display:grid;grid-template-columns:minmax(160px,32%) 1fr 70px;align-items:center;gap:12px;margin:12px 0}}.track{{background:#e7ece8;height:20px;border-radius:5px}}.bar{{background:#6651a8;height:100%;border-radius:5px}}.human{{background:#26745d}}table{{border-collapse:collapse;width:100%;font-size:15px}}td,th{{padding:10px;border-bottom:1px solid #ddd;text-align:left}}summary{{cursor:pointer;font-weight:bold}}.note{{border-left:5px solid #b98525;padding:14px;background:#fff4db}}@media(max-width:650px){{body{{padding:12px}}table{{display:block;overflow:auto}}.barrow{{grid-template-columns:125px 1fr 55px;font-size:14px}}}}</style>
<h1>{title}：正式测试结果</h1><p class="note">本页是一项研究的个体预测结果。不能单独据此宣布跨研究成功，也不代表合成人群实验的成绩。</p>
<section><h2>先看模型离真人有多远</h2><p>以下是概率预测误差（Brier 分数），越低越好；0 表示每次都把全部概率给了真人实际选择。它不是错误百分比。直接单选会丢掉不确定性，因此还应结合单选正确率阅读。</p>{bars}</section>
<section><h2>改法有没有帮助</h2><p>改善为正表示后者误差更低。95% 区间跨过 0，说明这批样本不能明确排除没有改善。采用门槛为相对改善至少 2%，且改善区间完全高于 0。每项比较均按同一受访者配对重抽样 2,000 次。</p><table><tr><th>前后对比</th><th>误差下降</th><th>相对改善</th><th>95% 区间</th><th>门槛</th></tr>{''.join(comparisons)}</table></section>
<section><h2>具体会选什么</h2><p>绿色是真人比例，紫色是预测概率汇总。属性相同、不能区分两款的题目被排除；这些是选择比例，不是属性的因果效应。</p>{''.join(events)}</section>
<section><h2>每个商品组合的实际结果</h2><p>商品文字保留原问卷语言；可展开查看所有选项的实际比例。不同研究的商品组合数量不同。</p>{"".join(card_sections)}</section>
<section><h2>哪些人群表现不同</h2><p>以下为描述性分析，不从中挑最好的人群替代总体成绩；小样本不作稳定结论。</p>{''.join(subgroup)}</section>
<section><h2>如何理解结论</h2><p>混合预测采用开发样本选定的参数，模型权重为 {100*data['calibration_llm_weight']:.0f}%。它使用过部分真人答案，不能称为冷启动。历史比例查不到相同题面时回退为均匀概率，本次回退 {data['history_unseen_tasks']} 道题，不能据击败这一参照就声称超过统计方法。</p><p>数据核验标识：{esc(data['prepared_sha256'])}。完整来源、题面限制及其他研究结果须与综合报告一起阅读。</p></section></html>'''

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('analysis',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.write_text(render(json.loads(a.analysis.read_text())))
