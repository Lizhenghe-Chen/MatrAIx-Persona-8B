#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the 6-ASIN shower curtain liner shopping survey task (official pipeline).

Products: 6 ASINs (Shower Curtain Liners, US) + None.
Questionnaire: choice + rationale, per-product rejection reasons,
search-page browse/buy tolerance, decision factors, listing-optimization
importance (title/image/bullets/A+/attributes/price/reviews/trust),
listing red lines, material/transparency preferences, badge & switch triggers.
Persona: amazon source, North America, same cohort convention (seed set at job gen).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path("/Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B")
TASK = ROOT / "application/tasks/survey_shower-liner-6asin"
SRC_TESTS = ROOT / "application/tasks/survey_toilet-brush-top30-brand-rating/tests"

# ---------------- product data (from 2026-09-17 Excel, US site) ----------------
# key: option id -> dict
PRODUCTS = {
    "A": {
        "asin": "B0CGLZ56JC", "brand": "AmazerBath",
        "name": "AmazerBath Rainbow Emerald EVA Shower Curtain Liner (72\" x 72\")",
        "material": "100% EVA, crystal-clear, silky touch; 100% brass grommets",
        "look": "Semi-transparent emerald-green EVA liner with natural drape, 12 brass grommets, weighted bottom stones; photographed in a bright modern bathroom.",
        "points": "Luxury soft-touch EVA; eco-friendly, BPA-free, odor-free; 12 rustproof brass grommets; reinforced double-layered header; weighted bottom keeps it in place; waterproof & quick-drying; wipe-clean care",
        "price": 18.99, "rating": 4.5, "reviews": 4156, "rank": 27,
        "size": '72"W x 72"L (Pack of 1)', "pack": "1",
    },
    "B": {
        "asin": "B0C9MCD5WL", "brand": "jssablo",
        "name": "jssablo Blue Cube 3D EVA Shower Curtain Liner, 72\" x 72\", Magnetic",
        "material": "70% EVA (healthier than PEVA/PVC)",
        "look": "Gradient blue liner with 3D cube-embossed texture (deep blue fading to clear), metal grommets, weighted hem; shown in a light-modern bathroom.",
        "points": "3D cube texture looks premium; 12 metal grommets for easy install & tear resistance; 3 magnets at bottom keep liner against the tub; waterproof; wipe/rinse to clean",
        "price": 7.19, "rating": 4.4, "reviews": 1872, "rank": 41,
        "size": '72"W x 72"L (Pack of 1)', "pack": "1",
    },
    "C": {
        "asin": "B0C2GTPSFR", "brand": "LQFMEHOT",
        "name": "LQFMEHOT EVA Blue Water-Wave Shower Curtain Liner, 72\" x 72\", Art Deco",
        "material": "EVA, lightweight",
        "look": "Gradient blue liner with water-ripple texture (deep blue to light transparent), metal grommets, weighted hem; shown with white tub and dark tiles.",
        "points": "Art-Deco wave pattern; waterproof smooth surface; 3 heavy magnets at bottom; tear-proof header film + anti-rust metal buttons; easy rinse-and-wipe care; odor-free EVA",
        "price": 7.09, "rating": 4.6, "reviews": 974, "rank": 124,
        "size": '72"W x 72"L (Pack of 1)', "pack": "1",
    },
    "D": {
        "asin": "B0GYWQQ2K3", "brand": "Laumyasof",
        "name": "Laumyasof 2-Pack Green 3D Pebble EVA Shower Curtain Liner, 72\" x 72\"",
        "material": "3.2-gauge EVA (thin, lightweight)",
        "look": "Semi-transparent green liner with 3D pebble texture; '2 PACK' badge on the image; shown against white tiles and a tub.",
        "points": "2-pack value; 3D pebble design; 12 rust-proof metal grommets; 3 magnets at weighted hem; water-repellent quick-dry surface; easy care",
        "price": 9.99, "rating": 4.4, "reviews": 16, "rank": 129,
        "size": '72"W x 72"L (Pack of 2)', "pack": "2",
    },
    "E": {
        "asin": "B0D212C4XS", "brand": "Dependable Industries Essentials",
        "name": "Dependable Industries EVA Black Shower Curtain Liner, 72\" x 72\", Modern",
        "material": "EVA, PVC-free",
        "look": "Plain solid-black liner with silver metal grommets on a white studio background; minimal, no pattern.",
        "points": "Water-resistant EVA contains spray; 3 weighted magnets at bottom; reinforced metal grommets; easy wipe-clean; standard 72x72 fits most tubs; PVC-free",
        "price": 9.99, "rating": 4.3, "reviews": 116, "rank": 203,
        "size": '72"W x 72"L (Pack of 1)', "pack": "1",
    },
    "F": {
        "asin": "B0FSRN9YTK", "brand": "MuuXii",
        "name": "MuuXii EVA Clear Polka-Dot Shower Curtain Liner, 71\" x 71\", with Hooks",
        "material": "EVA plastic, waterproof",
        "look": "Clear blue-tinted liner with subtle polka-dot pattern, white hooks included; shown in a bright modern bathroom.",
        "points": "Completely transparent — lets light through; 3 magnets at bottom add weight; includes 12 plastic hooks; rinse-off easy care; lightweight",
        "price": None, "rating": 4.4, "reviews": 10, "rank": 856,
        "size": '71"W x 71"L (Pack of 1)', "pack": "1",
    },
}

OPTION_ORDER = ["A", "B", "C", "D", "E", "F"]
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
    ("other", "Other reason"),
]
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
REDLINE_OPTIONS = [
    ("no_price", "No price shown"),
    ("low_rating", "Rating below 4.0"),
    ("few_reviews", "Fewer than ~50 reviews"),
    ("no_size", "No size / dimensions information"),
    ("material_unclear", "Material not clearly stated"),
    ("blur_image", "Main image is blurry / looks fake"),
    ("no_bullets", "No selling-point bullets / thin description"),
    ("no_aplus", "No A+ content / video / rich media"),
    ("brand_unfamiliar", "Brand is completely unfamiliar"),
    ("none", "None of the above would make me exclude a product"),
]
MATERIAL_OPTIONS = [
    ("eva", "EVA (flexible, odor-free, lightweight)"),
    ("peva", "PEVA (chlorine-free alternative)"),
    ("pvc", "PVC (heavier, classic)"),
    ("polyester", "Polyester / fabric (machine-washable)"),
    ("cloth", "Cloth / cotton blend"),
    ("no_preference", "No strong preference"),
]
TRANSPARENCY_OPTIONS = [
    ("fully_transparent", "Fully transparent (lets light through)"),
    ("semi", "Semi-transparent / light-filtering"),
    ("blackout", "Opaque / blackout"),
    ("no_preference", "No strong preference"),
]
BADGE_OPTIONS = [
    ("yes_strongly", "Yes, a lot"),
    ("yes_somewhat", "Yes, somewhat"),
    ("neutral", "Neutral"),
    ("unlikely", "Probably not"),
    ("no_effect", "No, it wouldn't affect me"),
]
SWITCH_OPTIONS = [
    ("lower_price", "A lower price"),
    ("better_rating", "A higher rating / more reviews"),
    ("better_look", "Better looks / design"),
    ("better_function", "Better function / features (magnets, waterproof, quick-dry)"),
    ("better_value", "Better value (2-pack, hooks included)"),
    ("nothing", "Nothing — I'm confident in my choice"),
]


def fmt_price(p) -> str:
    return f"${p:.2f}" if p else "Not shown on listing"


def build_context() -> str:
    lines = [
        "# Product brief — Shower Curtain Liner Shopping Shelf (6 options)",
        "",
        "You are shopping for a **shower curtain liner** for your bathroom. The following **6 liners** are on the shelf, "
        "like an online store search result — you can see each product's **brand, price, material, look & design, selling "
        "points, and ratings/review counts**. All 6 liners are equally in stock and buyable; stock, delivery and "
        "buy-box state are identical across options and must NOT influence your choice. Pick **the one** you would actually buy, or choose "
        '"None of these" if nothing fits your needs or budget.',
        "",
        "Ratings and review counts come from the product pages (Sep 2026). Liners with very few reviews are marked as "
        "less reliable. All 6 options are equally available for purchase — treat stock, delivery and buy-box state as "
        "identical across options and base your choice only on the product and listing information shown.",
        "",
        "| Option | Product | Material | Look & design | Key selling points | Price (USD) | Rating |",
        "|---|---|---|---|---|---|---|",
    ]
    for oid in OPTION_ORDER:
        p = PRODUCTS[oid]
        rating_txt = f"{p['rating']}★ · {p['reviews']:,} reviews"
        if p["reviews"] < 50:
            rating_txt += " (very few — rating less reliable)"
        points = "; ".join(p["points"].split("; "))
        lines.append(
            f"| {oid} | {p['brand']} — {p['name']} | {p['material']} | {p['look']} | "
            f"{points} | {fmt_price(p['price'])} | {rating_txt} |"
        )
    lines += [
        "",
        "**None of these** — if none of the 6 fits your needs or budget.",
        "",
        "Notes: prices are USD reference prices from Amazon.com (Sep 2026); where a listing did not display a price, "
        "the cell reads 'Not shown on listing' — treat that as missing listing information, NOT as a stock problem "
        "(every option is in stock and buyable). Look & design is a short objective "
        "description of each product's appearance based on its official product image. Use only the details in this "
        "brief — do not invent other product facts.",
    ]
    return "\n".join(lines)


def build_questionnaire() -> dict:
    qs: list[dict] = []

    # 1) choice + rationale
    choice_opts = []
    for oid in OPTION_ORDER:
        p = PRODUCTS[oid]
        choice_opts.append({
            "id": oid,
            "label": f"{oid} — {p['brand']} {p['name']} ({fmt_price(p['price'])})",
        })
    choice_opts.append({"id": "none_of_these", "label": "None of these — I would not buy any of them"})
    qs.append({
        "id": "q_choice",
        "prompt": "Which shower curtain liner would you buy for your bathroom? Give a 2-3 sentence reason for your choice.",
        "type": "single_choice",
        "construct": "liner_choice",
        "required": True,
        "askRationale": True,
        "options": choice_opts,
    })

    # 2-7) per-product rejection reasons (multi_choice)
    for oid in OPTION_ORDER:
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

    # 8-9) search-page browse / buy tolerance
    qs.append({
        "id": "q_page_browse",
        "prompt": "On Amazon, how far into the search results would you still click in and BROWSE a shower curtain liner?",
        "type": "single_choice",
        "construct": "page_browse",
        "required": True,
        "options": [{"id": pid, "label": plabel} for pid, plabel in PAGE_OPTIONS],
    })
    qs.append({
        "id": "q_page_buy",
        "prompt": "On Amazon, how far into the search results would you still consider BUYING a shower curtain liner?",
        "type": "single_choice",
        "construct": "page_buy",
        "required": True,
        "options": [{"id": pid, "label": plabel} for pid, plabel in PAGE_OPTIONS],
    })

    # 10-11) decision factors
    qs.append({
        "id": "q_factor_most",
        "prompt": "What mattered MOST in your choice?",
        "type": "single_choice",
        "construct": "factor_most",
        "required": True,
        "options": [{"id": fid, "label": flabel} for fid, flabel in FACTOR_OPTIONS],
    })
    qs.append({
        "id": "q_factor_second",
        "prompt": "What was your SECOND most important factor?",
        "type": "single_choice",
        "construct": "factor_second",
        "required": True,
        "options": [{"id": fid, "label": flabel} for fid, flabel in FACTOR_OPTIONS],
    })

    # 12-19) listing-optimization importance (likert 1-5)
    likerts = [
        ("q_importance_title", "A complete, clear product TITLE (size, material, key feature) matters to me."),
        ("q_importance_image", "CLEAR MAIN IMAGES that show the real look & effect matter to me."),
        ("q_importance_bullets", "Selling-point BULLETS (5 bullets) that explain benefits matter to me."),
        ("q_importance_aplus", "A+ content / product video / brand story pages influence my decision."),
        ("q_importance_attr", "Complete ATTRIBUTES / size & spec tables (dimensions, material, weight) matter to me."),
        ("q_importance_price", "PRICE and value for money matter to me."),
        ("q_importance_reviews", "RATINGS + review count + review content influence my decision."),
        ("q_importance_trust", "Brand trust and safety certifications (BPA-free / PVC-free / odor-free) matter to me."),
    ]
    for qid, prompt in likerts:
        qs.append({
            "id": qid,
            "prompt": prompt,
            "type": "likert",
            "construct": qid,
            "required": True,
            "minValue": 1,
            "maxValue": 5,
        })

    # 20) listing red lines
    qs.append({
        "id": "q_listing_redline",
        "prompt": "Which of the following would make you EXCLUDE a shower curtain liner immediately? Select all that apply.",
        "type": "multi_choice",
        "construct": "listing_redline",
        "required": True,
        "options": [{"id": rid, "label": rlabel} for rid, rlabel in REDLINE_OPTIONS],
    })

    # 21-22) category preferences
    qs.append({
        "id": "q_material_pref",
        "prompt": "Which liner material do you prefer?",
        "type": "single_choice",
        "construct": "material_pref",
        "required": True,
        "options": [{"id": mid, "label": mlab} for mid, mlab in MATERIAL_OPTIONS],
    })
    qs.append({
        "id": "q_transparency_pref",
        "prompt": "Which transparency level do you prefer for a liner?",
        "type": "single_choice",
        "construct": "transparency_pref",
        "required": True,
        "options": [{"id": tid, "label": tlab} for tid, tlab in TRANSPARENCY_OPTIONS],
    })

    # 23-24) badge & switch
    qs.append({
        "id": "q_badge_effect",
        "prompt": 'If one liner on the shelf carried an "Amazon\'s Choice" or "Best Seller" badge, would it influence you?',
        "type": "single_choice",
        "construct": "badge_effect",
        "required": True,
        "options": [{"id": bid, "label": blab} for bid, blab in BADGE_OPTIONS],
    })
    qs.append({
        "id": "q_switch_trigger",
        "prompt": "What would most likely make you switch to a different option on this shelf?",
        "type": "single_choice",
        "construct": "switch_trigger",
        "required": True,
        "options": [{"id": sid, "label": slab} for sid, slab in SWITCH_OPTIONS],
    })

    # 25-26) attitudes
    qs.append({
        "id": "q_price_acceptance",
        "prompt": "The price of the liner I chose is acceptable for what it offers.",
        "type": "likert",
        "construct": "price_acceptance",
        "required": True,
        "minValue": 1,
        "maxValue": 5,
    })
    qs.append({
        "id": "q_purchase_intent",
        "prompt": "I would realistically buy this shower curtain liner within the next 3 months.",
        "type": "likert",
        "construct": "purchase_intent",
        "required": True,
        "minValue": 1,
        "maxValue": 5,
    })

    return {
        "schemaVersion": "1.0",
        "id": "shower_liner_6asin_v1",
        "title": "Shower Curtain Liner Shopping Choice Survey (6 ASINs + None)",
        "description": (
            "Which shower curtain liner the persona would actually buy from a 6-option shelf (plus 'none'), "
            "why the other 5 were rejected, search-page browse/buy tolerance, and how listing-optimization "
            "elements (title/images/bullets/A+/attributes/price/reviews/brand trust) shape the decision; stock/availability is held constant and excluded as a factor."
        ),
        "questions": qs,
    }


def build_instruction() -> str:
    return """# Shower Curtain Liner Shopping Choice Survey

We're simulating a **shopping decision**. You are buying a **shower curtain liner** for your bathroom.
A shelf of **6 shower curtain liners** is in front of you — like shopping on an online store. All 6 are equally in
stock and buyable (stock/delivery is identical, do not let it affect you). Read the product cards
(brand, price, material, look & design, selling points, ratings/review counts), then pick **the one**
you would actually buy, or choose **"None of these"** if nothing fits your needs or budget.

After choosing, you will be asked:
- **Why you did not choose each of the other 5 options** — give a real reason for every one you did not pick
  (if you chose a product, mark "This is the one I chose" for that option's question).
- How far into **Amazon search results** you would still browse / buy a liner.
- Which **listing elements** (title, images, bullets, A+, attributes, price, reviews, brand trust) matter to you.

## How to answer

- Read the brief before you start.
- Answer every required question.
- For multiple-choice, select all that apply (option ids are the letters/keys listed).
- For rating scales, use a whole number in the given range.
- Give the answer alone unless a question also asks for a short reason or confidence.
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
    # rewrite ALLOWED_CHOICES in test_state.py
    tsp = TASK / "tests/test_state.py"
    text = tsp.read_text(encoding="utf-8")
    allowed_block = '    "A",\n    "B",\n    "C",\n    "D",\n    "E",\n    "F",\n    "none_of_these",\n'
    import re
    text = re.sub(
        r'ALLOWED_CHOICES = \{[^}]*\}',
        'ALLOWED_CHOICES = {\n' + allowed_block + '}',
        text,
        count=1,
    )
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
name = "application/survey_shower-liner-6asin"

[metadata]
difficulty = "easy"
type = "survey"
domain = "e-commerce"
tags = [ "consumer goods", "shower curtain liner", "choice", "listing optimization", "shopping simulation", "rejection reasons",]

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
