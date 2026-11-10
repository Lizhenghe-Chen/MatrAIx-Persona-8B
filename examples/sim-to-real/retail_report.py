"""Build the offline retail experiment report from aggregate scores."""
import json
from pathlib import Path
import tempfile

from retail_findings import findings

BASE = Path(__file__).parent / "study/08_购物预测"
LABELS = {
    "basic_choice": "基础背景 · 单选", "rich_choice": "补充背景 · 单选",
    "basic_probability": "基础背景 · 概率", "rich_probability": "补充背景 · 概率",
    "reverse_probability": "概率 · 反转选项顺序", "shuffle_probability": "概率 · 交换附加背景",
    "rich_probability_argmax": "概率答卷只取最高项", "statistics": "年龄学历统计基线",
}
QUESTIONS = dict(zip(
    ("SHOP6A", "SHOP6B", "SHOP6C", "SHOP6D", "SHOP6E", "SHOP6F", "SHOP6G",
     "SHOP7A", "SHOP7B", "SHOP7C", "SHOP12", "SHOP20B", "SHOP20C"),
    ("亲自看或试用商品的重要性", "阅读网上评价的重要性", "不用到店就能网购的重要性",
     "向多家商家比价的重要性", "能询问商品细节的重要性", "听取熟人建议的重要性",
     "向熟悉的商家购买的重要性", "评价对商品安全的帮助", "评价对购买信心的帮助",
     "评价对商家负责的帮助", "首次购买时看评价的频率", "在实体店用手机查更低价",
     "在实体店用手机查商品评价"),
))
STAGES = {"pilot": "48 人开发集", "formal": "240 人独立评估"}


def main():
    scores = {stage: json.loads((BASE / f"pew-{stage}-score.json").read_text())
              for stage in STAGES if (BASE / f"pew-{stage}-score.json").exists()}
    amazon = json.loads((BASE / "amazon-development.json").read_text())
    model_scores = BASE / "amazon-development-score.json"
    if model_scores.exists():
        amazon["development_only"] = json.loads(model_scores.read_text())["summary"]
    def available(stem, stages):
        return {stage: json.loads(path.read_text()) for stage in stages
                if (path := BASE / f"{stem.format(stage=stage)}.json").exists()}
    repeat_path = BASE / "amazon-repeat-diagnostics.json"
    repeat_diag = json.loads(repeat_path.read_text()) if repeat_path.exists() else None
    extra = {
        "repeatDiagnostics": repeat_diag,
        "shoes": available("shoes-{stage}-score", ("development", "test")),
        "amazonCategory": available("amazon-{stage}-score", ("development", "test")),
        "amazonMix": available("amazon-mix-{stage}-score", ("development", "test")),
        "calibration": available("pew-{stage}-calibration", ("pilot", "formal")),
    }
    payload = json.dumps({"scores": scores, "amazon": amazon, "labels": LABELS, "extra": extra,
                          "questions": QUESTIONS, "stages": STAGES}, ensure_ascii=False).replace("<", "\\u003c")
    sensitivity_path = BASE / "pew-answer-sampling-sensitivity.json"
    sensitivity = ""
    if sensitivity_path.exists():
        r = json.loads(sensitivity_path.read_text())
        low, median, high = r["sampling_error_pp"]
        sensitivity = (f"<p><strong>必须保留一人一票时。</strong> 在相同的 {r['people']} 人预测上，"
                       f"独立按概率抽取每题答案，重复 {r['replicates']:,} 次。分布误差中位数 {median:.2f}，"
                       f"抽样的中央 95% 范围 {low:.2f}–{high:.2f} 个百分点。"
                       f"总取最高项的误差为 {r['argmax_error_pp']:.2f}。按概率抽答的逐人正确率中位数"
                       f"为 {100*r['sampling_accuracy'][1]:.1f}%。该对照用已固定的评估预测做事后敏感性分析，"
                       "适用于模拟单题比例。每题独立抽样无法恢复同一个人各题答案间的关联。</p>")
    ready = BASE / "运行核验.json"
    audit = json.loads(ready.read_text()) if ready.exists() else {}
    title = "购物预测实验报告" if audit.get("all_independent_scores_verified") else "购物预测实验 · 阶段报告"
    scope_names = {"pew":"Pew 网购问卷", "shoes":"美国运动鞋", "amazon_category":"Amazon 品类购买",
                   "amazon_mix":"Amazon 价格、支出与复购"}
    progress = []
    for key, check in audit.get("independent_score_verification", {}).items():
        phase = "formal" if key == "pew" else "test"
        run = audit["completion"][key][phase]
        actual = min(run["valid"].values())
        expected = run["expected_per_arm"]
        errors = sum(run["failed_attempts_in_current_checkpoints"].values())
        status = "通过" if all(check[k] for k in ("completion_gate","score_exists","coverage_matches")) else "等待评估"
        progress.append(f"<tr><td>{scope_names[key]}</td><td>{actual}/{expected}</td><td>{errors}</td><td>{status}</td></tr>")
    decisions = ""
    if audit.get("all_independent_scores_verified"):
        decisions = """<section><h2>按用途选择方法</h2>
<div style="overflow:auto"><table><thead><tr><th>要回答的问题</th><th>采用的方式</th><th>验收重点</th></tr></thead>
<tbody>
<tr><td>一群人会怎样回答购物问卷？</td><td>需要用模型时，汇总完整选项概率。有同题真人数据时，先比较历史统计。</td><td>查看各选项份额与少数选项。生成一人一票时可按概率抽取，再查群体分布。</td></tr>
<tr><td>改产品材质、功能和价格，有多少人更喜欢？</td><td>用原商品对及商品属性统计模型做对照。</td><td>另验收只变一个属性时的影响。整体评分分布与属性取舍使用不同指标。</td></tr>
<tr><td>哪些账户之后会购买某个品类？</td><td>近期历史是主要预测。小权重模型组合可作为特定品类任务的候选。</td><td>组合的逐账户增益较小，需核对成本、比例误差和其他时间窗的复验。</td></tr>
<tr><td>之后买什么价位、花在哪些品类、是否复购同款？</td><td>优先使用近期购买历史。</td><td>同时查群体份额与逐账户误差。复购总比例接近时，仍检查每个账户的概率。</td></tr>
</tbody></table></div>
<p>可复用设置、失败的对照及适用范围见<a href="../05_优化记录/优化文档.md">优化文档</a>。</p></section>"""
    progress_html = ("<section><h2>正式评估完成率</h2><p>下表为生成报告时各组的最小有效答卷数。"
                     "每组达到 98% 后，再对共同受访者评分。失败尝试统计来自当前检查点。</p>"
                     "<div style='overflow:auto'><table><thead><tr><th>实验</th><th>有效数／计划数</th>"
                     "<th>失败尝试</th><th>评分核验</th></tr></thead><tbody>"+"".join(progress)+
                     "</tbody></table></div></section>") if progress else ""
    page = '''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MatrAIx · REPORT_TITLE</title>
<style>
body{margin:0;background:#f6f7f2;color:#17352e;font:17px/1.7 system-ui,sans-serif}
main{max-width:1080px;margin:auto;padding:28px 18px}h1{line-height:1.2}section{background:white;padding:18px;border:1px solid #d4e1da;border-radius:12px;margin:20px 0}
.chart{height:430px;width:100%}select{padding:7px;font:inherit;max-width:100%}label{display:inline-block;margin:8px 14px 8px 0}
small{color:#54655e}a{color:#12675d} table{border-collapse:collapse;width:100%} th,td{padding:8px;text-align:left;border-bottom:1px solid #ddd}
</style><script src="vendor/echarts.min.js"></script>
<main><h1>REPORT_TITLE</h1>
<p>比较同一批真人、同一道题在不同模型设置下的回答。开发集用来排查问题，独立评估用来检验改善能否复现。</p>
DECISIONS
FINDINGS
PROGRESS
<section><h2>Pew 网购问卷</h2><p>选自 2015 年网络问卷的 13 个购物问项。分布误差比较每个选项的真人份额和模拟份额，单位为百分点。Brier 分数衡量逐人的概率预测误差，越低越好。</p>
<label>样本 <select id="stage"></select></label><label>指标 <select id="metric"><option value="tv_pp">平均分布误差（百分点）</option><option value="brier">逐人概率误差</option><option value="accuracy">最可能答案正确率（%）</option></select></label>
<p id="status"></p><div id="overview" class="chart" role="img" aria-label="各设置总体指标"></div>
<h3>每道题的选项分布</h3>
<label>问题 <select id="question"></select></label><label>模拟设置 <select id="arm"></select></label>
<details><summary>查看英文题干</summary><p id="questionText"></p></details><div id="distribution" class="chart" role="img" aria-label="真人与模拟的选项份额"></div>
<p id="detail"></p>
<div style="overflow:auto"><table><thead><tr><th>选项</th><th>真人占比</th><th>预测占比</th><th>取最可能项时的召回率</th></tr></thead><tbody id="optionRows"></tbody></table></div>
<p><small>召回率表示实际选择该项的人中，预测最可能答案也为该项的人所占比例。没有该选项的真人时显示“无有效样本”。</small></p>
SAMPLING
<h3>同一批人上的配对比较</h3>
<p>正值表示后一个设置的误差更小。区间按受访者重抽样计算。</p>
<div style="overflow:auto"><table><thead><tr><th>比较</th><th>改善（百分点）</th><th>95% 区间</th></tr></thead><tbody id="contrasts"></tbody></table></div>
<h3>逐题看改动带来的变化</h3>
<label>配对比较 <select id="contrast"></select></label><div id="questionDelta" class="chart" role="img" aria-label="各题误差改善幅度"></div>
<h3>按年龄或学历查看误差</h3><p>每组每题至少 20 名有效受访者。图中对符合条件的题等权平均。</p>
<label>分组 <select id="groupField"><option value="Age group">年龄</option><option value="Education">学历</option></select></label>
<div id="groups" class="chart" role="img" aria-label="分组分布误差"></div>
<h3>逐人概率与实际发生率</h3><p>点越靠近虚线，表示预测概率越接近实际发生率。</p>
<div id="reliability" class="chart" role="img" aria-label="概率校准散点图"></div>
<p>原问卷与统计说明见 <a href="https://www.pewresearch.org/dataset/american-trends-panel-wave-13/">Pew 第 13 波</a>。</p></section>
<section><h2>Amazon 真实购买 · 品类预测误差</h2><p>用 2022 年 10 月前的历史预测第四季度各品类是否购买。60 个账户用于开发，另外 500 个账户已留作独立评估。目标范围中的空记录记为该品类在发布记录中未购买。</p>
<label>样本 <select id="amazonScoreStage"></select></label>
<label>指标 <select id="amazonMetric"><option value="brier">逐账户 Brier 分数</option><option value="mean_category_prevalence_error_pp">平均品类比例误差（百分点）</option></select></label>
<div id="amazon" class="chart" role="img" aria-label="Amazon 模型与统计基线的预测误差"></div>
<p>每个品类分别预测是否发生购买。图中 Brier 分数与问卷的多选项 Brier 定义不同。<a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC11091104/">Amazon 数据论文</a></p></section>
<section id="shoesPanel"><h2>运动鞋购买意愿</h2>
<p>每个人看到 8 对商品，分别给两款鞋 1–7 分。统计模型用独立样本学习商品属性、另一款鞋的价格与评分等信息，以及同样可用的真人背景。</p>
<p id="shoesStatus"></p>
<label>总体指标 <select id="shoeMetric"><option value="tv_pp">分布误差（百分点）</option><option value="brier">逐人概率误差</option><option value="rating_mae">平均评分绝对误差（分）</option></select></label>
<div id="shoeOverview" class="chart" role="img" aria-label="运动鞋各设置总体误差"></div>
<label>设置 <select id="shoeArm"></select></label><label>实验设计 <select id="shoeDesign"></select></label>
<div id="shoeDist" class="chart" role="img" aria-label="运动鞋购买评分分布"></div>
<h3>商品对评分差</h3>
<label>配对口径 <select id="gapScope"><option value="descriptive">全部组的价格与材质差异</option><option value="controlled">只变一个属性的配对</option></select></label>
<p id="gapDetail"></p>
<div id="shoeGaps" class="chart" role="img" aria-label="便宜款及环保款相对评分差"></div>
<div style="overflow:auto"><table><thead><tr><th>比较</th><th>分布误差改善</th><th>95% 区间</th><th>逐人误差改善</th><th>95% 区间</th></tr></thead><tbody id="shoeContrasts"></tbody></table></div>
<p><small>评分差按同一商品对计算。价格或材质不同的商品对也可能有其他属性差异，因此这里呈现的是观察到的取舍方向。</small> <a href="https://doi.org/10.1017/pan.2021.30">运动鞋原研究</a></p></section>
<section id="calibrationPanel"><h2>Pew 概率校准</h2><p>用开发集调整每道题的概率偏移，再到独立样本检验。开发集的分布误差对齐是校准机制本身的结果。逐人误差和独立样本决定它是否有预测价值。</p>
<p id="calibrationStatus"></p><div id="calibrationPlot" class="chart" role="img" aria-label="校准后群体与逐人指标"></div></section>
<section id="amazonFormalPanel"><h2>Amazon 品类购买预测</h2><p id="categoryStatus"></p>
<label>预测方法 <select id="categoryArm"></select></label><div id="categoryPlot" class="chart" role="img" aria-label="各品类购买发生率"></div>
<h3>按历史购买条目数分组</h3><p>分界取自开发账户的历史购买条目数。正值表示比近期历史基线更好。分组结果用于诊断，主判断以全体留出样本为准。</p>
<div id="categorySubgroups" class="chart" role="img" aria-label="历史记录量分组的逐账户预测改善"></div>
<div style="overflow:auto"><table><thead><tr><th>历史条目数</th><th>账户数</th><th>统计与模型组合的改善</th><th>95% 区间</th></tr></thead><tbody id="categorySubgroupRows"></tbody></table></div></section>
<section id="amazonMixPanel"><h2>Amazon 价格、支出和复购</h2><p id="mixStatus"></p>
<label>任务 <select id="mixTask"></select></label><label>预测方法 <select id="mixArm"></select></label>
<div id="mixPlot" class="chart" role="img" aria-label="消费结构与复购分布"></div><p id="mixMetric"></p>
<div id="repeatDiagnosis" hidden><h3>为什么复购总比例接近，逐人误差反而更大</h3><p id="repeatNote"></p>
<div id="repeatReliability" class="chart" role="img" aria-label="同款复购概率与实际发生率"></div></div></section>
<section><h2>试跑中发现并处理的问题</h2><ul>
<li>单选输出有时返回数字字符串。解码接受整数或等价数字字符串，两者都要符合实际选项范围。</li>
<li>保留各选项概率可以改善群体分布。对同一批概率取最高项，能区分这种改善来自汇总方式还是最高项判断。</li>
<li>增加真人背景、交换附加背景、倒转选项位置分别作为独立对照。开发集结果用于提出假设。</li>
<li>Amazon 先验用 2020 和 2021 年第四季度计算。预测输入和统计先验均早于 2022 年第四季度。</li>
</ul><p>运动鞋数据已按原实验设计准备，保留成对商品和原属性顺序。阶段结果按开发与独立评估标明。</p>
<p>既有研究在美国社区调查上观察到选项位置和标签的影响。本实验用倒转原选项做独立检查，并同时比较完整概率与最高项。<a href="https://proceedings.neurips.cc/paper_files/paper/2024/hash/515c62809e0a29729d7eec26e2916fc0-Abstract-Conference.html">Dominguez-Olmedo 等，2024</a></p>
</section>
<section><h2>读结果时采用的口径</h2>
<ul><li>购物问卷的真人参照是 2015 年 Pew 网络受访者。运动鞋参照是原美国线上招募样本，四个原设计等额评估。Amazon 参照是在观察期内有足够历史购买记录的参与账户。</li>
<li>总体分布误差衡量群体比例。逐人概率误差对照每人的实际答案或消费结构。只有前者改善时，应用范围限于群体估计。</li>
<li>运动鞋测试的是情境中的购买意愿。Amazon 测实际记录里的购买结果，使用每账户等权的品类、价格和支出构成。价格或金额不可用的季度纳入专门类别。</li>
<li>本轮用真人背景与内网 Qwen 测预测配置。公开材料可能被模型见过。合成人格的构造、当期市场份额和平台真实转化需要各自的验证。</li></ul></section>
<section><h2>资料与复算</h2><p>运行参数、队列和评分口径见<a href="README.md">实验记录</a>。源文件哈希、样本划分和答卷格式的核验见<a href="运行核验.json">运行核验</a>。图表可离线打开。</p></section>
</main><script>
const data = PAYLOAD;
const el = id => document.getElementById(id);
const fill = (node, entries) => { node.replaceChildren(...entries.map(([key,label]) => new Option(label,key))); };
fill(el("stage"),Object.keys(data.scores).map(key=>[key,data.stages[key]]));
fill(el("question"),Object.entries(data.questions));
const overview=echarts.init(el("overview")), distribution=echarts.init(el("distribution")), amazon=echarts.init(el("amazon")), reliability=echarts.init(el("reliability"));
const number=x=>Number(x.toFixed(2));
const questionDelta=echarts.init(el("questionDelta")),groups=echarts.init(el("groups"));
function drawContrast(){
 const stage=data.scores[el("stage").value], row=stage.contrasts[Number(el("contrast").value)];
 const old=stage.items[row.from], next=stage.items[row.to];
 const scores=old.map((item,i)=>number(item.tv_pp-next[i].tv_pp));
 questionDelta.setOption({tooltip:{trigger:"axis",valueFormatter:x=>x+" 个百分点"},
 grid:{left:155,right:35},xAxis:{type:"value",name:"改善"},yAxis:{type:"category",data:old.map(x=>data.questions[x.question]),
 inverse:true,axisLabel:{width:135,overflow:"truncate"}},
 series:[{type:"bar",data:scores.map(v=>({value:v,itemStyle:{color:v>=0?"#287e70":"#aa5b4f"}}))}]},true);
}
function drawGroups(){
 const stage=data.scores[el("stage").value], field=el("groupField").value, arm=el("arm").value;
 const rows=(stage.subgroups[arm]||[]).filter(x=>x.field===field);
 const baseline=(stage.subgroups.statistics||[]).filter(x=>x.field===field);
 groups.setOption({title:rows.length?{}:{text:"本组暂无达到人数要求的题",left:"center",top:"middle",textStyle:{fontSize:15}},
 tooltip:{trigger:"axis",valueFormatter:x=>x+" 个百分点"},legend:{data:["当前设置","统计基线"]},
 grid:{bottom:90,left:45,right:25},xAxis:{type:"category",data:rows.map(x=>x.group+" · "+x.people+" 人"),
 axisLabel:{interval:0,width:95,overflow:"break"}},yAxis:{type:"value"},
 series:[{name:"当前设置",type:"bar",data:rows.map(x=>number(x.tv_pp))},
 {name:"统计基线",type:"bar",data:rows.map(x=>number(baseline.find(y=>y.group===x.group).tv_pp))}]},true);
}
function render() {
 const stage=data.scores[el("stage").value], metric=el("metric").value, old=el("arm").value;
 fill(el("arm"),Object.keys(stage.summaries).map(key=>[key,data.labels[key]]));
 if(old in stage.summaries) el("arm").value=old;
 el("status").textContent="共同评分人数 "+stage.common_people+"。各组使用同一批人和同一套题。";
 const labels=Object.keys(stage.summaries).map(key=>data.labels[key]);
 const vals=Object.values(stage.summaries).map(row=>number(row[metric]*(metric==="accuracy"?100:1)));
 overview.setOption({tooltip:{trigger:"axis"},grid:{left:175,right:40},xAxis:{type:"value"},yAxis:{type:"category",data:labels,inverse:true},
 series:[{type:"bar",data:vals,itemStyle:{color:"#287e70"},label:{show:true,position:"right"}}]});
 const rows=stage.contrasts.map(row=>{
   const tr=document.createElement("tr");
   for(const value of [data.labels[row.from]+" 到 "+data.labels[row.to],number(row.tv_improvement_pp),
      row.tv_95_interval.map(number).join(" 至 ")]){
     const td=document.createElement("td");td.textContent=value;tr.append(td);
   }
   return tr;
 });
 el("contrasts").replaceChildren(...rows);
 fill(el("contrast"),stage.contrasts.map((row,i)=>[String(i),data.labels[row.from]+" 到 "+data.labels[row.to]]));
 el("contrast").value="3";
 drawContrast();
 drawQuestion();
}
const optionNames={"Extremely important":"非常重要","Somewhat important":"比较重要","Not too important":"不太重要",
 "Not important at all":"完全不重要","A lot":"帮助很大","Some":"有些帮助","A little":"帮助很小","Not at all":"完全没有帮助",
 "Always or almost always":"总是或几乎总是","Sometimes":"有时","Never":"从不","Yes":"是","No":"否"};
function drawQuestion(){
 drawGroups();
 const stage=data.scores[el("stage").value], q=el("question").value, arm=el("arm").value;
 const row=stage.items[arm].find(item=>item.question===q);
 el("questionText").textContent=row.question_text;
 const displayOptions=row.options.map(o=>optionNames[o]||o);
 const pct=v=>number(v*100)+"%";
 el("optionRows").replaceChildren(...displayOptions.map((option,i)=>{
   const tr=document.createElement("tr");
   for(const value of [option,pct(row.real[i]),pct(row.simulated[i]),
     row.recall[i]==null?"无有效样本":pct(row.recall[i])]){
     const td=document.createElement("td");td.textContent=value;tr.append(td);
   }
   return tr;
 }));
 const concentration=stage.summaries[arm].concentration_counts;
 el("detail").textContent="分布误差 "+number(row.tv_pp)+" 个百分点，有效真人 "+row.valid_real_people+
 " 人。全部 13 题中，单项份额达到 95% 的有 "+concentration["0.95"]+" 题。";
 if(stage.calibration){
  const points=stage.calibration[arm].map(x=>[number(x.mean_probability*100),number(x.observed_frequency*100),number(x.weight*100)]);
  reliability.setOption({tooltip:{formatter:e=>e.seriesType==="scatter"?
   "预测 "+e.data[0]+"% · 实际 "+e.data[1]+"% · 权重 "+e.data[2]+"%":""},
   xAxis:{type:"value",min:0,max:100,name:"预测概率",nameLocation:"middle",nameGap:32,axisLabel:{formatter:"{value}%"}},
   yAxis:{type:"value",min:0,max:100,name:"实际频率",axisLabel:{formatter:"{value}%"}},
   series:[{type:"line",data:[[0,0],[100,100]],symbol:"none",lineStyle:{type:"dashed",color:"#98a39c"}},
     {type:"scatter",data:points,symbolSize:p=>Math.max(5,Math.sqrt(p[2])*3),itemStyle:{color:"#7153a6"}}]},true);
 }
 distribution.setOption({tooltip:{trigger:"axis",valueFormatter:v=>v+"%"},legend:{data:["真人","模拟"]},
 grid:{left:42,right:18,bottom:105},xAxis:{type:"category",data:displayOptions,axisLabel:{interval:0,rotate:18,width:105,overflow:"break"}},
 yAxis:{type:"value",min:0,max:100,axisLabel:{formatter:"{value}%"}},
 series:[{name:"真人",type:"bar",data:row.real.map(x=>number(x*100)),itemStyle:{color:"#287e70"}},
 {name:"模拟",type:"bar",data:row.simulated.map(x=>number(x*100)),itemStyle:{color:"#7153a6"}}]});
}
["stage","metric"].forEach(id=>el(id).addEventListener("change",render));
["arm","question"].forEach(id=>el(id).addEventListener("change",drawQuestion));
const baseNames={population:"总体历史比例",history:"全部历史频率",recent:"最近四季度频率",history_only:"模型读购买历史",historical_anchor:"模型加统计估计",blend:"统计与模型加权组合"};
const amazonStages={development:data.amazon.development_only};
if(data.extra.amazonCategory.test) amazonStages.test=data.extra.amazonCategory.test.summary;
fill(el("amazonScoreStage"),Object.keys(amazonStages).map(k=>[k,k==="test"?"500 个独立账户":"60 个开发账户"]));
if(amazonStages.test) el("amazonScoreStage").value="test";
function drawAmazonScore(){
 const base=Object.entries(amazonStages[el("amazonScoreStage").value]);
 const metric=el("amazonMetric").value;
 amazon.setOption({tooltip:{trigger:"axis"},grid:{left:155,right:55},xAxis:{type:"value"},
  yAxis:{type:"category",data:base.map(([k])=>baseNames[k]),inverse:true},
  series:[{type:"bar",data:base.map(([,row])=>Number(row[metric].toFixed(4))),
   itemStyle:{color:"#287e70"},label:{show:true,position:"right"}}]},true);
}
["amazonScoreStage","amazonMetric"].forEach(k=>el(k).addEventListener("change",drawAmazonScore));
drawAmazonScore();
if(data.scores.formal) el("stage").value="formal";
render();

el("contrast").addEventListener("change",drawContrast);
el("groupField").addEventListener("change",drawGroups);
const charts=[overview,distribution,amazon,reliability,questionDelta,groups];
const last = (obj, finalKey, devKey) => obj[finalKey] || obj[devKey];
const make = id => { const chart=echarts.init(el(id)); charts.push(chart); return chart; };
function paired(chart, labels, actual, forecast, formatPercent=true) {
 const conv=x=>number(x*(formatPercent?100:1));
 chart.setOption({tooltip:{trigger:"axis",valueFormatter:v=>v+(formatPercent?"%":"")},legend:{data:["真人","预测"]},
 grid:{left:55,right:18,bottom:110},xAxis:{type:"category",data:labels,axisLabel:{interval:0,rotate:20,width:95,overflow:"break"}},
 yAxis:{type:"value",axisLabel:{formatter:formatPercent?"{value}%":"{value}"}},
 series:[{name:"真人",type:"bar",data:actual.map(conv),itemStyle:{color:"#287e70"}},
 {name:"预测",type:"bar",data:forecast.map(conv),itemStyle:{color:"#7153a6"}}]},true);
}
const shoes=last(data.extra.shoes,"test","development");
if(shoes){
 const ch=make("shoeDist"), gap=make("shoeGaps"), summary=make("shoeOverview");
 const names={...data.labels,statistics:"商品属性和背景统计基线",attitude_probability:"补充真人态度 · 概率",calibrated_rating:"校准单选评分",blend:"统计与校准评分组合"};
 const designs={"treat random":"环保属性 · 多属性随机","control random":"缓震属性 · 多属性随机",
 "treat constrained":"仅改变环保属性","control constrained":"仅改变缓震属性"};
 const shoeSettings=Object.entries(shoes.summary);
 fill(el("shoeArm"),shoeSettings.map(([k])=>[k,names[k]]));
 function drawShoeSummary(){
   const metric=el("shoeMetric").value;
   summary.setOption({tooltip:{trigger:"axis"},grid:{left:185,right:38},xAxis:{type:"value"},
    yAxis:{type:"category",inverse:true,data:shoeSettings.map(([k])=>names[k])},
    series:[{type:"bar",itemStyle:{color:"#287e70"},label:{show:true,position:"right"},
      data:shoeSettings.map(([,r])=>number(r[metric]))}]},true);
 }
 el("shoeMetric").addEventListener("change",drawShoeSummary);drawShoeSummary();
 el("shoeContrasts").replaceChildren(...shoes.contrasts.map(row=>{
   const tr=document.createElement("tr");
   for(const value of [names[row.from]+" 到 "+names[row.to],number(row.tv_improvement_pp),
     row.tv_interval.map(number).join(" 至 "),row.brier_improvement.toFixed(3),row.brier_interval.map(x=>x.toFixed(3)).join(" 至 ")]){
      const td=document.createElement("td");td.textContent=value;tr.append(td);
   }
   return tr;
 }));
 el("shoeArm").value="attitude_probability";
 fill(el("shoeDesign"),[["all","全部实验组"],...Object.entries(designs)]);
 el("shoesStatus").textContent=(shoes.stage==="test"?"独立评估":"开发集")+"，共同评分 "+shoes.people+" 人、"+shoes.paired_tasks+" 对商品。";
 function drawShoes(){
   const r=shoes.summary[el("shoeArm").value], g=el("shoeDesign").value;
   paired(ch,["1 很不可能","2 不太可能","3 有点不可能","4 中立","5 有点可能","6 可能","7 很可能"],
     g==="all"?shoes.real.distribution:shoes.real.design_distributions[g],
     g==="all"?r.distribution:r.design_distributions[g]);
   const controlled=shoes.controlled_attribute_effects;
   if(el("gapScope").value==="controlled" && controlled){
     const methods=Object.values(controlled), arm=el("shoeArm").value;
     paired(gap,["只增加环保材质","只增加缓震"],methods.map(x=>x.real_effect),methods.map(x=>x.methods[arm].effect),false);
     el("gapDetail").textContent=methods.map((x,i)=>{
       const effect=x.methods[arm];
       return ["环保材质","缓震"][i]+" "+x.pairs+" 对。模型减真人 "+number(effect.minus_real)+" 分，95% 区间 "+
       effect.minus_real_95_interval.map(number).join(" 至 ")+"。";
     }).join(" ");
   }else{
     paired(gap,["较便宜款减较贵款","环保款减普通款"],
       [shoes.real.cheaper_minus_expensive,shoes.real.eco_minus_regular],[r.cheaper_minus_expensive,r.eco_minus_regular],false);
     el("gapDetail").textContent="全部实验组中的配对均值，多个属性可能同时变化。";
   }
 }
 ["shoeArm","shoeDesign","gapScope"].forEach(k=>el(k).addEventListener("change",drawShoes)); drawShoes();
} else el("shoesStatus").textContent="等待开发集完成率检查与评分。";
const cal=last(data.extra.calibration,"formal","pilot");
if(cal){
 const names={statistics_rich:"完整背景统计模型",raw_model:"原始模型概率",calibrated_model:"校准模型概率",blend:"统计与校准概率组合"};
 const rows=Object.entries(cal.summary);
 el("calibrationStatus").textContent=(cal.stage==="formal"?"独立评估":"开发集")+" "+cal.people+" 人。组合中的模型权重为 "+number(cal.model_weight*100)+"%。";
 make("calibrationPlot").setOption({tooltip:{trigger:"axis"},legend:{data:["分布误差（百分点）","逐人误差"]},
 grid:{left:45,right:45,bottom:85},xAxis:{type:"category",data:rows.map(([k])=>names[k]),axisLabel:{interval:0,rotate:12}},
 yAxis:[{type:"value"},{type:"value"}],series:[{type:"bar",name:"分布误差（百分点）",data:rows.map(([,r])=>number(r.tv_pp))},
 {type:"bar",name:"逐人误差",yAxisIndex:1,data:rows.map(([,r])=>Number(r.brier.toFixed(3)))}]});
} else el("calibrationPanel").hidden=true;
const categories=last(data.extra.amazonCategory,"test","development");
const readable={ABIS_BOOK:"图书","Unknown category":"类别未知",PET_FOOD:"宠物食品",SHIRT:"上衣",NUTRITIONAL_SUPPLEMENT:"营养补充剂",
 GIFT_CARD:"礼品卡",ELECTRONIC_CABLE:"电子线缆",MEDICATION:"药品",HEALTH_PERSONAL_CARE:"健康个护",
 PANTS:"裤装",VEGETABLE:"蔬菜",FOOD:"食品",Other:"其他品类","no positive measured spend":"无正金额支出",
 "no usable priced purchases":"无可用价格","no repeated product":"未复购同款","at least one repeated product":"至少复购一款"};
if(categories){
 const ch=make("categoryPlot");
 el("categoryStatus").textContent=(categories.sample==="test"?"独立评估":"开发集")+" "+categories.common_accounts+" 个账户。每个品类独立计算，份额可相加超过 100%。";
 fill(el("categoryArm"),Object.keys(categories.summary).map(k=>[k,baseNames[k]]));
 el("categoryArm").value="history_only";
 const draw=()=>paired(ch,categories.categories.map(k=>readable[k]||k),categories.actual_prevalence,
   categories.summary[el("categoryArm").value].forecast_prevalence);
 el("categoryArm").addEventListener("change",draw);draw();
 const groups=categories.history_density_subgroups||[];
 const rows=groups.map(group=>{
   const tr=document.createElement("tr"), result=group.gains_vs_recent.blend;
   for(const value of [group.history_lines_min+"–"+group.history_lines_max,group.accounts,
      result.brier_gain.toFixed(5),result.interval.map(x=>x.toFixed(5)).join(" 至 ")]){
      const td=document.createElement("td");td.textContent=value;tr.append(td);
   }
   return tr;
 });
 el("categorySubgroupRows").replaceChildren(...rows);
 const methods=["history_only","historical_anchor","blend"];
 make("categorySubgroups").setOption({tooltip:{trigger:"axis"},legend:{data:methods.map(k=>baseNames[k])},
  grid:{left:60,right:18,bottom:75},xAxis:{type:"category",data:groups.map(g=>g.history_lines_min+"–"+
   g.history_lines_max+" 条 · "+g.accounts+" 个账户"),axisLabel:{interval:0,width:100,overflow:"break"}},
  yAxis:{type:"value",name:"Brier 改善"},series:methods.map(k=>({type:"bar",name:baseNames[k],
   data:groups.map(g=>Number(g.gains_vs_recent[k].brier_gain.toFixed(5)))}))});
} else el("amazonFormalPanel").hidden=true;
const mix=last(data.extra.amazonMix,"test","development");
if(mix){
 const ch=make("mixPlot");
 el("mixStatus").textContent=(mix.stage==="test"?"独立评估":"开发集")+" "+mix.accounts+" 个账户。每个账户等权。";
 fill(el("mixTask"),[["price","商品单价带"],["spend","各品类支出占比"],["repeat","同款商品复购"]]);
 fill(el("mixArm"),[["recent","最近四季度"],["seasonal","往年同季度"],["model","内网模型"],["blend","统计与模型组合"]]);el("mixArm").value="model";
 const draw=()=>{const task=mix.tasks[el("mixTask").value], r=task.results[el("mixArm").value];
  paired(ch,task.labels.map(k=>readable[k]||k),task.actual,r.shares);
  el("mixMetric").textContent="平均结构误差 "+number(r.tv_pp)+" 个百分点，逐人平方误差 "+r.brier.toFixed(4)+"。";
 };
 ["mixTask","mixArm"].forEach(k=>el(k).addEventListener("change",draw));draw();
} else el("mixStatus").textContent="等待开发集完成率检查与评分。";
const repeatDiag=data.extra.repeatDiagnostics;
if(repeatDiag){
 const methods=repeatDiag.results, base=methods.recent, model=methods.model;
 el("repeatDiagnosis").hidden=false;
 el("repeatNote").textContent="模型和近期历史基线的复购排序能力接近，AUC 分别为 "+model.auc.toFixed(3)+
   " 和 "+base.auc.toFixed(3)+"。模型给不同账户的概率更分散，按两档 Brier 分数分解，预测离散项为 "+
   model.forecast_dispersion.toFixed(3)+"，基线为 "+base.forecast_dispersion.toFixed(3)+
   "。它改善的总体均值偏差很小，额外的预测波动超过了和真实复购对齐的收益。";
 const names={model:"内网模型",recent:"近期历史基线"};
 const pointSeries=Object.entries(names).map(([key,name])=>({name,type:"scatter",
   data:methods[key].calibration.map(b=>[number(b.prediction*100),number(b.observed*100),b.accounts]),
   symbolSize:d=>Math.max(6,Math.sqrt(d[2])*1.8)}));
 make("repeatReliability").setOption({legend:{data:Object.values(names)},tooltip:{formatter:e=>e.seriesType==="scatter"?
  e.seriesName+"<br>预测 "+e.data[0]+"% · 实际 "+e.data[1]+"%<br>"+e.data[2]+" 个账户":""},
  xAxis:{type:"value",min:0,max:100,name:"预测概率",nameLocation:"middle",nameGap:35,axisLabel:{formatter:"{value}%"}},
  yAxis:{type:"value",min:0,max:100,name:"实际复购率",axisLabel:{formatter:"{value}%"}},
  series:[{type:"line",data:[[0,0],[100,100]],symbol:"none",lineStyle:{type:"dashed",color:"#98a39c"}},...pointSeries]});
}
window.addEventListener("resize",()=>charts.forEach(chart=>chart.resize()));
</script></html>'''
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=BASE, delete=False) as output:
        output.write(page.replace("REPORT_TITLE", title).replace("FINDINGS", findings(scores, extra)).replace("SAMPLING", sensitivity).replace("PROGRESS", progress_html).replace("DECISIONS", decisions).replace("PAYLOAD", payload))
    Path(output.name).replace(BASE / "index.html")


if __name__ == "__main__":
    main()
