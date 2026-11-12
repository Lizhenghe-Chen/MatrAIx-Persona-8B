"""Offline reader report for the frozen six-study formal run. No model calls."""
import argparse
import html
import json
from pathlib import Path

from .registry import OUT

STUDY_NAME = {'anes': '美国公共支出', 'pew168': '美国诈骗风险', 'shed': '美国消费调整',
              'pew13': '美国购物看法', 'dryer': '四国烘干机', 'swiss': '瑞士家电规格',
              'drone': '美国无人机配送', 'shoes': '美国运动鞋意愿（打分）'}
STUDY_KIND = {'anes': '政策态度', 'pew168': '风险判断', 'shed': '消费应对',
              'pew13': '购物行为', 'dryer': '商品选择', 'swiss': '商品选择',
              'drone': '配送服务选择', 'shoes': '商品意愿打分'}
STUDY_REGION = {'anes': '美国', 'pew168': '美国', 'shed': '美国', 'pew13': '美国',
                'dryer': '北美与西欧', 'swiss': '西欧', 'drone': '美国', 'shoes': '美国'}
ARM_LABEL = {'original': '原生提示·单选', 'output_only': '原生提示·概率',
             'prompt_only': '预测提示·单选', 'optimized': '预测提示·概率',
             'history': '统计：全体历史比例', 'stratum_history': '统计：同层历史比例',
             'uniform': '机会均等', 'attribute_logit': '统计：商品属性回归',
             'attribute_rating': '统计：商品属性评分模型'}
REFERENCE_ORDER = ['stratum_history__to__optimized', 'history__to__optimized',
                   'attribute_logit__to__optimized', 'attribute_rating__to__optimized']


def _pct(value, digits=1):
    return '—' if value is None else f'{100 * value:+.{digits}f}%'


def _available(comparison):
    return bool(comparison) and comparison.get('available', True)


def _verdict(comparison):
    if not _available(comparison):
        return '不可估计', 'pending'
    low, high = comparison['improvement_95_ci']
    if comparison.get('passes_brier_gate'):
        return '相对改善 ≥2% 且区间高于零', 'pass'
    if high < 0:
        return '明确退化', 'fail'
    if low > 0:
        return '方向为正但不足 2%', 'weak'
    return '无明确证据', 'neutral'


def _card_verdict(comparison):
    if not _available(comparison):
        return '不可估计', 'pending'
    low, high = comparison['improvement_95_ci']
    if comparison.get('passes_2pp_gate'):
        return '改善 ≥2 个百分点且区间高于零', 'pass'
    if high < 0:
        return '明确退化', 'fail'
    if low > 0:
        return '方向为正但不足 2 个百分点', 'weak'
    return '无明确证据', 'neutral'


def _reading_section(raw, rows):
    """Where an arm is a point prediction scored as a distribution, say so next to the number."""
    esc = lambda value: html.escape(str(value))
    lines, degenerate, flat = [], [], []
    for study, entry in raw['studies'].items():
        arms = entry['results']['arms']
        get = lambda a: (arms.get(a) or {}).get('brier')
        uniform, original, optimized = get('uniform'), get('original'), get('optimized')
        if None in (uniform, original, optimized):
            continue
        lines.append(f'<tr><td>{esc(STUDY_NAME.get(study, study))}</td><td>{original:.4f}</td>'
                     f'<td>{optimized:.4f}</td><td>{uniform:.4f}</td>'
                     f'<td>{100 * (uniform - optimized) / uniform:+.1f}%</td></tr>')
        if original > uniform:
            degenerate.append(STUDY_NAME.get(study, study))
        if optimized >= uniform:
            flat.append(STUDY_NAME.get(study, study))
    if not lines:
        return ''
    text = ('<p><strong>这一节是读法提醒，不是新结果。</strong>“原生”臂只交一个选项，'
            '把它当分布来算 Brier 时会因为过度自信而偏高，所以“优化比原生好 X%”主要说明'
            '“交出概率比只报一个选项更像分布”，不等于预测力提高。真正能说明信息量的是与'
            '“每档等可能”和统计参照的比较。</p>')
    if flat:
        text += (f'<p class="fail">在 { "、".join(flat) } 上，优化组合的 Brier 等于或高于'
                 '“每个选项等可能”：模型没有提供超过“永远答中间/等分”的信息。</p>')
    if degenerate:
        text += (f'<p>原生臂在 { "、".join(degenerate) } 上比“等可能”还差，这是点预测被当分布评分的'
                 '必然结果，不应读成“建模失败”。</p>')
    return ('<section><h2>怎么读这两个臂</h2>' + text +
            '<table><tr><th>研究</th><th>原生·单选</th><th>预测·概率</th><th>每档等可能</th>'
            '<th>优化相对等可能</th></tr>' + ''.join(lines) + '</table></section>')


def summarize(data):
    if data.get('status') != 'complete_formal_cross_study':
        raise ValueError('Completed formal results required')
    rows = {}
    for study, entry in data['studies'].items():
        result = entry['results']
        brier = result['contrasts']['original__to__optimized']
        card = result['card_contrasts']['original__to__optimized']
        statistical = None
        statistical_name = None
        for key in REFERENCE_ORDER:
            label = key.split('__to__')[0]
            if _available(result['contrasts'].get(key)):
                statistical = result['contrasts'][key]
                statistical_name = label
                break
        rows[study] = {
            'people': entry['people'], 'cards': entry['cards'],
            'estimable_cards': entry.get('cards_with_at_least_20_people'),
            'kind': STUDY_KIND.get(study, '未分类'), 'region': STUDY_REGION.get(study, '未知'),
            'brier': brier, 'card': card,
            'statistical': statistical, 'statistical_name': statistical_name,
            'brier_verdict': _verdict(brier), 'card_verdict': _card_verdict(card),
            'statistical_verdict': _verdict(statistical),
            'supports_versus_own_baseline': bool(
                _available(brier) and brier.get('passes_brier_gate')
                and _available(card) and card.get('passes_2pp_gate')),
        }
    supporting = [s for s, r in rows.items() if r['supports_versus_own_baseline']]
    beats_statistics = [s for s, r in rows.items() if _available(r['statistical'])
                        and r['statistical'].get('passes_brier_gate')]
    kinds = {rows[s]['kind'] for s in supporting}
    regions = {rows[s]['region'] for s in supporting}
    return {'rows': rows, 'supporting': supporting, 'beats_statistics': beats_statistics,
            'kinds': sorted(kinds), 'regions': sorted(regions),
            'cross_study_gate': len(supporting) >= 3 and len(kinds) >= 2 and len(regions) >= 2,
            'raw': data}


def render(summary):
    rows, raw = summary['rows'], summary['raw']
    count = len(rows)
    few = count < 4
    arms_run = list(raw['arms'])
    ablation = 'output_only' in arms_run and 'prompt_only' in arms_run
    references = [a for a in ['history', 'stratum_history', 'attribute_logit', 'attribute_rating', 'uniform']
                  if any(a in e['results']['arms'] for e in raw['studies'].values())]
    label_arm = lambda a: ARM_LABEL.get(a, a)
    esc = lambda value: html.escape(str(value))
    badge = lambda text, kind: f'<span class="{kind}">{esc(text)}</span>'

    main_rows = []
    for study, row in rows.items():
        b, c = row['brier'], row['card']
        main_rows.append(
            f'<tr><td>{esc(STUDY_NAME[study])}</td><td>{row["people"]}</td>'
            f'<td>{_pct(b["relative_improvement"])}</td>'
            f'<td>[{b["improvement_95_ci"][0]:+.4f}, {b["improvement_95_ci"][1]:+.4f}]</td>'
            f'<td>{badge(*row["brier_verdict"])}</td>'
            + (f'<td>{c["improvement_pp"]:+.2f}</td><td>[{c["improvement_95_ci"][0]:+.2f}, '
               f'{c["improvement_95_ci"][1]:+.2f}]</td><td>{badge(*row["card_verdict"])}</td>'
               if _available(c) else '<td>—</td><td>—</td><td>' + badge(*row['card_verdict']) + '</td>')
            + '</tr>')
    arm_rows = []
    for study, entry in raw['studies'].items():
        arms = entry['results']['arms']
        cells = ''.join(f'<td>{arms[a]["brier"]:.4f}</td>' if arms[a]['brier'] is not None else '<td>—</td>'
                        for a in raw['arms'])
        reference_cells = ''.join(f'<td>{arms[a]["brier"]:.4f}</td>' if arms[a]['brier'] is not None else '<td>—</td>'
                                  for a in ['history', 'stratum_history', 'attribute_logit',
                                            'attribute_rating', 'uniform'] if a in arms)
        arm_rows.append(f'<tr><td>{esc(STUDY_NAME[study])}</td>{cells}{reference_cells}</tr>')
    statistical_rows = []
    for study, row in rows.items():
        c = row['statistical']
        if not _available(c):
            statistical_rows.append(f'<tr><td>{esc(STUDY_NAME[study])}</td><td>—</td>'
                                    f'<td>—</td><td>—</td><td>{badge(*row["statistical_verdict"])}</td></tr>')
            continue
        statistical_rows.append(
            f'<tr><td>{esc(STUDY_NAME[study])}</td><td>{esc(ARM_LABEL[row["statistical_name"]])}</td>'
            f'<td>{_pct(c["relative_improvement"])}</td>'
            f'<td>[{c["improvement_95_ci"][0]:+.4f}, {c["improvement_95_ci"][1]:+.4f}]</td>'
            f'<td>{badge(*row["statistical_verdict"])}</td></tr>')
    refusal_rows = []
    for study, entry in raw['studies'].items():
        arms = entry['results']['arms']
        for qid in entry['results']['refusal_options']:
            refusal_rows.append(f'<tr><td>{esc(STUDY_NAME[study])}</td><td>{esc(qid)}</td>'
                                + ''.join(f'<td>{100 * (arms[a]["refusal"].get(qid) or 0):.1f}%</td>'
                                          for a in ['original', 'optimized'])
                                + f'<td>{100 * (arms["history"]["refusal"].get(qid) or 0):.1f}%</td></tr>')
    full_rows = []
    for study, entry in raw['studies'].items():
        for key, c in entry['results']['contrasts'].items():
            left, _, right = key.partition('__to__')
            rows_ci = '—' if not _available(c) else f'[{c["improvement_95_ci"][0]:+.4f}, {c["improvement_95_ci"][1]:+.4f}]'
            full_rows.append(f'<tr><td>{esc(STUDY_NAME[study])}</td>'
                             f'<td>{esc(ARM_LABEL.get(left, left))} → {esc(ARM_LABEL.get(right, right))}</td>'
                             f'<td>{_pct(c.get("relative_improvement")) if _available(c) else "—"}</td>'
                             f'<td>{rows_ci}</td><td>{badge(*_verdict(c))}</td></tr>')
    execution, budget = raw['execution'], raw['budget']
    supporting = summary['supporting']
    boost = (f'{count} 套研究全部显示：优化组合大幅优于原生流程' if all(
        rows[s]['brier'].get('passes_brier_gate') for s in rows) else '优化组合并非在所有研究都优于原生流程')
    headline = (
        f'{boost}（Brier 相对改善 '
        + '、'.join(f'{STUDY_NAME[s]} {_pct(rows[s]["brier"]["relative_improvement"])}' for s in rows)
        + f'）。但其中 {len(supporting)} 套同时达到“分布误差改善 ≥2 个百分点且区间高于零”：'
        + (f'{ "、".join(STUDY_NAME[s] for s in supporting) }。' if supporting else '没有。')
        + (f'并且在有统计参照的 {len([s for s in rows if _available(rows[s]["statistical"])])} 套研究中，'
           f'优化组合在 Brier 上全部显著差于统计参照。' if not summary['beats_statistics'] else
           f'其中 {len(summary["beats_statistics"])} 套在 Brier 上超过统计参照。'))
    gate_text = ('跨研究门槛已满足' if summary['cross_study_gate'] else '跨研究门槛未满足')
    if few:
        gate_text = (f'本计划只有 {count} 套研究，“至少三套”的跨研究门槛在设计上不可能满足；'
                     '因此逐套判定，不作跨研究概括')
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>跨研究正式验证：{count} 套研究</title>
<style>body{{font:17px/1.7 system-ui;max-width:1140px;margin:auto;padding:24px;background:#fafaf6;color:#20352f}}
section{{background:white;border:1px solid #d9e1db;border-radius:10px;padding:18px;margin:18px 0}}
table{{width:100%;border-collapse:collapse;font-size:15px}}td,th{{text-align:left;padding:9px;border-bottom:1px solid #ddd;vertical-align:top}}
.pass{{color:#1a6b3c;font-weight:bold}}.fail{{color:#a3242b;font-weight:bold}}.weak{{color:#8a5a00}}.neutral{{color:#444}}.pending{{color:#7a4b93}}
code{{background:#f1f3f0;padding:1px 5px;border-radius:4px}}@media(max-width:600px){{body{{padding:10px}}table{{display:block;overflow:auto}}}}</style>
<h1>同一套优化，换{count}份问卷还成立吗？</h1>
<section><h2>先说结论</h2><p><strong>{esc(headline)}</strong></p>
<p><strong>{esc(gate_text)}。</strong>预设门槛是“至少三套新研究同时通过、覆盖两类任务和两个地区”。</p>
<p>“优化组合”指把提示改成“预测这套画像代表的人会怎么选”，并让模型交出每个选项的概率；对照是原生 MatrAIx 问卷指令加单选。{len(arms_run)} 个臂使用同一批画像、同一份问卷、同一情境，只改这两件事。</p>
<p>Brier 越小越好；分布误差以百分点计，越小越好。区间均来自按人分层重抽样 2,000 次。</p></section>
<section><h2>主对照：优化组合 vs 原生流程</h2>
<p>分布误差只在“同一题卡在<b>被测人群</b>中至少有 20 人”时估计。题卡随机的商品/服务研究里，96 名被测者分散到几百张卡上，因此这些研究不报告分布误差，不拿稀疏卡片硬算。</p>
<table><tr><th>研究</th><th>人数</th><th>Brier 相对改善</th><th>95% 区间</th><th>Brier 判定</th><th>分布改善（百分点）</th><th>95% 区间</th><th>分布判定</th></tr>
{''.join(main_rows)}</table></section>
<section><h2>各组到底得多少分</h2>
<p>同一行内比较才有意义；不同研究的题数与选项数不同，不能横向比大小。</p>
<table><tr><th>研究</th>{''.join(f'<th>{esc(label_arm(a))}</th>' for a in arms_run)}{''.join(f'<th>{esc(label_arm(a))}</th>' for a in references if a != 'uniform')}<th>机会均等</th></tr>
{''.join(arm_rows)}</table></section>
{_reading_section(raw, rows) if few else ''}
<section><h2>和统计参照比，而不是只和自己比</h2>
<p>每一套取可用的最强统计参照：题卡重复的研究用“同层历史比例”，否则用“全体历史比例”；题卡随机的家电研究用商品属性条件 logit。所有参照只用未参与评测的受访者答案拟合，且与画像看到完全相同的题目。</p>
<table><tr><th>研究</th><th>统计参照</th><th>Brier 相对改善</th><th>95% 区间</th><th>判定</th></tr>
{''.join(statistical_rows)}</table></section>
{f'<section><h2>拒答与“都不”选项的比例</h2><p>仅统计题目本身含拒答类选项的情况，按标签识别，未按结果挑选。</p><table><tr><th>研究</th><th>题号</th><th>原生·单选</th><th>预测·概率</th><th>全体历史</th></tr>{"".join(refusal_rows)}</table></section>' if refusal_rows else ''}
{f'''<details><summary><strong>全部对照逐项明细（含拆解：只有概率 / 只有提示）</strong></summary>
<p>这张表回答“改善来自哪里”。原生→概率 与 原生→优化 几乎相同，说明收益主要来自“交出概率”，而不是改提示。</p>''' if ablation else '<details><summary><strong>全部对照逐项明细</strong></summary><p>本次只跑了两个臂，没有“只有概率/只有提示”的拆解，因此不能把改善归因到提示或概率中的哪一个。</p>'}
<table><tr><th>研究</th><th>比较</th><th>Brier 相对改善</th><th>95% 区间</th><th>判定</th></tr>
{''.join(full_rows)}</table></details>
<section><h2>跑完了吗：完成度与费用</h2>
<p>计划 {budget['max_calls']:,} 次调用；检查点状态 {esc(json.dumps(execution['states'], ensure_ascii=False))}。缺失调用 {execution['missing_calls']}。</p>
<p>保守预留上限 ${budget['reserved_peak_usd']:.2f}，冻结费用上限 ${budget['max_cost_usd']:.2f}；两者都按最大输出估算，不是账单。失败调用不会被自动填答案，需显式重试并保留原记录。</p>
<p>答题覆盖规则：按被测人实际作答的题目计算；少于一半题目的被测人整人排除并计数。规则只看观察到的事实答案，不看模型输出。</p>
<p>画像厚薄是跨研究比较的混淆因素：每套研究发出的规范人格字段中位数不同，详见冻结规格 <code>persona_field_distribution</code>。</p>
<p>本计划的两臂选择、题型口径与参照规则见 <code>docs/预注册协议-clean-v1.md</code>；冻结规格 <code>specs/cross-study-v1/clean-v1.json</code>。</p></section>
<section><h2>不能说什么</h2>
<ul>
<li>{'这六套不是六个独立行业：四套来自美国同一调查体系，两套是家电。跨国结论仍不成立。' if not few else '这几套不算多个独立行业，也不跨地区；结论只在这几套问卷内成立。'}</li>
<li>画像是发行版里的合成人格，不是这些真人的实测信息；匹配只做人口字段约束。</li>
<li>题面经过文字化与结构重建，图形、跳题与原始展示顺序未必完全一致。</li>
<li>公开数据可能已进入底层模型训练。</li>
<li>通过门槛只说明“预测这些问卷的选择更准”，不说明销量、转化或真实行为。</li>
<li>本页不含跨题相关性分析：每题单独请求，不能声称还原整份答卷的联合分布。</li>
<li>“优化组合”优于原生流程，很大一部分来自“给出概率”而不是“改提示”；两者要分开读。</li>
</ul></section>
<section><h2>怎么复算</h2>
<p>评分只读本机检查点，不调用模型：<code>PYTHONPATH=examples/sim-to-real .venv/bin/python -m decision_lab.cross_study.formal score</code>，随后 <code>... -m decision_lab.cross_study.formal_report</code>。冻结规格见 <code>specs/cross-study-v1/formal-v1.json</code>，逐组数字见 <code>reports/cross-study-v1/formal-results.json</code>。</p></section>
</html>'''


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=OUT / 'formal-results.json')
    parser.add_argument('--output', type=Path, default=OUT / 'formal-report.html')
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Do not overwrite an existing formal report')
    summary = summarize(json.loads(args.input.read_text()))
    args.output.write_text(render(summary))
    args.output.with_suffix('.summary.json').write_text(json.dumps(
        {k: v for k, v in summary.items() if k != 'raw'}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'supporting': summary['supporting'],
                      'beats_statistics': summary['beats_statistics'],
                      'cross_study_gate': summary['cross_study_gate']}, ensure_ascii=False))
