# MatrAIx 模型对比

分布误差以百分点计，越低越接近真人。集中度按 95%／99%／100% 三档统计题数。

| 组合 | 综合误差 | SHED | Pew | ANES | 集中题数 | 逐人正确率 |
|---|---:|---:|---:|---:|---:|---:|
| flash-A | 33.82 | 31.06 | 31.82 | 38.58 | 15/10/9 | — |
| flash-B | 31.91 | 29.36 | 33.54 | 32.82 | 13/10/8 | — |
| flash-C | 23.39 | 21.79 | 31.48 | 16.91 | 8/7/5 | — |
| pro-A | 21.97 | 12.76 | 27.69 | 25.46 | 4/3/2 | — |
| pro-B | 23.02 | 22.70 | 28.90 | 17.44 | 8/5/2 | — |
| pro-C | 23.38 | 23.35 | 28.82 | 17.97 | 7/5/2 | — |
| qwen-A | 26.92 | 26.68 | 28.37 | 25.71 | 8/5/3 | — |
| qwen-B | 28.18 | 25.88 | 27.58 | 31.06 | 8/5/2 | — |
| qwen-C | 24.27 | 24.00 | 25.59 | 23.22 | 6/4/0 | — |

## 整份答卷的重复情况

重复占比表示有多少答卷与至少另一份完全相同。

| 问卷 | 组合 | 不同答卷种数 | 最常见答卷占比 | 重复占比 |
|---|---|---:|---:|---:|
| SHED | flash-A | 5 | 76.2% | 100.0% |
| SHED | flash-B | 6 | 59.2% | 100.0% |
| SHED | flash-C | 13 | 54.2% | 98.8% |
| SHED | pro-A | 14 | 22.5% | 99.2% |
| SHED | pro-B | 13 | 37.5% | 98.8% |
| SHED | pro-C | 15 | 28.8% | 98.3% |
| SHED | qwen-A | 13 | 34.6% | 97.5% |
| SHED | qwen-B | 21 | 25.8% | 96.7% |
| SHED | qwen-C | 21 | 30.4% | 96.7% |
| Pew | flash-A | 2 | 84.2% | 100.0% |
| Pew | flash-B | 2 | 94.2% | 100.0% |
| Pew | flash-C | 2 | 84.2% | 100.0% |
| Pew | pro-A | 4 | 64.2% | 99.6% |
| Pew | pro-B | 4 | 77.1% | 99.6% |
| Pew | pro-C | 4 | 74.2% | 99.6% |
| Pew | qwen-A | 6 | 52.1% | 99.2% |
| Pew | qwen-B | 5 | 37.1% | 99.6% |
| Pew | qwen-C | 9 | 33.8% | 97.9% |
| ANES | flash-A | 13 | 89.2% | 97.5% |
| ANES | flash-B | 14 | 66.7% | 98.3% |
| ANES | flash-C | 40 | 24.6% | 92.5% |
| ANES | pro-A | 28 | 40.8% | 94.2% |
| ANES | pro-B | 37 | 29.6% | 94.2% |
| ANES | pro-C | 42 | 16.2% | 92.5% |
| ANES | qwen-A | 30 | 30.0% | 93.8% |
| ANES | qwen-B | 34 | 31.2% | 92.9% |
| ANES | qwen-C | 58 | 17.9% | 88.8% |

## 配对对照

正数表示候选组合误差下降，括号为 95% 区间。各问卷的区间见结果 JSON。

| 参照 → 候选 | 综合增益 | SHED | Pew | ANES | 达到门槛 |
|---|---:|---:|---:|---:|---|
| flash-A → pro-A | +11.86 [+10.46, +13.01] | +18.30 | +4.14 | +13.12 | 是 |
| flash-B → pro-B | +8.89 [+7.54, +10.04] | +6.66 | +4.63 | +15.38 | 是 |
| flash-C → pro-C | +0.01 [-1.46, +2.12] | -1.56 | +2.65 | -1.06 | 否 |
| flash-A → qwen-A | +6.90 [+5.74, +8.01] | +4.38 | +3.46 | +12.87 | 是 |
| flash-B → qwen-B | +3.73 [+2.53, +4.67] | +3.47 | +5.95 | +1.76 | 是 |
| flash-C → qwen-C | -0.88 [-2.05, +0.81] | -2.22 | +5.89 | -6.31 | 否 |
| pro-A → qwen-A | -4.96 [-6.34, -3.34] | -13.93 | -0.68 | -0.26 | 否 |
| pro-B → qwen-B | -5.16 [-6.50, -3.79] | -3.18 | +1.32 | -13.62 | 否 |
| pro-C → qwen-C | -0.89 [-2.59, +0.69] | -0.66 | +3.23 | -5.25 | 否 |
| flash-A → flash-B | +1.92 [+1.12, +2.63] | +1.70 | -1.71 | +5.76 | 否 |
| pro-A → pro-B | -1.05 [-2.82, +0.58] | -9.95 | -1.22 | +8.02 | 否 |
| qwen-A → qwen-B | -1.26 [-2.65, -0.08] | +0.80 | +0.78 | -5.35 | 否 |
| flash-B → flash-C | +8.51 [+7.09, +9.36] | +7.57 | +2.06 | +15.91 | 是 |
| pro-B → pro-C | -0.36 [-2.12, +1.70] | -0.64 | +0.08 | -0.53 | 否 |
| qwen-B → qwen-C | +3.91 [+2.44, +5.45] | +1.88 | +1.99 | +7.84 | 是 |

## 仍接近全票的题目

| 问卷 | 组合 | 题号 | 最常见选项 | 模拟选择率 | 真人同选项选择率 |
|---|---|---|---|---:|---:|
| SHED | flash-A | INF3_a | Yes | 100.0% | 62.2% |
| SHED | flash-A | INF3_b | Yes | 100.0% | 59.7% |
| SHED | flash-A | INF3_d | No | 100.0% | 84.2% |
| SHED | flash-A | INF3_e | Yes | 100.0% | 45.6% |
| SHED | flash-B | INF3_a | Yes | 100.0% | 62.2% |
| SHED | flash-B | INF3_b | Yes | 99.6% | 59.7% |
| SHED | flash-B | INF3_d | No | 100.0% | 84.2% |
| SHED | flash-B | INF3_e | Yes | 100.0% | 45.6% |
| SHED | flash-C | INF3_a | Yes | 100.0% | 62.2% |
| SHED | flash-C | INF3_d | No | 99.1% | 84.2% |
| SHED | flash-C | INF3_e | Yes | 99.1% | 45.6% |
| SHED | pro-B | INF3_d | No | 99.5% | 84.2% |
| SHED | pro-B | INF3_f | No | 99.5% | 83.0% |
| SHED | pro-C | INF3_a | Yes | 99.6% | 62.2% |
| SHED | pro-C | INF3_d | No | 99.2% | 84.2% |
| SHED | qwen-A | INF3_a | Yes | 100.0% | 62.2% |
| SHED | qwen-A | INF3_b | Yes | 99.2% | 59.7% |
| SHED | qwen-A | INF3_e | Yes | 99.6% | 45.6% |
| SHED | qwen-B | INF3_a | Yes | 99.8% | 62.2% |
| SHED | qwen-C | INF3_a | Yes | 99.0% | 62.2% |
| SHED | qwen-C | INF3_e | Yes | 99.4% | 45.6% |
| Pew | flash-A | OSCAM_PROB | Major problem | 100.0% | 79.6% |
| Pew | flash-A | OSCAM_PLAT_a | Major problem | 100.0% | 68.3% |
| Pew | flash-A | OSCAM_PLAT_b | Major problem | 100.0% | 64.8% |
| Pew | flash-A | OSCAM_PLAT_c | Major problem | 100.0% | 61.9% |
| Pew | flash-B | OSCAM_PROB | Major problem | 100.0% | 79.6% |
| Pew | flash-B | OSCAM_PLAT_a | Major problem | 100.0% | 68.3% |
| Pew | flash-B | OSCAM_PLAT_b | Major problem | 100.0% | 64.8% |
| Pew | flash-B | OSCAM_PLAT_c | Major problem | 100.0% | 61.9% |
| Pew | flash-C | OSCAM_PROB | Major problem | 100.0% | 79.6% |
| Pew | flash-C | OSCAM_PLAT_a | Major problem | 100.0% | 68.3% |
| Pew | flash-C | OSCAM_PLAT_b | Major problem | 100.0% | 64.8% |
| Pew | flash-C | OSCAM_PLAT_c | Major problem | 100.0% | 61.9% |
| Pew | pro-A | OSCAM_PROB | Major problem | 100.0% | 79.6% |
| Pew | pro-A | OSCAM_PLAT_a | Major problem | 100.0% | 68.3% |
| Pew | pro-A | OSCAM_PLAT_b | Major problem | 99.6% | 64.8% |
| Pew | pro-B | OSCAM_PROB | Major problem | 100.0% | 79.6% |
| Pew | pro-B | OSCAM_PLAT_a | Major problem | 100.0% | 68.3% |
| Pew | pro-B | OSCAM_PLAT_b | Major problem | 99.2% | 64.8% |
| Pew | pro-C | OSCAM_PROB | Major problem | 100.0% | 79.6% |
| Pew | pro-C | OSCAM_PLAT_a | Major problem | 100.0% | 68.3% |
| Pew | pro-C | OSCAM_PLAT_b | Major problem | 99.2% | 64.8% |
| Pew | qwen-A | OSCAM_PROB | Major problem | 100.0% | 79.6% |
| Pew | qwen-A | OSCAM_PLAT_b | Major problem | 100.0% | 64.8% |
| Pew | qwen-B | OSCAM_PROB | Major problem | 100.0% | 79.6% |
| Pew | qwen-B | OSCAM_PLAT_a | Major problem | 100.0% | 68.3% |
| Pew | qwen-B | OSCAM_PLAT_b | Major problem | 99.2% | 64.8% |
| Pew | qwen-C | OSCAM_PROB | Major problem | 99.9% | 79.6% |
| Pew | qwen-C | OSCAM_PLAT_a | Major problem | 99.3% | 68.3% |
| ANES | flash-A | V241264 | Increased | 99.2% | 71.0% |
| ANES | flash-A | V241282 | Increased | 100.0% | 56.6% |
| ANES | flash-B | V241264 | Increased | 99.4% | 71.0% |
| ANES | flash-B | V241282 | Increased | 100.0% | 56.6% |
| ANES | qwen-B | V241267 | Increased | 99.4% | 65.4% |

## 口径

- 使用各调查官方权重。问卷内题目等权，三份调查等权。仅比较同一问卷所有纳入条件都完成的样本。
- 95% 区间来自 2,000 次分层配对重抽样。模型对比固定加权真人分布，同步重抽三份问卷共用的画像。真人逐人实验对每份调查独立重抽真人及对应预测。
- 模型对比的 A 组按均衡抽样直接汇总，B、C 按真人四层权重汇总，沿用首轮口径。A→B 因此同时包含汇总权重的变化。
- 真人实验在每题排除无效或插补的目标答案，并在层内使用调查权重。历史基线的分布来自评估样本外的同调查答卷，逐人指标使用同层概率最高的选项。
- 重复答卷占比以整份选项组合出现至少两次的答卷为分子，另保留最常见组合占比。公开问卷及答案统计可能曾被模型见过。

逐题误差、完整真人及模拟选项分布、选项召回率、样本覆盖和答卷重复率见同目录的 `results.json`。
