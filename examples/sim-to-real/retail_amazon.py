"""Prepare an Amazon temporal holdout and evaluate transparent baselines."""
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import random

from data_sources import data_root

STUDY = Path(__file__).parent / "study"
RUN = STUDY / "08_购物预测/本机运行"
SOURCE = data_root() / "08_购物研究与候选/Open_eCommerce_1.0/amazon-purchases.csv.gz"
SEED = 20261109
CUTOFF = "2022-10-01"
START = "2020-01-01"
END = "2023-01-01"
HISTORY_QUARTERS = 11


def read_history():
    history = defaultdict(lambda: defaultdict(Counter))
    future = defaultdict(Counter)
    with gzip.open(SOURCE, "rt", encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            date = row["Order Date"]
            if not START <= date < END:
                continue
            month = int(date[5:7])
            quarter = f"{date[:4]}Q{(month - 1) // 3 + 1}"
            person = hashlib.sha256(("amazon:" + row["Survey ResponseID"]).encode()).hexdigest()[:24]
            category = row["Category"].strip() or "Unknown category"
            if date < CUTOFF:
                history[person][quarter][category] += 1
            else:
                future[person][category] += 1
    return history, future


def prepare():
    history, future = read_history()
    # Eligibility uses only events before the prediction date.
    keys = sorted(p for p, quarters in history.items() if len(quarters) >= 4 and
                  sum(sum(c.values()) for c in quarters.values()) >= 12)
    random.Random(SEED).shuffle(keys)
    split = {"test": keys[:500], "development": keys[500:560], "reference": keys[560:]}
    assert len(split["reference"]) > 500
    counts = Counter()
    for person in split["reference"]:
        for quarter in history[person].values():
            counts.update(quarter)
    categories = [c for c, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:12]]
    categories.append("Other")
    category_set = set(categories)
    def bucket(counts):
        mapped = Counter()
        for k, v in counts.items():
            mapped[k if k in category_set else "Other"] += v
        return mapped
    records = {}
    for stage in ("development", "test"):
        for key in split[stage]:
            records[key] = {"quarters": {q: dict(bucket(counts)) for q, counts in sorted(history[key].items())},
                            "target": dict(bucket(future[key]))}
    population = Counter()
    for key in split["reference"]:
        for quarter in ("2020Q4", "2021Q4"):
            population.update(bucket(history[key].get(quarter, {})).keys())
    priors = {c: population[c] / (2 * len(split["reference"])) for c in categories}
    return {"source_gzip_sha256": hashlib.file_digest(SOURCE.open("rb"), "sha256").hexdigest(),
            "split": split, "prediction_date": CUTOFF, "history_start": START, "target_end_exclusive": END,
            "categories": categories, "priors": priors, "records": records,
            "eligibility": "At least 12 historical purchase lines across at least four quarters"}


def probabilities(record, categories, prior, variant):
    quarters = record["quarters"]
    if variant == "population":
        return prior
    if variant == "recent":
        periods = ["2021Q4", "2022Q1", "2022Q2", "2022Q3"]
    else:
        periods = [f"{year}Q{q}" for year in (2020, 2021, 2022) for q in (1, 2, 3, 4)
                   if (year, q) != (2022, 4)]
        assert len(periods) == HISTORY_QUARTERS
    return {c: (sum(c in quarters.get(q, {}) for q in periods) + 2 * prior[c]) / (len(periods) + 2)
            for c in categories}


def evaluate(data, stage):
    records = [data["records"][key] for key in data["split"][stage]]
    categories = data["categories"]
    metrics = {}
    for name in ["population", "history", "recent"]:
        squared = 0
        errors = []
        for category in categories:
            pairs = [(probabilities(r, categories, data["priors"], name)[category],
                      float(category in r["target"])) for r in records]
            squared += sum((p - y) ** 2 for p, y in pairs)
            errors.append(abs(sum(p - y for p, y in pairs) / len(records)))
        metrics[name] = {"brier": squared / len(records) / len(categories),
                         "mean_category_prevalence_error_pp": 100 * sum(errors) / len(categories)}
    return metrics


if __name__ == "__main__":
    RUN.mkdir(parents=True, exist_ok=True)
    path = RUN / "amazon-freeze.json"
    data = prepare()
    if path.exists() and json.loads(path.read_text()) != data:
        raise ValueError("Frozen cohort or temporal protocol changed")
    path.write_text(json.dumps(data, ensure_ascii=False))
    metrics = evaluate(data, "development")
    output = {"development_people": 60, "frozen_test_people": 500, "categories": data["categories"],
              "development_only": metrics, "primary_baseline": min(metrics, key=lambda k: metrics[k]["brier"]),
              "prediction_date": CUTOFF}
    (RUN.parent / "amazon-development.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(output, ensure_ascii=False, indent=2))
