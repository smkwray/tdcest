"""Par-valued weekly Treasury reserve component on the Thursday–Wednesday clock.

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

from .catalog import WEEKLY_TRC_REGISTRY
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
ERAS = (("2003Q3", "2008Q3"), ("2009Q1", "2015Q3"), ("2016Q1", "2025Q4"))
OUTPUTS = {
    "weekly": "trc_weekly_components_v1.csv",
    "quarterly": "trc_weekly_quarterly_v1.csv",
    "identity": "trc_weekly_identity_v1.csv",
    "classification": "trc_weekly_soma_changes_v1.csv",
    "daily_route": "trc_weekly_route_daily_v1.csv",
    "receipt": "trc_weekly_v1_receipt.json",
}
CLASSIFICATION_RULE = (
    "For each consecutive Wednesday and CUSIP: maturity on the Fed payment calendar removes opening par; "
    "auction soma_accepted on issue dates is a primary add-on; residual par increase/decrease is net "
    "secondary purchase/sale. Missing auction allotments or inconsistent maturity/snapshot metadata carry "
    "an unclassifiable status. Primary add-ons and maturity removals both enter net Fed par to offset "
    "Treasury cash; matched rollover amounts are memo only and never added twice. Inflation compensation "
    "stock changes are noncash and excluded from net par. Weekly snapshots cannot identify gross churn."
)
BOUNDARIES = [
    "Core is a par-valued public-data proxy, not an exact cash-settlement flow or a causal estimate.",
    "H.4.1 cash leg is reused verbatim; no monthly fund position is allocated to weeks and no preferred row exists.",
    "Coupons use actual payment dates and the latest strictly preceding weekly holding. Intraweek trades are unobserved.",
    "TIPS coupons use CPI-U NSA reference CPI interpolation and auction dated-date base; FRNs reconstruct daily interest per USD 100 from 13-week auction high rates and lifetime spread, with payment lockout; complete published daily-rate periods cross-check the reconstruction.",
    "TIPS principal inflation paid at redemption, bill discount, accrued purchase interest, and primary auction price "
    "differences are not in the par-valued core; the named securities bridge retains their effect together with source differences.",
    "The premium/discount bridge covers all securities and mixes cash-price differences, amortization and derecognition. "
    "It does not identify Treasury cash prices and is never added to core.",
    "Route upper is a same-day net-bill-funding envelope, conditional on no intraday recycling or lagged funding. "
    "It excludes SOMA allotments from issue cash and snapshot-held SOMA par from redemptions. It uses total ON RRP, not observed money-fund participation; it is not an unconditional bound on gross MMF purchases.",
    "DTS observed positive cash remittances are retained even during an aggregate deferred-asset period; "
    "negative earnings accruals are not remittances. A reported zero is used, never a deferred-asset-based forced zero.",
    "Missing snapshots, missing daily observations, or required payment-rate inputs produce unavailable values with statuses.",
    "Identities close with named source/valuation and payment bridges; closure does not independently validate core.",
]


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


def prepare_soma(frame):
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
    if (
        frame.empty
        or frame.duplicated(["asOfDate", "cusip"]).any()
        or not frame.asOfDate.dt.weekday.eq(2).all()
    ):
        raise ValueError("SOMA: empty, duplicate CUSIP/date or non-Wednesday snapshot")
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
    return {day: group.set_index("cusip") for day, group in frame.groupby("asOfDate")}


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
    return frame.sort_values("issue_date")


def classify_week(start, end, opening, closing, auctions, holidays):
    """Return a complete signed partition of net par; unknown classification never becomes a sale."""
    issued = auctions.loc[auctions.issue_date.gt(start) & auctions.issue_date.le(end)]
    records = []
    by_cusip = {cusip: group for cusip, group in issued.groupby("cusip")}
    for cusip in sorted(set(opening.index) | set(closing.index)):
        a = opening.loc[cusip] if cusip in opening.index else None
        b = closing.loc[cusip] if cusip in closing.index else None
        old, new = (
            (a.par if a is not None else ZERO),
            (b.par if b is not None else ZERO),
        )
        row = b if b is not None else a
        redemption = (
            old if start < payment_day(row.maturityDate, holidays) <= end else ZERO
        )
        matches = by_cusip.get(cusip, issued.iloc[:0])
        status = "classified_net_snapshot_change"
        primary = ZERO
        if (
            a is not None
            and b is not None
            and (a.maturityDate != b.maturityDate or a.securityType != b.securityType)
        ):
            status = "unclassifiable_changed_security_metadata"
        if redemption and new:
            status = "unclassifiable_held_after_maturity"
        if old > new and start < row.maturityDate <= end < payment_day(
            row.maturityDate, holidays
        ):
            status = "unclassifiable_maturity_snapshot_payment_clock"
        if not matches.empty:
            if matches.soma_accepted.isin(["", "null"]).any():
                status = "unclassifiable_missing_soma_auction_allotment"
            else:
                primary = sum(
                    (
                        decimal(v, "auction SOMA accepted") / MILLION
                        for v in matches.soma_accepted
                    ),
                    ZERO,
                )
        delta = new - old
        residual = delta + redemption - primary
        if a is None and matches.empty:
            # Existing seasoned CUSIP may enter through secondary purchase; metadata supports that inference.
            if row.maturityDate <= end:
                status = "unclassifiable_new_matured_security"
        inflation = (b.inflation if b is not None else ZERO) - (
            a.inflation if a is not None else ZERO
        )
        # Retain zero-par changes only if inflation or a primary/maturity event changed.
        if (
            delta
            or primary
            or redemption
            or inflation
            or status.startswith("unclassifiable")
        ):
            unknown = status.startswith("unclassifiable")
            records.append(
                {
                    "date": str(end.date()),
                    "cusip": cusip,
                    "security_type": row.securityType,
                    "opening_par": old,
                    "closing_par": new,
                    "delta_par": delta,
                    "redemptions_par": redemption,
                    "primary_addons_par": primary,
                    "secondary_purchases_par": None if unknown else max(residual, ZERO),
                    "secondary_sales_par": None if unknown else max(-residual, ZERO),
                    "unclassifiable_par": residual if unknown else ZERO,
                    "inflation_compensation_change_excluded": inflation,
                    "classification_status": status,
                }
            )
    if sum((r["delta_par"] for r in records), ZERO) != sum(closing.par, ZERO) - sum(
        opening.par, ZERO
    ):
        raise ValueError(
            "SOMA classification partition does not equal snapshot net par"
        )
    return records


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


def tips_ratio(cusip, day, auctions, cpi):
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
        if eligible.empty or (day - eligible.auction_date.iloc[-1]).days > 14:
            raise ValueError(f"FRN {cusip}: missing weekly bill index auction")
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
    """Payment-date coupons using the latest strictly prior weekly position; missing rates carry status."""
    total = ZERO
    issues = []
    # A nominal payment moved from Wednesday holiday to Thursday belongs to the following week.
    payment_months = pd.period_range(
        (start - pd.Timedelta(days=7)).to_period("M"), end.to_period("M"), freq="M"
    )
    for cusip, row in opening.iterrows():
        kind = row.securityType
        if kind == "Bills" or row.par == ZERO:
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
                    coupon = row.par / D(100) * per100
                else:
                    ratio = (
                        tips_ratio(cusip, nominal, auctions, cpi)
                        if kind == "TIPS"
                        else D(1)
                    )
                    coupon = row.par * ratio * row.rate / D(200)
                total += money(coupon)
            except ValueError as exc:
                issues.append(str(exc))
    return (None if issues else total), (
        "unavailable_payment_input:" + "|".join(issues)
        if issues
        else "payment_dates_prior_week_positions"
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


def route_daily(rrp, auctions, start, end, holidays, snapshots=None):
    """A conditional same-day net-settlement bound; no monthly money-fund interpolation."""
    rrp = rrp.copy()
    rrp["date"] = pd.to_datetime(rrp.date, errors="raise")
    if rrp.date.duplicated().any():
        raise ValueError("ON RRP: duplicate day")
    # FRED prints '.' on holidays; never treat missing open-business-day observations as zero.
    levels = {
        d: decimal(v, "ON RRP take-up") * D(1000)
        for d, v in zip(rrp.date, rrp.value)
        if str(v) not in (".", "", "nan")
    }
    bills = auctions.loc[auctions.security_type.eq("Bill")]
    issuance, redemption, unknown = {}, {}, set()
    for _, row in bills.iterrows():
        issue, maturity = row.issue_date, payment_day(row.maturity_date, holidays)
        if not (start <= issue <= end or start <= maturity <= end):
            continue
        try:
            par = decimal(row.total_accepted, "bill accepted") / MILLION
            soma = decimal(row.soma_accepted, "bill SOMA allotment") / MILLION
            if soma < ZERO or soma > par:
                raise ValueError("bill SOMA allotment exceeds total")
            price = decimal(row.price_per100, "bill price") / D(100)
            if not ZERO < price <= D(1):
                raise ValueError("bill issue price outside (0,100]")
        except ValueError:
            if start <= issue <= end:
                unknown.add(issue)
            if start <= maturity <= end:
                unknown.add(maturity)
            continue
        # All allotments supply a conservative net-cash capacity; counterparties are not classified as MMFs.
        issuance[issue] = issuance.get(issue, ZERO) + (par - soma) * price
        redemption[maturity] = redemption.get(maturity, ZERO) + par
    if snapshots is not None:
        snapshot_dates = sorted(snapshots)
        for cusip, group in bills.groupby("cusip"):
            maturity = payment_day(group.maturity_date.iloc[0], holidays)
            if not start <= maturity <= end or maturity in unknown:
                continue
            prior = [d for d in snapshot_dates if d < maturity]
            if not prior or (maturity - prior[-1]).days > 7:
                unknown.add(maturity)
                continue
            held = snapshots[prior[-1]]
            if cusip in held.index:
                redemption[maturity] -= held.loc[cusip].par
    records, previous = [], None
    for day in pd.date_range(start - pd.Timedelta(days=7), end):
        business = day.weekday() < 5 and day not in holidays
        level = levels.get(day)
        if day < ON_RRP_OPERATION_START:
            decline, upper, status = (
                ZERO,
                ZERO,
                "structural_zero_before_on_rrp_facility",
            )
        elif not business:
            decline, upper, status = ZERO, ZERO, "no_settlement_closed_day"
        elif level is None or previous is None:
            decline, upper, status = None, None, "unavailable_on_rrp_daily_observation"
        elif day in unknown:
            decline, upper, status = (
                max(previous - level, ZERO),
                None,
                "unavailable_bill_cash_price_or_allotment",
            )
        else:
            decline = max(previous - level, ZERO)
            upper = min(
                decline, max(issuance.get(day, ZERO) - redemption.get(day, ZERO), ZERO)
            ).quantize(CENT_MILLION, rounding=ROUND_DOWN)
            status = "conditional_same_day_net_bill_bound"
        if day >= start:
            net = (
                money(max(issuance.get(day, ZERO) - redemption.get(day, ZERO), ZERO))
                if day not in unknown
                else None
            )
            records.append(
                {
                    "date": str(day.date()),
                    "week": str(wednesday(day).date()),
                    "on_rrp_decline": decline,
                    "positive_net_bill_cash": net,
                    "route_lower": ZERO,
                    "route_upper": upper,
                    "route_status": status,
                }
            )
        if business:
            previous = (
                level  # A missing business day breaks the next day's decline too.
            )
    return pd.DataFrame(records)


def total(values):
    values = list(values)
    return (
        None
        if any(v is None or pd.isna(v) for v in values)
        else sum((decimal(v) for v in values), ZERO)
    )


def build_weekly_trc(ledger, sources):
    """Use admitted ledger cash unchanged; unavailable inputs propagate through core and identity."""
    dates = pd.DatetimeIndex(pd.to_datetime(ledger.date, errors="raise"))
    if (
        dates.has_duplicates
        or not dates.weekday.tolist() == [2] * len(dates)
        or not dates.to_series().diff().dropna().eq(pd.Timedelta(days=7)).all()
    ):
        raise ValueError("Ledger: expected consecutive unique Wednesdays")
    snapshots = prepare_soma(sources["soma"])
    auctions = prepare_auctions(sources["auctions"])
    first, last = (
        max(pd.Timestamp(WEEKLY_TRC_REGISTRY.inputs[0].snapshot_window[0]), dates[0]),
        min(pd.Timestamp(WEEKLY_TRC_REGISTRY.inputs[0].snapshot_window[1]), dates[-1]),
    )
    dates = dates[(dates >= first) & (dates <= last)]
    if dates.empty:
        raise ValueError("Ledger and SOMA do not overlap")
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
    remits, remit_status = remittance_weeks(sources["remittances"], dates, holidays)
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
            changes = classify_week(start, end, opening, closing, auctions, holidays)
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
        core = total([cash, fed, None if coupon is None else -coupon, remit])
        group = route[str(end.date())]
        upper = total(group.route_upper)
        lower = ZERO
        state = (
            "unavailable_required_input"
            if core is None
            else (
                "par_proxy_unclassifiable_changes"
                if unknown
                else "par_proxy_weekly_positions"
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
            "trc_core": core,
            "route_lower": lower,
            "route_upper": upper,
            "trc_lower": core,
            "trc_upper": total([core, upper]),
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
            min(result["redemptions_par"], result["primary_addons_par"])
            if fed is not None
            else None
        )
        weeks.append(result)
        for variant, gamma in (("core", ZERO), ("lower", lower), ("upper", upper)):
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
    changes = pd.DataFrame(
        all_changes,
        columns=[
            "date",
            "cusip",
            "security_type",
            "opening_par",
            "closing_par",
            "delta_par",
            "redemptions_par",
            "primary_addons_par",
            "secondary_purchases_par",
            "secondary_sales_par",
            "unclassifiable_par",
            "inflation_compensation_change_excluded",
            "classification_status",
        ],
    )
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
        "route_lower",
        "route_upper",
        "trc_lower",
        "trc_upper",
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
            "available_par_proxy"
            if row["trc_core"] is not None
            else "unavailable_required_weeks"
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
            row["difference_coupon_schedule_timing"] = total(
                [
                    None
                    if row["soma_coupon_cash"] is None
                    else -row["soma_coupon_cash"],
                    admitted_coupon,
                ]
            )
            row["difference_remittance_cash_timing"] = total(
                [row["cash_remittances"], -admitted_remit]
            )
            row["difference_core"] = total(
                [row["trc_core"], -row["admitted_quarterly_core"]]
            )
            row["difference_identity_error"] = total(
                [
                    row["difference_core"],
                    None
                    if any(
                        row[k] is None
                        for k in (
                            "difference_treasury_deposit_clock",
                            "difference_fed_source_par_vs_z1",
                            "difference_coupon_schedule_timing",
                            "difference_remittance_cash_timing",
                        )
                    )
                    else -sum(
                        (
                            row[k]
                            for k in (
                                "difference_treasury_deposit_clock",
                                "difference_fed_source_par_vs_z1",
                                "difference_coupon_schedule_timing",
                                "difference_remittance_cash_timing",
                            )
                        ),
                        ZERO,
                    ),
                ]
            )
            # Admitted components are binary floats printed to CSV; explicitly retain their decimal arithmetic residue.
            if row["difference_identity_error"] is not None and abs(
                row["difference_identity_error"]
            ) > D("0.000001"):
                raise ValueError("Quarterly admitted-component reconciliation failed")
        quarterly.append(row)
    return pd.DataFrame(quarterly)


def describe_by_era(frame, columns, *, common=False):
    out = {}
    for start, end in ERAS:
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


def column_contracts(tables):
    """Every output column has an explicit source and a clock, including diagnostics and statuses."""
    source = {
        "c_h": "admitted reserve_factor_ledger_weekly_v1:c_h (WDTGAL,WDSFAL)",
        "fed_leg_par": "soma.treasury_holdings: difference of sum(parValue)/1e6",
        "soma_coupon_cash": "soma.treasury_holdings + fiscaldata.auctions_query + fred.cpiaucns + fiscaldata.frn_daily_indexes; scheduled cash coupons",
        "cash_remittances": "fiscaldata.dts_deposits_withdrawals: Federal Reserve Earnings deposits",
        "route_lower": "definition: zero",
        "route_upper": "min(on_rrp_decline,positive_net_bill_cash), summed by week",
        "on_rrp_decline": "fred.rrpontsyd: positive decline from preceding business day, billion times 1000",
        "positive_net_bill_cash": "fiscaldata.auctions_query: (total bill allotments - SOMA accepted) times price minus (maturing bill par - prior-snapshot SOMA par); clipped at zero",
        "bridge_all_securities_premium_discount": "admitted ledger:f_unamortized_premiums+f_unamortized_discounts; ALL securities",
        "bridge_treasury_securities_source_inflation": "admitted ledger:s_h - fed_leg_par; includes H.4.1 inflation, source, maturity valuation and settlement differences",
        "bridge_coupon_remittance_payments": "soma_coupon_cash - cash_remittances",
        "bridge_published_rounding": "admitted ledger:rho",
        "non_treasury_signed_factors": "admitted ledger: all factors except TGA,SFP,Treasury securities,RRP others,premiums,discounts",
        "rrp_others_net_route": "admitted ledger:f_rrp_others - route",
        "trc_core": "c_h + fed_leg_par - soma_coupon_cash + cash_remittances",
        "trc_lower": "trc_core + route_lower",
        "trc_upper": "trc_core + route_upper",
        "trc": "trc_<variant>",
        "route": "route_<variant>, zero for core",
        "admitted_quarterly_core": "admitted trc_quarterly_components_v1:trc_core",
        "difference_core": "weekly-quarter trc_core - admitted quarterly trc_core",
        "difference_treasury_deposit_clock": "weekly-quarter c_h - admitted trc_cash_leg",
        "difference_fed_source_par_vs_z1": "weekly-quarter fed_leg_par - admitted fed_tsy_tx; source and par vs Z.1 valuation",
        "difference_coupon_schedule_timing": "admitted fed_tsy_coupon_interest_proxy - weekly-quarter soma_coupon_cash",
        "difference_remittance_cash_timing": "weekly-quarter cash_remittances - admitted fed_remit_positive",
        "difference_identity_error": "difference_core less four named differences; printed admitted float arithmetic residue",
        "reserve_telescoping_error": "sum weekly delta_reserve_balances less Wednesday endpoint difference",
        "reserve_balances_start": "admitted ledger:reserve_balances - delta_reserve_balances",
        "reserve_balances_end": "admitted ledger:reserve_balances",
        "delta_reserve_balances": "admitted ledger:delta_reserve_balances",
        "identity_rhs": "sum of trc, other factors, net RRP factor and named bridges",
        "identity_error": "delta_reserve_balances - identity_rhs, Decimal arithmetic",
        "soma_inflation_compensation_change_excluded": "soma.treasury_holdings: difference of inflationCompensation, excluded from core",
        "inflation_compensation_change_excluded": "soma.treasury_holdings: CUSIP inflationCompensation difference, excluded from par",
        "matched_rollover_par_memo": "min(weekly redemptions_par,primary_addons_par); aggregate memo, not security-level cash matching",
        "opening_par": "soma.treasury_holdings: prior snapshot parValue/1e6",
        "closing_par": "soma.treasury_holdings: current snapshot parValue/1e6",
        "delta_par": "closing_par - opening_par",
        "redemptions_par": "opening_par at scheduled maturity, CLASSIFICATION_RULE",
        "primary_addons_par": "fiscaldata.auctions_query:soma_accepted on issue date, CLASSIFICATION_RULE",
        "secondary_purchases_par": "positive net residual delta_par+redemptions_par-primary_addons_par, CLASSIFICATION_RULE",
        "secondary_sales_par": "negative net residual delta_par+redemptions_par-primary_addons_par, CLASSIFICATION_RULE",
        "unclassifiable_par": "unresolved classification residual, CLASSIFICATION_RULE",
        "unclassifiable_changes": "count of CUSIP changes carrying unclassifiable status",
    }
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
    *, root, inputs_manifest_sha256, ledger_sha256, trc_components_sha256
):
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
        root / WEEKLY_TRC_REGISTRY.manifest,
        inputs_manifest_sha256,
        "weekly_inputs_manifest",
    )
    manifest = json.loads(manifest_raw)
    sources, records = load_fiscus_inputs(root, manifest, WEEKLY_TRC_REGISTRY)
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
        pd.read_csv(io.BytesIO(ledger_raw), dtype=str), sources
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
        "difference_coupon_schedule_timing",
        "difference_remittance_cash_timing",
        "difference_core",
    ]
    receipt = {
        "schema_version": "trc_weekly_v1",
        "producer_commit": commit,
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
            quarterly, differences, common=True
        ),
        "valuation_bridge_by_era": describe_by_era(
            quarterly, ["bridge_all_securities_premium_discount"]
        ),
        "weekly_summary_by_era": describe_by_era(
            weekly, ["trc_core", "route_lower", "route_upper"]
        ),
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
