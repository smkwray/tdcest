"""Interest on marketable Treasury debt by fiscal year, split into debt and rate effects.

Interest is the fiscal-year sum of the FiscalData interest-expense lines that
``treasury_interest_components`` classifies as marketable public issues: bills, notes,
bonds, FRNs and TIPS, including amortized discount, amortized premium (negative) and TIPS
inflation compensation. Debt is month-end MSPD Table 3 Total Marketable less the Federal
Financing Bank, averaged over the thirteen month-ends of the fiscal year with the two end
months at half weight. The counterfactual keeps average debt on its log-linear trend over
the fit window and the effective rate at its base-year level; sample, fit window and base
year are defined once in the catalog.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import catalog
from .config import project_paths
from .reserve_factor_ledger import _sha256
from .tier2_regression_series import read_pinned_input, require_clean_commit
from .trc_export import load_fiscus_inputs
from .trc_reserve_component import _numeric
from .treasury_interest_components import _component_key, _is_marketable_treasury_public_issue

SCHEMA_VERSION = "interest_rate_debt_fy_v1"
INTEREST_KEY, DEBT_KEY = "interest_expense", "mspd_marketable"
OUTPUT_FILES = {"table": "interest_rate_debt_fy_v1.csv", "receipt": "interest_rate_debt_fy_v1_receipt.json"}
INTEREST_COLUMNS = ["record_date", "expense_catg_desc", "expense_group_desc", "expense_type_desc",
                    "month_expense_amt"]
DEBT_COLUMNS = ["record_date", "security_class1_desc", "security_class2_desc", "outstanding_amt"]
MARKETABLE_TOTAL, FFB = "Total Marketable", "Federal Financing Bank"
CUSIP = r"[0-9A-Z]{9}"
IDENTITY_TOLERANCE = 1e-9
BOUNDARIES = [
    "Descriptive accounting split of interest into debt and rate effects; no causal claim",
    "Interest is gross: it includes interest paid on marketable debt held by the Federal Reserve",
    "The effective rate is fiscal-year interest over average outstanding marketable debt, not a market yield",
    "The counterfactual holds debt on its fit-window trend and the rate at its base-year level; it is not a "
    "forecast of either",
]


def _require(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{label}: missing columns {missing}")


def _fiscal_year(months: pd.PeriodIndex | pd.Series) -> np.ndarray:
    months = pd.PeriodIndex(months)
    return np.asarray(months.year + (months.month >= 10).astype(int))


def fiscal_year_interest(frame: pd.DataFrame, years: range) -> tuple[pd.DataFrame, list[list[str]]]:
    """Marketable interest and its TIPS inflation-compensation part by fiscal year, USD billion.

    Every month of every fiscal year must carry every marketable line seen in the window; the
    included (group, type) lines are returned with the table.
    """
    _require(frame, INTEREST_COLUMNS, INTEREST_KEY)
    text = frame[INTEREST_COLUMNS].astype(str).apply(lambda column: column.str.strip())
    month = pd.to_datetime(text["record_date"], format="%Y-%m-%d", errors="raise").dt.to_period("M")
    months = pd.period_range(f"{years[0] - 1}-10", f"{years[-1]}-09", freq="M")
    keep = [_is_marketable_treasury_public_issue(c, t)
            for c, t in zip(text["expense_catg_desc"], text["expense_type_desc"], strict=True)]
    rows = text[np.asarray(keep, dtype=bool) & month.isin(months).to_numpy()].assign(month=month)
    line = ["expense_group_desc", "expense_type_desc"]
    if rows.duplicated(["month", *line]).any():
        raise ValueError(f"{INTEREST_KEY}: duplicate marketable lines within a month")
    lines = rows[line].drop_duplicates()
    present = rows.groupby("month").size().reindex(months, fill_value=0)
    short = present.index[present.eq(0) | present.lt(len(lines))]
    if len(short):
        raise ValueError(f"{INTEREST_KEY}: months {[str(m) for m in short[:5]]} lack marketable lines; "
                         f"a fiscal year needs all 12 months")
    amount = _numeric(rows["month_expense_amt"], INTEREST_KEY) / 1e9
    tips = np.array([_component_key(g, t) == "tips_inflation_compensation"
                     for g, t in zip(rows["expense_group_desc"], rows["expense_type_desc"], strict=True)], dtype=bool)
    fy = _fiscal_year(rows["month"])
    out = pd.DataFrame({"interest": amount.groupby(fy).sum(),
                        "tips_inflation_compensation": amount.where(tips, 0.0).groupby(fy).sum()})
    return out.loc[list(years)], sorted(map(list, lines.itertuples(index=False)))


def month_end_marketable_debt(frame: pd.DataFrame, months: pd.PeriodIndex) -> tuple[pd.Series, dict]:
    """Total Marketable less the Federal Financing Bank at each month-end, USD million.

    The embedded totals are cross-checked against the class subtotals. A class's subtotal is
    the largest of its non-CUSIP rows, because the Matured and Unmatured subtotals are
    nonnegative parts of the class total and its label varies across months.
    """
    _require(frame, DEBT_COLUMNS, DEBT_KEY)
    text = frame[DEBT_COLUMNS].astype(str).apply(lambda column: column.str.strip())
    dates = pd.to_datetime(text["record_date"], format="%Y-%m-%d", errors="raise")
    if not dates.dt.is_month_end.all():
        raise ValueError(f"{DEBT_KEY}: record dates must be month-ends")
    month = dates.dt.to_period("M")

    def single(label: str) -> pd.Series:
        rows = text["security_class1_desc"].eq(label)
        if month[rows].duplicated().any():
            raise ValueError(f"{DEBT_KEY}: more than one {label} row in a month")
        return pd.Series(_numeric(text.loc[rows, "outstanding_amt"], f"{DEBT_KEY} {label}").to_numpy(),
                         index=month[rows])

    total, ffb = single(MARKETABLE_TOTAL), single(FFB)
    missing = months.difference(total.index.intersection(ffb.index))
    if len(missing):
        raise ValueError(f"{DEBT_KEY}: month-ends {[str(m) for m in missing[:5]]} lack {MARKETABLE_TOTAL} or {FFB}")
    debt = (total - ffb).loc[months]

    sub = text[~text["security_class1_desc"].isin([MARKETABLE_TOTAL, FFB])
               & ~text["security_class2_desc"].str.fullmatch(CUSIP) & month.isin(months)]
    sub = sub[sub["outstanding_amt"] != "*"]  # the published placeholder for an empty matured-bill subtotal
    values = _numeric(sub["outstanding_amt"], f"{DEBT_KEY} subtotals")
    classes = values.groupby([month[sub.index], sub["security_class1_desc"]]).max().groupby(level=0).sum()
    gap = (total.loc[months] - ffb.loc[months] - classes.reindex(months)).abs()
    worst = gap.idxmax() if gap.notna().all() else gap.index[gap.isna()][0]
    if not gap.notna().all() or gap[worst] > catalog.MSPD_SUBTOTAL_TOLERANCE_USD_MILLION:
        raise ValueError(f"{DEBT_KEY}: {MARKETABLE_TOTAL} less {FFB} differs from the class subtotals by "
                         f"{gap[worst]} USD million in {worst}")
    check = {"tolerance_usd_million": catalog.MSPD_SUBTOTAL_TOLERANCE_USD_MILLION,
             "max_abs_gap_usd_million": float(gap[worst]), "month": str(worst)}
    return debt, check


def fiscal_year_average_debt(debt: pd.Series, years: range) -> pd.Series:
    """Average of the 13 month-ends September y-1 through September y, ends at half weight, USD billion."""
    weights = np.r_[0.5, np.ones(11), 0.5] / 12
    return pd.Series({year: float(weights @ debt.loc[pd.Period(f"{year - 1}-09", "M"):pd.Period(f"{year}-09", "M")]
                                  .to_numpy()) / 1000 for year in years})


def build_interest_rate_debt(interest: pd.DataFrame, mspd: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """The fiscal-year table and its fit, base-rate and check record."""
    first, last = catalog.INTEREST_RATE_DEBT_SAMPLE
    fit_first, fit_last = catalog.INTEREST_RATE_DEBT_FIT_WINDOW
    base = catalog.INTEREST_RATE_DEBT_BASE_YEAR
    if not (first <= fit_first < fit_last <= last and first <= base <= last):
        raise ValueError("fit window and base year must lie inside the sample")
    years = range(first, last + 1)
    flows, lines = fiscal_year_interest(interest, years)
    monthly, debt_check = month_end_marketable_debt(
        mspd, pd.period_range(f"{first - 1}-09", f"{last}-09", freq="M"))
    D = fiscal_year_average_debt(monthly, years)
    I_y, IC = flows["interest"], flows["tips_inflation_compensation"]
    r, ric = I_y / D, IC / D

    fit = list(range(fit_first, fit_last + 1))
    g = float(np.polyfit(np.array(fit, dtype=float), np.log(D.loc[fit].to_numpy()), 1)[0])
    rc, ricc = float(r[base]), float(ric[base])
    pooled = float(I_y.loc[fit].sum() / D.loc[fit].sum())
    index = pd.Index(list(years))
    after = pd.Series(index >= base, index=index)
    Dc = pd.Series(D[base] * np.exp(g * (index - base)), index=index).where(after)
    table = pd.DataFrame({
        "fiscal_year": index,
        "interest": I_y, "tips_inflation_compensation": IC, "avg_marketable_debt": D, "effective_rate_pct": 100 * r,
        "trend_debt": Dc, "trend_interest": Dc * rc, "debt_only_interest": (D * rc).where(after),
        "debt_effect": (D - Dc) * rc, "rate_effect": (I_y - D * rc).where(after),
        "debt_effect_even": (D - Dc) * (r + rc) / 2, "rate_effect_even": (r - rc) * (D + Dc) / 2,
        "rate_effect_tips": (IC - D * ricc).where(after),
        "debt_effect_avg_rate": (D - Dc) * pooled, "rate_effect_avg_rate": (I_y - D * pooled).where(after),
    }, index=index)

    span = table[after]
    identities = {
        "debt_effect + rate_effect = interest - trend_interest":
            span.debt_effect + span.rate_effect - (span.interest - span.trend_interest),
        "debt_effect_even + rate_effect_even = interest - trend_interest":
            span.debt_effect_even + span.rate_effect_even - (span.interest - span.trend_interest),
        "debt_effect_avg_rate + rate_effect_avg_rate = interest - trend_debt * pooled_rate":
            span.debt_effect_avg_rate + span.rate_effect_avg_rate - (span.interest - span.trend_debt * pooled),
    }
    checks = {}
    for name, gap in identities.items():
        worst = float(gap.abs().max())
        if not worst <= IDENTITY_TOLERANCE:
            raise ValueError(f"identity fails by {worst}: {name}")
        checks[name] = {"tolerance": IDENTITY_TOLERANCE, "max_abs_gap_usd_billion": worst}
    record = {
        "sample": {"first_fiscal_year": first, "last_fiscal_year": last, "n": len(years),
                   "fiscal_year": "October of the prior calendar year through September"},
        "counterfactual": {
            "fit_window": [fit_first, fit_last], "base_year": base,
            "g": g, "g_definition": "OLS slope of ln avg_marketable_debt on fiscal year over the fit window",
            "trend_growth_pct_per_year": 100 * (np.exp(g) - 1),
            "rc": rc, "rc_pct": 100 * rc, "ricc": ricc, "ricc_pct": 100 * ricc,
            "pooled_rate": pooled, "pooled_rate_pct": 100 * pooled,
            "pooled_rate_definition": "sum of fit-window interest over sum of fit-window average debt",
        },
        "interest_lines": lines,
        "checks": {"identities": checks, "mspd_subtotals": debt_check},
    }
    return table.reset_index(drop=True), record


def column_metadata() -> dict:
    base = catalog.INTEREST_RATE_DEBT_BASE_YEAR
    fit = "FY{}-FY{}".format(*catalog.INTEREST_RATE_DEBT_FIT_WINDOW)
    blank = f"; blank before FY{base}"
    return {
        "fiscal_year": "Fiscal year ending in September",
        "interest": "I: fiscal-year sum of marketable interest-expense lines (accrued interest, amortized discount, "
                    "amortized premium, TIPS inflation compensation), USD billion",
        "tips_inflation_compensation": "IC: the TIPS inflation-compensation line of interest, USD billion",
        "avg_marketable_debt": "D: (v0/2 + v1 + ... + v11 + v12/2)/12 over month-ends September y-1 to September y "
                               "of MSPD Total Marketable less the Federal Financing Bank, USD billion",
        "effective_rate_pct": "r = I / D, percent",
        "trend_debt": f"Dc = D_{base} * exp(g * (y - {base})), g the {fit} log-linear trend{blank}",
        "trend_interest": f"Dc * rc, rc = r_{base}{blank}",
        "debt_only_interest": f"D * rc{blank}",
        "debt_effect": f"(D - Dc) * rc{blank}",
        "rate_effect": f"I - D * rc{blank}",
        "debt_effect_even": f"(D - Dc) * (r + rc) / 2{blank}",
        "rate_effect_even": f"(r - rc) * (D + Dc) / 2{blank}",
        "rate_effect_tips": f"IC - D * ricc, ricc = IC_{base} / D_{base}{blank}",
        "debt_effect_avg_rate": f"(D - Dc) * pooled_rate, pooled_rate = sum I / sum D over {fit}{blank}",
        "rate_effect_avg_rate": f"I - D * pooled_rate{blank}",
    }


def write_interest_rate_debt_export(*, root: Path | str, inputs_manifest_sha256: str) -> dict:
    """Bind the table to a clean commit and the pinned fiscus manifest."""
    registry = catalog.FISCUS_REGISTRIES["interest-rate-debt"]
    paths = project_paths(root)
    root = paths.root
    producer_commit = require_clean_commit(root)
    manifest_path = root / registry.manifest
    manifest_raw, manifest_record = read_pinned_input(root, manifest_path, inputs_manifest_sha256, "inputs_manifest")
    manifest = json.loads(manifest_raw)
    frames, input_records = load_fiscus_inputs(root, manifest, registry)

    table, record = build_interest_rate_debt(frames[INTEREST_KEY], frames[DEBT_KEY])
    payload = table.to_csv(index=False, lineterminator="\n").encode("utf-8")
    output_paths = {role: paths.processed / name for role, name in OUTPUT_FILES.items()}
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "producer_commit": producer_commit,
        "units": {"amounts": "USD billion", "effective_rate_pct": "percent"},
        **record,
        "boundaries": BOUNDARIES,
        "inputs": {"inputs_manifest": {**manifest_record, "fiscus": manifest.get("fiscus", {}),
                                       "acquired_at_utc": manifest.get("acquired_at_utc")},
                   "fiscus_inputs": input_records},
        "outputs": {"table": {"path": str(output_paths["table"].relative_to(root)), "sha256": _sha256(payload),
                              "byte_count": len(payload)}},
        "columns": column_metadata(),
    }
    text = json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    output_paths["table"].parent.mkdir(parents=True, exist_ok=True)
    output_paths["table"].write_bytes(payload)
    output_paths["receipt"].write_text(text, encoding="utf-8")
    return receipt
