from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.du_fiscal_flow_research import build_du_fiscal_flow_research


def test_build_du_fiscal_flow_research_computes_first_pass_terms(tmp_path: Path):
    quarterly = pd.DataFrame(
        {
            "domestic_nonfinancial_tsy_tx": [-10.0, -20.0],
            "domestic_financial_tsy_tx": [50.0, 60.0],
        },
        index=pd.to_datetime(["2025-03-31", "2025-06-30"]),
    )
    components = pd.DataFrame(
        {
            "fed_tsy_tx": [5.0, 6.0],
            "bank_depository_tsy_tx": [7.0, 8.0],
            "credit_unions_total_tsy_tx_reconstructed": [3.0, 4.0],
            "fed_tsy_coupon_interest_proxy": [1.0, 1.0],
            "bank_tsy_coupon_interest_proxy": [2.0, 2.0],
            "row_tsy_coupon_interest_proxy": [3.0, 3.0],
            "bank_noninterest_outlay_proxy": [4.0, 4.0],
            "row_noninterest_outlay_proxy": [5.0, 5.0],
            "bank_nonborrow_receipt_proxy": [6.0, 6.0],
            "row_nonborrow_receipt_proxy": [7.0, 7.0],
        },
        index=quarterly.index,
    )

    outlays_path = tmp_path / "mts_outlays.csv"
    receipts_path = tmp_path / "mts_receipts.csv"

    pd.DataFrame(
        [
            ["2025-01-31", "Total Outlays", 100_000_000.0],
            ["2025-02-28", "Total Outlays", 100_000_000.0],
            ["2025-03-31", "Total Outlays", 100_000_000.0],
            ["2025-01-31", "Total--Interest on Treasury Debt Securities (Gross)", 10_000_000.0],
            ["2025-02-28", "Total--Interest on Treasury Debt Securities (Gross)", 10_000_000.0],
            ["2025-03-31", "Total--Interest on Treasury Debt Securities (Gross)", 10_000_000.0],
            ["2025-04-30", "Total Outlays", 120_000_000.0],
            ["2025-05-31", "Total Outlays", 120_000_000.0],
            ["2025-06-30", "Total Outlays", 120_000_000.0],
            ["2025-04-30", "Total--Interest on Treasury Debt Securities (Gross)", 12_000_000.0],
            ["2025-05-31", "Total--Interest on Treasury Debt Securities (Gross)", 12_000_000.0],
            ["2025-06-30", "Total--Interest on Treasury Debt Securities (Gross)", 12_000_000.0],
        ],
        columns=["record_date", "classification_desc", "current_month_net_outly_amt"],
    ).to_csv(outlays_path, index=False)
    pd.DataFrame(
        [
            ["2025-01-31", "Total -- Receipts", 80_000_000.0],
            ["2025-02-28", "Total -- Receipts", 80_000_000.0],
            ["2025-03-31", "Total -- Receipts", 80_000_000.0],
            ["2025-01-31", "Deposit of Earnings, Federal Reserve System", 5_000_000.0],
            ["2025-02-28", "Deposit of Earnings, Federal Reserve System", 5_000_000.0],
            ["2025-03-31", "Deposit of Earnings, Federal Reserve System", 5_000_000.0],
            ["2025-04-30", "Total -- Receipts", 90_000_000.0],
            ["2025-05-31", "Total -- Receipts", 90_000_000.0],
            ["2025-06-30", "Total -- Receipts", 90_000_000.0],
            ["2025-04-30", "Deposit of Earnings, Federal Reserve System", 4_000_000.0],
            ["2025-05-31", "Deposit of Earnings, Federal Reserve System", 4_000_000.0],
            ["2025-06-30", "Deposit of Earnings, Federal Reserve System", 4_000_000.0],
        ],
        columns=["record_date", "classification_desc", "current_month_net_rcpt_amt"],
    ).to_csv(receipts_path, index=False)

    frame = build_du_fiscal_flow_research(
        quarterly,
        components,
        mts_outlays_path=outlays_path,
        mts_receipts_path=receipts_path,
        wamest_root=tmp_path / "missing_wamest",
    )

    latest = frame.loc[pd.Timestamp("2025-06-30")]
    assert latest["du_domestic_nonfinancial_security_flow_proxy"] == 20.0
    assert latest["du_other_domestic_financial_nonru_security_flow_proxy"] == -(60.0 - 6.0 - 8.0 - 4.0)
    assert latest["du_noninterest_outlay_proxy"] == 360.0 - 36.0 - 4.0 - 5.0
    assert latest["du_receipt_proxy"] == 270.0 - 12.0 - 6.0 - 7.0
    assert latest["du_coupon_proxy_residual"] == 36.0 - 1.0 - 2.0 - 3.0
    assert latest["du_coupon_proxy_direct_narrow"] == latest["du_coupon_proxy_residual"]
    assert latest["du_coupon_proxy_direct_broad"] == latest["du_coupon_proxy_residual"]
    assert latest["tdc_du_fiscal_flow_first_pass_narrow"] == 20.0 + (360.0 - 36.0 - 4.0 - 5.0) - (270.0 - 12.0 - 6.0 - 7.0) - (36.0 - 1.0 - 2.0 - 3.0)
    assert latest["tdc_du_fiscal_flow_first_pass_broad"] == (
        (20.0 - (60.0 - 6.0 - 8.0 - 4.0)) + (360.0 - 36.0 - 4.0 - 5.0) - (270.0 - 12.0 - 6.0 - 7.0) - (36.0 - 1.0 - 2.0 - 3.0)
    )


def test_build_du_fiscal_flow_research_prefers_direct_wamest_du_sector_sums(tmp_path: Path):
    index = pd.to_datetime(["2025-03-31", "2025-06-30"])
    quarterly = pd.DataFrame(
        {
            "domestic_nonfinancial_tsy_tx": [-10.0, -20.0],
            "domestic_financial_tsy_tx": [50.0, 60.0],
        },
        index=index,
    )
    components = pd.DataFrame(
        {
            "fed_tsy_tx": [5.0, 6.0],
            "bank_depository_tsy_tx": [7.0, 8.0],
            "credit_unions_total_tsy_tx_reconstructed": [3.0, 4.0],
            "fed_tsy_coupon_interest_proxy": [1.0, 1.0],
            "bank_tsy_coupon_interest_proxy": [2.0, 2.0],
            "row_tsy_coupon_interest_proxy": [3.0, 3.0],
            "bank_noninterest_outlay_proxy": [4.0, 4.0],
            "row_noninterest_outlay_proxy": [5.0, 5.0],
            "bank_nonborrow_receipt_proxy": [6.0, 6.0],
            "row_nonborrow_receipt_proxy": [7.0, 7.0],
        },
        index=index,
    )

    outlays_path = tmp_path / "mts_outlays.csv"
    receipts_path = tmp_path / "mts_receipts.csv"
    pd.DataFrame(
        [
            ["2025-01-31", "Total Outlays", 100_000_000.0],
            ["2025-02-28", "Total Outlays", 100_000_000.0],
            ["2025-03-31", "Total Outlays", 100_000_000.0],
            ["2025-01-31", "Total--Interest on Treasury Debt Securities (Gross)", 10_000_000.0],
            ["2025-02-28", "Total--Interest on Treasury Debt Securities (Gross)", 10_000_000.0],
            ["2025-03-31", "Total--Interest on Treasury Debt Securities (Gross)", 10_000_000.0],
            ["2025-04-30", "Total Outlays", 120_000_000.0],
            ["2025-05-31", "Total Outlays", 120_000_000.0],
            ["2025-06-30", "Total Outlays", 120_000_000.0],
            ["2025-04-30", "Total--Interest on Treasury Debt Securities (Gross)", 12_000_000.0],
            ["2025-05-31", "Total--Interest on Treasury Debt Securities (Gross)", 12_000_000.0],
            ["2025-06-30", "Total--Interest on Treasury Debt Securities (Gross)", 12_000_000.0],
        ],
        columns=["record_date", "classification_desc", "current_month_net_outly_amt"],
    ).to_csv(outlays_path, index=False)
    pd.DataFrame(
        [
            ["2025-01-31", "Total -- Receipts", 80_000_000.0],
            ["2025-02-28", "Total -- Receipts", 80_000_000.0],
            ["2025-03-31", "Total -- Receipts", 80_000_000.0],
            ["2025-01-31", "Deposit of Earnings, Federal Reserve System", 5_000_000.0],
            ["2025-02-28", "Deposit of Earnings, Federal Reserve System", 5_000_000.0],
            ["2025-03-31", "Deposit of Earnings, Federal Reserve System", 5_000_000.0],
            ["2025-04-30", "Total -- Receipts", 90_000_000.0],
            ["2025-05-31", "Total -- Receipts", 90_000_000.0],
            ["2025-06-30", "Total -- Receipts", 90_000_000.0],
            ["2025-04-30", "Deposit of Earnings, Federal Reserve System", 4_000_000.0],
            ["2025-05-31", "Deposit of Earnings, Federal Reserve System", 4_000_000.0],
            ["2025-06-30", "Deposit of Earnings, Federal Reserve System", 4_000_000.0],
        ],
        columns=["record_date", "classification_desc", "current_month_net_rcpt_amt"],
    ).to_csv(receipts_path, index=False)

    wamest_root = tmp_path / "wamest"
    release_dir = wamest_root / "outputs" / "full_coverage_release"
    release_dir.mkdir(parents=True)

    pd.DataFrame(
        {
            "sector_key": [
                "households_nonprofits",
                "nonfinancial_corporates",
                "nonfinancial_noncorporate_business",
                "life_insurers",
                "private_defined_benefit_pensions",
            ],
            "transactions_source_code": [
                "FU153061105.Q",
                "FU103061103.Q",
                "FU113061003.Q",
                "FU543061105.Q",
                "FU573061143.Q",
            ],
        }
    ).to_csv(release_dir / "required_sector_inventory.csv", index=False)

    pd.DataFrame(
        {
            "date": [
                "2025-03-31",
                "2025-03-31",
                "2025-03-31",
                "2025-03-31",
                "2025-03-31",
                "2025-06-30",
                "2025-06-30",
                "2025-06-30",
                "2025-06-30",
                "2025-06-30",
            ],
            "series_code": [
                "FU153061105.Q",
                "FU103061103.Q",
                "FU113061003.Q",
                "FU543061105.Q",
                "FU573061143.Q",
                "FU153061105.Q",
                "FU103061103.Q",
                "FU113061003.Q",
                "FU543061105.Q",
                "FU573061143.Q",
            ],
            "value": [11.0, 12.0, 13.0, 21.0, 22.0, 31.0, 32.0, 33.0, 41.0, 42.0],
        }
    ).to_csv(release_dir / "z1_series_auto_full.csv", index=False)

    frame = build_du_fiscal_flow_research(
        quarterly,
        components,
        mts_outlays_path=outlays_path,
        mts_receipts_path=receipts_path,
        wamest_root=wamest_root,
    )

    latest = frame.loc[pd.Timestamp("2025-06-30")]
    assert latest["du_domestic_nonfinancial_security_flow_proxy"] == -(31.0 + 32.0 + 33.0)
    assert latest["du_other_domestic_financial_nonru_security_flow_proxy"] == -(41.0 + 42.0)
    assert latest["du_broad_private_security_flow_proxy"] == -(31.0 + 32.0 + 33.0 + 41.0 + 42.0)


def test_build_du_fiscal_flow_research_prefers_direct_wamest_du_coupon_proxies(tmp_path: Path):
    index = pd.to_datetime(["2025-03-31", "2025-06-30"])
    quarterly = pd.DataFrame(
        {
            "domestic_nonfinancial_tsy_tx": [-10.0, -20.0],
            "domestic_financial_tsy_tx": [50.0, 60.0],
        },
        index=index,
    )
    components = pd.DataFrame(
        {
            "fed_tsy_tx": [5.0, 6.0],
            "bank_depository_tsy_tx": [7.0, 8.0],
            "credit_unions_total_tsy_tx_reconstructed": [3.0, 4.0],
            "fed_tsy_coupon_interest_proxy": [1.0, 1.0],
            "bank_tsy_coupon_interest_proxy": [2.0, 2.0],
            "row_tsy_coupon_interest_proxy": [3.0, 3.0],
            "bank_noninterest_outlay_proxy": [4.0, 4.0],
            "row_noninterest_outlay_proxy": [5.0, 5.0],
            "bank_nonborrow_receipt_proxy": [6.0, 6.0],
            "row_nonborrow_receipt_proxy": [7.0, 7.0],
        },
        index=index,
    )

    outlays_path = tmp_path / "mts_outlays.csv"
    receipts_path = tmp_path / "mts_receipts.csv"
    pd.DataFrame(
        [
            ["2025-01-31", "Total Outlays", 100_000_000.0],
            ["2025-02-28", "Total Outlays", 100_000_000.0],
            ["2025-03-31", "Total Outlays", 100_000_000.0],
            ["2025-01-31", "Total--Interest on Treasury Debt Securities (Gross)", 10_000_000.0],
            ["2025-02-28", "Total--Interest on Treasury Debt Securities (Gross)", 10_000_000.0],
            ["2025-03-31", "Total--Interest on Treasury Debt Securities (Gross)", 10_000_000.0],
            ["2025-04-30", "Total Outlays", 120_000_000.0],
            ["2025-05-31", "Total Outlays", 120_000_000.0],
            ["2025-06-30", "Total Outlays", 120_000_000.0],
            ["2025-04-30", "Total--Interest on Treasury Debt Securities (Gross)", 12_000_000.0],
            ["2025-05-31", "Total--Interest on Treasury Debt Securities (Gross)", 12_000_000.0],
            ["2025-06-30", "Total--Interest on Treasury Debt Securities (Gross)", 12_000_000.0],
        ],
        columns=["record_date", "classification_desc", "current_month_net_outly_amt"],
    ).to_csv(outlays_path, index=False)
    pd.DataFrame(
        [
            ["2025-01-31", "Total -- Receipts", 80_000_000.0],
            ["2025-02-28", "Total -- Receipts", 80_000_000.0],
            ["2025-03-31", "Total -- Receipts", 80_000_000.0],
            ["2025-01-31", "Deposit of Earnings, Federal Reserve System", 5_000_000.0],
            ["2025-02-28", "Deposit of Earnings, Federal Reserve System", 5_000_000.0],
            ["2025-03-31", "Deposit of Earnings, Federal Reserve System", 5_000_000.0],
            ["2025-04-30", "Total -- Receipts", 90_000_000.0],
            ["2025-05-31", "Total -- Receipts", 90_000_000.0],
            ["2025-06-30", "Total -- Receipts", 90_000_000.0],
            ["2025-04-30", "Deposit of Earnings, Federal Reserve System", 4_000_000.0],
            ["2025-05-31", "Deposit of Earnings, Federal Reserve System", 4_000_000.0],
            ["2025-06-30", "Deposit of Earnings, Federal Reserve System", 4_000_000.0],
        ],
        columns=["record_date", "classification_desc", "current_month_net_rcpt_amt"],
    ).to_csv(receipts_path, index=False)

    wamest_root = tmp_path / "wamest"
    release_dir = wamest_root / "outputs" / "full_coverage_release"
    normalized_dir = wamest_root / "data" / "external" / "normalized"
    interim_dir = wamest_root / "data" / "interim"
    release_dir.mkdir(parents=True)
    normalized_dir.mkdir(parents=True)
    interim_dir.mkdir(parents=True)

    pd.DataFrame(
        {
            "date": ["2025-03-31", "2025-03-31", "2025-03-31", "2025-06-30", "2025-06-30", "2025-06-30"],
            "sector_key": [
                "households_nonprofits",
                "nonfinancial_corporates",
                "private_defined_benefit_pensions",
                "households_nonprofits",
                "nonfinancial_corporates",
                "private_defined_benefit_pensions",
            ],
            "coupon_share": [0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
            "coupon_only_maturity_years": [5.0, 5.0, 5.0, 5.0, 5.0, 5.0],
            "publication_status": [
                "published_estimate",
                "published_estimate",
                "published_estimate",
                "published_estimate",
                "published_estimate",
                "published_estimate",
            ],
        }
    ).to_csv(release_dir / "canonical_sector_maturity.csv", index=False)
    pd.DataFrame(
        {
            "sector_key": [
                "households_nonprofits",
                "nonfinancial_corporates",
                "private_defined_benefit_pensions",
            ],
            "level_source_code": [
                "FL153061105.Q",
                "FL103061103.Q",
                "FL573061143.Q",
            ],
        }
    ).to_csv(release_dir / "required_sector_inventory.csv", index=False)
    pd.DataFrame(
        {
            "series_code": [
                "FL153061105.Q",
                "FL103061103.Q",
                "FL153061105.Q",
                "FL103061103.Q",
            ],
            "date": ["2025-03-31", "2025-03-31", "2025-06-30", "2025-06-30"],
            "value": [100.0, 20.0, 200.0, 40.0],
        }
    ).to_csv(normalized_dir / "z1_series_fred.csv", index=False)
    pd.DataFrame(
        {
            "date": ["2025-03-31", "2025-06-30"],
            "sector_key": ["private_defined_benefit_pensions", "private_defined_benefit_pensions"],
            "level": [80.0, 120.0],
            "method_priority": ["direct_z1", "direct_z1"],
        }
    ).to_csv(interim_dir / "z1_sector_panel_full.csv", index=False)
    pd.DataFrame(
        {
            "date": ["2025-03-31", "2025-06-30"],
            "5y": [4.0, 5.0],
        }
    ).to_csv(normalized_dir / "h15_curves_auto_nominal_treasury_constant_maturity.csv", index=False)

    frame = build_du_fiscal_flow_research(
        quarterly,
        components,
        mts_outlays_path=outlays_path,
        mts_receipts_path=receipts_path,
        wamest_root=wamest_root,
    )

    latest = frame.loc[pd.Timestamp("2025-06-30")]
    expected_narrow_coupon = 200.0 * 0.5 * 0.05 / 4.0 + 40.0 * 0.5 * 0.05 / 4.0
    expected_broad_coupon = expected_narrow_coupon + 120.0 * 1000.0 * 0.5 * 0.05 / 4.0
    assert round(float(latest["du_coupon_proxy_residual"]), 6) == round(36.0 - 1.0 - 2.0 - 3.0, 6)
    assert round(float(latest["du_coupon_proxy_direct_narrow"]), 6) == round(expected_narrow_coupon, 6)
    assert round(float(latest["du_coupon_proxy_direct_broad"]), 6) == round(expected_broad_coupon, 6)
    assert round(float(latest["tdc_du_fiscal_flow_first_pass_narrow"]), 6) == round(
        20.0 + (360.0 - 36.0 - 4.0 - 5.0) - (270.0 - 12.0 - 6.0 - 7.0) - expected_narrow_coupon,
        6,
    )
