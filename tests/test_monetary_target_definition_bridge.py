from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.monetary_target_definition_bridge import (
    build_monetary_target_definition_bridge,
    render_monetary_target_definition_bridge_markdown,
    write_monetary_target_definition_bridge,
)


def test_build_monetary_target_definition_bridge_matches_raw_and_residual_wedges() -> None:
    stage0 = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "delta_partial_m2_less_currency_level_mil": [172.0],
            "delta_depository_target_level_mil": [116.0],
            "delta_liquid_deposit_target_level_mil": [152.0],
            "delta_commercial_bank_deposits_level_mil": [331.0],
        }
    )
    wedge = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "bank_specific_residual_wedge_mil": [215.0],
            "bank_minus_depository_target_wedge_mil": [215.0],
            "depository_residual_after_expanded_mil": [75.0],
            "bank_residual_after_expanded_mil": [290.0],
        }
    )

    out = build_monetary_target_definition_bridge(stage0, wedge)
    latest = out.iloc[0]

    assert round(float(latest["retail_mmf_component_mil"]), 3) == 56.0
    assert round(float(latest["small_time_component_mil"]), 3) == 36.0
    assert round(float(latest["bank_minus_depository_target_wedge_mil"]), 3) == 215.0
    assert round(float(latest["wedge_alignment_gap_mil"]), 3) == 0.0
    assert latest["bank_wedge_alignment_status"] == "wedge_matches_target_definition"


def test_write_monetary_target_definition_bridge_outputs_files(tmp_path: Path) -> None:
    stage0 = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "delta_partial_m2_less_currency_level_mil": [172.0],
            "delta_depository_target_level_mil": [116.0],
            "delta_liquid_deposit_target_level_mil": [152.0],
            "delta_commercial_bank_deposits_level_mil": [331.0],
        }
    )
    wedge = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "bank_specific_residual_wedge_mil": [215.0],
            "bank_minus_depository_target_wedge_mil": [215.0],
            "depository_residual_after_expanded_mil": [75.0],
            "bank_residual_after_expanded_mil": [290.0],
        }
    )

    csv_path = tmp_path / "bridge.csv"
    md_path = tmp_path / "bridge.md"
    _, _, bridge = write_monetary_target_definition_bridge(
        monetary_stage0_diagnostics=stage0,
        monetary_target_wedge=wedge,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(bridge)
    markdown = render_monetary_target_definition_bridge_markdown(bridge)
    assert "Monetary Target Definition Bridge" in markdown
    assert "wedge_matches_target_definition" in markdown
