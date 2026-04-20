from __future__ import annotations

import pandas as pd

from tdc_estimator.downstream_problem_variable_review import (
    build_downstream_problem_variable_review,
)


def test_downstream_problem_variable_review_maps_live_terms_and_boundary_cells() -> None:
    quality = pd.DataFrame(
        [
            {
                "last_date": "2025-12-31",
                "latest_value_millions": -70.0,
                "reliability_grade": "medium",
                "notes": "Proxy Treasury coupon-interest correction to the rest of the world, with scale audited against BEA/FRED.",
            },
            {
                "last_date": "2025-12-31",
                "latest_value_millions": -22.0,
                "reliability_grade": "high",
                "notes": "Exact SOMA-based Treasury coupon-interest correction to the Fed.",
            },
            {
                "last_date": "2025-12-31",
                "latest_value_millions": -14.5,
                "reliability_grade": "medium",
                "notes": "Proxy Treasury coupon-interest correction to the default bank perimeter.",
            },
            {
                "last_date": "2025-12-31",
                "latest_value_millions": -1.6,
                "reliability_grade": "medium",
                "notes": "Current default narrow ROW noninterest-outlay correction from selected MTS foreign and international lines.",
            },
            {
                "last_date": "2025-12-31",
                "latest_value_millions": -0.4,
                "reliability_grade": "medium",
                "notes": "Current default bank noninterest-outlay correction from MTS Financial Agent Services-style lines.",
            },
        ]
    )
    gap = pd.DataFrame(
        [
            {
                "gap_key": "latest_live_base_to_tier2_bank_only",
                "dominant_component_key": "tier2_row_coupon_correction",
                "secondary_component_key": "tier1_fed_coupon_correction",
            },
            {
                "gap_key": "latest_live_tier2_to_tier3_bank_only",
                "dominant_component_key": "tier3_row_noninterest_outlay_correction",
                "secondary_component_key": "tier3_bank_noninterest_outlay_correction",
            },
            {
                "gap_key": "latest_historical_bank_receipt_overlay",
                "dominant_component_key": "bank_receipt_historical_default_candidate_delta_mil",
                "secondary_component_key": "bank_receipt_historical_lower_bound_delta_mil",
            },
            {
                "gap_key": "latest_live_bank_to_broad_depository_tier3",
                "dominant_component_key": "np_credit_unions_tsy_tx",
                "secondary_component_key": "n/a",
                "reference_date": "2025-12-31",
                "dominant_component_millions": 218.0,
            },
        ]
    )
    boundary = pd.DataFrame(
        [
            {
                "boundary_key": "bank_live_default_receipt_cell",
                "current_repo_role": "default_zero_cell",
                "included_in_live_tier3_headline": True,
                "latest_reference_date": "2025-12-31",
                "latest_value_millions": 0.0,
                "binding_blocker": "stale_share_rule",
                "interpretation": "Bank live receipt interpretation.",
            },
            {
                "boundary_key": "row_live_default_receipt_cell",
                "current_repo_role": "default_zero_cell",
                "included_in_live_tier3_headline": True,
                "latest_reference_date": "2025-12-31",
                "latest_value_millions": 0.0,
                "binding_blocker": "evidence_boundary",
                "interpretation": "ROW live receipt interpretation.",
            },
            {
                "boundary_key": "bank_receipt_historical_overlay_candidate",
                "current_repo_role": "historical_default_view",
                "included_in_live_tier3_headline": False,
                "latest_reference_date": "2024-12-31",
                "latest_value_millions": 6.9,
                "binding_blocker": "none_within_current_policy_window",
                "interpretation": "Historical overlay interpretation.",
            },
            {
                "boundary_key": "row_mrv_primary_nondefault_pilot",
                "current_repo_role": "leading_recurring_row_pilot",
                "included_in_live_tier3_headline": False,
                "latest_reference_date": "2025-12-31",
                "latest_value_millions": 0.6,
                "binding_blocker": "evidence_boundary",
                "interpretation": "MRV interpretation.",
            },
        ]
    )

    frame = build_downstream_problem_variable_review(
        fiscal_source_quality=quality,
        downstream_estimator_gap_review=gap,
        fiscal_receipt_boundary_review=boundary,
    )

    keys = set(frame["variable_key"])
    assert "tier2_row_coupon_correction" in keys
    assert "bank_live_default_receipt_cell" in keys
    assert "bank_receipt_historical_overlay_candidate" in keys
    assert "row_mrv_primary_nondefault_pilot" in keys

    row_coupon = frame.loc[frame["variable_key"].eq("tier2_row_coupon_correction")].iloc[0]
    assert row_coupon["evidence_grade"] == "medium"
    assert "latest_live_base_to_tier2_bank_only" in row_coupon["dominant_in_gap_keys"]

    bank_live = frame.loc[frame["variable_key"].eq("bank_live_default_receipt_cell")].iloc[0]
    assert bool(bank_live["included_in_live_headline"]) is True
    assert bank_live["binding_boundary"] == "stale_share_rule"

    perimeter = frame.loc[frame["variable_key"].eq("np_credit_unions_tsy_tx")].iloc[0]
    assert perimeter["latest_reference_date"].date().isoformat() == "2025-12-31"
    assert perimeter["latest_value_millions"] == 218.0
    assert "latest_live_bank_to_broad_depository_tier3" in perimeter["dominant_in_gap_keys"]
