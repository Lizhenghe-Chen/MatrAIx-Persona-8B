/* Clean-v1 charts. All data are embedded aggregates; works from file:// with no network. */
(function () {
  const node = document.getElementById('clean-data');
  if (!node || typeof echarts === 'undefined') return;
  const data = JSON.parse(node.textContent);
  const ink = '#14372f', muted = '#566a63', line = '#d8e1da';
  const green = '#117b70', purple = '#5358a5', orange = '#a15e38', grey = '#9fb0a8';
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

  const resize = () => { redraws.forEach((draw) => draw()); charts.forEach((chart) => chart.resize()); };
  window.addEventListener('resize', resize);
  window.addEventListener('beforeprint', resize);
})();
