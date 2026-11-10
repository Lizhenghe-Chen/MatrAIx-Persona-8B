"""Build the Chinese reading index from frozen file metadata."""
import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).parent


def build_index(records):
    files = json.loads((ROOT / '全文资料/文件索引.json').read_text())['files']
    counts = Counter(f['storage'] for f in files)
    total = sum(f['bytes'] for f in files) / 1048576
    available = sum(r['full_text']['status'] == '正文已下载' for r in records)
    lines = [
        '# 本地全文资料库：从这里找论文', '',
        '[返回综述](../综述.md) · [文献证据卡](../文献证据卡.md)', '',
        f'核对日期：2026-11-10。23项研究中，**{available}项已取得正文，2项待获取**。',
        f'共保存{len(files)}个文件，占用 **{total:.2f} MiB**（约{total * 1.048576:.1f} MB）。', '',
        '**如何使用：** 先按下面的中文主题找研究，点击“本地正文”打开文件；',
        '需要了解研究是否可信，再打开对应的证据卡。论文保持原文，中文名称是阅读导引，不是官方译名。', '',
        '**两个状态要分开：** “正文已下载”说明拿到了文件；“阅读核验”说明我们实际核查到了哪里。',
        '只检查文件能否解析，不等于已核对所有实验、图表和附录，也不等于独立复现。', '',
        'PDF可离线阅读。两份PMC正文网页保存了完整HTML，但图片和网站样式可能仍需联网。',
        '本轮没有把摘要、登录页、浏览器验证页当成全文保存。', '',
        '## 尚需人工获取的两项', '',
    ]
    for r in records:
        if r['full_text']['status'] != '正文已下载':
            lines += [f"- **[{r['title_zh']}]({r['url']})**：{r['full_text']['action']}"]
    lines += ['', '下载后提供文件路径即可继续入库。不要因为403或验证页就直接购买；先用自己的浏览器检查访问情况。', '',
              '## 按研究问题查找', '']
    for group in dict.fromkeys(r['full_text']['topic'] for r in records):
        lines += [f'### {group}', '', '| 研究 | 本地正文 | 状态与阅读范围 |', '| --- | --- | --- |']
        for r in records:
            if r['full_text']['topic'] != group:
                continue
            mains = [f for f in files if f['source_id'] == r['id'] and '正文' in f['role']]
            links = ' · '.join(f"[{f['role']}]({quote(f['path'].removeprefix('全文资料/'))})" for f in mains)
            lines.append(f"| [{r['title_zh']}](#{r['id']}) | {links or '待获取'} | {r['full_text']['status']}；{r['checked']} |")
        lines.append('')
    lines += ['## 文件为什么有的随Git，有的只留本机', '',
              f"- **{counts['git']}份正文PDF随Git**：已确认CC BY或CC BY-SA许可，保留原文件和署名，来源与许可逐项列在下方。",
              f"- **{counts['local_only']}份文件仅本机保存**：非商业限制、再分发许可待确认，或原始网页包含未独立核准的网站周边素材。",
              '- 本机文件也在此项目文件夹内，由 `.gitignore` 排除；其他电脑仅克隆仓库不会得到这些全文。',
              '- 论文和附件是第三方作品，不适用本项目的代码许可证。授权例外、第三方图像和原文声明仍以作者及出版方为准。',
              '- 文件按原始字节归档，未翻译、删页或改写。哈希用于确认文件内容是否变化，不用于证明结论正确。', '',
              '## 每项文献的版本、来源和附件', '']
    for r in records:
        lines += [f"<a id=\"{r['id']}\"></a>", '', f"### {r['title_zh']}", '',
                  f"英文原题：**{r['title']}**", '',
                  f"[原始文献入口]({r['url']}) · [阅读证据卡](../文献证据卡.md#{r['id']})", '',
                  f"证据卡引用版本：{r['version']}。阅读核验：{r['checked']}。", '',
                  f"获取说明：{r['full_text']['note']}", '']
        own = [f for f in files if f['source_id'] == r['id']]
        if not own:
            lines += ['尚无本地全文文件。', '']
        for f in own:
            path = quote(f['path'].removeprefix('全文资料/'))
            storage = '随Git保存' if f['storage'] == 'git' else '仅本机保存'
            pages = f"，{f['pages']}页" if f['pages'] else ''
            lines += [f"- **[{f['role']}]({path})**：{f['version']}{pages}；{f['bytes'] / 1048576:.2f} MiB；{storage}。",
                      f"  - [下载来源]({f['download_url']})；[许可依据]({f['license_evidence_url']})；许可：{f['license']}。"]
            if f['license_url']:
                lines += [f"  - [查看许可条款]({f['license_url']})。"]
            lines += [f"  - 文件检查：{f['validation']}。"]
            if f['note']:
                lines += [f"  - 注意：{f['note']}"]
        lines.append('')
    lines += ['## 维护与完整性检查', '',
              '在上一级综述目录运行：', '', '```sh', 'python manage_fulltexts.py verify',
              'python manage_fulltexts.py download', 'python build.py', '```', '',
              '第一条核对SHA-256和大小；第二条只补下载缺失文件，内容变化或访问验证会报错，不覆盖固定版本；',
              '第三条重建本索引和证据卡，不覆盖综述正文。完整机器记录见[文件索引.json](文件索引.json)。', '',
              '新版本须作为独立文件核验；先更新文件索引与获取记录，研究结论经过内容复核后再改。', '']
    (ROOT / '全文资料/全文索引.md').write_text('\n'.join(lines))
