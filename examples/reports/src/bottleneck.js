(() => {
  const spec = JSON.parse(document.getElementById('mechanism-data').textContent);
  const element = document.getElementById('mechanism-chart');
  const chart = echarts.init(element);
  let narrow;
  function render() {
    chart.resize();
    const compact = element.clientWidth < 440;
    if (compact === narrow) return;
    narrow = compact;
    chart.setOption({
      animation: false,
      textStyle: {fontFamily: getComputedStyle(document.body).fontFamily},
      grid: {left: 35, right: 13, top: 18, bottom: 42},
      tooltip: {
        trigger: 'axis', renderMode: 'richText', confine: true, axisPointer: {type: 'shadow'},
        valueFormatter: value => Number(value).toFixed(2) + ' 个百分点'
      },
      xAxis: {
        type: 'category', data: spec.labels,
        axisTick: {show: false}, axisLabel: {interval: 0, fontSize: compact ? 11 : 13, color: '#192b42'}
      },
      yAxis: {
        type: 'value', min: 0, max: 60, interval: 15,
        axisLabel: {color: '#4a5e74'}, splitLine: {lineStyle: {color: '#e4ebf3'}}
      },
      series: [
        {name: '只保留最高项', data: spec.argmax, color: '#a2b0c5'},
        {name: '汇总全部概率', data: spec.full, color: '#244d98'}
      ].map(({name, data, color}) => ({
        type: 'bar', name, data, barMaxWidth: compact ? 42 : 75, barGap: '22%',
        itemStyle: {color, borderRadius: [5, 5, 0, 0]},
        label: {show: true, position: 'top', fontSize: compact ? 11 : 13,
          fontWeight: 700, color: '#192b42', formatter: ({value}) => Number(value).toFixed(2)}
      }))
    }, true);
  }
  render();
  if (typeof ResizeObserver === 'function') new ResizeObserver(render).observe(element);
  else window.addEventListener('resize', render);
})();
