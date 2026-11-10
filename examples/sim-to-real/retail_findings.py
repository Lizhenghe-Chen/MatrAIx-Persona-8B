"""Translate experiment summaries into readable findings for the HTML report."""
from html import escape


def interval(bounds, digits=2):
    return " 至 ".join(f"{n:+.{digits}f}" for n in bounds)


def findings(scores, extra):
    paragraphs = []
    pew = scores.get("formal") or scores["pilot"]
    stage = "独立评估" if pew["stage"] == "formal" else "开发集"
    models = pew["summaries"]
    contrast = next(c for c in pew["contrasts"] if (c["from"],c["to"]) == ("rich_choice","rich_probability"))
    single, prob, argmax = [models[k] for k in ("rich_choice","rich_probability","rich_probability_argmax")]
    old_count, new_count = single["concentration_counts"]["0.95"], prob["concentration_counts"]["0.95"]
    paragraphs.append(f"<p><strong>Pew 网购 · {stage} {pew['common_people']} 人。</strong> "
                      f"保持背景相同，从单选改为概率，分布误差由 {single['tv_pp']:.2f} 降为 {prob['tv_pp']:.2f} 个百分点。"
                      f"改善 {contrast['tv_improvement_pp']:+.2f}，95% 区间 {interval(contrast['tv_95_interval'])}。"
                      f"达到 95% 单项集中度的题由 {old_count} 道变为 {new_count} 道。"
                      f"对这批概率重新只取最高项时，误差是 {argmax['tv_pp']:.2f}。"
                      f"按年龄和学历查统计比例的误差是 {models['statistics']['tv_pp']:.2f}。</p>")
    cal = extra["calibration"].get("formal") or extra["calibration"].get("pilot")
    if cal:
        stage = "独立评估" if cal["stage"] == "formal" else "开发集"
        ref = cal["summary"]["statistics_rich"]
        model = cal["summary"]["calibrated_model"]
        c = cal["versus_statistics"]["calibrated_model"]
        paragraphs.append(f"<p><strong>Pew 校准 · {stage}。</strong> 校准后的分布误差为 {model['tv_pp']:.2f} 个百分点，"
                          f"完整背景统计模型为 {ref['tv_pp']:.2f}。逐人 Brier 分数分别为 {model['brier']:.3f} 和 {ref['brier']:.3f}。"
                          f"校准相对统计模型的逐人改善为 {c['brier_gain']:+.3f}，95% 区间 {interval(c['interval'],3)}。"
                          f"开发集选出的模型组合权重为 {100*cal['model_weight']:.1f}%。</p>")
    shoes = extra["shoes"].get("test") or extra["shoes"].get("development")
    if shoes:
        stage = "独立评估" if shoes["stage"] == "test" else "开发集"
        m = shoes["summary"]
        a = m["rich_choice"]["tv_pp"]
        b = m["rich_probability"]["tv_pp"]
        c = m["attitude_probability"]["tv_pp"]
        paragraphs.append(f"<p><strong>运动鞋 · {stage} {shoes['people']} 人。</strong> "
                          f"完整人口背景下，单选与概率的分布误差分别为 {a:.2f} 和 {b:.2f} 个百分点。"
                          f"加入真人实测态度后为 {c:.2f}，商品属性与背景统计模型为 {m['statistics']['tv_pp']:.2f}。"
                          f"真人给较便宜款的评分平均高 {shoes['real']['cheaper_minus_expensive']:+.2f} 分，"
                          f"补充态度的模型估计为 {m['attitude_probability']['cheaper_minus_expensive']:+.2f} 分。"
                          "下文可查看七档分布与不同实验组。</p>")
        if "calibrated_rating" in m:
            direct = m["calibrated_rating"]
            blend = m["blend"]
            gain = next(x for x in shoes["contrasts"] if x["from"]=="statistics" and x["to"]=="blend")
            paragraphs.append(f"<p>把单选评分按开发集的真人分布转换为七档概率后，分布误差为 {direct['tv_pp']:.2f} 个百分点。"
                              f"统计与校准评分的组合误差为 {blend['tv_pp']:.2f}，"
                              f"逐人改善为 {gain['brier_improvement']:+.3f}，95% 区间 {interval(gain['brier_interval'],3)}。"
                              f"模型组合权重为 {100*shoes['calibration_model_weight']:.1f}%。"
                              + ("开发集的分布对齐来自拟合，改善须在独立样本上复现。" if shoes["stage"]=="development" else "")
                              + "</p>")
        controlled = shoes.get("controlled_attribute_effects",{}).get("Eco-Friendly Materials")
        if controlled:
            reference = controlled["real_effect"]
            forecast = controlled["methods"]["rich_probability"]
            paragraphs.append(f"<p>在仅变环保材质的 {controlled['pairs']} 对鞋中，真人评分差为 {reference:+.2f} 分，"
                              f"完整背景概率模型为 {forecast['effect']:+.2f} 分。"
                              f"预测减真人的差为 {forecast['minus_real']:+.2f} 分，"
                              f"配对 95% 区间 {interval(forecast['minus_real_95_interval'])}。"
                              "整体分布与商品属性敏感度需要分别验收。</p>")
    category = extra["amazonCategory"].get("test") or extra["amazonCategory"].get("development")
    if category:
        stage = "独立评估" if category["sample"] == "test" else "开发集"
        m = category["summary"]
        c = category["contrasts"]["recent → blend"]
        paragraphs.append(f"<p><strong>Amazon 品类购买 · {stage} {category['common_accounts']} 个账户。</strong> "
                          f"最近四季度频率、模型直接读历史、给模型附上频率的 Brier 分数依次是 "
                          f"{m['recent']['brier']:.4f}、{m['history_only']['brier']:.4f}、{m['historical_anchor']['brier']:.4f}。"
                          f"统计与模型组合相对频率基线的改善为 {c['brier_improvement']:+.4f}，95% 区间 {interval(c['interval'],4)}。</p>")
    mix = extra["amazonMix"].get("test") or extra["amazonMix"].get("development")
    if mix:
        stage = "独立评估" if mix["stage"] == "test" else "开发集"
        names = {"price":"价格带","spend":"品类支出","repeat":"同款复购"}
        lines = []
        for key, task in mix["tasks"].items():
            stats = task["results"][task["baseline"]]["brier"]
            model = task["results"]["model"]["brier"]
            combined = task["comparisons"]["blend"]
            lines.append(f"<li>{escape(names[key])}的历史基线误差为 {stats:.4f}，模型为 {model:.4f}。"
                         f"组合的改善为 {combined['gain']:+.4f}，95% 区间 {interval(combined['interval'],4)}。</li>")
        paragraphs.append(f"<p><strong>Amazon 消费结构与复购 · {stage} {mix['accounts']} 个账户。</strong></p><ul>"
                          +"".join(lines)+"</ul>")
        repeat = mix["tasks"]["repeat"]
        actual = 100*repeat["actual"][1]
        predicted = 100*repeat["results"]["model"]["shares"][1]
        historical = 100*repeat["results"][repeat["baseline"]]["shares"][1]
        c = repeat["comparisons"]["model"]
        paragraphs.append(f"<p>同款复购的整体比例，真人为 {actual:.1f}%，模型估计 {predicted:.1f}%，"
                          f"历史基线估计 {historical:.1f}%。逐账户比较时，模型的改善为 {c['gain']:+.4f}，"
                          f"95% 区间 {interval(c['interval'],4)}。两个结果分别回答了“有多少账户复购”和“具体谁会复购”。</p>")
    return "<section><h2>目前有哪些实证结果</h2>"+"".join(paragraphs)+"</section>"
