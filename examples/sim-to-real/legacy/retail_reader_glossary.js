// Reader help is local to the report. It never reads respondent-level records.
const reportTerms = {
 choice:{title:'模型只选一项',aliases:'原单选 原方法 单选',text:'给同一位受访者的背景和原题，让模型每题只选一个选项，再数各选项得票。模型的犹豫不会保留下来。这里的“原”指本轮同背景对照，不是第一轮 Flash。'},
 probability:{title:'模型给各项概率',aliases:'保留概率 概率输出 概率汇总',text:'模型为每位受访者的每道题输出一组总和为 100% 的估计，再按本任务权重汇总。它是模型生成的数，不是真人自报概率，也不保证已经准确校准。仅为示例：每人都给 60%／40%，汇总仍是 60%／40%；只取最大项则可能变成 100%／0%。'},
 'age-stat':{title:'同龄同学历真人比例',aliases:'年龄学历统计 年龄学统计 分层统计',text:'不用大模型。用评估对象之外、同年龄段和学历档的真人对同题的回答比例，预测评估对象。第五轮 Pew 用另外 4,029 人，人数较少的小组会适度参考总体比例，减少小样本造成的极端估计。它不是照抄被预测者自己的答案。'},
 statistics:{title:'真人数据参照',aliases:'历史统计 统计基线 真人统计对照',text:'这是不同简单方法的统称，不是一款大模型。问卷可按其他真人算比例；商品任务可用其他真人选择训练统计模型；购买任务用本人此前的记录估计。“历史”容易误导：同题问卷的训练人群常来自同一波调查，不一定是更早年份。'},
 'rich-stat':{title:'相同背景的真人统计',aliases:'同背景统计 完整背景统计',text:'用评估样本之外的真人答案训练统计模型，以年龄、学历、收入、性别、地区等可用字段预测。第五轮 Pew 采用多项逻辑回归，可理解为从其他真人中学习哪些背景与哪些选项较相关。它比单纯按年龄学历分组多用了字段，结果应分开标注。'},
 'shoe-stat':{title:'真人评分训练方法',aliases:'属性+态度统计 属性统计 商品统计',text:'用另外 2,785 名受访者的运动鞋评分学习商品属性与背景对应的七档评分概率。原方法额外使用两条实测态度与设计信息；事后补充去掉额外设计信息，并按对应模型对齐背景。两者都利用真实训练评分，不是纯粹的模型架构对决。'},
 'purchase-history':{title:'本人过往购买频率',aliases:'近期历史 历史购买 购买记录法',text:'用该账户预测日前最近四季度的记录估计下一季度：品类是否买过、价位与支出构成、是否复购；向其他账户更早历史适度平滑。输入不含目标季度。它按实际记录计算，不是让大模型扮演消费者。'},
 calibration:{title:'用真人数据修正模型概率',aliases:'校准 修正后概率 历史数据修正后',text:'先用开发样本固定修正规则，之后在另一批评估对象上评分。Pew 具体把开发样本的模型平均概率对齐到真人统计方法的预测，再固定该调整用于正式样本。这已经借助其他真人的答案，不是模型独立增加的能力；修正后的群体比例更准，也不保证具体个人更准。'},
 blend:{title:'统计与模型加权组合',aliases:'组合 混合',text:'把两套预测按固定比例平均。权重先用开发样本确定，正式评估时不再挑选。Amazon 品类用 88.4% 近期记录预测与 11.6% 模型预测；这个比例不适用于所有任务。'},
 synthetic:{title:'合成人格',aliases:'DAG 四项人格 画像',text:'由 MatrAIx 条件生成规则产生的设定，不是逐人心理测量。前两轮年龄学历也来自合成画像；第三轮有一组把同年龄学历层的四项合成人格随机分配给真人，目的是测试额外设定是否有增益。它不表示这位真人确实具有这些特征。'},
 background:{title:'真实背景记录',aliases:'补充背景 贴题背景 真实画像 实测态度',text:'原调查记录或同一人的前测中已有的字段。来源可是真人自报、机构整理或从真实行为计算的汇总；这不等于经外部审计的完整个人事实。编码翻译、分档与汇总可复核；模型没有替受访者编造缺失的职业或人生经历。不同任务用的字段见“画像哪些真实”表。'},
 prompt:{title:'预测提示与角色扮演提示',aliases:'P0 P1 预测受访者 扮演受访者',text:'角色扮演提示让模型“作为此人回答”；预测提示让模型根据已给背景，判断此人在调查当时最可能怎样回答，并避免自行补造缺失经历。只是提问方式不同，预测提示本身没有提供答案。'},
 distribution:{title:'分布误差',aliases:'分布差距 TV 总变差 百分点',text:'比较真人与预测各选项比例，绝对差相加后除以二，换算为百分点；越低越好。仅为例子：真人 60%／40%，预测 80%／20%，误差 20 个百分点。它不是“多少人答错”，不能用 100 减去它当准确率。产地实验另对四个属性选择比例求平均误差。'},
 individual:{title:'逐人概率误差',aliases:'Brier 逐账户误差 逐人正确率',text:'逐人概率误差检查是否把较高概率给了本人实际选择的选项，以平方差计算，越低越好；它不是百分比错误率。逐人正确率则取一个答案看是否答对。群体总体比例接近，仍可能没有找对具体的人。'},
 interval:{title:'95% 区间',aliases:'配对重抽样 bootstrap',text:'按人重复抽样 2,000 次，查看同一改动的改善值受这批样本波动影响多大。改善区间全高于零支持改善，跨零表示方向尚不明确。它不等于结论有 95% 概率正确，也不覆盖换模型、换时代和重新训练的所有不确定性。'},
 concentration:{title:'回答过度集中',aliases:'全票 95% 99% 100%',text:'真人有多种选择时，模型却把几乎所有份额放在一项。例如“达到 95%”表示某一选项占预测份额至少 95%。这不是 95% 准确率。输出概率可以缓和集中，但还需检查每项与真人的差距。'},
 matched:{title:'可见输入对齐',aliases:'输入对齐',text:'运动鞋补充分析去掉统计方法额外使用的设计标签，按模型条件提供同样的商品字段和背景。统计方法仍学习了另外一批真人评分。这是看过原评估结果后的事后检查，不是新增独立样本验证。'},
 split:{title:'训练、开发与评估样本',aliases:'开发样本 留出样本 独立评估',text:'训练样本给统计方法学习规律；开发样本用于选择修正或组合参数；评估样本最后用来检验。评估者自己的目标答案不进入模型提示或训练。相同调查中不同人之间的留出，也不能保证对新年代、新产品同样有效。'}
};
window.reportTerms=reportTerms;

function reportHelpSetup(){
 const dialog=document.getElementById('termDialog'),search=document.getElementById('termSearch'),list=document.getElementById('termList');
 let opener;
 function render(query=''){
  const entries=Object.entries(reportTerms).filter(([key,t])=>(key+t.title+t.aliases+t.text).toLowerCase().includes(query.toLowerCase()));
  list.replaceChildren(...entries.map(([key,t])=>{const article=document.createElement('article');article.id='explain-'+key;
   const h=document.createElement('h3');h.textContent=t.title;
   const old=document.createElement('p');old.className='note';old.textContent='也可能写作：'+t.aliases;
   const p=document.createElement('p');p.textContent=t.text;article.append(h,old,p);return article;}));
  document.getElementById('termCount').textContent=entries.length+' 项解释';
 }
 function open(key,trigger){opener=trigger;search.value=key&&reportTerms[key]?reportTerms[key].title:'';render(search.value);dialog.showModal();search.focus();}
 document.addEventListener('click',event=>{const button=event.target.closest('[data-explain]');if(button)open(button.dataset.explain,button);});
 document.getElementById('openTerms').addEventListener('click',event=>open('',event.currentTarget));
 document.getElementById('closeTerms').addEventListener('click',()=>dialog.close());
 dialog.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();dialog.close();}});
 dialog.addEventListener('close',()=>opener?.focus());
 dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});
 search.addEventListener('input',()=>render(search.value));render();
}

function reportTermForLabel(label){
 if(/可见输入对齐/.test(label))return 'matched';
 if(/同龄同学历|年龄学历统计/.test(label))return 'age-stat';
 if(/相同背景.*统计|同背景统计/.test(label))return 'rich-stat';
 if(/真人评分|属性.*统计|含设计信息/.test(label))return 'shoe-stat';
 if(/本人过往|近期历史/.test(label))return 'purchase-history';
 if(/组合|少量模型/.test(label))return 'blend';
 if(/修正|校准/.test(label))return 'calibration';
 if(/只选|单选/.test(label))return 'choice';
 if(/概率/.test(label))return 'probability';
 if(/真人数据参照|统计/.test(label))return 'statistics';
 if(/人格/.test(label))return 'synthetic';
 return null;
}

function explainChartTooltip(unit='',digits=2){return params=>{
 const rows=Array.isArray(params)?params:[params];
 const safe=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
 const lines=[`<b>${safe(rows[0]?.axisValueLabel||rows[0]?.name)}</b>`];
 const keys=new Set();
 rows.forEach(p=>{const v=typeof p.value==='number'?p.value.toFixed(digits):p.value;lines.push(`${p.marker||''}${safe(p.seriesName)}：${safe(v)} ${safe(unit)}`);const k=reportTermForLabel(p.seriesName)||reportTermForLabel(p.name);if(k)keys.add(k);});
 keys.forEach(k=>lines.push(`<div style="margin-top:8px;font-size:12px"><b>${safe(reportTerms[k].title)}</b>：${safe(reportTerms[k].text.split('。').slice(0,2).join('。'))}。</div>`));
 return `<div style="max-width:270px;max-height:45vh;overflow:auto;white-space:normal">${lines.join('<br>')}</div>`;
};}

function attachChartGuides(){
 const guide=(chartId,keys,note)=>{
  const chart=document.getElementById(chartId);if(!chart)return;
  let box=document.getElementById(chartId+'-guide');if(!box){box=document.createElement('aside');box.id=chartId+'-guide';box.className='chart-guide';chart.after(box);}
  box.replaceChildren();const p=document.createElement('p');p.textContent=note;box.append(p);
  const label=document.createElement('span');label.textContent='点开解释：';box.append(label);
  keys.forEach(key=>{const b=document.createElement('button');b.type='button';b.className='term';b.dataset.explain=key;b.textContent=reportTerms[key].title;box.append(b,document.createTextNode('　'));});
 };
 for(const id of ['headlinePew','surveyDistribution','surveyQuestions','pewFactors'])guide(id,['choice','probability','age-stat'],
  '模型只选一项＝每人投一票；模型给各项概率＝汇总可能性；同龄同学历真人比例＝从另外一批人的同题答案计算。背景变化以所选对照为准。');
 for(const id of ['headlineShoe','shoeDistribution','shoeEffects','shoeFactors'])guide(id,['choice','probability','shoe-stat'],
  '模型只选一项＝每款鞋只给一个分数；模型给各项概率＝保留 1–7 分各自的可能性；真人评分训练方法＝从其他人的评分学习规律。');
 for(const id of ['calibrationGroup','calibrationPerson'])guide(id,['calibration','rich-stat','individual'],
  '修正模型＝用开发样本固定概率调整；相同背景的真人统计＝从另外 4,029 人学习。前者误差更低于旧模型，不代表超过后者。');
 for(const id of ['amazonRelative','amazonCategories','amazonMix'])guide(id,['purchase-history','blend','individual'],
  '本人过往购买频率＝以最近四季度记录估计；直接用模型＝让 Qwen 根据预测日前汇总推断；组合＝两套预测按开发集固定权重平均。');
 for(const id of ['parityChart','parityEffects'])guide(id,['matched','probability','shoe-stat'],
  '本图统计方法与对应模型使用相同可见商品字段和背景；统计方法仍学过其他真人的评分。总体比例与属性效果分别判断。');
 for(const id of ['historyOverview0','historyOverview1'])guide(id,['synthetic','concentration','distribution'],
  '本轮年龄、学历和人格都是合成设定，真人调查提供群体参照；没有逐一预测对应真人。误差低不等于获得真实数字分身。');
 guide('historyOverview2',['background','synthetic','age-stat','prompt'],
  '基础与贴题背景取自该真人记录，额外四项人格是随机匹配的合成设定；统计方法使用本次评估样本之外的同题真人比例。');
 const shoppingNote={origin:'当前产地选择的统计方法：用其他 708 人的选择，学习商品属性与可用背景对应的选择概率。',packaging:'当前包装选择的统计方法：用其他 1,003 人的选择训练，包含“都不买”这一选项。',pew:'当前网购习惯的统计方法：用其他 5,575 人的同题答案，按年龄学历计算比例。'};
 guide('historyOverview3',['prompt','background','statistics'],shoppingNote[document.getElementById('historyScope3').value]);
 guide('historyRejection',['statistics','individual'],'真人拒买比例来自实际选择卡；模型与统计方法都要保留“都不买”。总体拒买比例与识别实际拒买者是两项指标。');
 const n=Number(document.getElementById('historyRound').value);
 const note='改前／改后对应上方当前选择的两种设置。'+(n<2?'本轮用合成人群比较群体比例，没有真人逐一对应。':n===2?'背景来自真人；新增人格组除外。统计参照用评估样本之外的同题真人。':shoppingNote[document.getElementById('historySurvey').value]);
 for(const id of ['historyQuestions','historyDistribution'])guide(id,[n<2?'synthetic':'background','statistics','distribution'],note);
}
