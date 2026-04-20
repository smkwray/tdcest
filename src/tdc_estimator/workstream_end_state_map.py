from __future__ import annotations

from pathlib import Path

import pandas as pd


END_STATE_COLUMNS = [
    "priority_order",
    "workstream_key",
    "domain",
    "recommended_mode",
    "current_state",
    "end_state_target",
    "binding_blocker",
    "external_dependency",
    "next_finite_push",
    "stop_rule",
    "deprioritize_now",
    "summary_note",
]


def _get_row(frame: pd.DataFrame | None, key_col: str, key: str) -> pd.Series:
    if frame is None or frame.empty or key_col not in frame.columns:
        return pd.Series(dtype="object")
    match = frame.loc[frame[key_col].eq(key)]
    if match.empty:
        return pd.Series(dtype="object")
    return match.iloc[0]


def build_workstream_end_state_map(
    *,
    receipt_unblock_status: pd.DataFrame | None,
    bank_receipt_stop_gate: pd.DataFrame | None,
    row_mrv_stop_gate: pd.DataFrame | None,
    monetary_target_preference_review: pd.DataFrame | None,
    monetary_bank_liquid_stop_gate: pd.DataFrame | None,
    fiscal_source_quality: pd.DataFrame | None,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    receipt = receipt_unblock_status.copy() if receipt_unblock_status is not None else pd.DataFrame()
    bank_gate = bank_receipt_stop_gate.copy() if bank_receipt_stop_gate is not None else pd.DataFrame()
    row_gate = row_mrv_stop_gate.copy() if row_mrv_stop_gate is not None else pd.DataFrame()
    monetary_pref = monetary_target_preference_review.copy() if monetary_target_preference_review is not None else pd.DataFrame()
    monetary_stop = monetary_bank_liquid_stop_gate.copy() if monetary_bank_liquid_stop_gate is not None else pd.DataFrame()
    fiscal_quality = fiscal_source_quality.copy() if fiscal_source_quality is not None else pd.DataFrame()

    bank_hist = _get_row(receipt, "branch_key", "bank_table51_historical_window")
    bank_current = _get_row(receipt, "branch_key", "bank_table51_current_window")
    row_mrv = _get_row(receipt, "branch_key", "row_mrv_cbsp_primary")
    row_secondary = _get_row(receipt, "branch_key", "row_secondary_state_visa")
    bank_gate_summary = _get_row(bank_gate, "check_name", "overall_stop_decision")
    row_gate_summary = _get_row(row_gate, "check_name", "overall_stop_decision")
    monetary_pref_summary = pd.Series(dtype="object")
    if not monetary_pref.empty:
        monetary_pref_summary = monetary_pref.iloc[-1]
    monetary_stop_summary = _get_row(monetary_stop, "check_name", "overall_stop_decision")

    reconstruction_note = "Fiscal shell is already live and should stay diagnostic until receipt cells improve."
    if not fiscal_quality.empty and "reliability_grade" in fiscal_quality.columns:
        grades = fiscal_quality["reliability_grade"].astype(str)
        reconstruction_note = (
            "Fiscal shell is already live; keep using it as a reconciliation surface rather than trying to solve weak receipt cells prematurely."
        )
        if grades.eq("A").any() or grades.eq("B").any():
            reconstruction_note += " Higher-quality measured cells already justify keeping the shell active."

    rows.extend(
        [
            {
                "priority_order": 1,
                "workstream_key": "bank_receipt_historical_window",
                "domain": "receipt_bank",
                "recommended_mode": "push_hard",
                "current_state": "historical_default_view_available",
                "end_state_target": "formal_historical_bank_receipt_view_integrated_into_tier3_reporting",
                "binding_blocker": str(bank_hist.get("binding_blocker", "none_within_current_policy_window")),
                "external_dependency": "none_required_for_historical_window",
                "next_finite_push": "Integrate the historical bank window into polished Tier 3 research tables and figures.",
                "stop_rule": "Do not wait on fresher IRS shares before improving historical reporting and labeling.",
                "deprioritize_now": False,
                "summary_note": str(
                    bank_hist.get(
                        "summary_note",
                        "Historical Table 5.1 bank window is already usable and should be exploited in reporting.",
                    )
                ),
            },
            {
                "priority_order": 2,
                "workstream_key": "row_mrv_primary_pilot",
                "domain": "receipt_row",
                "recommended_mode": "bounded_push",
                "current_state": "leading_nondefault_recurring_pilot",
                "end_state_target": "either_default_clearing_mrv_path_or_stable_nondefault_pilot_with_explicit_boundary",
                "binding_blocker": str(row_mrv.get("binding_blocker", "evidence_boundary")),
                "external_dependency": str(
                    row_mrv.get(
                        "missing_source_families",
                        "legal_remitter_or_debited_account_proof;observed_quarterly_cash_timing_or_remittance_schedule",
                    )
                ),
                "next_finite_push": "Tighten the MRV payment-chain and reconciliation layers around the stronger FAH/FAM/OIG nondefault evidence bundle.",
                "stop_rule": "Do not broaden beyond MRV or promote to default without remitter/debited-account proof and quarterly cash timing.",
                "deprioritize_now": False,
                "summary_note": str(
                    row_mrv.get(
                        "summary_note",
                        "MRV is the only recurring ROW branch with realistic payoff, but it remains nondefault.",
                    )
                ),
            },
            {
                "priority_order": 3,
                "workstream_key": "tier3_research_surfaces",
                "domain": "reporting",
                "recommended_mode": "push_hard",
                "current_state": "research_surfaces_exist_but_are_not_yet_the_clean_end_state_package",
                "end_state_target": "clear_default_historical_sensitivity_pack_for_tier2_tier3_bank_and_row_views",
                "binding_blocker": "presentation_and_labeling_work",
                "external_dependency": "none",
                "next_finite_push": "Build the polished Tier 2 vs Tier 3, historical bank, and receipt-boundary figures and tables.",
                "stop_rule": "Do not reopen broad source hunts before the current research surfaces are publication-ready.",
                "deprioritize_now": False,
                "summary_note": "The repo now has enough structured boundaries to package a cleaner end-state research surface without solving every live blocker first.",
            },
            {
                "priority_order": 4,
                "workstream_key": "bank_receipt_current_window",
                "domain": "receipt_bank",
                "recommended_mode": "bounded_monitor",
                "current_state": str(bank_gate_summary.get("status", "historical_default_only_current_nondefault")),
                "end_state_target": "either_fresher_current_default_or_explicit_permanent_nondefault_current_window",
                "binding_blocker": str(bank_current.get("binding_blocker", "stale_share_rule")),
                "external_dependency": str(
                    bank_current.get("missing_source_families", "fresher_public_irs_bank_minor_shares")
                ),
                "next_finite_push": "Keep the current window explicit and nondefault; only revisit if a genuinely newer public IRS bank-minor share appears.",
                "stop_rule": "Stop spending local cycles on parser or perimeter tweaks unless a fresher official public IRS year exists.",
                "deprioritize_now": False,
                "summary_note": str(
                    bank_current.get(
                        "summary_note",
                        "Current bank window is constrained by source freshness, not modeling ambiguity.",
                    )
                ),
            },
            {
                "priority_order": 5,
                "workstream_key": "fiscal_reconciliation_shell",
                "domain": "reconciliation",
                "recommended_mode": "bounded_push",
                "current_state": "diagnostic_shell_live",
                "end_state_target": "stable_reconciliation_matrix_around_the_ladder_not_a_replacement_estimator",
                "binding_blocker": "receipt_cells_still_partial",
                "external_dependency": "downstream_of_receipt_improvements",
                "next_finite_push": "Keep the shell coherent and source-graded while folding in improved historical receipt views.",
                "stop_rule": "Do not try to solve the full fiscal-flow estimator before receipt-side promotion boundaries change.",
                "deprioritize_now": False,
                "summary_note": reconstruction_note,
            },
            {
                "priority_order": 6,
                "workstream_key": "row_secondary_and_contaminated_families",
                "domain": "receipt_row",
                "recommended_mode": "freeze",
                "current_state": str(row_secondary.get("promotion_boundary", "keep_secondary_visa_nondefault")),
                "end_state_target": "stable_exclusion_and_contamination_layer",
                "binding_blocker": "not_primary_row_candidate",
                "external_dependency": "none_until_mrv_changes",
                "next_finite_push": "No new hunt; keep these families visible and excluded.",
                "stop_rule": "Do not spend additional research time on secondary visa, DHS mixed, traveler, or FMS branches unless they directly alter the MRV blocker.",
                "deprioritize_now": True,
                "summary_note": "These branches are now useful mainly as exclusion accounting, not as serious promotion candidates.",
            },
            {
                "priority_order": 7,
                "workstream_key": "bank_nontax_regulatory_receipts",
                "domain": "receipt_bank",
                "recommended_mode": "freeze",
                "current_state": "sensitivity_only",
                "end_state_target": "stable_sensitivity_only_bank_nontax_layer",
                "binding_blocker": "annual_surface_and_budget_treatment_limits",
                "external_dependency": "none_with_current_public_sources",
                "next_finite_push": "No active build beyond keeping OCC/FDIC/OFR lines explicitly nondefault.",
                "stop_rule": "Do not try to turn OCC, FDIC, or OFR families into a default bank receipt module with current public evidence.",
                "deprioritize_now": True,
                "summary_note": "These lines remain useful for sensitivity and exclusion logic, but they are low-payoff for the end-state estimator.",
            },
            {
                "priority_order": 8,
                "workstream_key": "monetary_branch",
                "domain": "monetary",
                "recommended_mode": "diagnostic_only",
                "current_state": str(
                    monetary_pref_summary.get("recommendation", "prefer_depository_target_crosscheck")
                ),
                "end_state_target": "stable_diagnostic_crosscheck_with_depository_target_primary",
                "binding_blocker": str(
                    monetary_stop_summary.get("status", "stop_at_perimeter_stress_test")
                ),
                "external_dependency": "bank_only_liquid_deposit_subcomponents_if_reopened",
                "next_finite_push": "Keep the depository target as the main cross-check and stop expanding the bank-target branch unless a new source family appears.",
                "stop_rule": "Do not spend major effort on monetary decomposition beyond maintaining the diagnostic surfaces.",
                "deprioritize_now": True,
                "summary_note": "The repo already has the monetary answer it needs: depository target as cross-check, commercial-bank target as stress test only.",
            },
        ]
    )

    return pd.DataFrame(rows).reindex(columns=END_STATE_COLUMNS)


def render_workstream_end_state_map_markdown(end_state_map: pd.DataFrame) -> str:
    title = "# Workstream End-State Map"
    intro = (
        "Finite push map for the project. This artifact ranks remaining workstreams by payoff, "
        "names the stop rules, and makes the freeze / bounded-push boundaries explicit."
    )
    if end_state_map.empty:
        return "\n".join([title, "", intro, "", "No workstream end-state rows are available."])

    high = end_state_map.loc[end_state_map["recommended_mode"].isin(["push_hard", "bounded_push"])].copy()
    frozen = end_state_map.loc[end_state_map["deprioritize_now"].fillna(False)].copy()

    lines = [title, "", intro, ""]

    lines.extend(
        [
            "## Highest-Yield Pushes",
            "",
            "| Priority | Workstream | Mode | End-state target | Next finite push | Stop rule |",
            "| ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for _, row in high.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(int(row["priority_order"])),
                    str(row["workstream_key"]),
                    str(row["recommended_mode"]),
                    str(row["end_state_target"]),
                    str(row["next_finite_push"]),
                    str(row["stop_rule"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Freeze Or Diagnostic-Only Branches",
            "",
            "| Priority | Workstream | Mode | Current state | Why not push harder now? |",
            "| ---: | --- | --- | --- | --- |",
        ]
    )
    for _, row in frozen.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(int(row["priority_order"])),
                    str(row["workstream_key"]),
                    str(row["recommended_mode"]),
                    str(row["current_state"]),
                    str(row["summary_note"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Full Map",
            "",
            "| Priority | Workstream | Domain | Mode | Blocker | External dependency | Deprioritize now? |",
            "| ---: | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for _, row in end_state_map.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(int(row["priority_order"])),
                    str(row["workstream_key"]),
                    str(row["domain"]),
                    str(row["recommended_mode"]),
                    str(row["binding_blocker"]),
                    str(row["external_dependency"]),
                    "yes" if bool(row["deprioritize_now"]) else "no",
                ]
            )
            + " |"
        )

    return "\n".join(lines + [""])


def write_workstream_end_state_map(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    receipt_unblock_status: pd.DataFrame | None,
    bank_receipt_stop_gate: pd.DataFrame | None,
    row_mrv_stop_gate: pd.DataFrame | None,
    monetary_target_preference_review: pd.DataFrame | None,
    monetary_bank_liquid_stop_gate: pd.DataFrame | None,
    fiscal_source_quality: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    end_state_map = build_workstream_end_state_map(
        receipt_unblock_status=receipt_unblock_status,
        bank_receipt_stop_gate=bank_receipt_stop_gate,
        row_mrv_stop_gate=row_mrv_stop_gate,
        monetary_target_preference_review=monetary_target_preference_review,
        monetary_bank_liquid_stop_gate=monetary_bank_liquid_stop_gate,
        fiscal_source_quality=fiscal_source_quality,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    end_state_map.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_workstream_end_state_map_markdown(end_state_map), encoding="utf-8")

    return csv_path, markdown_path, end_state_map
