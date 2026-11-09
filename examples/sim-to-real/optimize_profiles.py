"""Build allowlisted respondent profiles and keep ground truth on the scoring side."""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict

from experiment import AGES, DATES, EDUCATION, SHED_EDUCATION, STRATA, TRAITS, age_band, column, numeric
from experiment import read_json, read_table
from instruments import ITEMS
from optimize import P1, draw, task_text

YES_NO = {1: "Yes", 2: "No"}
PEW_AGE = dict(enumerate(("18–29", "30–49", "50–64", "65 or older"), 1))
PEW_EDU = dict(enumerate(("Less than high school", "High school graduate", "Some college, no degree",
                          "Associate degree", "Bachelor's degree", "Postgraduate degree"), 1))
ANES_EDU = dict(enumerate(("Less than high school", "High school graduate", "Some post-secondary education",
                           "Bachelor's degree", "Graduate degree"), 1))
PEW_NET = dict(enumerate(("Almost constantly", "Several times a day", "About once a day",
                          "Several times a week", "Less often", "Does not use the internet"), 1))
PARTY = dict(enumerate(("Strong Democrat", "Weak Democrat", "Independent leaning Democrat",
                        "Independent", "Independent leaning Republican", "Weak Republican",
                        "Strong Republican"), 1))
IDEOLOGY = dict(enumerate(("Extremely liberal", "Liberal", "Slightly liberal", "Moderate",
                           "Slightly conservative", "Conservative", "Extremely conservative"), 1))
INCOME = {code: label for bounds, label in (
    (range(1, 11), "Under $30,000"), (range(11, 15), "$30,000–49,999"),
    (range(15, 23), "$50,000–99,999"), (range(23, 27), "$100,000–174,999"),
    (range(27, 29), "$175,000 or more"),
) for code in bounds}
DEMOGRAPHICS = {
    "shed": ("shedid", "ppage", "ppeducat", "weight", 4),
    "pew": ("QKEY", "F_AGECAT", "F_EDUCCAT2", "WEIGHT", 5),
    "anes": ("V240001", "V241458x", "V241465x", "V240102a", 4),
}
EXTRA = {
    "shed": {"Household income": ("ppinc7", None), "Employment": ("ppemploy", None),
             "Household size": ("pphhsize", "size"), "Has children under 18": ("ppkid017", "children"),
             "Income stability": ("I9", None)},
    "pew": {"Frequency of internet use": ("F_INTFREQ", PEW_NET), "Shops online": ("ONLTSK_a", YES_NO),
            "Uses online banking": ("ONLTSK_b", YES_NO), "Uses social media": ("SNSUSE", YES_NO)},
    "anes": {"Household income": ("V241566x", INCOME), "Party identification": ("V241227x", PARTY),
             "Political ideology": ("V241177", IDEOLOGY)},
}


def background_value(raw, mapping):
    code = numeric(raw)
    if mapping == "size":
        return str(int(code)) if code.is_integer() and code > 0 else "Unknown"
    if mapping == "children":
        return ("Yes" if code else "No") if code.is_integer() and code >= 0 else "Unknown"
    if mapping:
        return mapping.get(code, "Unknown")
    return raw.strip() if raw.strip() not in {"", "Refused", "Not asked", "Don't know"} else "Unknown"


def read_people(study, survey):
    rows = read_table(study / "数据" / f"{survey}.zip")
    header = {name.lower(): name for name in rows[0]}
    wave = 168 if survey == "pew" else None
    pid, age, edu, weight, threshold = DEMOGRAPHICS[survey]
    pid, age, edu, weight = (column(header, key, wave) for key in (pid, age, edu, weight))
    extra = {label: (column(header, key, wave), mapping) for label, (key, mapping) in EXTRA[survey].items()}
    items = {item: column(header, item, wave) for item in ITEMS[survey]}
    flags = {item: column(header, f"{item}_iflag") for item in items} if survey == "shed" else {}
    people = []
    for row in rows:
        w = numeric(row[weight])
        if not math.isfinite(w) or w <= 0:
            continue
        age_code = numeric(row[age])
        if survey == "pew":
            band = AGES[age_code == 4] if age_code in PEW_AGE else None
            edu_code = numeric(row[edu])
            fine_age, fine_edu = PEW_AGE.get(age_code), PEW_EDU.get(edu_code)
        else:
            band = age_band(row[age])
            fine_age = ("80 or older" if survey == "anes" and age_code >= 80
                        else str(int(age_code))) if band else None
            if survey == "shed":
                edu_code, fine_edu = SHED_EDUCATION.get(row[edu]), row[edu]
            else:
                edu_code = numeric(row[edu])
                fine_edu = ANES_EDU.get(edu_code)
        if not band or not fine_edu or edu_code is None:
            continue
        stratum = f"{band}|{EDUCATION[edu_code >= threshold]}"
        detail = {label: background_value(row[field], mapping) for label, (field, mapping) in extra.items()}
        if survey == "shed" and numeric(row[column(header, "I9_iflag")]) != 0:
            detail["Income stability"] = "Unknown"
        answers = {}
        for item, field in items.items():
            answer = {"Yes": 1, "No": 0}.get(row[field]) if survey == "shed" else numeric(row[field])
            if answer in ITEMS[survey][item][1] and (item not in flags or numeric(row[flags[item]]) == 0):
                answers[item] = str(int(answer))
        token = hashlib.sha256(f"profile-comparison/{survey}/{row[pid]}".encode()).hexdigest()[:24]
        people.append({"id": token, "stratum": stratum, "weight": w, "answers": answers,
                       "background": {"Age": fine_age, "Education": fine_edu}, "detail": detail})
    if len({r["id"] for r in people}) != len(people):
        raise ValueError(f"{survey}: duplicate respondent IDs")
    return people


def history(people, survey):
    totals = defaultdict(float)
    for row in people:
        for item, answer in row["answers"].items():
            totals[row["stratum"], item, answer] += row["weight"]
    out = {}
    for stratum in STRATA:
        out[stratum] = {}
        for item, (_, options) in ITEMS[survey].items():
            counts = {str(k): totals[stratum, item, str(k)] for k in options}
            total = sum(counts.values())
            out[stratum][item] = {key: value / total for key, value in counts.items()}
    return out


def jobs_for(survey, people, traits):
    jobs = []
    for row, persona in zip(people, traits, strict=True):
        if row["stratum"] != persona["stratum"]:
            raise ValueError("Trait assignment crossed strata")
        age, edu = row["stratum"].split("|")
        question = task_text(survey, row["id"])
        extras = {label: persona["traits"][key] or "Unknown" for key, label in TRAITS.items()}
        backgrounds = (
            {"Age group": age, "Education": edu},
            row["background"],
            {**row["background"], **row["detail"]},
            {**row["background"], **row["detail"], **extras},
        )
        for prompt in (0, 1):
            system = (f"Answer as an adult living in the United States during {DATES[survey]}." if not prompt
                      else f"Survey context: United States during {DATES[survey]}. {P1}")
            for index, background in enumerate(backgrounds, 1):
                description = "\n".join(f"{label}: {value}" for label, value in background.items())
                jobs.append({"survey": survey, "id": row["id"], "stratum": row["stratum"],
                             "condition": f"p{prompt}-b{index}", "model": "qwen", "human": True,
                             "system": f"{system}\n{description}", "user": question})
    return jobs


def profile_jobs(study):
    dag = read_json(study / "01_首轮归档" / "cohort.json")
    jobs, pilot, result = [], [], {}
    for survey in ITEMS:
        people = read_people(study, survey)
        formal = draw(people, 60, survey, "respondents")
        formal_ids = {row["id"] for row in formal}
        remaining = [row for row in people if row["id"] not in formal_ids]
        traits = draw(dag["formal"], 60, survey, "traits")
        jobs.extend(jobs_for(survey, formal, traits))
        development = draw(remaining, 12, survey, "development") if survey == "shed" else []
        if development:
            pilot.extend(jobs_for(survey, development, draw([r for r in dag["formal"] if r["id"] not in {t["id"] for t in traits}],
                                                               12, survey, "development-traits")))
        result[survey] = {
            "respondents": [{k: row[k] for k in ("id", "stratum", "weight", "answers")} for row in formal],
            "development": [row["id"] for row in development],
            "trait_match": dict(zip((row["id"] for row in formal), (row["id"] for row in traits), strict=True)),
            "baseline": history(remaining, survey),
            "baseline_n": len(remaining),
        }
    return jobs, pilot, result
