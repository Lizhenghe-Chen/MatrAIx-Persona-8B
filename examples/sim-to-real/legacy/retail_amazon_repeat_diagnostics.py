"""Explain aggregate and account-level repeat-purchase errors on frozen forecasts."""
import json
import sqlite3

import numpy as np

from retail_amazon_mix import RUN, baseline


def analyze():
    data = json.loads((RUN/"amazon-mix-freeze.json").read_text())
    scored = json.loads((RUN.parent/"amazon-mix-test-score.json").read_text())
    with sqlite3.connect(RUN/"amazon-mix.sqlite") as db:
        forecasts = {key:json.loads(raw) for key,raw in db.execute(
            "SELECT person,prediction FROM forecasts WHERE prediction IS NOT NULL")}
    keys = [k for k in data["split"]["test"] if k in forecasts]
    assert len(keys) == scored["accounts"]
    actual = np.array([data["records"][k]["target"]["repeat"][1] for k in keys])
    values = {"model":[forecasts[k]["repeat"][1] for k in keys]}
    for name in ("recent","seasonal"):
        values[name] = [baseline(data["records"][k],data["prior"],name)["repeat"][1] for k in keys]
    positive = actual == 1
    results = {}
    for name, v in values.items():
        p = np.array(v)
        p_pos, p_neg = p[positive],p[~positive]
        delta = p_pos[:,None]-p_neg
        brier = 2*np.mean((p-actual)**2)
        group_bias = 2*(p.mean()-actual.mean())**2
        dispersion = 2*np.var(p)
        alignment = 4*np.mean((p-p.mean())*(actual-actual.mean()))
        assert np.isclose(brier, group_bias + dispersion + 2*np.var(actual) - alignment)
        assert np.isclose(brier,scored["tasks"]["repeat"]["results"][name]["brier"])
        bins = np.minimum((p*10).astype(int),9)
        calibration = [{"accounts":int(mask.sum()), "prediction":float(p[mask].mean()),
                        "observed":float(actual[mask].mean())}
                       for i in range(10) if (mask := bins==i).any()]
        results[name] = {"mean_prediction":float(p.mean()), "brier_two_options":float(brier),
                         "aggregate_squared_bias":float(group_bias), "forecast_dispersion":float(dispersion),
                         "alignment_credit":float(alignment),
                         "auc":float(np.mean(delta>0)+.5*np.mean(delta==0)),
                         "calibration":calibration}
    out = {"accounts":len(keys), "observed_repeat_rate":float(actual.mean()), "results":results,
           "scope":"Descriptive diagnosis on already-scored independent accounts; no refitting"}
    (RUN.parent/"amazon-repeat-diagnostics.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print({name:{k:round(x,4) for k,x in row.items() if k!="calibration"} for name,row in results.items()})


if __name__=="__main__":
    analyze()
