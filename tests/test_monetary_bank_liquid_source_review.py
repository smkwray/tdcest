from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.monetary_bank_liquid_source_review import (
    build_monetary_bank_liquid_source_review,
    render_monetary_bank_liquid_source_review_markdown,
    write_monetary_bank_liquid_source_review,
)


def test_build_monetary_bank_liquid_source_review_marks_context_boundary() -> None:
    liability_audit = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "delta_nonbank_depository_bridge_level_mil": [32.0],
            "nonbank_bridge_share_of_bank_minus_liquid_wedge": [32.0 / 179.0],
            "delta_large_time_deposits_all_commercial_banks_level_mil": [48.0],
            "large_time_share_of_bank_minus_liquid_wedge": [48.0 / 179.0],
            "delta_other_deposits_all_commercial_banks_level_mil": [86.0],
            "other_deposits_share_of_bank_minus_liquid_wedge": [86.0 / 179.0],
            "loaded_liability_context_total_mil": [80.0],
            "loaded_liability_context_share_of_bank_minus_liquid_wedge": [80.0 / 179.0],
            "residual_bank_minus_liquid_wedge_after_loaded_liability_context_mil": [99.0],
        }
    )
    perimeter_review = pd.DataFrame(
        {
            "latest_quarter": ["2025-12-31"],
            "review_status": ["new_source_families_required"],
            "recommended_next_step": ["target_bank_only_liquid_subcomponents"],
            "has_bank_only_liquid_deposit_subcomponents": [False],
            "missing_source_families": ["bank_only_liquid_deposit_subcomponents"],
            "review_rationale": ["Need a cleaner bank-only liquid family."],
        }
    )
    source_map = pd.DataFrame(
        {
            "source_family_key": [
                "bank_only_liquid_deposit_subcomponents",
                "large_time_or_wholesale_deposit_components",
            ],
            "candidate_series_or_product": [
                "ODSACBM027SBOG; fallback ODSACBM027NBOG or ODSACBW027SBOG; rejected ODSACBM027NBOG plus WDDNS pair",
                "LTDACBM027SBOG",
            ],
            "current_repo_stance": [
                "loaded_broad_context_not_subcomponent",
                "loaded_context_series",
            ],
        }
    )

    review = build_monetary_bank_liquid_source_review(
        liability_candidate_audit=liability_audit,
        perimeter_gap_review=perimeter_review,
        perimeter_source_map=source_map,
    )
    row = review.iloc[0]

    assert row["review_status"] == "no_clean_bank_only_liquid_subcomponent_loaded"
    assert row["recommendation_status"] == "keep_current_context_boundary"
    assert row["best_loaded_broad_context_series"] == "ODSACBM027SBOG"
    assert row["loaded_large_time_series"] == "LTDACBM027SBOG"
    assert row["rejected_candidate_construction"] == "ODSACBM027NBOG_plus_WDDNS"


def test_write_monetary_bank_liquid_source_review_outputs_files(tmp_path: Path) -> None:
    liability_audit = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "delta_nonbank_depository_bridge_level_mil": [32.0],
            "nonbank_bridge_share_of_bank_minus_liquid_wedge": [32.0 / 179.0],
            "delta_large_time_deposits_all_commercial_banks_level_mil": [48.0],
            "large_time_share_of_bank_minus_liquid_wedge": [48.0 / 179.0],
            "delta_other_deposits_all_commercial_banks_level_mil": [86.0],
            "other_deposits_share_of_bank_minus_liquid_wedge": [86.0 / 179.0],
            "loaded_liability_context_total_mil": [80.0],
            "loaded_liability_context_share_of_bank_minus_liquid_wedge": [80.0 / 179.0],
            "residual_bank_minus_liquid_wedge_after_loaded_liability_context_mil": [99.0],
        }
    )
    perimeter_review = pd.DataFrame(
        {
            "latest_quarter": ["2025-12-31"],
            "review_status": ["new_source_families_required"],
            "recommended_next_step": ["target_bank_only_liquid_subcomponents"],
            "has_bank_only_liquid_deposit_subcomponents": [False],
            "missing_source_families": ["bank_only_liquid_deposit_subcomponents"],
            "review_rationale": ["Need a cleaner bank-only liquid family."],
        }
    )
    source_map = pd.DataFrame(
        {
            "source_family_key": [
                "bank_only_liquid_deposit_subcomponents",
                "large_time_or_wholesale_deposit_components",
            ],
            "candidate_series_or_product": [
                "ODSACBM027SBOG; fallback ODSACBM027NBOG or ODSACBW027SBOG; rejected ODSACBM027NBOG plus WDDNS pair",
                "LTDACBM027SBOG",
            ],
            "current_repo_stance": [
                "loaded_broad_context_not_subcomponent",
                "loaded_context_series",
            ],
        }
    )

    csv_path = tmp_path / "review.csv"
    md_path = tmp_path / "review.md"

    _, _, review = write_monetary_bank_liquid_source_review(
        monetary_bank_liability_candidate_audit=liability_audit,
        monetary_bank_perimeter_gap_review=perimeter_review,
        monetary_bank_perimeter_source_map=source_map,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(review)
    markdown = render_monetary_bank_liquid_source_review_markdown(review)
    assert "Monetary Bank Liquid Source Review" in markdown
    assert "ODSACBM027SBOG" in markdown
    assert "ODSACBM027NBOG_plus_WDDNS" in markdown
