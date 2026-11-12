/* All data are embedded aggregates. Works from file:// without network access. */
const questions=JSON.parse(document.getElementById('question-data').textContent);
const questionSelect=document.getElementById('question-select');
const methodSelect=document.getElementById('method-select');
const format=x=>(100*x).toFixed(1)+'%';
questions.forEach((q,i)=>{const o=document.createElement('option');o.value=i;o.textContent=q.label;questionSelect.append(o)});
questionSelect.value='9';
function drawQuestion(){
 const q=questions[Number(questionSelect.value)], method=methodSelect.value, m=q.methods[method];
 document.getElementById('question-name').textContent=q.label;
 document.getElementById('question-original').textContent=q.original+' / '+q.original_options.join(' · ');
 document.getElementById('question-metric').textContent='分布误差 '+m.error.toFixed(2)+' 个百分点 · '+q.people+' 名有效真人 · 越低越好';
 const target=document.getElementById('question-bars');target.replaceChildren();
 q.options.forEach((label,i)=>{
   const block=document.createElement('div');block.className='distribution-option';
   const h=document.createElement('h4');h.textContent=label;block.append(h);
   [['真人回答',q.real[i],'#14372f'],[method,m.shares[i],method==='只选一项'?'#a15e38':method==='真人统计模型'?'#5358a5':'#117b70']].forEach(([title,share,color])=>{
     const row=document.createElement('div');row.className='dist-row';
     const name=document.createElement('span');name.textContent=title;
     const track=document.createElement('div');track.className='track';
     const fill=document.createElement('div');fill.className='fill';fill.style.width=100*share+'%';fill.style.background=color;track.append(fill);
     const value=document.createElement('b');value.textContent=format(share);row.append(name,track,value);block.append(row);
   });target.append(block);
 });
 document.getElementById('method-note').textContent=method==='真人数据校准'||method==='真人统计模型'?'这一方法使用了评估对象之外的真人训练答案；不能把收益全部归功于 AI。':'这一条件没有用该批评估对象的目标题答案进行校准。';
}
questionSelect.addEventListener('change',drawQuestion);methodSelect.addEventListener('change',drawQuestion);drawQuestion();
