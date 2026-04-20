from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


REVIEW_COLUMNS = [
    "check_key",
    "check_group",
    "status",
    "lhs_source",
    "rhs_source",
    "lhs_value",
    "rhs_value",
    "comparison_basis",
    "summary_note",
]


def _get_row(frame: pd.DataFrame | None, key_col: str, key: str) -> pd.Series:
    if frame is None or frame.empty or key_col not in frame.columns:
        return pd.Series(dtype="object")
    subset = frame.loc[frame[key_col].eq(key)]
    if subset.empty:
        return pd.Series(dtype="object")
    return subset.iloc[0]


def _get_latest_row(frame: pd.DataFrame | None, key_col: str, key: str, date_col: str) -> pd.Series:
    if frame is None or frame.empty or key_col not in frame.columns or date_col not in frame.columns:
        return pd.Series(dtype="object")
    subset = frame.loc[frame[key_col].eq(key)].copy()
    if subset.empty:
        return pd.Series(dtype="object")
    subset[date_col] = pd.to_datetime(subset[date_col], errors="coerce")
    subset = subset.sort_values(date_col)
    return subset.iloc[-1]


def _norm_date(value: Any) -> str:
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


def _norm_num(value: Any) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return None
    return float(parsed)


def _equal_num(lhs: Any, rhs: Any, tol: float = 1e-9) -> bool:
    lhs_num = _norm_num(lhs)
    rhs_num = _norm_num(rhs)
    if lhs_num is None and rhs_num is None:
        return True
    if lhs_num is None or rhs_num is None:
        return False
    return abs(lhs_num - rhs_num) <= tol


def _header_set(frame: pd.DataFrame | None) -> set[str]:
    if frame is None:
        return set()
    return set(str(column) for column in frame.columns)


def _record_map_header_set(records: Any) -> set[str]:
    if not isinstance(records, dict) or not records:
        return set()
    first = next(iter(records.values()))
    if not isinstance(first, dict):
        return set()
    return set(str(key) for key in first.keys())


def build_downstream_consistency_review(
    *,
    downstream_handoff_bundle: dict[str, Any] | None,
    downstream_ingest_manifest: pd.DataFrame | None,
    downstream_estimator_contract: pd.DataFrame | None,
    downstream_deposit_effect_use_case_review: pd.DataFrame | None,
    downstream_deposit_effect_series_panel: pd.DataFrame | None,
    downstream_deposit_effect_comparison_panel: pd.DataFrame | None,
    downstream_estimator_gap_review: pd.DataFrame | None = None,
    downstream_component_contribution_review: pd.DataFrame | None = None,
    downstream_problem_variable_review: pd.DataFrame | None = None,
    fiscal_receipt_boundary_review: pd.DataFrame | None = None,
    receipt_unblock_status: pd.DataFrame | None = None,
    project_goal_status_review: pd.DataFrame | None = None,
    backend_closeout_review: pd.DataFrame | None = None,
    tier3_research_comparison: pd.DataFrame | None = None,
    workstream_end_state_map: pd.DataFrame | None = None,
) -> pd.DataFrame:
    bundle = downstream_handoff_bundle or {}
    summary = bundle.get("summary", {})
    manifest = downstream_ingest_manifest.copy() if downstream_ingest_manifest is not None else pd.DataFrame()
    contract = downstream_estimator_contract.copy() if downstream_estimator_contract is not None else pd.DataFrame()
    use_cases = (
        downstream_deposit_effect_use_case_review.copy()
        if downstream_deposit_effect_use_case_review is not None
        else pd.DataFrame()
    )
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
    gap_review = (
        downstream_estimator_gap_review.copy()
        if downstream_estimator_gap_review is not None
        else pd.DataFrame()
    )
    contribution_review = (
        downstream_component_contribution_review.copy()
        if downstream_component_contribution_review is not None
        else pd.DataFrame()
    )
    problem_review = (
        downstream_problem_variable_review.copy()
        if downstream_problem_variable_review is not None
        else pd.DataFrame()
    )
    receipt_boundaries = (
        fiscal_receipt_boundary_review.copy()
        if fiscal_receipt_boundary_review is not None
        else pd.DataFrame()
    )
    receipt_unblock = receipt_unblock_status.copy() if receipt_unblock_status is not None else pd.DataFrame()
    goal_status = project_goal_status_review.copy() if project_goal_status_review is not None else pd.DataFrame()
    closeout_review = backend_closeout_review.copy() if backend_closeout_review is not None else pd.DataFrame()
    research_comparison = (
        tier3_research_comparison.copy()
        if tier3_research_comparison is not None
        else pd.DataFrame()
    )
    workstreams = workstream_end_state_map.copy() if workstream_end_state_map is not None else pd.DataFrame()

    current_contract = _get_row(contract, "artifact_key", "tdc_tier3_fiscal_corrected_bank_only_ru_flow")
    historical_contract = _get_row(contract, "artifact_key", "bank_receipt_historical_default_view")
    row_mrv_contract = _get_row(contract, "artifact_key", "row_mrv_primary_nondefault_pilot")
    row_use_case = _get_row(use_cases, "use_case_key", "current_row_receipt_sensitivity")
    current_use_case = _get_row(use_cases, "use_case_key", "current_quarter_bank_only_headline")

    latest_mrv_series = pd.Series(dtype="object")
    if not series_panel.empty and "series_key" in series_panel.columns:
        subset = series_panel.loc[series_panel["series_key"].eq("row_mrv_primary_nondefault_pilot_series")]
        if not subset.empty:
            subset = subset.copy()
            subset["date"] = pd.to_datetime(subset["date"], errors="coerce")
            subset = subset.sort_values("date")
            latest_mrv_series = subset.iloc[-1]

    latest_mrv_comparison = pd.Series(dtype="object")
    if not comparison_panel.empty and "comparison_key" in comparison_panel.columns:
        subset = comparison_panel.loc[
            comparison_panel["comparison_key"].eq("row_mrv_nondefault_pilot_minus_live_zero")
        ]
        if not subset.empty:
            subset = subset.copy()
            subset["date"] = pd.to_datetime(subset["date"], errors="coerce")
            subset = subset.sort_values("date")
            latest_mrv_comparison = subset.iloc[-1]

    rows = []

    top_manifest = manifest.sort_values("ingest_priority").iloc[0] if not manifest.empty else pd.Series(dtype="object")
    rows.append(
        {
            "check_key": "manifest_primary_entrypoint",
            "check_group": "manifest",
            "status": "pass" if str(top_manifest.get("artifact_key")) == "tdc_downstream_handoff_bundle" else "fail",
            "lhs_source": "tdc_downstream_ingest_manifest",
            "rhs_source": "expected_primary_entrypoint",
            "lhs_value": top_manifest.get("artifact_key"),
            "rhs_value": "tdc_downstream_handoff_bundle",
            "comparison_basis": "artifact_key equality at lowest ingest_priority",
            "summary_note": "The ingest manifest should always put the handoff bundle first.",
        }
    )

    rows.append(
        {
            "check_key": "handoff_current_headline_date",
            "check_group": "handoff_vs_contract",
            "status": "pass"
            if _norm_date(summary.get("current_bank_headline_latest_date"))
            == _norm_date(current_contract.get("latest_reference_date"))
            else "fail",
            "lhs_source": "tdc_downstream_handoff_bundle.summary",
            "rhs_source": "tdc_downstream_estimator_contract",
            "lhs_value": summary.get("current_bank_headline_latest_date"),
            "rhs_value": current_contract.get("latest_reference_date"),
            "comparison_basis": "normalized date equality",
            "summary_note": "Handoff summary should match the contract on current bank headline date.",
        }
    )
    rows.append(
        {
            "check_key": "handoff_current_headline_value",
            "check_group": "handoff_vs_contract",
            "status": "pass"
            if _equal_num(summary.get("current_bank_headline_latest_value_millions"), current_contract.get("latest_value_millions"))
            else "fail",
            "lhs_source": "tdc_downstream_handoff_bundle.summary",
            "rhs_source": "tdc_downstream_estimator_contract",
            "lhs_value": summary.get("current_bank_headline_latest_value_millions"),
            "rhs_value": current_contract.get("latest_value_millions"),
            "comparison_basis": "numeric equality",
            "summary_note": "Handoff summary should match the contract on current bank headline value.",
        }
    )
    rows.append(
        {
            "check_key": "handoff_historical_overlay_date",
            "check_group": "handoff_vs_contract",
            "status": "pass"
            if _norm_date(summary.get("historical_bank_overlay_latest_date"))
            == _norm_date(historical_contract.get("latest_reference_date"))
            else "fail",
            "lhs_source": "tdc_downstream_handoff_bundle.summary",
            "rhs_source": "tdc_downstream_estimator_contract",
            "lhs_value": summary.get("historical_bank_overlay_latest_date"),
            "rhs_value": historical_contract.get("latest_reference_date"),
            "comparison_basis": "normalized date equality",
            "summary_note": "Handoff summary should match the contract on historical bank overlay date.",
        }
    )
    rows.append(
        {
            "check_key": "handoff_historical_overlay_value",
            "check_group": "handoff_vs_contract",
            "status": "pass"
            if _equal_num(summary.get("historical_bank_overlay_latest_value_millions"), historical_contract.get("latest_value_millions"))
            else "fail",
            "lhs_source": "tdc_downstream_handoff_bundle.summary",
            "rhs_source": "tdc_downstream_estimator_contract",
            "lhs_value": summary.get("historical_bank_overlay_latest_value_millions"),
            "rhs_value": historical_contract.get("latest_value_millions"),
            "comparison_basis": "numeric equality",
            "summary_note": "Handoff summary should match the contract on historical bank overlay value.",
        }
    )

    rows.append(
        {
            "check_key": "contract_row_mrv_latest_nonzero_date",
            "check_group": "contract_vs_handoff",
            "status": "pass"
            if _norm_date(row_mrv_contract.get("latest_reference_date"))
            == _norm_date(summary.get("row_mrv_latest_date"))
            else "fail",
            "lhs_source": "tdc_downstream_estimator_contract",
            "rhs_source": "tdc_downstream_handoff_bundle.summary",
            "lhs_value": row_mrv_contract.get("latest_reference_date"),
            "rhs_value": summary.get("row_mrv_latest_date"),
            "comparison_basis": "normalized latest_nonzero_date equality",
            "summary_note": "MRV contract row should match the handoff bundle on latest supported date.",
        }
    )
    rows.append(
        {
            "check_key": "contract_row_mrv_latest_nonzero_value",
            "check_group": "contract_vs_handoff",
            "status": "pass"
            if _equal_num(row_mrv_contract.get("latest_value_millions"), summary.get("row_mrv_latest_value_millions"))
            else "fail",
            "lhs_source": "tdc_downstream_estimator_contract",
            "rhs_source": "tdc_downstream_handoff_bundle.summary",
            "lhs_value": row_mrv_contract.get("latest_value_millions"),
            "rhs_value": summary.get("row_mrv_latest_value_millions"),
            "comparison_basis": "numeric latest_nonzero_value equality",
            "summary_note": "MRV contract row should match the handoff bundle on latest supported value.",
        }
    )

    rows.append(
        {
            "check_key": "handoff_row_mrv_latest_nonzero_date",
            "check_group": "handoff_vs_panels",
            "status": "pass"
            if _norm_date(summary.get("row_mrv_latest_date"))
            == _norm_date(latest_mrv_series.get("latest_nonzero_date"))
            else "fail",
            "lhs_source": "tdc_downstream_handoff_bundle.summary",
            "rhs_source": "tdc_downstream_deposit_effect_series_panel",
            "lhs_value": summary.get("row_mrv_latest_date"),
            "rhs_value": latest_mrv_series.get("latest_nonzero_date"),
            "comparison_basis": "normalized latest_nonzero_date equality",
            "summary_note": "Handoff summary should use the latest nonzero MRV support date rather than a sparse zero quarter.",
        }
    )
    rows.append(
        {
            "check_key": "handoff_row_mrv_latest_nonzero_value",
            "check_group": "handoff_vs_panels",
            "status": "pass"
            if _equal_num(summary.get("row_mrv_latest_value_millions"), latest_mrv_series.get("latest_nonzero_value_millions"))
            else "fail",
            "lhs_source": "tdc_downstream_handoff_bundle.summary",
            "rhs_source": "tdc_downstream_deposit_effect_series_panel",
            "lhs_value": summary.get("row_mrv_latest_value_millions"),
            "rhs_value": latest_mrv_series.get("latest_nonzero_value_millions"),
            "comparison_basis": "numeric latest_nonzero_value equality",
            "summary_note": "Handoff summary should use the same latest nonzero MRV support value as the series panel.",
        }
    )
    rows.append(
        {
            "check_key": "mrv_series_vs_comparison_latest_nonzero_date",
            "check_group": "panel_consistency",
            "status": "pass"
            if _norm_date(latest_mrv_series.get("latest_nonzero_date"))
            == _norm_date(latest_mrv_comparison.get("latest_nonzero_date"))
            else "fail",
            "lhs_source": "tdc_downstream_deposit_effect_series_panel",
            "rhs_source": "tdc_downstream_deposit_effect_comparison_panel",
            "lhs_value": latest_mrv_series.get("latest_nonzero_date"),
            "rhs_value": latest_mrv_comparison.get("latest_nonzero_date"),
            "comparison_basis": "normalized latest_nonzero_date equality",
            "summary_note": "MRV latest nonzero support date should agree between the series and comparison panels.",
        }
    )
    rows.append(
        {
            "check_key": "mrv_series_vs_comparison_latest_nonzero_value",
            "check_group": "panel_consistency",
            "status": "pass"
            if _equal_num(latest_mrv_series.get("latest_nonzero_value_millions"), latest_mrv_comparison.get("latest_nonzero_value_millions"))
            else "fail",
            "lhs_source": "tdc_downstream_deposit_effect_series_panel",
            "rhs_source": "tdc_downstream_deposit_effect_comparison_panel",
            "lhs_value": latest_mrv_series.get("latest_nonzero_value_millions"),
            "rhs_value": latest_mrv_comparison.get("latest_nonzero_value_millions"),
            "comparison_basis": "numeric latest_nonzero_value equality",
            "summary_note": "MRV latest nonzero support value should agree between the series and comparison panels.",
        }
    )

    current_primary = str(current_use_case.get("primary_artifact_key"))
    rows.append(
        {
            "check_key": "use_case_current_headline_primary_exists_in_contract",
            "check_group": "use_case_vs_contract",
            "status": "pass" if not contract.empty and contract["artifact_key"].eq(current_primary).any() else "fail",
            "lhs_source": "tdc_downstream_deposit_effect_use_case_review",
            "rhs_source": "tdc_downstream_estimator_contract",
            "lhs_value": current_primary,
            "rhs_value": "artifact exists in contract",
            "comparison_basis": "artifact_key membership",
            "summary_note": "Use-case router should point only to artifacts declared in the estimator contract.",
        }
    )
    row_primary = str(row_use_case.get("primary_artifact_key"))
    rows.append(
        {
            "check_key": "use_case_row_mrv_primary_exists_in_contract",
            "check_group": "use_case_vs_contract",
            "status": "pass" if not contract.empty and contract["artifact_key"].eq(row_primary).any() else "fail",
            "lhs_source": "tdc_downstream_deposit_effect_use_case_review",
            "rhs_source": "tdc_downstream_estimator_contract",
            "lhs_value": row_primary,
            "rhs_value": "artifact exists in contract",
            "comparison_basis": "artifact_key membership",
            "summary_note": "ROW use-case router should point only to artifacts declared in the estimator contract.",
        }
    )

    if not use_cases.empty and "use_case_key" in use_cases.columns:
        for _, use_case in use_cases.iterrows():
            use_case_key = str(use_case.get("use_case_key", "unknown"))
            primary_raw = use_case.get("primary_artifact_key", "")
            comparison_raw = use_case.get("comparison_artifact_key", "")
            primary_artifact = "" if pd.isna(primary_raw) else str(primary_raw)
            comparison_artifact = "" if pd.isna(comparison_raw) else str(comparison_raw)
            if primary_artifact:
                rows.append(
                    {
                        "check_key": f"use_case_{use_case_key}_primary_exists_in_contract",
                        "check_group": "use_case_vs_contract",
                        "status": "pass" if not contract.empty and contract["artifact_key"].eq(primary_artifact).any() else "fail",
                        "lhs_source": "tdc_downstream_deposit_effect_use_case_review",
                        "rhs_source": "tdc_downstream_estimator_contract",
                        "lhs_value": primary_artifact,
                        "rhs_value": "artifact exists in contract",
                        "comparison_basis": "artifact_key membership",
                        "summary_note": "Use-case primary artifacts should be declared in the estimator contract.",
                    }
                )
            if comparison_artifact:
                rows.append(
                    {
                        "check_key": f"use_case_{use_case_key}_comparison_exists_in_contract",
                        "check_group": "use_case_vs_contract",
                        "status": "pass" if not contract.empty and contract["artifact_key"].eq(comparison_artifact).any() else "fail",
                        "lhs_source": "tdc_downstream_deposit_effect_use_case_review",
                        "rhs_source": "tdc_downstream_estimator_contract",
                        "lhs_value": comparison_artifact,
                        "rhs_value": "artifact exists in contract",
                        "comparison_basis": "artifact_key membership",
                        "summary_note": "Use-case comparison artifacts should be declared in the estimator contract.",
                    }
                )

    artifact_headers: dict[str, set[str]] = {
        "tdc_downstream_handoff_bundle": set(bundle.keys()),
        "tdc_downstream_estimator_contract": _header_set(contract),
        "tdc_downstream_deposit_effect_use_case_review": _header_set(use_cases),
        "tdc_downstream_problem_variable_review": _header_set(problem_review),
        "tdc_fiscal_receipt_boundary_review": _header_set(receipt_boundaries),
        "tdc_downstream_deposit_effect_series_panel": _header_set(series_panel),
        "tdc_downstream_deposit_effect_comparison_panel": _header_set(comparison_panel),
        "tdc_downstream_estimator_gap_review": _header_set(gap_review),
        "tdc_downstream_component_contribution_review": _header_set(contribution_review),
        "tdc_project_goal_status_review": _header_set(goal_status),
        "tdc_receipt_unblock_status": _header_set(receipt_unblock),
        "tdc_backend_closeout_review": _header_set(closeout_review),
        "tdc_tier3_research_comparison": _header_set(research_comparison),
        "tdc_workstream_end_state_map": _header_set(workstreams),
    }
    if not manifest.empty and {"artifact_key", "core_fields"}.issubset(manifest.columns):
        for _, manifest_row in manifest.iterrows():
            artifact_key = str(manifest_row.get("artifact_key", ""))
            declared = [field.strip() for field in str(manifest_row.get("core_fields", "")).split(";") if field.strip()]
            headers = artifact_headers.get(artifact_key, set())
            missing = [field for field in declared if field not in headers]
            rows.append(
                {
                    "check_key": f"manifest_{artifact_key}_core_fields_valid",
                    "check_group": "manifest_schema",
                    "status": "pass" if not missing else "fail",
                    "lhs_source": "tdc_downstream_ingest_manifest",
                    "rhs_source": artifact_key,
                    "lhs_value": ";".join(declared),
                    "rhs_value": ";".join(sorted(headers)),
                    "comparison_basis": "declared core_fields subset of actual artifact headers",
                    "summary_note": "Manifest core_fields should only advertise fields that exist in the referenced artifact."
                    if not missing
                    else f"Missing fields: {';'.join(missing)}",
                }
            )

    comparison_map = {
        "latest_live_base_to_tier2_bank_only": "bank_only_tier2_minus_base",
        "latest_live_tier2_to_tier3_bank_only": "bank_only_tier3_minus_tier2",
        "latest_live_bank_to_broad_depository_tier3": "broad_depository_tier3_minus_bank_only_tier3",
        "latest_historical_bank_receipt_overlay": "historical_bank_receipt_candidate_minus_default_tier3",
        "latest_historical_candidate_to_lower_bound": "historical_bank_receipt_candidate_minus_lower_bound",
    }
    if not gap_review.empty and not comparison_panel.empty:
        for gap_key, comparison_key in comparison_map.items():
            gap_row = _get_row(gap_review, "gap_key", gap_key)
            comparison_row = _get_latest_row(comparison_panel, "comparison_key", comparison_key, "date")
            rows.append(
                {
                    "check_key": f"gap_{gap_key}_matches_comparison_panel",
                    "check_group": "gap_vs_panel",
                    "status": "pass"
                    if _norm_date(gap_row.get("reference_date")) == _norm_date(comparison_row.get("date"))
                    and _equal_num(gap_row.get("net_delta_millions"), comparison_row.get("net_delta_millions"))
                    and _equal_num(gap_row.get("lhs_value_millions"), comparison_row.get("lhs_value_millions"))
                    and _equal_num(gap_row.get("rhs_value_millions"), comparison_row.get("rhs_value_millions"))
                    else "fail",
                    "lhs_source": "tdc_downstream_estimator_gap_review",
                    "rhs_source": "tdc_downstream_deposit_effect_comparison_panel",
                    "lhs_value": gap_key,
                    "rhs_value": comparison_key,
                    "comparison_basis": "date, lhs/rhs values, and net delta equality",
                    "summary_note": "Gap-review rows should reconcile to the matching comparison-panel rows.",
                }
            )

    if not contribution_review.empty and {"scenario_key", "signed_contribution_millions", "estimator_value_millions"}.issubset(contribution_review.columns):
        for scenario_key, scenario_frame in contribution_review.groupby("scenario_key"):
            lhs_value = pd.to_numeric(scenario_frame["signed_contribution_millions"], errors="coerce").sum()
            rhs_value = pd.to_numeric(scenario_frame["estimator_value_millions"], errors="coerce").dropna().iloc[0]
            rows.append(
                {
                    "check_key": f"contribution_sum_{scenario_key}",
                    "check_group": "contribution_reconciliation",
                    "status": "pass" if _equal_num(lhs_value, rhs_value) else "fail",
                    "lhs_source": "tdc_downstream_component_contribution_review",
                    "rhs_source": "scenario estimator value",
                    "lhs_value": lhs_value,
                    "rhs_value": rhs_value,
                    "comparison_basis": "sum(signed_contribution_millions) equals estimator_value_millions",
                    "summary_note": "Additive contribution rows should reconcile exactly to the scenario estimator value.",
                }
            )

    if not problem_review.empty and not gap_review.empty:
        perimeter_problem = _get_row(problem_review, "variable_key", "np_credit_unions_tsy_tx")
        perimeter_gap = _get_row(gap_review, "gap_key", "latest_live_bank_to_broad_depository_tier3")
        rows.append(
            {
                "check_key": "problem_variable_np_credit_unions_matches_gap",
                "check_group": "problem_variable_vs_gap",
                "status": "pass"
                if str(perimeter_problem.get("dominant_in_gap_keys", "")).find("latest_live_bank_to_broad_depository_tier3") >= 0
                and _norm_date(perimeter_problem.get("latest_reference_date")) == _norm_date(perimeter_gap.get("reference_date"))
                and _equal_num(perimeter_problem.get("latest_value_millions"), perimeter_gap.get("dominant_component_millions"))
                else "fail",
                "lhs_source": "tdc_downstream_problem_variable_review",
                "rhs_source": "tdc_downstream_estimator_gap_review",
                "lhs_value": perimeter_problem.get("variable_key"),
                "rhs_value": perimeter_gap.get("dominant_component_key"),
                "comparison_basis": "problem-variable key/date/value should match the live broad-depository gap driver",
                "summary_note": "The perimeter problem-variable row should point to the actual current broad-depository wedge driver.",
            }
        )

    research_live = _get_row(research_comparison, "comparison_key", "latest_live_defaults")
    research_hist = _get_row(research_comparison, "comparison_key", "latest_historical_bank_window")
    if not research_comparison.empty:
        for review_key, review_row in [
            ("latest_live_defaults", research_live),
            ("latest_historical_bank_window", research_hist),
        ]:
            carries_mrv_value = _norm_num(review_row.get("current_row_mrv_pilot_mil")) is not None
            rows.append(
                {
                    "check_key": f"research_comparison_{review_key}_mrv_date_present",
                    "check_group": "research_surface",
                    "status": "pass"
                    if (not carries_mrv_value) or _norm_date(review_row.get("current_row_mrv_pilot_latest_date")) != "n/a"
                    else "fail",
                    "lhs_source": "tdc_tier3_research_comparison",
                    "rhs_source": "row_mrv support date",
                    "lhs_value": review_row.get("current_row_mrv_pilot_latest_date"),
                    "rhs_value": "non-null date",
                    "comparison_basis": "compact research surface should carry the MRV support date when it carries an MRV value",
                    "summary_note": "The compact research table should expose the MRV support date alongside the MRV value whenever it carries an MRV pilot value.",
                }
            )

    review = pd.DataFrame(rows)
    return review.reindex(columns=REVIEW_COLUMNS)


def render_downstream_consistency_review_markdown(frame: pd.DataFrame) -> str:
    title = "# Downstream Consistency Review"
    intro = (
        "Compact backend self-audit. It checks whether the handoff bundle, ingest manifest, estimator contract, use-case router, "
        "and panel surfaces still agree on the same primary artifacts, dates, and values."
    )
    if frame.empty:
        return "\n".join([title, "", intro, "", "No downstream consistency checks are available."])

    lines = [
        title,
        "",
        intro,
        "",
        "| Check | Group | Status | LHS source | RHS source | Basis |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in frame.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["check_key"]),
                    str(row["check_group"]),
                    str(row["status"]),
                    str(row["lhs_source"]),
                    str(row["rhs_source"]),
                    str(row["comparison_basis"]),
                ]
            )
            + " |"
        )
    return "\n".join(lines + [""])


def write_downstream_consistency_review(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    downstream_handoff_bundle: dict[str, Any] | None,
    downstream_ingest_manifest: pd.DataFrame | None,
    downstream_estimator_contract: pd.DataFrame | None,
    downstream_deposit_effect_use_case_review: pd.DataFrame | None,
    downstream_deposit_effect_series_panel: pd.DataFrame | None,
    downstream_deposit_effect_comparison_panel: pd.DataFrame | None,
    downstream_estimator_gap_review: pd.DataFrame | None = None,
    downstream_component_contribution_review: pd.DataFrame | None = None,
    downstream_problem_variable_review: pd.DataFrame | None = None,
    fiscal_receipt_boundary_review: pd.DataFrame | None = None,
    receipt_unblock_status: pd.DataFrame | None = None,
    project_goal_status_review: pd.DataFrame | None = None,
    backend_closeout_review: pd.DataFrame | None = None,
    tier3_research_comparison: pd.DataFrame | None = None,
    workstream_end_state_map: pd.DataFrame | None = None,
) -> tuple[Path, Path, pd.DataFrame]:
    frame = build_downstream_consistency_review(
        downstream_handoff_bundle=downstream_handoff_bundle,
        downstream_ingest_manifest=downstream_ingest_manifest,
        downstream_estimator_contract=downstream_estimator_contract,
        downstream_deposit_effect_use_case_review=downstream_deposit_effect_use_case_review,
        downstream_deposit_effect_series_panel=downstream_deposit_effect_series_panel,
        downstream_deposit_effect_comparison_panel=downstream_deposit_effect_comparison_panel,
        downstream_estimator_gap_review=downstream_estimator_gap_review,
        downstream_component_contribution_review=downstream_component_contribution_review,
        downstream_problem_variable_review=downstream_problem_variable_review,
        fiscal_receipt_boundary_review=fiscal_receipt_boundary_review,
        receipt_unblock_status=receipt_unblock_status,
        project_goal_status_review=project_goal_status_review,
        backend_closeout_review=backend_closeout_review,
        tier3_research_comparison=tier3_research_comparison,
        workstream_end_state_map=workstream_end_state_map,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_downstream_consistency_review_markdown(frame), encoding="utf-8")

    return csv_path, markdown_path, frame
