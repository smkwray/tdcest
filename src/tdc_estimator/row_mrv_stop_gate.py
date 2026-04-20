from __future__ import annotations

from pathlib import Path

import pandas as pd


def _get_row(frame: pd.DataFrame | None, key_col: str, key: str) -> pd.Series:
    if frame is None or frame.empty or key_col not in frame.columns:
        return pd.Series(dtype="object")
    match = frame.loc[frame[key_col].eq(key)]
    if match.empty:
        return pd.Series(dtype="object")
    return match.iloc[0]


def _source_family_key(check_name: str) -> str | None:
    return {
        "treasury_receipt_account_identification": "treasury_state_account_mapping",
        "cash_treatment_and_retained_account": "cash_treatment_and_retention",
        "legal_remitter_or_debited_account": "legal_remitter_or_debited_account_proof",
        "observed_quarterly_cash_timing": "observed_quarterly_cash_timing_or_remittance_schedule",
    }.get(check_name)


def _display_name(check_name: str) -> str:
    return {
        "treasury_receipt_account_identification": "treasury_account_family_loaded",
        "payer_scope_and_exclusions": "payer_scope_and_exclusions_loaded",
        "cash_treatment_and_retained_account": "cash_treatment_default_grade",
        "annual_reconciliation": "annual_reconciliation_loaded",
        "legal_remitter_or_debited_account": "legal_remitter_or_debited_account_source",
        "observed_quarterly_cash_timing": "observed_quarterly_cash_timing_source",
    }.get(check_name, check_name)


def _blocking_issue_type(check_name: str, status: str) -> str:
    if status == "complete":
        return "none"
    return {
        "treasury_receipt_account_identification": "account_mapping_gap",
        "payer_scope_and_exclusions": "scope_control_gap",
        "cash_treatment_and_retained_account": "cash_treatment_gap",
        "annual_reconciliation": "annual_reconciliation_gap",
        "legal_remitter_or_debited_account": "payer_identity_gap",
        "observed_quarterly_cash_timing": "timing_gap",
    }.get(check_name, "evidence_gap")


def _recommended_action(check_name: str, status: str) -> str:
    if status == "complete":
        return "keep_loaded"
    return {
        "treasury_receipt_account_identification": "strengthen_account_mapping",
        "payer_scope_and_exclusions": "keep_mrv_primary_and_secondary_lines_fenced",
        "cash_treatment_and_retained_account": "keep_stronger_nondefault_cash_route_bundle_and_find_transaction_level_cash_mapping",
        "annual_reconciliation": "restore_annual_reconciliation_alignment",
        "legal_remitter_or_debited_account": "find_public_remitter_or_debited_account_source",
        "observed_quarterly_cash_timing": "find_public_cash_timing_or_remittance_schedule",
    }.get(check_name, "strengthen_required_default_evidence")


def build_row_mrv_stop_gate(
    *,
    row_mrv_promotion_checklist: pd.DataFrame | None,
    row_mrv_source_map: pd.DataFrame | None,
) -> pd.DataFrame:
    if (
        row_mrv_promotion_checklist is None
        or row_mrv_promotion_checklist.empty
        or row_mrv_source_map is None
        or row_mrv_source_map.empty
    ):
        return pd.DataFrame()

    checklist = row_mrv_promotion_checklist.copy()
    source_map = row_mrv_source_map.copy()

    required = checklist.loc[checklist.get("required_for_default", pd.Series(dtype="bool")).fillna(False)].copy()
    if required.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    complete_count = 0
    partial_count = 0
    missing_count = 0
    blocking_source_families: list[str] = []

    for _, check in required.iterrows():
        check_name = str(check.get("check_name", ""))
        status_value = str(check.get("status", "missing"))
        status = "pass" if status_value == "complete" else ("partial" if status_value == "partial" else "fail")
        passes = status_value == "complete"
        source_family_key = _source_family_key(check_name)
        source_row = _get_row(source_map, "source_family_key", source_family_key) if source_family_key else pd.Series(dtype="object")

        if status_value == "complete":
            complete_count += 1
        elif status_value == "partial":
            partial_count += 1
            if source_family_key:
                blocking_source_families.append(source_family_key)
        else:
            missing_count += 1
            if source_family_key:
                blocking_source_families.append(source_family_key)

        rows.append(
            {
                "check_name": _display_name(check_name),
                "status": status,
                "passes_for_default": passes,
                "blocking_issue_type": _blocking_issue_type(check_name, status_value),
                "metric_name": str(check.get("metric_name", check_name)),
                "metric_value": str(check.get("metric_value", "n/a")),
                "threshold_or_rule": str(check.get("promotion_rule", "Default promotion requires this checklist row to clear.")),
                "source_artifact": str(check.get("source_artifact", "tdc_row_mrv_promotion_checklist.csv")),
                "current_repo_stance": str(source_row.get("current_repo_stance", "checklist_only")),
                "recommended_action": _recommended_action(check_name, status_value),
                "details": str(source_row.get("notes", check.get("next_evidence_needed", "n/a"))),
                "row_type": "check",
            }
        )

    overall_passes = bool(required["status"].eq("complete").all())
    rows.append(
        {
            "check_name": "overall_stop_decision",
            "status": "eligible_for_default_reassessment" if overall_passes else "stop_at_mrv_nondefault_pilot",
            "passes_for_default": overall_passes,
            "blocking_issue_type": "none" if overall_passes else "evidence_boundary",
            "metric_name": "required_check_status_counts",
            "metric_value": f"complete={complete_count};partial_default_blockers={partial_count};missing_required_checks={missing_count}",
            "threshold_or_rule": "Keep MRV as a nondefault recurring pilot until all required checklist rows are complete.",
            "source_artifact": "tdc_row_mrv_promotion_checklist.csv + tdc_row_mrv_source_map.csv",
            "current_repo_stance": "mrv_primary_nondefault_stop_gate",
            "recommended_action": "reassess_default_promotion" if overall_passes else "keep_nondefault_and_target_missing_source_families",
            "details": (
                "Blocking source families: "
                + (";".join(blocking_source_families) if blocking_source_families else "none")
                + ". MRV remains the leading recurring ROW pilot. Public FAH/FAM and OIG evidence now gives a stronger nondefault cash-route bundle, "
                + "but the repo should still stop at nondefault pilot status until every required checklist row is complete."
            ),
            "row_type": "summary",
        }
    )
    return pd.DataFrame(rows)


def render_row_mrv_stop_gate_markdown(gate: pd.DataFrame) -> str:
    title = "# ROW MRV Stop Gate"
    intro = (
        "Explicit promotion stop gate for the MRV-first / CBSP branch. "
        "This artifact turns the current evidence boundary into check-level gate rows plus one overall promotion decision."
    )
    if gate.empty:
        return "\n".join([title, "", intro, "", "No ROW MRV stop gate is available."])

    summary = gate.loc[gate["row_type"].eq("summary")].iloc[0]
    summary_line = (
        f"Overall decision: {summary['status']}. "
        f"Recommended action: {summary['recommended_action']}. "
        f"Required-check counts: {summary['metric_value'] or 'none'}."
    )

    header = [
        "| Check | Status | Passes for default | Blocking issue | Metric | Value | Stance | Recommended action |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    rows: list[str] = []
    for _, row in gate.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    str(row["check_name"]),
                    str(row["status"]),
                    str(bool(row["passes_for_default"])),
                    str(row["blocking_issue_type"]),
                    str(row["metric_name"]),
                    str(row["metric_value"]),
                    str(row["current_repo_stance"]),
                    str(row["recommended_action"]),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- The stop gate is meant to stop accidental promotion, not to downgrade MRV as the leading recurring ROW pilot.",
        "- The binding missing families still center on public legal-remitter / debited-account proof and public quarterly cash timing or remittance evidence, with cash treatment still partial for default use.",
        "- Cash-treatment evidence is now stronger at the nondefault level because public FAH/FAM and OIG sources support USDO collection accounts, sweeps, OF-158 support, and GFSC reconciliation, but not a full MRV-specific Treasury cash mapping.",
    ]
    return "\n".join([title, "", intro, "", summary_line, "", *header, *rows, "", *notes, ""])


def write_row_mrv_stop_gate(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    row_mrv_promotion_checklist: pd.DataFrame | None,
    row_mrv_source_map: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    gate = build_row_mrv_stop_gate(
        row_mrv_promotion_checklist=row_mrv_promotion_checklist,
        row_mrv_source_map=row_mrv_source_map,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    gate.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_row_mrv_stop_gate_markdown(gate), encoding="utf-8")

    return csv_path, markdown_path, gate
