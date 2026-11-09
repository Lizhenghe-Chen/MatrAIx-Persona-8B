"""Render an offline, aggregate-only shopping report."""

import json


LABELS = {
    "P0+B1": "角色扮演＋年龄学历",
    "P0+B3": "角色扮演＋贴题背景",
    "P1+B1": "预测受访者＋年龄学历",
    "P1+B3": "预测受访者＋贴题背景",
    "统计基线": "用其他真人回答做统计对照",
}


def render(results, cross, names, outcome_labels, escape):
    head = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MatrAIx 北美电商选品对照实验</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f4eb;color:#19352d;font:16px/1.65 system-ui,sans-serif}
header{background:#19352d;color:#fff;padding:38px 0}main{padding:22px 0 50px}
.wrap{width:min(1000px,calc(100% - 32px));margin:auto}h1,h2,h3{line-height:1.25}
h1{font-size:clamp(28px,5vw,44px)}h2{margin-top:32px}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:.55rem;text-align:right;border-bottom:1px solid #d1ded4;white-space:nowrap}
th:first-child,td:first-child{text-align:left}.scroll{overflow:auto;margin:12px 0}
a{color:#216b57}.panel{background:#fffefa;padding:16px;border:1px solid #d1ded4;border-radius:12px}
select{max-width:100%;font:inherit;margin:3px;padding:5px}.bar{height:12px;border-radius:6px;background:#dce7df}
.bar b{display:block;height:100%;background:#216b57;border-radius:6px}.bar.pred b{background:#674ba1}
.legend{display:flex;gap:12px;align-items:center}.legend span{width:90px;font-size:.85rem}
.legend .bar{flex:1}footer{margin-top:30px}
</style>
<header><div class="wrap"><div>北美消费者 · 真人逐人对照</div><h1>MatrAIx 北美电商选品对照实验</h1>
<p>同一批受访者、同一商品或问题，比较原提示、预测提示与真实背景的影响。</p></div></header>
<main class="wrap">"""
    content = [head, "<h2>主要结果</h2>",
               f"<p>主比较在三项任务中{'达到' if cross else '未达到'}预设的跨任务复现门槛。</p>",
               "<p>「角色扮演」请模型扮演受访者。「预测受访者」请模型预测这个人会怎么答。"
               "「年龄学历」只有这两项背景。「贴题背景」再给与题目相关的真人资料，如收入和上网频率。</p>",
               '<div class="scroll"><table><thead><tr><th>任务</th><th>角色扮演＋年龄学历</th>'
               '<th>预测受访者＋贴题背景</th><th>改善及 95% 区间</th><th>真人统计对照</th></tr></thead><tbody>']
    for survey, result in results.items():
        cells = result["cells"]
        gain = result["comparisons"][0]
        lo, hi = gain["ci95"]
        content.append(f"<tr><td>{names[survey]}</td><td>{cells['P0+B1']['tv_pp']:.2f}</td>"
                       f"<td>{cells['P1+B3']['tv_pp']:.2f}</td>"
                       f"<td>{gain['gain_pp']:+.2f} [{lo:+.2f}, {hi:+.2f}]</td>"
                       f"<td>{cells['统计基线']['tv_pp']:.2f}</td></tr>")
    origin = results["origin"]["cells"]["P1+B3"]["metrics"]
    packaging = results["packaging"]["opt_out_pct"]
    pew = results["pew"]["cells"]["P1+B3"]["metrics"]["ONLSHOP4"]
    content += ["</tbody></table></div><p>误差单位为百分点，越低越接近真人。改善为正时，候选设置的误差较低。</p>",
                "<ul>"
                f"<li><b>产地与选品</b>。当两款中只有一款中国产，真人有 {origin['China']['human_pct'][0]:.1f}% 选它，优化组为 {origin['China']['predicted_pct'][0]:.1f}%。"
                f"优化组也更倾向于高分款，选择率为 {origin['higher-rated']['predicted_pct'][0]:.1f}%，真人为 {origin['higher-rated']['human_pct'][0]:.1f}%。</li>"
                f"<li><b>拒买</b>。真人有 {packaging['human']:.1f}% 选择都不买，优化组为 {packaging['P1+B3']:.1f}%。"
                f"统计基线的预测比例为 {packaging['统计基线']:.1f}%。</li>"
                f"<li><b>网购习惯</b>。问到是否曾看达人内容后购买，{pew['human_pct'][0]:.1f}% 的真人选是，优化组为 {pew['predicted_pct'][0]:.1f}%。</li></ul>",
                "<h2>逐题查看真人与模拟比例</h2>", '<div class="panel"><label>实验 <select id="survey"></select></label>'
                '<label>设置 <select id="cell"></select></label><label>题组 <select id="metric"></select></label>'
                '<div id="chart" aria-live="polite"></div></div>']
    for survey, result in results.items():
        content.append(f"<h2>{names[survey]}的对照</h2><p>共同完成的受访者 {result['matched']} 人，"
                       f"统计基线训练样本 {result['training']} 人。</p>")
        if survey == "packaging":
            rates = result["opt_out_pct"]
            content.append(f"<p>同一批选择卡里，真人的拒买率为 <b>{rates['human']:.1f}%</b>，"
                           f"原提示为 {rates['P0+B1']:.1f}%，预测提示加贴题背景为 {rates['P1+B3']:.1f}%。</p>")
        content.append('<div class="scroll"><table><thead><tr><th>设置</th><th>分布误差</th><th>逐人正确率</th>'
                       '<th>单项达 95% / 99% / 100% 的题数</th>' + ('<th>拒买召回率</th>' if survey == "packaging" else '')
                       + '</tr></thead><tbody>')
        for cell, row in result["cells"].items():
            counts = row["concentration"]
            density = "—" if counts is None else " / ".join(str(counts[str(n)]) for n in (95, 99, 100))
            recall = (f"<td>{row['individual_pct']['recall/All/0']:.1f}%</td>" if survey == "packaging" else "")
            content.append(f"<tr><td>{escape(LABELS[cell])}</td><td>{row['tv_pp']:.2f}</td>"
                           f"<td>{row['individual_pct']['person_mean']:.1f}%</td><td>{density}</td>{recall}</tr>")
        content.append('</tbody></table></div><div class="scroll"><table><thead><tr><th>配对比较</th>'
                       '<th>改善</th><th>95% 区间</th><th>达到门槛</th></tr></thead><tbody>')
        for row in result["comparisons"]:
            lo, hi = row["ci95"]
            content.append(f"<tr><td>{escape(LABELS[row['reference']])} → {escape(LABELS[row['candidate']])}</td>"
                           f"<td>{row['gain_pp']:+.2f}</td><td>[{lo:+.2f}, {hi:+.2f}]</td>"
                           f"<td>{'是' if row['passes'] else '否'}</td></tr>")
        content.append("</tbody></table></div>")
    content.append("""<h2>数据和计算口径</h2>
<p>产地实验对四个可辨别的属性分别比较选择份额，然后等权汇总。包装实验对每张固定选择卡算完整分布误差，Pew 按原跳题和权重逐题比较。两份产品实验按公开研究样本的年龄学历构成还原配额抽样比例。95% 区间来自 2,000 次分层受访者配对重抽样。</p>
<p>统计基线使用正式和试跑样本以外的真人记录。两份产品实验用商品属性和背景拟合条件选择模型，Pew 使用同层历史比例。分布分数使用基线的预测概率，逐人正确率使用最大概率选项。逐人正确率先算每个人的答对比例，再按分析权重汇总。</p>
<p>原实验是问卷选择与自报购物。制造产地、历史网购行为与平台真实下单各有独立的定义。Purdue 按公开问卷说明和选项字段用英文文字还原展示。</p>
<ul><li><a href="https://itemresponsewarehouse.org/tables/bankert_2023_consumer_origin/">Bankert 逐人数据与实验设计</a></li>
<li><a href="https://itemresponsewarehouse.org/tables/staples_2020_beer_eco_labels/">Purdue 逐人数据与实验设计</a></li>
<li><a href="https://www.pewresearch.org/wp-content/uploads/2022/11/online-shopping-methodology-topline.pdf">Pew 原题及方法</a></li>
<li><a href="results.json">逐题数据、各选项召回率及各品类正确率</a></li></ul></main>""")
    payload = json.dumps({"results": results, "names": names, "labels": outcome_labels, "settings": LABELS}, ensure_ascii=False).replace("<", "\\u003c")
    content.append(f'<script type="application/json" id="data">{payload}</script>')
    content.append("""<script>
const {results,names,labels,settings}=JSON.parse(document.getElementById('data').textContent);
const s=document.getElementById('survey'),c=document.getElementById('cell'),m=document.getElementById('metric');
const choose=(el, keys, label=k=>k)=>el.replaceChildren(...keys.map(k=>new Option(label(k),k)));
const pew={ONLSHOP1_a:'电脑网购',ONLSHOP1_b:'平板网购',ONLSHOP1_c:'手机网购',SHOP4:'线上还是到店',ONLSHOP3:'关注达人',ONLSHOP4:'看达人内容后购买'};
function update(){
 const row=results[s.value].cells[c.value].metrics[m.value], chart=document.getElementById('chart');
 chart.replaceChildren();
 const opts=s.value==='origin'?['选中该属性的商品','选另一款']:s.value==='packaging'?['A','B','都不买']:
 m.value==='SHOP4'?['线上','实体店']:['是','否','不确定'];
 const heading=document.createElement('p');heading.textContent='分布误差 '+row.tv_pp.toFixed(2)+' 个百分点 · '+row.tasks+' 道已评分选择';chart.append(heading);
 for(let i=0;i<row.human_pct.length;i++){
   const h=document.createElement('h3');h.textContent=opts[i];chart.append(h);
   const card=results[s.value].cards[m.value]?.[i];
   if(card){
     const p=document.createElement('p');
     const keys={packaging:'包装',price:'价格',water_conserving:'节水',energy_conserving:'节能',waste_reduction:'减废',local:'本地生产'};
     const vals={Yes:'是',No:'否',Can:'罐装',Bottle:'瓶装'};
     p.textContent=Object.entries(card).map(([k,v])=>(keys[k]||k)+' '+(vals[v]||v)).join(' · ');
     chart.append(p);
   }
   const key=s.value==='pew'?'recall/'+m.value+'/'+(i+1):
     s.value==='packaging'&&i===2?'recall/All/0':null;
   const recall=results[s.value].cells[c.value].individual_pct[key];
   if(recall!==undefined){
     const p=document.createElement('p');p.textContent=(s.value==='packaging'?'全部卡片的拒买召回率 ':'该选项召回率 ')+recall.toFixed(1)+'%';
     chart.append(p);
   }
   for(const [j,v] of [row.human_pct[i],row.predicted_pct[i]].entries()){
     const line=document.createElement('div');line.className='legend';
     const label=document.createElement('span');label.textContent=(j?'该设置 ':'真人 ')+v.toFixed(1)+'%';
     const bar=document.createElement('div');bar.className=j?'bar pred':'bar';
     const fill=document.createElement('b');fill.style.width=v+'%';bar.append(fill);line.append(label,bar);chart.append(line);
   }
 }
}
function metric(){choose(m,Object.keys(results[s.value].cells[c.value].metrics),k=>labels[k]||pew[k]||('选择卡 '+k));update();}
function cells(){choose(c,Object.keys(results[s.value].cells),k=>settings[k]);c.value='P1+B3';metric();}
choose(s,Object.keys(results),k=>names[k]);s.onchange=cells;c.onchange=metric;m.onchange=update;cells();
</script></html>""")
    return "\n".join(content)
