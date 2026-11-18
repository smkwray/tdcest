"""Treasury-Federal Reserve internal transfers that move Treasury operating cash.

Two kinds of payment run between the Treasury General Account and accounts the
Federal Reserve consolidates, so neither reaches a covered deposit or a reserve
balance:

* facility equity: Treasury equity paid into the Federal Reserve credit-facility
  LLCs and later returned, DTS Table II category ``ESF - Economic Recovery
  Programs``. A posting carries facility equity only when it matches a change in
  the H.4.1 Treasury-contributions liability within the lookback window and
  tolerance of ``catalog.TREASURY_FED_TRANSFER_RULES``. The internal part of a
  matched receipt is the equity principal (the H.4.1 change) plus components that
  ``catalog.TREASURY_FED_SETTLEMENT_EXCEPTIONS`` documents as Federal Reserve-account
  settlements; any other excess stays in the cash term. Every other posting in the
  category is unclassified ESF cash and stays in the cash term.
* LLC Treasury securities: the LLCs' purchases and redemptions of nonmarketable
  Domestic Series securities (MSPD holder class ``SPV Demand``), DTS Table
  III-A. Domestic Series redemptions of zero-coupon bonds at their MSPD maturity
  are a different holder and stay in TDC. Reinvested interest is issued as new
  securities without moving the Treasury cash balance.

Each posting carries its effect on Treasury operating cash in USD million on its
DTS date: negative when equity leaves Treasury cash or an LLC redeems, positive
when equity returns or an LLC buys. The internal-transfer cash change is the sum
of the internal parts. Inputs fail closed: every DTS publication date must carry
both Domestic Series lines, each daily amount must equal its fiscal-year-to-date
step, the LLC holdings implied by DTS must equal the Z.1 level at every quarter
end within published rounding, and every H.4.1 contribution change must find its
DTS cash.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .catalog import (
    DEFAULT_VINTAGE,
    TREASURY_FED_SETTLEMENT_EXCEPTIONS,
    TREASURY_FED_TRANSFER_RULES as RULES,
    MeasurementVintage,
    fiscus_registries,
)
from .config import project_paths
from .reserve_factor_ledger import _sha256
from .tier2_regression_series import read_pinned_input, require_clean_commit
from .trc_export import load_fiscus_inputs
from .trc_reserve_component import _numeric

SCHEMA_VERSION = "treasury_fed_transfers_v1"
SUPPORT_KEY = "treasury_fed_internal_cash_tx"
SUPPORT_FILE = f"support__{SUPPORT_KEY}.csv"
OUTPUT_FILES = {
    "postings": "treasury_fed_transfers_postings_v1.csv",
    "quarterly": "treasury_fed_transfers_quarterly_v1.csv",
    "weekly": "treasury_fed_transfers_weekly_v1.csv",
    "receipt": "treasury_fed_transfers_v1_receipt.json",
}
ESF_INPUT = ("weekly-trc", "internal_dts")
CALENDAR_INPUT = ("weekly-trc", "remittances")  # DTS Table II row published on every DTS date
CONTRIBUTIONS_INPUT = ("h41-ledger", "treasury_contributions_to_credit_facilities")
# Source families of the postings; the classification column names what each posting is.
ESF, DOMESTIC = "esf_economic_recovery", "domestic_series"
LLC_INTERNAL_CLASSES = {"llc_purchase", "llc_redemption"}
ESF_CALENDAR_LABEL = "DTS ESF economic-recovery cash"
DEFINITIONS = {
    "cash_effect": "Effect on Treasury operating cash, USD million, on the DTS record date",
    "internal_cash_effect": "Part of cash_effect that is a Treasury-Fed internal transfer and leaves the cash term",
    "retained_cash_effect": "Part of an ESF posting's cash_effect that stays in the cash term",
    "equity_principal_cash": "Share of the matched H.4.1 Treasury-contributions change a posting carries, capped at its cash",
    "equity_reduced_without_cash": "Matched H.4.1 equity reduction beyond the matched cash; it moved no Treasury cash",
    "facility_equity_payment / facility_equity_return": "DTS ESF economic-recovery posting matched to an H.4.1 "
                                                         "Treasury-contributions change; internal part = equity "
                                                         "principal plus documented Federal Reserve-account settlements",
    "facility_earnings_documented": "Unmatched ESF posting that a settlement exception documents",
    "esf_unclassified": "Unclassified ESF cash retained in the cash term; counterparty and settlement account unverified",
    "settlement_status": {
        "equity_principal": "cash equals the equity principal",
        "equity_principal_rounding": "cash differs from the equity principal by no more than the rounding of two "
                                     "published millions; the whole posting is principal",
        "equity_principal_shortfall": "cash is smaller than the equity reduction; all of it is principal and the "
                                      "rest of the reduction moved no Treasury cash",
        "facility_earnings_settlement_account_unverified_retained": "facility earnings, settlement account "
                                                                    "unverified (retained)",
        "facility_earnings_documented_fed_settlement": "excess documented as Federal Reserve-account settlement; internal",
        "facility_earnings_commercial_settlement_documented_retained": "excess documented as commercial-bank "
                                                                       "settlement; retained",
        "facility_earnings_split_documented": "excess split by documented settlement account",
        "unclassified_retained": "unclassified ESF cash; retained",
    },
    "llc_purchase / llc_redemption": "Domestic Series issue or redemption of the LLCs' nonmarketable holdings",
    "llc_capitalized_interest": "Domestic Series issue of reinvested interest; Treasury credits the interest and the "
                                "issue in the same amount, so the cash balance is unchanged",
    "zero_coupon_maturity": "Domestic Series redemption of zero-coupon bonds at their MSPD maturity; another holder, "
                            "stays in TDC",
    "domestic_series_before_llc": "Domestic Series posting before the LLCs held any; another holder, stays in TDC",
    "internal_cash_tx": "Sum of internal_cash_effect: the internal-transfer cash change the TDC and TRC cash terms remove",
}
BOUNDARIES = [
    "Accounting classification of dated public postings; no estimation or causal interpretation",
    "Facility equity is identified only by a dated match to the H.4.1 Treasury-contributions liability. The internal "
    "part of a matched receipt is the equity principal plus components the settlement-exception table documents as "
    "Federal Reserve-account settlements; undocumented excess stays in the cash term",
    "LLC Treasury securities are identified by the MSPD holder class; zero-coupon Domestic Series maturities stay "
    "in TDC",
    "Quarters before the DTS windows are zero because the H.4.1 contribution liability is zero on every Wednesday "
    "from its first observation (2002-12-18) to the start of the DTS ESF window and the Z.1 LLC holdings level is zero "
    "at both quarter ends; no Treasury-funded credit facility existed before 2020",
    "SDR certificate monetizations credit the Exchange Stabilization Fund's Federal Reserve account and have no DTS "
    "Table II posting; their cash incidence through a later ESF investment is unresolved pending a DTS Table III-A "
    "to III-B reconciliation, so they stay outside this ledger and remain candidates in weekly TRC",
    "ESF cash is checked for date completeness against the DTS publication calendar but not against its "
    "fiscal-year-to-date totals, which carry revisions",
]


@dataclass(frozen=True)
class TransferLedger:
    postings: pd.DataFrame
    matches: pd.DataFrame
    quarterly: pd.DataFrame
    weekly: pd.DataFrame
    stats: dict


def query_window(argv: tuple[str, ...]) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Record-date bounds of a FiscalData request in a registry argv."""
    query = next(v.removeprefix("filter=") for v in argv if v.startswith("filter="))
    bounds = {}
    for part in query.split(","):
        if part.startswith("record_date:"):
            _, op, value = part.split(":", 2)
            bounds[op] = pd.Timestamp(value)
    return bounds["gte"], bounds["lte"]


def esf_postings(frame: pd.DataFrame) -> pd.DataFrame:
    """Signed nonzero DTS ESF economic-recovery postings; malformed rows raise."""
    required = {"record_date", "account_type", "transaction_type", "transaction_catg", "transaction_today_amt"}
    if required - set(frame.columns):
        raise ValueError(f"DTS ESF cash: missing columns {sorted(required - set(frame.columns))}")
    rows = frame.loc[frame["transaction_catg"].eq(RULES.esf_category)]
    if len(rows) != len(frame):
        raise ValueError("DTS ESF cash: rows outside the economic-recovery category")
    if not rows["account_type"].isin(RULES.tga_accounts).all():
        raise ValueError(f"DTS ESF cash: unknown accounts {sorted(set(rows['account_type']) - set(RULES.tga_accounts))}")
    if not rows["transaction_type"].isin(["Withdrawals", "Deposits"]).all():
        raise ValueError("DTS ESF cash: unknown transaction type")
    if rows.duplicated(["record_date", "account_type", "transaction_type"]).any():
        raise ValueError("DTS ESF cash: duplicate account/date/type")
    amount = _numeric(rows["transaction_today_amt"], "DTS ESF cash")
    out = pd.DataFrame({
        "date": pd.to_datetime(rows["record_date"], format="%Y-%m-%d", errors="raise"),
        "family": ESF, "source": "dts_table_ii_esf_economic_recovery",
        "dts_line": rows["transaction_type"] + ":" + rows["account_type"], "amount": amount,
        "cash_effect": np.where(rows["transaction_type"].eq("Withdrawals"), -amount, amount),
    })
    return out.loc[out["cash_effect"].ne(0)].sort_values("date", kind="stable").reset_index(drop=True)


def wednesday_levels(frame: pd.DataFrame, label: str) -> pd.Series:
    dates = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise")
    if dates.duplicated().any() or not dates.dt.weekday.eq(2).all():
        raise ValueError(f"{label}: observations must be unique Wednesdays")
    series = pd.Series(_numeric(frame["value"], label).to_numpy(), index=pd.DatetimeIndex(dates)).sort_index()
    if not series.index.to_series().diff().dropna().eq(pd.Timedelta(days=7)).all():
        raise ValueError(f"{label}: Wednesdays must be consecutive")
    return series


def match_facility_equity(esf: pd.DataFrame, contributions: pd.Series, window_start: pd.Timestamp
                          ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Assign every H.4.1 contribution change the dated DTS postings that carry its cash.

    Changes are taken in date order. For each, the candidates are unassigned postings of the
    matching sign dated in the lookback window ending on its Wednesday; the smallest set whose
    cash is within tolerance of the change wins, the closest sum and then the latest dates
    breaking ties. A change with no such set raises.
    """
    esf = esf.copy()
    esf["match_wednesday"] = pd.NaT
    esf["equity_principal_cash"] = 0.0
    esf["equity_reduced_without_cash"] = 0.0
    changes = contributions.diff().dropna()
    changes = changes.loc[changes.ne(0)]
    records = []
    for wednesday, change in changes.items():
        start = wednesday - pd.Timedelta(days=RULES.equity_lookback_days)
        if start < window_start:
            raise ValueError(f"H.4.1 Treasury contributions change on {wednesday.date()}: lookback starts before "
                             f"the DTS ESF window {window_start.date()}")
        target = -change
        pool = esf.loc[esf["match_wednesday"].isna() & esf["date"].gt(start) & esf["date"].le(wednesday)
                       & (np.sign(esf["cash_effect"]) == np.sign(target))]
        tolerance = RULES.equity_match_rounding + RULES.equity_match_relative_tolerance * abs(target)
        best = None
        for size in range(1, min(RULES.equity_match_max_postings, len(pool)) + 1):
            for combo in combinations(pool.index, size):
                gap = abs(float(pool.loc[list(combo), "cash_effect"].sum()) - target)
                if gap <= tolerance:
                    key = (gap, -sum(pool.loc[i, "date"].value for i in combo))
                    if best is None or key < best[0]:
                        best = (key, combo)
            if best is not None:
                break
        if best is None:
            raise ValueError(f"H.4.1 Treasury contributions change {change:+,.0f} on {wednesday.date()} has no "
                             f"dated DTS ESF cash within {RULES.equity_lookback_days} days and tolerance {tolerance:,.1f}")
        combo = sorted(best[1], key=lambda i: esf.loc[i, "date"])
        esf.loc[combo, "match_wednesday"] = wednesday
        remaining = abs(target)  # equity principal, assigned to the postings in date order
        for i in combo:
            share = min(abs(esf.loc[i, "cash_effect"]), remaining)
            esf.loc[i, "equity_principal_cash"] = np.sign(target) * share
            remaining -= share
        esf.loc[combo, "equity_reduced_without_cash"] = remaining
        cash = float(esf.loc[combo, "cash_effect"].sum())
        records.append({
            "h41_wednesday": wednesday, "h41_contributions_change": float(change), "matched_cash_effect": cash,
            "cash_minus_equity_change": cash - target, "tolerance": tolerance, "n_postings": len(combo),
            "posting_dates": "|".join(str(d.date()) for d in esf.loc[combo, "date"]),
        })
    esf["classification"] = np.where(
        esf["match_wednesday"].isna(), "esf_unclassified",
        np.where(esf["cash_effect"] < 0, "facility_equity_payment", "facility_equity_return"))
    return esf, pd.DataFrame(records)


def exceptions_frame(exceptions) -> pd.DataFrame:
    frame = pd.DataFrame([vars(e) for e in exceptions],
                         columns=["facility", "date", "amount", "settling_account", "component", "treatment", "source"])
    if not frame["treatment"].isin(["internal", "retained"]).all() or (frame["amount"] <= 0).any():
        raise ValueError("settlement exceptions: treatment must be internal or retained and amounts positive")
    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise")
    return frame


def settle_esf(esf: pd.DataFrame, exceptions: pd.DataFrame) -> pd.DataFrame:
    """Split each ESF posting into the part that leaves the cash term and the part that stays.

    Matched postings: principal plus documented Federal Reserve-account settlements are internal.
    A posting within rounding of its principal, or smaller than it, is all principal. Undocumented
    excess stays in the cash term. Unmatched postings stay unless an exception documents them.
    Documented components must reconcile to the excess (or, unmatched, to the cash) within rounding,
    and every exception must fall on an ESF posting.
    """
    esf = esf.copy()
    rounding = RULES.equity_match_rounding
    used = set()
    internal, documented_fed, documented_retained, status = [], [], [], []
    for i, row in esf.iterrows():
        docs = exceptions.loc[exceptions["date"].eq(row["date"])]
        used.update(docs.index)
        sign = np.sign(row["cash_effect"])
        doc_fed = sign * float(docs.loc[docs["treatment"].eq("internal"), "amount"].sum()) + 0.0
        doc_kept = sign * float(docs.loc[docs["treatment"].eq("retained"), "amount"].sum()) + 0.0
        principal = row["equity_principal_cash"]
        base = principal if pd.notna(row["match_wednesday"]) else 0.0
        residual = row["cash_effect"] - base
        if len(docs):
            if abs(residual - doc_fed - doc_kept) > rounding:
                raise ValueError(f"settlement exceptions on {row['date'].date()} total {doc_fed + doc_kept:,.3f} "
                                 f"against {residual:,.3f} of cash beyond equity principal")
            value = base + doc_fed
            state = ("facility_earnings_documented_fed_settlement" if not doc_kept else
                     "facility_earnings_commercial_settlement_documented_retained" if not doc_fed else
                     "facility_earnings_split_documented")
        elif pd.isna(row["match_wednesday"]):
            value, state = 0.0, "unclassified_retained"
        elif residual == 0:
            # Principal is capped at the cash; an equity change larger than the cash moved no more Treasury cash.
            short = row["equity_reduced_without_cash"]
            value = row["cash_effect"]
            state = ("equity_principal_shortfall" if short > rounding else
                     "equity_principal_rounding" if short > 0 else "equity_principal")
        elif abs(residual) <= rounding:
            value, state = row["cash_effect"], "equity_principal_rounding"
        else:
            value, state = principal, "facility_earnings_settlement_account_unverified_retained"
        internal.append(value)
        documented_fed.append(doc_fed)
        documented_retained.append(doc_kept)
        status.append(state)
    stale = exceptions.loc[~exceptions.index.isin(sorted(used))]
    if len(stale):
        raise ValueError(f"settlement exceptions without an ESF posting: {stale['date'].dt.strftime('%Y-%m-%d').tolist()}")
    esf["documented_fed_cash"] = documented_fed
    esf["documented_retained_cash"] = documented_retained
    esf["internal_cash_effect"] = internal
    esf["retained_cash_effect"] = esf["cash_effect"] - esf["internal_cash_effect"]
    esf["settlement_status"] = status
    documented = esf["match_wednesday"].isna() & ~esf["settlement_status"].eq("unclassified_retained")
    esf.loc[documented, "classification"] = "facility_earnings_documented"
    return esf


def check_publication_calendar(dates: pd.Series, calendar: pd.DatetimeIndex, calendar_window: tuple,
                               window: tuple, label: str, *, start: pd.Timestamp | None = None) -> None:
    """Every DTS publication date in the window (from ``start`` if given) carries a row, and no other date does."""
    lo = max(window[0], calendar_window[0], start if start is not None else window[0])
    if calendar_window[1] < window[1] or (dates < calendar_window[0]).any():
        raise ValueError(f"{label}: the DTS publication calendar does not cover the input window")
    expected = calendar[(calendar >= lo) & (calendar <= window[1])]
    got = pd.DatetimeIndex(dates.unique())
    got = got[(got >= lo) & (got <= window[1])]
    missing, extra = expected.difference(got), got.difference(expected)
    if len(missing) or len(extra):
        raise ValueError(f"{label}: dates differ from the DTS publication calendar; missing "
                         f"{[str(d.date()) for d in missing[:5]]}, not published {[str(d.date()) for d in extra[:5]]}")


def _dedupe(frame: pd.DataFrame, keys: list[str], label: str) -> pd.DataFrame:
    duplicated = frame.duplicated(keys, keep=False)
    if duplicated.any() and frame.loc[duplicated].drop_duplicates().duplicated(keys).any():
        raise ValueError(f"{label}: conflicting duplicate rows for {frame.loc[duplicated, keys].head(3).values.tolist()}")
    return frame.drop_duplicates()


def domestic_series_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Every DTS Table III-A Domestic Series row, including zero days, with numeric amounts."""
    required = {"record_date", "security_market", "security_type", "transaction_type", "transaction_today_amt",
                "transaction_fytd_amt", "record_fiscal_year"}
    if required - set(frame.columns):
        raise ValueError(f"DTS Domestic Series: missing columns {sorted(required - set(frame.columns))}")
    rows = frame[sorted(required)].copy()
    if not (rows["security_type"].eq(RULES.domestic_series_class).all()
            and rows["security_market"].eq("Nonmarketable").all()):
        raise ValueError("DTS Domestic Series: rows of another security type")
    if not rows["transaction_type"].isin(["Issues", "Redemptions"]).all():
        raise ValueError("DTS Domestic Series: unknown transaction type")
    rows = _dedupe(rows, ["record_date", "transaction_type"], "DTS Domestic Series")
    rows["date"] = pd.to_datetime(rows["record_date"], format="%Y-%m-%d", errors="raise")
    rows["amount"] = _numeric(rows["transaction_today_amt"], "DTS Domestic Series today")
    rows["fytd"] = _numeric(rows["transaction_fytd_amt"], "DTS Domestic Series fiscal year to date")
    rows["fiscal_year"] = rows["record_fiscal_year"].astype(int)
    if (rows["amount"] < 0).any():
        raise ValueError("DTS Domestic Series: negative daily amount")
    if not rows["fiscal_year"].eq(rows["date"].dt.year + (rows["date"].dt.month >= 10)).all():
        raise ValueError("DTS Domestic Series: record_fiscal_year disagrees with the record date")
    complete = rows.groupby("date")["transaction_type"].agg(lambda s: sorted(s) == ["Issues", "Redemptions"])
    if not complete.all():
        raise ValueError(f"DTS Domestic Series: dates without both Issues and Redemptions "
                         f"{[str(d.date()) for d in complete.index[~complete][:5]]}")
    rows = rows.sort_values(["transaction_type", "date"]).reset_index(drop=True)
    # Each daily amount is the step in its fiscal-year-to-date total; the first row of a fiscal year
    # steps from zero. Two rounded totals and one rounded amount bound the gap.
    previous = rows.groupby(["transaction_type", "fiscal_year"])["fytd"].shift().fillna(0.0)
    first_row = rows.groupby("transaction_type").cumcount().eq(0)
    starts_fy = rows["date"].eq(rows.groupby(["transaction_type", "fiscal_year"])["date"].transform("min"))
    step_gap = (rows["fytd"] - previous - rows["amount"]).abs()
    checked = ~first_row | (rows["date"].dt.month.eq(10) & rows["date"].dt.day.le(7) & starts_fy)
    breach = checked & step_gap.gt(RULES.domestic_series_fytd_step_rounding)
    if breach.any():
        bad = rows.loc[breach].head(3)
        raise ValueError("DTS Domestic Series: daily amounts disagree with fiscal-year-to-date steps at "
                         f"{list(zip(bad['record_date'], bad['transaction_type'], step_gap[breach].head(3).round(3)))}")
    return rows.sort_values(["date", "transaction_type"]).reset_index(drop=True)


def mspd_domestic_series(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Zero-coupon maturities (amount outstanding before maturity) and the first month the LLCs held securities.

    Every Domestic Series row must belong to the LLC class, the zero-coupon class or a declared
    other-holder class, and the classes must add to the published Domestic Series total every
    month. An outstanding amount MSPD prints as below USD 0.5 million counts as zero and widens
    that month's tolerance by its half million.
    """
    required = {"record_date", "security_class1_desc", "security_class2_desc", "maturity_date",
                "current_month_outstanding_amt", "src_line_nbr"}
    if required - set(frame.columns):
        raise ValueError(f"MSPD Domestic Series: missing columns {sorted(required - set(frame.columns))}")
    rows = _dedupe(frame[sorted(required)].copy(), ["record_date", "src_line_nbr"], "MSPD Domestic Series")
    rows["record_date"] = pd.to_datetime(rows["record_date"], format="%Y-%m-%d", errors="raise")
    below = rows["current_month_outstanding_amt"].eq(RULES.mspd_below_half_million)
    rows["outstanding"] = _numeric(rows["current_month_outstanding_amt"].mask(below, "0"),
                                   "MSPD Domestic Series outstanding")
    rows["below_half_million"] = below
    totals = rows.loc[rows["security_class1_desc"].eq(RULES.domestic_series_total_class)]
    detail = rows.loc[rows["security_class1_desc"].eq(RULES.domestic_series_class)]
    if len(totals) + len(detail) != len(rows):
        raise ValueError("MSPD Domestic Series: rows outside the Domestic Series classes")
    llc = detail["security_class2_desc"].eq(RULES.llc_mspd_class)
    zero = detail["security_class2_desc"].str.startswith(RULES.zero_coupon_mspd_prefix)
    other = detail["security_class2_desc"].isin(RULES.other_holder_mspd_classes)
    if not (llc | zero | other).all():
        raise ValueError(f"MSPD Domestic Series: unknown holder classes {sorted(set(detail.loc[~(llc | zero | other), 'security_class2_desc']))}")
    if (llc | zero).loc[detail["below_half_million"]].any() or totals["below_half_million"].any():
        raise ValueError("MSPD Domestic Series: an LLC, zero-coupon or total amount is printed below half a million")
    by_month = detail.groupby("record_date")["outstanding"].sum()
    tolerance = 0.01 + 0.5 * detail.groupby("record_date")["below_half_million"].sum()
    total = totals.set_index("record_date")["outstanding"]
    if totals["record_date"].duplicated().any() or not by_month.index.equals(total.sort_index().index):
        raise ValueError("MSPD Domestic Series: every month needs one total row and its detail")
    if ((by_month - total.reindex(by_month.index)).abs() > tolerance).any():
        raise ValueError("MSPD Domestic Series: holder classes do not add to the published total")
    zeros = detail.loc[zero].copy()
    zeros["maturity"] = pd.to_datetime(zeros["maturity_date"], format="%Y-%m-%d", errors="raise")
    before = zeros.loc[zeros["record_date"] < zeros["maturity"]]
    last = before.groupby("maturity")["record_date"].transform("max")
    maturities = before.loc[before["record_date"].eq(last)].groupby("maturity")["outstanding"].sum()
    llc_months = detail.loc[llc & detail["outstanding"].ne(0), "record_date"]
    first_llc_month = llc_months.min().to_period("M").start_time if len(llc_months) else pd.NaT
    return maturities.rename("amount").reset_index(), first_llc_month


def classify_domestic_series(rows: pd.DataFrame, maturities: pd.DataFrame, first_llc_month: pd.Timestamp
                             ) -> pd.DataFrame:
    """Nonzero Domestic Series postings by holder; LLC issues split into purchases and reinvested interest."""
    postings = rows.loc[rows["amount"].ne(0)].copy()
    postings["family"] = DOMESTIC
    postings["source"] = "dts_table_iiia_domestic_series"
    postings["dts_line"] = postings["transaction_type"]
    postings["cash_effect"] = np.where(postings["transaction_type"].eq("Issues"), postings["amount"], -postings["amount"])
    postings["classification"] = ""
    dts_days = pd.DatetimeIndex(sorted(rows["date"].unique()))
    window = (dts_days.min(), dts_days.max())
    redemptions = postings["transaction_type"].eq("Redemptions")
    for maturity, amount in maturities.itertuples(index=False):
        if not window[0] <= maturity <= window[1]:
            continue
        payment_day = dts_days[dts_days >= maturity].min()
        hit = postings.index[redemptions & postings["date"].eq(payment_day)
                             & (postings["amount"] - amount).abs().le(RULES.zero_coupon_match_rounding)]
        if len(hit) != 1:
            raise ValueError(f"MSPD zero-coupon maturity {maturity.date()} ({amount:,.3f}) has no unique DTS redemption")
        postings.loc[hit, "classification"] = "zero_coupon_maturity"
    unassigned = postings["classification"].eq("")
    before_llc = postings["date"] < first_llc_month if pd.notna(first_llc_month) else pd.Series(True, index=postings.index)
    postings.loc[unassigned & before_llc, "classification"] = "domestic_series_before_llc"
    outstanding, last_issue = 0.0, None
    for i in postings.index[postings["classification"].eq("")]:
        row = postings.loc[i]
        if row["transaction_type"] == "Redemptions":
            postings.loc[i, "classification"] = "llc_redemption"
            outstanding -= row["amount"]
            continue
        days = max(1, (row["date"] - last_issue).days) if last_issue is not None else 1
        bound = (RULES.capitalized_interest_rounding
                 + RULES.capitalized_interest_max_annual_rate * max(outstanding, 0.0) * days / 365.0)
        postings.loc[i, "classification"] = "llc_capitalized_interest" if row["amount"] <= bound else "llc_purchase"
        outstanding += row["amount"]
        last_issue = row["date"]
    return postings[["date", "family", "source", "dts_line", "amount", "cash_effect", "classification"]]


def reconcile_llc_holdings(rows: pd.DataFrame, postings: pd.DataFrame, z1_level: pd.Series,
                           quarters: pd.PeriodIndex) -> pd.DataFrame:
    """DTS-implied LLC holdings against the Z.1 level at every quarter end; outside rounding raises.

    The DTS level sums fiscal-year-to-date issues less redemptions over the fiscal years since the
    LLCs' first posting and removes the other holders' postings, so each quarter carries only the
    rounding of the totals it uses: half a million per total, per removed posting and for Z.1.
    """
    llc = postings.loc[postings["classification"].str.startswith("llc_")]
    other = postings.loc[postings["family"].eq(DOMESTIC) & ~postings["classification"].str.startswith("llc_")]
    first = llc["date"].min() if len(llc) else None
    out = []
    for quarter in quarters:
        z1 = z1_level.get(quarter)
        if z1 is None or pd.isna(z1):
            raise ValueError(f"Z.1 LLC holdings level missing for {quarter}")
        row = {"quarter": str(quarter), "z1_llc_treasury_level": float(z1)}
        if first is None or quarter < first.to_period("Q"):
            if z1 != 0:
                raise ValueError(f"Z.1 LLC holdings {z1:,.0f} at {quarter} before any DTS LLC posting")
            out.append({**row, "dts_llc_treasury_level": 0.0, "reconciliation_gap": 0.0 - float(z1),
                        "reconciliation_tolerance": 0.5, "reconciliation_status": "zero_before_llc_holdings"})
            continue
        day = rows.loc[rows["date"] <= quarter.end_time, "date"].max()
        if (quarter.end_time.normalize() - day).days > 6:
            raise ValueError(f"DTS Domestic Series has no final business day for {quarter}")
        fy_first, fy_now = int(rows.loc[rows["date"].eq(first), "fiscal_year"].iloc[0]), int(
            rows.loc[rows["date"].eq(day), "fiscal_year"].iloc[0])
        level, n_totals = 0.0, 0
        for line, sign in (("Issues", 1.0), ("Redemptions", -1.0)):
            line_rows = rows.loc[rows["transaction_type"].eq(line)]
            for fy in range(fy_first, fy_now):
                closing = line_rows.loc[line_rows["fiscal_year"].eq(fy)]
                level += sign * float(closing.loc[closing["date"].idxmax(), "fytd"])
                n_totals += 1
            level += sign * float(line_rows.loc[line_rows["date"].eq(day), "fytd"].iloc[0])
            n_totals += 1
        fy_start = pd.Timestamp(year=fy_first - 1, month=10, day=1)
        removed = other.loc[other["date"].ge(fy_start) & other["date"].le(day)]
        level -= float(removed["cash_effect"].sum())
        tolerance = 0.5 * (n_totals + len(removed) + 1)
        gap = level - float(z1)
        if abs(gap) > tolerance:
            raise ValueError(f"DTS LLC holdings {level:,.1f} differ from Z.1 {z1:,.0f} at {quarter} by {gap:,.1f} "
                             f"(rounding bound {tolerance})")
        out.append({**row, "dts_llc_treasury_level": level, "reconciliation_gap": gap,
                    "reconciliation_tolerance": tolerance, "reconciliation_status": "reconciled_within_rounding"})
    return pd.DataFrame(out)


def _z1_levels(frame: pd.DataFrame) -> pd.Series:
    dates = pd.to_datetime(frame["date"], format="%Y-%m-%d", errors="raise")
    if not dates.eq(dates.dt.to_period("Q").dt.end_time.dt.normalize()).all() or dates.duplicated().any():
        raise ValueError("Z.1 LLC holdings: dates must be unique quarter ends")
    return pd.Series(_numeric(frame["value"], "Z.1 LLC holdings").to_numpy(), index=pd.PeriodIndex(dates, freq="Q"))


def _sums(frame: pd.DataFrame, key: str) -> pd.DataFrame:
    """Per-period internal-transfer cash, ESF cash left in the cash term and other-holder Domestic Series cash."""
    esf = frame.loc[frame["family"].eq(ESF)]
    kept = esf.loc[esf["retained_cash_effect"].ne(0)]
    facility_kept = kept.loc[~kept["classification"].eq("esf_unclassified")]
    unclassified = esf.loc[esf["classification"].eq("esf_unclassified")]
    labels = kept["date"].dt.strftime("%Y-%m-%d") + ":" + kept["retained_cash_effect"].map("{:g}".format)
    domestic = frame.loc[frame["family"].eq(DOMESTIC)]
    return pd.DataFrame({
        "facility_internal_cash_tx": esf.groupby(key)["internal_cash_effect"].sum(),
        "llc_treasury_securities_cash_tx": domestic.groupby(key)["internal_cash_effect"].sum(),
        "llc_capitalized_interest_memo": domestic.loc[domestic["classification"].eq("llc_capitalized_interest")
                                                      ].groupby(key)["amount"].sum(),
        "other_domestic_series_cash_tx": domestic.loc[domestic["classification"].isin(
            ["zero_coupon_maturity", "domestic_series_before_llc"])].groupby(key)["cash_effect"].sum(),
        "n_internal_postings": frame.loc[frame["internal_cash_effect"].ne(0)].groupby(key).size(),
        "esf_cash_tx": esf.groupby(key)["cash_effect"].sum(),
        "esf_retained_cash_tx": esf.groupby(key)["retained_cash_effect"].sum(),
        "esf_retained_abs": kept["retained_cash_effect"].abs().groupby(kept[key]).sum(),
        "facility_receipt_retained_tx": facility_kept.groupby(key)["retained_cash_effect"].sum(),
        "esf_unclassified_cash_tx": unclassified.groupby(key)["cash_effect"].sum(),
        "esf_retained_dates": labels.groupby(kept[key]).agg("|".join),
    })


ZERO_COLUMNS = ["facility_internal_cash_tx", "llc_treasury_securities_cash_tx", "llc_capitalized_interest_memo",
                "other_domestic_series_cash_tx", "n_internal_postings"]
ESF_COLUMNS = ["esf_cash_tx", "esf_retained_cash_tx", "esf_retained_abs", "facility_receipt_retained_tx",
               "esf_unclassified_cash_tx"]


def _period_table(postings: pd.DataFrame, key: str, labels: pd.Index, esf_covered: np.ndarray) -> pd.DataFrame:
    """Sums on an explicit calendar: internal terms are zero without postings; ESF cash is blank outside its window."""
    table = pd.DataFrame(index=labels).join(_sums(postings, key))
    table[ZERO_COLUMNS] = table[ZERO_COLUMNS].fillna(0.0)
    for column in ESF_COLUMNS:
        table[column] = table[column].where(~esf_covered, table[column].fillna(0.0))
    table["esf_retained_dates"] = table["esf_retained_dates"].fillna("")
    table["internal_cash_tx"] = table["facility_internal_cash_tx"] + table["llc_treasury_securities_cash_tx"]
    return table


def _esf_retained_window(postings: pd.DataFrame, end: pd.Timestamp | None) -> dict:
    esf = postings.loc[postings["family"].eq(ESF) & (postings["date"].le(end) if end is not None else True)]
    kept = esf.loc[esf["retained_cash_effect"].ne(0)]
    unclassified = esf.loc[esf["classification"].eq("esf_unclassified")]
    facility = kept.loc[~kept["classification"].eq("esf_unclassified")]
    return {
        "through": str(end.date()) if end is not None else str(esf["date"].max().date()),
        "esf_unclassified": {"n": int(len(unclassified)), "net": float(unclassified["cash_effect"].sum()),
                             "abs": float(unclassified["cash_effect"].abs().sum())},
        "facility_receipts_retained": {"n": int(len(facility)), "net": float(facility["retained_cash_effect"].sum())},
        "esf_retained_total": {"n": int(len(kept)), "net": float(kept["retained_cash_effect"].sum())},
    }


def build_treasury_fed_transfers(
    *, esf_frame: pd.DataFrame, esf_window: tuple[pd.Timestamp, pd.Timestamp], contributions_frame: pd.DataFrame,
    domestic_series_frame: pd.DataFrame, domestic_series_window: tuple[pd.Timestamp, pd.Timestamp],
    mspd_frame: pd.DataFrame, z1_frame: pd.DataFrame, calendar_frame: pd.DataFrame,
    calendar_window: tuple[pd.Timestamp, pd.Timestamp], vintage: MeasurementVintage = DEFAULT_VINTAGE,
    exceptions=TREASURY_FED_SETTLEMENT_EXCEPTIONS,
) -> TransferLedger:
    calendar = pd.DatetimeIndex(sorted(pd.to_datetime(calendar_frame["record_date"], format="%Y-%m-%d",
                                                      errors="raise").unique()))
    if not len(calendar):
        raise ValueError("DTS publication calendar is empty")
    contributions = wednesday_levels(contributions_frame, "H.4.1 Treasury contributions")
    if contributions.loc[contributions.index < esf_window[0]].ne(0).any():
        raise ValueError("H.4.1 Treasury contributions are nonzero before the DTS ESF window")
    if contributions.index.max() < min(esf_window[1], pd.Timestamp(vintage.weekly_end)):
        raise ValueError("H.4.1 Treasury contributions end before the DTS ESF window")
    esf = esf_postings(esf_frame)
    if len(esf) and not (esf_window[0] <= esf["date"].min() and esf["date"].max() <= esf_window[1]):
        raise ValueError("DTS ESF cash: postings outside the query window")
    esf_dates = pd.to_datetime(esf_frame["record_date"], format="%Y-%m-%d", errors="raise")
    if len(esf_dates):
        # The category begins with the 2020 facilities; from its first row every publication date carries it.
        check_publication_calendar(esf_dates, calendar, calendar_window, esf_window, ESF_CALENDAR_LABEL,
                                   start=esf_dates.min())
    esf, matches = match_facility_equity(esf, contributions, esf_window[0])
    esf = settle_esf(esf, exceptions_frame(exceptions))
    rows = domestic_series_rows(domestic_series_frame)
    if not (domestic_series_window[0] <= rows["date"].min() and rows["date"].max() <= domestic_series_window[1]):
        raise ValueError("DTS Domestic Series: rows outside the query window")
    check_publication_calendar(rows["date"], calendar, calendar_window, domestic_series_window, "DTS Domestic Series")
    maturities, first_llc_month = mspd_domestic_series(mspd_frame)
    llc = classify_domestic_series(rows, maturities, first_llc_month)
    quarters = pd.period_range(RULES.start_quarter, vintage.quarter_end, freq="Q")
    reconciliation = reconcile_llc_holdings(rows, llc, _z1_levels(z1_frame), quarters)

    llc = llc.assign(
        match_wednesday="", equity_principal_cash=0.0, equity_reduced_without_cash=0.0, documented_fed_cash=0.0,
        documented_retained_cash=0.0,
        internal_cash_effect=np.where(llc["classification"].isin(LLC_INTERNAL_CLASSES), llc["cash_effect"], 0.0),
        retained_cash_effect=0.0, settlement_status="")
    postings = pd.concat([
        esf.assign(match_wednesday=esf["match_wednesday"].dt.strftime("%Y-%m-%d").fillna("")), llc,
    ], ignore_index=True)
    postings = postings[["date", "family", "source", "dts_line", "amount", "cash_effect", "match_wednesday",
                         "classification", "equity_principal_cash", "equity_reduced_without_cash", "documented_fed_cash",
                         "documented_retained_cash", "internal_cash_effect", "retained_cash_effect", "settlement_status"]]
    postings = postings.sort_values(["date", "family", "dts_line"], kind="stable").reset_index(drop=True)
    postings["quarter"] = postings["date"].dt.to_period("Q").astype(str)
    postings["week_ending"] = (postings["date"] + pd.to_timedelta((2 - postings["date"].dt.weekday) % 7, unit="D")
                               ).dt.strftime("%Y-%m-%d")

    # Quarters: every quarter of the support series, each leg on a stated basis.
    q_start, q_end = quarters.start_time, quarters.end_time.normalize()
    esf_full = np.asarray((q_start >= esf_window[0]) & (q_end <= esf_window[1]))
    esf_before = np.asarray(q_end < esf_window[0])
    if (~esf_full & ~esf_before).any():
        raise ValueError(f"DTS ESF window covers only part of {[str(q) for q in quarters[~esf_full & ~esf_before]]}")
    dts_full = np.asarray((q_start >= domestic_series_window[0]) & (q_end <= domestic_series_window[1]))
    dts_before = np.asarray(q_end < domestic_series_window[0])
    if (~dts_full & ~dts_before).any():
        raise ValueError(f"DTS Domestic Series window covers only part of {[str(q) for q in quarters[~dts_full & ~dts_before]]}")
    quarterly = _period_table(postings, "quarter", pd.Index(quarters.astype(str)), esf_full)
    quarterly["equity_basis"] = np.where(esf_full, "dts_esf_postings_matched_to_h41",
                                         "zero_h41_contribution_liability_zero_before_dts_window")
    quarterly["llc_basis"] = np.where(dts_full, "dts_domestic_series_postings_reconciled_to_z1",
                                      "zero_z1_llc_level_zero_before_dts_window")
    quarterly = quarterly.join(reconciliation.set_index("quarter"))
    quarterly.insert(0, "date", q_end.strftime("%Y-%m-%d"))
    quarterly.index.name = "quarter"
    quarterly = quarterly.reset_index()
    if not np.isfinite(quarterly["internal_cash_tx"].to_numpy(dtype=float)).all():
        raise ValueError("internal-transfer cash change missing in a quarter")

    # H.4.1 Wednesday weeks (Thursday through Wednesday) from the second published Wednesday.
    weeks = pd.date_range(contributions.index[1], vintage.weekly_end, freq="W-WED")
    week_start = weeks - pd.Timedelta(days=6)
    esf_week = np.asarray((week_start >= esf_window[0]) & (weeks <= esf_window[1]))
    weekly = _period_table(postings, "week_ending", pd.Index(weeks.strftime("%Y-%m-%d")), esf_week)
    liability_zero = np.asarray(contributions.reindex(weeks).eq(0) & contributions.shift().reindex(weeks).eq(0))
    if (~esf_week & ~liability_zero).any():
        raise ValueError("H.4.1 Treasury contributions change in a week the DTS ESF window does not cover")
    weekly["equity_basis"] = np.where(esf_week, "dts_esf_postings_matched_to_h41", "zero_h41_contribution_liability_zero")
    dts_week = np.asarray((week_start >= domestic_series_window[0]) & (weeks <= domestic_series_window[1]))
    weekly["llc_basis"] = np.where(dts_week, "dts_domestic_series_postings", "zero_z1_llc_level_zero_before_dts_window")
    weekly.index.name = "date"
    weekly = weekly.reset_index()
    weekly.insert(1, "start_wednesday", (weeks - pd.Timedelta(days=7)).strftime("%Y-%m-%d"))
    internal_dates = postings.loc[postings["internal_cash_effect"].ne(0), "date"]
    if len(internal_dates) and (internal_dates.min() <= weeks[0] - pd.Timedelta(days=7) or internal_dates.max() > weeks[-1]):
        raise ValueError("internal-transfer postings fall outside the weekly calendar")
    late = postings.loc[postings["date"].gt(q_end[-1])]

    matched = postings.loc[postings["match_wednesday"].ne("") | postings["classification"].eq("facility_earnings_documented")]
    receipts = [{
        "date": str(r.date.date()), "match_wednesday": r.match_wednesday, "classification": r.classification,
        "cash": float(r.cash_effect), "equity_principal": float(r.equity_principal_cash),
        "cash_minus_principal": float(r.cash_effect - r.equity_principal_cash),
        "equity_reduced_without_cash": float(r.equity_reduced_without_cash),
        "documented_fed": float(r.documented_fed_cash), "documented_retained": float(r.documented_retained_cash),
        "internal": float(r.internal_cash_effect), "retained": float(r.retained_cash_effect),
        "settlement_status": r.settlement_status,
    } for r in matched.itertuples()]
    stats = {
        "postings_by_classification": {
            name: {"n": int(len(g)), "cash_effect": float(g["cash_effect"].sum()),
                   "internal_cash_effect": float(g["internal_cash_effect"].sum()),
                   "first": str(g["date"].min().date()), "last": str(g["date"].max().date())}
            for name, g in postings.groupby("classification")},
        "facility_equity_matches": {
            "n_h41_changes": int(len(matches)),
            "max_abs_cash_minus_equity_change": float(matches["cash_minus_equity_change"].abs().max()) if len(matches) else 0.0,
            "max_relative_deviation": float((matches["cash_minus_equity_change"].abs()
                                             / matches["h41_contributions_change"].abs()).max()) if len(matches) else 0.0,
            "multi_posting_matches": [f"{r['posting_dates']}->{r['h41_wednesday'].date()}"
                                      for r in matches.to_dict("records") if r["n_postings"] > 1],
        },
        "facility_receipts": receipts,
        "esf_retained": {"through_quarter_end": _esf_retained_window(postings, q_end[-1]),
                         "through_data_end": _esf_retained_window(postings, None)},
        "esf_unclassified_by_year": {str(y): float(v) for y, v in postings.loc[
            postings["classification"].eq("esf_unclassified")].groupby(
            postings["date"].dt.year)["cash_effect"].sum().items()},
        "llc_capitalized_interest_total": float(postings.loc[
            postings["classification"].eq("llc_capitalized_interest"), "amount"].sum()),
        "first_llc_month": str(first_llc_month.date()) if pd.notna(first_llc_month) else None,
        "zero_coupon_maturities_in_dts_window": [f"{d.date()}:{v:g}" for d, v in postings.loc[
            postings["classification"].eq("zero_coupon_maturity"), ["date", "cash_effect"]].itertuples(index=False)],
        "z1_reconciliation_max_abs_gap": float(reconciliation["reconciliation_gap"].abs().max()),
        "z1_reconciliation_max_ratio_to_bound": float((reconciliation["reconciliation_gap"].abs()
                                                       / reconciliation["reconciliation_tolerance"]).max()),
        "internal_cash_tx_quarterly_total": float(quarterly["internal_cash_tx"].sum()),
        "internal_cash_after_quarterly_window": float(late["internal_cash_effect"].sum()),
        "dts_windows": {"esf": [str(esf_window[0].date()), str(esf_window[1].date())],
                        "domestic_series": [str(domestic_series_window[0].date()), str(domestic_series_window[1].date())],
                        "publication_calendar": [str(calendar.min().date()), str(calendar.max().date()), int(len(calendar))]},
    }
    postings["date"] = postings["date"].dt.strftime("%Y-%m-%d")
    if len(matches):
        matches = matches.assign(h41_wednesday=matches["h41_wednesday"].dt.strftime("%Y-%m-%d"))
    return TransferLedger(postings=postings, matches=matches, quarterly=quarterly, weekly=weekly, stats=stats)


def support_frame(quarterly: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"date": quarterly["date"], "value": quarterly["internal_cash_tx"]})


def write_treasury_fed_transfer_export(
    *, root: Path | str, inputs_manifest_sha256: str, weekly_trc_manifest_sha256: str,
    h41_ledger_manifest_sha256: str, vintage: MeasurementVintage = DEFAULT_VINTAGE,
) -> dict:
    """Bind the ledger to a clean commit and three pinned fiscus manifests; write outputs and the support file."""
    registries = fiscus_registries(vintage)
    paths = project_paths(root)
    root = paths.root
    producer_commit = require_clean_commit(root)
    frames, manifests, inputs = {}, {}, {}
    for name, expected in [("treasury-fed-transfers", inputs_manifest_sha256), ("weekly-trc", weekly_trc_manifest_sha256),
                           ("h41-ledger", h41_ledger_manifest_sha256)]:
        registry = registries[name]
        raw, record = read_pinned_input(root, root / registry.manifest, expected, f"{name} inputs_manifest")
        manifest = json.loads(raw)
        loaded, records = load_fiscus_inputs(root, manifest, registry)
        frames[name] = loaded
        manifests[name] = {**record, "fiscus": manifest.get("fiscus", {}), "acquired_at_utc": manifest.get("acquired_at_utc")}
        inputs[name] = records
    def window(registry: str, key: str) -> tuple[pd.Timestamp, pd.Timestamp]:
        return query_window(next(s for s in registries[registry].inputs if s.key == key).argv)

    ledger = build_treasury_fed_transfers(
        esf_frame=frames[ESF_INPUT[0]][ESF_INPUT[1]], esf_window=window(*ESF_INPUT),
        contributions_frame=frames[CONTRIBUTIONS_INPUT[0]][CONTRIBUTIONS_INPUT[1]],
        domestic_series_frame=frames["treasury-fed-transfers"]["dts_domestic_series"],
        domestic_series_window=window("treasury-fed-transfers", "dts_domestic_series"),
        mspd_frame=frames["treasury-fed-transfers"]["mspd_domestic_series"],
        z1_frame=frames["treasury-fed-transfers"]["z1_llc_treasury_level"],
        calendar_frame=frames[CALENDAR_INPUT[0]][CALENDAR_INPUT[1]], calendar_window=window(*CALENDAR_INPUT),
        vintage=vintage,
    )
    exception_rows = [vars(e) for e in TREASURY_FED_SETTLEMENT_EXCEPTIONS]
    output_paths = {role: paths.processed / name for role, name in OUTPUT_FILES.items()}
    support_path = paths.raw / SUPPORT_FILE
    payloads = {role: getattr(ledger, role).to_csv(index=False, lineterminator="\n").encode("utf-8")
                for role in ["postings", "quarterly", "weekly"]}
    payloads["support"] = support_frame(ledger.quarterly).to_csv(index=False, lineterminator="\n").encode("utf-8")
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "producer_commit": producer_commit,
        "vintage": vintage.name,
        "units": "USD million; effect on Treasury operating cash",
        "inputs": {"manifests": manifests, "fiscus_inputs": inputs},
        "outputs": {role: {"path": str(output_paths[role].relative_to(root)), "sha256": _sha256(data)}
                    for role, data in payloads.items() if role != "support"}
                   | {"support": {"path": str(support_path.relative_to(root)), "sha256": _sha256(payloads["support"])}},
        "support_series": {"key": SUPPORT_KEY, "first_quarter": ledger.quarterly["quarter"].iloc[0],
                           "last_quarter": ledger.quarterly["quarter"].iloc[-1],
                           "rule": "every quarter carries an explicit value; quarters before the DTS windows are "
                                   "zero on the observed bases named in the quarterly table, not filled"},
        "rules": {key: value for key, value in vars(RULES).items()},
        "settlement_exceptions": {"sha256": _sha256(json.dumps(exception_rows, sort_keys=True).encode("utf-8")),
                                  "rows": exception_rows},
        "publication_calendar": {"input": f"{CALENDAR_INPUT[0]}:{CALENDAR_INPUT[1]}",
                                 "rule": "every DTS publication date carries both Domestic Series lines and, from its "
                                         "first row, the ESF economic-recovery line"},
        "facility_equity_matches": ledger.matches.to_dict("records"),
        "stats": ledger.stats,
        "definitions": DEFINITIONS,
        "boundaries": BOUNDARIES,
    }
    for role, data in payloads.items():
        path = support_path if role == "support" else output_paths[role]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    output_paths["receipt"].write_text(json.dumps(receipt, indent=2, allow_nan=False, default=str) + "\n",
                                       encoding="utf-8")
    return receipt


def read_weekly_ledger(raw: bytes) -> pd.DataFrame:
    frame = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False)
    required = {"date", "facility_internal_cash_tx", "llc_treasury_securities_cash_tx", "internal_cash_tx",
                "esf_cash_tx", "esf_retained_cash_tx", "esf_retained_abs", "esf_retained_dates", "equity_basis",
                "llc_basis"}
    if required - set(frame.columns):
        raise ValueError(f"Treasury-Fed weekly ledger: missing columns {sorted(required - set(frame.columns))}")
    if frame["date"].duplicated().any():
        raise ValueError("Treasury-Fed weekly ledger: duplicate weeks")
    return frame.set_index("date")
