from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.monetary_bank_liquid_stop_gate import (
    build_monetary_bank_liquid_stop_gate,
    render_monetary_bank_liquid_stop_gate_markdown,
    write_monetary_bank_liquid_stop_gate,
)


def test_build_monetary_bank_liquid_stop_gate_marks_stop_condition() -> None:
    source_review = pd.DataFrame(
        {
            "latest_quarter": ["2025-12-31"],
            "recommendation_status": ["keep_current_context_boundary"],
            "best_loaded_broad_context_series": ["ODSACBM027SBOG"],
            "best_loaded_broad_context_role": ["broad_context_only"],
            "best_loaded_broad_context_share_of_wedge": [86.0 / 179.0],
            "loaded_large_time_series": ["LTDACBM027SBOG"],
            "loaded_large_time_role": ["loaded_context_series"],
            "loaded_additive_liability_context_share_of_wedge": [80.0 / 179.0],
            "residual_after_loaded_additive_liability_context_mil": [99.0],
            "rejected_candidate_construction": ["ODSACBM027NBOG_plus_WDDNS"],
            "rejected_candidate_reason": ["likely_double_counts_demand_deposits"],
            "source_map_liquid_stance": ["loaded_broad_context_not_subcomponent"],
            "has_clean_bank_only_liquid_subcomponent_loaded": [False],
            "review_rationale": ["Still a public-source boundary."],
        }
    )
    perimeter_review = pd.DataFrame(
        {
            "latest_quarter": ["2025-12-31"],
            "has_bank_vs_broad_depository_bridge": [True],
            "has_large_time_or_wholesale_deposit_components": [True],
            "review_status": ["new_source_families_required"],
        }
    )

    gate = build_monetary_bank_liquid_stop_gate(
        bank_liquid_source_review=source_review,
        perimeter_gap_review=perimeter_review,
    )

    summary = gate[gate["row_type"] == "summary"].iloc[0]
    clean_check = gate[gate["check_name"] == "clean_bank_only_liquid_subcomponent_loaded"].iloc[0]
    assert summary["status"] == "stop_at_perimeter_stress_test"
    assert clean_check["status"] == "fail"
    assert clean_check["blocking_issue_type"] == "source_boundary"


def test_write_monetary_bank_liquid_stop_gate_outputs_files(tmp_path: Path) -> None:
    source_review = pd.DataFrame(
        {
            "latest_quarter": ["2025-12-31"],
            "recommendation_status": ["keep_current_context_boundary"],
            "best_loaded_broad_context_series": ["ODSACBM027SBOG"],
            "best_loaded_broad_context_role": ["broad_context_only"],
            "best_loaded_broad_context_share_of_wedge": [86.0 / 179.0],
            "loaded_large_time_series": ["LTDACBM027SBOG"],
            "loaded_large_time_role": ["loaded_context_series"],
            "loaded_additive_liability_context_share_of_wedge": [80.0 / 179.0],
            "residual_after_loaded_additive_liability_context_mil": [99.0],
            "rejected_candidate_construction": ["ODSACBM027NBOG_plus_WDDNS"],
            "rejected_candidate_reason": ["likely_double_counts_demand_deposits"],
            "source_map_liquid_stance": ["loaded_broad_context_not_subcomponent"],
            "has_clean_bank_only_liquid_subcomponent_loaded": [False],
            "review_rationale": ["Still a public-source boundary."],
        }
    )
    perimeter_review = pd.DataFrame(
        {
            "latest_quarter": ["2025-12-31"],
            "has_bank_vs_broad_depository_bridge": [True],
            "has_large_time_or_wholesale_deposit_components": [True],
            "review_status": ["new_source_families_required"],
        }
    )
    csv_path = tmp_path / "gate.csv"
    md_path = tmp_path / "gate.md"

    _, _, gate = write_monetary_bank_liquid_stop_gate(
        monetary_bank_liquid_source_review=source_review,
        monetary_bank_perimeter_gap_review=perimeter_review,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(gate)
    markdown = render_monetary_bank_liquid_stop_gate_markdown(gate)
    assert "Monetary Bank Liquid Stop Gate" in markdown
    assert "stop_at_perimeter_stress_test" in markdown
