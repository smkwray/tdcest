from __future__ import annotations

import pandas as pd

from tdc_estimator.bea_row_receipts_benchmark import (
    build_bea_row_receipts_benchmark_from_fred_paths,
    build_bea_row_receipts_benchmark,
    build_bea_row_receipts_ita_crosscheck_from_fred_paths,
    render_bea_row_receipts_benchmark_markdown,
    render_bea_row_receipts_ita_crosscheck_markdown,
)


def test_build_bea_row_receipts_benchmark_converts_saar_billions_to_quarterly_millions():
    quarterly = pd.DataFrame(
        {
            "bea_row_taxes_received_saar": [42.862],
            "bea_row_social_insurance_received_saar": [6.846],
            "bea_row_current_transfer_receipts_received_saar": [0.973],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )

    benchmark = build_bea_row_receipts_benchmark(quarterly)

    row = benchmark.iloc[0]
    assert round(row["bea_row_taxes_q_mil"], 3) == 10715.500
    assert round(row["bea_row_social_insurance_q_mil"], 3) == 1711.500
    assert round(row["bea_row_current_transfers_q_mil"], 3) == 243.250
    assert round(row["bea_row_current_receipts_total_q_mil"], 3) == 12670.250
    assert row["conversion_method"] == "saar_divide_by_4"
    assert "W008RC1Q027SBEA" in row["source_series_ids"]


def test_build_bea_row_receipts_benchmark_from_fred_paths_aligns_to_quarter_end(tmp_path):
    taxes = tmp_path / "taxes.csv"
    social = tmp_path / "social.csv"
    transfers = tmp_path / "transfers.csv"
    pd.DataFrame({"date": ["2003-01-01", "2003-04-01"], "value": [4.0, 8.0]}).to_csv(taxes, index=False)
    pd.DataFrame({"date": ["2003-01-01", "2003-04-01"], "value": [1.0, 2.0]}).to_csv(social, index=False)
    pd.DataFrame({"date": ["2003-01-01", "2003-04-01"], "value": [0.5, 1.0]}).to_csv(transfers, index=False)

    benchmark = build_bea_row_receipts_benchmark_from_fred_paths(
        taxes_path=taxes,
        social_insurance_path=social,
        current_transfers_path=transfers,
        start="2003-03-31",
    )

    assert list(benchmark.index) == list(pd.to_datetime(["2003-03-31", "2003-06-30"]))
    assert round(benchmark.loc[pd.Timestamp("2003-03-31"), "bea_row_current_receipts_total_q_mil"], 3) == 1375.0


def test_build_bea_row_receipts_ita_crosscheck_from_fred_paths_adds_scale_ratios(tmp_path):
    taxes = tmp_path / "taxes.csv"
    social = tmp_path / "social.csv"
    transfers = tmp_path / "transfers.csv"
    secondary = tmp_path / "secondary.csv"
    credits = tmp_path / "credits.csv"
    pd.DataFrame({"date": ["2003-01-01"], "value": [4.0]}).to_csv(taxes, index=False)
    pd.DataFrame({"date": ["2003-01-01"], "value": [1.0]}).to_csv(social, index=False)
    pd.DataFrame({"date": ["2003-01-01"], "value": [0.5]}).to_csv(transfers, index=False)
    pd.DataFrame({"DATE": ["2003-01-01"], "IEAXSIR": [5500.0]}).to_csv(secondary, index=False)
    pd.DataFrame({"DATE": ["2003-01-01"], "IEAX": [550000.0]}).to_csv(credits, index=False)

    crosscheck = build_bea_row_receipts_ita_crosscheck_from_fred_paths(
        taxes_path=taxes,
        social_insurance_path=social,
        current_transfers_path=transfers,
        secondary_income_receipts_path=secondary,
        total_receipts_credits_path=credits,
        start="2003-03-31",
    )

    row = crosscheck.iloc[0]
    assert round(row["bea_row_current_receipts_total_q_mil"], 3) == 1375.0
    assert round(row["bea_row_share_of_ita_secondary_income_receipts"], 3) == 0.25
    assert round(row["bea_row_share_of_ita_total_receipts_credits"], 4) == 0.0025
    assert row["ita_crosscheck_source_series_ids"] == "IEAXSIR|IEAX"
    assert not bool(row["row_anchor_exceeds_ita_secondary_income"])


def test_render_bea_row_receipts_benchmark_markdown_mentions_benchmark_only_role():
    benchmark = pd.DataFrame(
        {
            "bea_row_taxes_q_mil": [10715.5],
            "bea_row_social_insurance_q_mil": [1711.5],
            "bea_row_current_transfers_q_mil": [243.25],
            "bea_row_current_receipts_total_q_mil": [12670.25],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )

    markdown = render_bea_row_receipts_benchmark_markdown(benchmark)

    assert "BEA ROW Receipts Benchmark" in markdown
    assert "official macro benchmark" in markdown
    assert "saar_divide_by_4" in markdown
    assert "2025-12-31" in markdown


def test_render_bea_row_receipts_ita_crosscheck_markdown_prevents_double_counting():
    crosscheck = pd.DataFrame(
        {
            "bea_row_current_receipts_total_q_mil": [12670.25],
            "ita_secondary_income_receipts_q_mil": [45415.0],
            "ita_total_receipts_credits_q_mil": [1329510.0],
            "bea_row_share_of_ita_secondary_income_receipts": [12670.25 / 45415.0],
            "bea_row_share_of_ita_total_receipts_credits": [12670.25 / 1329510.0],
            "row_anchor_exceeds_ita_secondary_income": [False],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )

    markdown = render_bea_row_receipts_ita_crosscheck_markdown(crosscheck)

    assert "BEA ROW Receipts ITA Cross-Check" in markdown
    assert "diagnostic only" in markdown
    assert "IEAXSIR" in markdown
    assert "scale checks only" in markdown
