from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.monetary_bank_target_gap_attribution import (
    build_monetary_bank_target_gap_attribution,
    render_monetary_bank_target_gap_attribution_markdown,
    write_monetary_bank_target_gap_attribution,
)


def test_build_monetary_bank_target_gap_attribution_reconstructs_gap_and_residual() -> None:
    residuals = pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31"],
            "target_family": ["depository_target", "commercial_bank_deposit_target"],
            "gap_vs_tier3_mil": [156.0, 371.0],
            "residual_after_expanded_mil": [75.0, 290.0],
        }
    )
    decomposition = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "small_time_component_mil": [36.0],
            "bank_minus_liquid_target_wedge_mil": [179.0],
            "bank_specific_residual_wedge_mil": [215.0],
        }
    )

    out = build_monetary_bank_target_gap_attribution(residuals, decomposition)
    latest = out.iloc[0]

    assert round(float(latest["reconstructed_bank_gap_mil"]), 3) == 371.0
    assert round(float(latest["reconstructed_bank_residual_mil"]), 3) == 290.0
    assert round(float(latest["bank_gap_reconstruction_error_mil"]), 3) == 0.0
    assert round(float(latest["bank_residual_reconstruction_error_mil"]), 3) == 0.0
    assert latest["bank_residual_component_dominance"] == "bank_minus_liquid_component_dominant"


def test_write_monetary_bank_target_gap_attribution_outputs_files(tmp_path: Path) -> None:
    residuals = pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31"],
            "target_family": ["depository_target", "commercial_bank_deposit_target"],
            "gap_vs_tier3_mil": [156.0, 371.0],
            "residual_after_expanded_mil": [75.0, 290.0],
        }
    )
    decomposition = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "small_time_component_mil": [36.0],
            "bank_minus_liquid_target_wedge_mil": [179.0],
            "bank_specific_residual_wedge_mil": [215.0],
        }
    )

    csv_path = tmp_path / "attribution.csv"
    md_path = tmp_path / "attribution.md"
    _, _, attribution = write_monetary_bank_target_gap_attribution(
        monetary_residual_interpretation=residuals,
        monetary_target_definition_decomposition=decomposition,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(attribution)
    markdown = render_monetary_bank_target_gap_attribution_markdown(attribution)
    assert "Monetary Bank Target Gap Attribution" in markdown
    assert "bank_minus_liquid_component_dominant" in markdown
