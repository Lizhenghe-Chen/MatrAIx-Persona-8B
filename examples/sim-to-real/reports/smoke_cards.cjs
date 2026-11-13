/* Rendering QA for the per-question report: drawers, lazy charts, colour semantics. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process'),{pathToFileURL}=require('node:url');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const dir=fs.mkdtempSync('/tmp/matraix-cards-qa.');
 const chrome=spawn(process.env.CHROME_BIN||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
   ['--headless','--no-first-run','--disable-background-networking','--remote-debugging-port=0',
    '--user-data-dir='+dir,'about:blank'],{stdio:'ignore'});
 let socket;
 try{
  const portfile=dir+'/DevToolsActivePort';for(let i=0;!fs.existsSync(portfile)&&i<60;i++)await delay(200);
  const port=fs.readFileSync(portfile,'utf8').split('\n')[0];
  const tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
  socket=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);
  await new Promise(r=>socket.addEventListener('open',r,{once:true}));
  let id=0;const pending=new Map(),errors=[],remote=[];
  socket.addEventListener('message',e=>{const m=JSON.parse(e.data);
    if(m.id){pending.get(m.id)?.(m);pending.delete(m.id)}
    else if(m.method==='Runtime.exceptionThrown')errors.push(m.params);
    else if(m.method==='Network.requestWillBeSent'&&/^https?:/.test(m.params.request.url))remote.push(m.params.request.url)});
  const send=(method,params={})=>new Promise(r=>{const k=++id;pending.set(k,r);socket.send(JSON.stringify({id:k,method,params}))});
  const run=async(x)=>{const v=await send('Runtime.evaluate',{expression:x,returnByValue:true});
    assert.ok(!v.error&&!v.result.exceptionDetails,JSON.stringify(v));return v.result.result.value};
  await send('Runtime.enable');await send('Page.enable');await send('Network.enable');
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1080,deviceScaleFactor:1,mobile:false});
  await send('Page.navigate',{url:pathToFileURL(path.join(__dirname,'cards.html')).href});
  for(let i=0;i<60;i++){if(await run("document.querySelectorAll('.study-drawer').length"))break;await delay(150)}
  await run("document.documentElement.style.scrollBehavior='auto'");

  const studies=await run("document.querySelectorAll('.study-drawer').length");
  const questions=await run("document.querySelectorAll('.q-drawer').length");
  assert.equal(studies,15,'study drawers: '+studies);
  assert.equal(questions,88,'question drawers: '+questions);

  // Nothing heavy is rendered until a drawer opens.
  assert.equal(await run("document.querySelectorAll('.echart canvas').length"),0,'no canvas before open');
  assert.equal(await run("[...document.querySelectorAll('.study-drawer')].filter(d=>d.open).length"),0,'all collapsed');

  // Collapsed rows still carry a miniature comparison strip.
  const strips=await run("document.querySelectorAll('.qstrip .strip-row').length");
  assert.ok(strips>=240,'strip rows: '+strips);
  // Every study now has both arms, so no header may claim one is missing.
  assert.equal(await run("[...document.querySelectorAll('.snums')].filter(e=>e.textContent.includes('未跑')).length"),0,'no arm left unrun');
  assert.equal(await run("[...document.querySelectorAll('.snum-missing b')].filter(e=>e.textContent!=='逐题不可估').length"),0,'missing numbers only mean "cannot score"');
  assert.ok(await run("!document.body.innerHTML.includes('无法比较')"),'no vague wording');
  // A question nobody could score is labelled by cause, not lumped in with a missing arm.
  assert.ok(await run("document.body.innerHTML.includes('逐题不可估')"),'unscorable questions are named');
  // The label must be explained where it appears, not left for the reader to guess.
  assert.ok(await run("document.body.innerHTML.includes('不是普通问卷')"),'unscorable reason stated');
  assert.ok(await run("document.body.innerHTML.includes('不是抽样失败')"),'design intent named, not a sampling failure');
  assert.ok(await run("document.body.innerHTML.includes('联合分析')&&document.body.innerHTML.includes('打分任务')"),'both design kinds named');
  assert.ok(await run("document.body.innerHTML.includes('62pp')"),'sampling floor table present');
  // The external study gained its native arm: both numbers must be on the page.
  assert.ok(await run(`(()=>{const s=document.querySelector('#s-openecommerce');
    return !!s && /24\.2/.test(s.textContent) && /18\.2/.test(s.textContent);})()`),'external study shows both arms');

  // Colour semantics, checked against the intended values rather than by impression.
  const colouring=await run(`(()=>{
    const pick=(sel,prop)=>getComputedStyle(document.querySelector(sel))[prop];
    return {
      win:document.querySelectorAll('.tv.win').length,
      lose:document.querySelectorAll('.tv.lose').length,
      tie:document.querySelectorAll('.tv.tie').length,
      up:document.querySelectorAll('.dir.up').length,
      down:document.querySelectorAll('.dir.down').length,
      winColour:pick('.tv.win','color'),
      loseColour:pick('.tv.lose','color'),
      upColour:pick('.dir.up','color'),
      downColour:pick('.dir.down','color'),
      chipWin:pick('.chip.win','background-color'),
      chipLose:pick('.chip.lose','background-color')
    };
  })()`);
  assert.ok(colouring.win>0&&colouring.lose>0&&colouring.tie>0,'three states present: '+JSON.stringify(colouring));
  assert.ok(colouring.up>0&&colouring.down>0,'both deviation directions present');
  assert.equal(colouring.winColour,'rgb(15, 107, 95)','winner emphasised in teal');
  assert.equal(colouring.loseColour,'rgb(139, 154, 146)','loser muted, not red');
  assert.equal(colouring.upColour,'rgb(161, 94, 56)','over-estimate warm');
  assert.equal(colouring.downColour,'rgb(47, 111, 159)','under-estimate cool');
  assert.equal(colouring.chipWin,'rgb(232, 243, 239)','improvement chip is green');
  assert.equal(colouring.chipLose,'rgb(251, 238, 231)','regression chip is warm red');

  // Opening one question draws exactly one chart.
  await run("document.querySelector('#s-german .study-drawer').open=true");
  await delay(250);
  await run("document.querySelector('#s-german .q-drawer').open=true");
  await delay(900);
  const opened=await run("(()=>{const c=document.querySelector('#s-german .qchart canvas');return c?[c.width,c.height]:null})()");
  assert.ok(opened&&opened[0]>400&&opened[1]>200,JSON.stringify(opened));
  assert.equal(await run("document.querySelectorAll('#s-german .qchart canvas').length"),1,'lazy: one chart');
  assert.ok(await run("document.querySelectorAll('#s-german .opt-key li').length")>=2,'numbered key present');

  // Expand-all opens everything; collapse-all closes questions again.
  await run("document.querySelector('[data-act=expand]').click()");
  await delay(3000);
  assert.equal(await run("[...document.querySelectorAll('.q-drawer')].filter(d=>d.open).length"),88,'all questions open');
  assert.ok(await run("document.querySelectorAll('.echart canvas').length")>=85,'charts rendered');
  await run("document.querySelector('[data-act=collapse]').click()");
  await delay(400);
  assert.equal(await run("[...document.querySelectorAll('.q-drawer')].filter(d=>d.open).length"),0,'all collapsed again');

  // A study whose every card is unique falls back to one pooled chart.
  await run("document.querySelector('#s-dryer .study-drawer').open=true");
  await delay(900);
  assert.ok(await run("document.querySelectorAll('#s-dryer .pooled canvas').length")===1,'pooled chart');
  assert.ok(await run("document.querySelectorAll('#s-dryer .q-drawer').length")===0,'no per-question rows');

  const broken=await run(`(()=>{const bad=[];for(const a of document.querySelectorAll('a[href^="#"]')){const id=a.getAttribute('href').slice(1);if(id&&!document.getElementById(id))bad.push(a.getAttribute('href'))}return bad})()`);
  assert.deepEqual(broken,[]);

  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await delay(800);
  assert.ok(await run('document.documentElement.scrollWidth<=window.innerWidth+1'));
  assert.equal(errors.length,0);assert.deepEqual(remote,[]);
  console.log('PASS: '+studies+' studies; '+questions+' question drawers; '+strips+' strip rows; '
    +'lazy charts; expand/collapse; pooled fallback; winner-emphasis without red; mobile viewport; no JS errors; zero remote requests.');
 }finally{if(socket)socket.close();const stopped=new Promise(r=>chrome.once('exit',r));chrome.kill();await stopped;fs.rmSync(dir,{recursive:true,force:true,maxRetries:5,retryDelay:100})}
})().catch(e=>{console.error(e);process.exitCode=1});
