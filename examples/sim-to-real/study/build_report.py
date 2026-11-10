"""Build the offline report from the frozen, aggregate scoring files."""

import json
import math
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent
FOLDERS = ("01_首轮归档", "02_模型对比", "03_提示与背景", "06_北美电商选品")
SURVEYS = {"shed": "物价上涨与消费应对", "pew": "网络诈骗风险", "anes": "联邦公共支出"}
ARMS = dict(zip("ABC", ("仅给调查情境", "加入年龄和学历", "年龄学历＋四项合成人格"), strict=True))
MODELS = {"flash": "DeepSeek Flash", "pro": "DeepSeek Pro", "qwen": "内网 Qwen"}
PROMPTS = ("扮演受访者", "预测受访者")
BACKGROUNDS = ("粗分年龄学历", "细分年龄学历", "贴题真人背景", "贴题背景＋合成人格")
SHOP = {"origin": "产地、价格与评分", "packaging": "啤酒包装与拒买", "pew": "网购习惯"}
SHOP_SETTINGS = {
    "P0+B1": "扮演受访者 · 年龄学历", "P0+B3": "扮演受访者 · 贴题背景",
    "P1+B1": "预测受访者 · 年龄学历", "P1+B3": "预测受访者 · 贴题背景",
    "统计基线": "真人统计对照",
}
CONSUMER = dict(zip(
    ("INF3_a", "INF3_b", "INF3_c", "INF3_d", "INF3_e", "INF3_f", "INF5"),
    ("改买便宜商品", "少用或停用某些商品", "减少储蓄", "增加借款", "推迟大额购买",
     "增加工时或另找工作", "预期涨价而提前大额购买"), strict=True,
))
SCAMS = dict(zip(
    ("OSCAM_PROB", "OSCAM_PLAT_a", "OSCAM_PLAT_b", "OSCAM_PLAT_c", "OSCAM_PLAT_d"),
    ("美国整体的网络诈骗风险", "电话和短信诈骗", "电子邮件诈骗", "社交媒体诈骗", "购物网站或应用诈骗"),
    strict=True,
))
SPENDING = {f"V241{k}": f"{v}支出" for k, v in (
    (264, "公立学校"), (267, "边境安全"), (270, "治安"), (273, "福利"),
    (276, "公路建设与维修"), (282, "环境保护"),
)}
TITLES = {**CONSUMER, **SCAMS, **SPENDING}
OPTIONS = {
    "Yes": "是", "No": "否", "Major problem": "重大问题", "Minor problem": "小问题",
    "Not a problem": "不是问题", "Not sure": "不确定", "Increased": "增加", "Decreased": "减少",
    "Kept the same": "维持现状",
}
SHOP_ITEMS = {
    "China": "选中国产品", "United States": "选美国产品", "cheaper": "选更便宜的一款",
    "higher-rated": "选评分更高的一款", "ONLSHOP1_a": "是否用电脑网购",
    "ONLSHOP1_b": "是否用平板网购", "ONLSHOP1_c": "是否用手机网购",
    "SHOP4": "一般更喜欢线上还是到店购物", "ONLSHOP3": "是否关注网红或内容创作者",
    "ONLSHOP4": "是否曾在看达人内容后买过相关商品",
}
CARD_FIELDS = {
    "water_conserving": "节水", "energy_conserving": "节能", "waste_reduction": "减废", "local": "本地生产",
}


def read(folder):
    return json.loads((ROOT / folder / "results.json").read_text())


def comparison(before, after, gain, interval):
    return {"reference": before, "candidate": after, "gain_pp": gain, "ci95": interval}


def item(title, options, human, settings, **details):
    # Keep the same option order and assert that chart distributions reproduce the recorded scores.
    for setting in settings.values():
        predicted = setting["pct"]
        assert len(options) == len(human) == len(predicted), title
        for distribution in (human, predicted):
            assert all(-1e-8 <= value <= 100 + 1e-8 for value in distribution), title
            assert math.isclose(sum(distribution), 100, abs_tol=1e-7), title
        error = sum(abs(a - b) for a, b in zip(human, predicted, strict=True)) / 2
        assert math.isclose(error, setting["error"], abs_tol=1e-7), title
    return {"title": title, "options": options, "human": human, "settings": settings, **details}


def scope(items, scores, pairs, **details):
    for key, row in scores.items():
        assert math.isclose(row["error"], mean(q["settings"][key]["error"] for q in items), abs_tol=1e-7)
    check_pairs(scores, pairs)
    return {"items": items, "scores": scores, "pairs": pairs, **details}


def check_pairs(scores, pairs):
    for pair in pairs:
        gain = scores[pair["reference"]]["error"] - scores[pair["candidate"]]["error"]
        assert math.isclose(gain, pair["gain_pp"], abs_tol=1e-7), pair
        assert pair["ci95"][0] <= pair["ci95"][1], pair


def overall(data, scores, pairs):
    for key, row in scores.items():
        assert math.isclose(row["error"], mean(s["scores"][key]["error"] for s in data.values()), abs_tol=1e-7)
        row["questionMean"] = mean(q["settings"][key]["error"] for s in data.values() for q in s["items"])
    check_pairs(scores, pairs)
    return {"scores": scores, "pairs": pairs}


def first_stage(raw, labels):
    data = {}
    for survey, source in raw["surveys"].items():
        rows = []
        options = {"shed": {"1": "是", "0": "否"}, "pew": {"1": "重大问题", "2": "小问题", "3": "不是问题", "4": "不确定"},
                   "anes": {"1": "增加", "2": "减少", "3": "维持现状"}}[survey]
        for row in raw["items"]:
            if row["survey"] != survey or row["group"] != "overall":
                continue
            codes = [code for code in options if code in row["human"]]
            rows.append(item(TITLES[row["item"]], [options[code] for code in codes],
                             [100 * row["human"][code] for code in codes], {
                                 k: {"error": row["error_pp"][k], "pct": [100 * row["simulated"][k][c] for c in codes]}
                                 for k in labels
                             }, count=f'真人有效回答 {row["valid_human"]:,} 份'))
        scores = {k: {"error": source["groups"]["overall"][k]} for k in labels}
        pair = comparison("B", "C", source["gain_pp"], source["gain_ci95_pp"])
        data[survey] = scope(rows, scores, [pair])
    scores = {k: {"error": mean(s["scores"][k]["error"] for s in data.values())} for k in labels}
    combined = comparison("B", "C", raw["combined_gain_pp"], raw["combined_ci95_pp"])
    return {"labels": labels, "scopes": data, "overall": overall(data, scores, [combined])}


def optimization_stage(raw, labels):
    data = {}
    for survey, cells in raw["surveys"].items():
        reference = cells[next(iter(labels))]["items"]
        rows = []
        for key, ref in reference.items():
            codes = list(ref["options"])
            settings = {}
            for name in labels:
                row = cells[name]["items"][key]
                assert all(math.isclose(row["options"][c]["human_pct"], ref["options"][c]["human_pct"], abs_tol=1e-7)
                           for c in codes), (survey, key, name)
                settings[name] = {"error": row["tv_pp"], "pct": [row["options"][c]["predicted_pct"] for c in codes],
                                  "accuracy": row.get("accuracy_pct"),
                                  "recall": [row["options"][c].get("recall_pct") for c in codes]}
            rows.append(item(TITLES[key], [OPTIONS[ref["options"][c]["label"]] for c in codes],
                             [ref["options"][c]["human_pct"] for c in codes], settings, original=ref["question"]))
        scores = {key: {"error": v["tv_pp"], "accuracy": v.get("accuracy_pct")} for key, v in cells.items()}
        pairs = [
            {"reference": p["reference"], "candidate": p["candidate"], **p["surveys"][survey]}
            for p in raw["comparisons"]
        ]
        data[survey] = scope(rows, scores, pairs)
    pairs = [comparison(p["reference"], p["candidate"], p["overall"]["gain_pp"], p["overall"]["ci95"])
             for p in raw["comparisons"]]
    scores = {key: {"error": v["tv_pp"], "accuracy": v.get("accuracy_pct")} for key, v in raw["overall"].items()}
    return {"labels": labels, "scopes": data, "overall": overall(data, scores, pairs)}


def card_description(card):
    packaging = {"Can": "罐装", "Bottle": "瓶装"}
    features = "、".join(label for key, label in CARD_FIELDS.items() if card[key] == "Yes")
    return f'{packaging[card["packaging"]]} {card["price"]}（{features or "无所列附加标识"}）'


def shopping_stage(raw):
    data = {}
    for survey, source in raw["surveys"].items():
        cells = source["cells"]
        rows = []
        for index, (key, ref) in enumerate(cells["P0+B1"]["metrics"].items(), 1):
            description = ""
            if survey == "packaging":
                card = source["cards"][key]
                a, b = map(card_description, card)
                title = f"选择卡 {index} · {a.split('（')[0]} 对 {b.split('（')[0]}"
                description = f"商品甲：{a}。商品乙：{b}。两款都是受访者平时常买类型的六罐或六瓶装啤酒。"
                options = ["选商品甲", "选商品乙", "两款都不买"]
            else:
                title = SHOP_ITEMS[key]
                if survey == "origin":
                    options = [title, "选另一款"]
                    description = "仅统计两款商品在这个属性上可以明确区分的选择。"
                else:
                    options = ["线上", "到实体店"] if key == "SHOP4" else ["是", "否", "不确定"]
                    options = options[:len(ref["human_pct"])]
            settings = {}
            for name, cell in cells.items():
                row = cell["metrics"][key]
                assert row["human_pct"] == ref["human_pct"], (survey, key, name)
                settings[name] = {"error": row["tv_pp"], "pct": row["predicted_pct"],
                                  "recall": [cell["individual_pct"].get(f"recall/{key}/{i+1}")
                                             for i in range(len(options))] if survey == "pew" else []}
            rows.append(item(title, options, ref["human_pct"], settings, description=description,
                             count=f'有效选择 {ref["tasks"]:,} 次'))
        scores = {k: {"error": v["tv_pp"], "accuracy": v["individual_pct"]["person_mean"]}
                  for k, v in cells.items()}
        rejection_recall = {
            k: v["individual_pct"]["recall/All/0"] for k, v in cells.items()
        } if survey == "packaging" else {}
        data[survey] = scope(rows, scores, source["comparisons"], matched=source["matched"],
                             training=source["training"], optOut=source["opt_out_pct"], rejectionRecall=rejection_recall)
    return {"labels": SHOP_SETTINGS, "scopes": data}


def build():
    first, models, profiles, shopping = map(read, FOLDERS)
    model_labels = {f"{model}-{arm}": f"{name} · {label}" for model, name in MODELS.items() for arm, label in ARMS.items()}
    profile_labels = {f"p{p}-b{b}": f"{prompt} · {background}"
                      for p, prompt in enumerate(PROMPTS) for b, background in enumerate(BACKGROUNDS, 1)}
    profile_labels["historical-stratum"] = "真人统计对照"
    stages = [
        first_stage(first, ARMS), optimization_stage(models, model_labels),
        optimization_stage(profiles, profile_labels), shopping_stage(shopping),
    ]
    for stage, folder in zip(stages, FOLDERS, strict=True):
        stage["names"] = SHOP if folder == FOLDERS[-1] else SURVEYS
        stage["source"] = f"{folder}/results.json"
        for q in (q for s in stage["scopes"].values() for q in s["items"]):
            assert set(q["settings"]) == set(stage["labels"])
    template = (ROOT / "报告模板.html").read_text()
    html = template.replace("@@DATA@@", json.dumps(stages, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c"))
    html = html.replace("@@SCRIPT@@", (ROOT / "report_charts.js").read_text())
    assert "@@" not in html
    (ROOT / "index.html").write_text(html)


if __name__ == "__main__":
    build()
