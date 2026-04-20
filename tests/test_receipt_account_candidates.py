from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.receipt_account_candidates import (
    build_receipt_account_candidates,
    render_receipt_account_candidates_markdown,
    write_receipt_account_candidates,
)


def test_build_receipt_account_candidates_classifies_bank_and_row_lines(tmp_path: Path):
    raw_path = tmp_path / "treasury__receipts_by_department.csv"
    pd.DataFrame(
        [
            ["2025-09-30", "Consular and Border Security Programs, Machine Readable Visa Fee, State", "019", "X", "5713", "005", 2_487_431_164.11, 2025],
            ["2025-09-30", "Consular and Border Security Programs, Machine Readable Visa Fee, State", "019", "X", "5713", "005", 2_487_431_164.11, 2025],
            ["2025-09-30", "Consular and Border Security Programs, Passport Security Surcharge, State", "019", "X", "5713", "003", 1_783_122_827.71, 2025],
            ["2025-09-30", "Consular and Border Security Programs, Immigrant Visa Security Surcharge, State", "019", "X", "5713", "006", 55_192_433.40, 2025],
            ["2025-09-30", "Immigration Examinations Fee Account", "070", "X", "5094", "000", 7_498_102_183.00, 2025],
            ["2025-09-30", "International Registered Traveler Program Fund, U.S. Customs and Border Protection, Homeland Security", "070", "X", "5543", "001", 380_196_013.32, 2025],
            ["2025-09-30", "Fines, Penalties, and Forfeitures, Not Otherwise Classified, Office of the Comptroller of Currency, Treasury", "020", "null", "1099", "071", 450_488_475.01, 2025],
            ["2025-09-30", "Fees and Assessments, Financial Research Fund, Departmental Offices, Treasury", "020", "X", "5590", "001", 103_282_141.00, 2025],
            ["2025-09-30", "Federal Deposit Insurance Corporation, Resolution Activity", "051", "X", "5094", "010", 153_186_000.00, 2025],
            ["2025-09-30", "Random Unmatched Receipt", "001", "null", "0000", "000", 123.0, 2025],
        ],
        columns=["record_date", "receipt_line_item_nm", "aid_cd", "a_cd", "main_cd", "sub_cd", "receipt_amt", "record_fiscal_year"],
    ).to_csv(raw_path, index=False)

    candidates = build_receipt_account_candidates(raw_path, start_fiscal_year=2022)

    assert set(candidates["counterparty_group"]) == {"bank", "row"}
    assert "Random Unmatched Receipt" not in set(candidates["receipt_line_item_nm"])

    visa = candidates.loc[candidates["receipt_line_item_nm"].str.contains("Machine Readable Visa Fee", na=False)].iloc[0]
    assert visa["counterparty_group"] == "row"
    assert visa["payer_grade"] == "B_narrow_foreign_fee_candidate"
    assert visa["recommended_role"] == "future_row_pilot"
    assert visa["availability_type_class"] == "no_year_account"
    assert visa["fastbook_fund_group_proxy"] == "special_or_trust_like_no_year"
    assert pd.isna(visa["fastbook_general_major_class_code"])
    assert visa["budget_treatment_guess"] == "no_year_receipt_account_review"
    assert visa["candidate_family"] == "row_mrv_cbsp_primary"
    assert visa["promotion_priority"] == "high_priority_sensitivity"
    assert visa["payer_identity_subgrade"] == "row_applicant_fee_link"
    assert visa["default_blocker"] == "needs_cash_payer_and_debited_account_evidence"
    assert not bool(visa["default_eligible"])
    assert round(float(visa["receipt_amt_mil"]), 6) == 2_487.431164

    passport = candidates.loc[candidates["receipt_line_item_nm"].str.contains("Passport Security Surcharge", na=False)].iloc[0]
    assert passport["recommended_role"] == "reject_default_mixed_domestic"
    assert passport["candidate_family"] == "row_passport_domestic_contamination"
    assert passport["promotion_priority"] == "low_priority_contaminated"
    assert passport["default_blocker"] == "domestic_contamination_risk"

    iv = candidates.loc[candidates["receipt_line_item_nm"].str.contains("Immigrant Visa Security Surcharge", na=False)].iloc[0]
    assert iv["candidate_family"] == "row_secondary_visa_sensitivity"
    assert iv["promotion_priority"] == "medium_priority_sensitivity"
    assert iv["payer_identity_subgrade"] == "row_secondary_visa_fee_link"
    assert iv["default_blocker"] == "secondary_visa_line_not_primary_recurring_row_candidate"

    immigration = candidates.loc[candidates["receipt_line_item_nm"].str.contains("Immigration Examinations Fee Account", na=False)].iloc[0]
    assert immigration["candidate_family"] == "row_dhs_immigration_family_mixed"
    assert immigration["promotion_priority"] == "low_priority_contaminated"
    assert immigration["payer_identity_subgrade"] == "row_dhs_fee_family_with_domestic_contamination"
    assert immigration["default_blocker"] == "dhs_fee_family_with_domestic_contamination_risk"

    traveler = candidates.loc[candidates["receipt_line_item_nm"].str.contains("International Registered Traveler", na=False)].iloc[0]
    assert traveler["candidate_family"] == "row_dhs_traveler_family"
    assert traveler["promotion_priority"] == "medium_priority_sensitivity"
    assert traveler["payer_identity_subgrade"] == "traveler_program_foreign_link_not_actual_cash_payer"
    assert traveler["default_blocker"] == "traveler_program_title_without_actual_cash_payer_proof"

    occ = candidates.loc[candidates["receipt_line_item_nm"].str.contains("Comptroller of Currency", na=False)].iloc[0]
    assert occ["counterparty_group"] == "bank"
    assert occ["recommended_role"] == "bank_nontax_sensitivity"
    assert occ["a_cd"] == ""
    assert occ["availability_type_class"] == "blank_or_unavailable_receipt"
    assert occ["fastbook_fund_group_proxy"] == "general_fund_misc_receipt"
    assert int(occ["fastbook_general_major_class_code"]) == 1000
    assert occ["fastbook_general_major_class_label"] == "fines_penalties_and_forfeitures"
    assert occ["budget_treatment_guess"] == "general_fund_fine_penalty_receipt"
    assert occ["candidate_family"] == "bank_regulatory_specific_occ"
    assert occ["promotion_priority"] == "high_priority_sensitivity"
    assert occ["payer_identity_subgrade"] == "bank_regulator_specific_depository_link"
    assert occ["default_blocker"] == "annual_account_title_only_not_quarterly_cash_counterparty"

    ofr = candidates.loc[candidates["receipt_line_item_nm"].str.contains("Financial Research Fund", na=False)].iloc[0]
    assert ofr["payer_grade"] == "C_large_bhc_specific"
    assert ofr["availability_type_class"] == "no_year_account"
    assert ofr["candidate_family"] == "bank_large_bhc_specific_ofr"
    assert ofr["promotion_priority"] == "medium_priority_sensitivity"
    assert ofr["payer_identity_subgrade"] == "large_bhc_assessment_link"
    assert ofr["default_blocker"] == "large_bhc_specific_not_broad_bank_coverage"

    fdic = candidates.loc[candidates["receipt_line_item_nm"].str.contains("Federal Deposit Insurance Corporation", na=False)].iloc[0]
    assert fdic["candidate_family"] == "bank_regulatory_mixed_fdic"
    assert fdic["promotion_priority"] == "medium_priority_sensitivity"
    assert fdic["payer_identity_subgrade"] == "bank_regulatory_or_resolution_mixed"
    assert fdic["default_blocker"] == "annual_account_title_only_not_quarterly_cash_counterparty"


def test_write_receipt_account_candidates_carries_fastbook_overlay_for_deposit_trust_lines(tmp_path: Path):
    raw_path = tmp_path / "treasury__receipts_by_department.csv"
    csv_path = tmp_path / "tdc_receipt_account_candidates.csv"
    md_path = tmp_path / "tdc_receipt_account_candidates.md"

    pd.DataFrame(
        [
            ["2025-09-30", "Deposits, Advances, Foreign Military Sales, Executive", "011", "X", "8242", "001", 64_039_317_029.54, 2025],
        ],
        columns=["record_date", "receipt_line_item_nm", "aid_cd", "a_cd", "main_cd", "sub_cd", "receipt_amt", "record_fiscal_year"],
    ).to_csv(raw_path, index=False)

    _, _, candidates = write_receipt_account_candidates(
        receipts_by_department_path=raw_path,
        csv_path=csv_path,
        markdown_path=md_path,
        start_fiscal_year=2022,
    )

    row = candidates.iloc[0]
    assert row["fastbook_fund_group_proxy"] == "deposit_or_advance_no_year"
    assert row["budget_treatment_guess"] == "deposit_or_trust_nondefault"
    assert row["candidate_family"] == "row_fms_deposit_trust_family"
    assert row["promotion_priority"] == "conceptual_nondefault"
    assert row["payer_identity_subgrade"] == "foreign_program_counterparty_but_not_current_receipt"
    assert row["default_blocker"] == "deposit_or_trust_concept_not_current_receipt"
    assert row["source_basis"] == "annual_account_symbol_dollars_plus_fastbook_overlay"


def test_write_receipt_account_candidates_outputs_csv_and_markdown(tmp_path: Path):
    raw_path = tmp_path / "treasury__receipts_by_department.csv"
    csv_path = tmp_path / "tdc_receipt_account_candidates.csv"
    md_path = tmp_path / "tdc_receipt_account_candidates.md"

    pd.DataFrame(
        [
            ["2025-09-30", "Deposits, Advances, Foreign Military Sales, Executive", "011", "X", "8242", "001", 64_039_317_029.54, 2025],
            ["2025-09-30", "Consular and Border Security Programs, Immigrant Visa Security Surcharge, State", "019", "X", "5713", "006", 55_192_433.40, 2025],
        ],
        columns=["record_date", "receipt_line_item_nm", "aid_cd", "a_cd", "main_cd", "sub_cd", "receipt_amt", "record_fiscal_year"],
    ).to_csv(raw_path, index=False)

    _, _, candidates = write_receipt_account_candidates(
        receipts_by_department_path=raw_path,
        csv_path=csv_path,
        markdown_path=md_path,
        start_fiscal_year=2022,
    )

    assert csv_path.exists()
    assert md_path.exists()
    written = pd.read_csv(csv_path)
    assert len(written) == len(candidates)
    markdown = render_receipt_account_candidates_markdown(candidates)
    assert "Receipt Account Candidate Bridge" in markdown
    assert "future_row_pilot" in markdown
    assert "separate_row_deposit_trust_sensitivity" in markdown
    assert "FAST Book / CARS overlay" in markdown
