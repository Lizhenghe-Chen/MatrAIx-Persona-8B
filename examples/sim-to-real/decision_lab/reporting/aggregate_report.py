"""One offline summary across completed studies; no pooled interval is invented."""
import argparse, html, json
from pathlib import Path
from ..evaluation.execution_quality import summarize as execution_summary
from .report_sources import section as source_section

CONTRASTS=[
 ('none__to__basic','加年龄与学历背景'),
 ('basic__to__rich','背景升级为贴题真实背景'),
 ('statistics_rich__to__rich','纯 AI 对比同背景统计模型'),
 ('rich__to__calibrated','开发选定方案对比纯 AI'),
 ('statistics_rich__to__calibrated','开发选定方案对比同背景统计模型'),
 ('shuffled__to__rich','错配附加背景对比正确背景'),
 ('single__to__rich','直接单选对比完整概率'),
]
STUDY_NAME={'dryer':'四国烘干机','swiss':'瑞士家电'}
POPULATION_NAME={'dryer':'烘干机虚拟人群','swiss':'瑞士家电虚拟人群'}
EVENTS={'lower_price':'选择较便宜款','higher_customer_rating':'选择评分较高款','longer_functional_life':'选择寿命较长款','refusal':'两款都不买'}
POPULATION_LABELS={'demographics':'只匹配年龄与学历','personality':'增加合成人格','shuffled':'同层打乱人格'}
LIMITS=['两项研究都是耐用家电选择；即使都改善，也不能推到食品、服装或实际订单转化。',
        '四个国家、三类家电各算一项研究，不是七次独立复现。',
        '公开材料可能已进入底层模型训练；题面由图形改为文字。',
        '生成的人格不是这些真人的实测信息，不能当成事实。',
        '各研究区间分别计算，不合并成一个总分；不同选项数的题不混算。']


def _verdict(comparison):
    if comparison is None:return '未包含该对照','pending'
    low,high=comparison['improvement_95_ci']
    if comparison['passes_2_percent_gate']:return '达到预先规定的相对改善门槛','pass'
    if high<0:return '出现明确退化','fail'
    if low>0:return '有改善证据，但幅度未达到采用门槛','weak'
    return '尚无明确改善证据','neutral'


def _population_verdict(comparison):
    if comparison is None:return '题组太少，只作描述','neutral'
    interval=comparison['improvement_95_ci']
    if interval is None:return '重抽样覆盖不足，未给出可靠区间','pending'
    low,high=interval
    if comparison['passes_2pp_gate']:return '达到预设改善门槛','pass'
    if high<0:return '出现明确退化','fail'
    if comparison['improvement_pp']<=0:return '未改善','neutral'
    return '分布误差下降，但未达到预设门槛','weak'


def _execution(root):
    root=Path(root);units=[]
    formal=root/'formal-v1'
    manifest=json.loads((formal/'manifest.json').read_text())
    for unit in manifest['units']:
        database=formal/(unit['name']+'.sqlite')
        record={'track':'真人个体预测','unit':unit['name'],'expected':unit['calls'],'present':database.exists()}
        if database.exists():record['execution']=execution_summary(database)
        units.append(record)
    synthetic=root/'synthetic-formal-v1'
    design=json.loads((synthetic/'manifest.json').read_text())
    expected=design['tasks_per_condition']
    for unit in design['units']:
        database=synthetic/(unit['name']+'.sqlite')
        record={'track':'合成人群','unit':unit['name'],'expected':expected,'present':database.exists()}
        if database.exists():record['execution']=execution_summary(database)
        units.append(record)
    return units


def _differences(units):
    return [u for u in units if not u['present'] or u['execution']['states'].get('complete',0)!=u['expected']]


def build(individuals,populations,roots,development=None):
    if any(s.get('status')!='complete_test_primary_brier_only' for s in individuals):
        raise ValueError('Completed individual test analysis required')
    if any(s.get('status')!='complete_population_distribution_analysis' for s in populations):
        raise ValueError('Completed population analysis required')
    kinds=[s['kind'] for s in individuals]
    if len(set(kinds))!=len(kinds):raise ValueError('Duplicate study; countries or reruns are not independent studies')
    if sorted(kinds)!=sorted(s['kind'] for s in populations):
        raise ValueError('Every study needs both an individual and a population analysis')
    if set(kinds)!=set(roots):raise ValueError('Missing study root for execution accounting')
    execution={kind:_execution(root) for kind,root in roots.items()}
    incomplete={kind:_differences(units) for kind,units in execution.items()}
    if any(incomplete.values()):
        raise ValueError('Execution accounting shows incomplete units: '+json.dumps(
            {k:[(u['track'],u['unit'],u['execution']['states'] if u['present'] else 'no checkpoint') for u in v] for k,v in incomplete.items() if v},ensure_ascii=False))
    studies=[]
    for individual in individuals:
        population=next(p for p in populations if p['kind']==individual['kind'])
        studies.append({'kind':individual['kind'],
                        'comparisons':{key:_verdict(individual['comparisons'].get(key)) for key,_ in CONTRASTS},
                        'raw_comparisons':{key:individual['comparisons'].get(key) for key,_ in CONTRASTS},
                        'calibration_llm_weight':individual['calibration_llm_weight'],
                        'population':{'methods':{k:v['mean_tv_pp'] for k,v in population['methods'].items()},
                                      'primary':population['primary_distribution_comparison'],
                                      'primary_verdict':_population_verdict(population['primary_distribution_comparison']),
                                      'properties':population['property_comparisons'].get('add_personality',{}),
                                      'shuffle_properties':population['property_comparisons'].get('shuffle_diagnostic',{}),
                                      'human_people':population['human_people'],'synthetic_people':population['synthetic_people']},
                        'shuffle_diagnostic':individual.get('shuffle_changed_content_diagnostic')})
    return {'status':'complete_aggregate_summary','independent_studies':len(studies),'studies':studies,
            'development':development or [],'execution':execution,'population_separate':True,'limits':LIMITS}


def _pct(value,digits=1):return '—' if value is None else f'{100*value:+.{digits}f}%'


def _tv(methods,name):return '—' if name not in methods else f'{methods[name]:.2f}'


def render(summary):
    if summary.get('status')!='complete_aggregate_summary':raise ValueError('Completed aggregate evidence required')
    esc=lambda value:html.escape(str(value))
    studies=summary['studies']
    def sign(value):return 'pos' if value>0 else 'neg' if value<0 else ''
    bullets=[]
    for study in studies:
        name=STUDY_NAME[study['kind']]
        for key in ['basic__to__rich','statistics_rich__to__rich','rich__to__calibrated','statistics_rich__to__calibrated']:
            label=dict(CONTRASTS)[key]
            text,kind=study['comparisons'][key]
            bullets.append(f'<li><strong>{name}·{label}</strong>：{text}。</li>')
        if study['calibration_llm_weight']==0:
            bullets.append(f'<li><strong>{name}的选参结果是纯统计模型</strong>：AI 权重为 0，这条路线即使表现好，也不能记为 AI 自身的增益。</li>')
        population=study['population']
        bullets.append(f'<li><strong>{name}的虚拟人群</strong>：加入合成人格后主对照{population["primary_verdict"][0]}。</li>')
    comparison_rows=[]
    for study in studies:
        for key,label in CONTRASTS:
            raw=study['raw_comparisons'][key];text,kind=study['comparisons'][key]
            if raw is None:
                comparison_rows.append(f'<tr><td>{STUDY_NAME[study["kind"]]}</td><td>{label}</td><td>—</td><td>—</td><td>—</td><td class="{kind}">{text}</td></tr>')
                continue
            low,high=raw['improvement_95_ci']
            comparison_rows.append(f'<tr><td>{STUDY_NAME[study["kind"]]}</td><td>{label}</td><td>{raw["improvement"]:+.4f}</td>'
                                   f'<td>{_pct(raw["relative_improvement"])}</td><td>[{low:+.4f}, {high:+.4f}]</td><td class="{kind}">{text}</td></tr>')
    score_rows=[]
    for study in studies:
        population=study['population'];methods=population['methods']
        primary=population['primary']
        interval='—' if primary is None or primary['improvement_95_ci'] is None else '[{:+.2f}, {:+.2f}]'.format(*primary['improvement_95_ci'])
        improvement='—' if primary is None else f'{primary["improvement_pp"]:+.2f}'
        score_rows.append(f'<tr><td>{POPULATION_NAME[study["kind"]]}</td><td>{population["human_people"]}</td><td>{population["synthetic_people"]}</td>'
                          f'<td>{_tv(methods,"demographics")}</td><td>{_tv(methods,"personality")}</td>'
                          f'<td>{_tv(methods,"shuffled")}</td><td>{improvement}</td><td>{interval}</td>'
                          f'<td class="{population["primary_verdict"][1]}">{population["primary_verdict"][0]}</td></tr>')
    property_rows=[]
    for study in studies:
        for event,result in study['population']['properties'].items():
            if event not in EVENTS:continue
            ci=result['improvement_95_ci']
            property_rows.append(f'<tr><td>{POPULATION_NAME[study["kind"]]}</td><td>{EVENTS[event]}</td>'
                                 f'<td>{100*result["human_share"]:.1f}%</td><td>{100*result["candidate_prediction_share"]:.1f}%</td>'
                                 f'<td class="{sign(result["absolute_error_reduction_pp"])}">{result["absolute_error_reduction_pp"]:+.2f}</td>'
                                 f'<td>{"—" if ci is None else f"[{ci[0]:+.2f}, {ci[1]:+.2f}]"}</td></tr>')
    execution_rows=[];planned=completed=retried=0
    for kind,units in summary['execution'].items():
        for unit in units:
            execution=unit['execution'];states=execution['states']
            retried+=execution['failed_attempts'];planned+=unit['expected'];completed+=states.get('complete',0)
            execution_rows.append(f'<tr><td>{STUDY_NAME[kind]}</td><td>{unit["track"]}</td><td>{unit["unit"]}</td>'
                                  f'<td>{unit["expected"]:,}</td><td>{states.get("complete",0):,}</td>'
                                  f'<td>{100*states.get("complete",0)/unit["expected"]:.1f}%</td>'
                                  f'<td>{execution["failed_attempts"]}</td><td>${execution["reserved_budget_usd"]:.2f}</td></tr>')
    identity={json.dumps(item['identity'],sort_keys=True) for units in summary['execution'].values() for unit in units
              for item in unit['execution']['identities']}
    development_rows=''.join(f'<tr><td>{STUDY_NAME.get(item.get("kind"),esc(item.get("kind","")))}</td><td>{item.get("selected_temperature","—")}</td>'
                             f'<td>{item.get("selected_llm_weight","—")}</td><td>{item.get("development_brier","—")}</td>'
                             f'<td>{esc(item.get("interpretation",""))}</td></tr>' for item in summary['development'])
    development_section=('<section><h2>之前怎样：开发阶段选了哪些参数</h2><p>这些分数来自开发集，只用于选择参数。它们不是独立测试成绩，不能当作“已经验证有效”。</p>'
                         '<table><tr><th>研究</th><th>概率缩放温度</th><th>AI 权重</th><th>开发 Brier</th><th>说明</th></tr>'+development_rows+'</table></section>') if development_rows else ''
    limits=''.join(f'<li>{esc(x)}</li>' for x in summary['limits'])
    sources=''.join(source_section(kind) for kind in sorted(summary['execution']))
    regressions=[STUDY_NAME[s['kind']] for s in studies if s['comparisons']['statistics_rich__to__rich'][1]=='fail']
    headline=(f"两项研究里大语言模型都没有超过使用同样信息的统计模型（{('、'.join(regressions))}为明确退化）。"
              "因此本轮不能把“预测更准”算作 AI 的贡献；校准路线有效的那部分来自统计模型。"
              if len(regressions)==len(studies) else
              "大语言模型与统计模型的对比未见一致优势，逐项判定见下表。")
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>决策模拟总报告</title>
<style>body{{font:17px/1.7 system-ui;max-width:1080px;margin:auto;padding:24px;background:#fafaf6;color:#20352f}}section{{background:white;border:1px solid #d9e1db;border-radius:10px;padding:18px;margin:18px 0}}table{{width:100%;border-collapse:collapse;font-size:15px}}td,th{{text-align:left;padding:9px;border-bottom:1px solid #ddd;vertical-align:top}}.pass{{color:#1a6b3c;font-weight:bold}}.fail{{color:#a3242b;font-weight:bold}}.weak{{color:#8a5a00}}.neutral{{color:#444}}.pending{{color:#7a4b93}}details{{margin:12px 0}}summary{{cursor:pointer;font-weight:bold}}.pos{{color:#1a6b3c}}.neg{{color:#a3242b}}code{{background:#f1f3f0;padding:1px 5px;border-radius:4px}}@media(max-width:600px){{body{{padding:10px}}table{{display:block;overflow:auto}}}}</style>
<h1>虚拟受访者能不能替真人做选择：本轮完整结果</h1>
<section><h2>先说结论</h2><p><strong>{headline}</strong></p><ul>{''.join(bullets)}</ul><p>下面是正式测试集的结果，不是开发阶段分数。两项研究都属于家电选择；合成人群是另一条独立路线，不与真人逐人配对。因此这里没有“跨行业普遍有效”的结论。</p></section>
<section><h2>两项真人研究：每改一步，测试表现怎样</h2><p>Brier 越小越好；“改善”为正值表示右边做法比左边更接近真人的实际选择。区间来自对真人按人重抽样 2,000 次；区间整体低于 0 表示明确退化。</p><table><tr><th>研究</th><th>比较</th><th>Brier 改善（绝对）</th><th>相对改善</th><th>95% 区间</th><th>判定</th></tr>{''.join(comparison_rows)}</table></section>
{development_section}
<section><h2>虚拟人群：分布误差与属性比例</h2><p>分布误差是真人比例与虚拟人比例的差距（百分点，越小越好）。合成人群人数与真人参照人数不同，因为只纳入年龄和学历可映射的人；真人参照全程固定，不包含真人抽样误差。</p><table><tr><th>研究</th><th>真人参照</th><th>虚拟人</th><th>只匹配人口背景</th><th>增加合成人格</th><th>同层打乱人格</th><th>主对照改善（百分点）</th><th>95% 区间</th><th>判定</th></tr>{''.join(score_rows)}</table>
<p>主对照是“只匹配人口背景”减去“增加合成人格”。下表是更细的属性选择比例，正数表示更接近真人。</p><table><tr><th>研究</th><th>选择比例</th><th>真人</th><th>虚拟人</th><th>误差减少（百分点）</th><th>95% 区间</th></tr>{''.join(property_rows)}</table></section>
<section><h2>跑完了吗：完成度、失败与费用</h2><p>共计划 {planned:,} 次调用，实际完成 {completed:,} 次，完成率 {100*completed/planned:.2f}%。运行中共有 {retried} 次确定性失败，全部经显式重试恢复，原始失败记录和费用仍保留在数据库中，没有删除历史。</p><table><tr><th>研究</th><th>轨道</th><th>单元</th><th>计划</th><th>完成</th><th>完成率</th><th>失败重试</th><th>预留上界</th></tr>{''.join(execution_rows)}</table><p>“预留上界”是按每个请求的最大可能用量估算的保守上限，不是实际账单。模型身份在全部成功回答中一致：<code>{esc('; '.join(sorted(identity)))}</code>。</p></section>
<section><h2>不能据此说什么</h2><ul>{limits}</ul></section>
<section><h2>建议</h2><ol><li>把“AI 权重为 0”的路线如实写成统计预测，不当成 AI 优化成果。</li><li>只在有正式测试区间支持时才宣称改善；未达门槛的写成“方向对但幅度不足”。</li><li>下一步应补完未准入研究的题面材料，再独立冻结新版本验证，而不是回头包装成已完成的验证。</li></ol></section>
{sources}
</html>'''



def parse_roots(values):
    roots={}
    for item in values:
        kind,sep,path=item.partition('=')
        if not sep or kind not in STUDY_NAME or not path:
            raise ValueError('Root must be kind=path for a known study')
        if kind in roots:raise ValueError('Duplicate study root')
        roots[kind]=Path(path)
    if not roots:raise ValueError('At least one study root is required')
    return roots



if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--individual',nargs='+',type=Path,required=True)
    parser.add_argument('--population',nargs='+',type=Path,required=True)
    parser.add_argument('--root',action='append',nargs='+',required=True,help='kind=path for every study directory')
    parser.add_argument('--development',nargs='*',type=Path,default=[])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Do not overwrite aggregate report')
    roots=parse_roots([item for group in args.root for item in group])
    development=[]
    for path in args.development:
        record=json.loads(path.read_text());record['kind']=path.name.split('-calibration-freeze')[0];development.append(record)
    summary=build([json.loads(p.read_text()) for p in args.individual],[json.loads(p.read_text()) for p in args.population],roots,development)
    args.output.write_text(render(summary))
    print(json.dumps({'status':summary['status'],'studies':[s['kind'] for s in summary['studies']]}))
