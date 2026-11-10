"""Score the frozen comparisons with paired, stratified resampling."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np

from experiment import SEED, STRATA, dump, read_json, sha256, stable_seed
from instruments import ITEMS
from optimize import job_key

REPLICATES = 2000
THRESHOLDS = (95, 99, 100)
HIST = "historical-stratum"
SURVEY_NAMES = {"shed": "SHED", "pew": "Pew", "anes": "ANES"}


def pair_samples(identifiers):
    ids = tuple(identifiers)
    rng = np.random.default_rng(stable_seed(SEED, ids))
    n = len(ids)
    return np.vstack((np.ones(n), rng.multinomial(n, np.full(n, 1 / n), size=REPLICATES)))


def mix(x, mass):
    return (x * mass[:, :, None]).sum(axis=1) / mass.sum(axis=1)[:, None]


def average(values):
    return np.mean(values, axis=0)


def model_item(item, codes, strata, draws, predictions, ref, condition):
    human = np.array([[ref["items"][item][s]["distribution"][c] for c in codes] for s in STRATA])
    actual_mass = [ref["items"][item][s]["weight"] for s in STRATA]
    actual = np.average(human, axis=0, weights=actual_mass)
    model = []
    for ids, count in zip(strata, draws, strict=True):
        options = np.array([[predictions[i][item] == c for c in codes] for i in ids])
        model.append(count @ options / len(ids))
    weights = np.ones(len(STRATA)) if condition.endswith("-A") else [ref["stratum_weight"][s] for s in STRATA]
    return actual, np.average(model, axis=0, weights=weights), None, None


def human_item(item, codes, strata, draws, predictions, profiles, ref):
    target, predicted, mass, correct = [], [], [], []
    for s, ids, count in zip(STRATA, strata, draws, strict=True):
        answers = [profiles["people"][i]["answers"].get(item) for i in ids]
        weights = np.array([profiles["people"][i]["weight"] for i in ids])
        boot_weights = count * weights
        known = np.array([a is not None for a in answers])
        valid = boot_weights[:, known]
        denom = valid.sum(axis=1)
        if np.any(denom <= 0):
            raise ValueError(f"{item}/{s}: resample contains no valid reference answers")
        mass.append(ref["stratum_weight"][s] * denom / boot_weights.sum(axis=1))
        observed = np.array([[a == c for c in codes] for a in answers])[known]
        target.append((valid @ observed) / denom[:, None])
        if predictions is None:
            probabilities = np.array([profiles["baseline"][s][item][c] for c in codes])
            predicted.append(np.broadcast_to(probabilities, (len(count), len(codes))))
            guess = np.full(len(ids), codes[int(probabilities.argmax())])
        else:
            guess = np.array([predictions[i][item] for i in ids])
            forecast = np.array([[g == c for c in codes] for g in guess])[known]
            predicted.append((valid @ forecast) / denom[:, None])
        correct.append((valid @ (observed & (guess[known, None] == np.array(codes)))) / denom[:, None])
    mass = np.array(mass).T
    actual = mix(np.stack(target, axis=1), mass)
    model = mix(np.stack(predicted, axis=1), mass)
    correct = mix(np.stack(correct, axis=1), mass)
    return actual[0], model, actual, correct[0]


def patterns(predictions, ids, items):
    counts = Counter(tuple(predictions[i][item] for item in items) for i in ids)
    return {"distinct": len(counts), "top_share_pct": 100 * max(counts.values()) / len(ids),
            "repeat_share_pct": 100 * sum(n for n in counts.values() if n > 1) / len(ids)}


def survey_score(survey, condition, strata, draws, predictions, ref, profiles):
    items, distances, accuracy = {}, [], []
    for item, (question, options) in ITEMS[survey].items():
        codes = [str(c) for c in options]
        if profiles:
            human, simulated, draws_human, correct = human_item(
                item, codes, strata, draws, predictions, profiles, ref)
        else:
            human, simulated, draws_human, correct = model_item(
                item, codes, strata, draws, predictions, ref, condition)
        errors = 50 * np.abs(simulated - (human if draws_human is None else draws_human)).sum(axis=1)
        distances.append(errors)
        by_option = {}
        for k, (code, label) in enumerate(options.items()):
            by_option[str(code)] = {"label": label, "human_pct": 100 * human[k],
                                    "predicted_pct": 100 * simulated[0, k]}
            if correct is not None:
                by_option[str(code)]["recall_pct"] = 100 * correct[k] / human[k] if human[k] else None
        row = {"question": question, "tv_pp": errors[0], "options": by_option,
               "top_pct": 100 * simulated[0].max(), "human_top_pct": 100 * human.max(),
               "top_option": str(list(options)[simulated[0].argmax()])}
        if correct is not None:
            row["accuracy_pct"] = 100 * correct.sum()
            accuracy.append(row["accuracy_pct"])
        items[item] = row
    ids = [i for group in strata for i in group]
    score = average(distances)
    output = {"tv_pp": score[0], "n": len(ids), "items": items,
              "concentration": {str(t): sum(bool(row["top_pct"] >= t - 1e-8) for row in items.values())
                                for t in THRESHOLDS},
              "human_concentration": {str(t): sum(bool(row["human_top_pct"] >= t - 1e-8) for row in items.values())
                                      for t in THRESHOLDS}}
    if predictions is not None:
        output["patterns"] = patterns(predictions, ids, ITEMS[survey])
    if accuracy:
        output["accuracy_pct"] = float(average(accuracy))
    return output, score


def comparisons(experiment, conditions):
    if experiment == "models":
        models = {c.split("-")[0] for c in conditions}
        pairs = [(f"{first}-{arm}", f"{second}-{arm}")
                 for first, second in (("flash", "pro"), ("flash", "qwen"), ("pro", "qwen"))
                 for arm in "ABC"]
        pairs += [(f"{m}-A", f"{m}-B") for m in sorted(models)]
        pairs += [(f"{m}-B", f"{m}-C") for m in sorted(models)]
    else:
        pairs = [(f"p0-b{i}", f"p1-b{i}") for i in range(1, 5)]
        pairs += [(f"p{p}-b{i}", f"p{p}-b{i + 1}") for p in (0, 1) for i in range(1, 4)]
        pairs += [("p0-b1", c) for c in conditions if c not in {HIST, "p0-b1"}]
        pairs += [(HIST, c) for c in conditions if c != HIST]
    return [p for p in dict.fromkeys(pairs) if all(c in conditions for c in p)]


def interval(draws):
    return {"gain_pp": draws[0], "ci95": np.quantile(draws[1:], [0.025, 0.975]).tolist()}


def test_changes(scores, experiment, conditions):
    out = []
    for baseline, candidate in comparisons(experiment, conditions):
        draws = [scores[s][baseline] - scores[s][candidate] for s in ITEMS]
        per_survey = {s: interval(d) for s, d in zip(ITEMS, draws, strict=True)}
        pooled = interval(average(draws))
        recommend = (pooled["gain_pp"] >= 2 and pooled["ci95"][0] > 0
                     and sum(d[0] > 0 for d in draws) >= 2
                     and all(x["ci95"][1] >= 0 for x in per_survey.values()))
        out.append({"reference": baseline, "candidate": candidate, "overall": pooled,
                    "surveys": per_survey, "meets_threshold": bool(recommend)})
    return out


def report(experiment, result):
    label = "模型对比" if experiment == "models" else "提示词与背景对比"
    lines = [f"# MatrAIx {label}", "", "分布误差以百分点计，越低越接近真人。集中度按 95%／99%／100% 三档统计题数。", ""]
    if result["missing_conditions"]:
        lines += ["本表只纳入通过完成率门槛的对照组。待完成组为 " + "、".join(result["missing_conditions"]) + "。", ""]
    lines += ["| 组合 | 综合误差 | SHED | Pew | ANES | 集中题数 | 逐人正确率 |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for c, overall in result["overall"].items():
        parts = [result["surveys"][s][c] for s in ITEMS]
        counts = "/".join(str(sum(x["concentration"][str(t)] for x in parts)) for t in THRESHOLDS)
        accuracy = f"{overall['accuracy_pct']:.1f}%" if "accuracy_pct" in overall else "—"
        tv = " | ".join(f"{x['tv_pp']:.2f}" for x in parts)
        lines.append(f"| {c} | {overall['tv_pp']:.2f} | {tv} | {counts} | {accuracy} |")
    lines += ["", "## 整份答卷的重复情况", "",
              "重复占比表示有多少答卷与至少另一份完全相同。", "",
              "| 问卷 | 组合 | 不同答卷种数 | 最常见答卷占比 | 重复占比 |",
              "|---|---|---:|---:|---:|"]
    for survey, cells in result["surveys"].items():
        for c, cell in cells.items():
            if "patterns" in cell:
                p = cell["patterns"]
                lines.append(f"| {SURVEY_NAMES[survey]} | {c} | {p['distinct']} | "
                             f"{p['top_share_pct']:.1f}% | {p['repeat_share_pct']:.1f}% |")
    lines += ["", "## 配对对照", "",
              "正数表示候选组合误差下降，括号为 95% 区间。各问卷的区间见结果 JSON。",
              "", "| 参照 → 候选 | 综合增益 | SHED | Pew | ANES | 达到门槛 |",
              "|---|---:|---:|---:|---:|---|"]
    for row in result["comparisons"]:
        overall = row["overall"]
        gains = " | ".join(f"{d['gain_pp']:+.2f}" for d in row["surveys"].values())
        lo, hi = overall["ci95"]
        lines.append(f"| {row['reference']} → {row['candidate']} | "
                     f"{overall['gain_pp']:+.2f} [{lo:+.2f}, {hi:+.2f}] | {gains} | "
                     f"{'是' if row['meets_threshold'] else '否'} |")
    lines += ["", "## 仍接近全票的题目", "",
              "| 问卷 | 组合 | 题号 | 最常见选项 | 模拟选择率 | 真人同选项选择率 |",
              "|---|---|---|---|---:|---:|"]
    for survey, cells in result["surveys"].items():
        for c, cell in cells.items():
            for item, row in cell["items"].items():
                if row["top_pct"] >= 99 - 1e-8:
                    top = row["options"][row["top_option"]]
                    lines.append(f"| {SURVEY_NAMES[survey]} | {c} | {item} | {top['label']} | "
                                 f"{row['top_pct']:.1f}% | {top['human_pct']:.1f}% |")
    lines += ["", "## 口径", "",
              "- 使用各调查官方权重。问卷内题目等权，三份调查等权。仅比较同一问卷所有纳入条件都完成的样本。",
              "- 95% 区间来自 2,000 次分层配对重抽样。模型对比固定加权真人分布，同步重抽三份问卷共用的画像。真人逐人实验对每份调查独立重抽真人及对应预测。",
              "- 模型对比的 A 组按均衡抽样直接汇总，B、C 按真人四层权重汇总，沿用首轮口径。A→B 因此同时包含汇总权重的变化。",
              "- 真人实验在每题排除无效或插补的目标答案，并在层内使用调查权重。历史基线的分布来自评估样本外的同调查答卷，逐人指标使用同层概率最高的选项。",
              "- 重复答卷占比以整份选项组合出现至少两次的答卷为分子，另保留最常见组合占比。公开问卷及答案统计可能曾被模型见过。",
              "", "逐题误差、完整真人及模拟选项分布、选项召回率、样本覆盖和答卷重复率见同目录的 `results.json`。"]
    return "\n".join(lines) + "\n"


def score(experiment, study, destination, jobs, data):
    with sqlite3.connect(destination / "checkpoints.sqlite") as db:
        records = db.execute("SELECT stage,key,ok,payload FROM trials ORDER BY stage,key").fetchall()
    valid = {key: json.loads(payload)["answers"] for stage, key, ok, payload in records if stage == "formal" and ok}
    n = Counter((j["survey"], j["condition"]) for j in jobs)
    counts = Counter((j["survey"], j["condition"]) for j in jobs if job_key(j) in valid)
    planned = sorted({j["condition"] for j in jobs})
    included = [c for c in planned if all(counts[s, c] / n[s, c] >= 0.98 for s in ITEMS)]
    if not included:
        raise ValueError("No condition passes completion in all three surveys")
    if experiment == "profiles" and included != planned:
        raise ValueError("Incomplete profile factorial")
    conditions = included + ([HIST] if experiment == "profiles" else [])
    reference = read_json(study / "01_首轮归档" / "reference.json")
    result = {"missing_conditions": sorted(set(planned) - set(included)),
              "completion": {f"{s}/{c}": [counts[s, c], k] for (s, c), k in sorted(n.items())},
              "surveys": {}, "overall": {}, "paired": {}}
    errors = {}
    model_common = None
    if experiment == "models":
        model_common = set.intersection(*(
            {j["id"] for j in jobs if j["survey"] == s and j["condition"] == c and job_key(j) in valid}
            for s in ITEMS for c in included
        ))
    for s in ITEMS:
        selected = [j for j in jobs if j["survey"] == s and j["condition"] in included]
        stratum_by_id = {j["id"]: j["stratum"] for j in selected}
        answers = {c: {} for c in included}
        for j in selected:
            if job_key(j) in valid:
                answers[j["condition"]][j["id"]] = valid[job_key(j)]
        common = (model_common if model_common is not None
                  else set.intersection(*(set(answers[c]) for c in included)))
        strata = [sorted(i for i in common if stratum_by_id[i] == k) for k in STRATA]
        if any(not ids for ids in strata):
            raise ValueError(f"{s}: empty paired stratum")
        draws = [pair_samples(ids) for ids in strata]
        result["paired"][s] = dict(zip(STRATA, map(len, strata), strict=True))
        profiles = data[s] if experiment == "profiles" else None
        if profiles is not None:
            profiles = {**profiles, "people": {x["id"]: x for x in profiles["respondents"]}}
        result["surveys"][s], errors[s] = {}, {}
        for c in conditions:
            result["surveys"][s][c], errors[s][c] = survey_score(
                s, c, strata, draws, answers.get(c), reference[s], profiles)
    for c in conditions:
        result["overall"][c] = {"tv_pp": float(average([errors[s][c][0] for s in ITEMS]))}
        if experiment == "profiles":
            result["overall"][c]["accuracy_pct"] = float(
                average([result["surveys"][s][c]["accuracy_pct"] for s in ITEMS]))
    result["comparisons"] = test_changes(errors, experiment, conditions)
    dump(destination / "results.json", result)
    (destination / "report.md").write_text(report(experiment, result))
    if experiment == "profiles":
        sample = {s: {"formal": [r["id"] for r in data[s]["respondents"]],
                      "pilot": data[s]["development"], "trait_match": data[s]["trait_match"],
                      "baseline_n": data[s]["baseline_n"]} for s in ITEMS}
    else:
        sample = {s: [r["id"] for r in data["cohort"]] for s in ITEMS}
    dump(destination / "sample-index.json", sample)
    sources = [Path(__file__), Path(__file__).with_name("optimize.py")]
    if experiment == "profiles":
        sources.append(Path(__file__).with_name("optimize_profiles.py"))
    dump(destination / "analysis-source-sha256.json", {source.name: sha256(source) for source in sources})
    with ZipFile(destination / "trials.zip", "w", ZIP_DEFLATED) as archive:
        for stage in ("pilot", "formal"):
            entries = (payload for phase, _, _, payload in records if phase == stage)
            archive.writestr(f"{stage}.jsonl", "\n".join(entries) + "\n")
    outputs = ("report.md", "results.json", "sample-index.json", "analysis-source-sha256.json", "trials.zip")
    dump(destination / "output-sha256.json", {name: sha256(destination / name) for name in outputs})
