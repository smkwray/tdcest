import {
  formatDate,
  formatMillionsUsdDetail,
  formatQuarter,
  formatShortUsdFromMillions,
  groupSeriesRows,
  inflateFrameRows,
  loadJson,
  loadLatestRow,
  TREASURY_SOURCES,
} from "./data-loader.js";

const SERIES_INFO = {
  tdc_bank_only_extended_1990: {
    label: "Bank-only, full history (1990–present)",
    shortLabel: "Bank-only full history",
    color: "#0f766e",
    note: "Full history starting in 1990. Uses holdings-level changes for 1990–2002, then switches to transaction-based data from 2002 onward.",
  },
  tdc_base_bank_only_ru_flow: {
    label: "Bank-only headline (2002–present)",
    shortLabel: "Bank-only headline",
    color: "#146356",
    note: "The preferred estimate, using transaction-based data only. Starts in late 2002 when the source data begin. This is the project's recommended baseline.",
  },
  tdc_broad_depository_extended_1990: {
    label: "Broad depository, full history (1990–present)",
    shortLabel: "Broad full history",
    color: "#c26d22",
    note: "Full history starting in 1990. Includes banks plus natural-person credit unions. Uses holdings-level changes for 1990–2002, then transaction data from 2002 onward.",
  },
  tdc_base_broad_depository_np_cu_ru_flow: {
    label: "Broad depository headline (2002–present)",
    shortLabel: "Broad headline",
    color: "#d0873a",
    note: "Includes banks and natural-person credit unions, using transaction data only. Starts in late 2002.",
  },
  tdc_broad_depository_np_corp_cu_ru_flow: {
    label: "Broad depository plus corporate credit unions",
    shortLabel: "Plus corporate CU",
    color: "#5e60ce",
    note: "Adds corporate credit unions to the broad depository estimate. Shown as a sensitivity check.",
  },
  tdc_credit_union_aggregate_sensitivity: {
    label: "All credit unions (aggregate sensitivity)",
    shortLabel: "All CU sensitivity",
    color: "#8c6b3b",
    note: "Includes all credit-union categories plus the NCUA capitalization deposit. Matches the broadest published credit-union concept.",
  },
  tdc_domestic_bank_only_ru_flow: {
    label: "Domestic banks only (excludes foreign holdings)",
    shortLabel: "Domestic only",
    color: "#3b4d7a",
    note: "Removes the rest-of-world Treasury term from the bank-only estimate. Shows only domestic bank-sector contributions.",
  },
  tdc_no_remit_bank_only: {
    label: "Bank-only without Fed remittances",
    shortLabel: "No Fed remittances",
    color: "#6b7280",
    note: "Removes the Federal Reserve remittance term from the bank-only estimate. Shows the effect of Treasury securities alone.",
  },
};

const PICKER_ORDER = [
  "tdc_bank_only_extended_1990",
  "tdc_base_bank_only_ru_flow",
  "tdc_broad_depository_extended_1990",
  "tdc_base_broad_depository_np_cu_ru_flow",
  "tdc_broad_depository_np_corp_cu_ru_flow",
  "tdc_credit_union_aggregate_sensitivity",
  "tdc_domestic_bank_only_ru_flow",
  "tdc_no_remit_bank_only",
];

const DEFAULT_VISIBLE_SERIES = [
  "tdc_bank_only_extended_1990",
  "tdc_base_bank_only_ru_flow",
  "tdc_broad_depository_extended_1990",
  "tdc_base_broad_depository_np_cu_ru_flow",
];

const CANVAS_BG_PLUGIN = {
  id: "canvasBackground",
  beforeDraw(chart, _args, options) {
    const { ctx, chartArea } = chart;
    if (!chartArea) {
      return;
    }
    ctx.save();
    ctx.fillStyle = options?.color || "#ffffff";
    ctx.fillRect(chartArea.left, chartArea.top, chartArea.right - chartArea.left, chartArea.bottom - chartArea.top);
    ctx.restore();
  },
};

const RANGE_SELECTION_PLUGIN = {
  id: "rangeSelection",
  beforeDatasetsDraw(chart, _args, options) {
    const { chartArea, ctx, scales } = chart;
    if (!chartArea || !options?.start || !options?.end || !scales?.x) {
      return;
    }
    const xScale = scales.x;
    const left = xScale.getPixelForValue(options.start);
    const right = xScale.getPixelForValue(options.end);
    if (!Number.isFinite(left) || !Number.isFinite(right)) {
      return;
    }
    ctx.save();
    ctx.fillStyle = options.outsideFill || "rgba(0,0,0,0.08)";
    ctx.fillRect(chartArea.left, chartArea.top, Math.max(left - chartArea.left, 0), chartArea.bottom - chartArea.top);
    ctx.fillRect(right, chartArea.top, Math.max(chartArea.right - right, 0), chartArea.bottom - chartArea.top);
    ctx.fillStyle = options.selectionFill || "rgba(15, 118, 110, 0.12)";
    ctx.fillRect(left, chartArea.top, Math.max(right - left, 2), chartArea.bottom - chartArea.top);
    ctx.strokeStyle = options.edgeColor || "rgba(15, 118, 110, 0.35)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(left, chartArea.top);
    ctx.lineTo(left, chartArea.bottom);
    ctx.moveTo(right, chartArea.top);
    ctx.lineTo(right, chartArea.bottom);
    ctx.stroke();
    ctx.restore();
  },
};

Chart.register(CANVAS_BG_PLUGIN);

const state = {
  adjustInflation: false,
  focusSeries: DEFAULT_VISIBLE_SERIES[0],
  hoveredSeries: null,
  rangeEnd: null,
  rangeStart: null,
  visibleSeries: new Set(DEFAULT_VISIBLE_SERIES),
};

const els = {
  bundleStatus: document.getElementById("bundle-status"),
  componentsChart: document.getElementById("components-chart"),
  componentsNote: document.getElementById("components-note"),
  downloadEstimates: document.getElementById("download-estimates"),
  fredTable: document.getElementById("fred-table"),
  heroMetrics: document.getElementById("hero-metrics"),
  inflationToggle: document.getElementById("inflation-toggle"),
  ladderChart: document.getElementById("ladder-chart"),
  latestObservation: document.getElementById("latest-observation"),
  lineChart: document.getElementById("line-chart"),
  lineChartNote: document.getElementById("line-chart-note"),
  rangeEnd: document.getElementById("range-end"),
  rangeNote: document.getElementById("range-note"),
  rangeReset: document.getElementById("range-reset"),
  rangeStart: document.getElementById("range-start"),
  seriesCoverage: document.getElementById("series-coverage"),
  seriesDetailMode: document.getElementById("series-detail-mode"),
  seriesDetailTitle: document.getElementById("series-detail-title"),
  seriesFormula: document.getElementById("series-formula"),
  seriesNote: document.getElementById("series-note"),
  seriesToggle: document.getElementById("series-toggle"),
  treasuryTable: document.getElementById("treasury-table"),
  unitsNote: document.getElementById("units-note"),
};

let bundle = null;
let componentsChart = null;
let ladderChart = null;
let lineChart = null;

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function currentTheme() {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

function palette() {
  return {
    canvas: cssVar("--chart-bg"),
    grid: cssVar("--line"),
    muted: cssVar("--muted"),
    selectionEdge: cssVar("--accent"),
    selectionFill: cssVar("--accent-soft"),
    text: cssVar("--text"),
    tooltipBg: currentTheme() === "dark" ? "#0b1220" : "#fffdf8",
    tooltipBorder: cssVar("--line"),
    tooltipText: cssVar("--text"),
  };
}

function infoFor(seriesKey) {
  return SERIES_INFO[seriesKey] || {
    label: seriesKey,
    shortLabel: seriesKey,
    color: "#64748b",
    note: "No description available.",
  };
}

function availableSeriesKeys() {
  return PICKER_ORDER.filter((key) => bundle.summary.available_methods.includes(key));
}

function ensureVisibleState() {
  const available = availableSeriesKeys();
  state.visibleSeries = new Set([...state.visibleSeries].filter((key) => available.includes(key)));
  if (!state.visibleSeries.size && available.length) {
    state.visibleSeries = new Set(DEFAULT_VISIBLE_SERIES.filter((key) => available.includes(key)));
  }
  if (!state.visibleSeries.size && available.length) {
    state.visibleSeries.add(available[0]);
  }
  if (!state.visibleSeries.has(state.focusSeries) && state.visibleSeries.size) {
    state.focusSeries = [...state.visibleSeries][0];
  }
}

function focusedSeriesKey() {
  ensureVisibleState();
  return state.focusSeries;
}

function detailSeriesKey() {
  return state.hoveredSeries || focusedSeriesKey();
}

function methodFormula(seriesKey) {
  return bundle?.metadata?.method_meta?.method_formulas?.[seriesKey]
    || "Equation detail unavailable in this bundle.";
}

function createMetric(label, value, detail) {
  const node = document.createElement("div");
  node.className = "metric";
  node.innerHTML = `
    <span class="eyebrow">${label}</span>
    <strong>${value}</strong>
    <div class="small-copy">${detail}</div>
  `;
  return node;
}

function hasInflationSupport() {
  return Boolean(bundle?.latestDeflator) && bundle?.deflatorByDate?.size > 0;
}

function activeUnitsSummary() {
  if (state.adjustInflation && hasInflationSupport()) {
    return "Values are shown in latest-quarter dollars using the GDP implicit price deflator. The plotted values remain in millions of U.S. dollars.";
  }
  return "Values are nominal millions of U.S. dollars. Example: 60,592 means about $60.6 billion.";
}

function activeObservationLabel(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  return formatShortUsdFromMillions(value);
}

function activeObservationDetail(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  if (state.adjustInflation && hasInflationSupport()) {
    return `${formatMillionsUsdDetail(value)} in latest-quarter dollars`;
  }
  return formatMillionsUsdDetail(value);
}

function adjustedValue(value, date) {
  if (!state.adjustInflation || !hasInflationSupport()) {
    return value;
  }
  const deflator = bundle.deflatorByDate.get(date);
  if (deflator === null || deflator === undefined || Number.isNaN(deflator) || deflator <= 0) {
    return null;
  }
  return value * (bundle.latestDeflator / deflator);
}

function fullSeriesPoints(seriesKey) {
  return (bundle.seriesMap[seriesKey] || [])
    .map((point) => ({
      date: point.date,
      value: adjustedValue(point.value, point.date),
    }))
    .filter((point) => point.value !== null && !Number.isNaN(point.value));
}

function coverageBounds() {
  ensureVisibleState();
  const visibleKeys = availableSeriesKeys().filter((key) => state.visibleSeries.has(key));
  const pointSets = visibleKeys.map((key) => fullSeriesPoints(key)).filter((points) => points.length);
  if (!pointSets.length) {
    return { dates: [], end: null, start: null };
  }
  const start = pointSets.map((points) => points[0].date).sort((a, b) => a.localeCompare(b))[0];
  const end = pointSets.map((points) => points[points.length - 1].date).sort((a, b) => a.localeCompare(b)).at(-1);
  const dates = bundle.dates.filter((date) => date >= start && date <= end);
  return { dates, end, start };
}

function clampRangeState() {
  const { start, end } = coverageBounds();
  if (!start || !end) {
    state.rangeStart = null;
    state.rangeEnd = null;
    return;
  }
  if (!state.rangeStart || state.rangeStart < start || state.rangeStart > end) {
    state.rangeStart = start;
  }
  if (!state.rangeEnd || state.rangeEnd > end || state.rangeEnd < start) {
    state.rangeEnd = end;
  }
  if (state.rangeStart > state.rangeEnd) {
    state.rangeStart = start;
    state.rangeEnd = end;
  }
}

function visibleDates() {
  const { dates } = coverageBounds();
  clampRangeState();
  return dates.filter((date) => date >= state.rangeStart && date <= state.rangeEnd);
}

function seriesPoints(seriesKey) {
  const allowedDates = new Set(visibleDates());
  return fullSeriesPoints(seriesKey).filter((point) => allowedDates.has(point.date));
}

function fullSeriesCoverage(seriesKey) {
  const points = bundle.seriesMap[seriesKey] || [];
  if (!points.length) {
    return "No observations available.";
  }
  return `${formatQuarter(points[0].date)} to ${formatQuarter(points[points.length - 1].date)}`;
}

function renderSeriesDetail() {
  const seriesKey = detailSeriesKey();
  const info = infoFor(seriesKey);
  const isHover = Boolean(state.hoveredSeries);
  els.seriesDetailMode.textContent = isHover ? "Hovered series" : "Selected series";
  els.seriesDetailTitle.textContent = info.label;
  els.seriesNote.textContent = info.note;
  els.seriesFormula.textContent = `Equation: ${methodFormula(seriesKey)}`;
  els.seriesCoverage.textContent = `Coverage: ${fullSeriesCoverage(seriesKey)}.`;
}

function renderHero(summary) {
  const selectedKey = focusedSeriesKey();
  const selectedInfo = infoFor(selectedKey);
  const focusedAllPoints = fullSeriesPoints(selectedKey);
  const selectedLatest = focusedAllPoints.length ? focusedAllPoints[focusedAllPoints.length - 1].value : null;
  const bankLatest = adjustedValue(summary.latest_methods?.tdc_base_bank_only_ru_flow, summary.latest_period);
  const visibleCount = state.visibleSeries.size;

  const focusedMatchesBaseline = selectedLatest !== null && bankLatest !== null && Math.abs(selectedLatest - bankLatest) < 1;
  const baselineDetail = focusedMatchesBaseline
    ? `Recommended baseline (bank-only) as of ${formatDate(summary.latest_period)}: ${activeObservationDetail(bankLatest)}. Your selected series matches this value for the latest quarter.`
    : `Recommended baseline (bank-only) as of ${formatDate(summary.latest_period)}: ${activeObservationDetail(bankLatest)}.`;

  els.heroMetrics.replaceChildren(
    createMetric("Selected series", activeObservationLabel(selectedLatest), `${selectedInfo.shortLabel}: ${activeObservationDetail(selectedLatest)}.`),
    createMetric("Preferred estimate", activeObservationLabel(bankLatest), baselineDetail),
    createMetric("Range in view", `${formatDate(state.rangeStart)} to ${formatDate(state.rangeEnd)}`, `${visibleCount} series currently shown.`),
  );

  els.latestObservation.textContent = summary.latest_period
    ? `Latest observation in bundle: ${formatQuarter(summary.latest_period)}`
    : "Latest observation unavailable.";
  els.lineChartNote.textContent = `${activeUnitsSummary()} The chart shows your selected series across the visible date range.`;
}

function renderRangeControls() {
  const { start, end } = coverageBounds();
  if (!start || !end) {
    return;
  }
  els.rangeStart.min = start;
  els.rangeStart.max = end;
  els.rangeEnd.min = start;
  els.rangeEnd.max = end;
  els.rangeStart.value = state.rangeStart;
  els.rangeEnd.value = state.rangeEnd;

  els.rangeStart.oninput = () => {
    state.rangeStart = els.rangeStart.value;
    if (state.rangeStart > state.rangeEnd) {
      state.rangeEnd = state.rangeStart;
    }
    renderAll();
  };

  els.rangeEnd.oninput = () => {
    state.rangeEnd = els.rangeEnd.value;
    if (state.rangeEnd < state.rangeStart) {
      state.rangeStart = state.rangeEnd;
    }
    renderAll();
  };

  els.rangeReset.onclick = () => {
    state.rangeStart = start;
    state.rangeEnd = end;
    renderAll();
  };

  els.rangeNote.textContent = `Coverage for the current visible series runs from ${formatQuarter(start)} to ${formatQuarter(end)}.`;
}

function renderControls() {
  ensureVisibleState();
  clampRangeState();

  els.inflationToggle.checked = state.adjustInflation;
  els.inflationToggle.disabled = !hasInflationSupport();
  els.inflationToggle.onchange = () => {
    state.adjustInflation = els.inflationToggle.checked && hasInflationSupport();
    renderAll();
  };
  els.unitsNote.textContent = hasInflationSupport()
    ? `${activeUnitsSummary()} Inflation toggle uses GDPDEF.`
    : "Values are nominal millions of U.S. dollars. Inflation-adjusted view is unavailable in this bundle.";

  renderRangeControls();

  els.seriesToggle.replaceChildren();
  for (const seriesKey of availableSeriesKeys()) {
    const info = infoFor(seriesKey);
    const isVisible = state.visibleSeries.has(seriesKey);
    const isFocused = focusedSeriesKey() === seriesKey;
    const button = document.createElement("button");
    button.className = `chip ${isVisible ? "active" : "inactive"} ${isFocused ? "focused" : ""}`;
    button.innerHTML = `<span class="chip-swatch" style="background:${info.color}"></span><span class="chip-text">${info.shortLabel}</span>`;
    button.style.borderColor = `${info.color}33`;
    button.title = `${info.label}\n${methodFormula(seriesKey)}`;
    button.setAttribute("aria-pressed", String(isVisible));
    button.onclick = () => {
      if (!isVisible) {
        state.visibleSeries.add(seriesKey);
        state.focusSeries = seriesKey;
      } else if (state.visibleSeries.size > 1) {
        state.visibleSeries.delete(seriesKey);
        if (state.focusSeries === seriesKey) {
          state.focusSeries = [...state.visibleSeries][0];
        }
      }
      renderAll();
    };
    button.onmouseenter = () => {
      state.hoveredSeries = seriesKey;
      renderSeriesDetail();
    };
    button.onmouseleave = () => {
      if (state.hoveredSeries === seriesKey) {
        state.hoveredSeries = null;
        renderSeriesDetail();
      }
    };
    button.onfocus = () => {
      state.hoveredSeries = seriesKey;
      renderSeriesDetail();
    };
    button.onblur = () => {
      if (state.hoveredSeries === seriesKey) {
        state.hoveredSeries = null;
        renderSeriesDetail();
      }
    };
    els.seriesToggle.appendChild(button);
  }

  renderSeriesDetail();
}

function commonChartOptions() {
  const chartPalette = palette();
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      canvasBackground: { color: chartPalette.canvas },
      tooltip: {
        backgroundColor: chartPalette.tooltipBg,
        bodyColor: chartPalette.tooltipText,
        borderColor: chartPalette.tooltipBorder,
        borderWidth: 1,
        titleColor: chartPalette.tooltipText,
      },
    },
  };
}

function buildLineChart() {
  const chartPalette = palette();
  const visibleKeys = availableSeriesKeys().filter((seriesKey) => state.visibleSeries.has(seriesKey));
  const focusKey = focusedSeriesKey();
  const labels = visibleDates();
  const datasets = visibleKeys.map((seriesKey) => {
    const info = infoFor(seriesKey);
    const pointMap = new Map(seriesPoints(seriesKey).map((point) => [point.date, point.value]));
    const isFocused = seriesKey === focusKey;
    return {
      label: state.adjustInflation && hasInflationSupport()
        ? `${info.label} (latest-quarter dollars)`
        : `${info.label} (nominal)`,
      data: labels.map((date) => pointMap.get(date) ?? null),
      borderColor: info.color,
      backgroundColor: `${info.color}${isFocused ? "2b" : "14"}`,
      borderWidth: isFocused ? 3.4 : 2,
      pointRadius: 0,
      pointHoverRadius: isFocused ? 4.5 : 3.5,
      tension: 0.2,
    };
  });

  if (lineChart) {
    lineChart.destroy();
  }

  lineChart = new Chart(els.lineChart, {
    type: "line",
    data: { labels, datasets },
    options: {
      ...commonChartOptions(),
      interaction: { mode: "index", intersect: false },
      plugins: {
        ...commonChartOptions().plugins,
        legend: { display: false },
        tooltip: {
          ...commonChartOptions().plugins.tooltip,
          callbacks: {
            title: (items) => formatQuarter(items[0].label),
            label: (item) => `${item.dataset.label.replace(/ \((nominal|latest-quarter dollars)\)$/, "")}: ${activeObservationDetail(item.raw)}`,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: chartPalette.muted, maxTicksLimit: 8 },
          grid: { display: false },
        },
        y: {
          ticks: { color: chartPalette.muted, callback: (value) => formatShortUsdFromMillions(value) },
          title: {
            display: true,
            text: state.adjustInflation && hasInflationSupport()
              ? "Latest-quarter U.S. dollars (millions)"
              : "Millions of U.S. dollars",
            color: chartPalette.muted,
          },
          grid: { color: chartPalette.grid },
        },
      },
    },
  });
}

function buildComponentsChart() {
  const chartPalette = palette();
  const row = bundle.latestRow;
  const useBroad = focusedSeriesKey().includes("broad");
  const items = [
    { key: "fed_tsy_tx", label: "Fed Treasury transactions", color: "#0f766e" },
    {
      key: useBroad ? "broad_depository_np_cu_tsy_tx" : "bank_depository_tsy_tx",
      label: useBroad ? "Depositories incl. natural-person credit unions" : "Bank-sector Treasury transactions",
      color: "#c26d22",
    },
    { key: "row_tsy_tx", label: "Rest-of-world Treasury transactions", color: "#5e60ce" },
    { key: "minus_treasury_operating_cash_tx", label: "Negative Treasury operating cash term", color: "#1d4ed8" },
    { key: "fed_remit_positive", label: "Positive Fed remittances", color: "#b45309" },
  ];

  if (componentsChart) {
    componentsChart.destroy();
  }

  componentsChart = new Chart(els.componentsChart, {
    type: "bar",
    data: {
      labels: items.map((item) => item.label),
      datasets: [
        {
          data: items.map((item) => Number(row[item.key] ?? 0)),
          backgroundColor: items.map((item) => item.color),
          borderRadius: 8,
        },
      ],
    },
    options: {
      ...commonChartOptions(),
      plugins: {
        ...commonChartOptions().plugins,
        legend: { display: false },
        tooltip: {
          ...commonChartOptions().plugins.tooltip,
          callbacks: {
            label: (item) => activeObservationDetail(item.raw),
          },
        },
      },
      scales: {
        x: { ticks: { color: chartPalette.muted, maxRotation: 0, minRotation: 0 }, grid: { display: false } },
        y: { ticks: { color: chartPalette.muted, callback: (value) => formatShortUsdFromMillions(value) }, grid: { color: chartPalette.grid } },
      },
    },
  });

  els.componentsNote.textContent = `Latest period: ${bundle.summary.latest_period}. Components are shown for the ${useBroad ? "broad-depository" : "bank-only"} assembly in nominal millions of U.S. dollars.`;
}

function buildLadderChart() {
  const chartPalette = palette();
  const rows = [
    { label: "Bank-only headline", key: "tdc_base_bank_only_ru_flow", color: "#0f766e" },
    { label: "Broad-depository headline", key: "tdc_base_broad_depository_np_cu_ru_flow", color: "#c26d22" },
    { label: "Plus corporate credit unions", key: "tdc_broad_depository_np_corp_cu_ru_flow", color: "#5e60ce" },
    { label: "Aggregate credit-union sensitivity", key: "tdc_credit_union_aggregate_sensitivity", color: "#8c6b3b" },
  ];

  if (ladderChart) {
    ladderChart.destroy();
  }

  ladderChart = new Chart(els.ladderChart, {
    type: "bar",
    data: {
      labels: rows.map((row) => row.label),
      datasets: [
        {
          data: rows.map((row) => bundle.summary.latest_methods[row.key]),
          backgroundColor: rows.map((row) => row.color),
          borderRadius: 8,
        },
      ],
    },
    options: {
      ...commonChartOptions(),
      plugins: {
        ...commonChartOptions().plugins,
        legend: { display: false },
        tooltip: {
          ...commonChartOptions().plugins.tooltip,
          callbacks: {
            label: (item) => activeObservationDetail(item.raw),
          },
        },
      },
      scales: {
        x: { ticks: { color: chartPalette.muted, maxRotation: 0, minRotation: 0 }, grid: { display: false } },
        y: { ticks: { color: chartPalette.muted, callback: (value) => formatShortUsdFromMillions(value) }, grid: { color: chartPalette.grid } },
      },
    },
  });
}

function renderTables() {
  const seriesMeta = bundle.metadata.series_meta;
  els.fredTable.innerHTML = `
    <thead>
      <tr><th>Series ID</th><th>Description</th></tr>
    </thead>
    <tbody>
      ${Object.values(seriesMeta)
        .map(
          (meta) => `
            <tr>
              <td><a href="https://fred.stlouisfed.org/series/${meta.series_id}" target="_blank" rel="noreferrer">${meta.series_id}</a></td>
              <td>${meta.description}</td>
            </tr>`,
        )
        .join("")}
    </tbody>
  `;

  els.treasuryTable.innerHTML = `
    <thead>
      <tr><th>Endpoint</th><th>Description</th></tr>
    </thead>
    <tbody>
      ${TREASURY_SOURCES.map(
        (source) => `
          <tr>
            <td><code>${source.endpoint}</code></td>
            <td>${source.description}</td>
          </tr>`,
      ).join("")}
    </tbody>
  `;
}

function renderAll() {
  renderControls();
  buildLineChart();
  buildComponentsChart();
  buildLadderChart();
  renderHero(bundle.summary);
}

function downloadEstimatesCsv() {
  const rows = bundle.seriesRows;
  if (!rows.length) {
    return;
  }
  const headers = Object.keys(rows[0]);
  const csv = [
    headers.join(","),
    ...rows.map((row) =>
      headers
        .map((header) => {
          const value = row[header];
          if (value === null || value === undefined) {
            return "";
          }
          const text = `${value}`;
          return text.includes(",") ? `"${text.replaceAll('"', '""')}"` : text;
        })
        .join(","),
    ),
  ].join("\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "tdc_estimates.csv";
  link.click();
  URL.revokeObjectURL(url);
}

async function loadBundle() {
  try {
    const payload = await loadJson("./data/bundle.json");
    const summary = payload.summary;
    const metadata = payload.metadata;
    const dates = payload.dates || [];
    const seriesRows = inflateFrameRows(dates, payload.estimates).filter((row) => row.date);
    const componentRows = inflateFrameRows(dates, payload.components).filter((row) => row.date);
    const referenceRows = inflateFrameRows(dates, payload.references).filter((row) => row.date);
    const latestRow = loadLatestRow(componentRows);
    const deflatorByDate = new Map(
      referenceRows
        .filter((row) => row.gdp_deflator !== null && row.gdp_deflator !== undefined && !Number.isNaN(Number(row.gdp_deflator)))
        .map((row) => [row.date, Number(row.gdp_deflator)]),
    );

    bundle = {
      componentRows,
      dates,
      deflatorByDate,
      latestDeflator: [...deflatorByDate.values()].at(-1) ?? null,
      latestRow,
      metadata,
      referenceRows,
      seriesMap: groupSeriesRows(seriesRows),
      seriesRows,
      summary,
    };

    if (!bundle.summary.available_methods.includes(state.focusSeries)) {
      state.focusSeries = availableSeriesKeys()[0];
    }

    els.bundleStatus.textContent = `Bundle loaded from ./data/bundle.json through ${summary.latest_period}.`;
    els.downloadEstimates.onclick = (event) => {
      event.preventDefault();
      downloadEstimatesCsv();
    };

    renderTables();
    renderAll();
  } catch (error) {
    els.bundleStatus.textContent = "Bundle not found. Publish the generated bundle into ./data/bundle.json.";
    els.heroMetrics.innerHTML = `
      <div class="empty-state">
        <strong>Static shell ready.</strong>
        <p>The site expects <code>./data/bundle.json</code>. Run the build and restage the site bundle.</p>
      </div>
    `;
    console.error(error);
  }
}

window.addEventListener("tdc-themechange", () => {
  if (bundle) {
    renderAll();
  }
});

loadBundle();
