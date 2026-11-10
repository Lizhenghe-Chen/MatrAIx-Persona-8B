"""Offline aggregate-only report; never infer research success from available files."""
from html import escape
import math


def percentage(value):
    if not math.isfinite(value) or not 0<=value<=1:raise ValueError('Invalid share')
    return f'{100*value:.1f}%'


def render(doc):
    if doc.get('status') not in ('development','formal'):
        raise ValueError('Report must explicitly identify development or formal results')
    if not doc.get('provenance') or not doc.get('limitations'):
        raise ValueError('Provenance and limitations required')
    title=escape(doc['title']);parts=[]
    parts.append('<h1>'+title+'</h1>')
    parts.append('<p class="notice">'+('开发结果：用于选择方法，不能作为独立成功证据。' if doc['status']=='development' else '正式评估：以下结论仅适用于列明的冻结方案和数据。')+'</p>')
    parts.append('<h2>目前能得出什么结论</h2><p>'+escape(doc['conclusion'])+'</p>')
    parts.append('<h2>用了什么数据、怎样比较</h2><p>'+escape(doc['method'])+'</p>')
    parts.append('<p>概率误差（Brier）越低越好：模型给真实选项的概率越高，通常误差越小。分布误差按百分点计，衡量整个人群各选项比例相差多少；两者不能互相替代。</p>')
    for study in doc['studies']:
        parts.append('<section><h2>'+escape(study['name'])+'</h2>')
        parts.append('<p>'+escape(study['sample_note'])+'</p>')
        parts.append('<table><thead><tr><th>方案</th><th>概率误差</th><th>分布误差（百分点）</th><th>逐人正确率</th></tr></thead><tbody>')
        for arm in study['arms']:
            s=arm['scores']
            parts.append(f"<tr><td>{escape(arm['label'])}</td><td>{s['brier']:.4f}</td><td>{s['mean_tv_pp']:.2f}</td><td>{percentage(s['accuracy'])}</td></tr>")
        parts.append('</tbody></table>')
        parts.append('<h3>逐题查看：真人与每种方案差在哪里</h3>')
        names=set(study['arms'][0]['scores']['groups'])
        if any(set(a['scores']['groups'])!=names for a in study['arms']):raise ValueError('Arms use different question groups')
        for name in sorted(names):
            ref=study['arms'][0]['scores']['groups'][name]
            parts.append('<details><summary>'+escape(name)+'</summary>')
            for i,option in enumerate(ref['options']):
                parts.append('<h4>'+escape(option)+'</h4>')
                series=[('真人',ref['human'][i],'human')]
                for arm in study['arms']:
                    g=arm['scores']['groups'][name]
                    if g['options']!=ref['options'] or g['human']!=ref['human']:raise ValueError('Unmatched human reference or options')
                    series.append((arm['label'],g['model'][i],'model'))
                for label,value,cls in series:
                    pct=percentage(value)
                    parts.append(f'<div class="row"><span>{escape(label)}</span><div class="track"><div class="{cls}" style="width:{pct}"></div></div><strong>{pct}</strong></div>')
            parts.append('</details>')
        parts.append('</section>')
    parts.append('<h2>适用边界与尚未解决的问题</h2><ul>'+''.join('<li>'+escape(x)+'</li>' for x in doc['limitations'])+'</ul>')
    parts.append('<h2>数据与复算依据</h2><ul>'+''.join('<li>'+escape(x)+'</li>' for x in doc['provenance'])+'</ul>')
    parts.append('<h2>结论回顾</h2><p>'+escape(doc['conclusion'])+'</p>')
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'''+title+'''</title><style>
body{max-width:1100px;margin:32px auto;padding:0 20px;font:17px/1.7 system-ui;color:#203933;background:#faf9f5}h1{font-size:30px}section,details{border:1px solid #cad7d0;padding:16px;margin:18px 0;border-radius:10px}.notice{background:#fff0c8;padding:15px}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #ccd7d0;text-align:left}.row{display:flex;gap:12px;align-items:center;margin:8px 0}.row span{width:220px}.row strong{width:65px}.track{flex:1;background:#e3e9e5;height:16px}.human,.model{height:100%;background:#21715c}.model{background:#6951a2}summary{cursor:pointer;font-weight:bold}@media(max-width:650px){body{font-size:15px}.row span{width:110px}table{font-size:12px}td,th{padding:5px}}
</style><main>'''+''.join(parts)+'</main></html>'
