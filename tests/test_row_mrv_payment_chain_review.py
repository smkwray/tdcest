from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.row_mrv_payment_chain_review import (
    build_row_mrv_payment_chain_review,
    render_row_mrv_payment_chain_review_markdown,
    write_row_mrv_payment_chain_review,
)


def test_build_row_mrv_payment_chain_review_confirms_account_family_but_fails_remitter_proof() -> None:
    crosswalk = pd.DataFrame(
        [
            {
                "date": "2025-09-30",
                "candidate_family": "row_mrv_cbsp_primary",
                "account_code": "19-X-5713-5",
                "combined_statement_match_level": "main_account_rollup",
            }
        ]
    )
    crosswalk["date"] = pd.to_datetime(crosswalk["date"])
    pilot = pd.DataFrame(
        [
            {
                "date": "2025-09-30",
                "pilot_bucket": "mrv_cbsp_primary_candidate",
                "receipt_line_item_nm": "Consular and Border Security Programs, Machine Readable Visa Fee, State",
            }
        ]
    )
    pilot["date"] = pd.to_datetime(pilot["date"])
    timing = pd.DataFrame(
        {"row_state_visa_allocated_receipt_mil": [100.0]},
        index=pd.to_datetime(["2025-09-30"]),
    )

    review = build_row_mrv_payment_chain_review(
        receipt_account_crosswalk=crosswalk,
        row_visa_consular_pilot=pilot,
        row_state_visa_timing_sensitivity=timing,
    )

    cbsp = review.loc[review["check_name"].eq("cbsp_account_family_confirmation")].iloc[0]
    remitter = review.loc[review["check_name"].eq("legal_remitter_or_debited_account_proof")].iloc[0]
    exclusion = review.loc[review["check_name"].eq("iv_aos_domestic_bank_contamination_exclusion")].iloc[0]
    assert cbsp["status"] == "pass"
    assert remitter["status"] == "fail"
    assert exclusion["status"] == "pass"
    assert review["overall_recommendation"].iloc[0] == "not_yet_promotable"


def test_write_row_mrv_payment_chain_review_outputs(tmp_path: Path) -> None:
    csv_path = tmp_path / "payment_chain.csv"
    markdown_path = tmp_path / "payment_chain.md"
    crosswalk = pd.DataFrame(
        [
            {
                "date": "2025-09-30",
                "candidate_family": "row_mrv_cbsp_primary",
                "account_code": "19-X-5713-5",
                "combined_statement_match_level": "main_account_rollup",
            }
        ]
    )
    crosswalk["date"] = pd.to_datetime(crosswalk["date"])
    pilot = pd.DataFrame(
        [
            {
                "date": "2025-09-30",
                "pilot_bucket": "mrv_cbsp_primary_candidate",
                "receipt_line_item_nm": "Consular and Border Security Programs, Machine Readable Visa Fee, State",
            }
        ]
    )
    pilot["date"] = pd.to_datetime(pilot["date"])
    timing = pd.DataFrame(
        {"row_state_visa_allocated_receipt_mil": [100.0]},
        index=pd.to_datetime(["2025-09-30"]),
    )

    _, _, review = write_row_mrv_payment_chain_review(
        csv_path=csv_path,
        markdown_path=markdown_path,
        receipt_account_crosswalk=crosswalk,
        row_visa_consular_pilot=pilot,
        row_state_visa_timing_sensitivity=timing,
    )

    assert csv_path.exists()
    assert markdown_path.exists()
    assert len(pd.read_csv(csv_path)) == len(review)
    markdown = render_row_mrv_payment_chain_review_markdown(review)
    assert "ROW MRV Payment Chain Review" in markdown
    assert "legal-remitter" in markdown.lower()
