from __future__ import annotations

from pathlib import Path

import pandas as pd


UNBLOCK_STATUS_COLUMNS = [
    "branch_key",
    "counterparty_group",
    "coverage_scope",
    "current_repo_role",
    "promotion_boundary",
    "latest_relevant_date",
    "latest_value_millions",
    "binding_blocker",
    "missing_source_families",
    "best_external_research_target",
    "best_local_next_action",
    "summary_note",
]


def _latest_nonzero(series: pd.Series | None) -> float | None:
    if series is None:
        return None
    s = pd.to_numeric(series, errors="coerce").dropna()
    s = s.loc[s.ne(0.0)]
    if s.empty:
        return None
    return float(s.iloc[-1])


def _fmt(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def _parse_date(value: object) -> pd.Timestamp | pd.NaT:
    ts = pd.to_datetime(value, errors="coerce")
    return pd.NaT if pd.isna(ts) else pd.Timestamp(ts)


def _extract_blocking_families(details: object) -> str:
    text = str(details or "")
    prefix = "Blocking source families: "
    if text.startswith(prefix):
        return text[len(prefix):].split(".", 1)[0]
    return text


def _get_row(frame: pd.DataFrame | None, key_col: str, key: str) -> pd.Series:
    if frame is None or frame.empty or key_col not in frame.columns:
        return pd.Series(dtype="object")
    match = frame.loc[frame[key_col].eq(key)]
    if match.empty:
        return pd.Series(dtype="object")
    return match.iloc[0]


def build_receipt_unblock_status(
    *,
    bank_receipt_historical_promotion: pd.DataFrame | None,
    bank_receipt_default_readiness: pd.DataFrame | None,
    bank_receipt_source_map: pd.DataFrame | None,
    bank_receipt_stop_gate: pd.DataFrame | None,
    row_mrv_promotion_checklist: pd.DataFrame | None,
    row_mrv_source_map: pd.DataFrame | None,
    row_mrv_stop_gate: pd.DataFrame | None,
    receipt_promotion_review: pd.DataFrame | None,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    bank_source_map = bank_receipt_source_map.copy() if bank_receipt_source_map is not None else pd.DataFrame()
    bank_stop_gate = bank_receipt_stop_gate.copy() if bank_receipt_stop_gate is not None else pd.DataFrame()

    if bank_receipt_historical_promotion is not None and not bank_receipt_historical_promotion.empty:
        hist = bank_receipt_historical_promotion.copy().sort_values("quarter_end")
        eligible = hist.loc[hist["share_age_eligible_for_default"].fillna(False)].copy()
        if not eligible.empty:
            latest = eligible.iloc[-1]
            rows.append(
                {
                    "branch_key": "bank_table51_historical_window",
                    "counterparty_group": "bank",
                    "coverage_scope": "historical_age_eligible_quarters",
                    "current_repo_role": "historical_default_view",
                    "promotion_boundary": "historical_default_only_current_nondefault",
                    "latest_relevant_date": pd.Timestamp(latest["quarter_end"]),
                    "latest_value_millions": float(latest.get("age_eligible_default_candidate_mil", 0.0)),
                    "binding_blocker": "none_within_current_policy_window",
                    "missing_source_families": "",
                    "best_external_research_target": "none_required_for_historical_window",
                    "best_local_next_action": "keep_historical_default_view_separate_from_current_stale_window",
                    "summary_note": (
                        "Table 5.1 bank-minor bridge is now usable as a historical default view inside the age-eligible window."
                    ),
                }
            )

        latest_any = hist.iloc[-1]
        if not bool(latest_any.get("share_age_eligible_for_default", False)):
            stale_share_year = latest_any.get("stale_share_years")
            stop_summary = _get_row(bank_stop_gate, "check_name", "overall_stop_decision")
            rows.append(
                {
                    "branch_key": "bank_table51_current_window",
                    "counterparty_group": "bank",
                    "coverage_scope": "current_stale_quarters",
                    "current_repo_role": "nondefault_bridge",
                    "promotion_boundary": str(
                        stop_summary.get("status", latest_any.get("promotion_readiness_label", "n/a"))
                    ),
                    "latest_relevant_date": pd.Timestamp(latest_any["quarter_end"]),
                    "latest_value_millions": float(latest_any.get("depository_plus_bhc_bridge_mil", 0.0)),
                    "binding_blocker": "stale_share_rule",
                    "missing_source_families": str(
                        _get_row(bank_source_map, "source_family_key", "fresher_public_irs_bank_minor_shares").get(
                            "source_family_key",
                            "fresher_public_irs_bank_minor_shares",
                        )
                    ),
                    "best_external_research_target": "official_public_irs_bank_minor_shares_beyond_current_loaded_year",
                    "best_local_next_action": "keep_current_quarters_nondefault_and_isolate_historical_window",
                    "summary_note": (
                        f"Current bank bridge remains the leading candidate, but the latest share is too stale under the current rule "
                        f"(stale-share years = {stale_share_year}). No fresher official public IRS bank-minor share path beyond TY2022 has been identified."
                        + (
                            f" Stop gate: {stop_summary.get('status')}."
                            if not stop_summary.empty
                            else ""
                        )
                    ),
                }
            )

    mrv_checklist = row_mrv_promotion_checklist.copy() if row_mrv_promotion_checklist is not None else pd.DataFrame()
    mrv_source_map = row_mrv_source_map.copy() if row_mrv_source_map is not None else pd.DataFrame()
    mrv_stop_gate = row_mrv_stop_gate.copy() if row_mrv_stop_gate is not None else pd.DataFrame()
    review = receipt_promotion_review.copy() if receipt_promotion_review is not None else pd.DataFrame()

    if not review.empty:
        mrv_review = _get_row(review, "candidate_name", "row_state_mrv_cbsp_bridge")
        secondary_review = _get_row(review, "candidate_name", "row_secondary_state_visa_branch")

        if not mrv_review.empty:
            stop_summary = _get_row(mrv_stop_gate, "check_name", "overall_stop_decision")
            latest_mrv_date = _parse_date(mrv_review.get("latest_reference_date"))
            rows.append(
                {
                    "branch_key": "row_mrv_cbsp_primary",
                    "counterparty_group": "row",
                    "coverage_scope": "recurring_mrv_first_pilot",
                    "current_repo_role": "leading_nondefault_recurring_pilot",
                    "promotion_boundary": str(stop_summary.get("status", mrv_review.get("promotion_status", "n/a"))),
                    "latest_relevant_date": latest_mrv_date,
                    "latest_value_millions": float(mrv_review.get("latest_value_millions", 0.0)),
                    "binding_blocker": str(stop_summary.get("blocking_issue_type", "evidence_boundary")),
                    "missing_source_families": _extract_blocking_families(stop_summary.get("details")),
                    "best_external_research_target": "official_public_mrv_remitter_debited_account_or_cash_timing_evidence",
                    "best_local_next_action": "keep_mrv_as_primary_row_pilot_but_nondefault_until_missing_source_families_clear",
                    "summary_note": (
                        str(mrv_review.get("review_note", "n/a"))
                        + " Stronger nondefault FAH/FAM and OIG cash-route evidence is now loaded, but no public quarterly MRV cash series or global legal-remitter proof has been found."
                    ),
                }
            )

        if not secondary_review.empty:
            rows.append(
                {
                    "branch_key": "row_secondary_state_visa",
                    "counterparty_group": "row",
                    "coverage_scope": "secondary_recurring_state_visa_lines",
                    "current_repo_role": "secondary_sensitivity_only",
                    "promotion_boundary": str(secondary_review.get("promotion_status", "n/a")),
                    "latest_relevant_date": _parse_date(secondary_review.get("latest_reference_date")),
                    "latest_value_millions": float(secondary_review.get("latest_value_millions", 0.0)),
                    "binding_blocker": "not_primary_row_candidate",
                    "missing_source_families": "",
                    "best_external_research_target": "none_until_primary_mrv_branch_changes",
                    "best_local_next_action": "keep_secondary_branch_visible_but_nondefault",
                    "summary_note": str(secondary_review.get("review_note", "n/a")),
                }
            )

    if rows:
        out = pd.DataFrame(rows)
        if "latest_relevant_date" in out.columns:
            out["latest_relevant_date"] = pd.to_datetime(out["latest_relevant_date"], errors="coerce")
        return out.reindex(columns=UNBLOCK_STATUS_COLUMNS)

    return pd.DataFrame(columns=UNBLOCK_STATUS_COLUMNS)


def render_receipt_unblock_status_markdown(status_frame: pd.DataFrame) -> str:
    title = "# Receipt Unblock Status"
    intro = (
        "Consolidated critical-path status surface for the receipt side. "
        "It keeps historical bank progress, current bank blockers, and the MRV recurring ROW blocker in one place so new external evidence can be absorbed directly."
    )
    if status_frame.empty:
        return "\n".join([title, "", intro, "", "No receipt unblock-status rows are available."])

    header = [
        "| Branch | Group | Scope | Role | Boundary | Latest date | Latest value (mil) | Binding blocker | Missing source families | External target | Local next action |",
        "| --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    rows: list[str] = []
    for _, row in status_frame.iterrows():
        latest_date = pd.Timestamp(row["latest_relevant_date"]).date().isoformat() if pd.notna(row["latest_relevant_date"]) else "n/a"
        rows.append(
            "| "
            + " | ".join(
                [
                    str(row["branch_key"]),
                    str(row["counterparty_group"]),
                    str(row["coverage_scope"]),
                    str(row["current_repo_role"]),
                    str(row["promotion_boundary"]),
                    latest_date,
                    _fmt(row["latest_value_millions"]),
                    str(row["binding_blocker"]),
                    str(row["missing_source_families"]),
                    str(row["best_external_research_target"]),
                    str(row["best_local_next_action"]),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- The bank branch is now split cleanly between a historical age-eligible window and a current stale-share window.",
        "- The ROW branch is now split cleanly between the MRV-first primary pilot and the secondary visa branch.",
        "- This artifact is intended to be the easiest place to update after external research comes back.",
    ]
    return "\n".join([title, "", intro, "", *header, *rows, "", *notes, ""])


def write_receipt_unblock_status(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    bank_receipt_historical_promotion: pd.DataFrame | None,
    bank_receipt_default_readiness: pd.DataFrame | None,
    bank_receipt_source_map: pd.DataFrame | None,
    bank_receipt_stop_gate: pd.DataFrame | None,
    row_mrv_promotion_checklist: pd.DataFrame | None,
    row_mrv_source_map: pd.DataFrame | None,
    row_mrv_stop_gate: pd.DataFrame | None,
    receipt_promotion_review: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    status_frame = build_receipt_unblock_status(
        bank_receipt_historical_promotion=bank_receipt_historical_promotion,
        bank_receipt_default_readiness=bank_receipt_default_readiness,
        bank_receipt_source_map=bank_receipt_source_map,
        bank_receipt_stop_gate=bank_receipt_stop_gate,
        row_mrv_promotion_checklist=row_mrv_promotion_checklist,
        row_mrv_source_map=row_mrv_source_map,
        row_mrv_stop_gate=row_mrv_stop_gate,
        receipt_promotion_review=receipt_promotion_review,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    status_frame.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_receipt_unblock_status_markdown(status_frame), encoding="utf-8")

    return csv_path, markdown_path, status_frame
