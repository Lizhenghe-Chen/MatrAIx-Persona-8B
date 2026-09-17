#!/usr/bin/env python3
"""Generate the TOP30 toilet-brush 2x2 factorial job YAMLs via OFFICIAL Playground
services (amazon-only personas, North America region, fixed seed 42 so the SAME
1000 personas are used across all four arms -> within-subject factorial design).

Arms:
  anon-rating      anonymous shelf + ratings shown
  anon-norating    anonymous shelf + no ratings
  brand-rating     original brands + ratings shown
  brand-norating   original brands + no ratings

Usage:
  uv run python scripts/generate_toilet_top30_jobs.py [sample_size] [n_concurrent] [seed]
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


ARMS = ["anon-rating", "anon-norating", "brand-rating", "brand-norating"]


def main() -> None:
    sample_size = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    concurrent = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 42

    pr.retrieve_personas = _retrieve_full
    gen.retrieve_personas = _retrieve_full

    persona_ids_by_arm: dict[str, list[str]] = {}
    for arm in ARMS:
        task = f"application/tasks/survey_toilet-brush-top30-{arm}"
        slug = f"survey-toilet-brush-top30-{arm}-n{sample_size}"
        sys.argv = [
            "generate_toilet_top30_jobs",
            "--task", task,
            "--execution-mode", "auto",
            "--dataset", "persona/datasets/matraix-persona-1m",
            "--sample-size", str(sample_size),
            "--seed", str(seed),
            "--model-name", "deepseek/deepseek-chat",
            "--no-stratify",
            "--sources", "amazon",
            "--filter", "region=North America",
            "--n-concurrent-trials", str(concurrent),
            "--name", slug,
            "--job-name", slug,
        ]
        gen.main()
        print(f"[generated] {slug} (task={task}, concurrent={concurrent})")


if __name__ == "__main__":
    main()
