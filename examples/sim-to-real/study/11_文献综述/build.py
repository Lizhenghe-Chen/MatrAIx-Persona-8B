"""Generate the evidence-card index and legacy navigation; never overwrite prose."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).parent

def build():
    records = json.loads((ROOT / 'sources.json').read_text())
    assert len({r['id'] for r in records}) == len(records)
    lines = ['# 文献证据卡', '', '更新：2026-11-10。由 `sources.json` 生成；请修改数据源后运行 `python build.py`。', '',
             '[返回综述](综述.md) · [参数与实验建议](参数与实验建议.md)', '',
             '编号仅用于长期维护。每篇都用标题、任务和核验范围解释；摘要级证据不等于全文确认，也不等于已复现。', '',
             '| 文献 | 任务 | 核验范围 |', '| --- | --- | --- |']
    for r in records:
        lines.append(f"| [{r['title']}](#{r['id']}) | {r['factor']} | {r['checked']} |")
    for r in records:
        lines += ['', f'<a id="{r["id"]}"></a>', '', f"## {r['id']} · {r['factor']}", '',
                  f"[{r['title']}]({r['url']})", '', f"版本：{r['version']}。核验日期：{r['checked_on']}。", '',
                  f"**本项目相关性：** {r.get('project_relevance', '待分类')}", '',
                  f"**对象与对照：** {r['human_comparator']}", '', f"**已提取的发现：** {r['finding']}", '',
                  f"**定位与阅读范围：** {r['locator']}", '', f"**限制：** {r['limitations']}", '']
        if r.get('parameters'):
            lines += ['**提取到的配置：**', '']
            lines += [f'- `{k}`：{v}' for k, v in r['parameters'].items()]
            lines += ['', '这些是论文设置或比较条件，不自动等于最优参数。']
        else:
            lines += ['**配置提取：** 尚未完整提取；不能补猜温度、模型版本或训练参数。']
        for old in r.get('version_history',[]):
            lines += ['', f"**版本变更：** {old['version']} — {old['note']}"]
    (ROOT/'文献证据卡.md').write_text('\n'.join(lines)+'\n')
    links=[('综述.md','阅读完整主文：对应用户的决策与选择'),('文献证据卡.md',f'查看{len(records)}项文献证据卡'),('参数与实验建议.md','查看详细参数附录'),('检索与更新记录.md','查看检索和更新记录')]
    nav=''.join(f'<li><a href="{html.escape(p)}">{html.escape(t)}</a></li>' for p,t in links)
    (ROOT/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>文献综述已迁移到Markdown</title><style>body{max-width:760px;margin:60px auto;padding:0 22px;font:20px/1.8 system-ui;color:#213b36;background:#f6f4ed}a{color:#225f91}li{margin:16px 0}</style><h1>综述现在使用Markdown维护</h1><p>本页保留旧入口。正文、证据与参数说明均已迁到项目内的Markdown文件，方便审阅版本变化。</p><ul>'+nav+'</ul><p>若浏览器将文件下载，请在编辑器或Codex中打开同名 .md 文件。</p><p><a href="../index.html">返回已完成实验报告</a></p></html>\n')
    print(f'Generated {len(records)} evidence cards and legacy navigation; prose preserved.')

if __name__=='__main__':
    build()
