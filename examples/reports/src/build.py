"""Build the unified reports and source index from shareable, frozen aggregates."""
import argparse
import hashlib
from html import escape as h, unescape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from report_catalog import FEATURED_REPORTS, GROUPS, HTML, document_url, inventory, report_button

HERE = Path(__file__).resolve().parents[1]
EXAMPLES = HERE.parent
ROOT = EXAMPLES.parent
STAGE = EXAMPLES / 'decision-transfer'
FROZEN = EXAMPLES / 'sim-to-real'
VENDOR = FROZEN / 'reports/vendor/echarts.min.js'
CASES = HERE / 'data/question-cases-v1.json'
HISTORICAL_CARDS = FROZEN / 'decision_lab/reports/cross-study-v1/per-card.json'
SPARSE_STUDIES = {
    'dryer': '四国烘干机', 'swiss': '瑞士家电规格', 'origin': '美国商品产地',
    'tshirt': '美国 T 恤', 'drone': '美国无人机配送', 'shoes': '美国运动鞋打分',
}
CRITICAL = EXAMPLES / '虚拟消费者模拟研究报告/04-MatrAIx批判性评估/MatrAIx项目的证据与边界.html'
LINK_STYLE = (HERE / 'src/report-links.css').read_text()
THEME = (HERE / 'src/report.css').read_text() + LINK_STYLE
REPORT_OVERVIEW = STAGE / 'reports/final.html'
BEHAVIOR = STAGE / 'reports/summary.html'
PURCHASE = STAGE / 'data/conclusions-v1.json'
DIAGNOSIS = {
    'replication': STAGE / 'data/final-replication-v1.json',
    'combined': STAGE / 'data/final-combined-v1.json',
    'matching': FROZEN / 'study/10_匹配与商品复验/results.json',
    'same_info': STAGE / 'data/personal-choice-qwen-v1.json',
    'anchors': FROZEN / 'decision_lab/reports/cross-study-v1/anchor-v1-results.json',
}
READING = (
    ('选项占比（%）', '100 份等权回答中有 60 份选「会」，占比就是 60%。AI 给出各选项的概率时，取大家对同一选项给出概率的平均。'),
    ('分布误差（百分点）', '越低越好。二选一题上，真人有 60% 选甲，AI 估成 80%，差了 20 个百分点。选项多时，看所有选项的占比差。'),
    ('个人概率误差（Brier）', '越低越好。假如真人最终选了甲，事先给甲 90% 的概率，比给甲 10% 得到的误差小。'),
    ('逐人答对率（%）', '越高越好。对每个人，把 AI 的最高概率选项与真人的实际答案一一比对。'),
    ('相对降幅（%）', '误差从 0.4 降到 0.3，少了 0.1，也就是原误差的四分之一，降幅为 25%。'),
    ('95% 区间和样本量', '改善的区间含有 0 时，现有样本还无法确认改善方向。问卷按受访者计算。同一个人的多道题仍算一个人。'),
)


def read_json(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def relative(path):
    return quote(os.path.relpath(path, HERE), safe='/')


def a(label, target):
    url = relative(target) if isinstance(target, Path) else target
    if Path(urlsplit(url).path).suffix.lower() in HTML:
        return report_button(label, url)
    return f'<a href="{h(url, quote=True)}">{h(label)}</a>'


def nav():
    return f'''<header class="site-bar">
<a class="brand" href="index.html">MatrAI X 报告中心</a>
<nav class="report-actions" aria-label="报告导航">{a('最终对照', 'overview.html')}
{a('原题对照', 'question-cases.html')} {a('问题与瓶颈', 'bottleneck.html')}</nav></header>'''


def html_page(title, contents, js=''):
    return (f'<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{h(title)}</title>'
            f'<style>\n{THEME}</style></head><body><main>\n{nav()}\n{contents}\n</main>\n{js}</body></html>\n')


def headline(title, description):
    return f'<div class="hero"><h1>{h(title)}</h1><p class="lead">{h(description)}</p></div>'


def table(headers, rows, *, klass=''):
    head = ''.join(f'<th scope="col">{h(key)}</th>' for key in headers)
    body = ''.join(f'<tr class="{klass}">' + ''.join(f'<td>{cell}</td>' for cell in line) + '</tr>' for line in rows)
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def glossary():
    return table(['指标', '怎么读'], [(h(name), h(text)) for name, text in READING])


def index_page():
    tiles = ''.join(
        f'<article class="tile"><h3>{a(title, href)}</h3><p>{h(description)}</p></article>'
        for href, title, description in FEATURED_REPORTS
    )
    return html_page('MatrAI X 报告中心', f"""
{headline('MatrAI X 报告中心', '如果让 AI 替一群人填问卷，它会答得像这群人吗？从主报告里的三张图开始。想追问原因、看原题或核对购买记录，可以直接选下面的报告。')}
<div class="report-actions report-actions--hero">
  {report_button('打开主报告', 'overview.html', primary=True)}
</div>
<section aria-labelledby="featured-title">
  <h2 id="featured-title">重点报告</h2>
  <div class="tiles">{tiles}</div>
</section>
<details class="reading panel">
  <summary>报告里的数字怎么读</summary>
  {glossary()}
  <p class="small">比较结果前，先确认是否用了同一题面、同一批评估对象、同一个模型和同样的资料。每道题的页面都说明控制条件和实际改动。</p>
</details>
<footer class="report-actions">{a('历史归档与全部资料', 'catalog.html')}
  <span>历轮原页、过程记录、演示和外部文献可在此查找。</span></footer>
""")


def question_drawer(case):
    key = h(case['id'], quote=True)
    shares = {arm['key']: arm['shares'] for arm in case['arms']}
    errors = [50 * sum(abs(a - b) for a, b in zip(shares[arm], shares['real'], strict=True))
              for arm in ('original', case['compare'])]
    return (f'<details class="question-drawer" id="{key}" data-case-id="{key}">'
            f'<summary id="question-title-{key}">{h(case["title"])}<span class="drawer-meta">{case["n"]} 人 · 分布误差 '
            f'{errors[0]:.2f} → {errors[1]:.2f} 个百分点</span></summary></details>')


def study_drawer(cases, summary, note, source=''):
    study = cases[0]['study_id']
    title = cases[0]['family']
    if study == 'tofu':
        primary, *additional = cases
        questions = (question_drawer(primary)
                     + f'<details class="additional-questions"><summary>其余 {len(additional)} 张可比的豆腐卡</summary>'
                     + ''.join(question_drawer(case) for case in additional) + '</details>')
    else:
        questions = ''.join(question_drawer(case) for case in cases)
    return f'''<details class="study-drawer" id="study-{h(study, quote=True)}">
  <summary>{h(title)}<span class="drawer-meta">{h(summary)}</span></summary>
  <div class="study-questions"><p class="small">{h(note)}</p>{questions}{source}</div>
</details>'''


def question_page(cases, replication):
    plans = read_json(HISTORICAL_CARDS)['plans']
    history = {key: study for plan in ('v1', 'wide-v1', 'clean-v1', 'external-v2')
               for key, study in plans[plan]['studies'].items()}
    total_questions = sum(study['estimable_cards'] for study in history.values())
    by_study = {}
    for case in cases:
        by_study.setdefault(case['study_id'], []).append(case)
    older, latest = [], []
    for key, questions in by_study.items():
        if key not in history:
            continue
        study = history[key]
        before, after = (study['card_tv'][arm] for arm in ('original', 'optimized'))
        summary = (f'{study["people"]} 人 · {study["estimable_cards"]} 个题目可比 · '
                   f'平均误差 {before:.2f} → {after:.2f} 个百分点')
        note = '这里选一道题演示。研究平均值比较项目单选与「改提示＋保留概率」合用。'
        if study['estimable_cards'] < study['cards']:
            note += f' 原评估有 {study["cards"]} 张卡，人数达到 20 的卡用于比较群体比例。'
        link = a('查这项研究的全部可比题', f'../sim-to-real/reports/cards.html#s-{key}')
        older.append(study_drawer(questions, summary, note, f'<p class="source">{link}</p>'))

    for key, frozen in zip(('nhanes', 'tofu'), replication['studies'], strict=True):
        results = frozen['results']
        before, after = (results['scores'][arm]['tv'] for arm in ('original', 'output_only'))
        caption = (f'{results["scored_people"]} 人 · {results["scored_cards"]} 个题目可比 · '
                   f'平均误差 {before:.2f} → {after:.2f} 个百分点')
        note = '两组使用同一模型、题目和画像，只改输出为完整概率。食品标签还另有 20 份真人试答对照。'
        if key == 'tofu':
            total = replication['freeze']['metadata']['tofu']['cards']
            note = (f'正式评估共有 {total} 张不同的商品卡。每张卡需至少 20 人作答才比较群体比例。'
                    '下方先展示作答人数最多的一张。研究平均值比较项目单选与保留概率。')
        latest.append(study_drawer(by_study[key], caption, note))

    sparse_rows = []
    for key, label in SPARSE_STUDIES.items():
        study = history[key]
        scores = study['individual']
        sparse_rows.append((a(label, f'../sim-to-real/reports/cards.html#s-{key}'), str(study['people']),
                            f'{study["cards"]:,}', str(max(card['people'] for card in study['questions'])),
                            f'{scores["brier"]["original"]:.3f}', f'{scores["brier"]["optimized"]:.3f}',
                            f'{scores["reference"]["brier"]:.3f}'))
    sparse_table = table(['研究', '评估人数', '题卡数', '同卡最多人数', '项目单选', '优化后', '统计参照'], sparse_rows)
    source_links = ' · '.join((
        a('聚合案例数据', CASES),
        a('末轮冻结结果', STAGE / 'data/final-replication-v1.json'),
        a('末轮复验规程', STAGE / 'docs/末轮复验规程.md'),
        a('历史四组方案', FROZEN / 'decision_lab/reports/cross-study-v1/formal-results.json'),
        a('更多历史逐题对照', FROZEN / 'reports/cards.html'),
    ))
    payload = json.dumps(cases, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    js = (f'<script id="case-data" type="application/json">{payload}</script>\n'
          f'<script>{VENDOR.read_text()}</script>\n<script>{(HERE / "src/cases.js").read_text()}</script>\n')
    return html_page('原题与答案分布｜MatrAI X', f"""
{headline('同一道题，真人和 AI 怎么答？', '先选一道你熟悉的问题。展开后，找「真人」那一柱，挑一个颜色，再看看其他柱里同一个颜色占了多少。数字越接近真人，那个选项就估得越准。')}
<section class="panel" aria-labelledby="start-case-title">
  <h2 id="start-case-title">先看一道真题</h2>
  <div class="report-actions">
    {a('买东西会看评价吗？', 'question-cases.html#SHOP12')}
    {a('涨价后会改买便宜货吗？', 'question-cases.html#INF3_a')}
    {a('买食品会看日期吗？', 'question-cases.html#CBQ700')}
    {a('两款豆腐，都可以不买？', 'question-cases.html#tofu-1')}
  </div>
</section>
<noscript><p>开启本地 JavaScript 可以切换图表。{a('查阅案例数据', CASES)}。</p></noscript>
<section class="panel sources" aria-labelledby="historic-questions-title">
  <h2 id="historic-questions-title">历轮研究 · {len(older)} 个题例</h2>
  <p>每项先选一道实际问题。点开后可以看原文、选项，以及改动的是指令、作答方式还是两者一起改。每项完整题目可另查逐题页。</p>
  <p class="source report-actions">{a(f'历轮逐题完整版（{total_questions} 个可比题目）', FROZEN / 'reports/cards.html')}
    {a('历轮技术报告', FROZEN / 'reports/index.html')}</p>
  {''.join(older)}
</section>
<section class="panel sources" aria-labelledby="latest-questions-title">
  <h2 id="latest-questions-title">末轮复验 · 食品标签和豆腐</h2>
  {''.join(latest)}
</section>
<section class="panel sources" aria-labelledby="individual-studies-title">
  <h2 id="individual-studies-title">每张卡作答人数较少的研究</h2>
  <details><summary>看另外 {len(sparse_rows)} 套研究的逐人评分</summary>
    <p>这些实验给不同人看不同的商品搭配或评分对象。同一道题最多只有 1 至 8 人作答。研究用个人概率误差（Brier）评分，越低越好。统计参照用其他真人的历史答案建立。</p>
    {sparse_table}
  </details>
</section>
<section class="panel case-head" id="case-viewer" hidden>
  <div class="summary-line" aria-live="polite">
    <p id="case-example"></p>
    <p id="case-result"></p>
  </div>
  <div id="products"></div>
  <details><summary>查看实际使用的原文题面和选项</summary>
    <blockquote id="original-question" translate="no"></blockquote>
    <ul id="original-options" translate="no"></ul>
    <p class="source"><a id="case-source">原始调查和题目来源</a> · 页首题名和图例为中文释义。</p>
  </details>
  <div class="tabs" aria-label="图表显示方式">
    <button type="button" data-chart-mode="distribution" aria-pressed="true">看答案占比</button>
    <button type="button" data-chart-mode="error" aria-pressed="false">看分布误差</button>
  </div>
  <h3 class="chart-title" id="chart-heading"></h3>
  <p class="small" id="chart-unit"></p>
  <ul class="legend" id="legend" aria-label="选项颜色"></ul>
  <p class="small" id="chart-scroll-note" hidden>横向滑动可查看所有组。</p>
  <div class="chart-frame" tabindex="0" aria-label="对照图，可横向滚动">
    <div id="question-chart" class="chart" role="img" aria-labelledby="chart-heading chart-unit"></div>
  </div>
  <dl class="control">
    <div><dt>哪些条件一样？</dt><dd id="fixed"></dd></div>
    <div><dt>哪一步改了？</dt><dd id="changed"></dd></div>
  </dl>
  <p id="case-note" class="small"></p>
  <details><summary>各组具体怎么做</summary><div id="method-table"></div></details>
  <details><summary>逐选项数字和误差变化</summary><div id="numeric-table"></div></details>
</section>
<section class="panel sources">
  <h2>计算口径和来源</h2>
  <p>单选组统计选中比例，概率组平均各选项概率。与真人相比，分布误差等于各选项占比差的绝对值之和的一半。误差越低越好。误差变化栏以项目单选为参照，减少表示更接近真人。小数位四舍五入。</p>
  <p>展开后的图使用该题的真实答案和同一评估样本。题目旁的前后数字是样本里的分布误差，完整研究的改善区间见对应结果。每组使用的额外资料在图下标出。</p>
  <p class="source">{source_links}</p>
</section>
""", js)


def purchase_page(data):
    gains = data['gains']
    counts = data['summary_counts']
    yogurt = next(row for row in gains if row['label'] == '酸奶（超市）')
    beer = next(row for row in data['negative'] if row['study'] == '美国啤酒')
    basket_study = STAGE / 'archive/2026-11-13-exploration/docs/下一次购物买不买这个品类.md'
    rows = [
        (h(row['label']), h(row['group']), str(row['people']), f"{row['baseline']:.4f}",
         f"{row['with_history']:.4f}", f"{row['relative']:+.1%}",
         f"[{row['ci95'][0]:+.4f}, {row['ci95'][1]:+.4f}]",
         '区间全高于 0' if row['holds'] else '仍不确定')
        for row in gains
    ]
    same = [(h(row['study']), f"{row['model']:.4f}", f"{row['statistics']:.4f}", f"{row['gap']:+.4f}")
            for row in data['negative']]
    payload = json.dumps(gains, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    js = (f'<script type="application/json" id="purchase-data">{payload}</script>'
          f'<script>{VENDOR.read_text()}</script><script>{(HERE / "src/purchase.js").read_text()}</script>')
    return html_page('本人记录与购买预测｜MatrAI X', f"""
{headline('知道过去买过什么，下次能猜得更准吗？', '收银小票记得一家人常买什么。先看这些真实记录能帮多少，再看把同样的资料交给 AI 有没有额外收益。')}
<section class="panel" aria-labelledby="purchase-example-title">
  <h2 id="purchase-example-title">下一趟去超市，这家人会买酸奶吗？</h2>
  <p>先试一种简单办法，按其他家庭平常买酸奶的比例来猜。再打开这一家的旧小票，看他家以往有多少趟买了酸奶，最近两次又买了哪款。
    前一个数字用来估「这趟买不买」，后两笔记录用来估「买了更可能是哪款」。</p>
  <p class="summary-line">把 <b>{yogurt['people']} 户</b> 的下一趟真实购物留来判卷。加上本人记录后，预测误差从
    <b>{yogurt['baseline']:.3f} 降到 {yogurt['with_history']:.3f}</b>，比原来少 <b>{yogurt['relative']:.1%}</b>。
    这个分数越低，给各选项的概率就越接近实际结果。</p>
  <p class="source">{a('查看酸奶实验和数据来源', basket_study)}</p>
</section>
<section class="panel sources">
  <h2>换成其他问卷和商品，效果还在吗？</h2>
  <p>{counts['comparisons']} 组问卷或交易对照中，{counts['interval_above_zero']} 组的改善区间全在零的右边，已有数据支持误差减少。</p>
  <p>先找写着「0」的竖线。<b>点越往右，表示误差减少越多。</b> 每条横线是估计的 95% 区间。
    横线碰到或跨过零时，现有样本还无法确认有没有改善。横轴单位是误差分数（Brier）的差。</p>
  <p class="small" id="purchase-scroll" hidden>横向滑动可查看完整区间。</p>
  <div class="chart-frame" tabindex="0" aria-label="改善区间图，可横向滚动">
    <div id="purchase-chart" style="height:440px" role="img" aria-label="十二组 Brier 误差下降与 95% 区间"></div>
  </div>
  <dl class="control">
    <div><dt>用什么来判卷？</dt><dd>同一组的两种做法都用同一批人或家庭的留出答案，题目和打分方法相同。</dd></div>
    <div><dt>多知道了什么？</dt><dd>原先从一群人常怎么选来估计。改法再看这个人真的选过或买过什么。有日期的订单还能把买不买与买哪款分开估。</dd></div>
  </dl>
  <details><summary>查看 12 组改前改后及区间</summary>
    <p class="small">改前、改后的 Brier 是误差，越低越好。相对降幅是下降量除以改前误差，不能与横轴数值直接互换。</p>
    {table(['任务', '资料与改法', '人数或户数', '改前误差', '改后误差', '相对降幅', '下降量的 95% 区间', '解读'], rows)}
  </details>
</section>
<section class="panel sources">
  <h2>同一份资料交给 AI，还能再进一步吗？</h2>
  <p>以美国啤酒问卷为例。把一群人平常怎么选、这个人此前的两次选择同时交给统计方法和 AI。
    考的是同一批人和同一批题，AI 的误差为 <b>{beer['model']:.3f}</b>，统计方法为 <b>{beer['statistics']:.3f}</b>。奶酪问卷也由统计方法胜出。</p>
  <details><summary>查看两种方法的精确分数</summary>
    {table(['问卷', 'AI 的误差（越低越好）', '统计方法的误差（越低越好）', 'AI 多出的误差'], same)}
  </details>
  <p>有两套收银数据只能配对同一户的两笔购买，先后顺序无从核对。英国电商的两项误差改善区间包含零。
    这些成绩的对象都是已有同类记录的人。若用来预测新顾客，还需要相应的交易数据验证。</p>
  <p class="source">{a('冻结数据与来源哈希', PURCHASE)} · {a('阶段原报告', BEHAVIOR)} · {a('英国电商原始数据', 'https://doi.org/10.24432/C5BW33')}</p>
</section>
""", js)



def bottleneck_page(d, cases):
    def source_ref(key, name):
        return a(name, DIAGNOSIS[key])

    food, tofu = (s['results'] for s in d['replication']['studies'])
    data_ref = source_ref('replication', '正式复验数据')
    settings = a('末轮规程', STAGE / 'docs/末轮复验规程.md')
    repeat_ref = source_ref('matching', '换模型和三次重复的结果')
    pipeline_ci = [r['contrasts']['original__output_only']['group'] for r in (food, tofu)]
    labels = ['美国食品标签问卷', '瑞典豆腐选购']
    chart = {'labels': labels,
             'argmax': [r['scores']['argmax']['tv'] for r in (food, tofu)],
             'full': [r['scores']['output_only']['tv'] for r in (food, tofu)]}
    production_rows = []
    for label, study, contrast in zip(labels, (food, tofu), pipeline_ci, strict=True):
        scores = study['scores']
        production_rows.append((
            h(label), f"{scores['original']['tv']:.2f}", f"{scores['output_only']['tv']:.2f}",
            f"<b>{contrast['improvement']:.2f}</b>",
            f"[{contrast['ci95'][0]:.2f}, {contrast['ci95'][1]:.2f}]",
            f"{100 * (scores['output_only']['accuracy'] - scores['original']['accuracy']):+.2f}",
        ))

    shopping = next(c for c in cases if c['id'] == 'SHOP12')
    shopping_arms = {a['key']: a['shares'][0] for a in shopping['arms']}
    compare = d['matching']['matching']
    pro = compare['summary']['pro/matched']
    qwen = compare['summary']['qwen/matched']
    pro_more = compare['summary']['pro/matched_traits']
    runs = pro['tv_by_run_pp']
    delta = pro['mean_run_tv_pp'] - pro['ensemble_tv_pp']
    origin = d['matching']['products']['origin']
    origin_contrast = next(c for c in origin['comparisons'] if c['before'] == 'choice' and c['after'] == 'probability')
    origin_low, origin_high = origin_contrast['ci95']

    anchors = d['anchors']['studies']['german']['results']['arms']
    beer = d['same_info']['studies']['beer']['brier']
    cheese = d['same_info']['studies']['italy']['brier']
    stats = d['combined']['scores']
    buy = tofu['scores']
    pilot = food['pilot']
    pilot_err = pilot['scores']
    pilot_shift = pilot_err['pilot_ai'] - pilot_err['pilot']
    pilot_low, pilot_high = pilot['contrasts']['pilot']['ci95']
    combined_gap = stats['combined']['brier'] - stats['refusal_only']['brier']
    combined_low, combined_high = (-x for x in reversed(d['combined']['combined_vs_reference']['refusal_only']['ci95']))

    findings = [
        ('知道本人以前的选择，有用吗？', '有对照支持', f"""
          德国番茄包装问卷给 AI 同题真人比例后，个人概率误差从 {anchors['optimized']['brier']:.3f}
          降到 {anchors['anchored']['brier']:.3f}。直接采用同一组真人比例为 {anchors['stratum_history']['brier']:.3f}。
          豆腐实验中，用本人两次选择更新统计，误差从 {buy['population']['brier']:.3f} 降到 {buy['own']['brier']:.3f}。
          把这两次记录换成别人的，误差是 {buy['other']['brier']:.3f}。""",
          '这些任务中，同题资料和本人实际选择能提供帮助。较早的 Pew 对照中，'
          f'固定 Pro 和匹配的人群，加入四项合成人格，分布误差从 {pro["mean_run_tv_pp"]:.2f} 降到 {pro_more["mean_run_tv_pp"]:.2f} 个百分点。'
          '这次改善较小，且未达到预定的 2 个百分点门槛。',
          f'{source_ref("anchors","加入真人比例的完整结果")} · {data_ref} · {repeat_ref}'),
        ('换一个 AI，成绩会变吗？', '有对照支持', f"""
          同题、同画像和概率输出条件下，购物问卷从 Qwen 换到 DeepSeek Pro 后，
          分布误差从 {qwen['mean_run_tv_pp']:.2f} 降到 {pro['mean_run_tv_pp']:.2f} 个百分点。
          在啤酒、奶酪问卷里，给 Qwen 和统计方法同样的群体预测与本人记录，
          统计误差分别为 {beer['stat_own']:.3f}、{cheese['stat_own']:.3f}，好于 Qwen 的
          {beer['qwen_own']:.3f}、{cheese['qwen_own']:.3f}。""",
          '选模型会影响结果，而且给足相同资料也可能处理不好。现有对照无法把差距拆成理解、推理和概率校准各占多少。',
          f'{repeat_ref} · {source_ref("same_info", "同资料对照数据")}'),
        ('让同一个 AI 多答几次，会稳很多吗？', '测到波动，范围有限',
          f'同一组 {compare["people_per_cohort"]} 个画像和同配置的 Pro 购物问卷重复三次，分布误差在 {min(runs):.2f}–{max(runs):.2f} 之间。'
          f'把三次概率直接平均，比三次分开评分的平均误差仅少 {delta:.2f} 个百分点。',
          '这套问卷上，多跑几次没有消除剩余误差。其他问卷和单个问题可能更不稳定，需单独重复。',
          repeat_ref),
        ('调整 AI 的作答设置，会更准吗？', '还需要单独测试',
          f'末轮模型设定了温度 0.7 和 top_p＝1，分别控制输出的随机程度与取样候选范围。'
          f'Pro 的 {d["replication"]["run"]["pro"]["successful"]} 次技术检查或正式评估请求均完成。',
          '参数有记录。末轮各组用同一设置，也没有逐档调整温度或 top_p 的对照，因此无法估计调参能补掉多少误差。',
          settings),
        ('问卷会选，实际也会买吗？', '要看真实订单',
          '食品标签是自报行为，豆腐是设定情境中的假设选择。每套正式评估 96 人，同一豆腐题卡还需要达到最低人数才比较比例。',
          '各题的真人比例仍有抽样误差。这些结果用来评估同题、同人群条件下的模拟，实际下单需另用真实交易验证。',
          f'{settings} · {a("真实购买与时间留出结果", "purchase-evidence.html")}'),
    ]
    explanations = ''.join(
        f'<details><summary>{h(topic)} <span class="diagnosis-status">{h(status)}</span></summary>'
        f'<p>{h(test)}</p><p>{h(conclusion)}</p><p class="source">{sources}</p></details>'
        for topic, status, test, conclusion, sources in findings
    )
    main_unit = (f'{labels[0]} {chart["argmax"][0]:.2f} → {chart["full"][0]:.2f}，'
                 f'{labels[1]} {chart["argmax"][1]:.2f} → {chart["full"][1]:.2f}。')
    payload = json.dumps(chart, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    js = (f'<script type="application/json" id="mechanism-data">{payload}</script>'
          f'<script>{VENDOR.read_text()}</script><script>{(HERE / "src/bottleneck.js").read_text()}</script>')
    return html_page('问题、改法与剩余差距｜MatrAI X', f"""
{headline('为什么 AI 常常答成一边倒？', '真人有不同的习惯，虚拟人却容易挤到同一个答案。我们换一种数答案的方法，再看哪一步还会猜错。')}
<section class="panel" aria-labelledby="mechanism-title">
  <h2 id="mechanism-title">每人只数一个答案，会漏掉什么？</h2>
  <p>问「购物前会看评价吗」，真人中 <b>{shopping_arms['real']:.1%}</b> 选「总是或几乎总是」。
    MatrAI X 项目单选估成 <b>{shopping_arms['original']:.1%}</b>，保留全部概率后是 <b>{shopping_arms['output_only']:.1%}</b>。</p>
  <p class="summary-line"><b>打个比方。</b> 假设十位虚拟顾客都说自己有 60% 的可能看评价、40% 的可能不看。
    每位只数最高项，就成了十位都看。把两个选项的概率都算进去，得到的是 60% 看、40% 不看。</p>
  <p>再用实验里的同一批 DeepSeek Pro 答案试这两种数法。灰柱只数每人的最高项，蓝柱保留所有选项，只改怎么数。
    柱越矮，整群人的答案比例越接近真人。单位是百分点。</p>
  <ul class="legend" aria-label="图例"><li><i class="diagnosis-key secondary" aria-hidden="true"></i>只保留最高项</li>
    <li><i class="diagnosis-key" aria-hidden="true"></i>汇总全部概率</li></ul>
  <div class="chart mechanism-chart" id="mechanism-chart" role="img" aria-label="{h(main_unit, quote=True)}">
    <noscript><p>{h(main_unit)}</p></noscript>
  </div>
  <p>如果从 MatrAI X 项目原来的单选流程开始比较，美国食品标签和瑞典豆腐的误差分别少了
    <b>{pipeline_ci[0]['improvement']:.2f}</b> 和 <b>{pipeline_ci[1]['improvement']:.2f}</b> 个百分点。</p>
  <details><summary>查看正式对照的改前、改后和区间</summary>
    <p class="small">表中改前用的是项目直接单选的成绩。上图的灰柱则是从完整概率中取最高项，用于检验数法本身。
    每项 96 人，固定模型、画像、题卡和评分。比例误差、下降量和区间以百分点计。
    最后一列是答对率变化。误差越低越好，下降量和答对率越高越好。</p>
    {table(['研究', 'MatrAI X 项目单选误差', '完整概率误差', '误差下降', '下降的 95% 区间', '答对率变化（百分点）'], production_rows)}
    <p>较早的商品产地选择对照中，模型固定为 Qwen。改为概率后，产地、价格等四项选择比例的平均误差从
      {origin['summary']['choice']['mean_run_tv_pp']:.2f} 到 {origin['summary']['probability']['mean_run_tv_pp']:.2f} 个百分点。
      改善的 95% 区间 [{origin_low:+.2f}, {origin_high:+.2f}] 跨 0，效果仍不确定。{repeat_ref}</p>
  </details>
  <p class="source report-actions">{a('打开购物评价原题', 'question-cases.html#SHOP12')} {data_ref}
    {a('Jang 等的独立研究', 'https://arxiv.org/abs/2607.25292v3')}</p>
</section>
<section class="panel sources" aria-labelledby="remaining">
  <h2 id="remaining">知道他买不买，还能猜出买哪款吗？</h2>
  <p>把两款豆腐摆在面前，可以先猜受访者会不会买，再猜会选哪款。我们把第一步的预测固定相同，第二步分别交给统计方法和 AI。</p>
  <p>只看在题里选了商品的人，选款交给统计方法时，误差为 <b>{stats['refusal_only']['conditional']:.3f}</b>，交给 AI 后升到
    <b>{stats['combined']['conditional']:.3f}</b>。只改这一步就出现差距。统计方法还用过另一批真人的答案，资料和方法各影响了多少，现有对照无法分开算。</p>
  <p>换回「一群人有多少选某项」这个问题，食品标签和豆腐改后的比例误差仍是 <b>{chart['full'][0]:.2f}</b> 和
    <b>{chart['full'][1]:.2f}</b> 个百分点。</p>
  <details><summary>看两步合起来的误差</summary>
    <p>全部选项都计入后，个人概率误差从 {stats['refusal_only']['brier']:.3f} 升到 {stats['combined']['brier']:.3f}，多了
      {combined_gap:.3f} 分。增加量的 95% 区间为 [{combined_low:+.3f}, {combined_high:+.3f}]。</p>
    <p>这是用同一批实验题做的事后补算。概率误差用 Brier 分数表示，越低越好。</p>
  </details>
  <p class="source">{source_ref('combined', '组合补算数据')}</p>
  <details id="pilot-interpretation"><summary>为什么 20 份试答加 AI 还看不出改善？</summary>
    <p>同一批 20 位试答者直接统计，误差是 {pilot_err['pilot']:.2f} 个百分点。每项与 AI 各占一半后，
    误差为 {pilot_err['pilot_ai']:.2f}，增加 {pilot_shift:.2f}。改善的 95% 区间为
    [{pilot_low:+.2f}, {pilot_high:+.2f}]，跨 0。用同一组评估者另抽 {pilot['alternate_draws']} 组试答者，
    有 {pilot['share_ai_better']['pilot']:.1%} 的情况下，混合误差低于直接统计。收益随试答样本而变，具体原因尚未单独分离。</p>
  </details>
</section>
<section class="panel sources" aria-labelledby="causes">
  <h2 id="causes">还有哪些地方会影响结果？</h2>
  <p>相关的真人资料能帮上一些忙，换模型也改变过成绩。简单多跑几次在那份购物问卷上收益很小。可以展开看每件事是怎样测的。</p>
  {explanations}
</section>
<section class="panel sources">
  <h2>优先改什么</h2>
  <ol>
    <li>只需估人群比例时，保留完整概率。在新问题上保留真人比例或统计方法作为对照。</li>
    <li>能拿到同类真人记录时，先用统计更新。把「买不买」和「买哪款」分别核对，再判断 AI 能不能帮到其中一步。</li>
    <li>要验证调参或换模型时，固定题面、画像和输出方式，一次只改一个因素。每组重复调用，分别报告平均误差和波动。</li>
  </ol>
  <p class="source">{a('回到最终对照', 'overview.html')} · {a('查看真题与答案分布', 'question-cases.html')}</p>
</section>
""", js)



def catalog_page(entries):
    grouped = {}
    sections = []
    for category in GROUPS:
        items = [entry for entry in entries if entry['category'] == category]
        grouped[category] = len(items)
        rows = []
        for entry in items:
            url = document_url(entry, HERE)
            if entry['type'] == 'HTML':
                button = report_button(entry['title'], url, mark='在线' if 'url' in entry else 'HTML')
            else:
                button = a(entry['title'], url)
            rows.append((button, h(entry['purpose']), h(entry['type']), h(entry.get('url', entry['path']))))
        sections.append(f'<details class="catalog-group" data-category="{h(category, quote=True)}"'
                        f'{" open" if category == GROUPS[0] else ""}>'
                        f'<summary>{h(category)} · {len(items)} 项</summary>'
                        + table(['文件', '定位', '格式', '原位置'], rows, klass='catalog-row') + '</details>')
    options = ''.join(f'<option>{h(name)}</option>' for name in GROUPS)
    formats = ''.join(f'<option>{h(kind)}</option>' for kind in sorted({entry['type'] for entry in entries}))
    js = '''<script>
(() => {
  const query = document.getElementById('report-query');
  const category = document.getElementById('report-category');
  const format = document.getElementById('report-format');
  const requestedFormat = new URLSearchParams(location.search).get('format');
  if ([...format.options].some(option => option.value === requestedFormat)) format.value = requestedFormat;
  function filter() {
    const needle = query.value.trim().toLowerCase();
    const active = needle || category.value || format.value;
    let count = 0;
    for (const group of document.querySelectorAll('[data-category]')) {
      let found = 0;
      for (const row of group.querySelectorAll('.catalog-row')) {
        row.hidden = (category.value && category.value !== group.dataset.category) ||
          (format.value && format.value !== row.cells[2].textContent) ||
          !row.textContent.toLowerCase().includes(needle);
        if (!row.hidden) found++;
      }
      count += found;
      group.hidden = !found;
      if (active) group.open = !!found;
    }
    document.getElementById('report-count').textContent = '显示 ' + count + ' 项';
  }
  query.addEventListener('input', filter);
  category.addEventListener('change', filter);
  format.addEventListener('change', filter);
  filter();
})();
</script>'''
    return html_page('历轮实验与材料索引｜MatrAI X', f"""
{headline('全部报告与配套材料', '按研究报告、阶段记录、演示、方法和原始资料分类。重点报告收录在报告中心。')}
<section class="panel">
  <p class="small">带「HTML」标记的按钮打开原网页。标记「在线」的论文通过公开全文页阅读。</p>
  <div class="catalog-controls">
    <label class="field">搜索标题或路径<input id="report-query" type="search" placeholder="例如：瑞士、问卷、报告"></label>
    <label class="field">类别<select id="report-category"><option value="">全部类别</option>{options}</select></label>
    <label class="field">格式<select id="report-format"><option value="">全部格式</option>{formats}</select></label>
  </div>
  <p class="small" id="report-count" aria-live="polite">共 {len(entries)} 项</p>
  {''.join(sections)}
</section>
<footer>{a('下载机器可读索引', HERE / 'data/catalog.json')} · 阅读度量口径见 {a('报告中心', 'index.html')}。</footer>
""", js), grouped


ATTR = re.compile(r"(?P<name>[\w:-]+)(?P<eq>\s*=\s*)(?P<q>['\"])(?P<value>.*?)(?P=q)", re.S)


class CopyLinks(HTMLParser):
    """Relocate document paths while preserving scripts, styles and source HTML."""
    def __init__(self, path, text):
        super().__init__()
        self.path = path
        self.offsets = [0]
        for match in re.finditer('\n', text):
            self.offsets.append(match.end())
        self.replacements = []

    def handle_starttag(self, tag, attrs):
        raw = self.get_starttag_text()

        def relocate(match):
            name = match['name'].lower()
            if name not in {'href', 'src', 'poster'}:
                return match[0]
            url = urlsplit(unescape(match['value']))
            if not url.path or url.scheme or url.netloc or url.path.startswith('/'):
                return match[0]
            target = (self.path.parent / unquote(url.path)).resolve()
            updated = urlunsplit(('', '', relative(target), url.query, url.fragment))
            return match['name'] + match['eq'] + match['q'] + h(updated, quote=True) + match['q']

        updated = ATTR.sub(relocate, raw)
        if updated != raw:
            line, offset = self.getpos()
            start = self.offsets[line - 1] + offset
            self.replacements.append((start, start + len(raw), updated))


def relocate_page(path):
    text = path.read_text()
    parser = CopyLinks(path, text)
    parser.feed(text)
    for start, end, replacement in reversed(parser.replacements):
        text = text[:start] + replacement + text[end:]
    return text


def project_page():
    text = relocate_page(CRITICAL).replace('</head>', f'<style>{LINK_STYLE}</style></head>', 1)
    back = ('<nav class="report-actions" aria-label="报告导航" style="max-width:1160px;margin:0 auto;'
            'padding:10px 24px;font:16px/1.5 system-ui,sans-serif;">'
            f'{a("报告中心", "index.html")}{a("看真人对照主报告", "overview.html")}</nav>')
    text = re.sub(r'<body\b[^>]*>', lambda match: match[0] + back, text, count=1, flags=re.I)
    guide = f"""
<section class="chapter" aria-labelledby="project-example-title">
  <h2 id="project-example-title">从一张人物卡看起</h2>
  <p class="intro">有一位受访者在问卷里填了「35–44 岁、大学本科」。MatrAI X 把这两项转进人物卡。
    卡片上还多了「工作 6–10 年」，那是系统按年龄推的，原问卷没问工作年限。</p>
  <p>先把问卷和人物卡放在一起看，就能分清哪些有原话支持。接下来要知道虚拟人能不能替目标人群回答，需要拿同一道题去问真人。</p>
  <p class="report-actions">{a('对照问卷与人物卡', '#paired-samples')} {a('看原论文测了什么', '#validation')}
    {a('看后来怎样与真人对照', 'overview.html')}</p>
</section>
"""
    start, marker, rest = text.partition('<noscript>')
    if not marker:
        raise ValueError('Project evidence report is missing its introduction boundary')
    return start + guide + marker + rest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    evidence = read_json(CASES)
    for path, expected in evidence['sources'].items():
        if sha(EXAMPLES / path) != expected:
            raise ValueError(f'Case evidence changed: {path}')
    cases = evidence['cases']
    if '</script' in VENDOR.read_text().lower():
        raise ValueError('Chart dependency is not safe to embed')
    entries = inventory()
    catalog_html, counts = catalog_page(entries)
    diagnosis = {key: read_json(path) for key, path in DIAGNOSIS.items()}
    by_file = (REPORT_OVERVIEW, BEHAVIOR, PURCHASE, CRITICAL, CASES, VENDOR, *DIAGNOSIS.values())
    catalog = {
        'scope': 'examples 中可随项目分享的 HTML、Word、Markdown 和 PDF，另含论文在线正文。报告中心页面可从首页查阅。',
        'counts': counts,
        'highlight_sources': {p.relative_to(ROOT).as_posix(): sha(p) for p in by_file},
        'documents': entries,
    }
    outputs = {
        HERE / 'index.html': index_page(),
        HERE / 'overview.html': relocate_page(REPORT_OVERVIEW),
        HERE / 'question-cases.html': question_page(cases, diagnosis['replication']),
        HERE / 'bottleneck.html': bottleneck_page(diagnosis, cases),
        HERE / 'purchase-evidence.html': purchase_page(read_json(PURCHASE)),
        HERE / 'project-evidence.html': project_page(),
        HERE / 'catalog.html': catalog_html,
        HERE / 'data/catalog.json': json.dumps(catalog, ensure_ascii=False, indent=2) + '\n',
    }
    for path, value in outputs.items():
        if args.check:
            if path.read_text() != value:
                raise SystemExit(f'Outdated: {path.relative_to(ROOT)}')
        else:
            path.write_text(value)


if __name__ == '__main__':
    main()
