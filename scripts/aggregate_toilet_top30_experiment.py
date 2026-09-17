#!/usr/bin/env python3
"""Aggregate + analyze the TOP30 toilet-brush 2x2 factorial experiment.

Reads 4 arms (anon-rating / anon-norating / brand-rating / brand-norating),
joins product attributes + ground truth, and computes:
  - per-arm choice shares, none-rate, mean chosen price, factor ranking
  - 2x2 factorial effects (brand exposure, rating display, interaction)
  - persona segments (factor-driven clusters) and per-segment winners
  - rationale text signals (brand / rating / price / hygiene mentions)
  - simulated share vs real monthly sales / revenue rank correlation
Writes raw CSV + summary JSON (+ a compact TSV per persona).

Usage:
  uv run python scripts/aggregate_toilet_top30_experiment.py [jobs_dir] [out_dir]
"""

from __future__ import annotations

import csv
import glob
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
ARMS = ["anon-rating", "anon-norating", "brand-rating", "brand-norating"]

FACTOR_LABELS = {
    "price_value": "价格/性价比", "cleaning": "清洁效果", "hygiene": "卫生/速干",
    "design": "外观设计", "brand": "品牌信任", "material": "材质耐用",
    "holder": "收纳设计", "pack": "多件装价值", "reviews": "评分评论",
    "function_combo": "附加功能(通厕/缝隙刷)",
}
FACTOR_EN = {
    "price_value": "Price/value", "cleaning": "Cleaning", "hygiene": "Hygiene",
    "design": "Design", "brand": "Brand", "material": "Material",
    "holder": "Storage", "pack": "Multi-pack", "reviews": "Ratings", "function_combo": "Extra functions",
}


def load_sim() -> dict:
    return json.loads(
        (REPO / "results" / "toilet-brush-top30" / "toilet_brush_top30_simulation.json").read_text(encoding="utf-8")
    )


def load_ground_truth() -> dict:
    rows = []
    with open(REPO / "results" / "toilet-brush-top30" / "toilet_brush_top30_ground_truth.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return {r["id"]: r for r in rows}


def load_arm(arm: str, jobs_root: Path, suffix: str) -> list[dict]:
    trials: list[dict] = []
    pattern = str(jobs_root / f"survey-toilet-brush-top30-{arm}-{suffix}" / "*" / "artifacts" / "app" / "output" / "survey_result.json")
    for result_path in sorted(glob.glob(pattern)):
        trial_dir = Path(result_path).parents[3]
        cfg_path = trial_dir / "config.json"
        reward_path = trial_dir / "verifier" / "reward.txt"
        if not cfg_path.is_file():
            continue
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        persona_path = str((cfg.get("agent") or {}).get("kwargs", {}).get("persona_path") or "")
        persona_id = persona_path.split("/")[-1].replace(".yaml", "")
        reward = None
        if reward_path.is_file():
            try:
                reward = float(reward_path.read_text(encoding="utf-8").strip())
            except ValueError:
                reward = None
        try:
            result = json.loads(Path(result_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            result = None
        answers = {}
        if result:
            for a in result.get("answers", []):
                if isinstance(a, dict) and a.get("questionId"):
                    answers[a["questionId"]] = a.get("value")
                    if a.get("rationale"):
                        answers[a["questionId"] + "_rationale"] = a["rationale"]
        trials.append({
            "arm": arm, "persona_id": persona_id, "reward": reward,
            "choice": answers.get("q_choice"),
            "rationale": str(answers.get("q_choice_rationale") or ""),
            "answers": answers,
        })
    return trials


def spearman_rank(xs: list[float], ys: list[float]) -> float | None:
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    if len(xs) < 3:
        return None
    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    denom = n * (n * n - 1) / 6
    return 1 - d2 / denom if denom else None


def main() -> None:
    jobs_root = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "jobs"
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else REPO / "results" / "toilet-brush-top30-experiment"
    suffix = os.environ.get("JOB_SUFFIX", "n1000")
    out_dir.mkdir(parents=True, exist_ok=True)

    sim = load_sim()
    sim_products = sim["products"] if isinstance(sim, dict) and "products" in sim else sim
    if isinstance(sim_products, list):
        sim_products = {p["id"]: p for p in sim_products}
    gt = load_ground_truth()
    # 利润/FBA 等电商字段（来自 product_catalog.json，Excel 全字段导出）
    catalog_by_pid = {}
    cat_path = REPO / "results" / "toilet-brush-top30-experiment" / "product_catalog.json"
    if cat_path.exists():
        try:
            catalog_by_pid = {p["pid"]: p for p in json.loads(cat_path.read_text(encoding="utf-8"))}
        except Exception:
            catalog_by_pid = {}
    prod_meta = {}
    for pid in sorted(sim_products, key=lambda x: int(x[1:])):
        s = sim_products[pid]
        cat = catalog_by_pid.get(pid, {})
        prod_meta[pid] = {
            "pid": pid, "brand": s.get("brand", ""), "price": float(s.get("price", 0)),
            "ptype": s.get("ptype", ""), "material": s.get("material", ""),
            "head": s.get("head", ""), "pack": s.get("pack", ""),
            "rating": s.get("rating"), "reviews": s.get("reviews"),
            "gt_rank": int(gt.get(pid, {}).get("rank", 0) or 0),
            "gt_monthly_sales": float(gt.get(pid, {}).get("monthly_sales", 0) or 0),
            "gt_monthly_revenue": float(gt.get(pid, {}).get("monthly_revenue_usd", 0) or 0),
            "profit": cat.get("profit"),
        }

    # ---- load all arms ----
    all_rows: list[dict] = []
    for arm in ARMS:
        trials = load_arm(arm, jobs_root, suffix)
        if not trials:
            print(f"[warn] no trials for {arm} (n1000 not finished yet?)")
        for t in trials:
            pid = t["choice"]
            meta = prod_meta.get(pid) if pid else None
            row = {
                "arm": arm, "persona_id": t["persona_id"], "choice": pid,
                "rationale": t["rationale"], "reward": t["reward"],
                "chosen_price": meta["price"] if meta else None,
                "chosen_brand": meta["brand"] if meta else None,
                "chosen_rating": meta["rating"] if meta else None,
                "chosen_reviews": meta["reviews"] if meta else None,
                "gt_rank": meta["gt_rank"] if meta else None,
                "gt_monthly_sales": meta["gt_monthly_sales"] if meta else None,
                "gt_monthly_revenue": meta["gt_monthly_revenue"] if meta else None,
            }
            for qid in [
                "q_factor_most", "q_factor_second", "q_material_pref", "q_format_pref",
                "q_pack_pref", "q_badge_effect", "q_switch_trigger",
            ]:
                row[qid] = t["answers"].get(qid)
            for qid in [
                "q_price_acceptance", "q_purchase_intent", "q_importance_price",
                "q_importance_function", "q_importance_appearance", "q_importance_hygiene",
                "q_importance_reviews", "q_importance_brand", "q_refill_acceptance",
            ]:
                v = t["answers"].get(qid)
                row[qid] = v if isinstance(v, (int, float)) else None
            all_rows.append(row)

    # ---- CSV ----
    fieldnames = [
        "arm", "persona_id", "choice", "rationale", "reward",
        "chosen_price", "chosen_brand", "chosen_rating", "chosen_reviews",
        "gt_rank", "gt_monthly_sales", "gt_monthly_revenue",
        "q_factor_most", "q_factor_second", "q_material_pref", "q_format_pref",
        "q_pack_pref", "q_badge_effect", "q_switch_trigger",
        "q_price_acceptance", "q_purchase_intent", "q_importance_price",
        "q_importance_function", "q_importance_appearance", "q_importance_hygiene",
        "q_importance_reviews", "q_importance_brand", "q_refill_acceptance",
    ]
    csv_path = out_dir / "top30_2x2_raw.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in all_rows:
            w.writerow(r)

    # ---- per-arm summaries ----
    summary: dict = {"arms": {}, "n_personas_shared": None}
    share_by_arm: dict[str, dict[str, float]] = {}
    mean_price_by_arm: dict[str, float | None] = {}
    none_rate: dict[str, float] = {}
    factor_rank: dict[str, list] = {}
    for arm in ARMS:
        rows = [r for r in all_rows if r["arm"] == arm]
        n = len(rows)
        c = Counter(r["choice"] for r in rows if r["choice"])
        share = {pid: (c[pid] / n * 100) for pid in c}
        share_by_arm[arm] = share
        prices = [r["chosen_price"] for r in rows if r["chosen_price"] is not None]
        mean_price_by_arm[arm] = round(sum(prices) / len(prices), 2) if prices else None
        none_rate[arm] = (c.get("none_of_these", 0) / n * 100) if n else 0
        fm = Counter(r["q_factor_most"] for r in rows if r.get("q_factor_most"))
        fs = Counter(r["q_factor_second"] for r in rows if r.get("q_factor_second"))
        factor_rank[arm] = [
            {"factor": k, "label_en": FACTOR_EN.get(k, k), "label_zh": FACTOR_LABELS.get(k, k),
             "most_pct": round(v / n * 100, 1), "second_pct": round(fs[k] / n * 100, 1)}
            for k, v in fm.most_common()
        ]
        likerts = {}
        for qid in [
            "q_price_acceptance", "q_purchase_intent", "q_importance_price",
            "q_importance_function", "q_importance_appearance", "q_importance_hygiene",
            "q_importance_reviews", "q_importance_brand", "q_refill_acceptance",
        ]:
            vals = [r[qid] for r in rows if isinstance(r.get(qid), (int, float))]
            likerts[qid] = round(sum(vals) / len(vals), 2) if vals else None
        summary["arms"][arm] = {
            "n": n, "share": share, "mean_chosen_price": mean_price_by_arm[arm],
            "none_rate": round(none_rate[arm], 2), "factor_rank": factor_rank[arm],
            "likerts": likerts,
        }

    # ---- factorial effects (per product) ----
    effects = {}
    for pid in sorted(prod_meta, key=lambda x: int(x[1:])):
        s_anon_rating = share_by_arm.get("anon-rating", {}).get(pid, 0)
        s_anon_none = share_by_arm.get("anon-norating", {}).get(pid, 0)
        s_brand_rating = share_by_arm.get("brand-rating", {}).get(pid, 0)
        s_brand_none = share_by_arm.get("brand-norating", {}).get(pid, 0)
        brand_effect = ((s_brand_rating - s_anon_rating) + (s_brand_none - s_anon_none)) / 2
        rating_effect = ((s_anon_rating - s_anon_none) + (s_brand_rating - s_brand_none)) / 2
        interaction = (s_brand_rating - s_anon_rating) - (s_brand_none - s_anon_none)
        effects[pid] = {
            "pid": pid, "brand": prod_meta[pid]["brand"], "price": prod_meta[pid]["price"],
            "s_anon_rating": round(s_anon_rating, 2), "s_anon_none": round(s_anon_none, 2),
            "s_brand_rating": round(s_brand_rating, 2), "s_brand_none": round(s_brand_none, 2),
            "brand_effect_pp": round(brand_effect, 2),
            "rating_effect_pp": round(rating_effect, 2),
            "interaction_pp": round(interaction, 2),
            "gt_rank": prod_meta[pid]["gt_rank"],
            "gt_monthly_sales": prod_meta[pid]["gt_monthly_sales"],
            "gt_monthly_revenue": prod_meta[pid]["gt_monthly_revenue"],
        }
    summary["effects"] = effects

    # ---- aggregate brand-level effect ----
    brand_levels = {}
    for pid, e in effects.items():
        b = e["brand"]
        bl = brand_levels.setdefault(b, {"brand": b, "n": 0, "share_anon": 0, "share_brand": 0,
                                          "share_rating": 0, "share_norating": 0,
                                          "s_anon_rating": 0, "s_anon_none": 0, "s_brand_rating": 0, "s_brand_none": 0})
        bl["n"] += 1
        bl["s_anon_rating"] += e["s_anon_rating"]; bl["s_anon_none"] += e["s_anon_none"]
        bl["s_brand_rating"] += e["s_brand_rating"]; bl["s_brand_none"] += e["s_brand_none"]
    for b, bl in brand_levels.items():
        n = bl["n"]
        bl["share_anon"] = round((bl["s_anon_rating"] + bl["s_anon_none"]) / (2 * n), 2)
        bl["share_brand"] = round((bl["s_brand_rating"] + bl["s_brand_none"]) / (2 * n), 2)
        bl["share_rating"] = round((bl["s_anon_rating"] + bl["s_brand_rating"]) / (2 * n), 2)
        bl["share_norating"] = round((bl["s_anon_none"] + bl["s_brand_none"]) / (2 * n), 2)
        bl["brand_effect_pp"] = round(bl["share_brand"] - bl["share_anon"], 2)
        bl["rating_effect_pp"] = round(bl["share_rating"] - bl["share_norating"], 2)
    summary["brand_levels"] = sorted(brand_levels.values(), key=lambda x: -x["share_brand"])

    # ---- persona-level consistency & segments ----
    by_persona: dict[str, dict] = {}
    for r in all_rows:
        p = by_persona.setdefault(r["persona_id"], {"persona_id": r["persona_id"]})
        p[r["arm"]] = r["choice"]
    n_shared = len(by_persona)
    summary["n_personas_shared"] = n_shared

    # choice stability between arms (same persona picking the same product)
    stability = {}
    arm_pairs = [
        ("anon-norating", "anon-rating", "rating_effect"),
        ("brand-norating", "brand-rating", "rating_effect_brand"),
        ("anon-norating", "brand-norating", "brand_effect_anon"),
        ("anon-rating", "brand-rating", "brand_effect_rating"),
    ]
    for a, b, key in arm_pairs:
        same = sum(1 for p in by_persona.values() if p.get(a) and p.get(b) and p[a] == p[b])
        n = sum(1 for p in by_persona.values() if p.get(a) and p.get(b))
        stability[key] = {"n": n, "same_pct": round(same / n * 100, 1) if n else None}
    summary["persona_stability"] = stability

    # 互斥分群（按首要因素，一人一组，占比合计 100%）
    EXCLUSIVE_GROUPS = [
        ("price_driven", {"price_value"}),
        ("function_driven", {"cleaning", "function_combo"}),
        ("hygiene_driven", {"hygiene"}),
        ("design_driven", {"design"}),
        ("brand_driven", {"brand"}),
        ("reviews_driven", {"reviews", "pack", "material", "holder"}),
    ]
    base_rows = [r for r in all_rows if r["arm"] == "brand-rating"]
    n_base = len(base_rows) or 1
    excl: dict[str, dict] = {}
    assigned = 0
    for name, factors in EXCLUSIVE_GROUPS:
        rows = [r for r in base_rows if r.get("q_factor_most") in factors]
        assigned += len(rows)
        if not rows:
            continue
        n = len(rows)
        c = Counter(r["choice"] for r in rows)
        top = c.most_common(5)
        excl[name] = {
            "n": n, "pct": round(n / n_base * 100, 1),
            "mean_price": round(sum(r["chosen_price"] for r in rows if r["chosen_price"]) / n, 2),
            "top_choices": [{"pid": k, "pct": round(v / n * 100, 1), "brand": prod_meta.get(k, {}).get("brand")} for k, v in top],
        }
    summary["segments_exclusive"] = excl
    summary["segments_exclusive_assigned_pct"] = round(assigned / n_base * 100, 1)

    # 重叠分群（规则 OR 重要性高分，可重叠）
    seg_rules = [
        ("price_driven", lambda r: r["q_factor_most"] == "price_value" or (r.get("q_importance_price") or 0) >= 5),
        ("function_driven", lambda r: r["q_factor_most"] in ("cleaning", "function_combo") or (r.get("q_importance_function") or 0) >= 5),
        ("design_driven", lambda r: r["q_factor_most"] == "design" or (r.get("q_importance_appearance") or 0) >= 5),
        ("hygiene_driven", lambda r: r["q_factor_most"] == "hygiene" or (r.get("q_importance_hygiene") or 0) >= 5),
        ("brand_driven", lambda r: r["q_factor_most"] == "brand" or (r.get("q_importance_brand") or 0) >= 5),
        ("reviews_driven", lambda r: r["q_factor_most"] == "reviews" or (r.get("q_importance_reviews") or 0) >= 5),
    ]
    segments: dict[str, dict] = {}
    for name, rule in seg_rules:
        rows = [r for r in base_rows if rule(r)]
        if not rows:
            continue
        n = len(rows)
        c = Counter(r["choice"] for r in rows)
        top = c.most_common(5)
        segments[name] = {
            "n": n, "pct": round(n / len(base_rows) * 100, 1) if base_rows else 0,
            "mean_price": round(sum(r["chosen_price"] for r in rows if r["chosen_price"]) / n, 2),
            "top_choices": [{"pid": k, "pct": round(v / n * 100, 1), "brand": prod_meta.get(k, {}).get("brand")} for k, v in top],
        }
    summary["segments"] = segments

    # ---- rationale signals ----
    sig_re = {
        "brand_mention": re.compile(r"\b(clorox|forasto|mr\.?siga|oshang|hamitor|oxo|fazmoss|holaloha|setsail|lovloy|sellemer|aonez|uptronic|osameda|wsedor|dealsgogo|hohoky|simplehuman|savega)\b", re.I),
        "rating_mention": re.compile(r"rating|review|star|4\.[0-9]", re.I),
        "price_mention": re.compile(r"price|\$|cost|budget|afford|expensive|cheap", re.I),
        "hygiene_mention": re.compile(r"hygien|disposable|sanitar|germ|bacteria", re.I),
        "function_mention": re.compile(r"clean|scrub|plung|under-rim|deep", re.I),
        "look_mention": re.compile(r"look|design|color|modern|stylish|sleek|aesthetic", re.I),
    }
    sig_summary = {}
    for arm in ARMS:
        rows = [r for r in all_rows if r["arm"] == arm and r["rationale"]]
        n = len(rows)
        sig_summary[arm] = {
            k: round(sum(1 for r in rows if rx.search(r["rationale"])) / n * 100, 1)
            for k, rx in sig_re.items()
        }
    summary["rationale_signals"] = sig_summary

    # ---- 偏好分布（badge / switch / material / format / pack）----
    BADGE_LABELS = ["yes_strongly", "yes_somewhat", "neutral", "unlikely", "no_effect"]
    BADGE_CN = {"yes_strongly": "很有影响", "yes_somewhat": "有些影响", "neutral": "中立",
                "unlikely": "基本不影响", "no_effect": "完全不影响"}
    SWITCH_LABELS = ["lower_price", "better_rating", "better_look", "better_function", "better_value", "nothing"]
    SWITCH_CN = {"lower_price": "更低价格", "better_rating": "更高评分/更多评论", "better_look": "更好看",
                 "better_function": "更强功能", "better_value": "更值(多件/耗材)", "nothing": "不会换选"}
    pref_dist = {"q_badge_effect": {}, "q_switch_trigger": {}, "q_material_pref": {}, "q_format_pref": {}, "q_pack_pref": {}}
    for arm in ARMS:
        rows = [r for r in all_rows if r["arm"] == arm]
        n = len(rows) or 1
        for qid in pref_dist:
            c = Counter(r.get(qid) for r in rows if r.get(qid))
            pref_dist[qid][arm] = {k: round(v / n * 100, 1) for k, v in c.items()}
    summary["pref_dist"] = pref_dist
    # 全部四臂的汇总（简单平均）供报告展示
    summary["pref_dist_avg"] = {}
    for qid in pref_dist:
        merged: Counter = Counter()
        n_arms = 0
        for arm in ARMS:
            for k, v in pref_dist[qid][arm].items():
                merged[k] += v
            n_arms += 1
        summary["pref_dist_avg"][qid] = {k: round(v / n_arms, 1) for k, v in merged.items()}

    # ---- simulated vs ground truth rank correlation ----
    corr = {}
    for arm in ARMS:
        rows = [r for r in all_rows if r["arm"] == arm and r["choice"] not in (None, "none_of_these")]
        share = Counter(r["choice"] for r in rows)
        pids = [pid for pid in share]
        share_vals = [share[pid] for pid in pids]
        rank_vals = [prod_meta[pid]["gt_rank"] for pid in pids]
        sales_vals = [prod_meta[pid]["gt_monthly_sales"] for pid in pids]
        corr[arm] = {
            "share_vs_rank": round(spearman_rank(share_vals, rank_vals), 3) if spearman_rank(share_vals, rank_vals) is not None else None,
            "share_vs_sales": round(spearman_rank(share_vals, sales_vals), 3) if spearman_rank(share_vals, sales_vals) is not None else None,
        }
    summary["gt_correlation"] = corr

    # ---- rank shift: 真实榜排名 vs 模拟份额排名（逐款） ----
    rank_compare = {}
    for arm in ARMS:
        share = {pid: v for pid, v in summary["arms"][arm]["share"].items() if v > 0}
        sim_rank = {pid: i + 1 for i, (pid, _) in enumerate(sorted(share.items(), key=lambda kv: -kv[1]))}
        rows = []
        for pid, meta in prod_meta.items():
            gr = meta.get("gt_rank")
            if gr is None:
                continue
            sr = sim_rank.get(pid, len(prod_meta))
            rows.append({
                "pid": pid, "brand": meta.get("brand", ""),
                "gt_rank": int(gr), "sim_rank": int(sr),
                "delta": int(sr - gr), "share": round(share.get(pid, 0), 2),
            })
        rows.sort(key=lambda r: abs(r["delta"]), reverse=True)
        rank_compare[arm] = rows
    summary["rank_compare"] = rank_compare

    # ---- 品类形态结构：真实月销 vs 模拟偏好（归并为 5 大形态） ----
    def ptype_cat(raw: str) -> str:
        if not raw:
            return "其他"
        if raw.startswith("单刷套装"):
            return "单刷套装"
        if raw.startswith("刷+搋") and ("2合1" in raw or "3合1" in raw):
            return "刷+搋2合1"
        if raw.startswith("一次性"):
            return "一次性刷头"
        if "硅胶" in raw:
            return "硅胶刷"
        if "浮石" in raw:
            return "浮石棒"
        return "其他"

    cat_agg: dict[str, dict] = {}
    for pid, meta in prod_meta.items():
        cat = ptype_cat(meta.get("ptype") or "")
        g = cat_agg.setdefault(cat, {"n_sku": 0, "gt_sales": 0.0, "gt_revenue": 0.0, "sim_share": 0.0, "sim_est_monthly_revenue": 0.0, "mean_price": []})
        g["n_sku"] += 1
        g["gt_sales"] += meta.get("gt_monthly_sales") or 0
        g["gt_revenue"] += meta.get("gt_monthly_revenue") or 0
        share = summary["arms"]["brand-rating"]["share"].get(pid, 0)
        g["sim_share"] += share
        g["sim_est_monthly_revenue"] += share / 100 * (meta.get("gt_monthly_revenue") or 0)
        if meta.get("price"):
            g["mean_price"].append(meta["price"])
    total_gt = sum(g["gt_sales"] for g in cat_agg.values()) or 1
    category_structure = []
    for cat, g in sorted(cat_agg.items(), key=lambda kv: -kv[1]["gt_sales"]):
        category_structure.append({
            "category": cat, "n_sku": g["n_sku"],
            "gt_sales_share": round(g["gt_sales"] / total_gt * 100, 1),
            "sim_share": round(g["sim_share"], 1),
            "sim_est_monthly_revenue": round(g["sim_est_monthly_revenue"], 0),
            "gt_monthly_revenue": round(g["gt_revenue"], 0),
            "mean_price": round(sum(g["mean_price"]) / len(g["mean_price"]), 2) if g["mean_price"] else None,
        })
    summary["category_structure"] = category_structure

    # ---- 价格带：真实 vs 模拟 ----
    bands = [("$0-10", 0, 10), ("$10-15", 10, 15), ("$15-25", 15, 25), ("$25-35", 25, 35), ("$35+", 35, 10 ** 6)]
    band_agg: dict[str, dict] = {b[0]: {"n_sku": 0, "gt_sales": 0.0, "sim_share": 0.0} for b in bands}
    for pid, meta in prod_meta.items():
        price = meta.get("price") or 0
        for label, lo, hi in bands:
            if lo <= price < hi:
                b = band_agg[label]
                b["n_sku"] += 1
                b["gt_sales"] += meta.get("gt_monthly_sales") or 0
                b["sim_share"] += summary["arms"]["brand-rating"]["share"].get(pid, 0)
                break
    total_gt2 = sum(b["gt_sales"] for b in band_agg.values()) or 1
    price_band = [
        {"band": label, "n_sku": b["n_sku"], "gt_sales_share": round(b["gt_sales"] / total_gt2 * 100, 1),
         "sim_share": round(b["sim_share"], 1)}
        for label, b in band_agg.items()
    ]
    summary["price_band"] = price_band

    # ---- 营收池：模拟份额 × 真实月销售额（品牌+评分臂，可靠口径） ----
    revenue_rows = []
    for pid, meta in prod_meta.items():
        gt_rev = meta.get("gt_monthly_revenue") or 0
        if not gt_rev:
            continue
        share = summary["arms"]["brand-rating"]["share"].get(pid, 0)
        revenue_rows.append({
            "pid": pid, "brand": meta.get("brand", ""), "price": meta.get("price"),
            "share": round(share, 2),
            "sim_monthly_revenue": round(share / 100 * gt_rev, 0),
            "gt_monthly_revenue": round(gt_rev, 0),
        })
    revenue_rows.sort(key=lambda r: -r["sim_monthly_revenue"])
    summary["revenue_potential"] = revenue_rows

    summary["n_total_trials"] = len(all_rows)
    json_path = out_dir / "top30_2x2_summary.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", csv_path)
    print("wrote", json_path)
    for arm in ARMS:
        s = summary["arms"][arm]
        print(f"[{arm}] n={s['n']} none={s['none_rate']}% mean_price=${s['mean_chosen_price']}")
        top3 = sorted(s["share"].items(), key=lambda kv: -kv[1])[:3]
        print("   top:", ", ".join(f"{k} {v:.1f}%" for k, v in top3))
    print("personas shared:", n_shared)
    print("stability:", stability)
    print("gt corr:", corr)
    print("rationale signals:", json.dumps(sig_summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
