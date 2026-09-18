#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aggregate shower-liner experiment results (both surveys) into summary JSON + CSV.

Surveys:
  A) survey-shower-liner-6asin-n1000   — shelf choice (share / reject / page / factors / listing)
  B) survey-shower-liner-journey-n1000 — decision journey (first-click / info / buy / consider / fallback)

Outputs (under results/shower-liner-6asin-experiment/):
  shower_liner_summary.json
  survey_choice_raw.csv      (one row per persona, survey A answers)
  survey_journey_raw.csv     (one row per persona, survey B answers)
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B")
OUT = ROOT / "results/shower-liner-6asin-experiment"

PRODUCT_META = {
    "A": {"brand": "AmazerBath", "price": 18.99, "rating": 4.5, "reviews": 4156, "avail": "no featured offer"},
    "B": {"brand": "jssablo", "price": 7.19, "rating": 4.4, "reviews": 1872, "avail": "in stock"},
    "C": {"brand": "LQFMEHOT", "price": 7.09, "rating": 4.6, "reviews": 974, "avail": "in stock"},
    "D": {"brand": "Laumyasof", "price": 9.99, "rating": 4.4, "reviews": 16, "avail": "new listing"},
    "E": {"brand": "Dependable", "price": 9.99, "rating": 4.3, "reviews": 116, "avail": "only 10 left"},
    "F": {"brand": "MuuXii", "price": None, "rating": 4.4, "reviews": 10, "avail": "unavailable"},
}
OPTION_ORDER = ["A", "B", "C", "D", "E", "F", "none_of_these"]


def load_surveys(job_dir: Path) -> list[dict]:
    files = sorted(glob.glob(str(job_dir / "*/artifacts/app/output/survey_result.json")))
    out = []
    for f in files:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        answers = {a["questionId"]: a for a in d.get("answers", [])}
        out.append(answers)
    return out


def pct(c: Counter, total: int) -> dict:
    return {k: round(100.0 * v / total, 1) for k, v in c.items()}


def share_of(answers_list: list[dict], qid: str) -> tuple[dict, int]:
    c = Counter()
    for a in answers_list:
        v = a.get(qid, {}).get("value")
        if isinstance(v, list):
            for x in v:
                c[x] += 1
        elif v:
            c[v] += 1
    total = len(answers_list)
    return pct(c, total), total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--choice-dir", default=str(ROOT / "jobs/survey-shower-liner-6asin-n1000"))
    ap.add_argument("--journey-dir", default=str(ROOT / "jobs/survey-shower-liner-journey-n1000"))
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)

    # ---------------- Survey A: shelf choice ----------------
    choice = load_surveys(Path(args.choice_dir))
    print(f"survey A (shelf choice) 答卷数: {len(choice)}")

    choice_share, nA = share_of(choice, "q_choice")
    reject = {}
    for oid in ["A", "B", "C", "D", "E", "F"]:
        reject[oid], _ = share_of(choice, f"q_reject_{oid}")
    page_browse, _ = share_of(choice, "q_page_browse")
    page_buy, _ = share_of(choice, "q_page_buy")
    factor_most, _ = share_of(choice, "q_factor_most")
    factor_second, _ = share_of(choice, "q_factor_second")
    importance = {}
    for qid in ["q_importance_title", "q_importance_image", "q_importance_bullets",
                "q_importance_aplus", "q_importance_attr", "q_importance_price",
                "q_importance_reviews", "q_importance_trust"]:
        vals = []
        for a in choice:
            v = a.get(qid, {}).get("value")
            if isinstance(v, (int, float)):
                vals.append(float(v))
        importance[qid.replace("q_importance_", "")] = (round(sum(vals) / len(vals), 2) if vals else None)
    redline, _ = share_of(choice, "q_listing_redline")
    material_pref, _ = share_of(choice, "q_material_pref")
    transparency_pref, _ = share_of(choice, "q_transparency_pref")
    badge_effect, _ = share_of(choice, "q_badge_effect")
    switch_trigger, _ = share_of(choice, "q_switch_trigger")
    price_accept, _ = share_of(choice, "q_price_acceptance")
    purchase_intent, _ = share_of(choice, "q_purchase_intent")

    # ---------------- Survey B: decision journey ----------------
    journey = load_surveys(Path(args.journey_dir))
    print(f"survey B (journey) 答卷数: {len(journey)}")

    first_click, nB = share_of(journey, "q_first_click")
    click_info, _ = share_of(journey, "q_click_info")
    buy_decision, _ = share_of(journey, "q_buy_decision")
    consider_other, _ = share_of(journey, "q_consider_other")
    next_choice, _ = share_of(journey, "q_next_choice")
    fallback, _ = share_of(journey, "q_fallback")
    page_search, _ = share_of(journey, "q_page_search")
    overall_factor, _ = share_of(journey, "q_overall_factor")

    # Funnel: first_click -> (would buy at first detail) -> consider -> fallback
    buy_yes = buy_decision.get("buy_now", 0) + buy_decision.get("likely_buy", 0)

    # Cross: among those who first-clicked X, what is their fallback share
    first_to_fallback = defaultdict(Counter)
    for a in journey:
        fc = a.get("q_first_click", {}).get("value")
        fb = a.get("q_fallback", {}).get("value")
        if fc and fb:
            first_to_fallback[fc][fb] += 1
    first_to_fallback_pct = {
        k: pct(c, sum(c.values())) for k, c in first_to_fallback.items()
    }

    # Reasons (sample texts) for key decisions
    def reasons(qid: str, n: int = 6) -> list[str]:
        out = []
        for a in journey:
            r = (a.get(qid, {}).get("rationale") or "").strip()
            if len(r) >= 10:
                out.append(r)
            if len(out) >= n:
                break
        return out

    # Reject reason pool for survey A: for each rejected product, top reasons
    reject_top = {}
    for oid in ["A", "B", "C", "D", "E", "F"]:
        c = Counter()
        for a in choice:
            v = a.get(f"q_reject_{oid}", {}).get("value")
            if isinstance(v, list):
                for x in v:
                    if x != "already_chosen":
                        c[x] += 1
        reject_top[oid] = c.most_common(8)

    summary = {
        "meta": {
            "survey_a": {"id": "shower_liner_6asin_v1", "n": nA,
                         "job": "survey-shower-liner-6asin-n1000"},
            "survey_b": {"id": "shower_liner_6asin_journey_v1", "n": nB,
                         "job": "survey-shower-liner-journey-n1000"},
            "products": PRODUCT_META,
            "note": "all percentages are % of person-answers; multi-choice sums may exceed 100%",
        },
        "choice": {
            "share_pct": choice_share,
            "reject_top_reasons": reject_top,
            "page_browse_pct": page_browse,
            "page_buy_pct": page_buy,
            "factor_most_pct": factor_most,
            "factor_second_pct": factor_second,
            "importance_mean_1to5": importance,
            "redline_pct": redline,
            "material_pref_pct": material_pref,
            "transparency_pref_pct": transparency_pref,
            "badge_effect_pct": badge_effect,
            "switch_trigger_pct": switch_trigger,
            "price_accept_mean": (round(sum(float(k) * v for k, v in price_accept.items()) / sum(price_accept.values()), 2) if price_accept else None),
        },
        "journey": {
            "first_click_pct": first_click,
            "click_info_pct": click_info,
            "buy_decision_pct": buy_decision,
            "buy_yes_pct": round(100.0 * buy_yes / nB, 1) if nB else None,
            "consider_other_pct": consider_other,
            "next_choice_pct": next_choice,
            "fallback_pct": fallback,
            "page_search_pct": page_search,
            "overall_factor_pct": overall_factor,
            "first_to_fallback_pct": first_to_fallback_pct,
            "sample_first_click_reasons": reasons("q_first_click"),
            "sample_fallback_reasons": reasons("q_fallback"),
            "sample_buy_reasons": reasons("q_buy_decision"),
        },
    }

    (OUT / "shower_liner_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------------- CSVs ----------------
    def flat(a: dict, prefix: str = "") -> dict:
        row = {}
        for qid, ans in a.items():
            v = ans.get("value")
            if isinstance(v, list):
                v = "|".join(str(x) for x in v)
            row[qid] = v
            r = (ans.get("rationale") or "").strip()
            if r:
                row[f"{qid}_why"] = r
        return row

    choice_rows = [flat(a) for a in choice]
    if choice_rows:
        cols = list(dict.fromkeys(k for r in choice_rows for k in r))
        with open(OUT / "survey_choice_raw.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(choice_rows)

    journey_rows = [flat(a) for a in journey]
    if journey_rows:
        cols = list(dict.fromkeys(k for r in journey_rows for k in r))
        with open(OUT / "survey_journey_raw.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(journey_rows)

    print("written:", OUT)
    print("choice share:", json.dumps(choice_share, ensure_ascii=False))
    print("first_click:", json.dumps(first_click, ensure_ascii=False))
    print("fallback:", json.dumps(fallback, ensure_ascii=False))


if __name__ == "__main__":
    main()
