"""Shared explanation for the six studies that have no per-question distribution.

Those studies are conjoint (attribute-randomised choice) experiments and one rating task,
so each "question" is a product profile shown to one or a few respondents. Randomising the
profiles is the point of the design, not a sampling failure, and it also means a per-card
distribution cannot be estimated — the attribute model is the fair comparator there.

Kept in one place so the narrative report, the technical report and the per-question page
cannot drift into three different explanations of the same fact.
"""
import random
import re

_TEXT = re.compile(r'>([^<>]+)<')
MINIMUM = 20

_CONJOINT = ('同一组搭配问 96 个人，只能学到"这一组谁赢"；'
             '把搭配随机成 {n} 组，才能反推出"每个属性各值多少"。')

DESIGN = {
    'dryer': {'kind': '联合分析',
              'detail': '每道题是随机拼出来的两台烘干机，受访者各看各的几张',
              'motive': _CONJOINT},
    'swiss': {'kind': '联合分析', 'detail': '每道题是随机拼出来的两件家电', 'motive': _CONJOINT},
    'drone': {'kind': '联合分析', 'detail': '每道题是随机拼出来的两种外卖配送方案',
              'motive': _CONJOINT},
    'origin': {'kind': '联合分析', 'detail': '每道题是随机拼出来的两件商品', 'motive': _CONJOINT},
    'tshirt': {'kind': '联合分析', 'detail': '每道题是随机拼出来的三件 T 恤', 'motive': _CONJOINT},
    'shoes': {'kind': '打分任务', 'detail': '每道题是一双独一无二的鞋，全库 3,822 双',
              'motive': ('同一款鞋只问一个人，只能学到"这一款打几分"；'
                         '把款式随机成 {n} 款、每款问不同的人，'
                         '才能反推出"品牌、颜色、价格各值多少"。')},
}
_DEFAULT = {'kind': '逐题作答', 'detail': '每道题只有少数人作答',
            'motive': '同一道题问 96 个人只会学到这一题的答案，随机成 {n} 道才能反推属性。'}


def design(study):
    return DESIGN.get(study, _DEFAULT)


def sampling_floor():
    """Error a *perfect* answer still measures, by number of respondents.

    Reproducible: fixed seed and question, 4,000 draws per row. This is why a question
    needs about 20 respondents before its distribution can be read at all.
    """
    rng = random.Random(7)
    truth = (0.5, 0.3, 0.2)
    rows = []
    for n in (1, 4, 20, 96):
        totals = []
        for _ in range(4000):
            counts = [0, 0, 0]
            for _ in range(n):
                counts[rng.choices((0, 1, 2), truth)[0]] += 1
            totals.append(sum(abs(counts[i] / n - truth[i]) for i in range(3)) / 2)
        rows.append((n, 100 * sum(totals) / len(totals)))
    return rows


def floor_table(caption='一道题的作答人数 → 即使 AI 完全答对，也会量出这么大的误差'):
    rows = ''.join(f'<tr><td>{n} 人</td><td>{value:.0f}pp</td></tr>'
                   for n, value in sampling_floor())
    return ('<div class="table-wrap"><table style="min-width:280px">'
            f'<caption>{caption}</caption>'
            '<thead><tr><th>作答人数</th><th>量到的误差</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


def zero_card_studies(payload, labels=None):
    """The studies with no estimable card, widest plan first, with their real counts."""
    import json

    chosen, order = {}, []
    for plan, block in payload['plans'].items():
        for study, entry in block['studies'].items():
            if study not in chosen:
                chosen[study] = entry
                order.append(study)
                continue
            if 'original' not in chosen[study]['arms'] and 'original' in entry['arms']:
                chosen[study] = entry
    rows = []
    for study in order:
        entry = chosen[study]
        if entry['estimable_cards']:
            continue
        counts = [q['people'] for q in entry['questions']] or [0]
        rows.append({'study': study,
                     'label': (labels or {}).get(study, study),
                     'cards': entry['cards'],
                     'people': entry['people'],
                     'max_per_card': max(counts),
                     'mean_per_card': sum(counts) / len(counts),
                     'attribute_model': entry.get('attribute_model', False),
                     **design(study)})
    return rows


def study_table(rows):
    body = ''.join(
        f'<tr><th>{row["label"]}</th><td>{row["kind"]}</td>'
        f'<td>{row["cards"]:,}</td>'
        f'<td>{row["max_per_card"]} 人</td>'
        f'<td>{"有" if row["attribute_model"] else "无"}</td></tr>'
        for row in rows)
    return ('<div class="table-wrap"><table style="min-width:560px">'
            '<caption>没有逐题分布的六套：设计、题量、每题人数、是否有属性模型</caption>'
            '<thead><tr><th>研究</th><th>设计</th><th>题数</th>'
            '<th>每题最多人数</th><th>属性模型</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


def conjoint_block(rows, style='callout'):
    """One self-contained explanation, for reuse in any report."""
    if not rows:
        return ''
    kinds = [kind for kind in ('联合分析', '打分任务')
             if any(row['kind'] == kind for row in rows)]
    return ('<div class="' + style + '">'
            '<p><strong>为什么有六套研究没有逐题数字。</strong>'
            '它们不是普通问卷，而是' + '和'.join(kinds) + '这类<strong>实验</strong>：'
            '产品属性被随机拼成组合，每人只答其中几张。'
            '这是<strong>故意的</strong>，不是抽样失败。</p>'
            + study_table(rows)
            + '<p>随机化就是实验本身。同一组搭配问 96 个人，只能学到"这一组谁赢"；'
              '把它随机成几百组，才能反推出"容量、价格、评分各值多少"。'
              '代价是每道题只有 1–8 人作答，而一个人的答案就是 100%，量不出分布。</p>'
            + floor_table()
            + '<p>人少时量到的是抽样噪声，不是模型误差。所以这六套改用<strong>属性模型</strong>评分'
              '（条件逻辑回归或评分模型，只用题目里显示的属性、不看真人答案）——'
              '也就是本报告里"同信息统计参照"那个对手。'
              '「至少 20 人」这道门槛只针对普通问卷的逐题分布，不是对这批数据的减分。</p></div>')


_SCRIPT = re.compile(r'<(script|style)\b[\s\S]*?</\1>', re.I)


def curly_quotes(doc):
    """Straight quotes in visible text become Chinese curly quotes.

    Only text between tags is touched, and script/style bodies are skipped, so inline
    JSON and CSS keep their own quoting. One page, one convention: the reports were
    mixing "..." and “...” inside the same paragraph.
    """
    state = {'opening': True}

    def flip(segment):
        # The state is document-wide and is updated by quotes that are already curly,
        # so a paragraph that mixes “...” and "..." still pairs up correctly.
        out = []
        for char in segment:
            if char == '"':
                out.append('“' if state['opening'] else '”')
                state['opening'] = not state['opening']
            else:
                if char == '“':
                    state['opening'] = False
                elif char == '”':
                    state['opening'] = True
                out.append(char)
        return ''.join(out)

    parts, last = [], 0
    for match in _SCRIPT.finditer(doc):
        parts.append(_TEXT.sub(lambda m: '>' + flip(m.group(1)) + '<', doc[last:match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(_TEXT.sub(lambda m: '>' + flip(m.group(1)) + '<', doc[last:]))
    return ''.join(parts)
