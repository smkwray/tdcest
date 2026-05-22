from __future__ import annotations

import pandas as pd

from tdc_estimator.tier3_sensitivities_figures import (
    build_tier3_extension_sensitivity_matrix,
    plot_tier3_minus_tier2_component_decomposition,
    plot_tier3_research_extension_same_sample,
    render_tier3_extension_sensitivity_matrix_markdown,
    write_tier3_extension_sensitivity_matrix_from_paths,
)


def _sample_vintages() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "outlay_banks_mil": [10.0],
            "outlay_row_narrow_mil": [20.0],
            "outlay_row_broad_sensitivity_mil": [30.0],
            "cashfactor_mil": [5.0],
            "receipt_banks_strict_lower_mil": [100.0],
            "receipt_banks_depository_bhc_central_mil": [120.0],
            "receipt_banks_finance_upper_mil": [150.0],
            "receipt_row_bea_anchor_mil": [40.0],
            "receipt_row_mrv_nonadditive_overlay_mil": [3.0],
            "tier3_extended_research_correction_mil": [135.0],
            "tier3_bea_anchored_research_correction_mil": [105.0],
            "worst_component_key": ["receipt_row_bea_anchor"],
            "structural_break_flags": ["research_extension"],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )


def _sample_bank() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "bank_corp_tax_receipts_net_strict_depository_mil": [80.0],
            "bank_corp_tax_receipts_net_depository_plus_bhc_mil": [90.0],
            "bank_corp_tax_receipts_net_finance_share_mil": [110.0],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )


def test_build_tier3_extension_sensitivity_matrix_calculates_core_scenarios() -> None:
    matrix = build_tier3_extension_sensitivity_matrix(_sample_vintages(), _sample_bank())

    row = matrix.iloc[0]
    assert row["row_receipt_additive_rule"] == "do_not_add_mrv_to_bea_anchor"
    assert pd.isna(row["row_receipt_bea_plus_mrv_additive_mil"])
    assert round(float(row["scenario_gross_central_narrow_bea_mil"]), 3) == 135.0
    assert round(float(row["scenario_net_central_narrow_bea_mil"]), 3) == 105.0
    assert round(float(row["scenario_gross_central_broad_bea_mil"]), 3) == 125.0
    assert round(float(row["scenario_mrv_overlay_nonadditive_mil"]), 3) == 3.0


def test_write_tier3_extension_sensitivity_matrix_from_paths_outputs_files(tmp_path) -> None:
    vintages = tmp_path / "vintages.csv"
    bank = tmp_path / "bank.csv"
    _sample_vintages().rename_axis("date").to_csv(vintages)
    _sample_bank().rename_axis("date").to_csv(bank)
    csv_path = tmp_path / "matrix.csv"
    md_path = tmp_path / "matrix.md"

    _, _, matrix = write_tier3_extension_sensitivity_matrix_from_paths(
        vintages_path=vintages,
        bank_receipts_bridge_path=bank,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(matrix)
    assert "Historical Tier 3 research-extension" in render_tier3_extension_sensitivity_matrix_markdown(matrix)


def test_tier3_thesis_figure_functions_write_png_and_svg(tmp_path) -> None:
    matrix = build_tier3_extension_sensitivity_matrix(_sample_vintages(), _sample_bank())
    estimates = pd.DataFrame(
        {
            "tdc_tier1_fed_corrected_bank_only_ru_flow": [10.0],
            "tdc_tier2_interest_corrected_bank_only_ru_flow": [20.0],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )

    first = plot_tier3_research_extension_same_sample(estimates, matrix, tmp_path)
    second = plot_tier3_minus_tier2_component_decomposition(matrix, tmp_path)

    assert first.exists()
    assert first.with_suffix(".svg").exists()
    assert second.exists()
    assert second.with_suffix(".svg").exists()
