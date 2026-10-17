"""Monthly TRC on a last-Wednesday clock, with the money-fund ON RRP route term.

A month runs from the last Wednesday of the previous calendar month to the last
Wednesday of this one, so every week belongs to the month of its Wednesday and
the monthly reserve change is the change between those H.4.1 Wednesdays. Core
TRC and its cash leg are sums of the published weekly components; a month is
reported only when every one of its weeks has core TRC. The money-fund route
term is the calendar-month sum of the fund-month adjustments from SEC Form
N-MFP (month-end holdings), the same fund-months whose quarterly sums enter the
quarterly preferred TRC, so the two clocks differ by at most the days between
the last Wednesday and month end. Before the ON RRP mechanism (2013-09) the
route is zero by definition; after the last filed month it is missing.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

ON_RRP_START = pd.Period("2013-09", freq="M")
WEEKLY = "trc_weekly_components_v1.csv"
FUND_MONTH = "tdc_mmf_rrp_fund_month_adjustments.csv"
QUARTERLY = "trc_quarterly_components_v1.csv"
OUTPUT = "trc_monthly_v1.csv"
RECEIPT = "trc_monthly_v1_receipt.json"
WEEKLY_SUMS = ("trc_core", "trc_par_sensitivity", "c_h", "delta_reserve_balances")
ROUTES = {"lb": "mmf_rrp_adjustment_lb", "prop": "mmf_rrp_adjustment_prop", "ub": "mmf_rrp_adjustment_ub"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def monthly_routes(fund_month: pd.DataFrame) -> pd.DataFrame:
    """Calendar-month sums of fund-month route adjustments (USD million)."""
    frame = fund_month.copy()
    frame["month"] = pd.to_datetime(frame["date"], errors="raise").dt.to_period("M")
    if frame.duplicated(["month", "fund_id"]).any():
        raise ValueError("fund-month adjustments: duplicate fund-months")
    sums = frame.groupby("month")[list(ROUTES.values())].sum(min_count=1)
    sums.columns = [f"mmf_route_{k}" for k in ROUTES]
    return sums


def build_monthly(weekly: pd.DataFrame, fund_month: pd.DataFrame) -> pd.DataFrame:
    w = weekly.copy()
    w["date"] = pd.to_datetime(w["date"], errors="raise")
    if (w["date"].dt.weekday != 2).any() or w["date"].duplicated().any() or not w["date"].is_monotonic_increasing:
        raise ValueError("weekly components must be unique ordered Wednesdays")
    if (w["date"].diff().dropna() != pd.Timedelta(days=7)).any():
        raise ValueError("weekly components must be consecutive weeks")
    w["month"] = w["date"].dt.to_period("M")
    # The first and last months are kept only if they are complete calendar months of Wednesdays.
    first_full = w["month"].iloc[0] if w["date"].iloc[0].day <= 7 else w["month"].iloc[0] + 1
    last_full = w["month"].iloc[-1] if (w["date"].iloc[-1] + pd.Timedelta(days=7)).month != w["date"].iloc[-1].month else w["month"].iloc[-1] - 1
    # A month's opening level is the previous month's last Wednesday, so the first full month needs a prior week.
    w = w[(w["month"] > first_full - 1) & (w["month"] <= last_full)]
    groups = w.groupby("month")
    out = pd.DataFrame({
        "start_wednesday": groups["date"].min() - pd.Timedelta(days=7),
        "end_wednesday": groups["date"].max(),
        "weeks": groups.size(),
        "weeks_with_core": groups["trc_core"].count(),
        "reserve_balances_start": groups["reserve_balances_start"].first(),
        "reserve_balances_end": groups["reserve_balances_end"].last(),
    })
    for name in WEEKLY_SUMS:
        out[name] = groups[name].sum(min_count=1)
    complete = out["weeks_with_core"].eq(out["weeks"])
    out.loc[~complete, ["trc_core", "trc_par_sensitivity"]] = np.nan
    if not out["weeks"].between(4, 5).all():
        raise ValueError("every month must hold four or five Wednesdays")
    level_gap = (out["reserve_balances_end"] - out["reserve_balances_start"] - out["delta_reserve_balances"]).abs()
    if level_gap.max() > 1e-6:
        raise ValueError(f"weekly reserve changes do not sum to the monthly level change (max gap {level_gap.max()})")
    routes = monthly_routes(fund_month)
    out = out.join(routes, how="left")
    active = out.index >= ON_RRP_START
    out["mmf_route_status"] = np.where(active, "observed_one_sided", "structural_zero_pre_on_rrp_mechanism")
    for key in ROUTES:
        column = f"mmf_route_{key}"
        out.loc[~active, column] = 0.0
    out.loc[active & out["mmf_route_prop"].isna(), "mmf_route_status"] = "unavailable_after_last_filed_month"
    out["trc_preferred"] = out["trc_core"] + out["mmf_route_prop"]
    out["trc_mmf_lower"] = out["trc_core"] + out["mmf_route_lb"]
    out["trc_mmf_upper"] = out["trc_core"] + out["mmf_route_ub"]
    out.index.name = "month"
    return out.reset_index().assign(month=lambda f: f["month"].astype(str),
                                    start_wednesday=lambda f: f["start_wednesday"].dt.date.astype(str),
                                    end_wednesday=lambda f: f["end_wednesday"].dt.date.astype(str))


def quarterly_route_check(monthly: pd.DataFrame, quarterly: pd.DataFrame) -> float:
    """Monthly route terms summed by calendar quarter must equal the quarterly preferred-TRC route term."""
    m = monthly.set_index(pd.PeriodIndex(monthly["month"], freq="M"))["mmf_route_prop"].dropna()
    by_quarter = m.groupby(m.index.asfreq("Q")).sum()
    q = quarterly.set_index(pd.PeriodIndex(quarterly["quarter"], freq="Q"))["mmf_route_prop"]
    full = [p for p in by_quarter.index if (m.index.asfreq("Q") == p).sum() == 3 and p in q.index]
    gap = float((by_quarter.loc[full] - q.loc[full]).abs().max())
    if not full or gap > 1e-6:
        raise ValueError(f"monthly route terms do not reproduce the quarterly route term (max gap {gap})")
    return gap


def export(processed: Path, out_dir: Path) -> dict:
    """Read the processed vintage, write the monthly table and receipt to a new directory; never edits the vintage."""
    repository = Path(__file__).resolve().parents[2]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=repository, text=True)
    if dirty.strip():
        raise ValueError("commit the producer before exporting retained evidence")
    processed, out_dir = Path(processed), Path(out_dir)
    if out_dir.exists():
        raise FileExistsError(f"{out_dir} exists; move it aside before exporting")
    inputs = {name: processed / name for name in (WEEKLY, FUND_MONTH, QUARTERLY)}
    monthly = build_monthly(pd.read_csv(inputs[WEEKLY]), pd.read_csv(inputs[FUND_MONTH]))
    gap = quarterly_route_check(monthly, pd.read_csv(inputs[QUARTERLY]))
    out_dir.mkdir(parents=True)
    target = out_dir / OUTPUT
    monthly.to_csv(target, index=False, lineterminator="\n")
    receipt = {
        "schema_version": "trc_monthly_v1",
        "producer_commit": commit,
        "processed_root": str(processed.resolve()),
        "clock": "last Wednesday to last Wednesday; money-fund route on the calendar month (N-MFP month-end)",
        "inputs": {name: {"sha256": _sha256(path), "bytes": path.stat().st_size} for name, path in inputs.items()},
        "outputs": {OUTPUT: {"sha256": _sha256(target), "bytes": target.stat().st_size, "rows": len(monthly)}},
        "checks": {"weekly_reserve_sum_equals_level_change": True,
                   "monthly_route_sums_reproduce_quarterly_route_max_gap": gap},
        "coverage": {"first_month": monthly["month"].iloc[0], "last_month": monthly["month"].iloc[-1],
                     "first_month_with_core": monthly.loc[monthly["trc_core"].notna(), "month"].iloc[0],
                     "last_month_with_route": monthly.loc[monthly["mmf_route_prop"].notna(), "month"].iloc[-1]},
    }
    (out_dir / RECEIPT).write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt
