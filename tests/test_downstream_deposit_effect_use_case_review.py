from __future__ import annotations

import pandas as pd

from tdc_estimator.downstream_deposit_effect_use_case_review import (
    build_downstream_deposit_effect_use_case_review,
)


def test_downstream_deposit_effect_use_case_review_maps_core_questions() -> None:
    contract = pd.DataFrame(
        [
            {
                "artifact_key": "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
                "default_classification": "live_default_with_partial_receipt_cells",
                "latest_reference_date": "2025-12-31",
                "latest_value_millions": 40.0,
            },
            {
                "artifact_key": "tdc_tier2_interest_corrected_bank_only_ru_flow",
                "latest_reference_date": "2025-12-31",
                "latest_value_millions": 42.0,
            },
            {
                "artifact_key": "bank_receipt_historical_default_view",
                "default_classification": "historical_default_only",
                "latest_reference_date": "2024-12-31",
                "latest_value_millions": 107.0,
            },
            {
                "artifact_key": "row_mrv_primary_nondefault_pilot",
                "default_classification": "nondefault_pilot",
                "latest_reference_date": "2025-12-31",
                "latest_value_millions": 0.6,
            },
            {
                "artifact_key": "tdc_bea_row_receipts_benchmark",
                "default_classification": "benchmark_only",
                "latest_reference_date": "2025-12-31",
                "latest_value_millions": 11.0,
            },
            {
                "artifact_key": "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow",
                "default_classification": "broad_depository_default",
                "latest_reference_date": "2025-12-31",
                "latest_value_millions": 41.0,
            },
            {
                "artifact_key": "monetary_depository_crosscheck",
                "default_classification": "diagnostic_primary",
                "latest_reference_date": "2025-12-31",
                "latest_value_millions": 10.0,
            },
            {
                "artifact_key": "monetary_bank_target_stress_test",
                "default_classification": "diagnostic_secondary",
                "latest_reference_date": "2025-12-31",
                "latest_value_millions": 20.0,
            },
        ]
    )
    gap = pd.DataFrame(
        [
            {
                "gap_key": "latest_live_tier2_to_tier3_bank_only",
                "dominant_component_key": "tier3_row_noninterest_outlay_correction",
                "dominant_component_family": "fiscal",
            },
            {
                "gap_key": "latest_historical_bank_receipt_overlay",
                "dominant_component_key": "bank_receipt_historical_default_candidate_delta_mil",
                "dominant_component_family": "historical_receipt_overlay",
            },
            {
                "gap_key": "latest_live_bank_to_broad_depository_tier3",
                "dominant_component_key": "ncua_capitalization_deposit_tx",
                "dominant_component_family": "deposit_perimeter",
            },
            {
                "gap_key": "latest_live_base_to_tier2_bank_only",
                "dominant_component_key": "tier2_row_coupon_correction",
                "dominant_component_family": "coupon",
            },
        ]
    )
    receipt = pd.DataFrame(
        [
            {
                "boundary_key": "bank_live_default_receipt_cell",
                "binding_blocker": "stale_share_rule",
            },
            {
                "boundary_key": "row_live_default_receipt_cell",
                "binding_blocker": "evidence_boundary",
            },
            {
                "boundary_key": "bank_receipt_historical_overlay_candidate",
                "binding_blocker": "none_within_current_policy_window",
                "interpretation": "Historical overlay interpretation.",
            },
            {
                "boundary_key": "row_mrv_primary_nondefault_pilot",
                "binding_blocker": "evidence_boundary",
                "interpretation": "MRV interpretation.",
            },
        ]
    )
    goals = pd.DataFrame(
        [
            {
                "goal_key": "fiscal_flow_tdc_equation",
                "summary_note": "Fiscal shell note.",
            },
            {
                "goal_key": "monetary_disaggregated_tdc_equation",
                "binding_blocker": "stop_at_perimeter_stress_test",
                "summary_note": "Monetary note.",
            },
        ]
    )

    frame = build_downstream_deposit_effect_use_case_review(
        downstream_estimator_contract=contract,
        downstream_estimator_gap_review=gap,
        fiscal_receipt_boundary_review=receipt,
        project_goal_status_review=goals,
    )

    keys = set(frame["use_case_key"])
    assert "current_quarter_bank_only_headline" in keys
    assert "historical_bank_receipt_backtest" in keys
    assert "current_row_receipt_sensitivity" in keys
    assert "deposit_perimeter_comparison" in keys
    assert "monetary_crosscheck_and_problem_variable_audit" in keys

    live = frame.loc[frame["use_case_key"].eq("current_quarter_bank_only_headline")].iloc[0]
    assert live["dominant_problem_variable_family"] == "fiscal"
    assert "stale_share_rule" in live["binding_boundary"]

    hist = frame.loc[frame["use_case_key"].eq("historical_bank_receipt_backtest")].iloc[0]
    assert hist["readiness_status"] == "high_inside_age_eligible_window"

    row = frame.loc[frame["use_case_key"].eq("current_row_receipt_sensitivity")].iloc[0]
    assert row["comparison_artifact_key"] == "tdc_bea_row_receipts_benchmark"
