"""Treasury component of reserves (TRC): pure quarterly construction from frames.

TRC applies reserve-balance incidence to the Treasury events behind TDC. The
measured bridge, in USD million on the Z.1 calendar quarter, is

    core      = -dTGA - dSFP + fed_tsy_tx + fed_remit_positive - fed_tsy_coupon_interest_proxy
    preferred = core + MMF/ON RRP route adjustment (proportional; lower/upper companions)

Treasury Tax and Loan balances are commercial-bank claims and stay out of the
cash leg; SFP enters once. The Treasury route assembler is kept apart from the
reserve-factor diagnostics so an H.4.1 factor cannot become a Treasury
classification. Nothing here estimates or identifies a causal effect.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .catalog import BANK_DEPOSITORY_TX_KEYS
from .gse_rrp_boundary import build_gse_rrp_boundary_check
from .mmf_rrp import ON_RRP_OPERATION_START, mmf_on_rrp_route_adjustment
from .settlement_routes import load_settlement_routes
from .tier2_regression_series import LEG_CANONICAL_COLUMN, LEG_QUARTERS

TRC_QUARTERS = LEG_QUARTERS
TGA_SOURCE_TRANSITION = pd.Period("2006Q1", freq="Q")
ON_RRP_MECHANISM_QUARTER = ON_RRP_OPERATION_START.to_period("Q")
SFP_PROGRAM_START = pd.Timestamp("2008-09-17")
MAX_QUARTER_END_GAP_DAYS = 6
LEGS_SOURCE_KEY = "tdc_regression_legs_v1"
QUARTERLY_SOURCE_KEY = "quarterly_inputs"
LEGACY_SOURCE_KEYS = (LEGS_SOURCE_KEY, QUARTERLY_SOURCE_KEY)
LEG_COLUMNS = [
    "quarter", "C", "R", "fed_tsy_tx", *BANK_DEPOSITORY_TX_KEYS, "treasury_operating_cash_tx",
    "fed_remit_positive", "fed_tsy_coupon_interest_proxy", "bank_tier2_regression_interest_proxy",
    "effective_mmf_rrp_adjustment_prop", LEG_CANONICAL_COLUMN,
]
QUARTERLY_COLUMNS = [
    "date", "treasury_operating_cash_tx", "mmf_rrp_adjustment_lb", "mmf_rrp_adjustment_prop",
    "mmf_rrp_adjustment_ub", "gse_tsy_tx", "gse_tsy_level", "gse_on_rrp",
]
PERIOD_WINDOWS = [("2003Q1", "2007Q4"), ("2008Q1", "2014Q4"), ("2015Q1", "2019Q4"), ("2020Q1", "2025Q4")]

# DTS Table I account types, parsed era by era. The 2022-04-18 schema reports
# the TGA closing balance in open_today_bal of the Closing Balance row with
# close_today_bal literally "null". Table V Tax and Loan Note Accounts and their
# Short-Term Cash Investments successor are Treasury cash at commercial banks.
DTS_ACCOUNTS: dict[str, tuple[str, str | None]] = {
    "Federal Reserve Account": ("tga", "close_today_bal"),
    "Treasury General Account (TGA)": ("tga", "close_today_bal"),
    "Treasury General Account (TGA) Closing Balance": ("tga", "open_today_bal"),
    "Supplementary Financing Prog": ("sfp", "close_today_bal"),
    "Supplementary Financing Program": ("sfp", "close_today_bal"),
    "Supplementary Financing Programs": ("sfp", "close_today_bal"),
    "Supplementary Financing Program Account": ("sfp", "close_today_bal"),
    "Tax and Loan Note Accounts (Table V)": ("ttl", "close_today_bal"),
    "Account Tax and Loan Note Accounts (Table V)": ("ttl", "close_today_bal"),
    "Short-Term Cash Investments (Table V)": ("ttl", "close_today_bal"),
    "Account Short-Term Cash Investments (Table V)": ("ttl", "close_today_bal"),
    "Financial Institution Account": ("unclassified_zero_required", "close_today_bal"),
    "Financial Institution Accoun": ("unclassified_zero_required", "close_today_bal"),
    "Treasury General Account (TGA) Opening Balance": ("not_a_closing_balance", None),
    "Total TGA Deposits (Table II)": ("not_a_closing_balance", None),
    "Total TGA Withdrawals (Table II) (-)": ("not_a_closing_balance", None),
}


def _quarter_index(dates: pd.Series) -> pd.PeriodIndex:
    return pd.PeriodIndex(pd.to_datetime(dates, format="%Y-%m-%d", errors="raise"), freq="Q")


def _numeric(values: pd.Series, label: str) -> pd.Series:
    text = values.astype(str).str.strip()
    out = pd.to_numeric(text.where(~text.isin(["", ".", "null", "nan", "NaN"])), errors="coerce")
    if out.isna().any():
        raise ValueError(f"{label}: missing or nonnumeric values at {list(values.index[out.isna()])[:5]}")
    return out


def parse_dts_table_i(dts: pd.DataFrame) -> pd.DataFrame:
    """Daily TGA, SFP, and TT&L closing balances from DTS Table I, era by era.

    Unrecognized account types, duplicate concepts on a day, a non-null close in
    the post-2022 Closing Balance row, or a missing line inside its reporting
    span all raise. Outside a line's reporting span the balance is a structural
    zero only when the program had not begun or its last reported balance was zero.
    """
    required = {"record_date", "account_type", "open_today_bal", "close_today_bal"}
    if required - set(dts.columns):
        raise ValueError(f"DTS Table I: missing columns {sorted(required - set(dts.columns))}")
    frame = dts[list(required)].astype(str)
    unknown = sorted(set(frame["account_type"]) - set(DTS_ACCOUNTS))
    if unknown:
        raise ValueError(f"DTS Table I: unrecognized account types {unknown}")
    dates = pd.to_datetime(frame["record_date"], format="%Y-%m-%d", errors="raise")
    concept = frame["account_type"].map(lambda name: DTS_ACCOUNTS[name][0])
    reads_open = frame["account_type"].map(lambda name: DTS_ACCOUNTS[name][1]).eq("open_today_bal")
    if not frame.loc[reads_open, "close_today_bal"].eq("null").all():
        raise ValueError("DTS Table I: ambiguous TGA closing balance (non-null close in the Closing Balance row)")
    keep = concept.ne("not_a_closing_balance")
    value_text = frame["close_today_bal"].where(~reads_open, frame["open_today_bal"])
    rows = pd.DataFrame({
        "date": dates[keep], "concept": concept[keep],
        "value": _numeric(value_text[keep], "DTS Table I closing balance"),
    })
    counts = rows.groupby(["date", "concept"]).size()
    if counts.gt(1).any():
        raise ValueError(f"DTS Table I: ambiguous duplicate balances on {counts[counts.gt(1)].index[:5].tolist()}")
    wide = rows.pivot(index="date", columns="concept", values="value")
    business_days = pd.DatetimeIndex(sorted(dates.unique()), name="date")
    wide = wide.reindex(business_days)
    out = pd.DataFrame(index=business_days)
    if "tga" not in wide or wide["tga"].isna().any():
        raise ValueError("DTS Table I: a business day lacks exactly one TGA closing balance")
    out["tga"] = wide["tga"]
    for line in ["sfp", "ttl"]:
        series = wide[line] if line in wide else pd.Series(np.nan, index=business_days)
        reported = series.dropna()
        if reported.empty:
            raise ValueError(f"DTS Table I: no {line} balances reported")
        first, last = reported.index.min(), reported.index.max()
        inside = (business_days >= first) & (business_days <= last)
        if series[inside].isna().any():
            raise ValueError(f"DTS Table I: {line} line missing inside its reporting span")
        status = pd.Series("dts_reported", index=business_days)
        if (business_days > last).any() and reported.iloc[-1] != 0:
            raise ValueError(f"DTS Table I: {line} line discontinued with a nonzero balance")
        status[business_days > last] = "structural_zero_line_discontinued"
        if (business_days < first).any():
            if line != "sfp" or not 0 <= (first - SFP_PROGRAM_START).days <= MAX_QUARTER_END_GAP_DAYS:
                raise ValueError(f"DTS Table I: {line} line absent before its first report without a program start")
            status[business_days < first] = "structural_zero_pre_program"
        out[line] = series.where(inside, 0.0)
        out[f"{line}_status"] = status
    unclassified = wide["unclassified_zero_required"] if "unclassified_zero_required" in wide else 0.0
    out["unclassified_balance"] = pd.Series(unclassified, index=business_days).fillna(0.0)
    return out


def dts_quarter_end(daily: pd.DataFrame) -> pd.DataFrame:
    """Final-business-day balances for each quarter fully spanned by the DTS file."""
    dates = pd.Series(daily.index, index=daily.index)
    final = dates.groupby(daily.index.to_period("Q")).max()
    gap = (final.index.end_time.normalize() - pd.DatetimeIndex(final.values)).days
    if (gap > MAX_QUARTER_END_GAP_DAYS).any():
        raise ValueError(f"DTS Table I: quarters without a final business day {list(final.index[gap > MAX_QUARTER_END_GAP_DAYS].astype(str))}")
    out = daily.loc[final.values].copy()
    if out["unclassified_balance"].ne(0).any():
        raise ValueError("DTS Table I: unclassified Treasury account nonzero on a quarter-end business day")
    out["dts_date"] = out.index
    out.index = final.index
    return out


def last_wednesday_levels(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    """Last H.4.1 Wednesday level on or before each quarter end."""
    dates = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise")
    if dates.duplicated().any() or not dates.dt.weekday.eq(2).all():
        raise ValueError(f"{label}: observations must be unique Wednesdays")
    values = pd.Series(_numeric(frame["value"], label).to_numpy(), index=dates).sort_index()
    grouped = values.groupby(values.index.to_period("Q"))
    out = pd.DataFrame({"date": grouped.apply(lambda s: s.index.max()), "level": grouped.last()})
    gap = (out.index.end_time.normalize() - pd.DatetimeIndex(out["date"])).days
    if (gap > MAX_QUARTER_END_GAP_DAYS).any():
        raise ValueError(f"{label}: quarter without a final Wednesday {list(out.index[gap > MAX_QUARTER_END_GAP_DAYS].astype(str))}")
    return out


def z1_quarterly(frame: pd.DataFrame, label: str) -> pd.Series:
    dates = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise")
    if not dates.eq(dates.dt.to_period("Q").dt.end_time.dt.normalize()).all() or dates.duplicated().any():
        raise ValueError(f"{label}: dates must be unique quarter ends")
    return pd.Series(_numeric(frame["value"], label).to_numpy(), index=pd.PeriodIndex(dates, freq="Q"))


def monthly_final_month(frame: pd.DataFrame, label: str) -> pd.Series:
    dates = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise")
    if not dates.dt.day.eq(1).all() or dates.duplicated().any():
        raise ValueError(f"{label}: monthly observations must be unique first-of-month dates")
    values = pd.Series(_numeric(frame["value"], label).to_numpy(), index=dates).sort_index()
    final = values[values.index.month % 3 == 0]
    return pd.Series(final.to_numpy(), index=final.index.to_period("Q"))


def _require_frame(frame: pd.DataFrame, columns: list[str], label: str) -> pd.DataFrame:
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"{label}: missing columns {sorted(missing)}")
    return frame[columns].copy()


def _legs(legs: pd.DataFrame) -> pd.DataFrame:
    frame = _require_frame(legs, LEG_COLUMNS, "regression legs")
    frame.index = pd.PeriodIndex(frame.pop("quarter"), freq="Q")
    if not frame.index.equals(TRC_QUARTERS):
        raise ValueError("regression legs: expected exactly the 2002Q1-2025Q4 quarters")
    frame = frame.apply(pd.to_numeric, errors="raise")
    if not np.isfinite(frame.to_numpy(dtype=float)).all():
        raise ValueError("regression legs: nonfinite required values")
    if (frame["C"] - frame[LEG_CANONICAL_COLUMN]).abs().max() != 0:
        raise ValueError("regression legs: C is not the frozen canonical column")
    return frame


def _quarterly(quarterly: pd.DataFrame) -> pd.DataFrame:
    frame = _require_frame(quarterly, QUARTERLY_COLUMNS, "quarterly inputs")
    frame.index = _quarter_index(frame.pop("date"))
    if frame.index.has_duplicates:
        raise ValueError("quarterly inputs: duplicate quarters")
    frame = frame.apply(pd.to_numeric, errors="raise")
    window = frame.loc[(frame.index >= TRC_QUARTERS[0] - 1) & (frame.index <= TRC_QUARTERS[-1])]
    if not window.index.equals(pd.period_range(TRC_QUARTERS[0] - 1, TRC_QUARTERS[-1], freq="Q")):
        raise ValueError("quarterly inputs: expected every quarter from 2001Q4 to 2025Q4")
    return window


def _difference(levels: pd.Series, quarters: pd.PeriodIndex) -> pd.Series:
    full = levels.reindex(pd.period_range(quarters[0] - 1, quarters[-1], freq="Q"))
    return full.diff().reindex(quarters)


def assemble_treasury_routes(
    *, legs: pd.DataFrame, quarterly: pd.DataFrame, dts_quarter: pd.DataFrame, tga_h41: pd.DataFrame,
) -> pd.DataFrame:
    """Default TRC rows: Treasury Fed-deposit leg, Fed Treasury bridge, MMF route."""
    q = TRC_QUARTERS
    out = pd.DataFrame(index=q)
    dts_first = dts_quarter.index.min()
    if dts_first >= TGA_SOURCE_TRANSITION:
        raise ValueError("DTS Table I must supply the quarter before the TGA source transition")
    h41_level = tga_h41["level"]
    dts_level = dts_quarter["tga"]
    h41_part = _difference(h41_level, q)
    dts_part = _difference(dts_level, q)
    use_dts = q >= TGA_SOURCE_TRANSITION
    out["delta_tga"] = np.where(use_dts, dts_part, h41_part)
    out["tga_level"] = np.where(use_dts, dts_level.reindex(q), h41_level.reindex(q))
    level_dates = pd.to_datetime(dts_quarter["dts_date"]).reindex(q).where(use_dts, pd.to_datetime(tga_h41["date"]).reindex(q))
    out["tga_level_date"] = level_dates.dt.strftime("%Y-%m-%d")
    out["tga_source_key"] = np.where(use_dts, "dts_operating_cash_balance_table_i", "h41_tga_wednesday")
    out["tga_clock"] = np.where(use_dts, "dts_final_business_day", "h41_last_wednesday")
    measured = q >= q[0] + 4
    if out.loc[measured, "delta_tga"].isna().any():
        raise ValueError(f"TGA leg missing in measured quarters {list(q[measured & out['delta_tga'].isna().to_numpy()].astype(str))}")
    if out.loc[~measured, "delta_tga"].notna().any():
        raise ValueError("TGA leg unexpectedly observed before 2003Q1")

    levels = pd.period_range(q[0] - 1, q[-1], freq="Q")
    sfp = pd.Series(0.0, index=levels)
    sfp_status = pd.Series("structural_zero_pre_program", index=levels)
    if (levels[levels < dts_first].end_time >= SFP_PROGRAM_START).any():
        raise ValueError("DTS Table I must cover every quarter from the SFP program start")
    covered = levels[levels >= dts_first]
    sfp[covered] = dts_quarter.loc[covered, "sfp"]
    sfp_status[covered] = dts_quarter.loc[covered, "sfp_status"]
    out["sfp_level"] = sfp.reindex(q)
    out["sfp_status"] = sfp_status.reindex(q)
    out["delta_sfp"] = sfp.diff().reindex(q)

    ttl = dts_quarter["ttl"].reindex(levels)
    out["ttl_level"] = ttl.reindex(q)
    out["ttl_status"] = dts_quarter["ttl_status"].reindex(q).fillna("unavailable_pre_dts_history")
    out["delta_ttl"] = ttl.diff().reindex(q)
    out["ttl_change_status"] = np.where(out["delta_ttl"].isna(), "unavailable_pre_dts_history", out["ttl_status"])

    for column in ["fed_tsy_tx", "fed_remit_positive", "fed_tsy_coupon_interest_proxy"]:
        out[column] = legs[column]
    mmf = mmf_on_rrp_route_adjustment(quarterly.reindex(q))
    gap = (mmf["mmf_route_prop"] - legs["effective_mmf_rrp_adjustment_prop"]).abs().max()
    if gap > 1e-6:
        raise ValueError(f"MMF route proportional value differs from the frozen leg table by {gap}")
    out = out.join(mmf)
    out["trc_cash_leg"] = -out["delta_tga"] - out["delta_sfp"]
    out["trc_fed_bridge"] = out["fed_tsy_tx"] + out["fed_remit_positive"] - out["fed_tsy_coupon_interest_proxy"]
    out["trc_core"] = out["trc_cash_leg"] + out["trc_fed_bridge"]
    out["trc_preferred"] = out["trc_core"] + out["mmf_route_prop"]
    out["trc_mmf_lower"] = out["trc_core"] + out["mmf_route_lb"]
    out["trc_mmf_upper"] = out["trc_core"] + out["mmf_route_ub"]
    out["trc_status"] = np.where(
        out["trc_core"].isna(), "unavailable_no_opening_tga_level", "partial_one_sided_route_coverage",
    )
    out["trc_clock"] = "treasury_fed_deposits:" + out["tga_clock"] + ";fed_legs:z1_calendar_quarter"
    out["cash_leg_status"] = np.where(
        out["trc_cash_leg"].isna(), "unavailable_no_opening_tga_level", "source_exact_on_declared_clock",
    )
    return out


def nondefault_route_bounds(*, quarterly: pd.DataFrame, custody: pd.DataFrame, fo_cash: pd.Series) -> pd.DataFrame:
    """GSE ON RRP and foreign-official direct-account route bounds (never defaults).

    The foreign-official bound is a heuristic opposite-sign overlap of the change
    in custody holdings and the change in foreign official Fed cash. Custody
    identifies ownership, not the settling account, so no point value is formed.
    """
    q = TRC_QUARTERS
    out = pd.DataFrame(index=q)
    by_date = quarterly.copy()
    by_date.index = by_date.index.end_time.normalize()
    gse = build_gse_rrp_boundary_check(by_date)
    if not gse["status"].eq("diagnostic_only").all():
        raise ValueError(f"GSE ON RRP bound inputs unavailable: {gse['detail'].iloc[0]}")
    gse_adj = pd.Series(gse["gse_rrp_boundary_adjustment"].to_numpy(), index=pd.PeriodIndex(gse["date"], freq="Q")).reindex(q)
    active = q >= ON_RRP_MECHANISM_QUARTER
    if gse_adj[active].isna().any() or quarterly.loc[q[active], "gse_on_rrp"].isna().any():
        raise ValueError("GSE ON RRP bound missing in active ON RRP quarters")
    out["gse_route_lower"] = 0.0
    out["gse_route_upper"] = gse_adj.where(active, 0.0)
    out["gse_route_status"] = np.where(active, "nondefault_bound", "structural_zero_pre_on_rrp_mechanism")

    level = custody["level"]
    nonzero = level[level.ne(0)]
    if nonzero.empty:
        raise ValueError("custody holdings never reported")
    first_reported = nonzero.index.min()
    if level[level.index > first_reported].eq(0).any():
        raise ValueError("custody holdings report zero after first reporting a balance")
    # Leading zeros in the custody series are non-reporting, not zero holdings.
    reported = level.where(level.index >= first_reported)
    d_custody = _difference(reported, q)
    d_cash = _difference(fo_cash, q)
    out["delta_custody"] = d_custody
    out["delta_fo_cash"] = d_cash
    out["fo_route_upper"] = np.minimum(d_custody.clip(lower=0), (-d_cash).clip(lower=0))
    out["fo_route_lower"] = -np.minimum((-d_custody).clip(lower=0), d_cash.clip(lower=0))
    available = d_custody.notna() & d_cash.notna()
    out["fo_route_status"] = np.where(
        available, "nondefault_heuristic_opposite_sign_overlap_bound",
        np.where(d_cash.notna(), "unavailable_custody_not_reported", "unavailable_no_opening_level"),
    )
    out.attrs["custody_first_reported_quarter"] = str(first_reported)
    return out


def reserve_factor_remainder(delta_factor: pd.Series, allocation: pd.DataFrame) -> pd.DataFrame:
    """Non-Treasury remainder of a reserve-absorbing Fed liability.

    ``N = -delta_factor - Gamma^T``: the full reserve effect of the factor less the
    Treasury route allocation already counted in TRC, subtracted exactly once.
    ``allocation`` carries lower, central, and upper Treasury allocations.
    """
    return pd.DataFrame({
        "lower": -delta_factor - allocation["upper"],
        "central": -delta_factor - allocation["central"],
        "upper": -delta_factor - allocation["lower"],
    }, index=delta_factor.index)



def reserve_factor_diagnostics(
    routes: pd.DataFrame, *, h41: dict[str, pd.DataFrame], daily: pd.DataFrame, h3: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """H.4.1 factor remainders, memo perimeters, and the all-H.4.1 clock diagnostic.

    Reads the assembled Treasury allocations and returns only new columns, so a
    reserve factor cannot become a Treasury classification.
    """
    q = TRC_QUARTERS
    out = pd.DataFrame(index=q)
    out["delta_rrp_others_h41"] = _difference(h41["h41_rrp_others_wednesday"]["level"], q)
    rrp = reserve_factor_remainder(out["delta_rrp_others_h41"], pd.DataFrame({
        "lower": routes["mmf_route_lb"], "central": routes["mmf_route_prop"], "upper": routes["mmf_route_ub"]}))
    fo = reserve_factor_remainder(routes["delta_fo_cash"], pd.DataFrame({
        "lower": routes["fo_route_lower"], "central": 0.0, "upper": routes["fo_route_upper"]}, index=q))
    for name, cell in [("remainder_on_rrp", rrp), ("remainder_foreign_official", fo)]:
        for bound in ["lower", "central", "upper"]:
            out[f"{name}_{bound}"] = cell[bound]
    out["remainder_status"] = np.where(out["delta_rrp_others_h41"].isna(), "unavailable_no_opening_level", "diagnostic_h41_clock")
    out["remainder_fo_status"] = np.where(
        routes["delta_fo_cash"].isna(), "unavailable_no_opening_level",
        np.where(routes["fo_route_upper"].isna(), "diagnostic_h41_clock_bounds_unavailable", "diagnostic_h41_clock"),
    )

    rb_h41 = h41["h41_reserve_balances_wednesday"]
    out["delta_rb_h41"] = _difference(rb_h41["level"], q)
    out["memo_reserves_plus_rrp_others"] = _difference(rb_h41["level"] + h41["h41_rrp_others_wednesday"]["level"], q)
    h3_level = monthly_final_month(h3, "h3_total_reserves_monthly") * 1000.0
    recent = pd.period_range("2021Q1", q[-1], freq="Q")
    ratio = float((h3_level.reindex(recent) / rb_h41["level"].reindex(recent)).median())
    if not 0.8 <= ratio <= 1.25:
        raise ValueError(f"H.3 total reserves unit check failed: median ratio to H.4.1 reserves {ratio}")
    out["memo_h3_total_reserves_change"] = _difference(h3_level, q)
    out["h3_status"] = np.where(
        out["memo_h3_total_reserves_change"].isna(), "unavailable_no_opening_level", "memo_not_a_trc_perimeter",
    )

    sfp_at_wednesday = []
    unclassified_on_wednesdays: dict[str, float] = {}
    daily_dates = daily.index
    for quarter in q:
        wednesday = pd.Timestamp(h41["h41_tga_wednesday"]["date"].get(quarter, pd.NaT))
        if pd.isna(wednesday):
            sfp_at_wednesday.append(np.nan)
        elif wednesday < daily_dates[0]:
            if wednesday >= SFP_PROGRAM_START:
                raise ValueError("DTS Table I must cover every H.4.1 date from the SFP program start")
            sfp_at_wednesday.append(0.0)
        else:
            row = daily.loc[daily_dates[daily_dates <= wednesday].max()]
            if row["unclassified_balance"] != 0:
                unclassified_on_wednesdays[str(quarter)] = float(row["unclassified_balance"])
            sfp_at_wednesday.append(float(row["sfp"]))
    out["delta_tga_h41"] = _difference(h41["h41_tga_wednesday"]["level"], q)
    out["delta_sfp_h41_date"] = _difference(pd.Series(sfp_at_wednesday, index=q), q)
    h41_core = -out["delta_tga_h41"] - out["delta_sfp_h41_date"] + routes["trc_fed_bridge"]
    out["diag_trc_h41_preferred"] = h41_core + routes["mmf_route_prop"]
    out["diag_trc_h41_lower"] = h41_core + routes["mmf_route_lb"]
    out["diag_trc_h41_upper"] = h41_core + routes["mmf_route_ub"]
    out["h41_status"] = np.where(out["delta_rb_h41"].isna(), "unavailable_no_opening_level", "nondefault_clock_diagnostic")
    stats = {
        "h3_to_h41_reserve_level_median_ratio_2021_2025": ratio,
        "dts_unclassified_account_nonzero_on_h41_diagnostic_dates": unclassified_on_wednesdays,
    }
    return out, stats


def _window_stats(left: pd.Series, right: pd.Series, start: str, end: str) -> dict:
    window = slice(pd.Period(start, freq="Q"), pd.Period(end, freq="Q"))
    pair = pd.concat([left.loc[window], right.loc[window]], axis=1).dropna()
    diff = pair.iloc[:, 0] - pair.iloc[:, 1]
    return {
        "window": f"{start}-{end}", "n": int(len(pair)),
        "mean_abs_difference": _finite(diff.abs().mean()), "max_abs_difference": _finite(diff.abs().max()),
        "correlation": _finite(pair.iloc[:, 0].corr(pair.iloc[:, 1])),
    }


def _finite(value: float) -> float | None:
    """JSON-safe statistic: an undefined value (empty window, constant series) is null."""
    return float(value) if np.isfinite(value) else None


@dataclass(frozen=True)
class TrcInputs:
    legs: pd.DataFrame
    quarterly: pd.DataFrame
    sources: dict[str, pd.DataFrame]


def build_trc_components(inputs: TrcInputs) -> tuple[pd.DataFrame, dict]:
    """Assemble the wide quarterly component table and cross-check statistics."""
    legs = _legs(inputs.legs)
    quarterly = _quarterly(inputs.quarterly)
    src = inputs.sources
    if (legs["treasury_operating_cash_tx"] - quarterly["treasury_operating_cash_tx"].reindex(TRC_QUARTERS)).abs().max() != 0:
        raise ValueError("legs and quarterly inputs disagree on Z.1 Treasury operating cash")
    daily = parse_dts_table_i(src["dts_operating_cash_balance_table_i"])
    dts_q = dts_quarter_end(daily)
    h41 = {
        key: last_wednesday_levels(src[key], key) for key in [
            "h41_tga_wednesday", "h41_reserve_balances_wednesday", "h41_rrp_others_wednesday",
            "h41_rrp_foreign_official_wednesday", "h41_foreign_official_deposits_wednesday",
            "h41_custody_marketable_treasury_wednesday",
        ]
    }
    z1 = {key: z1_quarterly(src[key], key) for key in [
        "z1_reserves_transactions", "z1_sfp_transactions", "z1_us_chartered_reserves_transactions",
    ]}
    q = TRC_QUARTERS

    out = assemble_treasury_routes(legs=legs, quarterly=quarterly, dts_quarter=dts_q, tga_h41=h41["h41_tga_wednesday"])
    out["delta_rb_z1"] = z1["z1_reserves_transactions"].reindex(q)
    if out["delta_rb_z1"].isna().any():
        raise ValueError("Z.1 reserve outcome missing in the 2002Q1-2025Q4 shell")
    out["nontreasury_residual"] = out["delta_rb_z1"] - out["trc_preferred"]
    out["nontreasury_residual_lower"] = out["delta_rb_z1"] - out["trc_mmf_upper"]
    out["nontreasury_residual_upper"] = out["delta_rb_z1"] - out["trc_mmf_lower"]
    out["residual_status"] = np.where(
        out["trc_core"].isna(), "unavailable_no_opening_tga_level", "definitional_residual_closes_by_construction",
    )

    out["tdc_canonical"] = legs["C"]
    out["wedge_measured"] = out["tdc_canonical"] - out["trc_preferred"]
    out["wedge_bank_leg"] = legs[BANK_DEPOSITORY_TX_KEYS].sum(axis=1) - legs["bank_tier2_regression_interest_proxy"]
    out["wedge_row_leg"] = legs["R"]
    out["wedge_ttl_leg"] = -out["delta_ttl"]
    out["wedge_ttl_plus_residual"] = out["wedge_measured"] - out["wedge_bank_leg"] - out["wedge_row_leg"]
    out["wedge_residual_u"] = out["wedge_ttl_plus_residual"] - out["wedge_ttl_leg"]
    out["z1_treasury_operating_cash_tx"] = legs["treasury_operating_cash_tx"]
    out["cash_partition_gap"] = out["z1_treasury_operating_cash_tx"] - (out["delta_tga"] + out["delta_sfp"] + out["delta_ttl"])
    out["wedge_status"] = np.where(
        out["trc_core"].isna(), "unavailable_no_opening_tga_level",
        np.where(out["delta_ttl"].isna(), "reconciliation_ttl_unavailable_pre_2006", "reconciliation_not_identity"),
    )
    out["wedge_residual_status"] = np.where(
        out["trc_core"].isna(), "unavailable_no_opening_tga_level",
        np.where(out["delta_ttl"].isna(), "unavailable_ttl_pre_2006", "source_clock_residual"),
    )
    out["z1_sfp_tx"] = z1["z1_sfp_transactions"].reindex(q)

    fo_cash = h41["h41_foreign_official_deposits_wednesday"]["level"] + h41["h41_rrp_foreign_official_wednesday"]["level"]
    bounds = nondefault_route_bounds(quarterly=quarterly, custody=h41["h41_custody_marketable_treasury_wednesday"], fo_cash=fo_cash)
    out = out.join(bounds)
    out["trc_route_bounded_lower"] = out["trc_mmf_lower"] + out["gse_route_lower"] + out["fo_route_lower"]
    out["trc_route_bounded_upper"] = out["trc_mmf_upper"] + out["gse_route_upper"] + out["fo_route_upper"]

    diagnostics, diagnostic_stats = reserve_factor_diagnostics(out, h41=h41, daily=daily, h3=src["h3_total_reserves_monthly"])
    out = out.join(diagnostics, validate="one_to_one")
    out["memo_us_chartered_reserves_z1"] = z1["z1_us_chartered_reserves_transactions"].reindex(q)

    stats = {
        "tga_change_dts_vs_h41": _window_stats(_difference(dts_q["tga"], q), out["delta_tga_h41"], "2006Q1", "2025Q4"),
        "reserve_change_z1_vs_h41_last_wednesday": _window_stats(out["delta_rb_z1"], out["delta_rb_h41"], "2003Q1", "2025Q4"),
        "sfp_change_dts_vs_z1": _window_stats(out["delta_sfp"], out["z1_sfp_tx"], "2003Q1", "2025Q4"),
        "z1_operating_cash_vs_dts_tga_sfp_ttl": _window_stats(out["z1_treasury_operating_cash_tx"], out["z1_treasury_operating_cash_tx"] - out["cash_partition_gap"], "2006Q1", "2025Q4"),
        "max_abs_wedge_residual_plus_cash_partition_gap": _finite((out["wedge_residual_u"] + out["cash_partition_gap"]).abs().max()),
        **diagnostic_stats,
        "custody_first_reported_quarter": bounds.attrs["custody_first_reported_quarter"],
        "dts_first_quarter": str(dts_q.index.min()),
        "correlation_z1_reserve_change_with_trc": {
            series: {f"{lo}-{hi}": _finite(out.loc[lo:hi, "delta_rb_z1"].corr(out.loc[lo:hi, series])) for lo, hi in PERIOD_WINDOWS}
            for series in ["trc_preferred", "trc_core"]
        },
    }
    out.insert(0, "quarter", out.index.astype(str))
    return out.reset_index(drop=True), stats


@dataclass(frozen=True)
class SeriesSpec:
    series_id: str
    object: str
    perimeter: str
    lower: str | None
    central: str | None
    upper: str | None
    status: str
    sources: tuple[str, ...]
    clock: str
    route_coverage: tuple[str, ...]
    default_eligible: bool


DEFAULT_TRC_ROUTES = (
    "treasury_general_account", "other_treasury_fed_account", "fed_soma",
    "covered_deposit", "bank_reserve_own_account", "foreign_bank_settled",
)
TRC_SOURCES = ("@tga", "dts_operating_cash_balance_table_i", LEGS_SOURCE_KEY)
MMF_SOURCES = (*TRC_SOURCES, QUARTERLY_SOURCE_KEY)
WEDGE_SOURCES = (*MMF_SOURCES,)
H41_TRC_SOURCES = ("h41_tga_wednesday", "dts_operating_cash_balance_table_i", LEGS_SOURCE_KEY, QUARTERLY_SOURCE_KEY)
AGG = "aggregate_reserve_balances"
TRC_OBJ = "treasury_reserve_component"

SERIES_SPECS: tuple[SeriesSpec, ...] = (
    SeriesSpec("z1_reserve_change", "reserve_change", AGG, None, "delta_rb_z1", None, "=source_exact",
               ("z1_reserves_transactions",), "z1_calendar_quarter_transactions", (), True),
    SeriesSpec("trc_leg_treasury_fed_deposits", "trc_component", AGG, None, "trc_cash_leg", None, "cash_leg_status",
               ("@tga", "dts_operating_cash_balance_table_i"), "@tga_clock",
               ("treasury_general_account", "other_treasury_fed_account"), True),
    SeriesSpec("trc_leg_fed_treasury_bridge", "trc_component", AGG, None, "trc_fed_bridge", None, "=proxy",
               (LEGS_SOURCE_KEY,), "z1_calendar_quarter", ("fed_soma",), True),
    SeriesSpec("route_adj_mmf_on_rrp", "route_adjustment", AGG, "mmf_route_lb", "mmf_route_prop", "mmf_route_ub",
               "mmf_route_status", (LEGS_SOURCE_KEY, QUARTERLY_SOURCE_KEY), "calendar_quarter_fund_month_sum",
               ("mmf_on_rrp",), True),
    SeriesSpec("trc_core", TRC_OBJ, AGG, None, "trc_core", None, "trc_status", TRC_SOURCES, "@trc_clock",
               DEFAULT_TRC_ROUTES, True),
    SeriesSpec("trc_preferred", TRC_OBJ, AGG, "trc_mmf_lower", "trc_preferred", "trc_mmf_upper", "trc_status",
               MMF_SOURCES, "@trc_clock", (*DEFAULT_TRC_ROUTES, "mmf_on_rrp"), True),
    SeriesSpec("trc_core_mmf_lower", TRC_OBJ, AGG, None, "trc_mmf_lower", None, "trc_status", MMF_SOURCES,
               "@trc_clock", (*DEFAULT_TRC_ROUTES, "mmf_on_rrp"), True),
    SeriesSpec("trc_core_mmf_upper", TRC_OBJ, AGG, None, "trc_mmf_upper", None, "trc_status", MMF_SOURCES,
               "@trc_clock", (*DEFAULT_TRC_ROUTES, "mmf_on_rrp"), True),
    SeriesSpec("nontreasury_residual", "nontreasury_reserve_remainder", AGG, "nontreasury_residual_lower",
               "nontreasury_residual", "nontreasury_residual_upper", "residual_status",
               ("z1_reserves_transactions", *MMF_SOURCES), "@trc_clock", (), True),
    SeriesSpec("tdc_canonical", "treasury_deposit_component", "covered_domestic_nonbank_deposits", None,
               "tdc_canonical", None, "=frozen_canonical_tdc", (LEGS_SOURCE_KEY,), "z1_calendar_quarter", (), True),
    SeriesSpec("tdc_trc_wedge", "tdc_trc_wedge", "deposit_vs_reserve", None, "wedge_measured", None,
               "wedge_status", WEDGE_SOURCES, "@trc_clock", (), True),
    SeriesSpec("wedge_bank_leg", "tdc_trc_wedge_leg", "deposit_vs_reserve", None, "wedge_bank_leg", None,
               "=reconciliation_leg", (LEGS_SOURCE_KEY,), "z1_calendar_quarter", ("bank_reserve_own_account",), True),
    SeriesSpec("wedge_row_leg", "tdc_trc_wedge_leg", "deposit_vs_reserve", None, "wedge_row_leg", None,
               "=reconciliation_leg", (LEGS_SOURCE_KEY,), "z1_calendar_quarter", ("foreign_bank_settled",), True),
    SeriesSpec("wedge_ttl_leg", "tdc_trc_wedge_leg", "deposit_vs_reserve", None, "wedge_ttl_leg", None,
               "ttl_change_status", ("dts_operating_cash_balance_table_i",), "dts_final_business_day", ("tt_and_l",), True),
    SeriesSpec("wedge_residual_u", "tdc_trc_wedge_leg", "deposit_vs_reserve", None, "wedge_residual_u", None,
               "wedge_residual_status", WEDGE_SOURCES, "@trc_clock", (), True),
    SeriesSpec("route_bound_gse_on_rrp", "route_adjustment", AGG, "gse_route_lower", None, "gse_route_upper",
               "gse_route_status", (QUARTERLY_SOURCE_KEY,), "calendar_quarter_end_levels", ("gse_on_rrp",), False),
    SeriesSpec("route_bound_foreign_official", "route_adjustment", AGG, "fo_route_lower", None, "fo_route_upper",
               "fo_route_status", ("h41_custody_marketable_treasury_wednesday", "h41_foreign_official_deposits_wednesday",
                                   "h41_rrp_foreign_official_wednesday"), "h41_last_wednesday",
               ("foreign_official_deposit", "foreign_official_rrp"), False),
    SeriesSpec("trc_route_bounded_nondefault", TRC_OBJ, AGG, "trc_route_bounded_lower", None,
               "trc_route_bounded_upper", "fo_route_status",
               (*MMF_SOURCES, "h41_custody_marketable_treasury_wednesday", "h41_foreign_official_deposits_wednesday",
                "h41_rrp_foreign_official_wednesday"), "@trc_clock",
               (*DEFAULT_TRC_ROUTES, "mmf_on_rrp", "gse_on_rrp", "foreign_official_deposit", "foreign_official_rrp"),
               False),
    SeriesSpec("remainder_on_rrp", "nontreasury_reserve_remainder_cell", AGG, "remainder_on_rrp_lower",
               "remainder_on_rrp_central", "remainder_on_rrp_upper", "remainder_status",
               ("h41_rrp_others_wednesday", LEGS_SOURCE_KEY, QUARTERLY_SOURCE_KEY),
               "factor:h41_last_wednesday;allocation:calendar_quarter", ("mmf_on_rrp",), False),
    SeriesSpec("remainder_foreign_official", "nontreasury_reserve_remainder_cell", AGG,
               "remainder_foreign_official_lower", "remainder_foreign_official_central",
               "remainder_foreign_official_upper", "remainder_fo_status",
               ("h41_foreign_official_deposits_wednesday", "h41_rrp_foreign_official_wednesday",
                "h41_custody_marketable_treasury_wednesday"), "h41_last_wednesday",
               ("foreign_official_deposit", "foreign_official_rrp"), False),
    SeriesSpec("memo_reserves_plus_rrp_others", "memo_alternative_perimeter", "reserve_balances_plus_rrp_others",
               None, "memo_reserves_plus_rrp_others", None, "h41_status",
               ("h41_reserve_balances_wednesday", "h41_rrp_others_wednesday"), "h41_last_wednesday", (), False),
    SeriesSpec("memo_h3_total_reserves", "memo_alternative_perimeter", "h3_total_reserves", None,
               "memo_h3_total_reserves_change", None, "h3_status", ("h3_total_reserves_monthly",),
               "h3_final_month_average", (), False),
    SeriesSpec("memo_us_chartered_reserves", "memo_alternative_perimeter", "us_chartered_reserves", None,
               "memo_us_chartered_reserves_z1", None, "=memo_distributional_only",
               ("z1_us_chartered_reserves_transactions",), "z1_calendar_quarter_transactions", (), False),
    SeriesSpec("diag_h41_reserve_change", "clock_diagnostic", AGG, None, "delta_rb_h41", None, "h41_status",
               ("h41_reserve_balances_wednesday",), "h41_last_wednesday", (), False),
    SeriesSpec("diag_trc_h41_tga", "clock_diagnostic", AGG, "diag_trc_h41_lower", "diag_trc_h41_preferred",
               "diag_trc_h41_upper", "h41_status", H41_TRC_SOURCES,
               "treasury_fed_deposits:h41_last_wednesday;fed_legs:z1_calendar_quarter",
               (*DEFAULT_TRC_ROUTES, "mmf_on_rrp"), False),
)


def build_trc_series(components: pd.DataFrame, source_hashes: dict[str, str]) -> pd.DataFrame:
    """Long-format series table; every all-missing row must carry an unavailable status."""
    routes = load_settlement_routes()
    rows = []
    for spec in SERIES_SPECS:
        unknown = set(spec.route_coverage) - set(routes)
        if unknown:
            raise ValueError(f"{spec.series_id}: unknown routes {sorted(unknown)}")
        for _, row in components.iterrows():
            sources = list(dict.fromkeys(row["tga_source_key"] if key == "@tga" else key for key in spec.sources))
            missing = [key for key in sources if key not in source_hashes]
            if missing:
                raise ValueError(f"{spec.series_id}: no hash for sources {missing}")
            values = {bound: (float(row[column]) if column else np.nan)
                      for bound, column in [("value_lower", spec.lower), ("value_central", spec.central),
                                            ("value_upper", spec.upper)]}
            status = spec.status[1:] if spec.status.startswith("=") else row[spec.status]
            observed = any(np.isfinite(v) for v in values.values())
            if observed == str(status).startswith("unavailable"):
                raise ValueError(f"{spec.series_id} {row['quarter']}: status {status} contradicts value availability")
            clock = row[spec.clock[1:]] if spec.clock.startswith("@") else spec.clock
            legacy = [f"{key}:{source_hashes[key]}" for key in LEGACY_SOURCE_KEYS if key in sources]
            rows.append({
                "quarter": row["quarter"], "object": spec.object, "perimeter": spec.perimeter,
                "series_id": spec.series_id, **values, "units": "USD million", "clock": clock,
                "source_id": "+".join(sources), "source_hash": "+".join(source_hashes[key] for key in sources),
                "route_coverage": "|".join(spec.route_coverage), "measurement_status": status,
                "default_eligible": spec.default_eligible, "legacy_artifact_hash_set": ";".join(legacy),
            })
    return pd.DataFrame(rows)
