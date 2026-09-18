#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aggregate the 3 rank-position arms into a cross-arm comparison.

Arms (same 1000 amazon-NA cohort, same seed):
  a-first: A B C D E F   (baseline)
  c-first: C A B D E F   (C promoted to #1)
  f-first: F A B C D E   (unavailable F at #1, position-lure test)

Outputs under results/shower-liner-6asin-experiment/:
  rank_arms_summary.json
  rank_first_click_pivot.csv   (product x arm -> first-click %)
  rank_buy_pivot.csv           (product x arm -> buy %)
  rank_raw.csv                 (one row per arm-persona)
"""
from __future__ import annotations
import csv, glob, json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B")
OUT = ROOT / "results/shower-liner-6asin-experiment"

ARMS = {
    "a-first": (ROOT / "jobs/survey-shower-liner-rank-a-first-n1000", ["A","B","C","D","E","F"]),
    "c-first": (ROOT / "jobs/survey-shower-liner-rank-c-first-n1000", ["C","A","B","D","E","F"]),
    "f-first": (ROOT / "jobs/survey-shower-liner-rank-f-first-n1000", ["F","A","B","C","D","E"]),
}
PRODUCTS = ["A","B","C","D","E","F"]
PRODUCT_META = {
    "A": ("AmazerBath", 18.99, 27),
    "B": ("jssablo", 7.19, 41),
    "C": ("LQFMEHOT", 7.09, 124),
    "D": ("Laumyasof", 9.99, 129),
    "E": ("Dependable", 9.99, 203),
    "F": ("MuuXii", None, 856),
}


def load_arm(job_dir: Path) -> list[dict]:
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


def share(rows: list[dict], qid: str) -> dict:
    c = Counter()
    for a in rows:
        v = a.get(qid, {}).get("value")
        if isinstance(v, list):
            for x in v:
                c[x] += 1
        elif v:
            c[v] += 1
    t = len(rows) or 1
    return {k: round(100.0 * v / t, 1) for k, v in c.most_common()}


def likert_mean(rows: list[dict], qid: str) -> float | None:
    vals = [a.get(qid, {}).get("value") for a in rows]
    vals = [float(v) for v in vals if isinstance(v, (int, float))]
    return round(sum(vals) / len(vals), 2) if vals else None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    arms_data = {}
    for arm, (jdir, order) in ARMS.items():
        rows = load_arm(jdir)
        arms_data[arm] = rows
        print(f"{arm}: {len(rows)} valid answers")

    # Pivot tables: first-click % and buy % per product per arm
    fc_pct = {arm: share(rows, "q_first_click") for arm, rows in arms_data.items()}
    buy_pct = {arm: share(rows, "q_choice") for arm, rows in arms_data.items()}
    rank_aware = {arm: share(rows, "q_rank_aware") for arm, rows in arms_data.items()}
    rank_imp = {arm: likert_mean(rows, "q_rank_importance") for arm, rows in arms_data.items()}
    page_search = {arm: share(rows, "q_page_search") for arm, rows in arms_data.items()}

    # Position-effect table: for each product, its position in each arm vs first-click share
    pos_effect = []
    for p in PRODUCTS:
        row = {"product": p, "brand": PRODUCT_META[p][0]}
        for arm, (jdir, order) in ARMS.items():
            row[f"{arm}_pos"] = order.index(p) + 1
            row[f"{arm}_first_click_%"] = fc_pct[arm].get(p, 0.0)
            row[f"{arm}_buy_%"] = buy_pct[arm].get(p, 0.0)
        pos_effect.append(row)

    # Sample rationales for the lure arm (f-first)
    sample_lure = []
    for a in arms_data.get("f-first", []):
        r = (a.get("q_first_click", {}).get("rationale") or "").strip()
        fc = a.get("q_first_click", {}).get("value")
        if len(r) >= 10 and fc == "F":
            sample_lure.append({"first_click": fc, "why": r[:300]})
        if len(sample_lure) >= 8:
            break

    # rank_aware rationales: noticed + affected
    sample_aware = []
    for arm, rows in arms_data.items():
        for a in rows:
            if a.get("q_rank_aware", {}).get("value") == "noticed_affected":
                r = (a.get("q_rank_aware", {}).get("rationale") or "").strip()
                if len(r) >= 10:
                    sample_aware.append({"arm": arm, "why": r[:300]})
                break

    summary = {
        "meta": {
            "arms": {arm: {"n": len(rows), "display_order": order}
                     for arm, (jdir, order) in ARMS.items()
                     for rows in [arms_data[arm]]},
            "products": {p: {"brand": PRODUCT_META[p][0], "price": PRODUCT_META[p][1],
                              "bestseller_rank": PRODUCT_META[p][2]} for p in PRODUCTS},
        },
        "first_click_pct_by_arm": fc_pct,
        "buy_pct_by_arm": buy_pct,
        "rank_aware_pct_by_arm": rank_aware,
        "rank_importance_mean_1to5": rank_imp,
        "page_search_pct_by_arm": page_search,
        "position_effect_table": pos_effect,
        "sample_lure_first_click_F": sample_lure,
        "sample_rank_affected": sample_aware,
    }
    (OUT / "rank_arms_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # CSV pivots
    with open(OUT / "rank_first_click_pivot.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["product", "brand", "bestseller_rank",
                    "a-first_pos", "a-first_first_click%",
                    "c-first_pos", "c-first_first_click%",
                    "f-first_pos", "f-first_first_click%"])
        for r in pos_effect:
            w.writerow([r["product"], r["brand"], PRODUCT_META[r["product"]][2],
                        r["a-first_pos"], r["a-first_first_click_%"],
                        r["c-first_pos"], r["c-first_first_click_%"],
                        r["f-first_pos"], r["f-first_first_click_%"]])

    with open(OUT / "rank_buy_pivot.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["product", "brand",
                    "a-first_buy%", "c-first_buy%", "f-first_buy%"])
        for r in pos_effect:
            w.writerow([r["product"], r["brand"],
                        r["a-first_buy_%"], r["c-first_buy_%"], r["f-first_buy_%"]])

    # Long raw CSV
    with open(OUT / "rank_raw.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["arm", "first_click", "first_click_why", "buy", "buy_why",
                     "rank_aware", "rank_aware_why", "rank_importance", "page_search"])
        for arm, rows in arms_data.items():
            for a in rows:
                def gv(q): return a.get(q, {}).get("value")
                def gr(q): return (a.get(q, {}).get("rationale") or "").strip()
                w.writerow([arm, gv("q_first_click"), gr("q_first_click"),
                            gv("q_choice"), gr("q_choice"),
                            gv("q_rank_aware"), gr("q_rank_aware"),
                            gv("q_rank_importance"), gv("q_page_search")])

    print("\n=== first-click % by arm ===")
    for arm in ARMS:
        print(arm, fc_pct[arm])
    print("=== buy % by arm ===")
    for arm in ARMS:
        print(arm, buy_pct[arm])
    print("=== rank_aware % ===")
    for arm in ARMS:
        print(arm, rank_aware[arm])
    print("=== rank_importance mean ===", rank_imp)
    print("\nwritten:", OUT)


if __name__ == "__main__":
    main()
