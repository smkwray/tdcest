from __future__ import annotations

import pandas as pd

from tdc_estimator.downstream_handoff_bundle import build_downstream_handoff_bundle


def test_downstream_handoff_bundle_keys_core_backend_surfaces() -> None:
    goals = pd.DataFrame(
        [
            {"goal_key": "bank_receipts", "current_status": "historical_default_only_current_nondefault"},
            {"goal_key": "row_receipts", "current_status": "stop_at_mrv_nondefault_pilot"},
            {"goal_key": "fiscal_flow_tdc_equation", "current_status": "diagnostic_shell_live_not_full_receipt_solved"},
            {"goal_key": "monetary_disaggregated_tdc_equation", "current_status": "diagnostic_system_live_depository_target_preferred"},
        ]
    )
    receipt = pd.DataFrame(
        [
            {"branch_key": "bank_table51_current_window", "promotion_boundary": "historical_default_only_current_nondefault"},
            {"branch_key": "row_mrv_cbsp_primary", "promotion_boundary": "stop_at_mrv_nondefault_pilot"},
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
                "artifact_key": "bank_receipt_historical_default_view",
                "latest_reference_date": "2024-12-31",
                "latest_value_millions": 103.0,
            },
            {
                "artifact_key": "row_mrv_primary_nondefault_pilot",
                "latest_reference_date": "2025-09-30",
                "latest_value_millions": 0.6,
            },
        ]
    )
    use_cases = pd.DataFrame(
        [{"use_case_key": "current_quarter_bank_only_headline", "target_question": "Best current-quarter bank-only TDC?"}]
    )
    problem_variables = pd.DataFrame(
        [
            {"variable_key": "tier2_row_coupon_correction", "latest_value_millions": -70.0},
            {"variable_key": "row_live_default_receipt_cell", "latest_value_millions": 0.0},
        ]
    )
    receipt_boundaries = pd.DataFrame(
        [{"boundary_key": "row_live_default_receipt_cell", "binding_blocker": "evidence_boundary"}]
    )
    series_panel = pd.DataFrame(
        [
            {
                "date": "2025-12-31",
                "series_key": "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
                "historical_only": False,
                "nondefault_only": False,
            },
            {
                "date": "2025-12-31",
                "series_key": "row_mrv_primary_nondefault_pilot_series",
                "historical_only": False,
                "nondefault_only": True,
                "latest_nonzero_date": "2025-09-30",
                "latest_nonzero_value_millions": 0.6,
            },
        ]
    )
    comparison_panel = pd.DataFrame(
        [
            {
                "date": "2025-12-31",
                "comparison_key": "bank_only_tier3_partial_shell_minus_tier2",
                "historical_only": False,
                "nondefault_only": False,
            },
            {
                "date": "2025-12-31",
                "comparison_key": "row_mrv_nondefault_pilot_minus_live_zero",
                "historical_only": False,
                "nondefault_only": True,
                "latest_nonzero_date": "2025-09-30",
                "latest_nonzero_value_millions": 0.6,
            },
        ]
    )

    bundle = build_downstream_handoff_bundle(
        project_goal_status_review=goals,
        receipt_unblock_status=receipt,
        downstream_estimator_contract=contract,
        downstream_deposit_effect_use_case_review=use_cases,
        downstream_problem_variable_review=problem_variables,
        fiscal_receipt_boundary_review=receipt_boundaries,
        downstream_deposit_effect_series_panel=series_panel,
        downstream_deposit_effect_comparison_panel=comparison_panel,
    )

    assert bundle["bundle_format"] == "tdc_downstream_handoff_v1"
    assert bundle["distribution_scope"]["full_repo_regeneration_required"] is True
    assert bundle["distribution_scope"]["partial_pack_status"] == "snapshot_only_unless_explicitly_marked_full_repo"
    assert bundle["summary"]["bank_receipts_status"] == "historical_default_only_current_nondefault"
    assert "tdc_tier3_fiscal_corrected_bank_only_ru_flow" in bundle["estimator_contract"]
    assert "current_quarter_bank_only_headline" in bundle["use_cases"]
    assert "row_live_default_receipt_cell" in bundle["receipt_boundaries"]
    assert "backend_closeout_review" in bundle
    assert "backend_release_check" in bundle
    assert "row_mrv_primary_nondefault_pilot_series" in bundle["series_panel"]["latest_by_series_key"]
    assert "row_mrv_nondefault_pilot_minus_live_zero" in bundle["comparison_panel"]["latest_by_comparison_key"]
    assert bundle["summary"]["row_mrv_latest_date"] == "2025-09-30"
    assert isinstance(
        bundle["series_panel"]["latest_by_series_key"]["row_mrv_primary_nondefault_pilot_series"]["nondefault_only"],
        bool,
    )
    assert isinstance(
        bundle["comparison_panel"]["latest_by_comparison_key"]["row_mrv_nondefault_pilot_minus_live_zero"]["nondefault_only"],
        bool,
    )
