"""Evaluate purchase likelihood while preserving paired shoe stimuli."""
import argparse
import asyncio
import hashlib
import json
import sqlite3

import httpx

from optimize import MODELS, P1, request_for
from retail_amazon import RUN
from retail_pew import decode

OPTIONS = ["Very Unlikely", "Unlikely", "Somewhat Unlikely", "Neither Likely Nor Unlikely",
           "Somewhat Likely", "Likely", "Very Likely"]
ARMS = {"basic_choice": (2, False), "rich_choice": (4, False), "basic_probability": (2, True),
        "rich_probability": (4, True), "attitude_probability": (6, True)}


def build_request(record, arm):
    fields, probability = ARMS[arm]
    background = list(record["background"].items())[:fields]
    system = "United States, December 2018. " + P1 + "\n" + "\n".join(f"{k}: {v}" for k, v in background)
    lines = ["For each pair, imagine that you were shopping online for a new pair of athletic shoes "
             "and saw the following two descriptions for a pair of shoes.",
             "Ratings: " + " | ".join(f"{i}. {x}" for i, x in enumerate(OPTIONS, 1))]
    mapping = {}
    for pair in record["pairs"]:
        lines.append("Attribute | Shoe 1 | Shoe 2")
        lines.extend(" | ".join(row) for row in zip(pair["attributes"], *pair["shoes"], strict=True))
        for shoe in (1, 2):
            key = str(len(mapping) + 1)
            lines.append(f"{key}. How likely are you to purchase shoe {shoe}?")
            mapping[key] = (f"{pair['task']}.{shoe}", list(range(7)))
    instruction = (
        'Return a JSON object. For each question number return seven probabilities in rating order, summing to 1. '
        'Example {"1":[0.05,0.10,0.10,0.20,0.25,0.20,0.10]}.'
        if probability else 'Return a JSON object mapping each question number to one rating from 1 through 7. Example {"1":4}.'
    )
    url, headers, body = request_for({"human": True, "model": "qwen", "system": system,
                                      "user": instruction + "\n" + "\n".join(lines)})
    # Sixteen seven-value distributions may exceed the previous 768-token cap.
    body["max_tokens"] = 1536
    return url, headers, body, mapping


async def execute(stage):
    frozen = RUN / "shoes-freeze.json"
    data = json.loads(frozen.read_text())
    keys = data["split"][stage]
    protocol = {"cohort_sha256": hashlib.sha256(frozen.read_bytes()).hexdigest(),
                "runner_sha256": hashlib.sha256(open(__file__, "rb").read()).hexdigest(),
                "decoder_sha256": hashlib.sha256((RUN.parent.parent.parent / "retail_pew.py").read_bytes()).hexdigest(),
                "arms": {k: list(v) for k, v in ARMS.items()}}
    freeze = RUN / "shoes-model-protocol.json"
    if freeze.exists() and json.loads(freeze.read_text()) != protocol:
        raise ValueError("Shoe model protocol changed")
    freeze.write_text(json.dumps(protocol, indent=2))
    db = sqlite3.connect(RUN / "shoes.sqlite")
    db.execute("CREATE TABLE IF NOT EXISTS forecasts (person TEXT, arm TEXT, output TEXT, failures TEXT, PRIMARY KEY(person,arm))")
    done = set(db.execute("SELECT person,arm FROM forecasts WHERE output IS NOT NULL"))
    semaphore = asyncio.Semaphore(8)
    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        async def one(key, arm):
            if (key, arm) in done:
                return
            url, headers, body, mapping = build_request(data["records"][key], arm)
            output = None
            failures = []
            async with semaphore:
                for attempt in range(3):
                    try:
                        response = await client.post(url, json=body, headers=headers)
                        response.raise_for_status()
                        obj = response.json()
                        choice = obj["choices"][0]
                        if obj["model"] != MODELS["qwen"] or choice["finish_reason"] != "stop" or choice["message"].get("reasoning_content"):
                            raise ValueError("unexpected model protocol")
                        output = decode(choice["message"]["content"], mapping, ARMS[arm][1])
                        break
                    except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as error:
                        failures.append(type(error).__name__ + (": " + str(error) if type(error) is ValueError else ""))
                        await asyncio.sleep(attempt + 1)
                db.execute("INSERT OR REPLACE INTO forecasts VALUES (?,?,?,?)",
                           (key, arm, json.dumps(output) if output else None, json.dumps(failures)))
                db.commit()
        await asyncio.gather(*(one(key, arm) for key in keys for arm in ARMS))
    rows = db.execute("SELECT person,arm,output FROM forecasts").fetchall()
    for arm in ARMS:
        print(stage, arm, sum(key in keys and a == arm and out is not None for key, a, out in rows),
              "/", len(keys), flush=True)
    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["development","test"])
    asyncio.run(execute(parser.parse_args().stage))
