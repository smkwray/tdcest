from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.row_receipt_family_review import (
    build_row_receipt_family_review,
    render_row_receipt_family_review_markdown,
    write_row_receipt_family_review,
)


def _sample_candidates() -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {
                "date": "2025-09-30",
                "counterparty_group": "row",
                "candidate_family": "row_mrv_cbsp_primary",
                "receipt_line_item_nm": "Consular and Border Security Programs, Machine Readable Visa Fee, State",
                "receipt_amt_mil": 2487.431,
            },
            {
                "date": "2025-09-30",
                "counterparty_group": "row",
                "candidate_family": "row_dhs_immigration_family_mixed",
                "receipt_line_item_nm": "Immigration Examinations Fee Account, Homeland Security",
                "receipt_amt_mil": 7498.102,
            },
            {
                "date": "2025-09-30",
                "counterparty_group": "row",
                "candidate_family": "row_fms_deposit_trust_family",
                "receipt_line_item_nm": "Deposits, Advances, Foreign Military Sales, Executive",
                "receipt_amt_mil": 64039.317,
            },
            {
                "date": "2025-09-30",
                "counterparty_group": "row",
                "candidate_family": "row_dhs_traveler_family",
                "receipt_line_item_nm": "International Registered Traveler Program Fund, U.S. Customs and Border Protection, Homeland Security",
                "receipt_amt_mil": 380.196,
            },
            {
                "date": "2025-09-30",
                "counterparty_group": "row",
                "candidate_family": "row_foreign_title_bridge",
                "receipt_line_item_nm": "Interest on Quota in International Monetary Fund (Article V, Section 9), Treasury",
                "receipt_amt_mil": 852.408,
            },
        ]
    )
    df["date"] = pd.to_datetime(df["date"])
    return df


def _sample_crosswalk() -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {
                "date": "2025-09-30",
                "candidate_family": "row_mrv_cbsp_primary",
                "receipt_line_item_nm": "Consular and Border Security Programs, Machine Readable Visa Fee, State",
                "combined_statement_match_level": "main_account_rollup",
            },
            {
                "date": "2025-09-30",
                "candidate_family": "row_dhs_immigration_family_mixed",
                "receipt_line_item_nm": "Immigration Examinations Fee Account, Homeland Security",
                "combined_statement_match_level": "main_account_rollup",
            },
            {
                "date": "2025-09-30",
                "candidate_family": "row_fms_deposit_trust_family",
                "receipt_line_item_nm": "Deposits, Advances, Foreign Military Sales, Executive",
                "combined_statement_match_level": "main_account_rollup",
            },
            {
                "date": "2025-09-30",
                "candidate_family": "row_dhs_traveler_family",
                "receipt_line_item_nm": "International Registered Traveler Program Fund, U.S. Customs and Border Protection, Homeland Security",
                "combined_statement_match_level": "main_account_rollup",
            },
        ]
    )
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_build_row_receipt_family_review_distinguishes_confirmed_contaminated_and_partial_families() -> None:
    review = build_row_receipt_family_review(
        receipt_account_candidates=_sample_candidates(),
        receipt_account_crosswalk=_sample_crosswalk(),
    )

    mrv = review.loc[review["candidate_family"].eq("row_mrv_cbsp_primary")].iloc[0]
    immigration = review.loc[review["candidate_family"].eq("row_dhs_immigration_family_mixed")].iloc[0]
    fms = review.loc[review["candidate_family"].eq("row_fms_deposit_trust_family")].iloc[0]
    traveler = review.loc[review["candidate_family"].eq("row_dhs_traveler_family")].iloc[0]
    foreign_title = review.loc[review["candidate_family"].eq("row_foreign_title_bridge")].iloc[0]

    assert mrv["combined_statement_confirmation"] == "full_main_account_rollup"
    assert mrv["review_decision"] == "keep_as_primary_row_pilot_nondefault"
    assert immigration["review_decision"] == "confirmed_account_family_but_keep_contaminated_nondefault"
    assert fms["review_decision"] == "confirmed_deposit_trust_nondefault"
    assert traveler["review_decision"] == "confirmed_traveler_family_but_not_cash_payer"
    assert foreign_title["combined_statement_confirmation"] == "unmatched"
    assert foreign_title["review_decision"] == "title_only_bridge_nondefault"


def test_write_row_receipt_family_review_outputs(tmp_path: Path) -> None:
    csv_path = tmp_path / "row_family_review.csv"
    markdown_path = tmp_path / "row_family_review.md"

    _, _, review = write_row_receipt_family_review(
        csv_path=csv_path,
        markdown_path=markdown_path,
        receipt_account_candidates=_sample_candidates(),
        receipt_account_crosswalk=_sample_crosswalk(),
    )

    assert csv_path.exists()
    assert markdown_path.exists()
    assert len(pd.read_csv(csv_path)) == len(review)
    markdown = render_row_receipt_family_review_markdown(review)
    assert "ROW Receipt Family Review" in markdown
    assert "Families with at least partial Combined Statement confirmation" in markdown
    assert "deposit/trust" in markdown.lower()
