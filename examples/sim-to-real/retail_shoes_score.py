"""Score paired shoe forecasts against observed ratings and a disjoint statistical model."""
import argparse
import hashlib
import json
import sqlite3

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder

from retail_shoes_prepare import BACKGROUND, RUN, SEED, load

ATTRIBUTES = dict(zip(
    ("Ave. Customer Review", "Best Seller", "Brand", "Color", "Model Year", "Price", "Shipping", "Weight"),
    (f"filler{i}" for i in range(1, 9)), strict=True,
))
FLAGS = {
    "Eco-Friendly Materials": ("withEco", "100% Eco-Friendly Materials Used"),
    "Gel Cushioning": ("withGel", "Has Gel Cushioning"),
}
ARMS = ["basic_choice", "rich_choice", "basic_probability", "rich_probability", "attitude_probability"]
LEVELS = np.arange(1, 8)


def add_pair_features(frame):
    for col in ("filler6", "filler1", "withEco", "withGel"):
        paired = frame.groupby("pair", sort=False)[col].transform(lambda s: s.iloc[::-1].to_numpy())
        frame["other_" + col] = paired
    frame["design_eco"] = frame["design"] + "|" + frame["withEco"]
    frame["design_gel"] = frame["design"] + "|" + frame["withGel"]
    return frame


def test_frame(data, keys):
    rows = []
    for key in keys:
        record = data["records"][key]
        for pair in record["pairs"]:
            for j, shoe in enumerate(pair["shoes"], 1):
                attrs = dict(zip(pair["attributes"], shoe, strict=True))
                row = {col: attrs[name] for name, col in ATTRIBUTES.items()}
                row.update({col: str(int(attrs[name] == yes)) for name, (col, yes) in FLAGS.items()})
                row.update(record["background"])
                row.update({"design": record["design"], "profile": str(j), "pair": key + "." + str(pair["task"]),
                            "answer": pair["truth"][j - 1]})
                rows.append(row)
    return add_pair_features(pd.DataFrame(rows))


def training_frame(data, wave1, analysis):
    wave1.index = wave1.WorkerId.str.upper()
    reference_keys = set(data["split"]["reference"])
    people = {person for person in analysis.MID.unique() if hashlib.sha256(
        ("shoes:" + person).encode()).hexdigest()[:24] in reference_keys}
    reference = analysis[analysis.MID.isin(people)].copy()
    assert len(people) == len(data["split"]["reference"]) and len(reference) == 40 * len(people)
    reference.sort_values(["MID", "task_cont", "profile"], inplace=True)
    reference["pair"] = reference.MID + "." + reference.task_cont.astype(str)
    for col in ("withEco", "withGel", "profile"):
        reference[col] = reference[col].astype(int).astype(str)
    for col, name in BACKGROUND.items():
        reference[name] = reference.MID.str.upper().map(wave1[col]).astype(str)
    return add_pair_features(reference)


def baseline(data, frame):
    wave1, _, analysis = load()
    compare = analysis.copy()
    masked = {person: hashlib.sha256(("shoes:" + person).encode()).hexdigest()[:24]
              for person in compare.MID.unique()}
    compare["pair"] = compare.MID.map(masked) + "." + compare.task_cont.astype(int).astype(str)
    compare = compare[compare["pair"].isin(frame["pair"])].copy()
    for col in ("withEco", "withGel", "profile"):
        compare[col] = compare[col].astype(int).astype(str)
    compare["answer"] = compare.response_num.astype(int)
    columns = ["pair","profile","answer","design",*ATTRIBUTES.values(),"withEco","withGel"]
    expected = compare[columns].sort_values(["pair","profile"]).reset_index(drop=True)
    observed = frame[columns].sort_values(["pair","profile"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(observed,expected,check_dtype=False)
    train = training_frame(data,wave1,analysis)
    fields = [*ATTRIBUTES.values(), *(v[0] for v in FLAGS.values()), "design", "profile",
              "other_filler6", "other_filler1", "other_withEco", "other_withGel", "design_eco", "design_gel",
              *BACKGROUND.values()]
    encoder = OneHotEncoder(handle_unknown="ignore")
    inputs = encoder.fit_transform(train[fields].astype(str))
    model = LogisticRegression(C=1, max_iter=250, tol=0.0005)
    model.fit(inputs, train.response_num.astype(int))
    assert list(model.classes_) == list(LEVELS)
    return model.predict_proba(encoder.transform(frame[fields].astype(str)))


def metric_rows(predictions, truth, indices):
    real = truth.mean(axis=1)[indices].mean(axis=1)
    predicted = predictions.mean(axis=1)[indices].mean(axis=1)
    tv = 50 * abs(predicted - real).sum(axis=1)
    brier = ((predictions - truth) ** 2).sum(axis=2).mean(axis=1)[indices].mean(axis=1)
    return tv, brier


def score(stage):
    data = json.loads((RUN / "shoes-freeze.json").read_text())
    keys = data["split"][stage]
    with sqlite3.connect(RUN / "shoes.sqlite") as db:
        outputs = {(key, arm): json.loads(out) for key, arm, out in db.execute(
            "SELECT person, arm, output FROM forecasts WHERE output IS NOT NULL")}
    coverage = {arm: sum((key, arm) in outputs for key in keys) for arm in ARMS}
    if min(coverage.values()) / len(keys) < .98:
        raise ValueError(f"Completion below 98%: {coverage}")
    common = [key for key in keys if all((key, arm) in outputs for arm in ARMS)]
    frame = test_frame(data, common)
    pred = {"statistics": baseline(data, frame)}
    for arm in ARMS:
        pred[arm] = np.array([outputs[key, arm][f"{pair['task']}.{j}"]
                              for key in common for pair in data["records"][key]["pairs"] for j in (1, 2)])
    pred["rich_probability_argmax"] = np.eye(7)[pred["rich_probability"].argmax(axis=1)]
    n = len(common)
    truth = np.eye(7)[frame.answer.to_numpy() - 1].reshape(n, -1, 7)
    groups = np.array([data["records"][key]["design"] for key in common])
    rng = np.random.default_rng(SEED)
    indices = np.concatenate([rng.choice(ix, size=(2000, len(ix))) for g in sorted(set(groups))
                              if len(ix := np.flatnonzero(groups == g))], axis=1)
    calibration_path = RUN.parent / "shoes-calibration-protocol.json"
    if stage == "development":
        counts = np.ones((7,7))
        np.add.at(counts, (pred["rich_choice"].argmax(axis=1), frame.answer.to_numpy()-1), 1)
        mapping = counts/counts.sum(axis=1,keepdims=True)
    else:
        protocol = json.loads(calibration_path.read_text())
        mapping = np.array(protocol["rating_mapping"])
    pred["calibrated_rating"] = mapping[pred["rich_choice"].argmax(axis=1)]
    base = pred["statistics"]
    residual = pred["calibrated_rating"] - base
    if stage == "development":
        variance = np.sum(residual**2)
        weight = float(np.clip(np.sum((truth.reshape(-1,7)-base)*residual)/variance,0,1)) if variance else 0.
        protocol = {"rating_mapping":mapping.tolist(),"model_weight":weight,"fit":"48 development participants only"}
        if calibration_path.exists() and json.loads(calibration_path.read_text()) != protocol:
            raise ValueError("Frozen shoe calibration changed")
        calibration_path.write_text(json.dumps(protocol,indent=2)+"\n")
    pred["blend"] = base+protocol["model_weight"]*residual
    expected_real = (truth @ LEVELS).reshape(-1, 2)
    price = frame.filler6.str.replace("$", "", regex=False).astype(float).to_numpy().reshape(-1, 2)
    eco = frame.withEco.astype(int).to_numpy().reshape(-1, 2)
    price_sign = np.sign(price[:, 1] - price[:, 0])
    eco_sign = np.sign(eco[:, 0] - eco[:, 1])
    def gap(expected, sign):
        diff = expected[:, 0] - expected[:, 1]
        return float((diff[sign != 0] * sign[sign != 0]).mean())
    summary = {}
    boot = {}
    for arm, flat in pred.items():
        p = flat.reshape(n, -1, 7)
        real_dist, sim_dist = truth.mean(axis=(0,1)), p.mean(axis=(0,1))
        expected = (flat @ LEVELS).reshape(-1,2)
        boot[arm] = metric_rows(p, truth, indices)
        summary[arm] = {
            "tv_pp": float(50 * abs(sim_dist - real_dist).sum()),
            "brier": float(((p-truth)**2).sum(axis=2).mean()),
            "accuracy": float((p.argmax(axis=2)==truth.argmax(axis=2)).mean()),
            "rating_mae": float(np.abs((p-truth)@LEVELS).mean()),
            "distribution": sim_dist.tolist(),
            "cheaper_minus_expensive": gap(expected, price_sign),
            "eco_minus_regular": gap(expected, eco_sign),
            "design_distributions": {g: p[groups == g].mean(axis=(0,1)).tolist() for g in sorted(set(groups))},
        }
    comparisons = [("basic_choice", "rich_choice"), ("rich_choice","rich_probability"),
                   ("basic_probability", "rich_probability"), ("rich_probability_argmax", "rich_probability"),
                   ("rich_probability", "attitude_probability"), ("statistics", "attitude_probability"),
                   ("rich_choice", "calibrated_rating"), ("statistics", "calibrated_rating"),
                   ("statistics", "blend")]
    contrasts = []
    for old, new in comparisons:
        diffs = [a-b for a,b in zip(boot[old],boot[new], strict=True)]
        contrasts.append({"from": old, "to": new,
                          "tv_improvement_pp": summary[old]["tv_pp"]-summary[new]["tv_pp"],
                          "tv_interval": np.quantile(diffs[0],[.025,.975]).tolist(),
                          "brier_improvement": summary[old]["brier"]-summary[new]["brier"],
                          "brier_interval": np.quantile(diffs[1],[.025,.975]).tolist()})
    controlled = {}
    for attribute, flag in (("Eco-Friendly Materials", "withEco"), ("Gel Cushioning", "withGel")):
        exact = np.array([data["records"][key]["design"].endswith("constrained") and
                          [name for name, left, right in zip(pair["attributes"], *pair["shoes"], strict=True)
                           if left != right] == [attribute]
                          for key in common for pair in data["records"][key]["pairs"]])
        flag_values = frame[flag].astype(int).to_numpy().reshape(-1,2)
        direction = np.where(exact, np.sign(flag_values[:,0]-flag_values[:,1]),0)
        assert exact.sum()>0 and np.all(direction[exact]!=0)
        def pair_values(expected):
            return (direction * (expected[:,0]-expected[:,1])).reshape(n,-1)
        actual_values = pair_values(expected_real)
        pair_counts = exact.reshape(n,-1).sum(axis=1)
        def estimate(values):
            return float(values.sum()/pair_counts.sum())
        def bootstrap_effect(values):
            return values.sum(axis=1)[indices].sum(axis=1) / pair_counts[indices].sum(axis=1)
        actual_boot = bootstrap_effect(actual_values)
        comparisons = {}
        for arm, flat in pred.items():
            values = pair_values((flat@LEVELS).reshape(-1,2))
            delta = bootstrap_effect(values) - actual_boot
            comparisons[arm] = {"effect":estimate(values),"minus_real":estimate(values-actual_values),
                                "minus_real_95_interval":np.quantile(delta,[.025,.975]).tolist()}
        controlled[attribute] = {"pairs":int(pair_counts.sum()),"people":int((pair_counts>0).sum()),
                                 "real_effect":estimate(actual_values),
                                 "real_95_interval":np.quantile(actual_boot,[.025,.975]).tolist(),
                                 "methods":comparisons}
    output = {"stage": stage, "people": n, "requested": len(keys), "complete": coverage,
              "paired_tasks": n*8, "source_ratings_and_all_ten_attributes_verified": True, "reference_people": len(data["split"]["reference"]), "summary": summary,
              "real": {"distribution": truth.mean(axis=(0,1)).tolist(),
                       "cheaper_minus_expensive": gap(expected_real,price_sign), "eco_minus_regular": gap(expected_real,eco_sign),
                       "design_distributions": {g: truth[groups == g].mean(axis=(0,1)).tolist() for g in sorted(set(groups))}},
              "contrasts": contrasts, "controlled_attribute_effects": controlled, "calibration_model_weight": protocol["model_weight"]}
    (RUN.parent / f"shoes-{stage}-score.json").write_text(json.dumps(output, ensure_ascii=False, indent=2)+"\n")
    print({arm: (round(m["tv_pp"],2),round(m["brier"],4)) for arm,m in summary.items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["development","test"])
    score(parser.parse_args().stage)
