#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aggregate the 6-ASIN shower liner CLICK-JOURNEY experiment (n=1000).

Reads jobs/survey-shower-liner-journey-n1000/*/artifacts/app/output/survey_result.json
and writes results/shower-liner-journey/summary.json + raw.csv.
"""
from __future__ import annotations
import json, csv, glob, os
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B")
JOBS = ROOT / "jobs/survey-shower-liner-journey-n1000"
OUT = ROOT / "results/shower-liner-journey"

FILES = sorted(glob.glob(str(JOBS / "*/artifacts/app/output/survey_result.json")))
print("答卷数:", len(FILES))

OPTIONS = ["A", "B", "C", "D", "E", "F"]

def norm(v):
    if isinstance(v, list):
        return v
    if v is None:
        return []
    return [v]

def load():
    rows = []
    for f in FILES:
        d = json.load(open(f))
        ans = {a["questionId"]: a for a in d["answers"]}
        row = {}
        for a in d["answers"]:
            row[a["questionId"]] = a
        rows.append(row)
    return rows

rows = load()
N = len(rows)

def pct(n, base=None):
    b = N if base is None else base
    return round(100.0 * n / b, 1) if b else 0.0

def counter(qid, flatten=True):
    c = Counter()
    for r in rows:
        v = r[qid]["value"]
        for x in norm(v):
            c[x] += 1
    return c

def dist(qid):
    c = counter(qid)
    return {k: {"n": v, "pct": pct(v)} for k, v in c.most_common()}

def likert_mean(qid):
    vals = [r[qid]["value"] for r in rows if isinstance(r[qid]["value"], (int, float))]
    return round(sum(vals) / len(vals), 2) if vals else None

# ---------- 1. 决策漏斗 ----------
# 成交判定：按顺序 q_buy_first/second/third == buy_now；否则未在前三个成交
funnel = Counter()
first_click = Counter()
second_click = Counter()
third_click = Counter()
fallback = Counter()
detail_top = Counter()
consider = Counter()
buy1 = Counter(); buy2 = Counter(); buy3 = Counter()
for r in rows:
    fc = r["q_first_click"]["value"]
    first_click[fc] += 1
    b1 = r["q_buy_first"]["value"]
    buy1[b1] += 1
    if b1 == "buy_now":
        funnel[("final_buy", fc)] += 1
        continue
    sc = r["q_second_click"]["value"]
    second_click[sc] += 1
    b2 = r["q_buy_second"]["value"]
    buy2[b2] += 1
    if b2 == "buy_now":
        funnel[("final_buy", sc)] += 1
        continue
    tc = r["q_third_click"]["value"]
    third_click[tc] += 1
    b3 = r["q_buy_third"]["value"]
    buy3[b3] += 1
    if b3 == "buy_now":
        funnel[("final_buy", tc)] += 1
        continue
    funnel[("final_buy", "none")] += 1
    fallback[r["q_fallback"]["value"]] += 1
    consider[r["q_consider_more"]["value"]] += 1
    detail_top[r["q_detail_top"]["value"]] += 1

final_buy_dist = Counter()
for (k, opt), n in funnel.items():
    if k == "final_buy":
        final_buy_dist[opt] = n
# 兜底也算"最想买"
# 各款 最终成交 / 最想买（兜底）/ 首点 份额
first_share = {k: pct(v) for k, v in first_click.most_common()}
final_share = {k: pct(v) for k, v in final_buy_dist.most_common()}
fallback_share = {k: pct(v) for k, v in fallback.most_common()}

# ---------- 2. 各题分布 ----------
click_drivers = dist("q_click_drivers")
detail_info = dist("q_detail_info")
notbuy_first = dist("q_notbuy_first")
notbuy_second = dist("q_notbuy_second")
notbuy_third = dist("q_notbuy_third")
fallback_blocker = dist("q_fallback_blocker")
rejects = {}
final_ordered = {}
favorite_held = {}
for oid in OPTIONS:
    c = counter(f"q_reject_{oid}")
    rejects[oid] = {k: {"n": v, "pct": pct(v)} for k, v in c.most_common()}
    final_ordered[oid] = c.get("final_purchase", 0)
    favorite_held[oid] = c.get("fallback_favorite", 0)

page_browse = dist("q_page_browse")
page_buy = dist("q_page_buy")
factor_most = dist("q_factor_most")
factor_second = dist("q_factor_second")
redline = dist("q_listing_redline")
material_pref = dist("q_material_pref")
transparency_pref = dist("q_transparency_pref")
badge = dist("q_badge_effect")
switch = dist("q_switch_trigger")

likerts = {
    qid: likert_mean(qid) for qid in [
        "q_importance_title", "q_importance_image", "q_importance_bullets",
        "q_importance_aplus", "q_importance_attr", "q_importance_price",
        "q_importance_reviews", "q_importance_trust",
        "q_price_acceptance", "q_purchase_intent",
    ]
}

# ---------- 3. 拒绝理由 Top（全部款合并） ----------
all_reject_reasons = Counter()
for oid in OPTIONS:
    for k, v in rejects[oid].items():
        if k not in ("final_purchase", "fallback_favorite"):
            all_reject_reasons[k] += v["n"]
reject_top = {k: {"n": v, "pct": pct(v)} for k, v in all_reject_reasons.most_common()}

# ---------- 4. 交叉：首点 vs 最终成交 vs 兜底 对齐表 ----------
align = []
for oid in OPTIONS:
    align.append({
        "option": oid,
        "first_click_pct": first_share.get(oid, 0),
        "final_buy_pct": final_share.get(oid, 0),
        "fallback_fav_pct": fallback_share.get(oid, 0),
        "final_ordered_n": final_ordered.get(oid, 0),
        "held_back_fav_n": favorite_held.get(oid, 0),
    })

# ---------- 5. 理由文本抽样 ----------
def samples(qid, key=None, n=6):
    out = []
    for r in rows:
        txt = (r[qid].get("rationale") or "").strip()
        if not txt:
            continue
        val = r[qid]["value"]
        if key is not None and val != key:
            continue
        out.append(txt[:220])
        if len(out) >= n:
            break
    return out

quote_first = {oid: samples("q_first_click", oid, 2) for oid in OPTIONS}
quote_fallback = {oid: samples("q_fallback", oid, 2) for oid in OPTIONS}

summary = {
    "n": N,
    "pass_rate": 1.0,
    "first_click": first_share,
    "second_click_dist": {k: pct(v) for k, v in second_click.most_common()},
    "third_click_dist": {k: pct(v) for k, v in third_click.most_common()},
    "final_buy": final_share,
    "fallback_favorite": fallback_share,
    "final_ordered_n": final_ordered,
    "held_back_favorite_n": favorite_held,
    "alignment": align,
    "funnel_not_buy_first3_pct": final_share.get("none", 0),
    "buy_first_decisions": {k: pct(v) for k, v in buy1.most_common()},
    "buy_second_decisions": {k: pct(v) for k, v in buy2.most_common()},
    "buy_third_decisions": {k: pct(v) for k, v in buy3.most_common()},
    "consider_more": {k: pct(v) for k, v in consider.most_common()},
    "click_drivers": click_drivers,
    "detail_info": detail_info,
    "detail_top": {k: pct(v) for k, v in detail_top.most_common()},
    "notbuy_first": notbuy_first,
    "notbuy_second": notbuy_second,
    "notbuy_third": notbuy_third,
    "fallback_blocker": fallback_blocker,
    "reject_reasons": rejects,
    "reject_top": reject_top,
    "page_browse": page_browse,
    "page_buy": page_buy,
    "factor_most": factor_most,
    "factor_second": factor_second,
    "listing_redline": redline,
    "material_pref": material_pref,
    "transparency_pref": transparency_pref,
    "badge_effect": badge,
    "switch_trigger": switch,
    "likert_means": likerts,
    "quotes_first_click": quote_first,
    "quotes_fallback": quote_fallback,
}

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

# raw csv
qids_order = [q for q in rows[0].keys()]
with open(OUT / "raw.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    hdr = ["trial"] + qids_order
    w.writerow(hdr)
    for i, r in enumerate(rows):
        line = [i]
        for q in qids_order:
            v = r[q]["value"]
            if isinstance(v, list):
                v = "|".join(map(str, v))
            line.append(v)
        w.writerow(line)

print("written:", OUT / "summary.json", "| raw.csv rows:", len(rows))
print("\n=== 关键数字 ===")
print("首点:", {k: v for k, v in first_share.items()})
print("最终成交:", {k: v for k, v in final_share.items()})
print("兜底最想买:", {k: v for k, v in fallback_share.items()})
