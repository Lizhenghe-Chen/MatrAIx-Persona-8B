#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the 6-ASIN shower curtain liner DECISION-JOURNEY survey task (official pipeline).

Scenario: the persona searches Amazon for a shower curtain (liner), sees these 6
products in the search results, and walks through the real decision journey:
  Q1  first-click intent on the search page (with reason)
  Q2  which detail-page info they want to see (with reason)
  Q3  buy / not-buy decision after reading the page (with reason)
  Q4  whether they would consider another product after leaving (with reason)
  Q5  which other product they would consider (with reason)
  Q6  fallback: if nothing gets bought, which one they would finally buy (with reason)
  Q7  search-page browse tolerance (lightweight)
  Q8  single most important factor of the whole journey (lightweight)

Persona: amazon source, North America (same cohort convention; seed set at job gen).
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path("/Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B")
TASK = ROOT / "application/tasks/survey_shower-liner-6asin-journey"
SRC_TESTS = ROOT / "application/tasks/survey_toilet-brush-top30-brand-rating/tests"

# ---------------- product data (from 2026-09-17 Excel, US site) ----------------
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

OPTION_ORDER = ["A", "B", "C", "D", "E", "F"]
FACTOR_OPTIONS = [
    ("price_value", "Price / value for money"),
    ("material", "Material safety (EVA, odor-free, eco-friendly)"),
    ("waterproof", "Waterproof / anti-mold / quick-dry"),
    ("magnet", "Magnet / weighted hem (stays against the tub)"),
    ("transparency", "Transparency / light filtering"),
    ("appearance", "Look / color / texture"),
    ("size_fit", "Size fit (72x72 etc.)"),
    ("rating", "Star rating"),
    ("reviews", "Review count / review content"),
    ("brand", "Brand trust"),
    ("pack", "Pack size / multi-pack value"),
    ("listing", "Listing completeness (title / images / bullets / specs)"),
]
PAGE_OPTIONS = [
    ("page1", "Page 1 only"),
    ("page2", "I would go to page 2"),
    ("page3", "I would go to page 3"),
    ("page4_5", "I would go to pages 4–5"),
    ("beyond", "I might even go past page 5"),
    ("unsure", "Not sure"),
]
INFO_OPTIONS = [
    ("more_images", "More real-life / angle photos of the product"),
    ("video", "A product video / demo"),
    ("description", "The full product description"),
    ("bullets", "The selling-point bullets"),
    ("specs", "Size & spec table (dimensions, material, weight)"),
    ("material_safety", "Material & safety details (EVA, BPA-free, odor)"),
    ("reviews", "Customer review text and photos"),
    ("qa", "Q&A answers from other buyers"),
    ("aplus", "A+ brand story / comparison content"),
    ("delivery", "Delivery time and shipping options"),
    ("warranty", "Return policy / warranty"),
    ("other", "Something else"),
]
BUY_OPTIONS = [
    ("buy_now", "Yes — I would buy it right away"),
    ("likely_buy", "Probably — I would add it to my cart and keep comparing"),
    ("undecided", "Not sure — I would keep looking"),
    ("not_buy", "No — I would not buy this one"),
]
CONSIDER_OPTIONS = [
    ("yes", "Yes — I would look at the other products"),
    ("maybe", "Maybe — only if nothing better shows up"),
    ("no", "No — I would leave or stick with my decision"),
]


def fmt_price(p) -> str:
    return f"${p:.2f}" if p else "—"


def build_context() -> str:
    lines = [
        "# Product brief — Shower Curtain Liner Search Results (6 options)",
        "",
        "You are on Amazon looking for a **shower curtain liner** for your bathroom. You search and the results page "
        "shows **6 liners**. On the search results page you can see each product's **thumbnail, brand, price, star "
        "rating and review count**. You may click into a product to see its full page (material, look & design, selling "
        "points, availability, etc.).",
        "",
        "Below is what you see on each product's page once you click in (Sep 2026). Liners with very few reviews are "
        "marked as less reliable. Availability reflects the current listing state.",
        "",
        "| Option | Product | Material | Look & design | Key selling points | Price (USD) | Rating | Availability |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for oid in OPTION_ORDER:
        p = PRODUCTS[oid]
        rating_txt = f"{p['rating']}★ · {p['reviews']:,} reviews"
        if p["reviews"] < 50:
            rating_txt += " (very few — rating less reliable)"
        lines.append(
            f"| {oid} | {p['brand']} — {p['name']} | {p['material']} | {p['look']} | "
            f"{p['points']} | {fmt_price(p['price'])} | {rating_txt} | {p['avail']} |"
        )
    lines += [
        "",
        "Notes: prices are USD reference prices from Amazon.com (Sep 2026). Look & design is a short objective "
        "description of each product's appearance based on its official product image. Use only the details in this "
        "brief — do not invent other product facts.",
    ]
    return "\n".join(lines)


def _product_choices() -> list[dict]:
    opts = []
    for oid in OPTION_ORDER:
        p = PRODUCTS[oid]
        opts.append({"id": oid, "label": f"{oid} — {p['brand']} {p['name']} ({fmt_price(p['price'])})"})
    opts.append({"id": "none_of_these", "label": "None of these — I would not buy any of them"})
    return opts


def build_questionnaire() -> dict:
    qs: list[dict] = []

    # Q1 first-click intent on the search page
    qs.append({
        "id": "q_first_click",
        "prompt": ("On the search results page, which product's thumbnail would you be MOST drawn to click into first? "
                   "Give a 2-3 sentence reason — what catches your eye (look, price, rating, review count, brand, image)?"),
        "type": "single_choice",
        "construct": "first_click",
        "required": True,
        "askRationale": True,
        "options": _product_choices(),
    })

    # Q2 which info they want on the detail page
    qs.append({
        "id": "q_click_info",
        "prompt": ("After clicking into that product's page, which information would you most want to check? "
                   "Select up to 3, then give a 1-2 sentence reason why these matter to you."),
        "type": "multi_choice",
        "construct": "click_info",
        "required": True,
        "askRationale": True,
        "options": [{"id": iid, "label": ilab} for iid, ilab in INFO_OPTIONS],
    })

    # Q3 buy / not-buy decision after reading
    qs.append({
        "id": "q_buy_decision",
        "prompt": ("After reading that product's page, would you actually buy it? "
                   "Give a 1-2 sentence reason for your decision."),
        "type": "single_choice",
        "construct": "buy_decision",
        "required": True,
        "askRationale": True,
        "options": [{"id": bid, "label": blab} for bid, blab in BUY_OPTIONS],
    })

    # Q4 whether they would consider another product
    qs.append({
        "id": "q_consider_other",
        "prompt": ("If you did NOT buy it right away, after leaving this product's page would you consider looking at "
                   "the other products on the search results? Give a 1-2 sentence reason."),
        "type": "single_choice",
        "construct": "consider_other",
        "required": True,
        "askRationale": True,
        "options": [{"id": cid, "label": clab} for cid, clab in CONSIDER_OPTIONS],
    })

    # Q5 which other product they would consider
    qs.append({
        "id": "q_next_choice",
        "prompt": ("If you would consider another product, which one would you look at next? "
                   "If you answered 'No' to the previous question, select 'None of these'. "
                   "Give a 1-2 sentence reason."),
        "type": "single_choice",
        "construct": "next_choice",
        "required": True,
        "askRationale": True,
        "options": _product_choices(),
    })

    # Q6 fallback if nothing gets bought
    qs.append({
        "id": "q_fallback",
        "prompt": ("Imagine you clicked through all 6 products but still did not buy anything. "
                   "If you HAD to choose one to buy anyway, which one would it be? Give a 2-3 sentence reason."),
        "type": "single_choice",
        "construct": "fallback",
        "required": True,
        "askRationale": True,
        "options": _product_choices(),
    })

    # Q7 search-page browse tolerance (lightweight)
    qs.append({
        "id": "q_page_search",
        "prompt": "On Amazon, how far into the search results would you keep looking for a shower curtain liner?",
        "type": "single_choice",
        "construct": "page_search",
        "required": True,
        "options": [{"id": pid, "label": plabel} for pid, plabel in PAGE_OPTIONS],
    })

    # Q8 single most important factor across the journey
    qs.append({
        "id": "q_overall_factor",
        "prompt": "Across this whole decision journey, which ONE factor influenced you the most?",
        "type": "single_choice",
        "construct": "overall_factor",
        "required": True,
        "options": [{"id": fid, "label": flabel} for fid, flabel in FACTOR_OPTIONS],
    })

    return {
        "schemaVersion": "1.0",
        "id": "shower_liner_6asin_journey_v1",
        "title": "Shower Curtain Liner Decision Journey Survey (6 ASINs + None)",
        "description": (
            "Simulates the full Amazon shopping journey for a shower curtain liner across 6 search results: "
            "first-click intent, which detail-page info matters, buy / not-buy decision, whether another product "
            "is considered (and which), and a final fallback choice if nothing is bought — each with reasons."
        ),
        "questions": qs,
    }


def build_instruction() -> str:
    return """# Shower Curtain Liner Decision Journey Survey

We're simulating a **real Amazon shopping journey**. You need a **shower curtain liner** for your bathroom.
You search on Amazon and the search results page shows **6 liners** (thumbnail, brand, price, rating, review count).

Walk through the journey honestly, one step at a time:

1. **First click** — which product are you most drawn to click into first, and why?
2. **Detail page** — once inside, which information would you check, and why those?
3. **Buy decision** — after reading the page, would you buy it, and why / why not?
4. **Consider others** — if you didn't buy, would you consider the other products, and why?
5. **Next product** — which one would you consider next, and why?
6. **Fallback** — if you looked through all 6 and still bought nothing, which one would you finally buy, and why?

## How to answer

- Read the brief before you start. Use only the product facts in the brief.
- Answer every required question.
- Every decision question asks for a reason — always give one (1-3 sentences).
- For multiple-choice, select up to the stated number (option ids are the letters/keys listed).
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


def build_tests() -> None:
    shutil.copytree(SRC_TESTS, TASK / "tests", dirs_exist_ok=True)
    tsp = TASK / "tests/test_state.py"
    text = tsp.read_text(encoding="utf-8")

    # ALLOWED_CHOICES block stays identical (A-F + none_of_these)
    allowed_block = '    "A",\n    "B",\n    "C",\n    "D",\n    "E",\n    "F",\n    "none_of_these",\n'
    text = re.sub(
        r'ALLOWED_CHOICES = \{[^}]*\}',
        'ALLOWED_CHOICES = {\n' + allowed_block + '}',
        text,
        count=1,
    )

    # Semantic check: q_first_click (journey's first decision) + every journey
    # decision question must carry a real rationale.
    old_semantic = text[text.index("def _semantic_check"):text.index("def main()")]
    new_semantic = '''def _semantic_check(payload: dict[str, object]) -> str | None:
    """Task-specific: every journey decision question needs a valid answer + rationale."""
    answers = payload.get("answers")
    if not isinstance(answers, list):
        return "answers must be a list"
    answers_by_id = {str(a.get("questionId", "")).strip(): a for a in answers if isinstance(a, dict)}
    rationale_required = [
        "q_first_click",
        "q_click_info",
        "q_buy_decision",
        "q_consider_other",
        "q_next_choice",
        "q_fallback",
    ]
    for qid in rationale_required:
        answer = answers_by_id.get(qid)
        if answer is None:
            return "missing {} answer".format(qid)
        value = answer.get("value")
        if isinstance(value, list):
            if not value:
                return "{} value is empty".format(qid)
        elif str(value).strip() == "":
            return "{} value is empty".format(qid)
        if qid in ("q_first_click", "q_next_choice", "q_fallback"):
            if str(value).strip() not in ALLOWED_CHOICES:
                return "{} value '{}' not in allowed set".format(qid, value)
        rationale = str(answer.get("rationale") or "").strip()
        if len(rationale) < 10:
            return "{} rationale is missing or too short".format(qid)
    return None


'''
    text = text.replace(old_semantic, new_semantic)
    tsp.write_text(text, encoding="utf-8")


def main() -> None:
    if TASK.exists():
        shutil.rmtree(TASK)
    (TASK / "input").mkdir(parents=True)
    (TASK / "input").joinpath("context.md").write_text(build_context(), encoding="utf-8")
    (TASK / "input").joinpath("questionnaire.yaml").write_text(
        _dict_to_yaml(build_questionnaire()), encoding="utf-8")
    TASK.joinpath("instruction.md").write_text(build_instruction(), encoding="utf-8")
    TASK.joinpath("persona_strategy.json").write_text(
        json.dumps(build_persona(), ensure_ascii=False, indent=2), encoding="utf-8")
    TASK.joinpath("reporting.json").write_text(
        json.dumps({"schemaVersion": "1.0", "contextRules": []}), encoding="utf-8")
    TASK.joinpath("task.toml").write_text("""version = "1.0"
artifacts = [ "/app/output",]

[task]
name = "application/survey_shower-liner-6asin-journey"

[metadata]
difficulty = "easy"
type = "survey"
domain = "e-commerce"
tags = [ "consumer goods", "shower curtain liner", "decision journey", "first-click", "shopping simulation", "conversion funnel",]

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
""", encoding="utf-8")
    build_tests()
    print("task written:", TASK)
    n_q = len(build_questionnaire()["questions"])
    print("questions:", n_q)


def _dict_to_yaml(d: dict) -> str:
    import yaml
    return yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=120)


if __name__ == "__main__":
    main()
