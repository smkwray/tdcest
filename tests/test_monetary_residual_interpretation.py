from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.monetary_residual_interpretation import (
    build_monetary_residual_interpretation,
    render_monetary_residual_interpretation_markdown,
    write_monetary_residual_interpretation,
)


def test_build_monetary_residual_interpretation_computes_waterfall_and_regimes() -> None:
    controls = pd.DataFrame(
        {
            "depository_target_minus_tier3_bank_only_flow_mil": [100.0],
            "depository_target_minus_tier3_bank_only_flow_mil_minus_simple_controls_mil": [70.0],
            "depository_target_minus_tier3_bank_only_flow_mil_minus_refined_controls_mil": [50.0],
            "depository_target_minus_tier3_bank_only_flow_mil_minus_expanded_controls_mil": [30.0],
            "commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil": [200.0],
            "commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil_minus_simple_controls_mil": [180.0],
            "commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil_minus_refined_controls_mil": [140.0],
            "commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil_minus_expanded_controls_mil": [120.0],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )

    out = build_monetary_residual_interpretation(controls)
    depository = out.loc[out["target_family"] == "depository_target"].iloc[0]
    bank = out.loc[out["target_family"] == "commercial_bank_deposit_target"].iloc[0]

    assert round(float(depository["simple_explained_mil"]), 3) == 30.0
    assert round(float(depository["incremental_refined_explained_mil"]), 3) == 20.0
    assert round(float(depository["incremental_expanded_explained_mil"]), 3) == 20.0
    assert round(float(depository["total_explained_share_after_expanded"]), 3) == 0.7
    assert depository["residual_regime"] == "largely_explained"
    assert bank["residual_regime"] == "partly_explained"


def test_write_monetary_residual_interpretation_outputs_files(tmp_path: Path) -> None:
    controls = pd.DataFrame(
        {
            "depository_target_minus_tier3_bank_only_flow_mil": [100.0],
            "depository_target_minus_tier3_bank_only_flow_mil_minus_simple_controls_mil": [70.0],
            "depository_target_minus_tier3_bank_only_flow_mil_minus_refined_controls_mil": [50.0],
            "depository_target_minus_tier3_bank_only_flow_mil_minus_expanded_controls_mil": [30.0],
            "commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil": [200.0],
            "commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil_minus_simple_controls_mil": [180.0],
            "commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil_minus_refined_controls_mil": [140.0],
            "commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil_minus_expanded_controls_mil": [120.0],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )

    csv_path = tmp_path / "residual.csv"
    md_path = tmp_path / "residual.md"
    _, _, residuals = write_monetary_residual_interpretation(
        monetary_stage1_controls=controls,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(residuals)
    markdown = render_monetary_residual_interpretation_markdown(residuals)
    assert "Monetary Residual Interpretation" in markdown
    assert "expanded residual" in markdown
