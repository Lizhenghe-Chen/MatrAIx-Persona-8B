/* Drawer-driven per-question charts.

Charts are built lazily: the page holds 460 questions, but a canvas is only created
when its drawer is first opened. That keeps the initial paint cheap and the DOM small.
*/
(function () {
  const node = document.getElementById('card-data');
  if (!node || typeof echarts === 'undefined') return;
  const data = JSON.parse(node.textContent);
  const ink = '#14372f', muted = '#566a63', line = '#d8e1da';
  const colours = { truth: '#14372f', original: '#a15e38', optimized: '#5358a5' };
  const names = { truth: '真人', original: '原版 MatrAIx', optimized: '优化后' };

  const chartFor = (host) => echarts.getInstanceByDom(host) || echarts.init(host, null, { renderer: 'canvas' });
  const short = (text, limit) => {
    const clean = String(text || '').replace(/\s+/g, ' ').trim();
    return clean.length > limit ? clean.slice(0, limit - 1) + '…' : clean;
  };

  /* One question: grouped vertical bars. Option text lives in the tooltip and the
     table below the chart, so nothing is truncated into ambiguity. */
  const drawQuestion = (host) => {
    const index = Number(host.id.split('-').pop());
    const study = host.id.slice('qchart-'.length, host.id.length - String(index).length - 1);
    const card = (data.charts[study] || [])[index];
    if (!card) return null;
    const series = [
      { key: 'truth', data: card.truth },
      { key: 'original', data: card.original },
      { key: 'optimized', data: card.optimized }
    ].filter((s) => s.data);
    const chart = chartFor(host);
    chart.setOption({
      animationDuration: 420,
      tooltip: {
        trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: (items) => {
          const row = items[0].dataIndex;
          const ref = card.truth[row];
          const lines = ['<b>' + short(card.options[row], 110) + '</b>'];
          series.forEach((s) => {
            const value = s.data[row];
            const gap = 100 * (value - ref);
            lines.push(names[s.key] + '：' + (100 * value).toFixed(1) + '%'
              + (s.key === 'truth' ? '' : '（' + (gap >= 0 ? '+' : '') + gap.toFixed(1) + 'pp）'));
          });
          return lines.join('<br>');
        }
      },
      legend: { data: series.map((s) => names[s.key]), top: 0,
                textStyle: { color: muted, fontSize: 12 } },
      grid: { left: 10, right: 12, top: 36, bottom: 10, containLabel: true },
      xAxis: {
        type: 'category',
        data: card.options.map((_, i) => String(i + 1)),
        axisLabel: { color: ink, fontSize: 12 },
        axisLine: { lineStyle: { color: line } },
        axisTick: { show: false }
      },
      yAxis: {
        type: 'value', max: 100, name: '占比 %', nameTextStyle: { color: muted },
        axisLabel: { formatter: '{value}%', color: muted },
        splitLine: { lineStyle: { color: line } }
      },
      series: series.map((s) => ({
        name: names[s.key], type: 'bar', barMaxWidth: 22, barGap: '12%',
        itemStyle: { color: colours[s.key], borderRadius: [3, 3, 0, 0] },
        data: s.data.map((v) => Number((100 * v).toFixed(1))),
        label: { show: true, position: 'top', color: muted, fontSize: 10,
                 formatter: (p) => (p.value >= 3 ? p.value.toFixed(0) + '%' : '') }
      }))
    }, true);
    chart.resize();
    return chart;
  };

  /* Pooled picture for studies whose every card is unique. */
  const drawPooled = (host) => {
    const block = data.pooled[host.dataset.pool];
    if (!block) return null;
    const labels = Array.from({ length: block.options }, (_, i) => '第 ' + (i + 1) + ' 位');
    const series = [
      { key: 'truth', data: block.truth },
      { key: 'original', data: block.original },
      { key: 'optimized', data: block.optimized }
    ].filter((s) => s.data);
    const chart = chartFor(host);
    chart.setOption({
      tooltip: {
        trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: (items) => {
          const row = items[0].dataIndex;
          return '选项位置 ' + (row + 1) + '<br>'
            + series.map((s) => names[s.key] + '：' + (100 * s.data[row]).toFixed(1) + '%').join('<br>')
            + '<br><span style="color:' + muted + '">按位置对齐，不是同一道题</span>';
        }
      },
      legend: { data: series.map((s) => names[s.key]), top: 0, textStyle: { color: muted } },
      grid: { left: 52, right: 20, top: 32, bottom: 24 },
      xAxis: { type: 'category', data: labels,
               axisLabel: { color: muted }, axisLine: { lineStyle: { color: line } } },
      yAxis: { type: 'value', name: '占比', nameTextStyle: { color: muted },
               axisLabel: { formatter: '{value}%', color: muted },
               splitLine: { lineStyle: { color: line } } },
      series: series.map((s) => ({
        name: names[s.key], type: 'bar', barMaxWidth: 20, itemStyle: { color: colours[s.key] },
        data: s.data.map((v) => Number((100 * v).toFixed(1)))
      }))
    }, true);
    chart.resize();
    return chart;
  };

  const openQuestion = (details) => {
    if (details.dataset.drawn !== '1') {
      const host = details.querySelector('.qchart');
      if (host) drawQuestion(host);
      details.dataset.drawn = '1';
    }
    const host = details.querySelector('.qchart');
    const chart = host && echarts.getInstanceByDom(host);
    if (chart) chart.resize();
  };

  document.addEventListener('toggle', (event) => {
    const target = event.target;
    if (!(target instanceof HTMLDetailsElement)) return;
    if (target.classList.contains('q-drawer') && target.open) openQuestion(target);
  }, true);

  document.querySelectorAll('.study-drawer').forEach((study) => {
    study.addEventListener('toggle', () => {
      if (!study.open) return;
      study.querySelectorAll('.pooled').forEach((host) => drawPooled(host));
      study.querySelectorAll('.q-drawer[open]').forEach(openQuestion);
    });
  });

  document.querySelectorAll('.tools button').forEach((button) => {
    button.addEventListener('click', () => {
      const expand = button.dataset.act === 'expand';
      document.querySelectorAll('.study-drawer').forEach((study) => { study.open = true; });
      document.querySelectorAll('.q-drawer').forEach((question) => {
        question.open = expand;
        if (expand) openQuestion(question);
      });
    });
  });

  // Arriving on a study anchor should also open that study.
  if (location.hash.indexOf('#s-') === 0) {
    const study = document.querySelector(location.hash + ' .study-drawer');
    if (study) study.open = true;
  }

  const resize = () => {
    document.querySelectorAll('.qchart, .pooled').forEach((host) => {
      const chart = echarts.getInstanceByDom(host);
      if (chart) chart.resize();
    });
  };
  window.addEventListener('resize', resize);
  window.addEventListener('beforeprint', resize);
})();
