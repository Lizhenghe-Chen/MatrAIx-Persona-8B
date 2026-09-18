#!/usr/bin/env python3
"""Aggregate the 6-ASIN shower-liner survey (single shelf, availability EXCLUDED as a factor).

Reads:  jobs/survey-shower-liner-6asin-n1000/<trial>/artifacts/app/output/survey_result.json
Writes: results/shower-liner-6asin-experiment/{summary.json, raw.csv}
"""
from __future__ import annotations

import csv
import glob
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "results" / "shower-liner-6asin"))
from build_task import (  # noqa: E402
    PRODUCTS, OPTION_ORDER, REJECT_OPTIONS, FACTOR_OPTIONS, PAGE_OPTIONS,
    REDLINE_OPTIONS, MATERIAL_OPTIONS, TRANSPARENCY_OPTIONS, BADGE_OPTIONS,
    SWITCH_OPTIONS,
)

JOB_SLUG = os.environ.get("JOB_SLUG", "survey-shower-liner-6asin-n1000")
OUT_DIR = REPO / "results" / "shower-liner-6asin-experiment"

OIDS = OPTION_ORDER
REJECT_LABEL = dict(REJECT_OPTIONS)
FACTOR_LABEL = dict(FACTOR_OPTIONS)
PAGE_LABEL = dict(PAGE_OPTIONS)
REDLINE_LABEL = dict(REDLINE_OPTIONS)
MATERIAL_LABEL = dict(MATERIAL_OPTIONS)
TRANSPARENCY_LABEL = dict(TRANSPARENCY_OPTIONS)
BADGE_LABEL = dict(BADGE_OPTIONS)
SWITCH_LABEL = dict(SWITCH_OPTIONS)

LIKERT_8 = [
    ("q_importance_title", "标题完整清晰（尺寸/材质/核心卖点）"),
    ("q_importance_image", "主图清晰、展示真实外观与效果"),
    ("q_importance_bullets", "五点卖点讲清利益"),
    ("q_importance_aplus", "A+ 内容 / 视频 / 品牌故事"),
    ("q_importance_attr", "属性与规格表完整（尺寸/材质/重量）"),
    ("q_importance_price", "价格与性价比"),
    ("q_importance_reviews", "评分 + 评论数量 + 评论内容"),
    ("q_importance_trust", "品牌信任与安全认证（无 BPA/无 PVC/无异味）"),
]

# 决策因素聚类（12 因素 -> 5 个商家易懂的大群）
SEGMENT_MAP = {
    "price_value": "价格价值驱动",
    "pack": "价格价值驱动",
    "material": "材质安全驱动",
    "listing": "信息与信任驱动",
    "brand": "信息与信任驱动",
    "rating": "口碑评分驱动",
    "reviews": "口碑评分驱动",
    "waterproof": "功能实用驱动",
    "magnet": "功能实用驱动",
    "size_fit": "功能实用驱动",
    "transparency": "外观偏好驱动",
    "appearance": "外观偏好驱动",
}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round((c - h) / d * 100, 1), round((c + h) / d * 100, 1)


def load_trials() -> list[dict]:
    trials = []
    pattern = str(REPO / "jobs" / JOB_SLUG / "*" / "artifacts" / "app" / "output" / "survey_result.json")
    for rp in sorted(glob.glob(pattern)):
        trial_dir = Path(rp).parents[3]
        cfg_p = trial_dir / "config.json"
        reward_p = trial_dir / "verifier" / "reward.txt"
        if not cfg_p.is_file():
            continue
        cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
        persona_path = str((cfg.get("agent") or {}).get("kwargs", {}).get("persona_path") or "")
        pid = persona_path.split("/")[-1].replace(".yaml", "")
        reward = None
        if reward_p.is_file():
            try:
                reward = float(reward_p.read_text().strip())
            except ValueError:
                reward = None
        gen = None
        try:
            persona = yaml.safe_load(Path(persona_path).read_text(encoding="utf-8"))
            gen = (persona.get("dimensions") or {}).get("demo_generation")
        except Exception:
            gen = None
        try:
            result = json.loads(Path(rp).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ans = {}
        for a in result.get("answers", []):
            if isinstance(a, dict) and a.get("questionId"):
                ans[a["questionId"]] = a.get("value")
                if a.get("rationale"):
                    ans[a["questionId"] + "_rationale"] = a["rationale"]
        trials.append({"persona_id": pid, "generation": gen, "reward": reward, "ans": ans})
    return trials


def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def pct(k: int, n: int) -> float:
    return round(k / n * 100, 1) if n else 0.0


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    trials = load_trials()
    n = len(trials)
    if n == 0:
        print("[error] no trials found — job not finished?")
        sys.exit(1)
    passed = sum(1 for t in trials if t["reward"] == 1.0)
    print(f"[load] {n} trials, pass={passed} ({pct(passed,n)}%)")

    products = {}
    for oid in OIDS:
        p = PRODUCTS[oid]
        products[oid] = {
            "option": oid, "asin": p["asin"], "brand": p["brand"], "name": p["name"],
            "price": p["price"], "rating": p["rating"], "reviews": p["reviews"],
            "rank": p.get("rank"), "material": p["material"], "look": p["look"],
            "points": p["points"], "size": p["size"], "pack": p["pack"],
            "url": f"https://www.amazon.com/dp/{p['asin']}",
        }

    # ---------- 1. 选择份额 ----------
    choice_c = Counter(t["ans"].get("q_choice") for t in trials)
    shares = {}
    for oid in OIDS + ["none_of_these"]:
        k = choice_c.get(oid, 0)
        lo, hi = wilson(k, n)
        shares[oid] = {"count": k, "pct": pct(k, n), "ci_lo": lo, "ci_hi": hi}
    ranked = sorted(OIDS, key=lambda o: -shares[o]["count"])

    # 选中产品的均价 / 平均评分 / 平均评论数
    def chosen_stat(field):
        vals = [PRODUCTS[t["ans"].get("q_choice")][field]
                for t in trials if t["ans"].get("q_choice") in PRODUCTS and PRODUCTS[t["ans"].get("q_choice")][field] is not None]
        return round(sum(vals) / len(vals), 2) if vals else None
    chosen_stats = {
        "mean_price": chosen_stat("price"), "mean_rating": chosen_stat("rating"),
        "mean_reviews": chosen_stat("reviews"),
    }

    # ---------- 2. 每款被拒原因矩阵（基数=未选该款的人）----------
    reject_matrix = {}
    for oid in OIDS:
        choosers = choice_c.get(oid, 0)
        base = n - choosers  # 未选该款的人
        rc = Counter()
        for t in trials:
            if t["ans"].get("q_choice") == oid:
                continue
            for r in as_list(t["ans"].get(f"q_reject_{oid}")):
                rc[r] += 1
        reject_matrix[oid] = {
            "nonchooser_base": base,
            "reasons": [{"reason": r, "label": REJECT_LABEL.get(r, r),
                         "count": rc[r], "pct_of_nonchoosers": pct(rc[r], base)}
                        for r, _ in REJECT_OPTIONS if rc[r] > 0],
            "top": [{"reason": r, "label": REJECT_LABEL.get(r, r),
                     "count": rc[r], "pct_of_nonchoosers": pct(rc[r], base)}
                    for r, _ in rc.most_common(5) if r != "already_chosen"],
        }

    # ---------- 3. 获选理由（首要/次要因素）----------
    fm = Counter(t["ans"].get("q_factor_most") for t in trials)
    fs = Counter(t["ans"].get("q_factor_second") for t in trials)
    factor_rank = [{"factor": f, "label": FACTOR_LABEL.get(f, f),
                    "most_pct": pct(fm[f], n), "second_pct": pct(fs[f], n)}
                   for f, _ in FACTOR_OPTIONS]
    factor_rank.sort(key=lambda x: -x["most_pct"])

    # 每款真实选择理由原话（抽样）
    rationale_samples = defaultdict(list)
    for t in trials:
        c = t["ans"].get("q_choice")
        r = t["ans"].get("q_choice_rationale")
        if c in OIDS and r and len(rationale_samples[c]) < 6:
            rationale_samples[c].append(r.strip())

    # ---------- 4. 搜索页数容忍度（浏览 vs 购买）----------
    def page_dist(qid):
        c = Counter(t["ans"].get(qid) for t in trials)
        order = [o for o, _ in PAGE_OPTIONS]
        rows = [{"code": o, "label": PAGE_LABEL[o], "count": c.get(o, 0),
                 "pct": pct(c.get(o, 0), n)} for o in order]
        return rows, c
    browse_rows, browse_c = page_dist("q_page_browse")
    buy_rows, buy_c = page_dist("q_page_buy")
    # 累积：愿意到第 2 页及以后 = 非 page1/unsure
    def reach(c, codes):
        return pct(sum(c.get(x, 0) for x in codes), n)
    page_tolerance = {
        "browse": browse_rows, "buy": buy_rows,
        "browse_beyond_p1_pct": reach(browse_c, ["page2", "page3", "page4_5", "beyond"]),
        "buy_beyond_p1_pct": reach(buy_c, ["page2", "page3", "page4_5", "beyond"]),
        "buy_p1_only_pct": pct(buy_c.get("page1", 0), n),
        "browse_p1_only_pct": pct(browse_c.get("page1", 0), n),
    }

    # ---------- 5. listing 要素重要性 likert ----------
    listing_importance = []
    for qid, zh in LIKERT_8:
        vals = [t["ans"].get(qid) for t in trials if isinstance(t["ans"].get(qid), (int, float))]
        mean = round(sum(vals) / len(vals), 2) if vals else None
        dist = Counter(vals)
        listing_importance.append({
            "qid": qid, "label_zh": zh, "mean": mean,
            "top2_pct": pct(sum(dist.get(x, 0) for x in (4, 5)), len(vals)),
            "dist_1to5": [dist.get(i, 0) for i in range(1, 6)],
        })
    listing_importance.sort(key=lambda x: -(x["mean"] or 0))

    # ---------- 6. 信息红线 ----------
    rl = Counter()
    for t in trials:
        for x in as_list(t["ans"].get("q_listing_redline")):
            rl[x] += 1
    redlines = [{"reason": r, "label": REDLINE_LABEL.get(r, r), "count": rl[r],
                 "pct": pct(rl[r], n)} for r, _ in REDLINE_OPTIONS]
    redlines.sort(key=lambda x: -x["pct"])

    # ---------- 7. 品类偏好 ----------
    def single_dist(qid, labels):
        c = Counter(t["ans"].get(qid) for t in trials)
        return [{"code": k, "label": labels.get(k, k), "count": c.get(k, 0),
                 "pct": pct(c.get(k, 0), n)} for k in labels]
    material_pref = single_dist("q_material_pref", MATERIAL_LABEL)
    transparency_pref = single_dist("q_transparency_pref", TRANSPARENCY_LABEL)
    badge = single_dist("q_badge_effect", BADGE_LABEL)
    switch = single_dist("q_switch_trigger", SWITCH_LABEL)
    badge_sway_pct = pct(sum(1 for t in trials if t["ans"].get("q_badge_effect") in ("yes_strongly", "yes_somewhat")), n)

    # ---------- 8. 态度量表 ----------
    def likert_mean(qid):
        vals = [t["ans"].get(qid) for t in trials if isinstance(t["ans"].get(qid), (int, float))]
        return round(sum(vals) / len(vals), 2) if vals else None
    attitudes = {
        "price_acceptance_mean": likert_mean("q_price_acceptance"),
        "purchase_intent_mean": likert_mean("q_purchase_intent"),
        "purchase_intent_top2_pct": pct(sum(1 for t in trials if t["ans"].get("q_purchase_intent") in (4, 5)), n),
    }

    # ---------- 9. 决策人群聚类（按首要因素 -> 5 大群）----------
    seg_counter = Counter()
    seg_choice = defaultdict(Counter)
    for t in trials:
        f = t["ans"].get("q_factor_most")
        seg = SEGMENT_MAP.get(f)
        if not seg:
            continue
        seg_counter[seg] += 1
        seg_choice[seg][t["ans"].get("q_choice")] += 1
    segments = {}
    for seg, c in seg_counter.most_common():
        rows = [{"option": o, "count": cc, "pct_within": pct(cc, c)}
                for o, cc in seg_choice[seg].most_common()]
        segments[seg] = {"n": c, "pct_of_all": pct(c, n), "winner": rows[0] if rows else None,
                         "shares": rows}

    # ---------- 10. 代际交叉（样本够才保留）----------
    gen_choice = defaultdict(Counter)
    gen_n = Counter()
    for t in trials:
        g = t["generation"] or "Unknown"
        gen_n[g] += 1
        gen_choice[g][t["ans"].get("q_choice")] += 1
    generations = {}
    for g, c in gen_n.most_common():
        if c < 40:
            continue
        generations[g] = {"n": c, "shares": [
            {"option": o, "pct": pct(gen_choice[g].get(o, 0), c)} for o in OIDS]}

    # ---------- 11. 每款诊断 ----------
    diagnosis = {}
    for oid in OIDS:
        chosen = [t for t in trials if t["ans"].get("q_choice") == oid]
        # 获选人群的首要因素
        cf = Counter(t["ans"].get("q_factor_most") for t in chosen)
        diagnosis[oid] = {
            "share_pct": shares[oid]["pct"],
            "top_choice_drivers": [{"factor": f, "label": FACTOR_LABEL.get(f, f),
                                    "pct_of_choosers": pct(cf[f], len(chosen))}
                                   for f, _ in cf.most_common(4)] if chosen else [],
            "top_rejections": reject_matrix[oid]["top"][:4],
            "sample_rationales": rationale_samples.get(oid, [])[:4],
        }

    summary = {
        "meta": {
            "task": "application/tasks/survey_shower-liner-6asin",
            "instrument": "shower_liner_6asin_v1",
            "job": JOB_SLUG, "n": n, "pass_rate": pct(passed, n),
            "design_note": "Availability / stock / buy-box state held constant and EXCLUDED as a factor; "
                           "F's missing price is presented as missing listing info, not a stock problem.",
            "questions": 26,
        },
        "products": products,
        "shares": shares, "ranked": ranked, "none_rate_pct": shares["none_of_these"]["pct"],
        "chosen_stats": chosen_stats,
        "reject_matrix": reject_matrix,
        "factor_rank": factor_rank,
        "page_tolerance": page_tolerance,
        "listing_importance": listing_importance,
        "redlines": redlines,
        "material_pref": material_pref, "transparency_pref": transparency_pref,
        "badge_effect": badge, "badge_sway_pct": badge_sway_pct,
        "switch_trigger": switch,
        "attitudes": attitudes,
        "segments": segments,
        "generations": generations,
        "diagnosis": diagnosis,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- raw csv ----------
    qids = (["q_choice"] +
            [f"q_reject_{o}" for o in OIDS] +
            ["q_page_browse", "q_page_buy", "q_factor_most", "q_factor_second"] +
            [q for q, _ in LIKERT_8] +
            ["q_listing_redline", "q_material_pref", "q_transparency_pref",
             "q_badge_effect", "q_switch_trigger", "q_price_acceptance", "q_purchase_intent"])
    with open(OUT_DIR / "raw.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["persona_id", "generation", "reward"] + qids + ["rationale"])
        for t in trials:
            row = [t["persona_id"], t["generation"], t["reward"]]
            for q in qids:
                v = t["ans"].get(q)
                row.append("|".join(v) if isinstance(v, list) else v)
            row.append(t["ans"].get("q_choice_rationale", ""))
            w.writerow(row)

    # ---------- console ----------
    print("\n=== 选择份额 ===")
    for oid in ranked + ["none_of_these"]:
        print(f"  {oid:14s} {shares[oid]['pct']:5.1f}%  (n={shares[oid]['count']})")
    print("\n=== 首要决策因素 Top ===")
    for x in factor_rank[:6]:
        print(f"  {x['label'][:42]:44s} {x['most_pct']:5.1f}%")
    print("\n=== listing 要素重要性均值（排序）===")
    for x in listing_importance:
        print(f"  {x['label_zh'][:30]:32s} {x['mean']}")
    print("\n=== 红线命中率 Top ===")
    for x in redlines[:6]:
        print(f"  {x['label'][:46]:48s} {x['pct']:5.1f}%")
    print("\n=== 页数容忍：仅第1页就下单 / 愿翻到第2页后 ===")
    print(f"  浏览: 仅P1 {page_tolerance['browse_p1_only_pct']}%  翻P2+ {page_tolerance['browse_beyond_p1_pct']}%")
    print(f"  购买: 仅P1 {page_tolerance['buy_p1_only_pct']}%  翻P2+ {page_tolerance['buy_beyond_p1_pct']}%")
    print("\n=== 决策人群聚类 ===")
    for seg, d in segments.items():
        w = d["winner"]
        print(f"  {seg:14s} n={d['n']:4d} ({d['pct_of_all']:4.1f}%)  winner={w['option'] if w else '-'} {w['pct_within'] if w else 0:.1f}%")
    print(f"\n[written] {OUT_DIR/'summary.json'}")
    print(f"[written] {OUT_DIR/'raw.csv'}")


if __name__ == "__main__":
    main()
