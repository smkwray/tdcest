from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.monetary_target_wedge import (
    build_monetary_target_wedge,
    render_monetary_target_wedge_markdown,
    write_monetary_target_wedge,
)


def test_build_monetary_target_wedge_isolates_bank_specific_residual() -> None:
    controls = pd.DataFrame(
        {
            "delta_depository_target_level_mil": [100.0],
            "delta_commercial_bank_deposits_level_mil": [250.0],
            "depository_target_minus_tier3_bank_only_flow_mil": [120.0],
            "commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil": [270.0],
            "depository_target_minus_tier3_bank_only_flow_mil_minus_expanded_controls_mil": [60.0],
            "commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil_minus_expanded_controls_mil": [210.0],
            "delta_commercial_bank_cash_assets_mil": [30.0],
            "delta_foreign_official_custody_treasuries_mil": [-20.0],
            "delta_foreign_related_treasury_agency_non_mbs_mil": [15.0],
            "delta_tga_weekly_level_mil": [10.0],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )

    wedge = build_monetary_target_wedge(controls)
    latest = wedge.iloc[0]

    assert round(float(latest["bank_minus_depository_target_wedge_mil"]), 3) == 150.0
    assert round(float(latest["bank_specific_residual_wedge_mil"]), 3) == 150.0
    assert round(float(latest["bank_specific_residual_share_of_bank_residual"]), 3) == 0.714
    assert latest["bank_wedge_dominance"] == "bank_target_wedge_dominant"


def test_write_monetary_target_wedge_outputs_files(tmp_path: Path) -> None:
    controls = pd.DataFrame(
        {
            "delta_depository_target_level_mil": [100.0],
            "delta_commercial_bank_deposits_level_mil": [250.0],
            "depository_target_minus_tier3_bank_only_flow_mil": [120.0],
            "commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil": [270.0],
            "depository_target_minus_tier3_bank_only_flow_mil_minus_expanded_controls_mil": [60.0],
            "commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil_minus_expanded_controls_mil": [210.0],
            "delta_commercial_bank_cash_assets_mil": [30.0],
            "delta_foreign_official_custody_treasuries_mil": [-20.0],
            "delta_foreign_related_treasury_agency_non_mbs_mil": [15.0],
            "delta_tga_weekly_level_mil": [10.0],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )

    csv_path = tmp_path / "wedge.csv"
    md_path = tmp_path / "wedge.md"
    _, _, wedge = write_monetary_target_wedge(
        monetary_stage1_controls=controls,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(wedge)
    markdown = render_monetary_target_wedge_markdown(wedge)
    assert "Monetary Target Wedge" in markdown
    assert "bank-target-specific wedge" in markdown
