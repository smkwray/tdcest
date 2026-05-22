from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .bank_corp_tax_receipts_bridge import write_bank_corp_tax_receipts_bridge
from .bill_discount_validation import write_bill_discount_validation
from .bank_receipt_historical_promotion import write_bank_receipt_historical_promotion
from .bank_minor_industry_share_availability import write_bank_minor_industry_share_availability
from .bank_receipt_default_readiness import write_bank_receipt_default_readiness
from .bank_receipt_source_map import write_bank_receipt_source_map
from .bank_receipt_stop_gate import write_bank_receipt_stop_gate
from .bank_nontax_regulatory_pilot import write_bank_nontax_regulatory_pilot
from .bank_occ_timing_sensitivity import write_bank_occ_timing_sensitivity
from .bea_row_receipts_benchmark import write_bea_row_receipts_benchmark
from .du_fiscal_flow_research import write_du_fiscal_flow_research
from .catalog import all_fred_series
from .attribution import write_post2022_bank_only_attribution
from .estimators import compute_estimates
from .fdic_savings_institution_deposit_bridge import write_fdic_savings_institution_deposit_bridge
from .fiscal_reconciliation import write_fiscal_reconciliation_outputs
from .fiscal_receipt_boundary_review import write_fiscal_receipt_boundary_review
from .input_audit import write_input_audit
from .headline_validation_review import write_headline_validation_review
from .gse_rrp_boundary import write_gse_rrp_boundary_check
from .io import build_quarterly_frame
from .mmf_rrp import write_mmf_rrp_adjustment_outputs, write_mmf_rrp_source_comparison
from .monetary_stage0 import write_monetary_stage0_diagnostics
from .monetary_control_overlap_audit import write_monetary_control_overlap_audit
from .monetary_residual_interpretation import write_monetary_residual_interpretation
from .monetary_stage1_controls import write_monetary_stage1_controls
from .monetary_bank_target_gap_attribution import write_monetary_bank_target_gap_attribution
from .monetary_bank_perimeter_gap_review import write_monetary_bank_perimeter_gap_review
from .monetary_bank_perimeter_source_map import write_monetary_bank_perimeter_source_map
from .monetary_bank_liquid_source_review import write_monetary_bank_liquid_source_review
from .monetary_bank_liquid_stop_gate import write_monetary_bank_liquid_stop_gate
from .monetary_bank_target_stress_review import write_monetary_bank_target_stress_review
from .monetary_bank_liability_candidate_audit import write_monetary_bank_liability_candidate_audit
from .monetary_nonbank_depository_bridge_attribution import write_monetary_nonbank_depository_bridge_attribution
from .ncua_credit_union_deposit_bridge import write_ncua_credit_union_deposit_bridge
from .monetary_target_definition_bridge import write_monetary_target_definition_bridge
from .monetary_target_definition_decomposition import write_monetary_target_definition_decomposition
from .monetary_target_wedge import write_monetary_target_wedge
from .monetary_target_preference_review import write_monetary_target_preference_review
from .plots import build_all_figures
from .receipt_account_candidates import write_receipt_account_candidates
from .receipt_account_crosswalk import write_receipt_account_crosswalk
from .receipt_promotion_review import write_receipt_promotion_review
from .receipt_unblock_status import write_receipt_unblock_status
from .project_goal_status_review import write_project_goal_status_review
from .tier3_research_comparison import write_tier3_research_comparison
from .downstream_estimator_contract import write_downstream_estimator_contract
from .downstream_component_contribution_review import write_downstream_component_contribution_review
from .downstream_estimator_gap_review import write_downstream_estimator_gap_review
from .downstream_deposit_effect_use_case_review import write_downstream_deposit_effect_use_case_review
from .downstream_problem_variable_review import write_downstream_problem_variable_review
from .downstream_deposit_effect_series_panel import write_downstream_deposit_effect_series_panel
from .downstream_deposit_effect_comparison_panel import write_downstream_deposit_effect_comparison_panel
from .downstream_handoff_bundle import write_downstream_handoff_bundle
from .downstream_ingest_manifest import write_downstream_ingest_manifest
from .downstream_consistency_review import write_downstream_consistency_review
from .backend_closeout_review import write_backend_closeout_review
from .backend_release_check import write_backend_release_check
from .theory_measurement_map import write_theory_measurement_map
from .row_mrv_nondefault_evidence_summary import write_row_mrv_nondefault_evidence_summary
from .row_recurring_pilot_review import write_row_recurring_pilot_review
from .row_receipt_family_review import write_row_receipt_family_review
from .row_visa_consular_pilot import write_row_visa_consular_pilot
from .row_mrv_default_readiness import write_row_mrv_default_readiness
from .row_mrv_payment_chain_review import write_row_mrv_payment_chain_review
from .row_mrv_promotion_checklist import write_row_mrv_promotion_checklist
from .row_mrv_source_map import write_row_mrv_source_map
from .row_mrv_stop_gate import write_row_mrv_stop_gate
from .row_state_visa_timing_sensitivity import write_row_state_visa_timing_sensitivity
from .tier3_receipts_source import write_tier3_receipt_source_diagnostics
from .tier3_receipt_candidate_sensitivity import write_tier3_receipt_candidate_sensitivity
from .tier3_historical_bank_receipt_research import write_tier3_historical_bank_receipt_research
from .tier3_receipt_sensitivity import write_tier3_bank_receipt_upper_bound_sensitivity
from .workstream_end_state_map import write_workstream_end_state_map
from .site_export import export_site_bundle
from .tier3_source import write_tier3_source_diagnostics
from .utils import write_json


def run_estimation_pipeline(
    *,
    raw_dir: Path | str,
    processed_dir: Path | str,
    figures_dir: Path | str | None = None,
    site_dir: Path | str | None = None,
) -> dict[str, Any]:
    specs = all_fred_series(include_optional=True)
    quarterly, series_meta = build_quarterly_frame(raw_dir, specs)
    processed_dir = Path(processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)

    if "fed_remit_mts" in quarterly.columns:
        quarterly["fed_remit_or_deferred"] = quarterly["fed_remit_mts"]
        meta = dict(series_meta.get("fed_remit_mts", {}))
        meta["description"] = "Federal Reserve remittances from MTS Table 4 net receipts."
        meta["notes"] = (
            "Preferred Treasury cash-flow concept. Overrides H.4.1/FRED RESPPLLOPNWW, "
            "which is a weekly remittances-due/deferred-asset balance-sheet stock."
        )
        meta["source_kind"] = "local_support_preferred_over_fred"
        series_meta["fed_remit_or_deferred"] = meta

    mmf_rrp_monthly_path = processed_dir / "tdc_mmf_rrp_fund_month_adjustments.csv"
    mmf_rrp_quarterly_path = processed_dir / "tdc_mmf_rrp_quarterly_adjustments.csv"
    mmf_rrp_markdown_path = processed_dir / "tdc_mmf_rrp_adjustment.md"
    mmf_rrp_audit_path = processed_dir / "tdc_mmf_rrp_scale_audit.csv"
    mmf_rrp_audit_markdown_path = processed_dir / "tdc_mmf_rrp_scale_audit.md"
    mmf_rrp_source_comparison_path = processed_dir / "tdc_mmf_rrp_source_comparison.csv"
    mmf_rrp_source_comparison_markdown_path = processed_dir / "tdc_mmf_rrp_source_comparison.md"
    gse_rrp_boundary_path = processed_dir / "tdc_gse_rrp_boundary_check.csv"
    gse_rrp_boundary_markdown_path = processed_dir / "tdc_gse_rrp_boundary_check.md"
    bill_discount_validation_path = processed_dir / "bill_discount_validation.csv"
    bill_discount_validation_markdown_path = processed_dir / "bill_discount_validation.md"
    mmf_rrp_raw_path = Path(raw_dir) / "support__mmf_fund_month.csv"
    mmf_rrp_fallback_raw_path = Path(raw_dir) / "support__mmf_fund_month_ofr_aggregate.csv"
    mmf_rrp_quarterly = None
    mmf_rrp_source_comparison = None
    if mmf_rrp_raw_path.exists():
        _, mmf_rrp_quarterly = write_mmf_rrp_adjustment_outputs(
            raw_path=mmf_rrp_raw_path,
            monthly_csv_path=mmf_rrp_monthly_path,
            quarterly_csv_path=mmf_rrp_quarterly_path,
            markdown_path=mmf_rrp_markdown_path,
            audit_csv_path=mmf_rrp_audit_path,
            audit_markdown_path=mmf_rrp_audit_markdown_path,
            z1_mmf_treasury_level=quarterly.get("mmf_tsy_level"),
            z1_mmf_treasury_bills_level=quarterly.get("mmf_tsy_bills_level"),
        )
        for column in mmf_rrp_quarterly.columns:
            quarterly[column] = mmf_rrp_quarterly[column]
            series_meta[column] = {
                "series_id": None,
                "description": f"MMF/RRP source-of-funds adjustment component: {column}",
                "agg": "sum",
                "transform": None,
                "required": False,
                "source_kind": "local_support_derived",
                "notes": "Derived from data/raw/support__mmf_fund_month.csv by the MMF/RRP fund-month source-of-funds adjustment builder.",
                "raw_filename": mmf_rrp_raw_path.name,
                "raw_relative_path": str(Path("data/raw") / mmf_rrp_raw_path.name),
            }
        if mmf_rrp_fallback_raw_path.exists():
            mmf_rrp_source_comparison = write_mmf_rrp_source_comparison(
                preferred_raw_path=mmf_rrp_raw_path,
                fallback_raw_path=mmf_rrp_fallback_raw_path,
                csv_path=mmf_rrp_source_comparison_path,
                markdown_path=mmf_rrp_source_comparison_markdown_path,
            )

    estimates, components, corrections, method_meta = compute_estimates(quarterly)
    gse_rrp_boundary_check = write_gse_rrp_boundary_check(
        quarterly=quarterly,
        csv_path=gse_rrp_boundary_path,
        markdown_path=gse_rrp_boundary_markdown_path,
    )
    bill_discount_validation = None
    treasury_interest_path = Path(raw_dir) / "treasury__interest_expense.csv"
    if treasury_interest_path.exists():
        _, _ = write_bill_discount_validation(
            treasury_interest_path=treasury_interest_path,
            bank_proxy_path=Path(raw_dir) / "support__bank_tsy_bill_discount_interest_proxy.csv",
            row_proxy_path=Path(raw_dir) / "support__row_tsy_bill_discount_interest_proxy.csv",
            credit_union_proxy_path=Path(raw_dir) / "support__credit_union_tsy_bill_discount_interest_proxy.csv",
            out_csv_path=bill_discount_validation_path,
            out_markdown_path=bill_discount_validation_markdown_path,
        )
        bill_discount_validation = pd.read_csv(bill_discount_validation_path)

    quarterly_path = processed_dir / "quarterly_inputs.csv"
    estimates_path = processed_dir / "tdc_estimates.csv"
    components_path = processed_dir / "tdc_components.csv"
    corrections_path = processed_dir / "tdc_corrections.csv"
    post2022_attribution_path = processed_dir / "tdc_post2022_bank_only_attribution.csv"
    post2022_attribution_markdown_path = processed_dir / "tdc_post2022_bank_only_attribution.md"
    tier3_source_diag_path = processed_dir / "tdc_tier3_source_diagnostics.csv"
    tier3_source_diag_markdown_path = processed_dir / "tdc_tier3_source_diagnostics.md"
    tier3_receipt_diag_path = processed_dir / "tdc_tier3_receipt_source_diagnostics.csv"
    tier3_receipt_diag_markdown_path = processed_dir / "tdc_tier3_receipt_source_diagnostics.md"
    tier3_receipt_upper_bound_path = processed_dir / "tdc_tier3_bank_receipt_upper_bound_sensitivity.csv"
    tier3_receipt_upper_bound_markdown_path = processed_dir / "tdc_tier3_bank_receipt_upper_bound_sensitivity.md"
    bea_row_receipts_benchmark_path = processed_dir / "tdc_bea_row_receipts_benchmark.csv"
    bea_row_receipts_benchmark_markdown_path = processed_dir / "tdc_bea_row_receipts_benchmark.md"
    bank_corp_tax_bridge_path = processed_dir / "tdc_bank_corp_tax_receipts_bridge.csv"
    bank_corp_tax_bridge_markdown_path = processed_dir / "tdc_bank_corp_tax_receipts_bridge.md"
    bank_minor_industry_availability_path = processed_dir / "tdc_bank_minor_industry_share_availability.csv"
    bank_minor_industry_availability_markdown_path = processed_dir / "tdc_bank_minor_industry_share_availability.md"
    receipt_account_candidates_path = processed_dir / "tdc_receipt_account_candidates.csv"
    receipt_account_candidates_markdown_path = processed_dir / "tdc_receipt_account_candidates.md"
    receipt_account_crosswalk_path = processed_dir / "tdc_receipt_account_crosswalk.csv"
    receipt_account_crosswalk_markdown_path = processed_dir / "tdc_receipt_account_crosswalk.md"
    row_receipt_family_review_path = processed_dir / "tdc_row_receipt_family_review.csv"
    row_receipt_family_review_markdown_path = processed_dir / "tdc_row_receipt_family_review.md"
    row_visa_pilot_path = processed_dir / "tdc_row_visa_consular_pilot.csv"
    row_visa_pilot_markdown_path = processed_dir / "tdc_row_visa_consular_pilot.md"
    row_state_visa_timing_sensitivity_path = processed_dir / "tdc_row_state_visa_timing_sensitivity.csv"
    row_state_visa_timing_sensitivity_markdown_path = processed_dir / "tdc_row_state_visa_timing_sensitivity.md"
    row_recurring_pilot_review_path = processed_dir / "tdc_row_recurring_pilot_review.csv"
    row_recurring_pilot_review_markdown_path = processed_dir / "tdc_row_recurring_pilot_review.md"
    row_mrv_default_readiness_path = processed_dir / "tdc_row_mrv_default_readiness.csv"
    row_mrv_default_readiness_markdown_path = processed_dir / "tdc_row_mrv_default_readiness.md"
    row_mrv_payment_chain_review_path = processed_dir / "tdc_row_mrv_payment_chain_review.csv"
    row_mrv_payment_chain_review_markdown_path = processed_dir / "tdc_row_mrv_payment_chain_review.md"
    row_mrv_promotion_checklist_path = processed_dir / "tdc_row_mrv_promotion_checklist.csv"
    row_mrv_promotion_checklist_markdown_path = processed_dir / "tdc_row_mrv_promotion_checklist.md"
    row_mrv_source_map_path = processed_dir / "tdc_row_mrv_source_map.csv"
    row_mrv_source_map_markdown_path = processed_dir / "tdc_row_mrv_source_map.md"
    row_mrv_stop_gate_path = processed_dir / "tdc_row_mrv_stop_gate.csv"
    row_mrv_stop_gate_markdown_path = processed_dir / "tdc_row_mrv_stop_gate.md"
    bank_nontax_pilot_path = processed_dir / "tdc_bank_nontax_regulatory_pilot.csv"
    bank_nontax_pilot_markdown_path = processed_dir / "tdc_bank_nontax_regulatory_pilot.md"
    bank_occ_timing_sensitivity_path = processed_dir / "tdc_bank_occ_timing_sensitivity.csv"
    bank_occ_timing_sensitivity_markdown_path = processed_dir / "tdc_bank_occ_timing_sensitivity.md"
    tier3_receipt_candidate_sensitivity_path = processed_dir / "tdc_tier3_receipt_candidate_sensitivity.csv"
    tier3_receipt_candidate_sensitivity_markdown_path = processed_dir / "tdc_tier3_receipt_candidate_sensitivity.md"
    tier3_historical_bank_receipt_research_path = processed_dir / "tdc_tier3_historical_bank_receipt_research.csv"
    tier3_historical_bank_receipt_research_markdown_path = (
        processed_dir / "tdc_tier3_historical_bank_receipt_research.md"
    )
    fiscal_reconciliation_cells_path = processed_dir / "tdc_fiscal_reconciliation_cells.csv"
    fiscal_reconciliation_residuals_path = processed_dir / "tdc_fiscal_reconciliation_residuals.csv"
    fiscal_reconciliation_residuals_markdown_path = processed_dir / "tdc_fiscal_reconciliation_residuals.md"
    fiscal_source_quality_path = processed_dir / "tdc_fiscal_source_quality.csv"
    fiscal_source_quality_markdown_path = processed_dir / "tdc_fiscal_source_quality.md"
    receipt_promotion_review_path = processed_dir / "tdc_receipt_promotion_review.csv"
    receipt_promotion_review_markdown_path = processed_dir / "tdc_receipt_promotion_review.md"
    receipt_unblock_status_path = processed_dir / "tdc_receipt_unblock_status.csv"
    receipt_unblock_status_markdown_path = processed_dir / "tdc_receipt_unblock_status.md"
    project_goal_status_review_path = processed_dir / "tdc_project_goal_status_review.csv"
    project_goal_status_review_markdown_path = processed_dir / "tdc_project_goal_status_review.md"
    tier3_research_comparison_path = processed_dir / "tdc_tier3_research_comparison.csv"
    tier3_research_comparison_markdown_path = processed_dir / "tdc_tier3_research_comparison.md"
    downstream_estimator_contract_path = processed_dir / "tdc_downstream_estimator_contract.csv"
    downstream_estimator_contract_markdown_path = processed_dir / "tdc_downstream_estimator_contract.md"
    downstream_component_contribution_review_path = processed_dir / "tdc_downstream_component_contribution_review.csv"
    downstream_component_contribution_review_markdown_path = processed_dir / "tdc_downstream_component_contribution_review.md"
    downstream_estimator_gap_review_path = processed_dir / "tdc_downstream_estimator_gap_review.csv"
    downstream_estimator_gap_review_markdown_path = processed_dir / "tdc_downstream_estimator_gap_review.md"
    fiscal_receipt_boundary_review_path = processed_dir / "tdc_fiscal_receipt_boundary_review.csv"
    fiscal_receipt_boundary_review_markdown_path = processed_dir / "tdc_fiscal_receipt_boundary_review.md"
    downstream_deposit_effect_use_case_review_path = processed_dir / "tdc_downstream_deposit_effect_use_case_review.csv"
    downstream_deposit_effect_use_case_review_markdown_path = processed_dir / "tdc_downstream_deposit_effect_use_case_review.md"
    downstream_problem_variable_review_path = processed_dir / "tdc_downstream_problem_variable_review.csv"
    downstream_problem_variable_review_markdown_path = processed_dir / "tdc_downstream_problem_variable_review.md"
    downstream_deposit_effect_series_panel_path = processed_dir / "tdc_downstream_deposit_effect_series_panel.csv"
    downstream_deposit_effect_series_panel_markdown_path = processed_dir / "tdc_downstream_deposit_effect_series_panel.md"
    downstream_deposit_effect_comparison_panel_path = processed_dir / "tdc_downstream_deposit_effect_comparison_panel.csv"
    downstream_deposit_effect_comparison_panel_markdown_path = processed_dir / "tdc_downstream_deposit_effect_comparison_panel.md"
    downstream_handoff_bundle_path = processed_dir / "tdc_downstream_handoff_bundle.json"
    downstream_handoff_bundle_markdown_path = processed_dir / "tdc_downstream_handoff_bundle.md"
    downstream_ingest_manifest_path = processed_dir / "tdc_downstream_ingest_manifest.csv"
    downstream_ingest_manifest_markdown_path = processed_dir / "tdc_downstream_ingest_manifest.md"
    downstream_consistency_review_path = processed_dir / "tdc_downstream_consistency_review.csv"
    downstream_consistency_review_markdown_path = processed_dir / "tdc_downstream_consistency_review.md"
    backend_closeout_review_path = processed_dir / "tdc_backend_closeout_review.csv"
    backend_closeout_review_markdown_path = processed_dir / "tdc_backend_closeout_review.md"
    backend_release_check_path = processed_dir / "tdc_backend_release_check.csv"
    backend_release_check_markdown_path = processed_dir / "tdc_backend_release_check.md"
    theory_measurement_map_path = processed_dir / "tdc_theory_measurement_map.csv"
    theory_measurement_map_markdown_path = processed_dir / "tdc_theory_measurement_map.md"
    du_fiscal_flow_research_path = processed_dir / "tdc_du_fiscal_flow_research.csv"
    du_fiscal_flow_research_markdown_path = processed_dir / "tdc_du_fiscal_flow_research.md"
    row_mrv_nondefault_evidence_summary_path = processed_dir / "tdc_row_mrv_nondefault_evidence_summary.csv"
    row_mrv_nondefault_evidence_summary_markdown_path = processed_dir / "tdc_row_mrv_nondefault_evidence_summary.md"
    bank_receipt_default_readiness_path = processed_dir / "tdc_bank_receipt_default_readiness.csv"
    bank_receipt_default_readiness_markdown_path = processed_dir / "tdc_bank_receipt_default_readiness.md"
    bank_receipt_source_map_path = processed_dir / "tdc_bank_receipt_source_map.csv"
    bank_receipt_source_map_markdown_path = processed_dir / "tdc_bank_receipt_source_map.md"
    bank_receipt_stop_gate_path = processed_dir / "tdc_bank_receipt_stop_gate.csv"
    bank_receipt_stop_gate_markdown_path = processed_dir / "tdc_bank_receipt_stop_gate.md"
    bank_receipt_historical_promotion_path = processed_dir / "tdc_bank_receipt_historical_promotion.csv"
    bank_receipt_historical_promotion_markdown_path = processed_dir / "tdc_bank_receipt_historical_promotion.md"
    workstream_end_state_map_path = processed_dir / "tdc_workstream_end_state_map.csv"
    workstream_end_state_map_markdown_path = processed_dir / "tdc_workstream_end_state_map.md"
    monetary_stage0_path = processed_dir / "tdc_monetary_stage0_diagnostics.csv"
    monetary_stage0_markdown_path = processed_dir / "tdc_monetary_stage0_diagnostics.md"
    monetary_stage1_path = processed_dir / "tdc_monetary_stage1_controls.csv"
    monetary_stage1_markdown_path = processed_dir / "tdc_monetary_stage1_controls.md"
    monetary_overlap_audit_path = processed_dir / "tdc_monetary_control_overlap_audit.csv"
    monetary_overlap_audit_markdown_path = processed_dir / "tdc_monetary_control_overlap_audit.md"
    monetary_residual_interpretation_path = processed_dir / "tdc_monetary_residual_interpretation.csv"
    monetary_residual_interpretation_markdown_path = processed_dir / "tdc_monetary_residual_interpretation.md"
    monetary_target_wedge_path = processed_dir / "tdc_monetary_target_wedge.csv"
    monetary_target_wedge_markdown_path = processed_dir / "tdc_monetary_target_wedge.md"
    monetary_target_definition_bridge_path = processed_dir / "tdc_monetary_target_definition_bridge.csv"
    monetary_target_definition_bridge_markdown_path = processed_dir / "tdc_monetary_target_definition_bridge.md"
    monetary_target_definition_decomposition_path = processed_dir / "tdc_monetary_target_definition_decomposition.csv"
    monetary_target_definition_decomposition_markdown_path = (
        processed_dir / "tdc_monetary_target_definition_decomposition.md"
    )
    monetary_bank_target_stress_review_path = processed_dir / "tdc_monetary_bank_target_stress_review.csv"
    monetary_bank_target_stress_review_markdown_path = (
        processed_dir / "tdc_monetary_bank_target_stress_review.md"
    )
    monetary_bank_target_gap_attribution_path = processed_dir / "tdc_monetary_bank_target_gap_attribution.csv"
    monetary_bank_target_gap_attribution_markdown_path = (
        processed_dir / "tdc_monetary_bank_target_gap_attribution.md"
    )
    monetary_nonbank_depository_bridge_attribution_path = (
        processed_dir / "tdc_monetary_nonbank_depository_bridge_attribution.csv"
    )
    monetary_nonbank_depository_bridge_attribution_markdown_path = (
        processed_dir / "tdc_monetary_nonbank_depository_bridge_attribution.md"
    )
    monetary_bank_perimeter_gap_review_path = processed_dir / "tdc_monetary_bank_perimeter_gap_review.csv"
    monetary_bank_liability_candidate_audit_path = processed_dir / "tdc_monetary_bank_liability_candidate_audit.csv"
    monetary_bank_liability_candidate_audit_markdown_path = (
        processed_dir / "tdc_monetary_bank_liability_candidate_audit.md"
    )
    monetary_bank_perimeter_gap_review_markdown_path = (
        processed_dir / "tdc_monetary_bank_perimeter_gap_review.md"
    )
    monetary_bank_perimeter_source_map_path = processed_dir / "tdc_monetary_bank_perimeter_source_map.csv"
    monetary_bank_perimeter_source_map_markdown_path = (
        processed_dir / "tdc_monetary_bank_perimeter_source_map.md"
    )
    monetary_bank_liquid_source_review_path = processed_dir / "tdc_monetary_bank_liquid_source_review.csv"
    monetary_bank_liquid_source_review_markdown_path = (
        processed_dir / "tdc_monetary_bank_liquid_source_review.md"
    )
    monetary_bank_liquid_stop_gate_path = processed_dir / "tdc_monetary_bank_liquid_stop_gate.csv"
    monetary_bank_liquid_stop_gate_markdown_path = (
        processed_dir / "tdc_monetary_bank_liquid_stop_gate.md"
    )
    ncua_credit_union_bridge_path = processed_dir / "tdc_ncua_credit_union_deposit_bridge.csv"
    ncua_credit_union_bridge_markdown_path = processed_dir / "tdc_ncua_credit_union_deposit_bridge.md"
    fdic_savings_institution_bridge_path = processed_dir / "tdc_fdic_savings_institution_deposit_bridge.csv"
    fdic_savings_institution_bridge_markdown_path = processed_dir / "tdc_fdic_savings_institution_deposit_bridge.md"
    monetary_target_preference_review_path = processed_dir / "tdc_monetary_target_preference_review.csv"
    monetary_target_preference_review_markdown_path = processed_dir / "tdc_monetary_target_preference_review.md"
    input_audit_path = processed_dir / "tdc_input_audit.csv"
    input_audit_markdown_path = processed_dir / "tdc_input_audit.md"
    headline_validation_review_path = processed_dir / "tdc_headline_validation_review.csv"
    headline_validation_review_markdown_path = processed_dir / "tdc_headline_validation_review.md"
    method_meta_path = processed_dir / "method_meta.json"

    _, _, du_fiscal_flow_research = write_du_fiscal_flow_research(
        quarterly=quarterly,
        components=components,
        mts_outlays_path=Path(raw_dir) / "treasury__mts_outlays.csv",
        mts_receipts_path=Path(raw_dir) / "treasury__mts_receipts.csv",
        csv_path=du_fiscal_flow_research_path,
        markdown_path=du_fiscal_flow_research_markdown_path,
    )
    for column in [
        "tdc_du_fiscal_flow_first_pass_narrow",
        "tdc_du_fiscal_flow_first_pass_broad",
        "tdc_du_selected_domestic_nonfinancial_proxy",
        "tdc_du_residual_proxy_bank_only_ru",
        "tdc_du_residual_proxy_np_cu_ru",
        "tdc_du_residual_proxy_np_corp_cu_ru",
        "tdc_du_residual_proxy_full_cu_ru",
    ]:
        if column in du_fiscal_flow_research.columns:
            estimates[column] = du_fiscal_flow_research[column]
    for column in [
        "du_residual_tsy_purchase_proxy",
        "du_residual_tsy_purchase_bank_only_ru_proxy",
        "du_residual_tsy_purchase_np_cu_ru_proxy",
        "du_residual_tsy_purchase_np_corp_cu_ru_proxy",
        "du_residual_tsy_purchase_full_cu_ru_proxy",
        "du_residual_security_flow_proxy",
        "du_domestic_nonfinancial_security_flow_proxy",
        "du_broad_private_security_flow_proxy",
        "du_noninterest_outlay_proxy",
        "du_receipt_proxy",
        "du_coupon_proxy_direct_narrow",
        "du_coupon_proxy_direct_broad",
        "du_coupon_proxy_residual",
        "du_coupon_proxy_primary",
        "du_coupon_proxy_selected_narrow",
    ]:
        if column in du_fiscal_flow_research.columns:
            components[column] = du_fiscal_flow_research[column]

    method_meta["available_methods"] = list(estimates.columns)
    method_meta.setdefault("method_descriptions", {}).update(
        {
            "tdc_du_fiscal_flow_first_pass_narrow": (
                "Residual DU-facing fiscal-flow estimate using total Treasury cash totals, a residual DU Treasury-security purchase term, and residual DU coupon interest."
            ),
            "tdc_du_fiscal_flow_first_pass_broad": (
                "Residual DU-facing fiscal-flow estimate using total Treasury cash totals, a residual DU Treasury-security purchase term, and residual DU coupon interest."
            ),
            "tdc_du_selected_domestic_nonfinancial_proxy": (
                "Selected domestic nonfinancial DU-side diagnostic using the partial domestic-nonfinancial Treasury-security flow, DU noninterest outlays, DU receipts, and the direct narrow coupon diagnostic. Not a full DU residual object."
            ),
            "tdc_du_residual_proxy_bank_only_ru": (
                "DU residual sensitivity where credit unions remain inside DU and only Fed, ROW, and banks are removed from all-sector Treasury-security transactions."
            ),
            "tdc_du_residual_proxy_np_cu_ru": (
                "DU residual sensitivity where natural-person credit unions are included in the RU/depository subtraction block."
            ),
            "tdc_du_residual_proxy_np_corp_cu_ru": (
                "DU residual sensitivity where natural-person and corporate credit unions are included in the RU/depository subtraction block."
            ),
            "tdc_du_residual_proxy_full_cu_ru": (
                "DU residual sensitivity where the full credit-union Treasury-security transaction proxy is included in the RU/depository subtraction block."
            ),
        }
    )
    method_meta.setdefault("method_formulas", {}).update(
        {
            "tdc_du_fiscal_flow_first_pass_narrow": (
                "DU residual proxy = - residual DU Treasury-security purchases + DU noninterest outlay proxy - DU receipt proxy + DU residual coupon proxy. Residual DU Treasury-security purchases equal all-sector Treasury-security transactions minus Fed, ROW, bank, and credit-union Treasury-security transactions. DU residual coupon equals gross Treasury interest minus Fed, bank, and ROW coupon proxies."
            ),
            "tdc_du_fiscal_flow_first_pass_broad": (
                "DU residual proxy = - residual DU Treasury-security purchases + DU noninterest outlay proxy - DU receipt proxy + DU residual coupon proxy. Residual DU Treasury-security purchases equal all-sector Treasury-security transactions minus Fed, ROW, bank, and credit-union Treasury-security transactions. DU residual coupon equals gross Treasury interest minus Fed, bank, and ROW coupon proxies."
            ),
            "tdc_du_selected_domestic_nonfinancial_proxy": (
                "Selected DU proxy = selected domestic-nonfinancial security-flow proxy + DU noninterest outlay proxy - DU receipt proxy - direct narrow coupon diagnostic. This is a narrow selected-sector diagnostic, not a full residual DU estimate."
            ),
            "tdc_du_residual_proxy_bank_only_ru": (
                "DU residual, bank-only RU perimeter = - (all-sector Treasury-security transactions - Fed - ROW - bank Treasury-security transactions) + DU noninterest outlay proxy - DU receipt proxy + DU residual coupon proxy."
            ),
            "tdc_du_residual_proxy_np_cu_ru": (
                "DU residual, natural-person credit-union RU perimeter = bank-only RU perimeter minus natural-person credit-union Treasury-security transactions before applying the DU residual formula."
            ),
            "tdc_du_residual_proxy_np_corp_cu_ru": (
                "DU residual, natural-person plus corporate credit-union RU perimeter = bank-only RU perimeter minus natural-person and corporate credit-union Treasury-security transactions before applying the DU residual formula."
            ),
            "tdc_du_residual_proxy_full_cu_ru": (
                "DU residual, full credit-union RU perimeter = bank-only RU perimeter minus the full credit-union Treasury-security transaction proxy before applying the DU residual formula."
            ),
        }
    )

    quarterly_to_write = quarterly.copy()
    quarterly_to_write.index.name = "date"
    quarterly_to_write.to_csv(quarterly_path)

    estimates_to_write = estimates.copy()
    estimates_to_write.index.name = "date"
    estimates_to_write.to_csv(estimates_path)

    components_to_write = components.copy()
    components_to_write.index.name = "date"
    components_to_write.to_csv(components_path)

    corrections_to_write = corrections.copy()
    corrections_to_write.index.name = "date"
    corrections_to_write.to_csv(corrections_path)

    _, _, post2022_attribution = write_post2022_bank_only_attribution(
        estimates,
        corrections,
        csv_path=post2022_attribution_path,
        markdown_path=post2022_attribution_markdown_path,
    )
    _, _, input_audit = write_input_audit(
        quarterly,
        series_meta,
        csv_path=input_audit_path,
        markdown_path=input_audit_markdown_path,
    )
    _, _, headline_validation_review = write_headline_validation_review(
        estimates,
        corrections,
        csv_path=headline_validation_review_path,
        markdown_path=headline_validation_review_markdown_path,
        input_audit=input_audit,
    )
    _, _, bea_row_receipts_benchmark = write_bea_row_receipts_benchmark(
        quarterly,
        csv_path=bea_row_receipts_benchmark_path,
        markdown_path=bea_row_receipts_benchmark_markdown_path,
    )

    tier3_source_diagnostics = None
    mts_outlays_path = Path(raw_dir) / "treasury__mts_outlays.csv"
    if mts_outlays_path.exists():
        _, _, tier3_source_diagnostics = write_tier3_source_diagnostics(
            mts_outlays_path=mts_outlays_path,
            csv_path=tier3_source_diag_path,
            markdown_path=tier3_source_diag_markdown_path,
        )

    tier3_receipt_source_diagnostics = None
    tier3_receipt_upper_bound_sensitivity = None
    bank_corp_tax_receipts_bridge = None
    bank_minor_industry_availability = None
    receipt_account_candidates = None
    receipt_account_crosswalk = None
    row_receipt_family_review = None
    row_visa_consular_pilot = None
    row_state_visa_timing_sensitivity = None
    row_recurring_pilot_review = None
    row_mrv_default_readiness = None
    row_mrv_payment_chain_review = None
    row_mrv_promotion_checklist = None
    row_mrv_source_map = None
    row_mrv_stop_gate = None
    bank_nontax_regulatory_pilot = None
    bank_occ_timing_sensitivity = None
    tier3_receipt_candidate_sensitivity = None
    tier3_historical_bank_receipt_research = None
    fiscal_reconciliation_cells = None
    fiscal_reconciliation_residuals = None
    fiscal_source_quality = None
    receipt_promotion_review = None
    receipt_unblock_status = None
    project_goal_status_review = None
    tier3_research_comparison = None
    row_mrv_nondefault_evidence_summary = None
    bank_receipt_default_readiness = None
    bank_receipt_source_map = None
    bank_receipt_stop_gate = None
    bank_receipt_historical_promotion = None
    workstream_end_state_map = None
    monetary_stage0_diagnostics = None
    monetary_stage1_controls = None
    monetary_control_overlap_audit = None
    monetary_residual_interpretation = None
    monetary_target_wedge = None
    monetary_target_definition_bridge = None
    monetary_target_definition_decomposition = None
    monetary_bank_target_stress_review = None
    monetary_bank_target_gap_attribution = None
    monetary_nonbank_depository_bridge_attribution = None
    monetary_bank_liability_candidate_audit = None
    monetary_bank_perimeter_gap_review = None
    monetary_bank_perimeter_source_map = None
    monetary_bank_liquid_source_review = None
    monetary_bank_liquid_stop_gate = None
    ncua_credit_union_deposit_bridge = None
    fdic_savings_institution_deposit_bridge = None
    monetary_target_preference_review = None
    irs_soi_bank_minor_industry_availability_path = Path(raw_dir) / "irs__soi_bank_minor_industry_availability.csv"
    if irs_soi_bank_minor_industry_availability_path.exists():
        _, _, bank_minor_industry_availability = write_bank_minor_industry_share_availability(
            input_path=irs_soi_bank_minor_industry_availability_path,
            csv_path=bank_minor_industry_availability_path,
            markdown_path=bank_minor_industry_availability_markdown_path,
        )
    mts_receipts_path = Path(raw_dir) / "treasury__mts_receipts.csv"
    if mts_receipts_path.exists():
        _, _, tier3_receipt_source_diagnostics = write_tier3_receipt_source_diagnostics(
            mts_receipts_path=mts_receipts_path,
            csv_path=tier3_receipt_diag_path,
            markdown_path=tier3_receipt_diag_markdown_path,
            revenue_collections_path=(Path(raw_dir) / "treasury__revenue_collections.csv"),
        )
        irs_soi_bank_tax_shares_path = Path(raw_dir) / "irs__soi_bank_tax_shares.csv"
        if irs_soi_bank_tax_shares_path.exists():
            _, _, bank_corp_tax_receipts_bridge = write_bank_corp_tax_receipts_bridge(
                mts_receipts_path=mts_receipts_path,
                irs_soi_bank_tax_shares_path=irs_soi_bank_tax_shares_path,
                csv_path=bank_corp_tax_bridge_path,
                markdown_path=bank_corp_tax_bridge_markdown_path,
            )
        if (
            tier3_receipt_source_diagnostics is not None
            and "rcm_bank_channel_total_candidate" in tier3_receipt_source_diagnostics.columns
        ):
            _, _, tier3_receipt_upper_bound_sensitivity = write_tier3_bank_receipt_upper_bound_sensitivity(
                estimates,
                tier3_receipt_source_diagnostics,
                csv_path=tier3_receipt_upper_bound_path,
                markdown_path=tier3_receipt_upper_bound_markdown_path,
            )
    receipts_by_department_path = Path(raw_dir) / "treasury__receipts_by_department.csv"
    if receipts_by_department_path.exists():
        _, _, receipt_account_candidates = write_receipt_account_candidates(
            receipts_by_department_path=receipts_by_department_path,
            csv_path=receipt_account_candidates_path,
            markdown_path=receipt_account_candidates_markdown_path,
        )
        combined_statement_accounts_path = Path(raw_dir) / "support__combined_statement_receipt_accounts.csv"
        _, _, receipt_account_crosswalk = write_receipt_account_crosswalk(
            csv_path=receipt_account_crosswalk_path,
            markdown_path=receipt_account_crosswalk_markdown_path,
            receipt_account_candidates=receipt_account_candidates,
            combined_statement_accounts_path=combined_statement_accounts_path if combined_statement_accounts_path.exists() else None,
        )
        _, _, row_receipt_family_review = write_row_receipt_family_review(
            csv_path=row_receipt_family_review_path,
            markdown_path=row_receipt_family_review_markdown_path,
            receipt_account_candidates=receipt_account_candidates,
            receipt_account_crosswalk=receipt_account_crosswalk,
        )
        _, _, row_visa_consular_pilot = write_row_visa_consular_pilot(
            receipt_account_candidates,
            csv_path=row_visa_pilot_path,
            markdown_path=row_visa_pilot_markdown_path,
        )
        state_visa_monthly_path = Path(raw_dir) / "state__visa_issuances_monthly.csv"
        if state_visa_monthly_path.exists():
            _, _, row_state_visa_timing_sensitivity = write_row_state_visa_timing_sensitivity(
                estimates,
                row_visa_consular_pilot,
                state_visa_monthly_path=state_visa_monthly_path,
                csv_path=row_state_visa_timing_sensitivity_path,
                markdown_path=row_state_visa_timing_sensitivity_markdown_path,
            )
            _, _, row_mrv_default_readiness = write_row_mrv_default_readiness(
                csv_path=row_mrv_default_readiness_path,
                markdown_path=row_mrv_default_readiness_markdown_path,
                receipt_account_candidates=receipt_account_candidates,
                receipt_account_crosswalk=receipt_account_crosswalk,
                row_visa_consular_pilot=row_visa_consular_pilot,
                row_state_visa_timing_sensitivity=row_state_visa_timing_sensitivity,
            )
            _, _, row_recurring_pilot_review = write_row_recurring_pilot_review(
                csv_path=row_recurring_pilot_review_path,
                markdown_path=row_recurring_pilot_review_markdown_path,
                row_visa_consular_pilot=row_visa_consular_pilot,
                row_state_visa_timing_sensitivity=row_state_visa_timing_sensitivity,
                row_mrv_default_readiness=row_mrv_default_readiness,
            )
            _, _, row_mrv_payment_chain_review = write_row_mrv_payment_chain_review(
                csv_path=row_mrv_payment_chain_review_path,
                markdown_path=row_mrv_payment_chain_review_markdown_path,
                receipt_account_crosswalk=receipt_account_crosswalk,
                row_visa_consular_pilot=row_visa_consular_pilot,
                row_state_visa_timing_sensitivity=row_state_visa_timing_sensitivity,
            )
            _, _, row_mrv_promotion_checklist = write_row_mrv_promotion_checklist(
                csv_path=row_mrv_promotion_checklist_path,
                markdown_path=row_mrv_promotion_checklist_markdown_path,
                row_mrv_default_readiness=row_mrv_default_readiness,
                row_mrv_payment_chain_review=row_mrv_payment_chain_review,
                row_recurring_pilot_review=row_recurring_pilot_review,
            )
            _, _, row_mrv_source_map = write_row_mrv_source_map(
                csv_path=row_mrv_source_map_path,
                markdown_path=row_mrv_source_map_markdown_path,
                row_mrv_promotion_checklist=row_mrv_promotion_checklist,
            )
            _, _, row_mrv_stop_gate = write_row_mrv_stop_gate(
                csv_path=row_mrv_stop_gate_path,
                markdown_path=row_mrv_stop_gate_markdown_path,
                row_mrv_promotion_checklist=row_mrv_promotion_checklist,
                row_mrv_source_map=row_mrv_source_map,
            )
        _, _, bank_nontax_regulatory_pilot = write_bank_nontax_regulatory_pilot(
            receipt_account_candidates,
            csv_path=bank_nontax_pilot_path,
            markdown_path=bank_nontax_pilot_markdown_path,
        )
        _, _, bank_occ_timing_sensitivity = write_bank_occ_timing_sensitivity(
            estimates,
            bank_nontax_regulatory_pilot,
            csv_path=bank_occ_timing_sensitivity_path,
            markdown_path=bank_occ_timing_sensitivity_markdown_path,
        )
    if any(
        df is not None and not df.empty
        for df in [bank_corp_tax_receipts_bridge, bank_occ_timing_sensitivity, row_state_visa_timing_sensitivity]
    ):
        _, _, tier3_receipt_candidate_sensitivity = write_tier3_receipt_candidate_sensitivity(
            estimates,
            bank_corp_tax_bridge=bank_corp_tax_receipts_bridge,
            bank_occ_timing_sensitivity=bank_occ_timing_sensitivity,
            row_state_visa_timing_sensitivity=row_state_visa_timing_sensitivity,
            csv_path=tier3_receipt_candidate_sensitivity_path,
            markdown_path=tier3_receipt_candidate_sensitivity_markdown_path,
        )

    (
        _,
        _,
        _,
        fiscal_reconciliation_cells,
        fiscal_reconciliation_residuals,
        fiscal_source_quality,
    ) = write_fiscal_reconciliation_outputs(
        estimates,
        components,
        corrections,
        cells_csv_path=fiscal_reconciliation_cells_path,
        residuals_csv_path=fiscal_reconciliation_residuals_path,
        source_quality_csv_path=fiscal_source_quality_path,
        residuals_markdown_path=fiscal_reconciliation_residuals_markdown_path,
        source_quality_markdown_path=fiscal_source_quality_markdown_path,
        bea_row_receipts_benchmark=bea_row_receipts_benchmark,
        bank_corp_tax_receipts_bridge=bank_corp_tax_receipts_bridge,
        tier3_source_diagnostics=tier3_source_diagnostics,
        tier3_receipt_source_diagnostics=tier3_receipt_source_diagnostics,
        bank_occ_timing_sensitivity=bank_occ_timing_sensitivity,
        row_state_visa_timing_sensitivity=row_state_visa_timing_sensitivity,
    )
    irs_soi_bank_tax_shares = None
    irs_soi_bank_tax_shares_path = Path(raw_dir) / "irs__soi_bank_tax_shares.csv"
    if irs_soi_bank_tax_shares_path.exists():
        irs_soi_bank_tax_shares = pd.read_csv(irs_soi_bank_tax_shares_path)
    _, _, bank_receipt_default_readiness = write_bank_receipt_default_readiness(
        csv_path=bank_receipt_default_readiness_path,
        markdown_path=bank_receipt_default_readiness_markdown_path,
        bank_corp_tax_receipts_bridge=bank_corp_tax_receipts_bridge,
        irs_soi_bank_tax_shares=irs_soi_bank_tax_shares,
        bank_minor_industry_availability=bank_minor_industry_availability,
        estimates=estimates,
        tier3_receipt_candidate_sensitivity=tier3_receipt_candidate_sensitivity,
        bank_occ_timing_sensitivity=bank_occ_timing_sensitivity,
        tier3_receipt_source_diagnostics=tier3_receipt_source_diagnostics,
    )
    _, _, bank_receipt_historical_promotion = write_bank_receipt_historical_promotion(
        csv_path=bank_receipt_historical_promotion_path,
        markdown_path=bank_receipt_historical_promotion_markdown_path,
        bank_corp_tax_receipts_bridge=bank_corp_tax_receipts_bridge,
    )
    _, _, bank_receipt_source_map = write_bank_receipt_source_map(
        csv_path=bank_receipt_source_map_path,
        markdown_path=bank_receipt_source_map_markdown_path,
        bank_receipt_default_readiness=bank_receipt_default_readiness,
        bank_receipt_historical_promotion=bank_receipt_historical_promotion,
    )
    _, _, bank_receipt_stop_gate = write_bank_receipt_stop_gate(
        csv_path=bank_receipt_stop_gate_path,
        markdown_path=bank_receipt_stop_gate_markdown_path,
        bank_receipt_default_readiness=bank_receipt_default_readiness,
        bank_receipt_historical_promotion=bank_receipt_historical_promotion,
        bank_receipt_source_map=bank_receipt_source_map,
    )
    _, _, receipt_promotion_review = write_receipt_promotion_review(
        csv_path=receipt_promotion_review_path,
        markdown_path=receipt_promotion_review_markdown_path,
        bea_row_receipts_benchmark=bea_row_receipts_benchmark,
        bank_corp_tax_receipts_bridge=bank_corp_tax_receipts_bridge,
        receipt_account_candidates=receipt_account_candidates,
        receipt_account_crosswalk=receipt_account_crosswalk,
        row_receipt_family_review=row_receipt_family_review,
        row_recurring_pilot_review=row_recurring_pilot_review,
        row_mrv_promotion_checklist=row_mrv_promotion_checklist,
        row_mrv_stop_gate=row_mrv_stop_gate,
        bank_receipt_stop_gate=bank_receipt_stop_gate,
        bank_occ_timing_sensitivity=bank_occ_timing_sensitivity,
        row_state_visa_timing_sensitivity=row_state_visa_timing_sensitivity,
        tier3_receipt_source_diagnostics=tier3_receipt_source_diagnostics,
    )
    _, _, receipt_unblock_status = write_receipt_unblock_status(
        csv_path=receipt_unblock_status_path,
        markdown_path=receipt_unblock_status_markdown_path,
        bank_receipt_historical_promotion=bank_receipt_historical_promotion,
        bank_receipt_default_readiness=bank_receipt_default_readiness,
        bank_receipt_source_map=bank_receipt_source_map,
        bank_receipt_stop_gate=bank_receipt_stop_gate,
        row_mrv_promotion_checklist=row_mrv_promotion_checklist,
        row_mrv_source_map=row_mrv_source_map,
        row_mrv_stop_gate=row_mrv_stop_gate,
        receipt_promotion_review=receipt_promotion_review,
    )
    _, _, tier3_historical_bank_receipt_research = write_tier3_historical_bank_receipt_research(
        estimates,
        bank_receipt_historical_promotion=bank_receipt_historical_promotion,
        csv_path=tier3_historical_bank_receipt_research_path,
        markdown_path=tier3_historical_bank_receipt_research_markdown_path,
    )
    _, _, tier3_research_comparison = write_tier3_research_comparison(
        csv_path=tier3_research_comparison_path,
        markdown_path=tier3_research_comparison_markdown_path,
        estimates=estimates,
        tier3_historical_bank_receipt_research=tier3_historical_bank_receipt_research,
        receipt_unblock_status=receipt_unblock_status,
    )
    _, _, monetary_stage0_diagnostics = write_monetary_stage0_diagnostics(
        quarterly=quarterly,
        estimates=estimates,
        csv_path=monetary_stage0_path,
        markdown_path=monetary_stage0_markdown_path,
    )
    ncua_credit_union_bridge_raw_path = Path(raw_dir) / "ncua__credit_union_deposit_bridge.csv"
    if ncua_credit_union_bridge_raw_path.exists():
        _, _, ncua_credit_union_deposit_bridge = write_ncua_credit_union_deposit_bridge(
            raw_bridge_path=ncua_credit_union_bridge_raw_path,
            quarterly=quarterly,
            csv_path=ncua_credit_union_bridge_path,
            markdown_path=ncua_credit_union_bridge_markdown_path,
        )
    fdic_savings_institution_bridge_raw_path = Path(raw_dir) / "fdic__savings_institution_deposit_bridge.csv"
    if fdic_savings_institution_bridge_raw_path.exists():
        _, _, fdic_savings_institution_deposit_bridge = write_fdic_savings_institution_deposit_bridge(
            raw_bridge_path=fdic_savings_institution_bridge_raw_path,
            quarterly=quarterly,
            csv_path=fdic_savings_institution_bridge_path,
            markdown_path=fdic_savings_institution_bridge_markdown_path,
        )
    _, _, monetary_stage1_controls = write_monetary_stage1_controls(
        quarterly=quarterly,
        monetary_stage0=monetary_stage0_diagnostics,
        csv_path=monetary_stage1_path,
        markdown_path=monetary_stage1_markdown_path,
    )
    _, _, monetary_control_overlap_audit = write_monetary_control_overlap_audit(
        monetary_stage1_controls=monetary_stage1_controls,
        csv_path=monetary_overlap_audit_path,
        markdown_path=monetary_overlap_audit_markdown_path,
    )
    _, _, monetary_residual_interpretation = write_monetary_residual_interpretation(
        monetary_stage1_controls=monetary_stage1_controls,
        csv_path=monetary_residual_interpretation_path,
        markdown_path=monetary_residual_interpretation_markdown_path,
    )
    _, _, monetary_target_wedge = write_monetary_target_wedge(
        monetary_stage1_controls=monetary_stage1_controls,
        csv_path=monetary_target_wedge_path,
        markdown_path=monetary_target_wedge_markdown_path,
    )
    _, _, monetary_target_definition_bridge = write_monetary_target_definition_bridge(
        monetary_stage0_diagnostics=monetary_stage0_diagnostics,
        monetary_target_wedge=monetary_target_wedge,
        csv_path=monetary_target_definition_bridge_path,
        markdown_path=monetary_target_definition_bridge_markdown_path,
    )
    _, _, monetary_target_definition_decomposition = write_monetary_target_definition_decomposition(
        monetary_target_definition_bridge=monetary_target_definition_bridge,
        csv_path=monetary_target_definition_decomposition_path,
        markdown_path=monetary_target_definition_decomposition_markdown_path,
    )
    _, _, monetary_target_preference_review = write_monetary_target_preference_review(
        monetary_residual_interpretation=monetary_residual_interpretation,
        monetary_target_wedge=monetary_target_wedge,
        csv_path=monetary_target_preference_review_path,
        markdown_path=monetary_target_preference_review_markdown_path,
    )
    _, _, monetary_bank_target_stress_review = write_monetary_bank_target_stress_review(
        monetary_target_definition_decomposition=monetary_target_definition_decomposition,
        monetary_target_preference_review=monetary_target_preference_review,
        csv_path=monetary_bank_target_stress_review_path,
        markdown_path=monetary_bank_target_stress_review_markdown_path,
    )
    _, _, monetary_bank_target_gap_attribution = write_monetary_bank_target_gap_attribution(
        monetary_residual_interpretation=monetary_residual_interpretation,
        monetary_target_definition_decomposition=monetary_target_definition_decomposition,
        csv_path=monetary_bank_target_gap_attribution_path,
        markdown_path=monetary_bank_target_gap_attribution_markdown_path,
    )
    _, _, monetary_nonbank_depository_bridge_attribution = write_monetary_nonbank_depository_bridge_attribution(
        monetary_stage0_diagnostics=monetary_stage0_diagnostics,
        monetary_target_definition_decomposition=monetary_target_definition_decomposition,
        csv_path=monetary_nonbank_depository_bridge_attribution_path,
        markdown_path=monetary_nonbank_depository_bridge_attribution_markdown_path,
    )
    _, _, monetary_bank_liability_candidate_audit = write_monetary_bank_liability_candidate_audit(
        monetary_stage0_diagnostics=monetary_stage0_diagnostics,
        monetary_target_definition_decomposition=monetary_target_definition_decomposition,
        csv_path=monetary_bank_liability_candidate_audit_path,
        markdown_path=monetary_bank_liability_candidate_audit_markdown_path,
    )
    _, _, monetary_bank_perimeter_gap_review = write_monetary_bank_perimeter_gap_review(
        quarterly=quarterly,
        monetary_bank_target_gap_attribution=monetary_bank_target_gap_attribution,
        monetary_nonbank_depository_bridge_attribution=monetary_nonbank_depository_bridge_attribution,
        monetary_bank_liability_candidate_audit=monetary_bank_liability_candidate_audit,
        csv_path=monetary_bank_perimeter_gap_review_path,
        markdown_path=monetary_bank_perimeter_gap_review_markdown_path,
    )
    _, _, monetary_bank_perimeter_source_map = write_monetary_bank_perimeter_source_map(
        monetary_bank_perimeter_gap_review=monetary_bank_perimeter_gap_review,
        csv_path=monetary_bank_perimeter_source_map_path,
        markdown_path=monetary_bank_perimeter_source_map_markdown_path,
    )
    _, _, monetary_bank_liquid_source_review = write_monetary_bank_liquid_source_review(
        monetary_bank_liability_candidate_audit=monetary_bank_liability_candidate_audit,
        monetary_bank_perimeter_gap_review=monetary_bank_perimeter_gap_review,
        monetary_bank_perimeter_source_map=monetary_bank_perimeter_source_map,
        csv_path=monetary_bank_liquid_source_review_path,
        markdown_path=monetary_bank_liquid_source_review_markdown_path,
    )
    _, _, monetary_bank_liquid_stop_gate = write_monetary_bank_liquid_stop_gate(
        monetary_bank_liquid_source_review=monetary_bank_liquid_source_review,
        monetary_bank_perimeter_gap_review=monetary_bank_perimeter_gap_review,
        csv_path=monetary_bank_liquid_stop_gate_path,
        markdown_path=monetary_bank_liquid_stop_gate_markdown_path,
    )
    _, _, workstream_end_state_map = write_workstream_end_state_map(
        csv_path=workstream_end_state_map_path,
        markdown_path=workstream_end_state_map_markdown_path,
        receipt_unblock_status=receipt_unblock_status,
        bank_receipt_stop_gate=bank_receipt_stop_gate,
        row_mrv_stop_gate=row_mrv_stop_gate,
        monetary_target_preference_review=monetary_target_preference_review,
        monetary_bank_liquid_stop_gate=monetary_bank_liquid_stop_gate,
        fiscal_source_quality=fiscal_source_quality,
    )
    _, _, row_mrv_nondefault_evidence_summary = write_row_mrv_nondefault_evidence_summary(
        csv_path=row_mrv_nondefault_evidence_summary_path,
        markdown_path=row_mrv_nondefault_evidence_summary_markdown_path,
        row_mrv_payment_chain_review=row_mrv_payment_chain_review,
        row_mrv_promotion_checklist=row_mrv_promotion_checklist,
        row_mrv_source_map=row_mrv_source_map,
        row_mrv_stop_gate=row_mrv_stop_gate,
    )
    _, _, project_goal_status_review = write_project_goal_status_review(
        csv_path=project_goal_status_review_path,
        markdown_path=project_goal_status_review_markdown_path,
        estimates=estimates,
        corrections=corrections,
        receipt_unblock_status=receipt_unblock_status,
        workstream_end_state_map=workstream_end_state_map,
        fiscal_source_quality=fiscal_source_quality,
        monetary_target_preference_review=monetary_target_preference_review,
        monetary_bank_liquid_stop_gate=monetary_bank_liquid_stop_gate,
    )
    _, _, downstream_estimator_contract = write_downstream_estimator_contract(
        csv_path=downstream_estimator_contract_path,
        markdown_path=downstream_estimator_contract_markdown_path,
        estimates=estimates,
        method_meta=method_meta,
        input_audit=input_audit,
        receipt_unblock_status=receipt_unblock_status,
        project_goal_status_review=project_goal_status_review,
        tier3_research_comparison=tier3_research_comparison,
        bea_row_receipts_benchmark=bea_row_receipts_benchmark,
        row_mrv_nondefault_evidence_summary=row_mrv_nondefault_evidence_summary,
        monetary_target_preference_review=monetary_target_preference_review,
        workstream_end_state_map=workstream_end_state_map,
    )
    _, _, downstream_component_contribution_review = write_downstream_component_contribution_review(
        csv_path=downstream_component_contribution_review_path,
        markdown_path=downstream_component_contribution_review_markdown_path,
        estimates=estimates,
        components=components,
        corrections=corrections,
        tier3_historical_bank_receipt_research=tier3_historical_bank_receipt_research,
        receipt_unblock_status=receipt_unblock_status,
    )
    _, _, downstream_estimator_gap_review = write_downstream_estimator_gap_review(
        csv_path=downstream_estimator_gap_review_path,
        markdown_path=downstream_estimator_gap_review_markdown_path,
        estimates=estimates,
        components=components,
        corrections=corrections,
        tier3_historical_bank_receipt_research=tier3_historical_bank_receipt_research,
    )
    _, _, fiscal_receipt_boundary_review = write_fiscal_receipt_boundary_review(
        csv_path=fiscal_receipt_boundary_review_path,
        markdown_path=fiscal_receipt_boundary_review_markdown_path,
        fiscal_source_quality=fiscal_source_quality,
        receipt_unblock_status=receipt_unblock_status,
        tier3_research_comparison=tier3_research_comparison,
        downstream_estimator_gap_review=downstream_estimator_gap_review,
        row_mrv_nondefault_evidence_summary=row_mrv_nondefault_evidence_summary,
    )
    _, _, downstream_deposit_effect_use_case_review = write_downstream_deposit_effect_use_case_review(
        csv_path=downstream_deposit_effect_use_case_review_path,
        markdown_path=downstream_deposit_effect_use_case_review_markdown_path,
        downstream_estimator_contract=downstream_estimator_contract,
        downstream_estimator_gap_review=downstream_estimator_gap_review,
        fiscal_receipt_boundary_review=fiscal_receipt_boundary_review,
        project_goal_status_review=project_goal_status_review,
    )
    _, _, downstream_problem_variable_review = write_downstream_problem_variable_review(
        csv_path=downstream_problem_variable_review_path,
        markdown_path=downstream_problem_variable_review_markdown_path,
        fiscal_source_quality=fiscal_source_quality,
        downstream_estimator_gap_review=downstream_estimator_gap_review,
        fiscal_receipt_boundary_review=fiscal_receipt_boundary_review,
    )
    _, _, downstream_deposit_effect_series_panel = write_downstream_deposit_effect_series_panel(
        csv_path=downstream_deposit_effect_series_panel_path,
        markdown_path=downstream_deposit_effect_series_panel_markdown_path,
        estimates=estimates,
        tier3_historical_bank_receipt_research=tier3_historical_bank_receipt_research,
        row_state_visa_timing_sensitivity=row_state_visa_timing_sensitivity,
        receipt_unblock_status=receipt_unblock_status,
    )
    _, _, downstream_deposit_effect_comparison_panel = write_downstream_deposit_effect_comparison_panel(
        csv_path=downstream_deposit_effect_comparison_panel_path,
        markdown_path=downstream_deposit_effect_comparison_panel_markdown_path,
        estimates=estimates,
        corrections=corrections,
        tier3_historical_bank_receipt_research=tier3_historical_bank_receipt_research,
        row_state_visa_timing_sensitivity=row_state_visa_timing_sensitivity,
        receipt_unblock_status=receipt_unblock_status,
    )
    _, _, downstream_handoff_bundle = write_downstream_handoff_bundle(
        json_path=downstream_handoff_bundle_path,
        markdown_path=downstream_handoff_bundle_markdown_path,
        project_goal_status_review=project_goal_status_review,
        receipt_unblock_status=receipt_unblock_status,
        downstream_estimator_contract=downstream_estimator_contract,
        downstream_deposit_effect_use_case_review=downstream_deposit_effect_use_case_review,
        downstream_problem_variable_review=downstream_problem_variable_review,
        fiscal_receipt_boundary_review=fiscal_receipt_boundary_review,
        downstream_deposit_effect_series_panel=downstream_deposit_effect_series_panel,
        downstream_deposit_effect_comparison_panel=downstream_deposit_effect_comparison_panel,
    )
    _, _, downstream_ingest_manifest = write_downstream_ingest_manifest(
        csv_path=downstream_ingest_manifest_path,
        markdown_path=downstream_ingest_manifest_markdown_path,
        downstream_estimator_contract=downstream_estimator_contract,
        downstream_deposit_effect_use_case_review=downstream_deposit_effect_use_case_review,
        downstream_problem_variable_review=downstream_problem_variable_review,
        fiscal_receipt_boundary_review=fiscal_receipt_boundary_review,
        project_goal_status_review=project_goal_status_review,
        receipt_unblock_status=receipt_unblock_status,
        downstream_deposit_effect_series_panel=downstream_deposit_effect_series_panel,
        downstream_deposit_effect_comparison_panel=downstream_deposit_effect_comparison_panel,
    )
    _, _, downstream_consistency_review = write_downstream_consistency_review(
        csv_path=downstream_consistency_review_path,
        markdown_path=downstream_consistency_review_markdown_path,
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
        backend_closeout_review=None,
        tier3_research_comparison=tier3_research_comparison,
        workstream_end_state_map=workstream_end_state_map,
    )
    _, _, backend_closeout_review = write_backend_closeout_review(
        csv_path=backend_closeout_review_path,
        markdown_path=backend_closeout_review_markdown_path,
        project_goal_status_review=project_goal_status_review,
        receipt_unblock_status=receipt_unblock_status,
        downstream_consistency_review=downstream_consistency_review,
        workstream_end_state_map=workstream_end_state_map,
    )
    _, _, backend_release_check = write_backend_release_check(
        csv_path=backend_release_check_path,
        markdown_path=backend_release_check_markdown_path,
        downstream_consistency_review=downstream_consistency_review,
        backend_closeout_review=backend_closeout_review,
    )
    _, _, theory_measurement_map = write_theory_measurement_map(
        csv_path=theory_measurement_map_path,
        markdown_path=theory_measurement_map_markdown_path,
    )
    _, _, downstream_handoff_bundle = write_downstream_handoff_bundle(
        json_path=downstream_handoff_bundle_path,
        markdown_path=downstream_handoff_bundle_markdown_path,
        project_goal_status_review=project_goal_status_review,
        receipt_unblock_status=receipt_unblock_status,
        downstream_estimator_contract=downstream_estimator_contract,
        downstream_deposit_effect_use_case_review=downstream_deposit_effect_use_case_review,
        downstream_problem_variable_review=downstream_problem_variable_review,
        fiscal_receipt_boundary_review=fiscal_receipt_boundary_review,
        downstream_deposit_effect_series_panel=downstream_deposit_effect_series_panel,
        downstream_deposit_effect_comparison_panel=downstream_deposit_effect_comparison_panel,
        backend_closeout_review=backend_closeout_review,
        backend_release_check=backend_release_check,
    )
    _, _, downstream_consistency_review = write_downstream_consistency_review(
        csv_path=downstream_consistency_review_path,
        markdown_path=downstream_consistency_review_markdown_path,
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
    _, _, backend_closeout_review = write_backend_closeout_review(
        csv_path=backend_closeout_review_path,
        markdown_path=backend_closeout_review_markdown_path,
        project_goal_status_review=project_goal_status_review,
        receipt_unblock_status=receipt_unblock_status,
        downstream_consistency_review=downstream_consistency_review,
        workstream_end_state_map=workstream_end_state_map,
    )
    _, _, backend_release_check = write_backend_release_check(
        csv_path=backend_release_check_path,
        markdown_path=backend_release_check_markdown_path,
        downstream_consistency_review=downstream_consistency_review,
        backend_closeout_review=backend_closeout_review,
    )
    _, _, downstream_handoff_bundle = write_downstream_handoff_bundle(
        json_path=downstream_handoff_bundle_path,
        markdown_path=downstream_handoff_bundle_markdown_path,
        project_goal_status_review=project_goal_status_review,
        receipt_unblock_status=receipt_unblock_status,
        downstream_estimator_contract=downstream_estimator_contract,
        downstream_deposit_effect_use_case_review=downstream_deposit_effect_use_case_review,
        downstream_problem_variable_review=downstream_problem_variable_review,
        fiscal_receipt_boundary_review=fiscal_receipt_boundary_review,
        downstream_deposit_effect_series_panel=downstream_deposit_effect_series_panel,
        downstream_deposit_effect_comparison_panel=downstream_deposit_effect_comparison_panel,
        backend_closeout_review=backend_closeout_review,
        backend_release_check=backend_release_check,
    )

    write_json(method_meta_path, method_meta)

    figure_outputs: list[str] = []
    if figures_dir is not None:
        figure_outputs = build_all_figures(
            estimates,
            components,
            figures_dir,
            tier3_historical_bank_receipt_research=tier3_historical_bank_receipt_research,
            tier3_research_comparison=tier3_research_comparison,
            monetary_stage0=monetary_stage0_diagnostics,
            monetary_stage1=monetary_stage1_controls,
            monetary_target_wedge=monetary_target_wedge,
            monetary_target_preference_review=monetary_target_preference_review,
        )

    site_outputs: dict[str, str] = {}
    if site_dir is not None:
        site_outputs = export_site_bundle(
            estimates,
            components,
            corrections,
            quarterly,
            series_meta,
            method_meta,
            site_dir,
            research_frames={
                "receipt_unblock_status": receipt_unblock_status,
                "receipt_account_crosswalk": receipt_account_crosswalk,
                "project_goal_status_review": project_goal_status_review,
                "workstream_end_state_map": workstream_end_state_map,
                "tier3_research_comparison": tier3_research_comparison,
                "row_mrv_nondefault_evidence_summary": row_mrv_nondefault_evidence_summary,
                "bank_receipt_historical_promotion": bank_receipt_historical_promotion,
                "tier3_historical_bank_receipt_research": tier3_historical_bank_receipt_research,
                "bank_receipt_stop_gate": bank_receipt_stop_gate,
                "row_mrv_stop_gate": row_mrv_stop_gate,
                "fiscal_reconciliation_residuals": fiscal_reconciliation_residuals,
                "fiscal_source_quality": fiscal_source_quality,
                "monetary_target_preference_review": monetary_target_preference_review,
                "downstream_estimator_contract": downstream_estimator_contract,
                "downstream_component_contribution_review": downstream_component_contribution_review,
                "downstream_estimator_gap_review": downstream_estimator_gap_review,
                "fiscal_receipt_boundary_review": fiscal_receipt_boundary_review,
                "downstream_deposit_effect_use_case_review": downstream_deposit_effect_use_case_review,
                "downstream_problem_variable_review": downstream_problem_variable_review,
                "downstream_deposit_effect_series_panel": downstream_deposit_effect_series_panel,
                "downstream_deposit_effect_comparison_panel": downstream_deposit_effect_comparison_panel,
                "backend_closeout_review": backend_closeout_review,
                "backend_release_check": backend_release_check,
                "theory_measurement_map": theory_measurement_map,
                "du_fiscal_flow_research": du_fiscal_flow_research,
                "headline_validation_review": headline_validation_review,
                "bill_discount_validation": bill_discount_validation,
            },
        )

    return {
        "quarterly": quarterly,
        "estimates": estimates,
        "components": components,
        "corrections": corrections,
        "post2022_attribution": post2022_attribution,
        "tier3_source_diagnostics": tier3_source_diagnostics,
        "tier3_receipt_source_diagnostics": tier3_receipt_source_diagnostics,
        "tier3_bank_receipt_upper_bound_sensitivity": tier3_receipt_upper_bound_sensitivity,
        "bea_row_receipts_benchmark": bea_row_receipts_benchmark,
        "bank_corp_tax_receipts_bridge": bank_corp_tax_receipts_bridge,
        "receipt_account_candidates": receipt_account_candidates,
        "receipt_account_crosswalk": receipt_account_crosswalk,
        "row_receipt_family_review": row_receipt_family_review,
        "row_visa_consular_pilot": row_visa_consular_pilot,
        "row_state_visa_timing_sensitivity": row_state_visa_timing_sensitivity,
        "row_recurring_pilot_review": row_recurring_pilot_review,
        "row_mrv_default_readiness": row_mrv_default_readiness,
        "row_mrv_payment_chain_review": row_mrv_payment_chain_review,
        "row_mrv_promotion_checklist": row_mrv_promotion_checklist,
        "row_mrv_source_map": row_mrv_source_map,
        "row_mrv_stop_gate": row_mrv_stop_gate,
        "bank_nontax_regulatory_pilot": bank_nontax_regulatory_pilot,
        "bank_occ_timing_sensitivity": bank_occ_timing_sensitivity,
        "tier3_receipt_candidate_sensitivity": tier3_receipt_candidate_sensitivity,
        "tier3_historical_bank_receipt_research": tier3_historical_bank_receipt_research,
        "fiscal_reconciliation_cells": fiscal_reconciliation_cells,
        "fiscal_reconciliation_residuals": fiscal_reconciliation_residuals,
        "fiscal_source_quality": fiscal_source_quality,
        "receipt_promotion_review": receipt_promotion_review,
        "receipt_unblock_status": receipt_unblock_status,
        "project_goal_status_review": project_goal_status_review,
        "tier3_research_comparison": tier3_research_comparison,
        "downstream_estimator_contract": downstream_estimator_contract,
        "downstream_component_contribution_review": downstream_component_contribution_review,
        "downstream_estimator_gap_review": downstream_estimator_gap_review,
        "fiscal_receipt_boundary_review": fiscal_receipt_boundary_review,
        "downstream_deposit_effect_use_case_review": downstream_deposit_effect_use_case_review,
        "downstream_problem_variable_review": downstream_problem_variable_review,
        "downstream_deposit_effect_series_panel": downstream_deposit_effect_series_panel,
        "downstream_deposit_effect_comparison_panel": downstream_deposit_effect_comparison_panel,
        "downstream_handoff_bundle": downstream_handoff_bundle,
        "downstream_ingest_manifest": downstream_ingest_manifest,
        "downstream_consistency_review": downstream_consistency_review,
        "backend_closeout_review": backend_closeout_review,
        "backend_release_check": backend_release_check,
        "theory_measurement_map": theory_measurement_map,
        "du_fiscal_flow_research": du_fiscal_flow_research,
        "row_mrv_nondefault_evidence_summary": row_mrv_nondefault_evidence_summary,
        "bank_receipt_default_readiness": bank_receipt_default_readiness,
        "bank_receipt_source_map": bank_receipt_source_map,
        "bank_receipt_stop_gate": bank_receipt_stop_gate,
        "bank_receipt_historical_promotion": bank_receipt_historical_promotion,
        "workstream_end_state_map": workstream_end_state_map,
        "bank_minor_industry_share_availability": bank_minor_industry_availability,
        "monetary_stage0_diagnostics": monetary_stage0_diagnostics,
        "monetary_stage1_controls": monetary_stage1_controls,
        "monetary_control_overlap_audit": monetary_control_overlap_audit,
        "monetary_residual_interpretation": monetary_residual_interpretation,
        "monetary_target_wedge": monetary_target_wedge,
        "monetary_target_definition_bridge": monetary_target_definition_bridge,
        "monetary_target_definition_decomposition": monetary_target_definition_decomposition,
        "monetary_bank_target_stress_review": monetary_bank_target_stress_review,
        "monetary_bank_target_gap_attribution": monetary_bank_target_gap_attribution,
        "monetary_nonbank_depository_bridge_attribution": monetary_nonbank_depository_bridge_attribution,
        "monetary_bank_liability_candidate_audit": monetary_bank_liability_candidate_audit,
        "monetary_bank_perimeter_gap_review": monetary_bank_perimeter_gap_review,
        "monetary_bank_perimeter_source_map": monetary_bank_perimeter_source_map,
        "monetary_bank_liquid_source_review": monetary_bank_liquid_source_review,
        "monetary_bank_liquid_stop_gate": monetary_bank_liquid_stop_gate,
        "ncua_credit_union_deposit_bridge": ncua_credit_union_deposit_bridge,
        "fdic_savings_institution_deposit_bridge": fdic_savings_institution_deposit_bridge,
        "monetary_target_preference_review": monetary_target_preference_review,
        "input_audit": input_audit,
        "headline_validation_review": headline_validation_review,
        "mmf_rrp_quarterly_adjustments": mmf_rrp_quarterly,
        "mmf_rrp_source_comparison": mmf_rrp_source_comparison,
        "gse_rrp_boundary_check": gse_rrp_boundary_check,
        "bill_discount_validation": bill_discount_validation,
        "series_meta": series_meta,
        "method_meta": method_meta,
        "quarterly_path": str(quarterly_path),
        "estimates_path": str(estimates_path),
        "components_path": str(components_path),
        "corrections_path": str(corrections_path),
        "post2022_attribution_path": str(post2022_attribution_path),
        "post2022_attribution_markdown_path": str(post2022_attribution_markdown_path),
        "input_audit_path": str(input_audit_path),
        "input_audit_markdown_path": str(input_audit_markdown_path),
        "headline_validation_review_path": str(headline_validation_review_path),
        "headline_validation_review_markdown_path": str(headline_validation_review_markdown_path),
        "mmf_rrp_fund_month_adjustments_path": str(mmf_rrp_monthly_path)
        if mmf_rrp_quarterly is not None
        else None,
        "mmf_rrp_quarterly_adjustments_path": str(mmf_rrp_quarterly_path)
        if mmf_rrp_quarterly is not None
        else None,
        "mmf_rrp_adjustment_markdown_path": str(mmf_rrp_markdown_path)
        if mmf_rrp_quarterly is not None
        else None,
        "mmf_rrp_source_comparison_path": str(mmf_rrp_source_comparison_path)
        if mmf_rrp_source_comparison is not None
        else None,
        "mmf_rrp_source_comparison_markdown_path": str(mmf_rrp_source_comparison_markdown_path)
        if mmf_rrp_source_comparison is not None
        else None,
        "gse_rrp_boundary_check_path": str(gse_rrp_boundary_path),
        "gse_rrp_boundary_check_markdown_path": str(gse_rrp_boundary_markdown_path),
        "bill_discount_validation_path": str(bill_discount_validation_path)
        if bill_discount_validation is not None
        else None,
        "bill_discount_validation_markdown_path": str(bill_discount_validation_markdown_path)
        if bill_discount_validation is not None
        else None,
        "bea_row_receipts_benchmark_path": str(bea_row_receipts_benchmark_path) if not bea_row_receipts_benchmark.empty else None,
        "bea_row_receipts_benchmark_markdown_path": str(bea_row_receipts_benchmark_markdown_path)
        if not bea_row_receipts_benchmark.empty
        else None,
        "bank_corp_tax_receipts_bridge_path": str(bank_corp_tax_bridge_path) if bank_corp_tax_receipts_bridge is not None else None,
        "bank_corp_tax_receipts_bridge_markdown_path": str(bank_corp_tax_bridge_markdown_path)
        if bank_corp_tax_receipts_bridge is not None
        else None,
        "receipt_account_candidates_path": str(receipt_account_candidates_path) if receipt_account_candidates is not None else None,
        "receipt_account_candidates_markdown_path": str(receipt_account_candidates_markdown_path)
        if receipt_account_candidates is not None
        else None,
        "receipt_account_crosswalk_path": str(receipt_account_crosswalk_path) if receipt_account_crosswalk is not None else None,
        "receipt_account_crosswalk_markdown_path": str(receipt_account_crosswalk_markdown_path)
        if receipt_account_crosswalk is not None
        else None,
        "row_receipt_family_review_path": str(row_receipt_family_review_path) if row_receipt_family_review is not None else None,
        "row_receipt_family_review_markdown_path": str(row_receipt_family_review_markdown_path)
        if row_receipt_family_review is not None
        else None,
        "row_visa_consular_pilot_path": str(row_visa_pilot_path) if row_visa_consular_pilot is not None else None,
        "row_visa_consular_pilot_markdown_path": str(row_visa_pilot_markdown_path)
        if row_visa_consular_pilot is not None
        else None,
        "row_state_visa_timing_sensitivity_path": str(row_state_visa_timing_sensitivity_path)
        if row_state_visa_timing_sensitivity is not None
        else None,
        "row_state_visa_timing_sensitivity_markdown_path": str(row_state_visa_timing_sensitivity_markdown_path)
        if row_state_visa_timing_sensitivity is not None
        else None,
        "row_recurring_pilot_review_path": str(row_recurring_pilot_review_path)
        if row_recurring_pilot_review is not None
        else None,
        "row_recurring_pilot_review_markdown_path": str(row_recurring_pilot_review_markdown_path)
        if row_recurring_pilot_review is not None
        else None,
        "row_mrv_default_readiness_path": str(row_mrv_default_readiness_path)
        if row_mrv_default_readiness is not None
        else None,
        "row_mrv_default_readiness_markdown_path": str(row_mrv_default_readiness_markdown_path)
        if row_mrv_default_readiness is not None
        else None,
        "row_mrv_payment_chain_review_path": str(row_mrv_payment_chain_review_path)
        if row_mrv_payment_chain_review is not None
        else None,
        "row_mrv_payment_chain_review_markdown_path": str(row_mrv_payment_chain_review_markdown_path)
        if row_mrv_payment_chain_review is not None
        else None,
        "row_mrv_promotion_checklist_path": str(row_mrv_promotion_checklist_path)
        if row_mrv_promotion_checklist is not None
        else None,
        "row_mrv_promotion_checklist_markdown_path": str(row_mrv_promotion_checklist_markdown_path)
        if row_mrv_promotion_checklist is not None
        else None,
        "row_mrv_source_map_path": str(row_mrv_source_map_path)
        if row_mrv_source_map is not None
        else None,
        "row_mrv_source_map_markdown_path": str(row_mrv_source_map_markdown_path)
        if row_mrv_source_map is not None
        else None,
        "row_mrv_stop_gate_path": str(row_mrv_stop_gate_path)
        if row_mrv_stop_gate is not None
        else None,
        "row_mrv_stop_gate_markdown_path": str(row_mrv_stop_gate_markdown_path)
        if row_mrv_stop_gate is not None
        else None,
        "bank_nontax_regulatory_pilot_path": str(bank_nontax_pilot_path) if bank_nontax_regulatory_pilot is not None else None,
        "bank_nontax_regulatory_pilot_markdown_path": str(bank_nontax_pilot_markdown_path)
        if bank_nontax_regulatory_pilot is not None
        else None,
        "bank_occ_timing_sensitivity_path": str(bank_occ_timing_sensitivity_path)
        if bank_occ_timing_sensitivity is not None
        else None,
        "bank_occ_timing_sensitivity_markdown_path": str(bank_occ_timing_sensitivity_markdown_path)
        if bank_occ_timing_sensitivity is not None
        else None,
        "tier3_receipt_candidate_sensitivity_path": str(tier3_receipt_candidate_sensitivity_path)
        if tier3_receipt_candidate_sensitivity is not None
        else None,
        "tier3_receipt_candidate_sensitivity_markdown_path": str(tier3_receipt_candidate_sensitivity_markdown_path)
        if tier3_receipt_candidate_sensitivity is not None
        else None,
        "tier3_historical_bank_receipt_research_path": str(tier3_historical_bank_receipt_research_path)
        if tier3_historical_bank_receipt_research is not None
        else None,
        "tier3_historical_bank_receipt_research_markdown_path": str(tier3_historical_bank_receipt_research_markdown_path)
        if tier3_historical_bank_receipt_research is not None
        else None,
        "fiscal_reconciliation_cells_path": str(fiscal_reconciliation_cells_path),
        "fiscal_reconciliation_residuals_path": str(fiscal_reconciliation_residuals_path),
        "fiscal_reconciliation_residuals_markdown_path": str(fiscal_reconciliation_residuals_markdown_path),
        "fiscal_source_quality_path": str(fiscal_source_quality_path),
        "fiscal_source_quality_markdown_path": str(fiscal_source_quality_markdown_path),
        "receipt_promotion_review_path": str(receipt_promotion_review_path),
        "receipt_promotion_review_markdown_path": str(receipt_promotion_review_markdown_path),
        "receipt_unblock_status_path": str(receipt_unblock_status_path),
        "receipt_unblock_status_markdown_path": str(receipt_unblock_status_markdown_path),
        "project_goal_status_review_path": str(project_goal_status_review_path),
        "project_goal_status_review_markdown_path": str(project_goal_status_review_markdown_path),
        "tier3_research_comparison_path": str(tier3_research_comparison_path),
        "tier3_research_comparison_markdown_path": str(tier3_research_comparison_markdown_path),
        "downstream_estimator_contract_path": str(downstream_estimator_contract_path),
        "downstream_estimator_contract_markdown_path": str(downstream_estimator_contract_markdown_path),
        "downstream_component_contribution_review_path": str(downstream_component_contribution_review_path),
        "downstream_component_contribution_review_markdown_path": str(
            downstream_component_contribution_review_markdown_path
        ),
        "downstream_estimator_gap_review_path": str(downstream_estimator_gap_review_path),
        "downstream_estimator_gap_review_markdown_path": str(downstream_estimator_gap_review_markdown_path),
        "fiscal_receipt_boundary_review_path": str(fiscal_receipt_boundary_review_path),
        "fiscal_receipt_boundary_review_markdown_path": str(fiscal_receipt_boundary_review_markdown_path),
        "downstream_deposit_effect_use_case_review_path": str(downstream_deposit_effect_use_case_review_path),
        "downstream_deposit_effect_use_case_review_markdown_path": str(
            downstream_deposit_effect_use_case_review_markdown_path
        ),
        "downstream_problem_variable_review_path": str(downstream_problem_variable_review_path),
        "downstream_problem_variable_review_markdown_path": str(
            downstream_problem_variable_review_markdown_path
        ),
        "downstream_deposit_effect_series_panel_path": str(downstream_deposit_effect_series_panel_path),
        "downstream_deposit_effect_series_panel_markdown_path": str(
            downstream_deposit_effect_series_panel_markdown_path
        ),
        "downstream_deposit_effect_comparison_panel_path": str(
            downstream_deposit_effect_comparison_panel_path
        ),
        "downstream_deposit_effect_comparison_panel_markdown_path": str(
            downstream_deposit_effect_comparison_panel_markdown_path
        ),
        "downstream_handoff_bundle_path": str(downstream_handoff_bundle_path),
        "downstream_handoff_bundle_markdown_path": str(downstream_handoff_bundle_markdown_path),
        "downstream_ingest_manifest_path": str(downstream_ingest_manifest_path),
        "downstream_ingest_manifest_markdown_path": str(downstream_ingest_manifest_markdown_path),
        "downstream_consistency_review_path": str(downstream_consistency_review_path),
        "downstream_consistency_review_markdown_path": str(downstream_consistency_review_markdown_path),
        "backend_closeout_review_path": str(backend_closeout_review_path),
        "backend_closeout_review_markdown_path": str(backend_closeout_review_markdown_path),
        "backend_release_check_path": str(backend_release_check_path),
        "backend_release_check_markdown_path": str(backend_release_check_markdown_path),
        "theory_measurement_map_path": str(theory_measurement_map_path),
        "theory_measurement_map_markdown_path": str(theory_measurement_map_markdown_path),
        "row_mrv_nondefault_evidence_summary_path": str(row_mrv_nondefault_evidence_summary_path),
        "row_mrv_nondefault_evidence_summary_markdown_path": str(
            row_mrv_nondefault_evidence_summary_markdown_path
        ),
        "bank_receipt_default_readiness_path": str(bank_receipt_default_readiness_path),
        "bank_receipt_default_readiness_markdown_path": str(bank_receipt_default_readiness_markdown_path),
        "bank_receipt_source_map_path": str(bank_receipt_source_map_path),
        "bank_receipt_source_map_markdown_path": str(bank_receipt_source_map_markdown_path),
        "bank_receipt_stop_gate_path": str(bank_receipt_stop_gate_path),
        "bank_receipt_stop_gate_markdown_path": str(bank_receipt_stop_gate_markdown_path),
        "bank_receipt_historical_promotion_path": str(bank_receipt_historical_promotion_path),
        "bank_receipt_historical_promotion_markdown_path": str(bank_receipt_historical_promotion_markdown_path),
        "bank_minor_industry_share_availability_path": str(bank_minor_industry_availability_path),
        "bank_minor_industry_share_availability_markdown_path": str(bank_minor_industry_availability_markdown_path),
        "monetary_stage0_diagnostics_path": str(monetary_stage0_path),
        "monetary_stage0_diagnostics_markdown_path": str(monetary_stage0_markdown_path),
        "monetary_stage1_controls_path": str(monetary_stage1_path),
        "monetary_stage1_controls_markdown_path": str(monetary_stage1_markdown_path),
        "monetary_control_overlap_audit_path": str(monetary_overlap_audit_path),
        "monetary_control_overlap_audit_markdown_path": str(monetary_overlap_audit_markdown_path),
        "monetary_residual_interpretation_path": str(monetary_residual_interpretation_path),
        "monetary_residual_interpretation_markdown_path": str(monetary_residual_interpretation_markdown_path),
        "monetary_target_wedge_path": str(monetary_target_wedge_path),
        "monetary_target_wedge_markdown_path": str(monetary_target_wedge_markdown_path),
        "monetary_target_definition_bridge_path": str(monetary_target_definition_bridge_path),
        "monetary_target_definition_bridge_markdown_path": str(monetary_target_definition_bridge_markdown_path),
        "monetary_target_definition_decomposition_path": str(monetary_target_definition_decomposition_path),
        "monetary_target_definition_decomposition_markdown_path": str(
            monetary_target_definition_decomposition_markdown_path
        ),
        "monetary_bank_target_stress_review_path": str(monetary_bank_target_stress_review_path),
        "monetary_bank_target_stress_review_markdown_path": str(
            monetary_bank_target_stress_review_markdown_path
        ),
        "monetary_bank_target_gap_attribution_path": str(monetary_bank_target_gap_attribution_path),
        "monetary_bank_target_gap_attribution_markdown_path": str(
            monetary_bank_target_gap_attribution_markdown_path
        ),
        "monetary_nonbank_depository_bridge_attribution_path": str(
            monetary_nonbank_depository_bridge_attribution_path
        ),
        "monetary_nonbank_depository_bridge_attribution_markdown_path": str(
            monetary_nonbank_depository_bridge_attribution_markdown_path
        ),
        "monetary_bank_liability_candidate_audit_path": str(monetary_bank_liability_candidate_audit_path),
        "monetary_bank_liability_candidate_audit_markdown_path": str(
            monetary_bank_liability_candidate_audit_markdown_path
        ),
        "monetary_bank_perimeter_gap_review_path": str(monetary_bank_perimeter_gap_review_path),
        "monetary_bank_perimeter_gap_review_markdown_path": str(
            monetary_bank_perimeter_gap_review_markdown_path
        ),
        "monetary_bank_perimeter_source_map_path": str(monetary_bank_perimeter_source_map_path),
        "monetary_bank_perimeter_source_map_markdown_path": str(
            monetary_bank_perimeter_source_map_markdown_path
        ),
        "monetary_bank_liquid_source_review_path": str(monetary_bank_liquid_source_review_path),
        "monetary_bank_liquid_source_review_markdown_path": str(
            monetary_bank_liquid_source_review_markdown_path
        ),
        "monetary_bank_liquid_stop_gate_path": str(monetary_bank_liquid_stop_gate_path),
        "monetary_bank_liquid_stop_gate_markdown_path": str(
            monetary_bank_liquid_stop_gate_markdown_path
        ),
        "ncua_credit_union_deposit_bridge_path": str(ncua_credit_union_bridge_path)
        if ncua_credit_union_deposit_bridge is not None
        else None,
        "ncua_credit_union_deposit_bridge_markdown_path": str(ncua_credit_union_bridge_markdown_path)
        if ncua_credit_union_deposit_bridge is not None
        else None,
        "fdic_savings_institution_deposit_bridge_path": str(fdic_savings_institution_bridge_path)
        if fdic_savings_institution_deposit_bridge is not None
        else None,
        "fdic_savings_institution_deposit_bridge_markdown_path": str(fdic_savings_institution_bridge_markdown_path)
        if fdic_savings_institution_deposit_bridge is not None
        else None,
        "monetary_target_preference_review_path": str(monetary_target_preference_review_path),
        "monetary_target_preference_review_markdown_path": str(monetary_target_preference_review_markdown_path),
        "tier3_source_diagnostics_path": str(tier3_source_diag_path) if tier3_source_diagnostics is not None else None,
        "tier3_source_diagnostics_markdown_path": str(tier3_source_diag_markdown_path) if tier3_source_diagnostics is not None else None,
        "tier3_receipt_source_diagnostics_path": str(tier3_receipt_diag_path) if tier3_receipt_source_diagnostics is not None else None,
        "tier3_receipt_source_diagnostics_markdown_path": str(tier3_receipt_diag_markdown_path) if tier3_receipt_source_diagnostics is not None else None,
        "tier3_bank_receipt_upper_bound_sensitivity_path": str(tier3_receipt_upper_bound_path)
        if tier3_receipt_upper_bound_sensitivity is not None
        else None,
        "tier3_bank_receipt_upper_bound_sensitivity_markdown_path": str(tier3_receipt_upper_bound_markdown_path)
        if tier3_receipt_upper_bound_sensitivity is not None
        else None,
        "method_meta_path": str(method_meta_path),
        "figure_outputs": figure_outputs,
        "site_outputs": site_outputs,
    }
