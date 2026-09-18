#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the shower-curtain-liner RANK-POSITION experiment tasks (official pipeline).

Research question: does the search-result display ORDER (rank position) change
click intent and purchase choice on Amazon?

Design: same 6 products, same 1000-person amazon cohort, 3 position arms:
  arm-a-first (baseline):  A B C D E F
  arm-c-first:             C A B D E F   (low-price high-rating C promoted to #1)
  arm-f-first:             F A B C D E   (unavailable F on #1 — does position lure clicks?)

Each arm asks: first-click intent (with reason), final purchase (with reason),
per-product rejection reasons, rank-order awareness, rank importance, page tolerance.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path("/Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B")
SRC_TESTS = ROOT / "application/tasks/survey_toilet-brush-top30-brand-rating/tests"

PRODUCTS = {
    "A": {
        "asin": "B0CGLZ56JC", "brand": "AmazerBath",
        "name": "AmazerBath Rainbow Emerald EVA Shower Curtain Liner (72\" x 72\")",
        "material": "100% EVA, crystal-clear, silky touch; 100% brass grommets",
        "look": "Semi-transparent emerald-green EVA liner with natural drape, 12 brass grommets, weighted bottom stones; photographed in a bright modern bathroom.",
        "points": "Luxury soft-touch EVA; eco-friendly, BPA-free, odor-free; 12 rustproof brass grommets; reinforced double-layered header; weighted bottom keeps it in place; waterproof & quick-drying; wipe-clean care",
        "price": 18.99, "rating": 4.5, "reviews": 4156, "rank": 27,
        "size": '72"W x 72"L (Pack of 1)', "pack": "1",
        "avail": "Page shows delivery notice; reference price $18.99 (no featured offer at collection time)",
    },
    "B": {
        "asin": "B0C9MCD5WL", "brand": "jssablo",
        "name": "jssablo Blue Cube 3D EVA Shower Curtain Liner, 72\" x 72\", Magnetic",
        "material": "70% EVA (healthier than PEVA/PVC)",
        "look": "Gradient blue liner with 3D cube-embossed texture (deep blue fading to clear), metal grommets, weighted hem; shown in a light-modern bathroom.",
        "points": "3D cube texture looks premium; 12 metal grommets for easy install & tear resistance; 3 magnets at bottom keep liner against the tub; waterproof; wipe/rinse to clean",
        "price": 7.19, "rating": 4.4, "reviews": 1872, "rank": 41,
        "size": '72"W x 72"L (Pack of 1)', "pack": "1",
        "avail": "In Stock",
    },
    "C": {
        "asin": "B0C2GTPSFR", "brand": "LQFMEHOT",
        "name": "LQFMEHOT EVA Blue Water-Wave Shower Curtain Liner, 72\" x 72\", Art Deco",
        "material": "EVA, lightweight",
        "look": "Gradient blue liner with water-ripple texture (deep blue to light transparent), metal grommets, weighted hem; shown with white tub and dark tiles.",
        "points": "Art-Deco wave pattern; waterproof smooth surface; 3 heavy magnets at bottom; tear-proof header film + anti-rust metal buttons; easy rinse-and-wipe care; odor-free EVA",
        "price": 7.09, "rating": 4.6, "reviews": 974, "rank": 124,
        "size": '72"W x 72"L (Pack of 1)', "pack": "1",
        "avail": "In Stock",
    },
    "D": {
        "asin": "B0GYWQQ2K3", "brand": "Laumyasof",
        "name": "Laumyasof 2-Pack Green 3D Pebble EVA Shower Curtain Liner, 72\" x 72\"",
        "material": "3.2-gauge EVA (thin, lightweight)",
        "look": "Semi-transparent green liner with 3D pebble texture; '2 PACK' badge on the image; shown against white tiles and a tub.",
        "points": "2-pack value; 3D pebble design; 12 rust-proof metal grommets; 3 magnets at weighted hem; water-repellent quick-dry surface; easy care",
        "price": 9.99, "rating": 4.4, "reviews": 16, "rank": 129,
        "size": '72"W x 72"L (Pack of 2)', "pack": "2",
        "avail": "In Stock (brand-new listing, only 16 reviews)",
    },
    "E": {
        "asin": "B0D212C4XS", "brand": "Dependable Industries Essentials",
        "name": "Dependable Industries EVA Black Shower Curtain Liner, 72\" x 72\", Modern",
        "material": "EVA, PVC-free",
        "look": "Plain solid-black liner with silver metal grommets on a white studio background; minimal, no pattern.",
        "points": "Water-resistant EVA contains spray; 3 weighted magnets at bottom; reinforced metal grommets; easy wipe-clean; standard 72x72 fits most tubs; PVC-free",
        "price": 9.99, "rating": 4.3, "reviews": 116, "rank": 203,
        "size": '72"W x 72"L (Pack of 1)', "pack": "1",
        "avail": "Only 10 left in stock — order soon",
    },
    "F": {
        "asin": "B0FSRN9YTK", "brand": "MuuXii",
        "name": "MuuXii EVA Clear Polka-Dot Shower Curtain Liner, 71\" x 71\", with Hooks",
        "material": "EVA plastic, waterproof",
        "look": "Clear blue-tinted liner with subtle polka-dot pattern, white hooks included; shown in a bright modern bathroom.",
        "points": "Completely transparent — lets light through; 3 magnets at bottom add weight; includes 12 plastic hooks; rinse-off easy care; lightweight",
        "price": None, "rating": 4.4, "reviews": 10, "rank": 856,
        "size": '71"W x 71"L (Pack of 1)', "pack": "1",
        "avail": "Currently unavailable (cannot be purchased at collection time)",
    },
}

ARMS = {
    "a-first": ["A", "B", "C", "D", "E", "F"],
    "c-first": ["C", "A", "B", "D", "E", "F"],
    "f-first": ["F", "A", "B", "C", "D", "E"],
}
ARM_DESC = {
    "a-first": "baseline order (A at #1)",
    "c-first": "low-price high-rating C promoted to #1",
    "f-first": "unavailable F placed at #1 (position lure test)",
}

REJECT_OPTIONS = [
    ("already_chosen", "This is the one I chose"),
    ("price_too_high", "Price is too high for a liner"),
    ("price_suspicious", "Price seems cheap — I worry about quality"),
    ("look", "I don't like the look / color / texture"),
    ("material", "Material (EVA etc.) is not convincing / I worry about safety"),
    ("rating", "Rating is not high enough"),
    ("few_reviews", "Too few reviews — not enough evidence"),
    ("review_concern", "Review comments raised doubts"),
    ("brand", "Brand is unfamiliar / not trustworthy enough"),
    ("size", "Size / fit is unclear or unusual (71x71, 72x72)"),
    ("missing_magnet", "Missing magnet / weighted hem I want"),
    ("transparency", "Transparency or light-blocking is not what I want"),
    ("pack", "Pack size is not what I want (single vs 2-pack)"),
    ("info_incomplete", "Product info is incomplete (description / images / specs)"),
    ("availability", "Out of stock / low stock / delivery problem"),
    ("other", "Other reason"),
]
PAGE_OPTIONS = [
    ("page1", "Page 1 only"),
    ("page2", "I would go to page 2"),
    ("page3", "I would go to page 3"),
    ("page4_5", "I would go to pages 4–5"),
    ("beyond", "I might even go past page 5"),
    ("unsure", "Not sure"),
]
RANK_AWARE_OPTIONS = [
    ("noticed_affected", "Yes — I noticed the order and it influenced me"),
    ("noticed_not_affected", "I noticed the order but it did not influence me"),
    ("not_noticed", "I did not really notice the order"),
]


def fmt_price(p) -> str:
    return f"${p:.2f}" if p else "—"


def build_context(order: list[str], arm: str) -> str:
    lines = [
        "# Product brief — Shower Curtain Liner Search Results (display order varies)",
        "",
        "You are on Amazon looking for a **shower curtain liner** for your bathroom. You search and the results page "
        "shows **6 liners, listed in the order below** — item 1 is the top of the search results, item 6 the bottom. "
        "On the search results page you can see each product's **thumbnail, brand, price, star rating and review count**.",
        "",
        "Display order for this session (top to bottom): " + ", ".join(order) + ".",
        "",
        "Below is what you see on each product's page once you click in (Sep 2026). Liners with very few reviews are "
        "marked as less reliable. Availability reflects the current listing state.",
        "",
        "| Position | Option | Product | Material | Look & design | Key selling points | Price (USD) | Rating | Availability |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for pos, oid in enumerate(order, start=1):
        p = PRODUCTS[oid]
        rating_txt = f"{p['rating']}★ · {p['reviews']:,} reviews"
        if p["reviews"] < 50:
            rating_txt += " (very few — rating less reliable)"
        lines.append(
            f"| #{pos} | {oid} | {p['brand']} — {p['name']} | {p['material']} | {p['look']} | "
            f"{p['points']} | {fmt_price(p['price'])} | {rating_txt} | {p['avail']} |"
        )
    lines += [
        "",
        "Notes: prices are USD reference prices from Amazon.com (Sep 2026). Look & design is a short objective "
        "description of each product's appearance based on its official product image. Use only the details in this "
        "brief — do not invent other product facts.",
    ]
    return "\n".join(lines)


def _product_choices(order: list[str]) -> list[dict]:
    opts = []
    for oid in order:
        p = PRODUCTS[oid]
        pos = order.index(oid) + 1
        opts.append({"id": oid,
                     "label": f"{oid} (position #{pos}) — {p['brand']} {p['name']} ({fmt_price(p['price'])})"})
    opts.append({"id": "none_of_these", "label": "None of these — I would not buy any of them"})
    return opts


def build_questionnaire(order: list[str]) -> dict:
    qs: list[dict] = []

    qs.append({
        "id": "q_first_click",
        "prompt": ("Looking at the search results in the order shown, which product would you be MOST drawn to click "
                   "into first? Give a 2-3 sentence reason."),
        "type": "single_choice",
        "construct": "first_click",
        "required": True,
        "askRationale": True,
        "options": _product_choices(order),
    })

    qs.append({
        "id": "q_choice",
        "prompt": "Which shower curtain liner would you actually BUY for your bathroom? Give a 2-3 sentence reason.",
        "type": "single_choice",
        "construct": "liner_choice",
        "required": True,
        "askRationale": True,
        "options": _product_choices(order),
    })

    for oid in order:
        p = PRODUCTS[oid]
        qs.append({
            "id": f"q_reject_{oid}",
            "prompt": (f"Why did you NOT choose Option {oid} ({p['brand']}, {fmt_price(p['price'])})? "
                       "Select ALL that apply. If this is the one you chose, select 'This is the one I chose'."),
            "type": "multi_choice",
            "construct": f"reject_{oid}",
            "required": True,
            "options": [{"id": rid, "label": rlabel} for rid, rlabel in REJECT_OPTIONS],
        })

    qs.append({
        "id": "q_rank_aware",
        "prompt": ("The products were shown in a specific order (top to bottom). Did you notice the display order, "
                   "and did it influence your click / purchase decision? Give a 1-2 sentence reason."),
        "type": "single_choice",
        "construct": "rank_aware",
        "required": True,
        "askRationale": True,
        "options": [{"id": rid, "label": rlabel} for rid, rlabel in RANK_AWARE_OPTIONS],
    })

    qs.append({
        "id": "q_rank_importance",
        "prompt": "On Amazon, how much does the search-result RANK POSITION (top vs bottom of results) matter to your decision?",
        "type": "likert",
        "construct": "rank_importance",
        "required": True,
        "minValue": 1,
        "maxValue": 5,
    })

    qs.append({
        "id": "q_page_search",
        "prompt": "On Amazon, how far into the search results would you keep looking for a shower curtain liner?",
        "type": "single_choice",
        "construct": "page_search",
        "required": True,
        "options": [{"id": pid, "label": plabel} for pid, plabel in PAGE_OPTIONS],
    })

    return {
        "schemaVersion": "1.0",
        "id": "shower_liner_6asin_rank_v1",
        "title": "Shower Curtain Liner Rank-Position Experiment (6 ASINs + None)",
        "description": (
            "Tests whether search-result display ORDER (rank position) changes click intent and purchase choice: "
            "same 6 products shown in different orders across arms; measures first-click, final purchase, per-product "
            "rejection reasons, rank-order awareness and rank importance."
        ),
        "questions": qs,
    }


def build_instruction(order: list[str], arm: str) -> str:
    return f"""# Shower Curtain Liner Rank-Position Experiment

We're simulating a **real Amazon search**. You need a **shower curtain liner** for your bathroom.
You search on Amazon and the results page shows **6 liners in a specific order** — item #1 at the top,
item #6 at the bottom. This session's display order is: **{', '.join(order)}**.

Walk through the journey honestly:

1. **First click** — which product are you most drawn to click into first, and why?
2. **Buy choice** — after looking at the products, which one would you actually buy, and why?
3. **Rejections** — for each product you did NOT choose, say why (select all that apply).
4. **Rank awareness** — did you notice the display order, and did it influence you?
5. **Rank importance** — how much does search-result position matter to you in general?

## How to answer

- Read the brief before you start. Use only the product facts in the brief.
- Answer every required question.
- Every decision question asks for a reason — always give one (1-3 sentences).
- For multiple-choice, select all that apply (option ids are the letters/keys listed).
- For rating scales, use a whole number in the given range.
- Give the answer alone unless a question also asks for a short reason.
"""


def build_persona() -> dict:
    return {
        "schemaVersion": "1.0",
        "sources": ["amazon"],
        "dimensionFilters": {"region": ["North America"]},
        "sampling": {"mode": "random", "sampleSize": 1000},
        "datasetProfile": {
            "hard_filter": {"region": {"North America": 1.0}},
            "observed_review_style": {
                "cog_verbosity": {
                    "Terse": 0.161, "Concise": 0.407, "Balanced": 0.292,
                    "Wordy": 0.117, "Rambling": 0.019, "missing": 0.003,
                }
            },
            "soft_or_conditional_only": {
                "primary_language": "English",
                "economic_motivation": {"assign_only_when_price_evidence_exists": True},
                "pref_quality_vs_quantity": {"assign_only_when_quality_evidence_exists": True},
                "lstyle_shopping_style": {"assign_only_from_comparison_price_or_repeat_purchase": True},
            },
            "missing_by_default": [
                "age_bracket", "gender_identity", "urbanicity", "socioeconomic_band",
                "household_and_family_dimensions", "political_and_religious_dimensions",
                "personality_and_health_dimensions",
            ],
        },
    }


def build_tests(task: Path, order: list[str]) -> None:
    shutil.copytree(SRC_TESTS, task / "tests", dirs_exist_ok=True)
    tsp = task / "tests/test_state.py"
    text = tsp.read_text(encoding="utf-8")

    allowed_block = '    "A",\n    "B",\n    "C",\n    "D",\n    "E",\n    "F",\n    "none_of_these",\n'
    text = re.sub(
        r'ALLOWED_CHOICES = \{[^}]*\}',
        'ALLOWED_CHOICES = {\n' + allowed_block + '}',
        text, count=1,
    )

    old_semantic = text[text.index("def _semantic_check"):text.index("def main()")]
    new_semantic = '''def _semantic_check(payload: dict[str, object]) -> str | None:
    """Task-specific: first-click + purchase must be valid choices with real rationales."""
    answers = payload.get("answers")
    if not isinstance(answers, list):
        return "answers must be a list"
    answers_by_id = {str(a.get("questionId", "")).strip(): a for a in answers if isinstance(a, dict)}
    for qid in ("q_first_click", "q_choice", "q_rank_aware"):
        answer = answers_by_id.get(qid)
        if answer is None:
            return "missing {} answer".format(qid)
        value = str(answer.get("value", "")).strip()
        if value not in ALLOWED_CHOICES:
            if qid != "q_rank_aware":
                return "{} value '{}' not in allowed set".format(qid, value)
        rationale = str(answer.get("rationale") or "").strip()
        if len(rationale) < 10:
            return "{} rationale is missing or too short".format(qid)
    return None


'''
    text = text.replace(old_semantic, new_semantic)
    tsp.write_text(text, encoding="utf-8")


def main() -> None:
    for arm, order in ARMS.items():
        task = ROOT / f"application/tasks/survey_shower-liner-6asin-rank-{arm}"
        if task.exists():
            shutil.rmtree(task)
        (task / "input").mkdir(parents=True)
        (task / "input").joinpath("context.md").write_text(
            build_context(order, arm), encoding="utf-8")
        (task / "input").joinpath("questionnaire.yaml").write_text(
            _dict_to_yaml(build_questionnaire(order)), encoding="utf-8")
        task.joinpath("instruction.md").write_text(
            build_instruction(order, arm), encoding="utf-8")
        task.joinpath("persona_strategy.json").write_text(
            json.dumps(build_persona(), ensure_ascii=False, indent=2), encoding="utf-8")
        task.joinpath("reporting.json").write_text(
            json.dumps({"schemaVersion": "1.0", "contextRules": []}), encoding="utf-8")
        task.joinpath("task.toml").write_text(f'''version = "1.0"
artifacts = [ "/app/output",]

[task]
name = "application/survey_shower-liner-6asin-rank-{arm}"

[metadata]
difficulty = "easy"
type = "survey"
domain = "e-commerce"
tags = [ "consumer goods", "shower curtain liner", "rank position", "search order", "first-click", "shopping simulation",]

[verifier]
timeout_sec = 120.0

[agent]
timeout_sec = 600.0

[environment]
definition = "application/shared-survey-form"
build_timeout_sec = 1800.0
cpus = 1
memory_mb = 2048
storage_mb = 10240
gpus = 0
''', encoding="utf-8")
        build_tests(task, order)
        n_q = len(build_questionnaire(order)["questions"])
        print(f"task written: {task} ({len(order)} products in order {order}, {n_q} questions, arm: {ARM_DESC[arm]})")


def _dict_to_yaml(d: dict) -> str:
    import yaml
    return yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=120)


if __name__ == "__main__":
    main()
