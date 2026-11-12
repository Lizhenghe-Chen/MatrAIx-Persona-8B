/* Story-report charts. All values are embedded aggregates; works from file:// with no network. */
(function () {
  const node = document.getElementById('story-data');
  if (!node || typeof echarts === 'undefined') return;
  const data = JSON.parse(node.textContent);
  const ink = '#14372f', muted = '#566a63', line = '#d8e1da';
  const green = '#117b70', purple = '#5358a5', orange = '#a15e38', grey = '#9fb0a8', blue = '#2f6f9f';
  const charts = [], redraws = [];
  const mount = (id, draw) => {
    const host = document.getElementById(id);
    if (!host) return;
    const chart = echarts.init(host, null, { renderer: 'canvas' });
    charts.push(chart);
    const redraw = () => draw(chart, host.clientWidth < 560);
    redraws.push(redraw);
    redraw();
  };

  /* 1. every study: model versus the same-information reference */
  mount('storyCompare', (chart, narrow) => {
    const rows = data.rows.slice().sort((a, b) => a.ai_vs_reference - b.ai_vs_reference);
    chart.setOption({
      tooltip: {
        trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: (items) => {
          const row = rows[items[0].dataIndex];
          return row.label + '<br>AI 相对查表：' + (100 * row.ai_vs_reference).toFixed(1) + '%'
            + '<br>95% 区间：[' + (100 * row.ci[0]).toFixed(1) + ', ' + (100 * row.ci[1]).toFixed(1) + ']%';
        }
      },
      grid: { left: narrow ? 108 : 132, right: 62, top: 22, bottom: 56 },
      xAxis: {
        type: 'value', name: '相对查表的改善（%）', nameLocation: 'middle', nameGap: 28,
        nameTextStyle: { color: muted },
        axisLabel: { formatter: '{value}%', color: muted }, splitLine: { lineStyle: { color: line } }
      },
      yAxis: {
        type: 'category', data: rows.map((r) => r.label),
        axisLabel: { color: ink, fontSize: narrow ? 11 : 13 }, axisLine: { lineStyle: { color: line } }
      },
      series: [{
        type: 'bar', barMaxWidth: 18, itemStyle: { color: orange },
        data: rows.map((r) => Number((100 * r.ai_vs_reference).toFixed(1))),
        label: { show: true, position: 'right', distance: 6, color: ink, fontSize: 11,
                 formatter: (p) => p.value.toFixed(1) + '%' },
        markLine: {
          silent: true, symbol: 'none', lineStyle: { color: green, type: 'dashed', width: 1.4 },
          data: [{ xAxis: 0 }], label: { formatter: '与查表持平', color: green, position: 'end' }
        }
      }]
    });
  });

  /* 2. how many real answers before counting beats the model */
  mount('storyCrossover', (chart, narrow) => {
    const ks = ['5', '10', '20', '40', '80', '160', '320'];
    const palette = ['#117b70', '#5358a5', '#a15e38', '#2f6f9f', '#7d5ba6', '#8a6d3b', '#4f7c59', '#9b4f6f'];
    chart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { type: 'scroll', top: 0, textStyle: { color: muted, fontSize: 11 } },
      grid: { left: 54, right: 26, top: 54, bottom: 44 },
      xAxis: {
        type: 'category', data: ks, name: '小样本人数', nameTextStyle: { color: muted },
        axisLabel: { color: muted }
      },
      yAxis: {
        type: 'value', name: '分布误差（百分点）', nameTextStyle: { color: muted },
        axisLabel: { color: muted }, splitLine: { lineStyle: { color: line } }
      },
      series: data.curves.map((curve, index) => ({
        name: curve.label, type: 'line', smooth: true, symbolSize: 5,
        lineStyle: { width: 2, color: palette[index % palette.length] },
        itemStyle: { color: palette[index % palette.length] },
        data: curve.values,
        markLine: curve.ai === null ? undefined : {
          silent: true, symbol: 'none',
          lineStyle: { width: 1, type: 'dashed', color: palette[index % palette.length] },
          data: [{ yAxis: curve.ai }], label: { show: false }
        }
      }))
    });
  });

  /* 3. external validation: four ways to answer the same 14 questions */
  mount('storyExternal', (chart, narrow) => {
    const rows = data.external.rows.filter((r) => r.value !== null && r.value !== undefined);
    chart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: (items) => rows[items[0].dataIndex].label + '：'
          + rows[items[0].dataIndex].value.toFixed(1) + ' 个百分点' },
      grid: { left: 44, right: 26, top: 26, bottom: narrow ? 92 : 54 },
      xAxis: {
        type: 'category', data: rows.map((r) => r.label),
        axisLabel: { color: ink, interval: 0, rotate: narrow ? 42 : 0, fontSize: narrow ? 10 : 12 },
        axisLine: { lineStyle: { color: line } }
      },
      yAxis: {
        type: 'value', name: '分布误差（越低越好）', nameTextStyle: { color: muted },
        axisLabel: { color: muted }, splitLine: { lineStyle: { color: line } }
      },
      series: [{
        type: 'bar', barMaxWidth: 46,
        itemStyle: {
          color: (p) => [orange, orange, purple, grey, green][p.dataIndex] || grey
        },
        data: rows.map((r) => Number(r.value.toFixed(1))),
        label: { show: true, position: 'top', color: ink, fontSize: 12,
                 formatter: (p) => p.value.toFixed(1) }
      }]
    });
  });

  const resize = () => { redraws.forEach((draw) => draw()); charts.forEach((chart) => chart.resize()); };
  window.addEventListener('resize', resize);
  window.addEventListener('beforeprint', resize);
})();
