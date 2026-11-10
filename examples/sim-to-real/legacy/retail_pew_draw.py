"""Compare hard decisions and categorical sampling on the same frozen probabilities."""
import json
import sqlite3

import numpy as np

from retail_pew import RUN, SEED, dataset


def compare():
    people, options = dataset()
    report = json.loads((RUN.parent / "pew-formal-score.json").read_text())
    keys = json.loads((RUN / "pew-freeze.json").read_text())["splits"]["formal"]
    with sqlite3.connect(RUN / "pew.sqlite") as db:
        rows = {}
        for key, arm, out in db.execute("SELECT person,arm,output FROM runs WHERE output IS NOT NULL"):
            rows.setdefault(key, {})[arm] = json.loads(out)
    required = set(report["complete"])
    keys = [key for key in keys if required.issubset(rows[key])]
    assert len(keys) == report["common_people"]
    rng = np.random.default_rng(SEED)
    replicates = 1000
    aggregate = np.zeros(replicates)
    correct = np.zeros(replicates)
    saturated = np.zeros(replicates)
    average_item = []
    for item, choices in options.items():
        valid = [key for key in keys if item in people[key]["truth"]]
        weights = np.array([people[key]["weight"] for key in valid])
        weights /= weights.sum()
        y = np.array([people[key]["truth"][item] for key in valid])
        actual = weights @ np.eye(len(choices))[y]
        p = np.array([rows[key]["rich_probability"][item] for key in valid])
        cumulative = p.cumsum(axis=1)
        random = rng.random((replicates, len(valid)))
        draw = (random[:, :, None] >= cumulative[None, :, :-1]).sum(axis=2)
        simulated = np.eye(len(choices))[draw]
        shares = (simulated * weights[None, :, None]).sum(axis=1)
        error = 50 * np.abs(shares-actual).sum(axis=1)
        aggregate += error / len(options)
        correct += ((draw==y)*weights).sum(axis=1) / len(options)
        saturated += shares.max(axis=1)>=.95-1e-10
        average_item.append({"question":item,"mean_sampled_shares":shares.mean(axis=0).tolist(),
                             "distribution_error_quantiles":np.quantile(error,[.025,.5,.975]).tolist()})
    out = {"scope":"Post-hoc sensitivity analysis on frozen independent predictions",
           "people":len(keys),"questions":len(options),"replicates":replicates,
           "sampling_error_pp":np.quantile(aggregate,[.025,.5,.975]).tolist(),
           "sampling_accuracy":np.quantile(correct,[.025,.5,.975]).tolist(),
           "sampled_95_percent_concentration_questions":np.quantile(saturated,[.025,.5,.975]).tolist(),
           "argmax_error_pp":report["summaries"]["rich_probability_argmax"]["tv_pp"],
           "average_probability_error_pp":report["summaries"]["rich_probability"]["tv_pp"],
           "items":average_item}
    (RUN.parent/"pew-answer-sampling-sensitivity.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in out.items() if k!="items"},indent=2))


if __name__=="__main__":
    compare()
