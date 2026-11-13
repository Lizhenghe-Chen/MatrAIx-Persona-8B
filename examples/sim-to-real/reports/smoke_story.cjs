/* Rendering QA for the narrative report: charts, mobile layout, no network. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process'),{pathToFileURL}=require('node:url');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const dir=fs.mkdtempSync('/tmp/matraix-story-qa.');
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
  await send('Page.navigate',{url:pathToFileURL(path.join(__dirname,'story.html')).href});
  for(let i=0;i<50;i++){if(await run("document.querySelectorAll('section').length"))break;await delay(100)}
  const sections=await run("document.querySelectorAll('main section').length");
  assert.ok(sections>=10,'sections: '+sections);
  const charts=await run(`(()=>{const o={};for(const id of ['storyCompare','storyCrossover','storyExternal']){const c=document.querySelector('#'+id+' canvas');o[id]=c?[c.width,c.height]:null}return o})()`);
  for(const [name,size] of Object.entries(charts)){assert.ok(size&&size[0]>100&&size[1]>100,name+' '+JSON.stringify(size))}
  const broken=await run(`(()=>{const bad=[];for(const a of document.querySelectorAll('a[href^="#"]')){const id=a.getAttribute('href').slice(1);if(id&&!document.getElementById(id))bad.push(a.getAttribute('href'))}return bad})()`);
  assert.deepEqual(broken,[]);
  const numbers=await run(`(()=>{const t=document.body.innerText;return ['+5.6pp','+7.1%','+23.3%','14 / 14'].filter(x=>t.includes(x))})()`);
  assert.equal(numbers.length,4,'headline numbers present: '+JSON.stringify(numbers));
  const conjoint=await run(`(()=>{const t=document.body.innerText;return {stated:t.includes('为什么有的问卷'),why:t.includes('随机化就是实验本身'),kinds:t.includes('联合分析')&&t.includes('打分任务')}})()`);
  assert.ok(conjoint.stated&&conjoint.why&&conjoint.kinds,'conjoint explanation in narrative: '+JSON.stringify(conjoint));
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await delay(600);
  assert.ok(await run('document.documentElement.scrollWidth<=window.innerWidth+1'));
  assert.equal(errors.length,0);assert.deepEqual(remote,[]);
  console.log('PASS: '+sections+' sections; 3 charts; anchors resolve; headline numbers; mobile viewport; no JS errors; zero remote requests.');
 }finally{if(socket)socket.close();const stopped=new Promise(r=>chrome.once('exit',r));chrome.kill();await stopped;fs.rmSync(dir,{recursive:true,force:true,maxRetries:5,retryDelay:100})}
})().catch(e=>{console.error(e);process.exitCode=1});
