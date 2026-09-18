#!/usr/bin/env python3
"""Build dedicated Amazon-buyer persona datasets (20 / 100 / 1000).

Cross-border e-commerce mode: the Playground UI browses Amazon shoppers, so the
Dataset dropdown needs first-class Amazon-buyer pools. This script materializes
three sizes from the production MatrAIx Persona 1M release:

  persona/datasets/amazon-buyer-n20/    20  personas (source=amazon, North America)
  persona/datasets/amazon-buyer-n100/   100 personas (source=amazon, North America)
  persona/datasets/amazon-buyer-n1000/  1000 personas (source=amazon, North America)

Data source: the already-materialized Amazon cohorts under
persona/datasets/matraix-persona-1m/cohorts/ (all source=amazon, region=North
America, seed 42 — same pipeline the toilet-brush / water-bottle tests used).
n100 is a fixed-seed subset of the 1000-person cohort so all three sizes share
the same sampling pipeline and are mutually consistent.

Idempotent: re-running overwrites the three dataset dirs in place.

Usage:
  uv run python scripts/build_amazon_buyer_datasets.py
"""

from __future__ import annotations

import json
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASETS_DIR = REPO_ROOT / "persona" / "datasets"
PROD_COHORTS_DIR = DATASETS_DIR / "matraix-persona-1m" / "cohorts"

# Known Amazon source cohorts materialized from the 1M release (seed 42, NA).
AMAZON_1000_COHORT = PROD_COHORTS_DIR / "cohort-1ba6f2521983"
AMAZON_20_COHORT = PROD_COHORTS_DIR / "cohort-8b79c3f27ee5"

SEED = 42


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_yaml_dimensions(path: Path) -> dict[str, str]:
    """Extract persona_id / source / display_name / card dims from a persona YAML."""
    import yaml

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(raw, dict):
        return {}
    dims = raw.get("dimensions")
    if not isinstance(dims, dict):
        dims = {}
    card = {}
    for key in ("region", "age_bracket", "economic_motivation"):
        val = dims.get(key)
        if val is not None and str(val).strip():
            card[key] = str(val)
    return {
        "persona_id": str(
            raw.get("persona_id") or path.stem.removeprefix("persona_")
        ),
        "source": str(raw.get("source") or "amazon").strip() or "amazon",
        "display_name": str(raw.get("display_name") or "").strip(),
        "dimensions": card,
    }


def _write_dataset(
    slug: str,
    label: str,
    persona_paths: list[Path],
    *,
    source_pool: str,
    seed: int,
) -> dict[str, object]:
    """Write ``persona/datasets/<slug>/`` with manifest.json + persona YAMLs."""
    dest = DATASETS_DIR / slug
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    manifest_personas: list[dict[str, object]] = []
    source_counts: dict[str, int] = {}
    for src_yaml in persona_paths:
        info = _read_yaml_dimensions(src_yaml)
        out_yaml = dest / src_yaml.name
        shutil.copy2(src_yaml, out_yaml)
        src = str(info.get("source") or "amazon")
        source_counts[src] = source_counts.get(src, 0) + 1
        manifest_personas.append(
            {
                "persona_id": info["persona_id"],
                "display_name": info.get("display_name")
                or f"persona-{info['persona_id']}",
                "path": f"persona/datasets/{slug}/{src_yaml.name}",
                "source": src,
                "dimensions": info.get("dimensions") or {},
            }
        )

    manifest = {
        "kind": "amazon-buyer-dataset",
        "name": label,
        "count": len(manifest_personas),
        "seed": seed,
        "schema_version": "1.0",
        "smoke_persona_id": manifest_personas[0]["persona_id"]
        if manifest_personas
        else None,
        "source_counts": source_counts,
        "dimension_categories": "persona/schema/dimension_categories.json",
        "created_at": _utc_now(),
        "source_pool": source_pool,
        "parent_pool": "persona/datasets/matraix-persona-1m",
        "hf_repo": "MatrAIx2026/MatrAIx_Persona_1M_Public_Release",
        "personas": manifest_personas,
    }
    (dest / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return {
        "pool": f"persona/datasets/{slug}",
        "label": label,
        "count": len(manifest_personas),
    }


def main() -> int:
    if not AMAZON_1000_COHORT.is_dir():
        print(
            f"error: Amazon 1000 cohort missing: {AMAZON_1000_COHORT}\n"
            "Materialize it from the 1M release first "
            "(sample source=amazon, region=North America, seed 42, n=1000).",
            file=sys.stderr,
        )
        return 1
    if not AMAZON_20_COHORT.is_dir():
        print(
            f"error: Amazon 20 cohort missing: {AMAZON_20_COHORT}",
            file=sys.stderr,
        )
        return 1

    n1000_srcs = sorted(AMAZON_1000_COHORT.glob("persona_*.yaml"))
    n20_srcs = sorted(AMAZON_20_COHORT.glob("persona_*.yaml"))
    if len(n1000_srcs) < 1000:
        print(
            f"error: expected 1000 amazon personas, got {len(n1000_srcs)} "
            f"in {AMAZON_1000_COHORT}",
            file=sys.stderr,
        )
        return 1
    if len(n20_srcs) < 20:
        print(
            f"error: expected 20 amazon personas, got {len(n20_srcs)} "
            f"in {AMAZON_20_COHORT}",
            file=sys.stderr,
        )
        return 1

    # n100 = deterministic (seed 42) subset of the 1000 cohort.
    rng = random.Random(SEED)
    n100_srcs = rng.sample(n1000_srcs, 100)

    for slug, label, srcs, source_pool in (
        ("amazon-buyer-n20", "Amazon 买家 20", n20_srcs, str(AMAZON_20_COHORT)),
        ("amazon-buyer-n100", "Amazon 买家 100", n100_srcs, str(AMAZON_1000_COHORT)),
        ("amazon-buyer-n1000", "Amazon 买家 1000", n1000_srcs, str(AMAZON_1000_COHORT)),
    ):
        result = _write_dataset(
            slug,
            label,
            srcs,
            source_pool=source_pool,
            seed=SEED,
        )
        print(
            "built {label}  count={count}  pool={pool}".format(**result)
        )

    print(
        "\nDone. The Dataset dropdown will now show Amazon 买家 20/100/1000 "
        "+ matraix-persona-1m (Global 1M)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
