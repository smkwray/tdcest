"""Cash-corrected weekly Treasury reserve proxy on the Thursday–Wednesday clock.

Snapshot differences identify net positions, not gross transactions. Auction
allotments remove primary transfers from the secondary-market classification.
Core includes the net primary and redemption offset to the TGA cash leg. The
all-securities premium/discount factor is a named valuation bridge, not an
identified Treasury cash-price correction. Closure is accounting reconciliation,
not evidence validating a security's classification or transaction price.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
import calendar
import hashlib
import io
import json
from pathlib import Path

import pandas as pd
from pandas.tseries.holiday import (
    AbstractHolidayCalendar,
    Holiday,
    USMartinLutherKingJr,
    USPresidentsDay,
    USMemorialDay,
    USLaborDay,
    USColumbusDay,
    USThanksgivingDay,
    sunday_to_monday,
)

from .catalog import (
    DEFAULT_VINTAGE, WEEKLY_TRC_INTERNAL_MATCHES, WEEKLY_TRC_REGISTRY, MeasurementVintage, fiscus_registries,
)
from .mmf_rrp import ON_RRP_OPERATION_START
from .reserve_factor_ledger import CASH_KEYS, RRP_OTHER_KEY, load_h41_rows
from .tier2_regression_series import read_pinned_input, require_clean_commit
from .trc_export import load_fiscus_inputs, TRC_OUTPUT_FILES
from .reserve_factor_ledger import LEDGER_OUTPUT_FILES
from .treasury_support import extract_dts_operating_cash_balance

D = Decimal
ZERO = D(0)
MILLION = D(1000000)
CENT_MILLION = D("0.00000001")
def eras(quarter_end):
    """Reporting eras; the last runs to the final complete Wednesday quarter of the vintage."""
    return (
        ("2006Q1", "2008Q3"),
        ("2008Q4", "2008Q4"),
        ("2009Q1", "2015Q4"),
        ("2016Q1", quarter_end),
    )

OUTPUTS = {
    "weekly": "trc_weekly_components_v1.csv",
    "quarterly": "trc_weekly_quarterly_v1.csv",
    "identity": "trc_weekly_identity_v1.csv",
    "classification": "trc_weekly_soma_changes_v1.csv",
    "daily_route": "trc_weekly_route_daily_v1.csv",
    "receipt": "trc_weekly_v1_receipt.json",
}
CLASSIFICATION_RULE = (
    "Net snapshot partition including auction-only CUSIPs. Primary cash uses auction settlement fields; "
    "maturity cash assumes no intervening trade in opening holdings. Residuals are NET secondary par, "
    "with gross churn and prices unobserved. Missing expected auction records remain unclassifiable. "
    "Rollover memo matches payment and issue settlement dates, not weekly minima."
)
BOUNDARIES = [
    "Core is a cash-corrected public-data proxy with supported adjustments only, not an exact settlement flow.",
    "Core coverage cannot begin before 2005-10-12; first potentially complete Wednesday quarter is 2006Q1.",
    "Admitted H.4.1 cash and factors are unchanged; no monthly fund holdings or weekly preferred series.",
    "Primary cash includes discount, price, indexed principal and accrued interest. Missing corrections have statuses and unresolved par magnitudes; the par sensitivity is retained.",
    "Redemption quantities assume no intervening trade. TIPS maturity principal uses max(par, indexed par) on the nominal maturity index date; published contractual reference CPI is preferred; current CPI reconstruction is a proxy where those values are absent.",
    "Coupons are payment-date proxies on prior-week positions plus known primary allotments settling strictly before payment. Secondary entitlement is unobserved.",
    "TIPS coupon index date is the nominal coupon date; holiday-shifted payment date assigns the cash week. Published auction references supply nominal payment-date CPI where available; issue ratios independently cross-check the reconstruction.",
    "FRN rates carry through a documented no-auction interval within the complete auction-query window; missing feed/rate observations remain unavailable. Published daily intervals start inclusive and end exclusive, with feed history from 2024-10-31.",
    "Dated ESF cash is inspected independently of stock changes only within its pinned query window; outside-window candidates are unavailable. Unmatched postings retain their cash dates. No adjacent-week matching is applied.",
    "J applies to dated DTS cash matched to the facility factor or an independently documented dated facility transfer; unmatched stock remainder stays candidate-only. Other stock changes, certificate special-account entries and unmatched DTS cash remain candidates, not zero-valued observed corrections.",
    "Coin, Treasury currency, Treasury cash holdings, IORB and FIMA lending remain outside core.",
    "Secondary activity stays par-valued, with net unpriced par reported; gross secondary cash and churn are not measured.",
    "All-securities premiums/discounts are a reconciliation bridge, never a Treasury cash-price estimator.",
    "ON RRP variants are signed same-day primary-bill channel scenarios with shared total-facility capacity, not MMF observations, TRC bounds or coefficient bounds. Zero is a no-route baseline.",
    "The net-bill/ON RRP overlap statistic is diagnostic only. Pre-2013 zeros declare facility scope.",
    "Identity closure and telescoping check accounting only; independent event-cash fixtures test measurement.",
]

EVENT_COLUMNS = (
    "date",
    "cusip",
    "security_type",
    "nominal_maturity_date",
    "payment_date",
    "issue_settlement_dates",
    "opening_par",
    "closing_par",
    "delta_par",
    "settlement_clock_adjustment",
    "redemptions_par",
    "redemptions_cash",
    "redemption_inflation",
    "primary_addons_par",
    "primary_addons_cash",
    "primary_cash_adjustment",
    "primary_cash_unavailable_par",
    "redemption_cash_unavailable_par",
    "secondary_purchases_par",
    "secondary_sales_par",
    "unclassifiable_par",
    "unclassifiable_abs_par",
    "event_type",
    "inflation_compensation_change_excluded",
    "classification_status",
    "primary_cash_status",
    "redemption_status",
    "gross_trade_status",
)


class FedPaymentCalendar(AbstractHolidayCalendar):
    # Federal Reserve Banks do not close on Friday for a Saturday fixed holiday.
    rules = [
        Holiday("New Year", month=1, day=1, observance=sunday_to_monday),
        USMartinLutherKingJr,
        USPresidentsDay,
        USMemorialDay,
        Holiday(
            "Juneteenth",
            month=6,
            day=19,
            start_date="2022-01-01",
            observance=sunday_to_monday,
        ),
        Holiday("Independence", month=7, day=4, observance=sunday_to_monday),
        USLaborDay,
        USColumbusDay,
        Holiday("Veterans", month=11, day=11, observance=sunday_to_monday),
        USThanksgivingDay,
        Holiday("Christmas", month=12, day=25, observance=sunday_to_monday),
    ]


def decimal(value, label="value") -> Decimal:
    try:
        out = D(str(value))
    except Exception as exc:
        raise ValueError(f"{label}: malformed required value {value!r}") from exc
    if not out.is_finite():
        raise ValueError(f"{label}: missing required value")
    return out


def money(value) -> Decimal:
    return value.quantize(CENT_MILLION, rounding=ROUND_HALF_UP)


def payment_day(day, holidays) -> pd.Timestamp:
    day = pd.Timestamp(day).normalize()
    while day.weekday() >= 5 or day in holidays:
        day += pd.Timedelta(days=1)
    return day


def wednesday(day) -> pd.Timestamp:
    day = pd.Timestamp(day).normalize()
    return day + pd.Timedelta(days=(2 - day.weekday()) % 7)


def snapshot_date_mapping(targets, asof_dates):
    """Prefer Wednesday; substitute only across (min(source,target), max(source,target)] closed days."""
    targets = sorted({pd.Timestamp(d).normalize() for d in targets})
    sources = sorted({pd.Timestamp(d).normalize() for d in asof_dates})
    if any(d.weekday() != 2 for d in targets):
        raise ValueError("SOMA: effective dates must be Wednesdays")
    if not targets or not sources:
        return {}
    holidays = set(
        FedPaymentCalendar().holidays(min(*targets, *sources), max(*targets, *sources))
    )
    mapping = {}
    for target in targets:
        lower = upper = target
        # Earlier sources may reach the open day immediately BEFORE a closed run.
        while lower.weekday() >= 5 or lower in holidays:
            lower -= pd.Timedelta(days=1)
        # Later sources may reach the last closed day, never the next open day.
        while (upper + pd.Timedelta(days=1)).weekday() >= 5 or upper + pd.Timedelta(
            days=1
        ) in holidays:
            upper += pd.Timedelta(days=1)
        eligible = [d for d in sources if lower <= d <= upper]
        if eligible:
            source = min(eligible, key=lambda d: (abs(d - target), d))
            mapping[target] = {
                "asof": str(source.date()),
                "effective_wednesday": str(target.date()),
                "substitution_reason": "exact_wednesday"
                if source == target
                else "unchanged_position_across_non_settlement_days",
            }
    return mapping


def prepare_soma(frame, targets=None):
    required = {
        "asOfDate",
        "cusip",
        "maturityDate",
        "parValue",
        "coupon",
        "securityType",
        "inflationCompensation",
    }
    if required - set(frame):
        raise ValueError(f"SOMA: missing columns {sorted(required - set(frame))}")
    frame = frame.copy()
    frame["asOfDate"] = pd.to_datetime(frame.asOfDate, errors="raise")
    frame["maturityDate"] = pd.to_datetime(frame.maturityDate, errors="raise")
    if frame.empty or frame.duplicated(["asOfDate", "cusip"]).any():
        raise ValueError("SOMA: empty or duplicate CUSIP/date")
    if (
        not set(frame.securityType) <= {"Bills", "NotesBonds", "TIPS", "FRNs"}
        or frame.cusip.eq("").any()
    ):
        raise ValueError("SOMA: unrecognized instrument or missing CUSIP")
    frame["par"] = frame.parValue.map(lambda v: decimal(v, "SOMA par") / MILLION)
    if frame.par.lt(0).any():
        raise ValueError("SOMA: negative par")
    # Coupons and inflation fields are inapplicable to bills and nominal securities respectively.
    frame["rate"] = [
        ZERO if t in ("Bills", "FRNs") else decimal(v, "SOMA coupon")
        for t, v in zip(frame.securityType, frame.coupon)
    ]
    frame["inflation"] = [
        decimal(v, "SOMA inflation") / MILLION if t == "TIPS" else ZERO
        for t, v in zip(frame.securityType, frame.inflationCompensation)
    ]
    if targets is None:
        first, last = frame.asOfDate.min(), frame.asOfDate.max()
        first -= pd.Timedelta(days=(first.weekday() - 2) % 7)
        targets = pd.date_range(first, wednesday(last), freq="W-WED")
    mapping = snapshot_date_mapping(targets, frame.asOfDate.unique())
    originals = {
        day: group.set_index("cusip") for day, group in frame.groupby("asOfDate")
    }
    return {
        target: originals[pd.Timestamp(record["asof"])]
        for target, record in mapping.items()
    }


def prepare_auctions(frame):
    required = {
        "cusip",
        "issue_date",
        "maturity_date",
        "security_type",
        "soma_accepted",
        "total_accepted",
        "price_per100",
        "auction_date",
        "security_term",
    }
    if required - set(frame) or frame.empty:
        raise ValueError("Auctions: missing required fields or empty input")
    frame = frame.copy()
    for c in ("issue_date", "maturity_date", "auction_date"):
        frame[c] = pd.to_datetime(frame[c], errors="raise")
    if frame.duplicated(["cusip", "issue_date"]).any() or frame.cusip.eq("").any():
        raise ValueError("Auctions: duplicate allotment or missing CUSIP")
    frame = frame.sort_values("issue_date")
    frame.attrs["auction_feed_window"] = (
        frame.auction_date.min(),
        frame.auction_date.max(),
    )
    frame.attrs["contractual_reference_cpi"] = contractual_cpi(frame)
    return frame


def contractual_cpi(auctions):
    """Date/reference CPI crosswalk from original dated-date bases and issue-date references.

    Reopening dated_date can be a later coupon date while its base CPI still
    refers to the original dated date. Only the first issue establishes that
    date/base pair; issue-date reference CPI is independently dated on each row.
    """
    if "inflation_index_security" not in auctions:
        return {}
    tips = auctions.loc[auctions.inflation_index_security.eq("Yes")]
    values = {}

    def add(day, value):
        if not present(day) or not present(value):
            return
        day = pd.Timestamp(day)
        value = decimal(value, "published reference CPI")
        if day in values and values[day] != value:
            raise ValueError(
                f"TIPS: conflicting contractual reference CPI on {day.date()}"
            )
        values[day] = value

    for _, g in tips.groupby("cusip"):
        first = g.sort_values("issue_date").iloc[0]
        dated = first.get("original_dated_date")
        if not present(dated):
            dated = first.get("dated_date")
        add(dated, first.get("ref_cpi_on_dated_date"))
    for _, row in tips.iterrows():
        add(row.issue_date, row.get("ref_cpi_on_issue_date"))
    return values


def present(value):
    return str(value) not in ("", "null", "nan", "None", "<NA>")


def primary_cash(row, par):
    """Auction cash in millions; adjusted TIPS fields are already indexed."""
    kind = row.security_type
    tips = str(row.get("inflation_index_security", "No")) == "Yes"
    if tips:
        if present(row.get("adj_price")):
            price = decimal(row.adj_price)
        else:
            price = decimal(row.get("unadj_price", row.price_per100)) * decimal(
                row.get("index_ratio_on_issue_date"), "TIPS issue ratio"
            )
        if present(row.get("adj_accrued_int_per1000")):
            accrued = decimal(row.adj_accrued_int_per1000) / D(10)
        elif present(row.get("unadj_accrued_int_per1000")):
            accrued = (
                decimal(row.unadj_accrued_int_per1000)
                / D(10)
                * decimal(row.index_ratio_on_issue_date)
            )
        else:
            accrued = acquisition_accrual(row) * decimal(row.index_ratio_on_issue_date)
    else:
        price = decimal(row.price_per100, "auction price")
        accrued = ZERO if kind == "Bill" else acquisition_accrual(row)
    if par < ZERO or price <= ZERO or accrued < ZERO:
        raise ValueError("invalid primary par, price or accrued interest")
    return money(par * (price + accrued) / D(100))


def acquisition_accrual(row):
    for field, divisor in (
        ("accrued_int_per100", D(1)),
        ("accrued_int_per1000", D(10)),
    ):
        if present(row.get(field)):
            return decimal(row[field], field) / divisor
    # A genuinely new issue dated on settlement has definitionally no accrued interest.
    if (
        present(row.get("dated_date"))
        and pd.Timestamp(row.dated_date) == row.issue_date
    ):
        return ZERO
    raise ValueError(
        "missing acquisition accrued interest and no same-day dated-date evidence"
    )


def redemption_cash(par, kind, cusip, nominal, auctions, cpi):
    ratio = tips_ratio(cusip, nominal, auctions, cpi) if kind == "TIPS" else D(1)
    return money(par * max(D(1), ratio))


def classify_week(
    start, end, opening, closing, auctions, holidays, cpi=None, deferred=None
):
    """Net partition; cash-price support and redemption entitlement are separate grades."""
    deferred = {} if deferred is None else deferred
    issued = auctions.loc[auctions.issue_date.gt(start) & auctions.issue_date.le(end)]
    records = []
    by_cusip = {cusip: group for cusip, group in issued.groupby("cusip")}
    empty_issued = issued.iloc[:0]
    for cusip in sorted(
        set(opening.index) | set(closing.index) | set(by_cusip) | set(deferred)
    ):
        a = opening.loc[cusip] if cusip in opening.index else None
        b = closing.loc[cusip] if cusip in closing.index else None
        matches = by_cusip.get(cusip, empty_issued)
        old, new = (
            (a.par if a is not None else ZERO),
            (b.par if b is not None else ZERO),
        )
        row = b if b is not None else (a if a is not None else deferred.get(cusip))
        if row is None:
            auction = matches.iloc[0]
            kind = (
                "Bills"
                if auction.security_type == "Bill"
                else (
                    "TIPS"
                    if auction.get("inflation_index_security") == "Yes"
                    else (
                        "FRNs"
                        if auction.get("floating_rate") == "Yes"
                        else "NotesBonds"
                    )
                )
            )
            maturity = auction.maturity_date
        else:
            kind, maturity = row.securityType, row.maturityDate
        paid = payment_day(maturity, holidays)
        entitlement = (
            old if old else (deferred[cusip].par if cusip in deferred else ZERO)
        )
        redemption = entitlement if start < paid <= end else ZERO
        clock_adjustment = (
            -entitlement if cusip in deferred and old == ZERO and redemption else ZERO
        )
        if old > new and start < maturity <= end < paid:
            clock_adjustment = old - new
        status = "classified_net_snapshot_change"
        primary, cash = ZERO, ZERO
        primary_status = "no_primary_event_in_complete_auction_query"
        if (
            a is not None
            and b is not None
            and (a.maturityDate != b.maturityDate or a.securityType != b.securityType)
        ):
            status = "unclassifiable_changed_security_metadata"
        if redemption and new:
            status = "unclassifiable_held_after_maturity"
        if old > new and start < maturity <= end < paid:
            status = "assumed_maturity_snapshot_payment_clock_no_intervening_trade"
        if not matches.empty:
            primary_status = "auction_cash_observed"
            for _, auction in matches.iterrows():
                if not present(auction.soma_accepted):
                    status = "unclassifiable_missing_soma_auction_allotment"
                    primary_status = "unavailable_soma_allotment"
                    cash = None
                    continue
                amount = decimal(auction.soma_accepted, "SOMA allotment") / MILLION
                primary += amount
                if amount:
                    try:
                        amount_cash = primary_cash(auction, amount)
                    except ValueError as exc:
                        primary_status = "unavailable_primary_cash:" + str(exc)
                        cash = None
                    else:
                        if cash is not None:
                            cash += amount_cash
        # A new issue in the snapshot implies an expected auction record. Its absence is not secondary evidence.
        history_missing = (
            a is None
            and b is not None
            and matches.empty
            and not auctions.cusip.eq(cusip).any()
        )
        expected = (
            a is None
            and b is not None
            and present(b.get("issueDate"))
            and start < pd.Timestamp(b.issueDate) <= end
        )
        if history_missing:
            status = "unclassifiable_missing_security_auction_history"
        if expected and matches.empty:
            status = "unclassifiable_missing_expected_auction_record"
            primary_status = "unavailable_expected_auction_record"
            cash = None
        delta = new - old
        residual = delta + clock_adjustment + redemption - primary
        inflation = (b.inflation if b is not None else ZERO) - (
            a.inflation if a is not None else ZERO
        )
        redcash, redstatus = ZERO, "no_redemption"
        if redemption:
            try:
                redcash = redemption_cash(
                    redemption, kind, cusip, maturity, auctions, cpi or {}
                )
                redstatus = (
                    (
                        "contractual_reference_cpi_no_intervening_trade"
                        if maturity
                        in auctions.attrs.get("contractual_reference_cpi", {})
                        else "reconstructed_cpi_proxy_no_intervening_trade"
                    )
                    if kind == "TIPS"
                    else "par_cash_no_intervening_trade"
                )
            except ValueError as exc:
                redcash, redstatus = None, "unavailable_redemption_cash:" + str(exc)
        if (
            delta
            or primary
            or redemption
            or inflation
            or status.startswith("unclassifiable")
            or cash is None
        ):
            unknown = status.startswith("unclassifiable")
            records.append(
                dict(
                    date=str(end.date()),
                    cusip=cusip,
                    security_type=kind,
                    nominal_maturity_date=str(maturity.date()),
                    payment_date=str(paid.date()),
                    issue_settlement_dates="|".join(
                        str(d.date()) for d in matches.issue_date
                    ),
                    opening_par=old,
                    closing_par=new,
                    delta_par=delta,
                    settlement_clock_adjustment=clock_adjustment,
                    redemptions_par=redemption,
                    redemptions_cash=redcash,
                    redemption_inflation=None
                    if redcash is None
                    else redcash - redemption,
                    primary_addons_par=primary,
                    primary_addons_cash=cash,
                    primary_cash_adjustment=None if cash is None else cash - primary,
                    primary_cash_unavailable_par=max(primary, abs(residual))
                    if cash is None
                    else ZERO,
                    redemption_cash_unavailable_par=redemption
                    if redcash is None
                    else ZERO,
                    secondary_purchases_par=None if unknown else max(residual, ZERO),
                    secondary_sales_par=None if unknown else max(-residual, ZERO),
                    unclassifiable_par=residual if unknown else ZERO,
                    unclassifiable_abs_par=abs(residual) if unknown else ZERO,
                    event_type=status.removeprefix("unclassifiable_")
                    if unknown
                    else "net_partition",
                    inflation_compensation_change_excluded=inflation,
                    classification_status=status,
                    primary_cash_status=primary_status,
                    redemption_status=redstatus,
                    gross_trade_status="unobserved_intraweek_gross_trades",
                )
            )
    if sum((r["delta_par"] for r in records), ZERO) != sum(closing.par, ZERO) - sum(
        opening.par, ZERO
    ):
        raise ValueError("SOMA partition does not equal snapshot net par")
    return records


def rollover_memo(changes, auctions):
    """Date-matched par memo; cash/par differences and reinvestment destinations remain separate."""
    red, primary = {}, {}
    for r in changes:
        day = r["payment_date"]
        red[day] = red.get(day, ZERO) + r["redemptions_par"]
    for _, a in auctions.iterrows():
        if present(a.soma_accepted):
            day = str(a.issue_date.date())
            primary[day] = primary.get(day, ZERO) + decimal(a.soma_accepted) / MILLION
    return sum((min(v, primary.get(d, ZERO)) for d, v in red.items()), ZERO)


def reference_cpi(day, cpi):
    day = pd.Timestamp(day)
    month = day.to_period("M")
    a, b = cpi.get(month - 3), cpi.get(month - 2)
    if a is None or b is None:
        raise ValueError(f"TIPS: missing CPI at {day.date()}")
    value = a + (b - a) * D(day.day - 1) / D(
        calendar.monthrange(day.year, day.month)[1]
    )
    return value.quantize(D("0.000001"), rounding=ROUND_DOWN).quantize(
        D("0.00001"), rounding=ROUND_HALF_UP
    )


def reconstructed_tips_ratio(cusip, day, auctions, cpi):
    master = auctions.loc[auctions.cusip.eq(cusip)].sort_values("issue_date")
    if master.empty or "ref_cpi_on_dated_date" not in master:
        raise ValueError(f"TIPS {cusip}: no dated-date reference CPI")
    bases = master.ref_cpi_on_dated_date.loc[
        ~master.ref_cpi_on_dated_date.isin(["", "null"])
    ]
    if bases.empty:
        raise ValueError(f"TIPS {cusip}: missing base CPI")
    base = decimal(bases.iloc[0], "TIPS base CPI")
    return (
        (reference_cpi(day, cpi) / base)
        .quantize(D("0.000001"), rounding=ROUND_DOWN)
        .quantize(D("0.00001"), rounding=ROUND_HALF_UP)
    )


def tips_ratio(cusip, day, auctions, cpi):
    """Prefer published contractual reference CPI on the nominal index date."""
    references = auctions.attrs.get("contractual_reference_cpi", {})
    master = auctions.loc[auctions.cusip.eq(cusip)].sort_values("issue_date")
    if master.empty or "ref_cpi_on_dated_date" not in master:
        raise ValueError(f"TIPS {cusip}: no dated-date reference CPI")
    bases = master.ref_cpi_on_dated_date.loc[master.ref_cpi_on_dated_date.map(present)]
    if bases.empty:
        raise ValueError(f"TIPS {cusip}: missing base CPI")
    if pd.Timestamp(day) not in references:
        return reconstructed_tips_ratio(cusip, day, auctions, cpi)
    return (
        (references[pd.Timestamp(day)] / decimal(bases.iloc[0]))
        .quantize(D("0.000001"), rounding=ROUND_DOWN)
        .quantize(D("0.00001"), rounding=ROUND_HALF_UP)
    )


def schedule_date(maturity, months):
    target = maturity - pd.DateOffset(months=months)
    return target + pd.offsets.MonthEnd(0) if maturity.is_month_end else target


def frn_coupon_per100(cusip, prev, nominal, paid, auctions, holidays):
    """31 CFR 356 Appendix B: nine-decimal index; two-business-day settlement/payment lockout."""
    master = auctions.loc[auctions.cusip.eq(cusip)]
    if master.empty or "spread" not in master or "high_discnt_rate" not in auctions:
        raise ValueError(f"FRN {cusip}: missing auction spread/index inputs")
    spreads = master.spread.loc[~master.spread.isin(["", "null"])]
    if spreads.empty or spreads.nunique() != 1:
        raise ValueError(f"FRN {cusip}: absent or inconsistent lifetime spread")
    spread = decimal(spreads.iloc[0], "FRN spread")
    bills = auctions.loc[
        auctions.security_type.eq("Bill") & auctions.security_term.eq("13-Week")
    ].sort_values("auction_date")
    # Reopenings also lock the published daily accrual index. An auction's reset
    # takes effect the next calendar day, so resets ON the lockout start are excluded.
    events = set(master.issue_date) | {payment_day(prev, holidays), paid}
    locks = []
    for event in events:
        if event < prev - pd.Timedelta(days=7) or event > paid:
            continue
        lock_start = event
        for _ in range(2):
            lock_start -= pd.Timedelta(days=1)
            while lock_start.weekday() >= 5 or lock_start in holidays:
                lock_start -= pd.Timedelta(days=1)
        locks.append((lock_start, event))
    value = ZERO
    for day in pd.date_range(prev, nominal - pd.Timedelta(days=1)):
        cutoff = min(
            [
                day,
                *[
                    begin - pd.Timedelta(days=1)
                    for begin, finish in locks
                    if begin <= day <= finish
                ],
            ]
        )
        eligible = bills.loc[bills.auction_date.lt(cutoff)]
        window = auctions.attrs.get("auction_feed_window")
        if (
            eligible.empty
            or window is None
            or not window[0] <= cutoff <= window[1] + pd.Timedelta(days=1)
        ):
            raise ValueError(f"FRN {cusip}: unavailable auction feed coverage")
        bill = eligible.iloc[-1]
        rate = decimal(bill.high_discnt_rate, "13-week high discount rate")
        term = D((bill.maturity_date - bill.issue_date).days)
        index = (rate / (D(1) - rate / D(100) * term / D(360))).quantize(
            D("0.000000001"), rounding=ROUND_HALF_UP
        )
        value += (max(index + spread, ZERO) / D(360)).quantize(
            D("0.000000001"), rounding=ROUND_HALF_UP
        )
    return value


def coupon_week(start, end, opening, closing, auctions, cpi, frn, holidays):
    """Payment-date proxy on prior-week positions plus known pre-payment primary allotments."""
    total = ZERO
    issues = []
    # A nominal payment moved from Wednesday holiday to Thursday belongs to the following week.
    payment_months = pd.period_range(
        (start - pd.Timedelta(days=7)).to_period("M"), end.to_period("M"), freq="M"
    )
    positions = opening.copy()
    issued = auctions.loc[auctions.issue_date.gt(start) & auctions.issue_date.le(end)]
    for cusip, group in issued.groupby("cusip"):
        if cusip not in positions.index:
            first = group.iloc[0]
            kind = (
                "Bills"
                if first.security_type == "Bill"
                else (
                    "TIPS"
                    if first.get("inflation_index_security") == "Yes"
                    else (
                        "FRNs" if first.get("floating_rate") == "Yes" else "NotesBonds"
                    )
                )
            )
            if kind != "Bills":
                positions.loc[cusip] = dict.fromkeys(positions.columns)
                positions.loc[
                    cusip, ["securityType", "maturityDate", "par", "rate"]
                ] = [
                    kind,
                    first.maturity_date,
                    ZERO,
                    ZERO if kind == "FRNs" else first.get("int_rate"),
                ]
    for cusip, row in positions.iterrows():
        kind = row.securityType
        if kind == "Bills":
            continue
        step = 3 if kind == "FRNs" else 6
        maturity = row.maturityDate
        # Inspect only months intersecting this payment week; distant maturity dates retain their schedule.
        for month in payment_months:
            months_before = (
                (maturity.year - month.year) * 12 + maturity.month - month.month
            )
            if months_before < 0 or months_before % step:
                continue
            day = (
                calendar.monthrange(month.year, month.month)[1]
                if maturity.is_month_end
                else min(maturity.day, calendar.monthrange(month.year, month.month)[1])
            )
            nominal = pd.Timestamp(year=month.year, month=month.month, day=day)
            paid = payment_day(nominal, holidays)
            if not start < paid <= end:
                continue
            try:
                additions = issued.loc[
                    issued.cusip.eq(cusip) & issued.issue_date.lt(paid)
                ]
                if not additions.soma_accepted.map(present).all():
                    raise ValueError(f"{cusip}: unavailable primary coupon entitlement")
                entitlement = row.par + sum(
                    (decimal(v) / MILLION for v in additions.soma_accepted), ZERO
                )
                if entitlement == ZERO:
                    continue
                if kind == "FRNs":
                    prev = schedule_date(maturity, months_before + step)
                    rates = frn.loc[
                        frn.cusip.eq(cusip)
                        & frn.start_of_accrual_period.ge(prev)
                        & frn.start_of_accrual_period.lt(nominal)
                    ]
                    expected = pd.date_range(
                        prev, nominal - pd.Timedelta(days=1), freq="D"
                    )
                    per100 = frn_coupon_per100(
                        cusip, prev, nominal, paid, auctions, holidays
                    )
                    if (
                        pd.DatetimeIndex(rates.start_of_accrual_period)
                        .sort_values()
                        .equals(expected)
                    ):
                        observed = sum(
                            (
                                decimal(v, "FRN daily interest")
                                for v in rates.daily_accrued_int_per100
                            ),
                            ZERO,
                        )
                        if abs(per100 - observed) > D("0.000001"):
                            raise ValueError(
                                f"FRN {cusip}: reconstructed index disagrees with daily cash rates"
                            )
                    coupon = entitlement / D(100) * per100
                else:
                    ratio = (
                        tips_ratio(cusip, nominal, auctions, cpi)
                        if kind == "TIPS"
                        else D(1)
                    )
                    coupon = (
                        entitlement * ratio * decimal(row.rate, "coupon rate") / D(200)
                    )
                total += money(coupon)
            except ValueError as exc:
                issues.append(str(exc))
    return (None if issues else total), (
        "unavailable_payment_input:" + "|".join(issues)
        if issues
        else "payment_date_proxy_prior_week_plus_primary_secondary_entitlement_unobserved"
    )


def remittance_weeks(frame, dates, holidays):
    required = {
        "record_date",
        "account_type",
        "transaction_type",
        "transaction_catg",
        "transaction_today_amt",
    }
    if required - set(frame):
        raise ValueError("DTS Table II: missing required columns")
    selected = frame.loc[
        frame.transaction_catg.eq("Federal Reserve Earnings")
        & frame.transaction_type.eq("Deposits")
        & frame.account_type.isin(
            ["Federal Reserve Account", "Treasury General Account (TGA)"]
        )
    ].copy()
    if selected.empty:
        raise ValueError("DTS Table II: no Federal Reserve Earnings cash deposits")
    selected["record_date"] = pd.to_datetime(selected.record_date, errors="raise")
    if selected.record_date.duplicated().any():
        raise ValueError("DTS Table II: ambiguous duplicate Fed earnings deposits")
    daily = {
        d: decimal(v, "DTS Fed earnings")
        for d, v in zip(selected.record_date, selected.transaction_today_amt)
    }
    if any(v < 0 for v in daily.values()):
        raise ValueError("DTS: negative cash remittance")
    values, status = {}, {}
    for end in dates:
        days = pd.date_range(end - pd.Timedelta(days=6), end)
        required_days = [d for d in days if d.weekday() < 5 and d not in holidays]
        if any(d not in daily for d in required_days):
            values[end], status[end] = None, "unavailable_dts_daily_coverage"
        else:
            values[end] = sum((daily.get(d, ZERO) for d in days), ZERO)
            status[end] = (
                "dts_reported_cash" if values[end] else "dts_reported_zero_cash"
            )
    return values, status


def bill_total_par(row):
    """Normalize published total to all allotments, then remove SOMA exactly once."""
    par = decimal(row.total_accepted, "bill total") / MILLION
    soma = decimal(row.soma_accepted, "bill SOMA") / MILLION
    for flag, amount in (
        ("soma_included", soma),
        (
            "fima_included",
            decimal(row.get("fima_noncomp_accepted"), "bill FIMA") / MILLION,
        ),
    ):
        included = row.get(flag)
        if included not in ("Yes", "No"):
            raise ValueError(f"missing {flag} total inclusion convention")
        if included == "No":
            par += amount
    if soma < ZERO or par < soma:
        raise ValueError("SOMA exceeds normalized allotments")
    return par, soma


def allocate_route_capacity(capacity, shares):
    """MMF/GSE/other declared shares consume one shared channel capacity."""
    capacity = decimal(capacity)
    if capacity < ZERO:
        raise ValueError("negative route capacity")
    shares = [decimal(v) for v in shares]
    if any(v < ZERO for v in shares) or sum(shares, ZERO) > D(1):
        raise ValueError("route participants exceed shared capacity")
    return [capacity * v for v in shares]


def route_daily(rrp, auctions, start, end, holidays, snapshots=None):
    """Signed same-day primary-bill channel scenarios; overlap is diagnostic only."""
    rrp = rrp.copy()
    rrp["date"] = pd.to_datetime(rrp.date, errors="raise")
    if rrp.date.duplicated().any():
        raise ValueError("ON RRP: duplicate day")
    levels = {
        d: decimal(v, "ON RRP") * D(1000)
        for d, v in zip(rrp.date, rrp.value)
        if str(v) not in (".", "", "nan")
    }
    issuance, redemption, unknown_issue, unknown_red = {}, {}, set(), set()
    bills = auctions.loc[auctions.security_type.eq("Bill")]
    for _, row in bills.iterrows():
        issue, maturity = row.issue_date, payment_day(row.maturity_date, holidays)
        if not (start <= issue <= end or start <= maturity <= end):
            continue
        try:
            full, soma = bill_total_par(row)
        except ValueError:
            if start <= issue <= end:
                unknown_issue.add(issue)
            if start <= maturity <= end:
                unknown_red.add(maturity)
            continue
        redemption[maturity] = redemption.get(maturity, ZERO) + full
        if start <= issue <= end:
            try:
                price = decimal(row.price_per100, "bill price") / D(100)
                if not ZERO < price <= D(1):
                    raise ValueError("bill price outside (0,100]")
            except ValueError:
                unknown_issue.add(issue)
            else:
                issuance[issue] = issuance.get(issue, ZERO) + (full - soma) * price
    # Aggregate all reopenings/allotments, and remove actual prior-snapshot SOMA once per CUSIP.
    if snapshots is not None:
        snapshot_dates = sorted(snapshots)
        for cusip, group in bills.groupby("cusip"):
            maturity = payment_day(group.maturity_date.iloc[0], holidays)
            if not start <= maturity <= end or maturity in unknown_red:
                continue
            prior = [d for d in snapshot_dates if d < maturity]
            if not prior or (maturity - prior[-1]).days > 7:
                unknown_red.add(maturity)
                continue
            held = snapshots[prior[-1]]
            if cusip in held.index:
                redemption[maturity] -= held.loc[cusip].par
            if redemption[maturity] < ZERO:
                unknown_red.add(maturity)
    records, previous = [], None
    for day in pd.date_range(start - pd.Timedelta(days=7), end):
        business = day.weekday() < 5 and day not in holidays
        level = levels.get(day)
        issue = None if day in unknown_issue else money(issuance.get(day, ZERO))
        red = None if day in unknown_red else money(redemption.get(day, ZERO))
        net = None if issue is None or red is None else max(issue - red, ZERO)
        if day < ON_RRP_OPERATION_START:
            opening, closing, decline, forward, reverse, overlap = (ZERO,) * 6
            status = "declared_zero_before_on_rrp_facility_scope"
        elif not business:
            opening, closing, decline, forward, reverse, overlap = (
                previous,
                previous,
                ZERO,
                ZERO,
                ZERO,
                ZERO,
            )
            status = "no_settlement_closed_day"
        else:
            opening, closing = previous, level
            decline = (
                None
                if previous is None or level is None
                else max(previous - level, ZERO)
            )
            forward = (
                None if previous is None or issue is None else min(previous, issue)
            )
            reverse = None if level is None or red is None else min(level, red)
            overlap = None if decline is None or net is None else min(decline, net)
            flags = []
            if previous is None or level is None:
                flags.append("unavailable_on_rrp_daily_observation")
            if issue is None:
                flags.append("unavailable_bill_issue_cash_or_inclusion")
            if red is None:
                flags.append("unavailable_bill_redemption_entitlement_or_inclusion")
            status = (
                "|".join(flags)
                if flags
                else "same_day_channel_capacity_redemption_prior_snapshot_assumption"
            )
        if day >= start:
            records.append(
                dict(
                    date=str(day.date()),
                    week=str(wednesday(day).date()),
                    on_rrp_opening_principal=opening,
                    on_rrp_closing_principal=closing,
                    on_rrp_decline=decline,
                    gross_non_soma_bill_issue_cash=issue,
                    gross_non_soma_bill_redemption_cash=red,
                    positive_net_bill_cash=net,
                    net_bill_on_rrp_overlap=overlap,
                    route_forward=forward,
                    route_reverse=None if reverse is None else -reverse,
                    route_baseline=ZERO,
                    route_status=status,
                )
            )
        if business:
            previous = level
    return pd.DataFrame(records)


INTERNAL_FACTORS = (
    "treasury_contributions_to_credit_facilities",
    "sdr_certificate_account",
    "gold_stock",
)


def internal_postings(h, end, frame):
    """Report stock and dated cash independently; only a same-week crosswalk applies J."""
    cash = None
    postings = []
    window = None if frame is None else frame.attrs.get("query_window")
    covered = window is None or (
        pd.Timestamp(window[0]) <= end - pd.Timedelta(days=6)
        and end <= pd.Timestamp(window[1])
    )
    if frame is not None and covered:
        x = frame.loc[
            (pd.to_datetime(frame.record_date) > end - pd.Timedelta(days=7))
            & (pd.to_datetime(frame.record_date) <= end)
            & frame.transaction_catg.eq("ESF - Economic Recovery Programs")
            & frame.account_type.isin(
                ["Federal Reserve Account", "Treasury General Account (TGA)"]
            )
        ]
        if x.duplicated(["record_date", "transaction_type", "account_type"]).any():
            raise ValueError("DTS internal cash: duplicate account/date/type")
        if not x.transaction_type.isin(["Withdrawals", "Deposits"]).all():
            raise ValueError("DTS internal cash: unknown transaction type")
        postings = [
            {
                "date": r.record_date,
                "transaction_type": r.transaction_type,
                "amount": -decimal(r.transaction_today_amt)
                if r.transaction_type == "Withdrawals"
                else decimal(r.transaction_today_amt),
            }
            for r in x.itertuples()
        ]
        cash = sum((r["amount"] for r in postings), ZERO)
    out = {}
    matched = set()
    for key in INTERNAL_FACTORS:
        candidate = decimal(h["f_" + key])
        applied = ZERO
        status = "no_stock_candidate"
        if candidate:
            status = "candidate_only_no_dated_tga_cash_crosswalk"
            if key == "treasury_contributions_to_credit_facilities" and postings:
                signed = [r["amount"] for r in postings]
                if cash == candidate:
                    applied = candidate
                    matched = set(range(len(postings)))
                    status = "applied_dated_dts_facility_cash_match"
                elif signed.count(candidate) == 1:
                    applied = candidate
                    matched = {signed.index(candidate)}
                    status = "applied_dated_dts_facility_cash_match"
                else:
                    status = "candidate_only_dts_cash_stock_mismatch"
                    for match in WEEKLY_TRC_INTERNAL_MATCHES:
                        eligible = [
                            i
                            for i, r in enumerate(postings)
                            if r["date"] == match["date"]
                            and r["transaction_type"] == match["transaction_type"]
                            and r["amount"]
                            == (
                                -decimal(match["amount"])
                                if match["transaction_type"] == "Withdrawals"
                                else decimal(match["amount"])
                            )
                        ]
                        if len(eligible) == 1:
                            i = eligible[0]
                            confirmed = postings[i]["amount"]
                            if candidate * confirmed > ZERO and abs(confirmed) < abs(
                                candidate
                            ):
                                applied = confirmed
                                matched = {i}
                                status = "applied_dated_cash_partial_stock_remainder_candidate"
            elif key in ("sdr_certificate_account", "gold_stock"):
                status = (
                    "candidate_only_certificate_special_account_tga_link_unobserved"
                )
        out["j_" + key + "_applied"] = applied
        out["j_" + key + "_candidate_only"] = candidate - applied
        out["j_" + key + "_status"] = status
    unmatched = [
        r for i, r in enumerate(postings) if i not in matched and r["amount"] != ZERO
    ]
    out["j_facility_dts_cash_candidate"] = cash
    out["j_facility_dts_cash_candidate_only"] = (
        None if cash is None else sum((r["amount"] for r in unmatched), ZERO)
    )
    out["j_facility_dts_cash_candidate_only_absolute"] = (
        None if cash is None else sum((abs(r["amount"]) for r in unmatched), ZERO)
    )
    out["j_facility_dts_cash_candidate_dates"] = "|".join(
        r["date"] + ":" + str(r["amount"]) for r in unmatched
    )
    out["j_facility_dts_cash_status"] = (
        "unavailable_dated_cash_input"
        if cash is None
        else "cash_candidate_only_no_same_week_stock_crosswalk"
        if unmatched
        else "applied_dated_cash_no_unmatched_postings"
        if matched
        else "no_nonzero_dated_cash_candidate"
    )
    out["j_applied"] = sum((out["j_" + k + "_applied"] for k in INTERNAL_FACTORS), ZERO)
    out["j_candidate_only"] = sum(
        (out["j_" + k + "_candidate_only"] for k in INTERNAL_FACTORS), ZERO
    )
    return out


def total(values):
    values = list(values)
    return (
        None
        if any(v is None or pd.isna(v) for v in values)
        else sum((decimal(v) for v in values), ZERO)
    )


def build_weekly_trc(ledger, sources, registry=WEEKLY_TRC_REGISTRY):
    """Use admitted ledger cash unchanged; unavailable inputs propagate through core and identity."""
    dates = pd.DatetimeIndex(pd.to_datetime(ledger.date, errors="raise"))
    if (
        dates.has_duplicates
        or not dates.weekday.tolist() == [2] * len(dates)
        or not dates.to_series().diff().dropna().eq(pd.Timedelta(days=7)).all()
    ):
        raise ValueError("Ledger: expected consecutive unique Wednesdays")
    auctions = prepare_auctions(sources["auctions"])
    first, last = (
        max(pd.Timestamp(registry.inputs[0].snapshot_window[0]), dates[0]),
        min(pd.Timestamp(registry.inputs[0].snapshot_window[1]), dates[-1]),
    )
    dates = dates[(dates >= first) & (dates <= last)]
    if dates.empty:
        raise ValueError("Ledger and SOMA do not overlap")
    snapshots = prepare_soma(sources["soma"], dates.union(dates - pd.Timedelta(days=7)))
    ledger = ledger.set_index(pd.to_datetime(ledger.date)).loc[dates]
    holidays = set(
        FedPaymentCalendar().holidays(
            first - pd.Timedelta(days=370), last + pd.Timedelta(days=370)
        )
    )
    cpi_frame = sources["cpi"]
    cpi_dates = pd.PeriodIndex(pd.to_datetime(cpi_frame.date, errors="raise"), freq="M")
    if cpi_dates.has_duplicates:
        raise ValueError("CPI: duplicate month")
    cpi = {
        d: (None if v in ("", ".", "null") else decimal(v, "CPI"))
        for d, v in zip(cpi_dates, cpi_frame.value)
    }
    frn = sources["frn"].copy()
    if {"cusip", "start_of_accrual_period", "daily_accrued_int_per100"} - set(frn):
        raise ValueError("FRN: required fields missing")
    frn["start_of_accrual_period"] = pd.to_datetime(
        frn.start_of_accrual_period, errors="raise"
    )
    if frn.duplicated(["cusip", "start_of_accrual_period"]).any():
        raise ValueError("FRN: duplicate daily accrual")
    frn_feed_semantics(sources["frn"])
    remits, remit_status = remittance_weeks(sources["remittances"], dates, holidays)
    internal_dts = sources.get("internal_dts")
    if internal_dts is not None:
        internal_dts = internal_dts.copy()
        spec = next(s for s in registry.inputs if s.key == "internal_dts")
        query = next(
            v.removeprefix("filter=") for v in spec.argv if v.startswith("filter=")
        )
        filters = dict(part.rsplit(":", 1) for part in query.split(","))
        internal_dts.attrs["query_window"] = (
            filters["record_date:gte"],
            filters["record_date:lte"],
        )
    daily_route = route_daily(
        sources["on_rrp"],
        auctions,
        first - pd.Timedelta(days=6),
        last,
        holidays,
        snapshots,
    )
    route = {week: group for week, group in daily_route.groupby("week")}
    all_changes, weeks, identities = [], [], []
    rows = load_h41_rows()
    valuation_keys = ("unamortized_premiums", "unamortized_discounts")
    factor_keys = [k for k, e in rows.items() if e.row.role == "factor"]
    other_keys = [
        k
        for k in factor_keys
        if k not in {*CASH_KEYS, "treasury_securities", RRP_OTHER_KEY, *valuation_keys}
    ]
    for end in dates:
        start = end - pd.Timedelta(days=7)
        h = ledger.loc[end]
        changes, coupon, coupon_status, fed, inflation = (
            [],
            None,
            "unavailable_soma_snapshot",
            None,
            None,
        )
        opening, closing = snapshots.get(start), snapshots.get(end)
        if opening is not None and closing is not None:
            prior = snapshots.get(start - pd.Timedelta(days=7))
            deferred = (
                {}
                if prior is None
                else {
                    cusip: r
                    for cusip, r in prior.iterrows()
                    if r.maturityDate
                    <= start
                    < payment_day(r.maturityDate, holidays)
                    <= end
                    and (cusip not in opening.index or opening.loc[cusip].par == ZERO)
                }
            )
            changes = classify_week(
                start, end, opening, closing, auctions, holidays, cpi, deferred
            )
            all_changes.extend(changes)
            fed = sum(closing.par, ZERO) - sum(opening.par, ZERO)
            inflation = sum(closing.inflation, ZERO) - sum(opening.inflation, ZERO)
            coupon_opening = opening.copy()
            prior = snapshots.get(start - pd.Timedelta(days=7))
            if prior is not None:
                for cusip, old in prior.iterrows():
                    if (
                        old.par > ZERO
                        and old.maturityDate
                        <= start
                        < payment_day(old.maturityDate, holidays)
                        <= end
                    ):
                        if (
                            cusip not in coupon_opening.index
                            or coupon_opening.loc[cusip].par == ZERO
                        ):
                            coupon_opening.loc[cusip] = old
            coupon, coupon_status = coupon_week(
                start, end, coupon_opening, closing, auctions, cpi, frn, holidays
            )
        unknown = sum(
            r["classification_status"].startswith("unclassifiable") for r in changes
        )
        cash = decimal(h.c_h, "ledger cash")
        remit = remits[end]
        primary_adjustment = (
            sum(
                (
                    r["primary_cash_adjustment"]
                    for r in changes
                    if r["primary_cash_adjustment"] is not None
                ),
                ZERO,
            )
            if fed is not None
            else None
        )
        redemption_inflation = (
            sum(
                (
                    r["redemption_inflation"]
                    for r in changes
                    if r["redemption_inflation"] is not None
                ),
                ZERO,
            )
            if fed is not None
            else None
        )
        j = internal_postings(h, end, internal_dts)
        par_core = total([cash, fed, None if coupon is None else -coupon, remit])
        clock_adjustment = (
            sum((r["settlement_clock_adjustment"] for r in changes), ZERO)
            if fed is not None
            else None
        )
        fed_cash = total(
            [
                fed,
                clock_adjustment,
                primary_adjustment,
                None if redemption_inflation is None else -redemption_inflation,
            ]
        )
        core = total(
            [cash, fed_cash, None if coupon is None else -coupon, remit, j["j_applied"]]
        )
        group = route[str(end.date())]
        forward = total(group.route_forward)
        reverse = total(group.route_reverse)
        state = (
            "unavailable_required_input"
            if core is None
            else (
                "cash_corrected_proxy_unclassifiable_changes"
                if unknown
                else "cash_corrected_proxy_secondary_prices_and_entitlements_unobserved"
            )
        )
        result = {
            "date": str(end.date()),
            "quarter": str(end.to_period("Q")),
            "start_wednesday": str(start.date()),
            "c_h": cash,
            "bridge_all_securities_premium_discount": total(
                decimal(h["f_" + k]) for k in valuation_keys
            ),
            "fed_leg_par": fed,
            "fed_leg_cash_corrected": fed_cash,
            "settlement_clock_adjustment": clock_adjustment,
            "primary_cash_adjustment": primary_adjustment,
            "redemption_inflation": redemption_inflation,
            "primary_cash_unavailable_par": sum(
                (r["primary_cash_unavailable_par"] for r in changes), ZERO
            )
            if fed is not None
            else None,
            "redemption_cash_unavailable_par": sum(
                (r["redemption_cash_unavailable_par"] for r in changes), ZERO
            )
            if fed is not None
            else None,
            "cash_correction_status": "supported_adjustments_only_unavailable_events_reported"
            if any(
                r["primary_cash_adjustment"] is None
                or r["redemption_inflation"] is None
                for r in changes
            )
            else "identified_primary_cash_redemption_proxy_no_intervening_trade",
            **j,
            "soma_coupon_cash": coupon,
            "cash_remittances": remit,
            "soma_inflation_compensation_change_excluded": inflation,
            "secondary_purchases_par": total(
                r["secondary_purchases_par"] for r in changes
            )
            if fed is not None
            else None,
            "secondary_sales_par": total(r["secondary_sales_par"] for r in changes)
            if fed is not None
            else None,
            "redemptions_par": total(r["redemptions_par"] for r in changes)
            if fed is not None
            else None,
            "primary_addons_par": total(r["primary_addons_par"] for r in changes)
            if fed is not None
            else None,
            "unclassifiable_changes": unknown,
            "unclassifiable_abs_par": sum(
                (r["unclassifiable_abs_par"] for r in changes), ZERO
            )
            if fed is not None
            else None,
            "unpriced_secondary_net_par": sum(
                (
                    r["secondary_purchases_par"] + r["secondary_sales_par"]
                    for r in changes
                    if r["secondary_purchases_par"] is not None
                ),
                ZERO,
            )
            if fed is not None
            else None,
            "trc_core": core,
            "trc_par_sensitivity": par_core,
            "route_baseline": ZERO,
            "route_forward": forward,
            "route_reverse": reverse,
            "net_bill_on_rrp_overlap": total(group.net_bill_on_rrp_overlap),
            "trc_forward_scenario": total([core, forward]),
            "trc_reverse_scenario": total([core, reverse]),
            "rrp_others_vs_on_rrp_flow_bridge": total(
                [
                    decimal(h["f_" + RRP_OTHER_KEY]),
                    None
                    if group.on_rrp_closing_principal.iloc[-1] is None
                    else group.on_rrp_closing_principal.iloc[-1],
                    None
                    if group.on_rrp_opening_principal.iloc[0] is None
                    else -group.on_rrp_opening_principal.iloc[0],
                ]
            ),
            "core_status": state,
            "coupon_status": coupon_status,
            "remittance_status": remit_status[end],
            "soma_status": "consecutive_snapshots"
            if fed is not None
            else "unavailable_missing_consecutive_snapshot",
            "route_status": "|".join(sorted(set(group.route_status))),
            "reserve_balances_start": decimal(h.reserve_balances)
            - decimal(h.delta_reserve_balances),
            "reserve_balances_end": decimal(h.reserve_balances),
            "delta_reserve_balances": decimal(h.delta_reserve_balances),
        }
        result["matched_rollover_par_memo"] = (
            rollover_memo(
                changes,
                auctions.loc[
                    auctions.issue_date.gt(start) & auctions.issue_date.le(end)
                ],
            )
            if fed is not None
            else None
        )
        weeks.append(result)
        for variant, gamma in (
            ("core", ZERO),
            ("forward_scenario", forward),
            ("reverse_scenario", reverse),
        ):
            x = total([core, gamma])
            identity = {
                "date": str(end.date()),
                "variant": variant,
                "delta_reserve_balances": result["delta_reserve_balances"],
                "trc": x,
                "route": gamma,
                "non_treasury_signed_factors": total(
                    decimal(h["f_" + k]) for k in other_keys
                ),
                "rrp_others_net_route": total(
                    [
                        decimal(h["f_" + RRP_OTHER_KEY]),
                        None if gamma is None else -gamma,
                    ]
                ),
                "bridge_all_securities_premium_discount": total(
                    decimal(h["f_" + k]) for k in valuation_keys
                ),
                "bridge_treasury_securities_source_inflation": total(
                    [decimal(h.s_h), None if fed is None else -fed]
                ),
                "bridge_maturity_payment_clock": None
                if clock_adjustment is None
                else -clock_adjustment,
                "bridge_primary_cash_price": None
                if primary_adjustment is None
                else -primary_adjustment,
                "bridge_redemption_inflation": redemption_inflation,
                "bridge_internal_postings": -j["j_applied"],
                "bridge_coupon_remittance_payments": total(
                    [coupon, None if remit is None else -remit]
                ),
                "bridge_published_rounding": decimal(h.rho),
            }
            names = [
                "trc",
                "non_treasury_signed_factors",
                "rrp_others_net_route",
                "bridge_all_securities_premium_discount",
                "bridge_treasury_securities_source_inflation",
                "bridge_coupon_remittance_payments",
                "bridge_maturity_payment_clock",
                "bridge_primary_cash_price",
                "bridge_redemption_inflation",
                "bridge_internal_postings",
                "bridge_published_rounding",
            ]
            identity["identity_rhs"] = total(identity[c] for c in names)
            identity["identity_error"] = total(
                [
                    identity["delta_reserve_balances"],
                    None
                    if identity["identity_rhs"] is None
                    else -identity["identity_rhs"],
                ]
            )
            identity["identity_status"] = (
                "unavailable_required_input"
                if identity["identity_error"] is None
                else "closed_exact_decimal"
            )
            if (
                identity["identity_error"] is not None
                and identity["identity_error"] != ZERO
            ):
                raise ValueError(
                    f"Weekly identity failed {end}: {identity['identity_error']}"
                )
            identities.append(identity)
    changes = pd.DataFrame(all_changes, columns=EVENT_COLUMNS)

    return pd.DataFrame(weeks), pd.DataFrame(identities), changes, daily_route


def quarter_tables(weekly, components):
    """Full Wednesday-bounded quarters; incomplete coverage is recorded rather than summed to a point value."""
    quarterly = []
    comp = components.set_index("quarter")
    numeric = [
        "c_h",
        "bridge_all_securities_premium_discount",
        "fed_leg_par",
        "soma_coupon_cash",
        "cash_remittances",
        "trc_core",
        "trc_par_sensitivity",
        "primary_cash_adjustment",
        "redemption_inflation",
        "fed_leg_cash_corrected",
        "settlement_clock_adjustment",
        "primary_cash_unavailable_par",
        "redemption_cash_unavailable_par",
        "j_applied",
        "j_candidate_only",
        "unclassifiable_abs_par",
        "unpriced_secondary_net_par",
        "route_baseline",
        "route_forward",
        "route_reverse",
        "net_bill_on_rrp_overlap",
        "trc_forward_scenario",
        "trc_reverse_scenario",
        "delta_reserve_balances",
    ]
    for quarter, group in weekly.groupby("quarter", sort=True):
        period = pd.Period(quarter, freq="Q")
        end = period.end_time.normalize()
        end -= pd.Timedelta(days=(end.weekday() - 2) % 7)
        start = (period - 1).end_time.normalize()
        start -= pd.Timedelta(days=(start.weekday() - 2) % 7)
        expected = pd.date_range(start + pd.Timedelta(days=7), end, freq="W-WED")
        full_clock = pd.DatetimeIndex(pd.to_datetime(group.date)).equals(expected)
        row = {
            "quarter": quarter,
            "start_wednesday": str(start.date()),
            "end_wednesday": str(end.date()),
            "n_weeks": len(group),
            "expected_weeks": len(expected),
            "clock_status": "complete_wednesday_quarter"
            if full_clock
            else "incomplete_wednesday_quarter",
        }
        for column in numeric:
            row[column] = total(group[column]) if full_clock else None
        row["quarter_status"] = (
            "available_cash_corrected_proxy"
            if row["trc_core"] is not None
            else "unavailable_required_weeks"
        )
        row["unavailable_reasons"] = "|".join(
            sorted(
                set(
                    str(r.core_status)
                    + ":"
                    + str(r.soma_status)
                    + ":"
                    + str(r.coupon_status)
                    + ":"
                    + str(r.remittance_status)
                    for r in group.loc[group.trc_core.isna()].itertuples()
                )
            )
        )
        if not full_clock:
            row["unavailable_reasons"] = (
                "incomplete_wednesday_quarter|" + row["unavailable_reasons"]
            )
        if full_clock:
            endpoints = decimal(group.reserve_balances_end.iloc[-1]) - decimal(
                group.reserve_balances_start.iloc[0]
            )
            row["reserve_telescoping_error"] = row["delta_reserve_balances"] - endpoints
            if row["reserve_telescoping_error"] != ZERO:
                raise ValueError("Quarterly reserve sum does not telescope")
        else:
            row["reserve_telescoping_error"] = None
        if quarter in comp.index:
            c = comp.loc[quarter]
            admitted_cash = decimal(c.trc_cash_leg)
            admitted_fed = decimal(c.fed_tsy_tx)
            admitted_coupon = decimal(c.fed_tsy_coupon_interest_proxy)
            admitted_remit = decimal(c.fed_remit_positive)
            row["admitted_quarterly_core"] = decimal(c.trc_core)
            row["difference_treasury_deposit_clock"] = total(
                [row["c_h"], -admitted_cash]
            )
            row["difference_fed_source_par_vs_z1"] = total(
                [row["fed_leg_par"], -admitted_fed]
            )
            row["difference_coupon_measurement_clock"] = total(
                [
                    None
                    if row["soma_coupon_cash"] is None
                    else -row["soma_coupon_cash"],
                    admitted_coupon,
                ]
            )
            row["difference_remittance_source_clock"] = total(
                [row["cash_remittances"], -admitted_remit]
            )
            row["difference_maturity_payment_clock"] = row[
                "settlement_clock_adjustment"
            ]
            row["difference_primary_cash_price"] = row["primary_cash_adjustment"]
            row["difference_redemption_inflation"] = (
                None
                if row["redemption_inflation"] is None
                else -row["redemption_inflation"]
            )
            row["difference_internal_postings"] = row["j_applied"]
            row["difference_core"] = total(
                [row["trc_core"], -row["admitted_quarterly_core"]]
            )
            difference_names = (
                "difference_treasury_deposit_clock",
                "difference_fed_source_par_vs_z1",
                "difference_coupon_measurement_clock",
                "difference_remittance_source_clock",
                "difference_primary_cash_price",
                "difference_redemption_inflation",
                "difference_internal_postings",
                "difference_maturity_payment_clock",
            )
            difference_sum = total(row[k] for k in difference_names)
            row["difference_identity_error"] = total(
                [
                    row["difference_core"],
                    None if difference_sum is None else -difference_sum,
                ]
            )
            # Admitted components are binary floats printed to CSV; explicitly retain their decimal arithmetic residue.
            if row["difference_identity_error"] is not None and abs(
                row["difference_identity_error"]
            ) > D("0.000001"):
                raise ValueError("Quarterly admitted-component reconciliation failed")
        quarterly.append(row)
    return pd.DataFrame(quarterly)


def summary_windows(quarter_end):
    return (*eras(quarter_end), ("2006Q1", quarter_end), ("2003Q3", quarter_end))


def describe_by_era(frame, columns, *, common=False, quarter_end=DEFAULT_VINTAGE.weekly_quarter_end):
    out = {}
    for start, end in summary_windows(quarter_end):
        window = frame.loc[frame.quarter.ge(start) & frame.quarter.le(end)]
        if common:
            window = window.loc[window[columns].notna().all(axis=1)]
        cells = {}
        for column in columns:
            x = pd.to_numeric(window[column], errors="raise").dropna().astype(float)
            cells[column] = {
                "n": len(x),
                "sum": float(x.sum()) if len(x) else None,
                "mean": float(x.mean()) if len(x) else None,
                "mean_abs": float(x.abs().mean()) if len(x) else None,
                "sd": float(x.std()) if len(x) > 1 else None,
                "min": float(x.min()) if len(x) else None,
                "max": float(x.max()) if len(x) else None,
            }
        out[f"{start}-{end}"] = {"observed_rows": len(window), "columns": cells}
    return out


def era_windows(frame, quarter_end=DEFAULT_VINTAGE.weekly_quarter_end):
    for start, end in summary_windows(quarter_end):
        yield (
            start + "-" + end,
            frame.loc[frame.quarter.ge(start) & frame.quarter.le(end)],
        )


def event_summary(changes, quarter_end=DEFAULT_VINTAGE.weekly_quarter_end):
    frame = changes.assign(
        quarter=pd.to_datetime(changes.date).dt.to_period("Q").astype(str)
    )
    return {
        era: {
            str(kind): {
                "n": len(g),
                "signed_par": str(sum(g.unclassifiable_par, ZERO)),
                "absolute_par": str(sum(g.unclassifiable_abs_par, ZERO)),
            }
            for kind, g in window.loc[
                window.classification_status.str.startswith("unclassifiable")
            ].groupby("event_type")
        }
        for era, window in era_windows(frame, quarter_end)
    }


def internal_summary(weekly, quarter_end=DEFAULT_VINTAGE.weekly_quarter_end):
    return {
        era: {
            key: {
                str(status): {
                    "n": len(g),
                    "applied": str(sum(g["j_" + key + "_applied"], ZERO)),
                    "candidate_only": str(sum(g["j_" + key + "_candidate_only"], ZERO)),
                    "candidate_only_absolute": str(
                        sum((abs(v) for v in g["j_" + key + "_candidate_only"]), ZERO)
                    ),
                }
                for status, g in window.groupby("j_" + key + "_status")
            }
            for key in INTERNAL_FACTORS
        }
        for era, window in era_windows(weekly, quarter_end)
    }


def tips_crosscheck(auctions, cpi_frame):
    auctions = prepare_auctions(auctions)
    cpi = {
        pd.Period(d, freq="M"): decimal(v)
        for d, v in zip(cpi_frame.date, cpi_frame.value)
        if present(v) and v != "."
    }
    checked, missing, mismatches = 0, 0, []
    for _, row in auctions.loc[
        auctions.get(
            "inflation_index_security", pd.Series(index=auctions.index, dtype=str)
        ).eq("Yes")
    ].iterrows():
        if not present(row.index_ratio_on_issue_date):
            missing += 1
            continue
        try:
            rebuilt = reconstructed_tips_ratio(row.cusip, row.issue_date, auctions, cpi)
        except ValueError:
            missing += 1
            continue
        checked += 1
        published = decimal(row.index_ratio_on_issue_date)
        if rebuilt != published:
            mismatches.append(
                dict(
                    cusip=row.cusip,
                    issue_date=str(row.issue_date.date()),
                    reconstructed=str(rebuilt),
                    published=str(published),
                    difference=str(rebuilt - published),
                )
            )
    return dict(
        checked=checked,
        unavailable=missing,
        mismatch_count=len(mismatches),
        mismatches=mismatches,
        status="reconstruction_crosscheck_primary_cash_uses_published_fields_payment_ratios_prefer_contractual_reference_cpi",
        published_reference_dates=len(
            auctions.attrs.get("contractual_reference_cpi", {})
        ),
    )


def auction_field_coverage(frame, quarter_end=DEFAULT_VINTAGE.weekly_quarter_end):
    frame = frame.assign(
        quarter=pd.to_datetime(frame.issue_date).dt.to_period("Q").astype(str)
    )
    fields = (
        "soma_accepted",
        "price_per100",
        "adj_price",
        "accrued_int_per100",
        "accrued_int_per1000",
        "adj_accrued_int_per1000",
        "index_ratio_on_issue_date",
        "soma_included",
        "fima_included",
    )
    return {
        era: {
            kind: {
                field: int(g[field].map(present).sum()) if field in g else 0
                for field in fields
            }
            for kind, g in window.groupby("security_type")
        }
        for era, window in era_windows(frame, quarter_end)
    }


def frn_feed_semantics(frame):
    if frame.empty:
        return {"status": "unavailable_empty_feed", "rows": 0}
    if "end_of_accrual_period" not in frame:
        raise ValueError("FRN feed: missing accrual interval end")
    lengths = (
        pd.to_datetime(frame.end_of_accrual_period)
        - pd.to_datetime(frame.start_of_accrual_period)
    ).dt.days
    if not lengths.eq(1).all():
        raise ValueError(
            "FRN feed: expected verified one-calendar-day accrual intervals"
        )
    return {
        "status": "observed_one_day_start_inclusive_end_exclusive",
        "rows": len(frame),
        "first_accrual_date": str(frame.start_of_accrual_period.min()),
        "last_accrual_date": str(frame.start_of_accrual_period.max()),
        "source_record_date_is_publication_not_accrual_date": True,
    }


def column_contracts(tables):
    """Every output column has an explicit source and a clock, including diagnostics and statuses."""
    source = {
        "c_h": "admitted reserve_factor_ledger_weekly_v1:c_h (WDTGAL,WDSFAL)",
        "fed_leg_par": "soma.treasury_holdings: difference of sum(parValue)/1e6",
        "soma_coupon_cash": "soma.treasury_holdings + fiscaldata.auctions_query + fred.cpiaucns + fiscaldata.frn_daily_indexes; scheduled cash coupons",
        "cash_remittances": "fiscaldata.dts_deposits_withdrawals: Federal Reserve Earnings deposits",
        "route_baseline": "declared no-route baseline: zero",
        "route_forward": "min(opening ON RRP principal,gross non-SOMA bill settlement cash), summed by week",
        "route_reverse": "-min(closing ON RRP principal,gross non-SOMA bill redemption cash), summed by week",
        "on_rrp_decline": "fred.rrpontsyd: positive decline from preceding business day, billion times 1000",
        "positive_net_bill_cash": "normalized gross non-SOMA bill issue cash less gross non-SOMA redemption proxy, clipped at zero",
        "bridge_all_securities_premium_discount": "admitted ledger:f_unamortized_premiums+f_unamortized_discounts; ALL securities",
        "bridge_treasury_securities_source_inflation": "admitted ledger:s_h - fed_leg_par; includes H.4.1 inflation, source, maturity valuation and settlement differences",
        "bridge_coupon_remittance_payments": "soma_coupon_cash - cash_remittances",
        "bridge_published_rounding": "admitted ledger:rho",
        "non_treasury_signed_factors": "admitted ledger: all factors except TGA,SFP,Treasury securities,RRP others,premiums,discounts",
        "rrp_others_net_route": "admitted ledger:f_rrp_others - route",
        "trc_core": "c_h + fed_leg_cash_corrected - soma_coupon_cash + cash_remittances + j_applied",
        "trc_forward_scenario": "trc_core + route_forward",
        "trc_reverse_scenario": "trc_core + route_reverse",
        "trc": "trc_<variant>",
        "route": "declared forward or reverse channel scenario; zero for core",
        "admitted_quarterly_core": "admitted trc_quarterly_components_v1:trc_core",
        "difference_core": "weekly-quarter trc_core - admitted quarterly trc_core",
        "difference_treasury_deposit_clock": "weekly-quarter c_h - admitted trc_cash_leg",
        "difference_fed_source_par_vs_z1": "weekly-quarter fed_leg_par - admitted fed_tsy_tx; source and par vs Z.1 valuation",
        "difference_coupon_measurement_clock": "admitted fed_tsy_coupon_interest_proxy - weekly-quarter soma_coupon_cash",
        "difference_remittance_source_clock": "weekly-quarter cash_remittances - admitted fed_remit_positive",
        "difference_identity_error": "difference_core less eight named differences; printed admitted float arithmetic residue",
        "reserve_telescoping_error": "sum weekly delta_reserve_balances less Wednesday endpoint difference",
        "reserve_balances_start": "admitted ledger:reserve_balances - delta_reserve_balances",
        "reserve_balances_end": "admitted ledger:reserve_balances",
        "delta_reserve_balances": "admitted ledger:delta_reserve_balances",
        "identity_rhs": "sum of trc, other factors, net RRP factor and named bridges",
        "identity_error": "delta_reserve_balances - identity_rhs, Decimal arithmetic",
        "soma_inflation_compensation_change_excluded": "soma.treasury_holdings: difference of inflationCompensation, excluded from core",
        "inflation_compensation_change_excluded": "soma.treasury_holdings: CUSIP inflationCompensation difference, excluded from par",
        "matched_rollover_par_memo": "sum over actual settlement dates of min(maturing par,SOMA allotment par); date-matched memo only",
        "opening_par": "soma.treasury_holdings: prior snapshot parValue/1e6",
        "closing_par": "soma.treasury_holdings: current snapshot parValue/1e6",
        "delta_par": "closing_par - opening_par",
        "redemptions_par": "prior-snapshot entitlement at actual payment date, including deferred holiday maturity; no-intervening-trade assumption",
        "primary_addons_par": "fiscaldata.auctions_query:soma_accepted on issue date, CLASSIFICATION_RULE",
        "secondary_purchases_par": "positive net residual delta_par+redemptions_par-primary_addons_par, CLASSIFICATION_RULE",
        "secondary_sales_par": "negative net residual delta_par+redemptions_par-primary_addons_par, CLASSIFICATION_RULE",
        "unclassifiable_par": "unresolved classification residual, CLASSIFICATION_RULE",
        "unclassifiable_changes": "count of CUSIP changes carrying unclassifiable status",
    }
    source.update(
        {
            "settlement_clock_adjustment": "defer holiday maturity par removals from nominal snapshot date to payment week; opening entitlement assumption",
            "bridge_maturity_payment_clock": "-settlement_clock_adjustment",
            "difference_maturity_payment_clock": "weekly-quarter settlement_clock_adjustment",
            "fed_leg_cash_corrected": "fed_leg_par + maturity payment-clock adjustment + supported primary_cash_adjustment - supported redemption_inflation",
            "trc_par_sensitivity": "c_h + fed_leg_par - soma_coupon_cash + cash_remittances; no cash or J correction",
            "primary_addons_cash": "auction SOMA par times dirty settlement price, with adjusted TIPS fields indexed once",
            "primary_cash_adjustment": "supported primary_addons_cash - primary_addons_par; null event corrections reported separately",
            "redemptions_cash": "opening par with no-intervening-trade assumption; TIPS max(par,par*nominal-maturity index ratio)",
            "redemption_inflation": "redemptions_cash - redemptions_par; supported adjustments only in weekly aggregate",
            "primary_cash_unavailable_par": "par magnitude of events missing acquisition cash or allotment; not an error bound",
            "redemption_cash_unavailable_par": "par magnitude of events missing redemption cash; not an error bound",
            "unclassifiable_abs_par": "sum absolute net unresolved classification residuals; not gross unknown transactions",
            "unpriced_secondary_net_par": "sum absolute classified NET secondary residual par; no observed gross prices or churn",
            "on_rrp_opening_principal": "preceding observed business-day ON RRP take-up, billion times 1000",
            "on_rrp_closing_principal": "current business-day ON RRP take-up, billion times 1000",
            "gross_non_soma_bill_issue_cash": "normalized all auction allotments less SOMA once, times bill price; FIMA included, owners not classified",
            "gross_non_soma_bill_redemption_cash": "all normalized original auction par less prior-snapshot SOMA once; no-intervening-trade entitlement proxy",
            "net_bill_on_rrp_overlap": "min(positive aggregate ON RRP decline,positive net bill cash); diagnostic only",
            "bridge_primary_cash_price": "-primary_cash_adjustment",
            "bridge_redemption_inflation": "+redemption_inflation",
            "bridge_internal_postings": "-j_applied",
            "difference_primary_cash_price": "weekly-quarter primary_cash_adjustment",
            "difference_redemption_inflation": "negative weekly-quarter redemption_inflation",
            "difference_internal_postings": "weekly-quarter j_applied",
            "j_applied": "sum supported dated Treasury-Fed cash matches",
            "j_candidate_only": "sum signed internal factors lacking matched dated cash support; excluded from core",
            "j_facility_dts_cash_candidate": "all signed dated DTS ESF cash independently of facility stock changes; deposits minus withdrawals",
            "j_facility_dts_cash_candidate_only": "unmatched signed dated ESF postings after excluding matched cash once; no adjacent-week matching",
            "j_facility_dts_cash_candidate_only_absolute": "sum absolute unmatched dated ESF postings; not an uncertainty bound",
            "j_facility_dts_cash_candidate_dates": "cash dates and signed USD million for unmatched nonzero dated ESF postings",
            "rrp_others_vs_on_rrp_flow_bridge": "signed H.4.1 RRP-others factor + change in daily ON RRP principal; perimeters differ",
        }
    )
    for key in INTERNAL_FACTORS:
        source["j_" + key + "_applied"] = "dated cash match to admitted ledger:f_" + key
        source["j_" + key + "_candidate_only"] = (
            "admitted ledger:f_" + key + " less applied dated cash match"
        )
    metadata = {
        "date",
        "quarter",
        "week",
        "start_wednesday",
        "end_wednesday",
        "n_weeks",
        "expected_weeks",
        "variant",
        "cusip",
        "security_type",
        "nominal_maturity_date",
        "payment_date",
        "issue_settlement_dates",
        "event_type",
        "unavailable_reasons",
    }
    contracts = {}
    for role, frame in tables.items():
        clock = (
            "Thursday-Wednesday flow; Wednesday endpoint"
            if role in ("weekly", "identity", "classification")
            else (
                "actual daily settlement/payment or business-day take-up"
                if role == "daily_route"
                else "sum weeks between last Wednesdays of consecutive quarters; admitted comparator calendar-quarter"
            )
        )
        fields = {}
        for col in frame:
            if col in metadata:
                definition = (
                    "declared calendar/row key; CUSIP and security type from SOMA"
                )
            elif col.endswith("status"):
                definition = "explicit input, classification, or completeness state from the named calculation"
            else:
                definition = source[
                    col
                ]  # Any undeclared output column fails the producer.
            fields[col] = {
                "source": definition,
                "clock": clock,
                "units": "metadata"
                if col in metadata or col.endswith("status")
                else ("count" if col == "unclassifiable_changes" else "USD million"),
            }
        contracts[role] = fields
    return contracts


def write_weekly_trc_export(
    *, root, inputs_manifest_sha256, ledger_sha256, trc_components_sha256, vintage: MeasurementVintage = DEFAULT_VINTAGE,
):
    registry = fiscus_registries(vintage)["weekly-trc"]
    quarter_end = vintage.weekly_quarter_end
    root = Path(root).resolve()
    commit = require_clean_commit(root)
    protected_paths = [
        root / "data/processed" / name
        for name in [*TRC_OUTPUT_FILES.values(), *LEDGER_OUTPUT_FILES.values()]
    ]
    before = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in protected_paths
    }
    manifest_raw, manifest_record = read_pinned_input(
        root,
        root / registry.manifest,
        inputs_manifest_sha256,
        "weekly_inputs_manifest",
    )
    manifest = json.loads(manifest_raw)
    sources, records = load_fiscus_inputs(root, manifest, registry)
    # Use the existing Table II loader on the fiscus export, then strict cash-row selection.
    sources["remittances"] = extract_dts_operating_cash_balance(
        root / records["remittances"]["file"]
    ).astype(str)
    ledger_raw, ledger_record = read_pinned_input(
        root,
        root / "data/processed" / LEDGER_OUTPUT_FILES["weekly"],
        ledger_sha256,
        "admitted_weekly_ledger",
    )
    comp_raw, comp_record = read_pinned_input(
        root,
        root / "data/processed" / TRC_OUTPUT_FILES["components"],
        trc_components_sha256,
        "admitted_quarterly_components",
    )
    weekly, identity, changes, daily = build_weekly_trc(
        pd.read_csv(io.BytesIO(ledger_raw), dtype=str), sources, registry
    )
    quarterly = quarter_tables(weekly, pd.read_csv(io.BytesIO(comp_raw), dtype=str))
    tables = {
        "weekly": weekly,
        "quarterly": quarterly,
        "identity": identity,
        "classification": changes,
        "daily_route": daily,
    }
    contracts = column_contracts(tables)
    payloads = {
        role: frame.to_csv(index=False, lineterminator="\n").encode()
        for role, frame in tables.items()
    }
    after = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in protected_paths
    }
    if before != after:
        raise ValueError("Admitted outputs changed")
    differences = [
        "difference_treasury_deposit_clock",
        "difference_fed_source_par_vs_z1",
        "difference_coupon_measurement_clock",
        "difference_remittance_source_clock",
        "difference_primary_cash_price",
        "difference_redemption_inflation",
        "difference_internal_postings",
        "difference_maturity_payment_clock",
        "difference_core",
    ]
    receipt = {
        "schema_version": "trc_weekly_v1",
        "producer_commit": commit,
        "vintage": vintage.name,
        "units": "USD million",
        "inputs": {
            "manifest": manifest_record,
            "fiscus_inputs": records,
            "ledger": ledger_record,
            "quarterly_components": comp_record,
        },
        "sample": {
            "first": weekly.date.iloc[0],
            "last": weekly.date.iloc[-1],
            "n_weeks": len(weekly),
        },
        "outputs": {
            role: {
                "path": "data/processed/" + OUTPUTS[role],
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            for role, raw in payloads.items()
        },
        "column_contracts": contracts,
        "classification_rule": CLASSIFICATION_RULE,
        "boundaries": BOUNDARIES,
        "status_counts": {
            col: {str(k): int(v) for k, v in weekly[col].value_counts().items()}
            for col in weekly
            if col.endswith("status")
        },
        "unclassifiable_cusip_changes": int(weekly.unclassifiable_changes.sum()),
        "weeks_with_unclassifiable_changes": int(
            weekly.unclassifiable_changes.gt(0).sum()
        ),
        "worst_identity_error": str(
            max(
                (abs(v) for v in identity.identity_error if v is not None), default=ZERO
            )
        ),
        "identity_available_rows": int(identity.identity_error.notna().sum()),
        "worst_quarterly_difference_identity_error": str(
            max(
                (abs(v) for v in quarterly.difference_identity_error.dropna()),
                default=ZERO,
            )
        ),
        "worst_quarterly_reserve_telescoping_error": str(
            max(
                (abs(v) for v in quarterly.reserve_telescoping_error.dropna()),
                default=ZERO,
            )
        ),
        "quarterly_reconciliation_by_era": describe_by_era(
            quarterly, differences, common=True, quarter_end=quarter_end
        ),
        "valuation_bridge_by_era": describe_by_era(
            quarterly, ["bridge_all_securities_premium_discount"], quarter_end=quarter_end
        ),
        "weekly_summary_by_era": describe_by_era(
            weekly,
            [
                "trc_core",
                "trc_par_sensitivity",
                "primary_cash_adjustment",
                "redemption_inflation",
                "j_applied",
                "j_candidate_only",
                "j_facility_dts_cash_candidate_only",
                "j_facility_dts_cash_candidate_only_absolute",
                "unclassifiable_abs_par",
                "unpriced_secondary_net_par",
                "primary_cash_unavailable_par",
                "redemption_cash_unavailable_par",
                "route_forward",
                "route_reverse",
            ],
            quarter_end=quarter_end,
        ),
        "unavailable_quarters": quarterly.loc[
            quarterly.trc_core.isna(), ["quarter", "unavailable_reasons"]
        ].to_dict("records"),
        "core_sample": {
            "n_weeks": int(weekly.trc_core.notna().sum()),
            "first": weekly.loc[weekly.trc_core.notna(), "date"].min(),
            "last": weekly.loc[weekly.trc_core.notna(), "date"].max(),
        },
        "unclassifiable_by_event_and_era": event_summary(changes, quarter_end),
        "internal_postings_by_status_and_era": internal_summary(weekly, quarter_end),
        "internal_cash_candidates_by_status_and_era": {
            era: {
                str(status): {
                    "n_weeks": len(g),
                    "candidate_only": None
                    if g.j_facility_dts_cash_candidate_only.isna().all()
                    else str(total(g.j_facility_dts_cash_candidate_only)),
                    "candidate_only_absolute": None
                    if g.j_facility_dts_cash_candidate_only_absolute.isna().all()
                    else str(total(g.j_facility_dts_cash_candidate_only_absolute)),
                }
                for status, g in window.groupby("j_facility_dts_cash_status")
            }
            for era, window in era_windows(weekly, quarter_end)
        },
        "snapshot_substitutions": [
            r
            for r in manifest["inputs"]["soma"]["source_metadata"].get("snapshots", [])
            if r.get("substitution_reason") not in (None, "exact_wednesday")
        ],
        "tips_contract_crosscheck": tips_crosscheck(
            sources["auctions"], sources["cpi"]
        ),
        "tips_redemption_index_status_counts": {
            str(k): int(v)
            for k, v in changes.loc[
                changes.security_type.eq("TIPS") & changes.redemptions_par.gt(ZERO),
                "redemption_status",
            ]
            .value_counts()
            .items()
        },
        "auction_field_coverage_by_era": auction_field_coverage(sources["auctions"], quarter_end),
        "frn_feed_semantics": frn_feed_semantics(sources["frn"]),
        "admitted_outputs_before": before,
        "admitted_outputs_after": after,
        "input_missingness": {
            "cpi_months": sources["cpi"]
            .loc[sources["cpi"].value.isin(["", ".", "null"]), "date"]
            .tolist(),
            "empty_soma_snapshots": [
                r["asof"]
                for r in manifest["inputs"]["soma"]["source_metadata"].get(
                    "snapshots", []
                )
                if r["status"] != "source_reported"
            ],
        },
        "internal_cash_event_crosswalk": list(WEEKLY_TRC_INTERNAL_MATCHES),
        "acquisition": {
            "fiscus": manifest.get("fiscus"),
            "manifest_sha256": inputs_manifest_sha256,
        },
    }
    for role, raw in payloads.items():
        (root / "data/processed" / OUTPUTS[role]).write_bytes(raw)
    (root / "data/processed" / OUTPUTS["receipt"]).write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    )
    return receipt
