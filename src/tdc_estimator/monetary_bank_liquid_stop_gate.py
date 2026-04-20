from __future__ import annotations

from pathlib import Path

import pandas as pd


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def _safe_bool(value: object) -> bool:
    if pd.isna(value):
        return False
    return bool(value)


def _safe_float(value: object) -> float | pd._libs.missing.NAType:
    value = pd.to_numeric(value, errors="coerce")
    if pd.isna(value):
        return pd.NA
    return float(value)


def build_monetary_bank_liquid_stop_gate(
    bank_liquid_source_review: pd.DataFrame | None,
    perimeter_gap_review: pd.DataFrame | None,
) -> pd.DataFrame:
    if (
        bank_liquid_source_review is None
        or bank_liquid_source_review.empty
        or perimeter_gap_review is None
        or perimeter_gap_review.empty
    ):
        return pd.DataFrame()

    review = bank_liquid_source_review.iloc[0]
    perimeter = perimeter_gap_review.iloc[0]
    latest_quarter = str(review.get("latest_quarter"))
    residual_after_context = _safe_float(review.get("residual_after_loaded_additive_liability_context_mil"))
    additive_context_share = _safe_float(review.get("loaded_additive_liability_context_share_of_wedge"))
    broad_context_share = _safe_float(review.get("best_loaded_broad_context_share_of_wedge"))
    has_bank_vs_broad_bridge = _safe_bool(perimeter.get("has_bank_vs_broad_depository_bridge"))
    has_large_time = _safe_bool(perimeter.get("has_large_time_or_wholesale_deposit_components"))
    has_clean_bank_only = _safe_bool(review.get("has_clean_bank_only_liquid_subcomponent_loaded"))

    rows = [
        {
            "latest_quarter": latest_quarter,
            "candidate_key": "bank_vs_broad_depository_bridge",
            "check_name": "nonbank_bridge_side_loaded",
            "status": "pass" if has_bank_vs_broad_bridge else "fail",
            "passes_for_next_stage": has_bank_vs_broad_bridge,
            "passes_for_publication": has_bank_vs_broad_bridge,
            "blocking_issue_type": "none" if has_bank_vs_broad_bridge else "coverage_gap",
            "metric_name": "has_bank_vs_broad_depository_bridge",
            "metric_value": 1.0 if has_bank_vs_broad_bridge else 0.0,
            "threshold_or_rule": "must be loaded before blaming the commercial-bank wedge on missing nonbank bridge sides",
            "source_artifact": "tdc_monetary_bank_perimeter_gap_review.csv",
            "current_repo_stance": "bridge_sides_loaded" if has_bank_vs_broad_bridge else "bridge_incomplete",
            "recommended_action": "keep_loaded",
            "details": "Credit-union and thrift bridge sides should be loaded before the bank-only liquid stop condition is interpreted as binding.",
            "row_type": "check",
        },
        {
            "latest_quarter": latest_quarter,
            "candidate_key": "large_time_or_wholesale_deposit_components",
            "check_name": "large_time_component_loaded",
            "status": "pass" if has_large_time else "fail",
            "passes_for_next_stage": has_large_time,
            "passes_for_publication": has_large_time,
            "blocking_issue_type": "none" if has_large_time else "coverage_gap",
            "metric_name": "has_large_time_or_wholesale_deposit_components",
            "metric_value": 1.0 if has_large_time else 0.0,
            "threshold_or_rule": "large-time bucket should be loaded before treating the residual as purely bank-only liquid",
            "source_artifact": "tdc_monetary_bank_perimeter_gap_review.csv",
            "current_repo_stance": str(review.get("loaded_large_time_role") or "n/a"),
            "recommended_action": "keep_loaded" if has_large_time else "load_large_time_bucket",
            "details": "Large time deposits are the cleanest currently identified public bank-liability bucket and should remain part of the additive context.",
            "row_type": "check",
        },
        {
            "latest_quarter": latest_quarter,
            "candidate_key": "bank_only_liquid_deposit_subcomponents",
            "check_name": "clean_bank_only_liquid_subcomponent_loaded",
            "status": "pass" if has_clean_bank_only else "fail",
            "passes_for_next_stage": has_clean_bank_only,
            "passes_for_publication": has_clean_bank_only,
            "blocking_issue_type": "source_boundary" if not has_clean_bank_only else "none",
            "metric_name": "has_clean_bank_only_liquid_subcomponent_loaded",
            "metric_value": 1.0 if has_clean_bank_only else 0.0,
            "threshold_or_rule": "a clean current public bank-only liquid-deposit subcomponent family must exist before this branch can move past perimeter-stress interpretation",
            "source_artifact": "tdc_monetary_bank_liquid_source_review.csv",
            "current_repo_stance": str(review.get("source_map_liquid_stance") or "n/a"),
            "recommended_action": "stop_at_current_boundary" if not has_clean_bank_only else "reassess_boundary",
            "details": "This is the main blocking check. A broad bank-deposit context series is not equivalent to a clean bank-only liquid-deposit subcomponent family.",
            "row_type": "check",
        },
        {
            "latest_quarter": latest_quarter,
            "candidate_key": str(review.get("best_loaded_broad_context_series") or "n/a"),
            "check_name": "broad_context_not_promoted",
            "status": "guardrail_active",
            "passes_for_next_stage": False,
            "passes_for_publication": False,
            "blocking_issue_type": "perimeter_contamination",
            "metric_name": "best_loaded_broad_context_share_of_wedge",
            "metric_value": broad_context_share,
            "threshold_or_rule": "broad context may be reported, but not promoted into the additive stop-gate total unless it becomes a clean bank-only liquid subcomponent",
            "source_artifact": "tdc_monetary_bank_liquid_source_review.csv",
            "current_repo_stance": str(review.get("best_loaded_broad_context_role") or "n/a"),
            "recommended_action": "keep_as_context_only",
            "details": "ODSACBM027SBOG is meaningful context and currently large, but it remains broader than a clean bank-only liquid subcomponent.",
            "row_type": "check",
        },
        {
            "latest_quarter": latest_quarter,
            "candidate_key": str(review.get("rejected_candidate_construction") or "n/a"),
            "check_name": "rejected_overlap_construction",
            "status": "guardrail_active",
            "passes_for_next_stage": False,
            "passes_for_publication": False,
            "blocking_issue_type": "overlap_or_scope_mismatch",
            "metric_name": "rejected_candidate_reason",
            "metric_value": pd.NA,
            "threshold_or_rule": "do not rehabilitate explicitly rejected overlap constructions without a new source-level reason",
            "source_artifact": "tdc_monetary_bank_liquid_source_review.csv",
            "current_repo_stance": "rejected",
            "recommended_action": "keep_rejected",
            "details": str(review.get("rejected_candidate_reason") or "n/a"),
            "row_type": "check",
        },
        {
            "latest_quarter": latest_quarter,
            "candidate_key": "loaded_additive_liability_context",
            "check_name": "residual_after_loaded_context",
            "status": "fail" if pd.notna(residual_after_context) and float(residual_after_context) > 0 else "pass",
            "passes_for_next_stage": False,
            "passes_for_publication": False,
            "blocking_issue_type": "material_unexplained_residual",
            "metric_name": "residual_after_loaded_additive_liability_context_mil",
            "metric_value": residual_after_context,
            "threshold_or_rule": "if material residual remains after nonbank bridge plus large time, current public source coverage is still incomplete",
            "source_artifact": "tdc_monetary_bank_liquid_source_review.csv",
            "current_repo_stance": "additive_context_incomplete",
            "recommended_action": "keep_perimeter_stress_test_boundary",
            "details": "The additive loaded-liability context is useful, but does not resolve the wedge on its own.",
            "row_type": "check",
        },
        {
            "latest_quarter": latest_quarter,
            "candidate_key": "summary",
            "check_name": "overall_stop_decision",
            "status": "stop_at_perimeter_stress_test"
            if not has_clean_bank_only
            else "reassess_for_next_stage",
            "passes_for_next_stage": has_clean_bank_only,
            "passes_for_publication": has_clean_bank_only,
            "blocking_issue_type": "source_boundary" if not has_clean_bank_only else "none",
            "metric_name": "loaded_additive_liability_context_share_of_wedge",
            "metric_value": additive_context_share,
            "threshold_or_rule": "without a clean bank-only liquid subcomponent family, the commercial-bank target remains a perimeter stress test",
            "source_artifact": "tdc_monetary_bank_liquid_source_review.csv",
            "current_repo_stance": str(review.get("recommendation_status") or "n/a"),
            "recommended_action": "keep_current_context_boundary" if not has_clean_bank_only else "reassess_context_boundary",
            "details": str(review.get("review_rationale") or "n/a"),
            "row_type": "summary",
        },
    ]

    return pd.DataFrame(rows)


def render_monetary_bank_liquid_stop_gate_markdown(gate: pd.DataFrame) -> str:
    title = "# Monetary Bank Liquid Stop Gate"
    intro = (
        "Explicit gate for the bank-only liquid-deposit branch. "
        "This artifact turns the current source boundary into check-level pass/fail rows plus one overall stop decision."
    )
    if gate.empty:
        return "\n".join([title, "", intro, "", "No monetary bank liquid stop gate is available."])

    summary_row = gate[gate["row_type"] == "summary"].iloc[0]
    summary = (
        f"Latest quarter: {summary_row['latest_quarter']}. "
        f"Overall decision: {summary_row['status']}. "
        f"Recommended action: {summary_row['recommended_action']}. "
        f"Current stance: {summary_row['current_repo_stance']}."
    )

    header = [
        "| Quarter | Candidate | Check | Status | Passes next stage? | Passes publication? | Blocking issue | Metric | Value | Rule | Stance | Recommended action | Details |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    rows: list[str] = []
    for _, row in gate.iterrows():
        metric_value = row.get("metric_value")
        metric_name = str(row.get("metric_name") or "n/a")
        if metric_name.endswith("_share_of_wedge") and pd.notna(metric_value):
            metric_render = _format_millions(float(metric_value) * 100)
        elif metric_name.startswith("has_") and pd.notna(metric_value):
            metric_render = _format_millions(metric_value)
        else:
            metric_render = _format_millions(metric_value)

        rows.append(
            "| "
            + " | ".join(
                [
                    str(row["latest_quarter"]),
                    str(row["candidate_key"]),
                    str(row["check_name"]),
                    str(row["status"]),
                    str(bool(row["passes_for_next_stage"])),
                    str(bool(row["passes_for_publication"])),
                    str(row["blocking_issue_type"]),
                    metric_name,
                    metric_render,
                    str(row["threshold_or_rule"]),
                    str(row["current_repo_stance"]),
                    str(row["recommended_action"]),
                    str(row["details"]),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- The overall decision should stay at `stop_at_perimeter_stress_test` unless a clean current public bank-only liquid subcomponent family becomes available.",
        "- Broad context and rejected-overlap checks are included as guardrails so the repo does not silently promote weak constructions.",
    ]

    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_monetary_bank_liquid_stop_gate(
    *,
    monetary_bank_liquid_source_review: pd.DataFrame,
    monetary_bank_perimeter_gap_review: pd.DataFrame,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    gate = build_monetary_bank_liquid_stop_gate(
        bank_liquid_source_review=monetary_bank_liquid_source_review,
        perimeter_gap_review=monetary_bank_perimeter_gap_review,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    gate.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_monetary_bank_liquid_stop_gate_markdown(gate), encoding="utf-8")

    return csv_path, markdown_path, gate
