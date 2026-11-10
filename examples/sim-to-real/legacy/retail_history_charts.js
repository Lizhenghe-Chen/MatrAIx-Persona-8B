// All four earlier rounds use the validated normalized aggregates from build_report.py.
const historyNames=['第一轮：合成人格','第二轮：换模型','第三轮：提示与真人背景','第四轮：电商复验'];
const H=D.history;
function historyScores(stage,scopeKey){return scopeKey==='overall'||scopeKey==='questions'?stage.overall.scores:stage.scopes[scopeKey].scores;}
H.forEach((stage,i)=>{
 const select=$('historyScope'+i),c=chart('historyOverview'+i);
 if(stage.overall){select.add(new Option('三份调查等权平均（主口径）','overall'));select.add(new Option('18 道题等权平均（补充口径）','questions'));}
 Object.entries(stage.names).forEach(([key,name])=>select.add(new Option(name,key)));
 const max=Math.ceil(Math.max(...Object.values(stage.scopes).flatMap(s=>Object.values(s.scores).map(r=>r.error)))/10)*10;
 function draw(){
  const values=historyScores(stage,select.value),metric=select.value==='questions'?'questionMean':'error';
  let labels,ss;
  if(i===1){labels=['只给情境','加年龄学历','再加四项人格'];ss=[['flash','DeepSeek Flash',C.before],['pro','DeepSeek Pro',C.after],['qwen','内网 Qwen',C.stat]].map(([k,name,color])=>series(name,['A','B','C'].map(a=>values[k+'-'+a][metric]),color));}
  else if(i===2){labels=['粗分年龄学历','细分年龄学历','加贴题背景','再加合成人格'];ss=[series('扮演受访者',[1,2,3,4].map(b=>values['p0-b'+b][metric]),C.before),series('预测受访者',[1,2,3,4].map(b=>values['p1-b'+b][metric]),C.after),series('真人数据参照',[1,2,3,4].map(()=>values['historical-stratum'][metric]),C.stat)];}
  else if(i===0){labels=['只给情境','加年龄学历','再加四项人格'];ss=[series('分布误差',['A','B','C'].map(k=>values[k][metric]),C.after)];}
  else {labels=['扮演+基础背景','扮演+贴题背景','预测+基础背景','预测+贴题背景','真人数据参照'];ss=[{name:'分布误差',data:Object.keys(stage.labels).map(k=>values[k][metric]),color:C.after}];}
  distribution(c,labels,ss,{max,unit:' 点',digits:2});
  const rows=Object.entries(stage.labels).map(([key,name])=>[name,values[key][metric].toFixed(2),values[key].accuracy==null?'本轮不作逐人匹配':values[key].accuracy.toFixed(1)+'%']);
  setTable('historyTable'+i,['设置','分布误差（百分点）','逐人正确率'],rows,select.selectedOptions[0].textContent+'。主口径与逐题等权不可混用。');
 }
 select.addEventListener('change',draw);draw();
});
const reject=H[3].scopes.packaging.optOut;
distribution(chart('historyRejection'),['真人','原提示+基础背景','预测提示+贴题背景','真人数据参照'],[
 series('都不买的比例',[reject.human,reject['P0+B1'],reject['P1+B3'],reject['统计基线']],C.before)
],{max:40,unit:'%',digits:1});
// Per-question view: registered paired comparisons only, with full Chinese labels.
historyNames.forEach((n,i)=>$('historyRound').add(new Option(n,String(i))));$('historyRound').value='2';
const historyQuestionChart=chart('historyQuestions'),historyDistributionChart=chart('historyDistribution');
const defaults=[['B','C'],['flash-A','pro-A'],['p0-b1','p1-b3'],['P0+B1','P1+B3']];
function historyCurrent(){const stage=H[Number($('historyRound').value)],scope=stage.scopes[$('historySurvey').value];return {stage,scope,pair:scope.pairs[Number($('historyPair').value)]};}
function historyMethods(stage,pair){const keys=[pair.reference,pair.candidate];const stat=['historical-stratum','统计基线'].find(k=>k in stage.labels);if(stat&&!keys.includes(stat))keys.push(stat);return keys;}
function drawHistoryQuestion(){
 const {stage,scope,pair}=historyCurrent(),q=scope.items[Number($('historyQuestion').value)],keys=historyMethods(stage,pair);
 distribution(historyDistributionChart,q.options,[series('真人',q.human,C.real),...keys.map((k,i)=>series(['改前','改后','真人数据参照'][i],q.settings[k].pct,[C.before,C.after,C.stat][i]))]);
 $('historyQuestionText').textContent=q.title+(q.count?'。'+q.count:'');
 $('historyOriginal').textContent=[q.original,q.description,q.count].filter(Boolean).join('\n')||'正式题面与字段映射见本轮原始数据及方案。';
 setTable('historyOptionTable',['选项','真人',...keys.map(k=>stage.labels[k])],q.options.map((v,i)=>[v,q.human[i].toFixed(1)+'%',...keys.map(k=>q.settings[k].pct[i].toFixed(1)+'%')]));
}
function drawHistoryPair(){
 const {stage,scope,pair}=historyCurrent(),keys=historyMethods(stage,pair);
 const rows=scope.items;
 const unequalWeights=H.indexOf(stage)<2 && [pair.reference,pair.candidate].some(k=>k==='A'||k.endsWith('-A')) && ![pair.reference,pair.candidate].every(k=>k==='A'||k.endsWith('-A'));
 $('historyContrastNote').textContent='改前：'+stage.labels[pair.reference]+'。改后：'+stage.labels[pair.candidate]+'。本调查平均差距：'+scope.scores[pair.reference].error.toFixed(2)+' → '+scope.scores[pair.candidate].error.toFixed(2)+' 个百分点。改善值 '+(pair.gain_pp>=0?'+':'')+pair.gain_pp.toFixed(2)+'，95% 区间 '+pair.ci95.map(x=>x.toFixed(2)).join(' 至 ')+'。'+(unequalWeights?'这是保留的历史口径：两组权重不同，不能把差异全归给画像。统一权重复算及更正见前面的“匹配与方法审查”。':pair.ci95[0]>0?'区间支持改善。':pair.ci95[1]<0?'区间支持变差。':'本次改善方向不明确。');
 $('historyQuestions').style.height=Math.max(400,rows.length*58+110)+'px';historyQuestionChart.resize();
 historyQuestionChart.setOption({...base(),legend:{top:0,left:0},grid:{left:150,right:35,top:60,bottom:40},xAxis:{type:'value',min:0,name:'分布误差（百分点）',nameLocation:'middle',nameGap:27},yAxis:{type:'category',inverse:true,data:rows.map(q=>q.title),axisLabel:{width:135,overflow:'truncate'}},tooltip:{trigger:'axis',confine:true,enterable:true,formatter:explainChartTooltip('点')},series:keys.map((k,i)=>({name:['改前','改后','真人数据参照'][i],type:'bar',data:rows.map(q=>round(q.settings[k].error)),itemStyle:{color:[C.before,C.after,C.stat][i]},barMaxWidth:15}))},true);
 const tableRows=rows.map(q=>[q.title,...keys.map(k=>q.settings[k].error.toFixed(2)),(q.settings[pair.reference].error-q.settings[pair.candidate].error).toFixed(2)]);
 tableRows.push(['本调查等权平均',...keys.map(k=>scope.scores[k].error.toFixed(2)),pair.gain_pp.toFixed(2)]);
 setTable('historyQuestionTable',['题目',...keys.map(k=>stage.labels[k]),'改善（正值更好）'],tableRows);
 drawHistoryQuestion();
}
function chooseHistorySurvey(){
 const stage=H[Number($('historyRound').value)],scope=stage.scopes[$('historySurvey').value];
 $('historyPair').replaceChildren(...scope.pairs.map((p,i)=>new Option(stage.labels[p.reference]+' → '+stage.labels[p.candidate],String(i))));
 const desired=defaults[Number($('historyRound').value)],found=scope.pairs.findIndex(p=>p.reference===desired[0]&&p.candidate===desired[1]);if(found>=0)$('historyPair').value=String(found);
 $('historyQuestion').replaceChildren(...scope.items.map((q,i)=>new Option(q.title,String(i))));drawHistoryPair();
}
function chooseHistoryRound(){const stage=H[Number($('historyRound').value)];$('historySurvey').replaceChildren(...Object.entries(stage.names).map(([k,n])=>new Option(n,k)));chooseHistorySurvey();}
$('historyRound').addEventListener('change',chooseHistoryRound);$('historySurvey').addEventListener('change',chooseHistorySurvey);$('historyPair').addEventListener('change',drawHistoryPair);$('historyQuestion').addEventListener('change',drawHistoryQuestion);chooseHistoryRound();
if(D.inputParity){
 const parity=D.inputParity,keys=['basic','rich','attitude'],labels=['年龄与学历','再加性别、收入','再加实测态度'];
 distribution(chart('parityChart'),labels,[series('模型给各项概率',keys.map(k=>parity.summary[k+'_probability'].tv_pp),C.after),series('可见输入对齐的统计方法',keys.map(k=>parity.summary['statistics_'+k].tv_pp),C.stat)],{max:20,unit:' 点',digits:2});
 setTable('parityTable',['背景条件','模型分布误差','统计分布误差','统计改善及95%区间','模型逐人误差','统计逐人误差'],keys.map((k,i)=>{const a=parity.summary[k+'_probability'],b=parity.summary['statistics_'+k],c=parity.comparisons[k];return [labels[i],a.tv_pp.toFixed(2),b.tv_pp.toFixed(2),c.tv_improvement_pp.toFixed(2)+' ['+c.tv_95_interval.map(x=>x.toFixed(2)).join(', ')+']',a.brier.toFixed(4),b.brier.toFixed(4)]}));
 const attributes=Object.keys(parity.controlled_attribute_effects);
 distribution(chart('parityEffects'),['只增加环保材质','只增加凝胶缓震'],[
  series('真人',attributes.map(k=>parity.controlled_attribute_effects[k].real_effect),C.real),
  series('模型给各项概率',attributes.map(k=>parity.controlled_attribute_effects[k].methods.rich_probability.effect),C.after),
  series('可见输入对齐统计',attributes.map(k=>parity.controlled_attribute_effects[k].methods.statistics_rich.effect),C.stat),
  series('原含设计信息统计',attributes.map(k=>D.shoes.controlled_attribute_effects[k].methods.statistics.effect),C.blend)
 ],{max:2,unit:' 分',digits:2});
}
