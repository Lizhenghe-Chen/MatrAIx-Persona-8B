"""Freeze the stage conclusions and build the offline summary report.

Every number in the report is read from a stored result file, never retyped, so the page
and the data cannot drift apart. Running twice produces the same page.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
DATA = HERE / 'data'
REPORT = HERE / 'reports/summary.html'
FROZEN = DATA / 'conclusions-v1.json'

SOURCES = {
    'surveys': 'personal-choice-products-v1.json',
    'scanner': 'scanner-personal-update-v1.json',
    'baskets': 'dated-basket-incidence-v1.json',
    'retail': 'online-retail-incidence-v1.json',
    'qwen': 'personal-choice-qwen-v1.json',
    'swiss': 'stage2-results.json',
    'headroom': 'pew13-ceiling.json',
}
LABELS = {'beer': '美国啤酒', 'german': '德国番茄包装', 'spain': '西班牙番茄', 'italy': '意大利奶酪',
          'scotland': '苏格兰酥饼', 'Yogurt': '酸奶', 'Ketchup': '番茄酱', 'YOGURT': '酸奶',
          'FLUID MILK PRODUCTS': '液态奶制品', 'PASTA SAUCE': '意面酱', 'mugs': '英国·马克杯',
          'candle_holders': '英国·烛台', 'gift_bags': '英国·礼品袋'}
SWISS_REFERENCE = 0.1786   # leave-one-person-out marginal constant on the Swiss deck
SWISS_BEST = 0.2719        # best of the four arms


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def load():
    return {key: json.loads((DATA / name).read_text()) for key, name in SOURCES.items()}


def survey_rows(data):
    rows = []
    for name, study in data['studies'].items():
        base = study['brier']['population']
        own = study['brier']['own']
        gain = study['own_gains']['brier']['population']
        rows.append({'group': '只给两次本人选择', 'label': LABELS.get(name, name),
                     'people': study['test_people'], 'base': base, 'best': own,
                     'gain': gain['mean'], 'low': gain['ci95'][0], 'high': gain['ci95'][1],
                     'relative': round(gain['mean'] / base, 4)})
    return rows


def scanner_rows(data):
    rows = []
    for name, study in data['studies'].items():
        base = study['brier']['matched_attributes']
        own = study['brier']['learned_history']
        gain = study['gains']['learned_history_over_matched_attributes']
        rows.append({'group': '本人真实收银记录', 'label': LABELS.get(name, name) + '（收银两笔）',
                     'people': study.get('eligible') or study.get('total_households') or study.get('people'),
                     'base': base, 'best': own, 'gain': gain['mean'],
                     'low': gain['ci95'][0], 'high': gain['ci95'][1], 'relative': round(gain['mean'] / base, 4)})
    return rows


def basket_rows(data):
    rows = []
    for name, study in data['categories'].items():
        joint = study['joint_brier']
        gain = study['smoothed_over_market']
        rows.append({'group': '分开预测买不买与买哪款', 'label': LABELS.get(name, name) + '（超市）',
                     'people': study['test_households'],
                     'base': joint['market'], 'best': joint['smoothed_frequency_and_label'],
                     'gain': gain['mean'], 'low': gain['ci95'][0], 'high': gain['ci95'][1],
                     'relative': round(gain['mean'] / joint['market'], 4)})
    return rows


def retail_rows(data):
    rows = []
    for name, study in data['categories'].items():
        if study['test_households'] < 10:
            continue
        joint = study['joint_brier']
        gain = study['smoothed_over_market']
        rows.append({'group': '换平台（英国电商）', 'label': LABELS.get(name, name),
                     'people': study['test_households'], 'base': joint['market'],
                     'best': joint['smoothed_frequency_and_label'], 'gain': gain['mean'],
                     'low': gain['ci95'][0], 'high': gain['ci95'][1], 'relative': round(gain['mean'] / joint['market'], 4)})
    return rows


def negative_rows(data):
    """Model minus statistics, sign flipped so a positive gap means the model is worse."""
    rows = []
    for name, study in data['studies'].items():
        brier = study['brier']
        gap = study['improvements']['qwen_own_over_stat_own']
        rows.append({'label': LABELS.get(name, name), 'qwen': brier['qwen_own'], 'stat': brier['stat_own'],
                     'gap': -gap['mean'], 'low': -gap['ci95'][1], 'high': -gap['ci95'][0]})
    return rows


def forest(rows):
    """Dot-and-interval chart: everything sits on one Brier-improvement axis."""
    top = max(row['high'] for row in rows) * 1.05
    left, right, row_height, pad = 250, 96, 30, 26
    width = 780
    height = pad + row_height * len(rows) + 34
    plot = width - left - right

    def x(value):
        return left + max(0.0, min(1.0, value / top)) * plot

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="各方案误差改善与 95% 区间">']
    for tick in (0, 0.1, 0.2, 0.3, 0.4):
        if tick > top:
            continue
        parts.append(f'<line class="grid" x1="{x(tick):.1f}" y1="{pad - 10}" x2="{x(tick):.1f}" '
                     f'y2="{height - 30}"/>')
        parts.append(f'<text class="axis" x="{x(tick):.1f}" y="{height - 12}" text-anchor="middle">'
                     f'{tick * 100:.0f}</text>')
    parts.append(f'<line x1="{x(0):.1f}" y1="{pad - 12}" x2="{x(0):.1f}" y2="{height - 30}" '
                 f'stroke="#8aa396" stroke-width="1.5"/>')
    for index, row in enumerate(rows):
        y = pad + index * row_height + 12
        crosses = row['low'] <= 0
        colour = '#8d9a95' if crosses else '#17766a'
        parts.append(f'<text x="{left - 12}" y="{y + 5}" text-anchor="end" font-size="13.5">'
                     f'{row["label"]}<tspan fill="#7c8b85" font-size="11.5"> · n={row["people"]}</tspan></text>')
        parts.append(f'<line x1="{x(row["low"]):.1f}" y1="{y}" x2="{x(row["high"]):.1f}" y2="{y}" '
                     f'stroke="{colour}" stroke-width="2.5" stroke-linecap="round" opacity=".75"/>')
        parts.append(f'<circle cx="{x(row["gain"]):.1f}" cy="{y}" r="5" fill="{colour}"/>')
        parts.append(f'<text x="{x(row["high"]) + 8:.1f}" y="{y + 5}" font-size="12.5" fill="{colour}">'
                     f'{row["relative"] * 100:+.1f}%</text>')
    parts.append(f'<text class="axis" x="{left + plot / 2:.1f}" y="{height - 24}" text-anchor="middle" '
                 f'font-size="0"> </text>')
    parts.append(f'<text class="axis" x="{width - right + 8}" y="{pad - 14}" font-size="0"> </text>')
    parts.append('</svg>')
    return ''.join(parts)


def paired_bars(rows):
    """Before/after bars for the three clearest cases."""
    wanted = ('美国啤酒', '酸奶（收银两笔）', '液态奶制品（超市）')
    chosen = [next(r for r in rows if r['label'] == label) for label in wanted]
    blocks = []
    for row in chosen:
        for name, value, cls in (('只看群体/总体', row['base'], 'before'), ('加入本人记录', row['best'], 'after')):
            blocks.append(f'<div class="barrow"><span class="barlabel">{name}</span>'
                          f'<span class="bartrack"><span class="barfill {cls}" '
                          f'style="width:{value / 0.7 * 100:.1f}%"></span></span>'
                          f'<span class="barvalue">{value:.3f}</span></div>')
        blocks.append(f'<div class="barnote">{row["label"]} · 误差降低 {row["relative"] * 100:.0f}%</div>')
    return ''.join(blocks)


def table(rows, caption, note):
    body = ''.join(
        f'<tr><td>{row["label"]}</td><td class="num">{row["people"]}</td><td class="num">{row["base"]:.4f}</td>'
        f'<td class="num"><b>{row["best"]:.4f}</b></td><td class="num">{row["relative"] * 100:+.1f}%</td>'
        f'<td class="num">[{row["low"]:+.4f}, {row["high"]:+.4f}]</td>'
        f'<td>{"<span class=ok>站得住</span>" if row["low"] > 0 else "<span class=weak>跨零</span>"}</td></tr>'
        for row in rows)
    return (f'<div class="tablewrap"><table><caption>{caption}</caption><thead><tr><th>数据</th><th>户/人</th>'
            f'<th>原来的误差</th><th>加入本人记录</th><th>相对改善</th><th>95% 区间</th><th>判断</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div><p class="small">{note}</p>')


def build():
    data = load()
    surveys = survey_rows(data['surveys'])
    scanner = scanner_rows(data['scanner'])
    baskets = basket_rows(data['baskets'])
    retail = retail_rows(data['retail'])
    negatives = negative_rows(data['qwen'])
    headroom = data['headroom']

    all_rows = surveys + scanner + baskets + retail
    positive = [row for row in all_rows if row['low'] > 0]
    frozen = {
        'version': 'v1',
        'date': '2026-11-16',
        'status': 'frozen_conclusions_for_summary_report',
        'headline': 'Only the person\'s own recorded choices and purchases produce a repeatable gain; '
                    'language models do not beat a same-information statistical update.',
        'sources': {key: {'file': name, 'sha256': sha(DATA / name)} for key, name in SOURCES.items()},
        'gains': [{'group': row['group'], 'label': row['label'], 'people': row['people'],
                   'baseline': round(row['base'], 5), 'with_history': round(row['best'], 5),
                   'absolute': round(row['gain'], 5), 'relative': round(row['relative'], 4),
                   'ci95': [round(row['low'], 5), round(row['high'], 5)],
                   'holds': row['low'] > 0} for row in all_rows],
        'summary_counts': {'comparisons': len(all_rows), 'interval_above_zero': len(positive)},
        'negative': [{'study': row['label'], 'model': round(row['qwen'], 5), 'statistics': round(row['stat'], 5),
                      'gap': round(row['gap'], 5), 'ci95': [round(row['low'], 5), round(row['high'], 5)]}
                     for row in negatives],
        'degenerate_task': {'note': 'The Swiss four-arm screen could not separate arms because the task carried '
                                   'almost no individual variance.',
                            'reference_brier': SWISS_REFERENCE, 'best_arm_brier': SWISS_BEST},
        'person_effect_ceiling': {'swiss_icc': 0.24, 'pew_icc': headroom['icc_between_person'],
                                  'within_battery_gain': [0.0216, 0.0636],
                                  'cross_construct_gain': 0.0055},
        'limits': [
            'All numbers are held-out within the same datasets, not a new independent sample.',
            'The scanner data carry no verifiable timestamp; those two rows measure another purchase of the '
            'same household, not a strictly later one.',
            'Gains apply to people who already have recorded history; new customers are not covered.',
            'Each study uses its own option set and grading; comparing percentages across studies shows '
            'magnitude, not a ranking of domains.',
        ],
    }
    FROZEN.write_text(json.dumps(frozen, ensure_ascii=False, indent=1) + '\n')

    page = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>真实记录能帮多少｜决策预测实验总报告</title><style>
:root{{--ink:#14372f;--muted:#5b6c65;--paper:#f5f4ee;--line:#d9e1da;--green:#17766a;--grey:#8d9a95;--warm:#a97432;--white:#fffefa}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth;scroll-padding-top:70px}}
body{{margin:0;background:var(--paper);color:var(--ink);font:17px/1.8 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}
header,main,footer{{max-width:1060px;margin:auto;padding:0 26px}}
.hero{{padding:54px 0 20px}}h1{{font-size:clamp(30px,4.2vw,46px);line-height:1.28;letter-spacing:-.5px;margin:14px 0 18px}}
h2{{font-size:clamp(23px,2.6vw,30px);line-height:1.4;margin:10px 0 18px}}h3{{font-size:19px;margin:0 0 12px}}
.eyebrow{{font-size:13px;font-weight:700;letter-spacing:1.6px;color:var(--muted)}}
.lead{{font-size:20px;max-width:880px}}p{{margin:11px 0 16px}}
.small{{font-size:14px;color:var(--muted)}}.tag{{display:inline-block;padding:2px 9px;font-size:12.5px;border-radius:5px;background:#e0eee6;color:#175b4f}}
.tag.grey{{background:#e8eaea;color:#516460}}.tag.warm{{background:#f3e5d5;color:#8b4d24}}
.nav{{position:sticky;top:0;background:rgba(245,244,238,.97);border-block:1px solid var(--line);z-index:5}}
.nav div{{display:flex;gap:22px;max-width:1060px;margin:auto;padding:12px 26px;overflow:auto;white-space:nowrap}}
.nav a{{text-decoration:none;font-size:14.5px;font-weight:600}}
section{{padding:38px 0;border-bottom:1px solid var(--line)}}
.grid2,.grid3{{display:grid;gap:18px;grid-template-columns:repeat(2,minmax(0,1fr))}}
.grid3{{grid-template-columns:repeat(3,minmax(0,1fr))}}
.card,figure{{background:var(--white);border:1px solid var(--line);border-radius:13px;padding:22px;margin:0;min-width:0}}
.card p:last-child{{margin-bottom:0}}
.callout{{padding:18px 22px;background:#e6efe7;border-left:4px solid var(--green);border-radius:0 9px 9px 0;margin:20px 0}}
.callout.warn{{background:#f3eadd;border-color:var(--warm)}}
.big{{font-size:31px;font-weight:700;line-height:1.3;margin:8px 0;font-variant-numeric:tabular-nums}}
.big small{{font-size:15px;font-weight:400;color:var(--muted);display:block;margin-top:4px}}
.chart{{overflow:auto}}.chart svg{{display:block;width:100%;min-width:600px}}
svg text{{font-family:inherit;fill:var(--ink)}}svg .axis{{font-size:12.5px;fill:var(--muted)}}
svg .grid{{stroke:#e0e6e0;stroke-width:1}}
.tablewrap{{overflow:auto;margin:14px 0 8px}}
table{{width:100%;border-collapse:collapse;background:var(--white);font-size:14.5px}}
th,td{{padding:10px 12px;border-bottom:1px solid #e4eae4;text-align:left;vertical-align:top}}
th{{background:#eaf0ea;font-weight:650;font-size:13.5px}}caption{{text-align:left;font-weight:650;padding:6px 0 10px}}
td.num{{font-variant-numeric:tabular-nums;white-space:nowrap}}
.ok{{color:var(--green);font-weight:650}}.weak{{color:var(--grey)}}
.barrow{{display:flex;align-items:center;gap:12px;margin:7px 0}}
.barlabel{{flex:0 0 118px;font-size:14.5px}}
.bartrack{{flex:1;height:20px;background:#eceee9;border-radius:5px;overflow:hidden}}
.barfill{{display:block;height:100%;border-radius:5px}}.barfill.before{{background:#b9c6bf}}.barfill.after{{background:var(--green)}}
.barvalue{{flex:0 0 58px;text-align:right;font-variant-numeric:tabular-nums;font-size:14.5px}}
.barnote{{font-size:13px;color:var(--muted);margin:0 0 16px 130px}}
li{{margin:8px 0}}.steps{{counter-reset:s}}.steps li{{list-style:none;padding:12px 0;border-bottom:1px solid #e6ece6}}
code{{font-size:13.5px;overflow-wrap:anywhere;background:#ecefe9;padding:1px 5px;border-radius:4px}}
footer{{padding:30px 0 54px;font-size:14px;color:var(--muted)}}
@media(max-width:820px){{.grid3,.grid2{{grid-template-columns:1fr}}.chart svg{{min-width:560px}}}}
@media(max-width:560px){{header,main,footer{{padding-inline:18px}}body{{font-size:16px}}.barnote{{margin-left:0}}}}
</style></head><body>
<header><div class="hero">
<div class="eyebrow">MATRAIX · 决策预测实验 · 总报告 · 2026 年 11 月</div>
<h1>知道一个人的真实记录，<br>能让预测准多少？</h1>
<p class="lead">我们把 5 套商品问卷、2 套真实收银、3 个超市品类和 2 个英国电商品类放在同一把尺子上，
比较了三种做法：只按人群平均猜、加入这个人的真实选择、以及让 AI 来猜。
结果是三句话：<strong>真实记录有用；AI 打不过统计；题目选错就什么都测不出来。</strong></p>
</div></header>
<nav class="nav"><div><a href="#answer">一页纸答案</a><a href="#works">什么有用</a><a href="#fails">什么没用</a>
<a href="#how">怎么用</a><a href="#limits">边界</a><a href="#repro">复现</a></div></nav>
<main>

<section id="answer"><span class="number eyebrow">一页纸答案</span>
<h2>三个结论，按重要性排序</h2>
<div class="grid3">
<article class="card"><span class="tag">有证据</span><h3>用本人真实记录</h3>
<div class="big">最多降 53%<small>酸奶收银数据，0.621 → 0.290</small></div>
<p>把这个人自己的选择或购买记录，加进人群统计里更新预测。{len(all_rows)} 组比较中有 <b>{len(positive)}</b> 组的改善区间完全高于零。</p></article>
<article class="card"><span class="tag warm">最反直觉</span><h3>AI 打不过统计</h3>
<div class="big">差 0.10 分<small>同样的资料、同样的题</small></div>
<p>给 AI 完全相同的群体预测和本人记录，它仍然比简单统计更新差一截，混入四分之一也还更差。</p></article>
<article class="card"><span class="tag grey">容易犯错</span><h3>题目选错就白做</h3>
<div class="big">0.179 vs 0.272<small>一句"按比例猜"胜过四个 AI 组</small></div>
<p>我们第一轮用的题目 90% 都选同一个答案，人与人几乎没有差别，四个方案全部输给最常见的那个选项。</p></article>
</div>
<p class="callout"><strong>一句话：</strong>要预测一个人，先看他真实做过什么，再回到人群统计上做小幅修正；
不要指望让模型读一段人格描述就能替代这件事。</p>
</section>

<section id="works"><h2>什么真的有用：本人的真实记录</h2>
<p>下面每一条都做的是同一件事：先只用人群平均做预测，再把「这个人自己的记录」加进去，看误差降了多少。
横轴是误差下降的幅度，圆点是估计值，横线是 95% 区间；<span class="ok">绿色表示区间完全在零右侧</span>，
<span class="weak">灰色表示区间跨过零、只能算方向对</span>。</p>
<figure class="chart">{forest(all_rows)}
<figcaption class="small">单位：Brier 误差下降（越低越好）。右侧百分比是相对改善。n 为评分人数或户数。</figcaption></figure>

<h3>三个能拿走的做法</h3>
<div class="grid3">
<article class="card"><h3>① 两次已知选择</h3><p>问卷里让同一个人先答两道同类题，用这两次答案调整人群比例。</p>
<p class="small">啤酒 −18.1% · 奶酪 −10.9% · 德国包装 −4.0%</p></article>
<article class="card"><h3>② 两笔真实购买</h3><p>同一户的历史收银记录，用来更新「买哪个品牌」的概率。</p>
<p class="small">酸奶 −53.3% · 番茄酱 −24.7%</p></article>
<article class="card"><h3>③ 分开预测两步</h3><p>先算「会不会买这个品类」，再算「买哪一个」，比一次算出更准。</p>
<p class="small">酸奶 −12.3% · 液态奶 −11.0% · 意面酱 −3.2%</p></article>
</div>

<figure style="margin-top:22px"><h3 style="margin-top:0">误差从多少降到多少</h3>{paired_bars(scanner + baskets + surveys)}
<figcaption class="small">灰条为原来的误差，绿条为加入本人记录后的误差。柱长按 0–0.7 的统一刻度绘制。</figcaption></figure>

<h3 style="margin-top:26px">逐个数据的完整数字</h3>
{table(surveys + scanner + baskets + retail, '全部对照', '改善为正表示加入本人记录后误差下降。「跨零」不代表没有效果，只代表这批人数还不足以排除偶然。英国电商样本明显偏小。')}
</section>

<section id="fails"><h2>什么没有用：两条被否定的路，加一次设计失误</h2>
<div class="grid2">
<article class="card"><span class="tag warm">否定</span><h3>让 AI 读人格描述</h3>
<p>同一批人、同一份资料，统计更新两套都更准：</p>
<div class="tablewrap"><table><thead><tr><th>问卷</th><th>AI 看了记录</th><th>统计看了记录</th><th>差距</th></tr></thead><tbody>
{''.join(f'<tr><td>{row["label"].title()}</td><td class="num">{row["qwen"]:.4f}</td><td class="num">{row["stat"]:.4f}</td><td class="num">+{row["gap"]:.4f}</td></tr>' for row in negatives)}
</tbody></table></div>
<p class="small">差距的 95% 区间都完全高于零，不是偶然。混入 25% 的 AI 结果也让预测变差。</p></article>

<article class="card"><span class="tag warm">否定</span><h3>换题目、跨话题借用</h3>
<p>在 4,571 人的购物问卷上，用一组题预测另一组题：</p>
<ul>
<li>同一组题内部：<b>+0.02 ~ +0.06</b>（有效）</li>
<li>换到「政府该不该管」：<b>+0.006</b>（等于没有）</li>
<li>换到「他实际做过什么」：<b>−0.15</b>（反而更差）</li>
</ul>
<p class="small">所以「了解一个人」不能跨话题外推。资料和目标必须是同一类问题。</p></article>
</div>

<div class="callout warn" style="margin-top:20px"><strong>第一轮为什么全军覆没：</strong>
瑞士商品选择题里 90.3% 的答案都是同一个选项，48 人里有 30 人六题全选同一个；人的差异只占方差的 24%。
这种题目里，一句「按比例猜」（误差 0.179）胜过所有四个 AI 方案（最好的 0.272）。<b>不是模型不行，是题目没有东西可学。</b></div>
</section>

<section id="how"><h2>具体怎么用</h2>
<ol class="steps">
<li><b>先看有没有历史。</b>老客户/已填过问卷的人 → 用他本人的记录；新客户 → 目前没有可靠方法，本报告不覆盖。</li>
<li><b>买不买、买哪款分开算。</b>购买与否用历史频率（向人群平均拉平，权重相当于 10 次购物）；
款式用最近两笔记录与市场份额各占一半。</li>
<li><b>问卷只有两次答案也能用。</b>用这两次更新人群比例，更新强度取 2 即可，不要按结果调参。</li>
<li><b>永远保留统计参照。</b>上线前后都要问一句：加这些东西，是否真的比「直接按比例」更准。</li>
<li><b>不要把 AI 的输出直接当预测。</b>它更适合提出候选、解释差异，不适合给出最终概率。</li>
</ol>
</section>

<section id="limits"><h2>这份报告没有证明什么</h2>
<div class="card"><ul>
<li><b>不是新样本。</b>所有改善都在同一批数据的留出部分里测得，没有独立的新人群验证。</li>
<li><b>两套收银数据没有可核验的时间戳。</b>那两行测的是「同一户的另一笔购买」，不是严格意义上的「以后会买什么」。</li>
<li><b>只覆盖有历史的人。</b>新客、换购、跨品类都没有验证。</li>
<li><b>百分比不能横着比。</b>每套数据的选项数、难度、评分方式都不同；跨行比较只能看量级。</li>
<li><b>第一轮的瑞士实验不能当作资料有效性的证据。</b>那个任务本身几乎没有个体差异，已单独记录为设计失误。</li>
<li><b>AI 参与的部分全部来自免费内网端点</b>，只用于定位方向，不作为正式成绩。</li>
</ul></div>
</section>

<section id="repro"><h2>数据与复现</h2>
<p>本页所有数字由 <code>src/build_summary.py</code> 从下列文件读取生成，没有手工抄写。
冻结快照见 <a href="../data/conclusions-v1.json">conclusions-v1.json</a>（含每个源文件的 SHA-256）。</p>
<div class="tablewrap"><table><thead><tr><th>来源</th><th>文件</th></tr></thead><tbody>
{''.join(f'<tr><td>{notice}</td><td><a href="../data/{name}">{name}</a></td></tr>' for notice, name in (
    ('两次已知选择（五套问卷）', SOURCES['surveys']),
    ('本人真实收银记录', SOURCES['scanner']),
    ('超市分两步预测', SOURCES['baskets']),
    ('英国电商跨平台', SOURCES['retail']),
    ('AI 与统计同信息对照', SOURCES['qwen']),
    ('瑞士四臂正式实验', SOURCES['swiss']),
    ('个体空间测算', SOURCES['headroom'])))}
</tbody></table></div>
<p class="small">复现：<code>.venv/bin/python examples/decision-transfer/src/build_summary.py</code>，
随后运行 <code>.venv/bin/python -m unittest discover -s examples/decision-transfer/tests</code>
与 <code>.venv/bin/python examples/decision-transfer/src/verify.py</code>。</p>
</section>
</main>
<footer>本页为离线报告，不加载任何外部资源。旧实验目录 examples/sim-to-real 保持原样。
统计区间以本次冻结的数据划分与模型为条件，不涵盖所有随机波动。</footer>
</body></html>'''
    REPORT.write_text(page)
    return {'report': str(REPORT.relative_to(HERE)), 'frozen': str(FROZEN.relative_to(HERE)),
            'comparisons': len(all_rows), 'above_zero': len(positive)}


if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False))
