"""Offline paginated choice-card charts, without respondent identifiers."""
import json,html


def render(methods,labels,limit=None):
    """Interactive viewer. limit keeps the largest groups so the page stays openable."""
    safe={};truncated={}
    for name,cards in methods.items():
        if limit is None or len(cards)<=limit:
            chosen=cards;truncated[name]=0
        else:
            ranked=sorted(range(len(cards)),key=lambda i:(-(cards[i].get('people') or cards[i].get('human_people') or 0),i))
            chosen=[cards[i] for i in ranked[:limit]];truncated[name]=len(cards)-limit
        safe[name]=[{'options':c['options'],'human':c['human'],'model':c['model'],
                     'tv_pp':c['tv_pp'],'people':c.get('people',c.get('human_people')),
                     'small':c.get('small_group',c.get('small_human_group',False))} for c in chosen]
    payload=json.dumps(safe,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    options=''.join(f'<option value="{html.escape(k,quote=True)}">{html.escape(labels[k])}</option>' for k in safe)
    dropped=sum(truncated.values())
    note=('' if not dropped else
          f'<p>逐题图只展示每组真人样本量最大的 {limit} 个商品组合（共省略 {dropped} 个较小的组合）。'
          '完整分组数字保存在分析 JSON 中，未在此页省略。</p>')
    return note+'''<div id="choice-card-view"><label>选择预测设置 <select aria-label="预测设置">'''+options+'''</select></label>
<div><button type="button" data-step="-1">上一页</button> <span role="status"></span> <button type="button" data-step="1">下一页</button></div><div class="card-list"></div>
<noscript>逐题图表需要本地浏览器启用 JavaScript，不联网；完整数字同时保存在分析 JSON 中。</noscript></div>
<script type="application/json" id="choice-card-data">'''+payload+'''</script>
<script>
(()=>{
const root=document.getElementById('choice-card-view'), data=JSON.parse(document.getElementById('choice-card-data').textContent);
const selector=root.querySelector('select'), list=root.querySelector('.card-list'), status=root.querySelector('[role=status]');
let page=0;const size=12;
function el(tag,text,parent){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(parent)parent.appendChild(node);return node;}
function show(){
 const cards=data[selector.value]||[],pages=Math.max(1,Math.ceil(cards.length/size));page=Math.max(0,Math.min(page,pages-1));list.replaceChildren();
 status.textContent=` 第 ${page+1} / ${pages} 页，共 ${cards.length} 个商品组合 `;
 root.querySelector('[data-step="-1"]').disabled=page===0;root.querySelector('[data-step="1"]').disabled=page===pages-1;
 cards.slice(page*size,(page+1)*size).forEach((card,i)=>{
  const panel=el('details',undefined,list);panel.open=true;
  el('summary',`商品组合 ${page*size+i+1} · 真人 ${card.people} 人 · 误差 ${card.tv_pp.toFixed(2)} 个百分点`,panel);
  if(card.small)el('p','这个组合的真人样本少于 20 人，仅作描述，不能当作稳定的人群偏好。',panel);
  card.options.forEach((option,j)=>{
   el('h4',option,panel);
   [['真人',card.human[j],'#26745d'],['预测',card.model[j],'#6651a8']].forEach(([label,value,color])=>{
    const row=el('div',undefined,panel);row.style.cssText='display:grid;grid-template-columns:60px 1fr 65px;gap:10px;align-items:center;margin:8px 0';
    el('span',label,row);const track=el('div',undefined,row);track.style.cssText='height:18px;background:#e7ece8';
    const bar=el('div',undefined,track);bar.style.height='100%';bar.style.width=(100*value)+'%';bar.style.background=color;
    el('strong',(100*value).toFixed(1)+'%',row);
   });
  });
 });
}
selector.addEventListener('change',()=>{page=0;show();});root.querySelectorAll('[data-step]').forEach(button=>button.addEventListener('click',()=>{page+=Number(button.dataset.step);show();}));show();
})();
</script>'''
