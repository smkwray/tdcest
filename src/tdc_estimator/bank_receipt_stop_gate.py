from __future__ import annotations

from pathlib import Path

import pandas as pd


STOP_GATE_COLUMNS = [
    "check_name",
    "status",
    "passes_for_current_default",
    "blocking_issue_type",
    "metric_name",
    "metric_value",
    "threshold_or_rule",
    "source_artifact",
    "current_repo_stance",
    "recommended_action",
    "details",
    "row_type",
]


def _get_row(frame: pd.DataFrame | None, key_col: str, key: str) -> pd.Series:
    if frame is None or frame.empty or key_col not in frame.columns:
        return pd.Series(dtype="object")
    match = frame.loc[frame[key_col].eq(key)]
    if match.empty:
        return pd.Series(dtype="object")
    return match.iloc[0]


def build_bank_receipt_stop_gate(
    *,
    bank_receipt_default_readiness: pd.DataFrame | None,
    bank_receipt_historical_promotion: pd.DataFrame | None,
    bank_receipt_source_map: pd.DataFrame | None,
) -> pd.DataFrame:
    if (
        bank_receipt_default_readiness is None
        or bank_receipt_default_readiness.empty
        or bank_receipt_historical_promotion is None
        or bank_receipt_historical_promotion.empty
        or bank_receipt_source_map is None
        or bank_receipt_source_map.empty
    ):
        return pd.DataFrame(columns=STOP_GATE_COLUMNS)

    readiness = bank_receipt_default_readiness.copy()
    historical = bank_receipt_historical_promotion.copy().sort_values("quarter_end")
    source_map = bank_receipt_source_map.copy()

    perimeter = _get_row(readiness, "check_name", "perimeter_contamination")
    stale = _get_row(readiness, "check_name", "stale_share_rule")
    overlap = _get_row(readiness, "check_name", "estimator_integration_overlap")
    sign = _get_row(readiness, "check_name", "no_double_count_and_sign")
    latest = historical.iloc[-1]
    eligible = historical.loc[historical["share_age_eligible_for_default"].fillna(False)]
    latest_eligible = eligible.iloc[-1] if not eligible.empty else pd.Series(dtype="object")
    fresh_share_source = _get_row(source_map, "source_family_key", "fresher_public_irs_bank_minor_shares")

    perimeter_ok = str(perimeter.get("status")) == "pass"
    stale_ok = str(stale.get("status")) == "pass"
    overlap_ok = str(overlap.get("status")) == "pass"
    sign_ok = str(sign.get("status")) == "pass"

    rows = [
        {
            "check_name": "historical_window_available",
            "status": "pass" if not eligible.empty else "fail",
            "passes_for_current_default": False,
            "blocking_issue_type": "none" if not eligible.empty else "no_historical_window",
            "metric_name": "latest_historical_quarter",
            "metric_value": (
                pd.Timestamp(latest_eligible["quarter_end"]).date().isoformat() if not latest_eligible.empty else "n/a"
            ),
            "threshold_or_rule": "The historical age-eligible window should remain available even while current quarters stay nondefault.",
            "source_artifact": "tdc_bank_receipt_historical_promotion.csv",
            "current_repo_stance": "historical_default_view_available" if not eligible.empty else "no_historical_window_available",
            "recommended_action": "keep_historical_view" if not eligible.empty else "rebuild_historical_window",
            "details": "The bank branch is already usable as a historical default view inside the age-eligible window.",
            "row_type": "check",
        },
        {
            "check_name": "bank_perimeter_loaded",
            "status": "pass" if perimeter_ok else "fail",
            "passes_for_current_default": perimeter_ok,
            "blocking_issue_type": "none" if perimeter_ok else "perimeter_gap",
            "metric_name": "bridge_basis",
            "metric_value": str(perimeter.get("metric_value", "n/a")),
            "threshold_or_rule": "Current-quarter bank promotion only proceeds if the bank-minor perimeter is loaded and acceptable.",
            "source_artifact": "tdc_bank_receipt_default_readiness.csv",
            "current_repo_stance": "table51_bank_minor_loaded" if perimeter_ok else "perimeter_not_ready",
            "recommended_action": "keep_loaded" if perimeter_ok else "fix_perimeter",
            "details": str(perimeter.get("details", "n/a")),
            "row_type": "check",
        },
        {
            "check_name": "fresher_public_share_loaded",
            "status": "pass" if stale_ok else "fail",
            "passes_for_current_default": stale_ok,
            "blocking_issue_type": "share_freshness_gap" if not stale_ok else "none",
            "metric_name": "stale_share_years",
            "metric_value": str(stale.get("metric_value", "n/a")),
            "threshold_or_rule": "Current-quarter bank default cannot proceed while the share stays outside the stale-share rule.",
            "source_artifact": "tdc_bank_receipt_source_map.csv",
            "current_repo_stance": str(fresh_share_source.get("current_repo_stance", "n/a")),
            "recommended_action": "find_fresher_public_irs_share_source" if not stale_ok else "reassess_current_default",
            "details": str(fresh_share_source.get("notes", stale.get("details", "n/a"))),
            "row_type": "check",
        },
        {
            "check_name": "current_overlap_alignment",
            "status": "pass" if overlap_ok else "warn",
            "passes_for_current_default": overlap_ok,
            "blocking_issue_type": "integration_gap" if not overlap_ok else "none",
            "metric_name": str(overlap.get("metric_name", "latest_overlap")),
            "metric_value": str(overlap.get("metric_value", "n/a")),
            "threshold_or_rule": "If a fresher share appears, bridge and estimator overlap should still align cleanly before current default promotion.",
            "source_artifact": "tdc_bank_receipt_default_readiness.csv",
            "current_repo_stance": "current_overlap_warns" if not overlap_ok else "current_overlap_aligned",
            "recommended_action": "keep_overlap_visible_and_recheck_after_fresher_share",
            "details": str(overlap.get("details", "n/a")),
            "row_type": "check",
        },
        {
            "check_name": "sign_and_double_count_guardrail",
            "status": "pass" if sign_ok else "fail",
            "passes_for_current_default": sign_ok,
            "blocking_issue_type": "sign_or_overlap_issue" if not sign_ok else "none",
            "metric_name": str(sign.get("metric_name", "integration_sign_status")),
            "metric_value": str(sign.get("metric_value", "n/a")),
            "threshold_or_rule": "Any current default promotion must keep the bank bridge isolated from OCC and routing-channel layers.",
            "source_artifact": "tdc_bank_receipt_default_readiness.csv",
            "current_repo_stance": "isolated_positive_candidate" if sign_ok else "integration_issue",
            "recommended_action": "keep_isolated" if sign_ok else "fix_double_count_boundary",
            "details": str(sign.get("details", "n/a")),
            "row_type": "check",
        },
        {
            "check_name": "overall_stop_decision",
            "status": (
                "historical_default_only_current_nondefault"
                if not stale_ok
                else (
                    "current_nondefault_until_overlap_alignment"
                    if not overlap_ok
                    else "eligible_for_current_default_reassessment"
                )
            ),
            "passes_for_current_default": perimeter_ok and stale_ok and overlap_ok and sign_ok,
            "blocking_issue_type": (
                "share_freshness_boundary"
                if not stale_ok
                else ("integration_overlap_boundary" if not overlap_ok else "none")
            ),
            "metric_name": "latest_current_quarter",
            "metric_value": pd.Timestamp(latest["quarter_end"]).date().isoformat(),
            "threshold_or_rule": "Keep the bank branch split between historical default and current nondefault until a fresher public IRS share is loaded.",
            "source_artifact": "tdc_bank_receipt_historical_promotion.csv + tdc_bank_receipt_source_map.csv",
            "current_repo_stance": (
                "bank_historical_view_plus_current_nondefault"
                if not stale_ok
                else ("keep_current_nondefault_until_overlap_alignment" if not overlap_ok else "reassess_current_default")
            ),
            "recommended_action": (
                "keep_historical_default_and_target_fresher_irs_share"
                if not stale_ok
                else ("fix_overlap_alignment_before_reassessment" if not overlap_ok else "reassess_current_default_promotion")
            ),
            "details": (
                "Historical age-eligible quarters can remain usable, but the current quarter should stay nondefault until fresher public IRS bank-minor shares exist. "
                "Even with a fresher share, the bridge and estimator overlap should align cleanly before current default promotion. "
                "Current public official bank-minor share evidence still tops out at TY2022."
            ),
            "row_type": "summary",
        },
    ]
    return pd.DataFrame(rows).reindex(columns=STOP_GATE_COLUMNS)


def render_bank_receipt_stop_gate_markdown(gate: pd.DataFrame) -> str:
    title = "# Bank Receipt Stop Gate"
    intro = (
        "Explicit promotion stop gate for the bank corporate-tax bridge. "
        "This artifact keeps the historical age-eligible window separate from the current stale-share boundary."
    )
    if gate.empty:
        return "\n".join([title, "", intro, "", "No bank receipt stop gate is available."])

    summary = gate.loc[gate["row_type"].eq("summary")].iloc[0]
    summary_line = (
        f"Overall decision: {summary['status']}. "
        f"Recommended action: {summary['recommended_action']}. "
        f"Latest current quarter: {summary['metric_value']}."
    )

    header = [
        "| Check | Status | Passes for current default | Blocking issue | Metric | Value | Stance | Recommended action |",
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
                    str(bool(row["passes_for_current_default"])),
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
        "- This stop gate is about current-quarter bank promotion, not about rolling back the historical default window.",
        "- The binding current blocker remains fresher public IRS bank-minor share evidence.",
        "- Latest external source review found no official public IRS bank-minor share path fresher than Publication 16 Table 5.1 through TY2022.",
    ]
    return "\n".join([title, "", intro, "", summary_line, "", *header, *rows, "", *notes, ""])


def write_bank_receipt_stop_gate(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    bank_receipt_default_readiness: pd.DataFrame | None,
    bank_receipt_historical_promotion: pd.DataFrame | None,
    bank_receipt_source_map: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    gate = build_bank_receipt_stop_gate(
        bank_receipt_default_readiness=bank_receipt_default_readiness,
        bank_receipt_historical_promotion=bank_receipt_historical_promotion,
        bank_receipt_source_map=bank_receipt_source_map,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    gate.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_bank_receipt_stop_gate_markdown(gate), encoding="utf-8")

    return csv_path, markdown_path, gate
