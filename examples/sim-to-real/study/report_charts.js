(() => {
  "use strict";
  const stages = JSON.parse(document.querySelector("#report-data").textContent);
  const fmt = (x, digits = 2) => x.toFixed(digits);
  const signed = x => Math.abs(x) < .005 ? "0.00" : (x > 0 ? "+" : "−") + fmt(Math.abs(x));
  const pct = x => fmt(x, 1) + "%";
  const el = (tag, content, className) => {
    const node = document.createElement(tag);
    if (content !== undefined) node.textContent = content;
    if (className) node.className = className;
    return node;
  };
  const select = (label, choices) => {
    const control = el("select");
    for (const [value, text] of choices) control.add(new Option(text, value));
    const container = el("label", label + " ");
    container.append(control);
    return [container, control];
  };
  function table(headers, rows) {
    const node = el("table");
    const header = node.createTHead().insertRow();
    for (const title of headers) {
      const cell = el("th", title);
      cell.scope = "col";
      header.append(cell);
    }
    const body = node.createTBody();
    for (const row of rows) {
      const tr = body.insertRow();
      row.forEach((value, i) => {
        const cell = el(i === 0 ? "th" : "td");
        if (cell.tagName === "TH") cell.scope = "row";
        if (value instanceof Node) cell.append(value);
        else cell.textContent = value;
        tr.append(cell);
      });
    }
    const wrapper = el("div", undefined, "scroll");
    wrapper.tabIndex = 0;
    wrapper.setAttribute("aria-label", "数据表，可横向滚动");
    wrapper.append(node);
    return wrapper;
  }
  function bar(label, number, maximum, className) {
    const row = el("div", undefined, "bar-row");
    const track = el("span", undefined, "track");
    const fill = el("b", undefined, className);
    track.setAttribute("aria-hidden", "true");
    fill.style.width = 100 * number / maximum + "%";
    track.append(fill);
    row.append(el("span", label, "series-label"), track, el("strong", fmt(number)));
    return row;
  }
  function averages(scope, labels, concentrationItems, max, metric) {
    const chart = el("div", undefined, "bars");
    chart.append(el("p", "分布误差（百分点） · 柱从 0 开始 · 刻度上限 " + max, "muted"));
    for (const [key, title] of Object.entries(labels)) {
      chart.append(bar(title, scope.scores[key][metric], max, key === "统计基线" || key === "historical-stratum" ? "baseline" : "model"));
    }
    const hasQuestionMean = Object.values(scope.scores).some(row => row.questionMean !== undefined);
    const accuracy = Object.values(scope.scores).some(row => row.accuracy !== null && row.accuracy !== undefined);
    const headings = ["设置", hasQuestionMean ? "三份问卷等权误差" : "分布误差"];
    if (hasQuestionMean) headings.push("18 道题等权误差");
    if (accuracy) headings.push("与真人答案相同");
    if (concentrationItems) headings.push("单一选项 ≥95% / ≥99% / 100% 的题数");
    const concentrations = series => [95, 99, 100].map(threshold =>
      series.filter(dist => Math.max(...dist) >= threshold - 1e-8).length).join(" / ");
    const rows = Object.entries(labels).map(([key, title]) => {
      const row = scope.scores[key];
      const values = [title, fmt(row.error)];
      if (hasQuestionMean) values.push(fmt(row.questionMean));
      if (accuracy) values.push(pct(row.accuracy));
      if (concentrationItems) values.push(concentrations(concentrationItems.map(q => q.settings[key].pct)));
      return values;
    });
    if (concentrationItems) {
      const actual = ["真人", "—"];
      if (accuracy) actual.push("—");
      actual.push(concentrations(concentrationItems.map(q => q.human)));
      rows.unshift(actual);
    }
    chart.append(table(headings, rows));
    return chart;
  }
  function contrasts(scope, labels) {
    const panel = el("div");
    const accuracy = scope.pairs.some(p => p.accuracy_gain_pp !== undefined);
    const values = scope.pairs.flatMap(p => [p.gain_pp, ...p.ci95]);
    const range = Math.ceil(Math.max(1, ...values.map(Math.abs)) / 5) * 5;
    const x = value => 50 + 50 * value / range;
    const rows = scope.pairs.map(p => {
      const [lo, hi] = p.ci95;
      const plot = el("div", undefined, "interval");
      const whisker = el("span", undefined, hi < 0 ? "whisker loss" : lo > 0 ? "whisker gain" : "whisker");
      const dot = el("b", undefined, "point");
      plot.setAttribute("aria-hidden", "true");
      whisker.style.left = x(lo) + "%";
      whisker.style.width = x(hi) - x(lo) + "%";
      dot.style.left = x(p.gain_pp) + "%";
      plot.append(whisker, dot);
      const row = [labels[p.reference] + " → " + labels[p.candidate], plot,
        signed(p.gain_pp), "[" + signed(lo) + ", " + signed(hi) + "]",
        lo > 0 ? "区间在零以上" : hi < 0 ? "区间在零以下" : "区间包含零"];
      if (accuracy) row.push(signed(p.accuracy_gain_pp) + " [" + p.accuracy_ci95.map(signed).join(", ") + "]");
      return row;
    });
    panel.append(el("p", "原设置误差减去新设置误差。正值表示更接近真人。图中点为估计值，线段为 95% 区间，虚线为 0。区间跨过 0 时，方向不明确。", "muted"));
    const headers = ["从原设置到新设置", "−" + range + " 至 +" + range + " 点", "改善", "95% 区间", "如何读"];
    if (accuracy) headers.push("个人正确率变化及 95% 区间");
    panel.append(table(headers, rows));
    return panel;
  }
  function matrix(items, labels, target) {
    const keys = Object.keys(labels);
    const makeCell = value => {
      const node = el("span", fmt(value), "heat");
      node.style.background = "rgba(164,64,39," + Math.min(.27, value / 180) + ")";
      return node;
    };
    const rows = items.map((q, index) => {
      const button = el("button", q.title, "text-button");
      button.type = "button";
      button.addEventListener("click", () => target(index));
      return [button, ...keys.map(key => makeCell(q.settings[key].error))];
    });
    return table(["题目或选择卡", ...Object.values(labels)], rows);
  }
  function distribution(q, labels) {
    const panel = el("div");
    panel.append(el("h5", q.title));
    if (q.description) panel.append(el("p", q.description));
    if (q.count) panel.append(el("p", q.count, "muted"));
    const legend = el("ul", undefined, "legend");
    q.options.forEach((name, index) => {
      const li = el("li", name);
      li.prepend(el("i", undefined, "option-" + index));
      legend.append(li);
    });
    panel.append(legend);
    const rows = [[null, "真人", q.human], ...Object.entries(labels).map(([key, name]) => [key, name, q.settings[key].pct])];
    for (const [, label, dist] of rows) {
      const row = el("div", undefined, "bar-row distribution");
      const track = el("div", undefined, "stack");
      track.setAttribute("role", "img");
      track.setAttribute("aria-label", label + "，" + q.options.map((n, i) => n + " " + pct(dist[i])).join("，"));
      dist.forEach((value, i) => {
        const part = el("span", value >= 12 ? pct(value) : "", "option-" + i);
        part.style.width = Math.max(0, Math.min(100, value)) + "%";
        part.title = q.options[i] + " " + pct(value);
        part.setAttribute("aria-hidden", "true");
        track.append(part);
      });
      row.append(el("strong", label, "series-label"), track);
      panel.append(row);
    }
    const hasAccuracy = rows.slice(1).some(([key]) => q.settings[key].accuracy != null);
    const headers = ["设置", ...q.options, "误差（点）"];
    if (hasAccuracy) headers.push("与真人答案相同");
    panel.append(el("p", "括号内是模型或统计对照与真人的比例差，单位为百分点。正值表示高估。", "muted"));
    panel.append(table(headers, rows.map(([key, name, values]) => {
      const result = [name, ...values.map((v, i) => pct(v) + (key === null ? "" : " (" + signed(v - q.human[i]) + ")")),
        key === null ? "—" : fmt(q.settings[key].error)];
      if (hasAccuracy) result.push(key === null ? "—" : pct(q.settings[key].accuracy));
      return result;
    })));
    if (rows.slice(1).some(([key]) => q.settings[key].recall?.some(value => value != null))) {
      const details = el("details");
      details.append(el("summary", "查看各选项识别率"),
        el("p", "在真人实际选择这一选项的人里，这个设置有多少答成同一选项。没有真人选该项时以「—」表示。"),
        table(["设置", ...q.options], rows.slice(1).map(([key, name]) =>
          [name, ...q.settings[key].recall.map(value => value == null ? "—" : pct(value))])));
      panel.append(details);
    }
    if (q.original) {
      const details = el("details");
      details.append(el("summary", "查看英文原题"), el("p", q.original, "original"));
      panel.append(details);
    }
    return panel;
  }

  const shopping = stages[3];
  const shoppingOverview = document.querySelector("#shopping-overview");
  const featured = [
    ["P0+B1", "扮演受访者＋年龄学历", "old-setting"],
    ["P1+B3", "预测受访者＋贴题背景", "model"],
    ["统计基线", "真人统计对照", "baseline"],
  ];
  const shoppingScale = Math.ceil(Math.max(...Object.values(shopping.scopes)
    .flatMap(scope => featured.map(([key]) => scope.scores[key].error))) / 10) * 10;
  shoppingOverview.append(el("h4", "三项电商任务并排看"),
    el("p", "各任务内比较分布误差，柱从 0 开始，刻度上限 " + shoppingScale + " 个百分点。三项任务各自评分。", "muted"));
  for (const [survey, name] of Object.entries(shopping.names)) {
    shoppingOverview.append(el("h5", name));
    for (const [key, label, color] of featured) {
      shoppingOverview.append(bar(label, shopping.scopes[survey].scores[key].error, shoppingScale, color));
    }
  }

  document.querySelectorAll(".experiment-charts").forEach((root, index) => {
    const stage = stages[index];
    const labels = stage.labels;
    const choices = Object.entries(stage.names);
    const scopes = stage.overall ? [["overall", "三份问卷等权（主口径）"], ["questions", "18 道题等权（补充口径）"], ...choices] : choices;
    const [scopeLabel, scopeSelect] = select("平均分范围", scopes);
    const [surveyLabel, surveySelect] = select("查看哪份问卷或实验", choices);
    const [questionLabel, questionSelect] = select("查看哪一道题或选择卡", []);
    const averagePanel = el("div");
    const comparisonPanel = el("details");
    const matrixPanel = el("div");
    const detailPanel = el("div");
    const headings = ["各设置的平均误差", "逐题误差总表", "逐题完整选项分布"];
    const scopeMax = Math.ceil(Math.max(...Object.values(stage.scopes).flatMap(s => Object.values(s.scores).map(r => r.error))) / 10) * 10;
    function updateAverage() {
      const key = scopeSelect.value;
      const all = key === "overall" || key === "questions";
      const scope = all ? stage.overall : stage.scopes[key];
      const items = all ? Object.values(stage.scopes).flatMap(s => s.items) : scope.items;
      averagePanel.replaceChildren(averages(scope, labels, index === 3 && key === "origin" ? null : items,
        scopeMax, key === "questions" ? "questionMean" : "error"));
      if (scope.matched) {
        averagePanel.prepend(el("p", "各设置共同完成 " + scope.matched + " 人。统计对照由另 " + scope.training.toLocaleString("en-US") + " 人的回答估计。", "muted"));
      }
      if (scope.optOut && "human" in scope.optOut) {
        averagePanel.append(el("p", "全部选择卡的拒买比例（按实际作答加权）", "muted"),
          table(["设置", "拒买比例", "真实拒买的识别率"], [
            ["真人", pct(scope.optOut.human), "—"],
            ...Object.entries(labels).map(([k, name]) => [name, pct(scope.optOut[k]), pct(scope.rejectionRecall[k])]),
          ]));
      }
      comparisonPanel.hidden = key === "questions";
      comparisonPanel.replaceChildren(el("summary", "展开查看配对差异与 95% 区间（" + scope.pairs.length + " 项）"), contrasts(scope, labels));
      if (key === "questions") averagePanel.prepend(el("p", "这组柱按 18 道题等权绘制。配对区间见主口径或单份问卷。", "muted"));
    }
    function updateQuestion() {
      const q = stage.scopes[surveySelect.value].items[Number(questionSelect.value)];
      detailPanel.replaceChildren(distribution(q, labels));
    }
    function updateSurvey() {
      const questions = stage.scopes[surveySelect.value].items;
      questionSelect.replaceChildren(...questions.map((q, i) => new Option(q.title, i)));
      matrixPanel.replaceChildren(matrix(questions, labels, index => {
        questionSelect.value = String(index);
        updateQuestion();
        questionSelect.focus();
        questionLabel.scrollIntoView({block: "center"});
      }));
      updateQuestion();
    }
    scopeSelect.addEventListener("change", updateAverage);
    surveySelect.addEventListener("change", updateSurvey);
    questionSelect.addEventListener("change", updateQuestion);
    root.append(el("h4", headings[0]), scopeLabel, averagePanel, comparisonPanel,
      el("h4", headings[1]), surveyLabel,
      el("p", "单位为百分点，色块越深代表误差越大。点击题目即可查看该题各选项。", "muted"),
      matrixPanel, el("h4", headings[2]), questionLabel, detailPanel);
    const source = el("a", "核对本轮原始汇总结果");
    source.href = stage.source;
    const link = el("p");
    link.append(source);
    root.append(link);
    if (index === 3) surveySelect.value = "packaging";
    updateAverage();
    updateSurvey();
  });
})();
