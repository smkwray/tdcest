from __future__ import annotations

import pandas as pd

from tdc_estimator.downstream_ingest_manifest import build_downstream_ingest_manifest


def test_downstream_ingest_manifest_prioritizes_handoff_and_core_contracts() -> None:
    contract = pd.DataFrame(
        [
            {
                "artifact_key": "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
                "latest_reference_date": "2025-12-31",
                "latest_value_millions": -40.0,
            }
        ]
    )
    use_cases = pd.DataFrame(
        [
            {
                "use_case_key": "current_quarter_bank_only_headline",
                "primary_latest_reference_date": "2025-12-31",
                "binding_boundary": "bank_live_default_receipt_cell=stale_share_rule; row_live_default_receipt_cell=evidence_boundary",
            },
            {
                "use_case_key": "historical_bank_receipt_backtest",
                "primary_latest_reference_date": "2024-12-31",
                "binding_boundary": "none_within_current_policy_window",
            },
            {
                "use_case_key": "current_row_receipt_sensitivity",
                "binding_boundary": "evidence_boundary",
            },
            {
                "use_case_key": "deposit_perimeter_comparison",
            },
            {
                "use_case_key": "monetary_crosscheck_and_problem_variable_audit",
            },
        ]
    )
    problems = pd.DataFrame(
        [
            {"variable_key": "tier2_row_coupon_correction", "latest_value_millions": -70.0},
        ]
    )
    receipt_boundary = pd.DataFrame(
        [
            {"boundary_key": "bank_live_default_receipt_cell"},
        ]
    )
    goals = pd.DataFrame(
        [
            {"goal_key": "bank_receipts", "binding_blocker": "stale_share_rule"},
            {"goal_key": "row_receipts", "binding_blocker": "evidence_boundary"},
            {"goal_key": "fiscal_flow_tdc_equation", "binding_blocker": "receipt_cells_still_partial", "latest_relevant_date": "2025-12-31"},
        ]
    )
    unblock = pd.DataFrame(
        [
            {"branch_key": "bank_table51_current_window", "binding_blocker": "stale_share_rule", "latest_relevant_date": "2026-03-31"},
            {"branch_key": "row_mrv_cbsp_primary", "binding_blocker": "evidence_boundary"},
        ]
    )
    series_panel = pd.DataFrame(
        [
            {"date": "2025-12-31", "series_key": "tdc_tier3_fiscal_corrected_bank_only_ru_flow"},
        ]
    )
    comparison_panel = pd.DataFrame(
        [
            {"date": "2025-12-31", "comparison_key": "bank_only_tier3_partial_shell_minus_tier2"},
        ]
    )

    frame = build_downstream_ingest_manifest(
        downstream_estimator_contract=contract,
        downstream_deposit_effect_use_case_review=use_cases,
        downstream_problem_variable_review=problems,
        fiscal_receipt_boundary_review=receipt_boundary,
        project_goal_status_review=goals,
        receipt_unblock_status=unblock,
        downstream_deposit_effect_series_panel=series_panel,
        downstream_deposit_effect_comparison_panel=comparison_panel,
    )

    assert frame.iloc[0]["artifact_key"] == "tdc_downstream_handoff_bundle"
    assert frame.iloc[0]["ingest_priority"] == 1

    contract_row = frame.loc[frame["artifact_key"].eq("tdc_downstream_estimator_contract")].iloc[0]
    assert contract_row["stability_class"] == "primary_contract"

    handoff_row = frame.loc[frame["artifact_key"].eq("tdc_downstream_handoff_bundle")].iloc[0]
    assert handoff_row["artifact_format"] == "json"

    series_row = frame.loc[frame["artifact_key"].eq("tdc_downstream_deposit_effect_series_panel")].iloc[0]
    assert series_row["consumption_mode"] == "ingest_after_contract"

    closeout_row = frame.loc[frame["artifact_key"].eq("tdc_backend_closeout_review")].iloc[0]
    assert closeout_row["stability_class"] == "closeout_context"

    contribution_row = frame.loc[frame["artifact_key"].eq("tdc_downstream_component_contribution_review")].iloc[0]
    assert "signed_contribution_millions" in contribution_row["core_fields"]

    research_row = frame.loc[frame["artifact_key"].eq("tdc_tier3_research_comparison")].iloc[0]
    assert "tier3_bank_only_mil" in research_row["core_fields"]
    assert "current_row_mrv_pilot_latest_date" in research_row["core_fields"]

    workstream_row = frame.loc[frame["artifact_key"].eq("tdc_workstream_end_state_map")].iloc[0]
    assert workstream_row["core_fields"] == "current_state;end_state_target;binding_blocker;next_finite_push"
