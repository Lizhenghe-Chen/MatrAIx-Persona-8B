"""Build the offline report, with ECharts and numbers from frozen results."""
import argparse
import hashlib
import json
import re
import sys
from html import escape as h
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
REPORT = HERE / 'reports/final.html'
INDEX = HERE / 'data/final-evidence-v1.json'
TEMPLATE = HERE / 'src/final_report.html.tmpl'
ECHARTS = 'examples/sim-to-real/reports/vendor/echarts.min.js'
STUDY = 'examples/sim-to-real/study/'
CROSS = 'examples/sim-to-real/decision_lab/reports/cross-study-v1/'
STAGE = 'examples/decision-transfer/'
ARCHIVE = STAGE + 'archive/2026-11-13-exploration/'
CENTER = 'examples/reports/'
LINK_ASSETS = REPO / CENTER / 'src'
sys.path.insert(0, str(LINK_ASSETS))
from report_catalog import FEATURED_REPORTS, HTML, report_button  # noqa: E402

SOURCES = {
    'first': STUDY + '01_首轮归档/results.json',
    'model': STUDY + '02_模型对比/results.json',
    'background': STUDY + '03_提示与背景/results.json',
    'commerce': STUDY + '06_北美电商选品/results.json',
    'pew': STUDY + '08_购物预测/pew-formal-score.json',
    'amazon': STUDY + '08_购物预测/amazon-test-score.json',
    'audit': STUDY + '09_方法审查/audit-results.json',
    'repeat': STUDY + '10_匹配与商品复验/results.json',
    'formal': CROSS + 'formal-results.json',
    'wide': CROSS + 'wide-v1-results.json',
    'clean': CROSS + 'clean-v1-results.json',
    'external': CROSS + 'external-v2-results.json',
    'cluster': CROSS + 'cluster-summary.json',
    'inventory': CROSS + 'source-inventory.json',
    'pilot': CROSS + 'blend-pro.json',
    'pilot_external': CROSS + 'blend-ext-pro.json',
    'conclusions': STAGE + 'data/conclusions-v1.json',
    'products': STAGE + 'data/personal-choice-products-v1.json',
    'orders': STAGE + 'data/online-retail-incidence-v1.json',
    'swiss': STAGE + 'data/stage2-results.json',
    'history': 'examples/sim-to-real/decision_lab/reports/choice-history-result.json',
    'replication': STAGE + 'data/final-replication-v1.json',
    'combined': STAGE + 'data/final-combined-v1.json',
}
NAMES = dict(anes='美国公共开支', dryer='四国烘干机', pew13='购物态度（Pew）',
             pew168='诈骗风险（Pew）', shed='美联储涨价应对（SHED）', swiss='瑞士家电',
             origin='美国商品产地', packaging='美国啤酒包装', pew111='网购与达人（Pew）',
             german='德国番茄包装', tshirt='美国 T 恤', radiant='西班牙番茄',
             drone='美国无人机配送', shoes='美国运动鞋评分', openecommerce='美国 Open eCommerce')

PROJECT_BASELINE = 'MatrAI X 项目（单选）'
NEUTRAL, PROBABILITY, COMBINED, STATISTICS = '#a2b0c5', '#638bbd', '#234fa0', '#19815f'


def link(label, target, *, primary=False):
    parts = urlsplit(target)
    url = target if parts.scheme else urlunsplit(
        ('', '', quote('../../../' + parts.path, safe='/'), parts.query, parts.fragment)
    )
    if Path(parts.path).suffix.lower() in HTML:
        return report_button(label, url, primary=primary)
    return f'<a href="{h(url, quote=True)}">{h(label)}</a>'


def source(key, label='核对数据'):
    return link(label, SOURCES[key])


def number(value, digits=2):
    return '—' if value is None else f'{value:.{digits}f}'


def interval(values, digits=2):
    return '—' if values is None else '［' + '，'.join(f'{v:+.{digits}f}' for v in values) + '］'


def table(headers, rows):
    head = ''.join(f'<th scope="col">{h(x)}</th>' for x in headers)
    body = ''.join('<tr>' + ''.join(f'<td>{v}</td>' for v in row) + '</tr>' for row in rows)
    return (
        '<div class="table-scroll" tabindex="0" role="region" aria-label="数据表，可横向滚动">'
        f'<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'
    )


def details(title, body, anchor):
    return f'<details id="{anchor}"><summary>{h(title)}</summary>{body}</details>'


def chart(key, summary):
    return (
        f'<div class="chart" data-chart="{key}" role="img" aria-label="{h(summary, quote=True)}">'
        f'<noscript><p class="chart-note">{h(summary)}</p></noscript></div>'
    )


def plot(categories, series, *, precision, maximum, step, unit):
    return dict(categories=categories, series=series, precision=precision,
                maximum=maximum, interval=step, tooltipUnit=unit)


def series(name, values, color):
    return dict(name=name, values=values, color=color)


def colored_bars(name, values, colors, titles):
    bars = [
        {'value': value, 'name': title, 'itemStyle': {'color': color}}
        for value, color, title in zip(values, colors, titles, strict=True)
    ]
    return series(name, bars, colors[0])


def issue_summary(d):
    food = d['replication']['studies'][0]['results']
    case = next(card for card in food['card_distributions'] if card['card'] == 'CBQ700')
    option = case['options'].index('Sometimes')
    real = case['real'][option]
    before = case['model']['original'][option]
    after = case['model']['output_only'][option]
    return f"""
  <p class="lead">要估一群人怎么选，<b>把每个选项的概率都留下</b>，两项新实验的比例都更接近真人。
    要猜某个人会怎么选，<b>他以前真的选过什么</b>也能提供帮助。</p>
  <p class="finding-note">买食品时，你会看包装日期吗？这道真实问卷里，<b>{real:.1%}</b> 的人答「有时」。
    MatrAI X 项目只让每个虚拟人选一个答案，结果估成 <b>{before:.1%}</b>。</p>
  <p class="finding-note">只留概率最高的一项，其他答案的可能性就被舍掉了。
    改成把每个人给各选项的概率都算进去后，「有时」降到 <b>{after:.1%}</b>，离真人还有一段差距。</p>
  <p class="source report-actions">{link('先看哪些改法有效', CENTER + 'bottleneck.html', primary=True)}
    {link('为什么还不够准', CENTER + 'bottleneck.html#remaining')}
    {link('看食品日期原题', CENTER + 'question-cases.html#CBQ700')}</p>"""


def study_scope(d):
    food, tofu = d['replication']['studies']
    survey, choice = food['results'], tofu['results']
    tofu_meta = d['replication']['freeze']['metadata']['tofu']
    return f"""
  <p>我们找了两套此前没用来选改法的真人研究。让同一个 AI（DeepSeek Pro）用同一批虚拟人物、同样的题目和选项顺序作答。
    MatrAI X 项目原来只交一个答案，优化方法交出每个选项的概率。</p>
  <dl class="scope-grid">
    <div><dt>{h(food['label'])}</dt><dd>2017–2018 年的自报购物习惯。正式评估 {survey['scored_people']} 位成年人，
      共 {survey['scored_cards']} 道固定题、{survey['eligible_target_tasks']} 次作答，按官方访谈权重汇总。另抽 20 位同题试答者单独比较。</dd>
      <dd class="source">{link('CDC 问卷、代码本和数据', food['source'])}</dd></div>
    <div><dt>{h(tofu['label'])}</dt><dd>2021 年的情境选购。{choice['scored_people']} 位受访者作出 {choice['eligible_target_tasks']} 次待预测的选择。
      共出现 {tofu_meta['cards']} 种商品卡，其中 {choice['scored_cards']} 种达到至少 20 人作答，用于估人群比例。统计模型用另外 {choice['stat_training_people']} 人训练。</dd>
      <dd class="source">{link('作者问卷和工作簿', tofu['source'])}</dd></div>
  </dl>
  <p>这些虚拟人物来自 Persona 1M。我们按地区、年龄、学历和性别找相近的画像，瑞典按西欧大区匹配。
    最后用留出的真人答案判卷。两套研究早已公开，AI 在训练时是否见过相关资料，无法确认。</p>
  <details><summary>百分比、误差和区间怎么读？</summary>
    <p><b>群体比例误差越低越好。</b> 一道二选一题，真人有 60% 选甲，AI 估成 80%，误差就是 20 个百分点。</p>
    <p><b>个人概率误差也越低越好。</b> 例如真人选了甲，事先给甲 90% 的概率，比给甲 10% 更准。这个误差分数叫 Brier。</p>
    <p><b>95% 区间</b>帮我们判断改善稳不稳。按受访者重抽样 2,000 次来估计区间。改善区间如果包含 0，现有样本还无法确认有没有改善。</p>
  </details>
  <p class="source">{link('样本、匹配和评分规程', STAGE + 'docs/末轮复验规程.md')}</p>"""


def bottleneck_summary(d):
    food, tofu = (study['results'] for study in d['replication']['studies'])
    after = [r['scores']['output_only']['tv'] for r in (food, tofu)]
    combined = d['combined']['scores']
    return f"""
  <dl class="bottleneck-factors">
    <div><dt>人群比例仍有差距</dt><dd>保留概率后，食品标签和豆腐选购的比例误差还有
      <b>{after[0]:.2f}</b> 和 <b>{after[1]:.2f}</b> 个百分点。</dd></div>
    <div><dt>猜买哪款，AI 还会选偏</dt><dd>豆腐问卷里固定「买不买」的预测，只把选款交给 AI，误差从
      <b>{combined['refusal_only']['conditional']:.3f}</b> 升到 <b>{combined['combined']['conditional']:.3f}</b>。</dd></div>
  </dl>
  <p><b>现有证据首先指向两处</b>，给了什么真人资料，以及模型会不会用这些资料。豆腐对照把差距定位到选款。
    统计选款还用过其他真人的答案，资料和模型各影响多少还分不开。真人答题的方式也可能影响这段差距，本项目尚未单独测量。</p>
  <p class="source report-actions">{link('看四个可能原因与论文', CENTER + 'bottleneck.html#remaining', primary=True)}
    {link('看换模型和补资料的效果', CENTER + 'bottleneck.html#depends')}</p>"""


def usage_summary(d):
    history = [study['results']['arms'] for key in ('formal', 'wide', 'clean', 'external')
               for study in d[key]['studies'].values()]
    group_count = sum(arms['original']['card_tv_pp'] is not None for arms in history)
    summary = d['cluster']['summary']
    shed = d['formal']['studies']['shed']['results']['arms']
    gains = d['conclusions']['summary_counts']
    yogurt = next(row for row in d['conclusions']['gains'] if row['label'] == '酸奶（超市）')
    return f"""
  <dl>
    <div><dt>手头只有模拟答案</dt><dd>保留完整概率，先用于粗估人群比例。需要拿比例做决策时，安排真人问卷来校对。</dd></div>
    <div><dt>已经有同题真人试答</dt><dd>先直接统计这批人的选择。用另外留出的真人答案验证加入 AI 后能否继续降误差。</dd></div>
    <div><dt>有本人的同类选择记录</dt><dd>先用统计更新买不买的概率，再用留出的记录核对买哪款。豆腐实验的组合补算中，两步都用统计误差最低。</dd></div>
  </dl>
  <p><b>不同题的效果</b>　历轮另有 {len(history)} 套研究。{group_count} 套可比较人群比例，另外 {len(history) - group_count} 套主要按人评分。
    美国家庭涨价应对题上，改提示并保留概率后，群体误差由 {shed['original']['card_tv_pp']:.2f} 到 {shed['optimized']['card_tv_pp']:.2f} 个百分点，
    基本持平。历轮汇总纳入真人统计对照的 {summary['studies_with_reference']} 套研究中，有 {summary['studies_behind_reference']} 套的 AI 个人概率误差较大。
    这些统计参照使用了其他真人的答案。</p>
  <p><b>问卷和交易的证据</b>　加入本人记录的 {gains['comparisons']} 组问卷或交易对照中，{gains['interval_above_zero']} 组的改善区间高于零。
    有日期的超市酸奶记录中，把买不买和买哪款分开预测，个人概率误差从 {yogurt['baseline']:.3f} 降到 {yogurt['with_history']:.3f}。
    这项结果来自有购物记录的家庭。销量和新客转化还需另外的交易样本验证。</p>
  <p class="source report-actions">{source('cluster', '历轮统计参照')}
    {link('看 12 组个人记录与交易对照', CENTER + 'purchase-evidence.html')}</p>"""


def report_results(d):
    nhanes, tofu = (study['results'] for study in d['replication']['studies'])
    combined = d['combined']
    values = combined['scores']
    original, probability, hybrid, statistics = (
        values[key]['brier'] for key in ('original', 'output_only', 'combined', 'refusal_only')
    )
    reduction = combined['combined_vs_reference']['original']['relative_improvement']
    added_error = -combined['combined_vs_reference']['refusal_only']['relative_improvement']
    scores = nhanes['pilot']['scores']
    pilot, pilot_with_ai = scores['pilot'], scores['pilot_ai']
    pilot_difference = pilot_with_ai - pilot
    pilot_interval = interval(nhanes['pilot']['contrasts']['pilot']['ci95'])
    survey_names = ('美国食品标签', '瑞典豆腐选购')
    before = [r['scores']['original']['tv'] for r in (nhanes, tofu)]
    after = [r['scores']['output_only']['tv'] for r in (nhanes, tofu)]
    improvements = [r['contrasts']['original__output_only']['group'] for r in (nhanes, tofu)]

    chart_values = {
        'combined': plot(
            ['MatrAI X\n项目单选', '优化方法\n保留概率', '合用\nAI＋记录', '真人统计\n＋本人记录'],
            [colored_bars('个人概率误差', [original, probability, hybrid, statistics],
                          [NEUTRAL, PROBABILITY, COMBINED, STATISTICS],
                          [PROJECT_BASELINE, '优化方法（保留全部概率）', '真人记录判断买不买，AI 判断买哪款',
                           '两步都用统计，本人记录用于判断买不买'])],
            precision=3, maximum=1.2, step=.3, unit='',
        ),
        'survey': plot(
            list(survey_names),
            [series(PROJECT_BASELINE, before, NEUTRAL), series('优化方法（保留全部概率）', after, COMBINED)],
            precision=2, maximum=60, step=15, unit=' 个百分点',
        ),
        'pilot': plot(
            ['直接统计试答', '试答和 AI 各占一半'],
            [colored_bars('群体比例误差', [pilot, pilot_with_ai], [STATISTICS, PROBABILITY],
                          ['直接统计 20 份真人试答', '试答和 AI 各占一半'])],
            precision=2, maximum=25, step=5, unit=' 个百分点',
        ),
    }
    combined_chart = chart(
        'combined', f'瑞典豆腐实验四种方案的个人概率误差，越低越好。{PROJECT_BASELINE} {original:.3f}，'
        f'AI 保留概率 {probability:.3f}，合用 {hybrid:.3f}，两步都用统计 {statistics:.3f}。'
    )
    survey_chart = chart(
        'survey', '群体比例误差，越低越好。'
        + '。'.join(f'{name}从 {old:.2f} 降到 {new:.2f} 个百分点'
                    for name, old, new in zip(survey_names, before, after, strict=True)) + '。'
    )
    pilot_chart = chart(
        'pilot', f'食品标签问卷的群体比例误差，越低越好。直接统计 {pilot:.2f}，'
        f'试答和 AI 各占一半 {pilot_with_ai:.2f} 个百分点。'
    )
    gains = ''.join(
        f'<div><dt>{h(name)}</dt><dd>误差少 <strong>{gain["improvement"]:.2f}</strong> 个百分点</dd>'
        f'<dd class="gain-range">95% 区间 {interval(gain["ci95"])}</dd></div>'
        for name, gain in zip(survey_names, improvements, strict=True)
    )
    accuracy = [(r['scores']['original']['accuracy'], r['scores']['output_only']['accuracy']) for r in (nhanes, tofu)]
    combined_figure = f"""
<figure class="panel primary" id="combined" aria-labelledby="combined-title">
  <figcaption>
    <h2 id="combined-title">知道他以前怎么选，能猜中这次吗？</h2>
    <p class="meta">瑞典豆腐选购 · 同一批 {combined['people']} 人的 {combined['tasks']} 次选择 · 个人概率误差，越低越好</p>
  </figcaption>
  <div class="main-grid">
    {combined_chart}
    <div class="stats">
      <div>
        <span class="big-number">{reduction:.1%}</span>
        <p><strong>合用方案比 MatrAI X 项目单选的误差低</strong></p>
        <p>误差 {original:.3f} → {hybrid:.3f}</p>
      </div>
      <div class="best">
        <p><strong>两步都用统计更准（{statistics:.3f}）</strong></p>
        <p>用同一份记录判断买不买，再把选款交给 AI，误差增加 {added_error:.1%}。</p>
      </div>
    </div>
  </div>
  <p class="note method-note">想预测一个人会选哪款豆腐，可以先估他会不会买，再估买了会选哪款。
    合用方案先用他的两次实验选择判断买不买，选款交给 AI。图中降幅包含新增的真人资料和两步判断，来自同一批实验题的事后补算。</p>
  <p class="source report-actions">{source('combined', '组合补算数据')}
    {link('本人记录与购买预测', CENTER + 'purchase-evidence.html')}</p>
</figure>"""
    body = f"""
<div class="secondary">
  <figure class="panel primary" id="survey" aria-labelledby="survey-title">
    <figcaption>
      <h2 id="survey-title">一群人会怎么选？</h2>
      <p class="meta">每项 96 人，固定模型、画像和题目 · 群体比例误差（百分点），越低越好</p>
      <ul class="key" aria-label="图例">
        <li><i class="swatch old" aria-hidden="true"></i>{PROJECT_BASELINE}</li>
        <li><i class="swatch" aria-hidden="true"></i>保留全部概率</li>
      </ul>
    </figcaption>
    {survey_chart}
    <dl class="gains">{gains}</dl>
    <p class="note">用每人的单选答案或概率最高的答案判卷，食品标签的答对率从 {accuracy[0][0]:.1%} 到 {accuracy[0][1]:.1%}，
      豆腐从 {accuracy[1][0]:.1%} 到 {accuracy[1][1]:.1%}。</p>
    <p class="source report-actions">{source('replication', '正式复验数据')}
      {link('按研究查看真人原题', CENTER + 'question-cases.html')}</p>
  </figure>
  <figure class="panel" id="pilot" aria-labelledby="pilot-title">
    <figcaption>
      <h2 id="pilot-title">问过 20 人，还要加 AI 吗？</h2>
      <p class="meta">美国食品标签问卷 · 群体比例误差（百分点），越低越好</p>
    </figcaption>
    {pilot_chart}
    <div class="pilot-takeaway">
      <p>先拿 20 份试答数一遍，再试着让真人统计和 AI 各算一半。用另外一批真人的回答检验。</p>
      <p><b>加 AI 后，误差多 {pilot_difference:.2f} 个百分点。这次基本持平。</b></p>
      <p class="note">误差改善的 95% 区间为 {pilot_interval} 个百分点，包含 0。现有样本还无法确认加 AI 有帮助。</p>
    </div>
    <p class="source report-actions">{source('replication', '试答回放数据')}
      {link('看试答对照的解释', CENTER + 'bottleneck.html#pilot-interpretation')}</p>
  </figure>
</div>
{combined_figure}"""
    return body, chart_values


def latest_details(d):
    report = d['replication']
    combined = d['combined']
    rows = []
    original = combined['scores']['original']['brier']
    for key, values in combined['scores'].items():
        contrast = combined['combined_vs_reference'].get(key)
        change = '—' if key == 'original' else f"{(values['brier'] - original) / original:+.1%}"
        label = PROJECT_BASELINE if key == 'original' else values['label']
        rows.append((h(label), number(values['brier'], 3), change, number(values['tv']),
                     f"{values['accuracy']:.1%}", interval(contrast['ci95'], 3) if contrast else '—'))
    parts = [
        '<p>个人概率误差（Brier）根据预测概率和实际答案之间的平方差计算。群体比例误差以百分点计，'
        '例如二选一时，真人选甲为 60%，预测为 80%，分布误差是 20 个百分点。两种误差均越低越好。</p>',
        '<p>组合检验沿用同一批评估题。两步都用统计与合用方案共享同一份「买不买」预测，'
        '这份预测用本人的两次选择更新。选款时，一组用其他真人的训练数据拟合统计模型，另一组用 AI 的选款概率。'
        f'{PROJECT_BASELINE}使用项目原生问卷流程，实验模型固定为 DeepSeek Pro。</p>',
        '<p>组合与两步都用统计的个人概率误差比较按人配对重抽样。下表最后一列为'
        '「该方案的误差减去合用方案的误差」的 95% 区间，正值表示合用误差较低。</p>',
        table(['方案', '个人概率误差', '较项目单选变化', '群体比例误差（百分点）',
               '逐人答对率', '合用的误差改善区间'], rows),
        '<p>试答加 AI 的比较使用另一份问卷。三种改法在同一场任务里的叠加效果仍缺直接数据。</p>',
        f'<p class="source">{source("combined", "组合数据与重抽样区间")} · '
        f'{link("末轮规程", STAGE + "docs/末轮复验规程.md")}</p>',
    ]
    content = details('合用方案、两种误差和对照基线', ''.join(parts), 'metrics')

    run = report['run']
    parts = [
        f'<p>内网 Qwen 完成 {run["qwen"]["successful"]} 次技术检查。DeepSeek Pro 完成 '
        f'{run["pro"]["successful"]}/{run["pro"]["attempts"]} 次请求。'
        '正式任务共享同一版模型、匹配画像和文字题卡，两套公开数据是否曾进入模型训练未知。</p>'
    ]
    for study in report['studies']:
        parts.append(f'<h3>{h(study["label"])}</h3><p>{h(study["note"])}</p>')
        for data_table in study['tables']:
            headers = [name.replace('原单选比例', 'MatrAI X 项目单选比例') for name in data_table['headers']]
            rows = [[h(str(cell).replace('原生问卷单选', PROJECT_BASELINE)) for cell in row]
                    for row in data_table['rows']]
            parts.append(table(headers, rows))
        if study['source']:
            parts.append(f'<p class="source">{link("作者数据与问卷", study["source"])}</p>')
    parts.append(f'<p class="source">{source("replication", "原始汇总结果与题卡比例")}</p>')
    return content + details('两项正式复验和试答比较的全表', ''.join(parts), 'new')


def historical_details(d):
    ext = d['external']['studies']['openecommerce']['results']
    ext_tv = ext['card_contrasts']['original__to__optimized']
    pew_scores = d['pew']['summaries']
    formal_pew = d['formal']['studies']['pew13']['results']['arms']
    model = d['model']['overall']
    background = d['background']['overall']
    k20 = d['pilot_external']['studies']['openecommerce']['blend']['20']
    german = d['pilot']['studies']['german']['blend']['20']
    output_rows = [
        ('原模型直接单选', number(pew_scores['rich_choice']['tv_pp'])),
        ('要求输出概率，仍只取最高项', number(pew_scores['rich_probability_argmax']['tv_pp'])),
        ('保留每个选项的概率', number(pew_scores['rich_probability']['tv_pp'])),
        ('统计其他真人的同题数据', number(pew_scores['statistics']['tv_pp'])),
    ]
    body = f"""
    <p>购物态度问卷（240 人，13 题）上，即使让模型输出概率，如果汇总时只留最高项，比例误差仍然很高。
    当时用单选有 {pew_scores['rich_choice']['concentration_counts']['0.95']} 题的同一选项占比达到 95%，
    保留概率后为 {pew_scores['rich_probability']['concentration_counts']['0.95']} 题。</p>
    {table(['问卷做法', '群体比例误差（百分点）'], output_rows)}
    <p>另一轮只改输出方式的 Pew 对照，误差从 {formal_pew['original']['card_tv_pp']:.2f}
    降到 {formal_pew['output_only']['card_tv_pp']:.2f}。Open eCommerce 同时改了提示和输出，
    比例误差少 {ext_tv['improvement_pp']:.2f} 个百分点，95% 区间 {interval(ext_tv['improvement_95_ci'])}，
    逐人答对率从 {ext['arms']['original']['accuracy']:.1%} 到 {ext['arms']['optimized']['accuracy']:.1%}。</p>
    <p>三份美国问卷在共同情境条件下，Flash、Qwen 和 Pro 的比例误差分别是
    {model['flash-A']['tv_pp']:.2f}、{model['qwen-A']['tv_pp']:.2f} 和 {model['pro-A']['tv_pp']:.2f}。
    画像更丰富时，Flash 与 Pro 的误差接近。同一模型换成预测提示与贴题背景后，
    误差从 {background['p0-b1']['tv_pp']:.2f} 到 {background['p1-b3']['tv_pp']:.2f}；
    用其他真人同题数据统计的误差为 {background['historical-stratum']['tv_pp']:.2f}。</p>
    <p>在 Open eCommerce 的 20 人回放里，加 Pro 相比同权重的等概率方案少错
    {k20['model_gain_pp']:.2f} 个百分点，相比直接统计只少错 {k20['pilot'] - k20['blend_model']:.2f}。
    德国番茄包装的试答误差为 {german['pilot']:.2f}，加 Pro 后为 {german['blend_model']:.2f}。</p>
    <p class="source">{source('pew', '购物态度问卷')} · {source('formal', '只改输出的对照')} ·
    {source('external', '外部成绩')} · {source('model', '模型成绩')} · {source('background', '人物资料与提示成绩')} ·
    {source('pilot_external', '外部试答回放')} · {source('pilot', '其他试答回放')}</p>
    """
    content = details('历史实验中，概率、模型、人物资料和试答各改了多少', body, 'history')

    frozen_rows = []
    for key in ('formal', 'wide', 'clean', 'external'):
        for name, study in d[key]['studies'].items():
            arms = study['results']['arms']
            comp = study['results']['card_contrasts'].get('original__to__optimized', {})
            frozen_rows.append((h(NAMES[name]), str(study['people']),
                                number(arms['original']['card_tv_pp']), number(arms['optimized']['card_tv_pp']),
                                interval(comp.get('improvement_95_ci')), number(arms['original']['brier'], 3),
                                number(arms['optimized']['brier'], 3), f"{arms['original']['accuracy']:.1%}",
                                f"{arms['optimized']['accuracy']:.1%}", source(key)))
    content += details(
        f'{len(frozen_rows)} 套历轮研究的完整对照',
        '<p>下表按研究列成绩。群体比例误差单位为百分点，逐人答对率取最高概率。'
        '— 表示题卡没有足够重复或结果未提供。</p>'
        + table(['研究', '人数', 'MatrAI X 项目比例误差', '改后比例误差', '比例改善区间', '项目 Brier',
                 '改后 Brier', '项目答对率', '改后答对率', '来源'], frozen_rows)
        + f'''<p class="note">旧汇总把美联储 SHED 误归到 Pew。这里引用各研究的误差，跨来源复验以实际调查来源判断。
             {link('SHED 数据来源说明', STUDY + '01_首轮归档/README.md')}</p>
             <p class="source report-actions">{source("cluster", "十四套历史比较")}
             {link('历轮逐题完整版', 'examples/sim-to-real/reports/cards.html')}
             {link('历轮技术报告', 'examples/sim-to-real/reports/index.html')}</p>''', 'surveys',
    )

    conclusions = d['conclusions']
    original_gains = conclusions['gains']
    history_rows = [(h(x['label']), str(x['people']), number(x['baseline'], 3), number(x['with_history'], 3),
                     f"{x['relative']:+.1%}", interval(x['ci95'], 3),
                     '区间高于零' if x['holds'] else '区间跨零') for x in original_gains]
    beer = d['products']['studies']['beer']['brier']
    candle = d['orders']['categories']['candle_holders']
    people_body = f"""
    <p>美国啤酒实验的误差从 {beer['population']:.3f} 降到 {beer['own']:.3f}；
    只按本人资料更新其拒买倾向，误差为 {beer['refusal_only']:.3f}。五套商品问卷中，三个完整更新的改善区间高于零。
    瑞士实测背景四组筛查里，用他人的态度资料比用本人资料准。</p>
    <p id="orders">英国烛台订单中，买不买的概率误差为
    {candle['incidence_brier']['market']:.3f} → {candle['incidence_brier']['smoothed_frequency_and_label']:.3f}，
    已买者的选款误差为 {candle['choice_given_purchase_brier']['market']:.3f} →
    {candle['choice_given_purchase_brier']['smoothed_frequency_and_label']:.3f}。
    英国结果只适用于有足够历史且后来出现订单的样本，完整误差改善区间跨零。美国收银记录的两项复购结果缺可核验时间戳，
    有日期的美国超市记录另行按时间评估。销量和新客下单需要实际交易验证。</p>
    {table(['任务', '人数', '参照 Brier', '更新后 Brier', '相对误差下降', '绝对改善区间', '状态'], history_rows)}
    <p class="source">{source('products', '五套商品问卷')} · {source('swiss', '瑞士四组成绩')} ·
    {source('conclusions', '本人记录实验')} · {source('orders', '英国聚合数据')} ·
    {link('UCI 原始数据', 'https://doi.org/10.24432/C5BW33')}</p>
    """
    return content + details('本人记录与真实订单的历史结果', people_body, 'people')


def provenance_details(d):
    modules = [
        ('首轮真人问卷', '正式回测', '涨价应对、诈骗风险、公共支出', source('first')),
        ('模型、资料、提示分拆', '正式对照', '分别核对模型和人物资料的贡献',
         source('model') + ' · ' + source('background', '背景与提示')),
        ('北美选品', '正式对照', '产地二选一、包装可拒买、网购自报', source('commerce')),
        ('购物预测与方法审查', '回测和复核', '固定问题、运动鞋打分与 Amazon 行为',
         source('pew') + ' · ' + source('amazon', 'Amazon 行为') + ' · ' + source('audit', '方法审查')),
        ('匹配与复验', '已有数据内部复验', '调整人口分布并重复调用', source('repeat')),
        ('跨研究和外部问卷', '正式对照与外部复验', '冻结题面与分组，核对可评分的题卡',
         source('formal') + ' · ' + source('wide', '扩展') + ' · ' + source('clean', '配送与鞋')
         + ' · ' + source('external', 'Open eCommerce')),
        ('本人选择与实测背景', '探索', '检验给模型两次历史与真人背景',
         source('history') + ' · ' + source('swiss', '瑞士四组')),
        ('统计更新与真实订单', '用留出的真人数据检验', '商品问卷、收银记录和按时间留出的订单', source('conclusions')),
        ('马桶刷与保温杯', '应用展示', '模拟商品份额和理由，缺同题真人参照',
         link('应用说明', 'examples/虚拟消费者模拟研究报告/README.md')),
        ('Playground 任务', '功能展示', '运行环境和接口演示', link('任务说明', 'examples/tasks/README.md')),
    ]
    eligible = {row['study'] for row in d['cluster']['rows']}
    cases = {'amazon': '行为证据另列，并有同源问卷复验', 'swiss_six': '另有实测背景探索',
             'vegetables': '材料不足时保留审查', 'supermarket': '保留行为与备选集限制',
             'cius': '行为自报候选'}
    inventory = [(h(item['name']), h(item['task_scope']),
                  h('有正式成绩' if item['id'] in eligible else cases.get(item['id'], '见来源清单')),
                  h(item['outstanding'])) for item in d['inventory']['studies']]
    body = f"""
    {table(['阶段', '证据类型', '任务与边界', '来源'], modules)}
    <p>首轮三份问卷等权增益为 {d['first']['combined_gain_pp']:.2f} 个百分点。
    Git 中的 <code>284b106</code> 是起点，<code>66785e4</code> 补齐外部原流程对照，
    <code>3f03bf0</code> 冻结选择历史相关结论，<code>31244bf</code> 保存完整探索过程，
    <code>70ef513</code> 重排归档。搬运和重绘不新增样本。旧报告的 35／55 分是主观评议。</p>
    {table(['研究', '原任务', '成绩范围', '当时审查点'], inventory)}
    <p class="source">{source('inventory', '十九套来源清单')} ·
    {link('探索归档', ARCHIVE + 'INDEX.md')} ·
    {link('可复算证据索引', STAGE + 'data/final-evidence-v1.json')}</p>
    <p>官方技术论文的 400 次预设行为测试中有 366 次符合预期（91.5%），衡量的是代理能否按设定行事。
    真人问卷、个人选择和交易预测使用上文的对照结果作为依据。</p>
    <p class="source">{link('MatrAIx 技术论文', 'https://arxiv.org/html/2608.04205v1')} ·
    {link('Bisbee 等，真人与合成问卷对照', 'https://doi.org/10.1017/pan.2024.5')} ·
    {link('概率描述与回答抽样研究', 'https://arxiv.org/abs/2607.25292')} ·
    {link('本地文献综述', STUDY + '11_文献综述/综述.md')}</p>
    """
    return details('历次实验、覆盖数据与引用', body, 'coverage')


def render(d, echarts):
    results, chart_values = report_results(d)
    featured_links = ''.join(f'<li>{link(title, CENTER + filename)}<p class="note">{h(description)}</p></li>'
                             for filename, title, description in FEATURED_REPORTS)
    slots = {
        'ISSUE_SUMMARY': issue_summary(d),
        'RESULTS': results,
        'STUDY_SCOPE': study_scope(d),
        'USAGE_SUMMARY': usage_summary(d),
        'APPENDIX': latest_details(d) + historical_details(d) + provenance_details(d),
        'HTML_NAV': ' '.join((link('报告中心', CENTER + 'index.html'),
                              report_button('重点报告', '#html-reports', primary=True,
                                            mark=f'{len(FEATURED_REPORTS)} 份'))),
        'BOTTLENECK_SUMMARY': bottleneck_summary(d),
        'FEATURED_REPORTS': featured_links,
        'ARCHIVE_LINK': link('历史归档与全部资料', CENTER + 'catalog.html'),
        'LINK_STYLE': (LINK_ASSETS / 'report-links.css').read_text(),
        'CHART_DATA': json.dumps(chart_values, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c'),
        'ECHARTS': echarts,
    }
    return re.sub(r'@@([A-Z_]+)@@', lambda match: slots[match[1]], TEMPLATE.read_text())


def load_sources():
    data, sources = {}, {}
    for key, rel in SOURCES.items():
        raw = (REPO / rel).read_bytes()
        data[key] = json.loads(raw)
        sources[key] = {'path': rel, 'sha256': hashlib.sha256(raw).hexdigest()}
    return data, sources


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    data, sources = load_sources()
    if data['combined']['source_result_sha256'] != sources['replication']['sha256']:
        raise ValueError('The combination replay references a different replication result')
    vendor = (REPO / ECHARTS).read_bytes()
    if b'</script' in vendor.lower():
        raise ValueError('The chart asset cannot be embedded in an HTML script tag')
    manifest = {
        'historical_git_commit': '70ef5134c7164cedb68baed83f1b8c8f135dc0fe',
        'sources': sources,
        'embedded_assets': {'echarts': {'path': ECHARTS, 'sha256': hashlib.sha256(vendor).hexdigest()}},
    }
    outputs = {REPORT: render(data, vendor.decode()), INDEX: json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'}
    for path, content in outputs.items():
        if args.check:
            if path.read_text() != content:
                raise SystemExit(f'Outdated: {path}')
        else:
            path.write_text(content)


if __name__ == '__main__':
    main()
