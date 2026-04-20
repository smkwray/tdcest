from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.project_goal_status_review import (
    build_project_goal_status_review,
    render_project_goal_status_review_markdown,
    write_project_goal_status_review,
)


def _sample_estimates() -> pd.DataFrame:
    idx = pd.to_datetime(["2025-12-31"])
    return pd.DataFrame(
        {
            "tdc_tier2_interest_corrected_bank_only_ru_flow": [1.0],
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [2.0],
        },
        index=idx,
    )


def _sample_corrections() -> pd.DataFrame:
    idx = pd.to_datetime(["2025-12-31"])
    return pd.DataFrame(
        {
            "tier2_bank_coupon_correction": [1.0],
            "tier2_row_coupon_correction": [1.0],
            "tier3_bank_noninterest_outlay_correction": [1.0],
            "tier3_row_noninterest_outlay_correction": [1.0],
        },
        index=idx,
    )


def _sample_receipt_unblock_status() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "branch_key": "bank_table51_historical_window",
                "binding_blocker": "none_within_current_policy_window",
                "summary_note": "Historical bank window usable.",
            },
            {
                "branch_key": "bank_table51_current_window",
                "latest_relevant_date": "2026-03-31",
                "binding_blocker": "stale_share_rule",
                "promotion_boundary": "historical_default_only_current_nondefault",
                "summary_note": "Current bank window stale.",
            },
            {
                "branch_key": "row_mrv_cbsp_primary",
                "latest_relevant_date": "2025-09-30",
                "binding_blocker": "evidence_boundary",
                "promotion_boundary": "stop_at_mrv_nondefault_pilot",
                "summary_note": "MRV pilot nondefault.",
            },
        ]
    )


def _sample_workstreams() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "workstream_key": "bank_receipt_historical_window",
                "next_finite_push": "Integrate historical bank window.",
            },
            {
                "workstream_key": "row_mrv_primary_pilot",
                "next_finite_push": "Tighten MRV payment chain.",
            },
            {
                "workstream_key": "fiscal_reconciliation_shell",
                "next_finite_push": "Keep fiscal shell coherent.",
            },
            {
                "workstream_key": "monetary_branch",
                "next_finite_push": "Keep depository target as main cross-check.",
            },
        ]
    )


def _sample_fiscal_source_quality() -> pd.DataFrame:
    return pd.DataFrame([{"reliability_grade": "A"}])


def _sample_monetary_pref() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "latest_quarter": "2025-12-31",
                "recommendation_status": "prefer_depository_target_crosscheck",
            }
        ]
    )


def _sample_monetary_stop() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "check_name": "overall_stop_decision",
                "status": "stop_at_perimeter_stress_test",
            }
        ]
    )


def test_build_project_goal_status_review_summarizes_core_goals() -> None:
    review = build_project_goal_status_review(
        estimates=_sample_estimates(),
        corrections=_sample_corrections(),
        receipt_unblock_status=_sample_receipt_unblock_status(),
        workstream_end_state_map=_sample_workstreams(),
        fiscal_source_quality=_sample_fiscal_source_quality(),
        monetary_target_preference_review=_sample_monetary_pref(),
        monetary_bank_liquid_stop_gate=_sample_monetary_stop(),
    )

    bank_receipts = review.loc[review["goal_key"].eq("bank_receipts")].iloc[0]
    row_receipts = review.loc[review["goal_key"].eq("row_receipts")].iloc[0]
    monetary = review.loc[review["goal_key"].eq("monetary_disaggregated_tdc_equation")].iloc[0]

    assert bank_receipts["current_status"] == "historical_default_only_current_nondefault"
    assert row_receipts["current_status"] == "stop_at_mrv_nondefault_pilot"
    assert str(pd.Timestamp(row_receipts["latest_relevant_date"]).date()) == "2025-09-30"
    assert monetary["current_status"] == "diagnostic_system_live_depository_target_preferred"


def test_write_project_goal_status_review_outputs(tmp_path: Path) -> None:
    csv_path = tmp_path / "project_goal_status_review.csv"
    markdown_path = tmp_path / "project_goal_status_review.md"

    _, _, review = write_project_goal_status_review(
        csv_path=csv_path,
        markdown_path=markdown_path,
        estimates=_sample_estimates(),
        corrections=_sample_corrections(),
        receipt_unblock_status=_sample_receipt_unblock_status(),
        workstream_end_state_map=_sample_workstreams(),
        fiscal_source_quality=_sample_fiscal_source_quality(),
        monetary_target_preference_review=_sample_monetary_pref(),
        monetary_bank_liquid_stop_gate=_sample_monetary_stop(),
    )

    assert csv_path.exists()
    assert markdown_path.exists()
    assert len(pd.read_csv(csv_path)) == len(review)
    markdown = render_project_goal_status_review_markdown(review)
    assert "Project Goal Status Review" in markdown
    assert "bank_receipts" in markdown
