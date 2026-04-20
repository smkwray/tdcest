from __future__ import annotations

import pandas as pd

from tdc_estimator.tier3_source import (
    build_source_backed_tier3_input_table,
    build_tier3_source_diagnostics,
    render_tier3_source_diagnostics_markdown,
)


def test_build_source_backed_tier3_input_table_overlays_full_quarters_only(tmp_path):
    outlays_path = tmp_path / "mts_outlays.csv"
    base_path = tmp_path / "tier3_base.csv"

    pd.DataFrame(
        [
            ["2025-03-31", "Financial Agent Services", 99_000_000.0],
            ["2025-04-30", "Financial Agent Services", 100_000_000.0],
            ["2025-05-31", "Financial Agent Services", 110_000_000.0],
            ["2025-06-30", "Financial Agent Services", 120_000_000.0],
            ["2025-04-30", "Foreign Military Financing Program", 200_000_000.0],
            ["2025-05-31", "International Disaster Assistance", 300_000_000.0],
            ["2025-06-30", "Foreign Military Sales Trust Fund", 9_999_000_000.0],
            ["2025-06-30", "International Organizations and Conferences", 400_000_000.0],
            ["2025-04-30", "Total--International Assistance Programs", 8_000_000_000.0],
            ["2025-04-30", "United States Mint", -500_000_000.0],
            ["2025-05-31", "United States Mint", 100_000_000.0],
            ["2025-06-30", "United States Mint", -200_000_000.0],
        ],
        columns=["record_date", "classification_desc", "current_month_net_outly_amt"],
    ).to_csv(outlays_path, index=False)

    pd.DataFrame(
        {
            "date": ["2025-03-31", "2025-06-30"],
            "bank_noninterest_outlay_proxy": [1.0, 2.0],
            "row_noninterest_outlay_proxy": [3.0, 4.0],
            "bank_nonborrow_receipt_proxy": [5.0, 6.0],
            "row_nonborrow_receipt_proxy": [7.0, 8.0],
            "mint_cb_cash_factor_proxy": [9.0, 10.0],
        }
    ).to_csv(base_path, index=False)

    table = build_source_backed_tier3_input_table(
        mts_outlays_path=outlays_path,
        base_quarterly_input_path=base_path,
        start="2025-03-31",
    )

    assert list(table.index) == list(pd.to_datetime(["2025-03-31", "2025-06-30"]))
    assert round(table.loc[pd.Timestamp("2025-03-31"), "bank_noninterest_outlay_proxy"], 6) == 1.0
    assert round(table.loc[pd.Timestamp("2025-06-30"), "bank_noninterest_outlay_proxy"], 6) == 330.0
    assert round(table.loc[pd.Timestamp("2025-06-30"), "row_noninterest_outlay_proxy"], 6) == 700.0
    assert round(table.loc[pd.Timestamp("2025-06-30"), "bank_nonborrow_receipt_proxy"], 6) == 0.0
    assert round(table.loc[pd.Timestamp("2025-06-30"), "row_nonborrow_receipt_proxy"], 6) == 0.0
    assert round(table.loc[pd.Timestamp("2025-06-30"), "mint_cb_cash_factor_proxy"], 6) == 600.0


def test_build_tier3_source_diagnostics_exposes_row_components(tmp_path):
    outlays_path = tmp_path / "mts_outlays.csv"
    pd.DataFrame(
        [
            ["2025-04-30", "Financial Agent Services", 100_000_000.0],
            ["2025-05-31", "Financial Agent Services", 110_000_000.0],
            ["2025-06-30", "Financial Agent Services", 120_000_000.0],
            ["2025-04-30", "Foreign Military Financing Program", 200_000_000.0],
            ["2025-05-31", "International Disaster Assistance", 300_000_000.0],
            ["2025-06-30", "International Organizations and Conferences", 400_000_000.0],
            ["2025-04-30", "United States Mint", -500_000_000.0],
            ["2025-05-31", "United States Mint", 100_000_000.0],
            ["2025-06-30", "United States Mint", -200_000_000.0],
        ],
        columns=["record_date", "classification_desc", "current_month_net_outly_amt"],
    ).to_csv(outlays_path, index=False)

    diagnostics = build_tier3_source_diagnostics(mts_outlays_path=outlays_path, start="2025-03-31")

    assert list(diagnostics.index) == list(pd.to_datetime(["2025-06-30"]))
    row = diagnostics.loc[pd.Timestamp("2025-06-30")]
    assert round(row["bank_noninterest_outlay_source"], 6) == 330.0
    assert round(row["row_outlay_foreign_military_financing"], 6) == 200.0
    assert round(row["row_outlay_international_disaster"], 6) == 300.0
    assert round(row["row_outlay_international_orgs"], 6) == 400.0
    assert round(row["row_outlay_total_selected"], 6) == 900.0
    assert round(row["row_outlay_default_selected"], 6) == 700.0
    assert round(row["row_outlay_broad_selected"], 6) == 900.0
    assert round(row["row_outlay_security_selected"], 6) == 200.0
    assert round(row["row_outlay_humanitarian_development_selected"], 6) == 300.0
    assert round(row["row_outlay_institutions_selected"], 6) == 400.0
    assert round(row["mint_cb_cash_factor_source"], 6) == 600.0


def test_render_tier3_source_diagnostics_markdown_includes_latest_components():
    diagnostics = pd.DataFrame(
        {
            "bank_noninterest_outlay_source": [330.0],
            "row_outlay_foreign_military_financing": [200.0],
            "row_outlay_international_disaster": [300.0],
            "row_outlay_foreign_ag_service": [0.0],
            "row_outlay_ida_contribution": [0.0],
            "row_outlay_international_narcotics": [0.0],
            "row_outlay_international_orgs": [400.0],
            "row_outlay_international_monetary": [0.0],
            "row_outlay_default_selected": [700.0],
            "row_outlay_broad_selected": [900.0],
            "row_outlay_total_selected": [900.0],
            "row_outlay_security_selected": [200.0],
            "row_outlay_humanitarian_development_selected": [300.0],
            "row_outlay_institutions_selected": [400.0],
            "mint_net_outlay_source": [-600.0],
            "mint_cb_cash_factor_source": [600.0],
        },
        index=pd.to_datetime(["2025-06-30"]),
    )

    markdown = render_tier3_source_diagnostics_markdown(diagnostics)

    assert "Latest source-covered quarter: 2025-06-30." in markdown
    assert "ROW default 700.000; ROW broad 900.000;" in markdown
    assert "Top ROW components:" in markdown
    assert "foreign_military_financing=200.000" in markdown
    assert "international_orgs=400.000" in markdown
