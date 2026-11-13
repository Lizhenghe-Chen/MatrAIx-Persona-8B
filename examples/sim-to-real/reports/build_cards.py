"""Per-question report: real respondents, native MatrAIx, optimized output.

The story report argues; this page shows the raw comparison question by question.
Layout per study: one row of numbers, then a chart of the pooled marginal, then a
table of every estimable question with the three distributions side by side.

Cards with fewer than 20 evaluated respondents have no meaningful "distribution"
—one person's answer is 100% —so those studies show the pooled marginal only and
say why. Nothing is hidden: the count of skipped cards is printed.
"""
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CROSS = HERE.parent / 'decision_lab/reports/cross-study-v1'

LABELS = {
    'anes': '美国公共支出', 'pew168': '美国诈骗风险', 'shed': '美国消费调整',
    'pew13': '美国购物看法', 'dryer': '四国烘干机', 'swiss': '瑞士家电规格',
    'drone': '美国无人机配送', 'shoes': '美国运动鞋打分',
    'origin': '美国商品产地', 'packaging': '美国包装与拒买', 'pew111': '美国网购与达人',
    'german': '德国番茄包装', 'tshirt': '美国 T 恤', 'radiant': '西班牙悬挂番茄',
    'openecommerce': '美国线上购物调查（外部）',
}
ORDER = ['anes', 'pew13', 'pew168', 'shed', 'packaging', 'pew111', 'german', 'radiant',
         'openecommerce', 'dryer', 'swiss', 'drone', 'shoes', 'origin', 'tshirt']
ROLE = {
    'anes': '第一轮 · 政策态度', 'pew13': '第一轮 · 购物看法', 'pew168': '第一轮 · 风险判断',
    'shed': '第一轮 · 消费应对', 'dryer': '第一轮 · 商品选择', 'swiss': '第一轮 · 家电规格',
    'drone': '干净实验 · 配送二选一', 'shoes': '干净实验 · 1–7 打分',
    'origin': '铺开 · 商品选择', 'packaging': '铺开 · 包装与拒买', 'pew111': '铺开 · 购物行为',
    'german': '铺开 · 包装选择', 'tshirt': '铺开 · 商品选择', 'radiant': '铺开 · 食品选择',
    'openecommerce': '外部验证 · 行为与态度',
}


def load():
    path = CROSS / 'per-card.json'
    if not path.exists():
        raise SystemExit('per-card.json missing; run decision_lab.cross_study.per_card first')
    return json.loads(path.read_text())


def pick_studies(payload):
    """One entry per study; anchor-v1 duplicates two studies, so keep the widest arm set."""
    chosen = {}
    for plan, block in payload['plans'].items():
        for study, entry in block['studies'].items():
            if study not in chosen:
                chosen[study] = {'plan': plan, **entry}
                continue
            # Prefer the plan that has the native arm, else the one with more cards.
            current = chosen[study]
            if 'original' not in current['arms'] and 'original' in entry['arms']:
                chosen[study] = {'plan': plan, **entry}
            elif len(entry['arms']) > len(current['arms']) and 'original' in entry['arms']:
                chosen[study] = {'plan': plan, **entry}
    return chosen


def pct(value):
    return f'{100 * value:.1f}%'


def bar_cell(value, other, colour):
    """A tiny inline bar so a 4-way distribution is readable at a glance."""
    width = 100 * value
    gap = 100 * max(0.0, value - other)
    return (f'<span class="mini"><span class="mini-fill" style="width:{width:.1f}%;'
            f'background:{colour}"></span></span><b>{pct(value)}</b>')


def question_table(study, entry):
    rows = []
    for card in entry['questions']:
        if not card['estimable']:
            continue
        head = (f'<tr class="qhead"><th colspan="5">{html.escape(card["question"])}'
                f'<span class="small"> · {html.escape(card["prompt"][:110])}'
                f' · {card["people"]} 人作答</span></th></tr>')
        rows.append(head)
        for index, option in enumerate(card['options']):
            truth = card['truth'][index]
            native = card['original'][index] if card['original'] else None
            optimized = card['optimized'][index]
            native_cell = ('—' if native is None else bar_cell(native, truth, '#a15e38'))
            rows.append(
                f'<tr><th>{html.escape(option["label"][:120])}</th>'
                f'<td>{bar_cell(truth, truth, "#14372f")}</td>'
                f'<td>{native_cell}</td>'
                f'<td>{bar_cell(optimized, truth, "#5358a5")}</td>'
                f'<td>{"—" if native is None else f"{100*(native-truth):+.1f}"}</td></tr>')
        native_tv = '—' if card['tv_original'] is None else f"{card['tv_original']:.1f}pp"
        rows.append(
            f'<tr class="qfoot"><th>误差（TV，越低越好）</th><td>—</td>'
            f'<td>{native_tv}</td><td>{card["tv_optimized"]:.1f}pp</td><td>—</td></tr>')
    return ''.join(rows)


def chart_payload(chosen):
    """Pooled marginal per study, for one chart of all fourteen."""
    rows = []
    for study in ORDER:
        entry = chosen.get(study)
        if not entry or not entry['pooled']:
            continue
        pooled = entry['pooled']
        rows.append({'study': study, 'label': LABELS.get(study, study),
                     'original': pooled['tv_original'], 'optimized': pooled['tv_optimized'],
                     'cards': pooled['cards']})
    return rows


def build():
    payload = load()
    chosen = pick_studies(payload)
    sections = []
    for study in ORDER:
        entry = chosen.get(study)
        if not entry:
            continue
        pooled = entry['pooled']
        cards_total = entry['cards']
        estimable = entry['estimable_cards']
        has_native = 'original' in entry['arms']
        metrics = entry.get('card_tv')
        if metrics and metrics['original'] is not None:
            native_headline = f"逐题平均误差 {metrics['original']:.1f}pp"
        elif has_native:
            native_headline = '不可估'
        else:
            native_headline = '未运行'
        if metrics:
            optimized_headline = f"逐题平均误差 {metrics['optimized']:.1f}pp"
        else:
            optimized_headline = '不可估'
        rows = question_table(study, entry) if estimable else ''
        table = ''
        if estimable:
            table = (
                '<div class="table-wrap"><table class="qtable">'
                f'<caption>{LABELS.get(study, study)}：{estimable} 道可估题的三种分布'
                f'（另 {cards_total - estimable} 道题因每题人数不足 20 未逐题列出，'
                '已并入下方汇总）</caption>'
                '<thead><tr><th>选项</th><th>真人</th><th>原版 MatrAIx</th>'
                '<th>优化后</th><th>原版−真人</th></tr></thead><tbody>'
                + rows + '</tbody></table></div>')
        reason = ''
        if not estimable:
            reason = (f'<p class="small">这套问卷的 {cards_total} 道题几乎人人不同'
                      f'（平均每道题只有 {entry["people"] / max(1, cards_total):.1f} 人），'
                      '单题分布没有意义——一个人的答案就是 100%。因此只用下方"全部题目汇总"呈现，'
                      '不逐题列出。</p>')
        if not has_native:
            reason += ('<p class="small">这套研究只跑了优化臂，没有原版单选数据；'
                       '当时的设计目标是外部验证，为节省费用没有重复跑原生输出。</p>')
        sections.append(
            f'<section id="s-{study}" class="study">'
            f'<span class="number">{html.escape(ROLE.get(study, ""))}</span>'
            f'<h2>{html.escape(LABELS.get(study, study))}</h2>'
            '<div class="grid3">'
            f'<article class="card"><span class="tag">观测规模</span><h3>{entry["people"]} 人 / {cards_total} 题</h3>'
            f'<p>其中 {estimable} 道题达到"至少 20 人"，可做逐题分布比较。</p></article>'
            f'<article class="card"><span class="tag">原版 MatrAIx</span>'
            f'<h3>{native_headline}</h3>'
            '<p>把每个模型实例当成一个真人，只看它选的选项。</p></article>'
            f'<article class="card"><span class="tag">优化后</span>'
            f'<h3>{optimized_headline}</h3>'
            '<p>取它对每个选项给出的概率，再按人平均。</p></article>'
            '</div>'
            f'<p class="small">「逐题平均误差」= 每道可估题的 TV 取平均，与技术版报告的同一个数；'
            f'{"这套没有一道题达到 20 人，因此该指标不可估。" if not metrics else ""}</p>'
            f'<figure><h3>全部题目汇总：三个分布落在哪里</h3>'
            f'<div id="pool-{study}" class="echart" '
            f'style="height:{240 if pooled and pooled["options"] <= 4 else 300}px"></div>'
            '<figcaption>按选项位置对齐后的合并视图，用来看质量集中在哪里；'
            '<strong>不同题目的选项数不同，位置之间不可比，它不是误差指标。</strong>'
            '逐题结论看下表。</figcaption></figure>'
            '<p class="small">最后一列「原版−真人」＝ 原版占比减真人占比，正数表示高估、负数表示低估。'
            '它逐选项指出了偏差方向。</p>'
            + reason + table + '</section>')

    data = {'pooled': {study: chosen[study]['pooled'] for study in ORDER if study in chosen},
            'labels': {study: LABELS.get(study, study) for study in ORDER if study in chosen},
            'summary': chart_payload(chosen)}
    data_json = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')

    overview = ['<div class="table-wrap"><table style="min-width:720px">'
                '<caption>十四套研究一览：可估题数与逐题平均误差</caption>'
                '<thead><tr><th>研究</th><th>人数</th><th>题目</th><th>可估题</th>'
                '<th>原版 MatrAIx</th><th>优化后</th></tr></thead><tbody>']
    for study in ORDER:
        entry = chosen.get(study)
        if not entry:
            continue
        metrics = entry.get('card_tv')
        native_tv = ('—' if not metrics or metrics['original'] is None
                     else f"{metrics['original']:.1f}pp")
        optimized_tv = '—' if not metrics else f"{metrics['optimized']:.1f}pp"
        overview.append(
            f'<tr><th><a href="#s-{study}">{html.escape(LABELS.get(study, study))}</a></th>'
            f'<td>{entry["people"]}</td><td>{entry["cards"]}</td>'
            f'<td>{entry["estimable_cards"]}</td><td>{native_tv}</td>'
            f'<td>{optimized_tv}</td></tr>')
    overview.append('</tbody></table></div>'
                    '<p class="small">「可估题」= 至少 20 名被测者答过同一道题。'
                    '为 0 的研究，单题分布不可估（一个人的答案就是 100%），'
                    '只能看全部题目的汇总视图。数字与技术版报告逐套一致。</p>')
    overview = ''.join(overview)

    badges = ''.join(
        f'<a href="#s-{study}">{html.escape(LABELS.get(study, study))}</a>'
        for study in ORDER if study in chosen)

    page = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="description" content="逐题对比：真人选择分布、原版 MatrAIx 选择分布、'
            '优化后概率分布。">'
            '<title>逐题对比：真人 vs 原版 vs 优化｜MatrAIx</title>'
            f'<style>{STYLE}{EXTRA}</style></head><body>'
            '<header><div class="hero"><div class="eyebrow">MATRAIX · 逐题明细 · 2026 年 11 月</div>'
            '<h1>每一道题，<br>真人怎么分、AI 怎么分</h1>'
            '<p class="lead">这一页不做论证，只摆原始对比：<strong>同一道题</strong>上，'
            '真人 96 人的选项分布、原版 MatrAIx「只选一个」的分布、优化后「给概率」的分布。'
            '三种分布用的是同一批选项，可以直接并排看。</p>'
            '<div class="callout"><strong>怎么读这三行</strong>：'
            '「真人」是实际作答者的选中比例；'
            '「原版 MatrAIx」是把 96 次模型输出当成 96 个人投票（它每次只选一个，所以天然是分布）；'
            '「优化后」是模型给每个选项的概率取平均。'
            '后两者的误差（TV，百分点）列在同一行，越低越好。</div>'
            '<div class="badges">' + badges + '</div>'
            '</div></header>'
            '<main><section id="overview"><span class="number">概览</span>'
            '<h2>先看全局，再逐题</h2>' + overview + '</section>'
            + ''.join(sections) + '</main>'
            f'<script id="card-data" type="application/json">{data_json}</script>'
            f'<script>{ECHARTS}</script><script>{CHARTS}</script>'
            '</body></html>')
    (HERE / 'cards.html').write_text(page)
    print(f'Built per-question report: {HERE / "cards.html"} ({len(page):,} bytes)')


EXTRA = """
.study{border-top:1px solid var(--line,#d8e1da);padding-top:28px;margin-top:34px}
.badges{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0 0}
.badges a{font-size:14px;padding:6px 12px;border:1px solid #cdd9d1;border-radius:999px;
  color:#14372f;text-decoration:none;background:#fff}
.badges a:hover{border-color:#117b70}
table.qtable{font-size:14px}
table.qtable tr.qhead th{background:#eef3ef;text-align:left;font-weight:600;padding:10px 12px;
  border-top:1px solid #d8e1da}
table.qtable tr.qfoot th,table.qtable tr.qfoot td{background:#fafbfa;color:#566a63;font-weight:500}
.mini{display:inline-block;width:74px;height:8px;background:#eef1ef;border-radius:4px;
  overflow:hidden;vertical-align:middle;margin-right:8px}
.mini-fill{display:block;height:100%}
table.qtable td,table.qtable th{padding:8px 12px;vertical-align:middle}
"""

STYLE = (HERE / 'style.css').read_text()
ECHARTS = (HERE / 'vendor/echarts.min.js').read_text()
CHARTS = (HERE / 'charts_cards.js').read_text()

if __name__ == '__main__':
    build()
