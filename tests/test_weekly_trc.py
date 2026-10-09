"""Economic posting courts exercise the production builder and the hash-pinned CLI."""

from __future__ import annotations

from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import subprocess

import pandas as pd
import pytest

from tdc_estimator.catalog import WEEKLY_TRC_REGISTRY
from tdc_estimator.cli import main
from tdc_estimator.reserve_factor_ledger import LEDGER_OUTPUT_FILES, load_h41_rows
from tdc_estimator.trc_export import TRC_OUTPUT_FILES
from tdc_estimator.weekly_trc import (
    FedPaymentCalendar,
    OUTPUTS,
    build_weekly_trc,
    classify_week,
    coupon_week,
    prepare_auctions,
    prepare_soma,
    quarter_tables,
    frn_coupon_per100,
)


def holding(
    day,
    cusip="OLD",
    par=100,
    maturity="2032-01-31",
    coupon="0",
    kind="NotesBonds",
    inflation="0",
):
    return dict(
        asOfDate=day,
        cusip=cusip,
        parValue=str(par * 1000000),
        maturityDate=maturity,
        coupon=coupon,
        securityType=kind,
        inflationCompensation=inflation,
    )


def auction(
    cusip="SEED",
    issue="2021-01-07",
    maturity="2021-04-08",
    soma="0",
    par="100000000",
    price="100",
    kind="Bill",
):
    return dict(
        cusip=cusip,
        issue_date=issue,
        maturity_date=maturity,
        soma_accepted=soma,
        total_accepted=par,
        price_per100=price,
        security_type=kind,
        auction_date="2021-01-04",
        security_term="13-Week",
        high_discnt_rate="0.1",
        spread="0.1",
        ref_cpi_on_dated_date="100",
        accrued_int_per1000="0",
        soma_included="No",
        fima_included="Yes",
        fima_noncomp_accepted="0",
        dated_date=issue,
        int_rate="0",
        inflation_index_security="No",
        floating_rate="No",
    )


def fixture():
    dates = pd.date_range("2021-12-29", "2022-03-30", freq="W-WED")
    factors = ["f_" + k for k, v in load_h41_rows().items() if v.row.role == "factor"]
    ledger = pd.DataFrame(
        [
            {
                **dict.fromkeys(factors, "0"),
                "date": str(d.date()),
                "c_h": "0",
                "s_h": "0",
                "reserve_balances": "1000",
                "delta_reserve_balances": "0",
                "rho": "0",
            }
            for d in dates
        ]
    )
    holidays = set(FedPaymentCalendar().holidays("2021-01-01", "2023-01-01"))
    days = [
        d
        for d in pd.date_range("2021-12-20", "2022-03-30")
        if d.weekday() < 5 and d not in holidays
    ]
    sources = {
        "soma": pd.DataFrame([holding(str(d.date())) for d in dates]),
        "auctions": pd.DataFrame([auction()]),
        "cpi": pd.DataFrame(
            {
                "date": [
                    "2021-09-01",
                    "2021-10-01",
                    "2021-11-01",
                    "2021-12-01",
                    "2022-01-01",
                ],
                "value": ["100"] * 5,
            }
        ),
        "frn": pd.DataFrame(
            columns=["cusip", "start_of_accrual_period", "daily_accrued_int_per100"]
        ),
        "internal_dts": pd.DataFrame(
            columns=[
                "record_date",
                "transaction_catg",
                "account_type",
                "transaction_type",
                "transaction_today_amt",
            ]
        ),
        "remittances": pd.DataFrame(
            [
                dict(
                    record_date=str(d.date()),
                    account_type="Treasury General Account (TGA)",
                    transaction_type="Deposits",
                    transaction_catg="Federal Reserve Earnings",
                    transaction_today_amt="0",
                )
                for d in days
            ]
        ),
        "on_rrp": pd.DataFrame(
            {"date": [str(d.date()) for d in days], "value": ["1"] * len(days)}
        ),
    }
    return ledger, sources


def target(result, date="2022-01-05"):
    return result[0].set_index("date").loc[date]


@pytest.mark.parametrize(
    "event",
    [
        "redemption",
        "rollover",
        "addon",
        "coupon",
        "remittance",
        "purchase",
        "sale",
        "inflation",
    ],
)
def test_postings_zero_transfers_and_signed_secondary_reserves(event):
    ledger, sources = fixture()
    cash = fed = reserve = 0
    if event in ("redemption", "rollover"):
        sources["soma"].loc[sources["soma"].cusip.eq("OLD"), "maturityDate"] = (
            "2022-01-04"
        )
        after = sources["soma"].asOfDate.ge("2022-01-05")
        sources["soma"].loc[after, "cusip"] = "NEW"
        sources["soma"].loc[after, "maturityDate"] = "2032-01-31"
        # Retain a holding to make each snapshot a valid nonempty portfolio.
        if event == "redemption":
            sources["soma"].loc[after, "parValue"] = "1000000"
            sources["soma"].loc[~after, "parValue"] = "101000000"
            cash, fed = 101, -100
            # New 1-unit primary purchase is offset by TGA payment, leaving redemption net.
            cash = 100
            sources["auctions"] = pd.DataFrame(
                [
                    auction(
                        "NEW",
                        "2022-01-04",
                        "2032-01-31",
                        "1000000",
                        "1000000",
                        kind="Note",
                    )
                ]
            )
        else:
            sources["auctions"] = pd.DataFrame(
                [auction("NEW", "2022-01-04", "2032-01-31", "100000000", kind="Note")]
            )
    elif event in ("purchase", "sale", "addon"):
        size = 10 if event != "sale" else -10
        sources["soma"].loc[sources["soma"].asOfDate.ge("2022-01-05"), "parValue"] = (
            str((100 + size) * 1000000)
        )
        fed = size
        if event == "addon":
            cash = -10
            sources["auctions"] = pd.DataFrame(
                [auction("OLD", "2022-01-04", "2032-01-31", "10000000", kind="Note")]
            )
        else:
            reserve = size
    elif event == "coupon":
        # Actual payment Tuesday Jan 4, avoiding the scheduled maturity's principal.
        sources["soma"]["maturityDate"] = "2032-01-04"
        sources["soma"]["coupon"] = "2"
        cash = 1
    elif event == "remittance":
        sources["remittances"].loc[
            sources["remittances"].record_date.eq("2022-01-04"), "transaction_today_amt"
        ] = "2"
        cash = -2
    else:
        sources["soma"]["securityType"] = "TIPS"
        sources["soma"]["maturityDate"] = "2032-04-15"
        sources["soma"].loc[
            sources["soma"].asOfDate.ge("2022-01-05"), "inflationCompensation"
        ] = "3000000"
        ledger.loc[ledger.date.eq("2022-01-05"), "s_h"] = "3"
        ledger.loc[ledger.date.eq("2022-01-05"), "f_treasury_securities"] = "3"
        ledger.loc[ledger.date.eq("2022-01-05"), "f_other_liabilities_and_capital"] = (
            "-3"
        )
    ledger.loc[ledger.date.eq("2022-01-05"), "c_h"] = str(cash)
    if event != "inflation":
        ledger.loc[ledger.date.eq("2022-01-05"), "s_h"] = str(fed)
        ledger.loc[ledger.date.eq("2022-01-05"), "f_treasury_securities"] = str(fed)
    ledger.loc[ledger.date.eq("2022-01-05"), "delta_reserve_balances"] = str(reserve)
    ledger.loc[ledger.date.ge("2022-01-05"), "reserve_balances"] = str(1000 + reserve)
    # Synthetic ledger must balance independent of core.
    ledger.loc[ledger.date.eq("2022-01-05"), "rho"] = str(
        reserve
        - cash
        - (3 if event == "inflation" else fed)
        + (3 if event == "inflation" else 0)
    )
    result = build_weekly_trc(ledger, sources)
    row = target(result)
    assert row.trc_core == D(reserve)
    assert all(v == 0 for v in result[1].identity_error.dropna())
    if event == "redemption":
        assert row.redemptions_par == 101 and row.primary_addons_par == 1
    if event == "rollover":
        assert row.c_h == 0 and row.matched_rollover_par_memo == 100
    if event == "purchase":
        assert row.secondary_purchases_par == 10
    if event == "sale":
        assert row.secondary_sales_par == 10
    if event == "inflation":
        assert (
            row.fed_leg_par == 0
            and row.soma_inflation_compensation_change_excluded == 3
        )


def test_missing_snapshot_and_required_values_fail_closed():
    ledger, sources = fixture()
    sources["soma"] = sources["soma"].loc[sources["soma"].asOfDate.ne("2022-01-05")]
    result = build_weekly_trc(ledger, sources)
    assert target(result).trc_core is None
    assert target(result, "2022-01-12").trc_core is None
    assert target(result).soma_status == "unavailable_missing_consecutive_snapshot"
    sources["soma"].loc[sources["soma"].index[0], "parValue"] = "null"
    with pytest.raises(ValueError, match="malformed"):
        build_weekly_trc(ledger, sources)


def test_unknown_auction_is_recorded_and_never_assigned_secondary_purchase():
    _, sources = fixture()
    s = prepare_soma(sources["soma"])
    a = prepare_auctions(
        pd.DataFrame([auction("OLD", "2022-01-04", "2032-01-31", "null", kind="Note")])
    )
    changes = classify_week(
        pd.Timestamp("2021-12-29"),
        pd.Timestamp("2022-01-05"),
        s[pd.Timestamp("2021-12-29")],
        s[pd.Timestamp("2022-01-05")],
        a,
        set(),
    )
    assert changes[0]["classification_status"].startswith("unclassifiable")
    assert changes[0]["secondary_purchases_par"] is None


def test_route_scenarios_use_gross_cash_and_net_rrp_once():
    ledger, sources = fixture()
    sources["on_rrp"].loc[sources["on_rrp"].date.ge("2022-01-04"), "value"] = "0.99"
    sources["auctions"] = pd.DataFrame(
        [auction("BILL", "2022-01-04", "2022-04-05", par="8000000")]
    )
    result = build_weekly_trc(ledger, sources)
    row = target(result)
    assert row.route_baseline == 0 and row.route_forward == 8
    d = result[3].set_index("date").loc["2022-01-04"]
    assert (
        0 <= d.route_forward <= d.on_rrp_opening_principal
        and d.route_forward <= d.gross_non_soma_bill_issue_cash
    )
    identity = (
        result[1]
        .query("date == '2022-01-05' and variant == 'forward_scenario'")
        .iloc[0]
    )
    assert (
        identity.trc == 8
        and identity.rrp_others_net_route == -8
        and identity.identity_error == 0
    )
    sources["on_rrp"].loc[sources["on_rrp"].date.eq("2022-01-04"), "value"] = "."
    assert target(build_weekly_trc(ledger, sources)).route_forward is None


def test_end_month_and_actual_holiday_coupon_dates():
    _, sources = fixture()
    frame = pd.DataFrame([holding("2022-01-26", maturity="2052-07-31", coupon="2")])
    opening = prepare_soma(frame)[pd.Timestamp("2022-01-26")]
    auctions = prepare_auctions(sources["auctions"])
    value, status = coupon_week(
        pd.Timestamp("2022-01-26"),
        pd.Timestamp("2022-02-02"),
        opening,
        opening,
        auctions,
        {},
        sources["frn"],
        set(),
    )
    assert value == 1  # Jan 31, not Jan 30, even for a distant maturity.
    opening["maturityDate"] = pd.Timestamp("2030-07-04")
    holidays = set(FedPaymentCalendar().holidays("2022-01-01", "2022-12-31"))
    value, _ = coupon_week(
        pd.Timestamp("2022-06-29"),
        pd.Timestamp("2022-07-06"),
        opening,
        opening,
        auctions,
        {},
        sources["frn"],
        holidays,
    )
    assert value == 1  # Jul 5 after the holiday.


def test_complete_quarters_telescope_and_missing_week_is_not_partial_point():
    ledger, sources = fixture()
    cumulative = 0
    for n, day in enumerate(ledger.date):
        cumulative += n
        sources["soma"].loc[sources["soma"].asOfDate.eq(day), "parValue"] = str(
            (100 + cumulative) * 1000000
        )
        ledger.loc[
            ledger.date.eq(day),
            ["s_h", "f_treasury_securities", "delta_reserve_balances"],
        ] = str(n)
        ledger.loc[ledger.date.eq(day), "reserve_balances"] = str(1000 + cumulative)
    w, _, _, _ = build_weekly_trc(ledger, sources)
    components = pd.DataFrame(
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
    q = quarter_tables(w, components).set_index("quarter").loc["2022Q1"]
    assert (
        q.n_weeks == 13
        and q.trc_core == 91
        and q.delta_reserve_balances == 91
        and q.reserve_telescoping_error == 0
        and q.difference_identity_error == 0
    )
    w.loc[w.date.eq("2022-01-05"), "trc_core"] = None
    assert (
        quarter_tables(w, components).set_index("quarter").loc["2022Q1"].trc_core
        is None
    )


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_cli_receipt_pins_clean_producer_and_preserves_all_admitted_outputs(tmp_path):
    ledger, sources = fixture()
    root = tmp_path
    (root / "data/processed").mkdir(parents=True)
    (root / WEEKLY_TRC_REGISTRY.input_dir).mkdir(parents=True)
    (root / ".gitignore").write_text("data/\n")
    for name in [*TRC_OUTPUT_FILES.values(), *LEDGER_OUTPUT_FILES.values()]:
        (root / "data/processed" / name).write_text("admitted bytes\n")
    ledger.to_csv(root / "data/processed" / LEDGER_OUTPUT_FILES["weekly"], index=False)
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
    comp.to_csv(root / "data/processed" / TRC_OUTPUT_FILES["components"], index=False)
    entries = {}
    for spec in WEEKLY_TRC_REGISTRY.inputs:
        p = root / WEEKLY_TRC_REGISTRY.input_dir / (spec.key + ".csv")
        sources[spec.key].to_csv(p, index=False)
        entries[spec.key] = dict(
            dataset_id=spec.dataset_id,
            argv=list(spec.argv),
            file=str(p.relative_to(root)),
            sha256=sha(p),
            byte_count=p.stat().st_size,
            cache_key="fixture",
            retrieved_at_utc="2026-10-09",
            vintage="fixture",
            source_url="https://example.test/",
            source_metadata={},
            row_count=len(sources[spec.key]),
            data_coverage={},
        )
    manifest = root / WEEKLY_TRC_REGISTRY.manifest
    manifest.write_text(
        json.dumps(
            dict(schema_version=WEEKLY_TRC_REGISTRY.schema_version, inputs=entries)
        )
    )

    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(root), *args], text=True
        ).strip()

    git("init", "-q")
    git("config", "core.hooksPath", "/dev/null")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.test")
    git("add", ".gitignore")
    git("commit", "-qm", "fixture")
    before = {p.name: sha(p) for p in (root / "data/processed").iterdir()}
    args = [
        "weekly-trc-export",
        "--root",
        str(root),
        "--inputs-manifest-sha256",
        sha(manifest),
        "--ledger-sha256",
        sha(root / "data/processed" / LEDGER_OUTPUT_FILES["weekly"]),
        "--trc-components-sha256",
        sha(root / "data/processed" / TRC_OUTPUT_FILES["components"]),
    ]
    assert main(args) == 0
    receipt = json.loads((root / "data/processed" / OUTPUTS["receipt"]).read_text())
    assert receipt["producer_commit"] == git("rev-parse", "HEAD")
    assert receipt["admitted_outputs_before"] == receipt["admitted_outputs_after"]
    for name, value in before.items():
        assert sha(root / "data/processed" / name) == value
    for role, entry in receipt["outputs"].items():
        assert sha(root / entry["path"]) == entry["sha256"]
        assert set(pd.read_csv(root / entry["path"]).columns) == set(
            receipt["column_contracts"][role]
        )
    (root / "dirty.txt").write_text("dirty")
    with pytest.raises(ValueError, match="clean committed"):
        main(args)
    (root / "dirty.txt").unlink()
    manifest.write_text("{}")
    with pytest.raises(ValueError, match="hash mismatch"):
        main(args)


@pytest.mark.integration
def test_live_weekly_export_has_verified_receipt_and_exact_identity():
    root = Path(__file__).resolve().parents[1]
    receipt = json.loads((root / "data/processed" / OUTPUTS["receipt"]).read_text())
    for entry in receipt["outputs"].values():
        assert sha(root / entry["path"]) == entry["sha256"]
    identity = pd.read_csv(
        root / "data/processed" / OUTPUTS["identity"], dtype=str, keep_default_na=False
    )
    errors = identity.identity_error.loc[
        identity.identity_status.eq("closed_exact_decimal")
    ].map(D)
    assert len(errors) > 0 and errors.eq(0).all()
    # Reconstruct from exported columns, independently of the producer's error diagnostic.
    parts = [
        "trc",
        "non_treasury_signed_factors",
        "rrp_others_net_route",
        "bridge_all_securities_premium_discount",
        "bridge_treasury_securities_source_inflation",
        "bridge_coupon_remittance_payments",
        "bridge_primary_cash_price",
        "bridge_redemption_inflation",
        "bridge_internal_postings",
        "bridge_maturity_payment_clock",
        "bridge_published_rounding",
    ]
    for row in identity.loc[
        identity.identity_status.eq("closed_exact_decimal")
    ].to_dict("records"):
        assert D(row["delta_reserve_balances"]) == sum((D(row[k]) for k in parts), D(0))
    weekly = pd.read_csv(
        root / "data/processed" / OUTPUTS["weekly"], dtype=str, keep_default_na=False
    )
    quarterly = pd.read_csv(
        root / "data/processed" / OUTPUTS["quarterly"], dtype=str, keep_default_na=False
    )
    daily = pd.read_csv(
        root / "data/processed" / OUTPUTS["daily_route"],
        dtype=str,
        keep_default_na=False,
    )
    ledger = pd.read_csv(
        root / "data/processed" / LEDGER_OUTPUT_FILES["weekly"],
        dtype=str,
        keep_default_na=False,
    ).set_index("date")
    assert all(
        D(row.c_h) == D(ledger.loc[row.date, "c_h"]) for row in weekly.itertuples()
    )
    for row in daily.to_dict("records"):
        assert D(row["route_baseline"]) == 0
        if all(
            row[k]
            for k in (
                "route_forward",
                "on_rrp_opening_principal",
                "gross_non_soma_bill_issue_cash",
            )
        ):
            assert (
                0
                <= D(row["route_forward"])
                <= min(
                    D(row["on_rrp_opening_principal"]),
                    D(row["gross_non_soma_bill_issue_cash"]),
                )
            )
        if all(
            row[k]
            for k in (
                "route_reverse",
                "on_rrp_closing_principal",
                "gross_non_soma_bill_redemption_cash",
            )
        ):
            assert (
                -min(
                    D(row["on_rrp_closing_principal"]),
                    D(row["gross_non_soma_bill_redemption_cash"]),
                )
                <= D(row["route_reverse"])
                <= 0
            )
    for row in quarterly.loc[
        quarterly.clock_status.eq("complete_wednesday_quarter")
    ].to_dict("records"):
        weeks = weekly.loc[
            weekly.date.gt(row["start_wednesday"])
            & weekly.date.le(row["end_wednesday"])
        ]
        for col in [
            "c_h",
            "fed_leg_par",
            "soma_coupon_cash",
            "cash_remittances",
            "trc_core",
            "route_baseline",
            "route_forward",
            "route_reverse",
            "trc_forward_scenario",
            "trc_reverse_scenario",
            "delta_reserve_balances",
        ]:
            if weeks[col].eq("").any():
                assert row[col] == ""
            else:
                assert D(row[col]) == sum(weeks[col].map(D), D(0))
    assert receipt["admitted_outputs_before"] == receipt["admitted_outputs_after"]


def test_tips_coupon_uses_payment_date_index_ratio_and_missing_base_is_unavailable():
    _, sources = fixture()
    frame = pd.DataFrame(
        [holding("2022-01-12", maturity="2032-07-15", coupon="2", kind="TIPS")]
    )
    opening = prepare_soma(frame)[pd.Timestamp("2022-01-12")]
    a = auction("OLD", kind="Note")
    auctions = prepare_auctions(pd.DataFrame([a]))
    cpi = {
        pd.Period("2021-10", freq="M"): D(110),
        pd.Period("2021-11", freq="M"): D(110),
    }
    value, _ = coupon_week(
        pd.Timestamp("2022-01-12"),
        pd.Timestamp("2022-01-19"),
        opening,
        opening,
        auctions,
        cpi,
        sources["frn"],
        set(),
    )
    assert value == D("1.1")
    auctions["ref_cpi_on_dated_date"] = "null"
    value, status = coupon_week(
        pd.Timestamp("2022-01-12"),
        pd.Timestamp("2022-01-19"),
        opening,
        opening,
        auctions,
        cpi,
        sources["frn"],
        set(),
    )
    assert value is None and status.startswith("unavailable_payment_input")


def test_frn_index_conversion_and_payment_lockout_match_regulatory_example():
    bill = auction("BILL", "2012-07-26", "2012-10-25")
    bill.update(auction_date="2012-07-23", high_discnt_rate="0.095")
    note = auction("FRN", "2012-07-31", "2014-07-31", kind="FRN")
    note["spread"] = "0.120"
    a = prepare_auctions(pd.DataFrame([bill, note]))
    assert frn_coupon_per100(
        "FRN",
        pd.Timestamp("2012-07-30"),
        pd.Timestamp("2012-07-31"),
        pd.Timestamp("2012-07-31"),
        a,
        set(),
    ) == D("0.000597286")
    late = bill.copy()
    late.update(
        cusip="LATE", auction_date=pd.Timestamp("2012-07-30"), high_discnt_rate="9"
    )
    a = prepare_auctions(pd.concat([a, pd.DataFrame([late])], ignore_index=True))
    assert frn_coupon_per100(
        "FRN",
        pd.Timestamp("2012-07-30"),
        pd.Timestamp("2012-07-31"),
        pd.Timestamp("2012-07-31"),
        a,
        set(),
    ) == D("0.000597286")


def test_malformed_or_absent_dts_cash_is_never_zero_filled():
    ledger, sources = fixture()
    sources["remittances"] = sources["remittances"].loc[
        sources["remittances"].record_date.ne("2022-01-04")
    ]
    row = target(build_weekly_trc(ledger, sources))
    assert row.cash_remittances is None and row.trc_core is None
    sources["remittances"].loc[
        sources["remittances"].index[0], "transaction_today_amt"
    ] = "garbage"
    with pytest.raises(ValueError, match="malformed"):
        build_weekly_trc(ledger, sources)
