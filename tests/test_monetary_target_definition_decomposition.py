from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.monetary_target_definition_decomposition import (
    build_monetary_target_definition_decomposition,
    render_monetary_target_definition_decomposition_markdown,
    write_monetary_target_definition_decomposition,
)


def test_build_monetary_target_definition_decomposition_splits_wedge_components() -> None:
    bridge = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "bank_minus_depository_target_wedge_mil": [215.0],
            "small_time_component_mil": [36.0],
            "bank_minus_liquid_target_wedge_mil": [179.0],
            "bank_specific_residual_wedge_mil": [215.0],
        }
    )

    out = build_monetary_target_definition_decomposition(bridge)
    latest = out.iloc[0]

    assert round(float(latest["small_time_share_of_target_wedge"]), 6) == round(36.0 / 215.0, 6)
    assert round(float(latest["bank_minus_liquid_share_of_target_wedge"]), 6) == round(179.0 / 215.0, 6)
    assert latest["target_definition_component_dominance"] == "bank_minus_liquid_component_dominant"


def test_write_monetary_target_definition_decomposition_outputs_files(tmp_path: Path) -> None:
    bridge = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "bank_minus_depository_target_wedge_mil": [215.0],
            "small_time_component_mil": [36.0],
            "bank_minus_liquid_target_wedge_mil": [179.0],
            "bank_specific_residual_wedge_mil": [215.0],
        }
    )

    csv_path = tmp_path / "decomposition.csv"
    md_path = tmp_path / "decomposition.md"
    _, _, decomposition = write_monetary_target_definition_decomposition(
        monetary_target_definition_bridge=bridge,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(decomposition)
    markdown = render_monetary_target_definition_decomposition_markdown(decomposition)
    assert "Monetary Target Definition Decomposition" in markdown
    assert "bank_minus_liquid_component_dominant" in markdown
