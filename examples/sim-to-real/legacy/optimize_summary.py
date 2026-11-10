"""Produce a short interpretation of the frozen results and their status."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from experiment import read_json
from optimize import FOLDERS

NAMES = {"shed": "SHED", "pew": "Pew", "anes": "ANES"}
FACTORS = {
    "提示词": lambda a, b: a.startswith("p0") and b == "p1" + a[2:],
    "年龄和学历细分": lambda a, b: a.endswith("b1") and b == a[:3] + "b2",
    "贴题的真人信息": lambda a, b: a.endswith("b2") and b == a[:3] + "b3",
    "合成人格": lambda a, b: a.endswith("b3") and b == a[:3] + "b4",
}


def signed(row):
    lo, hi = row["ci95"]
    return f"{row['gain_pp']:+.2f} [{lo:+.2f}, {hi:+.2f}]"


def progress(folder):
    path = folder / "checkpoints.sqlite"
    if not path.exists():
        return 0, 0, 0
    with sqlite3.connect(path) as db:
        rows = dict(db.execute("SELECT stage, SUM(ok) FROM trials GROUP BY stage"))
        rejected = db.execute("SELECT COUNT(*) FROM trials WHERE stage='pilot' AND ok=0 "
                              "AND json_extract(payload,'$.failures[0].status')=401").fetchone()[0]
    return rows.get("pilot", 0), rows.get("formal", 0), rejected


def concentration(result, conditions):
    rows = []
    for survey, cells in result["surveys"].items():
        for condition in conditions:
            for item, row in cells[condition]["items"].items():
                if row["top_pct"] >= 99 - 1e-8:
                    option = row["options"][row["top_option"]]
                    rows.append((row["tv_pp"], NAMES[survey], condition, item, option["label"],
                                 row["top_pct"], option["human_pct"]))
    return sorted(rows, reverse=True)


def cases(rows):
    if not rows:
        return ["所列组合中没有题目达到 99% 单选集中度。"]
    return ["| 问卷 | 组合 | 题号 | 集中选项 | 模拟比例 | 真人选择同项 |",
            "|---|---|---|---|---:|---:|"] + [
        f"| {s} | {c} | {item} | {option} | {sim:.1f}% | {human:.1f}% |"
        for _, s, c, item, option, sim, human in rows[:8]]


def summary(study):
    folders = {key: study / folder for key, folder in FOLDERS.items()}
    results = {key: read_json(path / "results.json") for key, path in folders.items()
               if (path / "results.json").exists()}
    lines = ["# MatrAIx 真人问卷模拟优化结果", "",
             "误差是把模拟的选项份额调到真人分布所需重新分配的比例。误差为 20 个百分点，"
             "大致相当于每 100 份答卷要重新分配 20 份答案。增益为正表示候选设置离真人更近。", "",
             "| 实验 | 有效技术试跑 | 有效正式答卷 |", "|---|---:|---:|"]
    for key, target, pilot_n in (("models", 6480, 9), ("profiles", 5760, 384)):
        pilot, formal, rejected = progress(folders[key])
        lines.append(f"| {folders[key].name[3:]} | {pilot:,}/{pilot_n:,} | {formal:,}/{target:,} |")
        if key == "models":
            cloud_blocked = rejected > 0

    lines += ["", "## 换模型", ""]
    if cloud_blocked:
        lines.append("DeepSeek 官方接口对现有凭据返回 401。当前结果只覆盖通过验收的组。"
                     "首轮 Flash 使用不同思考设置和样本规模，作为历史背景列出。")
    if "models" in results:
        result = results["models"]
        cells = result["overall"]
        lines += ["", "| 输入 | Flash | Pro | Qwen |", "|---|---:|---:|---:|"]
        for arm, label in zip("ABC", ("A 共同情境", "B 加年龄和学历", "C 再加四项人格"), strict=True):
            errors = [f"{cells[f'{m}-{arm}']['tv_pp']:.2f}" if f"{m}-{arm}" in cells else "待完成"
                      for m in ("flash", "pro", "qwen")]
            lines.append(f"| {label} | " + " | ".join(errors) + " |")
        lines += ["", "| 对照 | 综合增益及 95% 区间 | 达到预设门槛 |",
                  "|---|---:|---|"]
        for row in result["comparisons"]:
            a, b = row["reference"], row["candidate"]
            verdict = "是" if row["meets_threshold"] else "否"
            lines.append(f"| {a} → {b} | {signed(row['overall'])} | {verdict} |")
        best = min(cells, key=lambda c: cells[c]["tv_pp"])
        lines += ["", f"误差最低的合成画像条件为 **{best}**。下表列出该条件下仍接近全票的题。",
                  "", *cases(concentration(result, [best])), ""]
    else:
        lines += ["正式评分尚未生成。", ""]
    lines += ["## 提示词和背景", ""]
    if "profiles" in results:
        result = results["profiles"]
        hist = result["overall"]["historical-stratum"]
        model = {c: r for c, r in result["overall"].items() if c != "historical-stratum"}
        best = min(model, key=lambda c: model[c]["tv_pp"])
        best_error = model[best]["tv_pp"]
        lines += [f"八种模型设置中，**{best}** 的综合分布误差最低，为 **{best_error:.2f}** 个百分点，"
                  f"逐人正确率为 **{model[best]['accuracy_pct']:.1f}%**。"
                  f"按年龄学历查同一调查历史比例的基线误差为 **{hist['tv_pp']:.2f}** 个百分点，"
                  f"取每层最常见选项的逐人正确率为 **{hist['accuracy_pct']:.1f}%**。", "",
                  "| 单项改动 | 对照 | 综合增益及 95% 区间 | 达到预设门槛 |",
                  "|---|---|---:|---|"]
        for factor, matches in FACTORS.items():
            for row in result["comparisons"]:
                a, b = row["reference"], row["candidate"]
                if matches(a, b):
                    verdict = "是" if row["meets_threshold"] else "否"
                    lines.append(f"| {factor} | {a} → {b} | {signed(row['overall'])} | {verdict} |")
        against_history = next(r for r in result["comparisons"]
                               if r["reference"] == "historical-stratum" and r["candidate"] == best)
        against_original = next((r for r in result["comparisons"]
                                 if r["reference"] == "p0-b1" and r["candidate"] == best), None)
        lines += ["", f"误差最低的模型组合相对统计基线的增益为 "
                  f"**{signed(against_history['overall'])}** 个百分点。"]
        if against_original:
            lines.append(f"相对原提示和粗背景，增益为 **{signed(against_original['overall'])}** 个百分点。")
        if best == "p1-b4":
            simpler = model["p1-b3"]
            p1_traits = next(r for r in result["comparisons"]
                             if r["reference"] == "p1-b3" and r["candidate"] == "p1-b4")
            if not p1_traits["meets_threshold"]:
                lines += ["", f"**在八种 Qwen 设置中，优先用 P1 + B3。** 误差为 {simpler['tv_pp']:.2f} 个百分点，"
                          f"逐人正确率为 {simpler['accuracy_pct']:.1f}%。再加合成人格的误差增益为 "
                          f"{signed(p1_traits['overall'])} 个百分点，逐人正确率降为 {model[best]['accuracy_pct']:.1f}%。"]
        lines += ["", f"下表列出 {best} 仍接近全票、且与真人差异最大的题目。", "",
                  *cases(concentration(result, [best])), "",
                  f"### {best} 的全部题目", "",
                  "| 问卷 | 题号 | 模型最常选项 | 模拟比例 | 真人选择同项 | 完整分布误差 |",
                  "|---|---|---|---:|---:|---:|"]
        for survey, cells in result["surveys"].items():
            for item, row in cells[best]["items"].items():
                option = row["options"][row["top_option"]]
                lines.append(f"| {NAMES[survey]} | {item} | {option['label']} | "
                             f"{row['top_pct']:.1f}% | {option['human_pct']:.1f}% | {row['tv_pp']:.2f} |")
        lines.append("")
    else:
        lines += ["正式评分尚未生成。", ""]
    lines += ["## 资料与适用范围", "",
              "模型试验用合成画像。逐人实验用真实背景加预测，B4 人格由合成画像随机匹配。"
              "这些题来自三份已公开调查，模型可能见过部分题目或答案统计。"
              "同调查历史基线衡量已有同题真人记录时的预测表现。", "",
              "[SHED 数据与字典](https://www.federalreserve.gov/consumerscommunities/shed_data.htm) · "
              "[Pew Wave 168 数据](https://www.pewresearch.org/dataset/american-trends-panel-wave-168/) · "
              "[ANES 2024 数据与字典](https://electionstudies.org/data-center/2024-time-series-study/) · "
              "[DeepSeek 模型说明](https://api-docs.deepseek.com/quick_start/pricing/)"]
    (study / "04_综合报告" / "优化实验综合报告.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", type=Path)
    summary(parser.parse_args().study)
