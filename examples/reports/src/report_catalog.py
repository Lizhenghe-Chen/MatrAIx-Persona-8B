"""Shared document list and HTML entry links for the report center and final report."""
from html import escape, unescape
import json
import os
from pathlib import Path
import re
from urllib.parse import quote

EXAMPLES = Path(__file__).resolve().parents[2]
CENTER = EXAMPLES / 'reports'
HTML = {'.html', '.htm'}
FEATURED_REPORTS = (
    ('bottleneck.html', '改法与剩余差距',
     '看新一轮真人对照提升了多少。对同一批 AI 回答换一种汇总方式，看看结果为什么会变。'),
    ('question-cases.html', '真人原题与答案分布',
     '按研究展开购物、涨价、诈骗风险、公共支出和选品题，查看真人和各方案怎么答。'),
    ('purchase-evidence.html', '本人记录与购买预测',
     '用真人问卷、收银记录和有日期的订单，检验本人以往的选择能否帮助预测买不买、买哪款。'),
    ('project-evidence.html', '项目证据与边界',
     '核对项目论文、数据来源和代码，了解哪些能力有实测，哪些还缺真人证据。'),
)
GROUPS = (
    '综合与正式研究', '阶段报告及实验过程', '模拟示范', '方法、证据与目录',
    '文献与问卷原件', '模板、任务与运行说明',
)
LITERATURE = EXAMPLES / 'sim-to-real/study/11_文献综述'
ONLINE_FULL_TEXT = {
    'R17': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC13214042/',
    'R19': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC12184514/',
}
LOCAL_APPENDIX = 'sim-to-real/study/06_北美电商选品/数据/origin-appendix.docx'
TITLES = {
    'sim-to-real/reports/index.html': '历轮问卷对照｜数据详版',
    'sim-to-real/reports/story.html': '历轮问卷对照｜故事版',
    'sim-to-real/reports/cards.html': '历轮问卷对照｜逐题分布版',
    'sim-to-real/decision_lab/reports/cross-study-v1/index.html': '十九套候选｜准入和画像覆盖审查',
    'sim-to-real/decision_lab/reports/cross-study-v1/formal-report.html': '首批六套问卷｜四组正式对照',
    'sim-to-real/decision_lab/reports/cross-study-v1/wide-v1-report.html': '扩展六套问卷｜跨研究复验',
    'sim-to-real/decision_lab/reports/cross-study-v1/clean-v1-report.html': '配送和运动鞋｜补充复验',
    'sim-to-real/decision_lab/reports/population-dryer.html': '四国烘干机｜合成人群对照',
    'sim-to-real/decision_lab/reports/population-swiss.html': '瑞士家电｜合成人群对照',
    'sim-to-real/study/index.html': '早期真人对照｜故事版',
    'sim-to-real/study/evidence.html': '早期真人对照｜逐轮证据',
    'sim-to-real/study/08_购物预测/index.html': '购物预测阶段｜故事版',
    'sim-to-real/study/08_购物预测/evidence.html': '购物预测阶段｜逐轮证据',
    'sim-to-real/study/11_文献综述/index.html': '文献综述｜新版入口说明',
}


def classify(path):
    rel = path.relative_to(EXAMPLES).as_posix()
    name = path.name
    suffix = path.suffix.lower()
    if name == 'optimize_report.html' and '/legacy/' in rel:
        return GROUPS[1], '早期优化报告副本，原页部分链接沿用旧位置'
    if rel.startswith('tasks/') or '/legacy/' in rel or '模板' in name:
        return GROUPS[5], '运行说明、展示模板或验证工具'
    if '全文资料/' in rel or suffix == '.pdf' or 'shed-questionnaire' in name:
        return GROUPS[4], '一手文献、原问卷、代码本或复算附件'
    if rel.startswith('虚拟消费者模拟研究报告/'):
        if '04-MatrAIx批判性评估/' in rel:
            return GROUPS[0], '独立的项目证据评价'
        if '03-数据源分析/' in rel or name == 'README.md':
            return GROUPS[3], '数据构成说明或目录'
        return GROUPS[2], '模拟选购或看板，缺少同题真人对照'
    if rel.endswith(('cross-study-v1/index.html', '11_文献综述/index.html')):
        return GROUPS[3], '研究准入、来源或索引'
    if '/archive/' in rel or name == 'historical-details.html':
        return GROUPS[1], '归档分析、历史报告或交接'
    if suffix in HTML | {'.docx'} and '/reports/' in rel:
        return GROUPS[0], '综合、正式报告或相应逐题版'
    if suffix in HTML | {'.docx'} or name in ('report.md', '优化实验综合报告.md'):
        return GROUPS[1], '阶段报告、候选数据或历史对照'
    return GROUPS[3], '方法、审查、来源或索引'


def document_title(path):
    suffix = path.suffix.lower()
    if suffix not in HTML | {'.md'}:
        return path.stem
    with path.open(encoding='utf-8') as file:
        prefix = file.read(24000)
    if suffix in HTML:
        match = re.search(r'<title[^>]*>(.*?)</title>', prefix, re.I | re.S)
    else:
        match = re.search(r'^# (.+)$', prefix, re.M)
    return unescape(' '.join(match[1].split())) if match else path.stem


def inventory():
    entries = []
    for path in EXAMPLES.rglob('*'):
        suffix = path.suffix.lower()
        rel = path.relative_to(EXAMPLES)
        if (CENTER in path.parents or suffix not in HTML | {'.md', '.docx', '.pdf'}
                or not path.is_file() or rel.as_posix() == LOCAL_APPENDIX
                or '本机全文' in rel.parts or any(part.startswith('.') for part in rel.parts)):
            continue
        key = rel.as_posix()
        category, purpose = classify(path)
        entries.append({'title': TITLES[key] if key in TITLES else document_title(path),
                        'path': key, 'type': 'HTML' if suffix in HTML else suffix[1:].upper(),
                        'category': category, 'purpose': purpose})

    for record in json.loads((LITERATURE / 'sources.json').read_text()):
        if record['id'] not in ONLINE_FULL_TEXT:
            continue
        entry_path = next(name for name in record['full_text']['files'] if Path(name).suffix in HTML)
        entries.append({'title': record['title_zh'], 'type': 'HTML', 'category': GROUPS[4],
                        'path': (LITERATURE / entry_path).relative_to(EXAMPLES).as_posix(),
                        'purpose': '外部论文正文，需联网', 'url': ONLINE_FULL_TEXT[record['id']]})
    return sorted(entries, key=lambda entry: entry['path'])


def document_url(entry, directory):
    if 'url' in entry:
        return entry['url']
    return quote(os.path.relpath(EXAMPLES / entry['path'], directory), safe='/')


def report_button(label, url, *, primary=False, mark='HTML'):
    kind = 'report-link report-link--primary' if primary else 'report-link'
    return (f'<a class="{kind}" href="{escape(url, quote=True)}"><span>{escape(label)}</span>'
            f'<span class="report-link-type" aria-hidden="true">{escape(mark)}</span></a>')
