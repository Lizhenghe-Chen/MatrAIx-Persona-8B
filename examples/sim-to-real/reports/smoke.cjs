/* Real Chrome rendering and interaction QA; no model calls or remote page loads. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process'),{pathToFileURL}=require('node:url');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const dir=fs.mkdtempSync('/tmp/matraix-overview-qa.');
 const chrome=spawn(process.env.CHROME_BIN||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['--headless','--no-first-run','--disable-background-networking','--remote-debugging-port=0','--user-data-dir='+dir,'about:blank'],{stdio:'ignore'});
 let socket;
 try{
  const portfile=dir+'/DevToolsActivePort';for(let i=0;!fs.existsSync(portfile)&&i<60;i++)await delay(200);
  const port=fs.readFileSync(portfile,'utf8').split('\n')[0];
  const tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
  socket=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise(r=>socket.addEventListener('open',r,{once:true}));
  let id=0;const pending=new Map(),errors=[],remote=[];
  socket.addEventListener('message',e=>{const msg=JSON.parse(e.data);if(msg.id){pending.get(msg.id)?.(msg);pending.delete(msg.id)}else if(msg.method==='Runtime.exceptionThrown')errors.push(msg.params);else if(msg.method==='Network.requestWillBeSent'&&/^https?:/.test(msg.params.request.url))remote.push(msg.params.request.url)});
  const send=(method,params={})=>new Promise(r=>{const key=++id;pending.set(key,r);socket.send(JSON.stringify({id:key,method,params}))});
  const run=async(expression)=>{const v=await send('Runtime.evaluate',{expression,returnByValue:true});assert.ok(!v.error&&!v.result.exceptionDetails,JSON.stringify(v));return v.result.result.value};
  await send('Runtime.enable');await send('Page.enable');await send('Network.enable');
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1080,deviceScaleFactor:1,mobile:false});
  await send('Page.navigate',{url:pathToFileURL(path.join(__dirname,'index.html')).href});
  for(let i=0;i<40;i++){if(await run("document.querySelectorAll('#question-select option').length===13"))break;await delay(100)}
  assert.equal(await run("document.querySelectorAll('#question-select option').length"),13);
  await run("document.documentElement.style.scrollBehavior='auto'");
  const results=await run(`(()=>{let n=0;for(let i=0;i<13;i++){questionSelect.value=String(i);for(const method of ['只选一项','保留概率','真人数据校准','真人统计模型']){methodSelect.value=method;drawQuestion();const q=questions[i];if(document.querySelectorAll('.distribution-option').length!==q.options.length)throw Error('Option count');if(!document.getElementById('question-metric').textContent.includes(q.methods[method].error.toFixed(2)))throw Error('Metric');if(![...document.querySelectorAll('.dist-row b')].every((x,j)=>x.textContent===format(j%2?q.methods[method].shares[Math.floor(j/2)]:q.real[Math.floor(j/2)])))throw Error('Share');n++;}}return n})()`);
  assert.equal(results,52);
  await run("questionSelect.value='9';methodSelect.value='只选一项';drawQuestion();window.scrollTo(0,0)");await delay(150);
  const screenshot=async(name)=>{const v=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync('/tmp/matraix-overview-'+name+'.png',Buffer.from(v.result.data,'base64'))};
  await screenshot('desktop');
  await run("document.querySelector('#probability').scrollIntoView();");await delay(200);await screenshot('charts');
  await run("document.querySelector('#questions').scrollIntoView();");await delay(200);await screenshot('distribution');
  await run("document.querySelectorAll('details').forEach(x=>x.open=true)");
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  assert.ok(await run('document.documentElement.scrollWidth<=window.innerWidth+1'));
  await run("window.scrollTo(0,0)");await delay(200);await screenshot('mobile');
  await run("document.querySelector('#questions').scrollIntoView();");await delay(200);await screenshot('mobile-distribution');
  await run("document.querySelector('#model').scrollIntoView();");await delay(200);await screenshot('mobile-model');
  assert.equal(errors.length,0);assert.deepEqual(remote,[]);
  console.log('PASS: 52 question/method combinations; all displayed percentages; mobile viewport; no JS errors; zero remote requests. Screenshots: /tmp/matraix-overview-*.png');
 }finally{if(socket)socket.close();const stopped=new Promise(r=>chrome.once('exit',r));chrome.kill();await stopped;fs.rmSync(dir,{recursive:true,force:true,maxRetries:5,retryDelay:100})}
})().catch(e=>{console.error(e);process.exitCode=1});
