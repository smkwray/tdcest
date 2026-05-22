from __future__ import annotations

from pathlib import Path

import pandas as pd


REVIEW_COLUMNS = [
    "variable_key",
    "variable_family",
    "current_repo_role",
    "included_in_live_headline",
    "latest_reference_date",
    "latest_value_millions",
    "evidence_grade",
    "dominant_in_gap_keys",
    "binding_boundary",
    "downstream_relevance",
    "interpretation_risk",
    "summary_note",
]


def _get_gap_rows(frame: pd.DataFrame | None, variable_key: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    mask = frame["dominant_component_key"].eq(variable_key) | frame["secondary_component_key"].eq(variable_key)
    return frame.loc[mask].copy()


def _latest_quality_row(frame: pd.DataFrame | None, note_contains: str) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype="object")
    subset = frame.loc[frame["notes"].fillna("").str.contains(note_contains, case=False, regex=False)].copy()
    if subset.empty:
        return pd.Series(dtype="object")
    subset["last_date"] = pd.to_datetime(subset["last_date"], errors="coerce")
    subset = subset.sort_values("last_date")
    return subset.iloc[-1]


def _get_boundary_row(frame: pd.DataFrame | None, key: str) -> pd.Series:
    if frame is None or frame.empty or "boundary_key" not in frame.columns:
        return pd.Series(dtype="object")
    subset = frame.loc[frame["boundary_key"].eq(key)]
    if subset.empty:
        return pd.Series(dtype="object")
    return subset.iloc[0]


def _gap_keys_text(frame: pd.DataFrame) -> str:
    if frame.empty:
        return ""
    keys = [str(value) for value in frame["gap_key"].dropna().tolist()]
    return ";".join(dict.fromkeys(keys))


def _latest_value(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return None
    return float(parsed)


def build_downstream_problem_variable_review(
    *,
    fiscal_source_quality: pd.DataFrame | None,
    downstream_estimator_gap_review: pd.DataFrame | None,
    fiscal_receipt_boundary_review: pd.DataFrame | None,
) -> pd.DataFrame:
    quality = fiscal_source_quality.copy() if fiscal_source_quality is not None else pd.DataFrame()
    gap = downstream_estimator_gap_review.copy() if downstream_estimator_gap_review is not None else pd.DataFrame()
    boundary = fiscal_receipt_boundary_review.copy() if fiscal_receipt_boundary_review is not None else pd.DataFrame()

    row_coupon = _latest_quality_row(quality, "rest of the world")
    fed_coupon = _latest_quality_row(quality, "Exact SOMA-based Treasury coupon-interest correction")
    bank_coupon = _latest_quality_row(quality, "default bank perimeter")
    row_outlay = _latest_quality_row(quality, "Current default narrow ROW noninterest-outlay correction")
    bank_outlay = _latest_quality_row(quality, "Current default bank noninterest-outlay correction")

    bank_live_receipt = _get_boundary_row(boundary, "bank_live_default_receipt_cell")
    row_live_receipt = _get_boundary_row(boundary, "row_live_default_receipt_cell")
    bank_hist_overlay = _get_boundary_row(boundary, "bank_receipt_historical_overlay_candidate")
    row_mrv = _get_boundary_row(boundary, "row_mrv_primary_nondefault_pilot")
    perimeter_term = _get_gap_rows(gap, "np_credit_unions_tsy_tx")

    rows = [
        {
            "variable_key": "tier2_row_coupon_correction",
            "variable_family": "interest_cleanup",
            "current_repo_role": "live_default_component",
            "included_in_live_headline": True,
            "latest_reference_date": row_coupon.get("last_date"),
            "latest_value_millions": _latest_value(row_coupon.get("latest_value_millions")),
            "evidence_grade": str(row_coupon.get("reliability_grade", "n/a")),
            "dominant_in_gap_keys": _gap_keys_text(_get_gap_rows(gap, "tier2_row_coupon_correction")),
            "binding_boundary": "proxy_scale_and_sector_allocation",
            "downstream_relevance": "largest live cleanup wedge between the base headline and Tier 2/Tier 3 bank-only views",
            "interpretation_risk": "A large component-anchored Treasury interest cleanup term means downstream users should not treat Tier 0 to corrected-ladder differences as receipt-side effects.",
            "summary_note": str(row_coupon.get("notes", "")),
        },
        {
            "variable_key": "tier1_fed_coupon_correction",
            "variable_family": "interest_cleanup",
            "current_repo_role": "live_default_component",
            "included_in_live_headline": True,
            "latest_reference_date": fed_coupon.get("last_date"),
            "latest_value_millions": _latest_value(fed_coupon.get("latest_value_millions")),
            "evidence_grade": str(fed_coupon.get("reliability_grade", "n/a")),
            "dominant_in_gap_keys": _gap_keys_text(_get_gap_rows(gap, "tier1_fed_coupon_correction")),
            "binding_boundary": "measured_coupon_cleanup_not_a_receipt_boundary",
            "downstream_relevance": "secondary but still material component in the base-to-Tier-2 cleanup wedge",
            "interpretation_risk": "Users comparing raw vs corrected TDC need to separate Fed coupon cleanup and non-Fed component interest cleanup from bank or ROW receipt debates.",
            "summary_note": str(fed_coupon.get("notes", "")),
        },
        {
            "variable_key": "tier3_row_noninterest_outlay_correction",
            "variable_family": "fiscal",
            "current_repo_role": "partial_shell_diagnostic_component",
            "included_in_live_headline": False,
            "latest_reference_date": row_outlay.get("last_date"),
            "latest_value_millions": _latest_value(row_outlay.get("latest_value_millions")),
            "evidence_grade": str(row_outlay.get("reliability_grade", "n/a")),
            "dominant_in_gap_keys": _gap_keys_text(_get_gap_rows(gap, "tier3_row_noninterest_outlay_correction")),
            "binding_boundary": "narrow_row_outlay_profile",
            "downstream_relevance": "dominant Tier-2-to-partial-shell fiscal-flow wedge",
            "interpretation_risk": "Current-quarter Tier 3 partial-shell changes versus Tier 2 are being driven more by ROW outlay treatment than by nonzero receipt corrections.",
            "summary_note": str(row_outlay.get("notes", "")),
        },
        {
            "variable_key": "tier3_bank_noninterest_outlay_correction",
            "variable_family": "fiscal",
            "current_repo_role": "partial_shell_diagnostic_component",
            "included_in_live_headline": False,
            "latest_reference_date": bank_outlay.get("last_date"),
            "latest_value_millions": _latest_value(bank_outlay.get("latest_value_millions")),
            "evidence_grade": str(bank_outlay.get("reliability_grade", "n/a")),
            "dominant_in_gap_keys": _gap_keys_text(_get_gap_rows(gap, "tier3_bank_noninterest_outlay_correction")),
            "binding_boundary": "narrow_bank_outlay_profile",
            "downstream_relevance": "secondary Tier-2-to-partial-shell fiscal-flow wedge",
            "interpretation_risk": "Bank fiscal outlay cleanup matters, but it is smaller than the live ROW outlay wedge in the current build.",
            "summary_note": str(bank_outlay.get("notes", "")),
        },
        {
            "variable_key": "bank_live_default_receipt_cell",
            "variable_family": "receipt_boundary",
            "current_repo_role": "missing_not_measured_cell",
            "included_in_live_headline": False,
            "latest_reference_date": bank_live_receipt.get("latest_reference_date"),
            "latest_value_millions": _latest_value(bank_live_receipt.get("latest_value_millions")),
            "evidence_grade": "low",
            "dominant_in_gap_keys": "",
            "binding_boundary": str(bank_live_receipt.get("binding_blocker", "stale_share_rule")),
            "downstream_relevance": "main current-quarter bank receipt limitation inside the fiscal shell",
            "interpretation_risk": "The zero live bank receipt cell is a source-boundary convention, not evidence that bank receipts are negligible.",
            "summary_note": str(bank_live_receipt.get("interpretation", "")),
        },
        {
            "variable_key": "row_live_default_receipt_cell",
            "variable_family": "receipt_boundary",
            "current_repo_role": "missing_not_measured_cell",
            "included_in_live_headline": False,
            "latest_reference_date": row_live_receipt.get("latest_reference_date"),
            "latest_value_millions": _latest_value(row_live_receipt.get("latest_value_millions")),
            "evidence_grade": "low",
            "dominant_in_gap_keys": "",
            "binding_boundary": str(row_live_receipt.get("binding_blocker", "evidence_boundary")),
            "downstream_relevance": "main current-quarter ROW receipt limitation inside the fiscal shell",
            "interpretation_risk": "The zero live ROW receipt cell is a source-boundary convention, not evidence that ROW receipts are negligible.",
            "summary_note": str(row_live_receipt.get("interpretation", "")),
        },
        {
            "variable_key": "bank_receipt_historical_overlay_candidate",
            "variable_family": "historical_receipt_overlay",
            "current_repo_role": str(bank_hist_overlay.get("current_repo_role", "historical_default_view")),
            "included_in_live_headline": bool(bank_hist_overlay.get("included_in_live_tier3_headline", False)),
            "latest_reference_date": bank_hist_overlay.get("latest_reference_date"),
            "latest_value_millions": _latest_value(bank_hist_overlay.get("latest_value_millions")),
            "evidence_grade": "medium",
            "dominant_in_gap_keys": _gap_keys_text(_get_gap_rows(gap, "bank_receipt_historical_default_candidate_delta_mil")),
            "binding_boundary": str(bank_hist_overlay.get("binding_blocker", "none_within_current_policy_window")),
            "downstream_relevance": "main historical receipt-side backtest variable for bank deposit-effect work",
            "interpretation_risk": "Historical receipt overlays are informative, but must be read with their lower bound rather than as single-point truth.",
            "summary_note": str(bank_hist_overlay.get("interpretation", "")),
        },
        {
            "variable_key": "row_mrv_primary_nondefault_pilot",
            "variable_family": "nondefault_pilot",
            "current_repo_role": str(row_mrv.get("current_repo_role", "leading_recurring_row_pilot")),
            "included_in_live_headline": bool(row_mrv.get("included_in_live_tier3_headline", False)),
            "latest_reference_date": row_mrv.get("latest_reference_date"),
            "latest_value_millions": _latest_value(row_mrv.get("latest_value_millions")),
            "evidence_grade": "bounded_nondefault",
            "dominant_in_gap_keys": "",
            "binding_boundary": str(row_mrv.get("binding_blocker", "evidence_boundary")),
            "downstream_relevance": "best recurring ROW receipt sensitivity now available",
            "interpretation_risk": "MRV should be used to bound ROW receipt effects, not to fill the live default receipt cell.",
            "summary_note": str(row_mrv.get("interpretation", "")),
        },
        {
            "variable_key": "np_credit_unions_tsy_tx",
            "variable_family": "deposit_perimeter",
            "current_repo_role": "broad_depository_perimeter_term",
            "included_in_live_headline": False,
            "latest_reference_date": perimeter_term.iloc[0]["reference_date"] if not perimeter_term.empty else pd.NaT,
            "latest_value_millions": _latest_value(
                perimeter_term.iloc[0]["dominant_component_millions"] if not perimeter_term.empty else None
            ),
            "evidence_grade": "medium",
            "dominant_in_gap_keys": _gap_keys_text(perimeter_term),
            "binding_boundary": "credit_union_and_depository_perimeter_choice",
            "downstream_relevance": "main current driver of the bank-only versus broad-depository comparison wedge",
            "interpretation_risk": "Perimeter-comparison differences are currently small and credit-union-driven, so they should not be confused with receipt-side uncertainty.",
            "summary_note": "This is the leading current perimeter term in the bank-only versus broad-depository comparison.",
        },
    ]

    frame = pd.DataFrame(rows)
    if "latest_reference_date" in frame.columns:
        frame["latest_reference_date"] = pd.to_datetime(frame["latest_reference_date"], errors="coerce")
    return frame.reindex(columns=REVIEW_COLUMNS)


def render_downstream_problem_variable_review_markdown(frame: pd.DataFrame) -> str:
    title = "# Downstream Problem-Variable Review"
    intro = (
        "Ranked backend review of the variables and boundary cells most likely to matter for downstream interpretation. "
        "It separates headline cleanup terms from Tier 3 partial-shell diagnostics, blocked receipt cells, and perimeter-only comparison terms."
    )
    if frame.empty:
        return "\n".join([title, "", intro, "", "No downstream problem-variable rows are available."])

    lines = [
        title,
        "",
        intro,
        "",
        "| Variable | Family | Role | Headline/default | Latest date | Latest value (mil) | Evidence grade | Gap keys | Boundary |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for _, row in frame.iterrows():
        latest_date = (
            pd.Timestamp(row["latest_reference_date"]).date().isoformat()
            if pd.notna(row["latest_reference_date"])
            else "n/a"
        )
        value = row["latest_value_millions"]
        value_text = "n/a" if value is None or pd.isna(value) else f"{float(value):,.3f}"
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["variable_key"]),
                    str(row["variable_family"]),
                    str(row["current_repo_role"]),
                    "yes" if bool(row["included_in_live_headline"]) else "no",
                    latest_date,
                    value_text,
                    str(row["evidence_grade"]),
                    str(row["dominant_in_gap_keys"]),
                    str(row["binding_boundary"]),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Notes", ""])
    for _, row in frame.iterrows():
        lines.append(f"- `{row['variable_key']}`: {row['interpretation_risk']}")

    return "\n".join(lines + [""])


def write_downstream_problem_variable_review(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    fiscal_source_quality: pd.DataFrame | None,
    downstream_estimator_gap_review: pd.DataFrame | None,
    fiscal_receipt_boundary_review: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    frame = build_downstream_problem_variable_review(
        fiscal_source_quality=fiscal_source_quality,
        downstream_estimator_gap_review=downstream_estimator_gap_review,
        fiscal_receipt_boundary_review=fiscal_receipt_boundary_review,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_downstream_problem_variable_review_markdown(frame), encoding="utf-8")

    return csv_path, markdown_path, frame
