from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.fiscal_reconciliation import (
    build_fiscal_reconciliation_cells,
    build_fiscal_reconciliation_residuals,
    build_fiscal_source_quality,
    write_fiscal_reconciliation_outputs,
)


def test_build_fiscal_reconciliation_cells_includes_default_and_receipt_benchmark_rows() -> None:
    idx = pd.to_datetime(["2025-12-31"])
    estimates = pd.DataFrame(
        {
            "tdc_base_bank_only_ru_flow": [100.0],
            "tdc_tier1_fed_corrected_bank_only_ru_flow": [90.0],
            "tdc_tier2_interest_corrected_bank_only_ru_flow": [80.0],
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [70.0],
        },
        index=idx,
    )
    components = pd.DataFrame(
        {
            "fed_tsy_tx": [10.0],
            "bank_depository_tsy_tx": [20.0],
            "row_tsy_tx": [30.0],
            "minus_treasury_operating_cash_tx": [35.0],
            "fed_remit_positive": [5.0],
        },
        index=idx,
    )
    corrections = pd.DataFrame(
        {
            "tier1_fed_coupon_correction": [-10.0],
            "tier2_bank_coupon_correction": [-5.0],
            "tier2_row_coupon_correction": [-5.0],
            "tier3_bank_noninterest_outlay_correction": [-4.0],
            "tier3_row_noninterest_outlay_correction": [-3.0],
            "tier3_bank_nonborrow_receipt_correction": [2.0],
            "tier3_row_nonborrow_receipt_correction": [0.0],
            "tier3_mint_cb_cash_factor_correction": [0.0],
        },
        index=idx,
    )
    bea = pd.DataFrame({"bea_row_current_receipts_total_q_mil": [12.0]}, index=idx)
    bank_bridge = pd.DataFrame({"bank_corp_tax_receipts_gross_finance_share_mil": [8.0]}, index=idx)

    cells = build_fiscal_reconciliation_cells(
        estimates,
        components,
        corrections,
        bea_row_receipts_benchmark=bea,
        bank_corp_tax_receipts_bridge=bank_bridge,
        start="2025-12-31",
    )

    assert "default" in set(cells["role"])
    assert "benchmark" in set(cells["role"])
    assert (
        cells.loc[
            cells["row_family"].eq("nonborrow_receipts")
            & cells["counterparty_column"].eq("row_total")
            & cells["source"].eq("bea_nipa_table_3_2"),
            "value_millions",
        ].iloc[0]
        == 12.0
    )


def test_build_fiscal_reconciliation_residuals_reconstructs_default_path() -> None:
    idx = pd.to_datetime(["2025-12-31"])
    estimates = pd.DataFrame(
        {
            "tdc_base_bank_only_ru_flow": [100.0],
            "tdc_tier1_fed_corrected_bank_only_ru_flow": [90.0],
            "tdc_tier2_interest_corrected_bank_only_ru_flow": [80.0],
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [75.0],
        },
        index=idx,
    )
    components = pd.DataFrame(
        {
            "fed_tsy_tx": [10.0],
            "bank_depository_tsy_tx": [20.0],
            "row_tsy_tx": [30.0],
            "minus_treasury_operating_cash_tx": [35.0],
            "fed_remit_positive": [5.0],
        },
        index=idx,
    )
    corrections = pd.DataFrame(
        {
            "tier1_fed_coupon_correction": [-10.0],
            "tier2_bank_coupon_correction": [-5.0],
            "tier2_row_coupon_correction": [-5.0],
            "tier3_bank_noninterest_outlay_correction": [-4.0],
            "tier3_row_noninterest_outlay_correction": [-3.0],
            "tier3_bank_nonborrow_receipt_correction": [2.0],
            "tier3_row_nonborrow_receipt_correction": [0.0],
            "tier3_mint_cb_cash_factor_correction": [0.0],
        },
        index=idx,
    )

    cells = build_fiscal_reconciliation_cells(estimates, components, corrections, start="2025-12-31")
    residuals = build_fiscal_reconciliation_residuals(estimates, cells, start="2025-12-31")

    assert round(float(residuals.loc[pd.Timestamp("2025-12-31"), "tier0_reconstruction_residual_mil"]), 6) == 0.0
    assert round(float(residuals.loc[pd.Timestamp("2025-12-31"), "tier1_reconstruction_residual_mil"]), 6) == 0.0
    assert round(float(residuals.loc[pd.Timestamp("2025-12-31"), "tier2_reconstruction_residual_mil"]), 6) == 0.0
    assert round(float(residuals.loc[pd.Timestamp("2025-12-31"), "tier3_reconstruction_residual_mil"]), 6) == 0.0


def test_write_fiscal_reconciliation_outputs(tmp_path: Path) -> None:
    idx = pd.to_datetime(["2025-12-31"])
    estimates = pd.DataFrame(
        {
            "tdc_base_bank_only_ru_flow": [100.0],
            "tdc_tier1_fed_corrected_bank_only_ru_flow": [90.0],
            "tdc_tier2_interest_corrected_bank_only_ru_flow": [80.0],
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [75.0],
        },
        index=idx,
    )
    components = pd.DataFrame(
        {
            "fed_tsy_tx": [10.0],
            "bank_depository_tsy_tx": [20.0],
            "row_tsy_tx": [30.0],
            "minus_treasury_operating_cash_tx": [35.0],
            "fed_remit_positive": [5.0],
        },
        index=idx,
    )
    corrections = pd.DataFrame(
        {
            "tier1_fed_coupon_correction": [-10.0],
            "tier2_bank_coupon_correction": [-5.0],
            "tier2_row_coupon_correction": [-5.0],
            "tier3_bank_noninterest_outlay_correction": [-4.0],
            "tier3_row_noninterest_outlay_correction": [-3.0],
            "tier3_bank_nonborrow_receipt_correction": [2.0],
            "tier3_row_nonborrow_receipt_correction": [0.0],
            "tier3_mint_cb_cash_factor_correction": [0.0],
        },
        index=idx,
    )

    cells_csv = tmp_path / "cells.csv"
    residuals_csv = tmp_path / "residuals.csv"
    source_quality_csv = tmp_path / "source_quality.csv"
    residuals_md = tmp_path / "residuals.md"
    source_quality_md = tmp_path / "source_quality.md"
    _, _, _, cells, residuals, source_quality = write_fiscal_reconciliation_outputs(
        estimates,
        components,
        corrections,
        cells_csv_path=cells_csv,
        residuals_csv_path=residuals_csv,
        source_quality_csv_path=source_quality_csv,
        residuals_markdown_path=residuals_md,
        source_quality_markdown_path=source_quality_md,
        start="2025-12-31",
    )

    assert cells_csv.exists()
    assert residuals_csv.exists()
    assert source_quality_csv.exists()
    assert residuals_md.exists()
    assert source_quality_md.exists()
    assert len(cells) > 0
    assert len(residuals) > 0
    assert len(source_quality) > 0
    assert "role" in pd.read_csv(source_quality_csv).columns

