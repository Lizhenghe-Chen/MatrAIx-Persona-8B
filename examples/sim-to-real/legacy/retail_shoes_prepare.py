"""Recover the original paired stimuli and earlier respondent background."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import tarfile
import tempfile

import pyreadr

from data_sources import data_root
from retail_amazon import RUN, SEED

SOURCE = data_root() / "08_购物研究与候选/Horiuchi2021_Conjoint_SDB/ReplicationPackage_v2.tar.gz"
DESIGNS = {"treat random": "A", "control random": "B", "treat constrained": "C", "control constrained": "D"}
BACKGROUND = {
    "Q2.4": "Age group", "Q2.12": "Education", "Q2.5": "Gender", "Q2.13": "Household income",
    "Q3.1_2": "Agreement: I prefer a cheaper product even if it is not environmentally sustainable",
    "Q3.1_4": "Agreement: It is important for consumers to consider the ethical consequences of the products that they purchase",
}


def load():
    with tempfile.TemporaryDirectory() as directory, tarfile.open(SOURCE) as archive:
        def table(member, key):
            path = Path(directory) / Path(member).name
            path.write_bytes(archive.extractfile("ReplicationPackage/study1/" + member).read())
            return pyreadr.read_r(path)[key]
        return (table("data/study1-wave1.RDS", None), table("data/study1-wave2.RDS", None),
                table("output/full_data.RData", "all"))


def prepare():
    wave1, wave2, analysis = load()
    counts = analysis.MID.value_counts()
    eligible = set(counts[counts == 40].index)
    assert len(eligible) == 3073
    wave1.index = wave1.WorkerId.str.upper()
    wave2 = wave2[wave2.MID.isin(eligible)].set_index("MID")
    assert wave2.index.is_unique and len(wave2) == 3073
    groups = defaultdict(list)
    for person, rows in analysis[analysis.MID.isin(eligible)].groupby("MID"):
        groups[str(rows.iloc[0].design)].append(person)
    splits = {stage: [] for stage in ["development", "test", "reference"]}
    selected = {}
    for design, members in sorted(groups.items()):
        random.Random(f"{SEED}:{design}").shuffle(members)
        for stage, ids in [("development", members[:12]), ("test", members[12:72]), ("reference", members[72:])]:
            for person in ids:
                key = hashlib.sha256(("shoes:" + person).encode()).hexdigest()[:24]
                splits[stage].append(key)
                if stage != "reference":
                    selected[person] = (key, design)
    records = {}
    for person, group in analysis[analysis.MID.isin(selected)].groupby("MID"):
        key, design = selected[person]
        background = {name: str(wave1.at[person.upper(), column]) for column, name in BACKGROUND.items()}
        stimulus = wave2.loc[person]
        prefix = DESIGNS[design]
        # Select eight whole pairs per person, preserving the original presentation order.
        tasks = sorted(random.Random(f"{SEED}:{key}").sample(range(1, 21), 8))
        prepared = []
        for task in tasks:
            attributes = [stimulus[f"{prefix}.{task}.{i}"] for i in range(1, 11)]
            shoes = [[str(stimulus[f"{prefix}.{task}.{j}.{i}"]) for i in range(1, 11)] for j in (1, 2)]
            truth = group[group.task_cont == task].sort_values("profile")["response_num"].astype(int).tolist()
            assert len(set(attributes)) == 10 and len(truth) == 2 and all(1 <= r <= 7 for r in truth)
            assert all(all(x and x.lower() != "nan" for x in shoe) for shoe in shoes)
            prepared.append({"task": task, "attributes": attributes, "shoes": shoes, "truth": truth})
        records[key] = {"design": design, "background": background, "pairs": prepared}
    with SOURCE.open("rb") as file:
        checksum = hashlib.file_digest(file, "sha256").hexdigest()
    return {"split": splits, "source_sha256": checksum, "records": records, "pairs_per_person": 8}


if __name__ == "__main__":
    RUN.mkdir(exist_ok=True, parents=True)
    data = prepare()
    path = RUN / "shoes-freeze.json"
    if path.exists() and json.loads(path.read_text()) != data:
        raise ValueError("Frozen shoe protocol or data changed")
    path.write_text(json.dumps(data, ensure_ascii=False))
    print({k: len(v) for k, v in data["split"].items()})
