#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aggregate v3 (no availability column) into summary."""
import json, glob
from collections import Counter
from pathlib import Path

ROOT = Path("/Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B")
JOB = ROOT / "jobs/survey-shower-liner-6asin-v3-n1000"
OUT = ROOT / "results/shower-liner-6asin-v3"

# v3: availability column removed from product cards; F price set to $8.99
PRODUCT_META = {
    "A": {"brand": "AmazerBath", "price": 18.99, "rating": 4.5, "reviews": 4156, "avail": "现货"},
    "B": {"brand": "jssablo", "price": 7.19, "rating": 4.4, "reviews": 1872, "avail": "现货"},
    "C": {"brand": "LQFMEHOT", "price": 7.09, "rating": 4.6, "reviews": 974, "avail": "现货"},
    "D": {"brand": "Laumyasof", "price": 9.99, "rating": 4.4, "reviews": 16, "avail": "现货"},
    "E": {"brand": "Dependable", "price": 9.99, "rating": 4.3, "reviews": 116, "avail": "现货"},
    "F": {"brand": "MuuXii", "price": 8.99, "rating": 4.4, "reviews": 10, "avail": "现货"},
}

def load():
    out = []
    for f in sorted(glob.glob(str(JOB / "*/artifacts/app/output/survey_result.json"))):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        out.append({a["questionId"]: a for a in d.get("answers", [])})
    return out

def pct(c, t): return {k: round(100.0*v/t, 1) for k, v in c.most_common()}
def share(rows, qid):
    c = Counter()
    for a in rows:
        v = a.get(qid, {}).get("value")
        if isinstance(v, list):
            for x in v: c[x] += 1
        elif v: c[v] += 1
    return pct(c, len(rows) or 1), len(rows)

def main():
    rows = load()
    n = len(rows)
    print(f"loaded {n}")
    choice, _ = share(rows, "q_choice")
    page_browse, _ = share(rows, "q_page_browse")
    page_buy, _ = share(rows, "q_page_buy")
    factor_most, _ = share(rows, "q_factor_most")
    factor_second, _ = share(rows, "q_factor_second")
    redline, _ = share(rows, "q_listing_redline")
    material_pref, _ = share(rows, "q_material_pref")
    transparency_pref, _ = share(rows, "q_transparency_pref")
    badge_effect, _ = share(rows, "q_badge_effect")
    switch_trigger, _ = share(rows, "q_switch_trigger")
    dp, _ = share(rows, "q_display_position_influence")

    importance = {}
    for qid in ["q_importance_title","q_importance_image","q_importance_bullets","q_importance_aplus",
                "q_importance_attr","q_importance_price","q_importance_reviews","q_importance_trust"]:
        vals = [a.get(qid,{}).get("value") for a in rows]
        vals = [float(v) for v in vals if isinstance(v,(int,float))]
        importance[qid.replace("q_importance_","")] = round(sum(vals)/len(vals),2) if vals else None

    pa, _ = share(rows, "q_price_acceptance")
    price_accept_mean = round(sum(float(k)*v for k,v in pa.items())/sum(pa.values()),2) if pa else None

    reject_top = {}
    for oid in "ABCDEF":
        c = Counter()
        for a in rows:
            v = a.get(f"q_reject_{oid}",{}).get("value")
            if isinstance(v, list):
                for x in v:
                    if x != "already_chosen": c[x] += 1
        reject_top[oid] = c.most_common(8)

    sample_choice_why = {}
    for p in "ABCDEF":
        why = [a.get("q_choice",{}).get("rationale","").strip()
               for a in rows if a.get("q_choice",{}).get("value")==p and len(a.get("q_choice",{}).get("rationale",""))>20]
        sample_choice_why[p] = why[:6]

    summary = {
        "meta": {"survey_a": {"id":"shower_liner_6asin_v3","n":n,"job":"survey-shower-liner-6asin-v3-n1000"},
                 "products": PRODUCT_META,
                 "note": "v3: availability column removed; F price=$8.99; all percentages are % of person-answers"},
        "choice": {
            "share_pct": choice, "reject_top_reasons": reject_top,
            "page_browse_pct": page_browse, "page_buy_pct": page_buy,
            "factor_most_pct": factor_most, "factor_second_pct": factor_second,
            "importance_mean_1to5": importance, "redline_pct": redline,
            "material_pref_pct": material_pref, "transparency_pref_pct": transparency_pref,
            "badge_effect_pct": badge_effect, "switch_trigger_pct": switch_trigger,
            "price_accept_mean": price_accept_mean,
            "display_position_influence_pct": dp,
        },
        "sample_choice_why": sample_choice_why,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/"summary_full.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("choice:", json.dumps(choice, ensure_ascii=False))
    print("display_position:", json.dumps(dp, ensure_ascii=False))
    print("reject_A:", json.dumps(reject_top["A"], ensure_ascii=False))
    print("written:", OUT/"summary_full.json")

if __name__ == "__main__":
    main()
