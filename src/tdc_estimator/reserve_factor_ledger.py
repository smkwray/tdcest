"""H.4.1 reserve-factor ledger on the Wednesday clock, with bridges to the admitted TRC.

Every input is an H.4.1 Table 1 Wednesday level in USD million named by the
typed row registry ``catalog.H41_TABLE1_ROWS``. Supplying factors enter with a
plus sign and absorbing factors other than reserve balances with a minus sign:

    dRB_w = sum_k f_k,w + rho_w,        f_k,w = side_k * d(level_k)_w

``rho`` holds published rounding and any unmapped row. Level and change closure
are checked on every Wednesday against reserve balances, the published totals,
and each published parent within half a million per rounded component; a breach
raises. Quarterly sums telescope between the last Wednesdays of adjacent
quarters.

The bridge table reconciles each admitted quarterly TRC variant ``x`` with the
ledger, row by row:

    y^Z - x = sum_{k other} F_k + N^{RRP,other} + (y^Z - y^H) + (C^H - C^M) + (S^H - B) + rho^H
    N^{RRP,other} = -dRRP_other - Gamma

so the MMF/ON RRP route already counted in TRC leaves the RRP-others factor
exactly once. Nothing here estimates or identifies a causal effect.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .catalog import (
    DEFAULT_VINTAGE, H41_LEDGER_START, H41_TABLE1_ROWS, H41Row, MeasurementVintage, fiscus_registries,
)
from .config import project_paths
from .tier2_regression_series import leg_quarters, read_pinned_input, require_clean_commit
from .trc_export import TRC_OUTPUT_FILES, load_fiscus_inputs
from .trc_reserve_component import _difference, _numeric, last_wednesday_levels, z1_quarterly

LEDGER_SCHEMA_VERSION = "reserve_factor_ledger_v1"
LEDGER_START = pd.Timestamp(H41_LEDGER_START)
HALF_UNIT = 0.5  # USD million: H.4.1 rounds every published row to the nearest million
IDENTITY_TOLERANCE = 1e-6
ROLES = ("factor", "check", "memo", "outcome")
SIDES = {"total_supplying": 1, "total_absorbing": -1}
OUTCOME_KEY = "reserve_balances"
REPORTED = "source_reported"
BEFORE_ROW = "structural_zero_before_row_introduced"
AFTER_ROW = "structural_zero_after_row_removed"
CASH_KEYS = ("treasury_general_account", "supplementary_financing_account")
SECURITIES_KEYS = ("treasury_securities",)
TERM_DEPOSIT_KEY = "term_deposits"
RRP_OTHER_KEY = "rrp_others"
TRC_VARIANTS = {"trc_core": None, "trc_preferred": "mmf_route_prop", "trc_mmf_lower": "mmf_route_lb",
                "trc_mmf_upper": "mmf_route_ub"}
COMPONENT_COLUMNS = [
    "quarter", "delta_rb_z1", "trc_cash_leg", "trc_fed_bridge", "tga_clock", "mmf_route_lb", "mmf_route_prop",
    "mmf_route_ub", *TRC_VARIANTS, "delta_rb_h41", "delta_tga_h41",
]
BRIDGE_COLUMNS = ["bridge_outcome", "bridge_outcome_term_deposits", "bridge_outcome_z1_flow_vs_level",
                  "bridge_outcome_unattributed", "bridge_cash", "bridge_securities", "rho"]
def eras(quarter_end: str) -> list[tuple[str, str]]:
    """Fixed reporting eras; the open-ended eras run to the measured endpoint."""
    return [("2003Q1", "2008Q3"), ("2008Q4", "2008Q4"), ("2009Q1", "2015Q3"), ("2015Q4", "2015Q4"),
            ("2016Q1", quarter_end), ("2003Q1", quarter_end)]

LEDGER_OUTPUT_FILES = {
    "weekly": "reserve_factor_ledger_weekly_v1.csv",
    "quarterly": "reserve_factor_ledger_quarterly_v1.csv",
    "bridges": "reserve_factor_bridges_quarterly_v1.csv",
    "receipt": "reserve_factor_ledger_v1_receipt.json",
}
DEFINITIONS = {
    "f_<factor>": "Signed change of one Table 1 row: +d(level) for a supplying factor, -d(level) for an absorbing factor other than reserve balances",
    "rho": "Change in reserve balances less the sum of signed factor changes: published rounding plus any unmapped row",
    "rho_level": "Reserve balances less (supplying factors - absorbing factors) on the same Wednesday",
    "level_bound": "0.5 USD million times (rounded factors reported that Wednesday + reserve balances)",
    "change_bound": "Sum of the level bounds at the two endpoint Wednesdays",
    "gap_<check>": "Published parent or total less the sum of its factor descendants; bound 0.5 times (reported descendants + 1)",
    "published_identity_gap": "Total supplying - total absorbing other than reserve balances - reserve balances; bound 1.5",
    "y_h": "Change in H.4.1 reserve balances (WRBWFRBL) between last Wednesdays",
    "c_h": "-d(WDTGAL) - d(WDSFAL): Treasury General Account and Supplementary Financing Account; Treasury Tax and Loan balances are commercial-bank claims, absent from H.4.1, and never enter",
    "s_h": "d(WSHOTSL): Table 1 'U.S. Treasury securities' held outright = bills + notes and bonds nominal + notes and bonds inflation-indexed + inflation compensation; excludes unamortized premiums and discounts (published for all securities held outright combined), repurchase agreements, securities lent, and custody holdings",
    "memo_f_treasury_inflation_compensation": "d(WSHOICL): inflation compensation already inside s_h; displayed, never summed",
    "y_z": "Admitted outcome delta_rb_z1, Z.1 FU713113003 calendar-quarter transactions",
    "c_m": "Admitted trc_cash_leg (clock per row in c_m_clock)",
    "b": "Admitted trc_fed_bridge: Z.1 Fed Treasury transactions + positive remittances - SOMA coupon proxy",
    "gamma": "Admitted MMF/ON RRP route for the variant: zero for trc_core, mmf_route_prop/lb/ub otherwise",
    "x": "Admitted TRC variant = c_m + b + gamma",
    "n_rrp_others": "f_rrp_others - gamma: the RRP-others factor net of the route already in TRC, subtracted once",
    "sum_other_factors": "Sum of f_<factor> over every factor except the TGA, SFP, Treasury securities, and RRP-others rows",
    "bridge_outcome": "y_z - y_h: outcome perimeter, clock, and source bridge",
    "bridge_outcome_term_deposits": "d(TERMT) on the last-Wednesday clock: Z.1 FL713113003 includes H.4.1 term deposits, which reserve balances exclude",
    "bridge_outcome_z1_flow_vs_level": "y_z - d(FL713113003): Z.1 transactions less the Z.1 level change (series breaks, including the FHLB exclusion boundaries)",
    "bridge_outcome_unattributed": "d(FL713113003) - y_h - d(TERMT): quarter-end versus last-Wednesday clock, FHLB deposits excluded from Z.1 in 2007Q1-2017Q4, and any other source difference; not attributed",
    "bridge_cash": "c_h - c_m: Treasury-deposit clock and source bridge",
    "bridge_securities": "s_h - b: securities valuation, accrual, and Fed-payment bridge",
    "identity": "y_z - x = sum_other_factors + n_rrp_others + bridge_outcome + bridge_cash + bridge_securities + rho",
}
BOUNDARIES = [
    "Descriptive accounting ledger and reconciliation; no estimation, identification, or causal interpretation",
    "Admitted TRC outputs are read under a pinned hash and never rewritten",
    "Weekly and quarterly ledger columns are H.4.1 Table 1 Wednesday levels only; the bridge table mixes that clock with the admitted calendar-quarter TRC legs and labels every bridge",
    "rho closes against published totals within rounding; the closure is independent evidence only for the H.4.1 rows, not for the Z.1 outcome or the TRC legs",
    "The RRP-others row mixes counterparties and is not ON RRP or money-fund take-up; the MMF route is subtracted from it once, and no other route correction is admitted",
    "Unamortized premiums and discounts cover all securities held outright and stay separate factors; they are not classified as Treasury or non-Treasury transactions",
    "bridge_outcome_unattributed is an explicit residual, not timing alone",
    "Structural zeros apply only before a declared row introduction or after a declared row removal, and published totals must close with them",
]


@dataclass(frozen=True)
class LedgerRow:
    row: H41Row
    side: int
    descendants: tuple[str, ...]


def load_h41_rows(rows: tuple[H41Row, ...] = H41_TABLE1_ROWS) -> dict[str, LedgerRow]:
    """Validate the Table 1 row hierarchy once; a factor never sits under another factor."""
    by_key: dict[str, H41Row] = {}
    for row in rows:
        if row.key in by_key:
            raise ValueError(f"duplicate H.4.1 row {row.key}")
        if row.role not in ROLES:
            raise ValueError(f"{row.key}: unknown role {row.role}")
        by_key[row.key] = row
    series = [row.series_id for row in rows]
    if len(set(series)) != len(series):
        raise ValueError("an H.4.1 series enters the registry twice")
    roots = {key for key, row in by_key.items() if row.parent is None}
    if roots != {*SIDES, OUTCOME_KEY}:
        raise ValueError(f"Table 1 roots must be {sorted({*SIDES, OUTCOME_KEY})}, got {sorted(roots)}")
    if by_key[OUTCOME_KEY].role != "outcome" or sum(row.role == "outcome" for row in rows) != 1:
        raise ValueError("reserve balances must be the only outcome row")

    def ancestors(key: str) -> list[str]:
        chain, parent = [], by_key[key].parent
        while parent is not None:
            if parent not in by_key:
                raise ValueError(f"{key}: unknown parent {parent}")
            if parent in chain or parent == key:
                raise ValueError(f"{key}: cyclic parent chain")
            chain.append(parent)
            parent = by_key[parent].parent
        return chain

    chains = {key: ancestors(key) for key in by_key}
    for key, row in by_key.items():
        chain = chains[key]
        parent_role = by_key[row.parent].role if row.parent else None
        if parent_role in ("memo", "outcome"):
            raise ValueError(f"{key}: a {parent_role} row cannot have children")
        if row.role == "factor":
            if not chain or chain[-1] not in SIDES:
                raise ValueError(f"{key}: a factor must sit under a Table 1 total")
            if any(by_key[a].role == "factor" for a in chain):
                raise ValueError(f"{key}: parent and child would both enter the ledger")
        if row.role == "check" and any(by_key[a].role != "check" for a in chain):
            raise ValueError(f"{key}: a check row must sit under check rows only")
        if row.role == "memo" and parent_role != "factor":
            raise ValueError(f"{key}: a memo row must be a child of a factor")
        if row.role != "factor" and (row.introduced or row.discontinued):
            raise ValueError(f"{key}: only factor rows may be introduced or removed")
        if row.terminal_nonzero and not row.discontinued:
            raise ValueError(f"{key}: terminal_nonzero requires a discontinued row")
        if row.introduced and pd.Timestamp(row.introduced) <= LEDGER_START:
            raise ValueError(f"{key}: introduced on or before the ledger start")
    out: dict[str, LedgerRow] = {}
    for key, row in by_key.items():
        descendants = tuple(k for k, r in by_key.items() if r.role == "factor" and key in chains[k])
        if row.role == "check" and not descendants:
            raise ValueError(f"{key}: a check row needs factor descendants")
        side = SIDES[chains[key][-1]] if chains[key] else SIDES.get(key, 0)
        out[key] = LedgerRow(row=row, side=side if row.role != "outcome" else 0, descendants=descendants)
    return out


def _keys(rows: dict[str, LedgerRow], role: str) -> list[str]:
    return [key for key, entry in rows.items() if entry.row.role == role]


def _wednesday_series(frame: pd.DataFrame, label: str) -> pd.Series:
    if {"date", "value"} - set(frame.columns):
        raise ValueError(f"{label}: expected date and value columns")
    dates = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise")
    if dates.duplicated().any() or not dates.dt.weekday.eq(2).all():
        raise ValueError(f"{label}: observations must be unique Wednesdays")
    return pd.Series(_numeric(frame["value"], label).to_numpy(), index=pd.DatetimeIndex(dates)).sort_index()


def h41_levels(frames: dict[str, pd.DataFrame], rows: dict[str, LedgerRow]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Wednesday levels on the reserve-balance calendar with an explicit status per row and date."""
    missing = [key for key in rows if key not in frames]
    if missing:
        raise ValueError(f"H.4.1 inputs missing for rows {missing}")
    outcome = _wednesday_series(frames[OUTCOME_KEY], OUTCOME_KEY)
    calendar = outcome.index
    if calendar[0] != LEDGER_START or not (calendar.to_series().diff().dropna() == pd.Timedelta(days=7)).all():
        raise ValueError("reserve balances must run on consecutive Wednesdays from the ledger start")
    levels, status, coverage = {}, {}, {}
    for key, entry in rows.items():
        row = entry.row
        series = _wednesday_series(frames[key], key)
        if not series.index.isin(calendar).all():
            raise ValueError(f"{key}: observations outside the reserve-balance calendar")
        first, last = series.index.min(), series.index.max()
        if len(series) != int(((calendar >= first) & (calendar <= last)).sum()):
            raise ValueError(f"{key}: Wednesdays missing inside its reporting span")
        before, after = calendar < first, calendar > last
        state = pd.Series(REPORTED, index=calendar)
        if before.any():
            if row.introduced is None:
                raise ValueError(f"{key}: no observation before {first.date()} and no declared row introduction")
            if not 0 <= (first - pd.Timestamp(row.introduced)).days <= 7:
                raise ValueError(f"{key}: first observation {first.date()} is not the week of its declared introduction")
            state[before] = BEFORE_ROW
        elif row.introduced is not None:
            raise ValueError(f"{key}: declared introduction but reported from the ledger start")
        if after.any():
            if not row.discontinued:
                raise ValueError(f"{key}: series ends {last.date()} before the latest Wednesday; the row should exist")
            if series.iloc[-1] != 0 and row.terminal_nonzero is None:
                raise ValueError(f"{key}: removed at a nonzero balance without a declared reason")
            state[after] = AFTER_ROW
        elif row.discontinued:
            raise ValueError(f"{key}: declared discontinued but reported through the latest Wednesday")
        if row.terminal_nonzero is not None and series.iloc[-1] == 0:
            raise ValueError(f"{key}: declared terminal nonzero but its last value is zero")
        levels[key] = series.reindex(calendar).where(state.eq(REPORTED), 0.0)
        status[key] = state
        nonzero = series[series.ne(0)]
        coverage[key] = {
            "series_id": row.series_id, "first_reported": str(first.date()), "last_reported": str(last.date()),
            "first_nonzero": str(nonzero.index.min().date()) if len(nonzero) else None,
            "last_nonzero": str(nonzero.index.max().date()) if len(nonzero) else None,
            "last_value": float(series.iloc[-1]),
            "status_counts": {k: int(v) for k, v in state.value_counts().items()},
        }
    return pd.DataFrame(levels), pd.DataFrame(status), coverage


def _worst(values: pd.Series, bounds: pd.Series) -> dict:
    valid = values.notna()
    if not valid.any():
        return {"max_abs": None}
    absolute = values[valid].abs()
    where = absolute.idxmax()
    ratio = (absolute / bounds[valid])
    return {"max_abs": float(absolute.max()), "at": str(where.date() if hasattr(where, "date") else where),
            "bound_at": float(bounds[where]), "max_ratio_to_bound": float(ratio.max()),
            "min_bound": float(bounds[valid].min())}


def build_weekly_ledger(levels: pd.DataFrame, status: pd.DataFrame, rows: dict[str, LedgerRow]) -> tuple[pd.DataFrame, dict]:
    """Signed weekly factor changes, rho, and level/change closure checks that raise on breach."""
    factors, checks, memos = _keys(rows, "factor"), _keys(rows, "check"), _keys(rows, "memo")
    sides = pd.Series({key: rows[key].side for key in factors}, dtype=float)
    signed = levels[factors] * sides
    contrib = signed.diff()
    rb = levels[OUTCOME_KEY]
    reported = status[factors].eq(REPORTED)
    out = pd.DataFrame(index=levels.index)
    out["date"] = levels.index.strftime("%Y-%m-%d")
    out["quarter"] = levels.index.to_period("Q").astype(str)
    out["reserve_balances"] = rb
    out["delta_reserve_balances"] = rb.diff()
    out["c_h"] = contrib[list(CASH_KEYS)].sum(axis=1, min_count=len(CASH_KEYS))
    out["s_h"] = contrib[list(SECURITIES_KEYS)].sum(axis=1, min_count=len(SECURITIES_KEYS))
    for key in factors:
        out[f"f_{key}"] = contrib[key]
    for key in memos:
        out[f"memo_f_{key}"] = levels[key].diff() * rows[key].side
    out["rho"] = out["delta_reserve_balances"] - contrib.sum(axis=1, min_count=len(factors))
    out["rho_level"] = rb - signed.sum(axis=1)
    out["level_bound"] = HALF_UNIT * (reported.sum(axis=1) + 1)
    out["change_bound"] = out["level_bound"] + out["level_bound"].shift()
    breaches = {"rho_level": out.index[out["rho_level"].abs() > out["level_bound"]],
                "rho": out.index[out["rho"].abs() > out["change_bound"]]}
    stats = {"rho_level": _worst(out["rho_level"], out["level_bound"]), "rho": _worst(out["rho"], out["change_bound"])}
    for key in checks:
        descendants = list(rows[key].descendants)
        gap = levels[key] - levels[descendants].sum(axis=1)
        bound = HALF_UNIT * (status[descendants].eq(REPORTED).sum(axis=1) + 1)
        out[f"gap_{key}"] = gap
        breaches[f"gap_{key}"] = out.index[gap.abs() > bound]
        stats[f"gap_{key}"] = {**_worst(gap, bound), "descendants": descendants}
    identity = levels["total_supplying"] - levels["total_absorbing"] - rb
    out["published_identity_gap"] = identity
    breaches["published_identity_gap"] = out.index[identity.abs() > 3 * HALF_UNIT]
    stats["published_identity_gap"] = _worst(identity, pd.Series(3 * HALF_UNIT, index=identity.index))
    failed = {name: [str(d.date()) for d in dates[:5]] for name, dates in breaches.items() if len(dates)}
    if failed:
        raise ValueError(f"H.4.1 closure exceeds the rounding bound: {failed}")
    structural = status[factors].ne(REPORTED)
    out["structural_zero_rows"] = [
        "|".join(f"{key}={status.at[date, key]}" for key in factors if structural.at[date, key])
        for date in levels.index
    ]
    out["ledger_status"] = np.where(out["rho"].isna(), "unavailable_no_prior_wednesday", "closed_within_rounding_bound")
    return out.reset_index(drop=True), stats


def _last_wednesday(quarter: pd.Period) -> pd.Timestamp:
    end = quarter.end_time.normalize()
    return end - pd.Timedelta(days=(end.weekday() - 2) % 7)


def build_quarterly_ledger(weekly: pd.DataFrame, levels: pd.DataFrame, rows: dict[str, LedgerRow]) -> tuple[pd.DataFrame, dict]:
    """Wednesday-bounded quarters that telescope between last Wednesdays of adjacent quarters."""
    factors, memos = _keys(rows, "factor"), _keys(rows, "memo")
    calendar = levels.index
    final = calendar[-1].to_period("Q")
    complete_end = final if _last_wednesday(final) <= calendar[-1] else final - 1
    trimmed = levels.loc[:_last_wednesday(complete_end)]
    dated = last_wednesday_levels(pd.DataFrame({
        "date": trimmed.index.strftime("%Y-%m-%d"), "value": trimmed[OUTCOME_KEY].to_numpy()}), OUTCOME_KEY)
    ends = pd.DatetimeIndex(dated["date"])
    end_levels = levels.loc[ends].set_axis(dated.index)
    sides = pd.Series({key: rows[key].side for key in factors}, dtype=float)
    flows = (end_levels[factors] * sides).diff().iloc[1:]
    quarters = flows.index
    week = weekly.set_index(pd.to_datetime(weekly["date"]))
    week = week.loc[(week.index > ends[0]) & (week.index <= ends[-1])]
    sums = week.groupby(week.index.to_period("Q"))
    out = pd.DataFrame(index=quarters)
    out["quarter"] = quarters.astype(str)
    out["start_wednesday"] = ends[:-1].strftime("%Y-%m-%d")
    out["end_wednesday"] = ends[1:].strftime("%Y-%m-%d")
    out["n_weeks"] = sums.size().reindex(quarters).to_numpy()
    out["reserve_balances_start"] = end_levels[OUTCOME_KEY].shift().iloc[1:]
    out["reserve_balances_end"] = end_levels[OUTCOME_KEY].iloc[1:]
    out["delta_reserve_balances"] = end_levels[OUTCOME_KEY].diff().iloc[1:]
    out["c_h"] = flows[list(CASH_KEYS)].sum(axis=1)
    out["s_h"] = flows[list(SECURITIES_KEYS)].sum(axis=1)
    for key in factors:
        out[f"f_{key}"] = flows[key]
    for key in memos:
        out[f"memo_f_{key}"] = end_levels[key].diff().iloc[1:] * rows[key].side
    out["rho"] = out["delta_reserve_balances"] - flows.sum(axis=1)
    columns = ["delta_reserve_balances", "c_h", "s_h", *[f"f_{k}" for k in factors], *[f"memo_f_{k}" for k in memos], "rho"]
    telescoping_gap = float((sums[columns].sum().reindex(quarters) - out[columns]).abs().max().max())
    if telescoping_gap > IDENTITY_TOLERANCE:
        raise ValueError(f"quarterly ledger does not telescope from weekly changes: {telescoping_gap}")
    level_bound = weekly.set_index("date")["level_bound"]
    out["change_bound"] = (level_bound.reindex(out["start_wednesday"]).to_numpy()
                           + level_bound.reindex(out["end_wednesday"]).to_numpy())
    if (out["rho"].abs() > out["change_bound"]).any():
        raise ValueError("quarterly rho exceeds the rounding bound")
    structural = weekly.set_index("date")["structural_zero_rows"]
    out["structural_zero_rows"] = [
        "|".join(sorted({*filter(None, structural[s].split("|")), *filter(None, structural[e].split("|"))}))
        for s, e in zip(out["start_wednesday"], out["end_wednesday"])
    ]
    out["ledger_status"] = "closed_within_rounding_bound"
    stats = {
        "first_quarter": str(quarters[0]), "last_complete_quarter": str(quarters[-1]),
        "incomplete_trailing_quarter": None if complete_end == final else {
            "quarter": str(final), "wednesdays_observed": int((calendar.to_period("Q") == final).sum()),
            "rule": "excluded until its last Wednesday is published; its weeks remain in the weekly ledger"},
        "telescoping_max_abs_gap": telescoping_gap,
        "rho": _worst(out.set_index("quarter")["rho"], out.set_index("quarter")["change_bound"]),
    }
    return out.reset_index(drop=True), stats


def _components(components: pd.DataFrame, quarters: pd.PeriodIndex) -> pd.DataFrame:
    missing = set(COMPONENT_COLUMNS) - set(components.columns)
    if missing:
        raise ValueError(f"TRC components: missing columns {sorted(missing)}")
    frame = components[COMPONENT_COLUMNS].copy()
    frame.index = pd.PeriodIndex(frame.pop("quarter"), freq="Q")
    if not frame.index.equals(quarters):
        raise ValueError(f"TRC components: expected exactly the {quarters[0]}-{quarters[-1]} quarters")
    clock = frame.pop("tga_clock")
    frame = frame.apply(pd.to_numeric, errors="raise")
    frame["tga_clock"] = clock
    for variant, route in TRC_VARIANTS.items():
        gamma = 0.0 if route is None else frame[route]
        gap = (frame[variant] - (frame["trc_cash_leg"] + frame["trc_fed_bridge"] + gamma)).abs().max()
        if gap > IDENTITY_TOLERANCE:
            raise ValueError(f"TRC components: {variant} is not cash leg + Fed bridge + route ({gap})")
    return frame


def build_bridges(
    quarterly: pd.DataFrame, components: pd.DataFrame, z1_level: pd.DataFrame, z1_flow: pd.DataFrame,
    rows: dict[str, LedgerRow], quarters: pd.PeriodIndex,
) -> tuple[pd.DataFrame, dict]:
    """Row-by-row reconciliation of every admitted TRC variant with the H.4.1 ledger."""
    q = quarters
    comp = _components(components, q)
    ledger = quarterly.set_index(pd.PeriodIndex(quarterly["quarter"], freq="Q")).reindex(q)
    fl = z1_quarterly(z1_level, "z1_reserves_level")
    fu = z1_quarterly(z1_flow, "z1_reserves_transactions")
    recent = pd.period_range("2021Q1", q[-1], freq="Q")
    ratio = float((fl.reindex(recent) / ledger["reserve_balances_end"].reindex(recent)).median())
    if not 0.8 <= ratio <= 1.25:
        raise ValueError(f"Z.1 reserve level unit check failed: median ratio to H.4.1 reserve balances {ratio}")
    factors = _keys(rows, "factor")
    other = [key for key in factors if key not in {*CASH_KEYS, *SECURITIES_KEYS, RRP_OTHER_KEY}]
    base = pd.DataFrame(index=q)
    base["y_z"] = comp["delta_rb_z1"]
    base["y_h"] = ledger["delta_reserve_balances"]
    base["c_h"] = ledger["c_h"]
    base["c_m"] = comp["trc_cash_leg"]
    base["c_m_clock"] = comp["tga_clock"]
    base["s_h"] = ledger["s_h"]
    base["b"] = comp["trc_fed_bridge"]
    base[f"f_{RRP_OTHER_KEY}"] = ledger[f"f_{RRP_OTHER_KEY}"]
    for key in other:
        base[f"f_{key}"] = ledger[f"f_{key}"]
    base["sum_other_factors"] = ledger[[f"f_{key}" for key in other]].sum(axis=1, min_count=len(other))
    base["bridge_outcome"] = base["y_z"] - base["y_h"]
    base["bridge_outcome_term_deposits"] = -ledger[f"f_{TERM_DEPOSIT_KEY}"]
    d_fl = _difference(fl, q)
    base["bridge_outcome_z1_flow_vs_level"] = base["y_z"] - d_fl
    base["bridge_outcome_unattributed"] = d_fl - base["y_h"] - base["bridge_outcome_term_deposits"]
    base["bridge_cash"] = base["c_h"] - base["c_m"]
    base["bridge_securities"] = base["s_h"] - base["b"]
    base["rho"] = ledger["rho"]
    base["memo_s_h_inflation_compensation"] = ledger["memo_f_treasury_inflation_compensation"]
    split = (base["bridge_outcome"] - base[["bridge_outcome_term_deposits", "bridge_outcome_z1_flow_vs_level",
                                            "bridge_outcome_unattributed"]].sum(axis=1)).abs().max()
    if split > IDENTITY_TOLERANCE:
        raise ValueError(f"outcome bridge split does not sum to the outcome bridge ({split})")
    frames, worst = [], {}
    for variant, route in TRC_VARIANTS.items():
        frame = base.copy()
        frame.insert(0, "trc_variant", variant)
        frame.insert(1, "x", comp[variant])
        frame.insert(2, "gamma", 0.0 if route is None else comp[route])
        frame["n_rrp_others"] = frame[f"f_{RRP_OTHER_KEY}"] - frame["gamma"]
        frame["gap"] = frame["y_z"] - frame["x"]
        frame["identity_rhs"] = frame[["sum_other_factors", "n_rrp_others", "bridge_outcome", "bridge_cash",
                                       "bridge_securities", "rho"]].sum(axis=1, min_count=6)
        frame["identity_error"] = frame["gap"] - frame["identity_rhs"]
        required = frame[["x", "gamma", "y_z", "y_h", "c_h", "c_m", "s_h", "b", "sum_other_factors", "rho",
                          "identity_error", "bridge_outcome_unattributed"]]
        available = required.notna().all(axis=1)
        if not (available | required.isna().any(axis=1)).all() or available.ne(frame["x"].notna()).any():
            raise ValueError(f"{variant}: ledger and TRC availability disagree")
        frame["bridge_status"] = np.where(available, "reconciled_mixed_clock", "unavailable_no_opening_level")
        error = frame.loc[available, "identity_error"].abs()
        if error.max() > IDENTITY_TOLERANCE:
            raise ValueError(f"{variant}: bridge identity fails by {error.max()}")
        worst[variant] = {"max_abs_identity_error": float(error.max()), "n_reconciled": int(available.sum())}
        frames.append(frame)
    bridges = pd.concat(frames)
    bridges.insert(0, "quarter", bridges.index.astype(str))
    measured = pd.period_range("2003Q1", q[-1], freq="Q")
    early = pd.period_range("2003Q1", "2005Q4", freq="Q")
    stats = {
        "identity": worst,
        f"z1_level_to_h41_reserve_balance_median_ratio_2021_{q[-1].year}": ratio,
        "y_h_minus_admitted_delta_rb_h41_max_abs": float((base["y_h"] - comp["delta_rb_h41"]).loc[measured].abs().max()),
        "tga_change_minus_admitted_delta_tga_h41_max_abs": float(
            (-ledger[f"f_{CASH_KEYS[0]}"] - comp["delta_tga_h41"]).loc[measured].abs().max()),
        "bridge_cash_max_abs_2003Q1_2005Q4_same_h41_clock": float(base.loc[early, "bridge_cash"].abs().max()),
        "admitted_y_z_minus_fetched_fu713113003_max_abs": float((base["y_z"] - fu.reindex(q)).loc[measured].abs().max()),
    }
    return bridges.reset_index(drop=True), stats


def era_summary(bridges: pd.DataFrame, quarter_end: str) -> dict:
    """Fixed-window descriptions of the variant-invariant bridges and rho (USD million)."""
    one = bridges.loc[bridges["trc_variant"].eq("trc_preferred")].set_index(
        pd.PeriodIndex(bridges.loc[bridges["trc_variant"].eq("trc_preferred"), "quarter"], freq="Q"))
    out = {}
    for start, end in eras(quarter_end):
        window = one.loc[pd.Period(start, freq="Q"):pd.Period(end, freq="Q")]
        cells = {}
        for column in [*BRIDGE_COLUMNS, "y_z", "y_h"]:
            values = window[column].dropna()
            if values.empty:
                raise ValueError(f"era {start}-{end}: no reconciled quarters for {column}")
            cells[column] = {
                "n": int(len(values)), "mean": float(values.mean()), "mean_abs": float(values.abs().mean()),
                "sd": float(values.std(ddof=1)) if len(values) > 1 else None,
                "min": float(values.min()), "max": float(values.max()), "sum": float(values.sum()),
            }
        out[start if start == end else f"{start}-{end}"] = cells
    return out


@dataclass(frozen=True)
class LedgerResult:
    weekly: pd.DataFrame
    quarterly: pd.DataFrame
    bridges: pd.DataFrame
    stats: dict


def build_reserve_factor_ledger(
    frames: dict[str, pd.DataFrame], components: pd.DataFrame, vintage: MeasurementVintage = DEFAULT_VINTAGE,
) -> LedgerResult:
    rows = load_h41_rows()
    levels, status, coverage = h41_levels(frames, rows)
    weekly, weekly_stats = build_weekly_ledger(levels, status, rows)
    quarterly, quarterly_stats = build_quarterly_ledger(weekly, levels, rows)
    bridges, bridge_stats = build_bridges(
        quarterly, components, frames["z1_reserves_level"], frames["z1_reserves_transactions"], rows,
        leg_quarters(vintage))
    stats = {
        "weekly_closure": weekly_stats, "quarterly": quarterly_stats, "bridges": bridge_stats,
        "bridge_summary_by_era": era_summary(bridges, vintage.quarter_end), "coverage": coverage,
        "weekly_sample": {"first": weekly["date"].iloc[0], "last": weekly["date"].iloc[-1], "n": int(len(weekly))},
    }
    return LedgerResult(weekly=weekly, quarterly=quarterly, bridges=bridges, stats=stats)


def column_clocks(rows: dict[str, LedgerRow]) -> dict:
    """Declared clock and source of every output column."""
    weekly_clock, quarter_clock = "h41_wednesday_change", "h41_last_wednesday_quarter_change"
    sources = {f"f_{k}": f"fred.{e.row.series_id.lower()} (H.4.1 Table 1: {e.row.label})"
               for k, e in rows.items() if e.row.role == "factor"}
    sources.update({f"memo_f_{k}": f"fred.{e.row.series_id.lower()} (H.4.1 Table 1: {e.row.label})"
                    for k, e in rows.items() if e.row.role == "memo"})
    sources.update({f"gap_{k}": f"fred.{e.row.series_id.lower()} (H.4.1 Table 1: {e.row.label}) less factor descendants"
                    for k, e in rows.items() if e.row.role == "check"})
    h41 = {**sources, "reserve_balances": "fred.wrbwfrbl", "delta_reserve_balances": "fred.wrbwfrbl",
           "c_h": "fred.wdtgal + fred.wdsfal", "s_h": "fred.wshotsl", "rho": "fred.wrbwfrbl less all factor rows",
           "rho_level": "fred.wrbwfrbl less all factor rows",
           "published_identity_gap": "fred.wtfsrfl - fred.wtforbafl - fred.wrbwfrbl"}
    bridge = {
        "x": ("trc_quarterly_components_v1:<variant>", "@c_m_clock;fed_legs:z1_calendar_quarter;route:calendar_quarter_fund_month_sum"),
        "gamma": ("trc_quarterly_components_v1:mmf_route_*", "calendar_quarter_fund_month_sum"),
        "y_z": ("trc_quarterly_components_v1:delta_rb_z1 (Z.1 FU713113003)", "z1_calendar_quarter_transactions"),
        "y_h": ("fred.wrbwfrbl", quarter_clock),
        "c_h": ("fred.wdtgal + fred.wdsfal", quarter_clock),
        "c_m": ("trc_quarterly_components_v1:trc_cash_leg", "@c_m_clock"),
        "s_h": ("fred.wshotsl", quarter_clock),
        "b": ("trc_quarterly_components_v1:trc_fed_bridge", "z1_calendar_quarter"),
        "n_rrp_others": ("fred.wlrraol less trc_quarterly_components_v1:mmf_route_*",
                         "factor:h41_last_wednesday;route:calendar_quarter_fund_month_sum"),
        "sum_other_factors": ("H.4.1 Table 1 factor rows other than TGA, SFP, Treasury securities, RRP others", quarter_clock),
        "bridge_outcome": ("y_z - y_h", "z1_calendar_quarter_transactions vs h41_last_wednesday"),
        "bridge_outcome_term_deposits": ("fred.termt", quarter_clock),
        "bridge_outcome_z1_flow_vs_level": ("Z.1 FU713113003 (admitted) - d Z.1 FL713113003", "z1_calendar_quarter"),
        "bridge_outcome_unattributed": ("d Z.1 FL713113003 - fred.wrbwfrbl - fred.termt",
                                        "z1_quarter_end_level vs h41_last_wednesday"),
        "bridge_cash": ("c_h - c_m", "h41_last_wednesday vs @c_m_clock"),
        "bridge_securities": ("s_h - b", "h41_last_wednesday vs z1_calendar_quarter"),
        "rho": ("fred.wrbwfrbl less all factor rows", quarter_clock),
        "memo_s_h_inflation_compensation": ("fred.wshoicl", quarter_clock),
    }
    return {
        "weekly": {column: {"source": source, "clock": weekly_clock} for column, source in h41.items()},
        "quarterly": {column: {"source": source, "clock": quarter_clock} for column, source in h41.items()
                      if not column.startswith("gap_") and column not in {"rho_level", "published_identity_gap"}},
        "bridges": {
            **{column: {"source": source, "clock": clock} for column, (source, clock) in bridge.items()},
            **{column: {"source": source, "clock": quarter_clock} for column, source in sources.items()
               if column.startswith("f_")},
        },
    }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_reserve_factor_ledger_export(
    *, root: Path | str, inputs_manifest_sha256: str, trc_components_sha256: str,
    vintage: MeasurementVintage = DEFAULT_VINTAGE,
) -> dict:
    """Bind the ledger to a clean commit, the pinned fiscus manifest, and the admitted TRC components."""
    registry = fiscus_registries(vintage)["h41-ledger"]
    paths = project_paths(root)
    root = paths.root
    producer_commit = require_clean_commit(root)
    manifest_path = root / registry.manifest
    manifest_raw, manifest_record = read_pinned_input(root, manifest_path, inputs_manifest_sha256, "inputs_manifest")
    manifest = json.loads(manifest_raw)
    frames, input_records = load_fiscus_inputs(root, manifest, registry)
    components_path = paths.processed / TRC_OUTPUT_FILES["components"]
    components_raw, components_record = read_pinned_input(
        root, components_path, trc_components_sha256, "trc_quarterly_components_v1")
    trc_receipt_path = paths.processed / TRC_OUTPUT_FILES["receipt"]
    trc_receipt_raw = trc_receipt_path.read_bytes()
    trc_receipt = json.loads(trc_receipt_raw)
    if trc_receipt.get("outputs", {}).get("components", {}).get("sha256") != trc_components_sha256:
        raise ValueError("TRC components: hash is not the one the TRC receipt admits")

    output_paths = {role: paths.processed / name for role, name in LEDGER_OUTPUT_FILES.items()}
    protected = {manifest_path.resolve(), components_path.resolve(), trc_receipt_path.resolve()} | {
        (root / record["file"]).resolve() for record in input_records.values()
    } | {(paths.processed / name).resolve() for name in TRC_OUTPUT_FILES.values()}
    if {path.resolve() for path in output_paths.values()} & protected:
        raise ValueError("Output paths cannot overwrite inputs or admitted TRC outputs")

    result = build_reserve_factor_ledger(frames, pd.read_csv(io.BytesIO(components_raw)), vintage)
    payloads = {
        role: getattr(result, role).to_csv(index=False, lineterminator="\n").encode("utf-8")
        for role in ["weekly", "quarterly", "bridges"]
    }
    rows = load_h41_rows()
    receipt = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "producer_commit": producer_commit,
        "vintage": vintage.name,
        "units": "USD million",
        "inputs": {
            "inputs_manifest": {**manifest_record, "fiscus": manifest.get("fiscus", {}),
                                "acquired_at_utc": manifest.get("acquired_at_utc")},
            "fiscus_inputs": input_records,
            "trc_quarterly_components_v1": components_record,
            "trc_quarterly_series_v1_receipt": {
                "path": str(trc_receipt_path.relative_to(root)), "sha256": _sha256(trc_receipt_raw),
                "producer_commit": trc_receipt.get("producer_commit")},
        },
        "outputs": {role: {"path": str(output_paths[role].relative_to(root)), "sha256": _sha256(data)}
                    for role, data in payloads.items()},
        "factor_map": [
            {"key": key, "series_id": entry.row.series_id, "label": entry.row.label, "parent": entry.row.parent,
             "role": entry.row.role, "side": {1: "supplying", -1: "absorbing", 0: "outcome"}[entry.side],
             "introduced": entry.row.introduced, "discontinued": entry.row.discontinued,
             "terminal_nonzero": entry.row.terminal_nonzero, **result.stats["coverage"][key]}
            for key, entry in rows.items()
        ],
        "definitions": DEFINITIONS,
        "weekly_sample": result.stats["weekly_sample"],
        "closure": {"weekly": result.stats["weekly_closure"], "quarterly": result.stats["quarterly"]},
        "bridges": result.stats["bridges"],
        "bridge_summary_by_era": result.stats["bridge_summary_by_era"],
        "column_clocks": column_clocks(rows),
        "boundaries": BOUNDARIES,
    }
    for role, data in payloads.items():
        output_paths[role].parent.mkdir(parents=True, exist_ok=True)
        output_paths[role].write_bytes(data)
    output_paths["receipt"].write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return receipt
