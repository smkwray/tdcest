"""Independent cash-event and source-contract courts for the production weekly proxy."""

from decimal import Decimal as D

import pandas as pd
import pytest

from test_weekly_trc import auction, fixture, holding, target
from tdc_estimator.weekly_trc import (
    allocate_route_capacity,
    bill_total_par,
    build_weekly_trc,
    classify_week,
    coupon_week,
    frn_coupon_per100,
    internal_postings,
    prepare_auctions,
    prepare_soma,
    primary_cash,
    quarter_tables,
    redemption_cash,
    remittance_weeks,
    rollover_memo,
    route_daily,
    tips_crosscheck,
    frn_feed_semantics,
)

START, END = pd.Timestamp("2021-12-29"), pd.Timestamp("2022-01-05")


def event_build(
    cash,
    securities,
    reserves,
    *,
    additions=None,
    rate="0",
    maturity="2032-01-31",
    kind="NotesBonds",
    inflation="0",
    auctions=None,
):
    ledger, sources = fixture()
    sources["soma"]["coupon"] = rate
    sources["soma"]["maturityDate"] = maturity
    sources["soma"]["securityType"] = kind
    if additions is not None:
        sources["soma"] = pd.concat(
            [sources["soma"], pd.DataFrame(additions)], ignore_index=True
        )
    if auctions is not None:
        sources["auctions"] = pd.DataFrame(auctions)
    h = ledger.date.eq(str(END.date()))
    ledger.loc[h, ["c_h", "s_h", "f_treasury_securities", "delta_reserve_balances"]] = [
        str(cash),
        str(securities),
        str(securities),
        str(reserves),
    ]
    ledger.loc[h, "rho"] = str(D(reserves) - D(cash) - D(securities))
    ledger.loc[ledger.date.ge(str(END.date())), "reserve_balances"] = str(
        1000 + D(reserves)
    )
    return ledger, sources


def partition(
    open_rows,
    close_rows,
    auction_rows,
    *,
    start=START,
    end=END,
    holidays=None,
    cpi=None,
):
    def positions(rows, day):
        if not rows:
            return pd.DataFrame(
                columns=["par", "maturityDate", "securityType", "inflation", "rate"]
            )
        return prepare_soma(pd.DataFrame(rows))[day]

    return classify_week(
        start,
        end,
        positions(open_rows, start),
        positions(close_rows, end),
        prepare_auctions(pd.DataFrame(auction_rows)),
        holidays or set(),
        cpi,
    )


def test_primary_cash_bill_neutrality():
    a = auction("NEW", "2022-01-04", "2022-04-05", soma="100000000", price="99")
    additions = [
        holding(str(d.date()), "NEW", kind="Bills", maturity="2022-04-05")
        for d in pd.date_range(END, "2022-03-30", freq="W-WED")
    ]
    ledger, sources = event_build(-99, 99, 0, additions=additions, auctions=[a])
    row = target(build_weekly_trc(ledger, sources))
    assert row.primary_cash_adjustment == -1
    assert row.trc_core == 0 and row.trc_par_sensitivity == 1


def test_reopening_accrual_dirty_price():
    a = auction("REOPEN", price="98", kind="Note")
    a["accrued_int_per1000"] = "10"
    assert primary_cash(pd.Series(a), D(100)) == 99
    a.pop("accrued_int_per1000")
    a["dated_date"] = "2020-01-01"
    with pytest.raises(ValueError, match="accrued interest"):
        primary_cash(pd.Series(a), D(100))


def test_tips_primary_indexed_once():
    a = auction("TIPS", price="98", kind="Note")
    a.update(
        inflation_index_security="Yes",
        index_ratio_on_issue_date="1.05",
        adj_price="102.9",
        adj_accrued_int_per1000="10.5",
    )
    assert primary_cash(pd.Series(a), D(100)) == D("103.95")
    a.pop("adj_price")
    a.pop("adj_accrued_int_per1000")
    a.update(unadj_price="98", unadj_accrued_int_per1000="10")
    assert primary_cash(pd.Series(a), D(100)) == D("103.95")


@pytest.mark.parametrize("ratio,expected", [("1.05", 105), ("0.95", 100)])
def test_tips_redemption_cash_and_floor(ratio, expected):
    a = prepare_auctions(pd.DataFrame([auction("OLD", kind="Note")]))
    cpi = {
        pd.Period("2021-10", freq="M"): D(ratio) * 100,
        pd.Period("2021-11", freq="M"): D(ratio) * 100,
    }
    cash = redemption_cash(D(100), "TIPS", "OLD", pd.Timestamp("2022-01-04"), a, cpi)
    assert cash == expected
    ledger, sources = event_build(
        expected,
        -expected,
        0,
        kind="TIPS",
        maturity="2022-01-04",
        auctions=[auction("OLD", kind="Note")],
    )
    sources["soma"].loc[sources["soma"].asOfDate.ge(str(END.date())), "parValue"] = "0"
    sources["cpi"]["value"] = str(D(ratio) * 100)
    row = target(build_weekly_trc(ledger, sources))
    assert row.trc_core == 0 and row.redemption_inflation == D(expected) - 100


def test_tips_noncash_accrual_excluded():
    ledger, sources = event_build(0, 0, 0, kind="TIPS", maturity="2032-04-15")
    sources["soma"].loc[
        sources["soma"].asOfDate.ge(str(END.date())), "inflationCompensation"
    ] = "5000000"
    row = target(build_weekly_trc(ledger, sources))
    assert row.trc_core == 0 and row.soma_inflation_compensation_change_excluded == 5


def test_settlement_partition_auction_only_cusip():
    a = auction("INVISIBLE", "2022-01-04", soma="50000000")
    records = partition([], [], [a])
    assert len(records) == 1
    r = records[0]
    assert (
        r["primary_addons_par"] == 50
        and r["secondary_sales_par"] == 50
        and r["delta_par"] == 0
    )


def test_missing_allotment_and_expected_auction_are_not_secondary():
    open_rows = [holding(str(START.date()))]
    close_rows = [holding(str(END.date()), par=110)]
    a = auction("OLD", "2022-01-04", soma="null", kind="Note")
    r = partition(open_rows, close_rows, [a])[0]
    assert r["secondary_purchases_par"] is None and r["unclassifiable_abs_par"] == 10
    b = holding(str(END.date()), "NEW", par=60)
    b["issueDate"] = "2022-01-04"
    r = partition([], [b], [auction()])[0]
    assert (
        r["secondary_purchases_par"] is None
        and "expected_auction" in r["classification_status"]
    )


def test_partial_rollover_full_retirement():
    a = auction("NEW", "2022-01-04", soma="60000000", kind="Note")
    records = partition(
        [holding(str(START.date()), maturity="2022-01-04")],
        [holding(str(END.date()), "NEW", par=60)],
        [a],
    )
    old = next(r for r in records if r["cusip"] == "OLD")
    assert old["redemptions_par"] == 100 and old["closing_par"] == 0
    assert rollover_memo(records, prepare_auctions(pd.DataFrame([a]))) == 60
    assert 100 - 60 == 40


def test_rollover_date_match_not_weekly_minimum():
    a = auction("NEW", "2022-01-03", soma="100000000", kind="Note")
    records = partition(
        [holding(str(START.date()), maturity="2022-01-04")],
        [holding(str(END.date()), "NEW")],
        [a],
    )
    assert rollover_memo(records, prepare_auctions(pd.DataFrame([a]))) == 0


def test_gross_churn_is_unobserved_not_zero():
    records = partition(
        [holding(str(START.date()), kind="TIPS")],
        [holding(str(END.date()), kind="TIPS", inflation="1000000")],
        [auction("OLD", kind="Note")],
    )
    assert records[0]["delta_par"] == 0
    assert records[0]["gross_trade_status"] == "unobserved_intraweek_gross_trades"


def test_redemption_entitlement_no_intervening_trade_assumption():
    r = partition(
        [holding(str(START.date()), maturity="2022-01-04")],
        [],
        [auction("OLD", kind="Note")],
    )[0]
    assert r["redemptions_par"] == 100
    assert "no_intervening_trade" in r["redemption_status"]
    # Weekly endpoints cannot distinguish a pre-maturity sale from actual Fed redemption.
    assert r["gross_trade_status"].startswith("unobserved")


def internal_h(facility=0, sdr=0, gold=0):
    return pd.Series(
        dict(
            f_treasury_contributions_to_credit_facilities=str(facility),
            f_sdr_certificate_account=str(sdr),
            f_gold_stock=str(gold),
        )
    )


def dts_cash(amount, kind="Withdrawals", account="Treasury General Account (TGA)"):
    return pd.DataFrame(
        [
            dict(
                record_date="2022-01-04",
                transaction_catg="ESF - Economic Recovery Programs",
                transaction_type=kind,
                account_type=account,
                transaction_today_amt=str(amount),
            )
        ]
    )


@pytest.mark.parametrize("cash,candidate", [(100, -100), (-100, 100)])
def test_internal_cash_and_return_neutral(cash, candidate):
    j = internal_postings(internal_h(candidate), END, dts_cash(cash))
    assert j["j_applied"] == candidate and D(cash) + j["j_applied"] == 0
    assert j["j_candidate_only"] == 0


def test_internal_reclassification_without_cash_stays_candidate():
    j = internal_postings(internal_h(-100), END, dts_cash(0))
    assert j["j_applied"] == 0 and j["j_candidate_only"] == -100
    assert "mismatch" in j["j_treasury_contributions_to_credit_facilities_status"]


def test_certificate_account_not_automatically_tga():
    j = internal_postings(
        internal_h(sdr=100, gold=2),
        END,
        dts_cash(100, account="Special Treasury account"),
    )
    assert j["j_applied"] == 0 and j["j_candidate_only"] == 102
    assert "special_account" in j["j_sdr_certificate_account_status"]


def test_coupon_entitlement_primary_before_payment_and_accrued_interest_once():
    a = auction(
        "OLD", "2022-01-03", "2032-01-04", soma="100000000", kind="Note", price="98"
    )
    a.update(accrued_int_per1000="10", int_rate="2")
    ledger, sources = event_build(
        -97, 99, 0, rate="2", maturity="2032-01-04", auctions=[a]
    )
    sources["soma"].loc[sources["soma"].asOfDate.ge(str(END.date())), "parValue"] = (
        "200000000"
    )
    row = target(build_weekly_trc(ledger, sources))
    assert (
        row.soma_coupon_cash == 2
        and row.primary_cash_adjustment == -1
        and row.trc_core == 0
    )
    assert "secondary_entitlement_unobserved" in row.coupon_status


def test_coupon_entitlement_auction_only_primary():
    _, sources = fixture()
    a = auction("NEW", "2022-01-03", "2032-01-04", soma="100000000", kind="Note")
    a["int_rate"] = "2"
    positions = prepare_soma(sources["soma"])[START]
    coupon, _ = coupon_week(
        START,
        END,
        positions,
        positions,
        prepare_auctions(pd.DataFrame([a])),
        {},
        sources["frn"],
        set(),
    )
    assert coupon == 1


def test_tips_contract_index_mismatch_reported():
    a = auction("OLD", kind="Note")
    a.update(inflation_index_security="Yes", index_ratio_on_issue_date="1.05")
    _, sources = fixture()
    a["issue_date"] = "2022-01-04"
    result = tips_crosscheck(pd.DataFrame([a]), sources["cpi"])
    assert result["checked"] == 1 and result["mismatch_count"] == 1
    assert result["mismatches"][0]["difference"] == "-0.05000"


def test_frn_no_auction_carry_and_missing_feed_distinct():
    b = auction("BILL", "2021-12-23", "2022-03-24")
    b["auction_date"] = "2021-12-20"
    n = auction("FRN", "2022-01-31", "2024-01-31", kind="Note")
    n["auction_date"] = "2022-01-26"
    a = prepare_auctions(pd.DataFrame([b, n]))
    value = frn_coupon_per100(
        "FRN",
        pd.Timestamp("2022-01-10"),
        pd.Timestamp("2022-01-20"),
        pd.Timestamp("2022-01-20"),
        a,
        set(),
    )
    assert (
        value > 0
    )  # latest index is 21 to 30 days old, but the complete query documents no new auction.
    a.attrs.clear()
    with pytest.raises(ValueError, match="feed coverage"):
        frn_coupon_per100(
            "FRN",
            pd.Timestamp("2022-01-10"),
            pd.Timestamp("2022-01-20"),
            pd.Timestamp("2022-01-20"),
            a,
            set(),
        )


def test_frn_interval_dates_and_units():
    f = pd.DataFrame(
        [
            dict(
                record_date="2024-11-01",
                start_of_accrual_period="2024-11-03",
                end_of_accrual_period="2024-11-04",
                daily_accrued_int_per100="0.01",
            )
        ]
    )
    assert (
        frn_feed_semantics(f)["status"]
        == "observed_one_day_start_inclusive_end_exclusive"
    )
    f["end_of_accrual_period"] = "2024-11-05"
    with pytest.raises(ValueError, match="one-calendar-day"):
        frn_feed_semantics(f)


def test_coverage_first_complete_remittance_week():
    x = dts_cash(0)
    x["transaction_catg"] = "Federal Reserve Earnings"
    x["transaction_type"] = "Deposits"
    x = pd.concat(
        [
            x.assign(record_date=str(d.date()))
            for d in pd.bdate_range("2005-10-03", "2005-10-12")
        ]
    )
    dates = pd.DatetimeIndex(["2005-10-05", "2005-10-12"])
    amounts, status = remittance_weeks(x, dates, set())
    assert amounts[dates[0]] is None and amounts[dates[1]] == 0
    assert status[dates[0]].startswith("unavailable")


def test_incomplete_quarter_never_partial_sum():
    ledger, sources = fixture()
    weekly = build_weekly_trc(ledger, sources)[0]
    comp = pd.DataFrame(
        [
            dict(
                quarter="2022Q1",
                trc_cash_leg="0",
                fed_tsy_tx="0",
                fed_tsy_coupon_interest_proxy="0",
                fed_remit_positive="0",
                trc_core="0",
            )
        ]
    )
    q = (
        quarter_tables(weekly.loc[weekly.date.ne("2022-01-05")], comp)
        .set_index("quarter")
        .loc["2022Q1"]
    )
    assert (
        q.trc_core is None and "incomplete_wednesday_quarter" in q.unavailable_reasons
    )


def daily_route_fixture(*, redemption=200, level_before="0.2", level_after="0.1"):
    days = pd.bdate_range("2024-01-25", "2024-02-07")
    rrp = pd.DataFrame(
        dict(
            date=days,
            value=[
                level_before if d < pd.Timestamp("2024-02-05") else level_after
                for d in days
            ],
        )
    )
    a = [auction("NEW", "2024-02-05", "2024-05-06", par="100000000")]
    if redemption:
        a.append(
            auction("OLD", "2023-11-06", "2024-02-05", par=str(redemption * 1000000))
        )
    return (
        route_daily(
            rrp,
            prepare_auctions(pd.DataFrame(a)),
            pd.Timestamp("2024-02-01"),
            pd.Timestamp("2024-02-07"),
            set(),
        )
        .set_index("date")
        .loc["2024-02-05"]
    )


def test_route_netting_counterexample():
    r = daily_route_fixture()
    assert r.positive_net_bill_cash == 0 and r.net_bill_on_rrp_overlap == 0
    assert r.route_forward == 100


def test_route_participant_netting():
    r = daily_route_fixture(redemption=0, level_after="0.2")
    assert (
        r.on_rrp_decline == 0
        and r.net_bill_on_rrp_overlap == 0
        and r.route_forward == 100
    )


def test_route_reverse_sign():
    r = daily_route_fixture(redemption=100, level_before="0", level_after="0.1")
    assert r.route_reverse == -100 and r.route_baseline == 0


def test_route_shared_capacity():
    assert allocate_route_capacity(D(100), ["0.6", "0.4"]) == [60, 40]
    with pytest.raises(ValueError, match="shared capacity"):
        allocate_route_capacity(D(100), [1, 1])


@pytest.mark.parametrize(
    "soma_included,total", [("Yes", "120000000"), ("No", "100000000")]
)
def test_route_soma_and_fima_inclusion_once(soma_included, total):
    a = auction(par=total, soma="20000000")
    a.update(
        soma_included=soma_included,
        fima_noncomp_accepted="5000000",
        fima_included="Yes",
    )
    full, soma = bill_total_par(pd.Series(a))
    assert full - soma == 100
    a["fima_included"] = "No"
    a["total_accepted"] = str(int(total) - 5000000)
    assert bill_total_par(pd.Series(a))[0] - soma == 100


def test_route_perimeter_bridge_and_foreign_bank_correspondent():
    ledger, sources = fixture()
    h = ledger.date.eq(str(END.date()))
    ledger.loc[h, "f_rrp_others"] = "-10"
    ledger.loc[h, "rho"] = "10"
    row = target(build_weekly_trc(ledger, sources))
    assert row.rrp_others_vs_on_rrp_flow_bridge == -10
    # No ownership-only foreign correction exists; foreign/GSE allocation needs a declared shared route.
    assert row.route_baseline == 0


def test_identity_mutation_is_not_validation():
    ledger, sources = event_build(1, 0, 0, rate="2", maturity="2032-01-04")
    good = build_weekly_trc(ledger, sources)
    assert target(good).trc_core == 0
    sources["soma"]["coupon"] = "4"
    bad = build_weekly_trc(ledger, sources)
    assert (
        good[1].identity_error.dropna().eq(0).all()
        and bad[1].identity_error.dropna().eq(0).all()
    )
    with pytest.raises(AssertionError):
        assert target(bad).trc_core == 0


def test_secondary_cash_is_unpriced_par_proxy():
    ledger, sources = event_build(0, 99, 99)
    sources["soma"].loc[sources["soma"].asOfDate.ge(str(END.date())), "parValue"] = (
        "200000000"
    )
    row = target(build_weekly_trc(ledger, sources))
    assert row.trc_core == 100 and row.unpriced_secondary_net_par == 100
    assert "prices_and_entitlements_unobserved" in row.core_status
    assert (
        row.delta_reserve_balances == 99
    )  # observed reserve cash; proxy's +1 error stays in a named source bridge.


def test_coupon_remittance_neutral_and_all_security_premium_excluded():
    ledger, sources = event_build(1, 0, 0, rate="2", maturity="2032-01-04")
    sources["remittances"].loc[
        sources["remittances"].record_date.eq("2022-01-04"), "transaction_today_amt"
    ] = "2"
    ledger.loc[ledger.date.eq(str(END.date())), ["c_h", "rho"]] = ["-1", "1"]
    result = build_weekly_trc(ledger, sources)
    assert target(result).trc_core == 0
    ledger.loc[ledger.date.eq(str(END.date())), ["f_unamortized_premiums", "rho"]] = [
        "8",
        "-7",
    ]
    assert target(build_weekly_trc(ledger, sources)).trc_core == 0


def test_reverse_repo_not_outright_sale():
    ledger, sources = fixture()
    h = ledger.date.eq(str(END.date()))
    ledger.loc[h, ["f_rrp_others", "rho"]] = ["-100", "100"]
    row = target(build_weekly_trc(ledger, sources))
    assert row.fed_leg_par == 0 and row.trc_core == 0


def test_settlement_clock_ignores_auction_announcement_and_publication():
    a = auction("NEW", "2022-01-06", soma="100000000")
    a["auction_date"] = "2022-01-04"
    assert partition([], [], [a]) == []
    assert (
        partition([], [], [a], start=END, end=pd.Timestamp("2022-01-12"))[0][
            "primary_addons_par"
        ]
        == 100
    )


def test_holiday_payment_and_nominal_maturity_month_separate():
    holidays = {pd.Timestamp("2024-07-31")}
    start, end = pd.Timestamp("2024-07-24"), pd.Timestamp("2024-07-31")
    records = partition(
        [holding(str(start.date()), maturity=str(end.date()))],
        [],
        [auction("OLD", kind="Note")],
        start=start,
        end=end,
        holidays=holidays,
    )
    r = records[0]
    assert r["redemptions_par"] == 0 and r["settlement_clock_adjustment"] == 100
    assert (
        r["nominal_maturity_date"] == "2024-07-31" and r["payment_date"] == "2024-08-01"
    )
    old = prepare_soma(
        pd.DataFrame([holding(str(start.date()), maturity=str(end.date()))])
    )[start]
    empty = pd.DataFrame(columns=old.columns)
    r = classify_week(
        end,
        pd.Timestamp("2024-08-07"),
        empty,
        empty,
        prepare_auctions(pd.DataFrame([auction("OLD", kind="Note")])),
        holidays,
        deferred={"OLD": old.loc["OLD"]},
    )[0]
    assert r["redemptions_par"] == 100 and r["settlement_clock_adjustment"] == -100


def test_internal_cash_partial_verified_dated_transfer():
    frame = dts_cash(37500)
    frame["record_date"] = "2020-05-11"
    j = internal_postings(internal_h(-47500), pd.Timestamp("2020-05-13"), frame)
    assert j["j_applied"] == -37500 and j["j_candidate_only"] == -10000
    assert (
        j["j_treasury_contributions_to_credit_facilities_status"]
        == "applied_dated_cash_partial_stock_remainder_candidate"
    )


def test_internal_cash_individual_return_not_netted_with_unrelated_esf():
    a = dts_cash(-41294)
    b = dts_cash(177)
    b["record_date"] = "2022-01-03"
    j = internal_postings(internal_h(41294), END, pd.concat([a, b]))
    assert j["j_applied"] == 41294 and j["j_facility_dts_cash_candidate"] == 41117


def test_tips_contract_index_preferred_over_revised_cpi():
    original = auction("OLD", kind="Note")
    original.update(inflation_index_security="Yes", ref_cpi_on_issue_date="100")
    same_date = auction("OTHER", "2022-01-04", kind="Note")
    same_date.update(
        inflation_index_security="Yes",
        ref_cpi_on_dated_date="105",
        ref_cpi_on_issue_date="105",
    )
    a = prepare_auctions(pd.DataFrame([original, same_date]))
    revised = {
        pd.Period("2021-10", freq="M"): D(95),
        pd.Period("2021-11", freq="M"): D(95),
    }
    assert (
        redemption_cash(D(100), "TIPS", "OLD", pd.Timestamp("2022-01-04"), a, revised)
        == 105
    )


def test_tips_reopening_base_does_not_map_to_later_coupon_date():
    original = auction("OLD", "2021-01-15", kind="Note")
    original.update(
        inflation_index_security="Yes",
        ref_cpi_on_dated_date="100",
        ref_cpi_on_issue_date="100",
    )
    reopen = auction("OLD", "2021-07-30", kind="Note")
    reopen.update(
        inflation_index_security="Yes",
        dated_date="2021-07-15",
        original_dated_date="null",
        ref_cpi_on_dated_date="100",
        ref_cpi_on_issue_date="105",
    )
    a = prepare_auctions(pd.DataFrame([original, reopen]))
    assert pd.Timestamp("2021-07-15") not in a.attrs["contractual_reference_cpi"]
    assert a.attrs["contractual_reference_cpi"][pd.Timestamp("2021-07-30")] == 105
