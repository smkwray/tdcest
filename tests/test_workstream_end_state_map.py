from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.workstream_end_state_map import (
    build_workstream_end_state_map,
    render_workstream_end_state_map_markdown,
    write_workstream_end_state_map,
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
                "binding_blocker": "stale_share_rule",
                "missing_source_families": "fresher_public_irs_bank_minor_shares",
                "summary_note": "Current bank window stale.",
            },
            {
                "branch_key": "row_mrv_cbsp_primary",
                "binding_blocker": "evidence_boundary",
                "missing_source_families": "cash_treatment_and_retention;legal_remitter_or_debited_account_proof;observed_quarterly_cash_timing_or_remittance_schedule",
                "summary_note": "MRV pilot nondefault.",
            },
            {
                "branch_key": "row_secondary_state_visa",
                "promotion_boundary": "keep_secondary_visa_nondefault",
            },
        ]
    )


def _sample_bank_stop_gate() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "check_name": "overall_stop_decision",
                "status": "historical_default_only_current_nondefault",
            }
        ]
    )


def _sample_row_stop_gate() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "check_name": "overall_stop_decision",
                "status": "stop_at_mrv_nondefault_pilot",
            }
        ]
    )


def _sample_monetary_preference() -> pd.DataFrame:
    return pd.DataFrame([{"recommendation": "prefer_depository_target_crosscheck"}])


def _sample_monetary_stop_gate() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "check_name": "overall_stop_decision",
                "status": "stop_at_perimeter_stress_test",
            }
        ]
    )


def test_build_workstream_end_state_map_marks_freeze_branches() -> None:
    frame = build_workstream_end_state_map(
        receipt_unblock_status=_sample_receipt_unblock_status(),
        bank_receipt_stop_gate=_sample_bank_stop_gate(),
        row_mrv_stop_gate=_sample_row_stop_gate(),
        monetary_target_preference_review=_sample_monetary_preference(),
        monetary_bank_liquid_stop_gate=_sample_monetary_stop_gate(),
        fiscal_source_quality=pd.DataFrame(),
    )

    bank_hist = frame.loc[frame["workstream_key"].eq("bank_receipt_historical_window")].iloc[0]
    monetary = frame.loc[frame["workstream_key"].eq("monetary_branch")].iloc[0]
    row_secondary = frame.loc[frame["workstream_key"].eq("row_secondary_and_contaminated_families")].iloc[0]

    assert bank_hist["recommended_mode"] == "push_hard"
    assert bool(monetary["deprioritize_now"]) is True
    assert row_secondary["recommended_mode"] == "freeze"


def test_write_workstream_end_state_map_outputs(tmp_path: Path) -> None:
    csv_path = tmp_path / "workstream_end_state_map.csv"
    markdown_path = tmp_path / "workstream_end_state_map.md"

    _, _, frame = write_workstream_end_state_map(
        csv_path=csv_path,
        markdown_path=markdown_path,
        receipt_unblock_status=_sample_receipt_unblock_status(),
        bank_receipt_stop_gate=_sample_bank_stop_gate(),
        row_mrv_stop_gate=_sample_row_stop_gate(),
        monetary_target_preference_review=_sample_monetary_preference(),
        monetary_bank_liquid_stop_gate=_sample_monetary_stop_gate(),
        fiscal_source_quality=pd.DataFrame(),
    )

    assert csv_path.exists()
    assert markdown_path.exists()
    assert len(pd.read_csv(csv_path)) == len(frame)
    markdown = render_workstream_end_state_map_markdown(frame)
    assert "Workstream End-State Map" in markdown
    assert "Freeze Or Diagnostic-Only Branches" in markdown
