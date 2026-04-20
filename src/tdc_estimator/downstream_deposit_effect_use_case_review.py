from __future__ import annotations

from pathlib import Path

import pandas as pd


USE_CASE_COLUMNS = [
    "use_case_key",
    "target_question",
    "primary_artifact_key",
    "primary_role",
    "comparison_artifact_key",
    "readiness_status",
    "primary_latest_reference_date",
    "primary_latest_value_millions",
    "dominant_problem_variable_key",
    "dominant_problem_variable_family",
    "binding_boundary",
    "fallback_artifacts",
    "recommended_reading",
    "summary_note",
]


def _get_row(frame: pd.DataFrame | None, key_col: str, key: str) -> pd.Series:
    if frame is None or frame.empty or key_col not in frame.columns:
        return pd.Series(dtype="object")
    match = frame.loc[frame[key_col].eq(key)]
    if match.empty:
        return pd.Series(dtype="object")
    return match.iloc[0]


def _normalize_date(value: object) -> str:
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


def build_downstream_deposit_effect_use_case_review(
    *,
    downstream_estimator_contract: pd.DataFrame | None,
    downstream_estimator_gap_review: pd.DataFrame | None,
    fiscal_receipt_boundary_review: pd.DataFrame | None,
    project_goal_status_review: pd.DataFrame | None,
) -> pd.DataFrame:
    contract = downstream_estimator_contract.copy() if downstream_estimator_contract is not None else pd.DataFrame()
    gap = downstream_estimator_gap_review.copy() if downstream_estimator_gap_review is not None else pd.DataFrame()
    receipt = fiscal_receipt_boundary_review.copy() if fiscal_receipt_boundary_review is not None else pd.DataFrame()
    goals = project_goal_status_review.copy() if project_goal_status_review is not None else pd.DataFrame()

    tier3_bank = _get_row(contract, "artifact_key", "tdc_tier3_fiscal_corrected_bank_only_ru_flow")
    tier2_bank = _get_row(contract, "artifact_key", "tdc_tier2_interest_corrected_bank_only_ru_flow")
    bank_hist = _get_row(contract, "artifact_key", "bank_receipt_historical_default_view")
    row_mrv = _get_row(contract, "artifact_key", "row_mrv_primary_nondefault_pilot")
    broad_tier3 = _get_row(contract, "artifact_key", "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow")
    monetary_dep = _get_row(contract, "artifact_key", "monetary_depository_crosscheck")
    monetary_bank = _get_row(contract, "artifact_key", "monetary_bank_target_stress_test")

    gap_live = _get_row(gap, "gap_key", "latest_live_tier2_to_tier3_bank_only")
    gap_hist = _get_row(gap, "gap_key", "latest_historical_bank_receipt_overlay")
    gap_perimeter = _get_row(gap, "gap_key", "latest_live_bank_to_broad_depository_tier3")
    gap_interest = _get_row(gap, "gap_key", "latest_live_base_to_tier2_bank_only")

    bank_live_cell = _get_row(receipt, "boundary_key", "bank_live_default_receipt_cell")
    row_live_cell = _get_row(receipt, "boundary_key", "row_live_default_receipt_cell")
    bank_hist_overlay = _get_row(receipt, "boundary_key", "bank_receipt_historical_overlay_candidate")
    row_mrv_boundary = _get_row(receipt, "boundary_key", "row_mrv_primary_nondefault_pilot")

    fiscal_goal = _get_row(goals, "goal_key", "fiscal_flow_tdc_equation")
    monetary_goal = _get_row(goals, "goal_key", "monetary_disaggregated_tdc_equation")

    rows = [
        {
            "use_case_key": "current_quarter_bank_only_headline",
            "target_question": "Best current-quarter bank-only TDC for downstream deposit-effect analysis.",
            "primary_artifact_key": "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
            "primary_role": str(tier3_bank.get("default_classification", "live_default_with_partial_receipt_cells")),
            "comparison_artifact_key": "tdc_tier2_interest_corrected_bank_only_ru_flow",
            "readiness_status": "usable_with_explicit_receipt_boundary",
            "primary_latest_reference_date": pd.to_datetime(tier3_bank.get("latest_reference_date"), errors="coerce"),
            "primary_latest_value_millions": pd.to_numeric(tier3_bank.get("latest_value_millions"), errors="coerce"),
            "dominant_problem_variable_key": str(gap_live.get("dominant_component_key", "n/a")),
            "dominant_problem_variable_family": str(gap_live.get("dominant_component_family", "n/a")),
            "binding_boundary": (
                f"bank_live_default_receipt_cell={bank_live_cell.get('binding_blocker', 'n/a')}; "
                f"row_live_default_receipt_cell={row_live_cell.get('binding_blocker', 'n/a')}"
            ),
            "fallback_artifacts": "tdc_tier2_interest_corrected_bank_only_ru_flow;tdc_fiscal_receipt_boundary_review",
            "recommended_reading": "Use Tier 3 as the live headline, but read it alongside the fiscal receipt boundary review and Tier 2 comparison.",
            "summary_note": str(fiscal_goal.get("summary_note", "Live fiscal-flow view still carries receipt-side caveats.")),
        },
        {
            "use_case_key": "historical_bank_receipt_backtest",
            "target_question": "Best historical bank-only TDC when testing the effect of a nonzero bank receipt correction.",
            "primary_artifact_key": "bank_receipt_historical_default_view",
            "primary_role": str(bank_hist.get("default_classification", "historical_default_only")),
            "comparison_artifact_key": "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
            "readiness_status": "high_inside_age_eligible_window",
            "primary_latest_reference_date": pd.to_datetime(bank_hist.get("latest_reference_date"), errors="coerce"),
            "primary_latest_value_millions": pd.to_numeric(bank_hist.get("latest_value_millions"), errors="coerce"),
            "dominant_problem_variable_key": str(gap_hist.get("dominant_component_key", "n/a")),
            "dominant_problem_variable_family": str(gap_hist.get("dominant_component_family", "n/a")),
            "binding_boundary": str(bank_hist_overlay.get("binding_blocker", "n/a")),
            "fallback_artifacts": "tdc_tier3_historical_bank_receipt_research;tdc_downstream_estimator_gap_review",
            "recommended_reading": "Use the historical bank overlay as the main receipt-side backtest and compare it against the lower bound before drawing causal conclusions.",
            "summary_note": str(bank_hist_overlay.get("interpretation", "Historical bank receipt overlay is the main receipt-side backtest path.")),
        },
        {
            "use_case_key": "current_row_receipt_sensitivity",
            "target_question": "Best bounded current-quarter ROW receipt sensitivity without pretending to have a default correction.",
            "primary_artifact_key": "row_mrv_primary_nondefault_pilot",
            "primary_role": str(row_mrv.get("default_classification", "nondefault_pilot")),
            "comparison_artifact_key": "tdc_bea_row_receipts_benchmark",
            "readiness_status": "bounded_nondefault_only",
            "primary_latest_reference_date": pd.to_datetime(row_mrv.get("latest_reference_date"), errors="coerce"),
            "primary_latest_value_millions": pd.to_numeric(row_mrv.get("latest_value_millions"), errors="coerce"),
            "dominant_problem_variable_key": "legal_remitter_or_debited_account_proof",
            "dominant_problem_variable_family": "receipt_identity_boundary",
            "binding_boundary": str(row_mrv_boundary.get("binding_blocker", "evidence_boundary")),
            "fallback_artifacts": "tdc_row_mrv_nondefault_evidence_summary;tdc_fiscal_receipt_boundary_review",
            "recommended_reading": "Use MRV only as a bounded sensitivity and pair it with the BEA benchmark for scale, not as a default additive correction.",
            "summary_note": str(row_mrv_boundary.get("interpretation", "MRV is still bounded by receipt-identity and timing evidence.")),
        },
        {
            "use_case_key": "deposit_perimeter_comparison",
            "target_question": "How much does widening the deposit perimeter from bank-only to broad depository change TDC?",
            "primary_artifact_key": "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow",
            "primary_role": str(broad_tier3.get("default_classification", "broad_depository_default")),
            "comparison_artifact_key": "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
            "readiness_status": "usable_for_perimeter_comparison",
            "primary_latest_reference_date": pd.to_datetime(broad_tier3.get("latest_reference_date"), errors="coerce"),
            "primary_latest_value_millions": pd.to_numeric(broad_tier3.get("latest_value_millions"), errors="coerce"),
            "dominant_problem_variable_key": str(gap_perimeter.get("dominant_component_key", "n/a")),
            "dominant_problem_variable_family": str(gap_perimeter.get("dominant_component_family", "n/a")),
            "binding_boundary": "credit_union_and_depository_perimeter_choice",
            "fallback_artifacts": "tdc_downstream_estimator_gap_review;tdc_downstream_component_contribution_review",
            "recommended_reading": "Use the broad-depository series to bound perimeter effects, not to replace the bank-only headline for all questions.",
            "summary_note": "The main live bank-vs-broad wedge is small relative to the full ladder and is currently driven by credit-union perimeter terms.",
        },
        {
            "use_case_key": "monetary_crosscheck_and_problem_variable_audit",
            "target_question": "Which monetary surface should be used as a cross-check, and where is the biggest ladder-cleanup wedge right now?",
            "primary_artifact_key": "monetary_depository_crosscheck",
            "primary_role": str(monetary_dep.get("default_classification", "diagnostic_primary")),
            "comparison_artifact_key": "tdc_base_bank_only_ru_flow",
            "readiness_status": "diagnostic_only",
            "primary_latest_reference_date": pd.to_datetime(monetary_dep.get("latest_reference_date"), errors="coerce"),
            "primary_latest_value_millions": pd.to_numeric(monetary_dep.get("latest_value_millions"), errors="coerce"),
            "dominant_problem_variable_key": str(gap_interest.get("dominant_component_key", "n/a")),
            "dominant_problem_variable_family": str(gap_interest.get("dominant_component_family", "n/a")),
            "binding_boundary": str(monetary_goal.get("binding_blocker", "stop_at_perimeter_stress_test")),
            "fallback_artifacts": "monetary_bank_target_stress_test;tdc_downstream_estimator_gap_review",
            "recommended_reading": "Use the depository monetary surface as a cross-check and use the gap review to see that the biggest live cleanup wedge is still coupon-related, not receipt-side.",
            "summary_note": str(monetary_goal.get("summary_note", "Monetary branch remains diagnostic-only.")),
        },
    ]

    frame = pd.DataFrame(rows).reindex(columns=USE_CASE_COLUMNS)
    if "primary_latest_reference_date" in frame.columns:
        frame["primary_latest_reference_date"] = frame["primary_latest_reference_date"].apply(_normalize_date)
    return frame


def render_downstream_deposit_effect_use_case_review_markdown(frame: pd.DataFrame) -> str:
    title = "# Downstream Deposit-Effect Use-Case Review"
    intro = (
        "Backend use-case review for downstream projects. It maps the main deposit-effect questions to the best current artifact, "
        "the right comparison surface, and the dominant problem-variable family."
    )
    if frame.empty:
        return "\n".join([title, "", intro, "", "No downstream use-case rows are available."])

    lines = [
        title,
        "",
        intro,
        "",
        "| Use case | Primary artifact | Comparison artifact | Readiness | Latest date | Latest value (mil) | Dominant problem family | Binding boundary |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for _, row in frame.iterrows():
        value = row["primary_latest_value_millions"]
        value_text = "n/a" if value is None or pd.isna(value) else f"{float(value):,.3f}"
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["use_case_key"]),
                    str(row["primary_artifact_key"]),
                    str(row["comparison_artifact_key"]),
                    str(row["readiness_status"]),
                    str(row["primary_latest_reference_date"]),
                    value_text,
                    str(row["dominant_problem_variable_family"]),
                    str(row["binding_boundary"]),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Notes", ""])
    for _, row in frame.iterrows():
        lines.append(f"- `{row['use_case_key']}`: {row['summary_note']}")

    return "\n".join(lines + [""])


def write_downstream_deposit_effect_use_case_review(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    downstream_estimator_contract: pd.DataFrame | None,
    downstream_estimator_gap_review: pd.DataFrame | None,
    fiscal_receipt_boundary_review: pd.DataFrame | None,
    project_goal_status_review: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    frame = build_downstream_deposit_effect_use_case_review(
        downstream_estimator_contract=downstream_estimator_contract,
        downstream_estimator_gap_review=downstream_estimator_gap_review,
        fiscal_receipt_boundary_review=fiscal_receipt_boundary_review,
        project_goal_status_review=project_goal_status_review,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_downstream_deposit_effect_use_case_review_markdown(frame), encoding="utf-8")

    return csv_path, markdown_path, frame
