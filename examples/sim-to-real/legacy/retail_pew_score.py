"""Score paired Pew forecasts with the original survey weights."""
import argparse
from collections import defaultdict
import json
import sqlite3

import numpy as np

from retail_pew import ARMS, ITEMS, RUN, SEED, dataset


def score(stage):
    people, options = dataset()
    freeze = json.loads((RUN / "pew-freeze.json").read_text())
    keys = freeze["splits"][stage]
    arms = list(ARMS) if stage == "pilot" else list(ARMS)[:4]
    with sqlite3.connect(RUN / "pew.sqlite") as db:
        forecasts = {(key, arm): json.loads(out) for key, arm, out in db.execute(
            "SELECT person, arm, output FROM runs WHERE output IS NOT NULL")}
    coverage = {arm: sum((key, arm) in forecasts for key in keys) for arm in arms}
    if min(coverage.values()) / len(keys) < .98:
        raise ValueError(f"Completion below 98%: {coverage}")
    common = [k for k in keys if all((k, arm) in forecasts for arm in arms)]
    training = [people[k] for k in freeze["splits"]["reference"]]
    rng = np.random.default_rng(SEED)
    bootstrap = rng.integers(len(common), size=(2000, len(common)))
    results = defaultdict(list)
    tv_draws = defaultdict(list)
    brier_draws = defaultdict(list)
    calibration = defaultdict(lambda: np.zeros((10, 3)))
    subgroup = defaultdict(lambda: defaultdict(list))
    subgroup_masks = {(field, value): np.array([people[k]["background"][field] == value for k in common])
              for field in ("Age group", "Education")
              for value in sorted({people[k]["background"][field] for k in common})}
    for question in ITEMS:
        n = len(options[question])
        prior = np.zeros(n)
        groups = defaultdict(lambda: np.zeros(n))
        for row in training:
            if question not in row["truth"]:
                continue
            choice = row["truth"][question]
            prior[choice] += row["weight"]
            stratum = tuple(list(row["background"].values())[:2])
            groups[stratum][choice] += row["weight"]
        prior /= prior.sum()
        weights = np.array([people[k]["weight"] if question in people[k]["truth"] else 0 for k in common])
        labels = np.array([people[k]["truth"].get(question, 0) for k in common])
        actual = np.eye(n)[labels]
        reference = np.average(actual, axis=0, weights=weights)
        boot_weights = weights[bootstrap]
        boot_totals = boot_weights.sum(axis=1)
        def estimate(matrix):
            return (matrix[bootstrap] * boot_weights[:, :, None]).sum(axis=1) / boot_totals[:, None]
        boot_truth = estimate(actual)
        by_arm = {arm: np.array([forecasts[k, arm][question] for k in common]) for arm in arms}
        by_arm["rich_probability_argmax"] = np.eye(n)[by_arm["rich_probability"].argmax(axis=1)]
        baseline = []
        for key in common:
            stratum = tuple(list(people[key]["background"].values())[:2])
            counts = groups[stratum] + 20 * prior
            baseline.append(counts / counts.sum())
        by_arm["statistics"] = np.array(baseline)
        for arm, pred in by_arm.items():
            share = np.average(pred, axis=0, weights=weights)
            brier = ((pred - actual) ** 2).sum(axis=1)
            best = pred.argmax(axis=1)
            tv_draws[arm].append(50 * np.abs(estimate(pred) - boot_truth).sum(axis=1))
            brier_draws[arm].append((brier[bootstrap] * boot_weights).sum(axis=1) / boot_totals)
            bins = np.minimum((pred * 10).astype(int), 9)
            scaled = weights / weights.sum() / n
            for j in range(10):
                weighted = (bins == j) * scaled[:, None]
                calibration[arm][j] += [weighted.sum(), (weighted*pred).sum(), (weighted*actual).sum()]
            for (field, value), mask in subgroup_masks.items():
                valid = mask & (weights > 0)
                if valid.sum() < 20:
                    continue
                group_truth = np.average(actual[valid], axis=0, weights=weights[valid])
                group_model = np.average(pred[valid], axis=0, weights=weights[valid])
                subgroup[arm][(field, value)].append(float(50 * abs(group_truth-group_model).sum()))
            recall = [float(np.average(best[labels == i] == i, weights=weights[labels == i]))
                      if weights[labels == i].sum() > 0 else None for i in range(n)]
            results[arm].append({"question": question, "question_text": ITEMS[question], "options": options[question],
                                 "real": reference.tolist(), "simulated": share.tolist(),
                                 "tv_pp": float(50 * abs(share - reference).sum()),
                                 "brier": float(np.average(brier, weights=weights)),
                                 "accuracy": float(np.average(best == labels, weights=weights)),
                                 "max_share": float(max(share)), "recall": recall,
                                 "valid_real_people": int((weights > 0).sum())})
    summaries = {}
    for arm, rows in results.items():
        summaries[arm] = {key: float(np.mean([row[key] for row in rows])) for key in ("tv_pp", "brier", "accuracy")}
        summaries[arm]["concentration_counts"] = {str(t): sum(row["max_share"] >= t - 1e-10 for row in rows)
                                                  for t in (.95, .99, 1)}
    pairs = [("basic_choice", "rich_choice"), ("basic_probability", "rich_probability"),
             ("basic_choice", "basic_probability"), ("rich_choice", "rich_probability"),
             ("rich_probability_argmax", "rich_probability"), ("statistics", "rich_probability")]
    if stage == "pilot":
        pairs.extend([("reverse_probability", "rich_probability"), ("shuffle_probability", "rich_probability")])
    contrasts = []
    for old, new in pairs:
        draws = np.mean(tv_draws[old], axis=0) - np.mean(tv_draws[new], axis=0)
        individual = np.mean(brier_draws[old], axis=0) - np.mean(brier_draws[new], axis=0)
        contrasts.append({"from": old, "to": new,
                          "tv_improvement_pp": summaries[old]["tv_pp"] - summaries[new]["tv_pp"],
                          "tv_95_interval": np.quantile(draws, [.025, .975]).tolist(),
                          "brier_improvement": summaries[old]["brier"] - summaries[new]["brier"],
                          "brier_95_interval": np.quantile(individual, [.025, .975]).tolist()})
    output = {"stage": stage, "requested": len(keys), "complete": coverage, "common_people": len(common),
              "questions": len(ITEMS), "summaries": summaries, "contrasts": contrasts, "items": results,
              "calibration": {arm: [{"mean_probability": float(p/w), "observed_frequency": float(y/w), "weight": float(w)}
                                    for w,p,y in bins if w > 0] for arm,bins in calibration.items()},
              "subgroups": {arm:[{"field":field,"group":group,"questions":len(errors),
                                   "people":int(subgroup_masks[(field,group)].sum()),"tv_pp":float(np.mean(errors))}
                                for (field,group),errors in values.items()] for arm,values in subgroup.items()}}
    (RUN.parent / f"pew-{stage}-score.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k:v for k,v in output.items() if k != "items"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["pilot", "formal"])
    score(parser.parse_args().stage)
