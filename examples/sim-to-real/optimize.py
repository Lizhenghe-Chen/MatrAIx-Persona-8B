"""Paired model and respondent-profile comparisons for the frozen surveys."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

import httpx

from experiment import ROOT, SEED, STRATA, dump, profile_prompt, read_json, sha256, survey_instrument
from instruments import ITEMS

LOCAL = "http://10.120.47.101:8000/v1/chat/completions"
MODELS = {"flash": "deepseek-flash", "pro": "deepseek-v4-pro", "qwen": "Qwen/Qwen3.8-27B"}
PARAMS = {"temperature": 0.7, "top_p": 1, "max_tokens": 768,
          "response_format": {"type": "json_object"}}
FOLDERS = {"models": "02_模型对比", "profiles": "03_提示与背景"}
P1 = ("Predict the answer this specific respondent would most likely give at the stated survey date. "
      "Use the background supplied for this person when it is relevant. Do not invent personal "
      "experiences or infer an unstated background fact as certain. Answer each item independently "
      "using only its original options. Return only the requested JSON answer object.")


def configure_imports():
    for path in ("", "application/playground", "packages/playground/src", "src", "environment/agents"):
        sys.path.insert(0, str(ROOT / path))


def draw(rows, n, *key):
    rng = random.Random(f"{SEED}:{key}")
    return [row for stratum in STRATA for row in rng.sample(
        sorted((r for r in rows if r["stratum"] == stratum), key=lambda r: r["id"]), n
    )]


def source_manifest(study):
    data = study / "数据"
    archive = study / "01_首轮归档"
    sources = [data / f"{survey}.zip" for survey in ITEMS]
    sources += [archive / "cohort.json", archive / "reference.json"]
    paths = [Path(__file__), Path(__file__).with_name("instruments.py"),
             Path(__file__).with_name("experiment.py")]
    return {"inputs": {str(path.relative_to(study)): sha256(path) for path in sources},
            "source": {path.name: sha256(path) for path in paths}}


def task_text(survey, order_id):
    from playground.inprocess.survey_eval import build_survey_task_prompt

    instrument = survey_instrument(survey, order_id)
    return build_survey_task_prompt(instrument=instrument)


def model_jobs(study):
    source = read_json(study / "01_首轮归档" / "cohort.json")
    cohort = draw(source["formal"], 60, "model-comparison")
    jobs = []
    for survey in ITEMS:
        for row in cohort:
            question = task_text(survey, row["id"])
            for arm in "ABC":
                system = profile_prompt(survey, arm, row)
                for model in MODELS:
                    jobs.append({"survey": survey, "id": row["id"], "stratum": row["stratum"],
                                 "condition": f"{model}-{arm}", "model": model, "human": False,
                                 "system": system, "user": question})
    pilot = []
    for survey in ITEMS:
        row = source["pilot"][0]
        for model in MODELS:
            pilot.append({"survey": survey, "id": row["id"], "stratum": row["stratum"],
                          "condition": f"{model}-C", "model": model, "human": False,
                          "system": profile_prompt(survey, "C", row),
                          "user": task_text(survey, row["id"])})
    return jobs, pilot, {"cohort": cohort}


def request_for(job):
    model = job["model"]
    if job["human"] and model != "qwen":
        raise ValueError("Respondent-derived inputs are restricted to the local Qwen endpoint")
    if model == "qwen":
        endpoint, headers = LOCAL, {}
        thinking = {"chat_template_kwargs": {"enable_thinking": False}}
    else:
        endpoint = "https://api.deepseek.com/chat/completions"
        headers = {"Authorization": "Bearer " + os.environ["DEEPSEEK_API_KEY"]}
        thinking = {"thinking": {"type": "disabled"}}
    return endpoint, headers, {
        **PARAMS, **thinking, "model": MODELS[model],
        "messages": [{"role": "system", "content": job["system"]},
                     {"role": "user", "content": job["user"]}],
    }


def answers_for(data, survey):
    choice = data["choices"][0]
    msg = choice["message"]
    if choice["finish_reason"] != "stop" or msg.get("reasoning_content") or msg.get("reasoning"):
        raise ValueError("Unexpected finish reason or thinking output")
    rows = json.loads(msg["content"])["answers"]
    allowed = ITEMS[survey]
    answers = {str(row["questionId"]): str(row["value"]) for row in rows}
    if len(rows) != len(allowed) or set(answers) != set(allowed):
        raise ValueError("Missing, duplicate, or unexpected survey item")
    if any(code not in {str(key) for key in allowed[item][1]} for item, code in answers.items()):
        raise ValueError("Unexpected option")
    return answers


async def call(client, job, retries):
    url, headers, body = request_for(job)
    failures = []
    for attempt in range(retries + 1):
        start = time.monotonic()
        try:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
            if data.get("model") != MODELS[job["model"]]:
                raise ValueError("Unexpected returned model ID")
            answers = answers_for(data, job["survey"])
            return {"answers": answers, "failures": failures,
                    "elapsed": round(time.monotonic() - start, 3),
                    "returned_model": data["model"], "usage": data.get("usage"),
                    "request_id": data.get("id")}
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            failures.append({"type": type(exc).__name__, "status": status,
                             "detail": str(exc) if type(exc) is ValueError and str(exc).startswith(
                                 ("Unexpected", "Missing")) else None})
            if status in {400, 401, 402, 403, 404, 422}:
                break
            if attempt < retries:
                await asyncio.sleep(1 << attempt)
    return {"failures": failures}


def job_key(job):
    return f"{job['survey']}:{job['condition']}:{job['id']}"


async def execute(jobs, destination, stage, only):
    jobs = [j for j in jobs if not only or j["model"] == only]
    if not jobs:
        raise ValueError("No trials selected")
    db = sqlite3.connect(destination / "checkpoints.sqlite")
    with db:
        db.execute("CREATE TABLE IF NOT EXISTS trials (stage TEXT, key TEXT, ok INT, payload TEXT, PRIMARY KEY(stage,key))")
    saved = dict(db.execute("SELECT key, payload FROM trials WHERE stage=?", (stage,)))
    todo = [j for j in jobs if "answers" not in json.loads(saved.get(job_key(j), "{}"))]
    random.Random(SEED).shuffle(todo)
    semaphores = {key: asyncio.Semaphore(n) for key, n in {"flash": 56, "pro": 56, "qwen": 48}.items()}
    completed = 0
    print(f"{destination.name}/{stage}: {len(todo)} pending of {len(jobs)}", flush=True)
    async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10),
                                 limits=httpx.Limits(max_connections=180), trust_env=False) as client:
        async def one(job):
            async with semaphores[job["model"]]:
                result = await call(client, job, retries=0 if stage == "pilot" else 2)
            old = json.loads(saved.get(job_key(job), "{}"))
            result["failures"] = old.get("failures", []) + result["failures"]
            return job, result

        for future in asyncio.as_completed([one(job) for job in todo]):
            job, result = await future
            result.update({k: job[k] for k in ("survey", "id", "stratum", "condition", "model")})
            with db:
                db.execute("INSERT OR REPLACE INTO trials VALUES (?, ?, ?, ?)",
                           (stage, job_key(job), int("answers" in result), json.dumps(result)))
            completed += 1
            if completed % 200 == 0:
                print(f"{destination.name}/{stage}: {completed}/{len(todo)} processed", flush=True)
    cells = Counter((j["survey"], j["condition"]) for j in jobs)
    successful = {key for key, in db.execute("SELECT key FROM trials WHERE stage=? AND ok=1", (stage,))}
    counts = Counter((j["survey"], j["condition"]) for j in jobs if job_key(j) in successful)
    summary = {"/".join(k): [counts[k], n] for k, n in sorted(cells.items())}
    dump(destination / f"{stage}-completion{('-' + only) if only else ''}.json", summary)
    db.close()
    if any(ok / total < (1 if stage == "pilot" else 0.98) for ok, total in summary.values()):
        raise SystemExit(f"{stage}: insufficient successful replies; inspect the completion summary and checkpoints")
    print(f"{stage}: {sum(counts.values())}/{len(jobs)} valid", flush=True)


def main():
    configure_imports()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", choices=FOLDERS)
    parser.add_argument("action", choices=("pilot", "formal", "score"))
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--only-model", choices=MODELS)
    args = parser.parse_args()
    destination = args.study / FOLDERS[args.experiment]
    if args.experiment == "models":
        jobs, pilot, data = model_jobs(args.study)
    else:
        from optimize_profiles import profile_jobs
        jobs, pilot, data = profile_jobs(args.study)
    manifest = {
        **source_manifest(args.study), "seed": SEED, "models": MODELS, "params": PARAMS,
        "thinking": False, "local_url": LOCAL, "count": len(jobs), "pilot": len(pilot),
        "plan_hash": hashlib.sha256(json.dumps([jobs, pilot, data], sort_keys=True).encode()).hexdigest(),
    }
    path = destination / "manifest.json"
    if path.exists() and read_json(path) != manifest:
        raise ValueError("Experiment inputs changed. Use a fresh run directory.")
    dump(path, manifest)
    if args.action == "score":
        from optimize_score import score
        score(args.experiment, args.study, destination, jobs, data)
        return
    if args.action == "formal":
        with sqlite3.connect(destination / "checkpoints.sqlite") as db:
            ok = {key for key, in db.execute("SELECT key FROM trials WHERE stage='pilot' AND ok=1")}
        if any(job_key(j) not in ok for j in pilot if not args.only_model or j["model"] == args.only_model):
            raise ValueError("All relevant technical pilot trials must pass before formal execution")
    asyncio.run(execute(pilot if args.action == "pilot" else jobs, destination, args.action, args.only_model))


if __name__ == "__main__":
    main()
