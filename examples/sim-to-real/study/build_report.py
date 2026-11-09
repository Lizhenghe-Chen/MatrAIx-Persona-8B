"""Build the standalone Chinese report from four frozen aggregate result files."""

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SURVEYS = {"shed": "消费应对", "pew": "诈骗风险", "anes": "公共支出"}
SHOP = {"origin": "商品产地、价格与评分", "packaging": "包装、价格与拒买", "pew": "网购习惯"}
BACKGROUND = ("基础年龄学历", "更细年龄学历", "贴题真人背景", "贴题背景＋合成人格")


def read(folder):
    return json.loads((ROOT / folder / "results.json").read_text())


def table(headers, rows):
    def cells(values, tag):
        return "".join(f"<{tag}>{html.escape(str(value))}</{tag}>" for value in values)

    return ('<div class="scroll"><table><thead><tr>' + cells(headers, "th") + "</tr></thead><tbody>"
            + "".join(f'<tr>{cells(row, "td")}</tr>' for row in rows) + "</tbody></table></div>")


def gain(row):
    lo, hi = row["ci95"]
    return f"{row['gain_pp']:+.2f}［{lo:+.2f}，{hi:+.2f}］"


def build():
    first = read("01_首轮归档")
    models = read("02_模型对比")
    profiles = read("03_提示与背景")
    shopping = read("06_北美电商选品")["surveys"]
    first_rows = []
    for key, label in SURVEYS.items():
        row = first["surveys"][key]
        first_rows.append([label, *(f"{row['groups']['overall'][arm]:.2f}" for arm in "ABC"),
                           gain({"gain_pp": row["gain_pp"], "ci95": row["gain_ci95_pp"]})])
    first_rows.append(["三份问卷等权", *(
        f"{sum(row['groups']['overall'][arm] for row in first['surveys'].values())/3:.2f}" for arm in "ABC"),
        gain({"gain_pp": first["combined_gain_pp"], "ci95": first["combined_ci95_pp"]})])
    model_rows = [[label, *(f"{models['overall'][f'{model}-{arm}']['tv_pp']:.2f}"
                            for model in ("flash", "pro", "qwen"))]
                  for arm, label in zip("ABC", ("只有共同情境", "加年龄学历", "再加四项合成人格"), strict=True)]
    profile_rows = [[label, *(f"{profiles['overall'][f'p{prompt}-b{i}']['tv_pp']:.2f}" for prompt in (0, 1))]
                    for i, label in enumerate(BACKGROUND, 1)]
    historical = profiles["overall"]["historical-stratum"]["tv_pp"]
    profile_rows.append(["按年龄学历查真人历史比例", f"{historical:.2f}", "—"])
    shopping_rows = []
    for key, label in SHOP.items():
        row = shopping[key]
        shopping_rows.append([label, f"{row['cells']['P0+B1']['tv_pp']:.2f}",
                              f"{row['cells']['P1+B3']['tv_pp']:.2f}", gain(row["comparisons"][0]),
                              f"{row['cells']['统计基线']['tv_pp']:.2f}"])
    phone = models["surveys"]["pew"]["pro-A"]["items"]["OSCAM_PLAT_a"]["options"]["1"]
    reject = shopping["packaging"]["opt_out_pct"]
    china = shopping["origin"]["cells"]["P1+B3"]["metrics"]["China"]
    china_before = shopping["origin"]["cells"]["P0+B1"]["metrics"]["China"]
    creator = shopping["pew"]["cells"]["P1+B3"]["metrics"]["ONLSHOP4"]
    examples = [
        {"title": "包装测试 · 两款商品都不买", "series": [
            ["真人", reject["human"]], ["优化设置", reject["P1+B3"]], ["统计对照", reject["统计基线"]]],
         "note": "同样的两款商品，模型拒买得太少。它只识别出约 7% 真正拒买的答卷。"},
        {"title": "商品选择 · 两款中选中国产", "series": [
            ["真人", china["human_pct"][0]], ["优化前", china_before["predicted_pct"][0]],
            ["优化后", china["predicted_pct"][0]]],
         "note": "只看恰好一款是中国产品的题。优化缩小了差距，模型仍高估中国产品的选择率。"},
        {"title": "Pew 网购 · 看达人内容后曾购买", "series": [
            ["真人", creator["human_pct"][0]], ["优化设置", creator["predicted_pct"][0]]],
         "note": "只有原调查符合跳题条件的人参与比较。这是自报购物经历。"},
        {"title": "Pew 诈骗 · 电话和短信诈骗是重大问题", "series": [
            ["真人", phone["human_pct"]], ["仅给情境的 Pro", phone["predicted_pct"]]],
         "note": "同样题目在真人中有分歧，综合误差最低的模型设置在这题仍给出全票。"},
    ]
    template = (ROOT / "报告模板.html").read_text()
    replacements = {
        "ROUND1": table(("问卷", "只有情境", "加年龄学历", "再加人格", "加入人格后的改善及区间"), first_rows),
        "MODELS": table(("输入背景", "DeepSeek Flash", "DeepSeek Pro", "内网 Qwen"), model_rows),
        "PROFILES": table(("输入背景", "扮演受访者", "预测这位受访者"), profile_rows),
        "SHOPPING": table(("任务", "原角色提示＋基础背景", "预测提示＋贴题背景", "改善及 95% 区间", "统计对照"), shopping_rows),
        "ORIGIN_GAIN": f"{shopping['origin']['comparisons'][0]['gain_pp']:.2f}",
        "REJECT_HUMAN": f"{reject['human']:.1f}",
        "REJECT_MODEL": f"{reject['P1+B3']:.1f}",
        "EXAMPLES": json.dumps(examples, ensure_ascii=False).replace("<", "\\u003c"),
    }
    for name, value in replacements.items():
        template = template.replace(f"@@{name}@@", value)
    if "@@" in template:
        raise ValueError("Unresolved report placeholder")
    (ROOT / "index.html").write_text(template)


if __name__ == "__main__":
    build()
