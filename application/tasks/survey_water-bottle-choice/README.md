# Water Bottle Shopping Choice Survey

Matraix Playground survey task. Simulates ~1000 personas shopping for a daily-use water bottle
from a 6-option shelf (plus "none"), returning a structured choice + reason.

- Matraix Playground entrypoint: `instruction.md`
- Supplementary docs: `input/context.md`, `input/questionnaire.yaml`
- Output: `/app/output/survey_result.json`
- Instrument id: `water_bottle_choice_v1`

## Shelf (reference prices, Sep 2026, CNY)

| id | Product | Price |
|---|---|---|
| fuguang_316 | Fuguang 316 Basic Insulated Bottle | ¥39.9 |
| nalgene_sustain | Nalgene Sustain Wide Mouth 32oz | ≈¥119 |
| beijixiong_316 | Beijixiong 316 Insulated Bottle | ¥129 |
| mijia_bottle | Mijia (Xiaomi) Insulated Bottle | ¥179 |
| zojirushi_sm_sz | Zojirushi SM-SZ Series | ≈¥229 |
| stanley_quencher | Stanley Quencher H2.0 | ≈¥319 |
| none_of_these | Would not buy any | — |

## Sampling strategy

`persona_strategy.json` samples **1000 personas at random** from the global
persona-1m pool, filtered to adults (`age_bracket` 18+) across all four
`economic_motivation` levels. This is a population-proportional draw in
expectation; analysis is stratified post-hoc (age × economic motivation).

> Note: the CLI generator truncates 1M-pool samples larger than ~100 to the
> 32-id UI preview. Use `scripts/generate_water_bottle_job.py` (official
> Playground services with `include_persona_ids=True`) to generate large jobs:
> `uv run python scripts/generate_water_bottle_job.py 1000 10`.

## Verifier

`tests/test_state.py` — generic structural checks (answers + trajectory) plus semantic
constraints: `q_choice` must be a valid option id and carry a non-empty rationale.
