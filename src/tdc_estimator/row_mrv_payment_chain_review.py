from __future__ import annotations

from pathlib import Path

import pandas as pd


PAYMENT_CHAIN_COLUMNS = [
    "check_name",
    "status",
    "severity",
    "supports_default",
    "evidence_grade",
    "metric_name",
    "metric_value",
    "details",
    "source_label",
    "source_url",
    "overall_recommendation",
]


def build_row_mrv_payment_chain_review(
    *,
    receipt_account_crosswalk: pd.DataFrame | None,
    row_visa_consular_pilot: pd.DataFrame | None,
    row_state_visa_timing_sensitivity: pd.DataFrame | None,
) -> pd.DataFrame:
    mrv_crosswalk = pd.DataFrame()
    if receipt_account_crosswalk is not None and not receipt_account_crosswalk.empty:
        mrv_crosswalk = receipt_account_crosswalk.loc[
            receipt_account_crosswalk.get("candidate_family", pd.Series(dtype="object")).eq("row_mrv_cbsp_primary")
        ].copy()

    mrv_pilot = pd.DataFrame()
    if row_visa_consular_pilot is not None and not row_visa_consular_pilot.empty:
        mrv_pilot = row_visa_consular_pilot.loc[
            row_visa_consular_pilot.get("pilot_bucket", pd.Series(dtype="object")).eq("mrv_cbsp_primary_candidate")
        ].copy()

    timing = pd.DataFrame()
    if row_state_visa_timing_sensitivity is not None and not row_state_visa_timing_sensitivity.empty:
        timing = row_state_visa_timing_sensitivity.loc[
            pd.to_numeric(
                row_state_visa_timing_sensitivity.get("row_state_visa_allocated_receipt_mil", pd.Series(dtype="float64")),
                errors="coerce",
            ).fillna(0.0).ne(0.0)
        ].copy()

    if mrv_crosswalk.empty and mrv_pilot.empty and timing.empty:
        return pd.DataFrame(columns=PAYMENT_CHAIN_COLUMNS)

    latest_crosswalk = mrv_crosswalk.sort_values("date").iloc[-1] if not mrv_crosswalk.empty else pd.Series(dtype="object")
    latest_pilot = mrv_pilot.sort_values("date").iloc[-1] if not mrv_pilot.empty else pd.Series(dtype="object")
    latest_timing = timing.sort_index().iloc[-1] if not timing.empty else pd.Series(dtype="object")

    crosswalk_level = str(latest_crosswalk.get("combined_statement_match_level", "unmatched"))
    annual_account_code = (
        f"{latest_pilot.get('receipt_line_item_nm', 'n/a')} / "
        f"{latest_crosswalk.get('account_code', '19-X-5713-5') if not latest_crosswalk.empty else '19-X-5713-5'}"
    )

    rows = [
        {
            "check_name": "treasury_annual_receipt_line",
            "status": "pass" if not latest_pilot.empty else "warn",
            "severity": "medium",
            "supports_default": bool(not latest_pilot.empty),
            "evidence_grade": "B_public_annual_receipt_line",
            "metric_name": "mrv_receipt_line",
            "metric_value": annual_account_code,
            "details": "The repo has a live Treasury annual MRV receipt line in Receipts by Department.",
            "source_label": "Treasury Receipts by Department / repo candidate bridge",
            "source_url": "https://fiscaldata.treasury.gov/datasets/receipts-by-department/",
        },
        {
            "check_name": "cbsp_account_family_confirmation",
            "status": "pass" if crosswalk_level == "main_account_rollup" else "warn",
            "severity": "medium",
            "supports_default": crosswalk_level in {"exact_account", "main_account_rollup"},
            "evidence_grade": "B_account_family_match",
            "metric_name": "combined_statement_match_level",
            "metric_value": crosswalk_level,
            "details": (
                "Combined Statement now confirms the broader CBSP main-account family around MRV."
                if crosswalk_level == "main_account_rollup"
                else "No Combined Statement account-family confirmation is currently loaded for MRV."
            ),
            "source_label": "Treasury Combined Statement / State department sheet",
            "source_url": "https://fiscal.treasury.gov/accounting/combined-statement-of-receipts/current",
        },
        {
            "check_name": "mrv_fee_applicant_link",
            "status": "pass",
            "severity": "medium",
            "supports_default": True,
            "evidence_grade": "B_applicant_pays_fee",
            "metric_name": "mrv_fee_type",
            "metric_value": "machine_readable_visa_application_processing_fee",
            "details": "Official State visa-fee guidance identifies the MRV fee as the visa application processing fee paid by applicants.",
            "source_label": "9 FAM 403.4 NIV Fees",
            "source_url": "https://fam.state.gov/FAM/09FAM/09FAM040304.html",
        },
        {
            "check_name": "mrv_retained_fee_account_authority",
            "status": "pass",
            "severity": "medium",
            "supports_default": True,
            "evidence_grade": "B_retained_fee_account_authority",
            "metric_name": "retained_fee_account",
            "metric_value": "19X5713.5",
            "details": "FAM accounting guidance states the Department has specific authority to retain MRV fees and credit them to account 19X5713.5.",
            "source_label": "4 FAM 320 Collections",
            "source_url": "https://fam.state.gov/fam/04fam/04fam0320.html",
        },
        {
            "check_name": "cbsp_standalone_account_evidence",
            "status": "pass",
            "severity": "low",
            "supports_default": True,
            "evidence_grade": "B_cbsp_account_structure",
            "metric_name": "cbsp_account_structure",
            "metric_value": "standalone_cbsp_account_since_fy2019",
            "details": "State organizational guidance says the Department created a standalone CBSP account in FY2019 where most retained consular fees are now deposited.",
            "source_label": "1 FAM 250 Bureau of Consular Affairs",
            "source_url": "https://fam.state.gov/fam/01fam/01fam0250.html",
        },
        {
            "check_name": "iv_aos_domestic_bank_contamination_exclusion",
            "status": "pass",
            "severity": "medium",
            "supports_default": True,
            "evidence_grade": "A_exclusion_evidence",
            "metric_name": "iv_aos_payment_rule",
            "metric_value": "us_bank_only_and_anyone_with_login_can_pay",
            "details": "Official NVC fee guidance says IV/AOS payments must be drawn on a U.S. bank and that anyone with the login information can pay, which supports excluding those lines from a strict ROW payer bridge.",
            "source_label": "Travel.State fee pages and NVC fee FAQs",
            "source_url": "https://travel.state.gov/content/travel/en/us-visas/immigrate/the-immigrant-visa-process/step-1-submit-a-petition/step-3-pay-fees/nvc-fee-payment-faqs.html",
        },
        {
            "check_name": "legal_remitter_or_debited_account_proof",
            "status": "fail",
            "severity": "high",
            "supports_default": False,
            "evidence_grade": "D_not_publicly_proven",
            "metric_name": "blocking_condition",
            "metric_value": "no_public_legal_remitter_or_debited_account_proof_for_mrv",
            "details": "The public official sources identify the fee type, retained account, and account family, but do not identify the actual legal remitter or debited account for the Treasury cash receipt.",
            "source_label": "Current repo evidence boundary",
            "source_url": "https://travel.state.gov/content/travel/en/us-visas/immigrate/the-immigrant-visa-process/step-1-submit-a-petition/step-3-pay-fees/nvc-fee-payment-faqs.html",
        },
        {
            "check_name": "observed_quarterly_cash_timing",
            "status": "fail" if not latest_timing.empty else "warn",
            "severity": "high",
            "supports_default": False,
            "evidence_grade": "C_activity_proxy_only",
            "metric_name": "timing_basis",
            "metric_value": "monthly_niv_issuance_share_proxy" if not latest_timing.empty else "no_quarterly_timing_loaded",
            "details": (
                "Quarterly allocation still relies on official monthly NIV issuance shares rather than observed Treasury cash timing."
                if not latest_timing.empty
                else "No quarterly MRV timing bridge is currently loaded."
            ),
            "source_label": "Travel.State monthly NIV issuance statistics / repo timing bridge",
            "source_url": "https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/visa-statistics/nonimmigrant-visa-statistics/monthly-nonimmigrant-visa-issuances.html",
        },
    ]

    out = pd.DataFrame(rows)
    out["overall_recommendation"] = "not_yet_promotable"
    return out.reindex(columns=PAYMENT_CHAIN_COLUMNS)


def render_row_mrv_payment_chain_review_markdown(review: pd.DataFrame) -> str:
    title = "# ROW MRV Payment Chain Review"
    intro = (
        "Evidence-focused review of the MRV / CBSP payment chain using official State, FAM, and Treasury account-system sources. "
        "This artifact is narrower than the main readiness gate: it separates what is already proven about the MRV fee and CBSP account structure "
        "from what still fails for default promotion."
    )
    if review.empty:
        return "\n".join([title, "", intro, "", "No MRV payment-chain review rows are available."])

    summary = f"Overall recommendation: {review.iloc[0]['overall_recommendation']}."
    header = [
        "| Check | Status | Supports default | Evidence grade | Metric | Value |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    rows: list[str] = []
    for _, row in review.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    str(row["check_name"]),
                    str(row["status"]),
                    "yes" if bool(row["supports_default"]) else "no",
                    str(row["evidence_grade"]),
                    str(row["metric_name"]),
                    str(row["metric_value"]),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- This review now confirms the MRV fee/applicant link, retained-fee authority, and broader CBSP account-family mapping.",
        "- It also strengthens the exclusion case for IV / AOS style lines because official NVC fee guidance routes those payments through U.S.-bank transactions that anyone with the case login can make.",
        "- The binding blocker remains the same: no public legal-remitter or debited-account proof for the actual Treasury MRV cash receipt, and no observed quarterly cash timing.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_row_mrv_payment_chain_review(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    receipt_account_crosswalk: pd.DataFrame | None,
    row_visa_consular_pilot: pd.DataFrame | None,
    row_state_visa_timing_sensitivity: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    review = build_row_mrv_payment_chain_review(
        receipt_account_crosswalk=receipt_account_crosswalk,
        row_visa_consular_pilot=row_visa_consular_pilot,
        row_state_visa_timing_sensitivity=row_state_visa_timing_sensitivity,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_row_mrv_payment_chain_review_markdown(review), encoding="utf-8")

    return csv_path, markdown_path, review
