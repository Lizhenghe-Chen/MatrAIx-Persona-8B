"""Verify frozen cohorts, source digests, and the scored response checkpoints."""
from collections import Counter
import hashlib
import json
import math
import sqlite3

from data_sources import data_root, frozen_code_matches
from retail_amazon import RUN, SOURCE as AMAZON_SOURCE


def read(name):
    return json.loads((RUN / name).read_text())


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source,"sha256").hexdigest()


def partition(data,key):
    values = [identifier for group in data[key].values() for identifier in group]
    assert len(values) == len(set(values)), "overlapping sample split"


def checked_forecasts(filename, query, phases, arms, options):
    totals = {phase:{arm:0 for arm in arms[phase]} for phase in phases}
    saved = {phase:Counter() for phase in phases}
    retries = {phase:Counter() for phase in phases}
    memberships = {key:phase for phase,keys in phases.items() for key in keys}
    with sqlite3.connect(f"file:{RUN/filename}?mode=ro",uri=True) as db:
        for key,arm,raw,failures in db.execute(query):
            phase = memberships[key]
            assert arm in arms[phase], (filename, phase, arm)
            saved[phase][arm] += 1
            retries[phase].update(json.loads(failures))
            if raw is None:
                continue
            record = json.loads(raw)
            spec = options(key)
            assert set(record) == set(spec), (filename,phase,arm)
            for field, value in record.items():
                if spec[field] is None:
                    assert type(value) in (int,float) and math.isfinite(value) and 0 <= value <= 1
                else:
                    assert isinstance(value,list) and len(value)==spec[field]
                    assert all(type(x) in (int,float) and math.isfinite(x) and 0<=x<=1 for x in value)
                    assert abs(sum(value)-1)<1e-7
            totals[phase][arm] += 1
    return {phase:{"expected_per_arm":len(phases[phase]),"valid":count,
                   "saved_by_arm":{arm:saved[phase][arm] for arm in arms[phase]},
                   "failed_attempts_in_current_checkpoints":dict(retries[phase]),
                   "all_arms_pass_98_pct":min(count.values())/len(phases[phase]) >= .98}
            for phase,count in totals.items()}


def audit():
    pew = read("pew-freeze.json")
    amazon = read("amazon-freeze.json")
    shoes = read("shoes-freeze.json")
    mix = read("amazon-mix-freeze.json")
    for data,key in [(pew,"splits"),(amazon,"split"),(shoes,"split"),(mix,"split")]:
        partition(data,key)
    sources = data_root() / "08_购物研究与候选"
    assert digest(sources/"Pew_Wave13/American-Trends-Panel-Wave-13-Dec-15.zip") == pew["dataset_sha256"]
    assert digest(AMAZON_SOURCE)==amazon["source_gzip_sha256"]
    assert digest(sources/"Horiuchi2021_Conjoint_SDB/ReplicationPackage_v2.tar.gz")==shoes["source_sha256"]
    assert all(mix["split"][p]==amazon["split"][p] for p in mix["split"])
    assert all(q < "2022Q4" for r in amazon["records"].values() for q in r["quarters"])
    assert all(q < "2022Q4" for r in mix["records"].values() for q in r["history"])
    assert all(len(r["pairs"])==8 and len({x["task"] for x in r["pairs"]})==8 for r in shoes["records"].values())
    common = ["basic_choice","rich_choice","basic_probability","rich_probability"]
    pew_arms = {"formal":common,"pilot":[*common,"reverse_probability","shuffle_probability"]}
    shoes_arms = {p:[*common,"attitude_probability"] for p in ("development","test")}
    amazon_arms = {p:["history_only","historical_anchor"] for p in ("development","test")}
    runs = {
        "pew": checked_forecasts("pew.sqlite","SELECT person,arm,output,failures FROM runs",
                                 {k:pew["splits"][k] for k in pew_arms},pew_arms,
                                 lambda _:{q:len(options) for q,options in pew["options"].items()}),
        "shoes": checked_forecasts("shoes.sqlite","SELECT person,arm,output,failures FROM forecasts",
                                   {k:shoes["split"][k] for k in shoes_arms},shoes_arms,
                                   lambda k:{f"{p['task']}.{j}":7 for p in shoes["records"][k]["pairs"] for j in (1,2)}),
        "amazon_category": checked_forecasts("amazon.sqlite","SELECT person,arm,prediction,errors FROM forecasts",
                                             {k:amazon["split"][k] for k in amazon_arms},amazon_arms,
                                             lambda _:{name:None for name in amazon["categories"]}),
        "amazon_mix": checked_forecasts("amazon-mix.sqlite","SELECT person,'forecast',prediction,errors FROM forecasts",
                                        mix["split"],{k:["forecast"] for k in mix["split"]},
                                        lambda _:{k:len(v) for k,v in mix["outcomes"].items()}),
    }
    score_files = {
        "pew": ("formal","pew-formal-score.json","common_people","complete"),
        "shoes": ("test","shoes-test-score.json","people","complete"),
        "amazon_category": ("test","amazon-test-score.json","common_accounts","complete"),
        "amazon_mix": ("test","amazon-mix-test-score.json","accounts",None),
    }
    readiness = {}
    for task, (phase, filename, count_key, coverage_key) in score_files.items():
        path = RUN.parent / filename
        group = runs[task][phase]
        row = {"source": filename, "completion_gate": group["all_arms_pass_98_pct"],
               "score_exists": path.is_file(), "coverage_matches": False}
        if path.exists():
            score = json.loads(path.read_text())
            people = score[count_key]
            assert 0 < people <= min(group["valid"].values())
            if coverage_key:
                row["coverage_matches"] = score[coverage_key] == group["valid"]
            else:
                row["coverage_matches"] = people == group["valid"]["forecast"]
            row["scored_people"] = people
        readiness[task] = row
    runner = RUN.parent.parent.parent
    protocol = read("shoes-model-protocol.json")
    assert pew["runner_sha256"] == protocol["decoder_sha256"]
    assert frozen_code_matches("retail_pew.py", pew["runner_sha256"], digest(runner/"retail_pew.py"))
    assert digest(runner/"retail_shoes_model.py") == protocol["runner_sha256"]
    assert digest(RUN/"shoes-freeze.json") == protocol["cohort_sha256"]
    dataset_digests = {"pew_zip":pew["dataset_sha256"],"shoes_replication_archive":shoes["source_sha256"],
                       "amazon_purchase_csv_gzip":amazon["source_gzip_sha256"]}
    frozen_digests = {name:digest(RUN/name) for name in
                      ("pew-freeze.json","shoes-freeze.json","amazon-freeze.json","amazon-mix-freeze.json")}
    output = {"verification_scope":"Source hashes, split membership, forecast format, completion and score-file coverage; does not independently recalculate numeric scores.",
              "dataset_digests_verified":True,"source_sha256":dataset_digests,"frozen_input_sha256":frozen_digests,
              "survey_runner_digests_verified":True,"all_splits_disjoint":True,"amazon_cutoff_verified":True,
              "forecast_format_verified":True,"cohort_counts":{
                  "pew":{k:len(v) for k,v in pew["splits"].items()},
                  "shoes":{k:len(v) for k,v in shoes["split"].items()},
                  "amazon":{k:len(v) for k,v in amazon["split"].items()},
              },"completion":runs,"score_artifact_coverage_checks":readiness,
              "all_score_artifacts_and_coverage_verified":all(row["completion_gate"] and row["score_exists"] and row["coverage_matches"]
                                                   for row in readiness.values())}
    path=RUN.parent/"运行核验.json"
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(output,ensure_ascii=False,indent=2))


if __name__=="__main__":
    audit()
