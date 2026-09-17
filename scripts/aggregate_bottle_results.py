#!/usr/bin/env python3
"""Aggregate the water-bottle shopping survey results into CSV / JSON.

Usage:
  uv run python scripts/aggregate_bottle_results.py [job_dir] [out_dir]

Reads every trial under jobs/survey-water-bottle-choice-n1000/:
  - artifacts/app/output/survey_result.json   (answers + rationale)
  - config.json                               (persona_path)
  - verifier/reward.txt                       (pass/fail)
and joins persona dimensions (age_bracket, economic_motivation, region, ...)
from the persona YAML. Writes:
  - <out>/bottle_choice_1000_raw.csv
  - <out>/bottle_choice_1000_summary.json
  - <out>/bottle_choice_1000_dashboard.html  (self-contained, ECharts CDN)
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
    "fuguang_316": {"name": "富光 316 保温杯", "price": 39.9, "tier": "低"},
    "nalgene_sustain": {"name": "Nalgene Sustain 32oz", "price": 119.0, "tier": "中"},
    "beijixiong_316": {"name": "杯具熊 316 保温杯", "price": 129.0, "tier": "中"},
    "mijia_bottle": {"name": "米家保温杯", "price": 179.0, "tier": "中高"},
    "zojirushi_sm_sz": {"name": "象印 SM-SZ", "price": 229.0, "tier": "高"},
    "stanley_quencher": {"name": "Stanley Quencher", "price": 319.0, "tier": "高"},
    "none_of_these": {"name": "都不买", "price": 0.0, "tier": "无"},
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


# Bilingual keyword patterns for per-product review profiles (from purchase rationale).
REVIEW_KW = {
    "材质/内胆": r"316|stainless|steel|内胆|材质|food.grade|食品级|material",
    "保温性能": r"保温|保冷|保暖|insulat|keep.*(hot|cold)|temperature",
    "价格/性价比": r"价格|便宜|贵|预算|性价比|price|afford|budget|value|cost|cheap|expensive",
    "外观/颜值": r"外观|颜值|好看|设计|颜色|可爱|萌|漂亮|时尚|look|design|color|style|cute|aesthet|appearance",
    "容量": r"容量|大容量|够装|capacity|size|liter|ml|ounce|oz",
    "品牌/信赖": r"品牌|信赖|口碑|国民|日本|靠谱|brand|trust|quality|reput|reliable|premium|japan",
    "轻便/便携": r"便携|轻|方便|携带|通勤|上班|light|portable|carry|handle|easy|convenient",
    "环保": r"环保|塑料|回收|环境|eco|recycl|environment|plastic",
}


def choice_x(dim: str, rows: list[dict]) -> dict:
    """Cross-tab: dimension value × choice, share % per group, sorted by group size desc."""
    by = defaultdict(Counter)
    for r in rows:
        v = (r.get(dim) or "unknown").strip() or "unknown"
        by[v][r["choice"]] += 1
    return {
        k: {p: {"count": c.get(p, 0), "share_pct": pct(c.get(p, 0), sum(c.values()))} for p in PRODUCTS}
        for k, c in sorted(by.items(), key=lambda kv: -sum(kv[1].values()))
    }


def product_reviews(rows: list[dict]) -> dict:
    """Per-product review profile: how often buyers' rationale mentions each aspect."""
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


# Mention patterns per product (rationale-level, case-insensitive, CN+EN).
MENTION_PAT = {
    "fuguang_316": r"fuguang|富光",
    "nalgene_sustain": r"nalgene",
    "beijixiong_316": r"beijixiong|杯具熊|beddybear",
    "mijia_bottle": r"mijia|米家|xiaomi|小米",
    "zojirushi_sm_sz": r"zojirushi|象印",
    "stanley_quencher": r"stanley|quencher",
}
REJECT_SIGNAL = re.compile(
    r"too (expensive|pricey|costly)|太贵|贵|not worth|不值得|overpriced|溢价|pass|skip|"
    r"however|but|although|though|instead|yet|not (insulated|insulation|worth)|不保温|算了|"
    r"doesn't (fit|help)|not my (style|taste)|no (need|use) for", re.I
)


def consideration(rows: list[dict]) -> dict:
    """For every product: votes, how many non-buyers mentioned it (considered but rejected),
    where they went instead, and sample rejection rationales (for 0-vote products)."""
    out = {}
    for prod, pat in MENTION_PAT.items():
        chosen = sum(1 for r in rows if r["choice"] == prod)
        others = [r for r in rows if r["choice"] != prod and r["rationale"] and re.search(pat, r["rationale"], re.I)]
        went = Counter(r["choice"] for r in others)
        went_top = {k: v for k, v in went.most_common(4)}
        samples = []
        core_fit = None
        if chosen == 0:
            for r in others:
                if REJECT_SIGNAL.search(r["rationale"]):
                    samples.append(r["rationale"][:170])
                    if len(samples) >= 2:
                        break
            # For the flagship 0-vote case (Stanley): what did its "best-fit" personas do?
            if prod == "stanley_quencher":
                core = [r for r in others if r.get("socioeconomic_band") == "High income"
                        or r.get("age_bracket") == "18-24" or r.get("region") == "North America"]
                core_fit = {"n": len(core), "went_to": dict(Counter(r["choice"] for r in core).most_common(4))}
        out[prod] = {"votes": chosen, "considered_by": len(others), "went_to": went_top,
                     "sample_rationales": samples, "core_fit": core_fit}
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
    # price sensitivity: avg accepted threshold per economic motivation
    sens = {}
    for eco, c in thr_x_econ.items():
        tot = sum(c.values())
        sens[eco] = {
            "n": tot,
            "avg_threshold": round(sum(int(k) * v for k, v in c.items()) / tot, 2),
            "threshold_dist": dict(sorted(c.items())),
        }
    # actual chosen price stats
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
              "gender_identity", "life_stage", "income", "employment", "rationale"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_dashboard(summary: dict, path: Path) -> None:
    """Self-contained HTML dashboard (ECharts CDN, graceful text fallback)."""
    data = json.dumps(summary, ensure_ascii=False)

    # ---- auto narrative (leadership-readable takeaways) ----
    ms = summary["market_share"]
    buyers = {k: v for k, v in ms.items() if k != "none_of_these"}
    topk = max(buyers.items(), key=lambda kv: kv[1]["count"])
    none_rate = ms["none_of_these"]["share_pct"]
    sens = summary["price_sensitivity"]
    avg_thr = summary["price_threshold"]["avg"]
    if sens:
        best = max(sens.items(), key=lambda kv: kv[1]["avg_threshold"])
        worst = min(sens.items(), key=lambda kv: kv[1]["avg_threshold"])
        sens_line = f"最能接受高价的群体是「{best[0]}」（平均可接受价档 {best[1]['avg_threshold']}），最在意价格的是「{worst[0]}」（{worst[1]['avg_threshold']}）"
    else:
        sens_line = ""
    ages = summary["choice_x_age"]
    age_diff = ""
    if len(ages) >= 2:
        def top_share(d):
            t = max(((k, v["share_pct"]) for k, v in d.items() if k != "none_of_these"),
                    key=lambda kv: kv[1])
            return t
        amin = min(ages, key=lambda a: int(a.split("-")[0]) if "-" in a else 999)
        amax = max(ages, key=lambda a: int(a.split("-")[0]) if "-" in a else 0)
        ta, tb = top_share(ages[amin]), top_share(ages[amax])
        age_diff = f"年龄差异：{amin} 群体最偏爱「{ta[0] and summary['products'][ta[0]]['name']}」（{ta[1]}%），而{amax} 群体更倾向「{tb[0] and summary['products'][tb[0]]['name']}」（{tb[1]}%）"
    narrative = [
        f"销冠：{topk[1]['name']}（¥{topk[1]['price']}），拿下 {topk[1]['share_pct']}% 的份额，是 1000 个虚拟消费者票选第一名。",
        f"「都不买」占 {none_rate}%，说明货架整体有吸引力，仍有提升空间。",
        f"1000 人平均可接受价位档为 {avg_thr}（满分 5），中位成交价 ¥{summary['chosen_price']['median']}。",
        sens_line + "。",
    ]
    if age_diff:
        narrative.append(age_diff + "。")
    bullets = "".join(f"<li>{b}</li>" for b in narrative)

    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>保温杯购物式选择 · Persona 1M × DeepSeek 模拟</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;margin:0;background:#f5f6f8;color:#1f2329}
.wrap{max-width:1080px;margin:0 auto;padding:24px 16px 60px}
h1{font-size:22px;margin:0 0 4px}
.sub{color:#646a73;font-size:13px;margin-bottom:20px}
.card{background:#fff;border-radius:10px;padding:16px 18px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.card h2{font-size:15px;margin:0 0 12px}
.chart{width:100%;height:340px}
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
<h1>保温杯「购物式选择」模拟结果</h1>
<div class="sub">Persona 1M 全球分层随机 1000 人 × DeepSeek（deepseek-chat）· 生成于 <span id="ts"></span> · 6 款真实竞品 + “都不买” · 数据为 AI 模拟，非真实市场调研</div>
<div class="card"><h2>核心结论（自动生成）</h2><ul class="concl">__BULLETS__</ul></div>
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
<div class="card"><h2>样本构成（全球分层校验）</h2><div id="sampleTables" class="small"></div></div>
<script>
const S = __DATA__;
document.getElementById('ts').textContent = new Date().toLocaleString();
const P = S.products;
const choiceNames = Object.fromEntries(Object.keys(P).map(k=>[k,P[k].name]));
const M = S.market_share;
const order = Object.keys(M);
function fmt(v){return v==null?'–':v;}
// KPI
const kpi=[["样本人数",S.n,"人"],["通过率",(S.sample.reward_rate*100)+"%","verifier"],["中位选择价","¥"+fmt(S.chosen_price.median),"含都不买=0"],["平均可接受价","¥"+fmt(S.price_threshold.avg)+"0","1–5 档"]];
document.getElementById('kpis').innerHTML=kpi.map(([v,l,s])=>`<div class="kpi"><div class="v">${v}</div><div class="l">${l} · ${s}</div></div>`).join('');
function mk(id,opt){const el=document.getElementById(id);if(window.echarts){const c=echarts.init(el);c.setOption(opt);window.addEventListener('resize',()=>c.resize());}else{el.innerHTML='<p>图表库加载失败，请查看下方文字表。</p>';}}
// Share
mk('cShare',{tooltip:{trigger:'item',formatter:p=>`${p.name}<br/>¥${P[p.dataIndex]?P[p.dataIndex].price:'–'} · ${p.value} 人 · ${p.percent}%`},series:[{type:'pie',radius:['38%','68%'],center:['50%','52%'],itemStyle:{borderRadius:6,borderColor:'#fff',borderWidth:2},label:{formatter:'{b}\\n{d}%'},data:order.map(k=>({name:P[k].name,value:M[k].count}))}]});
document.getElementById('tShare').textContent = order.map(k=>`${P[k].name} ¥${P[k].price}：${M[k].count} 人（${M[k].share_pct}%）`).join(' ｜ ');
// Threshold by econ
const econs=Object.keys(S.price_sensitivity);
mk('cThr',{tooltip:{trigger:'axis'},legend:{type:'scroll'},grid:{left:40,right:16,top:36,bottom:28,containLabel:true},xAxis:{type:'category',data:['1(最低)','2','3','4','5(最高)'],axisLabel:{fontSize:11}},yAxis:{type:'value'},series:econs.map(e=>({name:e,type:'line',smooth:true,symbolSize:6,data:['1','2','3','4','5'].map(t=>S.price_sensitivity[e].threshold_dist[t]||0)}))});
document.getElementById('tThr').textContent = econs.map(e=>`${e}：平均可接受价档 ${S.price_sensitivity[e].avg_threshold}（n=${S.price_sensitivity[e].n}）`).join(' ｜ ');
// Likelihood
const likes=Object.keys(S.purchase_likelihood).map(Number);
mk('cLike',{tooltip:{trigger:'axis'},grid:{left:40,right:16,top:16,bottom:28,containLabel:true},xAxis:{type:'category',data:likes.map(String)},yAxis:{type:'value'},series:[{type:'bar',barWidth:'55%',data:likes.map(t=>S.purchase_likelihood[t])}]});
document.getElementById('tLike').textContent = likes.map(t=>`${t} 分：${S.purchase_likelihood[t]} 人`).join(' ｜ ');
// Age x choice share
const ages=Object.keys(S.choice_x_age);
const topk = ['beijixiong_316','mijia_bottle','zojirushi_sm_sz','stanley_quencher','fuguang_316','nalgene_sustain','none_of_these'];
mk('cAge',{tooltip:{trigger:'axis',valueFormatter:v=>v+'%'},legend:{type:'scroll',top:0},grid:{left:40,right:16,top:40,bottom:40,containLabel:true},xAxis:{type:'category',data:ages,axisLabel:{fontSize:11}},yAxis:{type:'value',axisLabel:{formatter:'{value}%'}},series:topk.map(k=>({name:P[k].name,type:'bar',stack:'a',data:ages.map(a=>S.choice_x_age[a][k].share_pct)}))});
document.getElementById('tAge').textContent = ages.map(a=>`${a}（n=${ages.length?Object.values(S.choice_x_age[a]).reduce((s,v)=>s+v.count,0):0}）`).join(' ｜ ');
// Econ x choice share
const econs2=Object.keys(S.choice_x_econ);
mk('cEcon',{tooltip:{trigger:'axis',valueFormatter:v=>v+'%'},legend:{type:'scroll',top:0},grid:{left:40,right:16,top:40,bottom:28,containLabel:true},xAxis:{type:'category',data:econs2,axisLabel:{fontSize:11}},yAxis:{type:'value',axisLabel:{formatter:'{value}%'}},series:topk.map(k=>({name:P[k].name,type:'bar',stack:'a',data:econs2.map(e=>S.choice_x_econ[e][k].share_pct)}))});
document.getElementById('tEcon').textContent = econs2.map(e=>`${e}：avg 可接受档 ${S.price_sensitivity[e]?.avg_threshold??'–'}`).join(' ｜ ');
// Feature
const feats=Object.keys(S.feature_priority);
mk('cFeat',{tooltip:{trigger:'axis'},grid:{left:40,right:16,top:16,bottom:28,containLabel:true},xAxis:{type:'category',data:feats},yAxis:{type:'value'},series:[{type:'bar',barWidth:'50%',data:feats.map(f=>S.feature_priority[f])}]});
document.getElementById('tFeat').textContent = feats.map(f=>`${f}：${S.feature_priority[f]} 人`).join(' ｜ ');
// Sample tables
const sm=S.sample;
function tbl(title,d){const rows=Object.entries(d).sort((a,b)=>b[1]-a[1]);return `<h3>${title}</h3><table><tr><th>取值</th><th>人数</th></tr>${rows.map(([k,v])=>`<tr><td>${k}</td><td>${v}</td></tr>`).join('')}</table>`;}
document.getElementById('sampleTables').innerHTML = tbl('年龄段',sm.age)+tbl('经济动机',sm.econ)+tbl('地区',sm.region)+tbl('性别',sm.gender);
</script></div></body></html>"""
    path.write_text(html.replace("__DATA__", data).replace("__BULLETS__", bullets), encoding="utf-8")


def main() -> None:
    job_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "jobs" / "survey-water-bottle-choice-n1000"
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else REPO / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = collect_trials(job_dir)
    print(f"collected {len(rows)} trials from {job_dir.name}")
    summary = summarize(rows)
    write_csv(rows, out_dir / "bottle_choice_1000_raw.csv")
    (out_dir / "bottle_choice_1000_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_dashboard(summary, out_dir / "bottle_choice_1000_dashboard.html")
    ms = summary["market_share"]
    print("market share:", ", ".join(f"{v['name']} {v['share_pct']}%" for v in ms.values()))
    print("wrote:", out_dir / "bottle_choice_1000_raw.csv",
          out_dir / "bottle_choice_1000_summary.json",
          out_dir / "bottle_choice_1000_dashboard.html")


if __name__ == "__main__":
    main()
