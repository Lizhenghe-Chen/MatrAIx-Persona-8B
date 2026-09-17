#!/usr/bin/env python3
"""Aggregate the toilet-brush shopping survey results into CSV / JSON / dashboard.

Usage:
  uv run python scripts/aggregate_toilet_results.py [job_dir] [out_dir]

Reads every trial under a survey-toilet-brush-choice job dir:
  - artifacts/app/output/survey_result.json   (answers + rationale)
  - config.json                               (persona_path)
  - verifier/reward.txt                       (pass/fail)
joins persona dimensions from the persona YAML, and writes:
  - <out>/toilet_brush_raw.csv
  - <out>/toilet_brush_summary.json
  - <out>/toilet_brush_dashboard.html
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]

PRODUCTS = {
    "clorox_under_rim": {"name": "Clorox Corner Under-Rim", "price": 15.50, "tier": "低",
                         "material": "Rubber handle, antimicrobial bristles",
                         "selling": "Corner caddy; under-rim scrubber; antibacterial"},
    "mdesign_compact": {"name": "mDesign Compact Bronze", "price": 29.30, "tier": "中高",
                        "material": "Plastic",
                        "selling": "Compact freestanding covered holder; non-slip base"},
    "boomjoy_tweezer": {"name": "BOOMJOY Silicone+Tweezers", "price": 12.99, "tier": "低",
                        "material": "Silicone head, aluminum handle",
                        "selling": "Built-in tweezers; lightweight; quick-dry base"},
    "sellemer_silicone": {"name": "Sellemer Silicone", "price": 12.99, "tier": "低",
                          "material": "Silicone",
                          "selling": "Flexible under-rim head; ventilated quick-dry base"},
    "oxo_hideaway": {"name": "OXO Hideaway Compact", "price": 19.97, "tier": "中",
                     "material": "Plastic, firm nylon bristles",
                     "selling": "Auto-open hideaway canister; anti-water-tray; compact"},
    "ibergrif_silicone": {"name": "Ibergrif M34152 Silicone", "price": 13.90, "tier": "低",
                          "material": "Silicone bristles, stainless rod, plastic handle",
                          "selling": "Deep-clean silicone; quick-dry holder; replaceable head"},
    "ixo_stainless": {"name": "IXO 2-Pack Stainless", "price": 28.60, "tier": "中高",
                      "material": "304 stainless steel, plastic base",
                      "selling": "2 brushes; stainless long handles; elegant"},
    "nacena_long": {"name": "nacena 2-Pack Long Handle", "price": 23.50, "tier": "中",
                    "material": "Plastic, stiff bristles",
                    "selling": "Extra-long handle; covered storage; 2-pack"},
    "asobeage_silicone": {"name": "Asobeage Silicone", "price": 25.70, "tier": "中",
                          "material": "Silicone bristles, plastic handle",
                          "selling": "Flexible nubbed head; non-slip handle; quick-dry base"},
    "jiga_3pack": {"name": "JIGA 3-Pack", "price": 13.99, "tier": "低",
                   "material": "Plastic, stiff nylon bristles",
                   "selling": "3 brushes; stiff bristles; caddy; great value"},
    "none_of_these": {"name": "None of these", "price": 0.0, "tier": "无",
                      "material": "", "selling": ""},
}
CHOICE_LABEL = {k: v["name"] for k, v in PRODUCTS.items()}


def load_persona_dims(path: str) -> dict:
    try:
        d = yaml.safe_load(open(REPO / path, encoding="utf-8"))
    except Exception:
        return {}
    dims = d.get("dimensions") or {}
    return {
        "age_bracket": dims.get("age_bracket"),
        "economic_motivation": dims.get("economic_motivation"),
        "region": dims.get("region"),
        "socioeconomic_band": dims.get("socioeconomic_band"),
        "gender_identity": dims.get("gender_identity"),
        "life_stage": dims.get("life_stage"),
        "income": dims.get("demo_household_income"),
        "employment": dims.get("demo_employment_status"),
        "country": dims.get("country") or dims.get("country_code"),
        "urbanicity": dims.get("urbanicity"),
    }


def collect_trials(job_dir: Path) -> list[dict]:
    rows = []
    for trial in sorted(job_dir.iterdir()):
        if not trial.is_dir() or not trial.name.startswith("survey_"):
            continue
        out_json = trial / "artifacts" / "app" / "output" / "survey_result.json"
        if not out_json.exists():
            continue
        try:
            sr = json.loads(out_json.read_text(encoding="utf-8"))
        except Exception:
            continue
        answers = {a.get("questionId"): a for a in sr.get("answers", [])}
        choice = (answers.get("q_choice") or {}).get("value")
        if choice is None:
            continue
        reward = 0.0
        rw = trial / "verifier" / "reward.txt"
        if rw.exists():
            try:
                reward = float(rw.read_text(encoding="utf-8").strip())
            except ValueError:
                reward = 0.0
        cfg = json.loads((trial / "config.json").read_text(encoding="utf-8"))
        persona_path = (cfg.get("agent") or {}).get("kwargs", {}).get("persona_path", "")
        dims = load_persona_dims(persona_path) if persona_path else {}
        rows.append(
            {
                "trial": trial.name,
                "persona_path": persona_path,
                "reward": reward,
                "choice": choice,
                "choice_label": CHOICE_LABEL.get(choice, choice),
                "price": PRODUCTS.get(choice, {}).get("price"),
                "price_threshold": (answers.get("q_price_threshold") or {}).get("value"),
                "feature_priority": (answers.get("q_feature_priority") or {}).get("value"),
                "purchase_likelihood": (answers.get("q_purchase_likelihood") or {}).get("value"),
                "rationale": ((answers.get("q_choice") or {}).get("rationale") or "").strip(),
                **dims,
            }
        )
    return rows


def pct(n, d):
    return round(100.0 * n / d, 1) if d else 0.0


REVIEW_KW = {
    "Cleaning performance": r"clean|scrub|bristle|deep|rim|under.rim|corner|bowl|stain|power|effective",
    "Hygiene / quick-dry": r"hygien|quick.dry|dry|ventilat|drain|moisture|bacteria|germ|odor|smell|sanit",
    "Price / value": r"price|cheap|expensive|afford|budget|value|cost|worth|deal|money|save",
    "Design / looks": r"look|design|color|style|aesthet|sleek|modern|minimal|elegant|attract|beautiful|nice",
    "Material / durability": r"stainless|steel|silicone|aluminum|plastic|durab|sturdy|rust|material|quality|long.last",
    "Brand / trust": r"brand|trust|reput|reliable|known|oxo|clorox|quality|top",
    "Space / storage": r"space|compact|small|storage|holder|caddy|hid|slim|fit",
    "Hair tangle": r"hair|tangle|tweezer",
}


def choice_x(dim: str, rows: list[dict]) -> dict:
    by = defaultdict(Counter)
    for r in rows:
        v = (r.get(dim) or "unknown").strip() or "unknown"
        by[v][r["choice"]] += 1
    return {
        k: {p: {"count": c.get(p, 0), "share_pct": pct(c.get(p, 0), sum(c.values()))} for p in PRODUCTS}
        for k, c in sorted(by.items(), key=lambda kv: -sum(kv[1].values()))
    }


def product_reviews(rows: list[dict]) -> dict:
    out = {}
    for prod in PRODUCTS:
        texts = [r["rationale"] for r in rows if r["choice"] == prod and r["rationale"]]
        n = len(texts)
        if not n:
            out[prod] = {"n": 0, "keywords": {}}
            continue
        cnt = {k: sum(1 for t in texts if re.search(pat, t, re.I)) for k, pat in REVIEW_KW.items()}
        out[prod] = {"n": n, "keywords": {k: {"n": v, "pct": pct(v, n)} for k, v in cnt.items() if v}}
    return out


MENTION_PAT = {
    "clorox_under_rim": r"clorox|under.rim|corner",
    "mdesign_compact": r"mdesign",
    "boomjoy_tweezer": r"boomjoy|tweezer",
    "sellemer_silicone": r"sellemer",
    "oxo_hideaway": r"oxo|hideaway|canister",
    "ibergrif_silicone": r"ibergrif|m34152",
    "ixo_stainless": r"ixo|stainless|2.pack",
    "nacena_long": r"nacena|long handle",
    "asobeage_silicone": r"asobeage",
    "jiga_3pack": r"jiga|3.pack|3 pack",
}
REJECT_SIGNAL = re.compile(
    r"too (expensive|pricey|costly)|not worth|overpriced|pass|skip|however|but|although|though|instead|yet|"
    r"not (worth|durable|hygienic|good)|doesn'?t (fit|help|work|appeal)|not my (style|taste)|"
    r"no (need|use) for|prefer (a|the|something|cheaper)|would rather|rather (buy|get|have)", re.I
)


def consideration(rows: list[dict]) -> dict:
    out = {}
    for prod, pat in MENTION_PAT.items():
        chosen = sum(1 for r in rows if r["choice"] == prod)
        others = [r for r in rows if r["choice"] != prod and r["rationale"] and re.search(pat, r["rationale"], re.I)]
        went = Counter(r["choice"] for r in others)
        went_top = {k: v for k, v in went.most_common(4)}
        samples = []
        if chosen == 0:
            for r in others:
                if REJECT_SIGNAL.search(r["rationale"]):
                    samples.append(r["rationale"][:200])
                    if len(samples) >= 3:
                        break
        out[prod] = {"votes": chosen, "considered_by": len(others), "went_to": went_top,
                     "sample_rationales": samples}
    return out


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    choice_counts = Counter(r["choice"] for r in rows)
    market_share = {
        k: {"name": PRODUCTS[k]["name"], "price": PRODUCTS[k]["price"],
            "count": choice_counts.get(k, 0),
            "share_pct": pct(choice_counts.get(k, 0), n)}
        for k in PRODUCTS
    }
    by_econ = defaultdict(Counter)
    for r in rows:
        by_econ[r["economic_motivation"] or "unknown"][r["choice"]] += 1
    choice_x_econ = {
        eco: {k: {"count": c.get(k, 0), "share_pct": pct(c.get(k, 0), sum(c.values()))}
              for k in PRODUCTS}
        for eco, c in sorted(by_econ.items())
    }
    by_age = defaultdict(Counter)
    for r in rows:
        by_age[r["age_bracket"] or "unknown"][r["choice"]] += 1
    choice_x_age = {
        a: {k: {"count": c.get(k, 0), "share_pct": pct(c.get(k, 0), sum(c.values()))}
            for k in PRODUCTS}
        for a, c in sorted(by_age.items())
    }
    thr = Counter(r["price_threshold"] for r in rows if r["price_threshold"] is not None)
    thr_x_econ = defaultdict(Counter)
    for r in rows:
        if r["price_threshold"] is not None:
            thr_x_econ[r["economic_motivation"] or "unknown"][r["price_threshold"]] += 1
    feat = Counter(r["feature_priority"] for r in rows if r["feature_priority"])
    like = Counter(r["purchase_likelihood"] for r in rows if r["purchase_likelihood"] is not None)
    sens = {}
    for eco, c in thr_x_econ.items():
        tot = sum(c.values())
        sens[eco] = {
            "n": tot,
            "avg_threshold": round(sum(int(k) * v for k, v in c.items()) / tot, 2),
            "threshold_dist": dict(sorted(c.items())),
        }
    chosen_prices = [r["price"] for r in rows if r.get("price")]
    chosen_prices.sort()

    def q(lst, p):
        if not lst:
            return None
        i = min(len(lst) - 1, int(len(lst) * p))
        return lst[i]

    sample = {
        "n": n,
        "reward_rate": round(sum(1 for r in rows if r["reward"] >= 1.0) / n, 4) if n else 0,
        "age": dict(sorted(Counter(r["age_bracket"] or "unknown" for r in rows).items())),
        "econ": dict(sorted(Counter(r["economic_motivation"] or "unknown" for r in rows).items())),
        "region": dict(sorted(Counter(r["region"] or "unknown" for r in rows).items())),
        "gender": dict(sorted(Counter(r["gender_identity"] or "unknown" for r in rows).items())),
        "socio": dict(sorted(Counter(r["socioeconomic_band"] or "unknown" for r in rows).items())),
        "urbanicity": dict(sorted(Counter(r["urbanicity"] or "unknown" for r in rows).items())),
    }
    return {
        "n": n,
        "products": PRODUCTS,
        "market_share": market_share,
        "choice_x_econ": choice_x_econ,
        "choice_x_age": choice_x_age,
        "choice_x_region": choice_x("region", rows),
        "choice_x_gender": choice_x("gender_identity", rows),
        "choice_x_life_stage": choice_x("life_stage", rows),
        "choice_x_socio": choice_x("socioeconomic_band", rows),
        "choice_x_urban": choice_x("urbanicity", rows),
        "product_reviews": product_reviews(rows),
        "consideration": consideration(rows),
        "price_threshold": {"dist": dict(sorted(thr.items())), "avg": round(sum(int(k) * v for k, v in thr.items()) / sum(thr.values()), 2) if thr else None},
        "price_sensitivity": sens,
        "feature_priority": dict(feat.most_common()),
        "purchase_likelihood": dict(sorted(like.items())),
        "chosen_price": {"median": q(chosen_prices, 0.5), "p25": q(chosen_prices, 0.25), "p75": q(chosen_prices, 0.75), "avg": round(sum(chosen_prices) / len(chosen_prices), 1) if chosen_prices else None},
        "sample": sample,
    }


def write_csv(rows: list[dict], path: Path) -> None:
    fields = ["trial", "persona_path", "reward", "choice", "choice_label", "price",
              "price_threshold", "feature_priority", "purchase_likelihood",
              "age_bracket", "economic_motivation", "region", "socioeconomic_band",
              "gender_identity", "life_stage", "urbanicity", "income", "employment", "rationale"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_dashboard(summary: dict, path: Path) -> None:
    data = json.dumps(summary, ensure_ascii=False)
    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>马桶刷购物式选择 · Persona 1M × DeepSeek 模拟</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;margin:0;background:#f5f6f8;color:#1f2329}
.wrap{max-width:1100px;margin:0 auto;padding:24px 16px 60px}
h1{font-size:22px;margin:0 0 4px}
.sub{color:#646a73;font-size:13px;margin-bottom:20px}
.card{background:#fff;border-radius:10px;padding:16px 18px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.card h2{font-size:15px;margin:0 0 12px}
.chart{width:100%;height:360px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:760px){.grid2{grid-template-columns:1fr}}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:6px 8px;border-bottom:1px solid #eee;text-align:right}
th:first-child,td:first-child{text-align:left}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:16px}
.kpi{background:#fff;border-radius:10px;padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.kpi .v{font-size:22px;font-weight:700}
.kpi .l{font-size:12px;color:#646a73;margin-top:2px}
.small{color:#646a73;font-size:12px}
.concl li{margin:6px 0;line-height:1.6}
</style></head><body><div class="wrap">
<h1>马桶刷「购物式选择」模拟结果</h1>
<div class="sub">Persona 1M · 北美人群 1000 人 × DeepSeek（deepseek-chat）· 10 款真实在售马桶刷 + “都不买” · 数据为 AI 模拟，非真实市场调研</div>
<div class="card"><h2>核心结论</h2><ul class="concl" id="concl"></ul></div>
<div class="kpis" id="kpis"></div>
<div class="card"><h2>市场份额（含“都不买”）</h2><div class="chart" id="cShare"></div><div class="small" id="tShare"></div></div>
<div class="grid2">
<div class="card"><h2>价格敏感度：可接受价位 × 经济动机</h2><div class="chart" id="cThr"></div><div class="small" id="tThr"></div></div>
<div class="card"><h2>购买意向分布（1–5）</h2><div class="chart" id="cLike"></div><div class="small" id="tLike"></div></div>
</div>
<div class="card"><h2>分群偏好：选择 × 年龄段（份额 %）</h2><div class="chart" id="cAge"></div><div class="small" id="tAge"></div></div>
<div class="grid2">
<div class="card"><h2>分群偏好：选择 × 经济动机（份额 %）</h2><div class="chart" id="cEcon"></div><div class="small" id="tEcon"></div></div>
<div class="card"><h2>最看重属性</h2><div class="chart" id="cFeat"></div><div class="small" id="tFeat"></div></div>
</div>
<div class="card"><h2>样本构成（北美校验）</h2><div id="sampleTables" class="small"></div></div>
<script>
const S = __DATA__;
const P = S.products;
const M = S.market_share;
const order = Object.keys(M);
function fmt(v){return v==null?'–':v;}
const ms = M;
const buyers = order.filter(k=>k!=='none_of_these');
const topk = buyers.map(k=>[k,ms[k]]).sort((a,b)=>b[1].count-a[1].count)[0];
const noneRate = ms['none_of_these'].share_pct;
const sens = S.price_sensitivity;
let sensLine='';
if(Object.keys(sens).length){const es=Object.entries(sens).sort((a,b)=>b[1].avg_threshold-a[1].avg_threshold);sensLine=`最能接受高价的群体是「${es[0][0]}」(${es[0][1].avg_threshold})，最在意价格的是「${es[es.length-1][0]}」(${es[es.length-1][1].avg_threshold})`;}
document.getElementById('concl').innerHTML=[
`销冠：${P[topk[0]].name}（$${P[topk[0]].price}），拿下 ${topk[1].share_pct}% 份额，是北美 ${S.n} 个虚拟消费者票选第一。`,
`「都不买」占 ${noneRate}%，货架整体吸引力${noneRate<10?'强':'中等'}。`,
`平均可接受价位档 ${S.price_threshold.avg}（满分5），中位成交价 $${fmt(S.chosen_price.median)}。`,
sensLine||''
].map(x=>`<li>${x}</li>`).join('');
const kpi=[["样本人数",S.n,"人（全部北美）"],["通过率",(S.sample.reward_rate*100)+"%","verifier"],["中位选择价","$"+fmt(S.chosen_price.median),""],["平均可接受价",fmt(S.price_threshold.avg)+"/5","1–5 档"]];
document.getElementById('kpis').innerHTML=kpi.map(([v,l,s])=>`<div class="kpi"><div class="v">${v}</div><div class="l">${l} · ${s}</div></div>`).join('');
function mk(id,opt){const el=document.getElementById(id);if(window.echarts){const c=echarts.init(el);c.setOption(opt);window.addEventListener('resize',()=>c.resize());}else{el.innerHTML='<p>图表库加载失败，请查看下方文字表。</p>';}}
mk('cShare',{tooltip:{trigger:'item',formatter:p=>`${p.name}<br/>$${P[p.dataIndex]?P[p.dataIndex].price:'–'} · ${p.value} 人 · ${p.percent}%`},series:[{type:'pie',radius:['38%','68%'],center:['50%','52%'],itemStyle:{borderRadius:6,borderColor:'#fff',borderWidth:2},label:{formatter:'{b}\\n{d}%'},data:order.map(k=>({name:P[k].name,value:M[k].count}))}]});
document.getElementById('tShare').textContent = order.map(k=>`${P[k].name} $${P[k].price}：${M[k].count} 人（${M[k].share_pct}%）`).join(' ｜ ');
const econs=Object.keys(S.price_sensitivity);
mk('cThr',{tooltip:{trigger:'axis'},legend:{type:'scroll'},grid:{left:40,right:16,top:36,bottom:28,containLabel:true},xAxis:{type:'category',data:['1(最低)','2','3','4','5(最高)'],axisLabel:{fontSize:11}},yAxis:{type:'value'},series:econs.map(e=>({name:e,type:'line',smooth:true,symbolSize:6,data:['1','2','3','4','5'].map(t=>S.price_sensitivity[e].threshold_dist[t]||0)}))});
document.getElementById('tThr').textContent = econs.map(e=>`${e}：平均可接受价档 ${S.price_sensitivity[e].avg_threshold}（n=${S.price_sensitivity[e].n}）`).join(' ｜ ');
const likes=Object.keys(S.purchase_likelihood).map(Number);
mk('cLike',{tooltip:{trigger:'axis'},grid:{left:40,right:16,top:16,bottom:28,containLabel:true},xAxis:{type:'category',data:likes.map(String)},yAxis:{type:'value'},series:[{type:'bar',barWidth:'55%',data:likes.map(t=>S.purchase_likelihood[t])}]});
document.getElementById('tLike').textContent = likes.map(t=>`${t} 分：${S.purchase_likelihood[t]} 人`).join(' ｜ ');
const ages=Object.keys(S.choice_x_age);
const topOrder=order.filter(k=>k!=='none_of_these').sort((a,b)=>M[b].count-M[a].count).slice(0,6);
mk('cAge',{tooltip:{trigger:'axis',valueFormatter:v=>v+'%'},legend:{type:'scroll',top:0},grid:{left:40,right:16,top:40,bottom:40,containLabel:true},xAxis:{type:'category',data:ages,axisLabel:{fontSize:11}},yAxis:{type:'value',axisLabel:{formatter:'{value}%'}},series:topOrder.map(k=>({name:P[k].name,type:'bar',stack:'a',data:ages.map(a=>S.choice_x_age[a][k].share_pct)}))});
document.getElementById('tAge').textContent = ages.map(a=>`${a}（n=${Object.values(S.choice_x_age[a]).reduce((s,v)=>s+v.count,0)}）`).join(' ｜ ');
const econs2=Object.keys(S.choice_x_econ);
mk('cEcon',{tooltip:{trigger:'axis',valueFormatter:v=>v+'%'},legend:{type:'scroll',top:0},grid:{left:40,right:16,top:40,bottom:28,containLabel:true},xAxis:{type:'category',data:econs2,axisLabel:{fontSize:11}},yAxis:{type:'value',axisLabel:{formatter:'{value}%'}},series:topOrder.map(k=>({name:P[k].name,type:'bar',stack:'a',data:econs2.map(e=>S.choice_x_econ[e][k].share_pct)}))});
document.getElementById('tEcon').textContent = econs2.map(e=>`${e}：avg 可接受档 ${S.price_sensitivity[e]?.avg_threshold??'–'}`).join(' ｜ ');
const feats=Object.keys(S.feature_priority);
mk('cFeat',{tooltip:{trigger:'axis'},grid:{left:40,right:16,top:16,bottom:28,containLabel:true},xAxis:{type:'category',data:feats},yAxis:{type:'value'},series:[{type:'bar',barWidth:'50%',data:feats.map(f=>S.feature_priority[f])}]});
document.getElementById('tFeat').textContent = feats.map(f=>`${f}：${S.feature_priority[f]} 人`).join(' ｜ ');
const sm=S.sample;
function tbl(title,d){const rows=Object.entries(d).sort((a,b)=>b[1]-a[1]);return `<h3>${title}</h3><table><tr><th>取值</th><th>人数</th></tr>${rows.map(([k,v])=>`<tr><td>${k}</td><td>${v}</td></tr>`).join('')}</table>`;}
document.getElementById('sampleTables').innerHTML = tbl('年龄段',sm.age)+tbl('经济动机',sm.econ)+tbl('地区',sm.region)+tbl('性别',sm.gender)+tbl('社经层级',sm.socio);
</script></div></body></html>"""
    path.write_text(html.replace("__DATA__", data), encoding="utf-8")


def main() -> None:
    job_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "jobs" / "survey-toilet-brush-choice-n1000"
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else REPO / "results" / "toilet-brush-demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = collect_trials(job_dir)
    print(f"collected {len(rows)} trials from {job_dir.name}")
    summary = summarize(rows)
    write_csv(rows, out_dir / "toilet_brush_raw.csv")
    (out_dir / "toilet_brush_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_dashboard(summary, out_dir / "toilet_brush_dashboard.html")
    ms = summary["market_share"]
    print("market share:", ", ".join(f"{v['name']} {v['share_pct']}%" for v in ms.values()))
    print("wrote:", out_dir / "toilet_brush_raw.csv",
          out_dir / "toilet_brush_summary.json",
          out_dir / "toilet_brush_dashboard.html")


if __name__ == "__main__":
    main()
