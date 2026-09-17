# -*- coding: utf-8 -*-
"""
MatrAIx TOP30 马桶刷 2×2 因子对照实验 —— 任务目录构建脚本
================================================================
因子 A（品牌）：匿名 P01–P30  vs  原品牌
因子 B（评分）：显示评分+评价数 vs 不显示
4 臂：
  arm-anon-rating     匿名+评分
  arm-anon-norating   匿名+无评分
  arm-brand-rating    品牌+评分
  arm-brand-norating  品牌+无评分
每臂任务目录遵循官方 survey 任务结构：
  task.toml / instruction.md / reporting.json / persona_strategy.json
  input/context.md（30 款货架表）/ input/questionnaire.yaml（17 题扩充问卷）
画像策略：仅 amazon 源（97,915 人）+ 北美 region 过滤 + 固定 seed（由 job 生成脚本传入 42）。
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path("/Users/bunnychen/Documents/GitProjects/MatrAIx-Persona-8B")
DATA = REPO / "results" / "toilet-brush-top30" / "toilet_brush_top30_simulation.json"

# ---------------------------------------------------------------- 英文货架文案
# 每个产品：anon 名（不含品牌）、brand 名（含品牌）、材质、外观（图片识别客观描述）、卖点
EN = {
 "P01": dict(
   brand="Clorox",
   anon="Corner Toilet Bowl Brush with Under Rim Scrubber (White)",
   material="Antibacterial nylon bristles; rubber non-slip handle",
   look="White set with dark-gray non-slip grip and base trim; round bristle head; long slim handle; open cup-style corner caddy.",
   points="Corner caddy saves space; dedicated under-rim scrubber head; antibacterial bristles; non-slip grip"),
 "P02": dict(
   brand="FORASTO",
   anon="2-in-1 Toilet Brush & Plunger Set (Light Gray)",
   material="Nylon brush head; rubber plunger cup; plastic",
   look="Light-gray freestanding base holding a black rubber plunger and a white brush rod; compact upright design.",
   points="2-in-1 brush + plunger saves space; ideal for apartments and small bathrooms; long handles"),
 "P03": dict(
   brand="MR.SIGA",
   anon="Toilet Plunger and Bowl Brush Combo (Black)",
   material="Rubber plunger cup; nylon brush; metal-accent rods",
   look="Matte-black combo; plunger and slim cleaning brush stored in one black base stand; long handles.",
   points="Heavy-duty plunger; 2-in-1 combo; sleek matte black finish"),
 "P04": dict(
   brand="MR.SIGA",
   anon="Toilet Bowl Brush and Holder (Black)",
   material="Nylon bristles; plastic",
   look="Black cylindrical holder with blue accents; long brush leans on holder clips; gray-white bristle head.",
   points="Sturdy long handle; stable cylindrical holder"),
 "P05": dict(
   brand="oshang",
   anon="Disposable Toilet Brush System with 14 Refills (White)",
   material="Disposable sponge heads (blue-striped); plastic handle",
   look="White handle with gray grip and blue-striped sponge head; white base with gray lid and slots; stacks of replacement heads beside it.",
   points="Disposable heads keep hands clean; hygienic; deep cleaning; includes 14 refills"),
 "P06": dict(
   brand="HAMITOR",
   anon="Toilet Bowl Brush Holder Set with S-Shaped Bristles (Gray)",
   material="Nylon bristles; plastic",
   look="Light-gray openwork base holding a dark-gray long-handled brush; black bristle head; functional design.",
   points="S-shaped bristles reach dead corners; openwork base dries fast; splash-resistant"),
 "P07": dict(
   brand="OXO",
   anon="Compact Toilet Brush with Automatic Canister Door (White)",
   material="Nylon bristles; plastic",
   look="White standing canister base with blue-bristle brush head; minimal compact design.",
   points="Canister door opens automatically when lifted; compact for small bathrooms; non-slip handle"),
 "P08": dict(
   brand="FAZMoss",
   anon="2-Pack Pumice Stone Toilet Cleaner with Extra Long Handle (Gray)",
   material="Pumice stone heads; plastic handles",
   look="Two long-handled pumice cleaning rods; blue-and-white retail box beside them.",
   points="Removes hard-water stains and limescale; harmless to porcelain; extra-long handle"),
 "P09": dict(
   brand="Holaloha",
   anon="Toilet Brush and Holder Set, 2-Pack (White)",
   material="Nylon bristles; plastic",
   look="Two white brush sets with gray anti-slip grips; one fluffy round bristle head, the other stored in an openwork base.",
   points="Space-saving; dense bristles for 360° cleaning; 2-pack value"),
 "P10": dict(
   brand="Holaloha",
   anon="Toilet Brush and Holder Set, 3-Pack with 3 Replacement Heads (White)",
   material="Nylon bristles; plastic",
   look="Three white brush sets with gray handles plus three replacement heads; compact openwork bases.",
   points="Space-saving; 3 sets + 3 replacement heads; multi-bathroom value"),
 "P11": dict(
   brand="SetSail",
   anon="2-Pack Toilet Brush and Plunger Set, Semi-Hidden (Black)",
   material="Rubber plunger cups; nylon brushes; plastic",
   look="Two matching glossy-black rounded bases with slim upright rods; clean modern silhouette.",
   points="Semi-hidden plungers keep the bathroom tidy; 2-pack; one-piece storage"),
 "P12": dict(
   brand="LOVLOY",
   anon="Toilet Plunger and Brush Set with Ventilated Holder (Gray)",
   material="Rubber plunger cup; nylon brush; plastic",
   look="Gray-black storage base holding two rods — rubber plunger cup and brush slot; ventilated design.",
   points="Ventilated holder for quick drying; heavy-duty plunger; fits 5.3-inch toilet drains"),
 "P13": dict(
   brand="Sellemer",
   anon="Silicone Toilet Brush with Ventilated Holder (Pearl White)",
   material="Silicone bristles; plastic",
   look="Long white rod with silicone brush head; white case with black base.",
   points="Flexible silicone head won't scratch porcelain; ventilated slot base for quick drying"),
 "P14": dict(
   brand="AONEZ",
   anon="Toilet Brush and Holder, 3-Pack Compact (Black)",
   material="Sponge heads; stainless steel handles; plastic",
   look="Three sets; one leaning with a silver metal rod and black handle; two stored in dark-gray cylindrical bases.",
   points="Compact size hides easily; stainless steel handles; drip-proof; 3-pack value"),
 "P15": dict(
   brand="HAMITOR",
   anon="Toilet Bowl Brush Holder Set, Curved Design (White)",
   material="Nylon bristles; plastic",
   look="Gray-white set; curved handle with anti-slip texture and dense black bristles; white base with gray band and openwork slot.",
   points="Curved handle reaches under the rim; compact hidden storage; RV-friendly"),
 "P16": dict(
   brand="uptronic",
   anon="Toilet Brush and Holder, 2-Pack, Extra Long Handle (Bronze)",
   material="Nylon bristles; plastic and metal",
   look="Two matte dark-bronze cylindrical covered holders with long-handled brushes; symmetrical minimal design.",
   points="Extra-long handle; covered storage; durable; 2-pack"),
 "P17": dict(
   brand="Holaloha",
   anon="Toilet Brush and Holder Set with Crevice Brushes (White)",
   material="Nylon bristles; plastic",
   look="White set with gray accents; main long-handled brush plus two small detail brushes and a white base.",
   points="Includes crevice brushes for tight spots; dense-bristle 360° cleaning; budget price"),
 "P18": dict(
   brand="MR.SIGA",
   anon="Toilet Plunger and Brush Combo, 2-Set (Black)",
   material="Rubber plunger cups; nylon brushes; plastic",
   look="Two matching glossy-black plunger sets with long handles and black base stands.",
   points="Heavy-duty plunger; 2 complete sets for multiple bathrooms"),
 "P19": dict(
   brand="SetSail",
   anon="Toilet Brush and Holder with Self-Closing Lid, 4-Pack (White)",
   material="Nylon bristles; plastic; metal connector rods",
   look="Four white sets with metal-rod long handles and square base cases; the first case lid is open showing inner storage.",
   points="Self-closing lid hides the brush; ventilated; extra-long handle; 4-pack"),
 "P20": dict(
   brand="uptronic",
   anon="Toilet Brush with Extra Long Handle and Covered Holder (Brown)",
   material="Nylon bristles; plastic",
   look="Dark-brown cylindrical covered holder with a matching long-handled brush; brush head stored inside.",
   points="Extra-long handle; durable bristles; covered storage"),
 "P21": dict(
   brand="OSAMEDA",
   anon="3-in-1 Toilet Brush and Plunger Set with Crevice Brushes, 2-Pack (Black)",
   material="Rubber plunger cups; nylon brushes; metal rods",
   look="Two black plunger sets with long rods and bases; two extra slim metal-rod crevice brushes beside them; glossy black.",
   points="3-in-1 brush + plunger + crevice tools; 2-pack; extra tools for tight spots"),
 "P22": dict(
   brand="Clorox",
   anon="Toilet Plunger and Bowl Brush Combo Set with Caddy, 2-Pack (White/Gray)",
   material="Rubber plunger cup; nylon brush; plastic",
   look="Two matching sets; white handles with black grips, black rubber plunger cups, freestanding white caddies.",
   points="Heavy-duty plunger; freestanding caddy; 2-pack"),
 "P23": dict(
   brand="Wsedor",
   anon="Toilet Brush and Holder, 2-Pack, 304 Stainless Steel Long Handle (Silver)",
   material="304 stainless steel; plastic",
   look="Two matching matte-silver stainless cylinders with slim metal brush rods extending from the top; modern minimalist.",
   points="304 stainless steel handles; ergonomic; elegant and durable; 2-pack"),
 "P24": dict(
   brand="Dealsgogo",
   anon="Wall-Mounted Silicone Toilet Brush for RVs (Gray)",
   material="Silicone bristles; plastic",
   look="Light-gray long-handled brush with a wall-mount base; hanging hole at the rod top; close-up shows a threaded rod joint.",
   points="Silicone won't damage toilets; wall-mounted; anti-roll and anti-drip; made for RVs and travel trailers"),
 "P25": dict(
   brand="FORASTO",
   anon="2-in-1 Toilet Brush and Plunger Set with Cleaning Gloves, 2-Pack (Cream White)",
   material="Rubber plunger cups; nylon brushes; plastic",
   look="Two cream-white integrated sets with black plunger heads; two blue rubber cleaning gloves included as a bonus.",
   points="2-in-1; extended-handle plunger; includes 2 pairs of cleaning gloves; 2-pack"),
 "P26": dict(
   brand="HAMITOR",
   anon="Toilet Bowl Brush Holder Set, 2-Pack, Modern Design (White)",
   material="Sponge heads; plastic",
   look="White brush with a black sponge head and a circular splash guard on the rod; white cylindrical base; shown in use and stored states.",
   points="Modern design; splash guard; RV-friendly; 2-pack"),
 "P27": dict(
   brand="Hohoky",
   anon="Disposable Toilet Brush Cleaning System with 50 Refill Pads (White)",
   material="Disposable sponge pads (blue-white striped); plastic",
   look="White handle and wall-mount base; stacks of blue-white striped refill pads; blue retail box in the background.",
   points="Disposable heads — hygienic; 50 refill pads; wall-mounted; no messy brush cleaning"),
 "P28": dict(
   brand="simplehuman",
   anon="Toilet Brush with Stainless Steel Caddy (White)",
   material="Nylon bristles; stainless steel; plastic",
   look="White brush with silver metal parts and gray bristles; long handle with a curved stainless base stand.",
   points="Stainless steel caddy; classic premium design"),
 "P29": dict(
   brand="SAVEGA",
   anon="2-in-1 Toilet Bowl Brush and Plunger Set with Gold Caddy",
   material="Rubber plunger cup; nylon brush; metal rods",
   look="Dark-gray two-slot base with metal rods and black grips; teal retail box; circular icons show grip color options.",
   points="Gold caddy adds a premium look; 2-in-1; stylish design"),
 "P30": dict(
   brand="HAMITOR",
   anon="2-in-1 Toilet Plunger and Brush Set, Stainless Steel with Gold Accents",
   material="Rubber plunger cup; nylon bristles; stainless steel",
   look="Gold-and-black base; plunger with a black-yellow segmented handle and a brush with dense black bristles; premium look.",
   points="Stainless steel construction; curved bristles for deep cleaning; heavy-duty unclogging; compact hideaway"),
}

# 评分（评分臂显示；低样本加可信度注记）
RATING = {
 "P01": "4.6★ · 5,865 reviews", "P02": "4.3★ · 7,628 reviews", "P03": "4.4★ · 78,059 reviews",
 "P04": "4.5★ · 18,880 reviews", "P05": "4.5★ · 4,881 reviews", "P06": "4.6★ · 2,620 reviews",
 "P07": "4.7★ · 18,325 reviews", "P08": "4.6★ · 6,171 reviews", "P09": "4.2★ · 1,436 reviews",
 "P10": "4.5★ · 2,204 reviews", "P11": "4.4★ · 7,796 reviews", "P12": "4.7★ · 1,475 reviews",
 "P13": "4.0★ · 36,538 reviews", "P14": "4.3★ · 10,656 reviews", "P15": "4.4★ · 7,393 reviews",
 "P16": "4.5★ · 4,627 reviews", "P17": "4.3★ · 173 reviews (very few — rating less reliable)",
 "P18": "4.5★ · 11,972 reviews", "P19": "4.5★ · 5,202 reviews", "P20": "4.4★ · 4,780 reviews",
 "P21": "4.4★ · 740 reviews", "P22": "4.5★ · 7,722 reviews", "P23": "4.4★ · 272 reviews (very few — rating less reliable)",
 "P24": "4.3★ · 978 reviews", "P25": "4.4★ · 1,335 reviews", "P26": "4.4★ · 1,648 reviews",
 "P27": "4.7★ · 1,725 reviews", "P28": "4.4★ · 5,347 reviews", "P29": "4.0★ · 40 reviews (extremely few — rating unreliable)",
 "P30": "4.4★ · 1,039 reviews",
}

PRICE = {"P01":8.99,"P02":14.99,"P03":23.99,"P04":19.99,"P05":9.99,"P06":12.73,"P07":19.90,
 "P08":8.99,"P09":8.99,"P10":12.99,"P11":29.99,"P12":15.29,"P13":11.99,"P14":29.99,
 "P15":11.99,"P16":19.99,"P17":6.99,"P18":38.99,"P19":33.99,"P20":11.69,"P21":20.99,
 "P22":22.40,"P23":29.99,"P24":9.99,"P25":26.99,"P26":23.99,"P27":26.99,"P28":34.99,
 "P29":24.99,"P30":59.99}

def load_sim() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))

def build_context(arm: str) -> str:
    show_rating = arm.endswith("-rating")
    show_brand = arm.startswith("brand")
    head = (
        "# Product brief — Toilet Brush Shopping Shelf (30 options)\n\n"
        "You are shopping for a **toilet brush and holder set** for your bathroom. "
        "The following **30 sets** are on the shelf, like an online store product page — "
        "you can see each product's **look & design**, specs and price. "
        "Pick the **one** you would actually buy, or choose \"None of these\" if nothing fits.\n\n"
    )
    if show_rating:
        head += "Ratings and review counts come from the product pages (Sep 2026). "
        head += "Products with very few reviews are marked as less reliable.\n\n"
    head += "| Option id | Product | Material | Look & design | Key selling points | Price (USD)"
    if show_rating:
        head += " | Rating"
    head += " |\n|---|---|---|---|---|---"
    if show_rating:
        head += "|---"
    head += "|\n"
    rows = []
    for pid in [f"P{i:02d}" for i in range(1, 31)]:
        e = EN[pid]
        product = f"{e['brand']} {e['anon']}" if show_brand else e["anon"]
        cells = [pid, product, e["material"], e["look"], e["points"], f"${PRICE[pid]:.2f}"]
        if show_rating:
            cells.append(RATING[pid])
        rows.append("| " + " | ".join(cells) + " |")
    body = "\n".join(rows)
    tail = (
        "\n\n**None of these** — if none of the 30 fits your needs or budget.\n\n"
        "Notes: prices are USD reference prices from Amazon.com listings (Sep 2026). "
        "Look & design is a short objective description of each product's appearance based on its official product image. "
        "Use only the details in this brief — do not invent other product facts.\n"
    )
    return head + body + tail

# ---------------------------------------------------------------- 问卷（17 题）
Q_SHARED = [
 dict(id="q_price_acceptance",
      prompt="The price of the product I chose is acceptable for what it offers.",
      type="likert", construct="price_acceptance", required=True, minValue=1, maxValue=5),
 dict(id="q_purchase_intent",
      prompt="I would realistically buy this toilet brush set within the next 3 months.",
      type="likert", construct="purchase_intent", required=True, minValue=1, maxValue=5),
 dict(id="q_factor_most",
      prompt="What mattered MOST in your choice?",
      type="single_choice", construct="factor_most", required=True,
      options=[
        dict(id="price_value", label="Price / value for money"),
        dict(id="cleaning", label="Cleaning performance (brush head, under-rim / deep cleaning)"),
        dict(id="hygiene", label="Hygiene (disposable heads, quick-drying holder)"),
        dict(id="design", label="Design / looks / color"),
        dict(id="brand", label="Brand trust"),
        dict(id="material", label="Material quality / durability"),
        dict(id="holder", label="Holder / storage design (caddy, hidden, wall-mount)"),
        dict(id="pack", label="Pack size / multi-pack value"),
        dict(id="reviews", label="Ratings and reviews"),
        dict(id="function_combo", label="Extra functions (plunger combo, crevice tools)"),
      ]),
 dict(id="q_factor_second",
      prompt="What was your SECOND most important factor?",
      type="single_choice", construct="factor_second", required=True,
      options=[
        dict(id="price_value", label="Price / value for money"),
        dict(id="cleaning", label="Cleaning performance (brush head, under-rim / deep cleaning)"),
        dict(id="hygiene", label="Hygiene (disposable heads, quick-drying holder)"),
        dict(id="design", label="Design / looks / color"),
        dict(id="brand", label="Brand trust"),
        dict(id="material", label="Material quality / durability"),
        dict(id="holder", label="Holder / storage design (caddy, hidden, wall-mount)"),
        dict(id="pack", label="Pack size / multi-pack value"),
        dict(id="reviews", label="Ratings and reviews"),
        dict(id="function_combo", label="Extra functions (plunger combo, crevice tools)"),
      ]),
 dict(id="q_importance_price",
      prompt="Price / value for money is important to me when choosing a toilet brush.",
      type="likert", construct="importance_price", required=True, minValue=1, maxValue=5),
 dict(id="q_importance_function",
      prompt="Cleaning function (brush head design, deep / under-rim cleaning) is important to me.",
      type="likert", construct="importance_function", required=True, minValue=1, maxValue=5),
 dict(id="q_importance_appearance",
      prompt="Appearance / design / color of the set matters to me.",
      type="likert", construct="importance_appearance", required=True, minValue=1, maxValue=5),
 dict(id="q_importance_hygiene",
      prompt="Hygiene and quick-drying holder design matter to me.",
      type="likert", construct="importance_hygiene", required=True, minValue=1, maxValue=5),
 dict(id="q_importance_reviews",
      prompt="Ratings and review counts influence my purchase decision.",
      type="likert", construct="importance_reviews", required=True, minValue=1, maxValue=5),
 dict(id="q_importance_brand",
      prompt="Brand trust matters to me when buying a toilet brush.",
      type="likert", construct="importance_brand", required=True, minValue=1, maxValue=5),
 dict(id="q_material_pref",
      prompt="Which brush head material do you prefer?",
      type="single_choice", construct="material_pref", required=True,
      options=[
        dict(id="silicone", label="Silicone (gentle, won't scratch)"),
        dict(id="nylon_bristles", label="Nylon bristles (classic, tough)"),
        dict(id="disposable_sponge", label="Disposable sponge heads (hygienic)"),
        dict(id="pumice_stone", label="Pumice stone (hard-water stains)"),
        dict(id="stainless_steel", label="Stainless steel construction"),
        dict(id="no_preference", label="No strong preference"),
      ]),
 dict(id="q_format_pref",
      prompt="Which product format do you prefer?",
      type="single_choice", construct="format_pref", required=True,
      options=[
        dict(id="single_brush_set", label="Single toilet brush + holder"),
        dict(id="brush_plunger_combo", label="Brush + plunger combo"),
        dict(id="disposable_system", label="Disposable head system"),
        dict(id="pumice_cleaner", label="Pumice stone cleaner"),
        dict(id="no_preference", label="No strong preference"),
      ]),
 dict(id="q_pack_pref",
      prompt="Which pack size do you prefer?",
      type="single_choice", construct="pack_pref", required=True,
      options=[
        dict(id="single", label="Single (1 set)"),
        dict(id="two_pack", label="2-pack"),
        dict(id="three_or_more", label="3-pack or more"),
        dict(id="no_preference", label="No strong preference"),
      ]),
 dict(id="q_refill_acceptance",
      prompt="For a disposable-head system, I would accept buying replacement heads regularly.",
      type="likert", construct="refill_acceptance", required=True, minValue=1, maxValue=5),
 dict(id="q_badge_effect",
      prompt="If one product on the shelf carried an \"Amazon's Choice\" badge, would it influence you?",
      type="single_choice", construct="badge_effect", required=True,
      options=[
        dict(id="yes_strongly", label="Yes, a lot"),
        dict(id="yes_somewhat", label="Yes, somewhat"),
        dict(id="neutral", label="Neutral"),
        dict(id="unlikely", label="Probably not"),
        dict(id="no_effect", label="No, it wouldn't affect me"),
      ]),
 dict(id="q_switch_trigger",
      prompt="What would most likely make you switch to a different option on this shelf?",
      type="single_choice", construct="switch_trigger", required=True,
      options=[
        dict(id="lower_price", label="A lower price"),
        dict(id="better_rating", label="A higher rating / more reviews"),
        dict(id="better_look", label="Better looks / design"),
        dict(id="better_function", label="Better cleaning function / features"),
        dict(id="better_value", label="Better value (multi-pack, refills)"),
        dict(id="nothing", label="Nothing — I'm confident in my choice"),
      ]),
]

def build_questionnaire(arm: str) -> dict:
    show_brand = arm.startswith("brand")
    labels = []
    for pid in [f"P{i:02d}" for i in range(1, 31)]:
        e = EN[pid]
        name = f"{e['brand']} {e['anon']}" if show_brand else e["anon"]
        labels.append(dict(id=pid, label=f"{pid} — {name} (${PRICE[pid]:.2f})"))
    labels.append(dict(id="none_of_these", label="None of these — I would not buy any of them"))
    q_choice = dict(
        id="q_choice",
        prompt="Which toilet brush set would you buy for your bathroom? Give a 2-3 sentence reason for your choice.",
        type="single_choice", construct="brush_choice", required=True, askRationale=True,
        options=labels,
    )
    return dict(
        schemaVersion="1.0",
        id=f"toilet_brush_top30_{arm.replace('-', '_')}_v1",
        title="Toilet Brush Top30 Shopping Choice Survey (30 options)",
        description=(
            "Which toilet brush set the persona would actually buy from a 30-option shelf "
            "(plus 'none'), which factors drive the decision, and how price / brand / ratings "
            "shape the choice."
        ),
        questions=[q_choice] + Q_SHARED,
    )

# ---------------------------------------------------------------- 其他任务文件
INSTRUCTION = """# Toilet Brush Top30 Shopping Choice Survey

We're simulating a **shopping decision**. You are buying a **toilet brush and holder set** for your bathroom.
A shelf of **30 toilet brush sets** is in front of you — like shopping on an online store. Read the product cards
(price, material, look & design, selling points{rating_note}), then pick **the one** you would actually buy,
or choose **"None of these"** if nothing fits your needs or budget.

## How to answer

- Read the brief before you start.
- Answer every required question.
- For multiple-choice, use the listed option ids.
- For rating scales, use a whole number in the given range.
- Give the answer alone unless a question also asks for a short reason or confidence.
"""

TASK_TOML = """version = "1.0"
artifacts = [ "/app/output",]

[task]
name = "application/{folder}"

[metadata]
difficulty = "easy"
type = "survey"
domain = "commerce"
tags = [ "consumer goods", "toilet brush", "choice", "price sensitivity", "shopping simulation", "factorial experiment",]

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
"""

REPORTING = '{"schemaVersion": "1.0", "contextRules": []}\n'

PERSONA_STRATEGY = {
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

def write_task(arm: str) -> None:
    folder = f"survey_toilet-brush-top30-{arm}"
    tdir = REPO / "application" / "tasks" / folder
    (tdir / "input").mkdir(parents=True, exist_ok=True)
    rating_note = ", ratings and review counts" if arm.endswith("-rating") else ""
    (tdir / "instruction.md").write_text(
        INSTRUCTION.format(rating_note=rating_note), encoding="utf-8")
    (tdir / "task.toml").write_text(TASK_TOML.format(folder=folder), encoding="utf-8")
    (tdir / "reporting.json").write_text(REPORTING, encoding="utf-8")
    (tdir / "persona_strategy.json").write_text(
        json.dumps(PERSONA_STRATEGY, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (tdir / "input" / "context.md").write_text(build_context(arm), encoding="utf-8")

    import yaml
    q = build_questionnaire(arm)
    (tdir / "input" / "questionnaire.yaml").write_text(
        yaml.safe_dump(q, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8")
    print("wrote", tdir)

def main() -> None:
    arms = ["anon-rating", "anon-norating", "brand-rating", "brand-norating"]
    for arm in arms:
        write_task(arm)
    # 校验：30 行货架、31 个选项、17 题
    for arm in arms:
        ctx = build_context(arm)
        assert ctx.count("| P") >= 30, arm
        q = build_questionnaire(arm)
        assert len(q["questions"]) == 17, (arm, len(q["questions"]))
        assert len(q["questions"][0]["options"]) == 31, arm
        print("check ok:", arm, "| context rows:", ctx.count("\n| p"), "| questions:", len(q["questions"]))

if __name__ == "__main__":
    main()
