/* Rendering QA for the per-question report: every chart, every anchor, no network. */
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
  for(let i=0;i<60;i++){if(await run("document.querySelectorAll('section.study').length"))break;await delay(150)}
  const studies=await run("document.querySelectorAll('section.study').length");
  assert.equal(studies,15,'one section per study-row: '+studies);
  const rows=await run("document.querySelectorAll('table.qtable tbody tr').length");
  assert.ok(rows>=300,'per-question rows: '+rows);
  const charts=await run(`document.querySelectorAll('.echart canvas').length`);
  assert.ok(charts>=15,'charts: '+charts);
  const tiny=await run(`(()=>{const bad=[];for(const c of document.querySelectorAll('.echart canvas')){if(c.width<100||c.height<100)bad.push([c.width,c.height])}return bad})()`);
  assert.deepEqual(tiny,[]);
  const broken=await run(`(()=>{const bad=[];for(const a of document.querySelectorAll('a[href^="#"]')){const id=a.getAttribute('href').slice(1);if(id&&!document.getElementById(id))bad.push(a.getAttribute('href'))}return bad})()`);
  assert.deepEqual(broken,[]);
  const shuffled=await run(`(()=>{const t=document.body.innerText;return ['77.1%','52.8%','18.2pp','41.6pp'].filter(x=>t.includes(x))})()`);
  assert.equal(shuffled.length,4,'spot numbers present: '+JSON.stringify(shuffled));
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await delay(700);
  assert.ok(await run('document.documentElement.scrollWidth<=window.innerWidth+1'));
  const shots=[['overview','#overview'],['german','#s-german'],['dryer','#s-dryer']];
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1080,deviceScaleFactor:1,mobile:false});
  for(const [name,sel] of shots){
    await run(`document.querySelector('${sel}').scrollIntoView({block:'start'})`);await delay(700);
    const {result}=await send('Page.captureScreenshot',{format:'png'});
    fs.writeFileSync('/tmp/cards-'+name+'.png',Buffer.from(result.data,'base64'));
  }
  assert.equal(errors.length,0);assert.deepEqual(remote,[]);
  console.log('PASS: '+studies+' study sections; '+rows+' per-question rows; '+charts+' charts; anchors resolve; spot numbers; mobile viewport; no JS errors; zero remote requests.');
 }finally{if(socket)socket.close();const stopped=new Promise(r=>chrome.once('exit',r));chrome.kill();await stopped;fs.rmSync(dir,{recursive:true,force:true,maxRetries:5,retryDelay:100})}
})().catch(e=>{console.error(e);process.exitCode=1});
