#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aggregate baseline arm vs reshuffled-position arm.

Baseline arm (already run):  jobs/survey-shower-liner-6asin-n1000   order A B C D E F
Reshuffled arm (this run):   jobs/survey-shower-liner-reshuffled-n1000 order C B D E A F

Position map (baseline -> reshuffled):
  A:1->5  B:2->2  C:3->1  D:4->3  E:5->4  F:6->6

Outputs under results/shower-liner-6asin-experiment/:
  position_effect_summary.json
  position_buy_compare.csv
  position_first_click_compare.csv
  reshuffled_raw.csv
"""
from __future__ import annotations
import csv, glob, json
from collections import Counter
from pathlib import Path

ROOT = Path("/Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B")
OUT = ROOT / "results/shower-liner-6asin-experiment"

BASELINE = ROOT / "jobs/survey-shower-liner-6asin-n1000"
RESHUFFLED = ROOT / "jobs/survey-shower-liner-reshuffled-n1000"
JOURNEY = ROOT / "jobs/survey-shower-liner-journey-n1000"

BASELINE_ORDER = ["A", "B", "C", "D", "E", "F"]
RESHUFFLED_ORDER = ["C", "B", "D", "E", "A", "F"]
PRODUCTS = ["A", "B", "C", "D", "E", "F"]
PRODUCT_META = {
    "A": ("AmazerBath", 18.99, "高端翡翠绿 EVA + 铜扣，$18.99"),
    "B": ("jssablo", 7.19, "蓝色 3D 立方 EVA + 磁铁，$7.19"),
    "C": ("LQFMEHOT", 7.09, "蓝色 Art-Deco 水波纹 EVA + 磁铁，$7.09"),
    "D": ("Laumyasof", 9.99, "绿色 3D 卵石 2 件装 EVA，$9.99"),
    "E": ("Dependable", 9.99, "纯黑简约 EVA + 磁铁，$9.99"),
    "F": ("MuuXii", None, "透明波点 EVA + 挂钩，无货"),
}


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


def likert_mean(rows: list[dict], qid: str):
    vals = [a.get(qid, {}).get("value") for a in rows]
    vals = [float(v) for v in vals if isinstance(v, (int, float))]
    return round(sum(vals) / len(vals), 2) if vals else None


def reject_top(rows: list[dict], oid: str) -> list:
    c = Counter()
    for a in rows:
        v = a.get(f"q_reject_{oid}", {}).get("value")
        if isinstance(v, list):
            for x in v:
                if x != "already_chosen":
                    c[x] += 1
    n = len(rows) or 1
    return [(k, v, round(100.0 * v / n, 1)) for k, v in c.most_common(6)]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base = load_surveys(BASELINE)
    resh = load_surveys(RESHUFFLED)
    journey = load_surveys(JOURNEY)
    print(f"baseline n={len(base)}  reshuffled n={len(resh)}  journey n={len(journey)}")

    base_buy = share(base, "q_choice")
    resh_buy = share(resh, "q_choice")
    resh_first = share(resh, "q_first_click")
    journey_first = share(journey, "q_first_click")  # baseline arm's first-click proxy
    resh_pos_aware = share(resh, "q_position_aware")
    resh_rank_imp = likert_mean(resh, "q_importance_reviews")  # reuse reviews likert as trust proxy

    # Position vs buy share table
    rows_out = []
    for p in PRODUCTS:
        bp = BASELINE_ORDER.index(p) + 1
        rp = RESHUFFLED_ORDER.index(p) + 1
        rows_out.append({
            "product": p,
            "brand": PRODUCT_META[p][0],
            "blurb": PRODUCT_META[p][2],
            "baseline_position": bp,
            "reshuffled_position": rp,
            "position_change": rp - bp,  # negative = moved up
            "baseline_buy_pct": base_buy.get(p, 0.0),
            "reshuffled_buy_pct": resh_buy.get(p, 0.0),
            "buy_pct_delta": round(resh_buy.get(p, 0.0) - base_buy.get(p, 0.0), 1),
            "reshuffled_first_click_pct": resh_first.get(p, 0.0),
        })

    # Sample rationales
    def sample_reason(rows, qid, want=None, n=4):
        out = []
        for a in rows:
            v = a.get(qid, {}).get("value")
            r = (a.get(qid, {}).get("rationale") or "").strip()
            if want is not None and v != want:
                continue
            if len(r) >= 15:
                out.append(r[:350])
            if len(out) >= n:
                break
        return out

    summary = {
        "meta": {
            "baseline_arm": {"n": len(base), "order": BASELINE_ORDER},
            "reshuffled_arm": {"n": len(resh), "order": RESHUFFLED_ORDER},
            "journey_arm_first_click_proxy": {"n": len(journey), "order": BASELINE_ORDER},
            "products": {p: {"brand": PRODUCT_META[p][0], "price": PRODUCT_META[p][1],
                              "blurb": PRODUCT_META[p][2]} for p in PRODUCTS},
        },
        "buy_compare": rows_out,
        "reshuffled_first_click_pct": resh_first,
        "journey_first_click_pct_baseline_order": journey_first,
        "reshuffled_position_aware_pct": resh_pos_aware,
        "baseline_reject_top": {p: reject_top(base, p) for p in PRODUCTS},
        "reshuffled_reject_top": {p: reject_top(resh, p) for p in PRODUCTS},
        "sample_reshuffled_first_click_reasons": sample_reason(resh, "q_first_click"),
        "sample_position_affected_reasons": sample_reason(resh, "q_position_aware", want="noticed_affected"),
    }
    (OUT / "position_effect_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # CSV: buy compare
    with open(OUT / "position_buy_compare.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["商品", "品牌", "一句话", "基线位置(A序)", "打乱位置(价格序)",
                    "位置变化(负=上升)", "基线购买%", "打乱购买%", "购买%变化"])
        for r in rows_out:
            w.writerow([r["product"], r["brand"], r["blurb"],
                        r["baseline_position"], r["reshuffled_position"],
                        r["position_change"], r["baseline_buy_pct"],
                        r["reshuffled_buy_pct"], r["buy_pct_delta"]])

    # CSV: reshuffled raw
    with open(OUT / "reshuffled_raw.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["first_click", "first_click_why", "buy", "buy_why",
                     "position_aware", "position_aware_why", "factor_most"])
        for a in resh:
            def gv(q): return a.get(q, {}).get("value")
            def gr(q): return (a.get(q, {}).get("rationale") or "").strip()
            w.writerow([gv("q_first_click"), gr("q_first_click"),
                        gv("q_choice"), gr("q_choice"),
                        gv("q_position_aware"), gr("q_position_aware"),
                        gv("q_factor_most")])

    print("\n=== BUY COMPARE (baseline vs reshuffled) ===")
    for r in rows_out:
        print(f"  {r['product']} {r['brand']:12s} pos {r['baseline_position']}->{r['reshuffled_position']}  "
              f"buy {r['baseline_buy_pct']}% -> {r['reshuffled_buy_pct']}%  (Δ{r['buy_pct_delta']:+.1f})")
    print("\nreshuffled first-click:", resh_first)
    print("reshuffled position-aware:", resh_pos_aware)
    print("\nwritten:", OUT)


if __name__ == "__main__":
    main()
