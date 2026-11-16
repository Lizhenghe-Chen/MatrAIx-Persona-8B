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
             pew168='诈骗风险（Pew）', shed='美国涨价应对', swiss='瑞士家电',
             origin='美国商品产地', packaging='美国啤酒包装', pew111='网购与达人（Pew）',
             german='德国番茄包装', tshirt='美国 T 恤', radiant='西班牙番茄',
             drone='美国无人机配送', shoes='美国运动鞋评分', openecommerce='美国 Open eCommerce')

PROJECT_BASELINE = 'MatrAI X 项目（单选）'
NEUTRAL, PROBABILITY, COMBINED, STATISTICS = '#a2b0c5', '#638bbd', '#234fa0', '#19815f'


def link(label, target):
    parts = urlsplit(target)
    url = target if parts.scheme else urlunsplit(
        ('', '', quote('../../../' + parts.path, safe='/'), parts.query, parts.fragment)
    )
    if Path(parts.path).suffix.lower() in HTML:
        return report_button(label, url)
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
  <p class="lead"><b>发现的问题</b>　以买食品会不会看包装日期为例，真人中 <b>{real:.1%}</b> 选「有时」，
    MatrAI X 项目单选估成 <b>{before:.1%}</b>。改用完整概率后降到 <b>{after:.1%}</b>。</p>
  <p class="finding-note"><b>原因与改法</b>　每人只给最高项投一票，会把其他选项的概率都丢掉。
    对同一批 AI 答案保留所有选项的概率，再按相同权重汇总，两项复验的群体比例误差都下降了。</p>
  <p class="source report-actions">{link('看食品日期原题', CENTER + 'question-cases.html#CBQ700')}
    {link('看只改汇总的对照', CENTER + 'bottleneck.html#mechanism-title')}</p>"""


def bottleneck_summary(d):
    food, tofu = (study['results'] for study in d['replication']['studies'])
    after = [r['scores']['output_only']['tv'] for r in (food, tofu)]
    combined = d['combined']['scores']
    matching = d['repeat']['matching']['summary']
    qwen, pro = (matching[f'{model}/matched'] for model in ('qwen', 'pro'))
    runs = pro['tv_by_run_pp']
    averaging_gain = pro['mean_run_tv_pp'] - pro['ensemble_tv_pp']
    return f"""
  <p>保留概率后，食品标签和豆腐复验的群体比例误差仍有
    <b>{after[0]:.2f}</b> 和 <b>{after[1]:.2f}</b> 个百分点。豆腐的组合对照固定了「买不买」的预测，
    选款用统计时，个人概率误差是 <b>{combined['refusal_only']['brier']:.3f}</b>，改用 AI 选款后上升到
    <b>{combined['combined']['brier']:.3f}</b>。差距出现在选款这一步。统计选款用过其他真人的训练答案。</p>
  <dl class="bottleneck-factors">
    <div><dt>真人资料</dt><dd>豆腐实验用本人的两次选择更新统计，个人概率误差从
      {tofu['scores']['population']['brier']:.3f} 降到 {tofu['scores']['own']['brier']:.3f}。与商品直接相关的记录能提供帮助。</dd></div>
    <div><dt>模型的影响</dt><dd>早期购物问卷固定题目和画像，Qwen 换成 DeepSeek Pro 后，
      群体误差从 {qwen['mean_run_tv_pp']:.2f} 降到 {pro['mean_run_tv_pp']:.2f} 个百分点。</dd></div>
    <div><dt>随机波动</dt><dd>同一套购物问卷用 Pro 重复三次，误差在 {min(runs):.2f} 至 {max(runs):.2f} 个百分点之间。
      平均三次预测，误差比三次单独评分的平均值再少 {averaging_gain:.2f} 个百分点。</dd></div>
    <div><dt>温度等运行参数</dt><dd>末轮固定温度 0.7、top_p＝1。两项参数都影响作答时的取样。
      这轮缺少单独改变参数的对照，调参能带来多少改善仍未知。</dd></div>
  </dl>
  <p class="note">这些对照只量出了各自条件下的效果。剩余误差还有多少来自画像遗漏、模型能力或样本波动，现有数据无法分开估计。</p>
  <p class="source">{link('查看瓶颈证据与实验条件', CENTER + 'bottleneck.html#remaining')}</p>"""


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
    improvements = [r['contrasts']['original__output_only']['group']['improvement'] for r in (nhanes, tofu)]

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
        f'<div><dt>{h(name)}</dt><dd>误差少 <strong>{gain:.2f}</strong> 个百分点</dd></div>'
        for name, gain in zip(survey_names, improvements, strict=True)
    )
    combined_figure = f"""
<figure class="panel primary" id="combined" aria-labelledby="combined-title">
  <figcaption>
    <h2 id="combined-title">本人记录和 AI 合用，准了多少？</h2>
    <p class="meta">瑞典豆腐选购 · 同一批 {combined['people']} 人的 {combined['tasks']} 次选择 · 个人概率误差，越低越好</p>
  </figcaption>
  <div class="main-grid">
    {combined_chart}
    <div class="stats">
      <div>
        <span class="big-number">{reduction:.1%}</span>
        <p><strong>比 MatrAI X 项目单选低</strong></p>
        <p>误差 {original:.3f} → {hybrid:.3f}</p>
      </div>
      <div class="best">
        <p><strong>两步都用统计最准确（{statistics:.3f}）</strong></p>
        <p>同样用本人记录判断买不买，把选款交给 AI 后，误差增加 {added_error:.1%}。</p>
      </div>
    </div>
  </div>
  <p class="note method-note"><b>合用的意思</b> 用本人的两次真实选择帮忙判断买不买，再让 AI 判断会选哪款。结果来自同一批数据的事后补算。</p>
  <p class="source report-actions">{source('combined', '组合补算数据')}
    {link('本人记录与购买预测', CENTER + 'purchase-evidence.html')}</p>
</figure>"""
    body = f"""
<div class="secondary">
  <figure class="panel primary" id="survey" aria-labelledby="survey-title">
    <figcaption>
      <h2 id="survey-title">保留概率，误差少了多少？</h2>
      <p class="meta">每项 96 人，固定模型、画像和题目 · 群体比例误差（百分点），越低越好</p>
      <ul class="key" aria-label="图例">
        <li><i class="swatch old" aria-hidden="true"></i>{PROJECT_BASELINE}</li>
        <li><i class="swatch" aria-hidden="true"></i>保留全部概率</li>
      </ul>
    </figcaption>
    {survey_chart}
    <dl class="gains">{gains}</dl>
    <p class="note">人群比例更准了，两项研究的逐人答对率各提高约 1 个百分点。</p>
    <p class="source report-actions">{source('replication', '正式复验数据')}
      {link('按研究查看真人原题', CENTER + 'question-cases.html')}</p>
  </figure>
  <figure class="panel" id="pilot" aria-labelledby="pilot-title">
    <figcaption>
      <h2 id="pilot-title">20 份真人试答，加 AI 有用吗？</h2>
      <p class="meta">美国食品标签问卷 · 群体比例误差（百分点），越低越好</p>
    </figcaption>
    {pilot_chart}
    <div class="pilot-takeaway">
      <p><b>加 AI 后误差增加 {pilot_difference:.2f} 个百分点。</b></p>
      <p class="note">误差下降量的 95% 区间为 {pilot_interval} 个百分点，跨过 0，效果仍不确定。</p>
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
    cluster = d['cluster']['summary']
    content += details(
        '十五套问卷的完整对照',
        f"<p>历史汇总的 {cluster['studies']} 套对照全部落后于各自采用的真人统计参照，"
        '这些参照使用其他真人的历史答案或用其训练模型。群体比例误差单位为百分点，'
        '逐人答对率取最高概率。— 表示题卡没有足够重复或结果未提供。</p>'
        + table(['研究', '人数', 'MatrAI X 项目比例误差', '改后比例误差', '比例改善区间', '项目 Brier',
                 '改后 Brier', '项目答对率', '改后答对率', '来源'], frozen_rows)
        + f'''<p class="source report-actions">{source("cluster", "十四套历史比较")}
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
