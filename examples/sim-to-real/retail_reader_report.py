"""Build an accessible, offline narrative from frozen aggregate scores only."""
import hashlib
import json
import posixpath
import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).parent
BASE = ROOT / "study/08_购物预测"
FILES = {
    "pew": "pew-formal-score.json",
    "calibration": "pew-formal-calibration.json",
    "shoes": "shoes-test-score.json",
    "category": "amazon-test-score.json",
    "mix": "amazon-mix-test-score.json",
    "sampling": "pew-answer-sampling-sensitivity.json",
    "audit": "运行核验.json",
    "receipt": "../07_购物数据候选/本次接收核验.json",
}


def table(headers, rows, caption=""):
    return ('<div class="table-wrap"><table>' +
            (f"<caption>{escape(caption)}</caption>" if caption else "") +
            '<thead><tr>' + ''.join(f'<th scope="col">{escape(h)}</th>' for h in headers) +
            '</tr></thead><tbody>' + ''.join(
                '<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>' for row in rows
            ) + '</tbody></table></div>')


def interval(bounds, digits=2):
    return ' 至 '.join(f'{v:+.{digits}f}' for v in bounds)


def build():
    from study.build_report import build_history, FOLDERS
    history = build_history()
    data = {key: json.loads((BASE / name).read_text()) for key, name in FILES.items()}
    data['history'] = history
    extra_files = {f'history_{i}': '../' + folder + '/results.json' for i, folder in enumerate(FOLDERS)}
    parity_file = BASE / 'shoes-input-parity-score.json'
    assert parity_file.exists(), 'The unified narrative requires the supplemental input-parity result.'
    if parity_file.exists():
        data['inputParity'] = json.loads(parity_file.read_text())
        extra_files['input_parity'] = parity_file.name
        extra_files['input_parity_protocol'] = 'shoes-input-parity-protocol.json'
    assert data['audit']['all_independent_scores_verified']
    pew, shoes, cal, cat, mix = (data[k] for k in ('pew', 'shoes', 'calibration', 'category', 'mix'))
    names = {
        'basic_choice': '年龄学历 → 选一个答案',
        'rich_choice': '补充背景 → 选一个答案',
        'basic_probability': '年龄学历 → 保留各项概率',
        'rich_probability': '补充背景 → 保留各项概率',
        'attitude_probability': '再加实测态度 → 保留各项概率',
        'rich_probability_argmax': '已有概率 → 只取最高的一项',
        'calibrated_rating': '用开发样本修正单选评分',
        'statistics': '历史真人统计方法',
        'blend': '历史统计与模型组合',
    }
    data['names'] = names
    contexts = [
        ('购物问卷', pew['summaries'], pew['contrasts'], 'tv_95_interval'),
        ('运动鞋', shoes['summary'], shoes['contrasts'], 'tv_interval'),
    ]
    changes = []
    for label, summaries, comparisons, ci_key in contexts:
        for row in comparisons:
            if (row['from'], row['to']) not in {
                ('rich_choice', 'rich_probability'), ('basic_choice', 'rich_choice'),
                ('basic_probability', 'rich_probability'), ('rich_probability', 'attitude_probability'),
            }:
                continue
            low, high = row[ci_key]
            gain = row['tv_improvement_pp']
            verdict = ('达到采用门槛' if low > 0 and gain >= 2 else
                       '差距明确变大' if high < 0 else
                       '有改善，但不足 2 点' if low > 0 else '改善尚不明确')
            changes.append([label, escape(names[row['from']] + '；改为 ' + names[row['to']]),
                            f"{summaries[row['from']]['tv_pp']:.2f} → {summaries[row['to']]['tv_pp']:.2f}",
                            f'{gain:+.2f}', interval(row[ci_key]), verdict])
    settings = []
    for key in ('basic_choice', 'rich_choice', 'basic_probability', 'rich_probability',
                'attitude_probability', 'rich_probability_argmax', 'calibrated_rating', 'blend', 'statistics'):
        a = pew['summaries'].get(key)
        b = shoes['summary'].get(key)
        settings.append([escape(names[key]), f"{a['tv_pp']:.2f}" if a else '本任务未设置',
                         f"{b['tv_pp']:.2f}" if b else '本任务未设置'])
    amazon_rows = []
    for key, label in [('category', '下季度会买哪些品类'), ('price', '买什么价位'),
                       ('spend', '钱花在哪些品类'), ('repeat', '会不会复购同款')]:
        if key == 'category':
            scores = cat['summary']; base = scores['recent']['brier']; model = scores['history_only']['brier']
            combo = scores['blend']['brier']; c = cat['contrasts']['recent → blend']
            gain, ci = c['brier_improvement'], c['interval']
        else:
            task = mix['tasks'][key]; scores = task['results']; base = scores['recent']['brier']
            model = scores['model']['brier']; combo = scores['blend']['brier']
            gain, ci = task['comparisons']['blend']['gain'], task['comparisons']['blend']['interval']
        amazon_rows.append([label, f'{base:.5f}', f'{model:.5f}', f'{combo:.5f}',
                            f'{gain:+.6f}', interval(ci, 6)])
    data['sources'] = {key: {'path': name, 'sha256': hashlib.sha256((BASE / name).read_bytes()).hexdigest()}
                       for key, name in {**FILES, **extra_files}.items()}
    token = {
        'PAYLOAD': json.dumps(data, ensure_ascii=False).replace('<', '\\u003c'),
        'PEW_BEFORE': f"{pew['summaries']['rich_choice']['tv_pp']:.2f}",
        'PEW_AFTER': f"{pew['summaries']['rich_probability']['tv_pp']:.2f}",
        'PEW_STAT': f"{pew['summaries']['statistics']['tv_pp']:.2f}",
        'SHOE_BEFORE': f"{shoes['summary']['rich_choice']['tv_pp']:.2f}",
        'SHOE_AFTER': f"{shoes['summary']['rich_probability']['tv_pp']:.2f}",
        'SHOE_STAT': f"{shoes['summary']['statistics']['tv_pp']:.2f}",
        'CHANGE_TABLE': table(['任务', '只改什么', '改前 → 改后', '差距减少', '95% 区间', '判断'], changes,
                              '同一批人配对比较；分布差距和改善幅度均为百分点'),
        'SETTING_TABLE': table(['方法', '购物问卷差距', '运动鞋差距'], settings,
                               '各设置的正式评估结果。数字越低越接近真人；两列的汇总方式不同，不合成总分'),
        'AMAZON_TABLE': table(['要预测什么', '近期历史', '直接用模型', '统计与模型组合', '组合比历史减少的误差', '95% 区间'], amazon_rows,
                              '逐账户平方误差原值，只在同一行比较；正的改善表示组合更好'),
    }
    page = (ROOT / 'retail_reader_template.html').read_text()
    page = page.replace('{{HISTORY}}', (ROOT / 'retail_history_template.html').read_text())
    page = page.replace('{{HISTORY_SCRIPT}}', (ROOT / 'retail_history_charts.js').read_text())
    for key, value in token.items():
        page = page.replace('{{' + key + '}}', value)
    assert '{{' not in page, 'Unexpanded report template field'
    (BASE / 'index.html').write_text(page)
    # Keep the currently opened legacy URL working, and make the study root the
    # canonical entry. Rebase only HTML link/source attributes, never payload data.
    def root_link(match):
        attr, value = match.groups()
        if value.startswith(('#', '/', 'https:', 'http:', 'data:', 'mailto:')):
            return match.group(0)
        return f'{attr}="{posixpath.normpath(posixpath.join("08_购物预测", value))}"'
    root_page = re.sub(r'(href|src)="([^"]+)"', root_link, page)
    (BASE.parent / 'index.html').write_text(root_page)
    manifest = {
        'report': 'index.html', 'canonical_report': '../index.html',
        'scope': '五轮正式实验统一汇报；新增运动鞋输入对齐的事后统计对照，未新增 LLM 请求或重选样本',
        'sources': data['sources'],
        'report_sha256': hashlib.sha256(page.encode()).hexdigest(),
        'canonical_report_sha256': hashlib.sha256(root_page.encode()).hexdigest(),
    }
    (BASE / '报告展示核验.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print('Built reader report from verified aggregate results.')


if __name__ == '__main__':
    build()
