from __future__ import annotations

from pathlib import Path

import pandas as pd


STATUS_COLUMNS = [
    "goal_key",
    "category",
    "current_status",
    "current_role",
    "strongest_live_surface",
    "latest_relevant_date",
    "binding_blocker",
    "next_finite_push",
    "summary_note",
]


def _get_row(frame: pd.DataFrame | None, key_col: str, key: str) -> pd.Series:
    if frame is None or frame.empty or key_col not in frame.columns:
        return pd.Series(dtype="object")
    match = frame.loc[frame[key_col].eq(key)]
    if match.empty:
        return pd.Series(dtype="object")
    return match.iloc[0]


def _normalize_date(value: object) -> pd.Timestamp | pd.NaT:
    ts = pd.to_datetime(value, errors="coerce")
    return pd.NaT if pd.isna(ts) else pd.Timestamp(ts)


def build_project_goal_status_review(
    *,
    estimates: pd.DataFrame | None,
    corrections: pd.DataFrame | None,
    receipt_unblock_status: pd.DataFrame | None,
    workstream_end_state_map: pd.DataFrame | None,
    fiscal_source_quality: pd.DataFrame | None,
    monetary_target_preference_review: pd.DataFrame | None,
    monetary_bank_liquid_stop_gate: pd.DataFrame | None,
) -> pd.DataFrame:
    receipt = receipt_unblock_status.copy() if receipt_unblock_status is not None else pd.DataFrame()
    workstreams = workstream_end_state_map.copy() if workstream_end_state_map is not None else pd.DataFrame()
    fiscal_quality = fiscal_source_quality.copy() if fiscal_source_quality is not None else pd.DataFrame()
    monetary_pref = monetary_target_preference_review.copy() if monetary_target_preference_review is not None else pd.DataFrame()
    monetary_stop = monetary_bank_liquid_stop_gate.copy() if monetary_bank_liquid_stop_gate is not None else pd.DataFrame()
    est = estimates.copy() if estimates is not None else pd.DataFrame()
    corr = corrections.copy() if corrections is not None else pd.DataFrame()

    bank_receipts = _get_row(receipt, "branch_key", "bank_table51_current_window")
    bank_hist = _get_row(receipt, "branch_key", "bank_table51_historical_window")
    row_receipts = _get_row(receipt, "branch_key", "row_mrv_cbsp_primary")
    bank_hist_push = _get_row(workstreams, "workstream_key", "bank_receipt_historical_window")
    row_mrv_push = _get_row(workstreams, "workstream_key", "row_mrv_primary_pilot")
    fiscal_push = _get_row(workstreams, "workstream_key", "fiscal_reconciliation_shell")
    monetary_push = _get_row(workstreams, "workstream_key", "monetary_branch")
    monetary_stop_summary = _get_row(monetary_stop, "check_name", "overall_stop_decision")

    tier2_live = "tdc_tier2_interest_corrected_bank_only_ru_flow" in est.columns
    tier3_live = "tdc_tier3_fiscal_corrected_bank_only_ru_flow" in est.columns
    bank_outlay_live = "tier3_bank_noninterest_outlay_correction" in corr.columns
    row_outlay_live = "tier3_row_noninterest_outlay_correction" in corr.columns
    bank_coupon_live = "tier2_bank_coupon_correction" in corr.columns
    row_coupon_live = "tier2_row_coupon_correction" in corr.columns

    latest_est_date = pd.Timestamp(est.index.max()) if not est.empty else pd.NaT

    fiscal_status = "diagnostic_shell_live_not_full_receipt_solved"
    if not fiscal_quality.empty:
        fiscal_status = "diagnostic_shell_live"
        if not receipt.empty and not bank_receipts.empty and not row_receipts.empty:
            if (
                str(bank_receipts.get("binding_blocker")) == "stale_share_rule"
                and str(row_receipts.get("binding_blocker")) == "evidence_boundary"
            ):
                fiscal_status = "diagnostic_shell_live_not_full_receipt_solved"

    monetary_status = "diagnostic_system_live_not_headline"
    if not monetary_pref.empty:
        pref = monetary_pref.iloc[-1]
        if str(pref.get("recommendation_status")) == "prefer_depository_target_crosscheck":
            monetary_status = "diagnostic_system_live_depository_target_preferred"

    rows = [
        {
            "goal_key": "bank_transfers_and_outlays",
            "category": "bank",
            "current_status": "live_interest_plus_partial_outlay_corrections" if tier2_live and bank_outlay_live and bank_coupon_live else "partial",
            "current_role": "headline_ladder_component",
            "strongest_live_surface": "Tier 2 / Tier 3 corrected ladder",
            "latest_relevant_date": latest_est_date,
            "binding_blocker": "receipt_side_completion",
            "next_finite_push": "Keep transfers where they are and improve receipt-side integration around the historical bank window.",
            "summary_note": "Bank interest corrections are live and bank noninterest outlay corrections are already inside Tier 3 narrow / partial. The missing piece is bank receipts, not bank transfer-side construction.",
        },
        {
            "goal_key": "row_transfers_and_outlays",
            "category": "row",
            "current_status": "live_interest_plus_partial_outlay_corrections" if tier2_live and row_outlay_live and row_coupon_live else "partial",
            "current_role": "headline_ladder_component",
            "strongest_live_surface": "Tier 2 / Tier 3 corrected ladder",
            "latest_relevant_date": latest_est_date,
            "binding_blocker": "row_receipt_identity",
            "next_finite_push": "Keep the current narrow ROW outlay/coupon layer and tighten the MRV branch rather than broadening ROW families.",
            "summary_note": "ROW interest corrections are live and narrow ROW noninterest outlay corrections are already inside Tier 3 narrow / partial. The missing piece is a defensible ROW receipt correction, not ROW transfer-side coverage.",
        },
        {
            "goal_key": "bank_receipts",
            "category": "receipt_bank",
            "current_status": str(bank_receipts.get("promotion_boundary", "historical_default_only_current_nondefault")),
            "current_role": "historical_default_plus_current_nondefault_bridge",
            "strongest_live_surface": "Table 5.1 bank-minor bridge with historical-promotion split",
            "latest_relevant_date": _normalize_date(bank_receipts.get("latest_relevant_date")),
            "binding_blocker": str(bank_receipts.get("binding_blocker", "stale_share_rule")),
            "next_finite_push": str(bank_hist_push.get("next_finite_push", "Integrate the historical bank window into Tier 3 reporting.")),
            "summary_note": str(
                bank_receipts.get(
                    "summary_note",
                    "Historical bank receipt window is usable, but current-quarter promotion remains blocked by stale public shares.",
                )
            ),
        },
        {
            "goal_key": "row_receipts",
            "category": "receipt_row",
            "current_status": str(row_receipts.get("promotion_boundary", "stop_at_mrv_nondefault_pilot")),
            "current_role": "leading_nondefault_mrv_pilot",
            "strongest_live_surface": "MRV-first / CBSP branch with checklist, source map, and stop gate",
            "latest_relevant_date": _normalize_date(row_receipts.get("latest_relevant_date")),
            "binding_blocker": str(row_receipts.get("binding_blocker", "evidence_boundary")),
            "next_finite_push": str(row_mrv_push.get("next_finite_push", "Tighten the MRV payment-chain and reconciliation layers.")),
            "summary_note": str(
                row_receipts.get(
                    "summary_note",
                    "MRV remains the leading recurring ROW pilot, but default promotion still fails on remitter/debited-account proof and quarterly cash timing.",
                )
            ),
        },
        {
            "goal_key": "fiscal_flow_tdc_equation",
            "category": "fiscal_flow",
            "current_status": fiscal_status,
            "current_role": "diagnostic_reconciliation_system",
            "strongest_live_surface": "Fiscal reconciliation shell",
            "latest_relevant_date": latest_est_date,
            "binding_blocker": "receipt_cells_still_partial",
            "next_finite_push": str(fiscal_push.get("next_finite_push", "Keep the shell coherent while folding in stronger receipt views.")),
            "summary_note": "The fiscal-flow version exists as a real reconciliation shell around the ladder, not as a fully solved replacement estimator. Its main limitation is still unresolved receipt-side cells.",
        },
        {
            "goal_key": "monetary_disaggregated_tdc_equation",
            "category": "monetary",
            "current_status": monetary_status,
            "current_role": "diagnostic_crosscheck_system",
            "strongest_live_surface": "Monetary target preference review plus bank-liquid stop gate",
            "latest_relevant_date": (
                _normalize_date(monetary_pref.iloc[-1]["latest_quarter"])
                if not monetary_pref.empty and "latest_quarter" in monetary_pref.columns
                else latest_est_date
            ),
            "binding_blocker": str(monetary_stop_summary.get("status", "stop_at_perimeter_stress_test")),
            "next_finite_push": str(monetary_push.get("next_finite_push", "Keep the depository target as the main cross-check.")),
            "summary_note": "The monetary-disaggregated version is already strong as a diagnostic system. The repo prefers the depository target as the main cross-check and keeps the commercial-bank target as a stress-test surface, not a headline estimator.",
        },
    ]
    return pd.DataFrame(rows).reindex(columns=STATUS_COLUMNS)


def render_project_goal_status_review_markdown(review: pd.DataFrame) -> str:
    title = "# Project Goal Status Review"
    intro = (
        "Repo-level status review for the original end goals: bank and ROW transfers, bank and ROW receipts, "
        "the fiscal-flow TDC equation, and the monetary-disaggregated TDC equation."
    )
    if review.empty:
        return "\n".join([title, "", intro, "", "No project goal status review is available."])

    lines = [
        title,
        "",
        intro,
        "",
        "| Goal | Status | Role | Strongest live surface | Binding blocker | Next finite push |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in review.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["goal_key"]),
                    str(row["current_status"]),
                    str(row["current_role"]),
                    str(row["strongest_live_surface"]),
                    str(row["binding_blocker"]),
                    str(row["next_finite_push"]),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Notes", ""])
    for _, row in review.iterrows():
        lines.append(f"- `{row['goal_key']}`: {row['summary_note']}")

    return "\n".join(lines + [""])


def write_project_goal_status_review(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    estimates: pd.DataFrame | None,
    corrections: pd.DataFrame | None,
    receipt_unblock_status: pd.DataFrame | None,
    workstream_end_state_map: pd.DataFrame | None,
    fiscal_source_quality: pd.DataFrame | None,
    monetary_target_preference_review: pd.DataFrame | None,
    monetary_bank_liquid_stop_gate: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    review = build_project_goal_status_review(
        estimates=estimates,
        corrections=corrections,
        receipt_unblock_status=receipt_unblock_status,
        workstream_end_state_map=workstream_end_state_map,
        fiscal_source_quality=fiscal_source_quality,
        monetary_target_preference_review=monetary_target_preference_review,
        monetary_bank_liquid_stop_gate=monetary_bank_liquid_stop_gate,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_project_goal_status_review_markdown(review), encoding="utf-8")

    return csv_path, markdown_path, review
