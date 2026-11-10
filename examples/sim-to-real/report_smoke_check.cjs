// Check offline charts, all question comparisons, and desktop/mobile layout.
// Node.js 22+ and Chrome; optionally set CHROME_BIN on non-macOS systems.
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process'),{pathToFileURL}=require('node:url');
const wait=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const dir=fs.mkdtempSync('/tmp/matraix-reader-qa.');
 const file=process.argv[2] || path.join(__dirname,'study','index.html'),url=pathToFileURL(file).href;
 const chrome=spawn(process.env.CHROME_BIN || (process.platform==='darwin' ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' : 'google-chrome'),['--headless','--no-first-run','--disable-background-networking','--remote-debugging-port=0','--user-data-dir='+dir,'about:blank'],{stdio:'ignore'});
 let socket;
 try{
  const portfile=path.join(dir,'DevToolsActivePort');for(let i=0;!fs.existsSync(portfile)&&i<60;i++)await wait(200);
  const port=fs.readFileSync(portfile,'utf8').split('\n')[0];
  const tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
  socket=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise(r=>socket.addEventListener('open',r,{once:true}));
  let id=0;const pending=new Map(),errors=[],requests=[],failedRequests=[];
  socket.addEventListener('message',e=>{const msg=JSON.parse(e.data);if(msg.id){pending.get(msg.id)?.(msg);pending.delete(msg.id)}else if(msg.method==='Runtime.exceptionThrown')errors.push(msg.params);else if(msg.method==='Network.requestWillBeSent')requests.push(msg.params.request.url);else if(msg.method==='Network.loadingFailed'&&!msg.params.canceled)failedRequests.push(msg.params.errorText)});
  const send=(method,params={})=>new Promise(r=>{const key=++id;pending.set(key,r);socket.send(JSON.stringify({id:key,method,params}))});
  const run=async(expression)=>{const v=await send('Runtime.evaluate',{expression,returnByValue:true});assert.ok(!v.error&&!v.result.exceptionDetails,JSON.stringify(v));return v.result.result.value};
  await send('Runtime.enable');await send('Network.enable');await send('Page.enable');
  const legacyEntry=pathToFileURL(path.join(path.dirname(file),'..','retail_reader_template.html')).href;
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1080,deviceScaleFactor:1,mobile:false});await send('Page.navigate',{url:legacyEntry+'#revalidation'});await wait(200);
  for(let i=0;i<100;i++){if(await run("document.readyState==='complete' && window.reportCharts?.length===22"))break;await wait(100)}
  assert.equal(await run('window.reportCharts.length'),22);assert.deepEqual(errors,[]);
  assert.equal(await run('window.location.href'),url+'#revalidation');
  assert.equal(await run('/\\{\\{[A-Z_]+\\}\\}/.test(document.body.textContent)'),false);
  assert.deepEqual(failedRequests,[]);
  await run("window.scrollTo({top:0,behavior:'instant'})");
  assert.equal(await run("document.querySelectorAll('.chart-guide').length"),22);
  assert.ok(await run("document.querySelector('#final-answer').textContent.includes('官方 8B')"));
  assert.ok(await run("document.querySelector('#profile-truth').textContent.includes('不是该真人的测量')"));
  assert.ok(await run("document.querySelector('#matching-audit').textContent.includes('412')"));
  assert.ok(await run("document.querySelector('#matching-audit').textContent.includes('31.1%')"));
  assert.ok(await run("document.querySelector('#matching-audit').textContent.includes('方向尚不明确')"));
  assert.ok(await run("document.querySelector('#closing').textContent.includes('内网 Qwen')"));
  assert.ok(await run("document.querySelector('#model-decision').textContent.includes('21.97')"));
  assert.ok(await run("explainChartTooltip('个百分点')([{axisValueLabel:'读图检查',seriesName:'同龄同学历真人比例',value:4.51}]).includes('不用大模型')"));
  assert.ok(requests.every(u=>u.startsWith('file:')||u.startsWith('data:')),JSON.stringify(requests));
  const result=await run(`(()=>{const data=JSON.parse(document.querySelector('#report-data').textContent);return {charts:window.reportCharts.length,questionOptions:document.querySelector('#surveyQuestion').options.length,average:data.pew.summaries.rich_probability.tv_pp,summary:document.querySelector('#surveyDetail').textContent,tableRows:document.querySelectorAll('#surveyAllTable tbody tr').length,overflow:[document.documentElement.clientWidth,document.documentElement.scrollWidth]}})()`);
  assert.equal(result.questionOptions,13);assert.equal(result.tableRows,14);assert.match(result.summary,/240 名有效受访者/);assert.equal(result.overflow[0],result.overflow[1]);assert.ok(result.overflow[0]>1000);
  const change=(id,value)=>`{const el=document.getElementById(${JSON.stringify(id)});el.value=${JSON.stringify(value)};el.dispatchEvent(new Event('change'));}`;
  const all=await run(`(()=>{const sel=document.querySelector('#surveyQuestion');return [...sel.options].map(x=>x.value)})()`);
  for(const q of all){await run(change('surveyQuestion',q));assert.ok(await run(`document.querySelector('#surveyOriginal').textContent.length>25`))}
  for(const mode of ['format','background-choice','background-probability','calibration']){
   await run(change('surveyContrast',mode));
   for(const q of all){await run(change('surveyQuestion',q));assert.equal(await run("document.querySelectorAll('#surveyOptionTable tbody tr').length"),q.startsWith('SHOP20')?2:q==='SHOP12'?3:4)}
   const row=await run("[...document.querySelector('#surveyAllTable tbody tr:last-child').cells].map(x=>x.textContent)");
   const expected={format:['43.41','18.08','4.51'],'background-choice':['41.71','43.41','4.51'],'background-probability':['18.64','18.08','4.51'],calibration:['18.08','5.43','4.59']}[mode];
   assert.deepEqual(row.slice(1,4),expected);
  }
  await run(change('surveyContrast','format'));
  await run(change('surveyQuestion','SHOP7C'));await run(change('surveyView','gain'));await run(change('surveyView','comparison'));
  for(let round=0;round<4;round++){
   await run(change('historyRound',String(round)));
   const scopes=await run("[...document.querySelector('#historySurvey').options].map(x=>x.value)");
   for(const scope of scopes){
    await run(change('historySurvey',scope));
    const pairs=await run("document.querySelector('#historyPair').options.length");
    for(let pair=0;pair<pairs;pair++){
     await run(change('historyPair',String(pair)));
     assert.ok(await run("document.querySelector('#historyContrastNote').textContent.includes('95%')"));
    }
    const items=await run("document.querySelector('#historyQuestion').options.length");
    for(let item=0;item<items;item++){
     await run(change('historyQuestion',String(item)));
     assert.ok(await run("document.querySelectorAll('#historyOptionTable tbody tr').length>=2"));
    }
   }
   const averages=await run("[...document.querySelector('#historyScope"+round+"').options].map(x=>x.value)");
   for(const average of averages)await run(change('historyScope'+round,average));
   await run(change('historyScope'+round,round===3?'origin':'overall'));
  }
  await run(change('historyRound','2'));
  for(const d of ['treat constrained','control constrained','treat random','control random','all'])await run(change('shoeDesign',d));
  for(const task of ['spend','repeat','price'])await run(change('amazonTask',task));
  // The sixth round keeps separate chart instances and only aggregate inputs.
  assert.equal(await run('window.revalidationCharts.length'),8);
  assert.equal(await run("document.querySelectorAll('.rv-chart svg').length"),8);
  assert.ok(await run("document.querySelector('#revalidation').textContent.includes('4,090')"));
  assert.ok(await run("document.querySelector('#revalidation').textContent.includes('285份正式答卷')"));
  assert.ok(await run("document.querySelector('#latest-conclusion').textContent.includes('三次运行均改善')"));
  const matchPairs=await run("document.querySelector('#rvMatchingContrast').options.length");
  const matchQuestions=await run("[...document.querySelector('#rvMatchingQuestion').options].map(x=>x.value)");
  assert.equal(matchPairs,7);assert.equal(matchQuestions.length,13);
  for(let i=0;i<matchPairs;i++){
   await run(change('rvMatchingContrast',String(i)));
   for(const q of matchQuestions){
    await run(change('rvMatchingQuestion',q));
    assert.equal(await run("document.querySelectorAll('#rvMatchingOptions tbody tr').length"),q.startsWith('SHOP20')?2:q==='SHOP12'?3:4);
   }
  }
  for(const survey of ['origin','packaging']){
   await run(change('rvProductSurvey',survey));
   const qs=await run("[...document.querySelector('#rvProductQuestion').options].map(x=>x.value)");
   assert.equal(qs.length,survey==='origin'?4:16);
   for(const method of ['choice','statistics']){
    await run(change('rvProductContrast',method));
    for(const q of qs){
     await run(change('rvProductQuestion',q));
     assert.equal(await run("document.querySelectorAll('#rvProductOptions tbody tr').length"),survey==='origin'?2:3);
    }
   }
  }
  await run(change('rvMatchingContrast','5'));
  await run(change('rvMatchingQuestion','SHOP7C'));
  await run(change('rvProductContrast','choice'));
  async function screenshot(name,selector){let params={format:'png'};if(selector){const rect=await run(`(()=>{const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return {x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:Math.min(r.height,1500),scale:1}})()`);params={...params,clip:rect,captureBeyondViewport:true}}const r=await send('Page.captureScreenshot',params);fs.writeFileSync(path.join(dir,name+'.png'),Buffer.from(r.result.data,'base64'))}
  await run("document.querySelector('#openTerms').click()");
  assert.equal(await run("document.querySelector('#termDialog').open"),true);
  await run("{const q=document.querySelector('#termSearch');q.value='年龄学统计';q.dispatchEvent(new Event('input'))}");
  assert.equal(await run("document.querySelector('#termList h3').textContent"),'同龄同学历真人比例');
  await run("{const q=document.querySelector('#termSearch');q.value='历史统计';q.dispatchEvent(new Event('input'))}");
  assert.ok(await run("document.querySelector('#termList').textContent.includes('不一定是更早年份')"));
  await screenshot('desktop-glossary');
  await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
  assert.equal(await run("document.querySelector('#termDialog').open"),false);
  await screenshot('desktop-conclusion','#final-answer');await screenshot('desktop-provenance','#profile-truth');await screenshot('desktop-closing','#closing');
  await screenshot('desktop-matching-audit','#matching-audit');
  await screenshot('desktop-revalidation','#revalidation');
  await screenshot('desktop-revalidation-models','#rvMatchingOverall');
  await screenshot('desktop-revalidation-product','#rvProductDistribution');
  await screenshot('desktop-revalidation-refusal','#rvRefusal');
  await screenshot('desktop-top');await screenshot('desktop-models','#models');await screenshot('desktop-history','#history-details');await screenshot('desktop-parity','#input-parity');await screenshot('desktop-survey','#survey');await screenshot('desktop-shoes','#shoes');await screenshot('desktop-method','#method');
  await send('Emulation.setDeviceMetricsOverride',{width:581,height:954,deviceScaleFactor:1,mobile:false});await wait(200);
  const sidebar=await run('[document.documentElement.clientWidth,document.documentElement.scrollWidth]');assert.equal(sidebar[0],sidebar[1]);
  const chartSizes=await run('window.revalidationCharts.map(c=>({id:c.getDom().id,chart:c.getWidth(),container:c.getDom().clientWidth}))');
  for(const size of chartSizes)assert.equal(size.chart,size.container,JSON.stringify(size));
  assert.deepEqual(await run(`(()=>{const chart=document.querySelector('#rvMatchingOverall'),box=chart.getBoundingClientRect();return [...chart.querySelectorAll('svg text')].filter(t=>/^[0-9]+([.][0-9]+)?$/.test(t.textContent)).filter(t=>{const r=t.getBoundingClientRect();return r.right>box.right+1||r.left<box.left-1}).map(t=>t.textContent)})()`),[]);
  assert.equal(await run("window.revalidationCharts[1].getOption().xAxis[0].nameLocation"),'middle');
  await screenshot('sidebar-top');await screenshot('sidebar-revalidation-models','#rvMatchingOverall');
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await wait(200);
  assert.deepEqual(await run('[document.documentElement.clientWidth,document.documentElement.scrollWidth]'),[390,390]);
  await screenshot('mobile-top');await screenshot('mobile-history','#history-details');await screenshot('mobile-models','#models');await screenshot('mobile-survey','#survey');await screenshot('mobile-factors','#decisions');
  await screenshot('mobile-matching-audit','#matching-audit');
  await screenshot('mobile-revalidation','#revalidation');
  await screenshot('mobile-revalidation-models','#rvMatchingOverall');
  await screenshot('mobile-revalidation-product','#rvProductDistribution');
  await run("document.querySelector('[data-explain=probability]').click()");
  assert.equal(await run("document.querySelector('#termDialog').open"),true);
  assert.ok(await run("(()=>{const r=document.querySelector('#termDialog').getBoundingClientRect();return r.left>=0&&r.right<=390})()"));
  await screenshot('mobile-glossary');await run("document.querySelector('#closeTerms').click()");
  // Every chart must have a non-empty SVG and an option object after switching.
  assert.equal(await run("[...document.querySelectorAll('.chart')].filter(x=>x.querySelector('svg')).length"),22);
  assert.deepEqual(errors,[]);
  const standalone=pathToFileURL(path.join(path.dirname(file),'10_匹配与商品复验','index.html')).href;
  await send('Page.navigate',{url:standalone});
  for(let i=0;i<100;i++){if(await run("document.readyState==='complete' && window.revalidationCharts?.length===8"))break;await wait(100)}
  assert.equal(await run("document.querySelectorAll('.rv-chart svg').length"),8);
  assert.deepEqual(await run('[document.documentElement.clientWidth,document.documentElement.scrollWidth]'),[390,390]);
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1080,deviceScaleFactor:1,mobile:false});await wait(200);
  await screenshot('standalone-revalidation');
  assert.deepEqual(errors,[]);
  assert.ok(requests.every(u=>u.startsWith('file:')||u.startsWith('data:')));
  assert.deepEqual(failedRequests,[]);
  console.log(JSON.stringify({folder:dir,...result,networkRequests:requests.length,failedRequests,consoleErrors:errors.length,legacyTemplateRedirectVerified:true,unexpandedPlaceholders:0,allSelectorsVerified:true,questionByComparisonViewsVerified:52,revalidationCharts:8,revalidationViews:131,standaloneVerified:true,sidebarWidth:581,mobileWidth:390,contextualChartGuides:22,glossarySearchAndKeyboardVerified:true},null,2));
 }finally{socket?.close();chrome.kill()}
})().catch(e=>{console.error(e);process.exitCode=1});
