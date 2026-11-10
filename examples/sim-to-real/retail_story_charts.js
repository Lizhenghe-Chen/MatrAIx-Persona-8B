// Small, offline progressive enhancement. The initial comparison remains readable without JS.
(()=>{
 let hash=location.hash.slice(1);
 try{hash=decodeURIComponent(hash);}catch{/* An invalid bookmark must not hide the report. */}
 // Preserve links/bookmarks to all sections of the previous detailed report.
 if(hash&&!document.getElementById(hash)){
  location.replace(new URL('evidence.html'+location.hash,document.baseURI).href);
  return;
 }
 const data=JSON.parse(document.getElementById('story-data-json').textContent);
 const selector=document.getElementById('storyCase'),content=document.getElementById('storyCaseContent');
 const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function render(){
  const c=data.cases[selector.value];
  const rows=[['改之前',c.before,'before'],['改之后',c.after,'after'],['用其他真人数据的方法',c.statistics,'statistics']];
  content.innerHTML='<p class="context">'+esc(c.scope)+'</p><h3>'+esc(c.title)+'</h3><p>'+esc(c.change)+'</p>'+
   '<div class="bar-chart" role="img" aria-label="平均分布误差，条越短越好">'+rows.map(([label,value,color])=>
    '<div class="bar-row"><div class="bar-heading"><span>'+esc(label)+'</span><strong>'+value.toFixed(1)+' 点</strong></div>'+
    '<div class="bar-track"><span class="bar-fill '+color+'" style="width:'+(value*2)+'%"></span></div></div>').join('')+'</div>'+
   '<p class="takeaway"><strong>'+esc(c.verdict)+'</strong> '+esc(c.meaning)+'</p>'+
   '<p class="small">'+esc(c.note)+'</p><p><a class="text-link" href="'+esc(c.detail)+'">查看这项实验的每道题与完整比较 →</a></p>';
  document.getElementById('storyInterval').textContent='当前所选对照的误差改善：'+(c.before-c.after).toFixed(2)+'个百分点；95%区间：'+c.ci.map(x=>x.toFixed(2)).join(' 至 ')+'。正数表示改后更接近，负数表示更远。';
 }
 selector.addEventListener('change',render);render();
 window.storyReportReady=true;
})();
