#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the self-contained HTML report for the 6-ASIN shower liner
click-journey experiment (n=1000). Includes Bar Chart Race, Sankey x2,
dynamic scatter, plus the full listing-optimization analysis."""

from __future__ import annotations
import json, base64
from pathlib import Path

ROOT = Path("/Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B")
SRC = ROOT / "results/shower-liner-journey"
OUT = ROOT / "results/shower-liner-journey" / "shower_liner_journey_report.html"
ECHARTS = (ROOT / "scripts/vendor/echarts.min.js").read_text(encoding="utf-8")

S = json.loads((SRC / "summary.json").read_text(encoding="utf-8"))
RACE = json.loads((SRC / "race_stages.json").read_text(encoding="utf-8"))
SCATTER = json.loads((SRC / "scatter.json").read_text(encoding="utf-8"))
SANKEY_CLICK = json.loads((SRC / "sankey_click.json").read_text(encoding="utf-8"))

ASSETS = ROOT / "results/shower-liner-6asin" / "assets"
ASINS = {"A": "B0CGLZ56JC", "B": "B0C9MCD5WL", "C": "B0C2GTPSFR",
         "D": "B0GYWQQ2K3", "E": "B0D212C4XS", "F": "B0FSRN9YTK"}

PROD = {
    "A": {"brand": "AmazerBath", "name": "AmazerBath Rainbow Emerald EVA Shower Curtain Liner 72×72",
          "price": "$18.99", "rating": "4.5★ · 4,156评", "mat": "100% EVA / 黄铜扣眼",
          "look": "半透明祖母绿 EVA，自然垂坠，12 个黄铜扣眼+底部配重；明亮现代浴室场景",
          "points": "豪华触感 EVA；BPA-free 无味环保；防锈黄铜扣眼；双层加固挂头；底部配重防飘；防水速干"},
    "B": {"brand": "jssablo", "name": "jssablo Blue Cube 3D EVA Magnetic Liner 72×72",
          "price": "$7.19", "rating": "4.4★ · 1,872评", "mat": "70% EVA",
          "look": "深蓝渐变→透明的 3D 立方格纹；金属扣眼+配重底；现代浴室",
          "points": "3D 立方纹理显质感；12 金属扣眼；底部 3 磁吸贴浴缸；防水；易冲洗"},
    "C": {"brand": "LQFMEHOT", "name": "LQFMEHOT EVA Blue Water-Wave Art Deco 72×72",
          "price": "$7.09", "rating": "4.6★ · 974评", "mat": "EVA 轻量",
          "look": "深蓝→透蓝的水波纹 Art Deco 纹理；金属扣眼+配重底；白浴缸深色瓷砖",
          "points": "水波纹图案；防水光滑面；底部 3 重磁铁；防撕裂挂头+防锈金属扣；无味 EVA"},
    "D": {"brand": "Laumyasof", "name": "Laumyasof 2-Pack Green 3D Pebble EVA 72×72",
          "price": "$9.99", "rating": "4.4★ · 16评", "mat": "3.2 加仑 EVA（薄）",
          "look": "半透明绿 3D 鹅卵石纹理；图上标 2 PACK；白瓷砖浴室",
          "points": "2 件装价值；3D 鹅卵石设计；12 防锈扣眼；底部 3 磁吸；拒水速干"},
    "E": {"brand": "Dependable", "name": "Dependable Industries EVA Black Modern 72×72",
          "price": "$9.99", "rating": "4.3★ · 116评", "mat": "EVA / PVC-free",
          "look": "纯黑无图案极简；银色金属扣眼；白底影棚图",
          "points": "防水防溅；底部 3 配重磁吸；加固扣眼；易擦拭；标准 72×72；PVC-free"},
    "F": {"brand": "MuuXii", "name": "MuuXii EVA Clear Polka-Dot with Hooks 71×71",
          "price": "$7.99*", "rating": "4.4★ · 10评", "mat": "EVA 防水",
          "look": "浅蓝透明底+波点；附 12 个白色塑料挂钩；明亮浴室",
          "points": "全透明透光；底部 3 磁吸；附 12 挂钩；易冲洗；轻量"},
}

# 中文标签
LABEL = {
    "first": "首点", "second": "第2次点击", "third": "第3次点击", "fallback": "兜底最想买", "buy": "最终成交",
    "A": "A AmazerBath", "B": "B jssablo", "C": "C LQFMEHOT", "D": "D Laumyasof", "E": "E Dependable", "F": "F MuuXii",
    "none": "未购买",
    "review_count": "评论数量多(社会证明)", "material_word": "材质词(无味/BPA-free)", "imagine_look": "能想象装进浴室效果",
    "star_rating": "星级高", "main_image": "主图/场景图吸睛", "color_pattern": "颜色/花纹/3D纹理突出",
    "price": "卡片价格划算", "title_keyword": "标题命中需求词", "brand": "认识/信任品牌",
    "pack_value": "件装/赠挂钩价值", "magnets": "磁吸/配重卖点", "right_size": "尺寸合适", "other": "其他",
    "reviews_photos": "带图/视频评论", "negative_reviews": "差评与抱怨", "bullets": "五点卖点",
    "material_cert": "材质与安全认证", "size_specs": "尺寸/规格表", "zoom_images": "放大图片看质感",
    "main_video": "主图视频/演示", "aplus": "A+品牌内容", "qa": "问答Q&A",
    "price_deal": "价格/优惠", "delivery_returns": "配送与退换", "seller": "卖家信息",
    "want_compare": "没毛病，想再比比", "price_too_high": "价格太贵", "price_suspicious": "太便宜担心质量",
    "transparency": "透明度不合需求", "material": "材质不放心", "no_concern": "没有顾虑，会买",
    "few_reviews": "评论太少", "brand_unfamiliar": "品牌陌生", "look": "外观不合眼缘",
    "size": "尺寸存疑", "missing_magnet": "缺磁吸/配重", "pack": "件装不对", "info_incomplete": "页面信息不全",
    "review_concern": "评论有疑虑", "rating": "评分不够", "other": "其他",
    "timing": "只是先逛逛，不急着买", "reviews_trust": "评论太少/参差，信任不足",
    "look_compromise": "外观只是妥协", "info_gap": "listing 没解答我的疑问", "price": "价格/性价比犹豫",
    "page1": "只看第1页", "page2": "会翻到第2页", "page3": "会翻到第3页",
    "page4_5": "会翻到4-5页", "beyond": "可能超过5页", "unsure": "不确定",
    "reviews": "评论数与评论内容", "price_value": "价格/性价比", "appearance": "外观",
    "magnet": "磁吸/配重", "size_fit": "尺寸", "waterproof": "防水防霉", "rating": "星级",
    "brand": "品牌信任", "pack": "件装/挂钩价值", "listing": "listing完整度",
    "material_unclear": "材质不明", "blur_image": "主图模糊/像假图", "low_rating": "评分<4.0",
    "no_size": "无尺寸信息", "mismatch_title": "标题与图不符/堆词", "no_bullets": "无五点/描述薄",
    "no_aplus": "无A+/视频", "none": "以上都不至于排除",
    "eva": "EVA", "peva": "PEVA", "pvc": "PVC", "polyester": "聚酯纤维", "cloth": "棉布", "no_preference": "无偏好",
    "fully_transparent": "全透明", "semi": "半透明", "blackout": "遮光",
    "yes_strongly": "会，很大影响", "yes_somewhat": "会，有些影响", "neutral": "中立",
    "unlikely": "可能不会", "no_effect": "完全不影响",
    "lower_price": "更低价格", "better_rating": "更高评分/更多评论", "better_look": "更好看",
    "better_function": "功能更强(磁吸/防水)", "better_value": "更值(2件装/挂钩)", "better_listing": "页面更清晰完整",
    "nothing": "不会换", "final_purchase": "最终下单款", "fallback_favorite": "最想买但没下单",
    "skip_ordered": "已在前序下单", "add_cart": "加入购物车，继续比", "not_buy": "不买，返回搜索", "buy_now": "直接下单",
    "yes_more": "会，返回继续看别的", "no_ordered": "不会，现在下单第一个", "no_leave": "不会，什么都不买离开",
}

def L(k):
    return LABEL.get(k, k)

def img_b64(oid):
    p = ASSETS / f"{ASINS[oid]}.jpg"
    return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()

def pct_dict(d):
    return {k: v for k, v in d.items()}

# ---------- 图表数据 ----------
def race_data():
    stages = ["first", "second", "third", "fallback", "buy"]
    labels = [L(s) for s in stages]
    series_map = {}
    for oid in "ABCDEF":
        series_map[oid] = [RACE.get(s, {}).get(oid, 0) for s in stages]
    return labels, series_map

def align_data():
    return S["alignment"]

def top_items(d, n=8):
    return [(k, v["pct"]) for k, v in list(d.items())[:n]]

def likert_data():
    return [(k.replace("q_importance_", ""), v) for k, v in S["likert_means"].items()
            if k.startswith("q_importance_")]

def reject_sankey():
    nodes, links = [], []
    for oid in "ABCDEF":
        nodes.append({"name": oid})
    reasons = {}
    for oid in "ABCDEF":
        d = S["reject_reasons"][oid]
        top = [(k, v["n"]) for k, v in d.items()
               if k not in ("final_purchase", "fallback_favorite")][:3]
        for k, n in top:
            reasons.setdefault(k, 0)
            links.append({"source": oid, "target": k, "value": n})
            nodes.append({"name": k})
    # 去重 node
    seen, nn = set(), []
    for nd in nodes:
        if nd["name"] not in seen:
            seen.add(nd["name"]); nn.append(nd)
    return nn, links

def scatter_groups():
    groups = {"A": [], "B": [], "C": [], "none": [], "D": [], "E": [], "F": []}
    for px, py, fb in SCATTER:
        g = fb if fb in groups else "none"
        groups[g].append([px, py])
    return groups

# ---------- 核心发现 ----------
def core_findings():
    return [
        ("点击≠成交", "首点 A 占 94.2%，但 A 最终直接下单仅 0.9%；97.7% 的人浏览 3 款后仍未下单——高点击与高转化是两件事。", "up"),
        ("下单只认第 1 页", "99.2% 的人只在搜索第 1 页下单；浏览可容忍翻到第 2 页（93.9%）——页 1 位置是生死线。", "up"),
        ("价格是最后一道坎", "85.1% 把 A 列为最想买却因价格/性价比犹豫；价格接受度均分仅 3.21/5。", "warn"),
        ("低价反而劝退", "B/C 两款 $7 级产品被 76-78% 的人以“太便宜担心质量/气味”拒绝——低价无信任=负资产。", "warn"),
        ("评论是决策第一因素", "60.5% 首选评论因素；99%+ 会查晒图、差评、五点、材质认证；评分/评论数也是点击第一驱动。", "up"),
        ("listing 红线近乎一票否决", "材质不明、主图模糊、评分<4.0 三项各被 99% 的人列为排除红线。", "warn"),
        ("新链接冷启动难", "D(16评)/F(10评) 被 99.2% 以“评论太少”排除——新品没有评论量就打不进决策圈。", "warn"),
        ("浏览≠购买，加购≠成交", "首个详情页 98.5% 因“想再比比”不直接下单；兜底最想买 A 占 83.5%，说明偏好存在但被价格/时机挡住。", "up"),
    ]

# ================= HTML =================
RACE_L, RACE_S = race_data()
ALIGN = align_data()
TOP_DRIVERS = top_items(S["click_drivers"])
TOP_DETAIL = top_items(S["detail_info"])
TOP_NOTBUY1 = top_items(S["notbuy_first"])
TOP_BLOCKER = top_items(S["fallback_blocker"])
TOP_REDLINE = top_items(S["listing_redline"])
FACTOR1 = top_items(S["factor_most"])
FACTOR2 = top_items(S["factor_second"])
LIKE = likert_data()
SK_NODES, SK_LINKS = reject_sankey()
SCAT_GROUPS = scatter_groups()

def charts_js():
    return r'''
var PALETTE = ['#1f4e79','#e67e22','#27ae60','#c0392b','#8e44ad','#16a085','#95a5a6','#f39c12','#2980b9','#d35400'];
var TOOLTIP_BASE = {triggerOn:'click', renderMode:'richText', confine:true};
function mk(id, opt){ var c = echarts.init(document.getElementById(id)); c.setOption(opt); return c; }

/* ===== 1. Bar Chart Race ===== */
(function(){
  var stages = __RACE_L__;
  var seriesMap = __RACE_S__;
  var div = document.getElementById('ch-race');
  var chart = echarts.init(div);
  var idx = 0;
  function optionFor(i){
    var data = [];
    var names = ['A','B','C','D','E','F'];
    for (var j=0;j<names.length;j++){ data.push({name:names[j], value:seriesMap[names[j]][i]}); }
    data.sort(function(x,y){ return y.value - x.value; });
    return {
      backgroundColor:'transparent',
      title:{text:'第 '+(i+1)+' 个决策节点 · '+stages[i], left:16, top:10, textStyle:{fontSize:16, fontWeight:700, color:'#1f4e79'}},
      tooltip:Object.assign({trigger:'item'}, TOOLTIP_BASE),
      grid:{left:120, right:60, top:64, bottom:32, containLabel:true},
      xAxis:{type:'value', max:100, axisLabel:{formatter:'{value}%', fontSize:11}, splitLine:{lineStyle:{type:'dashed'}}},
      yAxis:{type:'category', inverse:true, data:data.map(function(d){return d.name;}), axisLabel:{fontSize:13, fontWeight:600, color:'#333'}},
      series:[{type:'bar', data:data, barWidth:26,
        itemStyle:{color:function(p){return PALETTE[p.dataIndex];}, borderRadius:[0,6,6,0]},
        label:{show:true, position:'right', formatter:function(p){return p.value+'%';}, fontSize:12, fontWeight:700, color:'#333'}}]
    };
  }
  chart.setOption(optionFor(0));
  var t = setInterval(function(){
    idx = (idx + 1) % stages.length;
    chart.setOption(optionFor(idx), true);
  }, 1800);
  window.__raceTimer = t;
})();

/* ===== 2. Sankey: 首点 -> 成交 ===== */
(function(){
  var flow = __SANKEY_FLOW__;
  var prodNames = {A:'A AmazerBath',B:'B jssablo',C:'C LQFMEHOT',D:'D Laumyasof',E:'E Dependable',F:'F MuuXii'};
  var linkMap = {};
  flow.forEach(function(row){
    var src = '首点 · ' + (prodNames[row[0]]||row[0]);
    var dst = row[1]==='none' ? '未购买' : '下单 · ' + (prodNames[row[1]]||row[1]);
    var k = src+'|'+dst;
    linkMap[k] = (linkMap[k]||0)+1;
  });
  var nodes = [], links = [], seen = {};
  Object.keys(linkMap).forEach(function(k){
    var parts = k.split('|');
    [parts[0], parts[1]].forEach(function(n){ if(!seen[n]){ seen[n]=1; nodes.push({name:n}); } });
    links.push({source:parts[0], target:parts[1], value:linkMap[k]});
  });
  var chart = mk('ch-sankey-click', {
    title:{text:'从首点产品到最终下单的流向（n=1000）', left:16, top:8, textStyle:{fontSize:15, color:'#1f4e79'}},
    tooltip:Object.assign({trigger:'item'}, TOOLTIP_BASE),
    series:[{type:'sankey', left:40, right:60, top:56, bottom:20,
      data:nodes,
      links:links,
      lineStyle:{color:'gradient', curveness:0.5},
      itemStyle:{borderWidth:0},
      label:{fontSize:11, color:'#333'},
      emphasis:{focus:'adjacency'}}]
  });
})();

/* ===== 3. Sankey: 产品 -> 被拒理由 ===== */
(function(){
  var nodes = __SK_NODES__;
  var links = __SK_LINKS__;
  var nameMap = {A:'A AmazerBath',B:'B jssablo',C:'C LQFMEHOT',D:'D Laumyasof',E:'E Dependable',F:'F MuuXii'};
  var reasonLabel = {price_too_high:'价格太贵', transparency:'透明度不合需求', price_suspicious:'太便宜担心质量',
    look:'外观不合眼缘', brand:'品牌陌生', material:'材质不放心', few_reviews:'评论太少', pack:'件装不对',
    size:'尺寸存疑', info_incomplete:'页面信息不全', missing_magnet:'缺磁吸/配重', review_concern:'评论有疑虑',
    rating:'评分不够', other:'其他'};
  nodes.forEach(function(n){ n.name = nameMap[n.name] || reasonLabel[n.name] || n.name; });
  links.forEach(function(l){ l.source = nameMap[l.source]||reasonLabel[l.source]||l.source; l.target = nameMap[l.target]||reasonLabel[l.target]||l.target; });
  var targetSet = {};
  links.forEach(function(l){ targetSet[l.target]=1; });
  var chart = mk('ch-sankey-reject', {
    title:{text:'为什么没选它？——每款产品被拒的主因流向（人次）', left:16, top:8, textStyle:{fontSize:15, color:'#1f4e79'}},
    tooltip:Object.assign({trigger:'item'}, TOOLTIP_BASE),
    series:[{type:'sankey', left:20, right:140, top:56, bottom:20,
      data:nodes.map(function(n){return {name:n.name};}),
      links:links,
      lineStyle:{color:'gradient', curveness:0.5},
      itemStyle:{borderWidth:0},
      label:{fontSize:11, color:'#333'},
      emphasis:{focus:'adjacency'}}]
  });
})();

/* ===== 4. 首点/成交/兜底 对齐 ===== */
(function(){
  var d = __ALIGN__;
  var cats = d.map(function(x){return x.option;});
  var names = {A:'A AmazerBath',B:'B jssablo',C:'C LQFMEHOT',D:'D Laumyasof',E:'E Dependable',F:'F MuuXii'};
  var chart = mk('ch-align', {
    title:{text:'首点 / 最终成交 / 兜底最想买 份额对比', left:16, top:8, textStyle:{fontSize:15, color:'#1f4e79'}},
    tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'}}, TOOLTIP_BASE),
    legend:{top:38, data:['首点点击','直接下单','兜底最想买']},
    grid:{left:20, right:20, top:80, bottom:30, containLabel:true},
    xAxis:{type:'category', data:cats.map(function(c){return names[c];}), axisLabel:{fontSize:11}},
    yAxis:{type:'value', max:100, axisLabel:{formatter:'{value}%', fontSize:11}},
    series:[
      {name:'首点点击', type:'bar', data:d.map(function(x){return x.first_click_pct;}), barWidth:16, itemStyle:{color:'#1f4e79', borderRadius:[4,4,0,0]}},
      {name:'直接下单', type:'bar', data:d.map(function(x){return x.final_buy_pct;}), barWidth:16, itemStyle:{color:'#c0392b', borderRadius:[4,4,0,0]}},
      {name:'兜底最想买', type:'bar', data:d.map(function(x){return x.fallback_fav_pct;}), barWidth:16, itemStyle:{color:'#e67e22', borderRadius:[4,4,0,0]}}
    ]
  });
})();

/* ===== 5. 点击驱动 ===== */
(function(){
  var d = __TOP_DRIVERS__;
  var chart = mk('ch-drivers', {
    title:{text:'什么让 1000 人第一眼点进这款？', left:16, top:8, textStyle:{fontSize:15, color:'#1f4e79'}},
    tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'}}, TOOLTIP_BASE),
    grid:{left:20, right:50, top:44, bottom:24, containLabel:true},
    xAxis:{type:'value', max:100, axisLabel:{formatter:'{value}%', fontSize:11}},
    yAxis:{type:'category', inverse:true, data:d.map(function(x){return x[0];}), axisLabel:{fontSize:11, color:'#333'}},
    series:[{type:'bar', data:d.map(function(x){return x[1];}), barWidth:16,
      itemStyle:{color:'#2980b9', borderRadius:[0,5,5,0]},
      label:{show:true, position:'right', formatter:'{c}%', fontSize:11}}]
  });
})();

/* ===== 6. 详情页信息查看 ===== */
(function(){
  var d = __TOP_DETAIL__;
  var chart = mk('ch-detail', {
    title:{text:'点进详情页后，先看什么？（选中率）', left:16, top:8, textStyle:{fontSize:15, color:'#1f4e79'}},
    tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'}}, TOOLTIP_BASE),
    grid:{left:20, right:50, top:44, bottom:24, containLabel:true},
    xAxis:{type:'value', max:100, axisLabel:{formatter:'{value}%', fontSize:11}},
    yAxis:{type:'category', inverse:true, data:d.map(function(x){return x[0];}), axisLabel:{fontSize:11, color:'#333'}},
    series:[{type:'bar', data:d.map(function(x){return x[1];}), barWidth:16,
      itemStyle:{color:'#27ae60', borderRadius:[0,5,5,0]},
      label:{show:true, position:'right', formatter:'{c}%', fontSize:11}}]
  });
})();

/* ===== 7. 顾虑：首款不买 + 兜底阻碍 ===== */
(function(){
  var nb = __TOP_NOTBUY1__;
  var bl = __TOP_BLOCKER__;
  var chart = mk('ch-concern', {
    title:{text:'“为什么没下单”的真实顾虑', left:16, top:8, textStyle:{fontSize:15, color:'#1f4e79'}},
    tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'}}, TOOLTIP_BASE),
    legend:{top:38, data:['首个产品未下单原因','兜底最想买却未买的阻碍']},
    grid:{left:20, right:20, top:80, bottom:24, containLabel:true},
    xAxis:{type:'value', max:100, axisLabel:{formatter:'{value}%', fontSize:11}},
    yAxis:{type:'category', inverse:true, data:bl.map(function(x){return x[0];}), axisLabel:{fontSize:11, color:'#333'}},
    series:[
      {name:'首个产品未下单原因', type:'bar', data:bl.map(function(x){ return nb[x[0]] ? nb[x[0]][1] : 0; }), barWidth:14, itemStyle:{color:'#e67e22'}},
      {name:'兜底最想买却未买的阻碍', type:'bar', data:bl.map(function(x){return x[1];}), barWidth:14, itemStyle:{color:'#c0392b'}}
    ]
  });
})();

/* ===== 8. 页数容忍度 ===== */
(function(){
  var order = ['page1','page2','page3','page4_5','beyond','unsure'];
  var pageLabel = {page1:'只看第1页', page2:'会翻到第2页', page3:'会翻到第3页', page4_5:'会翻到4-5页', beyond:'可能超过5页', unsure:'不确定'};
  var pb = __PAGE_BROWSE__; var pby = __PAGE_BUY__;
  var chart = mk('ch-page', {
    title:{text:'搜索页数容忍度：浏览 vs 下单（%选此项）', left:16, top:8, textStyle:{fontSize:15, color:'#1f4e79'}},
    tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'}}, TOOLTIP_BASE),
    legend:{top:38, data:['仍会浏览','仍会下单']},
    grid:{left:20, right:20, top:80, bottom:30, containLabel:true},
    xAxis:{type:'category', data:order.map(function(k){return pageLabel[k]||k;}), axisLabel:{fontSize:11, interval:0}},
    yAxis:{type:'value', max:100, axisLabel:{formatter:'{value}%', fontSize:11}},
    series:[
      {name:'仍会浏览', type:'bar', data:order.map(function(k){return pb[k]?pb[k].pct:0;}), barWidth:18, itemStyle:{color:'#1f4e79'}},
      {name:'仍会下单', type:'bar', data:order.map(function(k){return pby[k]?pby[k].pct:0;}), barWidth:18, itemStyle:{color:'#c0392b'}}
    ]
  });
})();

/* ===== 9. 决策因素 ===== */
(function(){
  var f1 = __FACTOR1__; var f2 = __FACTOR2__;
  var names = [];
  f1.forEach(function(x){ names.push(x[0]); });
  var chart = mk('ch-factor', {
    title:{text:'整个旅程中，什么最重要？（首要+次要）', left:16, top:8, textStyle:{fontSize:15, color:'#1f4e79'}},
    tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'}}, TOOLTIP_BASE),
    legend:{top:38, data:['首要因素','次要因素']},
    grid:{left:20, right:20, top:80, bottom:24, containLabel:true},
    xAxis:{type:'value', max:80, axisLabel:{formatter:'{value}%', fontSize:11}},
    yAxis:{type:'category', inverse:true, data:names, axisLabel:{fontSize:11, color:'#333'}},
    series:[
      {name:'首要因素', type:'bar', data:f1.map(function(x){return x[1];}), barWidth:14, itemStyle:{color:'#1f4e79'}},
      {name:'次要因素', type:'bar', data:names.map(function(k){ var it=f2.filter(function(x){return x[0]===k;}); return it.length?it[0][1]:0; }), barWidth:14, itemStyle:{color:'#95a5a6'}}
    ]
  });
})();

/* ===== 10. listing 8 要素 likert ===== */
(function(){
  var d = __LIKE__;
  var names = {title:'标题完整度', image:'主图清晰度', bullets:'五点卖点', aplus:'A+/视频',
    attr:'属性规格表', price:'价格性价比', reviews:'评分与评论', trust:'品牌与认证'};
  var chart = mk('ch-listing', {
    title:{text:'listing 优化要素重要性（1-5 分均值）', left:16, top:8, textStyle:{fontSize:15, color:'#1f4e79'}},
    tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'}}, TOOLTIP_BASE),
    grid:{left:20, right:50, top:44, bottom:24, containLabel:true},
    xAxis:{type:'value', max:5, axisLabel:{fontSize:11}},
    yAxis:{type:'category', inverse:true, data:d.map(function(x){return names[x[0]]||x[0];}), axisLabel:{fontSize:11, color:'#333'}},
    series:[{type:'bar', data:d.map(function(x){return x[1];}), barWidth:16,
      itemStyle:{color:function(p){ return p.value>=4.5?'#c0392b':(p.value>=4?'#e67e22':'#95a5a6'); }, borderRadius:[0,5,5,0]},
      label:{show:true, position:'right', formatter:'{c}', fontSize:12, fontWeight:700}}]
  });
})();

/* ===== 11. 红线命中率 ===== */
(function(){
  var d = __TOP_REDLINE__;
  var chart = mk('ch-redline', {
    title:{text:'listing 红线：出现即一票否决（选中率）', left:16, top:8, textStyle:{fontSize:15, color:'#1f4e79'}},
    tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'}}, TOOLTIP_BASE),
    grid:{left:20, right:50, top:44, bottom:24, containLabel:true},
    xAxis:{type:'value', max:100, axisLabel:{formatter:'{value}%', fontSize:11}},
    yAxis:{type:'category', inverse:true, data:d.map(function(x){return x[0];}), axisLabel:{fontSize:11, color:'#333'}},
    series:[{type:'bar', data:d.map(function(x){return x[1];}), barWidth:16,
      itemStyle:{color:function(p){ return p.value>=90?'#c0392b':'#e67e22'; }, borderRadius:[0,5,5,0]},
      label:{show:true, position:'right', formatter:'{c}%', fontSize:11}}]
  });
})();

/* ===== 12. 人群分布散点 ===== */
(function(){
  var groups = __SCAT_GROUPS__;
  var colors = {A:'#e67e22', B:'#2980b9', C:'#27ae60', D:'#8e44ad', E:'#7f8c8d', F:'#f39c12', none:'#bdc3c7'};
  var names = {A:'兜底最想买 A (AmazerBath)', B:'兜底最想买 B (jssablo)', C:'兜底最想买 C (LQFMEHOT)',
    D:'兜底最想买 D (Laumyasof)', E:'兜底最想买 E (Dependable)', F:'兜底最想买 F (MuuXii)', none:'未选中任何款'};
  var series = [];
  Object.keys(colors).forEach(function(g){
    var pts = groups[g].map(function(p){
      var x = p[0] + (Math.random()-0.5)*0.35;
      var y = p[1] + (Math.random()-0.5)*0.35;
      return [Math.max(0.5,Math.min(5.5,x)), Math.max(0.5,Math.min(5.5,y))];
    });
    series.push({
      name: names[g], type:'scatter', symbolSize:7, data:pts,
      itemStyle:{color:colors[g], opacity:0.55},
      emphasis:{itemStyle:{opacity:0.95}}
    });
  });
  var chart = mk('ch-scatter', {
    title:{text:'人群分布：价格接受度 × 购买意向（颜色=最终偏好）', left:16, top:8, textStyle:{fontSize:15, color:'#1f4e79'}},
    tooltip:Object.assign({trigger:'item'}, TOOLTIP_BASE),
    legend:{top:38, data:Object.values(names), textStyle:{fontSize:10}},
    grid:{left:20, right:20, top:84, bottom:40, containLabel:true},
    xAxis:{type:'value', name:'价格接受度 (1=太贵 5=可接受)', min:0.5, max:5.5, nameLocation:'middle', nameGap:26, axisLabel:{fontSize:10}},
    yAxis:{type:'value', name:'购买意向 (1=不会买 5=会买)', min:0.5, max:5.5, nameLocation:'middle', nameGap:34, axisLabel:{fontSize:10}},
    series:series
  });
})();
'''

def findings_html():
    cards = ""
    for title, text, tone in core_findings():
        color = {"up": "#1f4e79", "warn": "#c0392b"}[tone]
        cards += f'''<div class="card" style="border-top:4px solid {color}">
          <div class="card-num">{title}</div>
          <div class="card-text">{text}</div>
        </div>'''
    return cards

def product_cards():
    html = ""
    for oid in "ABCDEF":
        p = PROD[oid]
        al = next(x for x in ALIGN if x["option"] == oid)
        rej = S["reject_reasons"][oid]
        top_rej = [(k, v["pct"]) for k, v in rej.items()
                   if k not in ("final_purchase", "fallback_favorite")][:2]
        rej_txt = "；".join(f"{L(k)} {v}%" for k, v in top_rej)
        badge = "$7.99*（实验补价，非源数据）" if oid == "F" else p["price"]
        html += f'''<div class="prod">
          <img class="prod-img" src="{img_b64(oid)}" alt="{p['brand']}">
          <div class="prod-body">
            <div class="prod-name">{oid} · {p['brand']}</div>
            <div class="prod-sub">{p['name']}</div>
            <div class="prod-meta">
              <span class="pill">价格 {badge}</span><span class="pill">{p['rating']}</span>
              <span class="pill">{p['mat']}</span>
            </div>
            <div class="prod-look"><b>主图印象：</b>{p['look']}</div>
            <div class="prod-points"><b>卖点：</b>{p['points']}</div>
            <div class="prod-stats">
              <div><b>{al['first_click_pct']}%</b><span>首点</span></div>
              <div><b>{al['final_buy_pct']}%</b><span>直接下单</span></div>
              <div><b>{al['fallback_fav_pct']}%</b><span>兜底最想买</span></div>
            </div>
            <div class="prod-rej"><b>被拒主因：</b>{rej_txt}</div>
            <div class="prod-link"><a href="https://www.amazon.com/dp/{ASINS[oid]}" target="_blank" rel="noopener">查看亚马逊页面 · ASIN {ASINS[oid]} ↗</a></div>
          </div>
        </div>'''
    return html

def quotes_html():
    q = S["quotes_first_click"]
    lines = []
    for oid in "ABCDEF":
        for t in q.get(oid, [])[:1]:
            lines.append(f'<div class="quote"><span class="q-tag">首点 {oid} · {PROD[oid]["brand"]}</span>“{t}”</div>')
    fb = S["quotes_fallback"]
    for oid in ["A", "C", "B"]:
        for t in fb.get(oid, [])[:1]:
            lines.append(f'<div class="quote"><span class="q-tag">兜底 {oid} · {PROD[oid]["brand"]}</span>“{t}”</div>')
    return "\n".join(lines)

def table_block():
    rows = ""
    for x in ALIGN:
        rej = S["reject_reasons"][x["option"]]
        top1 = [(k, v["pct"]) for k, v in rej.items()
                if k not in ("final_purchase", "fallback_favorite")][:1]
        rej_txt = f"{L(top1[0][0])} {top1[0][1]}%" if top1 else "—"
        rows += f'''<tr>
          <td><b>{x['option']}</b> {PROD[x['option']]['brand']}</td>
          <td>{x['first_click_pct']}%</td><td>{x['final_buy_pct']}%</td><td>{x['fallback_fav_pct']}%</td>
          <td>{rej_txt}</td>
        </tr>'''
    return rows

# ---------- 组装 ----------
html = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>亚马逊浴帘内衬 6 款 · 搜索→购买旅程模拟实验报告（n=1000）</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%231f4e79'/%3E%3Cpath d='M16 46 L32 18 L48 46 Z' fill='white'/%3E%3C/svg%3E">
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif; background:#f5f7fa; color:#2c3e50; line-height:1.6; }
.wrap { max-width:1200px; margin:0 auto; padding:24px 20px 80px; }
.hero { background:linear-gradient(135deg,#1f4e79 0%,#2c6e9e 60%,#3b8fc2 100%); color:#fff; border-radius:16px; padding:36px 40px; margin-bottom:24px; }
.hero h1 { font-size:28px; font-weight:800; margin-bottom:10px; letter-spacing:.5px; }
.hero .sub { font-size:14px; opacity:.92; }
.hero .chips { margin-top:14px; display:flex; flex-wrap:wrap; gap:8px; }
.hero .chip { background:rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.25); padding:4px 12px; border-radius:999px; font-size:12px; }
.section { margin-top:32px; }
.section h2 { font-size:20px; color:#1f4e79; border-left:5px solid #e67e22; padding-left:12px; margin-bottom:14px; }
.section .lead { font-size:14px; color:#555; margin-bottom:12px; }
@media (max-width:640px){ .section .lead { font-size:15px; } .card-text { font-size:15px; } }
.grid4 { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; }
@media (max-width:900px){ .grid4 { grid-template-columns:repeat(2,1fr); } }
.card { background:#fff; border-radius:10px; padding:16px; box-shadow:0 1px 4px rgba(0,0,0,.06); }
.card-num { font-size:15px; font-weight:800; color:#1f4e79; margin-bottom:6px; }
.card-text { font-size:14px; color:#555; }
.chart-box { background:#fff; border-radius:12px; box-shadow:0 1px 4px rgba(0,0,0,.06); padding:14px; margin-bottom:16px; }
.chart-box .chart { width:100%; height:420px; }
.chart-note { font-size:12px; color:#888; margin-top:6px; padding-left:4px; }
.two-col { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
@media (max-width:900px){ .two-col { grid-template-columns:1fr; } }
.products { display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }
@media (max-width:1000px){ .products { grid-template-columns:repeat(2,1fr); } }
@media (max-width:640px){ .products { grid-template-columns:1fr; } }
.prod { background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 1px 5px rgba(0,0,0,.08); display:flex; flex-direction:column; }
.prod-img { width:100%; aspect-ratio:1; object-fit:cover; background:#f0f2f5; }
.prod-body { padding:14px; display:flex; flex-direction:column; gap:8px; }
.prod-name { font-size:16px; font-weight:800; color:#1f4e79; }
.prod-sub { font-size:12px; color:#666; }
.prod-meta { display:flex; flex-wrap:wrap; gap:6px; }
.pill { background:#eef3f8; color:#1f4e79; border-radius:999px; padding:2px 10px; font-size:11px; font-weight:600; }
.prod-look { font-size:12px; color:#555; }
.prod-points { font-size:12px; color:#555; }
.prod-stats { display:flex; gap:10px; margin-top:4px; }
.prod-stats div { flex:1; background:#f7f9fc; border-radius:8px; padding:6px 4px; text-align:center; }
.prod-stats b { display:block; font-size:15px; color:#c0392b; }
.prod-stats span { font-size:11px; color:#888; }
.prod-rej { font-size:12px; color:#7d3c3c; background:#fdf0ee; border-radius:8px; padding:6px 8px; }
.prod-link a { font-size:12px; color:#2980b9; text-decoration:none; font-weight:600; }
.quotes { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
@media (max-width:900px){ .quotes { grid-template-columns:1fr; } }
.quote { background:#fff; border-radius:10px; padding:12px 14px; font-size:13px; color:#444; box-shadow:0 1px 3px rgba(0,0,0,.05); border-left:4px solid #f39c12; }
.q-tag { display:inline-block; background:#fdf3e3; color:#a05a00; border-radius:6px; padding:1px 8px; font-size:11px; font-weight:700; margin-bottom:4px; }
table { width:100%; border-collapse:collapse; background:#fff; border-radius:10px; overflow:hidden; box-shadow:0 1px 4px rgba(0,0,0,.06); font-size:13px; }
th,td { padding:10px 12px; text-align:center; }
th { background:#1f4e79; color:#fff; font-weight:600; }
tr:nth-child(even) { background:#f7f9fc; }
.note { background:#fffbe8; border:1px solid #f5e3a5; border-radius:10px; padding:12px 16px; font-size:13px; color:#7a6420; margin-bottom:16px; }
.footer { margin-top:40px; font-size:12px; color:#999; text-align:center; }
</style>
</head>
<body>
<div class="wrap">

<div class="hero">
  <h1>亚马逊「浴帘内衬」搜索 → 点击 → 购买旅程模拟实验</h1>
  <div class="sub">6 款在售 SKU 同场竞技 · 1000 名北美亚马逊画像用户逐环节决策 · 每个决策点记录真实理由</div>
  <div class="chips">
    <span class="chip">样本 n=1000 · 通过率 100%</span>
    <span class="chip">Amazon 北美画像（同一人格池，可跨实验对比）</span>
    <span class="chip">deepseek-chat · seed=42</span>
    <span class="chip">购买状态/库存/配送已剔除（受控实验）</span>
    <span class="chip">决策链：搜索页→详情页→2/3次回流→兜底</span>
  </div>
</div>

<div class="note">
  <b>实验设计说明：</b>6 款浴帘内衬在搜索第 1 页同场展示，1000 名买家模拟完整旅程：第一眼点进哪款 → 详情页看什么 → 买不买、不买顾虑 → 返回后是否再看、看哪款 → 全部点完都不买时最想买哪款。所有购买状态（缺货/无价/配送）已按实验要求剔除，F 款源数据无价格，按同规格带挂钩 EVA 浴帘市场价补为 <b>$7.99*</b>（受控假设值，仅用于本次对照）。
</div>

<div class="section">
  <h2>核心发现速览</h2>
  <div class="grid4">
    __FINDINGS__
  </div>
</div>

<div class="section">
  <h2>① 决策竞赛：份额如何一路演变（Bar Chart Race）</h2>
  <div class="lead">5 个决策节点 × 6 款产品的份额排名动态。注意 A（$18.99 高评论款）开局 94.2% 碾压，中途被 C/B（$7 低价高性价比款）在"二次点击"抢走查看，但最终偏好又回流 A——点击注意力与下单行动严重错位。</div>
  <div class="chart-box"><div id="ch-race" class="chart"></div>
  <div class="chart-note">份额口径 = 该决策节点上选择该产品的人数 ÷ 全体 1000 人。动画每 1.8 秒切换一个决策节点，可鼠标悬停查看具体数值。</div></div>
</div>

<div class="section">
  <h2>② 从点击到成交：钱到底流失在哪</h2>
  <div class="two-col">
    <div class="chart-box"><div id="ch-sankey-click" class="chart"></div>
    <div class="chart-note">每 1000 人中，最终只有 23 人在前 3 款内直接下单（A 9、B 5、C 9）；977 人全部看完仍未下单。粗线 = 首点 A 的 942 人最终流向。</div></div>
    <div class="chart-box"><div id="ch-align" class="chart"></div>
    <div class="chart-note">三列对比：首点点击（注意吸引）≠ 直接下单（行动）≠ 兜底最想买（偏好）。A 同时是点击王与偏好王，却是成交洼地。</div></div>
  </div>
</div>

<div class="section">
  <h2>③ 为什么没选它？—— 每款被拒主因（Sankey）</h2>
  <div class="chart-box"><div id="ch-sankey-reject" class="chart"></div>
  <div class="chart-note">流向 = 人次（多选）。A 被"价格太贵"堵死；B/C 被"太便宜担心质量"反噬；D/F 因评论太少出局；E 因外观/评论双重失分。</div></div>
</div>

<div class="section">
  <h2>④ 第一眼的吸引与详情页的审视</h2>
  <div class="two-col">
    <div class="chart-box"><div id="ch-drivers" class="chart"></div>
    <div class="chart-note">点击驱动：评论数(97.5%)、材质词(97%)、可想象效果(92.1%)、星级(91.7%)、主图(90.6%)——第一眼是"信任证据 + 画面感"的战争。</div></div>
    <div class="chart-box"><div id="ch-detail" class="chart"></div>
    <div class="chart-note">详情页几乎人人把"带图评论、差评、五点、材质认证、放大图"全查一遍（99%+）——listing 任何一项薄弱都会被看见。</div></div>
  </div>
</div>

<div class="section">
  <h2>⑤ 不买的原因与最后的阻碍</h2>
  <div class="chart-box"><div id="ch-concern" class="chart"></div>
  <div class="chart-note">首个产品未下单：98.5% 是"想再比比"（不是产品差，是决策习惯）；93.1% 提到价格。兜底阻碍：85.1% 卡在价格/性价比，64.1% 只是"还没准备买"。</div></div>
</div>

<div class="section">
  <h2>⑥ 搜索位置的价值：下单只认第 1 页</h2>
  <div class="chart-box"><div id="ch-page" class="chart"></div>
  <div class="chart-note">浏览可以翻到第 2 页（93.9%），但下单 99.2% 只发生在第 1 页——位置排名直接影响转化，第 1 页 = 生死线。</div></div>
</div>

<div class="section">
  <h2>⑦ 决策因素与 listing 优化优先级</h2>
  <div class="two-col">
    <div class="chart-box"><div id="ch-factor" class="chart"></div>
    <div class="chart-note">评论是绝对第一因素（60.5% 首选），价格与材质并列第二梯队。</div></div>
    <div class="chart-box"><div id="ch-listing" class="chart"></div>
    <div class="chart-note">评分评论(4.98)与主图(4.85)是 listing 最重要的两块；A+/视频(2.04)重要性垫底——先补前两项，别急着做品牌故事。</div></div>
  </div>
</div>

<div class="section">
  <h2>⑧ listing 红线：一票否决清单</h2>
  <div class="chart-box"><div id="ch-redline" class="chart"></div>
  <div class="chart-note">材质不明、主图模糊/像假图、评分<4.0 各被 99% 的人列为"直接排除"；新品评论少（<50）也是 82% 的红线。</div></div>
</div>

<div class="section">
  <h2>⑨ 人群分布：价格接受度 × 购买意向</h2>
  <div class="chart-box"><div id="ch-scatter" class="chart"></div>
  <div class="chart-note">颜色 = 兜底最想买的产品。A 偏好人群集中在"价格接受度低（嫌贵）但购买意向高（想买）"的左上区——典型的"想要但没下单"；B/C 偏好人群分散在中部。这是价格策略（降价/优惠/价值包装）的目标人群画像。</div></div>
</div>

<div class="section">
  <h2>⑩ 六款产品全景</h2>
  <div class="products">
    __PRODUCTS__
  </div>
</div>

<div class="section">
  <h2>⑪ 买家原声（答卷理由摘录）</h2>
  <div class="quotes">
    __QUOTES__
  </div>
</div>

<div class="section">
  <h2>⑫ 关键口径对齐表</h2>
  <table>
    <tr><th>产品</th><th>首点点击（全体）</th><th>直接下单（严格口径）</th><th>兜底最想买（全体）</th><th>被拒主因 Top1</th></tr>
    __TABLE__
  </table>
  <div class="chart-note" style="margin-top:8px;">口径：直接下单 = 在前 3 次点击的任一详情页明确选择 buy_now；兜底最想买 = 全部浏览后 q_fallback；被拒主因 = q_reject 中"为什么不选它"的首位理由（排除已下单/兜底标记）。</div>
</div>

<div class="section">
  <h2>给电商团队的行动建议</h2>
  <div class="grid4">
    <div class="card"><div class="card-num">1. 抢第 1 页，保前 3 位</div><div class="card-text">99.2% 只在第 1 页下单。广告/排名预算优先保住核心词第 1 页曝光。</div></div>
    <div class="card"><div class="card-num">2. 评论量是第一资产</div><div class="card-text">评论数驱动点击（97.5%），评论因素是决策第一（60.5%）。新品先用种子评论+老品带新突破 50 条线。</div></div>
    <div class="card"><div class="card-num">3. 价格带卡在信任盲区</div><div class="card-text">$7 档被 76-78% 质疑质量；$18.99 档被 98.8% 嫌贵。中间 $9-13 档+价值包装（件装/挂钩/磁吸）是甜区。</div></div>
    <div class="card"><div class="card-num">4. 主图与五点别省</div><div class="card-text">主图清晰度 4.85、材质认证 99% 必查。主图放"真实场景+材质细节"，五点讲清无味/防水/磁吸。</div></div>
    <div class="card"><div class="card-num">5. 差评与晒图是转化开关</div><div class="card-text">99.9% 看带图评论、99.2% 查差评。差评区要有合理解释/卖家回复，晒图决定最后一脚。</div></div>
    <div class="card"><div class="card-num">6. 降价不如降犹豫</div><div class="card-text">85.1% 卡在"价格/性价比"而非买不起。用优惠券、套装、运费包邮降低决策成本，比裸降价更能守住利润。</div></div>
    <div class="card"><div class="card-num">7. A+/视频优先级最低</div><div class="card-text">重要性仅 2.04/5。先把评论、主图、五点、属性表做扎实，A+ 锦上添花。</div></div>
    <div class="card"><div class="card-num">8. 别把"浏览"当"购买"</div><div class="card-text">97.7% 看完不买是常态（比较型购物）。用站内 Coupon+到货提醒+复购场景内容把"最想买"转成订单。</div></div>
  </div>
</div>

<div class="footer">
  生成于 2026-09-18 · MatrAIx-Persona-8B 用户模拟选品实验 · 数据源：Amazon.com 全字段明细（2026-09-17）+ 1000 名亚马逊画像用户旅程模拟<br>
  图表可交互：悬停查看数值、桑基可点击聚焦、竞赛图自动轮播
</div>

</div>
<script>__ECHARTS__</script>
<script>
__CHART_JS__
</script>
</body>
</html>'''

html = (html.replace("__FINDINGS__", findings_html())
            .replace("__PRODUCTS__", product_cards())
            .replace("__QUOTES__", quotes_html())
            .replace("__TABLE__", table_block())
            .replace("__ECHARTS__", ECHARTS)
            .replace("__CHART_JS__", charts_js()
                     .replace("__RACE_L__", json.dumps(RACE_L, ensure_ascii=False))
                     .replace("__RACE_S__", json.dumps(RACE_S, ensure_ascii=False))
                     .replace("__SANKEY_FLOW__", json.dumps(SANKEY_CLICK, ensure_ascii=False))
                     .replace("__SK_NODES__", json.dumps(SK_NODES, ensure_ascii=False))
                     .replace("__SK_LINKS__", json.dumps(SK_LINKS, ensure_ascii=False))
                     .replace("__ALIGN__", json.dumps(ALIGN, ensure_ascii=False))
                     .replace("__TOP_DRIVERS__", json.dumps(TOP_DRIVERS, ensure_ascii=False))
                     .replace("__TOP_DETAIL__", json.dumps(TOP_DETAIL, ensure_ascii=False))
                     .replace("__TOP_NOTBUY1__", json.dumps(TOP_NOTBUY1, ensure_ascii=False))
                     .replace("__TOP_BLOCKER__", json.dumps(TOP_BLOCKER, ensure_ascii=False))
                     .replace("__PAGE_BROWSE__", json.dumps(S["page_browse"], ensure_ascii=False))
                     .replace("__PAGE_BUY__", json.dumps(S["page_buy"], ensure_ascii=False))
                     .replace("__FACTOR1__", json.dumps(FACTOR1, ensure_ascii=False))
                     .replace("__FACTOR2__", json.dumps(FACTOR2, ensure_ascii=False))
                     .replace("__LIKE__", json.dumps(LIKE, ensure_ascii=False))
                     .replace("__TOP_REDLINE__", json.dumps(TOP_REDLINE, ensure_ascii=False))
                     .replace("__SCAT_GROUPS__", json.dumps(SCAT_GROUPS, ensure_ascii=False))))

OUT.write_text(html, encoding="utf-8")
print("written:", OUT, f"({OUT.stat().st_size/1024/1024:.2f} MB)")
