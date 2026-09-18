#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aggregate v2 (6asin + display-position-influence) into summary JSON + CSV."""
from __future__ import annotations
import csv, glob, json
from collections import Counter
from pathlib import Path

ROOT = Path("/Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B")
JOB = ROOT / "jobs/survey-shower-liner-6asin-v2-n1000"
OUT = ROOT / "results/shower-liner-6asin-v2"

PRODUCT_META = {
    "A": ("AmazerBath", 18.99, 4.5, 4156, "无购买按钮/仅配送通知"),
    "B": ("jssablo", 7.19, 4.4, 1872, "有货"),
    "C": ("LQFMEHOT", 7.09, 4.6, 974, "有货"),
    "D": ("Laumyasof", 9.99, 4.4, 16, "新品上架"),
    "E": ("Dependable", 9.99, 4.3, 116, "仅剩10件"),
    "F": ("MuuXii", None, 4.4, 10, "当前无货"),
}
REASON_ZH = {
    "price_too_high": "价格太贵", "price_suspicious": "太便宜/担心质量", "look": "不喜欢外观",
    "material": "材质不放心", "rating": "评分不够高", "few_reviews": "评价太少",
    "review_concern": "评价内容有疑虑", "brand": "品牌陌生", "size": "尺寸不合适",
    "missing_magnet": "缺磁铁/加重下摆", "transparency": "透明度不符", "pack": "包装规格不合",
    "info_incomplete": "信息不全", "availability": "缺货/配送问题", "other": "其他",
}
DP_ZH = {"not_at_all": "完全没有", "slightly": "一点点", "moderately": "中等",
         "very_much": "很大程度", "extremely": "极其严重"}


def load() -> list[dict]:
    files = sorted(glob.glob(str(JOB / "*/artifacts/app/output/survey_result.json")))
    out = []
    for f in files:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        out.append({a["questionId"]: a for a in d.get("answers", [])})
    return out


def share(rows, qid):
    c = Counter()
    for a in rows:
        v = a.get(qid, {}).get("value")
        if isinstance(v, list):
            for x in v: c[x] += 1
        elif v: c[v] += 1
    t = len(rows) or 1
    return {k: round(100.0*v/t, 1) for k, v in c.most_common()}, len(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load()
    n = len(rows)
    print(f"loaded {n} valid answers")

    choice, _ = share(rows, "q_choice")
    dp, _ = share(rows, "q_display_position_influence")
    page_browse, _ = share(rows, "q_page_browse")
    page_buy, _ = share(rows, "q_page_buy")
    factor_most, _ = share(rows, "q_factor_most")

    # reject reasons
    reject = {}
    for p in "ABCDEF":
        c = Counter()
        for a in rows:
            v = a.get(f"q_reject_{p}", {}).get("value")
            if isinstance(v, list):
                for x in v:
                    if x != "already_chosen": c[x] += 1
        reject[p] = [(k, v, round(100.0*v/n, 1)) for k, v in c.most_common(6)]

    # choice rationales by product
    choice_why = {}
    for p in "ABCDEF":
        why = [a.get("q_choice", {}).get("rationale", "").strip()
               for a in rows if a.get("q_choice", {}).get("value") == p]
        choice_why[p] = why

    summary = {
        "n": n,
        "products": {p: {"brand": m[0], "price": m[1], "rating": m[2],
                         "reviews": m[3], "avail_zh": m[4]} for p, m in PRODUCT_META.items()},
        "choice_pct": choice,
        "display_position_influence_pct": dp,
        "page_browse_pct": page_browse,
        "page_buy_pct": page_buy,
        "factor_most_pct": factor_most,
        "reject_top": reject,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # long CSV
    with open(OUT / "raw.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["choice", "choice_why", "reject_A", "reject_B", "reject_C",
                    "reject_D", "reject_E", "reject_F", "display_position_influence"])
        for a in rows:
            def gv(q): return a.get(q, {}).get("value")
            def gr(q): return (a.get(q, {}).get("rationale") or "").strip()
            w.writerow([gv("q_choice"), gr("q_choice"),
                        "|".join(gv("q_reject_A") or []) if isinstance(gv("q_reject_A"), list) else gv("q_reject_A"),
                        "|".join(gv("q_reject_B") or []) if isinstance(gv("q_reject_B"), list) else gv("q_reject_B"),
                        "|".join(gv("q_reject_C") or []) if isinstance(gv("q_reject_C"), list) else gv("q_reject_C"),
                        "|".join(gv("q_reject_D") or []) if isinstance(gv("q_reject_D"), list) else gv("q_reject_D"),
                        "|".join(gv("q_reject_E") or []) if isinstance(gv("q_reject_E"), list) else gv("q_reject_E"),
                        "|".join(gv("q_reject_F") or []) if isinstance(gv("q_reject_F"), list) else gv("q_reject_F"),
                        gv("q_display_position_influence")])

    print("choice:", json.dumps(choice, ensure_ascii=False))
    print("display_position:", json.dumps(dp, ensure_ascii=False))
    print("written:", OUT)


if __name__ == "__main__":
    main()
