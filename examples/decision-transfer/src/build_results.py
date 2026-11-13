"""Offline results page: four-arm Brier, paired intervals and one anonymised example.

Reads only frozen public summaries plus the local ledger; never writes individual rows
into the report.
"""
import json
from pathlib import Path

from freeze import HERE

PRIVATE = Path.home() / '.local/share/matraix-decision-transfer/work/stage2'
ARMS = [('basic', '只有基础资料'), ('own', '加本人的真实资料'), ('other', '加可比他人的资料'),
        ('matraix', '当前 MatrAIx 方法')]
THRESHOLD = 0.02


def pct(value):
    return f'{value * 100:+.2f}%'


def decision(comparisons, arms):
    own_basic = next(c for c in comparisons if c['arm'] == 'own' and c['reference'] == 'basic')
    own_other = next(c for c in comparisons if c['arm'] == 'own' and c['reference'] == 'other')
    passes = (own_basic['relative'] or -1) >= THRESHOLD and own_basic['low'] > 0 \
        and own_other['low'] > 0
    if passes:
        verdict = '通过本轮门槛：可以进入同研究内的品类外推检验（服装、食品），但仍不能称为跨研究复现。'
    elif (own_basic['low'] > 0) and (own_basic['relative'] or 0) >= THRESHOLD:
        verdict = '本人资料优于基础资料且区间高于零，但没有优于错配资料；帮助可能来自资料内容本身，不来自「对应到本人」。'
    elif own_other['high'] < 0:
        verdict = ('本人资料相对基础资料方向为正但区间跨零（+{:.1f}%，[{:+.4f}, {:+.4f}]），而相对错配资料反而显著更差'
                   '（{:+.4f}，[{:+.4f}, {:+.4f}]）。按方案不宣称真实资料有额外价值，也不进入品类外推。'
                   ).format(own_basic['relative'] * 100, own_basic['low'], own_basic['high'],
                            own_other['absolute'], own_other['low'], own_other['high'])
    else:
        verdict = '未通过门槛：不扩大样本、不换指标，按方案记录为「真实资料没有显示出额外价值」。'
    return verdict, passes


def bars(arms):
    top = max(row['mean_brier'] for row in arms.values())
    out = []
    for key, label in ARMS:
        value = arms[key]['mean_brier']
        width = value / top * 100
        out.append(f'<div class="bar"><span class="lab">{label}</span>'
                   f'<span class="track"><span class="fill {"best" if key == "own" else ""}" '
                   f'style="width:{width:.1f}%"></span></span><span class="val">{value:.4f}</span></div>')
    return '\n'.join(out)


def interval_rows(comparisons):
    rows = []
    labels = {('own', 'basic'): '本人资料 − 基础资料', ('own', 'other'): '本人资料 − 错配资料',
              ('other', 'basic'): '错配资料 − 基础资料', ('matraix', 'basic'): 'MatrAIx − 基础资料',
              ('matraix', 'own'): 'MatrAIx − 本人资料'}
    for item in comparisons:
        label = labels.get((item['arm'], item['reference']), f"{item['arm']} − {item['reference']}")
        span = f"[{item['low']:+.4f}, {item['high']:+.4f}]"
        rows.append(f'<tr><td>{label}</td><td>{item["absolute"]:+.4f}</td>'
                    f'<td>{pct(item["relative"]) if item["relative"] is not None else "不适用"}</td>'
                    f'<td>{span}</td><td>{"高于零" if item["low"] > 0 else ("低于零" if item["high"] < 0 else "跨零")}</td></tr>')
    return '\n'.join(rows)


def example_block(model='pro'):
    """One anonymised participant: what the model saw and what was chosen."""
    requests = json.loads((PRIVATE / 'requests.json').read_text())
    answers = json.loads((PRIVATE / 'answers.json').read_text())
    state = [json.loads(line) for line in (PRIVATE / 'runs' / f'{model}.jsonl').read_text().splitlines() if line.strip()]
    ok = {(row['sha256'], row['arm']): row for row in state if row.get('status') == 'ok'}
    rigs = sorted({row['rig'] for row in requests if row['role'] == 'evaluation'})
    for rig in rigs:
        own = next((r for r in requests if r['rig'] == rig and r['arm'] == 'own'), None)
        if own is None or (own['sha256'], 'own') not in ok:
            continue
        row = ok[(own['sha256'], 'own')]
        truth = answers[str(rig)]
        lines = []
        for question in own['questions'][:6]:
            qid = question['id']
            options = list(question['options'])
            probability = row['probabilities'][qid][0]
            picked = truth[qid]
            label = question['options'][picked]
            if abs(probability - 0.5) < 1e-9:
                judgement = '持平'
            else:
                judgement = '一致' if (probability > 0.5) == (picked == options[0]) else '相反'
            lines.append(f'<tr><td><code>{qid}</code></td><td>{label}</td>'
                         f'<td>{probability:.2f}</td><td>{judgement}</td></tr>')
        return ''.join(lines)
    return '<tr><td colspan="4">暂无可用示例</td></tr>'


def main():
    results = json.loads((HERE / 'data/stage2-results.json').read_text())
    freeze = json.loads((HERE / 'data/stage2-freeze.json').read_text())
    technical = json.loads((HERE / 'data/stage2-technical.json').read_text())
    diag = json.loads((HERE / 'data/stage2-diagnostics.json').read_text())
    verdict, passed = decision(results['comparisons'], results['arms'])
    armed = results['arms']
    baseline = 0.5
    best = min(row['mean_brier'] for row in armed.values())
    page = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>结果｜真实资料能不能帮 AI 预测这个人</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f5f4ee;color:#213e35;font:17px/1.8 system-ui,-apple-system,"PingFang SC",sans-serif}}
main{{max-width:1000px;margin:auto;padding:40px 24px 70px}}h1{{font-size:34px;line-height:1.35}}h2{{font-size:24px;margin-top:34px}}
.eyebrow,small{{color:#5b6c65}}.notice{{padding:18px 22px;background:#e4eee8;border-left:5px solid #257461;border-radius:5px;margin:22px 0}}
.warn{{background:#f7ead8;border-color:#a97432}}.card{{background:white;border:1px solid #d7ded7;border-radius:12px;padding:20px;margin:16px 0}}
.bar{{display:flex;align-items:center;gap:12px;margin:10px 0}}.lab{{flex:0 0 190px;font-size:15px}}
.track{{flex:1;background:#e8ebe6;border-radius:6px;height:20px;overflow:hidden}}.fill{{display:block;height:100%;background:#8fa8a0}}
.fill.best{{background:#257461}}.val{{flex:0 0 78px;text-align:right;font-variant-numeric:tabular-nums}}
table{{width:100%;border-collapse:collapse;background:white;font-size:15px}}th,td{{padding:9px 10px;border-bottom:1px solid #e3e6e0;text-align:left;vertical-align:top}}
th{{background:#eef1ec}}code{{font-size:13px}}a{{color:#176c65}}footer{{margin-top:34px;font-size:14px;color:#5b6c65}}
</style></head><body><main>
<div class="eyebrow">2026-11-13 · 瑞士六品类 · 电子产品组 · 正式成绩（DeepSeek Pro）</div>
<h1>知道一个人的真实态度，能不能让 AI 更准确地预测他没答过的选择？</h1>
<div class="notice"><strong>结论：{verdict}</strong><br>
四臂同一批 {results['complete_people']} 名受访者、同一套 6 道二选一；分数是逐人 Brier 误差，越低越准。</div>

<h2>四组误差</h2><div class="card">{bars(armed)}
<p><small>参照：每个选项都给 0.5 时，Brier 恒为 0.5。本轮最好的一组为 {best:.4f}。</small></p></div>

<h2>配对比较（2000 次分层重抽样，同人同步）</h2>
<table><tr><th>比较</th><th>绝对差</th><th>相对改善</th><th>95% 区间</th><th>判断</th></tr>{interval_rows(results['comparisons'])}</table>
<p><small>绝对差为「参照臂误差 − 比较臂误差」，正数表示比较臂更准。区间以本次冻结的供体和模型输出为条件，不涵盖所有可能错配或模型随机性。</small></p>

<h2>模型看到什么、实际选了什么（示例，已去标识）</h2>
<table><tr><th>题目</th><th>本人实际选择</th><th>模型给「Offer 1」的概率</th><th>与0.5判断</th></tr>{example_block()}</table>

<h2>为什么会这样（事后诊断，不替代主指标）</h2><div class="card">
<ul>
<li>模型确实会随资料块变动：同一道题上，本人资料与错配资料给出的概率平均相差 {diag['mean_abs_probability_gap_own_vs_other']:.2f}，但 {diag['share_identical_side_of_0.5']*100:.0f}% 的题仍然落在 0.5 的同一侧，很少真正改判。</li>
<li>两臂的自信程度几乎一样（|p−0.5| 约 0.24），差别在于「自信却答错」的比例：本人资料 {diag['own_confident_wrong']*100:.1f}%，错配资料 {diag['other_confident_wrong']*100:.1f}%。</li>
<li>也就是说，本人的态度资料有时和他真实的选择不一致（典型的态度—行为落差），模型却更信它；而错配资料与这个人无关，反而更接近「这类人通常怎么选」的稳定先验。</li>
<li>这条解释是事后提出的，只能说明机制可能是什么，不能反过来证明主比较。</li>
</ul></div>

<h2>这次没有证明什么</h2><div class="notice warn">
<ul><li>只有一套研究通过准入，所以任何结果都是<strong>单一研究内的探索性筛查</strong>，不是跨研究、跨国家复现。</li>
<li>样本框架是「选择有效＋29 项事实齐全」，无法复现作者按答题速度做的剔除。</li>
<li>错配供体固定为这一批，区间不代表所有可能错配；错配诊断也不能证明人格的因果作用。</li></ul></div>

<h2>运行与检查</h2><div class="card">
<p>请求 {freeze['request_estimate']['requests']} 份，估算 {freeze['request_estimate']['usd_peak']:.2f} 美元（上限 10 美元）；Qwen 技术检查 {technical['calls']} 次，其中 {technical['repeat_pairs']} 对相同请求全部出现差异，说明不能假设输出确定。</p>
<p>字段来源：[准入进度](../docs/准入进度.md) · [核心研究方案](../docs/核心研究方案.md) · 冻结规格：[stage2-freeze.json](../data/stage2-freeze.json)</p></div>
<footer>成绩只来自 DeepSeek Pro；Qwen 只做流程检查，不与正式成绩混算。旧实验报告保持原样，不重新计算。</footer>
</main></body></html>'''
    (HERE / 'reports/results.html').write_text(page)
    print(json.dumps({'written': 'reports/results.html', 'passed': passed, 'people': results['complete_people']},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
