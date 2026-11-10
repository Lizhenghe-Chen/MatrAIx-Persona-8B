"""Run the Wave 13 shopping experiment with local, resumable checkpoints."""
import argparse
import asyncio
import hashlib
import json
import math
from pathlib import Path
import random
import sqlite3
import tempfile
import zipfile

import httpx
import pyreadstat

from data_sources import data_root
from optimize import MODELS, P1, request_for

STUDY = Path(__file__).parent / "study"
RUN = STUDY / "08_购物预测" / "本机运行"
SOURCE = data_root() / "08_购物研究与候选/Pew_Wave13/American-Trends-Panel-Wave-13-Dec-15.zip"
SEED = 20261109
IMPORTANCE = "In general, when shopping for something that you haven’t purchased before, how important is it for you to be able to"
REVIEWS = "Consumers today can access lots of customer reviews and ratings about products and services they might want to buy. How much do you think these ratings and reviews help to"
PHONE = "Do you ever use a cell phone while you are inside a physical store to"
ITEMS = {
    **{f"SHOP6{k}": f"{IMPORTANCE} {v}?" for k, v in zip("ABCDEFG", (
        "look at or try out the product in person", "read ratings or reviews that other people have posted online",
        "buy online, without having to make a trip to the store", "compare prices from a number of different sellers",
        "be able to ask questions about what it is that you’re buying", "get advice or recommendations from people you know",
        "buy from a store or seller that you are familiar with"))},
    **{f"SHOP7{k}": f"{REVIEWS} {v}?" for k, v in zip("ABC", (
        "ensure that the products and services people buy are safe", "make consumers feel confident about what they are buying",
        "make companies be accountable to their customers"))},
    "SHOP12": "How often do you read customer ratings or reviews that other people have posted online when buying something for the first time?",
    "SHOP20B": f"{PHONE} see if you can find a better price online for something you want to buy?",
    "SHOP20C": f"{PHONE} look up reviews or other information online about a product you want to buy?",
}
ARMS = {
    "basic_choice": (False, False, False, False),
    "rich_choice": (True, False, False, False),
    "basic_probability": (False, True, False, False),
    "rich_probability": (True, True, False, False),
    "reverse_probability": (True, True, True, False),
    "shuffle_probability": (True, True, False, True),
}
FIELDS = {"F_AGECAT_FINAL": "Age group", "F_EDUCCAT_FINAL": "Education", "F_INCOME_FINAL": "Income",
          "F_SEX_FINAL": "Sex", "F_CREGION_FINAL": "Region"}


def dataset():
    with tempfile.TemporaryDirectory() as directory, zipfile.ZipFile(SOURCE) as archive:
        path = Path(directory) / "survey.sav"
        path.write_bytes(archive.read("W13_Dec15/ATP W13.sav"))
        frame, meta = pyreadstat.read_sav(path, output_format="dict")
    labels = meta.variable_value_labels
    options = {}
    for question in ITEMS:
        count = 4 if question.startswith(("SHOP6", "SHOP7")) else 3 if question == "SHOP12" else 2
        options[question] = [labels[question + "_W13"][index] for index in range(1, count + 1)]
    people = {}
    for i, identifier in enumerate(frame["QKEY"]):
        if frame["NEW_Device_Type_W13"][i] not in (1, 2, 3):
            continue
        key = hashlib.sha256(f"pew13:{int(identifier)}".encode()).hexdigest()[:24]
        people[key] = {
            "background": {name: labels[col].get(frame[col][i], "Unknown") for col, name in FIELDS.items()},
            "weight": frame["WEIGHT_W13"][i],
            "truth": {q: int(frame[q + "_W13"][i]) - 1 for q in ITEMS
                      if frame[q + "_W13"][i] in range(1, len(options[q]) + 1)},
        }
    assert len(people) == 4317
    return people, options


def request(person, donor, key, arm, options):
    rich, probability, reverse, shuffle = ARMS[arm]
    background = dict(list(person["background"].items())[:2])
    if rich:
        background.update(list((donor if shuffle else person)["background"].items())[2:])
    order = list(ITEMS)
    rng = random.Random(f"{SEED}:{key}")
    for start, stop in [(0, 7), (7, 10), (11, 13)]:
        group = order[start:stop]
        rng.shuffle(group)
        order[start:stop] = group
    lines = []
    mapping = {}
    for i, q in enumerate(order, 1):
        indices = list(range(len(options[q])))
        if reverse:
            indices.reverse()
        mapping[str(i)] = (q, indices)
        choices = " | ".join(f"{j + 1}. {options[q][k]}" for j, k in enumerate(indices))
        lines.append(f"{i}. {ITEMS[q]}\n{choices}")
    format_instruction = (
        'Return JSON keyed by item number, with an array of probabilities in displayed option order. '
        'Each array must sum to 1. Example {"1":[0.2,0.3,0.4,0.1]}.'
        if probability else 'Return JSON keyed by item number with the displayed option number. Example {"1":2}.'
    )
    system = f"United States, November–December 2015. {P1}\n" + "\n".join(f"{k}: {v}" for k,v in background.items())
    endpoint, headers, body = request_for({"human": True, "model": "qwen", "system": system,
                                           "user": format_instruction + "\n" + "\n".join(lines)})
    return endpoint, headers, body, mapping


def decode(content, mapping, probability):
    raw = json.loads(content)
    if set(raw) != set(mapping):
        raise ValueError("item keys mismatch")
    result = {}
    for item, (q, order) in mapping.items():
        value = raw[item]
        if probability:
            if not isinstance(value, list) or len(value) != len(order):
                raise ValueError("probability length")
            if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in value):
                raise ValueError("probability values")
            total = sum(value)
            if not 0.98 <= total <= 1.02:
                raise ValueError("probability sum")
            vector = [v / total for v in value]
        else:
            if isinstance(value, str) and value in {str(i) for i in range(1, len(order) + 1)}:
                value = int(value)
            if type(value) is not int or not 1 <= value <= len(order):
                raise ValueError("invalid option")
            vector = [float(i == value) for i in range(1, len(order) + 1)]
        result[q] = [vector[order.index(i)] for i in range(len(order))]
    return result


async def execute(stage):
    people, options = dataset()
    keys = sorted(people)
    random.Random(SEED).shuffle(keys)
    # Simple random split avoids distorting the original age and education distribution.
    partitions = {"pilot": keys[:48], "formal": keys[48:288], "reference": keys[288:]}
    RUN.mkdir(parents=True, exist_ok=True)
    manifest = {"dataset_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "splits": partitions, "seed": SEED, "items": ITEMS, "options": options}
    path = RUN / "pew-freeze.json"
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise ValueError("Frozen protocol differs from current code or data")
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    arms = list(ARMS) if stage == "pilot" else list(ARMS)[:4]
    selected = partitions[stage]
    donors = selected[1:] + selected[:1]
    db = sqlite3.connect(RUN / "pew.sqlite")
    db.execute("CREATE TABLE IF NOT EXISTS runs (person TEXT, arm TEXT, output TEXT, failures TEXT, PRIMARY KEY(person,arm))")
    done = set(db.execute("SELECT person, arm FROM runs WHERE output IS NOT NULL"))
    semaphore = asyncio.Semaphore(16)
    async with httpx.AsyncClient(timeout=100, trust_env=False) as client:
        async def one(key, donor, arm):
            if (key, arm) in done:
                return
            endpoint, headers, body, mapping = request(people[key], people[donor], key, arm, options)
            failures = []
            output = None
            async with semaphore:
                for attempt in range(3):
                    try:
                        response = await client.post(endpoint, json=body, headers=headers)
                        response.raise_for_status()
                        data = response.json()
                        choice = data["choices"][0]
                        if data["model"] != MODELS["qwen"] or choice["finish_reason"] != "stop" or choice["message"].get("reasoning_content"):
                            raise ValueError("unexpected model protocol")
                        output = decode(choice["message"]["content"], mapping, ARMS[arm][1])
                        break
                    except (httpx.HTTPError, KeyError, TypeError, ValueError, IndexError) as error:
                        failures.append(type(error).__name__ + (": " + str(error) if type(error) is ValueError else ""))
                        await asyncio.sleep(attempt + 1)
                db.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?)", (
                    key, arm, json.dumps(output) if output else None, json.dumps(failures)))
                db.commit()
        await asyncio.gather(*(one(key, donor, arm) for key, donor in zip(selected, donors) for arm in arms))
    for arm in arms:
        complete = {key for (key,) in db.execute("SELECT person FROM runs WHERE arm=? AND output IS NOT NULL", (arm,))}
        print(stage, arm, len(complete.intersection(selected)), "/", len(selected), flush=True)
    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["pilot", "formal"])
    asyncio.run(execute(parser.parse_args().stage))
