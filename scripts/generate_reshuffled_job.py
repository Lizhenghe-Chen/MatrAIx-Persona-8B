#!/usr/bin/env python3
"""Generate the reshuffled-position job YAML (amazon personas, NA, seed 42, 1000 people)."""
from __future__ import annotations
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT, REPO_ROOT/"application"/"scripts", REPO_ROOT/"application"/"playground",
           REPO_ROOT/"environment"/"runtime", REPO_ROOT/"packages"/"playground"/"src"):
    _raw = str(_p)
    if _raw not in sys.path:
        sys.path.insert(0, _raw)

import generate_application_job as gen
import persona_retrieval as pr
from backend.service.persona_pool_service import PersonaPoolService

_ORIG_RETRIEVE = pr.retrieve_personas
def _retrieve_full(plan, *, repo_root, task_path=None):
    if plan.persona_ids or plan.cohort_id:
        return _ORIG_RETRIEVE(plan, repo_root=repo_root, task_path=task_path)
    sampled = PersonaPoolService.from_repo(repo_root=repo_root).sample_pool(
        persona_pool=plan.persona_pool, sample_size=plan.sample_size, seed=plan.seed,
        sources=plan.sources or None, dimension_filters=plan.dimension_filters or None,
        stratify_fields=plan.stratify_fields or None,
        sample_size_per_value_group=plan.sample_size_per_value_group,
        allocation=plan.allocation, task_path=task_path, include_persona_ids=True)
    persona_ids = [str(pid) for pid in (sampled.get("personaIds") or []) if str(pid).strip()]
    return pr.PersonaRetrievalResult(
        persona_pool=str(sampled.get("pool") or plan.persona_pool),
        persona_ids=persona_ids, matched_count=int(sampled.get("matchedCount") or len(persona_ids)),
        sample_size=int(sampled.get("sampleSize") or len(persona_ids)), seed=plan.seed,
        sources=list(plan.sources), dimension_filters=dict(plan.dimension_filters),
        stratify_fields=list(sampled.get("fields") or plan.stratify_fields),
        strategy_path=plan.strategy_path)

def main() -> None:
    sample_size = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    concurrent = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 42
    pr.retrieve_personas = _retrieve_full
    gen.retrieve_personas = _retrieve_full
    task = "application/tasks/survey_shower-liner-6asin-reshuffled"
    slug = f"survey-shower-liner-reshuffled-n{sample_size}"
    sys.argv = [
        "generate_reshuffled_job", "--task", task, "--execution-mode", "auto",
        "--dataset", "persona/datasets/matraix-persona-1m",
        "--sample-size", str(sample_size), "--seed", str(seed),
        "--model-name", "deepseek/deepseek-chat", "--no-stratify",
        "--sources", "amazon", "--filter", "region=North America",
        "--n-concurrent-trials", str(concurrent), "--name", slug, "--job-name", slug,
    ]
    gen.main()
    print(f"[generated] {slug} (display order: C B D E A F)")

if __name__ == "__main__":
    main()
