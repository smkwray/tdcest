from __future__ import annotations

from pathlib import Path

import pandas as pd


READINESS_COLUMNS = [
    "check_name",
    "status",
    "passes_for_default",
    "severity",
    "metric_name",
    "metric_value",
    "threshold_or_rule",
    "details",
    "overall_recommendation",
]


def _format_num(value: float | int | None, places: int = 3) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.{places}f}"


def build_row_mrv_default_readiness(
    *,
    receipt_account_candidates: pd.DataFrame | None,
    receipt_account_crosswalk: pd.DataFrame | None,
    row_visa_consular_pilot: pd.DataFrame | None,
    row_state_visa_timing_sensitivity: pd.DataFrame | None,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    mrv_candidates = pd.DataFrame()
    if receipt_account_candidates is not None and not receipt_account_candidates.empty:
        mrv_candidates = receipt_account_candidates.loc[
            receipt_account_candidates.get("candidate_family", pd.Series(dtype="object")).eq("row_mrv_cbsp_primary")
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

    mrv_crosswalk = pd.DataFrame()
    if receipt_account_crosswalk is not None and not receipt_account_crosswalk.empty:
        mrv_crosswalk = receipt_account_crosswalk.loc[
            receipt_account_crosswalk.get("candidate_family", pd.Series(dtype="object")).eq("row_mrv_cbsp_primary")
        ].copy()

    if mrv_candidates.empty and mrv_pilot.empty and timing.empty and mrv_crosswalk.empty:
        return pd.DataFrame(columns=READINESS_COLUMNS)

    latest_candidate = mrv_candidates.sort_values("date").iloc[-1] if not mrv_candidates.empty else pd.Series(dtype="object")
    latest_pilot = mrv_pilot.sort_values("date").iloc[-1] if not mrv_pilot.empty else pd.Series(dtype="object")
    latest_timing = timing.sort_index().iloc[-1] if not timing.empty else pd.Series(dtype="object")
    latest_crosswalk = mrv_crosswalk.sort_values("date").iloc[-1] if not mrv_crosswalk.empty else pd.Series(dtype="object")

    annual_candidate_amt = pd.to_numeric(pd.Series([latest_candidate.get("receipt_amt_mil")]), errors="coerce").iloc[0]
    annual_pilot_amt = pd.to_numeric(pd.Series([latest_pilot.get("receipt_amt_mil")]), errors="coerce").iloc[0]
    timing_primary_annual = pd.to_numeric(
        pd.Series([latest_timing.get("state_mrv_cbsp_primary_annual_mil")]),
        errors="coerce",
    ).iloc[0]
    timing_quarterly_total = pd.to_numeric(
        timing.get("row_state_visa_allocated_receipt_mil", pd.Series(dtype="float64")),
        errors="coerce",
    ).sum() if not timing.empty else float("nan")

    account_code = (
        f"{latest_candidate.get('aid_cd', '')}-{latest_candidate.get('a_cd', '')}-{latest_candidate.get('main_cd', '')}-{latest_candidate.get('sub_cd', '')}"
        if not latest_candidate.empty
        else "n/a"
    )
    mapping_level = str(latest_crosswalk.get("combined_statement_match_level", "no_crosswalk_context"))
    mapping_supported = mapping_level in {"exact_account", "main_account_rollup"}

    annual_recon_pass = (
        pd.notna(annual_candidate_amt)
        and pd.notna(timing_primary_annual)
        and abs(float(annual_candidate_amt) - float(timing_primary_annual)) < 1e-6
    )

    rows.extend(
        [
            {
                "check_name": "treasury_account_mapping",
                "status": "pass" if not latest_candidate.empty and not latest_pilot.empty and mapping_supported else "warn",
                "passes_for_default": bool(not latest_candidate.empty and not latest_pilot.empty and mapping_supported),
                "severity": "medium",
                "metric_name": "mrv_account_mapping",
                "metric_value": f"{account_code} / {mapping_level}",
                "threshold_or_rule": "MRV default work requires an exact Treasury annual receipt line and pilot mapping.",
                "details": (
                    f"Latest MRV candidate line `{latest_candidate.get('receipt_line_item_nm', 'n/a')}` and pilot bucket `{latest_pilot.get('pilot_bucket', 'n/a')}` are aligned, and the Combined Statement now confirms the broader `{latest_crosswalk.get('combined_statement_title', 'n/a')}` account family at `{mapping_level}` level."
                    if not latest_candidate.empty and not latest_pilot.empty and mapping_supported
                    else "MRV Treasury line or pilot bucket is missing, or no Combined Statement account-family support is currently loaded."
                ),
            },
            {
                "check_name": "payer_identity_evidence",
                "status": "warn",
                "passes_for_default": False,
                "severity": "high",
                "metric_name": "payer_identity_subgrade",
                "metric_value": str(latest_candidate.get("payer_identity_subgrade", "n/a")),
                "threshold_or_rule": "Default promotion requires stronger-than-title-level evidence that the actual payer is ROW-identified.",
                "details": "Current MRV evidence reaches applicant-link level, but not direct legal-remitter or ROW cash-payer proof.",
            },
            {
                "check_name": "debited_account_or_legal_remitter",
                "status": "fail",
                "passes_for_default": False,
                "severity": "high",
                "metric_name": "default_blocker",
                "metric_value": str(latest_candidate.get("default_blocker", "n/a")),
                "threshold_or_rule": "Default promotion requires public evidence about the actual debited account or legal cash remitter.",
                "details": "No public debited-account or legal-remitter proof is currently loaded for MRV / CBSP.",
            },
            {
                "check_name": "cash_treatment",
                "status": "warn" if not latest_pilot.empty else "fail",
                "passes_for_default": False,
                "severity": "medium",
                "metric_name": "cash_treatment_grade",
                "metric_value": str(latest_pilot.get("cash_treatment_grade", "n/a")),
                "threshold_or_rule": "Default promotion requires stronger public cash-treatment evidence than an annual receipt-account title alone.",
                "details": "The current repo has annual CBSP/MRV receipt-account evidence, but not a direct deposit-change cash ledger for MRV.",
            },
            {
                "check_name": "quarterly_timing",
                "status": "warn" if not latest_timing.empty else "fail",
                "passes_for_default": False,
                "severity": "medium",
                "metric_name": "timing_grade",
                "metric_value": str(latest_timing.get("timing_grade", latest_pilot.get("timing_grade", "n/a"))),
                "threshold_or_rule": "Default promotion requires observed quarterly cash timing or an official remittance schedule.",
                "details": (
                    "Quarterly timing currently uses monthly NIV issuance shares as a proxy rather than observed cash timing."
                    if not latest_timing.empty
                    else "No quarterly MRV timing bridge is currently loaded."
                ),
            },
            {
                "check_name": "annual_reconciliation",
                "status": "pass" if annual_recon_pass else "warn",
                "passes_for_default": bool(annual_recon_pass),
                "severity": "low",
                "metric_name": "annual_alignment",
                "metric_value": (
                    f"candidate={_format_num(annual_candidate_amt)} pilot={_format_num(annual_pilot_amt)} timing={_format_num(timing_primary_annual)}"
                ),
                "threshold_or_rule": "Quarterly MRV timing bridge should reconcile back to the same annual MRV receipt line used in the candidate bridge.",
                "details": (
                    f"Quarterly MRV timing sums to annual MRV amount {_format_num(timing_quarterly_total)} and matches the annual candidate line."
                    if annual_recon_pass
                    else "Annual MRV candidate and quarterly MRV timing do not yet reconcile cleanly in the currently loaded inputs."
                ),
            },
        ]
    )

    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=READINESS_COLUMNS)
    out["overall_recommendation"] = "not_yet_promotable"
    return out.reindex(columns=READINESS_COLUMNS)


def render_row_mrv_default_readiness_markdown(readiness: pd.DataFrame) -> str:
    title = "# ROW MRV Default Readiness"
    intro = (
        "Explicit readiness gate for promoting the MRV-first / CBSP bridge into a default ROW receipt correction. "
        "This artifact keeps the current default unchanged and records the current evidence blockers."
    )
    if readiness.empty:
        return "\n".join([title, "", intro, "", "No MRV default-readiness checks are available."])

    summary = f"Overall recommendation: {readiness.iloc[0]['overall_recommendation']}."
    header = [
        "| Check | Status | Passes for default | Metric | Value |",
        "| --- | --- | --- | --- | --- |",
    ]
    rows: list[str] = []
    for _, row in readiness.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    str(row["check_name"]),
                    str(row["status"]),
                    "yes" if bool(row["passes_for_default"]) else "no",
                    str(row["metric_name"]),
                    str(row["metric_value"]),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- The current blocker is not lack of an MRV candidate line; it is lack of public debited-account / legal-remitter proof.",
        "- Quarterly timing currently remains a NIV-share proxy rather than observed cash timing.",
        "- This gate is the ROW-side counterpart to the bank readiness gate: it is meant to sharpen the blocker, not to promote MRV prematurely.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_row_mrv_default_readiness(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    receipt_account_candidates: pd.DataFrame | None,
    receipt_account_crosswalk: pd.DataFrame | None,
    row_visa_consular_pilot: pd.DataFrame | None,
    row_state_visa_timing_sensitivity: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    readiness = build_row_mrv_default_readiness(
        receipt_account_candidates=receipt_account_candidates,
        receipt_account_crosswalk=receipt_account_crosswalk,
        row_visa_consular_pilot=row_visa_consular_pilot,
        row_state_visa_timing_sensitivity=row_state_visa_timing_sensitivity,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    readiness.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_row_mrv_default_readiness_markdown(readiness), encoding="utf-8")

    return csv_path, markdown_path, readiness
