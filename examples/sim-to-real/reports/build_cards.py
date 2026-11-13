"""Per-question report: real respondents, native MatrAIx, optimized output.

Layout is two levels of drawers so that 460 questions stay scannable:

* one drawer per study, collapsed by default, its header carrying the three numbers
  that matter (people, estimable questions, and the two error totals);
* one drawer per question. Collapsed, it shows a miniature distribution strip per
  series, so questions can be compared by eye without opening anything. Opened, it
  draws a grouped bar chart plus the exact shares.

Charts are created only when a drawer is first opened, so the page stays light even
though every question is on it.

Cards with fewer than 20 evaluated respondents have no meaningful distribution —
one person's answer is 100% — so those studies show a single pooled chart and say
why. Nothing is hidden: the skipped count is printed.
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
SERIES = (('truth', '真人', '#14372f'), ('original', '原版 MatrAIx', '#a15e38'),
          ('optimized', '优化后', '#5358a5'))


def load():
    path = CROSS / 'per-card.json'
    if not path.exists():
        raise SystemExit('per-card.json missing; run decision_lab.cross_study.per_card first')
    return json.loads(path.read_text())


def pick_studies(payload):
    """One entry per study; a study can appear in several plans, keep the widest arm set."""
    chosen = {}
    for plan, block in payload['plans'].items():
        for study, entry in block['studies'].items():
            if study not in chosen:
                chosen[study] = {'plan': plan, **entry}
                continue
            current = chosen[study]
            if 'original' not in current['arms'] and 'original' in entry['arms']:
                chosen[study] = {'plan': plan, **entry}
    return chosen


def pct(value):
    return f'{100 * value:.1f}%'


def strip(card):
    """Miniature distribution strip: one thin row per series, segments proportional to shares."""
    rows = []
    for key, name, colour in SERIES:
        values = card.get(key)
        if not values:
            continue
        segments = ''.join(
            f'<i style="flex:{max(value, 0.0005):.4f};background:{colour};'
            f'opacity:{1 - 0.3 * index:.2f}"></i>'
            for index, value in enumerate(values))
        rows.append(f'<span class="strip-row"><b class="strip-name">{name[:2]}</b>'
                    f'<span class="strip">{segments}</span></span>')
    return ''.join(rows)


def direction_cell(delta):
    """Over- or under-estimate: a direction, deliberately not a good/bad colour."""
    if delta is None:
        return '<span class="dir muted">—</span>'
    value = 100 * delta
    if abs(value) < DIRECTION_PP:
        return f'<span class="dir flat">{value:+.1f}</span>'
    kind = 'up' if value > 0 else 'down'
    word = '高估' if value > 0 else '低估'
    return f'<span class="dir {kind}" title="{word}">{value:+.1f}</span>'


def question_rows(card):
    who, gain, state = verdict(card['tv_original'], card['tv_optimized'])
    rows = []
    for index, option in enumerate(card['options']):
        truth = card['truth'][index]
        native = card['original'][index] if card['original'] else None
        optimized = card['optimized'][index]
        delta = None if native is None else native - truth
        rows.append(f'<tr><th>{html.escape(option["label"][:130])}</th>'
                    f'<td>{pct(truth)}</td>'
                    f'<td>{"—" if native is None else pct(native)}</td>'
                    f'<td>{pct(optimized)}</td><td>{direction_cell(delta)}</td></tr>')
    rows.append(
        '<tr class="qfoot"><th>误差（TV，越低越好）</th><td>—</td>'
        f'<td>{tv_cell(card["tv_original"], state, who == "native")}</td>'
        f'<td>{tv_cell(card["tv_optimized"], state, who == "optimized")}</td>'
        f'<td>{verdict_chip(card["tv_original"], card["tv_optimized"])}</td></tr>')
    return ''.join(rows)


GATE_PP = 2.0          # the project's declared gate for a meaningful distribution difference
DIRECTION_PP = 1.0     # below this an over/under-estimate is not worth colouring


def verdict(native_tv, optimized_tv):
    """Compare two error totals. Returns (who, gain, state) with state in good/bad/tie."""
    if native_tv is None or optimized_tv is None:
        return None, None, 'unknown'
    gain = native_tv - optimized_tv          # positive = optimized is better
    if abs(gain) < GATE_PP:
        return 'tie', gain, 'tie'
    return ('optimized' if gain > 0 else 'native'), gain, ('good' if gain > 0 else 'bad')


def tv_cell(value, state, is_winner):
    """One error number. The winner is emphasised; the other is muted, never red."""
    if value is None:
        return '<span class="tv muted">—</span>'
    text = f'{value:.1f}'
    if state == 'tie':
        return f'<span class="tv tie">{text}<i>≈</i></span>'
    if is_winner:
        return f'<span class="tv win">{text}<i>▼</i></span>'
    return f'<span class="tv lose">{text}</span>'


def verdict_chip(native_tv, optimized_tv, prefix=''):
    who, gain, state = verdict(native_tv, optimized_tv)
    if state == 'unknown':
        return '<span class="chip unknown">无法比较</span>'
    if state == 'tie':
        return '<span class="chip tie">≈ 两者相当</span>'
    # The verdict chip carries the good/bad reading, so the detail cells need not shout.
    if who == 'optimized':
        return f'<span class="chip win">优化更准 {abs(gain):.1f}pp</span>'
    return f'<span class="chip lose">原版更准 {abs(gain):.1f}pp</span>'


def option_key(card):
    """Numbered key under the chart: the bars carry numbers, the text lives here."""
    items = ''.join(
        f'<li><b>{index + 1}</b>{html.escape(option["label"])}</li>'
        for index, option in enumerate(card['options']))
    return f'<ol class="opt-key">{items}</ol>'


def study_section(study, entry, index):
    label = LABELS.get(study, study)
    metrics = entry.get('card_tv')
    estimable, cards = entry['estimable_cards'], entry['cards']
    has_native = 'original' in entry['arms']
    native_value = metrics['original'] if metrics else None
    optimized_value = metrics['optimized'] if metrics else None
    who, gain, state = verdict(native_value, optimized_value)
    coverage = f'{estimable}/{cards} 题可估'

    body = []
    if not estimable:
        body.append(f'<p class="small">这套问卷的 {cards} 道题几乎人人不同'
                    f'（平均每道题 {entry["people"] / max(1, cards):.1f} 人作答），'
                    '单题分布没有意义——一个人选了什么就是 100%。'
                    '因此这里只给"全部题目汇总"的视图，不编造逐题分布。</p>')
        body.append(f'<div class="echart pooled" id="pool-{study}" data-pool="{study}"></div>')
    else:
        if not has_native:
            body.append('<p class="small">这套只跑了优化臂，没有原版单选数据；'
                        '当时的设计目标是外部验证，为省费用没有重复跑原生输出。</p>')
        if estimable < cards:
            body.append(f'<p class="small">另有 {cards - estimable} 道题人数不足 20，'
                        '未逐题列出。</p>')
        items = []
        for card_index, card in enumerate(entry['questions']):
            if not card['estimable']:
                continue
            q_who, q_gain, q_state = verdict(card['tv_original'], card['tv_optimized'])
            items.append(
                '<details class="q-drawer">'
                '<summary>'
                '<span class="q-head">'
                f'<code class="qid">{html.escape(card["question"])}</code>'
                f'<span class="qprompt">{html.escape(card["prompt"][:80])}</span>'
                '</span>'
                f'<span class="qstrip">{strip(card)}</span>'
                f'<span class="qtv">'
                f'{tv_cell(card["tv_original"], q_state, q_who == "native")}'
                f'{tv_cell(card["tv_optimized"], q_state, q_who == "optimized")}'
                '</span>'
                f'<span class="qpeople">{card["people"]} 人</span>'
                '</summary>'
                '<div class="q-body">'
                f'<div class="echart qchart" id="qchart-{study}-{card_index}"></div>'
                '<div class="table-wrap"><table class="qtable">'
                '<thead><tr><th>选项</th><th>真人</th><th>原版 MatrAIx</th><th>优化后</th>'
                '<th>原版−真人</th></tr></thead><tbody>'
                + question_rows(card) + '</tbody></table></div>'
                + option_key(card)
                + '</div></details>')
        body.append('<div class="qlist">' + ''.join(items) + '</div>')

    return (f'<section class="study" id="s-{study}">'
            '<details class="study-drawer">'
            '<summary>'
            f'<span class="order">{index:02d}</span>'
            f'<span class="sname">{html.escape(label)}</span>'
            f'<span class="srole">{html.escape(ROLE.get(study, ""))}</span>'
            f'<span class="smeta">{entry["people"]} 人 · {coverage}</span>'
            f'<span class="snums">'
            f'<span class="snum-native">{tv_cell(native_value, state, who == "native")} '
            f'<i>原版</i></span>'
            f'<span class="snum-optimized">{tv_cell(optimized_value, state, who == "optimized")} '
            f'<i>优化</i></span>'
            f'{verdict_chip(native_value, optimized_value)}</span>'
            '</summary>'
            '<div class="study-body">' + ''.join(body) + '</div>'
            '</details></section>')


def build():
    payload = load()
    chosen = pick_studies(payload)
    studies = [(study, chosen[study]) for study in ORDER if study in chosen]

    overview = ['<div class="table-wrap"><table style="min-width:700px">'
                '<caption>十四套研究：可估题数与逐题平均误差（点研究名展开逐题）</caption>'
                '<thead><tr><th>研究</th><th>人数</th><th>题目</th><th>可估题</th>'
                '<th>原版 MatrAIx</th><th>优化后</th><th>谁更准</th></tr></thead><tbody>']
    for study, entry in studies:
        metrics = entry.get('card_tv')
        native_value = metrics['original'] if metrics else None
        optimized_value = metrics['optimized'] if metrics else None
        who, gain, state = verdict(native_value, optimized_value)
        overview.append(
            f'<tr><th><a href="#s-{study}">{html.escape(LABELS.get(study, study))}</a></th>'
            f'<td>{entry["people"]}</td><td>{entry["cards"]}</td>'
            f'<td>{entry["estimable_cards"]}</td>'
            f'<td>{tv_cell(native_value, state, who == "native")}</td>'
            f'<td>{tv_cell(optimized_value, state, who == "optimized")}</td>'
            f'<td>{verdict_chip(native_value, optimized_value)}</td></tr>')
    overview.append('</tbody></table></div>'
                    '<p class="small">「可估题」＝至少 20 名被测者答过同一道题。'
                    '为 0 的研究，单题分布不可估（一个人的答案就是 100%），'
                    '只能看全部题目的汇总视图。这些数字与技术版报告逐套一致。</p>')
    overview = ''.join(overview)

    charts, pooled = {}, {}
    for study, entry in studies:
        charts[study] = [
            {'id': card['question'],
             'options': [option['label'] for option in card['options']],
             'truth': card['truth'], 'original': card['original'],
             'optimized': card['optimized'],
             'tv_original': card['tv_original'], 'tv_optimized': card['tv_optimized'],
             'people': card['people']}
            for card in entry['questions'] if card['estimable']]
        if entry['pooled']:
            pooled[study] = {'truth': entry['pooled']['truth'],
                             'original': entry['pooled']['original'],
                             'optimized': entry['pooled']['optimized'],
                             'options': entry['pooled']['options'],
                             'cards': entry['pooled']['cards']}

    badges = ''.join(f'<a href="#s-{study}">{html.escape(LABELS.get(study, study))}</a>'
                     for study, _ in studies)
    data_json = json.dumps({'charts': charts, 'pooled': pooled, 'labels': LABELS},
                           ensure_ascii=False).replace('</', '<\\/')

    page = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="description" content="逐题抽屉：真人选择分布、原版 MatrAIx 选择分布、'
            '优化后概率分布，可直接对照柱状图。">'
            '<title>逐题对比：真人 vs 原版 vs 优化｜MatrAIx</title>'
            f'<style>{STYLE}{EXTRA}</style></head><body>'
            '<header><div class="hero"><div class="eyebrow">MATRAIX · 逐题明细 · 2026 年 11 月</div>'
            '<h1>每一道题，<br>真人怎么分、AI 怎么分</h1>'
            '<p class="lead">展开一套研究，再展开任意一道题，就是三种分布的柱状图对照：'
            '<strong>真人</strong>、<strong>原版 MatrAIx「只选一个」</strong>、'
            '<strong>优化后「给概率」</strong>。收起时每道题旁有一条迷你分布条，'
            '不点开也能扫一眼差在哪。</p>'
            '<div class="callout"><strong>怎么读</strong>：'
            '「真人」是实际作答者的选中比例；'
            '「原版 MatrAIx」把 96 次输出当成 96 个人投票（它每次只选一个，天然是分布）；'
            '「优化后」是模型给每个选项的概率取平均。'
            '误差 TV（百分点）越低越好，最后一列「原版−真人」指出高估（正）还是低估（负）。</div>'
            '<div class="legend"><span class="legend-item"><b class="tv win">12.1<i>▼</i></b> 更准的那一版</span>'
            '<span class="legend-item"><b class="tv tie">13.4<i>≈</i></b> 差异不到 2 个百分点，视为相当</span>'
            '<span class="legend-item"><b class="dir up">+21.9</b> 高估</span>'
            '<span class="legend-item"><b class="dir down">−16.7</b> 低估</span>'
            '<span class="legend-item"><b class="chip win">优化更准</b> / '
            '<b class="chip lose">原版更准</b></span>'
            '<span class="legend-item muted">误差越低越好；高估/低估只表示方向，不是好坏</span></div>'
            '<div class="tools"><button type="button" data-act="expand">全部展开题目</button>'
            '<button type="button" data-act="collapse">全部收起</button></div>'
            '<div class="badges">' + badges + '</div>'
            '</div></header>'
            '<main><section id="overview"><span class="number">概览</span>'
            '<h2>先看全局，再逐题</h2>' + overview + '</section>'
            '<h2 class="list-title">逐题明细</h2>'
            + ''.join(study_section(study, entry, index + 1)
                      for index, (study, entry) in enumerate(studies))
            + '</main>'
            f'<script id="card-data" type="application/json">{data_json}</script>'
            f'<script>{ECHARTS}</script><script>{CHARTS}</script>'
            '</body></html>')
    (HERE / 'cards.html').write_text(page)
    print(f'Built per-question report: {HERE / "cards.html"} ({len(page):,} bytes)')


EXTRA = """
.study{margin:10px 0}
.study-drawer,.q-drawer{border:1px solid #dde5de;border-radius:12px;background:#fff}
.study-drawer>summary{display:flex;flex-wrap:wrap;align-items:center;gap:12px;
  padding:14px 18px;cursor:pointer;list-style:none}
.study-drawer>summary::-webkit-details-marker{display:none}
.study-drawer>summary::before{content:'\\25B8';color:#117b70;font-size:14px;width:12px}
.study-drawer[open]>summary::before{content:'\\25BE'}
.study-drawer[open]>summary{border-bottom:1px solid #e6ece7}
.order{font-size:12px;color:#9fb0a8;font-variant-numeric:tabular-nums}
.sname{font-weight:700;font-size:17px;color:#14372f}
.srole{font-size:12px;color:#566a63;background:#f1f5f2;border-radius:999px;padding:2px 9px}
.smeta{font-size:13px;color:#566a63;margin-left:auto}
.snums{font-size:13px;display:flex;gap:12px;align-items:center;font-variant-numeric:tabular-nums}
.qtv{font-size:13px;display:flex;gap:8px;align-items:center;font-variant-numeric:tabular-nums;
  flex:0 0 116px;justify-content:flex-end}
.snum-native i,.snum-optimized i{font-style:normal;color:#8b9a92;font-size:11px;margin-left:3px}
/* --- error numbers: one emphasis colour, never red --- */
.tv{font-variant-numeric:tabular-nums;font-weight:600}
.tv i{font-style:normal;font-size:9px;margin-left:2px;opacity:.85}
.tv.win{color:#0f6b5f;background:#e8f3ef;border-radius:5px;padding:1px 5px}
.tv.lose{color:#8b9a92;font-weight:500}
.tv.tie{color:#5d6b64;font-weight:500}
.tv.muted{color:#b8c4bc;font-weight:400}
/* --- verdict chip: text carries the meaning, colour only supports it --- */
.chip{font-size:11px;border-radius:999px;padding:2px 8px;white-space:nowrap}
.chip.win{background:#e8f3ef;color:#0f6b5f}
.chip.lose{background:#fbeee7;color:#a1442a}
.chip.tie{background:#f1f3f1;color:#5d6b64}
.chip.unknown{background:#f6f2ea;color:#8a7550}
/* --- share deviations: warm = over-estimate, cool = under-estimate, not good/bad --- */
.dir{font-variant-numeric:tabular-nums}
.dir.up{color:#a15e38}
.dir.down{color:#2f6f9f}
.dir.flat{color:#8b9a92}
.dir.muted{color:#b8c4bc}
.study-body{padding:16px 18px 20px}
.qlist{display:flex;flex-direction:column;gap:8px;margin-top:12px}
.q-drawer>summary{display:flex;align-items:center;gap:14px;flex-wrap:nowrap;
  padding:9px 12px;cursor:pointer;list-style:none;font-size:13px}
.q-head{display:flex;align-items:baseline;gap:10px;flex:1 1 auto;min-width:0}
.q-drawer>summary::-webkit-details-marker{display:none}
.q-drawer[open]{box-shadow:0 2px 14px rgba(20,55,47,.07)}
.qid{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;color:#117b70;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.qprompt{color:#566a63;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.qpeople{color:#9fb0a8;font-size:12px;text-align:right}
.qstrip{display:flex;flex-direction:column;gap:2px;flex:0 0 132px}
.strip-row{display:flex;align-items:center;gap:5px;line-height:0}
.strip-name{font-size:9px;color:#9fb0a8;width:24px;flex:none;font-weight:400;
  white-space:nowrap;text-align:right;letter-spacing:-.02em;line-height:1.1}
.strip{display:flex;height:5px;width:100%;border-radius:2px;overflow:hidden;background:#f0f3f1}
.strip i{display:block;height:100%}
.q-body{padding:4px 12px 14px}
.qchart{height:300px}
.table-wrap{margin-top:6px}
table.qtable{font-size:13px}
table.qtable tr.qfoot th,table.qtable tr.qfoot td{background:#fafbfa;color:#566a63}
.legend{display:flex;flex-wrap:wrap;gap:8px 18px;margin:16px 0 0;font-size:12px;color:#566a63}
.legend-item{display:flex;align-items:center;gap:6px}
.legend-item.muted{color:#8b9a92}
.tools{display:flex;gap:10px;margin:14px 0 0}
.tools button{font:inherit;font-size:13px;padding:7px 14px;border-radius:999px;cursor:pointer;
  border:1px solid #cdd9d1;background:#fff;color:#14372f}
.tools button:hover{border-color:#117b70;color:#117b70}
.badges{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 0}
.badges a{font-size:13px;padding:5px 11px;border:1px solid #cdd9d1;border-radius:999px;
  color:#14372f;text-decoration:none;background:#fff}
.badges a:hover{border-color:#117b70}
.pooled{height:300px}
.list-title{margin-top:46px}
.opt-key{list-style:none;margin:10px 0 0;padding:0;display:grid;gap:3px;font-size:12px;color:#566a63}
.opt-key li{display:flex;gap:8px;line-height:1.5}
.opt-key b{color:#117b70;flex:none;min-width:14px;text-align:right}
@media (max-width:760px){
  .q-drawer>summary{flex-wrap:wrap;gap:6px 10px}
  .q-head{flex:1 1 100%}
  .qprompt{white-space:normal}
  .qstrip{flex:1 1 100%}
  .smeta{margin-left:0;width:100%}
}
"""

STYLE = (HERE / 'style.css').read_text()
ECHARTS = (HERE / 'vendor/echarts.min.js').read_text()
CHARTS = (HERE / 'charts_cards.js').read_text()

if __name__ == '__main__':
    build()
