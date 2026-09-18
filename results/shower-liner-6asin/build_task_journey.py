#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the 6-ASIN shower curtain liner CLICK-JOURNEY survey task (official pipeline).

Scenario (v2, requested 2026-09-18):
  1000 personas shop on Amazon; search "shower curtain liner"; page 1 shows 6 cards.
  Questionnaire replays the real journey:
    1. first click on the search page + why
    2. which product-page information they inspect + buy decision on product 1
    3. if not buying: concerns; back to search; 2nd / 3rd click + buy decisions + reasons
    4. fallback: after clicking all without ordering, which one they most want anyway
    5. per-product final attitude (ordered / favorite-held-back / rejection reasons)
    6. search-page tolerance, decision factors, listing-optimization importance & red lines

PURCHASE-STATE CONFOUND REMOVED (explicit user request):
  All 6 listings are presented as equally in-stock, normal buy-box, identical delivery.
  No stock warnings / badges / coupons / availability language anywhere.
  - ASIN B0FSRN9YTK (F, MuuXii) was "Currently unavailable" with no price at collection.
    For this experiment it is restored as a normal in-stock listing and assigned a
    CONTROLLED ASSUMED PRICE of $7.99 (mid-range of comparable 71-72in EVA liners with
    hooks; B/C with magnets are $7.09-7.19). This is an experimental fill, NOT source data.
  - ASIN B0CGLZ56JC (A) $18.99 is the controlled source price from v1 (no featured offer).
"""
from __future__ import annotations

import json
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
        # CONTROLLED ASSUMED PRICE for the purchase-state-removed experiment (see module docstring).
        "price": 7.99, "rating": 4.4, "reviews": 10, "rank": 856,
        "size": '71"W x 71"L (Pack of 1)', "pack": "1",
    },
}

OPTION_ORDER = ["A", "B", "C", "D", "E", "F"]

# ---- option libraries ----
CLICK_DRIVER_OPTIONS = [
    ("main_image", "The main image / lifestyle photo caught my eye"),
    ("color_pattern", "Its color / pattern / 3D texture stood out"),
    ("price", "The price looked attractive on the card"),
    ("star_rating", "Its star rating looked high"),
    ("review_count", "It had a lot of reviews (social proof)"),
    ("title_keyword", "The title named a feature I want (magnetic, odor-free, etc.)"),
    ("brand", "I recognized / trusted the brand name"),
    ("pack_value", "Multi-pack or hooks-included value on the card"),
    ("magnets", "Magnets / weighted hem selling point"),
    ("material_word", "Material wording (EVA, BPA-free, PVC-free, odor-free)"),
    ("right_size", "Size (72x72 etc.) clearly fits my bathroom"),
    ("imagine_look", "I could picture it looking good in my bathroom"),
    ("other", "Something else (explain in your reason)"),
]
DETAIL_INFO_OPTIONS = [
    ("reviews_photos", "Customer reviews with photos / videos"),
    ("negative_reviews", "Negative reviews / complaints — checking for problems"),
    ("bullets", "The 5 bullet selling points"),
    ("size_specs", "Size / gauge / spec table"),
    ("material_cert", "Material composition & safety certifications"),
    ("main_video", "Main-image video / product demo"),
    ("aplus", "A+ brand content / comparison charts"),
    ("qa", "Customer questions & answers (Q&A)"),
    ("price_deal", "Price, coupons, multi-buy discounts"),
    ("delivery_returns", "Delivery time & return policy"),
    ("seller", "Seller / store information"),
    ("zoom_images", "Zooming the images to judge real look & quality"),
]
BUY_DECISION_OPTIONS = [
    ("buy_now", "Buy it now — I would place the order on this product"),
    ("add_cart", "Add it to cart, but keep comparing the others"),
    ("not_buy", "Not buy it — go back to the search results"),
]
BUY_DECISION_SKIP = [
    ("skip_ordered", "Skip — I already ordered an earlier product"),
    ("buy_now", "Buy it now — I would place the order on this product"),
    ("add_cart", "Add it to cart, but keep comparing the others"),
    ("not_buy", "Not buy it — go back to the search results"),
]
NOTBUY_OPTIONS = [
    ("no_concern", "I have no real concern — I would buy this one"),
    ("price_too_high", "Price is too high for a liner"),
    ("price_suspicious", "Price seems too cheap — I worry about quality / smell"),
    ("look", "I don't like the look / color / pattern"),
    ("material", "Material is not convincing / I worry about safety or plastic smell"),
    ("rating", "Star rating is not high enough"),
    ("few_reviews", "Too few reviews — not enough evidence"),
    ("review_concern", "Review comments / photos raised doubts (mold, tearing, etc.)"),
    ("brand", "Brand is unfamiliar / not trustworthy enough"),
    ("size", "Size / fit is unclear or unusual (71x71 vs 72x72)"),
    ("missing_magnet", "Missing magnets / weighted hem I want"),
    ("transparency", "Transparency / light-blocking is wrong for my bathroom"),
    ("pack", "Pack size is wrong (I want single / 2-pack)"),
    ("info_incomplete", "Product page info is incomplete (images / bullets / specs)"),
    ("want_compare", "Nothing wrong — I just want to compare other options first"),
    ("other", "Other concern (explain in your reason)"),
]
NOTBUY_SKIP_OPTIONS = [("skip_ordered", "Skip — I already ordered an earlier product")] + NOTBUY_OPTIONS
CONSIDER_OPTIONS = [
    ("yes_more", "Yes — I would go back and open another result"),
    ("no_ordered", "No — I would order the first product now"),
    ("no_leave", "No — I would leave Amazon without buying anything"),
]
NEXT_CLICK_OPTIONS = [
    ("A", "A — AmazerBath Emerald EVA ($18.99)"),
    ("B", "B — jssablo Blue Cube 3D Magnetic ($7.19)"),
    ("C", "C — LQFMEHOT Blue Water-Wave ($7.09)"),
    ("D", "D — Laumyasof 2-Pack Green Pebble ($9.99)"),
    ("E", "E — Dependable Solid Black ($9.99)"),
    ("F", "F — MuuXii Clear Polka-Dot with Hooks ($7.99)"),
    ("none_more", "None — I would not open any other product"),
    ("skip_ordered", "Skip — I already ordered an earlier product"),
]
FALLBACK_BLOCKER_OPTIONS = [
    ("no_blocker", "Nothing blocks me — I would actually order it"),
    ("price", "Price / value hesitation"),
    ("reviews_trust", "Too few / mixed reviews — not enough trust"),
    ("brand", "Unknown brand / seller"),
    ("timing", "I am just browsing — not ready to buy yet"),
    ("look_compromise", "Its look is only a compromise, not what I love"),
    ("size", "Size / fit uncertainty"),
    ("material", "Material / smell / safety uncertainty"),
    ("info_gap", "The listing did not answer one of my questions"),
    ("other", "Other (explain in your reason)"),
]
REJECT_OPTIONS = [
    ("final_purchase", "This is the one I finally ordered"),
    ("fallback_favorite", "This is my favorite, but I held off ordering"),
    ("price_too_high", "Price is too high for a liner"),
    ("price_suspicious", "Price seems too cheap — I worry about quality / smell"),
    ("look", "I don't like the look / color / pattern"),
    ("material", "Material is not convincing / I worry about safety or smell"),
    ("rating", "Star rating is not high enough"),
    ("few_reviews", "Too few reviews — not enough evidence"),
    ("review_concern", "Review comments / photos raised doubts"),
    ("brand", "Brand is unfamiliar / not trustworthy enough"),
    ("size", "Size / fit is unclear or unusual (71x71, 72x72)"),
    ("missing_magnet", "Missing magnets / weighted hem I want"),
    ("transparency", "Transparency / light-blocking is wrong for my bathroom"),
    ("pack", "Pack size is wrong (single vs 2-pack)"),
    ("info_incomplete", "Product page info is incomplete"),
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
    ("pack", "Pack size / multi-pack / hooks-included value"),
    ("listing", "Listing completeness (title / images / bullets / specs)"),
]
REDLINE_OPTIONS = [
    ("low_rating", "Rating below 4.0"),
    ("few_reviews", "Fewer than ~50 reviews"),
    ("no_size", "No size / dimensions information"),
    ("material_unclear", "Material not clearly stated"),
    ("blur_image", "Main image is blurry / looks fake / doesn't show the real product"),
    ("no_bullets", "No selling-point bullets / thin description"),
    ("no_aplus", "No A+ content / video / rich media"),
    ("brand_unfamiliar", "Brand is completely unfamiliar"),
    ("mismatch_title", "Title / images mismatch or keyword-stuffed title"),
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
    ("better_listing", "A clearer, more complete product page"),
    ("nothing", "Nothing — I'd stick with my pick"),
]


def opt(pairs):
    return [{"id": k, "label": v} for k, v in pairs]


def build_context() -> str:
    lines = [
        "# Product brief — Amazon \"Shower Curtain Liner\" Search Journey (6 results on page 1)",
        "",
        "You are shopping on **Amazon.com** for a **shower curtain liner**. You type \"shower curtain liner\" "
        "into the search bar. **Page 1 of the search results shows exactly these 6 products**, each as a normal "
        "search-result card: main image, title, brand, price, star rating with review count, and a few key selling "
        "points. The table below is what those six cards contain.",
        "",
        "**Controlled shelf — read carefully:** all 6 listings are **equally in stock, normally buyable, with the "
        "same delivery terms**. There are no stock warnings, \"only X left\" notices, unavailable items, buy-box "
        "differences, coupons or badges on any card, and you must NOT imagine any — **stock, availability, delivery "
        "and buy-box state are removed from this experiment and must never influence your answers.** Base every "
        "decision only on the product and listing information shown: image/look, title, brand, price, material, "
        "selling points, star rating and review count.",
        "",
        "**You will relive a real click journey** and give the reason at every decision point:",
        "1. On the search page — which card you click into **first**, and what drew your eye.",
        "2. On that product page — which information you inspect, and whether you buy it there; if not, what holds you back.",
        "3. Back on the search page — whether you open a **2nd / 3rd** product, which one, and whether you buy there.",
        "4. If you clicked through all of them and still did not order — which one you would most want to buy anyway, and what blocks you.",
        "",
        "Ratings and review counts are from the product pages (Sep 2026). Listings with very few reviews are flagged "
        "as having a less reliable rating — that is review evidence, not a stock signal.",
        "",
        "| Option | Product | Material | Look & design (from the main image) | Key selling points | Price (USD) | Rating |",
        "|---|---|---|---|---|---|---|",
    ]
    for oid in OPTION_ORDER:
        p = PRODUCTS[oid]
        rating_txt = f"{p['rating']}★ · {p['reviews']:,} reviews"
        if p["reviews"] < 50:
            rating_txt += " (very few — rating less reliable)"
        lines.append(
            f"| {oid} | {p['brand']} — {p['name']} | {p['material']} | {p['look']} | "
            f"{p['points']} | ${p['price']:.2f} | {rating_txt} |"
        )
    lines += [
        "",
        "Notes: prices are USD prices shown on the Amazon search cards for this experiment (Sep 2026). "
        "\"Look & design\" is a short objective description of each official main image. Use only the details in "
        "this brief — do not invent other product facts, stock conditions, badges or discounts.",
    ]
    return "\n".join(lines)


def build_questionnaire() -> dict:
    qs: list[dict] = []

    def single(qid, prompt, construct, pairs, rationale=False):
        q = {"id": qid, "prompt": prompt, "type": "single_choice",
             "construct": construct, "required": True, "options": opt(pairs)}
        if rationale:
            q["askRationale"] = True
        qs.append(q)

    def multi(qid, prompt, construct, pairs):
        qs.append({"id": qid, "prompt": prompt, "type": "multi_choice",
                   "construct": construct, "required": True, "options": opt(pairs)})

    def likert(qid, prompt, construct):
        qs.append({"id": qid, "prompt": prompt, "type": "likert",
                   "construct": construct, "required": True, "minValue": 1, "maxValue": 5})

    # ---------- Stage A: search page, first impression ----------
    first_opts = [(oid, f"{oid} — {PRODUCTS[oid]['brand']} {PRODUCTS[oid]['name']} (${PRODUCTS[oid]['price']:.2f})")
                  for oid in OPTION_ORDER]
    first_opts.append(("none_of_these", "None of these cards — I would not click any of them"))
    single("q_first_click",
           "STAGE 1 — Search results page: which of the 6 product cards would you click into FIRST? "
           "Give a 1-2 sentence reason (what on the card made you click).",
           "first_click", first_opts, rationale=True)
    multi("q_click_drivers",
          "On the search-result card, what specifically made you want to click it first? Select all that apply.",
          "click_drivers", CLICK_DRIVER_OPTIONS)

    # ---------- Stage B: first product detail page ----------
    multi("q_detail_info",
          "STAGE 2 — You are now on that product's detail page. Which information do you actively inspect before "
          "deciding? Select all that apply.",
          "detail_info", DETAIL_INFO_OPTIONS)
    single("q_detail_top",
           "Which single piece of product-page information most influences whether you buy it?",
           "detail_top", DETAIL_INFO_OPTIONS)
    single("q_buy_first",
           "After inspecting this first product page, what do you do?",
           "buy_first", BUY_DECISION_OPTIONS)
    multi("q_notbuy_first",
          "If you would NOT order this first product, what concerns or reasons hold you back? Select all that apply. "
          "If you would buy it, select 'I have no real concern'.",
          "notbuy_first", NOTBUY_OPTIONS)

    # ---------- Stage C: back to search, 2nd / 3rd clicks ----------
    single("q_consider_more",
           "STAGE 3 — You leave the first product page and return to the search results. Do you open another product?",
           "consider_more", CONSIDER_OPTIONS)
    single("q_second_click",
           "Which product do you click into SECOND? Pick an option DIFFERENT from your first click, and give a "
           "1-sentence reason. If you already ordered or would not open another, choose the matching skip/none option.",
           "second_click", NEXT_CLICK_OPTIONS, rationale=True)
    single("q_buy_second",
           "After inspecting this second product page, what do you do? (Skip if you already ordered earlier.)",
           "buy_second", BUY_DECISION_SKIP)
    multi("q_notbuy_second",
          "If you would NOT order the second product, what concerns hold you back? Select all that apply. "
          "Skip if you already ordered.",
          "notbuy_second", NOTBUY_SKIP_OPTIONS)
    single("q_third_click",
           "If you still have not ordered, which product do you click into THIRD? Pick an option DIFFERENT from your "
           "first two clicks, and give a 1-sentence reason; otherwise choose skip/none.",
           "third_click", NEXT_CLICK_OPTIONS, rationale=True)
    single("q_buy_third",
           "After inspecting this third product page, what do you do? (Skip if you already ordered earlier.)",
           "buy_third", BUY_DECISION_SKIP)
    multi("q_notbuy_third",
          "If you would NOT order the third product, what concerns hold you back? Select all that apply. "
          "Skip if you already ordered.",
          "notbuy_third", NOTBUY_SKIP_OPTIONS)

    # ---------- Stage D: fallback after clicking through all ----------
    fallback_opts = [(oid, f"{oid} — {PRODUCTS[oid]['brand']} (${PRODUCTS[oid]['price']:.2f})")
                     for oid in OPTION_ORDER]
    fallback_opts.append(("none_of_these", "None — even after looking at all 6, I would not want any of them"))
    single("q_fallback",
           "STAGE 4 — Imagine you have clicked through ALL 6 products and ended up ordering none. Looking back, "
           "which ONE would you most want to buy anyway? Give a 1-2 sentence reason.",
           "fallback_favorite", fallback_opts, rationale=True)
    multi("q_fallback_blocker",
          "What stops you from actually ordering that favorite product? Select all that apply. "
          "If you would in fact order it, select 'Nothing blocks me'.",
          "fallback_blocker", FALLBACK_BLOCKER_OPTIONS)

    # ---------- Stage E: per-product final attitude ----------
    for oid in OPTION_ORDER:
        p = PRODUCTS[oid]
        multi(f"q_reject_{oid}",
              f"FINAL ATTITUDE toward Option {oid} ({p['brand']}, ${p['price']:.2f}): if you did NOT finally order "
              f"it, select every reason that applies. If you finally ordered it, select 'This is the one I finally "
              f"ordered'; if it is your favorite but you held off, select that option.",
              f"reject_{oid}", REJECT_OPTIONS)

    # ---------- Stage F: shelf position & listing optimization ----------
    single("q_page_browse",
           "On Amazon, how far into the search results would you still click in and BROWSE a shower curtain liner?",
           "page_browse", PAGE_OPTIONS)
    single("q_page_buy",
           "On Amazon, how far into the search results would you still place an ORDER for a shower curtain liner?",
           "page_buy", PAGE_OPTIONS)
    single("q_factor_most", "Across this whole journey, what mattered MOST in your decision?", "factor_most", FACTOR_OPTIONS)
    single("q_factor_second", "What was your SECOND most important factor?", "factor_second", FACTOR_OPTIONS)
    for qid, prompt in [
        ("q_importance_title", "A complete, clear product TITLE (size, material, key feature) matters to me."),
        ("q_importance_image", "CLEAR MAIN IMAGES that show the real look & effect matter to me."),
        ("q_importance_bullets", "Selling-point BULLETS that explain benefits matter to me."),
        ("q_importance_aplus", "A+ content / product video / brand story pages influence my decision."),
        ("q_importance_attr", "Complete ATTRIBUTES / size & spec tables matter to me."),
        ("q_importance_price", "PRICE and value for money matter to me."),
        ("q_importance_reviews", "RATINGS + review count + review photos influence my decision."),
        ("q_importance_trust", "Brand trust and safety certifications (BPA-free / PVC-free / odor-free) matter to me."),
    ]:
        likert(qid, prompt, qid)
    multi("q_listing_redline",
          "Which listing problems would make you EXCLUDE a shower curtain liner immediately? Select all that apply.",
          "listing_redline", REDLINE_OPTIONS)
    single("q_material_pref", "Which liner material do you personally prefer?", "material_pref", MATERIAL_OPTIONS)
    single("q_transparency_pref", "Which transparency level do you prefer for a liner?", "transparency_pref", TRANSPARENCY_OPTIONS)
    single("q_badge_effect",
           "Hypothetically, if one result carried an \"Amazon's Choice\" or \"Best Seller\" badge, would it change what you click?",
           "badge_effect", BADGE_OPTIONS)
    single("q_switch_trigger",
           "What would most likely make you switch from your first click to a different product?",
           "switch_trigger", SWITCH_OPTIONS)
    likert("q_price_acceptance",
           "The price of the product I most want is acceptable for what it offers.", "price_acceptance")
    likert("q_purchase_intent",
           "I would realistically buy a shower curtain liner like this within the next 3 months.", "purchase_intent")

    return {
        "schemaVersion": "1.0",
        "id": "shower_liner_6asin_journey_v1",
        "title": "Amazon Shower Curtain Liner Click-Journey Survey (6 results)",
        "description": (
            "Simulates the Amazon search-to-purchase journey across 6 shower curtain liner results: "
            "first click + drivers on the search page, product-page information inspection, buy/not-buy "
            "decisions and concerns at the 1st/2nd/3rd click, fallback favorite after clicking through all, "
            "per-product final attitude, search-page tolerance, decision factors, and listing-optimization "
            "importance/red-lines. Stock, availability, delivery and buy-box state are held identical and "
            "excluded as factors; one missing source price is filled with a controlled assumed price."
        ),
        "questions": qs,
    }


def build_instruction() -> str:
    return """# Amazon Shower Curtain Liner — Click-Journey Survey

We are simulating a **real Amazon shopping trip**. You need a **shower curtain liner**. You search for it on
Amazon and **page 1 shows 6 products**. All 6 are equally in stock and buyable with the same delivery terms —
**ignore stock, availability, badges, coupons and delivery differences completely**; they are deliberately
removed from this experiment.

Answer as yourself, step by step, as if you were actually clicking through Amazon:

1. **First click** — which of the 6 cards you open first, and a short reason.
2. **Product page** — what information you inspect, and whether you buy there; if not, your real concerns.
3. **2nd / 3rd clicks** — after going back, which other products you open, whether you buy there, and why not.
   Each later click must be a **different** product from your earlier clicks.
4. **Fallback** — if you clicked all 6 and bought nothing, which one you most want anyway, and what blocks you.
5. **Final attitude** — for every product you did not order, check every genuine rejection reason.
6. Then answer the shelf-position and listing-element questions.

## How to answer

- Read the brief before you start; use only the information given there — do not invent facts.
- Answer every required question; multiple-choice questions may need several boxes.
- Where a question asks for a reason, write 1-2 concrete sentences tied to that product's card or page.
- Rating scales: a whole number from 1 (strongly disagree) to 5 (strongly agree).
- If a question does not apply because you already ordered earlier, choose the explicit skip option.
- Give the option id (letters/keys) for choice questions.
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
    import re
    # semantic check now anchors on q_first_click (journey entry decision)
    text = text.replace(
        '# Valid q_choice option ids (must match input/questionnaire.yaml).',
        '# Valid q_first_click option ids (must match input/questionnaire.yaml).')
    text = re.sub(
        r'ALLOWED_CHOICES = \{[^}]*\}',
        'ALLOWED_CHOICES = {\n    "A",\n    "B",\n    "C",\n    "D",\n    "E",\n    "F",\n    "none_of_these",\n}',
        text, count=1)
    text = text.replace(
        '"""Task-specific: q_choice must be a valid option id with a real rationale."""',
        '"""Task-specific: q_first_click must be a valid option id with a real rationale."""')
    text = text.replace('== "q_choice"', '== "q_first_click"')
    text = text.replace('missing q_choice answer', 'missing q_first_click answer')
    text = text.replace('q_choice value', 'q_first_click value')
    text = text.replace('q_choice rationale', 'q_first_click rationale')
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
tags = [ "consumer goods", "shower curtain liner", "click journey", "search to purchase", "listing optimization", "rejection reasons",]

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
    q = build_questionnaire()
    print("task written:", TASK)
    print("instrument:", q["id"], "| questions:", len(q["questions"]))


def _dict_to_yaml(d: dict) -> str:
    import yaml
    return yaml.safe_dump(d, allow_unicode=True, sort_keys=False, width=120)


if __name__ == "__main__":
    main()
