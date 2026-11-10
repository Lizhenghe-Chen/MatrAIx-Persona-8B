"""Forecast price mix, spend mix, and exact-item repeat purchases."""
import argparse
import asyncio
from bisect import bisect_right
from collections import Counter, defaultdict
import csv
import gzip
import json
import math
import sqlite3
import hashlib

import httpx
import numpy as np

from optimize import MODELS, request_for
from retail_amazon import START, END, RUN, SEED, SOURCE
from retail_pew import decode

PERIODS = [f"{y}Q{q}" for y in (2020, 2021, 2022) for q in (1, 2, 3, 4)]
PRICE_BANDS = ["under $15", "$15 to under $30", "$30 to under $60", "$60 to under $100", "$100 and above",
               "no usable priced purchases"]


def prepare():
    original = json.loads((RUN / "amazon-freeze.json").read_text())
    split, categories = original["split"], original["categories"]
    keep = set(sum(split.values(), []))
    taxonomy = set(categories)
    observations = defaultdict(lambda: defaultdict(list))
    with gzip.open(SOURCE, "rt", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            date = row["Order Date"]
            if not START <= date < END:
                continue
            key = hashlib.sha256(("amazon:" + row["Survey ResponseID"]).encode()).hexdigest()[:24]
            if key not in keep:
                continue
            q = f"{date[:4]}Q{(int(date[5:7])-1)//3+1}"
            category = row["Category"].strip() or "Unknown category"
            try:
                price, quantity = float(row["Purchase Price Per Unit"]), float(row["Quantity"])
                if not math.isfinite(price) or not math.isfinite(quantity) or price < 0 or quantity <= 0:
                    price, quantity = None, None
            except ValueError:
                price, quantity = None, None
            observations[key][q].append((category if category in taxonomy else "Other",
                                         price, quantity, row["ASIN/ISBN (Product Code)"].strip()))
    outcomes = {"price": PRICE_BANDS, "spend": [*categories, "no positive measured spend"],
                "repeat": ["no repeated product", "at least one repeated product"]}
    def summarize(key):
        history = {}
        already_seen = set()
        for q in PERIODS:
            rows = observations[key][q]
            price, spend = Counter(), Counter()
            for category, unit, quantity, _ in rows:
                if unit is not None:
                    price[PRICE_BANDS[bisect_right([15,30,60,100],unit)]] += 1
                    spend[category] += unit * quantity
            products = {code for _, _, _, code in rows if code}
            total_price, total_spend = sum(price.values()), sum(spend.values())
            repeat = int(bool(already_seen & products))
            history[q] = {
                "price": [price[x] / total_price if total_price else float(x == PRICE_BANDS[-1])
                          for x in PRICE_BANDS],
                "spend": [spend[x] / total_spend if total_spend else float(x == outcomes["spend"][-1])
                          for x in outcomes["spend"]],
                "repeat": [1-repeat, repeat],
            }
            already_seen.update(products)
        return history
    profiles = {key: summarize(key) for key in [*split["development"], *split["test"]]}
    prior_rows = [summarize(key)[q] for key in split["reference"] for q in ("2020Q4", "2021Q4")]
    priors = {k: np.mean([x[k] for x in prior_rows], axis=0).tolist() for k in outcomes}
    result = {"outcomes": outcomes, "split": {k:split[k] for k in ("development","test")}, "prior": priors,
              "records": {key: {"target": values[PERIODS[-1]], "history": {q: values[q] for q in PERIODS[:-1]}}
                          for key,values in profiles.items()}}
    return result


def baseline(record, prior, method):
    q = ["2021Q4","2022Q1","2022Q2","2022Q3"] if method == "recent" else ["2020Q4","2021Q4"]
    return {k: np.mean([*(record["history"][p][k] for p in q), prior[k]],axis=0).tolist()
            for k in prior}


async def model(stage, data):
    keys = data["split"][stage]
    db = sqlite3.connect(RUN / "amazon-mix.sqlite")
    db.execute("CREATE TABLE IF NOT EXISTS forecasts (person TEXT PRIMARY KEY, prediction TEXT, errors TEXT)")
    complete = {key for (key,) in db.execute("SELECT person FROM forecasts WHERE prediction IS NOT NULL")}
    semaphore = asyncio.Semaphore(8)
    async with httpx.AsyncClient(timeout=110, trust_env=False) as client:
        async def one(key):
            if key in complete:
                return
            row = data["records"][key]
            description = {"outcome_order":data["outcomes"],
                           "history_by_quarter": {q:{k:[round(v,4) for v in a] for k,a in values.items()}
                                                  for q,values in row["history"].items()}}
            instruction = ("Forecast 2022 Q4 for this US Amazon account. Return exactly three JSON arrays keyed "
                           "price, spend, repeat. Each array must sum to one and follow the listed category order. "
                           "Price predicts the shares of purchase lines by unit price band. Spend predicts shares "
                           "of dollars by category. The last category in price and spend includes quarters without "
                           "usable prices or positive spend, respectively. Repeat means at least one previously "
                           "purchased exact product ID reappears, not merely a category. Use history only.")
            url, headers, body = request_for({"human":True,"model":"qwen","system":instruction,
                                             "user":json.dumps(description)})
            mapping = {name:(name,list(range(len(labels)))) for name,labels in data["outcomes"].items()}
            output = None
            errors = []
            async with semaphore:
                for _ in range(3):
                    try:
                        response = await client.post(url,headers=headers,json=body)
                        response.raise_for_status()
                        obj=response.json()
                        choice=obj["choices"][0]
                        if obj["model"] != MODELS["qwen"] or choice["finish_reason"] != "stop" or choice["message"].get("reasoning_content"):
                            raise ValueError("protocol")
                        output=decode(choice["message"]["content"],mapping,True)
                        break
                    except (httpx.HTTPError,ValueError,KeyError,TypeError,IndexError) as error:
                        errors.append(str(error) if type(error) is ValueError else type(error).__name__)
                        await asyncio.sleep(1)
                db.execute("INSERT OR REPLACE INTO forecasts VALUES (?,?,?)",
                           (key,json.dumps(output) if output else None,json.dumps(errors)))
                db.commit()
        await asyncio.gather(*(one(key) for key in keys))
    db.close()


def score(stage,data):
    with sqlite3.connect(RUN / "amazon-mix.sqlite") as db:
        outputs={k:json.loads(x) for k,x in db.execute("SELECT person,prediction FROM forecasts WHERE prediction IS NOT NULL")}
    keys=[k for k in data["split"][stage] if k in outputs]
    if len(keys)/len(data["split"][stage]) < .98:
        raise ValueError("Amazon mix below 98% completion")
    sample=np.random.default_rng(SEED).integers(len(keys),size=(2000,len(keys)))
    records=[data["records"][k] for k in keys]
    methods={"recent":[baseline(r,data["prior"],"recent") for r in records],
             "seasonal":[baseline(r,data["prior"],"seasonal") for r in records],
             "model":[outputs[k] for k in keys]}
    tasks={}
    protocol_path = RUN.parent/"amazon-mix-protocol.json"
    protocol = {} if stage == "development" else json.loads(protocol_path.read_text())
    for task, labels in data["outcomes"].items():
        actual=np.array([r["target"][task] for r in records])
        task_scores={}
        squared={}
        for name, forecasts in methods.items():
            pred=np.array([r[task] for r in forecasts])
            squared[name]=((pred-actual)**2).sum(axis=1)
            task_scores[name]={"brier":float(squared[name].mean()),
                               "tv_pp":float(50*abs((pred-actual).mean(axis=0)).sum()),
                               "shares":pred.mean(axis=0).tolist()}
        if stage == "development":
            selected = min(("recent","seasonal"),key=lambda name: task_scores[name]["brier"])
            base = np.array([r[task] for r in methods[selected]])
            model = np.array([r[task] for r in methods["model"]])
            residual = model-base
            variance = np.sum(residual**2)
            weight = float(np.clip(np.sum((actual-base)*residual)/variance,0,1)) if variance else 0.
            protocol[task] = {"baseline": selected,"model_weight": weight}
        selected = protocol[task]["baseline"]
        weight = protocol[task]["model_weight"]
        base = np.array([r[task] for r in methods[selected]])
        model = np.array([r[task] for r in methods["model"]])
        mixed = base+(model-base)*weight
        squared["blend"] = ((mixed-actual)**2).sum(axis=1)
        task_scores["blend"] = {"brier":float(squared["blend"].mean()),
                                "tv_pp":float(50*abs((mixed-actual).mean(axis=0)).sum()),
                                "shares":mixed.mean(axis=0).tolist()}
        comparisons = {}
        for name in ("model","blend"):
            diff = squared[selected]-squared[name]
            comparisons[name] = {"gain":float(diff.mean()),
                                 "interval":np.quantile(diff[sample].mean(axis=1),[.025,.975]).tolist()}
        tasks[task]={"labels":labels,"actual":actual.mean(axis=0).tolist(),"results":task_scores,
                     "comparisons":comparisons,"baseline":selected,"model_weight":weight}
    if stage == "development":
        if protocol_path.exists() and json.loads(protocol_path.read_text()) != protocol:
            raise ValueError("Frozen Amazon mix protocol changed")
        protocol_path.write_text(json.dumps(protocol,indent=2)+"\n")
    out={"stage":stage,"accounts":len(keys),"requested":len(data["split"][stage]),"tasks":tasks}
    (RUN.parent / f"amazon-mix-{stage}-score.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print({k:v["comparisons"] for k,v in tasks.items()})


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["prepare","run","score"])
    parser.add_argument("stage",choices=["development","test"],nargs="?",default="development")
    args=parser.parse_args()
    path=RUN/"amazon-mix-freeze.json"
    if args.action=="prepare":
        fresh=prepare()
        if path.exists() and json.loads(path.read_text())!=fresh:
            raise ValueError("Amazon mix freeze changed")
        path.write_text(json.dumps(fresh,ensure_ascii=False))
        print({k:len(v) for k,v in fresh["split"].items()})
    else:
        data=json.loads(path.read_text())
        if args.action=="run":
            asyncio.run(model(args.stage,data))
        else:
            score(args.stage,data)
