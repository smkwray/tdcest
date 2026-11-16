"""Quarterly interest on marketable Treasury debt, split into debt and rate effects and by holder.

Interest is the official component pool of the Tier 2 interest allocation: accrued coupon
interest on notes, bonds and TIPS, bill discount amortization and FRN interest, taken once per
component family. Each family-quarter pool is reconciled to the FiscalData lines of the same
family. Debt is month-end MSPD Table 3 Total Marketable less the Federal Financing Bank,
averaged over the quarter's four month-ends with the two ends at half weight. The effective
rate is annualized on calendar days. The counterfactual keeps average debt on its log-linear
trend over the fit window and the rate at its base-quarter level. The holder split assigns
the Fed its exact component amounts, foreign holders and banks with credit unions their
allocated amounts, and deposit users the residual, then decomposes each holder's interest
above trend into a base-share part and a share shift. Sample, fit window, base quarter,
families and holders are defined once in the catalog.
"""

from __future__ import annotations

import io
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
from .treasury_interest_components import (
    _component_family,
    _component_key,
    _is_marketable_treasury_public_issue,
)

SCHEMA_VERSION = "interest_rate_debt_q_v1"
INTEREST_KEY, DEBT_KEY = "interest_expense", "mspd_marketable"
ALLOCATION_FILE = "tier2_interest_component_candidate.csv"
OUTPUT_FILES = {
    "aggregate": "interest_rate_debt_q_v1.csv",
    "holders": "interest_rate_debt_holders_q_v1.csv",
    "receipt": "interest_rate_debt_q_v1_receipt.json",
}
INTEREST_COLUMNS = ["record_date", "expense_catg_desc", "expense_group_desc", "expense_type_desc",
                    "month_expense_amt"]
DEBT_COLUMNS = ["record_date", "security_class1_desc", "security_class2_desc", "outstanding_amt"]
POOL, FED, ALLOCATION_POOL = "official_component_pool_mil", "fed_exact_component_mil", "allocation_pool_mil"
MID, LOW, HIGH = ("component_anchored_interest_mil", "component_anchored_interest_low_mil",
                  "component_anchored_interest_high_mil")
ALLOCATION_COLUMNS = ["date", "sector_group", "component_family", POOL, FED, ALLOCATION_POOL, MID, LOW, HIGH]
MARKETABLE_TOTAL, FFB = "Total Marketable", "Federal Financing Bank"
CUSIP = r"[0-9A-Z]{9}"
IDENTITY_TOLERANCE = 1e-9
BOUNDARIES = [
    "Descriptive accounting split of interest into debt and rate effects; no causal claim",
    "Interest is gross: it includes interest paid on marketable debt held by the Federal Reserve",
    "Interest is the official component pool: accrued coupon interest on notes, bonds and TIPS, bill discount "
    "amortization and FRN interest. It excludes TIPS inflation compensation and the amortized discount and premium "
    "on notes, bonds, TIPS and FRNs",
    "The effective rate is annualized quarterly interest over average outstanding marketable debt, not a market yield",
    "The counterfactual holds debt on its fit-window trend and the rate at its base-quarter level; it is not a "
    "forecast of either",
    "The holder split is a shift-share accounting of interest received, with holders defined as in the Tier 2 "
    "interest allocation and deposit users as the residual. Interest to deposit users is the part credited to "
    "covered deposits",
    "The allocation to foreign holders, banks and credit unions is modeled; the Fed's is exact. Where a "
    "family-quarter has no exact Fed amount, the Fed's weighted share stays in the deposit-user residual",
]


def _require(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{label}: missing columns {missing}")


def _strip(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return frame[columns].astype(str).apply(lambda column: column.str.strip())


def fiscaldata_families(frame: pd.DataFrame, quarters: pd.PeriodIndex) -> pd.DataFrame:
    """Marketable FiscalData interest by component family and quarter, USD million.

    Every month of every quarter must carry every marketable line seen in the window.
    """
    _require(frame, INTEREST_COLUMNS, INTEREST_KEY)
    text = _strip(frame, INTEREST_COLUMNS)
    month = pd.to_datetime(text["record_date"], format="%Y-%m-%d", errors="raise").dt.to_period("M")
    months = pd.period_range(quarters[0].asfreq("M", "start"), quarters[-1].asfreq("M", "end"), freq="M")
    keep = np.array([_is_marketable_treasury_public_issue(c, t)
                     for c, t in zip(text["expense_catg_desc"], text["expense_type_desc"], strict=True)], dtype=bool)
    rows = text[keep & month.isin(months).to_numpy()].assign(month=month)
    line = ["expense_group_desc", "expense_type_desc"]
    if rows.duplicated(["month", *line]).any():
        raise ValueError(f"{INTEREST_KEY}: duplicate marketable lines within a month")
    n_lines = len(rows[line].drop_duplicates())
    present = rows.groupby("month").size().reindex(months, fill_value=0)
    short = present.index[present.eq(0) | present.lt(n_lines)]
    if len(short):
        raise ValueError(f"{INTEREST_KEY}: months {[str(m) for m in short[:5]]} lack marketable lines; "
                         "a quarter needs all three months")
    family = [_component_family(_component_key(g, t))
              for g, t in zip(rows["expense_group_desc"], rows["expense_type_desc"], strict=True)]
    amount = _numeric(rows["month_expense_amt"], INTEREST_KEY) / 1e6
    quarter = pd.PeriodIndex(rows["month"]).asfreq("Q")
    return amount.groupby([quarter, family]).sum().unstack(fill_value=0.0).reindex(quarters)


def month_end_marketable_debt(frame: pd.DataFrame, months: pd.PeriodIndex) -> tuple[pd.Series, dict]:
    """Total Marketable less the Federal Financing Bank at each month-end, USD million.

    The embedded totals are cross-checked against the class subtotals. A class's subtotal is
    the largest of its non-CUSIP rows, because the Matured and Unmatured subtotals are
    nonnegative parts of the class total and its label varies across months.
    """
    _require(frame, DEBT_COLUMNS, DEBT_KEY)
    text = _strip(frame, DEBT_COLUMNS)
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
    gap = (debt - classes.reindex(months)).abs()
    worst = gap.idxmax() if gap.notna().all() else gap.index[gap.isna()][0]
    if not gap.notna().all() or gap[worst] > catalog.MSPD_SUBTOTAL_TOLERANCE_USD_MILLION:
        raise ValueError(f"{DEBT_KEY}: {MARKETABLE_TOTAL} less {FFB} differs from the class subtotals by "
                         f"{gap[worst]} USD million in {worst}")
    check = {"tolerance_usd_million": catalog.MSPD_SUBTOTAL_TOLERANCE_USD_MILLION,
             "max_abs_gap_usd_million": float(gap[worst]), "month": str(worst)}
    return debt, check


def quarter_average_debt(debt: pd.Series, quarters: pd.PeriodIndex) -> pd.Series:
    """Mean of the prior quarter-end and the quarter's three month-ends, ends at half weight, USD billion."""
    weights = np.array([0.5, 1.0, 1.0, 0.5]) / 3
    return pd.Series([float(weights @ debt.loc[q.asfreq("M", "start") - 1:q.asfreq("M", "end")].to_numpy()) / 1000
                      for q in quarters], index=quarters)


def holder_interest(allocation: pd.DataFrame, quarters: pd.PeriodIndex) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Holder interest with bounds (USD billion, quarter x holder), pools by family (USD million), and a record."""
    _require(allocation, ALLOCATION_COLUMNS, "interest allocation")
    families = list(catalog.INTEREST_POOL_FAMILIES)
    groups = sorted({group for sector_groups in catalog.INTEREST_ALLOCATED_HOLDERS.values() for group in sector_groups})
    frame = allocation[ALLOCATION_COLUMNS].copy()
    dates = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise")
    frame["quarter"] = pd.PeriodIndex(dates, freq="Q")
    if not dates.eq(frame["quarter"].dt.end_time.dt.normalize()).all():
        raise ValueError("interest allocation: dates must be quarter-ends")
    frame = frame[frame["quarter"].isin(quarters) & frame["component_family"].isin(families)
                  & frame["sector_group"].isin(groups)]
    key = ["quarter", "component_family", "sector_group"]
    if frame.duplicated(key).any():
        raise ValueError("interest allocation: duplicate quarter, family and sector rows")
    expected = pd.MultiIndex.from_product([quarters, families, groups], names=key)
    missing = expected.difference(pd.MultiIndex.from_frame(frame[key]))
    if len(missing):
        raise ValueError(f"interest allocation: missing rows {[tuple(map(str, m)) for m in missing[:3]]}")
    for column in [POOL, ALLOCATION_POOL, MID, LOW, HIGH]:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if not np.isfinite(frame[column]).all():
            raise ValueError(f"interest allocation: missing or nonfinite {column}")
    frame[FED] = pd.to_numeric(frame[FED], errors="raise")
    if not ((frame[LOW] <= frame[MID]) & (frame[MID] <= frame[HIGH])).all():
        raise ValueError("interest allocation: allocated interest outside its bounds")

    family = frame.groupby(["quarter", "component_family"])
    if (family[[POOL, ALLOCATION_POOL]].nunique() > 1).any().any() or (family[FED].nunique(dropna=False) > 1).any():
        raise ValueError("interest allocation: pool or Fed amount differs across sectors of one family-quarter")
    pools = family[[POOL, FED, ALLOCATION_POOL]].first()
    # A missing exact Fed amount is accepted only where the producer kept the whole pool for allocation.
    absent = pools[FED].isna()
    tolerance = catalog.INTEREST_POOL_TOLERANCE_USD_MILLION
    if (pools.loc[absent, ALLOCATION_POOL] - pools.loc[absent, POOL]).abs().gt(tolerance).any():
        raise ValueError("interest allocation: no exact Fed amount but the allocation pool is not the whole pool")
    present = pools[~absent]
    if (present[ALLOCATION_POOL] - (present[POOL] - present[FED])).abs().gt(tolerance).any():
        raise ValueError("interest allocation: allocation pool differs from the pool less the Fed's exact amount")
    fed_absent = [{"component_family": name, "quarters": int(len(block)), "first": str(block.min()),
                   "last": str(block.max())}
                  for name, block in pools[absent].reset_index().groupby("component_family")["quarter"]]

    pool = pools[POOL].groupby(level="quarter").sum() / 1000
    fed = pools[FED].fillna(0.0).groupby(level="quarter").sum() / 1000
    sums = frame.groupby(["sector_group", "quarter"])[[MID, LOW, HIGH]].sum() / 1000
    names = ["interest", "interest_low", "interest_high"]
    holders = {holder: sum(sums.loc[group] for group in sector_groups).set_axis(names, axis=1)
               for holder, sector_groups in catalog.INTEREST_ALLOCATED_HOLDERS.items()}
    others = sum(holders.values())
    available = pool - fed
    holders["fed"] = pd.DataFrame({"interest": fed, "interest_low": fed, "interest_high": fed})
    holders["deposit_users"] = pd.DataFrame({"interest": available - others["interest"],
                                             "interest_low": available - others["interest_high"],
                                             "interest_high": available - others["interest_low"]})
    negative = holders["deposit_users"]["interest"] < 0
    if negative.any():
        raise ValueError(f"interest allocation: allocated and Fed interest exceed the pool in "
                         f"{[str(q) for q in negative.index[negative][:5]]}")
    table = pd.concat([holders[holder].reindex(quarters).assign(holder=holder)
                       for holder in catalog.INTEREST_HOLDERS])
    table = table.rename_axis("quarter").reset_index()
    order = {holder: n for n, holder in enumerate(catalog.INTEREST_HOLDERS)}
    table = table.sort_values(["quarter", "holder"], key=lambda c: c.map(order) if c.name == "holder" else c,
                              kind="stable").reset_index(drop=True)
    return table[["quarter", "holder", *names]], pools[POOL].unstack().reindex(quarters), {"fed_exact_absent":
                                                                                            fed_absent}


def build_interest_rate_debt(
    interest: pd.DataFrame, mspd: pd.DataFrame, allocation: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """The aggregate and holder tables and their fit, base, reconciliation and check record."""
    first, last = (pd.Period(q, "Q") for q in catalog.INTEREST_RATE_DEBT_SAMPLE)
    fit_first, fit_last = (pd.Period(q, "Q") for q in catalog.INTEREST_RATE_DEBT_FIT_WINDOW)
    base = pd.Period(catalog.INTEREST_RATE_DEBT_BASE_QUARTER, "Q")
    if not (first <= fit_first < fit_last <= last and first <= base <= last):
        raise ValueError("fit window and base quarter must lie inside the sample")
    quarters = pd.period_range(first, last, freq="Q")
    holders, family_pools, holder_record = holder_interest(allocation, quarters)
    fiscal = fiscaldata_families(interest, quarters)
    families = list(catalog.INTEREST_POOL_FAMILIES)
    missing = sorted(set(families) - set(fiscal.columns))
    if missing:
        raise ValueError(f"{INTEREST_KEY}: no lines for families {missing}")
    family_gap = (family_pools[families] - fiscal[families]).abs()
    if family_gap.max().max() > catalog.INTEREST_POOL_TOLERANCE_USD_MILLION:
        q, name = family_gap.stack().idxmax()
        raise ValueError(f"interest allocation pool differs from FiscalData {name} by {family_gap.loc[q, name]} "
                         f"USD million in {q}")
    ex_tips_ic = fiscal.drop(columns="tips_inflation_compensation", errors="ignore").sum(axis=1) / 1000
    monthly, debt_check = month_end_marketable_debt(
        mspd, pd.period_range(first.asfreq("M", "start") - 1, last.asfreq("M", "end"), freq="M"))

    I_q = family_pools[families].sum(axis=1) / 1000
    D = quarter_average_debt(monthly, quarters)
    days = pd.Series((quarters.end_time.normalize() - quarters.start_time).days + 1, index=quarters)
    year = days / 365
    r = I_q / (D * year)
    position = pd.Series([(q - base).n for q in quarters], index=quarters, dtype=float)
    fit = (quarters >= fit_first) & (quarters <= fit_last)
    g = float(np.polyfit(position[fit].to_numpy(), np.log(D[fit].to_numpy()), 1)[0])
    rc = float(r[base])
    after = pd.Series(quarters >= base, index=quarters)
    Dc = (D[base] * np.exp(g * position)).where(after)
    trend = Dc * rc * year
    debt_only = (D * rc * year).where(after)
    aggregate = pd.DataFrame({
        "quarter": quarters.astype(str), "days": days, "interest": I_q, "avg_marketable_debt": D,
        "effective_rate_pct": 100 * r, "trend_debt": Dc, "trend_interest": trend, "debt_only_interest": debt_only,
        "debt_effect": debt_only - trend, "rate_effect": I_q - debt_only,
        "debt_effect_even": (D - Dc) * (r + rc) / 2 * year, "rate_effect_even": (r - rc) * (D + Dc) / 2 * year,
        "fiscaldata_interest_ex_tips_ic": ex_tips_ic, "pool_minus_fiscaldata": I_q - ex_tips_ic,
    }, index=quarters)

    total = holders["quarter"].map(I_q).to_numpy()
    share = holders["interest"].to_numpy() / total
    base_share = pd.Series(share[(holders["quarter"] == base).to_numpy()],
                           index=holders.loc[holders["quarter"] == base, "holder"])
    theta_b = holders["holder"].map(base_share).to_numpy()
    trend_q = holders["quarter"].map(trend).to_numpy()
    long = holders.assign(share=share, trend_interest=theta_b * trend_q,
                          base_share_part=theta_b * (total - trend_q), shift=total * (share - theta_b))
    is_after = (holders["quarter"] >= base).to_numpy()
    long.loc[~is_after, ["trend_interest", "base_share_part", "shift"]] = np.nan

    span, post = aggregate[after], long[is_after]
    identities = {
        "debt_effect + rate_effect = interest - trend_interest":
            span.debt_effect + span.rate_effect - (span.interest - span.trend_interest),
        "debt_effect_even + rate_effect_even = interest - trend_interest":
            span.debt_effect_even + span.rate_effect_even - (span.interest - span.trend_interest),
        "holder interest - holder trend_interest = base_share_part + shift":
            post["interest"] - post["trend_interest"] - post["base_share_part"] - post["shift"],
        "sum over holders of shift = 0": post.groupby("quarter")["shift"].sum(),
        "sum over holders of interest = interest": long.groupby("quarter")["interest"].sum() - I_q,
    }
    checks = {}
    for name, gap in identities.items():
        worst = float(gap.abs().max())
        if not worst <= IDENTITY_TOLERANCE:
            raise ValueError(f"identity fails by {worst}: {name}")
        checks[name] = {"tolerance": IDENTITY_TOLERANCE, "max_abs_gap_usd_billion": worst}
    long["quarter"] = long["quarter"].astype(str)
    gaps = aggregate["pool_minus_fiscaldata"]
    record = {
        "sample": {"first_quarter": str(first), "last_quarter": str(last), "n": len(quarters)},
        "counterfactual": {
            "fit_window": [str(fit_first), str(fit_last)], "base_quarter": str(base),
            "g": g, "g_definition": "OLS slope of ln avg_marketable_debt on the quarter index over the fit window, "
                                    "per quarter",
            "trend_growth_pct_per_year": float(100 * (np.exp(4 * g) - 1)),
            "rc": rc, "rc_pct": 100 * rc, "rc_definition": "annualized effective rate in the base quarter",
            "base_shares": {holder: float(base_share[holder]) for holder in catalog.INTEREST_HOLDERS},
        },
        "holders": {
            "fed": "Exact Fed component amounts summed over the pool families",
            **{holder: f"Allocated interest of sector groups {list(groups)}, with its low and high bounds"
               for holder, groups in catalog.INTEREST_ALLOCATED_HOLDERS.items()},
            "deposit_users": "Pool less the Fed and the allocated holders; low and high bounds use the allocated "
                             "holders' high and low bounds",
            **holder_record,
        },
        "reconciliation": {
            "family_pool_vs_fiscaldata": {
                "families": families, "tolerance_usd_million": catalog.INTEREST_POOL_TOLERANCE_USD_MILLION,
                "max_abs_gap_usd_million": float(family_gap.max().max())},
            "pool_minus_fiscaldata_ex_tips_ic_usd_billion": {
                "explained_by": "amortized discount net of premium on notes, bonds, TIPS and FRNs, outside the pool",
                "min": float(gaps.min()), "max": float(gaps.max()),
                "by_quarter": {str(q): float(v) for q, v in gaps.items()}},
        },
        "checks": {"identities": checks, "mspd_subtotals": debt_check},
    }
    return aggregate.reset_index(drop=True), long, record


def column_metadata() -> dict:
    base = catalog.INTEREST_RATE_DEBT_BASE_QUARTER
    fit = "{}-{}".format(*catalog.INTEREST_RATE_DEBT_FIT_WINDOW)
    blank = f"; blank before {base}"
    aggregate = {
        "quarter": "Calendar quarter",
        "days": "Calendar days in the quarter",
        "interest": "I: official pool interest summed once over the component families "
                    f"{list(catalog.INTEREST_POOL_FAMILIES)}, USD billion",
        "avg_marketable_debt": "D: (v0/2 + v1 + v2 + v3/2)/3 over the prior quarter-end and the quarter's month-ends "
                               "of MSPD Total Marketable less the Federal Financing Bank, USD billion",
        "effective_rate_pct": "r = I / (D * days / 365), percent per year",
        "trend_debt": f"Dc = D_{base} * exp(g * quarters since {base}), g the {fit} log-linear trend{blank}",
        "trend_interest": f"Dc * rc * days / 365, rc = r_{base}{blank}",
        "debt_only_interest": f"D * rc * days / 365{blank}",
        "debt_effect": f"debt_only_interest - trend_interest{blank}",
        "rate_effect": f"I - debt_only_interest{blank}",
        "debt_effect_even": f"(D - Dc) * (r + rc) / 2 * days / 365{blank}",
        "rate_effect_even": f"(r - rc) * (D + Dc) / 2 * days / 365{blank}",
        "fiscaldata_interest_ex_tips_ic": "FiscalData marketable interest lines less TIPS inflation compensation, "
                                          "USD billion",
        "pool_minus_fiscaldata": "interest - fiscaldata_interest_ex_tips_ic: minus the amortized discount net of "
                                 "premium on notes, bonds, TIPS and FRNs",
    }
    holders = {
        "quarter": "Calendar quarter",
        "holder": f"One of {list(catalog.INTEREST_HOLDERS)}",
        "interest": "I_g: holder interest, USD billion",
        "interest_low": "Low bound of I_g",
        "interest_high": "High bound of I_g",
        "share": "theta_g = I_g / I",
        "trend_interest": f"theta_g,{base} * trend_interest{blank}",
        "base_share_part": f"theta_g,{base} * (I - trend_interest){blank}",
        "shift": f"I * (theta_g - theta_g,{base}){blank}",
    }
    return {"aggregate": aggregate, "holders": holders}


def write_interest_rate_debt_export(*, root: Path | str, inputs_manifest_sha256: str, allocation_sha256: str) -> dict:
    """Bind the tables to a clean commit, the pinned allocation and the pinned fiscus manifest."""
    registry = catalog.FISCUS_REGISTRIES["interest-rate-debt"]
    paths = project_paths(root)
    root = paths.root
    producer_commit = require_clean_commit(root)
    allocation_path, manifest_path = paths.processed / ALLOCATION_FILE, root / registry.manifest
    allocation_raw, allocation_record = read_pinned_input(root, allocation_path, allocation_sha256,
                                                          "interest_allocation")
    manifest_raw, manifest_record = read_pinned_input(root, manifest_path, inputs_manifest_sha256, "inputs_manifest")
    manifest = json.loads(manifest_raw)
    frames, input_records = load_fiscus_inputs(root, manifest, registry)

    aggregate, holders, record = build_interest_rate_debt(
        frames[INTEREST_KEY], frames[DEBT_KEY], pd.read_csv(io.BytesIO(allocation_raw)))
    payloads = {role: frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
                for role, frame in [("aggregate", aggregate), ("holders", holders)]}
    output_paths = {role: paths.processed / name for role, name in OUTPUT_FILES.items()}
    protected = {allocation_path.resolve(), manifest_path.resolve()}
    if {path.resolve() for path in output_paths.values()} & protected:
        raise ValueError("Output paths cannot overwrite inputs")
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "producer_commit": producer_commit,
        "units": {"amounts": "USD billion", "effective_rate_pct": "percent per year", "share": "fraction"},
        **record,
        "boundaries": BOUNDARIES,
        "inputs": {"interest_allocation": allocation_record,
                   "inputs_manifest": {**manifest_record, "fiscus": manifest.get("fiscus", {}),
                                       "acquired_at_utc": manifest.get("acquired_at_utc")},
                   "fiscus_inputs": input_records},
        "outputs": {role: {"path": str(output_paths[role].relative_to(root)), "sha256": _sha256(data),
                           "byte_count": len(data)} for role, data in payloads.items()},
        "columns": column_metadata(),
    }
    text = json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    for role, data in payloads.items():
        output_paths[role].parent.mkdir(parents=True, exist_ok=True)
        output_paths[role].write_bytes(data)
    output_paths["receipt"].write_text(text, encoding="utf-8")
    return receipt
