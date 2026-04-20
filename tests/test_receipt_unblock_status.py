from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.receipt_unblock_status import (
    build_receipt_unblock_status,
    render_receipt_unblock_status_markdown,
    write_receipt_unblock_status,
)


def _sample_bank_historical() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "quarter_end": "2024-12-31",
                "share_age_eligible_for_default": True,
                "age_eligible_default_candidate_mil": 6948.526,
                "promotion_readiness_label": "historical_default_candidate_under_current_policy",
            },
            {
                "quarter_end": "2026-03-31",
                "share_age_eligible_for_default": False,
                "depository_plus_bhc_bridge_mil": 3032.789,
                "stale_share_years": 4,
                "promotion_readiness_label": "bridge_only_share_too_stale",
            },
        ]
    )


def _sample_receipt_review() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "candidate_name": "row_state_mrv_cbsp_bridge",
                "latest_reference_date": "2025-09-30",
                "latest_value_millions": 578.399,
                "promotion_status": "future_row_mrv_default_pilot_under_review",
                "review_note": "MRV primary review note",
            },
            {
                "candidate_name": "row_secondary_state_visa_branch",
                "latest_reference_date": "2025-09-30",
                "latest_value_millions": 16.845,
                "promotion_status": "keep_secondary_visa_nondefault",
                "review_note": "secondary review note",
            },
        ]
    )


def _sample_mrv_stop_gate() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "check_name": "overall_stop_decision",
                "row_type": "summary",
                "status": "stop_at_mrv_nondefault_pilot",
                "blocking_issue_type": "evidence_boundary",
                "metric_value": "complete=3;partial_default_blockers=1;missing_required_checks=2",
                "details": "Blocking source families: cash_treatment_and_retention;legal_remitter_or_debited_account_proof;observed_quarterly_cash_timing_or_remittance_schedule",
            }
        ]
    )


def test_build_receipt_unblock_status_splits_bank_and_row_branches() -> None:
    status = build_receipt_unblock_status(
        bank_receipt_historical_promotion=_sample_bank_historical(),
        bank_receipt_default_readiness=pd.DataFrame(),
        bank_receipt_source_map=pd.DataFrame(
            [{"source_family_key": "fresher_public_irs_bank_minor_shares"}]
        ),
        bank_receipt_stop_gate=pd.DataFrame(
            [
                {
                    "check_name": "overall_stop_decision",
                    "row_type": "summary",
                    "status": "historical_default_only_current_nondefault",
                }
            ]
        ),
        row_mrv_promotion_checklist=pd.DataFrame(),
        row_mrv_source_map=pd.DataFrame(),
        row_mrv_stop_gate=_sample_mrv_stop_gate(),
        receipt_promotion_review=_sample_receipt_review(),
    )

    bank_hist = status.loc[status["branch_key"].eq("bank_table51_historical_window")].iloc[0]
    bank_current = status.loc[status["branch_key"].eq("bank_table51_current_window")].iloc[0]
    row_mrv = status.loc[status["branch_key"].eq("row_mrv_cbsp_primary")].iloc[0]

    assert bank_hist["current_repo_role"] == "historical_default_view"
    assert bank_current["binding_blocker"] == "stale_share_rule"
    assert bank_current["promotion_boundary"] == "historical_default_only_current_nondefault"
    assert row_mrv["promotion_boundary"] == "stop_at_mrv_nondefault_pilot"
    assert str(pd.Timestamp(row_mrv["latest_relevant_date"]).date()) == "2025-09-30"


def test_write_receipt_unblock_status_outputs(tmp_path: Path) -> None:
    csv_path = tmp_path / "receipt_unblock_status.csv"
    markdown_path = tmp_path / "receipt_unblock_status.md"

    _, _, status = write_receipt_unblock_status(
        csv_path=csv_path,
        markdown_path=markdown_path,
        bank_receipt_historical_promotion=_sample_bank_historical(),
        bank_receipt_default_readiness=pd.DataFrame(),
        bank_receipt_source_map=pd.DataFrame(
            [{"source_family_key": "fresher_public_irs_bank_minor_shares"}]
        ),
        bank_receipt_stop_gate=pd.DataFrame(
            [
                {
                    "check_name": "overall_stop_decision",
                    "row_type": "summary",
                    "status": "historical_default_only_current_nondefault",
                }
            ]
        ),
        row_mrv_promotion_checklist=pd.DataFrame(),
        row_mrv_source_map=pd.DataFrame(),
        row_mrv_stop_gate=_sample_mrv_stop_gate(),
        receipt_promotion_review=_sample_receipt_review(),
    )

    assert csv_path.exists()
    assert markdown_path.exists()
    assert len(pd.read_csv(csv_path)) == len(status)
    markdown = render_receipt_unblock_status_markdown(status)
    assert "Receipt Unblock Status" in markdown
    assert "bank_table51_current_window" in markdown
