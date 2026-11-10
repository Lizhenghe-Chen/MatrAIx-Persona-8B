"""Freeze survey calibration on development data and test added individual signal."""
import argparse
import json
import sqlite3

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder

from retail_pew import ITEMS, RUN, SEED, dataset


def weighted_mean(matrix, weights):
    return np.average(matrix, axis=0, weights=weights)


def predict_stage(stage):
    people, options = dataset()
    split = json.loads((RUN / "pew-freeze.json").read_text())["splits"]
    with sqlite3.connect(RUN / "pew.sqlite") as db:
        raw = {key: json.loads(out) for key,out in db.execute(
            "SELECT person,output FROM runs WHERE arm='rich_probability' AND output IS NOT NULL")}
    keys = [k for k in split[stage] if k in raw]
    if len(keys)/len(split[stage]) < .98:
        raise ValueError("Calibration cohort below 98% completion")
    ref = split["reference"]
    enc = OneHotEncoder(handle_unknown="ignore")
    background = lambda k: list(people[k]["background"].values())
    train_features = enc.fit_transform([background(k) for k in ref])
    stage_features = enc.transform([background(k) for k in keys])
    spec_path = RUN.parent / "pew-calibration-protocol.json"
    spec = {"marginal_logit_shifts": {}, "reference": "rich demographics multinomial logistic regression"}
    if stage == "formal":
        spec = json.loads(spec_path.read_text())
    by_item = {}
    for q in ITEMS:
        n = len(options[q])
        valid = np.array([q in people[k]["truth"] for k in ref])
        ref_truth = np.array([people[k]["truth"].get(q,0) for k in ref])
        ref_weights = np.array([people[k]["weight"] for k in ref])
        stat = LogisticRegression(C=1,max_iter=300)
        stat.fit(train_features[valid],ref_truth[valid],sample_weight=ref_weights[valid])
        baseline = stat.predict_proba(stage_features)
        assert list(stat.classes_) == list(range(n))
        actual = np.eye(n)[[people[k]["truth"].get(q,0) for k in keys]]
        weights = np.array([people[k]["weight"] if q in people[k]["truth"] else 0 for k in keys])
        forecast = np.array([raw[k][q] for k in keys])
        adjusted = np.clip(forecast, .0001, 1)
        if stage == "pilot":
            # Shift intercepts to match the statistical reference for the development case mix.
            target = weighted_mean(baseline,weights)
            ratios = np.ones(n)
            for _ in range(100):
                new = adjusted * ratios
                new /= new.sum(axis=1,keepdims=True)
                current = weighted_mean(new,weights)
                ratios *= target/current
                if np.max(abs(target-current)) < 1e-8:
                    break
            spec["marginal_logit_shifts"][q] = np.log(ratios).tolist()
        calibrated = adjusted * np.exp(spec["marginal_logit_shifts"][q])
        calibrated /= calibrated.sum(axis=1,keepdims=True)
        by_item[q] = (actual,weights,baseline,forecast,calibrated)
    if stage == "pilot":
        numerator,denominator = 0.,0.
        for actual, weights, baseline, _, calibrated in by_item.values():
            residual = calibrated-baseline
            numerator += weighted_mean(((actual-baseline)*residual).sum(axis=1),weights)
            denominator += weighted_mean((residual**2).sum(axis=1),weights)
        spec["model_weight"] = float(np.clip(numerator/denominator,0,1)) if denominator else 0.
        if spec_path.exists() and json.loads(spec_path.read_text())!=spec:
            raise ValueError("Frozen calibration differs")
        spec_path.write_text(json.dumps(spec,indent=2)+"\n")
    draw = np.random.default_rng(SEED).integers(len(keys),size=(2000,len(keys)))
    results = {}
    samples = {}
    for q,(actual,w,baseline,forecast,calibrated) in by_item.items():
        pred = {"statistics_rich":baseline,"raw_model":forecast,"calibrated_model":calibrated,
                "blend":baseline+(calibrated-baseline)*spec["model_weight"]}
        real = weighted_mean(actual,w)
        result = {}
        for name,matrix in pred.items():
            shares = weighted_mean(matrix,w)
            errors = ((matrix-actual)**2).sum(axis=1)
            samples.setdefault(name,[]).append((errors[draw]*w[draw]).sum(axis=1)/w[draw].sum(axis=1))
            result[name] = {"tv_pp":float(50*abs(shares-real).sum()),"brier":float(weighted_mean(errors,w)),
                            "shares":shares.tolist()}
        results[q] = {"real":real.tolist(),"methods":result}
    overall = {name:{metric:float(np.mean([row["methods"][name][metric] for row in results.values()]))
                     for metric in ("brier","tv_pp")} for name in samples}
    brier_draws = {k:np.mean(v,axis=0) for k,v in samples.items()}
    contrasts = {}
    for name in ("raw_model","calibrated_model","blend"):
        diff = brier_draws["statistics_rich"]-brier_draws[name]
        contrasts[name] = {"brier_gain":overall["statistics_rich"]["brier"]-overall[name]["brier"],
                           "interval":np.quantile(diff,[.025,.975]).tolist()}
    summary = {"stage":stage,"people":len(keys),"model_weight":spec["model_weight"],
               "summary":overall,"versus_statistics":contrasts,"questions":results}
    (RUN.parent/f"pew-{stage}-calibration.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in summary.items() if k!="questions"},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("stage",choices=["pilot","formal"])
    predict_stage(parser.parse_args().stage)
