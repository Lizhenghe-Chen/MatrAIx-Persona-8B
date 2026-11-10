"""Pilot two representations of the same past purchase history on local Qwen."""
import argparse
import asyncio
import json
import math
import sqlite3

import httpx

from optimize import MODELS, request_for
from retail_amazon import RUN, probabilities


async def run(stage):
    data = json.loads((RUN / "amazon-freeze.json").read_text())
    categories = data["categories"]
    keys = data["split"][stage]
    db = sqlite3.connect(RUN / "amazon.sqlite")
    db.execute("CREATE TABLE IF NOT EXISTS forecasts (person TEXT, arm TEXT, prediction TEXT, errors TEXT, PRIMARY KEY(person,arm))")
    done = set(db.execute("SELECT person,arm FROM forecasts WHERE prediction IS NOT NULL"))
    limit = asyncio.Semaphore(8)
    async with httpx.AsyncClient(timeout=100, trust_env=False) as client:
        async def one(key, arm):
            if (key, arm) in done:
                return
            row = data["records"][key]
            evidence = {"historical_purchase_line_counts": row["quarters"]}
            if arm == "historical_anchor":
                evidence["recent_frequency_estimate"] = probabilities(row, categories, data["priors"], "recent")
            job = {"human": True, "model": "qwen",
                   "system": ("Forecast purchases for one US Amazon account in October–December 2022. "
                              "Use only the supplied earlier history. For each listed category estimate the "
                              "probability of at least one purchase in that category. These are separate "
                              "events, so the probabilities do not need to sum to one."),
                   "user": "Return a JSON object with exactly these category keys and numeric values from 0 to 1.\n"
                           + json.dumps(categories) + "\n" + json.dumps(evidence)}
            url, headers, body = request_for(job)
            errors = []
            prediction = None
            async with limit:
                for attempt in range(3):
                    try:
                        response = await client.post(url, headers=headers, json=body)
                        response.raise_for_status()
                        obj = response.json()
                        choice = obj["choices"][0]
                        if obj["model"] != MODELS["qwen"] or choice["finish_reason"] != "stop" or choice["message"].get("reasoning_content"):
                            raise ValueError("protocol")
                        values = json.loads(choice["message"]["content"])
                        if set(values) != set(categories) or any(
                            type(v) not in (int,float) or not math.isfinite(v) or not 0 <= v <= 1 for v in values.values()
                        ):
                            raise ValueError("invalid prediction")
                        prediction = values
                        break
                    except (httpx.HTTPError, KeyError, ValueError, TypeError, IndexError) as error:
                        errors.append(type(error).__name__)
                        await asyncio.sleep(attempt + 1)
                db.execute("INSERT OR REPLACE INTO forecasts VALUES (?,?,?,?)",
                           (key, arm, json.dumps(prediction) if prediction else None, json.dumps(errors)))
                db.commit()
        await asyncio.gather(*(one(key, arm) for key in keys for arm in ("history_only","historical_anchor")))
    print(db.execute("SELECT arm,count(*),count(prediction) FROM forecasts GROUP BY arm").fetchall())
    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["development", "test"])
    asyncio.run(run(parser.parse_args().stage))
