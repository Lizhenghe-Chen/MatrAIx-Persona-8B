#!/usr/bin/env python3
"""Finalize v2 summary: attach official cost + duration from the job directory.

Usage:
  uv run python scripts/finalize_v2_summary.py <job_dir> <summary_json>

Reads jobs/<job>/_matraix_budget.json (spent_usd, official budget tracker)
and the earliest/latest trial timestamps in result.json to compute duration.
Patches <summary_json> in place with cost_usd / duration_min / input-output hints.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main() -> None:
    job_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "jobs" / "survey-water-bottle-choice-v2-n1000"
    summary_path = Path(sys.argv[2]) if len(sys.argv) > 2 else REPO / "results" / "bottle_choice_1000_summary.json"

    cost = 0.0
    budget = job_dir / "_matraix_budget.json"
    if budget.exists():
        cost = json.loads(budget.read_text(encoding="utf-8")).get("spent_usd", 0.0)

    # duration = first started_at -> last finished_at across trials
    starts, ends = [], []
    for trial in job_dir.glob("survey_*"):
        rj = trial / "result.json"
        if not rj.exists():
            continue
        try:
            d = json.loads(rj.read_text(encoding="utf-8"))
        except Exception:
            continue
        for key, bucket in (("started_at", starts), ("finished_at", ends)):
            v = d.get(key)
            if v:
                try:
                    bucket.append(datetime.fromisoformat(str(v).replace("Z", "+00:00")))
                except ValueError:
                    pass
    dur_min = None
    if starts and ends:
        dur_min = round((max(ends) - min(starts)).total_seconds() / 60, 1)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["cost_usd"] = round(cost, 4)
    if dur_min:
        summary["duration_min"] = dur_min
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"patched {summary_path}: cost_usd={summary['cost_usd']}, duration_min={summary.get('duration_min')}")


if __name__ == "__main__":
    main()
