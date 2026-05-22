from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.fed_interest_components import (
    build_fed_interest_components_from_soma_csvs,
    estimate_quarterly_fed_frn_interest_from_soma_snapshots,
    estimate_quarterly_fed_tips_inflation_comp_from_soma_snapshots,
    estimate_quarterly_fed_tips_coupon_from_soma_snapshots,
    summarize_fed_interest_components,
    write_fed_interest_components_from_soma_csvs,
)


def _write_soma_fixture(path: Path) -> None:
    pd.DataFrame(
        {
            "as_of_date": ["2025-01-01"],
            "maturity_date": ["2025-03-15"],
            "par_value": [1_000_000_000],
            "coupon": [4.0],
            "security_type": ["Treasury Note"],
            "cusip": ["912828TEST"],
        }
    ).to_csv(path, index=False)


def test_build_fed_interest_components_keeps_non_coupon_placeholders_without_bill_master(tmp_path: Path):
    soma_path = tmp_path / "soma.csv"
    _write_soma_fixture(soma_path)

    out = build_fed_interest_components_from_soma_csvs([soma_path])

    row = out.iloc[0]
    assert row["date"] == pd.Timestamp("2025-03-31")
    assert row["fed_tsy_coupon_interest_proxy"] == 20.0
    assert pd.isna(row["fed_tsy_bill_discount_interest_proxy"])
    assert row["source_tier"] == "coupon_bill_tips_frn_present_tips_comp_stock_change_proxy"


def test_build_fed_interest_components_adds_bill_discount_from_auction_master(tmp_path: Path):
    soma_path = tmp_path / "soma.csv"
    pd.DataFrame(
        {
            "as_of_date": ["2025-01-01", "2025-01-01"],
            "maturity_date": ["2025-03-15", "2025-03-31"],
            "par_value": [1_000_000_000, 360_000_000],
            "coupon": [4.0, 0.0],
            "security_type": ["Treasury Note", "Bill"],
            "cusip": ["912828TEST", "912795BILL"],
        }
    ).to_csv(soma_path, index=False)
    auction_master = pd.DataFrame(
        {
            "cusip": ["912795BILL"],
            "security_type": ["Bill"],
            "issue_date": ["2025-01-01"],
            "maturity_date": ["2025-03-31"],
            "avg_med_price": [99.0],
        }
    )

    out = build_fed_interest_components_from_soma_csvs([soma_path], auction_master)

    row = out.iloc[0]
    assert row["fed_tsy_coupon_interest_proxy"] == 20.0
    assert round(float(row["fed_tsy_bill_discount_interest_proxy"]), 6) == 3.6


def test_estimate_quarterly_fed_tips_coupon_uses_inflation_adjusted_principal():
    holdings = pd.DataFrame(
        {
            "as_of_date": ["2025-01-01"],
            "maturity_date": ["2025-01-15"],
            "par_value": [1_000_000_000],
            "inflation_compensation": [100_000_000],
            "coupon": [2.0],
            "security_type": ["TIPS"],
            "cusip": ["912810TIPS"],
        }
    )

    out = estimate_quarterly_fed_tips_coupon_from_soma_snapshots(holdings)

    assert out.loc[pd.Timestamp("2025-03-31")] == 11.0


def test_estimate_quarterly_fed_frn_interest_uses_daily_indexes():
    holdings = pd.DataFrame(
        {
            "as_of_date": ["2025-01-01"],
            "maturity_date": ["2025-01-31"],
            "par_value": [1_000_000_000],
            "spread": [0.10],
            "security_type": ["FRNs"],
            "cusip": ["91282CFRN"],
        }
    )
    indexes = pd.DataFrame(
        {
            "cusip": ["91282CFRN", "91282CFRN"],
            "start_of_accrual_period": ["2025-01-01", "2025-01-02"],
            "daily_accrued_int_per100": [0.01, 0.02],
        }
    )

    out = estimate_quarterly_fed_frn_interest_from_soma_snapshots(holdings, indexes)

    assert round(float(out.loc[pd.Timestamp("2025-03-31")]), 6) == 0.3


def test_estimate_quarterly_fed_tips_inflation_comp_uses_snapshot_change():
    holdings = pd.DataFrame(
        {
            "as_of_date": ["2025-03-31", "2025-06-30"],
            "maturity_date": ["2030-01-15", "2030-01-15"],
            "par_value": [1_000_000_000, 1_000_000_000],
            "inflation_compensation": [100_000_000, 125_000_000],
            "coupon": [2.0, 2.0],
            "security_type": ["TIPS", "TIPS"],
            "cusip": ["912810TIPS", "912810TIPS"],
        }
    )

    out = estimate_quarterly_fed_tips_inflation_comp_from_soma_snapshots(holdings)

    assert out.loc[pd.Timestamp("2025-06-30")] == 25.0


def test_write_fed_interest_components_and_summary(tmp_path: Path):
    soma_path = tmp_path / "soma.csv"
    csv_path = tmp_path / "support__fed_treasury_interest_components.csv"
    md_path = tmp_path / "fed_treasury_interest_components.md"
    _write_soma_fixture(soma_path)

    written_csv, written_md = write_fed_interest_components_from_soma_csvs(
        soma_paths=[soma_path],
        out_csv_path=csv_path,
        out_markdown_path=md_path,
    )

    assert written_csv == csv_path
    assert written_md == md_path
    summary = summarize_fed_interest_components(pd.read_csv(csv_path))
    assert "SOMA coupon component" in summary
    assert "stock-change proxy" in summary
