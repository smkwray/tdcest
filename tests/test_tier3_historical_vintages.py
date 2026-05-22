from __future__ import annotations

import pandas as pd

from tdc_estimator.tier3_historical_vintages import (
    build_tier3_historical_vintages,
    render_tier3_historical_vintages_markdown,
    write_tier3_historical_vintages_from_paths,
)


def _outlays_fixture(path) -> None:
    pd.DataFrame(
        [
            ["2003-01-31", "Financial Agent Services", 100_000_000.0],
            ["2003-02-28", "Financial Agent Services", 100_000_000.0],
            ["2003-03-31", "Financial Agent Services", 100_000_000.0],
            ["2003-01-31", "International Disaster Assistance", 50_000_000.0],
            ["2003-02-28", "International Disaster Assistance", 50_000_000.0],
            ["2003-03-31", "International Disaster Assistance", 50_000_000.0],
            ["2003-01-31", "Foreign Military Financing Program", 25_000_000.0],
            ["2003-02-28", "Foreign Military Financing Program", 25_000_000.0],
            ["2003-03-31", "Foreign Military Financing Program", 25_000_000.0],
            ["2003-01-31", "United States Mint", -10_000_000.0],
            ["2003-02-28", "United States Mint", -10_000_000.0],
            ["2003-03-31", "United States Mint", -10_000_000.0],
        ],
        columns=["record_date", "classification_desc", "current_month_net_outly_amt"],
    ).to_csv(path, index=False)


def test_build_tier3_historical_vintages_assembles_correction_deltas(tmp_path) -> None:
    outlays = tmp_path / "outlays.csv"
    _outlays_fixture(outlays)
    bank = pd.DataFrame(
        {
            "bank_corp_tax_receipts_gross_strict_depository_mil": [20.0],
            "bank_corp_tax_receipts_gross_depository_plus_bhc_mil": [40.0],
            "bank_corp_tax_receipts_gross_finance_share_mil": [60.0],
        },
        index=pd.to_datetime(["2003-03-31"]),
    )
    bea = pd.DataFrame({"bea_row_current_receipts_total_q_mil": [70.0]}, index=pd.to_datetime(["2003-03-31"]))
    mrv = pd.DataFrame({"mrv_cbsp_primary_timing_overlay_mil": [5.0]}, index=pd.to_datetime(["2003-03-31"]))

    vintages = build_tier3_historical_vintages(
        mts_outlays_path=outlays,
        bank_receipts_bridge=bank,
        bea_row_anchor=bea,
        mrv_overlay=mrv,
        start="2003-03-31",
    )

    row = vintages.loc[pd.Timestamp("2003-03-31")]
    assert round(float(row["outlay_banks_mil"]), 3) == 300.0
    assert round(float(row["outlay_row_narrow_mil"]), 3) == 150.0
    assert round(float(row["outlay_row_broad_sensitivity_mil"]), 3) == 225.0
    assert round(float(row["cashfactor_mil"]), 3) == 30.0
    assert pd.isna(row["tier3_live_partial_shell_correction_mil"])
    assert round(float(row["tier3_extended_research_correction_mil"]), 3) == -310.0
    assert round(float(row["tier3_bea_anchored_research_correction_mil"]), 3) == -405.0
    assert pd.isna(row["tier3_live_default_correction_mil"])
    assert row["receipt_row_additive_rule"] == "bea_anchor_only_mrv_nonadditive_overlay"


def test_render_tier3_historical_vintages_markdown_marks_research_surface() -> None:
    vintages = pd.DataFrame(
        {
            "tier3_live_default_correction_mil": [pd.NA],
            "tier3_live_partial_shell_correction_mil": [pd.NA],
            "tier3_machinereadable_only_correction_mil": [pd.NA],
            "tier3_extended_research_correction_mil": [1.0],
            "tier3_bea_anchored_research_correction_mil": [2.0],
            "receipt_banks_depository_bhc_central_mil": [3.0],
            "receipt_row_bea_anchor_mil": [4.0],
            "receipt_row_mrv_nonadditive_overlay_mil": [0.5],
            "worst_component_key": ["receipt_row_bea_anchor"],
        },
        index=pd.to_datetime(["2003-03-31"]),
    )

    markdown = render_tier3_historical_vintages_markdown(vintages)

    assert "Tier 3 Historical Vintages" in markdown
    assert "correction deltas relative to Tier 2" in markdown
    assert "partial shell" in markdown
    assert "non-additive overlay" in markdown


def test_write_tier3_historical_vintages_from_paths_outputs_files(tmp_path) -> None:
    outlays = tmp_path / "outlays.csv"
    bank = tmp_path / "bank.csv"
    bea = tmp_path / "bea.csv"
    mrv = tmp_path / "mrv.csv"
    _outlays_fixture(outlays)
    pd.DataFrame(
        {
            "date": ["2003-03-31"],
            "bank_corp_tax_receipts_gross_strict_depository_mil": [20.0],
            "bank_corp_tax_receipts_gross_depository_plus_bhc_mil": [40.0],
            "bank_corp_tax_receipts_gross_finance_share_mil": [60.0],
        }
    ).to_csv(bank, index=False)
    pd.DataFrame({"date": ["2003-03-31"], "bea_row_current_receipts_total_q_mil": [70.0]}).to_csv(bea, index=False)
    pd.DataFrame({"date": ["2003-03-31"], "mrv_cbsp_primary_timing_overlay_mil": [5.0]}).to_csv(mrv, index=False)

    csv_path = tmp_path / "vintages.csv"
    md_path = tmp_path / "vintages.md"
    _, _, vintages = write_tier3_historical_vintages_from_paths(
        mts_outlays_path=outlays,
        bank_receipts_bridge_path=bank,
        bea_row_anchor_path=bea,
        mrv_overlay_path=mrv,
        csv_path=csv_path,
        markdown_path=md_path,
        start="2003-03-31",
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(vintages)
