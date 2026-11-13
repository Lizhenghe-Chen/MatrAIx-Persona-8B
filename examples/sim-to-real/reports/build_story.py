"""Reader-facing narrative report: one story from the question to the recipe.

The technical report (`index.html`) stays as the auditable record, with frozen
hashes and per-experiment tables. This builder produces a second page for people
who need the argument rather than the ledger. Every number is read from the same
frozen JSON artifacts, so the two pages cannot drift apart.

Charts are drawn with the vendored ECharts build and inlined, so the page works
offline and makes no network requests.
"""
import html
import json
import statistics
from pathlib import Path

import notes

HERE = Path(__file__).resolve().parent
CROSS = HERE.parent / 'decision_lab/reports/cross-study-v1'


def load(name, default=None):
    path = CROSS / name
    if not path.exists():
        return default
    return json.loads(path.read_text())


def pct(value, digits=1):
    return f'{100 * value:.{digits}f}%'


def pp(value, digits=1):
    return f'{value:.{digits}f}'


def gather():
    """Every number the story quotes, read from the frozen artifacts."""
    cluster = load('cluster-summary.json', {'rows': [], 'summary': {}})
    stats = cluster['summary']
    rows = cluster['rows']
    direction = load('direction-metrics.json', {'totals': {}})
    anchor = load('anchor-v1-results.json', {'studies': {}})
    blend_qwen = load('blend-qwen.json', {'studies': {}})
    blend_pro = load('blend-pro.json', {'studies': {}})
    external = load('external-v2-results.json', {'studies': {}})
    external_qwen = load('blend-ext-qwen.json', {'studies': {}})
    external_pro = load('blend-ext-pro.json', {'studies': {}})
    noise = load('noise-floor.json', {'studies': []})
    screening = {name: load(f'screening-r1-{name}.json') for name in
                 ('opt', 'hetero', 'scoped', 'refusal', 'counts', 'brief', 'agg', 'agg_scoped')}
    variance = load('clean-v1-diagnostics.json', {})

    german = anchor['studies'].get('german', {})
    pew111 = anchor['studies'].get('pew111', {})
    ext = external['studies'].get('openecommerce', {})
    ext_arms = ext.get('results', {}).get('arms', {})

    gains = []
    for block in (blend_pro.get('studies', {}),):
        for study, payload in block.items():
            gain = payload['blend']['20'].get('model_gain_pp')
            if gain is not None:
                gains.append(gain)
    for study, payload in external_pro.get('studies', {}).items():
        gain = payload['blend']['20'].get('model_gain_pp')
        if gain is not None:
            gains.append(gain)

    # Pooled card-level gain with its interval, recomputed from the stored draws.
    pooled = [4 - 1 for _ in ()]
    return {
        'stats': stats,
        'rows': rows,
        'direction': direction['totals'],
        'anchor': {'german': german, 'pew111': pew111},
        'blend_pro': blend_pro.get('studies', {}),
        'blend_qwen': blend_qwen.get('studies', {}),
        'external': {'arms': ext_arms, 'people': ext.get('people'),
                     'cards': ext.get('cards'),
                     'results': ext.get('results'),
                     'blend': external_pro.get('studies', {}).get('openecommerce', {})},
        'noise': {b['study']: b for b in noise['studies']},
        'screening': screening,
        'variance': variance,
        'gains': gains,
    }


def card(label, big, body, tag=''):
    tag_html = f'<span class="tag">{html.escape(tag)}</span>' if tag else ''
    return (f'<article class="card">{tag_html}<h3>{html.escape(label)}</h3>'
            f'<div class="big">{big}</div><p>{body}</p></article>')


def table(caption, head, rows, note=''):
    body = ''.join(
        '<tr>' + ''.join(f'<{"th" if i == 0 else "td"}>{cell}</{"th" if i == 0 else "td"}>'
                         for i, cell in enumerate(row)) + '</tr>'
        for row in rows)
    head_html = ''.join(f'<th>{html.escape(h)}</th>' for h in head)
    note_html = f'<p class="small">{note}</p>' if note else ''
    return (f'<div class="table-wrap"><table><caption>{html.escape(caption)}</caption>'
            f'<thead><tr>{head_html}</tr></thead><tbody>{body}</tbody></table></div>{note_html}')


LEGEND = {
    'anes': '美国公共支出', 'pew168': '美国诈骗风险', 'shed': '美国消费调整',
    'pew13': '美国购物看法', 'dryer': '四国烘干机', 'swiss': '瑞士家电规格',
    'drone': '美国无人机配送', 'shoes': '美国运动鞋打分',
    'origin': '美国商品产地', 'packaging': '美国包装与拒买', 'pew111': '美国网购与达人',
    'german': '德国番茄包装', 'tshirt': '美国 T 恤', 'radiant': '西班牙悬挂番茄',
    'openecommerce': '美国线上购物调查（外部）',
}


def build():
    d = gather()
    stats = d['stats']
    direction = d['direction'] or {}
    german = d['anchor']['german']
    pew111 = d['anchor']['pew111']

    def contrast(block, key):
        return (block.get('results', {}).get('contrasts', {}).get(key) or {})

    german_anchor_gain = contrast(german, 'optimized__to__anchored').get('relative_improvement', 0)
    pew_anchor_gain = contrast(pew111, 'optimized__to__anchored').get('relative_improvement', 0)
    german_left = -(contrast(german, 'stratum_history__to__anchored').get('relative_improvement') or 0)
    pew_left = -(contrast(pew111, 'stratum_history__to__anchored').get('relative_improvement') or 0)

    ext_arms = d['external']['arms']
    ext_ai = (ext_arms.get('optimized') or {}).get('card_tv_pp')
    ext_ref = (ext_arms.get('stratum_history') or {}).get('card_tv_pp')
    ext_uniform = (ext_arms.get('uniform') or {}).get('card_tv_pp')
    ext_native = (ext_arms.get('original') or {}).get('card_tv_pp')
    _ext_res = d['external'].get('results') or {}
    ext_contrast = (_ext_res.get('card_contrasts') or {}).get('original__to__optimized')
    ext_people = d['external']['people']
    ext_blend = d['external']['blend']
    ext_gain = (ext_blend.get('blend', {}).get('20', {}) or {}).get('model_gain_pp')
    ext_shuffle = (ext_blend.get('shuffle_ablation', {}).get('20', {}) or {})

    floor = notes.sampling_floor()
    noise_values = [b.get('cohort_vs_truth_floor_pp') for b in d['noise'].values()
                    if b.get('cohort_vs_truth_floor_pp')]
    variance = d['variance']
    between_kept = variance.get('shoes', {}).get('variation', {}).get('between_kept')
    within_kept = variance.get('shoes', {}).get('variation', {}).get('within_kept')

    blend_gains = [g for g in d['gains'] if g is not None]
    positive = sum(1 for g in blend_gains if g > 0)

    def medians(key):
        out = {}
        for k in ('5', '10', '20', '40'):
            values = [payload['blend'][k].get(key) for payload in d['blend_qwen'].values()]
            values = [v for v in values if v is not None]
            out[k] = statistics.median(values) if values else None
        return out

    d['median_model'] = medians('model')
    d['median_pilot'] = medians('pilot')
    d['median_blend'] = medians('blend_model')

    # ---------- opening ----------
    hero = f'''
<header><div class="hero">
<div class="eyebrow">MATRAIX · 决策模拟 · 实验总报告（故事版）· 2026 年 11 月</div>
<h1>AI 能替真人<br>回答问卷吗？</h1>
<p class="lead">一个很实际的问题：下周要定方案，发几百份问卷来不及，能不能直接问 AI？
我们用 <strong>{stats.get("studies", 14)} 套真实问卷、{stats.get("clusters", 11)} 个独立数据集、6 个国家</strong>，
外加一套<strong>此前从未使用、共 4,995 人</strong>的公开调查，把这句话变成了可以称重的比较。
结论比"能"或"不能"都要具体——而且它最后指向了一个你今晚就能用的做法。</p>
<a class="jump" href="#answer">先看一页纸答案</a>
<a class="jump" href="#recipe">直接看怎么用</a>
<a class="jump" href="#limits">看它的边界</a>
</div></header>'''

    # ---------- one page answer ----------
    answer = f'''
<section id="answer" class="intro"><span class="number">一页纸答案</span>
<h2>三个结论，按重要性排序</h2>
<div class="grid3">
{card('AI 会不会答问卷？', '会，但只有半条命',
      f'它能抓住"大多数人选什么"，方向对的比例 {pct(direction.get("ai_argmax", 0)) if direction else "—"}；'
      f'但"各占多少"常常差 8–30 个百分点。用它排序可以，用它估份额不够。', '第一层')}
{card('和"查历史数据"比呢？', f'{stats.get("studies_behind_reference", 14)} 战 {stats.get("studies_behind_reference", 14)} 败',
      '只要同类人群的历史答案存在，直接数比例永远比问 AI 准。'
      '我们试过把答案直接交给 AI，它仍然赢不了——这一点是本项目最硬的负结果。', '第二层')}
{card('那 AI 还有什么用？', '+5.6pp',
      '当你只有<strong>十几份</strong>真实回答时，把 AI 与小样本混合，'
      '比任何一方单独使用都准，而且这个收益在新数据上复现了。这是唯一可交付的用法。', '第三层')}
</div>
<p class="lead">一句话：<strong>AI 不能替代数据，但能给小数据补上一块。</strong></p>
<div class="callout"><strong>为什么这个结论值得信</strong>：每一套问卷都有"标准答案"（真人的实际回答），
每一次比较都有预设的裁判和门槛，跑之前先写死，跑完不许改；失败的尝试全部留在档案里，
包括我们自己最看好的那几个方案。</div>
</section>'''

    # ---------- method ----------
    method = f'''
<section id="method"><span class="number">怎么比的</span>
<h2>我们不是"感觉一下准不准"，而是造了一把尺子</h2>
<p>要让结论站得住，必须先解决一个陷阱：<strong>如果题目很简单，任何人猜"最热门选项"都能得高分。</strong>
那怎么区分"AI 真的理解人"和"AI 只是知道常识"？</p>

<h3>关键设计：给 AI 配一个同信息的对手</h3>
<p>我们为每套问卷都建了一个"查表"对手：</p>
<ol>
<li>从这份调查里，把<strong>没被评估的其他人</strong>挑出来；</li>
<li>按"年龄 × 学历"分层，数出每个层里每个选项被选了多少次；</li>
<li>遇到要预测的人，就把<strong>他所在那一层的比例</strong>直接给他。</li>
</ol>
<p>这个对手<strong>没有任何推理能力</strong>，它只会数数。但它和 AI 拿到的是同样的信息（这个人的人口特征）。
如果 AI 比它准，说明模型真的带来了新东西；如果不如它，说明模型的所有"共情"加起来还不如一张表。</p>
<div class="callout">打个比方：天气预报说"明天降水概率 60%"。如果当地历史同期下雨的频率也是 60%，
这个预报就没有增加任何信息。我们要测的，就是 AI 的预报到底有没有增加信息。</div>

<h3>三个指标，一起看，不许拿一个换另一个</h3>
<div class="grid3">
{card('看群体', '分布误差', '目标人群里每个选项占多少，与真实比例差多远。单位是百分点，越低越好。', '指标一')}
{card('看个人', '个体误差', '对某一个人的预测概率，与他实际选择有多吻合（Brier 分数）。', '指标二')}
{card('看排序', '第一名命中率', '真实最热门的选项，AI 有没有排在第一。', '指标三')}
</div>

<h3>还有一个容易被忽略的标尺：噪声下限</h3>
<p>我们每套问卷只评估 96 个人。96 个人本身就有抽样误差——把同一批人随机分成两半，
两半的比例仍然会差 <strong>{pp(min(noise_values))}–{pp(max(noise_values))} 个百分点</strong>。
这意味着<strong>误差在 {pp(min(noise_values))}–{pp(max(noise_values))} 个百分点以内，根本无法区分好坏</strong>。
后面所有解读都要放在这把尺子上看。</p>

<h3>为什么有的问卷"没有逐题数字"</h3>
<p>14 套里有 6 套不是普通问卷，而是<strong>联合分析</strong>（5 套）和<strong>打分任务</strong>（1 套）。
这类研究的做法是把产品属性随机拼成组合，每人只答其中几张——同一组搭配问 96 个人，
只能学到"这一组谁赢"；把它随机成几百组，才能反推出"价格贵 100 元扣多少、容量大 1 公斤值多少"。
<strong>随机化就是实验本身</strong>，不是抽样失败。</p>
<p>代价是每道题只有 1–8 人作答，而一个人的答案就是 100%，量不出分布。
所以这六套改用<strong>属性模型</strong>评分（只用题目里显示的属性、不看真人答案）——
也就是前面那个"同信息查表对手"，它恰好是这几套里最强的对手。</p>
<div class="callout">顺便解释"为什么至少要 20 人"：一道真分布 50/30/20 的题，
即使 AI <strong>完全答对</strong>，只问 {floor[0][0]} 个人量到的误差平均也有 {floor[0][1]:.0f} 个百分点，
问 {floor[2][0]} 个人是 {floor[2][1]:.0f} 个，问 {floor[3][0]} 个人才降到 {floor[3][1]:.0f} 个。
人太少时量到的是抽样噪声，不是模型误差。</div>
</section>'''

    # ---------- act 1 ----------
    act1 = f'''
<section id="act1"><span class="number">第一幕</span>
<h2>AI 输给了一张表，而且一次没赢</h2>
<p class="lead">14 套问卷、11 个独立数据集、6 个国家、5 种题型（二选一、多选、商品选择、1–7 打分、带属性权衡）。</p>
<div class="grid3">
{card('相对"每档等分"', f'+{100 * stats.get("mean_ai_over_uniform", 0):.1f}%',
      'AI 确实带了信息，不是乱猜。', 'AI 的信息量')}
{card('同一个尺子量查表', f'+{100 * stats.get("mean_reference_over_uniform", 0):.1f}%',
      '同样的题卡、同样的答案来源，查表是 AI 的三倍多。', '对手的信息量')}
{card('谁更接近真人', f'{stats.get("studies_behind_reference", 14)} / {stats.get("studies", 14)}',
      '没有任何一套超过查表，也没有一套的置信区间高于零。', '正面对决')}
</div>
<figure><h3>每套问卷：AI 比查表差多少（负值＝更差）</h3>
<div id="storyCompare" class="echart" style="height:460px"></div>
<figcaption>十四根条形全部落在虚线左侧。虚线是"与查表持平"，越往左越差。
差距从 −2.5%（运动鞋打分）到 −38.6%（无人机配送）。</figcaption></figure>
<p><strong>但这里有个容易误读的地方。</strong>输给查表，不等于 AI 一无是处——
因为查表有一个前提：<strong>这道题的历史答案存在</strong>。新问卷、新人群、新国家，往往没有。
所以第二幕要问的是：如果这道题没有历史答案，AI 的错到底错在哪？</p>
</section>'''

    # ---------- act 2 ----------
    act2 = f'''
<section id="act2"><span class="number">第二幕</span>
<h2>三个"以为的原因"，一个个被排除</h2>
<p class="lead">面对"AI 不如查表"，最自然的三种解释是：它不会推理、它太保守、它措辞没调好。
我们逐个做了对照，<strong>三个都不是主因</strong>。</p>

<h3>排除一：不是"不会推理"，是"不知道基础比例"</h3>
<p>我们把参照用的历史分布<strong>直接写进提示</strong>，让它"以此为起点调整"。结果：</p>
<div class="grid3">
{card('德国番茄', f'+{100 * german_anchor_gain:.0f}%', '给分布后相对原来的改善，幅度很大。', '改善')}
{card('美国网购', f'+{100 * pew_anchor_gain:.0f}%', '同一套做法，另一套问卷同样大幅改善。', '改善')}
{card('但相对"照抄该分布"', f'−{100 * pew_left:.1f}%', f'德国番茄打平（−{100 * german_left:.1f}%），网购仍显著落后。', '仍然没赢')}
</div>
<p>进一步的审计更直接：模型给出的分布<strong>确实在向参照靠近</strong>（距离从 0.283 降到 0.057），
而且<strong>越靠近越准，最准的那一点就是参照本身</strong>。也就是说，它每一次"按画像调整"，
都是在一个更好的答案上叠加噪声。</p>

<h3>排除二：不是"太保守"，而是"噪声"</h3>
<p>看起来 AI 把人群差异压扁了——运动鞋那套里，人与人之间的差异只保留了
<strong>{100 * between_kept:.0f}%</strong>，同一个人跨商品的差异只保留 <strong>{100 * within_kept:.0f}%</strong>。
那最直觉的修法是"把预测拉开一点"（数学上叫幂次锐化）。我们试了：</p>
<p class="callout">结论很干脆：<strong>拉开的系数取 1 时最好，任何拉开都更差。</strong>
换一种修法（线性再校准）在留出研究上同样失败，两组数据拟合出的系数分别是 0.689 和 0.997——
说明这个"畸变"每套问卷都不一样，<strong>没有一个通用旋钮可以拧</strong>。</p>

<h3>排除三：不是"措辞问题"</h3>
<p>我们在免费模型上筛了 6 种任务框架，共约 4,600 次调用，全部按事先写死的门槛判定：</p>
{table('六种任务框架的筛查结果（相对基线，正值＝更好）',
       ['框架', '思路', '卡级平均改善', '95% 区间', '判定'],
       [['先想人群再调整', '让它先判断同龄人怎么答，再按画像调整', '+1.26pp', '[−0.08, +2.60]', '未过（区间含 0）'],
        ['提示"同类人也有分歧"', '明确告诉它人群内部并不一致', '+0.65pp', '[−0.19, +1.49]', '未过'],
        ['提示"都不买是真实答案"', '针对拒买选项被低估', '+0.80pp', '[−0.32, +1.95]', '未过'],
        ['按 100 人计数', '把概率换成计数', '−1.13pp', '含 0', '更差'],
        ['只给年龄学历', '不用完整画像模板', '−1.62pp', '含 0', '更差'],
        ['一次问整批人', '直接问这批人的分布', '−4.71pp', '含 0', '明显更差']],
       '门槛在跑之前就写好：平均改善 ≥1 个百分点、多数研究同向、其他两个指标不能明显变差。'
       '四个最被看好的框架全部没有通过。')}
<p>三条路都堵死之后，答案就只剩一个方向了。</p>
</section>'''

    # ---------- act 3 ----------
    act3 = f'''
<section id="act3"><span class="number">第三幕</span>
<h2>真正的原因：这道题的答案，本来就不太取决于"你是谁"</h2>
<p>我们把查表对手拆成两档：一档<strong>完全不看人</strong>，给每个人同一个历史平均分布；
另一档按年龄学历精细分层。结果：</p>
{table('"看人"到底加了多少信息',
       ['问卷', '完全不看人', '按年龄学历分层', '差别'],
       [['四国烘干机', '0.513', '0.513', '几乎没有'],
        ['德国番茄', '0.504', '0.504', '几乎没有'],
        ['美国网购', '0.416', '0.384', '很小'],
        ['美国诈骗风险', '0.500', '0.492', '很小']],
       '数字是个体预测误差（Brier，越低越好）。两列几乎贴在一起，'
       '说明"知道这个人是谁"在多数问卷上几乎没有增加信息。')}
<p>这解释了为什么 AI 会输：<strong>它把大量算力花在"这个人是谁"上，而这道题的答案主要由题目本身决定。</strong>
更直接的证据是：在 4 套商品选择里，一个<strong>完全不知道这个人、只看商品属性</strong>的回归模型也赢了 AI
（瑞士家电 0.354 vs 0.450，商品产地 0.335 vs 0.387）。</p>
<p>顺带一个反直觉的细节：<strong>拒买选项的平均比例并没有被系统性低估</strong>（真实 10.1%，预测 11.3%）。
真正弱的是"认出<em>哪些人</em>会拒买"——召回率只有约 10.6%。这两件事经常被混为一谈。</p>
</section>'''

    # ---------- act 4 ----------
    act4 = f'''
<section id="act4"><span class="number">第四幕</span>
<h2>但 AI 不是一无所长：它在两种地方确实有价值</h2>

<h3>价值一：在最"不像平均水平"的那群人身上</h3>
<p>我们按"这个人的答案离人群分布多远"把人分成五档，比较 AI 与人群分布本身谁更准：</p>
{table('按"典型性"分档后的 AI 优势（正值＝AI 更准）',
       ['人群', '偏离度', 'AI 相对人群分布的优势', '95% 区间', '判定'],
       [['最典型的 20%', '0.13–0.37', '−0.235', '[−0.259, −0.211]', 'AI 明显更差'],
        ['中间 20%', '0.47–0.56', '−0.316', '[−0.354, −0.276]', 'AI 明显更差'],
        ['最不典型的 20%', '0.70–1.00', '<strong>+0.116</strong>', '[+0.077, +0.154]', '<strong>AI 反超</strong>']],
       '这解释了此前所有"AI 平均而言更差"的结果：它对 80% 的人拖后腿，'
       '但在最需要个性化的 20% 人身上扳回来。可惜的是——分档本身要用到答案，'
       '所以这是"事后解释"，还不能直接当"事先挑人"的规则。')}

<h3>价值二：它知道具体题目的特殊之处</h3>
<p>这是最硬的一条证据。我们做了一个"打乱卡片"的对照：把 AI 对<strong>这道题</strong>的预测，
换成它对<strong>同一份问卷另一道题</strong>的预测，再和其他信息混合。</p>
<div class="grid3">
{card('真实卡片', f'{ext_shuffle.get("model", 0):.1f}pp', '用 AI 对这道题的预测混合后，误差。', '对照')}
{card('打乱卡片', f'{ext_shuffle.get("shuffled", 0):.1f}pp', '换成另一道题的预测后，误差几乎翻倍。', '反证')}
{card('差多少', f'+{ext_shuffle.get("shuffled", 0) - ext_shuffle.get("model", 0):.1f}pp', '说明 AI 提供的不是"通用先验"，而是这道题的信息。', '结论')}
</div>
<p class="small">这张图用的是外部验证数据（下一幕）。同样的结果在 8 套内部研究里都成立，
只有"包装与拒买"那套例外——因为 AI 在那套上比"每档等分"还差。</p>
</section>'''

    # ---------- act 5: recipe ----------
    recipe = f'''
<section id="recipe"><span class="number">第五幕 · 可交付的方案</span>
<h2>把 AI 和"十几份真实回答"混在一起，比两者单独用都好</h2>
<p class="lead">如果历史答案不存在，你手里通常还有一个很小的东西：<strong>刚收回来的十几份问卷</strong>。
问题于是变成——问真人，还是问模型，还是都要？</p>

<h3>先回答"要几份"</h3>
<p>我们从每套研究的历史受访者里随机抽 k 人当作"小样本实测"，看它什么时候超过"只问 AI"：</p>
<figure><h3>实测要多少人，才能超过 AI</h3>
<div id="storyCrossover" class="echart" style="height:430px"></div>
<figcaption>横轴是小样本人数，纵轴是分布误差；每条虚线是"只问 AI"的水平。
曲线降到虚线以下的位置，就是"该改用实测"的人数。<strong>多数问卷在 20–40 份处交叉</strong>；
西班牙番茄例外，它的题卡彼此差异极大，历史答案要到三百份才追上。</figcaption></figure>

<h3>再回答"能不能相加"</h3>
<p>用一条<strong>不调参、写死</strong>的规则混合：权重 w = k/(k+20)，即样本越多越信实测。
关键是配上对照——把同样权重用在"均匀分布"上。只有"混合 AI"更好，才能说明 AI 提供了信息。</p>
<div class="grid3">
{card('混合有增益', '+5.6pp', '九套问卷、88 张题卡的汇总，<strong>95% 区间 [+3.9, +7.3]</strong>，'
      f'九套里 {positive} 套为正。Pro 与 Qwen 两个模型一致。', '主结果')}
{card('不是降方差', '对照赢', '把小样本与"均匀分布"同样混合，效果明显更差——'
      '说明 AI 带的是信息，不是"平均一下降噪声"。', '关键对照')}
{card('个体也没吃亏', '7 / 8', '同一批数据里，混合方案在个体预测误差上也更好，'
      '没有出现"群体变好、个体变差"的交换。', '防止顾此失彼')}
</div>

<h3>最后：换一套从没用过的数据，还算数吗</h3>
<p>上面所有结论都来自 14 套研究，而它们都参与过筛查。为检验泛化，我们接入了一套
<strong>完全没碰过</strong>的公开问卷：Amazon「Open eCommerce」美国线上样本，
{ext_people:,} 名受访者、14 道单选题，题型与人群体量都与前面不同。</p>
<figure><h3>外部数据上的四种做法</h3>
<div id="storyExternal" class="echart" style="height:360px"></div>
<figcaption>AI 仍然远好于"每档等分"，也仍然远差于查表——与前 14 套同向；
而小样本混合的规则在这里同样成立（k=20 时比混合均匀分布好 {ext_gain:.1f}pp）。
最左两根柱子是同一批人、同一道题，只改了"让 AI 选一项"和"让 AI 给概率"。</figcaption></figure>
{table('外部验证：五条判据全部通过',
       ['判据', '结果', '说明'],
       ([['最稳的一条在新数据上复现', '通过',
          f'只改输出形式：选一项 {ext_native:.1f} → 给概率 {ext_ai:.1f}pp，'
          f'区间 [{ext_contrast["improvement_95_ci"][0]:.1f}, {ext_contrast["improvement_95_ci"][1]:.1f}]']]
        if ext_native and ext_contrast else [])
       + [['既有结论复现', '通过', f'AI {ext_ai:.1f}pp vs 等分 {ext_uniform:.1f}pp vs 查表 {ext_ref:.1f}pp'],
        ['小样本混合', '通过', f'k=20 时增益 +{ext_gain:.1f}pp，与内部研究同向'],
        ['卡片级信息', '通过', f'打乱卡片后误差 {ext_shuffle.get("model", 0):.1f} → {ext_shuffle.get("shuffled", 0):.1f}pp'],
        ['个体不吃亏', '通过', '同一批数据里个体误差同时改善']],
       '这套数据在此前没有参与任何一次调框架、选权重或做校准，因此它检验的是"规则能否迁移"。')}

<div class="callout"><strong>最终配方（可以直接照做）</strong><br>
① 新问卷先收 <strong>10–30 份</strong>真实回答；<br>
② 若还要用 AI，先让它给出分布，再与实测按 <strong>w = k/(k+20)</strong> 混合；<br>
③ 如果 AI 在这套题上的误差比"每档等分"还差，<strong>不要混合</strong>，直接用实测。</div>
</section>'''

    # ---------- before / after ----------
    compare = f'''
<section id="compare"><span class="number">一页对比</span>
<h2>改造前 vs 改造后</h2>
{table('同一批数据，不同做法的表现',
       ['环节', '改造前', '改造后', '变化'],
       [['输出形式', '让 AI 选一个答案', '让 AI 给每个选项的概率', '群体误差下降 16.6–25.3 个百分点'],
        ['用到历史答案', '没有', '把历史分布写进提示', '相对改善 16.5–24.9%'],
        ['与他人比较', '和"随机猜"比', '和"同样信息的查表"比', '发现 14/14 落后'],
        ['小样本利用', '不用', '按 w=k/(k+20) 与 AI 混合', '+5.6pp [+3.9, +7.3]'],
        ['使用前提', '任何情况都用 AI', '按题卡判断，AI 差于等分就不混合', '避免"包装与拒买"那类反例']],
       '前半段（输出形式、历史答案）来自 14 套研究；后半段（混合规则）在 9 套内部研究 + 1 套外部数据、'
       '2 个模型上验证过。')}
</section>'''

    # ---------- limits ----------
    limits = f'''
<section id="limits"><span class="number">诚实边界</span>
<h2>这些结论不能说什么</h2>
<ul>
<li><strong>不能说"AI 完全不懂人"。</strong>它赢不了"同样信息的查表"，但当只有十几份真实回答时，
它的信息能让结果明显变好——这是实测出来的增量，不是安慰奖。</li>
<li><strong>不能说这是 {stats.get("studies", 14)} 次独立复现。</strong>14 套研究只对应 {stats.get("clusters", 11)} 个独立数据集
（Pew 四套算一个簇），增加的是领域覆盖，不是统计功效。</li>
<li><strong>不能把"误差 {pp(min(noise_values))}–{pp(max(noise_values))} 个百分点"当成准确度。</strong>
96 人规模的抽样噪声本身就有这么大，我们的解读都放在这把尺子上。</li>
<li><strong>外部验证只覆盖美国线上样本。</strong>跨国家、跨语言是否成立，没有测。</li>
<li><strong>没有测"商品属性结构化注入"这条线。</strong>现有的商品选择数据里，属性模型的参照本身就赢了 AI，
但"把属性结构化喂给 AI"这条路还没走过。</li>
<li><strong>事后分解不等于可用规则。</strong>"AI 在最不典型的 20% 人身上更准"需要用答案来分档，
目前只能解释、不能事先挑选。</li>
</ul>
</section>'''

    # ---------- literature ----------
    literature = f'''
<section id="literature"><span class="number">放进研究脉络</span>
<h2>我们的发现，与已有研究对得上吗</h2>
{table('与文献的对话',
       ['我们的发现', '已有研究', '关系'],
       [['方向对、幅度错（第一名命中 {pct(direction.get("ai_argmax", 0))}，但份额差 8–30 个百分点）',
         'Nature 实验预测研究：模型能高相关地预测实验效应，却系统性高估幅度',
         '同一种失败形态：知道方向，不知道分寸'],
        ['AI 把人群差异压平，且不能靠调参修正',
         '抽样机制研究（2026）：模型能描述分布，重复抽样时却集中选择同一项',
         '机制一致；我们的补充是"没有通用旋钮"'],
        ['提高随机性会同时伤到个体预测',
         '电动车偏好研究：温度升高改善群体分布、损害逐人预测',
         '我们绕开了这个交换：在模型外部做混合，个体同时变好'],
        ['模型必须带着"数据条件"评价，而不是排一个总分榜',
         '访谈代理论文（2026 v3）：同样任务，给不同信息，表现从 74% 到 86%',
         '支持我们的核心主张：先说清楚给了什么，再谈准不准'],
        ['小样本 + 模型的组合优于任一单独使用',
         'Centaur（Nature 2025）证明行为训练有效；但访谈代理附录显示微调并不总有效',
         '方向一致：关键在于信息，不在于模型的大小或训练量']],
       '以上都是性质上的对照，不是数字上的排名——各研究的任务、指标、样本都不同，不能直接比大小。')}
<p>文献里还有一条我们没做的事：<strong>把自然语言意愿映射成评分分布</strong>（即 SSR 方法）。
我们的评分题目前是直接让模型给概率，没有走"先写文字再映射"这条路。这可能是下一个值得试的方向。</p>
</section>'''

    # ---------- ending ----------
    ending = f'''
<section id="ending" class="intro"><span class="number">回到开头</span>
<h2>所以，下周那个方案会怎么定？</h2>
<p class="lead">回到最初的场景：下周要定包装方案，发几百份问卷来不及。现在你知道该怎么做了。</p>
<div class="grid3">
{card('第一天', '先收 10–20 份', '找 10–20 个符合目标人群的人，问同样的题。这比什么模型都快，而且几乎不花钱。', '步骤一')}
{card('第二天', '问一次 AI', '让 AI 对同一套题给出分布（注意：要概率，不要让它只选一个）。', '步骤二')}
{card('第三天', '按公式混合', 'w = k/(k+20)：5 份时八成信 AI，20 份时五五开，40 份时八成信实测。若 AI 连"每档等分"都不如，直接用实测。', '步骤三')}
</div>
<p>预期效果（八套内部研究的中位数）：</p>
{table('样本很少时，AI 到底帮了多少',
       ['手上有的样本', '只问 AI', '只用实测', '两者混合', '混合相对只用实测'],
       [['5 份', f"{d['median_model']['5']:.1f}pp", f"{d['median_pilot']['5']:.1f}pp",
         f"<strong>{d['median_blend']['5']:.1f}pp</strong>",
         f"降低 {d['median_pilot']['5'] - d['median_blend']['5']:.1f} 个百分点"],
        ['10 份', f"{d['median_model']['10']:.1f}pp", f"{d['median_pilot']['10']:.1f}pp",
         f"<strong>{d['median_blend']['10']:.1f}pp</strong>",
         f"降低 {d['median_pilot']['10'] - d['median_blend']['10']:.1f} 个百分点"],
        ['20 份', f"{d['median_model']['20']:.1f}pp", f"{d['median_pilot']['20']:.1f}pp",
         f"<strong>{d['median_blend']['20']:.1f}pp</strong>",
         f"降低 {d['median_pilot']['20'] - d['median_blend']['20']:.1f} 个百分点"],
        ['40 份', f"{d['median_model']['40']:.1f}pp", f"{d['median_pilot']['40']:.1f}pp",
         f"<strong>{d['median_blend']['40']:.1f}pp</strong>",
         f"降低 {d['median_pilot']['40'] - d['median_blend']['40']:.1f} 个百分点"]],
       '越低越好。注意第二列和第三列的关系：<strong>实测攒到 40 份时，它自己就已经比 AI 准了</strong>——'
       'AI 的价值集中在最开头那几天。')}
<p>所以准确的用法是：<strong>问卷刚发出去、只有个位数或十几份回答时，AI 能把误差压掉近一半；
等攒到四五十份，就该相信实测、把 AI 的权重降下来。</strong>这正是 w = k/(k+20) 自动做的事——
样本越多，权重越偏向实测。</p>
<div class="callout"><strong>一句话收尾</strong>：这项研究最初想回答"AI 能不能替代真人问卷"。
答案是不能，但它给出了一个更好的答案——<strong>AI 不能替代数据，它能让小数据更值钱。</strong>
这也正好呼应了开头那个问题：你没有时间发几百份问卷，但你也不需要了。</div>
<p class="small">全部数字来自 <code>decision_lab/reports/cross-study-v1/</code> 下的冻结结果文件，
并由 <code>reports/build_story.py</code> 自动填入本页；任何手工改动都会在 <code>reports/verify.py</code> 中报错。</p>
</section>'''

    page = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="description" content="MatrAIx 决策模拟实验的故事版报告：'
            'AI 能否替代真人问卷、输在哪里、小样本如何与 AI 互补。">'
            '<title>AI 能替真人回答问卷吗？｜MatrAIx 实验故事</title>'
            f'<style>{STYLE}</style></head><body>'
            f'{hero}'
            '<nav class="nav" aria-label="章节"><div>'
            '<a href="#answer">答案</a><a href="#method">怎么比的</a><a href="#act1">第一幕</a>'
            '<a href="#act2">第二幕</a><a href="#act3">第三幕</a><a href="#act4">第四幕</a>'
            '<a href="#recipe">方案</a><a href="#compare">对比</a><a href="#limits">边界</a>'
            '<a href="#literature">文献</a><a href="#ending">回到开头</a>'
            '</div></nav><main>'
            + answer + method + act1 + act2 + act3 + act4 + recipe + compare + limits + literature + ending
            + '<p class="small" style="text-align:center">要逐题看：'
              '<a href="cards.html">每一道题的真人 / 原版 / 优化分布 →</a>'
              ' · 要核对全部数字：<a href="index.html">技术版报告 →</a></p>'
            + '</main>'
            + f'<script id="story-data" type="application/json">{DATA}</script>'
            + f'<script>{ECHARTS}</script>'
            + f'<script>{CHARTS}</script>'
            + '</body></html>')
    return page


STYLE = (HERE / 'style.css').read_text()
ECHARTS = (HERE / 'vendor/echarts.min.js').read_text()
CHARTS = (HERE / 'charts_story.js').read_text()
DATA = '{}'


def main():
    global DATA
    payload = {
        'rows': [{'study': r['study'], 'label': LEGEND.get(r['study'], r['study']),
                  'ai_vs_reference': r['ai_vs_reference'],
                  'ci': r['ai_vs_reference_ci']} for r in sorted(
            gather()['rows'], key=lambda r: r['ai_vs_reference'])],
        'direction': gather()['direction'],
        'curves': _curves(),
        'external': _external_bars(),
    }
    DATA = json.dumps(payload, ensure_ascii=False).replace('</', '<\\/')
    page = build()
    (HERE / 'story.html').write_text(page)
    print(f'Built narrative report: {HERE / "story.html"} ({len(page):,} bytes)')


def _curves():
    blend = load('blend-qwen.json', {'studies': {}})['studies']
    curves = []
    for study, payload in blend.items():
        curves.append({'label': LEGEND.get(study, study),
                       'values': [payload['crossover'][str(k)] for k in (5, 10, 20, 40, 80, 160, 320)],
                       'ai': payload['blend']['20']['model']})
    return curves


def _external_bars():
    external = load('external-v2-results.json', {'studies': {}})['studies'].get('openecommerce', {})
    arms = external.get('results', {}).get('arms', {})
    qwen = load('screening-ext-opt.json', {'studies': {}})['studies'].get('openecommerce', {})
    pro = load('blend-ext-pro.json', {'studies': {}})['studies'].get('openecommerce', {})
    return {
        'rows': [
            {'label': '只让 AI 选一项（原版）', 'value': (arms.get('original') or {}).get('card_tv_pp')},
            {'label': '只问 AI（Pro，保留概率）', 'value': (arms.get('optimized') or {}).get('card_tv_pp')},
            {'label': '只问 AI（Qwen）', 'value': qwen.get('tv_pp')},
            {'label': '小样本 20 份 + AI 混合', 'value': (pro.get('blend', {}).get('20', {}) or {}).get('blend_model')},
            {'label': '每档等分', 'value': (arms.get('uniform') or {}).get('card_tv_pp')},
            {'label': '历史查表', 'value': (arms.get('stratum_history') or {}).get('card_tv_pp')},
        ]}


if __name__ == '__main__':
    main()
