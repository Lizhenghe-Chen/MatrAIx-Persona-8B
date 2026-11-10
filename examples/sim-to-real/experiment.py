"""Prepare, run and score the preregistered MatrAIx survey comparison."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from data_sources import data_root, survey_source
from instruments import DATES, ITEMS, PEW_INTRO

ROOT = Path(__file__).resolve().parents[2]
SEED = 20261109
AGES = ("18–64", "65+")
PER_STRATUM = 300
EDUCATION = ("Below bachelor's degree", "Bachelor's degree or higher")
STRATA = tuple(f"{age}|{education}" for age in AGES for education in EDUCATION)
TRAITS = {
    "decision_style": "Decision style",
    "risk_tolerance": "Risk tolerance",
    "values_priority": "Core value",
    "bfi2_domain_conscientiousness": "Conscientiousness",
}
AGE_MAP = {
    "18-24": 0,
    "25-34": 0,
    "35-44": 0,
    "45-54": 0,
    "55-64": 0,
    "65-74": 1,
    "75-84": 1,
    "85+": 1,
}
EDUCATION_MAP = {
    "No formal": 0,
    "Primary": 0,
    "Secondary": 0,
    "Vocational / cert": 0,
    "Some college": 0,
    "Associate's": 0,
    "Bachelor's": 1,
    "Master's": 1,
    "Doctorate": 1,
    "Postdoc": 1,
}
ARMS = "ABC"
SHED_EDUCATION = {
    "No high school diploma or GED": 1,
    "High school graduate (high school diploma or the equivalent GED)": 2,
    "Some college or Associate's degree": 3,
    "Bachelor's degree or higher": 4,
}


def dump(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stable_seed(*parts):
    return int.from_bytes(hashlib.sha256(repr(parts).encode()).digest()[:8], "big")


def read_table(path):
    with ZipFile(path) as archive:
        candidates = [
            name
            for name in archive.namelist()
            if not name.startswith("__MACOSX/") and name.lower().endswith(".csv")
        ]
        if len(candidates) != 1:
            raise ValueError(f"{path}: expected exactly one CSV")
        with archive.open(candidates[0]) as stream:
            return list(csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig")))


def numeric(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return math.nan


def age_band(value):
    age = numeric(value)
    if not age.is_integer() or not 18 <= age <= 120:
        return None
    return AGES[age >= 65]


def column(header, name, wave=None):
    candidates = [name] + ([f"{name}_W{wave}"] if wave else [])
    for candidate in candidates:
        if candidate.lower() in header:
            return header[candidate.lower()]
    raise ValueError(f"Missing column {name}")


def human_reference(survey, path):
    rows = read_table(path)
    if not rows:
        raise ValueError(f"{path}: empty survey")
    header = {name.lower(): name for name in rows[0]}
    if survey == "shed":
        age, education, weight, college = "ppage", "ppeducat", "weight", 4
        education_values = range(1, 5)
    elif survey == "anes":
        age, education, weight, college = "V241458x", "V241465x", "V240102a", 4
        education_values = range(1, 6)
    else:
        age, education, weight, college = "F_AGECAT", "F_EDUCCAT2", "WEIGHT", 5
        education_values = range(1, 7)
    wave = 168 if survey == "pew" else None
    age, education, weight = (
        column(header, field, wave) for field in (age, education, weight)
    )
    item_columns = {item: column(header, item, wave) for item in ITEMS[survey]}
    flags = (
        {item: column(header, f"{item}_iflag") for item in item_columns}
        if survey == "shed"
        else {}
    )
    masses = Counter()
    counts = Counter()
    valid = defaultdict(Counter)
    weighted = defaultdict(Counter)
    eligible = 0
    for row in rows:
        w = numeric(row[weight])
        if not math.isfinite(w) or w <= 0:
            continue
        eligible += 1
        if survey == "pew":
            age_code = numeric(row[age])
            age_group = AGES[age_code == 4] if age_code in (1, 2, 3, 4) else None
        else:
            age_group = age_band(row[age])
        edu = (
            SHED_EDUCATION.get(row[education])
            if survey == "shed"
            else numeric(row[education])
        )
        if age_group is None or edu not in education_values:
            continue
        stratum = f"{age_group}|{EDUCATION[edu >= college]}"
        masses[stratum] += w
        counts[stratum] += 1
        for item, field in item_columns.items():
            value = (
                {"Yes": 1, "No": 0}.get(row[field])
                if survey == "shed"
                else numeric(row[field])
            )
            if value not in ITEMS[survey][item][1] or (
                item in flags and numeric(row[flags[item]]) != 0
            ):
                continue
            valid[item][stratum] += 1
            weighted[item, stratum][int(value)] += w
    missing = [stratum for stratum in STRATA if not counts[stratum]]
    if missing:
        raise ValueError(f"{survey}: no eligible records in strata {missing}")
    items = {}
    for item, (_, options) in ITEMS[survey].items():
        by_stratum = {}
        for stratum in STRATA:
            answers = weighted[item, stratum]
            if not answers:
                raise ValueError(f"{survey}/{item}: no valid responses in {stratum}")
            by_stratum[stratum] = {
                "valid": valid[item][stratum],
                "weight": sum(answers.values()),
                "distribution": {
                    str(code): answers[code] / sum(answers.values()) for code in options
                },
            }
        items[item] = by_stratum
    return {
        "sha256": sha256(path),
        "input_rows": len(rows),
        "positive_weight_rows": eligible,
        "matched_rows": sum(counts.values()),
        "stratum_count": dict(counts),
        "stratum_weight": {key: masses[key] / sum(masses.values()) for key in STRATA},
        "columns": {
            "age": age,
            "education": education,
            "weight": weight,
            "items": item_columns,
            "imputation_flags": flags,
        },
        "items": items,
    }


def sample_cohort(release, output):
    import pyarrow.parquet as pq
    from backend.service.persona_1m_pool import _decode_batch_rows, load_codec

    manifest = release / "manifest.json"
    schema = release / "persona_codes.schema.json"
    paths = sorted((release / "data").glob("persona-1m-*.parquet"))
    if len(paths) != 10 or not manifest.is_file():
        raise ValueError(
            "Expected the complete official ten-shard release and manifest"
        )
    codec = load_codec(schema)
    pools = defaultdict(list)
    seen = set()
    files = {manifest.name: sha256(manifest), schema.name: sha256(schema)}
    expected_hashes = {
        entry["path"]: entry["sha256"] for entry in read_json(manifest)["files"]
    }
    total = 0
    for path in paths:
        relative = str(path.relative_to(release))
        digest = sha256(path)
        if expected_hashes.get(relative) != digest:
            raise ValueError(f"Manifest hash mismatch: {relative}")
        files[relative] = digest
        reader = pq.ParquetFile(path)
        total += reader.metadata.num_rows
        for batch in reader.iter_batches(
            batch_size=8192,
            columns=[
                "source",
                "source_row_index",
                "attributes",
                "null_bitmap",
                "attribute_overrides",
            ],
        ):
            sources = batch.column("source").to_pylist()
            indices = [i for i, source in enumerate(sources) if source == "synthetic"]
            if not indices:
                continue
            for row in _decode_batch_rows(batch.take(indices), codec):
                fields = row["dimensions"]
                age = AGE_MAP.get(fields.get("age_bracket"))
                education = EDUCATION_MAP.get(fields.get("highest_education"))
                if (
                    fields.get("region") != "North America"
                    or age is None
                    or education is None
                ):
                    continue
                pid = row["persona_id"]
                if pid in seen:
                    raise ValueError(f"Duplicate persona ID {pid}")
                seen.add(pid)
                stratum = f"{AGES[age]}|{EDUCATION[education]}"
                pools[stratum].append(
                    {
                        "id": pid,
                        "stratum": stratum,
                        "traits": {key: fields.get(key) for key in TRAITS},
                    }
                )
    if total != 999847:
        raise ValueError(f"Expected 999847 official records, found {total}")
    write_cohort(
        output, pools, {"source": "persona-1m", "files": files}, "coverage.json"
    )


def write_cohort(output, pools, provenance, coverage_name):
    coverage = {key: len(pools[key]) for key in STRATA}
    dump(output / coverage_name, coverage)
    if min(coverage.values()) < PER_STRATUM + 3:
        raise ValueError(
            f"Need {PER_STRATUM} formal and 3 distinct pilot personas per stratum: {coverage}"
        )
    rng = random.Random(SEED)
    selected = []
    pilot = []
    for key in STRATA:
        entries = sorted(pools[key], key=lambda row: row["id"])
        draw = rng.sample(entries, PER_STRATUM + 3)
        selected.extend(draw[:PER_STRATUM])
        pilot.extend(draw[PER_STRATUM:])
    dump(
        output / "cohort.json",
        {
            "seed": SEED,
            **provenance,
            "formal": selected,
            "pilot": pilot,
        },
    )


def sample_dag(output):
    from persona.synthesis.sampler import (
        DEFAULT_GRAPH_PATH,
        PersonaForwardSampler,
        SamplingConfig,
    )

    pins = {"region": "North America"}
    candidates = 50_000
    sampler = PersonaForwardSampler(DEFAULT_GRAPH_PATH, SamplingConfig(seed=SEED))
    if not sampler.assignment_supported(pins):
        raise ValueError(f"DAG does not support {pins}")
    codes = sampler.sample_indices(candidates, fixed=pins)
    pools = defaultdict(list)
    for index, (age_code, education_code) in enumerate(
        zip(
            codes["age_bracket"],
            codes["highest_education"],
            strict=True,
        )
    ):
        age = AGE_MAP.get(sampler.values["age_bracket"][age_code])
        education = EDUCATION_MAP.get(
            sampler.values["highest_education"][education_code]
        )
        if age is None or education is None:
            continue
        stratum = f"{AGES[age]}|{EDUCATION[education]}"
        pools[stratum].append(
            {
                "id": f"dag-{SEED}-{index:05d}",
                "stratum": stratum,
                "traits": {
                    key: sampler.values[key][codes[key][index]] for key in TRAITS
                },
            }
        )
    write_cohort(
        output,
        pools,
        {
            "source": "native-dag-pinned-region",
            "graph_sha256": sha256(DEFAULT_GRAPH_PATH),
            "pins": pins,
            "candidates": candidates,
        },
        "dag-coverage.json",
    )


def survey_instrument(survey, pid):
    from backend.service.survey_types import SurveyInstrument

    items = list(ITEMS[survey])
    rng = random.Random(stable_seed(SEED, survey, pid))
    start = {"shed": len(items), "pew": 1, "anes": 0}[survey]
    tail = items[start:]
    rng.shuffle(tail)
    return SurveyInstrument.from_dict(
        {
            "id": f"sim-to-real-{survey}",
            "title": "Questionnaire",
            "description": PEW_INTRO if survey == "pew" else "",
            "questions": [
                {
                    "id": item,
                    "type": "single_choice",
                    "prompt": ITEMS[survey][item][0],
                    "options": [
                        {"id": str(code), "label": label}
                        for code, label in ITEMS[survey][item][1].items()
                    ],
                }
                for item in items[:start] + tail
            ],
        }
    )


def profile_prompt(survey, arm, row):
    prompt = f"Answer as an adult living in the United States during {DATES[survey]}."
    if arm != "A":
        age, education = row["stratum"].split("|")
        prompt += f"\nAge group: {age}\nEducation: {education}"
    if arm == "C":
        for key, label in TRAITS.items():
            value = row["traits"][key]
            if value is not None:
                prompt += f"\n{label}: {value}"
    return prompt


def run_one(job, model, client_factory):
    from backend.service.survey_types import SurveyEvalConfig
    from playground.inprocess.survey_eval import InprocessSurveyEvalRunner
    from playground.types import Persona

    survey, arm, row = job
    identity = {"survey": survey, "arm": arm, "id": row["id"]}
    instrument = survey_instrument(survey, row["id"])
    expected = {question.id: set(question.options) for question in instrument.questions}
    errors = []
    for _ in range(2):
        try:
            result = InprocessSurveyEvalRunner()(
                Persona(
                    id="respondent",
                    name="Respondent",
                    context=profile_prompt(survey, arm, row),
                ),
                instrument,
                config=SurveyEvalConfig(persona_model=model),
                created_at=datetime.now(timezone.utc).isoformat(),
                persona_yaml_path="",
                client_factory=client_factory,
            )
            answers = {
                answer.question_id: str(answer.value) for answer in result.answers
            }
            if (
                len(result.answers) != len(expected)
                or answers.keys() != expected.keys()
                or any(value not in expected[item] for item, value in answers.items())
            ):
                raise ValueError("Incomplete or invalid answers")
            return {
                **identity,
                "answers": answers,
                "errors": errors,
                "usage": result.usage,
            }
        except Exception as error:
            errors.append(
                {
                    "type": type(error).__name__,
                    "status": getattr(error, "status_code", None),
                }
            )
    return {**identity, "errors": errors}


def read_json(path):
    return json.loads(path.read_text())


def read_trials(folder):
    return [read_json(path) for path in sorted(folder.glob("trial-*.json"))]


def run_experiment(output, phase, model, workers):
    from playground.model_client import build_json_client

    cohort = read_json(output / "cohort.json")
    reference_path = output / "reference.json"
    if set(read_json(reference_path)) != set(ITEMS):
        raise ValueError("All three verified human datasets are required")
    run_info = {
        "model": model,
        "temperature": 0.7,
        "cohort": sha256(output / "cohort.json"),
        "reference": sha256(reference_path),
        "cohort_source": cohort["source"],
        "instruments": sha256(Path(__file__).with_name("instruments.py")),
        "runner": sha256(Path(__file__)),
        "seed": SEED,
    }
    if phase == "formal":
        pilot = read_trials(output / "pilot")
        expected = len(cohort["pilot"]) * len(ITEMS) * len(ARMS)
        if len(pilot) != expected or not all("answers" in row for row in pilot):
            raise ValueError(
                "Complete the technical pilot before running the formal survey"
            )
        if read_json(output / "pilot" / "run.json") != run_info:
            raise ValueError(
                "The pilot and formal run must use identical inputs and model"
            )

    client = build_json_client(model, temperature=0.7)

    def factory(_):
        return client

    folder = output / phase
    folder.mkdir(exist_ok=True)
    run_file = folder / "run.json"
    if run_file.exists() and read_json(run_file) != run_info:
        raise ValueError("Run inputs changed; use a new work directory")
    dump(run_file, run_info)
    jobs = [
        (survey, arm, row) for survey in ITEMS for arm in ARMS for row in cohort[phase]
    ]
    random.Random(SEED).shuffle(jobs)
    pending = []
    for job in jobs:
        survey, arm, row = job
        path = folder / f"trial-{survey}-{arm}-{row['id']}.json"
        if not path.exists() or "answers" not in read_json(path):
            pending.append((path, job))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(run_one, job, model, factory): path for path, job in pending
        }
        for index, future in enumerate(as_completed(futures), 1):
            path = futures[future]
            result = future.result()
            if path.exists():
                result["errors"] = read_json(path)["errors"] + result["errors"]
            dump(path, result)
            if index % 100 == 0:
                print(
                    f"{phase}: {index}/{len(pending)} pending trials processed",
                    flush=True,
                )
    complete = Counter(
        (row["survey"], row["arm"]) for row in read_trials(folder) if "answers" in row
    )
    status = {survey: {arm: complete[survey, arm] for arm in ARMS} for survey in ITEMS}
    dump(folder / "completion.json", status)
    print(json.dumps(status))
    minimum = (
        len(cohort[phase]) if phase == "pilot" else math.ceil(0.98 * len(cohort[phase]))
    )
    if any(n < minimum for survey in status.values() for n in survey.values()):
        raise ValueError(
            f"{phase}: completion below threshold {minimum}; rerun to retry failed trials"
        )


def score(output):
    import numpy as np

    reference = read_json(output / "reference.json")
    cohort = read_json(output / "cohort.json")["formal"]
    run_info = read_json(output / "formal" / "run.json")
    if run_info["cohort"] != sha256(output / "cohort.json") or run_info[
        "reference"
    ] != sha256(output / "reference.json"):
        raise ValueError("Formal run provenance does not match scoring inputs")
    trials = {
        (row["survey"], row["arm"], row["id"]): row["answers"]
        for row in read_trials(output / "formal")
        if "answers" in row
    }
    completion = {
        survey: {
            arm: sum((survey, arm, row["id"]) in trials for row in cohort)
            for arm in ARMS
        }
        for survey in ITEMS
    }
    if min(n for counts in completion.values() for n in counts.values()) < math.ceil(
        0.98 * len(cohort)
    ):
        raise ValueError("A formal arm is below 98% completion")
    paired = defaultdict(list)
    for row in cohort:
        if all((survey, arm, row["id"]) in trials for survey in ITEMS for arm in "BC"):
            paired[row["stratum"]].append(row["id"])
    if any(not paired[key] for key in STRATA):
        raise ValueError("Paired comparison is missing a stratum")
    rng = np.random.default_rng(SEED)
    draws = {
        key: rng.multinomial(
            len(paired[key]), np.full(len(paired[key]), 1 / len(paired[key])), size=2000
        )
        / len(paired[key])
        for key in STRATA
    }
    groups = {"overall": STRATA}
    for field, labels in enumerate((AGES, EDUCATION)):
        groups.update(
            {
                label: tuple(key for key in STRATA if key.split("|")[field] == label)
                for label in labels
            }
        )
    summaries = {}
    bootstrap = []
    details = []
    for survey, questions in ITEMS.items():
        baseline = reference[survey]
        mix = baseline["stratum_weight"]
        group_scores = defaultdict(list)
        item_draws = []
        for item, (_, options) in questions.items():
            codes = list(map(str, options))
            reference_item = baseline["items"][item]
            observed = np.array(
                [
                    [reference_item[key]["distribution"][code] for code in codes]
                    for key in STRATA
                ]
            )
            human_mass = np.array([reference_item[key]["weight"] for key in STRATA])
            by_arm = {}
            for arm in "BC":
                matrices = {
                    key: np.array(
                        [
                            [trials[survey, arm, pid][item] == code for code in codes]
                            for pid in paired[key]
                        ],
                        dtype=float,
                    )
                    for key in STRATA
                }
                by_arm[arm] = (
                    np.array([matrices[key].mean(axis=0) for key in STRATA]),
                    np.stack([draws[key] @ matrices[key] for key in STRATA], axis=1),
                )
            a_counts = Counter(
                trials[survey, "A", row["id"]][item]
                for row in cohort
                if (survey, "A", row["id"]) in trials
            )
            a = np.array([a_counts[code] / sum(a_counts.values()) for code in codes])
            for group, keys in groups.items():
                idx = [STRATA.index(key) for key in keys]
                w = np.array([mix[key] for key in keys])
                w /= w.sum()
                human = np.average(observed[idx], axis=0, weights=human_mass[idx])
                estimates = {
                    arm: w @ values[idx] for arm, (values, _) in by_arm.items()
                }
                if group == "overall":
                    estimates["A"] = a
                    b, c = (w @ by_arm[arm][1] for arm in "BC")
                    item_draws.append(
                        50
                        * (
                            np.abs(b - human).sum(axis=1)
                            - np.abs(c - human).sum(axis=1)
                        )
                    )
                errors = {
                    arm: float(50 * np.abs(values - human).sum())
                    for arm, values in estimates.items()
                }
                group_scores[group].append(errors)
                details.append(
                    {
                        "survey": survey,
                        "item": item,
                        "group": group,
                        "valid_human": sum(
                            reference_item[key]["valid"] for key in keys
                        ),
                        "human": dict(zip(codes, human.tolist())),
                        "simulated": {
                            arm: dict(zip(codes, values.tolist()))
                            for arm, values in estimates.items()
                        },
                        "error_pp": errors,
                    }
                )
        sample = np.mean(item_draws, axis=0)
        bootstrap.append(sample)
        summaries[survey] = {
            "groups": {
                group: {
                    arm: sum(row[arm] for row in rows) / len(rows) for arm in rows[0]
                }
                for group, rows in group_scores.items()
            },
            "gain_ci95_pp": np.quantile(sample, [0.025, 0.975]).tolist(),
        }
        overall = summaries[survey]["groups"]["overall"]
        summaries[survey]["gain_pp"] = overall["B"] - overall["C"]
    interval = np.quantile(np.mean(bootstrap, axis=0), [0.025, 0.975]).tolist()
    survey_intervals = [result["gain_ci95_pp"] for result in summaries.values()]
    report = {
        "run": run_info,
        "completion": completion,
        "paired_by_stratum": {key: len(paired[key]) for key in STRATA},
        "surveys": summaries,
        "combined_gain_pp": sum(s["gain_pp"] for s in summaries.values()) / len(ITEMS),
        "combined_ci95_pp": interval,
        "cross_domain_gain": sum(lo > 0 for lo, _ in survey_intervals) >= 2
        and all(hi >= 0 for _, hi in survey_intervals),
        "items": details,
    }
    dump(output / "results.json", report)
    lines = [
        "# MatrAIx 真人问卷对照结果",
        "",
        f"模型 {run_info['model']}。误差和增益单位为百分点。",
        "",
        "| 调查 | A 误差 | B 误差 | C 误差 | B − C | 95% 区间 |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for survey, result in summaries.items():
        overall = result["groups"]["overall"]
        lo, hi = result["gain_ci95_pp"]
        lines.append(
            f"| {survey} | {overall['A']:.2f} | {overall['B']:.2f} | {overall['C']:.2f} | "
            f"{result['gain_pp']:.2f} | [{lo:.2f}, {hi:.2f}] |"
        )
    lines.extend(
        [
            "",
            f"三份等权平均增益 **{report['combined_gain_pp']:.2f}**，95% 区间 "
            f"[{interval[0]:.2f}, {interval[1]:.2f}]。",
            "",
            f"跨题材增益 **{'达到预设标准' if report['cross_domain_gain'] else '未达到预设标准'}**。",
            "",
            "区间仅反映模拟样本波动。详细分群、逐题分布及有效人数见 results.json。",
            "这是公开问卷回测，底层模型可能曾见过题目或公开统计。",
        ]
    )
    (output / "report.md").write_text("\n".join(lines) + "\n")


def main():
    for path in (
        "",
        "application/playground",
        "packages/playground/src",
        "src",
        "environment/agents",
    ):
        sys.path.insert(0, str(ROOT / path))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("reference")
    sample = commands.add_parser("sample")
    sample.add_argument("--release", type=Path)
    commands.add_parser("sample-dag")
    for phase in ("pilot", "formal"):
        run = commands.add_parser(phase)
        run.add_argument("--model", required=True)
        run.add_argument("--workers", type=int, default=8)
    commands.add_parser("score")
    args = parser.parse_args()
    output = args.work_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    try:
        if args.command == "reference":
            summaries = {
                name: human_reference(name, survey_source(name))
                for name in ITEMS
            }
            dump(output / "reference.json", summaries)
            print(
                json.dumps(
                    {
                        name: {
                            key: summary[key]
                            for key in (
                                "input_rows",
                                "positive_weight_rows",
                                "matched_rows",
                                "stratum_count",
                            )
                        }
                        for name, summary in summaries.items()
                    },
                    ensure_ascii=False,
                )
            )
        elif args.command == "sample":
            release = args.release or data_root() / "09_MatrAIx画像/Persona-1M发行版"
            sample_cohort(release, output)
        elif args.command == "sample-dag":
            sample_dag(output)
        elif args.command in ("pilot", "formal"):
            run_experiment(output, args.command, args.model, args.workers)
        else:
            score(output)
    except (FileNotFoundError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
