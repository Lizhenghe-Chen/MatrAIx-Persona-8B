"""Frozen North American shopping choice experiment."""

import argparse
import asyncio
import csv
import hashlib
import json
import random
import sqlite3
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from zipfile import ZipFile

import httpx

from experiment import SEED, dump, sha256, stable_seed
from data_sources import frozen_code_matches, shopping_sources
from optimize import MODELS, P1, PARAMS, request_for

SURVEYS = ("origin", "packaging", "pew")
CONDITIONS = ("P0+B1", "P0+B3", "P1+B1", "P1+B3")
STRATA = ("18–64|Below associate degree", "18–64|Associate degree or higher",
          "65+|Below associate degree", "65+|Associate degree or higher")
PEW_ITEMS = {
    "ONLSHOP1_a": ("Do you ever buy things online using a desktop or laptop computer?", ("Yes", "No")),
    "ONLSHOP1_b": ("Do you ever buy things online using a tablet?", ("Yes", "No")),
    "ONLSHOP1_c": ("Do you ever buy things online using a smartphone?", ("Yes", "No")),
    "SHOP4": ("If given the choice, do you generally prefer to buy online or from a physical store?",
              ("Online", "Physical store")),
    "ONLSHOP3": ("Do you follow any influencers or content creators on social media?", ("Yes", "No", "Not sure")),
    "ONLSHOP4": ("Have you ever purchased something after seeing an influencer or content creator post about it on social media?",
                 ("Yes", "No", "Not sure")),
}
DATES = {"origin": "June 2020", "packaging": "2019", "pew": "July 2022"}


def product_people(path, survey):
    original = {}
    if survey == "origin":
        with path.with_name("origin-original.tab").open(newline="") as stream:
            original = {r["id"]: r for r in csv.DictReader(stream, delimiter="\t")}
    by_person = defaultdict(lambda: defaultdict(list))
    with path.open(newline="") as stream:
        for row in csv.DictReader(stream):
            by_person[row["id"]][row["task"]].append(row)
    people = []
    for raw_id, groups in by_person.items():
        pid = identity(survey, raw_id)
        row = next(iter(groups.values()))[0]
        if survey == "origin":
            older = int(row["cov_age"]) >= 65
            degree = row["cov_education"] in ("2-year Degree", "College", "Prof Degree/PhD")
            source = original[raw_id]
            for i in range(1, 7):
                a, b = source[f"ethno{i}"], row[f"cov_ethno{i}"]
                if (float(a) if a else None) != (float(b) if b else None):
                    raise ValueError("Bankert source ID alignment failed")
            if int(float(source["inc"])) != int(row["cov_income"]):
                raise ValueError("Bankert source income alignment failed")
            income = int(row["cov_income"])
            band = ("Under $30,000" if income <= 2 else "$30,000–$59,000" if income < 6
                    else "$60,000–$120,000" if income < 10 else "Above $120,000")
            score = source["ethnocentrism"]
            background = {"Household income": band, "Cultural in-group favoritism, 0 (lowest) to 1 (highest)":
                          f"{float(score):.3f}" if score else "Unknown"}
            instructions = ("Compare similar products. If you had to buy one, which would you choose? "
                            "Quality/customer satisfaction is shown on a five-star scale.")
        else:
            older = row["cov_age_group"] == "65+"
            degree = row["cov_education"] in ("AA or BA", "Graduate degree")
            background = {"Household income (USD)": row["cov_income_usd"] or "Unknown",
                          "US census region": row["cov_region"] or "Unknown"}
            instructions = ("Imagine both six-packs are the style of beer you most often buy. The displayed attributes "
                            "are the only differences and do not change the taste. You can choose either beer or neither.")
            if row["trial_cheap_talk"] == "1":
                instructions += (" No money changes hands in this survey. Make each choice as if paying the displayed "
                                 "price at your usual retailer. Choose neither if you would buy neither.")
        tasks = []
        for key in sorted(groups, key=int):
            rows = sorted(groups[key], key=lambda item: int(item["profile"]))
            chosen = [str(i + 1) for i, item in enumerate(rows) if item["choice"] == "1"]
            if len(rows) != 2 or len(chosen) > 1 or (not chosen and survey == "origin"):
                raise ValueError(f"{survey}: invalid choice pair")
            attrs = [{k.removeprefix("attr_"): v for k, v in item.items() if k.startswith("attr_")} for item in rows]
            if survey == "origin" and attrs[0]["product"] != attrs[1]["product"]:
                raise ValueError("Origin pair compares different products")
            card = key if survey == "origin" else row["trial_block"] + ":" + key
            tasks.append({"id": key, "card": card, "truth": chosen[0] if chosen else "0", "attrs": attrs,
                          "codes": ("1", "2") if survey == "origin" else ("1", "2", "0")})
        people.append({"id": pid, "stratum": STRATA[2 * older + degree], "weight": 1.,
                       "background": background, "instructions": instructions, "tasks": tasks,
                       "treatment": row.get("trial_cheap_talk", "")})
    return people


def identity(survey, raw_id):
    return hashlib.sha256(f"shopping/{survey}/{raw_id}".encode()).hexdigest()[:24]


def pew_people(path):
    import pyreadstat

    names = ["QKEY", "WEIGHT_W111", "F_AGECAT", "F_EDUCCAT2", "F_INC_SDT1", "F_INTFREQ",
             "XTABLET_W111", "SNSUSE_W111", *(f"{q}_W111" for q in PEW_ITEMS)]
    with ZipFile(path) as zipfile, tempfile.TemporaryDirectory() as directory:
        sav = zipfile.extract(next(name for name in zipfile.namelist() if name.endswith(".sav")), directory)
        table, meta = pyreadstat.read_sav(sav, usecols=names, output_format="dict")
    people = []
    for values in zip(*(table[k] for k in names), strict=True):
        row = dict(zip(names, values, strict=True))
        age, edu, weight = (row[k] for k in ("F_AGECAT", "F_EDUCCAT2", "WEIGHT_W111"))
        if age not in (1, 2, 3, 4) or edu not in range(1, 7) or not weight or weight <= 0:
            continue
        if row["XTABLET_W111"] != 2:
            continue
        tasks = []
        for q, (question, options) in PEW_ITEMS.items():
            codes = tuple(str(i + 1) for i in range(len(options)))
            raw = row[f"{q}_W111"]
            eligible = q not in ("ONLSHOP3", "ONLSHOP4") or row["SNSUSE_W111"] == 1
            valid = raw in range(1, len(options) + 1)
            if not eligible and valid:
                raise ValueError(f"Pew routing disagrees with source for {q}")
            if eligible:
                tasks.append({"id": q, "card": q, "truth": str(int(raw)) if valid else None,
                              "question": question, "options": options, "codes": codes})
        if not any(t["truth"] for t in tasks):
            continue
        background = {label: meta.variable_value_labels[k].get(row[k], "Unknown") if row[k] != 99 else "Unknown"
                      for label, k in (("Family income", "F_INC_SDT1"), ("Internet use frequency", "F_INTFREQ"))}
        people.append({"id": identity("pew", row["QKEY"]), "stratum": STRATA[2 * (age == 4) + (edu >= 4)],
                       "weight": weight, "background": background, "instructions": "", "tasks": tasks})
    return people


def split(people, survey):
    formal, pilot, training = [], [], []
    sizes = (72, 60, 48, 60) if survey == "origin" else (60,) * 4
    for stratum, n in zip(STRATA, sizes, strict=True):
        group = sorted((p for p in people if p["stratum"] == stratum), key=lambda p: p["id"])
        if len(group) <= n + 12:
            raise ValueError(f"{survey}/{stratum}: only {len(group)} people for {n} formal plus pilot and training")
        random.Random(stable_seed(SEED, survey, stratum)).shuffle(group)
        formal.extend(group[:n])
        pilot.extend(group[n:n + 12])
        training.extend(group[n + 12:])
    return {"formal": formal, "pilot": pilot, "training": training}


def prompt(survey, person, condition):
    age, edu = person["stratum"].split("|")
    system = (f"Answer as an adult living in the United States during {DATES[survey]}."
              if condition.startswith("P0") else f"Survey context: United States during {DATES[survey]}. {P1}")
    system += f"\nAge group: {age}\nEducation: {edu}"
    if condition.endswith("B3"):
        system += "\n" + "\n".join(f"{key}: {value}" for key, value in person["background"].items())
    body = [person["instructions"], "For each item, return its option ID. Output JSON only, e.g. "
            '{"answers":{"q1":"1"}}. Include exactly one value for each item.']
    mapping = {}
    for i, task in enumerate(person["tasks"], 1):
        key = f"q{i}"
        codes = list(task["codes"])
        if survey == "origin" and stable_seed(SEED, person["id"], task["id"]) % 2:
            codes.reverse()
        mapping[key] = dict(zip(task["codes"], codes, strict=True))
        if survey == "pew":
            body.append(f"{key}. {task['question']} " + "; ".join(f"{j} = {v}" for j, v in
                        zip(codes, task["options"], strict=True)))
            if task["id"] == "ONLSHOP3":
                body.insert(-1, "Influencers and content creators use social media to promote products, share tutorials, or shape opinions and purchases.")
        else:
            rows = [f"{code}: " + ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in attrs.items())
                    for code, attrs in zip(codes[:2], task["attrs"], strict=True)]
            rows.sort()
            if "0" in codes:
                rows.append("0: Do not buy either")
            body.append(f"{key}. Which would you choose? " + " | ".join(rows))
    user = "\n".join(body)
    if person["id"] in system + user:
        raise ValueError("Respondent ID entered model inputs")
    return {"model": "qwen", "human": True, "system": system, "user": user}, mapping


async def ask(client, survey, person, condition, attempts):
    job, mapping = prompt(survey, person, condition)
    endpoint, headers, payload = request_for(job)
    failures = []
    for attempt in range(attempts):
        try:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
            choice = body["choices"][0]
            message = choice["message"]
            if (body["model"] != MODELS["qwen"] or choice["finish_reason"] != "stop"
                    or message.get("reasoning_content") or message.get("reasoning")):
                raise ValueError("Model protocol or reasoning mismatch")
            answers = json.loads(message["content"])["answers"]
            if set(answers) != set(mapping):
                raise ValueError("Wrong answer keys")
            decoded = {t["id"]: mapping[q][str(answers[q])] for q, t in zip(mapping, person["tasks"], strict=True)}
            return {"answers": decoded, "failures": failures, "usage": body.get("usage")}
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as error:
            failures.append({"kind": type(error).__name__, "status": getattr(getattr(error, "response", None), "status_code", None)})
            if attempt + 1 < attempts:
                await asyncio.sleep(2 ** attempt)
    return {"failures": failures}


async def execute(study, datasets, stage):
    with sqlite3.connect(study / "checkpoints.sqlite") as db:
        db.execute("CREATE TABLE IF NOT EXISTS runs (stage TEXT, survey TEXT, id TEXT, cell TEXT, payload TEXT, PRIMARY KEY(stage,survey,id,cell))")
        saved = {(s, p, c): json.loads(value) for s, p, c, value in db.execute(
            "SELECT survey,id,cell,payload FROM runs WHERE stage=?", (stage,))}
        if stage == "formal":
            ok = {(s, p, c) for s, p, c, value in db.execute(
                "SELECT survey,id,cell,payload FROM runs WHERE stage='pilot'") if "answers" in json.loads(value)}
            if any((s, p["id"], c) not in ok for s, ds in datasets.items() for p in ds["pilot"] for c in CONDITIONS):
                raise ValueError("Pass all pilot checks before formal run")
        jobs = [(s, p, c) for s, ds in datasets.items() for p in ds[stage] for c in CONDITIONS
                if "answers" not in saved.get((s, p["id"], c), {})]
        random.Random(SEED).shuffle(jobs)
        print(f"{stage}: {len(jobs)} requests pending", flush=True)
        gate = asyncio.Semaphore(48)
        async with httpx.AsyncClient(timeout=120, limits=httpx.Limits(max_connections=48), trust_env=False) as client:
            async def run(job):
                survey, person, condition = job
                async with gate:
                    result = await ask(client, survey, person, condition, 3)
                key = (survey, person["id"], condition)
                result["failures"] = saved.get(key, {}).get("failures", []) + result["failures"]
                return key, result
            for i, future in enumerate(asyncio.as_completed([run(j) for j in jobs]), 1):
                key, result = await future
                saved[key] = result
                db.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?)", (stage, *key, json.dumps(result)))
                db.commit()
                if i % 100 == 0:
                    print(f"{stage}: {i}/{len(jobs)} attempted", flush=True)
        summary = {f"{s}/{c}": [sum("answers" in saved.get((s, p["id"], c), {}) for p in ds[stage]), len(ds[stage])]
                   for s, ds in datasets.items() for c in CONDITIONS}
        dump(study / f"{stage}-completion.json", summary)
        if any(ok / n < (1 if stage == "pilot" else .98) for ok, n in summary.values()):
            raise SystemExit(f"{stage}: completion threshold not met")
        print(f"{stage}: {sum(pair[0] for pair in summary.values())} valid", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "pilot", "formal", "score"))
    parser.add_argument("study", type=Path)
    args = parser.parse_args()
    study = args.study
    sources = shopping_sources()
    people = {s: product_people(sources[f"{s}.csv"], s) for s in SURVEYS[:2]}
    if sources["pew.zip"].is_file():
        people["pew"] = pew_people(sources["pew.zip"])
    datasets = {s: split(rows, s) for s, rows in people.items()}
    manifest = {"seed": SEED, "model": MODELS["qwen"], "parameters": PARAMS, "thinking": False,
                "source": {name: sha256(path) for name, path in sources.items() if path.is_file()},
                "prompt_code_sha256": sha256(Path(__file__)),
                "original_prompt_code_sha256": sha256(Path(__file__).with_name("optimize.py")),
                "groups": {s: {k: dict(Counter(p["stratum"] for p in rows)) for k, rows in ds.items()}
                           for s, ds in datasets.items()},
                "input_hash": hashlib.sha256(json.dumps([
                    (s, p["id"], c, prompt(s, p, c)) for s, ds in datasets.items() for part in ("pilot", "formal")
                    for p in ds[part] for c in CONDITIONS], sort_keys=True).encode()).hexdigest()}
    path = study / "manifest.json"
    if path.exists():
        saved = json.loads(path.read_text())
        for field, name in (("prompt_code_sha256", "shopping.py"), ("original_prompt_code_sha256", "optimize.py")):
            if frozen_code_matches(name, saved[field], manifest[field]):
                manifest[field] = saved[field]
        if saved != manifest:
            raise ValueError("Frozen experiment inputs changed")
    else:
        dump(path, manifest)
    dump(study / "sample-index.json", {s: {k: [p["id"] for p in rows] for k, rows in ds.items()}
                                      for s, ds in datasets.items()})
    if args.stage == "score":
        from shopping_score import score
        score(study, people, datasets)
    elif args.stage != "prepare":
        asyncio.run(execute(study, datasets, args.stage))
    else:
        print(manifest["groups"])


if __name__ == "__main__":
    main()
