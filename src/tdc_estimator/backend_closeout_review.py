from __future__ import annotations

from pathlib import Path

import pandas as pd


REVIEW_COLUMNS = [
    "review_key",
    "backend_area",
    "current_state",
    "release_readiness",
    "latest_reference_date",
    "strongest_surface",
    "binding_boundary",
    "next_action",
    "stop_rule",
    "summary_note",
]


def _get_row(frame: pd.DataFrame | None, key_col: str, key: str) -> pd.Series:
    if frame is None or frame.empty or key_col not in frame.columns:
        return pd.Series(dtype="object")
    subset = frame.loc[frame[key_col].eq(key)]
    if subset.empty:
        return pd.Series(dtype="object")
    return subset.iloc[0]


def _date(value: object) -> str:
    if value is None:
        return "n/a"
    try:
        if pd.isna(value):
            return "n/a"
    except TypeError:
        pass
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return str(value)
    return pd.Timestamp(ts).date().isoformat()


def build_backend_closeout_review(
    *,
    project_goal_status_review: pd.DataFrame | None,
    receipt_unblock_status: pd.DataFrame | None,
    downstream_consistency_review: pd.DataFrame | None,
    workstream_end_state_map: pd.DataFrame | None,
) -> pd.DataFrame:
    goals = project_goal_status_review.copy() if project_goal_status_review is not None else pd.DataFrame()
    receipt = receipt_unblock_status.copy() if receipt_unblock_status is not None else pd.DataFrame()
    consistency = downstream_consistency_review.copy() if downstream_consistency_review is not None else pd.DataFrame()
    workstreams = workstream_end_state_map.copy() if workstream_end_state_map is not None else pd.DataFrame()

    bank_branch = _get_row(receipt, "branch_key", "bank_table51_historical_window")
    bank_current = _get_row(receipt, "branch_key", "bank_table51_current_window")
    row_branch = _get_row(receipt, "branch_key", "row_mrv_cbsp_primary")
    fiscal_goal = _get_row(goals, "goal_key", "fiscal_flow_tdc_equation")
    monetary_goal = _get_row(goals, "goal_key", "monetary_disaggregated_tdc_equation")
    bank_work = _get_row(workstreams, "workstream_key", "bank_receipt_historical_window")
    row_work = _get_row(workstreams, "workstream_key", "row_mrv_primary_pilot")
    fiscal_work = _get_row(workstreams, "workstream_key", "fiscal_reconciliation_shell")
    monetary_work = _get_row(workstreams, "workstream_key", "monetary_branch")

    all_consistency_pass = (
        not consistency.empty
        and "status" in consistency.columns
        and consistency["status"].eq("pass").all()
    )

    rows = [
        {
            "review_key": "downstream_contract_layer",
            "backend_area": "downstream_contracts",
            "current_state": "aligned" if all_consistency_pass else "drift_detected",
            "release_readiness": "closeout_ready" if all_consistency_pass else "needs_alignment",
            "latest_reference_date": _date(fiscal_goal.get("latest_relevant_date")),
            "strongest_surface": "tdc_downstream_consistency_review.csv",
            "binding_boundary": "all downstream contract invariants must stay green",
            "next_action": "Keep invariant tests green and avoid adding new backend branches without updating the contract layer.",
            "stop_rule": "If consistency review stays all-pass, stop branching and treat the contract layer as stable.",
            "summary_note": "The downstream handoff is closeout-ready only when the bundle, contract, router, and panels stay aligned.",
        },
        {
            "review_key": "bank_receipt_branch",
            "backend_area": "bank_receipts",
            "current_state": str(bank_branch.get("promotion_boundary", "historical_default_only_current_nondefault")),
            "release_readiness": "bounded_historical_ready",
            "latest_reference_date": _date(bank_branch.get("latest_relevant_date")),
            "strongest_surface": "tdc_receipt_unblock_status.csv",
            "binding_boundary": str(bank_current.get("binding_blocker", "stale_share_rule")),
            "next_action": str(bank_work.get("next_finite_push", "Keep the historical bank overlay first-class and leave current quarters nondefault.")),
            "stop_rule": "Do not reopen current-quarter bank receipt promotion unless fresher official IRS bank-minor shares appear.",
            "summary_note": str(bank_branch.get("summary_note", "Historical bank window is usable; current quarters remain nondefault.")),
        },
        {
            "review_key": "row_mrv_branch",
            "backend_area": "row_receipts",
            "current_state": str(row_branch.get("promotion_boundary", "stop_at_mrv_nondefault_pilot")),
            "release_readiness": "bounded_nondefault_ready",
            "latest_reference_date": _date(row_branch.get("latest_relevant_date")),
            "strongest_surface": "tdc_row_mrv_stop_gate.csv",
            "binding_boundary": str(row_branch.get("binding_blocker", "evidence_boundary")),
            "next_action": str(row_work.get("next_finite_push", "Keep MRV as the only bounded ROW receipt branch and tighten presentation, not scope.")),
            "stop_rule": "Do not reopen secondary ROW branches unless they directly clear the MRV blocker.",
            "summary_note": str(row_branch.get("summary_note", "MRV remains the only bounded ROW pilot and stays nondefault.")),
        },
        {
            "review_key": "fiscal_shell",
            "backend_area": "fiscal_flow",
            "current_state": str(fiscal_goal.get("current_status", "diagnostic_shell_live_not_full_receipt_solved")),
            "release_readiness": "bounded_diagnostic_ready",
            "latest_reference_date": _date(fiscal_goal.get("latest_relevant_date")),
            "strongest_surface": str(fiscal_goal.get("strongest_live_surface", "Fiscal reconciliation shell")),
            "binding_boundary": str(fiscal_goal.get("binding_blocker", "receipt_cells_still_partial")),
            "next_action": str(fiscal_work.get("next_finite_push", "Keep the fiscal shell aligned with historical bank and MRV boundaries.")),
            "stop_rule": "Do not expand fiscal-flow scope until receipt boundaries move with genuinely new evidence.",
            "summary_note": str(fiscal_goal.get("summary_note", "Fiscal shell is usable as a reconciliation system, not a fully solved receipt-complete estimator.")),
        },
        {
            "review_key": "monetary_crosscheck",
            "backend_area": "monetary_branch",
            "current_state": str(monetary_goal.get("current_status", "diagnostic_system_live_depository_target_preferred")),
            "release_readiness": "diagnostic_only_stable",
            "latest_reference_date": _date(monetary_goal.get("latest_relevant_date")),
            "strongest_surface": "tdc_monetary_target_preference_review.csv",
            "binding_boundary": str(monetary_goal.get("binding_blocker", "stop_at_perimeter_stress_test")),
            "next_action": str(monetary_work.get("next_finite_push", "Keep the depository target as the main cross-check and stop expanding the bank target branch.")),
            "stop_rule": "Do not reopen major monetary expansion unless a genuinely new source family appears.",
            "summary_note": str(monetary_goal.get("summary_note", "Monetary branch is stable as a diagnostic cross-check rather than a headline estimator.")),
        },
    ]

    return pd.DataFrame(rows).reindex(columns=REVIEW_COLUMNS)


def render_backend_closeout_review_markdown(frame: pd.DataFrame) -> str:
    title = "# Backend Closeout Review"
    intro = (
        "Explicit backend closeout surface. It says which branches are stable enough to freeze, which remain bounded, "
        "and what exact rule would justify reopening them."
    )
    if frame.empty:
        return "\n".join([title, "", intro, "", "No backend closeout rows are available."])

    lines = [
        title,
        "",
        intro,
        "",
        "| Area | State | Release readiness | Latest date | Strongest surface | Binding boundary |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in frame.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["review_key"]),
                    str(row["current_state"]),
                    str(row["release_readiness"]),
                    str(row["latest_reference_date"]),
                    str(row["strongest_surface"]),
                    str(row["binding_boundary"]),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Notes", ""])
    for _, row in frame.iterrows():
        lines.append(f"- `{row['review_key']}`: {row['summary_note']}")

    return "\n".join(lines + [""])


def write_backend_closeout_review(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    project_goal_status_review: pd.DataFrame | None,
    receipt_unblock_status: pd.DataFrame | None,
    downstream_consistency_review: pd.DataFrame | None,
    workstream_end_state_map: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    frame = build_backend_closeout_review(
        project_goal_status_review=project_goal_status_review,
        receipt_unblock_status=receipt_unblock_status,
        downstream_consistency_review=downstream_consistency_review,
        workstream_end_state_map=workstream_end_state_map,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_backend_closeout_review_markdown(frame), encoding="utf-8")

    return csv_path, markdown_path, frame
