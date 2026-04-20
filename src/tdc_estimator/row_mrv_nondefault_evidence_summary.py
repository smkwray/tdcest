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


def _extract_blocking_families(details: object) -> str:
    text = str(details or "")
    prefix = "Blocking source families: "
    if text.startswith(prefix):
        return text[len(prefix):].split(".", 1)[0]
    return text


def build_row_mrv_nondefault_evidence_summary(
    *,
    row_mrv_payment_chain_review: pd.DataFrame | None,
    row_mrv_promotion_checklist: pd.DataFrame | None,
    row_mrv_source_map: pd.DataFrame | None,
    row_mrv_stop_gate: pd.DataFrame | None,
) -> pd.DataFrame:
    payment = row_mrv_payment_chain_review.copy() if row_mrv_payment_chain_review is not None else pd.DataFrame()
    checklist = row_mrv_promotion_checklist.copy() if row_mrv_promotion_checklist is not None else pd.DataFrame()
    source_map = row_mrv_source_map.copy() if row_mrv_source_map is not None else pd.DataFrame()
    stop_gate = row_mrv_stop_gate.copy() if row_mrv_stop_gate is not None else pd.DataFrame()

    if payment.empty and checklist.empty and source_map.empty and stop_gate.empty:
        return pd.DataFrame()

    complete = int(checklist["status"].eq("complete").sum()) if not checklist.empty and "status" in checklist.columns else 0
    partial = int(checklist["status"].eq("partial").sum()) if not checklist.empty and "status" in checklist.columns else 0
    missing = int(checklist["status"].eq("missing").sum()) if not checklist.empty and "status" in checklist.columns else 0
    loaded_supportive = int(source_map["currently_loaded"].fillna(False).sum()) if not source_map.empty and "currently_loaded" in source_map.columns else 0

    cash = _get_row(source_map, "source_family_key", "cash_treatment_and_retention")
    remitter = _get_row(source_map, "source_family_key", "legal_remitter_or_debited_account_proof")
    timing = _get_row(source_map, "source_family_key", "observed_quarterly_cash_timing_or_remittance_schedule")
    stop = _get_row(stop_gate, "check_name", "overall_stop_decision")

    rows = [
        {
            "summary_key": "mrv_nondefault_evidence_state",
            "overall_recommendation": str(stop.get("status", "stop_at_mrv_nondefault_pilot")),
            "supportive_loaded_source_families": loaded_supportive,
            "promotion_checks_complete": complete,
            "promotion_checks_partial": partial,
            "promotion_checks_missing": missing,
            "cash_route_state": str(cash.get("current_repo_stance", "n/a")),
            "remitter_state": str(remitter.get("current_repo_stance", "n/a")),
            "timing_state": str(timing.get("current_repo_stance", "n/a")),
            "strongest_nondefault_claim": "USDO collection accounts, sweep mechanics, deposit notifications, OF-158 support, and GFSC reconciliation are now publicly evidenced.",
            "binding_default_blocker": _extract_blocking_families(
                stop.get(
                    "details",
                    "cash_treatment_and_retention;legal_remitter_or_debited_account_proof;observed_quarterly_cash_timing_or_remittance_schedule",
                )
            ),
            "next_finite_push": "Tighten the MRV payment-chain and reconciliation presentation without broadening beyond MRV or implying default readiness.",
        }
    ]
    return pd.DataFrame(rows)


def render_row_mrv_nondefault_evidence_summary_markdown(frame: pd.DataFrame) -> str:
    title = "# ROW MRV Nondefault Evidence Summary"
    intro = (
        "Condensed summary of why MRV remains the leading recurring ROW pilot while still staying below default. "
        "This artifact is designed for research packaging rather than source-by-source auditing."
    )
    if frame.empty:
        return "\n".join([title, "", intro, "", "No MRV nondefault evidence summary is available."])

    row = frame.iloc[0]
    lines = [
        title,
        "",
        intro,
        "",
        f"Overall recommendation: `{row['overall_recommendation']}`.",
        f"Loaded supportive source families: `{row['supportive_loaded_source_families']}`.",
        f"Promotion checks: `{row['promotion_checks_complete']}` complete, `{row['promotion_checks_partial']}` partial, `{row['promotion_checks_missing']}` missing.",
        "",
        "| Cash-route state | Remitter state | Timing state | Binding blocker | Next finite push |",
        "| --- | --- | --- | --- | --- |",
        "| "
        + " | ".join(
            [
                str(row["cash_route_state"]),
                str(row["remitter_state"]),
                str(row["timing_state"]),
                str(row["binding_default_blocker"]),
                str(row["next_finite_push"]),
            ]
        )
        + " |",
        "",
        "Notes:",
        f"- {row['strongest_nondefault_claim']}",
        "- This is a packaging artifact for the MRV branch, not a promotion artifact.",
    ]
    return "\n".join(lines + [""])


def write_row_mrv_nondefault_evidence_summary(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    row_mrv_payment_chain_review: pd.DataFrame | None,
    row_mrv_promotion_checklist: pd.DataFrame | None,
    row_mrv_source_map: pd.DataFrame | None,
    row_mrv_stop_gate: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    frame = build_row_mrv_nondefault_evidence_summary(
        row_mrv_payment_chain_review=row_mrv_payment_chain_review,
        row_mrv_promotion_checklist=row_mrv_promotion_checklist,
        row_mrv_source_map=row_mrv_source_map,
        row_mrv_stop_gate=row_mrv_stop_gate,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_row_mrv_nondefault_evidence_summary_markdown(frame), encoding="utf-8")

    return csv_path, markdown_path, frame
