from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.receipt_promotion_review import (
    build_receipt_promotion_review,
    render_receipt_promotion_review_markdown,
    write_receipt_promotion_review,
)


def test_build_receipt_promotion_review_identifies_bank_bridge_as_best_default_candidate() -> None:
    review = build_receipt_promotion_review(
        bank_corp_tax_receipts_bridge=pd.DataFrame(
            {
                "bank_corp_tax_receipts_gross_depository_plus_bhc_mil": [12.0],
                "bank_corp_tax_receipts_gross_strict_depository_mil": [4.0],
                "bank_corp_tax_receipts_gross_finance_share_mil": [30.0],
                "share_age_eligible_for_default": [True],
            },
            index=pd.to_datetime(["2025-12-31"]),
        ),
        bea_row_receipts_benchmark=pd.DataFrame(
            {"bea_row_current_receipts_total_q_mil": [10.0]},
            index=pd.to_datetime(["2025-12-31"]),
        ),
        tier3_receipt_source_diagnostics=pd.DataFrame(
            {"rcm_bank_channel_total_candidate": [100.0]},
            index=pd.to_datetime(["2025-12-31"]),
        ),
        row_state_visa_timing_sensitivity=pd.DataFrame(
            {
                "row_state_visa_allocated_receipt_mil": [5.0],
                "row_state_visa_secondary_allocated_receipt_mil": [1.0],
            },
            index=pd.to_datetime(["2025-12-31"]),
        ),
        row_receipt_family_review=pd.DataFrame(
            [
                {
                    "date": "2025-09-30",
                    "candidate_family": "row_dhs_immigration_family_mixed",
                    "family_total_receipt_mil": 8522.332,
                    "combined_statement_confirmed_share_pct": 100.0,
                },
                {
                    "date": "2025-09-30",
                    "candidate_family": "row_fms_deposit_trust_family",
                    "family_total_receipt_mil": 64039.317,
                    "combined_statement_confirmed_receipt_mil": 64039.317,
                    "combined_statement_confirmation": "partial_main_account_rollup",
                    "review_decision": "confirmed_deposit_trust_nondefault",
                },
            ]
        ),
        row_recurring_pilot_review=pd.DataFrame(
            [
                {
                    "date": "2025-09-30",
                    "branch_name": "secondary_state_visa",
                    "latest_quarter_amount_mil": 1.0,
                    "review_note": "Secondary recurring State-visa branch kept nondefault.",
                }
            ]
        ),
        row_mrv_promotion_checklist=pd.DataFrame(
            [
                {"check_name": "a", "required_for_default": True, "status": "complete", "blocks_default": False},
                {"check_name": "b", "required_for_default": True, "status": "complete", "blocks_default": False},
                {"check_name": "c", "required_for_default": True, "status": "complete", "blocks_default": False},
                {"check_name": "d", "required_for_default": True, "status": "partial", "blocks_default": True},
                {"check_name": "e", "required_for_default": True, "status": "missing", "blocks_default": True},
                {"check_name": "f", "required_for_default": True, "status": "missing", "blocks_default": True},
            ]
        ),
        row_mrv_stop_gate=pd.DataFrame(
            [
                {
                    "check_name": "overall_stop_decision",
                    "row_type": "summary",
                    "status": "stop_at_mrv_nondefault_pilot",
                }
            ]
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
        receipt_account_crosswalk=pd.DataFrame(
            [
                {
                    "date": "2025-09-30",
                    "candidate_family": "row_mrv_cbsp_primary",
                    "combined_statement_match_level": "main_account_rollup",
                }
            ]
        ),
    )

    bank_bridge = review.loc[review["candidate_name"].eq("bank_corporate_tax_bridge_depository_plus_bhc")].iloc[0]
    assert bank_bridge["promotion_status"] == "best_bank_default_candidate_under_review"
    assert "Stop gate: historical_default_only_current_nondefault." in bank_bridge["review_note"]

    rcm = review.loc[review["candidate_name"].eq("revenue_collections_bank_channel")].iloc[0]
    assert rcm["promotion_status"] == "rejected_default"
    row_bridge = review.loc[review["candidate_name"].eq("row_state_mrv_cbsp_bridge")].iloc[0]
    assert row_bridge["promotion_status"] == "future_row_mrv_default_pilot_under_review"
    assert "Combined Statement now confirms the broader CBSP main-account family" in row_bridge["review_note"]
    assert "Promotion checklist: 3 complete, 1 partial default blocker, 2 missing required checks." in row_bridge["review_note"]
    assert "Stop gate: stop_at_mrv_nondefault_pilot." in row_bridge["review_note"]
    secondary_branch = review.loc[review["candidate_name"].eq("row_secondary_state_visa_branch")].iloc[0]
    assert secondary_branch["promotion_status"] == "keep_secondary_visa_nondefault"
    dsh = review.loc[review["candidate_name"].eq("row_dhs_immigration_family_mixed")].iloc[0]
    assert dsh["promotion_status"] == "confirmed_contaminated_nondefault"


def test_build_receipt_promotion_review_flags_stale_bank_bridge() -> None:
    review = build_receipt_promotion_review(
        bank_corp_tax_receipts_bridge=pd.DataFrame(
            {
                "bank_corp_tax_receipts_gross_depository_plus_bhc_mil": [12.0],
                "bank_corp_tax_receipts_gross_strict_depository_mil": [4.0],
                "bank_corp_tax_receipts_gross_finance_share_mil": [30.0],
                "share_age_eligible_for_default": [False],
            },
            index=pd.to_datetime(["2026-03-31"]),
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
    )

    bank_bridge = review.loc[review["candidate_name"].eq("bank_corporate_tax_bridge_depository_plus_bhc")].iloc[0]
    assert bank_bridge["promotion_status"] == "best_bank_default_candidate_under_review_but_share_too_stale"


def test_write_receipt_promotion_review_outputs_files(tmp_path: Path) -> None:
    csv_path = tmp_path / "review.csv"
    md_path = tmp_path / "review.md"

    _, _, review = write_receipt_promotion_review(
        csv_path=csv_path,
        markdown_path=md_path,
        receipt_account_candidates=pd.DataFrame(
            [
                {
                    "date": "2025-09-30",
                    "receipt_line_item_nm": "Deposits, Advances, Foreign Military Sales, Executive",
                    "receipt_amt_mil": 100.0,
                }
            ]
        ),
        row_receipt_family_review=pd.DataFrame(
            [
                {
                    "date": "2025-09-30",
                    "candidate_family": "row_fms_deposit_trust_family",
                    "combined_statement_confirmed_receipt_mil": 100.0,
                    "combined_statement_confirmation": "partial_main_account_rollup",
                    "review_decision": "confirmed_deposit_trust_nondefault",
                }
            ]
        ),
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(review)
    markdown = render_receipt_promotion_review_markdown(review)
    assert "Receipt Promotion Review" in markdown
