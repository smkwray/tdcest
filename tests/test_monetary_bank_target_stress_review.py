from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.monetary_bank_target_stress_review import (
    build_monetary_bank_target_stress_review,
    render_monetary_bank_target_stress_review_markdown,
    write_monetary_bank_target_stress_review,
)


def test_build_monetary_bank_target_stress_review_flags_perimeter_stress_test() -> None:
    decomposition = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "bank_minus_depository_target_wedge_mil": [215.0],
            "small_time_component_mil": [36.0],
            "bank_minus_liquid_target_wedge_mil": [179.0],
            "bank_specific_residual_wedge_mil": [215.0],
            "small_time_share_of_target_wedge": [36.0 / 215.0],
            "bank_minus_liquid_share_of_target_wedge": [179.0 / 215.0],
            "abs_small_time_share_of_components": [36.0 / (36.0 + 179.0)],
            "abs_bank_minus_liquid_share_of_components": [179.0 / (36.0 + 179.0)],
            "target_definition_component_dominance": ["bank_minus_liquid_component_dominant"],
        }
    )
    preference = pd.DataFrame(
        {
            "latest_quarter": ["2025-12-31"],
            "commercial_bank_target_role": ["stress_test_only"],
        }
    )

    review = build_monetary_bank_target_stress_review(decomposition, preference)
    row = review.iloc[0]

    assert row["review_status"] == "bank_target_is_perimeter_stress_test"
    assert row["recommended_use"] == "stress_test_for_bank_perimeter_definition"


def test_write_monetary_bank_target_stress_review_outputs_files(tmp_path: Path) -> None:
    decomposition = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "bank_minus_depository_target_wedge_mil": [215.0],
            "small_time_component_mil": [36.0],
            "bank_minus_liquid_target_wedge_mil": [179.0],
            "bank_specific_residual_wedge_mil": [215.0],
            "small_time_share_of_target_wedge": [36.0 / 215.0],
            "bank_minus_liquid_share_of_target_wedge": [179.0 / 215.0],
            "abs_small_time_share_of_components": [36.0 / (36.0 + 179.0)],
            "abs_bank_minus_liquid_share_of_components": [179.0 / (36.0 + 179.0)],
            "target_definition_component_dominance": ["bank_minus_liquid_component_dominant"],
        }
    )
    preference = pd.DataFrame(
        {
            "latest_quarter": ["2025-12-31"],
            "commercial_bank_target_role": ["stress_test_only"],
        }
    )

    csv_path = tmp_path / "review.csv"
    md_path = tmp_path / "review.md"
    _, _, review = write_monetary_bank_target_stress_review(
        monetary_target_definition_decomposition=decomposition,
        monetary_target_preference_review=preference,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(review)
    markdown = render_monetary_bank_target_stress_review_markdown(review)
    assert "Monetary Bank Target Stress Review" in markdown
    assert "bank_target_is_perimeter_stress_test" in markdown
