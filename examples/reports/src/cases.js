(() => {
  const $ = (id) => document.getElementById(id);
  const cases = JSON.parse($('case-data').textContent);
  const byId = new Map(cases.map(q => [q.id, q]));
  const viewer = $('case-viewer');
  const container = $('question-chart');
  const frame = container.parentElement;
  const optionsColors = ['#2857a4', '#1b7a6a', '#d39333', '#8661a8', '#88a2bb', '#bf6953'];
  let chart;
  let active;
  const percent = (x) => (100 * x).toFixed(1) + '%';
  const tv = (shares, actual) => 50 * shares.reduce((sum, p, i) => sum + Math.abs(p - actual[i]), 0);
  const plainLabel = (label) => label.replace(/^[ABC](?: ·)? /, '');
  const chartLabel = (label) => plainLabel(label).replace('＋', '\n＋').replace(/^(合用|统计) /, '$1\n');
  let mode = 'distribution';

  function element(tag, text, className) {
    const node = document.createElement(tag);
    node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function table(headers, rows) {
    const wrap = document.createElement('div');
    wrap.className = 'table-wrap';
    wrap.tabIndex = 0;
    wrap.setAttribute('role', 'region');
    wrap.setAttribute('aria-label', '数据表，可横向滚动');
    const root = document.createElement('table');
    const head = root.createTHead().insertRow();
    const body = root.createTBody();
    for (const title of headers) {
      const cell = element('th', title);
      cell.scope = 'col';
      head.append(cell);
    }
    for (const row of rows) {
      const tr = body.insertRow();
      for (const value of row) {
        tr.append(typeof value === 'string' ? element('td', value) : value);
      }
    }
    wrap.append(root);
    return wrap;
  }

  function updateChart(q) {
    if (!frame.clientWidth) return;
    const actual = q.arms[0].shares;
    const isShares = mode === 'distribution';
    $('chart-heading').textContent = isShares ? '各方案的答案分布' : '各方案的答案离真人多远？';
    $('chart-unit').textContent = isShares
      ? '每柱合计 100%。同一种颜色代表同一个选项，拿它的占比和真人那一柱比。'
      : '单位为百分点。把一道题的所有选项都算进去，柱越矮越接近真人。';
    $('legend').replaceChildren(...(isShares ? q.option_labels.map((label, i) => {
      const li = element('li', label);
      const swatch = element('i', '', 'legend-swatch');
      swatch.style.background = optionsColors[i];
      swatch.setAttribute('aria-hidden', 'true');
      li.prepend(swatch);
      return li;
    }) : []));
    $('legend').hidden = !isShares;
    const width = Math.max(frame.clientWidth, 30 + 83 * q.arms.length);
    const labelThreshold = 1600 / (container.clientHeight - 80);
    container.style.width = width + 'px';
    $('chart-scroll-note').hidden = width <= frame.clientWidth;
    chart ||= echarts.init(container);
    chart.resize();
    chart.setOption({
      animation: false,
      textStyle: {fontFamily: getComputedStyle(document.body).fontFamily},
      grid: {left: 40, right: 13, top: 22, bottom: 58},
      tooltip: {
        trigger: 'axis', renderMode: 'richText', confine: true,
        axisPointer: {type: 'shadow'},
        formatter: (items) => {
          const arm = q.arms[items[0].dataIndex];
          const name = plainLabel(arm.label);
          if (!isShares) return name + '\n分布误差  ' + tv(arm.shares, actual).toFixed(2) + ' 个百分点';
          return name + '\n' + q.option_labels.map((label, i) => label + '  ' + percent(arm.shares[i])).join('\n');
        }
      },
      xAxis: {
        type: 'category', data: q.arms.map(arm => chartLabel(arm.short)),
        axisTick: {show: false},
        axisLabel: {interval: 0, fontSize: 12, lineHeight: 15, color: '#243953'}
      },
      yAxis: {
        type: 'value', min: 0, max: isShares ? 100 : 10 * Math.ceil(Math.max(...q.arms.map(a => tv(a.shares, actual)), 1) / 10),
        axisLabel: {formatter: isShares ? '{value}%' : '{value}', color: '#4a5e74'},
        splitLine: {lineStyle: {color: '#e4ebf3'}}
      },
      series: isShares ? q.option_labels.map((label, idx) => ({
        name: label, type: 'bar', stack: 'answers', barMaxWidth: 76,
        data: q.arms.map(arm => 100 * arm.shares[idx]),
        itemStyle: {color: optionsColors[idx]},
        label: {show: true, position: 'inside', color: idx === 2 || idx === 4 ? '#14253b' : '#fff',
          fontSize: 12, fontWeight: 700,
          formatter: ({value}) => value >= labelThreshold ? value.toFixed(1) + '%' : ''}
      })) : [{
        name: '分布误差', type: 'bar', barMaxWidth: 70,
        data: q.arms.map((arm, i) => ({value: tv(arm.shares, actual),
          itemStyle: {color: ['#19815f', '#9aaac0'][i] || '#2857a4'}})),
        label: {show: true, position: 'top', color: '#243953', fontWeight: 700,
          formatter: ({value}) => value.toFixed(2)}
      }]
    }, true);
  }

  function render(q) {
    const actual = q.arms[0].shares;
    const original = q.arms[1].shares;
    const base = tv(original, actual);
    const best = q.arms.slice(1).reduce((left, right) => tv(left.shares, actual) <= tv(right.shares, actual) ? left : right);
    const bestError = tv(best.shares, actual);
    const candidate = q.arms.find(arm => arm.key === q.compare);
    const candidateError = tv(candidate.shares, actual);
    const difference = base - candidateError;
    const option = actual.reduce((largest, share, i) =>
      Math.abs(original[i] - share) > Math.abs(original[largest] - actual[largest]) ? i : largest, 0);
    const method = plainLabel(candidate.label);
    $('case-example').textContent = `先看「${q.option_labels[option]}」这个选项。真人占 ${percent(actual[option])}，` +
      `MatrAI X 项目单选估成 ${percent(original[option])}，「${method}」估成 ${percent(candidate.shares[option])}。`;
    const result = Math.abs(difference) < .005 ? '与项目单选接近持平' :
      '比项目单选' + (difference > 0 ? '少 ' : '多 ') + Math.abs(difference).toFixed(2) + ' 个百分点';
    $('case-result').textContent = `把所有选项都算进去，「${method}」的误差是 ${candidateError.toFixed(2)} 个百分点，${result}。` +
      (best === candidate ? '在这道题上，它的误差最低。' :
        `在这道题上，误差最低的是「${plainLabel(best.label)}」（${bestError.toFixed(2)} 个百分点）。`);
    $('fixed').textContent = q.fixed;
    $('changed').textContent = q.study_id === 'nhanes'
      ? '让 AI 交出所有选项的概率。另外先数 20 份真人试答，再试着把试答和 AI 各算一半。等概率参照把 AI 换成每个选项机会相同。'
      : q.changed;
    $('case-note').textContent = q.note || '这是一道题的结果。整项实验的平均值见总报告和原始明细。';
    $('original-question').textContent = q.prompt;
    $('original-options').replaceChildren(...q.original_options.map(label => element('li', label)));
    $('case-source').href = q.source;
    $('products').replaceChildren();
    if (q.products) {
      $('products').append(table(['选项', '豆腐生产地', '大豆产地', '种植方式', '每 400 克价格'],
        q.products.map(p => [p.choice, p.origin, p.soy, p.method, p.price]),
      ));
    } else if (q.alternatives) {
      $('products').append(table(['选项', '商品属性'],
        q.alternatives.map((description, i) => [q.option_labels[i], description]),
      ));
    }
    $('method-table').replaceChildren(table(['方案', '用了什么资料，怎么作答'], q.arms.map(arm => [
      plainLabel(arm.label), arm.key === 'pilot_ai' ? '同一批 20 份真人试答占一半，AI 给出的完整概率占另一半。' : arm.method
    ])));
    $('numeric-table').replaceChildren(table(
      ['回答组', ...q.option_labels, '分布误差（百分点）', '较项目单选'],
      q.arms.map((arm, i) => {
        const error = tv(arm.shares, actual);
        const delta = base - error;
        const gainText = i < 2 ? '—' : Math.abs(delta) < .005 ? '接近持平' :
          (delta < 0 ? '增加 ' : '减少 ') + Math.abs(delta).toFixed(2) + ' 个百分点';
        return [plainLabel(arm.label), ...arm.shares.map(x => element('td', percent(x), 'numeric')),
          element('td', error.toFixed(2), 'numeric'), element('td', gainText, i < 2 ? '' : delta < 0 ? 'up' : 'down')];
      })
    ));
    frame.scrollLeft = 0;
    updateChart(q);
  }

  function activate(drawer) {
    if (!drawer.open || drawer === active) return;
    if (active) active.open = false;
    active = drawer;
    drawer.append(viewer);
    viewer.setAttribute('aria-labelledby', drawer.querySelector('summary').id);
    viewer.hidden = false;
    viewer.querySelectorAll('details').forEach(section => { section.open = false; });
    history.replaceState(null, '', '#' + drawer.id);
    render(byId.get(drawer.dataset.caseId));
  }

  function selectHash() {
    const drawer = $(location.hash.slice(1));
    if (!drawer?.dataset.caseId) return;
    for (let section = drawer; section; section = section.parentElement) {
      if (section.tagName === 'DETAILS') section.open = true;
    }
    activate(drawer);
    requestAnimationFrame(() => drawer.scrollIntoView({block: 'start'}));
  }

  for (const drawer of document.querySelectorAll('[data-case-id]')) {
    drawer.addEventListener('toggle', () => activate(drawer));
  }
  for (const link of document.querySelectorAll('a[href^="question-cases.html#"]')) {
    link.addEventListener('click', () => {
      if (link.hash === location.hash) selectHash();
    });
  }
  for (const button of document.querySelectorAll('[data-chart-mode]')) {
    button.addEventListener('click', () => {
      mode = button.dataset.chartMode;
      for (const other of document.querySelectorAll('[data-chart-mode]')) {
        other.setAttribute('aria-pressed', String(other === button));
      }
      frame.scrollLeft = 0;
      updateChart(byId.get(active.dataset.caseId));
    });
  }
  window.addEventListener('hashchange', selectHash);
  selectHash();
  const resize = () => {
    if (active) updateChart(byId.get(active.dataset.caseId));
  };
  if (typeof ResizeObserver === 'function') new ResizeObserver(resize).observe(frame);
  else window.addEventListener('resize', resize);
})();
