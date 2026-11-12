/* Clean-v1 charts. All data are embedded aggregates; works from file:// with no network. */
(function () {
  const node = document.getElementById('clean-data');
  if (!node || typeof echarts === 'undefined') return;
  const data = JSON.parse(node.textContent);
  const ink = '#14372f', muted = '#566a63', line = '#d8e1da';
  const green = '#117b70', purple = '#5358a5', orange = '#a15e38', grey = '#9fb0a8', blue = '#2f6f9f';
  const base = {
    textStyle: { fontFamily: '-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif', color: ink },
    animationDuration: 600
  };
  const charts = [], redraws = [];
  const mount = (id, draw) => {
    const host = document.getElementById(id);
    if (!host) return null;
    const chart = echarts.init(host, null, { renderer: 'canvas' });
    charts.push(chart);
    redraws.push(() => draw(chart, host.clientWidth < 540));
    redraws[redraws.length - 1]();
    return chart;
  };
  const narrow = (host) => host.clientWidth < 540;

  /* 1. relative to "every option equally likely" */
  mount('cleanRelative', (relative, isNarrow) => {
    const studies = [{ key: 'drone', name: '无人机配送' }, { key: 'shoes', name: '运动鞋意愿' }];
    const methods = [
      { key: 'original', name: '原生提示·单选', short: '原生单选', color: orange },
      { key: 'optimized', name: '优化·概率', short: '优化概率', color: purple },
      { key: 'reference', name: '同信息统计参照', short: '统计参照', color: green }
    ];
    const valueOf = (study, method) => {
      const block = data[study];
      const key = method === 'reference' ? block.reference : method;
      const value = block.improvement[key];
      return value === null || value === undefined ? null : Number((100 * value).toFixed(2));
    };
    const brierOf = (study, method) => {
      const block = data[study];
      const key = method === 'reference' ? block.reference : method;
      const entry = block.arms[key];
      return entry && entry[0] !== null && entry[0] !== undefined ? entry[0].toFixed(4) : '不可估计';
    };
    relative.setOption(Object.assign({}, base, {
      tooltip: {
        trigger: 'axis',
        formatter: (items) => {
          const study = studies[items[0].dataIndex].key;
          return items.map((item) => {
            const method = methods[item.seriesIndex].key;
            const shown = item.value === null ? '不可估计' : item.value.toFixed(1) + '%';
            return item.marker + item.seriesName + '：' + shown + '（Brier ' + brierOf(study, method) + '）';
          }).join('<br>');
        }
      },
      legend: { data: methods.map((m) => m.name), bottom: 0, textStyle: { color: muted } },
      grid: { left: isNarrow ? 96 : 150, right: isNarrow ? 44 : 74, top: 26, bottom: 62 },
      xAxis: {
        type: 'value', name: '相对“每档等可能”的改善（→ 更准）', nameLocation: 'middle', nameGap: 30,
        min: -100, max: 50, interval: isNarrow ? 50 : 25,
        axisLabel: { formatter: '{value}%', color: muted, hideOverlap: true },
        splitLine: { lineStyle: { color: line } }
      },
      yAxis: {
        type: 'category', inverse: true,
        data: studies.flatMap((study) => methods.map((method) =>
          (isNarrow ? (study.key === 'drone' ? '无人机' : '运动鞋') + '·' : study.name + ' · ') + method.short)),
        axisLabel: { color: ink, fontSize: isNarrow ? 11 : 13 }, axisLine: { lineStyle: { color: line } }
      },
      series: [{
        type: 'bar', barMaxWidth: 26,
        data: studies.flatMap((study) => methods.map((method) => ({
          value: valueOf(study.key, method.key),
          itemStyle: { color: method.color }
        }))),
        label: {
          show: true, color: ink, fontSize: isNarrow ? 11 : 12, position: 'right', distance: 7,
          formatter: (p) => (p.value === null ? '不可估计' : p.value.toFixed(1) + '%')
        },
        markLine: {
          silent: true, symbol: 'none', lineStyle: { color: grey, type: 'dashed' },
          data: [{ xAxis: 0 }], label: { formatter: '等分', color: muted, position: 'start' }
        }
      }]
    }, true));
  });

  /* 2. drone: real share per card vs predicted */
  mount('cleanScatter', (scatter, isNarrow) => {
    const points = data.drone.scatter.map((p) => [Number((100 * p.actual).toFixed(2)), Number((100 * p.predicted).toFixed(2)), p.n]);
    const bands = Object.keys(data.drone.bands).map((key) => [key, data.drone.bands[key]]);
    scatter.setOption(Object.assign({}, base, {
      tooltip: {
        trigger: 'item',
        formatter: (p) => (p.seriesType === 'scatter'
          ? '真实 ' + p.value[0].toFixed(1) + '% · AI 预测 ' + p.value[1].toFixed(1) + '%<br>该卡回答人数 ' + p.value[2]
          : p.name + '：' + p.value + ' 张卡')
      },
      grid: [
        { left: isNarrow ? 52 : 70, right: isNarrow ? 18 : 26, top: 26, height: '50%' },
        { left: isNarrow ? 52 : 70, right: isNarrow ? 18 : 26, top: '72%', height: '16%' }
      ],
      xAxis: [
        {
          type: 'value', min: 0, max: 100, gridIndex: 0,
          name: '真人选择率', nameLocation: 'middle', nameGap: 28,
          axisLabel: { formatter: '{value}%', color: muted }, splitLine: { lineStyle: { color: line } }
        },
        {
          type: 'category', gridIndex: 1, data: bands.map((b) => b[0]),
          axisLabel: { color: muted, fontSize: 11 }, axisLine: { lineStyle: { color: line } }
        }
      ],
      yAxis: [
        {
          type: 'value', min: 0, max: 100, name: 'AI 预测率', nameTextStyle: { color: muted },
          axisLabel: { formatter: '{value}%', color: muted }, splitLine: { lineStyle: { color: line } }
        },
        { type: 'value', gridIndex: 1, axisLabel: { show: false }, axisTick: { show: false }, axisLine: { show: false }, splitLine: { show: false } }
      ],
      legend: { data: ['题卡', '完全学会'], right: 0, top: 0, itemWidth: 14, itemHeight: 8,
        textStyle: { color: muted, fontSize: 11 } },
      series: [
        {
          name: '完全学会', type: 'line', data: [[0, 0], [100, 100]], showSymbol: false, silent: true,
          lineStyle: { color: green, type: 'dashed', width: 1.5 }, itemStyle: { color: green }
        },
        {
          name: '题卡', type: 'scatter', data: points, symbolSize: 7,
          itemStyle: { color: 'rgba(83,88,165,0.62)', borderColor: 'rgba(83,88,165,0.95)' }
        },
        {
          name: '真人分布', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
          data: bands.map((b) => b[1]), itemStyle: { color: green }, barMaxWidth: 26
        }
      ],
      title: {
        text: '上：一卡一点　下：真人选择率的分布',
        left: 0, bottom: 0, textStyle: { fontSize: 12, color: muted, fontWeight: 'normal' }
      }
    }));
  });

  /* 3. drone overall mix */
  mount('cleanDonut', (donut) => {
    const actual = 100 * data.drone.actual_drone_share;
    const predicted = 100 * data.drone.predicted_drone_share;
    donut.setOption(Object.assign({}, base, {
      tooltip: { trigger: 'item', formatter: '{b}：{c}%' },
      legend: { bottom: 0, textStyle: { color: muted } },
      title: [
        { text: '真人', subtext: '无人机 ' + actual.toFixed(1) + '%', left: '27%', top: '2%', textAlign: 'center',
          textStyle: { fontSize: 15, color: muted, fontWeight: 'normal' }, subtextStyle: { fontSize: 13, color: ink } },
        { text: 'AI 预测', subtext: '无人机 ' + predicted.toFixed(1) + '%', left: '75%', top: '2%', textAlign: 'center',
          textStyle: { fontSize: 15, color: muted, fontWeight: 'normal' }, subtextStyle: { fontSize: 13, color: ink } }
      ],
      series: [
        {
          name: '真人', type: 'pie', radius: ['34%', '62%'], center: ['27%', '57%'],
          label: { show: false }, labelLine: { show: false },
          data: [
            { name: '地面车', value: Number((100 - actual).toFixed(1)), itemStyle: { color: grey } },
            { name: '无人机', value: Number(actual.toFixed(1)), itemStyle: { color: green } }
          ]
        },
        {
          name: 'AI 预测', type: 'pie', radius: ['34%', '62%'], center: ['75%', '57%'],
          label: { show: false }, labelLine: { show: false },
          data: [
            { name: '地面车', value: Number((100 - predicted).toFixed(1)), itemStyle: { color: grey } },
            { name: '无人机', value: Number(predicted.toFixed(1)), itemStyle: { color: green } }
          ]
        }
      ]
    }));
  });

  /* 4. shoes: rating distribution */
  mount('cleanRating', (rating, isNarrow) => {
    rating.setOption(Object.assign({}, base, {
      tooltip: { trigger: 'axis', valueFormatter: (v) => v.toFixed(1) + '%' },
      legend: { data: ['真人', 'AI 预测'], bottom: 0, textStyle: { color: muted } },
      grid: { left: isNarrow ? 50 : 62, right: isNarrow ? 16 : 24, top: 30, bottom: 66 },
      xAxis: {
        type: 'category', data: ['1', '2', '3', '4', '5', '6', '7'],
        name: '评分', nameLocation: 'middle', nameGap: 28,
        axisLabel: { color: ink }, axisLine: { lineStyle: { color: line } }
      },
      yAxis: {
        type: 'value', name: '占比', axisLabel: { formatter: '{value}%', color: muted },
        splitLine: { lineStyle: { color: line } }
      },
      series: [
        {
          name: '真人', type: 'bar', barMaxWidth: 30, itemStyle: { color: green },
          data: data.shoes.human_histogram.map((v) => Number((100 * v).toFixed(1)))
        },
        {
          name: 'AI 预测', type: 'bar', barMaxWidth: 30, itemStyle: { color: purple },
          data: data.shoes.model_histogram.map((v) => Number((100 * v).toFixed(1)))
        }
      ]
    }));
  });

  /* 5. variation kept */
  mount('cleanVariation', (variation, isNarrow) => {
    const v = data.shoes.variation;
    variation.setOption(Object.assign({}, base, {
      tooltip: { trigger: 'axis', valueFormatter: (x) => x.toFixed(1) + '%' },
      grid: { left: isNarrow ? 88 : 108, right: isNarrow ? 18 : 46, top: 30, bottom: 46 },
      xAxis: { type: 'value', max: 120, interval: 20, axisLabel: { formatter: '{value}%', color: muted }, splitLine: { lineStyle: { color: line } } },
      yAxis: {
        type: 'category', inverse: true, data: ['人与人之间', '同一人跨商品'],
        axisLabel: { color: ink }, axisLine: { lineStyle: { color: line } }
      },
      series: [{
        type: 'bar', barMaxWidth: 40,
        data: [
          { value: Number((100 * v.between_kept).toFixed(1)), itemStyle: { color: purple } },
          { value: Number((100 * v.within_kept).toFixed(1)), itemStyle: { color: orange } }
        ],
        label: {
          show: true, position: 'right', color: ink, fontSize: 12,
          formatter: (p) => isNarrow
            ? p.value.toFixed(0) + '%'
            : p.value.toFixed(0) + '%（真人 ' + (p.dataIndex === 0 ? v.between_human.toFixed(2) : v.within_human.toFixed(2))
              + ' → AI ' + (p.dataIndex === 0 ? v.between_model.toFixed(2) : v.within_model.toFixed(2)) + '）'
        },
        markLine: {
          silent: true, symbol: 'none', lineStyle: { color: grey, type: 'dashed' },
          data: [{ xAxis: 100 }], label: { show: false }
        }
      }]
    }));
  });

  /* 6. wide round: AI vs same-information reference, both relative to "every option equally likely" */
  const wideNode = document.getElementById('wide-data');
  if (wideNode) {
    const wide = JSON.parse(wideNode.textContent);
    const labels = { origin: '商品产地', packaging: '包装与拒买', pew111: '网购与达人',
                     german: '德国番茄', tshirt: '美国 T 恤', radiant: '西班牙番茄' };
    mount('wideCompare', (chart, isNarrow) => {
      const rows = wide.rows;
      chart.setOption(Object.assign({}, base, {
        tooltip: {
          trigger: 'axis', axisPointer: { type: 'shadow' },
          formatter: (items) => {
            const row = rows[items[0].dataIndex];
            const ref = row.reference === null ? '不可估计' : row.reference.toFixed(1) + '%';
            const gap = row.gap === null ? '—' : row.gap.toFixed(1) + '%（区间 '
              + row.ci[0].toFixed(1) + ', ' + row.ci[1].toFixed(1) + '）';
            return '<b>' + labels[row.study] + '</b> · ' + row.people + ' 人<br>'
              + 'AI 优化 vs 等分：' + row.ai.toFixed(1) + '%<br>'
              + '统计参照 vs 等分：' + ref + '<br>AI vs 参照：' + gap;
          }
        },
        legend: { data: ['AI 优化', '同信息统计参照'], bottom: 0, textStyle: { color: muted } },
        grid: { left: isNarrow ? 56 : 72, right: isNarrow ? 16 : 26, top: 30, bottom: 72 },
        xAxis: {
          type: 'category', data: rows.map((r) => labels[r.study] || r.study),
          axisLabel: { color: ink, fontSize: isNarrow ? 10 : 12, interval: 0,
                       rotate: isNarrow ? 40 : 0 },
          axisLine: { lineStyle: { color: line } }
        },
        yAxis: {
          type: 'value', name: '相对“每档等分”的改善', nameTextStyle: { color: muted },
          axisLabel: { formatter: '{value}%', color: muted }, splitLine: { lineStyle: { color: line } }
        },
        series: [
          { name: 'AI 优化', type: 'bar', barMaxWidth: 26, itemStyle: { color: purple },
            data: rows.map((r) => r.ai) },
          { name: '同信息统计参照', type: 'bar', barMaxWidth: 26, itemStyle: { color: green },
            data: rows.map((r) => r.reference) },
          { name: '等分', type: 'line', showSymbol: false, silent: true,
            lineStyle: { color: grey, type: 'dashed' }, data: rows.map(() => 0) }
        ]
      }));
    });
  }

  /* 7. all studies: AI minus reference, with 95% intervals */
  const allNode = document.getElementById('all-data');
  if (allNode) {
    const all = JSON.parse(allNode.textContent);
    const labels = { anes: '美国公共支出', pew168: '美国诈骗风险', shed: '美国消费调整',
                     pew13: '美国购物看法', dryer: '四国烘干机', swiss: '瑞士家电规格',
                     drone: '美国无人机配送', shoes: '美国运动鞋（打分）', origin: '美国商品产地',
                     packaging: '美国包装与拒买', pew111: '美国网购与达人', german: '德国番茄包装',
                     tshirt: '美国 T 恤', radiant: '西班牙悬挂番茄' };
    const rows = all.rows.filter((r) => r.ai_vs_reference !== null)
      .slice().sort((a, b) => a.ai_vs_reference - b.ai_vs_reference);
    mount('allCompare', (chart, isNarrow) => {
      const low = rows.map((r) => 100 * r.ai_vs_reference_ci[0]);
      const high = rows.map((r) => 100 * r.ai_vs_reference_ci[1]);
      chart.setOption(Object.assign({}, base, {
        tooltip: {
          trigger: 'axis', axisPointer: { type: 'shadow' },
          formatter: (items) => {
            const row = rows[items[0].dataIndex];
            return '<b>' + (labels[row.study] || row.study) + '</b><br>'
              + '簇：' + row.cluster + ' · ' + row.people + ' 人<br>'
              + 'AI vs 参照：' + (100 * row.ai_vs_reference).toFixed(1) + '%<br>'
              + '区间：[' + (100 * row.ai_vs_reference_ci[0]).toFixed(1) + ', '
              + (100 * row.ai_vs_reference_ci[1]).toFixed(1) + ']';
          }
        },
        grid: { left: isNarrow ? 118 : 150, right: isNarrow ? 44 : 60, top: 24, bottom: 46 },
        xAxis: {
          type: 'value', name: 'AI 相对统计参照的 Brier 改善', nameTextStyle: { color: muted },
          axisLabel: { formatter: '{value}%', color: muted }, splitLine: { lineStyle: { color: line } }
        },
        yAxis: {
          type: 'category', data: rows.map((r) => labels[r.study] || r.study),
          axisLabel: { color: ink, fontSize: isNarrow ? 11 : 13 },
          axisLine: { lineStyle: { color: line } }
        },
        series: [
          { name: 'AI vs 参照', type: 'bar', barMaxWidth: 20,
            itemStyle: { color: orange }, data: rows.map((r) => 100 * r.ai_vs_reference),
            label: { show: !isNarrow, position: 'left', color: ink, fontSize: 11,
                     formatter: (p) => p.value.toFixed(1) + '%' } },
          { name: '零线', type: 'line', showSymbol: false, silent: true,
            lineStyle: { color: green, type: 'dashed', width: 1.4 },
            data: rows.map(() => 0),
            markLine: { silent: true, symbol: 'none', lineStyle: { color: green, type: 'dashed' },
                        data: [{ xAxis: 0 }], label: { formatter: '与参照持平', color: green, position: 'end' } } }
        ]
      }));
    });
  }

  /* 7. direction correctness: does the model rank options the way people did? */
  (function () {
    const node = document.getElementById('direction-data');
    if (!node) return;
    const direction = JSON.parse(node.textContent);
    const labels = { anes: '公共支出', pew13: '购物看法', pew168: '诈骗风险', shed: '消费调整',
      packaging: '包装与拒买', pew111: '网购与达人', german: '德国番茄', radiant: '西班牙番茄' };
    mount('directionCompare', (chart, isNarrow) => {
      const rows = direction.blocks.slice().sort((a, b) => b.ai_argmax - a.ai_argmax);
      chart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
          formatter: (items) => {
            const row = rows[items[0].dataIndex];
            return labels[row.study] || row.study
              + '<br>可估题卡：' + row.cards
              + '<br>AI 排对第一：' + (100 * row.ai_argmax).toFixed(0) + '%'
              + '<br>参照排对第一：' + (row.reference_argmax === null ? '—'
                  : (100 * row.reference_argmax).toFixed(0) + '%')
              + '<br>AI 份额中位误差：' + (100 * row.ai_median_share_error).toFixed(1) + 'pp';
          } },
        legend: { data: ['AI', '同信息参照'], top: 0, textStyle: { color: muted } },
        grid: { left: isNarrow ? 92 : 108, right: 58, top: 34, bottom: 34 },
        xAxis: { type: 'value', max: 100, name: '第一名排对比例', nameTextStyle: { color: muted },
          axisLabel: { formatter: '{value}%', color: muted }, splitLine: { lineStyle: { color: line } } },
        yAxis: { type: 'category', data: rows.map((r) => labels[r.study] || r.study),
          axisLabel: { color: ink, fontSize: isNarrow ? 11 : 13 }, axisLine: { lineStyle: { color: line } } },
        series: [
          { name: 'AI', type: 'bar', barMaxWidth: 14, itemStyle: { color: green },
            data: rows.map((r) => Number((100 * r.ai_argmax).toFixed(1))),
            label: { show: !isNarrow, position: 'right', color: ink, fontSize: 11,
                     formatter: (p) => p.value.toFixed(0) + '%' } },
          { name: '同信息参照', type: 'bar', barMaxWidth: 14, itemStyle: { color: purple },
            data: rows.map((r) => r.reference_argmax === null ? null
              : Number((100 * r.reference_argmax).toFixed(1))),
            label: { show: !isNarrow, position: 'right', color: muted, fontSize: 11,
                     formatter: (p) => p.value.toFixed(0) + '%' } }
        ]
      });
    });

    /* 8. where the persona helps: advantage over the population distribution by atypicality */
    mount('deviationQuintiles', (chart, isNarrow) => {
      const plans = Object.keys(direction.deviation);
      const colours = [purple, green, orange, grey];
      const names = { 'v1': '六研究轮', 'clean-v1': '干净实验轮', 'wide-v1': '六套新研究轮' };
      const first = direction.deviation[plans[0]];
      const quintiles = first.quintiles.map((q) => 'Q' + q.quintile);
      const ranges = first.quintiles.map((q) => q.atypical_from.toFixed(2) + '–' + q.atypical_to.toFixed(2));
      chart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
          formatter: (items) => {
            const index = items[0].dataIndex;
            const lines = ['偏离度 ' + ranges[index] + '（越大越不典型）'];
            plans.forEach((plan) => {
              const q = direction.deviation[plan].quintiles[index];
              lines.push(names[plan] + '：' + q.ai_advantage.toFixed(3)
                + '（区间 ' + q.ai_advantage_ci[0].toFixed(3) + ', ' + q.ai_advantage_ci[1].toFixed(3) + '）'
                + ' · AI ' + q.ai_brier.toFixed(3) + ' vs 人群分布 ' + q.population_brier.toFixed(3));
            });
            return lines.join('<br>');
          } },
        legend: { data: plans.map((p) => names[p] || p), top: 0, textStyle: { color: muted } },
        grid: { left: isNarrow ? 52 : 66, right: 24, top: 42, bottom: 40 },
        xAxis: { type: 'category', data: quintiles, axisLabel: { color: muted },
          axisLine: { lineStyle: { color: line } } },
        yAxis: { type: 'value', name: '相对人群分布的 Brier 优势', nameTextStyle: { color: muted },
          axisLabel: { color: muted }, splitLine: { lineStyle: { color: line } } },
        series: plans.map((plan, index) => ({
          name: names[plan] || plan, type: 'bar', barMaxWidth: 26,
          itemStyle: { color: colours[index % colours.length] },
          data: direction.deviation[plan].quintiles.map((q) => Number(q.ai_advantage.toFixed(3))),
          label: { show: !isNarrow, position: 'top', fontSize: 10, color: muted,
                   formatter: (p) => p.value.toFixed(2) },
          markLine: index === 0 ? { silent: true, symbol: 'none',
            lineStyle: { color: ink, type: 'dashed', width: 1 },
            data: [{ yAxis: 0 }], label: { formatter: '与人群分布持平', color: ink, position: 'insideEndTop' } } : undefined
        }))
      });
    });
  })();

  /* 9. anchor-v1: hand the model the distribution and see what is left */
  (function () {
    const node = document.getElementById('anchor-data');
    if (!node) return;
    const anchor = JSON.parse(node.textContent);
    mount('anchorCompare', (chart, isNarrow) => {
      const studies = ['german', 'pew111'];
      const order = ['optimized', 'anchored', 'bounded', 'stratum_history', 'uniform'];
      const colours = { optimized: orange, anchored: purple, bounded: blue,
                        stratum_history: green, uniform: grey };
      const labels = studies.map((s) => anchor.frame[s] || s);
      chart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
          formatter: (items) => {
            const index = items[0].dataIndex;
            return (anchor.frame[studies[index]] || studies[index]) + '<br>'
              + anchor.rows.filter((r) => r.study === studies[index])
                  .map((r) => anchor.arm_name[r.arm] + '：' + r.brier.toFixed(3)).join('<br>');
          } },
        legend: { data: order.map((a) => anchor.arm_name[a]), top: 0, textStyle: { color: muted } },
        grid: { left: isNarrow ? 46 : 56, right: 24, top: 52, bottom: 34 },
        xAxis: { type: 'category', data: labels, axisLabel: { color: ink },
          axisLine: { lineStyle: { color: line } } },
        yAxis: { type: 'value', name: 'Brier（越低越好）', nameTextStyle: { color: muted },
          min: 0, axisLabel: { color: muted }, splitLine: { lineStyle: { color: line } } },
        series: order.map((arm) => ({
          name: anchor.arm_name[arm], type: 'bar', barMaxWidth: 26,
          itemStyle: { color: colours[arm] || grey },
          data: studies.map((s) => {
            const row = anchor.rows.find((r) => r.study === s && r.arm === arm);
            return row ? Number(row.brier.toFixed(3)) : null;
          }),
          label: { show: !isNarrow, position: 'top', fontSize: 10, color: muted,
                   formatter: (p) => p.value === null ? '' : p.value.toFixed(3) }
        }))
      });
    });
  })();

  const resize = () => { redraws.forEach((draw) => draw()); charts.forEach((chart) => chart.resize()); };
  window.addEventListener('resize', resize);
  window.addEventListener('beforeprint', resize);
})();
