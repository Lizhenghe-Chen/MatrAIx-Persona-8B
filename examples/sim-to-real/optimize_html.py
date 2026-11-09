"""Render an offline, shareable HTML report from aggregate results only."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from experiment import read_json, sha256
from optimize import FOLDERS
from optimize_summary import FACTORS, progress

HIST = "historical-stratum"


def metric(value, text):
    return f'<div class="metric"><strong>{html.escape(value)}</strong><span>{html.escape(text)}</span></div>'


def card(title, text):
    return f'<article class="card"><h3>{html.escape(title)}</h3><p>{html.escape(text)}</p></article>'


def human_label(setting):
    return setting.upper().replace("-", " · ")


def describing_factor(rows, name, formatted=False):
    match = FACTORS[name]
    selected = [row for row in rows if match(row["reference"], row["candidate"])]
    best = max(selected, key=lambda row: row["overall"]["gain_pp"])
    low = min(selected, key=lambda row: row["overall"]["gain_pp"])["overall"]["gain_pp"]
    high = best["overall"]["gain_pp"]
    reached = [row for row in selected if row["meets_threshold"]]
    if reached:
        best = max(reached, key=lambda row: row["overall"]["gain_pp"])
        overall = best["overall"]
        wording = (f"{human_label(best['reference'])} → {human_label(best['candidate'])} "
                   f"下降 {overall['gain_pp']:.2f} 个百分点，达到预设门槛。")
    elif len(selected) == 2:
        wording = f"两个提示版本下误差降幅分别为 {selected[0]['overall']['gain_pp']:+.2f} 和 {selected[1]['overall']['gain_pp']:+.2f} 个百分点，均未达到门槛。"
    else:
        wording = f"四档背景下误差降幅在 {low:+.2f} 到 {high:+.2f} 个百分点之间，均未达到门槛。"
    return f"{name}。{wording}" if formatted else wording


def render(study, library):
    folders = {key: study / name for key, name in FOLDERS.items()}
    data = {key: read_json(path / "results.json") for key, path in folders.items()
            if (path / "results.json").is_file()}
    model = data["models"]
    overall = model["overall"]
    model_cards = (
        metric(f"{overall['pro-A']['tv_pp']:.2f} pp", "三模型的最低误差 · Pro A"),
        metric(f"{progress(folders['models'])[1]:,}", "三模型有效答卷"),
    )
    model_text = (f"只给共同情境时，Flash 的误差为 {overall['flash-A']['tv_pp']:.2f}，"
                  f"Pro 为 {overall['pro-A']['tv_pp']:.2f}，Qwen 为 {overall['qwen-A']['tv_pp']:.2f} 个百分点。"
                  f"三者都加四项人格后，误差在 "
                  f"{min(overall[f'{m}-C']['tv_pp'] for m in ('flash','pro','qwen')):.2f}–"
                  f"{max(overall[f'{m}-C']['tv_pp'] for m in ('flash','pro','qwen')):.2f} 个百分点之间。")
    cards = [card("换模型有用，取决于输入", model_text)]
    example = model["surveys"]["pew"]["pro-A"]["items"]["OSCAM_PLAT_a"]["options"]["1"]
    collapse = (f"仅给共同情境时，Pro 在电话或短信诈骗题选「重大问题」的比例是 "
                f"<b>{example['predicted_pct']:.1f}%</b>，Pew 真人为 <b>{example['human_pct']:.1f}%</b>。"
                "该组综合误差仍是模型对比九个条件中最低的。")
    decision = ""
    pilot, count, _ = progress(folders["profiles"])
    if "profiles" in data:
        profile = data["profiles"]
        values = profile["overall"]
        best = min((k for k in values if k != HIST), key=lambda k: values[k]["tv_pp"])
        data["bestProfile"] = best
        data["preferredProfile"] = best
        baseline = values[HIST]
        v = values[best]
        model_cards += (metric(f"{v['tv_pp']:.2f} pp", f"逐人模型最低误差 · {human_label(best)}"),)
        cards.append(card("提示词的影响", describing_factor(profile["comparisons"], "提示词")))
        cards.append(card("背景信息的影响", " ".join(describing_factor(profile["comparisons"], name, True)
                          for name in ("年龄和学历细分", "贴题的真人信息", "合成人格"))))
        lookup = {(r["reference"], r["candidate"]): r for r in profile["comparisons"]}
        to_baseline = lookup[HIST, best]["overall"]
        gap = v["tv_pp"] - baseline["tv_pp"]
        effect = "高出" if gap >= 0 else "低了"
        decision = (f"误差最低的模型设置比统计基线{effect} {abs(gap):.2f} 个百分点。"
                    f"以误差下降为正，差值的 95% 区间是 "
                    f"[{to_baseline['ci95'][0]:+.2f}, {to_baseline['ci95'][1]:+.2f}]。")
        if best == "p1-b4" and not lookup["p1-b3", "p1-b4"]["meets_threshold"]:
            data["preferredProfile"] = "p1-b3"
            simpler = values["p1-b3"]
            b4 = lookup["p1-b3", "p1-b4"]["overall"]
            decision += (f" 如果需要在这八种 Qwen 设置中选一个，优先用 P1 · B3。"
                         f"它的误差为 {simpler['tv_pp']:.2f} 个百分点，逐人正确率 {simpler['accuracy_pct']:.1f}%。"
                         f"再加合成人格的误差降幅只有 {b4['gain_pp']:.2f} 个百分点，"
                         f"95% 区间 [{b4['ci95'][0]:+.2f}, {b4['ci95'][1]:+.2f}]，"
                         f"逐人正确率降到 {v['accuracy_pct']:.1f}%。")
        if best != "p0-b1":
            original = lookup["p0-b1", best]
            gain = original["overall"]
            verdict = "达到" if original["meets_threshold"] else "未达到"
            decision = (f"相对原始设置 P0 · B1，误差最低的模型设置综合增益为 "
                        f"{gain['gain_pp']:+.2f} 个百分点，{verdict}预设门槛。") + decision
        status = (f"技术试跑 {pilot:,}/384 份，正式答卷 {count:,}/5,760 份。"
                  f"误差最低的模型设置为 {human_label(best)}，误差 {v['tv_pp']:.2f} 个百分点，"
                  f"逐人正确率 {v['accuracy_pct']:.1f}%。"
                  f"分层统计基线误差为 {baseline['tv_pp']:.2f} 个百分点，逐人正确率 {baseline['accuracy_pct']:.1f}%。")
    else:
        model_cards += (metric(f"{count:,}", "逐人正式答卷已通过校验"),)
        status = f"技术试跑 {pilot:,}/384 份通过。正式答卷已通过 {count:,}/5,760 份，评分待生成。"
        cards.extend((card("提示词的影响", "两版提示的正式答卷正在运行。"),
                      card("背景信息的影响", "四档背景将与同调查的分层统计基线比较。")))

    template = Path(__file__).with_name("optimize_report.html").read_text()
    vendor = library / "dist" / "echarts.min.js"
    licence = "\n\n".join((library / f).read_text() for f in ("LICENSE", "NOTICE"))
    rendered = template.replace("@@METRICS@@", "".join(model_cards)).replace("@@TAKEAWAYS@@", "".join(cards))
    rendered = rendered.replace("@@PROFILE_STATUS@@", html.escape(status)).replace("@@LICENSE@@", html.escape(licence))
    rendered = rendered.replace("@@COLLAPSE@@", collapse).replace("@@DECISION@@", html.escape(decision))
    rendered = rendered.replace("@@DATA@@", json.dumps(data, ensure_ascii=False).replace("<", "\\u003c"))
    rendered = rendered.replace("@@ECHARTS@@", vendor.read_text().replace("</script", "<\\/script"))
    output = study / "04_综合报告" / "MatrAIx 优化实验交互报告.html"
    output.write_text(rendered)
    (output.parent / "交互报告.sha256").write_text(f"{sha256(output)}  {output.name}\n")
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", type=Path)
    parser.add_argument("--echarts-package", type=Path, required=True)
    args = parser.parse_args()
    render(args.study, args.echarts_package)
