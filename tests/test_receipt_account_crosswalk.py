from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.receipt_account_crosswalk import (
    build_receipt_account_crosswalk,
    render_receipt_account_crosswalk_markdown,
    write_receipt_account_crosswalk,
)


def _sample_candidates() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2025-09-30",
                "fiscal_year": 2025,
                "counterparty_group": "row",
                "receipt_line_item_nm": "Consular and Border Security Programs, Machine Readable Visa Fee, State",
                "receipt_amt_mil": 2487.431,
                "aid_cd": "19",
                "a_cd": "X",
                "main_cd": "5713",
                "sub_cd": "5",
                "candidate_family": "row_mrv_cbsp_primary",
                "promotion_priority": "high_priority_sensitivity",
                "default_blocker": "needs_cash_payer_and_debited_account_evidence",
                "budget_treatment_guess": "no_year_receipt_account_review",
            },
            {
                "date": "2025-09-30",
                "fiscal_year": 2025,
                "counterparty_group": "bank",
                "receipt_line_item_nm": "Fines, Penalties, and Forfeitures, Not Otherwise Classified, Office of the Comptroller of Currency, Treasury",
                "receipt_amt_mil": 450.488,
                "aid_cd": "20",
                "a_cd": "",
                "main_cd": "1099",
                "sub_cd": "71",
                "candidate_family": "bank_regulatory_specific_occ",
                "promotion_priority": "high_priority_sensitivity",
                "default_blocker": "annual_account_title_only_not_quarterly_cash_counterparty",
                "budget_treatment_guess": "general_fund_fine_penalty_receipt",
            },
        ]
    ).assign(date=lambda df: pd.to_datetime(df["date"]))


def test_build_receipt_account_crosswalk_without_combined_statement_marks_backbone_only() -> None:
    crosswalk = build_receipt_account_crosswalk(_sample_candidates())

    assert (crosswalk["source_coverage_status"] == "receipts_by_department_only").all()
    assert (crosswalk["match_status"] == "no_combined_statement_support_loaded").all()
    assert "row_mrv_cbsp_primary" in set(crosswalk["candidate_family"])


def test_build_receipt_account_crosswalk_matches_combined_statement_support(tmp_path: Path) -> None:
    support_path = tmp_path / "support__combined_statement_receipt_accounts.csv"
    pd.DataFrame(
        [
            {
                "fiscal_year": 2025,
                "aid_cd": "019",
                "a_cd": "X",
                "main_cd": "5713",
                "sub_cd": "005",
                "combined_statement_title": "Consular and Border Security Programs, Machine Readable Visa Fee, State",
                "combined_statement_amt_mil": 2487.431,
            },
            {
                "fiscal_year": 2025,
                "aid_cd": "20",
                "a_cd": "",
                "main_cd": "1099",
                "sub_cd": "71",
                "combined_statement_title": "OCC Fines, Penalties, and Forfeitures",
                "combined_statement_amt_mil": 450.488,
            },
        ]
    ).to_csv(support_path, index=False)

    crosswalk = build_receipt_account_crosswalk(
        _sample_candidates(),
        combined_statement_accounts_path=support_path,
    )

    mrv = crosswalk.loc[crosswalk["candidate_family"].eq("row_mrv_cbsp_primary")].iloc[0]
    occ = crosswalk.loc[crosswalk["candidate_family"].eq("bank_regulatory_specific_occ")].iloc[0]
    assert mrv["match_status"] == "exact_code_exact_title_match"
    assert mrv["amount_alignment_status"] == "exact_or_near_exact_alignment"
    assert occ["match_status"] == "exact_code_title_mismatch"
    assert occ["source_coverage_status"] == "receipts_by_department_plus_combined_statement"
    assert occ["combined_statement_match_level"] == "exact_account"


def test_write_receipt_account_crosswalk_outputs_files(tmp_path: Path) -> None:
    csv_path = tmp_path / "crosswalk.csv"
    markdown_path = tmp_path / "crosswalk.md"

    _, _, crosswalk = write_receipt_account_crosswalk(
        csv_path=csv_path,
        markdown_path=markdown_path,
        receipt_account_candidates=_sample_candidates(),
    )

    assert csv_path.exists()
    assert markdown_path.exists()
    assert len(pd.read_csv(csv_path)) == len(crosswalk)
    markdown = render_receipt_account_crosswalk_markdown(crosswalk)
    assert "Receipt Account Crosswalk" in markdown
    assert "receipts_by_department_only" in markdown


def test_build_receipt_account_crosswalk_marks_main_account_rollup_matches(tmp_path: Path) -> None:
    support_path = tmp_path / "support__combined_statement_receipt_accounts.csv"
    pd.DataFrame(
        [
            {
                "fiscal_year": 2025,
                "aid_cd": "019",
                "a_cd": "",
                "main_cd": "5713",
                "sub_cd": "000",
                "combined_statement_title": "Consular and Border Security Programs, Administration of Foreign Affairs, State",
                "combined_statement_amt_mil": 5840.035,
                "combined_statement_metric_basis": "appropriations_and_transfers_mil",
                "combined_statement_match_scope": "main_account_rollup",
            }
        ]
    ).to_csv(support_path, index=False)

    crosswalk = build_receipt_account_crosswalk(
        _sample_candidates().loc[lambda df: df["candidate_family"].eq("row_mrv_cbsp_primary")],
        combined_statement_accounts_path=support_path,
    )

    row = crosswalk.iloc[0]
    assert row["combined_statement_match_level"] == "main_account_rollup"
    assert row["match_status"] == "main_account_rollup_match"
    assert row["amount_alignment_status"] == "aggregate_context_not_receipt_comparable"
