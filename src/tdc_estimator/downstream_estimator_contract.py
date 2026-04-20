from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


CONTRACT_COLUMNS = [
    "artifact_key",
    "artifact_family",
    "current_role",
    "default_classification",
    "deposit_scope",
    "counterparty_scope",
    "time_scope",
    "latest_reference_date",
    "latest_value_millions",
    "strongest_supporting_surface",
    "core_equation_or_claim",
    "best_downstream_use",
    "comparison_anchor",
    "binding_blocker",
    "main_known_boundary",
    "next_finite_push",
    "summary_note",
]


def _get_row(frame: pd.DataFrame | None, key_col: str, key: str) -> pd.Series:
    if frame is None or frame.empty or key_col not in frame.columns:
        return pd.Series(dtype="object")
    match = frame.loc[frame[key_col].eq(key)]
    if match.empty:
        return pd.Series(dtype="object")
    return match.iloc[0]


def _latest_value(estimates: pd.DataFrame | None, column: str) -> tuple[str, float | None]:
    if estimates is None or estimates.empty or column not in estimates.columns:
        return "n/a", None
    series = pd.to_numeric(estimates[column], errors="coerce").dropna().sort_index()
    if series.empty:
        return "n/a", None
    latest_date = pd.Timestamp(series.index.max()).date().isoformat()
    return latest_date, float(series.loc[series.index.max()])


def _latest_frame_value(frame: pd.DataFrame | None, value_col: str) -> tuple[str, float | None]:
    if frame is None or frame.empty or value_col not in frame.columns:
        return "n/a", None
    series = pd.to_numeric(frame[value_col], errors="coerce")
    working = frame.copy()
    working["_value"] = series
    working.index = pd.to_datetime(working.index, errors="coerce")
    working = working.loc[working.index.notna() & working["_value"].notna()].sort_index()
    if working.empty:
        return "n/a", None
    latest_idx = working.index.max()
    return pd.Timestamp(latest_idx).date().isoformat(), float(working.loc[latest_idx, "_value"])


def _normalize_date(value: Any) -> str:
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


def _fmt(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def build_downstream_estimator_contract(
    *,
    estimates: pd.DataFrame | None,
    method_meta: dict[str, Any] | None,
    receipt_unblock_status: pd.DataFrame | None,
    project_goal_status_review: pd.DataFrame | None,
    tier3_research_comparison: pd.DataFrame | None,
    bea_row_receipts_benchmark: pd.DataFrame | None,
    row_mrv_nondefault_evidence_summary: pd.DataFrame | None,
    monetary_target_preference_review: pd.DataFrame | None,
    workstream_end_state_map: pd.DataFrame | None,
) -> pd.DataFrame:
    method_meta = method_meta or {}
    method_formulas = method_meta.get("method_formulas", {})
    method_descriptions = method_meta.get("method_descriptions", {})

    receipt = receipt_unblock_status.copy() if receipt_unblock_status is not None else pd.DataFrame()
    goals = project_goal_status_review.copy() if project_goal_status_review is not None else pd.DataFrame()
    research = tier3_research_comparison.copy() if tier3_research_comparison is not None else pd.DataFrame()
    mrv_summary = row_mrv_nondefault_evidence_summary.copy() if row_mrv_nondefault_evidence_summary is not None else pd.DataFrame()
    monetary = monetary_target_preference_review.copy() if monetary_target_preference_review is not None else pd.DataFrame()
    workstreams = workstream_end_state_map.copy() if workstream_end_state_map is not None else pd.DataFrame()

    bank_hist = _get_row(receipt, "branch_key", "bank_table51_historical_window")
    bank_current = _get_row(receipt, "branch_key", "bank_table51_current_window")
    row_mrv = _get_row(receipt, "branch_key", "row_mrv_cbsp_primary")
    goal_fiscal = _get_row(goals, "goal_key", "fiscal_flow_tdc_equation")
    goal_monetary = _get_row(goals, "goal_key", "monetary_disaggregated_tdc_equation")
    work_hist = _get_row(workstreams, "workstream_key", "bank_receipt_historical_window")
    work_mrv = _get_row(workstreams, "workstream_key", "row_mrv_primary_pilot")
    work_fiscal = _get_row(workstreams, "workstream_key", "fiscal_reconciliation_shell")
    work_monetary = _get_row(workstreams, "workstream_key", "monetary_branch")
    latest_hist = _get_row(research, "comparison_key", "latest_historical_bank_window")
    latest_live = _get_row(research, "comparison_key", "latest_live_defaults")
    latest_mrv = mrv_summary.iloc[0] if not mrv_summary.empty else pd.Series(dtype="object")
    latest_monetary = (
        monetary.sort_values("latest_quarter").iloc[-1]
        if not monetary.empty and "latest_quarter" in monetary.columns
        else (monetary.iloc[-1] if not monetary.empty else pd.Series(dtype="object"))
    )
    latest_bea_date, latest_bea_value = _latest_frame_value(bea_row_receipts_benchmark, "bea_row_current_receipts_total_q_mil")

    rows: list[dict[str, object]] = []

    for key, role, default_classification, best_use in [
        (
            "tdc_base_bank_only_ru_flow",
            "headline_estimator",
            "headline_default",
            "Primary downstream bank-only TDC estimate and the anchor for deposit-effect work.",
        ),
        (
            "tdc_tier2_interest_corrected_bank_only_ru_flow",
            "corrected_estimator",
            "default_sensitivity_with_stronger_transfer_cleanup",
            "Interest-cleaned comparison against the base headline to isolate coupon-related bias.",
        ),
        (
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
            "corrected_estimator",
            "live_default_with_partial_receipt_cells",
            "Main fiscal-flow-corrected live estimator, with explicit receipt-side caveats.",
        ),
        (
            "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow",
            "alternative_estimator",
            "broad_depository_default",
            "Best live broad-depository comparison when downstream work needs a wider deposit perimeter.",
        ),
    ]:
        latest_date, latest_value = _latest_value(estimates, key)
        rows.append(
            {
                "artifact_key": key,
                "artifact_family": "estimator_series",
                "current_role": role,
                "default_classification": default_classification,
                "deposit_scope": "bank_only" if "broad_depository" not in key else "broad_depository",
                "counterparty_scope": "bank_plus_row_transaction_flow",
                "time_scope": "transaction_era_quarterly",
                "latest_reference_date": latest_date,
                "latest_value_millions": latest_value,
                "strongest_supporting_surface": "tdc_estimates.csv",
                "core_equation_or_claim": method_formulas.get(key, method_descriptions.get(key, "")),
                "best_downstream_use": best_use,
                "comparison_anchor": "Compare against Tier 0, Tier 2, Tier 3, and historical bank overlay to isolate where correction layers change TDC.",
                "binding_blocker": "none" if key != "tdc_tier3_fiscal_corrected_bank_only_ru_flow" else "receipt_side_completion",
                "main_known_boundary": (
                    "Receipt-side default corrections remain incomplete; bank current quarters stay nondefault and MRV stays nondefault."
                    if key == "tdc_tier3_fiscal_corrected_bank_only_ru_flow"
                    else "Perimeter and correction assumptions remain explicit in method metadata."
                ),
                "next_finite_push": (
                    "Keep polishing historical bank and receipt-boundary comparisons around this ladder."
                    if key == "tdc_tier3_fiscal_corrected_bank_only_ru_flow"
                    else "Maintain as comparison anchor."
                ),
                "summary_note": method_descriptions.get(key, ""),
            }
        )

    rows.extend(
        [
            {
                "artifact_key": "tdc_bea_row_receipts_benchmark",
                "artifact_family": "benchmark_surface",
                "current_role": "benchmark_only",
                "default_classification": "benchmark_only",
                "deposit_scope": "not_additive_to_headline",
                "counterparty_scope": "row_receipt_macro_benchmark",
                "time_scope": "quarterly_macro_benchmark",
                "latest_reference_date": latest_bea_date,
                "latest_value_millions": latest_bea_value,
                "strongest_supporting_surface": "tdc_bea_row_receipts_benchmark.csv",
                "core_equation_or_claim": "BEA/FRED macro benchmark for federal current receipts from the rest of the world; useful for scale checks, not Treasury cash-payer identification.",
                "best_downstream_use": "Benchmark MRV scale and coverage without mistaking NIPA ROW receipts for a Treasury cash-payer correction.",
                "comparison_anchor": "Read beside the MRV bounded pilot to compare scale, not to promote a default receipt correction.",
                "binding_blocker": "not_treasury_cash_payer_identity",
                "main_known_boundary": "Macro benchmark only; does not identify the actual Treasury cash payer, remitter, or debited account.",
                "next_finite_push": "Maintain as context only unless a Treasury cash-payer bridge can be tied to it cleanly.",
                "summary_note": "BEA ROW receipts benchmark stays benchmark-only under the current Treasury cash-payer rules.",
            },
            {
                "artifact_key": "bank_receipt_historical_default_view",
                "artifact_family": "historical_receipt_overlay",
                "current_role": "historical_default_view",
                "default_classification": "historical_default_only",
                "deposit_scope": "bank_only",
                "counterparty_scope": "bank_receipts",
                "time_scope": "historical_age_eligible_window_only",
                "latest_reference_date": pd.to_datetime(
                    bank_hist.get("latest_relevant_date", latest_hist.get("reference_date")),
                    errors="coerce",
                ),
                "latest_value_millions": pd.to_numeric(
                    latest_hist.get("historical_bank_receipt_variant_mil"),
                    errors="coerce",
                ),
                "strongest_supporting_surface": "tdc_tier3_historical_bank_receipt_research.csv",
                "core_equation_or_claim": "Historical Tier 3 bank-only plus the age-eligible Table 5.1 depository-plus-BHC bank receipt delta.",
                "best_downstream_use": "Historical bank receipt overlay for deposit-effect work when current-quarter bank receipt default is unavailable.",
                "comparison_anchor": "Compare against default Tier 3 and the lower-bound historical overlay in the same quarter.",
                "binding_blocker": str(bank_current.get("binding_blocker", "stale_share_rule")),
                "main_known_boundary": "Valid only inside the age-eligible historical share window; current quarters remain explicitly nondefault.",
                "next_finite_push": str(work_hist.get("next_finite_push", "Integrate historical bank window into polished Tier 3 reporting.")),
                "summary_note": str(bank_hist.get("summary_note", "Historical bank receipt view is usable inside the age-eligible window.")),
            },
            {
                "artifact_key": "row_mrv_primary_nondefault_pilot",
                "artifact_family": "receipt_pilot",
                "current_role": "leading_nondefault_recurring_pilot",
                "default_classification": "nondefault_pilot",
                "deposit_scope": "bank_only_ladder_adjustment_candidate",
                "counterparty_scope": "row_receipts",
                "time_scope": "recurring_mrv_first_pilot",
                "latest_reference_date": pd.to_datetime(row_mrv.get("latest_relevant_date"), errors="coerce"),
                "latest_value_millions": pd.to_numeric(row_mrv.get("latest_value_millions"), errors="coerce"),
                "strongest_supporting_surface": "tdc_row_mrv_nondefault_evidence_summary.csv",
                "core_equation_or_claim": "MRV-first / CBSP recurring ROW receipt candidate, kept nondefault until remitter and quarterly cash timing evidence clears.",
                "best_downstream_use": "Bounded ROW receipt sensitivity and boundary marker, not a default additive correction.",
                "comparison_anchor": "Compare against the zero default ROW receipt correction and keep secondary visa outside the main pilot.",
                "binding_blocker": str(row_mrv.get("binding_blocker", "evidence_boundary")),
                "main_known_boundary": str(latest_mrv.get("binding_default_blocker", "legal_remitter_or_debited_account_proof;observed_quarterly_cash_timing_or_remittance_schedule")),
                "next_finite_push": str(work_mrv.get("next_finite_push", "Tighten MRV payment-chain and reconciliation layers.")),
                "summary_note": str(row_mrv.get("summary_note", "MRV is the leading recurring ROW pilot, but remains nondefault.")),
            },
            {
                "artifact_key": "fiscal_reconciliation_shell",
                "artifact_family": "diagnostic_system",
                "current_role": "diagnostic_reconciliation_system",
                "default_classification": "diagnostic_shell",
                "deposit_scope": "bank_only_and_broad_depository",
                "counterparty_scope": "full_ladder_integration",
                "time_scope": "transaction_era_quarterly",
                "latest_reference_date": pd.to_datetime(goal_fiscal.get("latest_relevant_date"), errors="coerce"),
                "latest_value_millions": None,
                "strongest_supporting_surface": str(goal_fiscal.get("strongest_live_surface", "Fiscal reconciliation shell")),
                "core_equation_or_claim": "Reconstruct Tier 0 through Tier 3 from additive cells and track residual closure rather than replacing the main estimator ladder.",
                "best_downstream_use": "Audit whether component-level fiscal-flow logic still closes around the live ladder before using the estimates downstream.",
                "comparison_anchor": "Use alongside Tier 2/Tier 3 and historical receipt overlays to see which cells remain provisional.",
                "binding_blocker": str(goal_fiscal.get("binding_blocker", "receipt_cells_still_partial")),
                "main_known_boundary": str(goal_fiscal.get("summary_note", "Fiscal shell remains receipt-side incomplete.")),
                "next_finite_push": str(work_fiscal.get("next_finite_push", "Keep the shell coherent and source-graded.")),
                "summary_note": str(goal_fiscal.get("summary_note", "")),
            },
            {
                "artifact_key": "monetary_depository_crosscheck",
                "artifact_family": "diagnostic_crosscheck",
                "current_role": "main_monetary_crosscheck",
                "default_classification": "diagnostic_primary",
                "deposit_scope": "broad_depository_target",
                "counterparty_scope": "monetary_target_crosscheck",
                "time_scope": "transaction_era_quarterly",
                "latest_reference_date": pd.to_datetime(
                    latest_monetary.get("latest_quarter", goal_monetary.get("latest_relevant_date")),
                    errors="coerce",
                ),
                "latest_value_millions": pd.to_numeric(latest_monetary.get("depository_residual_after_expanded_mil"), errors="coerce"),
                "strongest_supporting_surface": "tdc_monetary_target_preference_review.csv",
                "core_equation_or_claim": "Use the depository target as the main monetary cross-check because it behaves materially better than the commercial-bank target after expanded controls.",
                "best_downstream_use": "Cross-check whether the ladder is directionally plausible against a broader deposit target, without treating the monetary branch as a headline estimator.",
                "comparison_anchor": "Compare depository residuals against commercial-bank residuals and the bank-target wedge.",
                "binding_blocker": str(goal_monetary.get("binding_blocker", "stop_at_perimeter_stress_test")),
                "main_known_boundary": "Diagnostic only; not a replacement estimator.",
                "next_finite_push": str(work_monetary.get("next_finite_push", "Keep the depository target as the main cross-check.")),
                "summary_note": str(goal_monetary.get("summary_note", "")),
            },
            {
                "artifact_key": "monetary_bank_target_stress_test",
                "artifact_family": "diagnostic_crosscheck",
                "current_role": "stress_test_only",
                "default_classification": "diagnostic_secondary",
                "deposit_scope": "commercial_bank_target",
                "counterparty_scope": "monetary_target_crosscheck",
                "time_scope": "transaction_era_quarterly",
                "latest_reference_date": pd.to_datetime(latest_monetary.get("latest_quarter"), errors="coerce"),
                "latest_value_millions": pd.to_numeric(latest_monetary.get("commercial_bank_residual_after_expanded_mil"), errors="coerce"),
                "strongest_supporting_surface": "tdc_monetary_target_preference_review.csv",
                "core_equation_or_claim": "Commercial-bank-deposit target remains a perimeter stress test rather than a main estimator or main cross-check.",
                "best_downstream_use": "Stress-test whether a bank-only deposit target leaves a large unresolved wedge, and treat that wedge as a warning rather than a target to fit.",
                "comparison_anchor": "Read next to the depository target to see how much of the commercial-bank residual remains mostly unresolved.",
                "binding_blocker": str(goal_monetary.get("binding_blocker", "stop_at_perimeter_stress_test")),
                "main_known_boundary": "Perimeter-style wedge remains dominant; do not treat this as a headline estimator target.",
                "next_finite_push": "Maintain only as a stress-test surface.",
                "summary_note": "Commercial-bank target remains stress-test only under the current source surface.",
            },
        ]
    )

    frame = pd.DataFrame(rows).reindex(columns=CONTRACT_COLUMNS)
    if "latest_reference_date" in frame.columns:
        frame["latest_reference_date"] = frame["latest_reference_date"].apply(_normalize_date)
    return frame


def render_downstream_estimator_contract_markdown(frame: pd.DataFrame) -> str:
    title = "# Downstream Estimator Contract"
    intro = (
        "Backend-facing contract for downstream projects. It identifies which estimator or diagnostic surface should be used, "
        "what role it currently has, which boundary still binds, and what each artifact is best suited for."
    )
    if frame.empty:
        return "\n".join([title, "", intro, "", "No downstream estimator contract rows are available."])

    lines = [
        title,
        "",
        intro,
        "",
        "| Artifact | Role | Classification | Scope | Latest date | Latest value (mil) | Binding blocker | Best downstream use |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for _, row in frame.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["artifact_key"]),
                    str(row["current_role"]),
                    str(row["default_classification"]),
                    str(row["deposit_scope"]),
                    str(row["latest_reference_date"]),
                    _fmt(row["latest_value_millions"]),
                    str(row["binding_blocker"]),
                    str(row["best_downstream_use"]),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Notes", ""])
    for _, row in frame.iterrows():
        lines.append(f"- `{row['artifact_key']}`: {row['summary_note']}")

    return "\n".join(lines + [""])


def write_downstream_estimator_contract(
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    estimates: pd.DataFrame | None,
    method_meta: dict[str, Any] | None,
    receipt_unblock_status: pd.DataFrame | None,
    project_goal_status_review: pd.DataFrame | None,
    tier3_research_comparison: pd.DataFrame | None,
    bea_row_receipts_benchmark: pd.DataFrame | None,
    row_mrv_nondefault_evidence_summary: pd.DataFrame | None,
    monetary_target_preference_review: pd.DataFrame | None,
    workstream_end_state_map: pd.DataFrame | None,
) -> tuple[Path, Path, pd.DataFrame]:
    frame = build_downstream_estimator_contract(
        estimates=estimates,
        method_meta=method_meta,
        receipt_unblock_status=receipt_unblock_status,
        project_goal_status_review=project_goal_status_review,
        tier3_research_comparison=tier3_research_comparison,
        bea_row_receipts_benchmark=bea_row_receipts_benchmark,
        row_mrv_nondefault_evidence_summary=row_mrv_nondefault_evidence_summary,
        monetary_target_preference_review=monetary_target_preference_review,
        workstream_end_state_map=workstream_end_state_map,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_downstream_estimator_contract_markdown(frame), encoding="utf-8")

    return csv_path, markdown_path, frame
