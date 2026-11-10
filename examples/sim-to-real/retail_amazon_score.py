"""Score Amazon model forecasts and history baselines on paired accounts."""
import argparse
import json
import sqlite3

import numpy as np

from retail_amazon import RUN, SEED, probabilities


def score(stage):
    data = json.loads((RUN / "amazon-freeze.json").read_text())
    categories = data["categories"]
    keys = data["split"][stage]
    model_arms = ["history_only", "historical_anchor"]
    with sqlite3.connect(RUN / "amazon.sqlite") as db:
        cache = {(key, arm): json.loads(pred) for key, arm, pred in db.execute(
            "SELECT person, arm, prediction FROM forecasts WHERE prediction IS NOT NULL")}
    coverage = {arm: sum((key, arm) in cache for key in keys) for arm in model_arms}
    if min(coverage.values()) / len(keys) < .98:
        raise ValueError(f"Completion below 98%: {coverage}")
    common = [key for key in keys if all((key, arm) in cache for arm in model_arms)]
    truth = np.array([[float(c in data["records"][key]["target"]) for c in categories] for key in common])
    variants = {arm: [cache[key, arm] for key in common] for arm in model_arms}
    for baseline in ["population", "history", "recent"]:
        variants[baseline] = [probabilities(data["records"][key], categories, data["priors"], baseline) for key in common]
    # Freeze one scalar weight on development accounts before evaluating held-out accounts.
    blend_path = RUN.parent / "amazon-blend-protocol.json"
    if stage == "development":
        recent = np.array([[r[c] for c in categories] for r in variants["recent"]])
        model = np.array([[r[c] for c in categories] for r in variants["history_only"]])
        residual = model - recent
        variance = np.mean(residual**2)
        weight = float(np.clip(np.mean((truth - recent) * residual) / variance, 0, 1)) if variance else 0
        spec = {"model_weight": weight, "fit": "development only, squared-error minimizing convex blend"}
        if blend_path.exists() and json.loads(blend_path.read_text()) != spec:
            raise ValueError("Frozen blend weight changed")
        blend_path.write_text(json.dumps(spec, indent=2) + "\n")
    else:
        weight = json.loads(blend_path.read_text())["model_weight"]
    variants["blend"] = [{c: (1-weight)*base[c] + weight*model[c] for c in categories}
                         for base, model in zip(variants["recent"], variants["history_only"], strict=True)]
    summary, errors = {}, {}
    draws = np.random.default_rng(SEED).integers(len(common), size=(2000, len(common)))
    for name, variant in variants.items():
        pred = np.array([[row[c] for c in categories] for row in variant])
        errors[name] = ((pred - truth)**2).mean(axis=1)
        summary[name] = {"brier": float(errors[name].mean()),
                         "mean_category_prevalence_error_pp": float(100 * np.abs((pred-truth).mean(axis=0)).mean()),
                         "forecast_prevalence": pred.mean(axis=0).tolist()}
    contrasts = {}
    for before, after in [("recent", "history_only"), ("recent", "historical_anchor"),
                          ("history_only", "historical_anchor"), ("recent", "blend")]:
        delta = errors[before] - errors[after]
        contrasts[f"{before} → {after}"] = {"brier_improvement": float(delta.mean()),
                                            "interval": np.quantile(delta[draws].mean(axis=1), [.025,.975]).tolist()}
    def history_lines(key):
        return sum(sum(q.values()) for q in data["records"][key]["quarters"].values())
    cuts = np.quantile([history_lines(key) for key in data["split"]["development"]], [1/3,2/3])
    density = np.array([history_lines(key) for key in common])
    groups = np.searchsorted(cuts, density, side="left")
    subgroups = []
    rng = np.random.default_rng(SEED)
    for group in range(3):
        mask = groups == group
        n = int(mask.sum())
        if n < 12:
            continue
        sample = rng.integers(n, size=(2000,n))
        gain = {}
        for method in ("history_only","historical_anchor","blend"):
            difference = (errors["recent"]-errors[method])[mask]
            gain[method] = {"brier_gain":float(difference.mean()),
                            "interval":np.quantile(difference[sample].mean(axis=1),[.025,.975]).tolist()}
        subgroups.append({"group":group,"accounts":n,
                          "history_lines_min":int(density[mask].min()),"history_lines_max":int(density[mask].max()),
                          "gains_vs_recent":gain})
    output = {"sample": stage, "complete": coverage, "common_accounts": len(common),
              "categories": categories, "actual_prevalence": truth.mean(axis=0).tolist(),
              "summary": summary, "contrasts": contrasts, "history_density_cutoffs":cuts.tolist(),
              "history_density_subgroups":subgroups}
    (RUN.parent / f"amazon-{stage}-score.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: output[key] for key in ["common_accounts","contrasts"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["development","test"])
    score(parser.parse_args().stage)
