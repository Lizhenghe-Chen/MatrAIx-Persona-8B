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

from notes import curly_quotes, design, floor_table

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


def question_table(card):
    """Shares plus the verdict row. Columns for an arm that never ran are omitted.

    Printing "not run" in every cell would be noise; leaving the column out and saying
    so once is clearer.
    """
    has_native = card['original'] is not None
    who, gain, state = verdict(card['tv_original'], card['tv_optimized'], has_native)
    head = ['选项', '真人'] + (['原版 MatrAIx'] if has_native else []) + \
           ['优化后'] + (['原版−真人'] if has_native else [])
    rows = []
    for index, option in enumerate(card['options']):
        truth = card['truth'][index]
        optimized = card['optimized'][index]
        cells = [f'<th>{html.escape(option["label"][:130])}</th>', f'<td>{pct(truth)}</td>']
        if has_native:
            native = card['original'][index]
            cells.append(f'<td>{pct(native)}</td>')
        cells.append(f'<td>{pct(optimized)}</td>')
        if has_native:
            cells.append(f'<td>{direction_cell(card["original"][index] - truth)}</td>')
        rows.append('<tr>' + ''.join(cells) + '</tr>')
    foot = ['<th>误差（TV，越低越好）</th>', '<td>—</td>']
    if has_native:
        foot.append(f'<td>{tv_cell(card["tv_original"], state, who == "native")}</td>')
    foot.append(f'<td>{tv_cell(card["tv_optimized"], state, who == "optimized")}</td>')
    if has_native:
        foot.append(f'<td>{verdict_chip(card["tv_original"], card["tv_optimized"], has_native)}</td>')
    else:
        foot.append(f'<td>{verdict_chip(None, card["tv_optimized"], has_native)}</td>')
    rows.append('<tr class="qfoot">' + ''.join(foot) + '</tr>')
    head_html = ''.join(f'<th>{html.escape(h)}</th>' for h in head)
    return ('<div class="table-wrap"><table class="qtable">'
            f'<thead><tr>{head_html}</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>')


GATE_PP = 2.0          # the project's declared gate for a meaningful distribution difference
DIRECTION_PP = 1.0     # below this an over/under-estimate is not worth colouring


def verdict(native_tv, optimized_tv, native_ran=True):
    """Compare two error totals. Returns (who, gain, state) with state in good/bad/tie.

    A missing native number has two different causes and they must not share a label:
    the arm never ran, or it ran but no question had enough respondents to score.
    """
    if native_tv is None or optimized_tv is None:
        return None, None, ('unknown' if not native_ran else 'unestimable')
    gain = native_tv - optimized_tv          # positive = optimized is better
    if abs(gain) < GATE_PP:
        return 'tie', gain, 'tie'
    return ('optimized' if gain > 0 else 'native'), gain, ('good' if gain > 0 else 'bad')


def tv_cell(value, state, is_winner):
    """One error number. The winner is emphasised; the other is muted, never red."""
    if value is None:
        label = '未跑原版臂' if state == 'unknown' else '逐题不可估'
        return f'<span class="tv muted" title="{label}">—</span>'
    text = f'{value:.1f}'
    if state == 'tie':
        return f'<span class="tv tie">{text}<i>≈</i></span>'
    if is_winner:
        return f'<span class="tv win">{text}<i>▼</i></span>'
    return f'<span class="tv lose">{text}</span>'


def verdict_chip(native_tv, optimized_tv, native_ran=True):
    who, gain, state = verdict(native_tv, optimized_tv, native_ran)
    if state == 'unknown':
        return ('<span class="chip unknown" title="这套研究只运行了优化臂，'
                '因此没有原版误差可对比；正文给出每档等分的参照误差">'
                '仅优化臂</span>')
    if state == 'unestimable':
        return ('<span class="chip tie" title="原版臂跑了，但这套问卷的题目人人不同，'
                '没有一道题够 20 人，逐题误差算不出来；展开可看个体误差">'
                '改看个体误差</span>')
    if state == 'tie':
        return '<span class="chip tie">≈ 两者相当</span>'
    # The verdict chip carries the good/bad reading, so the detail cells need not shout.
    if who == 'optimized':
        return f'<span class="chip win">优化更准 {abs(gain):.1f}pp</span>'
    return f'<span class="chip lose">原版更准 {abs(gain):.1f}pp</span>'


def missing_cell(value, state):
    """A missing number says why, rather than showing a dash the reader must decode."""
    if value is None and state == 'unknown':
        return '<span class="tv muted" title="这套研究没有运行原版单选臂">未跑</span>'
    return '<span class="tv muted" title="原版臂跑了，但没有一道题的作答人数够 20">逐题不可估</span>'


def study_numbers(native_value, optimized_value, who, state, native_ran=True):
    """Header numbers. A missing arm is named, not shown as a bare dash."""
    parts = []
    if native_value is None:
        word = '未跑' if not native_ran else '逐题不可估'
        parts.append(f'<span class="snum-missing">原版 <b>{word}</b></span>')
    else:
        parts.append(f'<span class="snum-native"><i>原版</i>'
                     f'{tv_cell(native_value, state, who == "native")}</span>')
    parts.append(f'<span class="snum-optimized"><i>优化</i>'
                 f'{tv_cell(optimized_value, state, who == "optimized")}</span>')
    parts.append(verdict_chip(native_value, optimized_value, native_ran))
    return ''.join(parts)


def option_key(card):
    """Numbered key under the chart: the bars carry numbers, the text lives here."""
    items = ''.join(
        f'<li><b>{index + 1}</b>{html.escape(option["label"])}</li>'
        for index, option in enumerate(card['options']))
    return f'<ol class="opt-key">{items}</ol>'



def individual_block(entry):
    """What the six non-estimable studies are judged on instead of a per-card distribution."""
    data = entry.get('individual')
    if not data:
        return ''
    rows = []
    for name, label in (('original', '只让 AI 选一项（原版）'),
                        ('optimized', '只问 AI，保留概率（优化）'),
                        ('uniform', '每档等分'),
                        ('history', '历史查表'),
                        ('stratum_history', '历史分层查表')):
        value = data['brier'].get(name)
        if value is None or any(abs(value - (r[2] or -1)) < 1e-9 for r in rows):
            continue
        mark = ' class="win"'
        rows.append((label, value, value))
    reference = data['reference']
    if reference and not any((r[2] or -1) == reference['brier'] for r in rows):
        rows.append((reference['label'], reference['brier'], reference['brier']))
    best = min(r[1] for r in rows)
    body = ''.join(
        f'<tr><th>{html.escape(label)}</th>'
        f'<td><span class="tv{" win" if value == best else ""}">{value:.3f}</span></td></tr>'
        for label, value, _ in rows)
    ai = data['brier'].get('optimized')
    uni = data['brier'].get('uniform')
    ref = reference['brier'] if reference else None
    verdict = ''
    if ai is not None and uni:
        share = 100 * (1 - ai / uni)
        if abs(share) < 0.5:
            verdict += f'这六套的胜负是在这里判的：个体误差与“每档等分”基本持平（{ai:.3f} vs {uni:.3f}）。'
        else:
            verdict += (f'这六套的胜负是在这里判的：个体误差比“每档等分”'
                        f'{"低" if share > 0 else "高"} {abs(share):.0f}%'
                        f'（{ai:.3f} vs {uni:.3f}）。')
    if ai is not None and ref:
        verdict += (f'但仍不如{html.escape(reference["label"])}'
                    f'（{ai:.3f} vs {ref:.3f}，差 {100 * (1 - ref / ai):.0f}%）。')
    contrast = data.get('native_to_optimized')
    if contrast:
        low, high = contrast['improvement_95_ci']
        verdict += (f' 只改“选一项”为“给概率”，个体误差改善 '
                    f'{contrast["improvement"]:.3f}，区间 [{low:+.3f}, {high:+.3f}]。')
    return ('<p class="small"><strong>那这套怎么判好坏？</strong>换一个不需要"多人答同一题"的指标：'
            '<strong>个体误差</strong>——每个人的每道题算一个预测，与他的实际选择比。'
            '一个人的答案就够评分，不必凑够 20 人。</p>'
            '<div class="table-wrap"><table style="min-width:300px">'
            '<caption>个体误差（每人每题，越低越好；这六套的正式口径）</caption>'
            '<thead><tr><th>做法</th><th>Brier</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>'
            f'<p class="small">{verdict}</p>')


def study_section(study, entry, index):
    label = LABELS.get(study, study)
    metrics = entry.get('card_tv')
    estimable, cards = entry['estimable_cards'], entry['cards']
    has_native = 'original' in entry['arms']
    native_value = metrics['original'] if metrics else None
    optimized_value = metrics['optimized'] if metrics else None
    who, gain, state = verdict(native_value, optimized_value, has_native)
    coverage = f'{estimable}/{cards} 题可估'

    body = []
    if not estimable:
        counts = [q['people'] for q in entry['questions']] or [0]
        shape = design(study)
        body.append('<p class="note-warn"><strong>这套不是普通问卷，是'
                    + html.escape(shape['kind']) + '。</strong>'
                    + html.escape(shape['detail']) + '。'
                    '所以「每个人答的题不一样」是<strong>故意的</strong>，不是抽样失败：'
                    + html.escape(shape['motive'].format(n=cards))
                    + (f'代价就是每题只有 1 人作答。' if max(counts) == 1 else
                       f'代价就是每题只有 1–{max(counts)} 人作答（平均 {sum(counts) / len(counts):.1f} 人）。')
                    + '一个人选了什么就是 100%，逐题分布无从谈起。</p>'
                    + floor_table()
                    + individual_block(entry)
                    + '<p class="small">人少时量到的是抽样噪声，不是模型误差，'
                      '所以这套不报逐题分布。下面这张汇总图只是"质量集中在哪儿"的示意'
                      '（按选项位置对齐后求和，不是误差指标）；'
                      '"至少 20 人"这道门槛只针对普通问卷的逐题分布。</p>')
        body.append(f'<div class="echart pooled" id="pool-{study}" data-pool="{study}"></div>')
    else:
        if not has_native:
            uniform_tv = metrics['uniform'] if metrics else None
            gap = '' if uniform_tv is None else (
                f'作为参照：如果对每道题都按"每个选项等可能"去猜，误差是 {uniform_tv:.1f}pp，'
                f'优化后是 {metrics["optimized"]:.1f}pp，降低了 '
                f'{100 * (1 - metrics["optimized"] / uniform_tv):.0f}%。')
            body.append('<p class="note-warn"><strong>这套没有原版臂。</strong>'
                        '它的定位是外部验证，为省费用只跑了优化臂，所以表里的"原版 MatrAIx"是空的——'
                        '不是没有数据，是当时没跑。' + gap + '</p>')
        if estimable < cards:
            body.append(f'<p class="small">另有 {cards - estimable} 道题人数不足 20，'
                        '未逐题列出。</p>')
        items = []
        for card_index, card in enumerate(entry['questions']):
            if not card['estimable']:
                continue
            q_who, q_gain, q_state = verdict(card['tv_original'], card['tv_optimized'], has_native)
            items.append(
                '<details class="q-drawer">'
                '<summary>'
                '<span class="q-head">'
                f'<code class="qid">{html.escape(card["question"])}</code>'
                f'<span class="qprompt">{html.escape(card["prompt"][:80])}</span>'
                '</span>'
                f'<span class="qstrip">{strip(card)}</span>'
                f'<span class="qtv">'
                + ('' if card['original'] is None else
                   tv_cell(card['tv_original'], q_state, q_who == 'native'))
                + tv_cell(card['tv_optimized'], q_state, q_who == 'optimized')
                + '</span>'
                
                f'<span class="qpeople">{card["people"]} 人</span>'
                '</summary>'
                '<div class="q-body">'
                f'<div class="echart qchart" id="qchart-{study}-{card_index}"></div>'
                + question_table(card)
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
            f'<span class="snums">{study_numbers(native_value, optimized_value, who, state, has_native)}</span>'
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
        native_ran = 'original' in entry['arms']
        who, gain, state = verdict(native_value, optimized_value, native_ran)
        overview.append(
            f'<tr><th><a href="#s-{study}">{html.escape(LABELS.get(study, study))}</a></th>'
            f'<td>{entry["people"]}</td><td>{entry["cards"]}</td>'
            f'<td>{entry["estimable_cards"]}</td>'
            + ('<td><span class="tv muted">—</span></td><td><span class="tv muted">—</span></td>'
               if not entry['estimable_cards'] else
               f'<td>{tv_cell(native_value, state, who == "native") if native_value is not None else missing_cell(native_value, state)}</td>'
               f'<td>{tv_cell(optimized_value, state, who == "optimized")}</td>')
            + f'<td>{verdict_chip(native_value, optimized_value, native_ran)}</td></tr>')
    overview.append('</tbody></table></div>'
                    '<p class="small">「可估题」＝至少 20 名被测者答过同一道题。'
                    '为 0 的六套是联合分析或打分任务，题目人人不同，'
                    '单题分布算不出来——展开后改用<strong>个体误差</strong>判好坏，'
                    '并保留全部题目的汇总视图。这些数字与技术版报告逐套一致。</p>')
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
            '「原版 MatrAIx」是每个人只交一个选项，把这些单选汇总起来就是一条分布；'
            '「优化后」是模型给每个选项的概率取平均。'
            '误差 TV（百分点）越低越好，最后一列「原版−真人」指出高估（正）还是低估（负）。</div>'
            '<div class="legend"><span class="legend-item"><b class="tv win">12.1<i>▼</i></b> 两种做法里误差更低的那个</span>'
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
    (HERE / 'cards.html').write_text(curly_quotes(page))
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
.snum-native i,.snum-optimized i{font-style:normal;color:#8b9a92;font-size:11px;margin-right:4px}
.snum-missing{color:#a1442a;font-size:12px}
.snum-missing b{font-weight:600}
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
.na{font-size:11px;color:#a1442a;background:#fbeee7;border-radius:4px;padding:0 5px}
.note-warn{margin:0 0 12px;padding:10px 14px;border-radius:10px;background:#fdf7f3;
  border:1px solid #f0ddd1;font-size:13px;line-height:1.7;color:#6b4a37}
.note-warn strong{color:#a1442a}
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
