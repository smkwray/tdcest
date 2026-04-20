from __future__ import annotations

import pandas as pd

from tdc_estimator.backend_closeout_review import build_backend_closeout_review


def test_backend_closeout_review_summarizes_bounded_backend_state() -> None:
    goals = pd.DataFrame(
        [
            {
                "goal_key": "fiscal_flow_tdc_equation",
                "current_status": "diagnostic_shell_live_not_full_receipt_solved",
                "latest_relevant_date": "2025-12-31",
                "strongest_live_surface": "Fiscal reconciliation shell",
                "binding_blocker": "receipt_cells_still_partial",
                "summary_note": "Fiscal shell note.",
            },
            {
                "goal_key": "monetary_disaggregated_tdc_equation",
                "current_status": "diagnostic_system_live_depository_target_preferred",
                "latest_relevant_date": "2025-12-31",
                "binding_blocker": "stop_at_perimeter_stress_test",
                "summary_note": "Monetary note.",
            },
        ]
    )
    receipt = pd.DataFrame(
        [
            {
                "branch_key": "bank_table51_historical_window",
                "promotion_boundary": "historical_default_only_current_nondefault",
                "latest_relevant_date": "2024-12-31",
                "summary_note": "Historical bank note.",
            },
            {
                "branch_key": "bank_table51_current_window",
                "binding_blocker": "stale_share_rule",
            },
            {
                "branch_key": "row_mrv_cbsp_primary",
                "promotion_boundary": "stop_at_mrv_nondefault_pilot",
                "latest_relevant_date": "2025-09-30",
                "binding_blocker": "evidence_boundary",
                "summary_note": "MRV note.",
            },
        ]
    )
    consistency = pd.DataFrame(
        [
            {"check_key": "one", "status": "pass"},
            {"check_key": "two", "status": "pass"},
        ]
    )
    workstreams = pd.DataFrame(
        [
            {"workstream_key": "bank_receipt_historical_window", "next_finite_push": "Push historical bank."},
            {"workstream_key": "row_mrv_primary_pilot", "next_finite_push": "Push MRV carefully."},
            {"workstream_key": "fiscal_reconciliation_shell", "next_finite_push": "Keep shell aligned."},
            {"workstream_key": "monetary_branch", "next_finite_push": "Keep as cross-check."},
        ]
    )

    frame = build_backend_closeout_review(
        project_goal_status_review=goals,
        receipt_unblock_status=receipt,
        downstream_consistency_review=consistency,
        workstream_end_state_map=workstreams,
    )

    keys = set(frame["review_key"])
    assert "downstream_contract_layer" in keys
    assert "bank_receipt_branch" in keys
    assert "row_mrv_branch" in keys
    assert "fiscal_shell" in keys
    assert "monetary_crosscheck" in keys

    contract = frame.loc[frame["review_key"].eq("downstream_contract_layer")].iloc[0]
    assert contract["release_readiness"] == "closeout_ready"

    bank = frame.loc[frame["review_key"].eq("bank_receipt_branch")].iloc[0]
    assert bank["binding_boundary"] == "stale_share_rule"

    row = frame.loc[frame["review_key"].eq("row_mrv_branch")].iloc[0]
    assert row["latest_reference_date"] == "2025-09-30"
