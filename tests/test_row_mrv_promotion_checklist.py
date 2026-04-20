from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.row_mrv_promotion_checklist import (
    build_row_mrv_promotion_checklist,
    render_row_mrv_promotion_checklist_markdown,
    write_row_mrv_promotion_checklist,
)


def _sample_readiness() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "check_name": "treasury_account_mapping",
                "status": "pass",
                "metric_value": "19-X-5713-5 / main_account_rollup",
            },
            {
                "check_name": "cash_treatment",
                "status": "warn",
                "metric_value": "B_cbsp_receipt_account_public_annual",
            },
            {
                "check_name": "annual_reconciliation",
                "status": "pass",
                "metric_value": "candidate=2,487.431 pilot=2,487.431 timing=2,487.431",
            },
        ]
    )


def _sample_payment_chain() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "check_name": "treasury_annual_receipt_line",
                "status": "pass",
                "metric_value": "Consular and Border Security Programs, Machine Readable Visa Fee, State / 19-X-5713-5",
            },
            {
                "check_name": "mrv_fee_applicant_link",
                "status": "pass",
            },
            {
                "check_name": "mrv_retained_fee_account_authority",
                "status": "pass",
            },
            {
                "check_name": "cbsp_standalone_account_evidence",
                "status": "pass",
            },
            {
                "check_name": "iv_aos_domestic_bank_contamination_exclusion",
                "status": "pass",
            },
            {
                "check_name": "legal_remitter_or_debited_account_proof",
                "status": "fail",
                "metric_name": "blocking_condition",
                "metric_value": "no_public_legal_remitter_or_debited_account_proof_for_mrv",
            },
            {
                "check_name": "observed_quarterly_cash_timing",
                "status": "fail",
                "metric_name": "timing_basis",
                "metric_value": "monthly_niv_issuance_share_proxy",
            },
        ]
    )


def _sample_recurring() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "branch_name": "mrv_cbsp_primary",
                "promotion_status": "future_row_mrv_default_pilot_under_review",
            },
            {
                "branch_name": "secondary_state_visa",
                "promotion_status": "keep_secondary_visa_nondefault",
            },
        ]
    )


def test_build_row_mrv_promotion_checklist_identifies_partial_and_missing_checks() -> None:
    checklist = build_row_mrv_promotion_checklist(
        row_mrv_default_readiness=_sample_readiness(),
        row_mrv_payment_chain_review=_sample_payment_chain(),
        row_recurring_pilot_review=_sample_recurring(),
    )

    account = checklist.loc[checklist["check_name"].eq("treasury_receipt_account_identification")].iloc[0]
    cash = checklist.loc[checklist["check_name"].eq("cash_treatment_and_retained_account")].iloc[0]
    remitter = checklist.loc[checklist["check_name"].eq("legal_remitter_or_debited_account")].iloc[0]
    timing = checklist.loc[checklist["check_name"].eq("observed_quarterly_cash_timing")].iloc[0]

    assert account["status"] == "complete"
    assert cash["status"] == "partial"
    assert remitter["status"] == "missing"
    assert timing["status"] == "missing"
    assert checklist["overall_recommendation"].iloc[0] == "not_yet_promotable"


def test_write_row_mrv_promotion_checklist_outputs(tmp_path: Path) -> None:
    csv_path = tmp_path / "row_mrv_promotion_checklist.csv"
    markdown_path = tmp_path / "row_mrv_promotion_checklist.md"

    _, _, checklist = write_row_mrv_promotion_checklist(
        csv_path=csv_path,
        markdown_path=markdown_path,
        row_mrv_default_readiness=_sample_readiness(),
        row_mrv_payment_chain_review=_sample_payment_chain(),
        row_recurring_pilot_review=_sample_recurring(),
    )

    assert csv_path.exists()
    assert markdown_path.exists()
    assert len(pd.read_csv(csv_path)) == len(checklist)
    markdown = render_row_mrv_promotion_checklist_markdown(checklist)
    assert "ROW MRV Promotion Checklist" in markdown
    assert "partial" in markdown
    assert "missing" in markdown
