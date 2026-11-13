/* Per-question charts: one bar group per study, three distributions side by side. */
(function () {
  const node = document.getElementById('card-data');
  if (!node || typeof echarts === 'undefined') return;
  const data = JSON.parse(node.textContent);
  const ink = '#14372f', muted = '#566a63', line = '#d8e1da';
  const native = '#a15e38', optimized = '#5358a5', human = '#14372f';
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

  Object.entries(data.pooled).forEach(([study, pooled]) => {
    if (!pooled) return;
    mount('pool-' + study, (chart, narrow) => {
      const count = pooled.options;
      const labels = Array.from({ length: count }, (_, i) => '第 ' + (i + 1) + ' 位');
      const series = [
        { name: '真人', data: pooled.truth, color: human },
        { name: '原版 MatrAIx', data: pooled.original, color: native },
        { name: '优化后', data: pooled.optimized, color: optimized }
      ].filter((s) => s.data);
      chart.setOption({
        tooltip: {
          trigger: 'axis', axisPointer: { type: 'shadow' },
          formatter: (items) => {
            const index = items[0].dataIndex;
            return (data.labels[study] || study) + ' · 选项位置 ' + (index + 1)
              + '<br><span style="color:' + muted + '">按选项位置对齐，不是同一道题</span><br>'
              + series.map((s) => s.name + '：' + (100 * s.data[index]).toFixed(1) + '%').join('<br>');
          }
        },
        legend: { data: series.map((s) => s.name), top: 0, textStyle: { color: muted } },
        grid: { left: 52, right: 18, top: 34, bottom: 30 },
        xAxis: {
          type: 'category', data: labels, axisLabel: { color: muted, fontSize: narrow ? 10 : 12 },
          axisLine: { lineStyle: { color: line } }
        },
        yAxis: {
          type: 'value', name: '占比', nameTextStyle: { color: muted },
          axisLabel: { formatter: '{value}%', color: muted }, splitLine: { lineStyle: { color: line } }
        },
        series: series.map((s) => ({
          name: s.name, type: 'bar', barMaxWidth: 22, itemStyle: { color: s.color },
          data: s.data.map((v) => Number((100 * v).toFixed(1)))
        }))
      });
    });
  });

  const resize = () => { redraws.forEach((draw) => draw()); charts.forEach((chart) => chart.resize()); };
  window.addEventListener('resize', resize);
  window.addEventListener('beforeprint', resize);
})();
