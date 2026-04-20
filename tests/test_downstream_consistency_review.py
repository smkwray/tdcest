from __future__ import annotations

import pandas as pd

from tdc_estimator.downstream_consistency_review import build_downstream_consistency_review


def test_downstream_consistency_review_passes_when_contract_and_panels_align() -> None:
    bundle = {
        "summary": {
            "current_bank_headline_latest_date": "2025-12-31",
            "current_bank_headline_latest_value_millions": -40.0,
            "historical_bank_overlay_latest_date": "2024-12-31",
            "historical_bank_overlay_latest_value_millions": 103.0,
            "row_mrv_latest_date": "2025-09-30",
            "row_mrv_latest_value_millions": 0.6,
        },
        "goal_status": {},
        "receipt_unblock_status": {},
        "estimator_contract": {},
        "use_cases": {},
        "receipt_boundaries": {},
        "problem_variables": {},
        "series_panel": {},
        "comparison_panel": {},
    }
    manifest = pd.DataFrame(
        [
            {
                "artifact_key": "tdc_downstream_handoff_bundle",
                "ingest_priority": 1,
                "core_fields": "summary;goal_status;receipt_unblock_status;estimator_contract;use_cases;receipt_boundaries;problem_variables;series_panel;comparison_panel",
            },
            {
                "artifact_key": "tdc_downstream_estimator_contract",
                "ingest_priority": 2,
                "core_fields": "artifact_key;latest_reference_date;latest_value_millions",
            },
            {
                "artifact_key": "tdc_downstream_component_contribution_review",
                "ingest_priority": 9,
                "core_fields": "scenario_key;signed_contribution_millions;estimator_value_millions",
            },
            {
                "artifact_key": "tdc_tier3_research_comparison",
                "ingest_priority": 13,
                "core_fields": "comparison_key;reference_date;tier2_bank_only_mil;tier3_bank_only_mil;historical_bank_receipt_variant_mil;current_row_mrv_pilot_latest_date",
            },
            {
                "artifact_key": "tdc_workstream_end_state_map",
                "ingest_priority": 14,
                "core_fields": "workstream_key;current_state;end_state_target;binding_blocker;next_finite_push",
            },
        ]
    )
    contract = pd.DataFrame(
        [
            {
                "artifact_key": "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
                "latest_reference_date": "2025-12-31",
                "latest_value_millions": -40.0,
            },
            {
                "artifact_key": "tdc_tier2_interest_corrected_bank_only_ru_flow",
                "latest_reference_date": "2025-12-31",
                "latest_value_millions": -38.0,
            },
            {
                "artifact_key": "bank_receipt_historical_default_view",
                "latest_reference_date": "2024-12-31",
                "latest_value_millions": 103.0,
            },
            {
                "artifact_key": "row_mrv_primary_nondefault_pilot",
                "latest_reference_date": "2025-09-30",
                "latest_value_millions": 0.6,
            },
            {
                "artifact_key": "tdc_bea_row_receipts_benchmark",
                "latest_reference_date": "2025-12-31",
                "latest_value_millions": 11.0,
            },
        ]
    )
    use_cases = pd.DataFrame(
        [
            {
                "use_case_key": "current_quarter_bank_only_headline",
                "primary_artifact_key": "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
                "comparison_artifact_key": "tdc_tier2_interest_corrected_bank_only_ru_flow",
            },
            {
                "use_case_key": "current_row_receipt_sensitivity",
                "primary_artifact_key": "row_mrv_primary_nondefault_pilot",
                "comparison_artifact_key": "tdc_bea_row_receipts_benchmark",
            },
        ]
    )
    series_panel = pd.DataFrame(
        [
            {
                "date": "2025-12-31",
                "series_key": "row_mrv_primary_nondefault_pilot_series",
                "latest_nonzero_date": "2025-09-30",
                "latest_nonzero_value_millions": 0.6,
            }
        ]
    )
    comparison_panel = pd.DataFrame(
        [
            {
                "date": "2025-12-31",
                "comparison_key": "row_mrv_nondefault_pilot_minus_live_zero",
                "latest_nonzero_date": "2025-09-30",
                "latest_nonzero_value_millions": 0.6,
                "lhs_value_millions": 0.0,
                "rhs_value_millions": 0.0,
                "net_delta_millions": 0.0,
            },
            {
                "date": "2025-12-31",
                "comparison_key": "bank_only_tier2_minus_base",
                "lhs_value_millions": -38.0,
                "rhs_value_millions": -40.0,
                "net_delta_millions": 2.0,
            },
            {
                "date": "2025-12-31",
                "comparison_key": "bank_only_tier3_minus_tier2",
                "lhs_value_millions": -40.0,
                "rhs_value_millions": -38.0,
                "net_delta_millions": -2.0,
            },
            {
                "date": "2025-12-31",
                "comparison_key": "broad_depository_tier3_minus_bank_only_tier3",
                "lhs_value_millions": -39.8,
                "rhs_value_millions": -40.0,
                "net_delta_millions": 0.2,
            },
            {
                "date": "2024-12-31",
                "comparison_key": "historical_bank_receipt_candidate_minus_default_tier3",
                "lhs_value_millions": 103.0,
                "rhs_value_millions": 100.0,
                "net_delta_millions": 3.0,
            },
            {
                "date": "2024-12-31",
                "comparison_key": "historical_bank_receipt_candidate_minus_lower_bound",
                "lhs_value_millions": 103.0,
                "rhs_value_millions": 101.5,
                "net_delta_millions": 1.5,
            }
        ]
    )
    gap_review = pd.DataFrame(
        [
            {
                "gap_key": "latest_live_base_to_tier2_bank_only",
                "reference_date": "2025-12-31",
                "lhs_value_millions": -38.0,
                "rhs_value_millions": -40.0,
                "net_delta_millions": 2.0,
                "dominant_component_key": "tier2_row_coupon_correction",
                "dominant_component_millions": -2.0,
            },
            {
                "gap_key": "latest_live_tier2_to_tier3_bank_only",
                "reference_date": "2025-12-31",
                "lhs_value_millions": -40.0,
                "rhs_value_millions": -38.0,
                "net_delta_millions": -2.0,
                "dominant_component_key": "tier3_row_noninterest_outlay_correction",
                "dominant_component_millions": -2.0,
            },
            {
                "gap_key": "latest_live_bank_to_broad_depository_tier3",
                "reference_date": "2025-12-31",
                "lhs_value_millions": -39.8,
                "rhs_value_millions": -40.0,
                "net_delta_millions": 0.2,
                "dominant_component_key": "np_credit_unions_tsy_tx",
                "dominant_component_millions": 0.2,
            },
            {
                "gap_key": "latest_historical_bank_receipt_overlay",
                "reference_date": "2024-12-31",
                "lhs_value_millions": 103.0,
                "rhs_value_millions": 100.0,
                "net_delta_millions": 3.0,
                "dominant_component_key": "bank_receipt_historical_default_candidate_delta_mil",
                "dominant_component_millions": 3.0,
            },
            {
                "gap_key": "latest_historical_candidate_to_lower_bound",
                "reference_date": "2024-12-31",
                "lhs_value_millions": 103.0,
                "rhs_value_millions": 101.5,
                "net_delta_millions": 1.5,
                "dominant_component_key": "bank_receipt_historical_default_candidate_delta_mil",
                "dominant_component_millions": 3.0,
            },
        ]
    )
    contribution_review = pd.DataFrame(
        [
            {
                "scenario_key": "latest_live_bank_tier3_default",
                "signed_contribution_millions": -30.0,
                "estimator_value_millions": -40.0,
            },
            {
                "scenario_key": "latest_live_bank_tier3_default",
                "signed_contribution_millions": -10.0,
                "estimator_value_millions": -40.0,
            },
        ]
    )
    problem_review = pd.DataFrame(
        [
            {
                "variable_key": "np_credit_unions_tsy_tx",
                "latest_reference_date": "2025-12-31",
                "latest_value_millions": 0.2,
                "dominant_in_gap_keys": "latest_live_bank_to_broad_depository_tier3",
            }
        ]
    )
    research_comparison = pd.DataFrame(
        [
            {
                "comparison_key": "latest_live_defaults",
                "reference_date": "2025-12-31",
                "tier2_bank_only_mil": -38.0,
                "tier3_bank_only_mil": -40.0,
                "historical_bank_receipt_variant_mil": pd.NA,
                "current_row_mrv_pilot_latest_date": "2025-09-30",
            },
            {
                "comparison_key": "latest_historical_bank_window",
                "reference_date": "2024-12-31",
                "tier2_bank_only_mil": 100.0,
                "tier3_bank_only_mil": 100.0,
                "historical_bank_receipt_variant_mil": 103.0,
                "current_row_mrv_pilot_latest_date": "2025-09-30",
            },
        ]
    )
    workstreams = pd.DataFrame(
        [
            {
                "workstream_key": "row_mrv_primary_pilot",
                "current_state": "bounded",
                "end_state_target": "stable_nondefault",
                "binding_blocker": "evidence_boundary",
                "next_finite_push": "keep bounded",
            }
        ]
    )

    frame = build_downstream_consistency_review(
        downstream_handoff_bundle=bundle,
        downstream_ingest_manifest=manifest,
        downstream_estimator_contract=contract,
        downstream_deposit_effect_use_case_review=use_cases,
        downstream_deposit_effect_series_panel=series_panel,
        downstream_deposit_effect_comparison_panel=comparison_panel,
        downstream_estimator_gap_review=gap_review,
        downstream_component_contribution_review=contribution_review,
        downstream_problem_variable_review=problem_review,
        tier3_research_comparison=research_comparison,
        workstream_end_state_map=workstreams,
    )

    assert not frame.empty
    assert set(frame["status"]) == {"pass"}
