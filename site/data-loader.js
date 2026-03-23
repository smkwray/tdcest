export const TREASURY_SOURCES = [
  {
    key: "dts_operating_cash_balance",
    endpoint: "/v1/accounting/dts/operating_cash_balance",
    description: "Daily Treasury Statement operating cash balance",
  },
  {
    key: "mts_receipts",
    endpoint: "/v1/accounting/mts/mts_table_4",
    description: "Monthly Treasury Statement receipts table",
  },
  {
    key: "mspd_marketable",
    endpoint: "/v1/debt/mspd/mspd_table_3_market",
    description: "Monthly Statement of the Public Debt marketable detail",
  },
  {
    key: "mspd_detail",
    endpoint: "/v1/debt/mspd/mspd_table_3",
    description: "Monthly Statement of the Public Debt full detail",
  },
  {
    key: "slgs_securities",
    endpoint: "/v1/accounting/od/slgs_securities",
    description: "State and Local Government Series securities",
  },
];

export const METHOD_COLORS = {
  tdc_base_bank_only_ru_flow: "#0f766e",
  tdc_base_broad_depository_np_cu_ru_flow: "#c26d22",
  tdc_broad_depository_np_corp_cu_ru_flow: "#5e60ce",
  tdc_credit_union_aggregate_sensitivity: "#8c6b3b",
  tdc_domestic_bank_only_ru_flow: "#3b4d7a",
  tdc_no_remit_bank_only: "#6b7280",
  tdc_level_bank_only_sensitivity: "#7c3aed",
  tdc_level_broad_depository_np_cu_sensitivity: "#b45309",
  tdc_decomposition_proxy_bank_centric: "#9ca3af",
  tdc_base_bank_only_ru_flow_4q: "#0ea5e9",
  tdc_base_bank_only_ru_flow_cum: "#111827",
};

export function formatValue(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 1,
    minimumFractionDigits: Math.abs(value) >= 100 ? 0 : 1,
  }).format(value);
}

export function formatShortUsdFromMillions(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  const abs = Math.abs(value);
  if (abs >= 1_000_000) {
    return `$${new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value / 1_000_000)}T`;
  }
  if (abs >= 1_000) {
    return `$${new Intl.NumberFormat("en-US", { maximumFractionDigits: abs >= 100_000 ? 0 : 1 }).format(value / 1_000)}B`;
  }
  return `$${formatValue(value)}M`;
}

export function formatMillionsUsdDetail(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  const raw = `${formatValue(value)} million U.S. dollars`;
  const short = formatShortUsdFromMillions(value);
  if (short.endsWith("M")) {
    return raw;
  }
  return `${raw} (${short})`;
}

export function formatDate(date) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    year: "numeric",
  }).format(new Date(`${date}T00:00:00`));
}

export function formatQuarter(date) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  }).format(new Date(`${date}T00:00:00`));
}

export async function loadJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Failed to load ${path}: ${response.status}`);
  }
  return response.json();
}

export function groupSeriesRows(rows) {
  const bySeries = new Map();
  for (const row of rows) {
    for (const [series, rawValue] of Object.entries(row)) {
      if (series === "date") {
        continue;
      }
      if (!bySeries.has(series)) {
        bySeries.set(series, []);
      }
      const value =
        rawValue === null || rawValue === undefined || rawValue === ""
          ? null
          : Number(rawValue);
      bySeries.get(series).push({
        date: row.date,
        value,
      });
    }
  }
  return Object.fromEntries(
    [...bySeries.entries()].map(([series, points]) => [
      series,
      points
        .filter((point) => point.value !== null && !Number.isNaN(point.value))
        .sort((a, b) => a.date.localeCompare(b.date)),
    ]),
  );
}

export function inflateFrameRows(dates, frame) {
  const columns = frame?.columns || [];
  return dates.map((date, index) => {
    const row = { date };
    for (const column of columns) {
      row[column] = frame[column]?.[index] ?? null;
    }
    return row;
  });
}

export function loadLatestRow(rows) {
  return rows.reduce((latest, row) => {
    if (!latest || row.date > latest.date) {
      return row;
    }
    return latest;
  }, null);
}

export function visibleWindow(rows, mode) {
  if (mode === "5y") {
    return rows.slice(-20);
  }
  if (mode === "10y") {
    return rows.slice(-40);
  }
  return rows;
}

export function computeExtent(seriesMap, visibleSeries, rows, windowMode) {
  const windowRows = visibleWindow(rows, windowMode);
  const lookup = new Set(windowRows.map((row) => row.date));
  const values = [];
  for (const series of visibleSeries) {
    const seriesRows = seriesMap[series] || [];
    for (const point of seriesRows) {
      if (lookup.has(point.date)) {
        values.push(point.value);
      }
    }
  }
  const min = values.length ? Math.min(...values) : -1;
  const max = values.length ? Math.max(...values) : 1;
  const pad = Math.max((max - min) * 0.12, 1);
  return {
    min: min - pad,
    max: max + pad,
  };
}

export function buildSvgLines({
  width,
  height,
  seriesMap,
  visibleSeries,
  rows,
  windowMode,
  primarySeries = null,
}) {
  const padding = { top: 18, right: 20, bottom: 34, left: 58 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const windowRows = visibleWindow(rows, windowMode);
  const lookup = new Set(windowRows.map((row) => row.date));
  const extent = computeExtent(seriesMap, visibleSeries, rows, windowMode);
  const startIndex = rows.findIndex((row) => row.date === windowRows[0]?.date);
  const endIndex = rows.findIndex((row) => row.date === windowRows[windowRows.length - 1]?.date);
  const sample = rows.slice(startIndex, endIndex + 1);

  const xForIndex = (index) => padding.left + (plotWidth * index) / Math.max(sample.length - 1, 1);
  const yForValue = (value) => padding.top + ((extent.max - value) * plotHeight) / (extent.max - extent.min);

  const yZero = yForValue(0);
  const grid = [];
  const gridCount = 5;
  for (let i = 0; i <= gridCount; i += 1) {
    const value = extent.min + ((extent.max - extent.min) * i) / gridCount;
    const y = yForValue(value);
    grid.push(`<line x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" />`);
    grid.push(
      `<text x="${padding.left - 10}" y="${y + 4}" text-anchor="end">${formatValue(value)}</text>`,
    );
  }
  grid.push(
    `<line class="zero-line" x1="${padding.left}" y1="${yZero}" x2="${width - padding.right}" y2="${yZero}" />`,
  );

  const seriesSvg = visibleSeries
    .map((series) => {
      const points = sample
        .map((row, index) => {
          const point = (seriesMap[series] || []).find((item) => item.date === row.date);
          if (!point || !lookup.has(row.date)) {
            return null;
          }
          return `${xForIndex(index)},${yForValue(point.value)}`;
        })
        .filter(Boolean);
      if (!points.length) {
        return "";
      }
      const isPrimary = primarySeries === series;
      return `<polyline fill="none" stroke="${METHOD_COLORS[series] || "#64748b"}" stroke-width="${isPrimary ? 3.9 : 2.1}" stroke-opacity="${isPrimary || !primarySeries ? 1 : 0.28}" points="${points.join(" ")}" />`;
    })
    .join("");

  const ticks = sample
    .filter((_, index) => index === 0 || index === sample.length - 1 || index % Math.max(Math.round(sample.length / 5), 1) === 0)
    .map((row, index) => {
      const actualIndex = sample.findIndex((item) => item.date === row.date);
      return `<text x="${xForIndex(actualIndex)}" y="${height - 10}" text-anchor="middle">${row.date.slice(0, 4)}</text>`;
    })
    .join("");

  return `
    ${grid.join("")}
    ${seriesSvg}
    ${ticks}
  `;
}
