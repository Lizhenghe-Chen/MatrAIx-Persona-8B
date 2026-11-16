(() => {
  const gains = JSON.parse(document.getElementById('purchase-data').textContent);
  const container = document.getElementById('purchase-chart');
  const frame = container.parentElement;
  const graph = echarts.init(container);
  const plotRows = gains.map((row, i) => ({
    name: row.label,
    value: [row.absolute, i, ...row.ci95],
    itemStyle: {color: row.holds ? '#17745a' : '#647b9a'}
  }));
  graph.setOption({
    animation: false,
    grid: {left: 159, right: 37, top: 12, bottom: 31},
    tooltip: {
      trigger: 'item', renderMode: 'richText', confine: true,
      formatter: ({dataIndex}) => {
        const row = gains[dataIndex];
        return row.label + '\n评估人数或户数 ' + row.people + '\nBrier 误差下降 ' + row.absolute.toFixed(4) +
          '\n95% 区间 [' + row.ci95.map(x => x.toFixed(4)).join(', ') + ']';
      }
    },
    xAxis: {
      type: 'value',
      min: Math.floor(20 * Math.min(0, ...gains.map(row => row.ci95[0]))) / 20,
      max: Math.ceil(20 * Math.max(...gains.map(row => row.ci95[1]))) / 20,
      axisLabel: {formatter: x => x.toFixed(2)},
      splitLine: {lineStyle: {color: '#e4ebf3'}}
    },
    yAxis: {
      type: 'category', inverse: true, data: gains.map(row => row.label),
      axisTick: {show: false}, axisLine: {show: false},
      axisLabel: {width: 146, overflow: 'truncate', fontSize: 12, color: '#243953'}
    },
    series: [
      {
        type: 'scatter',
        data: plotRows.map(row => [0, row.value[1]]),
        symbolSize: 0,
        silent: true,
        markLine: {symbol: 'none', silent: true, label: {show: false}, data: [{xAxis: 0}],
          lineStyle: {color: '#4a5e74', type: 'solid'}}
      },
      {
        type: 'custom',
        data: plotRows,
        encode: {x: [0, 2, 3], y: 1},
        renderItem: (params, api) => {
          const [value, y, low, high] = [0, 1, 2, 3].map(i => api.value(i));
          const [point, start, end] = [value, low, high].map(x => api.coord([x, y]));
          const color = plotRows[params.dataIndex].itemStyle.color;
          return {
            type: 'group',
            children: [
              {type: 'line', shape: {x1: start[0], y1: start[1], x2: end[0], y2: end[1]},
                style: {stroke: color, lineWidth: 2}},
              {type: 'circle', shape: {cx: point[0], cy: point[1], r: 4.6}, style: {fill: color}}
            ]
          };
        }
      }
    ]
  });
  function resize() {
    const width = Math.max(frame.clientWidth, 545);
    container.style.width = width + 'px';
    document.getElementById('purchase-scroll').hidden = width <= frame.clientWidth;
    graph.resize();
  }
  resize();
  if (typeof ResizeObserver === 'function') new ResizeObserver(resize).observe(frame);
  else window.addEventListener('resize', resize);
})();
