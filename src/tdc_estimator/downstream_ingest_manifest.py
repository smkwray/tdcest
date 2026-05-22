from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


MANIFEST_COLUMNS = [
    "artifact_key",
    "artifact_path",
    "artifact_format",
    "ingest_priority",
    "stability_class",
    "consumption_mode",
    "recommended_for",
    "primary_key_field",
    "core_fields",
    "binding_boundary",
    "latest_reference_date",
    "summary_note",
]


def _get_row(frame: pd.DataFrame | None, key_col: str, key: str) -> pd.Series:
    if frame is None or frame.empty or key_col not in frame.columns:
        return pd.Series(dtype="object")
    subset = frame.loc[frame[key_col].eq(key)]
    if subset.empty:
        return pd.Series(dtype="object")
    return subset.iloc[0]


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    return str(value)


def build_downstream_ingest_manifest(
    *,
    downstream_estimator_contract: pd.DataFrame | None,
    downstream_deposit_effect_use_case_review: pd.DataFrame | None,
    downstream_problem_variable_review: pd.DataFrame | None,
    fiscal_receipt_boundary_review: pd.DataFrame | None,
    project_goal_status_review: pd.DataFrame | None,
    receipt_unblock_status: pd.DataFrame | None,
    downstream_deposit_effect_series_panel: pd.DataFrame | None,
    downstream_deposit_effect_comparison_panel: pd.DataFrame | None,
) -> pd.DataFrame:
    contract = downstream_estimator_contract.copy() if downstream_estimator_contract is not None else pd.DataFrame()
    use_cases = (
        downstream_deposit_effect_use_case_review.copy()
        if downstream_deposit_effect_use_case_review is not None
        else pd.DataFrame()
    )
    problems = (
        downstream_problem_variable_review.copy()
        if downstream_problem_variable_review is not None
        else pd.DataFrame()
    )
    receipt_boundary = (
        fiscal_receipt_boundary_review.copy() if fiscal_receipt_boundary_review is not None else pd.DataFrame()
    )
    goals = project_goal_status_review.copy() if project_goal_status_review is not None else pd.DataFrame()
    unblock = receipt_unblock_status.copy() if receipt_unblock_status is not None else pd.DataFrame()
    series_panel = (
        downstream_deposit_effect_series_panel.copy()
        if downstream_deposit_effect_series_panel is not None
        else pd.DataFrame()
    )
    comparison_panel = (
        downstream_deposit_effect_comparison_panel.copy()
        if downstream_deposit_effect_comparison_panel is not None
        else pd.DataFrame()
    )

    bank_goal = _get_row(goals, "goal_key", "bank_receipts")
    row_goal = _get_row(goals, "goal_key", "row_receipts")
    fiscal_goal = _get_row(goals, "goal_key", "fiscal_flow_tdc_equation")
    row_branch = _get_row(unblock, "branch_key", "row_mrv_cbsp_primary")
    bank_branch = _get_row(unblock, "branch_key", "bank_table51_current_window")
    current_headline = _get_row(use_cases, "use_case_key", "current_quarter_bank_only_headline")
    historical_backtest = _get_row(use_cases, "use_case_key", "historical_bank_receipt_backtest")
    row_sensitivity = _get_row(use_cases, "use_case_key", "current_row_receipt_sensitivity")
    perimeter_use = _get_row(use_cases, "use_case_key", "deposit_perimeter_comparison")
    monetary_use = _get_row(use_cases, "use_case_key", "monetary_crosscheck_and_problem_variable_audit")

    latest_series_date = (
        pd.to_datetime(series_panel["date"], errors="coerce").max()
        if not series_panel.empty and "date" in series_panel.columns
        else pd.NaT
    )
    latest_comparison_date = (
        pd.to_datetime(comparison_panel["date"], errors="coerce").max()
        if not comparison_panel.empty and "date" in comparison_panel.columns
        else pd.NaT
    )

    rows = [
        {
            "artifact_key": "tdc_downstream_handoff_bundle",
            "artifact_path": "data/processed/tdc_downstream_handoff_bundle.json",
            "artifact_format": "json",
            "ingest_priority": 1,
            "stability_class": "primary_entrypoint",
            "consumption_mode": "ingest_first",
            "recommended_for": "any downstream repo that wants one stable backend entrypoint",
            "primary_key_field": "bundle sections keyed by goal_key / branch_key / artifact_key / use_case_key",
            "core_fields": "summary;goal_status;receipt_unblock_status;estimator_contract;use_cases;receipt_boundaries;problem_variables;series_panel;comparison_panel",
            "binding_boundary": "receipt-side default boundaries remain active inside the bundled sections",
            "latest_reference_date": latest_series_date,
            "summary_note": "Single-file downstream handoff package. Prefer this first, then inspect the source tables only when more detail is needed.",
        },
        {
            "artifact_key": "tdc_downstream_estimator_contract",
            "artifact_path": "data/processed/tdc_downstream_estimator_contract.csv",
            "artifact_format": "csv",
            "ingest_priority": 2,
            "stability_class": "primary_contract",
            "consumption_mode": "ingest_early",
            "recommended_for": "selecting the right estimator or diagnostic surface for each downstream question",
            "primary_key_field": "artifact_key",
            "core_fields": "current_role;default_classification;best_downstream_use;binding_blocker;main_known_boundary;latest_reference_date;latest_value_millions",
            "binding_boundary": _stringify(current_headline.get("binding_boundary")),
            "latest_reference_date": _stringify(current_headline.get("primary_latest_reference_date")),
            "summary_note": "Main backend contract for which estimator or diagnostic surface should be treated as primary, bounded, or diagnostic-only.",
        },
        {
            "artifact_key": "tdc_downstream_deposit_effect_use_case_review",
            "artifact_path": "data/processed/tdc_downstream_deposit_effect_use_case_review.csv",
            "artifact_format": "csv",
            "ingest_priority": 3,
            "stability_class": "primary_router",
            "consumption_mode": "ingest_early",
            "recommended_for": "routing each downstream question to the right artifact and comparison pair",
            "primary_key_field": "use_case_key",
            "core_fields": "primary_artifact_key;comparison_artifact_key;readiness_status;dominant_problem_variable_family;binding_boundary",
            "binding_boundary": _stringify(current_headline.get("binding_boundary")),
            "latest_reference_date": _stringify(current_headline.get("primary_latest_reference_date")),
            "summary_note": "Question-to-artifact router. Use this before writing downstream analysis code.",
        },
        {
            "artifact_key": "tdc_downstream_problem_variable_review",
            "artifact_path": "data/processed/tdc_downstream_problem_variable_review.csv",
            "artifact_format": "csv",
            "ingest_priority": 4,
            "stability_class": "primary_risk_map",
            "consumption_mode": "ingest_early",
            "recommended_for": "finding the variables and boundary cells most likely to distort downstream interpretation",
            "primary_key_field": "variable_key",
            "core_fields": "variable_family;included_in_live_headline;evidence_grade;dominant_in_gap_keys;binding_boundary;interpretation_risk",
            "binding_boundary": "Treasury interest-cleanup terms dominate the live ladder wedge; receipt boundaries dominate current receipt cells",
            "latest_reference_date": latest_series_date,
            "summary_note": "Problem-variable map. Use this to separate real live cleanup terms from blocked receipt cells and perimeter-only wedges.",
        },
        {
            "artifact_key": "tdc_fiscal_receipt_boundary_review",
            "artifact_path": "data/processed/tdc_fiscal_receipt_boundary_review.csv",
            "artifact_format": "csv",
            "ingest_priority": 5,
            "stability_class": "primary_boundary_map",
            "consumption_mode": "ingest_early",
            "recommended_for": "understanding which live receipt cells are missing/not measured, historical overlays, bounded pilots, or benchmarks",
            "primary_key_field": "boundary_key",
            "core_fields": "receipt_family;current_repo_role;included_in_live_tier3_headline;binding_blocker;downstream_use",
            "binding_boundary": _stringify(fiscal_goal.get("binding_blocker")),
            "latest_reference_date": _stringify(fiscal_goal.get("latest_relevant_date")),
            "summary_note": "Fiscal-shell receipt boundary surface. Essential for not misreading live zero cells as empirical zero flows.",
        },
        {
            "artifact_key": "tdc_downstream_deposit_effect_series_panel",
            "artifact_path": "data/processed/tdc_downstream_deposit_effect_series_panel.csv",
            "artifact_format": "csv",
            "ingest_priority": 6,
            "stability_class": "primary_time_series",
            "consumption_mode": "ingest_after_contract",
            "recommended_for": "time-series analysis of the main bank-only, broad-depository, historical-bank, and MRV pilot surfaces",
            "primary_key_field": "series_key + date",
            "core_fields": "value_millions;historical_only;nondefault_only;latest_nonzero_date;latest_nonzero_value_millions",
            "binding_boundary": _stringify(bank_goal.get("binding_blocker")) + ";" + _stringify(row_goal.get("binding_blocker")),
            "latest_reference_date": latest_series_date,
            "summary_note": "Quarterly panel for downstream modeling. Latest-nonzero support fields keep sparse MRV quarters interpretable.",
        },
        {
            "artifact_key": "tdc_downstream_deposit_effect_comparison_panel",
            "artifact_path": "data/processed/tdc_downstream_deposit_effect_comparison_panel.csv",
            "artifact_format": "csv",
            "ingest_priority": 7,
            "stability_class": "primary_comparison_panel",
            "consumption_mode": "ingest_after_contract",
            "recommended_for": "quarterly wedge analysis between base/Tier2/Tier3, bank-only/broad-depository, historical bank overlays, and MRV pilot deltas",
            "primary_key_field": "comparison_key + date",
            "core_fields": "net_delta_millions;historical_only;nondefault_only;latest_nonzero_date;latest_nonzero_value_millions",
            "binding_boundary": _stringify(bank_branch.get("binding_blocker")) + ";" + _stringify(row_branch.get("binding_blocker")),
            "latest_reference_date": latest_comparison_date,
            "summary_note": "Quarterly delta panel. Use this with the series panel when studying which wedges actually move the downstream deposit story.",
        },
        {
            "artifact_key": "tdc_downstream_estimator_gap_review",
            "artifact_path": "data/processed/tdc_downstream_estimator_gap_review.csv",
            "artifact_format": "csv",
            "ingest_priority": 8,
            "stability_class": "diagnostic_latest_gap",
            "consumption_mode": "context_then_drill_down",
            "recommended_for": "latest-quarter or latest-historical wedge diagnosis before doing longer panel work",
            "primary_key_field": "gap_key",
            "core_fields": "net_delta_millions;dominant_component_key;dominant_component_family;secondary_component_key",
            "binding_boundary": _stringify(current_headline.get("binding_boundary")),
            "latest_reference_date": latest_comparison_date,
            "summary_note": "Latest-gap summary. Faster to read than the full comparison panel, but not a substitute for it.",
        },
        {
            "artifact_key": "tdc_downstream_component_contribution_review",
            "artifact_path": "data/processed/tdc_downstream_component_contribution_review.csv",
            "artifact_format": "csv",
            "ingest_priority": 9,
            "stability_class": "diagnostic_component_breakout",
            "consumption_mode": "context_then_drill_down",
            "recommended_for": "additive component decomposition inside the main live and historical scenarios",
            "primary_key_field": "scenario_key + component_key",
            "core_fields": "component_family;signed_contribution_millions;share_of_absolute_estimator;inclusion_role;boundary_note",
            "binding_boundary": _stringify(current_headline.get("binding_boundary")),
            "latest_reference_date": latest_series_date,
            "summary_note": "Long-form additive breakout. Use when the downstream repo needs component-level attribution rather than estimator-level routing.",
        },
        {
            "artifact_key": "tdc_project_goal_status_review",
            "artifact_path": "data/processed/tdc_project_goal_status_review.csv",
            "artifact_format": "csv",
            "ingest_priority": 10,
            "stability_class": "context_status",
            "consumption_mode": "context_only",
            "recommended_for": "top-line status framing across transfers, receipts, fiscal shell, and monetary branch",
            "primary_key_field": "goal_key",
            "core_fields": "current_status;current_role;binding_blocker;next_finite_push",
            "binding_boundary": _stringify(fiscal_goal.get("binding_blocker")),
            "latest_reference_date": _stringify(fiscal_goal.get("latest_relevant_date")),
            "summary_note": "Repo-level goal summary. Useful for orientation, but not the main ingest surface.",
        },
        {
            "artifact_key": "tdc_receipt_unblock_status",
            "artifact_path": "data/processed/tdc_receipt_unblock_status.csv",
            "artifact_format": "csv",
            "ingest_priority": 11,
            "stability_class": "context_boundary_tracker",
            "consumption_mode": "context_only",
            "recommended_for": "branch-level receipt status and external-research targeting",
            "primary_key_field": "branch_key",
            "core_fields": "promotion_boundary;binding_blocker;missing_source_families;best_local_next_action",
            "binding_boundary": _stringify(bank_branch.get("binding_blocker")) + ";" + _stringify(row_branch.get("binding_blocker")),
            "latest_reference_date": _stringify(bank_branch.get("latest_relevant_date")),
            "summary_note": "Receipt-side branch tracker. Useful for closeout and audit, but downstream repos should usually consume the boundary review and handoff bundle first.",
        },
        {
            "artifact_key": "tdc_backend_closeout_review",
            "artifact_path": "data/processed/tdc_backend_closeout_review.csv",
            "artifact_format": "csv",
            "ingest_priority": 12,
            "stability_class": "closeout_context",
            "consumption_mode": "context_only",
            "recommended_for": "final freeze / bounded-push / monitor decisions once the downstream contract layer is already in place",
            "primary_key_field": "review_key",
            "core_fields": "current_state;release_readiness;binding_boundary;next_action;stop_rule",
            "binding_boundary": _stringify(bank_branch.get("binding_blocker")) + ";" + _stringify(row_branch.get("binding_blocker")),
            "latest_reference_date": _stringify(fiscal_goal.get("latest_relevant_date")),
            "summary_note": "Backend closeout surface. Use this after the main handoff/contract layers when deciding whether a branch should stay frozen, bounded, or actively pushed.",
        },
        {
            "artifact_key": "tdc_tier3_research_comparison",
            "artifact_path": "data/processed/tdc_tier3_research_comparison.csv",
            "artifact_format": "csv",
            "ingest_priority": 13,
            "stability_class": "bounded_research_context",
            "consumption_mode": "context_only",
            "recommended_for": "quick live-versus-historical Tier 2/Tier 3 comparisons around the bank receipt overlay",
            "primary_key_field": "comparison_key",
            "core_fields": "reference_date;tier2_bank_only_mil;tier3_bank_only_mil;historical_bank_receipt_variant_mil;current_row_mrv_pilot_latest_date",
            "binding_boundary": _stringify(historical_backtest.get("binding_boundary")),
            "latest_reference_date": _stringify(historical_backtest.get("primary_latest_reference_date")),
            "summary_note": "Useful compact context table, but downstream repos should prefer the formal contract and panels.",
        },
        {
            "artifact_key": "tdc_workstream_end_state_map",
            "artifact_path": "data/processed/tdc_workstream_end_state_map.csv",
            "artifact_format": "csv",
            "ingest_priority": 14,
            "stability_class": "closeout_context",
            "consumption_mode": "context_only",
            "recommended_for": "freeze / bounded-push / monitor decisions inside this repo",
            "primary_key_field": "workstream_key",
            "core_fields": "current_state;end_state_target;binding_blocker;next_finite_push",
            "binding_boundary": _stringify(row_goal.get("binding_blocker")),
            "latest_reference_date": "",
            "summary_note": "Useful for repo management and audit, not a primary downstream ingest surface.",
        },
    ]

    frame = pd.DataFrame(rows)
    if "latest_reference_date" in frame.columns:
        frame["latest_reference_date"] = pd.to_datetime(frame["latest_reference_date"], errors="coerce")
    return frame.reindex(columns=MANIFEST_COLUMNS)


def render_downstream_ingest_manifest_markdown(frame: pd.DataFrame) -> str:
    title = "# Downstream Ingest Manifest"
    intro = (
        "Priority-ordered ingest manifest for downstream repos. It tells a consuming project which backend artifacts to read first, "
        "which ones are primary versus bounded versus diagnostic, and which ones are context only."
    )
    if frame.empty:
        return "\n".join([title, "", intro, "", "No downstream ingest-manifest rows are available."])

    lines = [
        title,
        "",
        intro,
        "",
        "| Artifact | Priority | Stability | Consumption mode | Format | Recommended for |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for _, row in frame.sort_values("ingest_priority").iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["artifact_key"]),
                    str(row["ingest_priority"]),
                    str(row["stability_class"]),
                    str(row["consumption_mode"]),
                    str(row["artifact_format"]),
                    str(row["recommended_for"]),
                ]
            )
            + " |"
        )

    return "\n".join(lines + [""])


def write_downstream_ingest_manifest(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    downstream_estimator_contract: pd.DataFrame | None,
    downstream_deposit_effect_use_case_review: pd.DataFrame | None,
    downstream_problem_variable_review: pd.DataFrame | None,
    fiscal_receipt_boundary_review: pd.DataFrame | None,
    project_goal_status_review: pd.DataFrame | None,
    receipt_unblock_status: pd.DataFrame | None,
    downstream_deposit_effect_series_panel: pd.DataFrame | None,
    downstream_deposit_effect_comparison_panel: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    frame = build_downstream_ingest_manifest(
        downstream_estimator_contract=downstream_estimator_contract,
        downstream_deposit_effect_use_case_review=downstream_deposit_effect_use_case_review,
        downstream_problem_variable_review=downstream_problem_variable_review,
        fiscal_receipt_boundary_review=fiscal_receipt_boundary_review,
        project_goal_status_review=project_goal_status_review,
        receipt_unblock_status=receipt_unblock_status,
        downstream_deposit_effect_series_panel=downstream_deposit_effect_series_panel,
        downstream_deposit_effect_comparison_panel=downstream_deposit_effect_comparison_panel,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_downstream_ingest_manifest_markdown(frame), encoding="utf-8")

    return csv_path, markdown_path, frame
