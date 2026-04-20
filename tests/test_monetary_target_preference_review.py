from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.monetary_target_preference_review import (
    build_monetary_target_preference_review,
    render_monetary_target_preference_review_markdown,
    write_monetary_target_preference_review,
)


def test_build_monetary_target_preference_review_prefers_depository_when_bank_gap_is_wedge_dominant() -> None:
    residuals = pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31"],
            "target_family": ["depository_target", "commercial_bank_deposit_target"],
            "gap_vs_tier3_mil": [156.0, 371.0],
            "residual_after_expanded_mil": [75.0, 290.0],
            "total_explained_share_after_expanded": [0.52, 0.22],
            "residual_regime": ["partly_explained", "mostly_unresolved"],
        }
    )
    wedge = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "bank_specific_residual_wedge_mil": [215.0],
            "bank_specific_residual_share_of_bank_residual": [0.74],
            "bank_wedge_dominance": ["bank_target_wedge_dominant"],
        }
    )

    review = build_monetary_target_preference_review(residuals, wedge)
    row = review.iloc[0]

    assert row["recommendation_status"] == "prefer_depository_target_crosscheck"
    assert row["commercial_bank_target_role"] == "stress_test_only"
    assert row["preferred_target"] == "depository_target"


def test_write_monetary_target_preference_review_outputs_files(tmp_path: Path) -> None:
    residuals = pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31"],
            "target_family": ["depository_target", "commercial_bank_deposit_target"],
            "gap_vs_tier3_mil": [156.0, 371.0],
            "residual_after_expanded_mil": [75.0, 290.0],
            "total_explained_share_after_expanded": [0.52, 0.22],
            "residual_regime": ["partly_explained", "mostly_unresolved"],
        }
    )
    wedge = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "bank_specific_residual_wedge_mil": [215.0],
            "bank_specific_residual_share_of_bank_residual": [0.74],
            "bank_wedge_dominance": ["bank_target_wedge_dominant"],
        }
    )

    csv_path = tmp_path / "pref.csv"
    md_path = tmp_path / "pref.md"
    _, _, review = write_monetary_target_preference_review(
        monetary_residual_interpretation=residuals,
        monetary_target_wedge=wedge,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(review)
    markdown = render_monetary_target_preference_review_markdown(review)
    assert "Monetary Target Preference Review" in markdown
    assert "prefer_depository_target_crosscheck" in markdown
