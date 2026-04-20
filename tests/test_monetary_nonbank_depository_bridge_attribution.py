from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.monetary_nonbank_depository_bridge_attribution import (
    build_monetary_nonbank_depository_bridge_attribution,
    render_monetary_nonbank_depository_bridge_attribution_markdown,
    write_monetary_nonbank_depository_bridge_attribution,
)


def test_build_monetary_nonbank_depository_bridge_attribution_computes_residual() -> None:
    stage0 = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "delta_credit_union_deposits_level_mil": [30.0],
            "delta_thrift_deposits_level_mil": [40.0],
            "delta_nonbank_depository_bridge_level_mil": [70.0],
        }
    )
    decomposition = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "bank_minus_depository_target_wedge_mil": [220.0],
            "small_time_component_mil": [40.0],
            "bank_minus_liquid_target_wedge_mil": [180.0],
        }
    )

    out = build_monetary_nonbank_depository_bridge_attribution(stage0=stage0, decomposition=decomposition)
    latest = out.iloc[0]

    assert round(float(latest["residual_bank_minus_liquid_wedge_after_nonbank_bridge_mil"]), 3) == 110.0
    assert round(float(latest["nonbank_depository_bridge_share_of_bank_minus_liquid_wedge"]), 6) == round(70.0 / 180.0, 6)
    assert latest["nonbank_bridge_sign_alignment"] == "same_sign"


def test_write_monetary_nonbank_depository_bridge_attribution_outputs_files(tmp_path: Path) -> None:
    stage0 = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "delta_credit_union_deposits_level_mil": [30.0],
            "delta_thrift_deposits_level_mil": [40.0],
            "delta_nonbank_depository_bridge_level_mil": [70.0],
        }
    )
    decomposition = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "bank_minus_depository_target_wedge_mil": [220.0],
            "small_time_component_mil": [40.0],
            "bank_minus_liquid_target_wedge_mil": [180.0],
        }
    )
    csv_path = tmp_path / "nonbank_bridge.csv"
    md_path = tmp_path / "nonbank_bridge.md"

    _, _, attribution = write_monetary_nonbank_depository_bridge_attribution(
        monetary_stage0_diagnostics=stage0,
        monetary_target_definition_decomposition=decomposition,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(attribution)
    markdown = render_monetary_nonbank_depository_bridge_attribution_markdown(attribution)
    assert "Monetary Nonbank Depository Bridge Attribution" in markdown
    assert "Residual after loaded bridge" in markdown
