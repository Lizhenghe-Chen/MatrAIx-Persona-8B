"""Score matched product choices and survey answers by respondent."""

import html
import json
import sqlite3
from pathlib import Path
from collections import defaultdict
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
from scipy.optimize import minimize
from scipy.special import softmax

from experiment import dump, sha256, stable_seed
from shopping import CONDITIONS, STRATA

HISTORY = "统计基线"
OUTCOMES = {"China": "选择中国产", "United States": "选择美国产",
            "cheaper": "选择较便宜款", "higher-rated": "选择较高评分款"}
NAMES = {"origin": "产地与选品", "packaging": "包装与拒买", "pew": "网购习惯"}
PAIRS = (("P0+B1", "P1+B3"), ("P0+B1", "P1+B1"), ("P0+B3", "P1+B3"),
         ("P0+B1", "P0+B3"), ("P1+B1", "P1+B3"), (HISTORY, "P1+B3"))


def price(row):
    return float(row["price"].replace("$", "").replace(",", ""))


def product_features(person, task):
    rows = []
    for attrs in task["attrs"]:
        numeric = {"log price": np.log(price(attrs)), "purchase": 1.}
        categorical = {k: v for k, v in attrs.items() if k != "price"}
        categorical.update({f"product and {k}": f"{attrs['product']}/{attrs[k]}" for k in ("rating", "country")
                            if "product" in attrs})
        features = {**numeric, **{f"{k}={v}": 1. for k, v in categorical.items()}}
        modifier = {"stratum": person["stratum"], **person["background"], "instruction arm": person["treatment"]}
        for k, v in modifier.items():
            for key in ("purchase", "log price", *((f"country={attrs['country']}",) if "country" in attrs else ())):
                features[f"{k}={v}/{key}"] = features[key]
        rows.append(features)
    if "0" in task["codes"]:
        rows.append({})
    return rows


def product_baseline(training, evaluation):
    train = [(product_features(p, t), t["codes"].index(t["truth"])) for p in training for t in p["tasks"]]
    columns = {key: i for i, key in enumerate(sorted({k for rows, _ in train for row in rows for k in row}))}
    def matrix(groups):
        x = np.zeros((len(groups), len(groups[0]), len(columns)))
        for i, rows in enumerate(groups):
            for j, row in enumerate(rows):
                for k, v in row.items():
                    if k in columns:
                        x[i, j, columns[k]] = v
        return x
    x = matrix([rows for rows, _ in train])
    y = np.array([y for _, y in train])
    indices = np.arange(len(y))
    def loss(beta):
        prob = softmax(x @ beta, axis=1)
        value = -np.log(np.maximum(prob[indices, y], 1e-15)).mean() + .002 * (beta @ beta)
        prob[indices, y] -= 1
        return value, np.einsum("na,nak->k", prob, x) / len(y) + .004 * beta
    fit = minimize(loss, np.zeros(len(columns)), method="L-BFGS-B", jac=True)
    if not fit.success:
        raise ValueError(f"Choice baseline fit failed: {fit.message}")
    keys = [(p["id"], t["id"]) for p in evaluation for t in p["tasks"]]
    probs = softmax(matrix([product_features(p, t) for p in evaluation for t in p["tasks"]]) @ fit.x, axis=1)
    return dict(zip(keys, probs, strict=True))


def pew_baseline(training, evaluation):
    counts = defaultdict(float)
    for person in training:
        for task in person["tasks"]:
            counts[person["stratum"], task["id"], task["truth"]] += person["weight"]
    out = {}
    for person in evaluation:
        for task in person["tasks"]:
            row = np.array([counts[person["stratum"], task["id"], k] for k in task["codes"]])
            out[person["id"], task["id"]] = row / row.sum()
    return out


def metrics_for(survey, task):
    if survey != "origin":
        yield task["card"], tuple((code,) for code in task["codes"])
        return
    a, b = task["attrs"]
    for label in ("China", "United States"):
        if (a["country"] == label) != (b["country"] == label):
            k = int(b["country"] == label)
            yield label, ((str(1 + k),), (str(2 - k),))
    for label, measure, fn in (("cheaper", price, min), ("higher-rated", lambda x: int(x["rating"][0]), max)):
        values = [measure(a), measure(b)]
        if values[0] != values[1]:
            k = values.index(fn(values))
            yield label, ((str(1 + k),), (str(2 - k),))


def compare(survey, pool, ds, predicted):
    people = [p for p in ds["formal"] if all((survey, p["id"], c) in predicted for c in CONDITIONS)]
    population = {s: sum(p["weight"] for p in pool if p["stratum"] == s) for s in STRATA}
    sampled = {s: sum(p["weight"] for p in people if p["stratum"] == s) for s in STRATA}
    if not all(sampled.values()):
        raise ValueError(f"{survey}: empty matched stratum")
    weight = [p["weight"] * population[p["stratum"]] / sampled[p["stratum"]] for p in people]
    rng = np.random.default_rng(stable_seed(survey, "shopping-bootstrap"))
    draws = np.ones((2001, len(people)))
    for stratum in STRATA:
        ids = [i for i, p in enumerate(people) if p["stratum"] == stratum]
        draws[1:, ids] = rng.multinomial(len(ids), np.full(len(ids), 1 / len(ids)), 2000)
    weighted = draws * weight
    for stratum in STRATA:
        ids = [i for i, p in enumerate(people) if p["stratum"] == stratum]
        weighted[:, ids] *= population[stratum] / weighted[:, ids].sum(axis=1, keepdims=True)
    conditions = (*CONDITIONS, HISTORY)
    baseline = (pew_baseline if survey == "pew" else product_baseline)(ds["training"], people)
    groups = {}
    individual = {c: defaultdict(lambda: np.zeros((len(people), 2))) for c in conditions}
    cards = {}
    opt_out = defaultdict(float)
    opt_out_total = 0.
    for i, person in enumerate(people):
        for task in person["tasks"]:
            if task["truth"] is None:
                continue
            truth = task["codes"].index(task["truth"])
            probabilities = {c: np.array([predicted[survey, person["id"], c][task["id"]] == v for v in task["codes"]])
                             for c in CONDITIONS}
            probabilities[HISTORY] = baseline[person["id"], task["id"]]
            if survey == "packaging":
                cards[task["card"]] = task["attrs"]
                opt_out["human"] += weight[i] * (task["truth"] == "0")
                opt_out_total += weight[i]
                for cell, probs in probabilities.items():
                    opt_out[cell] += weight[i] * probs[2]
            for cell, probs in probabilities.items():
                guess = int(probs.argmax())
                key = (task["attrs"][0]["product"] if survey == "origin" else
                       task["id"] if survey == "pew" else "All")
                labels = ["overall", f"accuracy/{key}"]
                if survey != "origin":
                    labels.append(f"recall/{key}/{task['truth']}")
                for label in labels:
                    stat = individual[cell][label]
                    stat[i, 0] += guess == truth
                    stat[i, 1] += 1
            for label, buckets in metrics_for(survey, task):
                data = groups.setdefault(label, np.zeros((len(people), len(conditions) + 1, len(buckets))))
                for j, bucket in enumerate(buckets):
                    indexes = [task["codes"].index(v) for v in bucket]
                    data[i, 0, j] += truth in indexes
                    for k, cell in enumerate(conditions, 1):
                        data[i, k, j] += probabilities[cell][indexes].sum()
    differences = defaultdict(list)
    details = defaultdict(dict)
    for label, matrix in sorted(groups.items()):
        counts = (weighted @ matrix.reshape(len(people), -1)).reshape(len(draws), *matrix.shape[1:])
        totals = counts[:, 0, :].sum(axis=1)
        if not np.all(totals > 0):
            raise ValueError(f"{survey}/{label}: insufficient coverage for bootstrap")
        dist = counts / totals[:, None, None]
        for j, cell in enumerate(conditions, 1):
            error = 50 * abs(dist[:, j] - dist[:, 0]).sum(axis=1)
            differences[cell].append(error)
            details[cell][label] = {"human_pct": (100 * dist[0, 0]).tolist(),
                                    "predicted_pct": (100 * dist[0, j]).tolist(),
                                    "tv_pp": float(error[0]), "tasks": int(matrix[:, 0].sum())}
    scores = {c: np.mean(values, axis=0) for c, values in differences.items()}
    individual_draws = {}
    for cell, values in individual.items():
        individual_draws[cell] = {}
        overall = values["overall"]
        present = overall[:, 1] > 0
        person_accuracy = np.divide(overall[:, 0], overall[:, 1], out=np.zeros(len(people)), where=present)
        individual_draws[cell]["person_mean"] = 100 * (weighted @ person_accuracy) / (weighted @ present)
        for label, raw in values.items():
            counts = weighted @ raw
            individual_draws[cell][label] = np.divide(
                100 * counts[:, 0], counts[:, 1], out=np.full(len(draws), np.nan), where=counts[:, 1] > 0)
    comparisons = []
    for a, b in PAIRS:
        gain = scores[a] - scores[b]
        ci = np.quantile(gain[1:], [.025, .975]).tolist()
        accuracy = individual_draws[b]["person_mean"] - individual_draws[a]["person_mean"]
        comparisons.append({"reference": a, "candidate": b, "gain_pp": float(gain[0]), "ci95": ci,
                            "accuracy_gain_pp": float(accuracy[0]),
                            "accuracy_ci95": np.quantile(accuracy[1:], [.025, .975]).tolist(),
                            "passes": bool(gain[0] >= 2 and ci[0] > 0)})
    return {"matched": len(people), "training": len(ds["training"]), "cards": cards,
            "opt_out_pct": {k: 100 * v / opt_out_total for k, v in opt_out.items()}, "cells": {
        c: {"tv_pp": float(scores[c][0]), "metrics": details[c],
            "individual_pct": {k: float(v[0]) for k, v in individual_draws[c].items()},
            "individual_ci95": {k: np.nanquantile(v[1:], [.025, .975]).tolist()
                                for k, v in individual_draws[c].items()},
            "concentration": ({str(k): sum(max(row["predicted_pct"]) >= k - 1e-8 for row in details[c].values())
                               for k in (95, 99, 100)} if survey != "origin" else None)}
        for c in conditions}, "comparisons": comparisons}


def score(study, people, datasets):
    with sqlite3.connect(study / "checkpoints.sqlite") as db:
        records = db.execute("SELECT stage,survey,id,cell,payload FROM runs ORDER BY 1,2,3,4").fetchall()
    predictions = {(s, p, c): data["answers"] for stage, s, p, c, payload in records
                   if stage == "formal" and "answers" in (data := json.loads(payload))}
    result = {}
    for survey, ds in datasets.items():
        if any(sum((survey, p["id"], cell) in predictions for p in ds["formal"]) / len(ds["formal"]) < .98
               for cell in CONDITIONS):
            raise ValueError(f"{survey}: insufficient completion")
        result[survey] = compare(survey, people[survey], ds, predictions)
    main = {s: v["comparisons"][0] for s, v in result.items()}
    cross = (len(main) == 3 and main["origin"]["passes"]
             and sum(r["passes"] for r in main.values()) >= 2 and all(r["ci95"][1] >= 0 for r in main.values()))
    dump(study / "results.json", {"cross_task_gain": cross, "surveys": result})
    with ZipFile(study / "trials.zip", "w", ZIP_DEFLATED) as archive:
        for stage in ("pilot", "formal"):
            archive.writestr(f"{stage}.jsonl", "\n".join(json.dumps({"survey": s, "id": p, "cell": c,
                              **json.loads(payload)}) for part, s, p, c, payload in records if part == stage) + "\n")
    write_report(study, result, cross)
    dump(study / "analysis-source-sha256.json", {name: sha256(Path(__file__).with_name(name))
         for name in ("shopping.py", "shopping_score.py", "shopping_report.py")})
    dump(study / "output-sha256.json", {name: sha256(study / name) for name in
         ("results.json", "trials.zip", "report.html", "manifest.json", "sample-index.json", "analysis-source-sha256.json")})


def write_report(study, result, cross):
    from shopping_report import render
    (study / "report.html").write_text(render(result, cross, NAMES, OUTCOMES, html.escape))
