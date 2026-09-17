#!/usr/bin/env python3
"""Generate the water-bottle shopping job YAML via OFFICIAL Playground services.

Why this helper exists
----------------------
``application/scripts/generate_application_job.py`` calls
``PersonaPoolService.sample_pool`` WITHOUT ``include_persona_ids=True``, so on the
persona-1m pool any sample larger than 100 gets truncated to the 32-id UI
preview in the generated job YAML (observed: `--sample-size 1000` -> 32 trials).

The official Playground backend (`harbor_job_service.launch`) does the same
sampling WITH ``include_persona_ids=True``. This helper reuses the exact CLI
flow but swaps in that official parameter, then delegates everything else
(job config build, YAML writing, meta sidecar, run hints) to the CLI's own code.

Usage
-----
  uv run python scripts/generate_water_bottle_job.py [sample_size] [n_concurrent_trials]

  e.g.  uv run python scripts/generate_water_bottle_job.py 1000 10
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (
    REPO_ROOT,
    REPO_ROOT / "application" / "scripts",
    REPO_ROOT / "application" / "playground",
    REPO_ROOT / "environment" / "runtime",
    REPO_ROOT / "packages" / "playground" / "src",
):
    _raw = str(_p)
    if _raw not in sys.path:
        sys.path.insert(0, _raw)

import generate_application_job as gen  # noqa: E402
import persona_retrieval as pr  # noqa: E402
from backend.service.persona_pool_service import PersonaPoolService  # noqa: E402

_ORIG_RETRIEVE = pr.retrieve_personas


def _retrieve_full(plan, *, repo_root, task_path=None):
    """Official retrieval, but with include_persona_ids=True (Playground parity)."""
    # Explicit ids / saved-cohort flows are already correct in the CLI.
    if plan.persona_ids or plan.cohort_id:
        return _ORIG_RETRIEVE(plan, repo_root=repo_root, task_path=task_path)

    sampled = PersonaPoolService.from_repo(repo_root=repo_root).sample_pool(
        persona_pool=plan.persona_pool,
        sample_size=plan.sample_size,
        seed=plan.seed,
        sources=plan.sources or None,
        dimension_filters=plan.dimension_filters or None,
        stratify_fields=plan.stratify_fields or None,
        sample_size_per_value_group=plan.sample_size_per_value_group,
        allocation=plan.allocation,
        task_path=task_path,
        include_persona_ids=True,
    )
    persona_ids = [str(pid) for pid in (sampled.get("personaIds") or []) if str(pid).strip()]
    return pr.PersonaRetrievalResult(
        persona_pool=str(sampled.get("pool") or plan.persona_pool),
        persona_ids=persona_ids,
        matched_count=int(sampled.get("matchedCount") or len(persona_ids)),
        sample_size=int(sampled.get("sampleSize") or len(persona_ids)),
        seed=plan.seed,
        sources=list(plan.sources),
        dimension_filters=dict(plan.dimension_filters),
        stratify_fields=list(sampled.get("fields") or plan.stratify_fields),
        strategy_path=plan.strategy_path,
    )


def main() -> None:
    sample_size = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    concurrent = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    job_slug = sys.argv[3] if len(sys.argv) > 3 else "survey-water-bottle-choice-n{}".format(sample_size)

    pr.retrieve_personas = _retrieve_full
    # The CLI imported `retrieve_personas` into its own module namespace at
    # import time, so patch that binding too (monkeypatch target).
    gen.retrieve_personas = _retrieve_full
    sys.argv = [
        "generate_water_bottle_job",
        "--task", "application/tasks/survey_water-bottle-choice",
        "--execution-mode", "auto",
        "--dataset", "persona/datasets/matraix-persona-1m",
        "--sample-size", str(sample_size),
        "--seed", "42",
        "--model-name", "deepseek/deepseek-chat",
        "--no-stratify",
        "--n-concurrent-trials", str(concurrent),
        "--name", job_slug,
        "--job-name", job_slug,
    ]
    gen.main()


if __name__ == "__main__":
    main()
