from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.row_mrv_default_readiness import (
    build_row_mrv_default_readiness,
    render_row_mrv_default_readiness_markdown,
    write_row_mrv_default_readiness,
)


def test_build_row_mrv_default_readiness_flags_debited_account_and_timing_blockers() -> None:
    candidates = pd.DataFrame(
        [
            {
                "date": "2025-09-30",
                "candidate_family": "row_mrv_cbsp_primary",
                "receipt_line_item_nm": "Consular and Border Security Programs, Machine Readable Visa Fee, State",
                "receipt_amt_mil": 2487.431,
                "payer_identity_subgrade": "row_applicant_fee_link",
                "default_blocker": "needs_cash_payer_and_debited_account_evidence",
                "aid_cd": "19",
                "a_cd": "X",
                "main_cd": "5713",
                "sub_cd": "5",
            }
        ]
    )
    candidates["date"] = pd.to_datetime(candidates["date"])
    pilot = pd.DataFrame(
        [
            {
                "date": "2025-09-30",
                "pilot_bucket": "mrv_cbsp_primary_candidate",
                "receipt_line_item_nm": "Consular and Border Security Programs, Machine Readable Visa Fee, State",
                "receipt_amt_mil": 2487.431,
                "cash_treatment_grade": "B_cbsp_receipt_account_public_annual",
                "timing_grade": "C_requires_monthly_niv_timing_proxy",
            }
        ]
    )
    pilot["date"] = pd.to_datetime(pilot["date"])
    timing = pd.DataFrame(
        {
            "row_state_visa_allocated_receipt_mil": [500.0, 600.0, 700.0, 687.431],
            "state_mrv_cbsp_primary_annual_mil": [2487.431, 2487.431, 2487.431, 2487.431],
            "timing_grade": ["C_niv_issuance_share_not_observed_cash_date"] * 4,
        },
        index=pd.to_datetime(["2024-12-31", "2025-03-31", "2025-06-30", "2025-09-30"]),
    )
    crosswalk = pd.DataFrame(
        [
            {
                "date": "2025-09-30",
                "candidate_family": "row_mrv_cbsp_primary",
                "combined_statement_title": "Consular and Border Security Programs, Administration of Foreign Affairs, State",
                "combined_statement_match_level": "main_account_rollup",
            }
        ]
    )
    crosswalk["date"] = pd.to_datetime(crosswalk["date"])

    readiness = build_row_mrv_default_readiness(
        receipt_account_candidates=candidates,
        receipt_account_crosswalk=crosswalk,
        row_visa_consular_pilot=pilot,
        row_state_visa_timing_sensitivity=timing,
    )

    mapping = readiness.loc[readiness["check_name"].eq("treasury_account_mapping")].iloc[0]
    debited = readiness.loc[readiness["check_name"].eq("debited_account_or_legal_remitter")].iloc[0]
    timing_row = readiness.loc[readiness["check_name"].eq("quarterly_timing")].iloc[0]
    recon = readiness.loc[readiness["check_name"].eq("annual_reconciliation")].iloc[0]
    assert mapping["status"] == "pass"
    assert "main_account_rollup" in str(mapping["metric_value"])
    assert debited["status"] == "fail"
    assert timing_row["status"] == "warn"
    assert recon["status"] == "pass"
    assert readiness["overall_recommendation"].iloc[0] == "not_yet_promotable"


def test_write_row_mrv_default_readiness_outputs(tmp_path: Path) -> None:
    csv_path = tmp_path / "row_mrv_readiness.csv"
    markdown_path = tmp_path / "row_mrv_readiness.md"

    candidates = pd.DataFrame(
        [
            {
                "date": "2025-09-30",
                "candidate_family": "row_mrv_cbsp_primary",
                "receipt_line_item_nm": "Consular and Border Security Programs, Machine Readable Visa Fee, State",
                "receipt_amt_mil": 100.0,
                "payer_identity_subgrade": "row_applicant_fee_link",
                "default_blocker": "needs_cash_payer_and_debited_account_evidence",
                "aid_cd": "19",
                "a_cd": "X",
                "main_cd": "5713",
                "sub_cd": "5",
            }
        ]
    )
    candidates["date"] = pd.to_datetime(candidates["date"])
    pilot = pd.DataFrame(
        [
            {
                "date": "2025-09-30",
                "pilot_bucket": "mrv_cbsp_primary_candidate",
                "receipt_line_item_nm": "Consular and Border Security Programs, Machine Readable Visa Fee, State",
                "receipt_amt_mil": 100.0,
                "cash_treatment_grade": "B_cbsp_receipt_account_public_annual",
                "timing_grade": "C_requires_monthly_niv_timing_proxy",
            }
        ]
    )
    pilot["date"] = pd.to_datetime(pilot["date"])
    timing = pd.DataFrame(
        {
            "row_state_visa_allocated_receipt_mil": [100.0],
            "state_mrv_cbsp_primary_annual_mil": [100.0],
            "timing_grade": ["C_niv_issuance_share_not_observed_cash_date"],
        },
        index=pd.to_datetime(["2025-09-30"]),
    )
    crosswalk = pd.DataFrame(
        [
            {
                "date": "2025-09-30",
                "candidate_family": "row_mrv_cbsp_primary",
                "combined_statement_title": "Consular and Border Security Programs, Administration of Foreign Affairs, State",
                "combined_statement_match_level": "main_account_rollup",
            }
        ]
    )
    crosswalk["date"] = pd.to_datetime(crosswalk["date"])

    _, _, readiness = write_row_mrv_default_readiness(
        csv_path=csv_path,
        markdown_path=markdown_path,
        receipt_account_candidates=candidates,
        receipt_account_crosswalk=crosswalk,
        row_visa_consular_pilot=pilot,
        row_state_visa_timing_sensitivity=timing,
    )

    assert csv_path.exists()
    assert markdown_path.exists()
    assert len(pd.read_csv(csv_path)) == len(readiness)
    markdown = render_row_mrv_default_readiness_markdown(readiness)
    assert "ROW MRV Default Readiness" in markdown
    assert "debited-account" in markdown
