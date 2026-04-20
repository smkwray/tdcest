from __future__ import annotations

from pathlib import Path

import pandas as pd


PROMOTION_CHECKLIST_COLUMNS = [
    "check_name",
    "status",
    "required_for_default",
    "blocks_default",
    "priority",
    "source_artifact",
    "metric_name",
    "metric_value",
    "promotion_rule",
    "next_evidence_needed",
    "overall_recommendation",
]


def _get_row(frame: pd.DataFrame | None, key_col: str, key: str) -> pd.Series:
    if frame is None or frame.empty or key_col not in frame.columns:
        return pd.Series(dtype="object")
    match = frame.loc[frame[key_col].eq(key)]
    if match.empty:
        return pd.Series(dtype="object")
    return match.iloc[0]


def _status_complete_or_missing(flag: bool) -> str:
    return "complete" if flag else "missing"


def _bool_flag(row: pd.Series, field: str) -> bool:
    value = row.get(field)
    if pd.isna(value):
        return False
    return bool(value)


def build_row_mrv_promotion_checklist(
    *,
    row_mrv_default_readiness: pd.DataFrame | None,
    row_mrv_payment_chain_review: pd.DataFrame | None,
    row_recurring_pilot_review: pd.DataFrame | None,
) -> pd.DataFrame:
    if (
        (row_mrv_default_readiness is None or row_mrv_default_readiness.empty)
        and (row_mrv_payment_chain_review is None or row_mrv_payment_chain_review.empty)
        and (row_recurring_pilot_review is None or row_recurring_pilot_review.empty)
    ):
        return pd.DataFrame(columns=PROMOTION_CHECKLIST_COLUMNS)

    readiness = row_mrv_default_readiness.copy() if row_mrv_default_readiness is not None else pd.DataFrame()
    payment = row_mrv_payment_chain_review.copy() if row_mrv_payment_chain_review is not None else pd.DataFrame()
    recurring = row_recurring_pilot_review.copy() if row_recurring_pilot_review is not None else pd.DataFrame()

    readiness_mapping = _get_row(readiness, "check_name", "treasury_account_mapping")
    readiness_cash = _get_row(readiness, "check_name", "cash_treatment")
    readiness_recon = _get_row(readiness, "check_name", "annual_reconciliation")
    payment_receipt_line = _get_row(payment, "check_name", "treasury_annual_receipt_line")
    payment_applicant = _get_row(payment, "check_name", "mrv_fee_applicant_link")
    payment_retained = _get_row(payment, "check_name", "mrv_retained_fee_account_authority")
    payment_cbsp_account = _get_row(payment, "check_name", "cbsp_standalone_account_evidence")
    payment_exclusion = _get_row(payment, "check_name", "iv_aos_domestic_bank_contamination_exclusion")
    payment_remitter = _get_row(payment, "check_name", "legal_remitter_or_debited_account_proof")
    payment_timing = _get_row(payment, "check_name", "observed_quarterly_cash_timing")
    recurring_primary = _get_row(recurring, "branch_name", "mrv_cbsp_primary")
    recurring_secondary = _get_row(recurring, "branch_name", "secondary_state_visa")

    account_complete = (
        str(readiness_mapping.get("status")) == "pass"
        and str(payment_receipt_line.get("status")) == "pass"
    )
    scope_complete = (
        str(payment_applicant.get("status")) == "pass"
        and str(payment_exclusion.get("status")) == "pass"
        and str(recurring_primary.get("promotion_status")) == "future_row_mrv_default_pilot_under_review"
        and str(recurring_secondary.get("promotion_status")) == "keep_secondary_visa_nondefault"
    )
    cash_status = "missing"
    if (
        str(readiness_cash.get("status")) == "warn"
        and str(payment_retained.get("status")) == "pass"
        and str(payment_cbsp_account.get("status")) == "pass"
    ):
        cash_status = "partial"
    elif (
        str(readiness_cash.get("status")) == "pass"
        and str(payment_retained.get("status")) == "pass"
        and str(payment_cbsp_account.get("status")) == "pass"
    ):
        cash_status = "complete"

    recon_complete = str(readiness_recon.get("status")) == "pass"
    remitter_complete = str(payment_remitter.get("status")) == "pass"
    timing_complete = str(payment_timing.get("status")) == "pass"

    rows = [
        {
            "check_name": "treasury_receipt_account_identification",
            "status": _status_complete_or_missing(account_complete),
            "required_for_default": True,
            "blocks_default": not account_complete,
            "priority": "medium",
            "source_artifact": "row_mrv_default_readiness + row_mrv_payment_chain_review",
            "metric_name": "account_mapping",
            "metric_value": str(readiness_mapping.get("metric_value", payment_receipt_line.get("metric_value", "n/a"))),
            "promotion_rule": "Default promotion needs a public Treasury MRV / CBSP receipt line with account-family support.",
            "next_evidence_needed": "Current account-family evidence is usable; tighten only if an exact sub-account source appears.",
        },
        {
            "check_name": "payer_scope_and_exclusions",
            "status": _status_complete_or_missing(scope_complete),
            "required_for_default": True,
            "blocks_default": not scope_complete,
            "priority": "medium",
            "source_artifact": "row_mrv_payment_chain_review + row_recurring_pilot_review",
            "metric_name": "scope_control",
            "metric_value": (
                "mrv_primary_under_review; secondary_visa_nondefault; iv_aos_exclusion_loaded"
                if scope_complete
                else "scope_control_incomplete"
            ),
            "promotion_rule": "MRV must remain the primary recurring ROW branch, with secondary visa and contaminated IV/AOS lines fenced off.",
            "next_evidence_needed": "Keep the MRV-first scope intact and avoid broadening the recurring ROW branch without stronger payer proof.",
        },
        {
            "check_name": "cash_treatment_and_retained_account",
            "status": cash_status,
            "required_for_default": True,
            "blocks_default": cash_status != "complete",
            "priority": "medium",
            "source_artifact": "row_mrv_default_readiness + row_mrv_payment_chain_review",
            "metric_name": "cash_treatment_basis",
            "metric_value": str(readiness_cash.get("metric_value", "n/a")),
            "promotion_rule": "Default promotion needs public cash-treatment evidence stronger than an annual retained-fee receipt title alone.",
            "next_evidence_needed": (
                "Use loaded FAH/FAM/OIG evidence as stronger nondefault support for USDO collection accounts, sweeps, OF-158, and GFSC reconciliation, "
                "but still find a public source that ties MRV retained receipts to the Treasury deposit-change cash concept at the transaction or reporting level."
            ),
        },
        {
            "check_name": "annual_reconciliation",
            "status": _status_complete_or_missing(recon_complete),
            "required_for_default": True,
            "blocks_default": not recon_complete,
            "priority": "low",
            "source_artifact": "row_mrv_default_readiness",
            "metric_name": "annual_alignment",
            "metric_value": str(readiness_recon.get("metric_value", "n/a")),
            "promotion_rule": "Quarterly MRV allocation must reconcile exactly back to the annual Treasury MRV line.",
            "next_evidence_needed": "Keep the annual reconciliation intact as timing refinements change.",
        },
        {
            "check_name": "legal_remitter_or_debited_account",
            "status": _status_complete_or_missing(remitter_complete),
            "required_for_default": True,
            "blocks_default": not remitter_complete,
            "priority": "high",
            "source_artifact": "row_mrv_payment_chain_review",
            "metric_name": str(payment_remitter.get("metric_name", "blocking_condition")),
            "metric_value": str(payment_remitter.get("metric_value", "no_public_legal_remitter_or_debited_account_proof_for_mrv")),
            "promotion_rule": "Default promotion needs public evidence identifying the actual legal remitter or debited account for the Treasury cash receipt.",
            "next_evidence_needed": "Loaded FAH/FAM and OIG sources now support the MRV collection route into USDO accounts and daily or weekly sweeps, "
            "but the repo still needs a public source that names the global legal remitter or debited account path for default use.",
        },
        {
            "check_name": "observed_quarterly_cash_timing",
            "status": _status_complete_or_missing(timing_complete),
            "required_for_default": True,
            "blocks_default": not timing_complete,
            "priority": "high",
            "source_artifact": "row_mrv_payment_chain_review",
            "metric_name": str(payment_timing.get("metric_name", "timing_basis")),
            "metric_value": str(payment_timing.get("metric_value", "monthly_niv_issuance_share_proxy")),
            "promotion_rule": "Default promotion needs observed quarterly cash timing or an official remittance schedule.",
            "next_evidence_needed": "Loaded OIG and FAH/FAM evidence now supports daily, weekly, next-business-day, and short-lag remittance mechanics, "
            "but no public quarterly MRV cash series or global remittance schedule has been found to replace the NIV-issuance timing proxy.",
        },
    ]

    out = pd.DataFrame(rows)
    out["overall_recommendation"] = "not_yet_promotable"
    return out.reindex(columns=PROMOTION_CHECKLIST_COLUMNS)


def render_row_mrv_promotion_checklist_markdown(checklist: pd.DataFrame) -> str:
    title = "# ROW MRV Promotion Checklist"
    intro = (
        "Single promotion-checklist surface for the MRV-first / CBSP branch. "
        "It collapses the scattered readiness, payment-chain, and recurring-pilot evidence into the exact checks that would need to clear before any default promotion."
    )
    if checklist.empty:
        return "\n".join([title, "", intro, "", "No MRV promotion-checklist rows are available."])

    required = checklist.loc[checklist["required_for_default"]]
    complete = int(required["status"].eq("complete").sum())
    partial = int(required["status"].eq("partial").sum())
    missing = int(required["status"].eq("missing").sum())
    summary = (
        f"Overall recommendation: {checklist.iloc[0]['overall_recommendation']}. "
        f"Required checks complete {complete}/{len(required)}, partial {partial}, missing {missing}."
    )

    header = [
        "| Check | Status | Blocks default | Priority | Metric | Value |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    rows: list[str] = []
    for _, row in checklist.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    str(row["check_name"]),
                    str(row["status"]),
                    "yes" if bool(row["blocks_default"]) else "no",
                    str(row["priority"]),
                    str(row["metric_name"]),
                    str(row["metric_value"]),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- The remaining binding blockers are still legal-remitter / debited-account proof and observed quarterly cash timing.",
        "- Cash-treatment evidence is better than before because the retained-fee authority, CBSP account structure, and FAH/FAM/OIG cash-route evidence are loaded, but it is still only partial for default promotion.",
        "- This checklist is meant to drive promotion decisions directly, not just restate the blocker narratively.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_row_mrv_promotion_checklist(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    row_mrv_default_readiness: pd.DataFrame | None,
    row_mrv_payment_chain_review: pd.DataFrame | None,
    row_recurring_pilot_review: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    checklist = build_row_mrv_promotion_checklist(
        row_mrv_default_readiness=row_mrv_default_readiness,
        row_mrv_payment_chain_review=row_mrv_payment_chain_review,
        row_recurring_pilot_review=row_recurring_pilot_review,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    checklist.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_row_mrv_promotion_checklist_markdown(checklist), encoding="utf-8")

    return csv_path, markdown_path, checklist
