const METHOD_FAMILIES = {
  bank_only_ladder: [
    "tdc_base_bank_only_ru_flow",
    "tdc_tier1_fed_corrected_bank_only_ru_flow",
    "tdc_tier2_interest_corrected_bank_only_ru_flow",
    "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
  ],
  broad_depository_ladder: [
    "tdc_base_broad_depository_np_cu_ru_flow",
    "tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow",
    "tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow",
    "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow",
  ],
  headline_vs_sensitivity: [
    "tdc_base_bank_only_ru_flow",
    "tdc_base_broad_depository_np_cu_ru_flow",
    "tdc_credit_union_aggregate_sensitivity",
    "tdc_decomposition_proxy_bank_centric",
    "tdc_bank_only_extended_1990",
  ],
};

const METHOD_RANGE_OPTIONS = {
  last_3y: "Last 3 years",
  last_5y: "Last 5 years",
  last_10y: "Last 10 years",
  post_2002: "Post-2002 transaction era",
  full_history: "Full history",
};

const BASE_COMPONENT_KEYS = [
  "fed_tsy_tx",
  "bank_depository_tsy_tx",
  "row_tsy_tx",
  "minus_treasury_operating_cash_tx",
  "fed_remit_positive",
];

const CORRECTION_KEYS = [
  "tier1_fed_coupon_correction",
  "tier2_bank_coupon_correction",
  "tier2_row_coupon_correction",
  "tier3_bank_noninterest_outlay_correction",
  "tier3_row_noninterest_outlay_correction",
  "tier3_bank_nonborrow_receipt_correction",
  "tier3_row_nonborrow_receipt_correction",
  "tier3_mint_cb_cash_factor_correction",
];

const METHOD_LABELS = {
  tdc_base_bank_only_ru_flow: "Uncorrected bank-only baseline",
  tdc_tier1_fed_corrected_bank_only_ru_flow: "Fed-corrected bank-only estimate",
  tdc_tier2_interest_corrected_bank_only_ru_flow: "Interest-corrected bank-only estimate",
  tdc_tier3_fiscal_corrected_bank_only_ru_flow: "Fiscal-corrected bank-only headline",
  tdc_base_broad_depository_np_cu_ru_flow: "Uncorrected broad-depository baseline",
  tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow: "Fed-corrected broad-depository estimate",
  tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow: "Interest-corrected broad-depository estimate",
  tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow: "Fiscal-corrected broad-depository estimate",
  tdc_credit_union_aggregate_sensitivity: "Aggregate credit-union sensitivity",
  tdc_decomposition_proxy_bank_centric: "Bank-centric decomposition proxy",
  tdc_bank_only_extended_1990: "Historical bank-only extension",
  fed_tsy_tx: "Fed Treasury transactions",
  bank_depository_tsy_tx: "Bank Treasury transactions",
  row_tsy_tx: "Foreign Treasury transactions",
  minus_treasury_operating_cash_tx: "Less Treasury operating cash",
  fed_remit_positive: "Positive Fed remittances",
  tier1_fed_coupon_correction: "Fed coupon correction",
  tier2_bank_coupon_correction: "Bank coupon correction",
  tier2_row_coupon_correction: "Foreign coupon correction",
  tier3_bank_noninterest_outlay_correction: "Bank outlay correction",
  tier3_row_noninterest_outlay_correction: "Foreign outlay correction",
  tier3_bank_nonborrow_receipt_correction: "Bank receipt correction",
  tier3_row_nonborrow_receipt_correction: "Foreign receipt correction",
  tier3_mint_cb_cash_factor_correction: "Mint/cash-factor correction",
};

const METHOD_FAMILY_LABELS = {
  bank_only_ladder: "Bank-only correction ladder",
  broad_depository_ladder: "Broader deposit perimeter ladder",
  headline_vs_sensitivity: "Headline and sensitivity views",
};

const METHOD_PALETTE_KEYS = {
  bank_only_ladder: ["--chart-bank-1", "--chart-bank-2", "--chart-bank-3", "--chart-bank-4"],
  broad_depository_ladder: ["--chart-broad-1", "--chart-broad-2", "--chart-broad-3", "--chart-broad-4"],
  headline_vs_sensitivity: ["--chart-mix-1", "--chart-mix-2", "--chart-mix-3", "--chart-mix-4", "--chart-mix-5"],
};

const METHOD_POSTURES = {
  tdc_base_bank_only_ru_flow: "baseline",
  tdc_tier1_fed_corrected_bank_only_ru_flow: "intermediate",
  tdc_tier2_interest_corrected_bank_only_ru_flow: "intermediate",
  tdc_tier3_fiscal_corrected_bank_only_ru_flow: "live",
  tdc_base_broad_depository_np_cu_ru_flow: "baseline",
  tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow: "intermediate",
  tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow: "intermediate",
  tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow: "live",
  tdc_credit_union_aggregate_sensitivity: "diagnostic",
  tdc_decomposition_proxy_bank_centric: "diagnostic",
  tdc_bank_only_extended_1990: "historical",
};

const GOAL_LABELS = {
  bank_transfers_and_outlays: "Bank-side transfers and outlays",
  row_transfers_and_outlays: "Foreign transfers and outlays",
  bank_receipts: "Bank receipts",
  row_receipts: "Foreign receipts",
  fiscal_flow_tdc_equation: "Fiscal-flow TDC equation",
  monetary_disaggregated_tdc_equation: "Monetary-disaggregated TDC equation",
};

const BRANCH_LABELS = {
  bank_table51_historical_window: "Bank historical Table 5.1 window",
  bank_table51_current_window: "Bank current Table 5.1 window",
  row_mrv_cbsp_primary: "Primary MRV fee branch",
  row_secondary_state_visa: "Secondary visa branch",
};

const WORKSTREAM_LABELS = {
  bank_receipt_historical_window: "Historical bank receipt window",
  bank_receipt_current_window: "Current bank receipt bridge",
  row_mrv_primary_pilot: "MRV primary pilot",
  fiscal_reconciliation_shell: "Fiscal reconciliation shell",
  monetary_branch: "Monetary branch",
  tier3_research_surfaces: "Tier 3 research surfaces",
  bank_nontax_regulatory_receipts: "Bank non-tax regulatory receipts",
  row_secondary_and_contaminated_families: "Secondary foreign families",
};

const STATUS_HEADLINES = {
  historical_default_only_current_nondefault: "Historical default only; current quarters remain nondefault",
  stop_at_mrv_nondefault_pilot: "Bounded MRV pilot; not promoted into the live default",
  prefer_depository_target_crosscheck: "Use the depository target as the preferred cross-check",
  diagnostic_shell_live_not_full_receipt_solved: "Diagnostic shell live; receipt side still incomplete",
  diagnostic_system_live_depository_target_preferred: "Diagnostic system live; depository target preferred",
};

const STATUS_SHORT_LABELS = {
  historical_default_only_current_nondefault: "Historical default only",
  stop_at_mrv_nondefault_pilot: "MRV bounded pilot",
  diagnostic_shell_live_not_full_receipt_solved: "Diagnostic shell",
  diagnostic_system_live_depository_target_preferred: "Depository cross-check",
};

const STATUS_PUBLIC_LABELS = {
  historical_default_only_current_nondefault: "Historical default ready; current bank receipts still held out",
  stop_at_mrv_nondefault_pilot: "Bounded MRV pilot; not used in the live default",
  diagnostic_shell_live_not_full_receipt_solved: "Diagnostic shell live; receipt side still incomplete",
  diagnostic_system_live_depository_target_preferred: "Diagnostic system live; depository cross-check preferred",
  live_interest_plus_partial_outlay_corrections: "Transfers and outlays mostly covered",
};

const ROLE_LABELS = {
  informational_identity: "Informational identity",
  headline_estimate: "Live working estimate",
  live_corrected_estimate: "Live corrected estimate",
  historical_default_view: "Historical bounded overlay",
  bounded_nondefault_pilot: "Bounded nondefault pilot",
  diagnostic_crosscheck: "Diagnostic cross-check",
};

const BLOCKER_LABELS = {
  stale_share_rule: "Current public bank-share evidence is stale",
  evidence_boundary: "Public payer evidence is still incomplete",
  receipt_cells_still_partial: "Receipt-side cells remain partial",
  receipt_side_completion: "Receipt-side completion still missing",
  row_receipt_identity: "Foreign payer identity still incomplete",
  stop_at_perimeter_stress_test: "Stop at perimeter stress-test use only",
  none_within_current_policy_window: "No blocker inside the current policy window",
  not_primary_row_candidate: "Not the leading foreign receipt candidate",
  not_treasury_cash_payer_identity: "Not a Treasury cash-payer identity series",
  perimeter_too_broad: "Perimeter is too broad for default use",
  annual_surface_and_budget_treatment_limits: "Annual treatment and budget-surface limits",
  presentation_and_labeling_work: "Presentation and labeling work remains",
};

const BOUNDARY_LABELS = {
  bank_live_default_receipt_cell: "Live bank receipt cell",
  row_live_default_receipt_cell: "Live foreign receipt cell",
  bank_receipt_historical_overlay_candidate: "Historical bank receipt overlay",
  bank_receipt_historical_overlay_lower_bound: "Historical bank lower-bound overlay",
  row_mrv_primary_nondefault_pilot: "Primary MRV pilot",
  row_bea_receipt_benchmark: "Foreign benchmark row",
  bank_receipt_bridge_depository_plus_bhc: "Bank bridge: depository plus BHC",
  bank_receipt_bridge_strict_depository_lower_bound: "Bank bridge: strict lower bound",
  bank_receipt_bridge_broad_finance_upper_benchmark: "Bank bridge: broad finance upper benchmark",
};

const QUALITY_FAMILY_LABELS = {
  treasury_security_net_transactions: "Treasury security transactions",
  treasury_operating_cash_change: "Treasury operating cash change",
  fed_remittances: "Fed remittances",
  coupon_interest_outlays: "Coupon-interest outlays",
  noninterest_outlays: "Non-interest outlays",
  nonborrow_receipts: "Non-borrowing receipts",
  mint_cb_cash_factor: "Mint and central-bank cash factor",
};

const RELIABILITY_LABELS = {
  high: "High",
  medium_high: "Medium-high",
  medium: "Medium",
  medium_low: "Medium-low",
  low_medium: "Low-medium",
  low: "Low",
};

const THEORY_TERM_LISTS = {
  theory_du_facing_identity: [
    { latex: "\\Delta D^{TDC}_{DU}", description: "The Treasury-attributed part of deposit change for domestic nonbank holders." },
    { latex: "G^{ND}_{DU} - R^{T}_{DU}", description: "Net Treasury payments into domestic nonbank deposits: Treasury payments in minus Treasury collections out." },
    { latex: "DS^{T}_{DU}", description: "Treasury debt-service payments that land in domestic nonbank deposit accounts." },
    { latex: "Q^{T}_{DU \\to RU} - Q^{T}_{RU \\to DU}", description: "Net Treasury security sales by domestic nonbanks to reserve-side counterparties." },
    { latex: "DU", description: "Domestic nonbank deposit users: households, firms, and other domestic nonbank holders." },
    { latex: "RU", description: "Reserve-side counterparties such as the Fed, banks, and foreign reserve-side holders." },
  ],
  theory_treasury_cash_constraint: [
    { latex: "\\Delta D^{TDC}_{DU}", description: "The Treasury-attributed part of domestic nonbank deposit change." },
    { latex: "Q^{T}_{DU \\to RU} - Q^{T}_{RU \\to DU}", description: "Treasury security settlement with reserve-side counterparties." },
    { latex: "I^{T} + R^{T}_{RU} + \\Pi^{F}_{T}", description: "Treasury cash income to reserve-side counterparties: interest, reserve-side receipts, and positive Fed remittances." },
    { latex: "G^{ND}_{RU} + DS^{T}_{RU}", description: "Treasury cash outflows paid out through reserve-side sectors." },
    { latex: "\\Delta TOC", description: "The change in Treasury operating cash, broader than a narrow Treasury General Account shorthand." },
  ],
  theory_fed_remittance_deferred_asset: [
    { latex: "\\Pi^{F}_{T,t}", description: "Positive remittance from the Federal Reserve to Treasury in the current period." },
    { latex: "E^{F}_{t}", description: "Current-period Federal Reserve earnings before deferred-asset adjustment." },
    { latex: "DA^{F}_{t-1}", description: "Deferred asset carried from the prior period." },
    { latex: "DA^{F}_{t}", description: "Deferred asset remaining at the end of the current period." },
    { latex: "\\max(0, \\cdot)", description: "Only positive remittances count as Treasury cash inflow; negative Fed earnings do not create Treasury cash outflows." },
  ],
  theory_residual_deposit_decomposition: [
    { latex: "\\Delta D^{TDC}_{DU}", description: "Residual deposit change attributed to Treasury after other drivers are removed." },
    { latex: "\\Delta M - \\Delta C - \\Delta X", description: "Total money or deposit change after subtracting currency and other non-deposit leakage." },
    { latex: "\\Delta L^{B}_{DU} + \\Delta A^{B,NT}_{DU}", description: "Bank-side non-Treasury lending and other non-Treasury asset changes." },
    { latex: "\\Delta A^{CB,NT}_{DU}", description: "Central-bank non-Treasury asset changes that affect deposits." },
    { latex: "\\Delta F^{NT}_{DU}", description: "Other non-Treasury financial flows that move deposits." },
    { latex: "\\varepsilon", description: "Residual error or leftover measurement wedge." },
  ],
};

const METHOD_DESCRIPTIONS = {
  tdc_base_bank_only_ru_flow: "Raw bank-only baseline built from Treasury security transactions, Treasury operating cash, and positive Fed remittances.",
  tdc_tier1_fed_corrected_bank_only_ru_flow: "Step one of the correction ladder, removing the Fed coupon distortion from the raw bank-only baseline.",
  tdc_tier2_interest_corrected_bank_only_ru_flow: "Transfer-side cleanup after removing coupon distortions for the Fed, banks, and foreign holders.",
  tdc_tier3_fiscal_corrected_bank_only_ru_flow: "Current live working estimate after adding the narrow fiscal-flow correction layer.",
  tdc_base_broad_depository_np_cu_ru_flow: "Broader perimeter baseline that adds natural-person credit unions to the bank-only baseline.",
  tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow: "Broader-perimeter version of the Fed-corrected estimate.",
  tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow: "Broader-perimeter version of the interest-corrected ladder.",
  tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow: "Broader-perimeter version of the fiscal-corrected ladder, used for perimeter comparison rather than as the headline.",
  tdc_credit_union_aggregate_sensitivity: "Sensitivity view for credit-union treatment, kept outside the headline ladder.",
  tdc_decomposition_proxy_bank_centric: "Proxy decomposition surface used for context rather than as the main estimator.",
  tdc_bank_only_extended_1990: "Historical extension used to compare the modern transaction-era ladder against a longer bank-only history.",
};

const METHOD_PLAIN_FORMULAS = {
  tdc_base_bank_only_ru_flow:
    "Fed Treasury transactions + bank Treasury transactions + foreign Treasury transactions - Treasury operating cash change + positive Fed remittances.",
  tdc_tier1_fed_corrected_bank_only_ru_flow:
    "Uncorrected bank-only baseline - Fed coupon effect.",
  tdc_tier2_interest_corrected_bank_only_ru_flow:
    "Fed-corrected bank-only estimate - bank coupon effect - foreign coupon effect.",
  tdc_tier3_fiscal_corrected_bank_only_ru_flow:
    "Interest-corrected bank-only estimate + fiscal outlay and receipt adjustments + mint and cash-factor adjustment.",
  tdc_base_broad_depository_np_cu_ru_flow:
    "Uncorrected bank-only baseline + natural-person credit-union Treasury transactions.",
  tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow:
    "Uncorrected broad-depository baseline - Fed coupon effect.",
  tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow:
    "Fed-corrected broad-depository estimate - bank coupon effect - foreign coupon effect.",
  tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow:
    "Interest-corrected broad-depository estimate + fiscal outlay and receipt adjustments + mint and cash-factor adjustment.",
};

const REPO_URL = "https://github.com/smkwray/tdcest";
const LICENSE_NAME = "MIT";
const AUTHOR_NAME = "Shane Wray";

const formatMillions = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
  const billions = Number(value) / 1000;
  const sign = billions < 0 ? "-" : "";
  return `${sign}$${new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(Math.abs(billions))}B`;
};

const formatCompact = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(Number(value));
};

const formatAxisBillions = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
  const billions = Number(value) / 1000;
  return `${billions >= 0 ? "" : "-"}${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(Math.abs(billions))}B`;
};

const asRecords = (payload) => (payload && Array.isArray(payload.rows) ? payload.rows : []);

const getColumnSeries = (frame, key) => {
  if (!frame || !Array.isArray(frame[key])) return [];
  return frame[key];
};

const getLatestResearchRow = (payload, keyName, keyValue) =>
  asRecords(payload).find((row) => row[keyName] === keyValue) || null;

const percentBar = (value, scale) => {
  const pct = scale > 0 ? Math.max(0, Math.min(100, (Math.abs(Number(value) || 0) / scale) * 100)) : 0;
  return `${pct.toFixed(1)}%`;
};

const signedBarWidth = (value, scale) => {
  const pct = scale > 0 ? Math.max(0, Math.min(50, (Math.abs(Number(value) || 0) / scale) * 50)) : 0;
  return `${pct.toFixed(1)}%`;
};

const humanizeKey = (value, map = {}) => {
  if (!value) return "n/a";
  if (map[value]) return map[value];
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

const splitValues = (value) =>
  String(value || "")
    .split(";")
    .map((item) => item.trim())
    .filter(Boolean);

const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const getMethodPalette = (familyKey) => {
  const keys = METHOD_PALETTE_KEYS[familyKey] || METHOD_PALETTE_KEYS.headline_vs_sensitivity;
  return keys.map((key) => cssVar(key) || "#0f5b51");
};

const renderTermList = (termRows = []) =>
  termRows.length
    ? `<details class="term-disclosure">
        <summary>Show variable definitions</summary>
        <div class="term-list">
        ${termRows
          .map(
            (item) => `<div class="term-list-item">
              <strong class="term-latex">$${escapeHtml(item.latex)}$</strong>
              <span>${escapeHtml(item.description)}</span>
            </div>`,
          )
          .join("")}
      </div>
      </details>`
    : "";

const formatBillions = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
  const billions = Number(value) / 1000;
  const sign = billions < 0 ? "-" : "";
  return `${sign}$${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(Math.abs(billions))}B`;
};

const formatSignedBillions = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
  const billions = Number(value) / 1000;
  const sign = billions >= 0 ? "+" : "-";
  return `${sign}$${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(Math.abs(billions))}B`;
};

const formatSignedCompact = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
  return `${Number(value) >= 0 ? "+" : ""}${formatCompact(value)}`;
};

const formatSignedMillions = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
  const billions = Number(value) / 1000;
  const sign = billions >= 0 ? "+" : "-";
  return `${sign}$${new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(Math.abs(billions))}B`;
};

const formatPercentGdp = (value, { digits = 2 } = {}) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
  const numeric = Number(value);
  const sign = numeric < 0 ? "-" : "";
  return `${sign}${new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(Math.abs(numeric))}%`;
};

const formatSignedPercentGdp = (value, { digits = 2 } = {}) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
  const numeric = Number(value);
  const sign = numeric >= 0 ? "+" : "-";
  return `${sign}${new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(Math.abs(numeric))}%`;
};

const formatAxisPercentGdp = (value, { digits = 1 } = {}) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "n/a";
  const numeric = Number(value);
  const sign = numeric < 0 ? "-" : "";
  return `${sign}${new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(Math.abs(numeric))}%`;
};

const pickPercentDigits = (maxAbs) => {
  if (!Number.isFinite(maxAbs) || maxAbs <= 0) return 2;
  if (maxAbs >= 10) return 1;
  if (maxAbs >= 1) return 2;
  if (maxAbs >= 0.1) return 3;
  if (maxAbs >= 0.01) return 4;
  return 5;
};

// Raw TDC values in the bundle are quarterly flows in millions of U.S. dollars.
// Nominal GDP is stored as SAAR in billions. Annualize the quarterly flow (multiply by 4)
// and divide by the annual-rate GDP level in matching units (billions × 1000 = millions).
const toPercentOfNominalGdp = (valueMillions, gdpSaarBillions) => {
  const millions = Number(valueMillions);
  const gdp = Number(gdpSaarBillions);
  if (!Number.isFinite(millions) || !Number.isFinite(gdp) || gdp <= 0) return null;
  return ((millions * 4) / (gdp * 1000)) * 100;
};

const formatUtcDate = (value) => {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
    timeZone: "UTC",
  }).format(date);
};

const METHOD_EQUATIONS = {
  tdc_base_bank_only_ru_flow:
    "\\Delta D^{mkt,bank}_{TDC}=\\Delta TS^{tx}_{Fed}+\\Delta TS^{tx}_{Banks}+\\Delta TS^{tx}_{ROW}-\\Delta TOC^{tx}_{Treasury}+Remit^{+}_{Fed}",
  tdc_tier1_fed_corrected_bank_only_ru_flow:
    "\\text{Tier 1}_{bank}=\\text{Tier 0}_{bank}-Coupon_{Fed}",
  tdc_tier2_interest_corrected_bank_only_ru_flow:
    "\\text{Tier 2}_{bank}=\\text{Tier 0}_{bank}-Coupon_{Fed}-Coupon_{Banks}-Coupon_{ROW}",
  tdc_tier3_fiscal_corrected_bank_only_ru_flow:
    "\\text{Tier 3}_{bank}=\\text{Tier 2}_{bank}+Adj^{fiscal}_{bank}+Adj^{fiscal}_{ROW}+Adj^{cash}_{Mint}",
  tdc_base_broad_depository_np_cu_ru_flow:
    "\\text{Tier 0}_{broad}=\\text{Tier 0}_{bank}+\\Delta TS^{tx}_{NPCU}",
  tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow:
    "\\text{Tier 1}_{broad}=\\text{Tier 0}_{broad}-Coupon_{Fed}",
  tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow:
    "\\text{Tier 2}_{broad}=\\text{Tier 0}_{broad}-Coupon_{Fed}-Coupon_{Banks}-Coupon_{ROW}",
  tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow:
    "\\text{Tier 3}_{broad}=\\text{Tier 2}_{broad}+Adj^{fiscal}_{bank}+Adj^{fiscal}_{ROW}+Adj^{cash}_{Mint}",
  bank_receipt_historical_default_view:
    "\\text{Historical Tier 3}^{bank}_{overlay}=\\text{Tier 3}_{bank}+Receipt^{hist}_{bank}",
  row_mrv_primary_nondefault_pilot:
    "\\text{ROW MRV pilot}=\\text{Live Tier 3}_{bank}+MRV^{pilot}_{ROW}",
};

function chip(label, value) {
  return `<span class="chip"><strong>${label}</strong><span>${value}</span></span>`;
}

function panelMetric(title, value, note) {
  return `<article class="metric-card">
    <div class="metric-title"><h3>${title}</h3><span class="metric-value">${value}</span></div>
    <p class="metric-subtext">${note}</p>
  </article>`;
}

function posterMetric(label, value, note, posture = "live") {
  return `<article class="poster-metric poster-metric--${posture}">
    <p class="poster-label">${label}</p>
    <strong>${value}</strong>
    <p>${note}</p>
  </article>`;
}

function tableShell(title, headers, rows, note = "") {
  const head = headers.map((header) => `<th>${header}</th>`).join("");
  const body = rows
    .map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`)
    .join("");
  return `<div class="table-shell">
    <h3>${title}</h3>
    <table>
      <thead><tr>${head}</tr></thead>
      <tbody>${body}</tbody>
    </table>
    ${note ? `<p class="table-note">${note}</p>` : ""}
  </div>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderTheorySection(bundle) {
  const rows = asRecords(bundle.research?.theory_measurement_map).sort(
    (a, b) => Number(a.display_order || 0) - Number(b.display_order || 0),
  );
  const theoryRows = rows.filter((row) => row.equation_family === "theoretical_identity");
  const measuredRows = rows.filter((row) => row.equation_family !== "theoretical_identity");

  document.querySelector("#theory-cards").innerHTML = theoryRows
    .map(
      (row) => `<article class="equation-card is-theoretical">
        <header>
          <div>
            <p class="eyebrow">Theoretical identity</p>
            <h3>${escapeHtml(row.display_title)}</h3>
          </div>
          <span class="equation-status">Informational only</span>
        </header>
        <div class="equation-block">$$${escapeHtml(row.latex)}$$</div>
        <p class="metric-subtext">${escapeHtml(row.plain_english_summary)}</p>
        ${renderTermList(THEORY_TERM_LISTS[row.equation_key] || [])}
        <p class="table-note"><strong>How the site uses this identity:</strong> ${escapeHtml(row.current_measurement_mapping)}</p>
        <p class="table-note"><strong>Important limit:</strong> ${escapeHtml(row.main_caveat)}</p>
      </article>`,
    )
    .join("");

  const theoryNode = document.querySelector("#theory-cards");
  if (window.renderMathInElement) {
    window.renderMathInElement(theoryNode, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "$", right: "$", display: false },
      ],
      throwOnError: false,
    });
  }

  document.querySelector("#theory-map-table").innerHTML = `
    <div class="map-stack">
      <article class="summary-card map-lead">
        <p class="summary-kicker">Theory to measurement map</p>
        <h3>Theory stays informational; measurements carry the live burden.</h3>
        <p>The live repo is narrower than the identities. Each measurement below shows what is actually implemented now, what role it plays, and what still limits it.</p>
      </article>
      ${measuredRows
        .map(
          (row) => `<article class="map-card">
            <div class="map-card-head">
              <div>
                <p class="summary-kicker">${escapeHtml(ROLE_LABELS[row.repo_role] || "Measured approximation")}</p>
                <h3>${escapeHtml(row.display_title)}</h3>
              </div>
              <span class="equation-status">${escapeHtml(humanizeKey(row.implementation_status).replaceAll("Estimate", "measurement"))}</span>
            </div>
            <p>${escapeHtml(row.current_measurement_mapping)}</p>
            <p class="table-note"><strong>Important limit:</strong> ${escapeHtml(row.main_caveat)}</p>
          </article>`,
        )
        .join("")}
      <p class="table-note">The theory identities explain what TDC is. The repo’s live estimates are narrower public-data implementations, bounded overlays, or diagnostics.</p>
    </div>
  `;
}

function renderHero(bundle) {
  document.querySelector("#hero-thesis").textContent = bundle.site?.thesis || "";
  const goals = asRecords(bundle.research?.project_goal_status_review);
  const bankReceipts = goals.find((row) => row.goal_key === "bank_receipts");
  const rowReceipts = goals.find((row) => row.goal_key === "row_receipts");
  const fiscal = goals.find((row) => row.goal_key === "fiscal_flow_tdc_equation");
  const monetary = goals.find((row) => row.goal_key === "monetary_disaggregated_tdc_equation");
  document.querySelector("#hero-status").innerHTML = [
    chip("Latest quarter", bundle.summary.latest_period || "n/a"),
    chip("Bank receipts", STATUS_SHORT_LABELS[bankReceipts?.current_status] || humanizeKey(bankReceipts?.current_status || "n/a")),
    chip("Foreign receipts", STATUS_SHORT_LABELS[rowReceipts?.current_status] || humanizeKey(rowReceipts?.current_status || "n/a")),
    chip("Fiscal shell", STATUS_SHORT_LABELS[fiscal?.current_status] || humanizeKey(fiscal?.current_status || "n/a")),
    chip("Monetary", STATUS_SHORT_LABELS[monetary?.current_status] || humanizeKey(monetary?.current_status || "n/a")),
  ].join("");
  document.querySelector("#hero-notes").innerHTML = [
    `<div class="hero-note"><span class="hero-note-kicker">Live headline</span><p>The fiscal-corrected bank-only estimate is the working measure for current quarters. It is the corrected ladder, not the raw Treasury-transaction baseline.</p></div>`,
    `<div class="hero-note"><span class="hero-note-kicker">Receipt boundary</span><p>Current bank and foreign receipt cells remain explicit boundary choices. Historical bank overlays and the MRV pilot stay visible but separate.</p></div>`,
  ].join("");

  const latest = bundle.summary.latest_methods || {};
  const ladder = bundle.site?.latest_ladder?.bank_only || {};
  document.querySelector("#hero-panel").innerHTML = `
    <article class="hero-feature">
      <p class="eyebrow">Current live working estimate</p>
      <div class="hero-feature-head">
        <div>
          <h3>Fiscal-corrected bank-only headline</h3>
          <p class="metric-subtext">Main live fiscal-flow-corrected estimate, with receipt-side boundaries still explicit.</p>
        </div>
        <div class="hero-feature-value">
          <em>${formatBillions(latest.tdc_tier3_fiscal_corrected_bank_only_ru_flow)}</em>
          <span class="hero-feature-units">${bundle.summary.latest_period || "n/a"} · USD billions per quarter</span>
        </div>
      </div>
      <div class="hero-feature-ladder">
        <div class="hero-step"><span>Uncorrected baseline</span><strong>${formatSignedBillions(ladder.tier0)}</strong></div>
        <div class="hero-step"><span>After Fed coupon correction</span><strong>${formatSignedBillions(ladder.tier1)}</strong></div>
        <div class="hero-step"><span>After interest corrections</span><strong>${formatSignedBillions(ladder.tier2)}</strong></div>
        <div class="hero-step hero-step-active"><span>After fiscal corrections</span><strong>${formatSignedBillions(ladder.tier3)}</strong></div>
      </div>
      <div class="chip-row">
        ${chip("Live working estimate", "Fiscal-corrected bank-only headline")}
        ${chip("Broader perimeter view", formatBillions(latest.tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow))}
      </div>
      <div class="posture-legend">
        <div class="posture-legend-item"><span class="posture-swatch posture-swatch--live"></span><strong>Live</strong><span>Main working estimate now</span></div>
        <div class="posture-legend-item"><span class="posture-swatch posture-swatch--historical"></span><strong>Historical</strong><span>Bounded window with fresher support</span></div>
        <div class="posture-legend-item"><span class="posture-swatch posture-swatch--bounded"></span><strong>Bounded</strong><span>Visible, but not promoted into default</span></div>
        <div class="posture-legend-item"><span class="posture-swatch posture-swatch--diagnostic"></span><strong>Diagnostic</strong><span>Cross-check or residual surface</span></div>
      </div>
      <div class="poster-foot">
        <div><span>Uncorrected baseline</span><strong>${formatBillions(latest.tdc_base_bank_only_ru_flow)}</strong></div>
        <div><span>After interest corrections</span><strong>${formatBillions(latest.tdc_tier2_interest_corrected_bank_only_ru_flow)}</strong></div>
        <div><span>Final correction step</span><strong>${formatSignedMillions((latest.tdc_tier3_fiscal_corrected_bank_only_ru_flow ?? 0) - (latest.tdc_tier2_interest_corrected_bank_only_ru_flow ?? 0))}</strong></div>
      </div>
    </article>
  `;
}

function renderSignalBand(bundle) {
  const researchComparison = asRecords(bundle.research?.tier3_research_comparison);
  const liveComparison = researchComparison.find((row) => row.comparison_key === "latest_live_defaults");
  const historicalComparison = researchComparison.find((row) => row.comparison_key === "latest_historical_bank_window");
  const mrvRow = getLatestResearchRow(bundle.research?.receipt_unblock_status, "branch_key", "row_mrv_cbsp_primary");
  const monetary = asRecords(bundle.research?.monetary_target_preference_review)[0];

  document.querySelector("#signal-strip").innerHTML = [
    posterMetric(
      "Current live estimate",
      formatBillions(liveComparison?.tier3_bank_only_mil),
      `Fiscal-corrected bank-only headline at ${liveComparison?.reference_date || "n/a"}. This is the live working estimate for the site.`,
      "live",
    ),
    posterMetric(
      "Strongest historical receipt result",
      formatBillions(historicalComparison?.historical_bank_receipt_variant_mil),
      `Historical bank overlay at ${historicalComparison?.reference_date || "n/a"}. Strongest bounded receipt-side result in the repo.`,
      "historical",
    ),
    posterMetric(
      "Bounded foreign pilot",
      formatBillions(mrvRow?.latest_value_millions),
      `MRV latest support at ${mrvRow?.latest_relevant_date || "n/a"}. Bounded nondefault sensitivity, not live default.`,
      "bounded",
    ),
    posterMetric(
      "Preferred cross-check",
      formatBillions(monetary?.depository_residual_after_expanded_mil),
      `Preferred target: ${monetary?.preferred_target === "depository_target" ? "Depository target" : humanizeKey(monetary?.preferred_target || "depository_target")}. Monetary branch remains diagnostic, not a replacement headline.`,
      "diagnostic",
    ),
  ].join("");
}

function renderMethodExplorer(bundle) {
  const familySelect = document.querySelector("#method-family-select");
  const rangeSelect = document.querySelector("#method-range-select");
  familySelect.innerHTML = Object.entries(METHOD_FAMILY_LABELS)
    .map(([value, label]) => `<option value="${value}">${label}</option>`)
    .join("");
  rangeSelect.innerHTML = Object.entries(METHOD_RANGE_OPTIONS)
    .map(([value, label]) => `<option value="${value}">${label}</option>`)
    .join("");
  rangeSelect.value = "last_5y";

  const dates = bundle.dates || [];
  let currentFamily = familySelect.value || "bank_only_ladder";
  let currentRange = rangeSelect.value || "last_5y";
  let activeMethods = [...METHOD_FAMILIES[currentFamily]];
  let resizeObserver;

  const gdpSeries = Array.isArray(bundle?.references?.nominal_gdp_saar_bil)
    ? bundle.references.nominal_gdp_saar_bil
    : null;
  const gdpAvailable =
    Array.isArray(gdpSeries) &&
    gdpSeries.some((value) => Number.isFinite(Number(value)) && Number(value) > 0);
  let showPercentGdp = false;
  const percentToggle = document.querySelector("#method-percent-gdp-toggle");
  const percentNote = document.querySelector("#method-percent-gdp-note");
  if (percentToggle) {
    percentToggle.checked = false;
    percentToggle.disabled = !gdpAvailable;
  }
  if (percentNote) {
    if (gdpAvailable) {
      percentNote.hidden = true;
      percentNote.textContent = "";
    } else {
      percentNote.hidden = false;
      percentNote.textContent =
        "Percent-of-GDP view is unavailable: nominal GDP is missing from this bundle.";
    }
  }

  const drawChart = () =>
    drawMethodChart(bundle, dates, activeMethods, currentRange, currentFamily, {
      showPercentGdp: showPercentGdp && gdpAvailable,
      gdpSeries,
    });

  const rerender = () => {
    currentFamily = familySelect.value;
    currentRange = rangeSelect.value;
    const methods = METHOD_FAMILIES[currentFamily];
    const container = document.querySelector("#method-toggle-list");
    container.innerHTML = methods
      .map((method) => {
        const checked = activeMethods.includes(method) ? "checked" : "";
        return `<label class="toggle-pill">
          <input type="checkbox" data-method="${method}" ${checked} />
          <span>${METHOD_LABELS[method] || method}</span>
        </label>`;
      })
      .join("");
    container.querySelectorAll("input").forEach((input) => {
      input.addEventListener("change", () => {
        const method = input.dataset.method;
        if (input.checked) {
          activeMethods = Array.from(new Set([...activeMethods, method]));
        } else {
          activeMethods = activeMethods.filter((item) => item !== method);
        }
        drawChart();
        renderMethodTable(bundle, activeMethods);
      });
    });
    activeMethods = methods.filter((method) => activeMethods.includes(method));
    if (!activeMethods.length) activeMethods = [methods[0]];
    renderMethodStory(bundle, currentFamily, currentRange, activeMethods);
    drawChart();
    renderMethodTable(bundle, activeMethods);
  };

  familySelect.addEventListener("change", () => {
    activeMethods = [...METHOD_FAMILIES[familySelect.value]];
    rerender();
  });
  rangeSelect.addEventListener("change", rerender);
  if (percentToggle && gdpAvailable) {
    percentToggle.addEventListener("change", () => {
      showPercentGdp = percentToggle.checked;
      drawChart();
    });
  }
  if ("ResizeObserver" in window) {
    resizeObserver = new ResizeObserver(() => drawChart());
    resizeObserver.observe(document.querySelector("#method-chart"));
  } else {
    window.addEventListener("resize", () => drawChart());
  }
  window.__tdcRerenderMethods = rerender;
  rerender();
}

function renderMethodStory(bundle, familyKey, rangeKey, methods) {
  const latest = bundle.summary.latest_methods || {};
  const familyCopy = {
    bank_only_ladder: "This view tracks the bank-only correction ladder from the raw baseline to the live fiscal-corrected headline.",
    broad_depository_ladder: "This view keeps the same ladder shape but widens the deposit perimeter to include natural-person credit unions.",
    headline_vs_sensitivity: "This view contrasts the live headline with historical and sensitivity variants that should not be read as co-equal defaults.",
  };
  const familyNarratives = {
    bank_only_ladder: {
      primaryLabel: "Live headline",
      primaryMethod: "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
      secondaryLabel: "Uncorrected baseline",
      secondaryMethod: "tdc_base_bank_only_ru_flow",
    },
    broad_depository_ladder: {
      primaryLabel: "Live headline",
      primaryMethod: "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow",
      secondaryLabel: "Perimeter baseline",
      secondaryMethod: "tdc_base_broad_depository_np_cu_ru_flow",
    },
    headline_vs_sensitivity: {
      primaryLabel: "Live headline",
      primaryMethod: "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
      secondaryLabel: "Sensitivity context",
      secondaryMethod: methods.find((method) => METHOD_POSTURES[method] !== "live") || methods[0],
    },
  };
  const narrative = familyNarratives[familyKey] || familyNarratives.bank_only_ladder;
  document.querySelector("#method-story").innerHTML = `
    <article class="story-panel">
      <p class="posture-ribbon posture-ribbon--live">Live comparison surface</p>
      <h3>${METHOD_FAMILY_LABELS[familyKey] || "Method comparison"}</h3>
      <p>${familyCopy[familyKey] || ""}</p>
      <div class="story-grid">
        <div>
          <span class="story-label">Current window</span>
          <strong>${METHOD_RANGE_OPTIONS[rangeKey] || "Current range"}</strong>
        </div>
        <div>
          <span class="story-label">${narrative.primaryLabel}</span>
          <strong>${METHOD_LABELS[narrative.primaryMethod] || narrative.primaryMethod} · ${formatBillions(latest[narrative.primaryMethod])}</strong>
        </div>
        <div>
          <span class="story-label">${narrative.secondaryLabel}</span>
          <strong>${METHOD_LABELS[narrative.secondaryMethod] || narrative.secondaryMethod} · ${formatBillions(latest[narrative.secondaryMethod])}</strong>
        </div>
      </div>
    </article>
  `;
}

function filterDatesForRange(dates, range) {
  if (range === "full_history") return dates;
  if (range === "post_2002") return dates.filter((date) => date >= "2002-01-01");
  if (range === "last_3y") return dates.slice(-12);
  if (range === "last_5y") return dates.slice(-20);
  if (range === "last_10y") return dates.slice(-40);
  return dates;
}

function drawMethodChart(bundle, dates, methods, rangeKey, familyKey, options = {}) {
  const { showPercentGdp = false, gdpSeries = null } = options;
  const svg = document.querySelector("#method-chart");
  const legend = document.querySelector("#method-chart-legend");
  const tooltip = document.querySelector("#method-chart-tooltip");
  const width = Math.max(720, Math.round(svg.getBoundingClientRect().width || 1200));
  const height = Math.round(width * 0.44);
  const margin = { top: 18, right: 32, bottom: 36, left: 78 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  const filteredDates = filterDatesForRange(dates, rangeKey);
  const startIndex = Math.max(0, dates.length - filteredDates.length);
  const palette = getMethodPalette(familyKey);
  const gridColor = cssVar("--rule") || "rgba(24,32,24,0.12)";
  const zeroColor = cssVar("--rule-strong") || "rgba(24,32,24,0.18)";
  const percentMode = Boolean(showPercentGdp) && Array.isArray(gdpSeries);
  const filteredGdp = percentMode ? gdpSeries.slice(startIndex) : null;
  const axisTitle = percentMode
    ? "Quarterly flow, percent of nominal GDP (SAAR-annualized)"
    : "Quarterly flow, USD billions";
  const unitDescription = percentMode
    ? "quarterly TDC flow expressed as percent of nominal GDP"
    : "quarterly USD billions";
  const chartSeries = methods.map((method, index) => ({
    method,
    label: METHOD_LABELS[method] || method,
    color: palette[index % palette.length],
    posture: METHOD_POSTURES[method] || "diagnostic",
    values: getColumnSeries(bundle.estimates, method)
      .slice(startIndex)
      .map((value, i) => {
        if (value === null || value === undefined) return null;
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return null;
        if (!percentMode) return numeric;
        return toPercentOfNominalGdp(numeric, filteredGdp?.[i]);
      }),
  }));
  const values = chartSeries
    .flatMap((series) => series.values)
    .filter(Number.isFinite);
  const percentDigits = percentMode
    ? pickPercentDigits(values.reduce((m, v) => Math.max(m, Math.abs(v)), 0))
    : 2;
  const axisFormat = percentMode
    ? (value) => formatAxisPercentGdp(value, { digits: percentDigits })
    : formatAxisBillions;
  const legendFormat = percentMode
    ? (value) => formatPercentGdp(value, { digits: percentDigits })
    : formatBillions;
  const tooltipFormat = percentMode
    ? (value) => formatSignedPercentGdp(value, { digits: percentDigits })
    : formatSignedBillions;
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const includesZero = rawMin < 0 && rawMax > 0;
  const minValue = includesZero ? Math.min(rawMin, 0) : rawMin;
  const maxValue = includesZero ? Math.max(rawMax, 0) : rawMax;
  const valueRange = maxValue - minValue || 1;
  const xAt = (i) => margin.left + (i / Math.max(filteredDates.length - 1, 1)) * innerWidth;
  const yAt = (value) => margin.top + innerHeight - ((value - minValue) / valueRange) * innerHeight;

  const ticks = Array.from({ length: 5 }, (_, index) => minValue + (valueRange * index) / 4);
  const grid = ticks
    .map((tick) => {
      const y = yAt(tick);
      return `<g>
        <line x1="${margin.left}" x2="${width - margin.right}" y1="${y}" y2="${y}" stroke="${gridColor}" />
        <text class="chart-label" x="${margin.left - 12}" y="${y + 4}" text-anchor="end">${axisFormat(tick)}</text>
      </g>`;
    })
    .join("");

  const xLabels = Array.from({ length: Math.min(5, filteredDates.length) }, (_, index) =>
    Math.round((index / Math.max(Math.min(5, filteredDates.length) - 1, 1)) * Math.max(filteredDates.length - 1, 0)),
  )
    .filter((value, index, array) => array.indexOf(value) === index && value >= 0)
    .map((i) => `<text class="chart-label" x="${xAt(i)}" y="${height - 10}" text-anchor="middle">${filteredDates[i]}</text>`)
    .join("");

  const lines = chartSeries
    .map((series) => {
      const points = series.values
        .map((value, i) => (Number.isFinite(value) ? `${xAt(i)},${yAt(value)}` : null))
        .filter(Boolean)
        .join(" ");
      const latestValue = series.values.filter(Number.isFinite).slice(-1)[0];
      const latestIndex =
        series.values
          .map((value, i) => ({ value, i }))
          .filter(({ value }) => Number.isFinite(value))
          .slice(-1)[0]?.i ?? 0;
      const endLabel =
        series.posture === "live"
          ? `<text class="chart-end-label" x="${Math.min(width - margin.right + 8, xAt(latestIndex) + 10)}" y="${yAt(latestValue) + 4}" fill="${series.color}">${series.label}</text>`
          : "";
      return `<g>
        <polyline class="chart-line chart-line--${series.posture}" fill="none" stroke="${series.color}" points="${points}" />
        <circle cx="${xAt(latestIndex)}" cy="${yAt(latestValue)}" r="4.5" fill="${series.color}" />
        ${endLabel}
      </g>`;
    })
    .join("");

  const zeroLine = includesZero
    ? `<line x1="${margin.left}" x2="${width - margin.right}" y1="${yAt(0)}" y2="${yAt(0)}" stroke="${zeroColor}" />`
    : "";
  document.querySelector("#method-chart-note").textContent = percentMode
    ? `Window: ${METHOD_RANGE_OPTIONS[rangeKey] || "Current range"}. Units: percent of nominal GDP. Percent-of-GDP view annualizes the quarterly TDC flow and divides by nominal GDP at SAAR: (value in millions × 4) / (nominal_gdp_saar_billions × 1000) × 100. Quarters without a matching nominal-GDP observation render as gaps.`
    : `Window: ${METHOD_RANGE_OPTIONS[rangeKey] || "Current range"}. Units: quarterly flow, USD billions throughout the chart and hover readout. Reduce the visible series count before making close comparisons.`;
  legend.innerHTML = chartSeries
    .map(
      (series) => `<div class="chart-legend-item">
        <span class="chart-legend-swatch" style="background:${series.color}"></span>
        <span>${series.label}</span>
        <strong>${legendFormat(series.values.filter(Number.isFinite).slice(-1)[0])}</strong>
      </div>`,
    )
    .join("");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.innerHTML = `<rect width="${width}" height="${height}" fill="transparent" />
    <title>Method comparison chart</title>
    <desc>${METHOD_FAMILY_LABELS[familyKey] || "Method comparison"} for ${METHOD_RANGE_OPTIONS[rangeKey] || "current range"}, with live and comparison estimator lines shown as ${unitDescription}.</desc>
    ${grid}
    ${zeroLine}
    <text class="chart-axis-title" transform="translate(18 ${height / 2}) rotate(-90)">${axisTitle}</text>
    ${lines}
    ${xLabels}
    <g id="method-hover-layer"></g>`;
  document.querySelector("#method-chart-summary").textContent = `${METHOD_FAMILY_LABELS[familyKey] || "Method comparison"} for ${METHOD_RANGE_OPTIONS[rangeKey] || "current range"}. Latest visible values: ${chartSeries
    .map((series) => `${series.label} ${legendFormat(series.values.filter(Number.isFinite).slice(-1)[0])}`)
    .join("; ")}.`;

  const hoverLayer = svg.querySelector("#method-hover-layer");
  const clampIndex = (index) => Math.max(0, Math.min(filteredDates.length - 1, index));
  const renderHover = (index) => {
    const activeDate = filteredDates[index];
    const guideline = `<line x1="${xAt(index)}" x2="${xAt(index)}" y1="${margin.top}" y2="${height - margin.bottom}" stroke="${zeroColor}" stroke-dasharray="4 6" />`;
    const activePoints = chartSeries
      .filter((series) => Number.isFinite(series.values[index]))
      .map(
        (series) =>
          `<circle cx="${xAt(index)}" cy="${yAt(series.values[index])}" r="5.5" fill="${series.color}" stroke="rgba(255,255,255,0.9)" stroke-width="2" />`,
      )
      .join("");
    hoverLayer.innerHTML = `${guideline}${activePoints}`;
    tooltip.hidden = false;
    tooltip.innerHTML = `<strong>${activeDate}</strong>${chartSeries
      .filter((series) => Number.isFinite(series.values[index]))
      .map(
        (series) => `<div class="chart-tooltip-row">
          <span class="chart-legend-swatch" style="background:${series.color}"></span>
          <span>${series.label}</span>
          <strong>${tooltipFormat(series.values[index])}</strong>
        </div>`,
      )
      .join("")}`;
  };

  const clientToSvgX = (clientX) => {
    const ctm = svg.getScreenCTM();
    if (ctm && typeof svg.createSVGPoint === "function") {
      const pt = svg.createSVGPoint();
      pt.x = clientX;
      pt.y = 0;
      return pt.matrixTransform(ctm.inverse()).x;
    }
    const rect = svg.getBoundingClientRect();
    return ((clientX - rect.left) / Math.max(rect.width, 1)) * width;
  };
  const indexFromClientX = (clientX) => {
    const svgX = clientToSvgX(clientX);
    const relative = (svgX - margin.left) / Math.max(innerWidth, 1);
    return clampIndex(Math.round(relative * Math.max(filteredDates.length - 1, 0)));
  };

  svg.onmousemove = (event) => {
    const rect = svg.getBoundingClientRect();
    const pixelX = event.clientX - rect.left;
    renderHover(indexFromClientX(event.clientX));
    tooltip.style.left = `${Math.min(rect.width - 240, Math.max(12, pixelX + 14))}px`;
    tooltip.style.top = "14px";
  };
  svg.onmouseleave = () => {
    hoverLayer.innerHTML = "";
    tooltip.hidden = true;
  };
  svg.onclick = (event) => {
    renderHover(indexFromClientX(event.clientX));
  };
  svg.ontouchstart = (event) => {
    const touch = event.touches?.[0];
    if (!touch) return;
    renderHover(indexFromClientX(touch.clientX));
  };

  renderHover(filteredDates.length - 1);
}

function renderMethodTable(bundle, methods) {
  const latest = bundle.summary.latest_methods || {};
  document.querySelector("#method-table").innerHTML = methods
    .map((method) => `<article class="method-row">
      <div>
        <div class="list-title">
          <h3>${METHOD_LABELS[method] || method}</h3>
        </div>
        <span class="method-subtitle">${METHOD_DESCRIPTIONS[method] || ""}</span>
        <div class="method-equation method-equation--ascii">${escapeHtml(METHOD_PLAIN_FORMULAS[method] || "Used as a comparison or sensitivity surface rather than a main formula row.")}</div>
      </div>
      <div class="metric-value">${formatBillions(latest[method])}</div>
    </article>`)
    .join("");
}

function renderComponentExplorer(bundle) {
  const quarterSelect = document.querySelector("#quarter-select");
  const dates = [...bundle.dates].reverse();
  quarterSelect.innerHTML = dates.map((date) => `<option value="${date}">${date}</option>`).join("");
  const update = () => {
    const date = quarterSelect.value;
    const index = bundle.dates.indexOf(date);
    const methodValues = bundle.estimates;
    const ladderRows = [
      ["Uncorrected bank-only baseline", getColumnSeries(methodValues, "tdc_base_bank_only_ru_flow")[index]],
      ["After Fed coupon correction", getColumnSeries(methodValues, "tdc_tier1_fed_corrected_bank_only_ru_flow")[index]],
      ["After interest corrections", getColumnSeries(methodValues, "tdc_tier2_interest_corrected_bank_only_ru_flow")[index]],
      ["After fiscal corrections", getColumnSeries(methodValues, "tdc_tier3_fiscal_corrected_bank_only_ru_flow")[index]],
    ];
    document.querySelector("#ladder-list").innerHTML = ladderRows
      .map(([label, value]) => `<div class="ladder-row"><div class="list-title"><strong>${label}</strong><span class="metric-value">${formatBillions(value)}</span></div></div>`)
      .join("");

    const baseScale = Math.max(
      1,
      ...BASE_COMPONENT_KEYS.map((key) => Math.abs(Number(getColumnSeries(bundle.components, key)[index]) || 0)),
    );
    const correctionScale = Math.max(
      1,
      ...CORRECTION_KEYS.map((key) => Math.abs(Number(getColumnSeries(bundle.corrections, key)[index]) || 0)),
    );
    renderContributionList("#base-contrib-list", bundle.components, BASE_COMPONENT_KEYS, index, baseScale);
    renderContributionList("#correction-contrib-list", bundle.corrections, CORRECTION_KEYS, index, correctionScale);
  };
  quarterSelect.addEventListener("change", update);
  update();
}

function renderContributionList(target, frame, keys, index, scale) {
  document.querySelector(target).innerHTML = keys
    .map((key) => {
      const value = Number(getColumnSeries(frame, key)[index]);
      const directionClass = value >= 0 ? "positive" : "negative";
      return `<div class="list-row">
        <div class="list-title">
          <span>${METHOD_LABELS[key] || key}</span>
          <strong>${formatBillions(value)}</strong>
        </div>
        <div class="bar-track signed">
          <div class="bar-midline"></div>
          <div class="bar-fill ${directionClass}" style="width:${signedBarWidth(value, scale)}"></div>
        </div>
      </div>`;
    })
    .join("");
}

function renderReceiptSection(bundle) {
  const unblock = asRecords(bundle.research.receipt_unblock_status);
  const bankHist = unblock.find((row) => row.branch_key === "bank_table51_historical_window");
  const bankCurrent = unblock.find((row) => row.branch_key === "bank_table51_current_window");
  const rowMrv = unblock.find((row) => row.branch_key === "row_mrv_cbsp_primary");
  const bankStop = asRecords(bundle.research.bank_receipt_stop_gate).find((row) => row.row_type === "summary");
  const mrvStop = asRecords(bundle.research.row_mrv_stop_gate).find((row) => row.row_type === "summary");
  const comparison = asRecords(bundle.research.tier3_research_comparison);
  const histComparison = comparison.find((row) => row.comparison_key === "latest_historical_bank_window");
  const liveComparison = comparison.find((row) => row.comparison_key === "latest_live_defaults");
  const mrvSummary = asRecords(bundle.research.row_mrv_nondefault_evidence_summary)[0];
  const mrvBlockers = splitValues(rowMrv?.missing_source_families);
  const bankStopRows = [
    bankCurrent?.summary_note || "",
    `Historical overlay remains usable through ${bankHist?.latest_relevant_date || "n/a"}.`,
    `Current quarters stay nondefault until fresher public IRS bank-minor shares exist.`,
  ];

  document.querySelector("#bank-package-card").innerHTML = `
    <p class="posture-ribbon posture-ribbon--bounded">Historical default only</p>
    <p class="eyebrow">Historical bank receipt window</p>
    <h3>${STATUS_HEADLINES[bankStop?.status] || humanizeKey(bankStop?.status || "historical_default_only_current_nondefault")}</h3>
    <p>${bankHist?.summary_note || ""}</p>
    <div class="chip-row">
      ${chip("Latest historical quarter", bankHist?.latest_relevant_date || "n/a")}
      ${chip("Historical bridge", formatMillions(bankHist?.latest_value_millions))}
      ${chip("Historical corrected total", formatMillions(histComparison?.historical_bank_receipt_variant_mil))}
    </div>
    <ul class="summary-list">
      ${bankStopRows.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
  `;

  document.querySelector("#mrv-package-card").innerHTML = `
    <p class="posture-ribbon posture-ribbon--bounded">Bounded nondefault pilot</p>
    <p class="eyebrow">MRV bounded foreign pilot</p>
    <h3>${STATUS_HEADLINES[mrvStop?.status] || humanizeKey(mrvStop?.status || "stop_at_mrv_nondefault_pilot")}</h3>
    <p>${rowMrv?.summary_note || ""}</p>
    <div class="chip-row">
      ${chip("Current MRV pilot", formatMillions(rowMrv?.latest_value_millions))}
      ${chip("Checks complete", String(mrvSummary?.promotion_checks_complete ?? "n/a"))}
      ${chip("Checks missing", String(mrvSummary?.promotion_checks_missing ?? "n/a"))}
    </div>
    <ul class="summary-list">
      ${mrvBlockers.map((item) => `<li>${escapeHtml(BLOCKER_LABELS[item] || humanizeKey(item))}</li>`).join("")}
    </ul>
  `;

  document.querySelector("#receipt-unblock-table").innerHTML = `
    <div class="summary-stack">
      <article class="summary-card">
        <p class="summary-kicker">Current live default cells</p>
        <h3>The live fiscal-corrected estimate still keeps both receipt cells at zero by rule.</h3>
        <p>Those zeros are boundary choices, not claims that receipts are absent.</p>
        <ul class="summary-list">
          <li>Bank current window: ${escapeHtml(BLOCKER_LABELS[bankCurrent?.binding_blocker] || humanizeKey(bankCurrent?.binding_blocker || "stale_share_rule"))}</li>
          <li>Foreign current window: ${escapeHtml(BLOCKER_LABELS[rowMrv?.binding_blocker] || humanizeKey(rowMrv?.binding_blocker || "evidence_boundary"))}</li>
          <li>Live fiscal-corrected bank-only headline at ${escapeHtml(liveComparison?.reference_date || "n/a")}: ${formatMillions(liveComparison?.tier3_bank_only_mil)}</li>
        </ul>
      </article>
      <article class="summary-card">
        <p class="summary-kicker">What is usable now</p>
        <h3>The bank historical window is the strongest receipt-side result in the repo.</h3>
        <p>It is usable as a historical default view inside the age-eligible window and should stay separate from the stale current bridge.</p>
        <ul class="summary-list">
          <li>Historical overlay support date: ${escapeHtml(bankHist?.latest_relevant_date || "n/a")}</li>
          <li>Historical overlay effect: ${formatMillions(bankHist?.latest_value_millions)}</li>
          <li>Historical corrected total: ${formatMillions(histComparison?.historical_bank_receipt_variant_mil)}</li>
        </ul>
      </article>
      <article class="summary-card">
        <p class="summary-kicker">Foreign bounded push</p>
        <h3>MRV is the only recurring foreign branch still worth carrying.</h3>
        <p>It is informative as a bounded sensitivity, but still blocked from default promotion.</p>
        <ul class="summary-list">
          <li>Latest nonzero support: ${escapeHtml(rowMrv?.latest_relevant_date || "n/a")} · ${formatMillions(rowMrv?.latest_value_millions)}</li>
          <li>Promotion status: ${escapeHtml(STATUS_PUBLIC_LABELS[mrvStop?.status] || humanizeKey(mrvStop?.status || "stop_at_mrv_nondefault_pilot"))}</li>
          <li>Still missing: ${escapeHtml(mrvBlockers.map((item) => BLOCKER_LABELS[item] || humanizeKey(item)).join(", ") || "n/a")}</li>
        </ul>
      </article>
    </div>
  `;

  document.querySelector("#research-comparison-table").innerHTML = `
    <div class="comparison-stack">
      <article class="comparison-panel">
        <p class="summary-kicker">Live ladder slice</p>
        <h3>${escapeHtml(liveComparison?.reference_date || "n/a")}</h3>
        <div class="comparison-grid">
          <div><span>After interest corrections</span><strong>${formatMillions(liveComparison?.tier2_bank_only_mil)}</strong></div>
          <div><span>After fiscal corrections</span><strong>${formatMillions(liveComparison?.tier3_bank_only_mil)}</strong></div>
          <div><span>Bank boundary</span><strong>${escapeHtml(STATUS_PUBLIC_LABELS[liveComparison?.bank_receipt_boundary] || humanizeKey(liveComparison?.bank_receipt_boundary))}</strong></div>
          <div><span>Foreign boundary</span><strong>${escapeHtml(STATUS_PUBLIC_LABELS[liveComparison?.row_receipt_boundary] || humanizeKey(liveComparison?.row_receipt_boundary))}</strong></div>
        </div>
        <p class="table-note">${escapeHtml(liveComparison?.interpretation || "")}</p>
      </article>
      <article class="comparison-panel">
        <p class="summary-kicker">Historical bank window</p>
        <h3>${escapeHtml(histComparison?.reference_date || "n/a")}</h3>
        <div class="comparison-grid">
          <div><span>Historical default</span><strong>${formatMillions(histComparison?.tier3_bank_only_mil)}</strong></div>
          <div><span>Historical variant</span><strong>${formatMillions(histComparison?.historical_bank_receipt_variant_mil)}</strong></div>
          <div><span>Lower bound</span><strong>${formatMillions(histComparison?.historical_bank_lower_bound_variant_mil)}</strong></div>
          <div><span>MRV latest support</span><strong>${escapeHtml(histComparison?.current_row_mrv_pilot_latest_date || "n/a")}</strong></div>
        </div>
        <p class="table-note">${escapeHtml(histComparison?.interpretation || "")}</p>
      </article>
    </div>
  `;
}

function renderFiscalSection(bundle) {
  const residuals = asRecords(bundle.research.fiscal_reconciliation_residuals);
  const latestResidual = residuals.slice(-1)[0];
  const sourceQuality = asRecords(bundle.research.fiscal_source_quality);
  const headlineFamilies = sourceQuality.filter((row) => row.included_in_headline).slice(0, 4);
  const benchmarkFamilies = sourceQuality.filter((row) => !row.included_in_headline).slice(0, 4);
  const receiptBoundaries = asRecords(bundle.research.fiscal_receipt_boundary_review).filter((row) =>
    ["bank_live_default_receipt_cell", "row_live_default_receipt_cell", "bank_receipt_historical_overlay_candidate", "row_mrv_primary_nondefault_pilot"].includes(row.boundary_key),
  );
  document.querySelector("#fiscal-lead").innerHTML = `
    <article class="story-panel story-panel--diagnostic">
      <p class="posture-ribbon posture-ribbon--diagnostic">Bounded diagnostic shell</p>
      <h3>Arithmetic closure is not the same thing as receipt completeness.</h3>
      <p>The fiscal shell is useful because it shows where the ladder still closes and where the unresolved receipt cells are policy boundaries rather than observed zeros.</p>
    </article>
  `;
  document.querySelector("#fiscal-residual-card").innerHTML = `
    <div class="panel">
      <p class="posture-ribbon posture-ribbon--diagnostic">Diagnostic reconciliation</p>
      <p class="eyebrow">Latest reconciliation</p>
      <h3>${latestResidual?.date || "n/a"}</h3>
      <div class="chip-row">
        ${chip("Uncorrected residual", formatMillions(latestResidual?.tier0_reconstruction_residual_mil))}
        ${chip("Interest-corrected residual", formatMillions(latestResidual?.tier2_reconstruction_residual_mil))}
        ${chip("Fiscal-corrected residual", formatMillions(latestResidual?.tier3_reconstruction_residual_mil))}
      </div>
      <p class="metric-subtext">
        The fiscal shell remains a reconciliation matrix around the ladder. Zero-ish residuals mean the currently loaded ladder components still close arithmetically even while receipt-side boundaries remain only partly solved.
      </p>
    </div>
  `;
  document.querySelector("#fiscal-quality-table").innerHTML = `
    <div class="quality-band">
      <article class="summary-card">
        <p class="summary-kicker">Loaded in the live shell</p>
        <h3>Coupon and outlay families already do most of the fiscal work.</h3>
        <div class="quality-list">
          ${headlineFamilies
            .map(
              (row) => `<div class="quality-item">
                <div>
                  <strong>${escapeHtml(QUALITY_FAMILY_LABELS[row.row_family] || humanizeKey(row.row_family))}</strong>
                  <p>${escapeHtml(row.notes || "")}</p>
                </div>
                <div class="quality-meta">
                  <span>${escapeHtml(RELIABILITY_LABELS[row.reliability_grade] || humanizeKey(row.reliability_grade))}</span>
                  <strong>${formatMillions(row.latest_value_millions)}</strong>
                </div>
              </div>`,
            )
            .join("")}
        </div>
      </article>
      <article class="summary-card">
        <p class="summary-kicker">Receipt boundaries inside the shell</p>
        <h3>Live default cells stay zero, while bounded overlays remain separate.</h3>
        <div class="quality-list">
          ${receiptBoundaries
            .map(
              (row) => `<div class="quality-item">
                <div>
                  <strong>${escapeHtml(BOUNDARY_LABELS[row.boundary_key] || humanizeKey(row.boundary_key))}</strong>
                  <p>${escapeHtml(row.interpretation || "")}</p>
                </div>
                <div class="quality-meta">
                  <span>${escapeHtml(BLOCKER_LABELS[row.binding_blocker] || humanizeKey(row.binding_blocker))}</span>
                  <strong>${formatMillions(row.latest_value_millions)}</strong>
                </div>
              </div>`,
            )
            .join("")}
        </div>
      </article>
      <article class="summary-card">
        <p class="summary-kicker">Benchmark and context rows</p>
        <h3>These rows matter for scale and reconciliation, not for headline promotion.</h3>
        <div class="quality-list">
          ${benchmarkFamilies
            .map(
              (row) => `<div class="quality-item">
                <div>
                  <strong>${escapeHtml(QUALITY_FAMILY_LABELS[row.row_family] || humanizeKey(row.row_family))}</strong>
                  <p>${escapeHtml(row.notes || "")}</p>
                </div>
                <div class="quality-meta">
                  <span>${escapeHtml(RELIABILITY_LABELS[row.reliability_grade] || humanizeKey(row.reliability_grade))}</span>
                  <strong>${formatMillions(row.latest_value_millions)}</strong>
                </div>
              </div>`,
            )
            .join("")}
        </div>
      </article>
    </div>
  `;
}

function renderMonetarySection(bundle) {
  const goals = asRecords(bundle.research.project_goal_status_review);
  const monetary = asRecords(bundle.research.monetary_target_preference_review)[0];
  const coreGoals = goals.filter((row) =>
    ["bank_receipts", "row_receipts", "fiscal_flow_tdc_equation", "monetary_disaggregated_tdc_equation"].includes(row.goal_key),
  );
  document.querySelector("#monetary-lead").innerHTML = `
    <article class="story-panel story-panel--diagnostic">
      <p class="posture-ribbon posture-ribbon--diagnostic">Diagnostic branch</p>
      <h3>The monetary system is there to bound interpretation, not to replace the ladder.</h3>
      <p>The site should make the preferred depository cross-check visible while keeping the commercial-bank target framed as a stress surface.</p>
    </article>
  `;
  document.querySelector("#goal-status-table").innerHTML = `
    <div class="status-board">
      ${coreGoals
        .map(
          (row) => `<article class="summary-card">
            <p class="summary-kicker">${escapeHtml(humanizeKey(row.goal_key, GOAL_LABELS))}</p>
            <h3>${escapeHtml(STATUS_PUBLIC_LABELS[row.current_status] || humanizeKey(row.current_status))}</h3>
            <p>${escapeHtml(row.summary_note || "")}</p>
            <div class="goal-footer">
              <span>${escapeHtml(row.latest_relevant_date || "n/a")}</span>
              <strong>${escapeHtml(BLOCKER_LABELS[row.binding_blocker] || humanizeKey(row.binding_blocker || "none"))}</strong>
            </div>
          </article>`,
        )
        .join("")}
    </div>
  `;
  document.querySelector("#monetary-card").innerHTML = `
    <div class="panel">
      <p class="posture-ribbon posture-ribbon--diagnostic">Diagnostic only</p>
      <p class="eyebrow">Monetary cross-check</p>
      <h3>${STATUS_HEADLINES[monetary?.recommendation_status] || humanizeKey(monetary?.recommendation_status || "prefer_depository_target_crosscheck")}</h3>
      <div class="chip-row">
        ${chip("Preferred target", monetary?.preferred_target === "depository_target" ? "Depository target" : humanizeKey(monetary?.preferred_target || "n/a"))}
        ${chip("Depository residual", formatMillions(monetary?.depository_residual_after_expanded_mil))}
        ${chip("Bank residual", formatMillions(monetary?.commercial_bank_residual_after_expanded_mil))}
      </div>
      <p class="metric-subtext">${monetary?.review_rationale || ""}</p>
      <ul class="summary-list">
        <li>Use the depository target as the preferred diagnostic cross-check.</li>
        <li>Keep the commercial-bank target as a perimeter stress surface, not a headline replacement.</li>
        <li>Do not reopen the monetary branch unless a genuinely new source family appears.</li>
      </ul>
    </div>
  `;
}

function renderWorkstreamSection(bundle) {
  const rows = asRecords(bundle.research.workstream_end_state_map).slice(0, 8);
  const order = ["push_hard", "bounded_push", "bounded_monitor", "freeze"];
  const groups = order
    .map((mode) => ({
      mode,
      rows: rows.filter((row) => row.recommended_mode === mode),
    }))
    .filter((group) => group.rows.length);
  document.querySelector("#workstream-table").innerHTML = `
    <div class="workstream-groups">
      ${groups
        .map(
          (group) => `<section class="workstream-group">
            <div class="workstream-group-head">
              <p class="summary-kicker">${escapeHtml(humanizeKey(group.mode))}</p>
              <h3>${escapeHtml(humanizeKey(group.mode))}</h3>
              <p class="table-note">${group.rows.length} ${group.rows.length === 1 ? "workstream" : "workstreams"}</p>
            </div>
            <div class="workstream-list">
              ${group.rows
                .map(
                  (row) => `<article class="workstream-item">
                    <div>
                      <strong>${escapeHtml(humanizeKey(row.workstream_key, WORKSTREAM_LABELS))}</strong>
                      <p>${escapeHtml(row.summary_note || "")}</p>
                    </div>
                    <div class="workstream-meta">
                      <span>${escapeHtml(BLOCKER_LABELS[row.binding_blocker] || humanizeKey(row.binding_blocker || "none"))}</span>
                      <p>${escapeHtml(row.next_finite_push || "")}</p>
                    </div>
                  </article>`,
                )
                .join("")}
            </div>
          </section>`,
        )
        .join("")}
    </div>
  `;
}

function renderFooter(bundle) {
  document.querySelector("#site-footer-note").textContent =
    "Public estimator ladder for Treasury-attributed deposit effects, with bounded receipt and diagnostic branches kept explicit.";
  document.querySelector("#site-footer-meta").innerHTML = `
    <a class="footer-link" href="${REPO_URL}" target="_blank" rel="noreferrer">Repository</a>
    <a class="footer-link" href="./data/bundle.json" target="_blank" rel="noreferrer">Data bundle</a>
    <a class="footer-link" href="${REPO_URL}/blob/main/LICENSE" target="_blank" rel="noreferrer">License</a>
    <span class="footer-pill">Built ${formatUtcDate(bundle.metadata?.generated_at_utc || bundle.generated_at_utc)}</span>
    <span class="footer-pill">${AUTHOR_NAME}</span>
    <span class="footer-pill">${LICENSE_NAME}</span>
    <span class="footer-pill">Latest period ${bundle.summary.latest_period || "n/a"}</span>
  `;
}

async function loadBundle() {
  const primary = await fetch("./data/bundle.json");
  if (primary.ok) return primary.json();
  const fallback = await fetch("./bundle.json");
  if (!fallback.ok) throw new Error("Could not load bundle.json");
  return fallback.json();
}

loadBundle()
  .then((bundle) => {
    renderHero(bundle);
    renderSignalBand(bundle);
    renderTheorySection(bundle);
    renderMethodExplorer(bundle);
    renderComponentExplorer(bundle);
    renderReceiptSection(bundle);
    renderFiscalSection(bundle);
    renderMonetarySection(bundle);
    renderWorkstreamSection(bundle);
    renderFooter(bundle);
  })
  .catch((error) => {
    document.body.innerHTML = `<main class="section"><h1>Bundle load failed.</h1><p class="hero-text">${error.message}</p></main>`;
  });

window.addEventListener("tdc-theme-change", () => {
  if (typeof window.__tdcRerenderMethods === "function") {
    window.__tdcRerenderMethods();
  }
});
