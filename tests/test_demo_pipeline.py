from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tdc_estimator.demo import generate_synthetic_raw_bundle
from tdc_estimator.pipeline import run_estimation_pipeline


def test_demo_pipeline_runs(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    figures_dir = tmp_path / "figures"
    site_dir = tmp_path / "site"

    generate_synthetic_raw_bundle(raw_dir, seed=7)
    result = run_estimation_pipeline(
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        figures_dir=figures_dir,
        site_dir=site_dir,
    )

    assert "tdc_base_bank_only_ru_flow" in result["estimates"].columns
    assert "tdc_tier1_fed_corrected_bank_only_ru_flow" in result["estimates"].columns
    assert "tdc_tier2_interest_corrected_bank_only_ru_flow" in result["estimates"].columns
    assert "tdc_tier3_fiscal_corrected_bank_only_ru_flow" in result["estimates"].columns
    assert "tdc_base_broad_depository_np_cu_ru_flow" in result["estimates"].columns
    assert (processed_dir / "tdc_estimates.csv").exists()
    assert (figures_dir / "tdc_method_comparison.png").exists()
    assert (figures_dir / "tdc_credit_union_increments.png").exists()
    assert (figures_dir / "tdc_monetary_target_preference.png").exists()
    assert (processed_dir / "tdc_corrections.csv").exists()
    assert (processed_dir / "tdc_post2022_bank_only_attribution.csv").exists()
    assert (processed_dir / "tdc_post2022_bank_only_attribution.md").exists()
    assert (processed_dir / "tdc_input_audit.csv").exists()
    assert (processed_dir / "tdc_input_audit.md").exists()
    assert not (processed_dir / "tdc_bea_row_receipts_benchmark.csv").exists()
    assert not (processed_dir / "tdc_bea_row_receipts_benchmark.md").exists()
    assert not (processed_dir / "tdc_bank_corp_tax_receipts_bridge.csv").exists()
    assert not (processed_dir / "tdc_bank_corp_tax_receipts_bridge.md").exists()
    assert not (processed_dir / "tdc_bank_minor_industry_share_availability.csv").exists()
    assert not (processed_dir / "tdc_bank_minor_industry_share_availability.md").exists()
    assert not (processed_dir / "tdc_receipt_account_candidates.csv").exists()
    assert not (processed_dir / "tdc_receipt_account_candidates.md").exists()
    assert not (processed_dir / "tdc_receipt_account_crosswalk.csv").exists()
    assert not (processed_dir / "tdc_receipt_account_crosswalk.md").exists()
    assert not (processed_dir / "tdc_row_receipt_family_review.csv").exists()
    assert not (processed_dir / "tdc_row_receipt_family_review.md").exists()
    assert not (processed_dir / "tdc_row_visa_consular_pilot.csv").exists()
    assert not (processed_dir / "tdc_row_visa_consular_pilot.md").exists()
    assert not (processed_dir / "tdc_bank_nontax_regulatory_pilot.csv").exists()
    assert not (processed_dir / "tdc_bank_nontax_regulatory_pilot.md").exists()
    assert not (processed_dir / "tdc_bank_occ_timing_sensitivity.csv").exists()
    assert not (processed_dir / "tdc_bank_occ_timing_sensitivity.md").exists()
    assert not (processed_dir / "tdc_tier3_receipt_candidate_sensitivity.csv").exists()
    assert not (processed_dir / "tdc_tier3_receipt_candidate_sensitivity.md").exists()
    assert (processed_dir / "tdc_fiscal_reconciliation_cells.csv").exists()
    assert (processed_dir / "tdc_fiscal_reconciliation_residuals.csv").exists()
    assert (processed_dir / "tdc_fiscal_source_quality.csv").exists()
    assert (processed_dir / "tdc_receipt_promotion_review.csv").exists()
    assert (processed_dir / "tdc_receipt_promotion_review.md").exists()
    assert (processed_dir / "tdc_receipt_unblock_status.csv").exists()
    assert (processed_dir / "tdc_receipt_unblock_status.md").exists()
    assert (processed_dir / "tdc_project_goal_status_review.csv").exists()
    assert (processed_dir / "tdc_project_goal_status_review.md").exists()
    assert (processed_dir / "tdc_workstream_end_state_map.csv").exists()
    assert (processed_dir / "tdc_workstream_end_state_map.md").exists()
    assert (processed_dir / "tdc_tier3_research_comparison.csv").exists()
    assert (processed_dir / "tdc_tier3_research_comparison.md").exists()
    assert (processed_dir / "tdc_downstream_estimator_contract.csv").exists()
    assert (processed_dir / "tdc_downstream_estimator_contract.md").exists()
    assert (processed_dir / "tdc_downstream_component_contribution_review.csv").exists()
    assert (processed_dir / "tdc_downstream_component_contribution_review.md").exists()
    assert (processed_dir / "tdc_downstream_estimator_gap_review.csv").exists()
    assert (processed_dir / "tdc_downstream_estimator_gap_review.md").exists()
    assert (processed_dir / "tdc_fiscal_receipt_boundary_review.csv").exists()
    assert (processed_dir / "tdc_fiscal_receipt_boundary_review.md").exists()
    assert (processed_dir / "tdc_downstream_deposit_effect_use_case_review.csv").exists()
    assert (processed_dir / "tdc_downstream_deposit_effect_use_case_review.md").exists()
    assert (processed_dir / "tdc_downstream_problem_variable_review.csv").exists()
    assert (processed_dir / "tdc_downstream_problem_variable_review.md").exists()
    assert (processed_dir / "tdc_downstream_deposit_effect_series_panel.csv").exists()
    assert (processed_dir / "tdc_downstream_deposit_effect_series_panel.md").exists()
    assert (processed_dir / "tdc_downstream_deposit_effect_comparison_panel.csv").exists()
    assert (processed_dir / "tdc_downstream_deposit_effect_comparison_panel.md").exists()
    assert (processed_dir / "tdc_downstream_handoff_bundle.json").exists()
    assert (processed_dir / "tdc_downstream_handoff_bundle.md").exists()
    assert (processed_dir / "tdc_downstream_ingest_manifest.csv").exists()
    assert (processed_dir / "tdc_downstream_ingest_manifest.md").exists()
    assert (processed_dir / "tdc_downstream_consistency_review.csv").exists()
    assert (processed_dir / "tdc_downstream_consistency_review.md").exists()
    assert (processed_dir / "tdc_backend_closeout_review.csv").exists()
    assert (processed_dir / "tdc_backend_closeout_review.md").exists()
    assert (processed_dir / "tdc_backend_release_check.csv").exists()
    assert (processed_dir / "tdc_backend_release_check.md").exists()
    assert (processed_dir / "tdc_theory_measurement_map.csv").exists()
    assert (processed_dir / "tdc_theory_measurement_map.md").exists()
    assert (processed_dir / "tdc_row_mrv_nondefault_evidence_summary.csv").exists()
    assert (processed_dir / "tdc_row_mrv_nondefault_evidence_summary.md").exists()
    assert (processed_dir / "tdc_bank_receipt_default_readiness.csv").exists()
    assert (processed_dir / "tdc_bank_receipt_default_readiness.md").exists()
    assert (processed_dir / "tdc_bank_receipt_source_map.csv").exists()
    assert (processed_dir / "tdc_bank_receipt_source_map.md").exists()
    assert (processed_dir / "tdc_bank_receipt_stop_gate.csv").exists()
    assert (processed_dir / "tdc_bank_receipt_stop_gate.md").exists()
    assert (processed_dir / "tdc_bank_receipt_historical_promotion.csv").exists()
    assert (processed_dir / "tdc_bank_receipt_historical_promotion.md").exists()
    assert (processed_dir / "tdc_tier3_historical_bank_receipt_research.csv").exists()
    assert (processed_dir / "tdc_tier3_historical_bank_receipt_research.md").exists()
    assert (processed_dir / "tdc_monetary_stage0_diagnostics.csv").exists()
    assert (processed_dir / "tdc_monetary_stage0_diagnostics.md").exists()
    assert (processed_dir / "tdc_monetary_stage1_controls.csv").exists()
    assert (processed_dir / "tdc_monetary_stage1_controls.md").exists()
    assert (processed_dir / "tdc_monetary_control_overlap_audit.csv").exists()
    assert (processed_dir / "tdc_monetary_control_overlap_audit.md").exists()
    assert (processed_dir / "tdc_monetary_residual_interpretation.csv").exists()
    assert (processed_dir / "tdc_monetary_residual_interpretation.md").exists()
    assert (processed_dir / "tdc_monetary_target_wedge.csv").exists()
    assert (processed_dir / "tdc_monetary_target_wedge.md").exists()
    assert (processed_dir / "tdc_monetary_target_definition_bridge.csv").exists()
    assert (processed_dir / "tdc_monetary_target_definition_bridge.md").exists()
    assert (processed_dir / "tdc_monetary_target_definition_decomposition.csv").exists()
    assert (processed_dir / "tdc_monetary_target_definition_decomposition.md").exists()
    assert (processed_dir / "tdc_monetary_bank_target_stress_review.csv").exists()
    assert (processed_dir / "tdc_monetary_bank_target_stress_review.md").exists()
    assert (processed_dir / "tdc_monetary_bank_target_gap_attribution.csv").exists()
    assert (processed_dir / "tdc_monetary_bank_target_gap_attribution.md").exists()
    assert (processed_dir / "tdc_monetary_nonbank_depository_bridge_attribution.csv").exists()
    assert (processed_dir / "tdc_monetary_nonbank_depository_bridge_attribution.md").exists()
    assert (processed_dir / "tdc_monetary_bank_liability_candidate_audit.csv").exists()
    assert (processed_dir / "tdc_monetary_bank_liability_candidate_audit.md").exists()
    assert (processed_dir / "tdc_monetary_bank_perimeter_gap_review.csv").exists()
    assert (processed_dir / "tdc_monetary_bank_perimeter_gap_review.md").exists()
    assert (processed_dir / "tdc_monetary_bank_perimeter_source_map.csv").exists()
    assert (processed_dir / "tdc_monetary_bank_perimeter_source_map.md").exists()
    assert (processed_dir / "tdc_monetary_bank_liquid_source_review.csv").exists()
    assert (processed_dir / "tdc_monetary_bank_liquid_source_review.md").exists()
    assert (processed_dir / "tdc_monetary_bank_liquid_stop_gate.csv").exists()
    assert (processed_dir / "tdc_monetary_bank_liquid_stop_gate.md").exists()
    assert (processed_dir / "tdc_ncua_credit_union_deposit_bridge.csv").exists()
    assert (processed_dir / "tdc_ncua_credit_union_deposit_bridge.md").exists()
    assert (processed_dir / "tdc_fdic_savings_institution_deposit_bridge.csv").exists()
    assert (processed_dir / "tdc_fdic_savings_institution_deposit_bridge.md").exists()
    assert (processed_dir / "tdc_monetary_target_preference_review.csv").exists()
    assert (processed_dir / "tdc_monetary_target_preference_review.md").exists()
    assert not (processed_dir / "tdc_row_state_visa_timing_sensitivity.csv").exists()
    assert not (processed_dir / "tdc_row_state_visa_timing_sensitivity.md").exists()
    assert not (processed_dir / "tdc_row_recurring_pilot_review.csv").exists()
    assert not (processed_dir / "tdc_row_recurring_pilot_review.md").exists()
    assert not (processed_dir / "tdc_row_mrv_default_readiness.csv").exists()
    assert not (processed_dir / "tdc_row_mrv_default_readiness.md").exists()
    assert not (processed_dir / "tdc_row_mrv_payment_chain_review.csv").exists()
    assert not (processed_dir / "tdc_row_mrv_payment_chain_review.md").exists()
    assert not (processed_dir / "tdc_row_mrv_promotion_checklist.csv").exists()
    assert not (processed_dir / "tdc_row_mrv_promotion_checklist.md").exists()
    assert not (processed_dir / "tdc_row_mrv_source_map.csv").exists()
    assert not (processed_dir / "tdc_row_mrv_source_map.md").exists()
    assert not (processed_dir / "tdc_row_mrv_stop_gate.csv").exists()
    assert not (processed_dir / "tdc_row_mrv_stop_gate.md").exists()
    assert not (processed_dir / "tdc_tier3_source_diagnostics.csv").exists()
    assert not (processed_dir / "tdc_tier3_source_diagnostics.md").exists()
    assert (processed_dir / "tdc_tier3_receipt_source_diagnostics.csv").exists()
    assert (processed_dir / "tdc_tier3_receipt_source_diagnostics.md").exists()
    assert not (processed_dir / "tdc_tier3_bank_receipt_upper_bound_sensitivity.csv").exists()
    assert not (processed_dir / "tdc_tier3_bank_receipt_upper_bound_sensitivity.md").exists()
    assert (site_dir / "bundle.json").exists()
    assert (site_dir / "data" / "bundle.json").exists()

    bundle = json.loads((site_dir / "bundle.json").read_text())
    assert bundle["bundle_format"] == "tdc_site_bundle_v4"
    assert bundle["metadata"]["value_units"]["nominal"] == "Millions of U.S. dollars"
    assert "gdp_deflator" in bundle["references"]["columns"]
    assert bundle["metadata"]["method_meta"]["cash_term"]["transaction_series_key"] == "treasury_operating_cash_tx"
    assert bundle["metadata"]["method_meta"]["cash_term"]["diagnostic_only_series"] == ["tga_weekly"]
    assert bundle["metadata"]["method_meta"]["correction_inputs"]["fed_tsy_coupon_interest_proxy"]["raw_filename"] == "support__fed_tsy_coupon_interest_proxy.csv"
    assert bundle["metadata"]["method_meta"]["correction_inputs"]["bank_tsy_coupon_interest_proxy"]["raw_filename"] == "support__bank_tsy_coupon_interest_proxy.csv"
    assert bundle["metadata"]["method_meta"]["correction_inputs"]["row_tsy_coupon_interest_proxy"]["raw_filename"] == "support__row_tsy_coupon_interest_proxy.csv"
    assert bundle["metadata"]["method_meta"]["correction_inputs"]["bank_noninterest_outlay_proxy"]["raw_filename"] == "support__bank_noninterest_outlay_proxy.csv"
    assert bundle["metadata"]["method_meta"]["correction_inputs"]["row_noninterest_outlay_proxy"]["raw_filename"] == "support__row_noninterest_outlay_proxy.csv"
    assert bundle["metadata"]["method_meta"]["correction_inputs"]["bank_nonborrow_receipt_proxy"]["raw_filename"] == "support__bank_nonborrow_receipt_proxy.csv"
    assert bundle["metadata"]["method_meta"]["correction_inputs"]["row_nonborrow_receipt_proxy"]["raw_filename"] == "support__row_nonborrow_receipt_proxy.csv"
    assert bundle["metadata"]["method_meta"]["correction_inputs"]["mint_cb_cash_factor_proxy"]["raw_filename"] == "support__mint_cb_cash_factor_proxy.csv"
    assert "fed_tsy_coupon_interest_proxy" in bundle["components"]["columns"]
    assert "bank_tsy_coupon_interest_proxy" in bundle["components"]["columns"]
    assert "row_tsy_coupon_interest_proxy" in bundle["components"]["columns"]
    assert "bank_noninterest_outlay_proxy" in bundle["components"]["columns"]
    assert "bank_nonborrow_receipt_proxy" in bundle["components"]["columns"]
    assert "mint_cb_cash_factor_proxy" in bundle["components"]["columns"]
    assert "tier1_fed_coupon_correction" in bundle["corrections"]["columns"]
    assert "tdc_tier2_bank_only_delta_from_base" in bundle["corrections"]["columns"]
    assert "tdc_tier3_bank_only_delta_from_base" in bundle["corrections"]["columns"]
    assert "latest_corrections" in bundle["summary"]
    assert bundle["site"]["title"] == "TDCest"
    assert "receipt_unblock_status" in bundle["research"]
    assert "project_goal_status_review" in bundle["research"]
    assert "tier3_research_comparison" in bundle["research"]
    assert "downstream_estimator_contract" in bundle["research"]
    assert "downstream_component_contribution_review" in bundle["research"]
    assert "downstream_estimator_gap_review" in bundle["research"]
    assert "fiscal_receipt_boundary_review" in bundle["research"]
    assert "downstream_deposit_effect_use_case_review" in bundle["research"]
    assert "downstream_problem_variable_review" in bundle["research"]
    assert "downstream_deposit_effect_series_panel" in bundle["research"]
    assert "downstream_deposit_effect_comparison_panel" in bundle["research"]
    assert "backend_closeout_review" in bundle["research"]
    assert "backend_release_check" in bundle["research"]
    assert "theory_measurement_map" in bundle["research"]
    assert "row_mrv_nondefault_evidence_summary" in bundle["research"]
    assert result["theory_measurement_map_path"] == str(processed_dir / "tdc_theory_measurement_map.csv")
    handoff_json = (processed_dir / "tdc_downstream_handoff_bundle.json").read_text()
    assert "\"NaT\"" not in handoff_json
    attribution_markdown = (processed_dir / "tdc_post2022_bank_only_attribution.md").read_text()
    assert "Post-2022 Bank-Only Correction Attribution" in attribution_markdown
    input_audit_markdown = (processed_dir / "tdc_input_audit.md").read_text()
    assert "Input Unit And Frequency Audit" in input_audit_markdown


def test_pipeline_writes_tier3_source_diagnostics_when_mts_outlays_are_present(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"

    generate_synthetic_raw_bundle(raw_dir, seed=7)
    pd.DataFrame(
        [
            ["2025-04-30", "Financial Agent Services", 100_000_000.0],
            ["2025-05-31", "Financial Agent Services", 110_000_000.0],
            ["2025-06-30", "Financial Agent Services", 120_000_000.0],
            ["2025-04-30", "Foreign Military Financing Program", 200_000_000.0],
            ["2025-05-31", "International Disaster Assistance", 300_000_000.0],
            ["2025-06-30", "International Organizations and Conferences", 400_000_000.0],
            ["2025-04-30", "United States Mint", -500_000_000.0],
            ["2025-05-31", "United States Mint", 100_000_000.0],
            ["2025-06-30", "United States Mint", -200_000_000.0],
        ],
        columns=["record_date", "classification_desc", "current_month_net_outly_amt"],
    ).to_csv(raw_dir / "treasury__mts_outlays.csv", index=False)

    result = run_estimation_pipeline(raw_dir=raw_dir, processed_dir=processed_dir)

    assert result["tier3_source_diagnostics_path"] == str(processed_dir / "tdc_tier3_source_diagnostics.csv")
    assert result["tier3_source_diagnostics_markdown_path"] == str(processed_dir / "tdc_tier3_source_diagnostics.md")
    assert (processed_dir / "tdc_tier3_source_diagnostics.csv").exists()
    assert (processed_dir / "tdc_tier3_source_diagnostics.md").exists()
    markdown = (processed_dir / "tdc_tier3_source_diagnostics.md").read_text()
    assert "Tier 3 Source Diagnostics" in markdown
    assert "Latest source-covered quarter: 2025-06-30." in markdown


def test_pipeline_writes_tier3_receipt_source_diagnostics_when_mts_receipts_are_present(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"

    generate_synthetic_raw_bundle(raw_dir, seed=7)
    pd.DataFrame(
        [
            ["2025-04-30", "Deposit of Earnings, Federal Reserve System", 100_000_000.0],
            ["2025-05-31", "Deposit of Earnings, Federal Reserve System", 110_000_000.0],
            ["2025-06-30", "Deposit of Earnings, Federal Reserve System", 120_000_000.0],
            ["2025-04-30", "Customs Duties", 200_000_000.0],
            ["2025-05-31", "Customs Duties", 300_000_000.0],
            ["2025-06-30", "Customs Duties", 400_000_000.0],
            ["2025-04-30", "Deposits by States", 500_000_000.0],
            ["2025-05-31", "Deposits by States", 100_000_000.0],
            ["2025-06-30", "Deposits by States", 200_000_000.0],
        ],
        columns=["record_date", "classification_desc", "current_month_net_rcpt_amt"],
    ).to_csv(raw_dir / "treasury__mts_receipts.csv", index=False)

    result = run_estimation_pipeline(raw_dir=raw_dir, processed_dir=processed_dir)

    assert result["tier3_receipt_source_diagnostics_path"] == str(processed_dir / "tdc_tier3_receipt_source_diagnostics.csv")
    assert result["tier3_receipt_source_diagnostics_markdown_path"] == str(processed_dir / "tdc_tier3_receipt_source_diagnostics.md")
    assert (processed_dir / "tdc_tier3_receipt_source_diagnostics.csv").exists()
    assert (processed_dir / "tdc_tier3_receipt_source_diagnostics.md").exists()
    markdown = (processed_dir / "tdc_tier3_receipt_source_diagnostics.md").read_text()
    assert "Tier 3 Receipt Source Diagnostics" in markdown
    assert "Latest source-covered quarter: 2025-06-30." in markdown


def test_pipeline_includes_revenue_collections_candidates_in_receipt_diagnostics(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"

    generate_synthetic_raw_bundle(raw_dir, seed=7)
    pd.DataFrame(
        [
            ["2025-04-30", "Deposit of Earnings, Federal Reserve System", 100_000_000.0],
            ["2025-05-31", "Deposit of Earnings, Federal Reserve System", 110_000_000.0],
            ["2025-06-30", "Deposit of Earnings, Federal Reserve System", 120_000_000.0],
        ],
        columns=["record_date", "classification_desc", "current_month_net_rcpt_amt"],
    ).to_csv(raw_dir / "treasury__mts_receipts.csv", index=False)
    pd.DataFrame(
        [
            ["2025-04-30", "Bank", "Non-Tax", 200_000_000.0],
            ["2025-05-31", "Bank", "IRS Tax", 300_000_000.0],
            ["2025-06-30", "Bank", "IRS Non-Tax", 400_000_000.0],
        ],
        columns=["record_date", "channel_type_desc", "tax_category_desc", "net_collections_amt"],
    ).to_csv(raw_dir / "treasury__revenue_collections.csv", index=False)

    run_estimation_pipeline(raw_dir=raw_dir, processed_dir=processed_dir)

    diagnostics = pd.read_csv(processed_dir / "tdc_tier3_receipt_source_diagnostics.csv")
    assert "rcm_bank_channel_total_candidate" in diagnostics.columns
    markdown = (processed_dir / "tdc_tier3_receipt_source_diagnostics.md").read_text()
    assert "RCM bank-channel candidate" in markdown


def test_pipeline_input_audit_flags_row_coupon_scale_issue_when_benchmark_is_present(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"

    generate_synthetic_raw_bundle(raw_dir, seed=7)
    pd.DataFrame(
        [
            ["2025-12-31", 70.346378],
        ],
        columns=["date", "value"],
    ).to_csv(raw_dir / "support__row_tsy_coupon_interest_proxy.csv", index=False)
    pd.DataFrame(
        [
            ["2025-12-31", 285.891],
        ],
        columns=["date", "value"],
    ).to_csv(raw_dir / "fred__bea_row_fed_interest_paid_saar.csv", index=False)

    result = run_estimation_pipeline(raw_dir=raw_dir, processed_dir=processed_dir)

    assert result["input_audit_path"] == str(processed_dir / "tdc_input_audit.csv")
    assert result["input_audit_markdown_path"] == str(processed_dir / "tdc_input_audit.md")
    audit = pd.read_csv(processed_dir / "tdc_input_audit.csv")
    row = audit.loc[audit["series_key"].eq("row_tsy_coupon_interest_proxy")].iloc[0]
    assert row["audit_status"] == "possible_x1000_mismatch"
    markdown = (processed_dir / "tdc_input_audit.md").read_text()
    assert "ratio if x1000" in markdown


def test_pipeline_writes_bank_receipt_upper_bound_sensitivity_when_revenue_collections_are_present(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"

    generate_synthetic_raw_bundle(raw_dir, seed=7)
    pd.DataFrame(
        [
            ["2025-04-30", "Deposit of Earnings, Federal Reserve System", 100_000_000.0],
            ["2025-05-31", "Deposit of Earnings, Federal Reserve System", 110_000_000.0],
            ["2025-06-30", "Deposit of Earnings, Federal Reserve System", 120_000_000.0],
        ],
        columns=["record_date", "classification_desc", "current_month_net_rcpt_amt"],
    ).to_csv(raw_dir / "treasury__mts_receipts.csv", index=False)
    pd.DataFrame(
        [
            ["2025-04-30", "Bank", "Non-Tax", 200_000_000.0],
            ["2025-05-31", "Bank", "IRS Tax", 300_000_000.0],
            ["2025-06-30", "Bank", "IRS Non-Tax", 400_000_000.0],
        ],
        columns=["record_date", "channel_type_desc", "tax_category_desc", "net_collections_amt"],
    ).to_csv(raw_dir / "treasury__revenue_collections.csv", index=False)

    result = run_estimation_pipeline(raw_dir=raw_dir, processed_dir=processed_dir)

    assert result["tier3_bank_receipt_upper_bound_sensitivity_path"] == str(
        processed_dir / "tdc_tier3_bank_receipt_upper_bound_sensitivity.csv"
    )
    assert result["tier3_bank_receipt_upper_bound_sensitivity_markdown_path"] == str(
        processed_dir / "tdc_tier3_bank_receipt_upper_bound_sensitivity.md"
    )
    diagnostics = pd.read_csv(processed_dir / "tdc_tier3_bank_receipt_upper_bound_sensitivity.csv")
    assert "tdc_tier3_bank_only_plus_rcm_bank_channel_total_upper_bound" in diagnostics.columns
    markdown = (processed_dir / "tdc_tier3_bank_receipt_upper_bound_sensitivity.md").read_text()
    assert "Tier 3 Bank-Receipt Upper-Bound Sensitivity" in markdown
    assert "routing-heavy upper bound" in markdown


def test_pipeline_writes_bea_row_receipts_benchmark_when_component_series_are_present(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"

    generate_synthetic_raw_bundle(raw_dir, seed=7)
    pd.DataFrame([["2025-12-31", 42.862]], columns=["date", "value"]).to_csv(
        raw_dir / "fred__bea_row_taxes_received_saar.csv", index=False
    )
    pd.DataFrame([["2025-12-31", 6.846]], columns=["date", "value"]).to_csv(
        raw_dir / "fred__bea_row_social_insurance_received_saar.csv", index=False
    )
    pd.DataFrame([["2025-12-31", 0.973]], columns=["date", "value"]).to_csv(
        raw_dir / "fred__bea_row_current_transfer_receipts_received_saar.csv", index=False
    )

    result = run_estimation_pipeline(raw_dir=raw_dir, processed_dir=processed_dir)

    assert result["bea_row_receipts_benchmark_path"] == str(processed_dir / "tdc_bea_row_receipts_benchmark.csv")
    assert result["bea_row_receipts_benchmark_markdown_path"] == str(processed_dir / "tdc_bea_row_receipts_benchmark.md")
    assert (processed_dir / "tdc_bea_row_receipts_benchmark.csv").exists()
    markdown = (processed_dir / "tdc_bea_row_receipts_benchmark.md").read_text()
    assert "BEA ROW Receipts Benchmark" in markdown
    benchmark = pd.read_csv(processed_dir / "tdc_bea_row_receipts_benchmark.csv")
    assert "bea_row_current_receipts_total_q_mil" in benchmark.columns


def test_pipeline_writes_bank_corp_tax_receipts_bridge_when_irs_share_file_is_present(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"

    generate_synthetic_raw_bundle(raw_dir, seed=7)
    pd.DataFrame(
        [
            ["2025-10-31", "Corporation Income Taxes", 100_000_000.0, 10_000_000.0, 90_000_000.0],
            ["2025-11-30", "Corporation Income Taxes", 120_000_000.0, 20_000_000.0, 100_000_000.0],
            ["2025-12-31", "Corporation Income Taxes", 140_000_000.0, 30_000_000.0, 110_000_000.0],
        ],
        columns=[
            "record_date",
            "classification_desc",
            "current_month_gross_rcpt_amt",
            "current_month_refund_amt",
            "current_month_net_rcpt_amt",
        ],
    ).to_csv(raw_dir / "treasury__mts_receipts.csv", index=False)
    pd.DataFrame(
        [[2025, "IRS Publication 16 Table 5.1", 1_000_000, 100_000, 10_000, 5_000, 3_000, 0.10, 0.015, 0.018]],
        columns=[
            "tax_year",
            "source_table",
            "all_total_income_tax_after_credits_thousands",
            "finance_and_insurance_total_income_tax_after_credits_thousands",
            "commercial_banking_total_income_tax_after_credits_thousands",
            "savings_and_other_depository_credit_intermediation_total_income_tax_after_credits_thousands",
            "bank_holding_companies_total_income_tax_after_credits_thousands",
            "finance_share_after_credits",
            "strict_depository_share_after_credits",
            "depository_plus_bhc_share_after_credits",
        ],
    ).to_csv(raw_dir / "irs__soi_bank_tax_shares.csv", index=False)

    result = run_estimation_pipeline(raw_dir=raw_dir, processed_dir=processed_dir)

    assert result["bank_corp_tax_receipts_bridge_path"] == str(processed_dir / "tdc_bank_corp_tax_receipts_bridge.csv")
    assert result["bank_corp_tax_receipts_bridge_markdown_path"] == str(
        processed_dir / "tdc_bank_corp_tax_receipts_bridge.md"
    )
    assert (processed_dir / "tdc_bank_corp_tax_receipts_bridge.csv").exists()
    bridge = pd.read_csv(processed_dir / "tdc_bank_corp_tax_receipts_bridge.csv")
    assert "bank_corp_tax_receipts_gross_finance_share_mil" in bridge.columns
    markdown = (processed_dir / "tdc_bank_corp_tax_receipts_bridge.md").read_text()
    assert "Bank Corporate-Tax Receipts Bridge" in markdown


def test_pipeline_writes_receipt_account_candidates_when_receipts_by_department_is_present(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"

    generate_synthetic_raw_bundle(raw_dir, seed=7)
    pd.DataFrame(
        [
            ["2025-09-30", "Consular and Border Security Programs, Machine Readable Visa Fee, State", "019", "X", "5713", "005", 2_487_431_164.11, 2025],
            ["2025-09-30", "Fines, Penalties, and Forfeitures, Not Otherwise Classified, Office of the Comptroller of Currency, Treasury", "020", "null", "1099", "071", 450_488_475.01, 2025],
        ],
        columns=["record_date", "receipt_line_item_nm", "aid_cd", "a_cd", "main_cd", "sub_cd", "receipt_amt", "record_fiscal_year"],
    ).to_csv(raw_dir / "treasury__receipts_by_department.csv", index=False)

    result = run_estimation_pipeline(raw_dir=raw_dir, processed_dir=processed_dir)

    assert result["receipt_account_candidates_path"] == str(processed_dir / "tdc_receipt_account_candidates.csv")
    assert result["receipt_account_candidates_markdown_path"] == str(processed_dir / "tdc_receipt_account_candidates.md")
    candidates = pd.read_csv(processed_dir / "tdc_receipt_account_candidates.csv")
    assert set(candidates["counterparty_group"]) == {"bank", "row"}
    markdown = (processed_dir / "tdc_receipt_account_candidates.md").read_text()
    assert "Receipt Account Candidate Bridge" in markdown


def test_pipeline_writes_row_and_bank_pilots_when_receipts_by_department_is_present(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"

    generate_synthetic_raw_bundle(raw_dir, seed=7)
    pd.DataFrame(
        [
            ["2025-09-30", "Consular and Border Security Programs, Machine Readable Visa Fee, State", "019", "X", "5713", "005", 2_487_431_164.11, 2025],
            ["2025-09-30", "Consular and Border Security Programs, Passport Security Surcharge, State", "019", "X", "5713", "003", 1_783_122_827.71, 2025],
            ["2025-09-30", "Fines, Penalties, and Forfeitures, Not Otherwise Classified, Office of the Comptroller of Currency, Treasury", "020", "null", "1099", "071", 450_488_475.01, 2025],
            ["2025-09-30", "Fees and Assessments, Financial Research Fund, Departmental Offices, Treasury", "020", "X", "5590", "001", 103_282_141.00, 2025],
        ],
        columns=["record_date", "receipt_line_item_nm", "aid_cd", "a_cd", "main_cd", "sub_cd", "receipt_amt", "record_fiscal_year"],
    ).to_csv(raw_dir / "treasury__receipts_by_department.csv", index=False)

    result = run_estimation_pipeline(raw_dir=raw_dir, processed_dir=processed_dir)

    assert result["row_visa_consular_pilot_path"] == str(processed_dir / "tdc_row_visa_consular_pilot.csv")
    assert result["bank_nontax_regulatory_pilot_path"] == str(processed_dir / "tdc_bank_nontax_regulatory_pilot.csv")
    row_pilot = pd.read_csv(processed_dir / "tdc_row_visa_consular_pilot.csv")
    bank_pilot = pd.read_csv(processed_dir / "tdc_bank_nontax_regulatory_pilot.csv")
    assert "mrv_cbsp_primary_candidate" in set(row_pilot["pilot_bucket"])
    assert "occ_candidate" in set(bank_pilot["pilot_bucket"])
    assert "ofr_candidate" in set(bank_pilot["pilot_bucket"])


def test_pipeline_writes_bank_occ_timing_sensitivity_when_occ_pilot_is_present(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"

    generate_synthetic_raw_bundle(raw_dir, seed=7)
    pd.DataFrame(
        [
            ["2025-09-30", "Fines, Penalties, and Forfeitures, Not Otherwise Classified, Office of the Comptroller of Currency, Treasury", "020", "null", "1099", "071", 450_488_475.01, 2025],
        ],
        columns=["record_date", "receipt_line_item_nm", "aid_cd", "a_cd", "main_cd", "sub_cd", "receipt_amt", "record_fiscal_year"],
    ).to_csv(raw_dir / "treasury__receipts_by_department.csv", index=False)

    result = run_estimation_pipeline(raw_dir=raw_dir, processed_dir=processed_dir)

    assert result["bank_occ_timing_sensitivity_path"] == str(processed_dir / "tdc_bank_occ_timing_sensitivity.csv")
    assert result["bank_occ_timing_sensitivity_markdown_path"] == str(processed_dir / "tdc_bank_occ_timing_sensitivity.md")
    sensitivity = pd.read_csv(processed_dir / "tdc_bank_occ_timing_sensitivity.csv")
    assert "occ_due_date_allocated_receipt_mil" in sensitivity.columns
    markdown = (processed_dir / "tdc_bank_occ_timing_sensitivity.md").read_text()
    assert "Bank OCC Timing Sensitivity" in markdown


def test_pipeline_writes_row_state_visa_timing_sensitivity_when_monthly_state_data_is_present(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"

    generate_synthetic_raw_bundle(raw_dir, seed=7)
    pd.DataFrame(
        [
            ["2025-09-30", "Consular and Border Security Programs, Machine Readable Visa Fee, State", "019", "X", "5713", "005", 2_487_431_164.11, 2025],
            ["2025-09-30", "Consular and Border Security Programs, Immigrant Visa Security Surcharge, State", "019", "X", "5713", "006", 55_192_433.40, 2025],
            ["2025-09-30", "Consular and Border Security Programs, Diversity Visa Lottery Fee, State", "019", "X", "5713", "008", 18_705_912.23, 2025],
        ],
        columns=["record_date", "receipt_line_item_nm", "aid_cd", "a_cd", "main_cd", "sub_cd", "receipt_amt", "record_fiscal_year"],
    ).to_csv(raw_dir / "treasury__receipts_by_department.csv", index=False)
    pd.DataFrame(
        [
            ["2025-07-31", 2025, 100, 20],
            ["2025-08-31", 2025, 200, 30],
            ["2025-09-30", 2025, 300, 50],
        ],
        columns=["date", "fiscal_year", "niv_issuances_total", "iv_issuances_total"],
    ).to_csv(raw_dir / "state__visa_issuances_monthly.csv", index=False)

    result = run_estimation_pipeline(raw_dir=raw_dir, processed_dir=processed_dir)

    assert result["row_state_visa_timing_sensitivity_path"] == str(processed_dir / "tdc_row_state_visa_timing_sensitivity.csv")
    assert result["row_state_visa_timing_sensitivity_markdown_path"] == str(
        processed_dir / "tdc_row_state_visa_timing_sensitivity.md"
    )
    sensitivity = pd.read_csv(processed_dir / "tdc_row_state_visa_timing_sensitivity.csv")
    assert "row_state_visa_allocated_receipt_mil" in sensitivity.columns
    assert "row_state_visa_secondary_allocated_receipt_mil" in sensitivity.columns
    assert "row_state_visa_total_allocated_receipt_mil" in sensitivity.columns
    markdown = (processed_dir / "tdc_row_state_visa_timing_sensitivity.md").read_text()
    assert "ROW State MRV / CBSP Timing Bridge" in markdown


def test_pipeline_writes_tier3_receipt_candidate_sensitivity_when_receipt_candidates_are_present(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"

    generate_synthetic_raw_bundle(raw_dir, seed=7)
    pd.DataFrame(
        [
            ["2025-10-31", "Corporation Income Taxes", 100_000_000.0, 10_000_000.0, 90_000_000.0],
            ["2025-11-30", "Corporation Income Taxes", 120_000_000.0, 20_000_000.0, 100_000_000.0],
            ["2025-12-31", "Corporation Income Taxes", 140_000_000.0, 30_000_000.0, 110_000_000.0],
        ],
        columns=[
            "record_date",
            "classification_desc",
            "current_month_gross_rcpt_amt",
            "current_month_refund_amt",
            "current_month_net_rcpt_amt",
        ],
    ).to_csv(raw_dir / "treasury__mts_receipts.csv", index=False)
    pd.DataFrame(
        [[2025, "IRS Publication 16 Table 5.1", 1_000_000, 100_000, 10_000, 5_000, 3_000, 0.10, 0.015, 0.018]],
        columns=[
            "tax_year",
            "source_table",
            "all_total_income_tax_after_credits_thousands",
            "finance_and_insurance_total_income_tax_after_credits_thousands",
            "commercial_banking_total_income_tax_after_credits_thousands",
            "savings_and_other_depository_credit_intermediation_total_income_tax_after_credits_thousands",
            "bank_holding_companies_total_income_tax_after_credits_thousands",
            "finance_share_after_credits",
            "strict_depository_share_after_credits",
            "depository_plus_bhc_share_after_credits",
        ],
    ).to_csv(raw_dir / "irs__soi_bank_tax_shares.csv", index=False)
    pd.DataFrame(
        [
            ["2025-09-30", "Consular and Border Security Programs, Machine Readable Visa Fee, State", "019", "X", "5713", "005", 2_487_431_164.11, 2025],
            ["2025-09-30", "Consular and Border Security Programs, Immigrant Visa Security Surcharge, State", "019", "X", "5713", "006", 55_192_433.40, 2025],
            ["2025-09-30", "Consular and Border Security Programs, Diversity Visa Lottery Fee, State", "019", "X", "5713", "008", 18_705_912.23, 2025],
            ["2025-09-30", "Fines, Penalties, and Forfeitures, Not Otherwise Classified, Office of the Comptroller of Currency, Treasury", "020", "null", "1099", "071", 450_488_475.01, 2025],
        ],
        columns=["record_date", "receipt_line_item_nm", "aid_cd", "a_cd", "main_cd", "sub_cd", "receipt_amt", "record_fiscal_year"],
    ).to_csv(raw_dir / "treasury__receipts_by_department.csv", index=False)
    pd.DataFrame(
        [
            ["2025-07-31", 2025, 100, 20],
            ["2025-08-31", 2025, 200, 30],
            ["2025-09-30", 2025, 300, 50],
        ],
        columns=["date", "fiscal_year", "niv_issuances_total", "iv_issuances_total"],
    ).to_csv(raw_dir / "state__visa_issuances_monthly.csv", index=False)

    result = run_estimation_pipeline(raw_dir=raw_dir, processed_dir=processed_dir)

    assert result["tier3_receipt_candidate_sensitivity_path"] == str(
        processed_dir / "tdc_tier3_receipt_candidate_sensitivity.csv"
    )
    assert result["tier3_receipt_candidate_sensitivity_markdown_path"] == str(
        processed_dir / "tdc_tier3_receipt_candidate_sensitivity.md"
    )
    sensitivity = pd.read_csv(processed_dir / "tdc_tier3_receipt_candidate_sensitivity.csv")
    assert "bank_corp_tax_depository_plus_bhc_bridge_delta_mil" in sensitivity.columns
    assert "row_state_visa_timing_delta_mil" in sensitivity.columns
    assert sensitivity.loc[sensitivity["row_state_visa_timing_delta_mil"].ne(0.0), "row_state_visa_timing_delta_mil"].iloc[0] > 0.0
    markdown = (processed_dir / "tdc_tier3_receipt_candidate_sensitivity.md").read_text()
    assert "Tier 3 Receipt Candidate Sensitivity" in markdown


def test_pipeline_always_writes_fiscal_reconciliation_shell(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"

    generate_synthetic_raw_bundle(raw_dir, seed=7)

    result = run_estimation_pipeline(raw_dir=raw_dir, processed_dir=processed_dir)

    assert result["fiscal_reconciliation_cells_path"] == str(processed_dir / "tdc_fiscal_reconciliation_cells.csv")
    assert result["fiscal_reconciliation_residuals_path"] == str(
        processed_dir / "tdc_fiscal_reconciliation_residuals.csv"
    )
    assert result["fiscal_source_quality_path"] == str(processed_dir / "tdc_fiscal_source_quality.csv")
    assert result["receipt_promotion_review_path"] == str(processed_dir / "tdc_receipt_promotion_review.csv")
    assert result["receipt_unblock_status_path"] == str(processed_dir / "tdc_receipt_unblock_status.csv")
    assert result["downstream_estimator_contract_path"] == str(
        processed_dir / "tdc_downstream_estimator_contract.csv"
    )
    assert result["downstream_component_contribution_review_path"] == str(
        processed_dir / "tdc_downstream_component_contribution_review.csv"
    )
    assert result["downstream_estimator_gap_review_path"] == str(
        processed_dir / "tdc_downstream_estimator_gap_review.csv"
    )
    assert result["fiscal_receipt_boundary_review_path"] == str(
        processed_dir / "tdc_fiscal_receipt_boundary_review.csv"
    )
    assert result["downstream_deposit_effect_use_case_review_path"] == str(
        processed_dir / "tdc_downstream_deposit_effect_use_case_review.csv"
    )
    assert result["downstream_problem_variable_review_path"] == str(
        processed_dir / "tdc_downstream_problem_variable_review.csv"
    )
    assert result["downstream_deposit_effect_series_panel_path"] == str(
        processed_dir / "tdc_downstream_deposit_effect_series_panel.csv"
    )
    assert result["downstream_deposit_effect_comparison_panel_path"] == str(
        processed_dir / "tdc_downstream_deposit_effect_comparison_panel.csv"
    )
    assert result["downstream_handoff_bundle_path"] == str(
        processed_dir / "tdc_downstream_handoff_bundle.json"
    )
    assert result["downstream_ingest_manifest_path"] == str(
        processed_dir / "tdc_downstream_ingest_manifest.csv"
    )
    assert result["downstream_consistency_review_path"] == str(
        processed_dir / "tdc_downstream_consistency_review.csv"
    )
    assert result["backend_closeout_review_path"] == str(
        processed_dir / "tdc_backend_closeout_review.csv"
    )
    assert result["backend_release_check_path"] == str(
        processed_dir / "tdc_backend_release_check.csv"
    )
    assert result["bank_receipt_default_readiness_path"] == str(
        processed_dir / "tdc_bank_receipt_default_readiness.csv"
    )
    assert result["bank_receipt_source_map_path"] == str(processed_dir / "tdc_bank_receipt_source_map.csv")
    assert result["bank_receipt_stop_gate_path"] == str(processed_dir / "tdc_bank_receipt_stop_gate.csv")
    assert result["bank_minor_industry_share_availability_path"] == str(
        processed_dir / "tdc_bank_minor_industry_share_availability.csv"
    )
    assert result["monetary_stage0_diagnostics_path"] == str(
        processed_dir / "tdc_monetary_stage0_diagnostics.csv"
    )
    assert result["monetary_stage1_controls_path"] == str(
        processed_dir / "tdc_monetary_stage1_controls.csv"
    )
    assert result["monetary_control_overlap_audit_path"] == str(
        processed_dir / "tdc_monetary_control_overlap_audit.csv"
    )
    assert result["monetary_residual_interpretation_path"] == str(
        processed_dir / "tdc_monetary_residual_interpretation.csv"
    )
    assert result["monetary_target_wedge_path"] == str(
        processed_dir / "tdc_monetary_target_wedge.csv"
    )
    assert result["monetary_target_definition_bridge_path"] == str(
        processed_dir / "tdc_monetary_target_definition_bridge.csv"
    )
    assert result["monetary_target_definition_decomposition_path"] == str(
        processed_dir / "tdc_monetary_target_definition_decomposition.csv"
    )
    assert result["monetary_bank_target_stress_review_path"] == str(
        processed_dir / "tdc_monetary_bank_target_stress_review.csv"
    )
    assert result["monetary_bank_target_gap_attribution_path"] == str(
        processed_dir / "tdc_monetary_bank_target_gap_attribution.csv"
    )
    assert result["monetary_nonbank_depository_bridge_attribution_path"] == str(
        processed_dir / "tdc_monetary_nonbank_depository_bridge_attribution.csv"
    )
    assert result["monetary_bank_liability_candidate_audit_path"] == str(
        processed_dir / "tdc_monetary_bank_liability_candidate_audit.csv"
    )
    assert result["monetary_bank_perimeter_gap_review_path"] == str(
        processed_dir / "tdc_monetary_bank_perimeter_gap_review.csv"
    )
    assert result["monetary_bank_perimeter_source_map_path"] == str(
        processed_dir / "tdc_monetary_bank_perimeter_source_map.csv"
    )
    assert result["monetary_bank_liquid_source_review_path"] == str(
        processed_dir / "tdc_monetary_bank_liquid_source_review.csv"
    )
    assert result["monetary_bank_liquid_stop_gate_path"] == str(
        processed_dir / "tdc_monetary_bank_liquid_stop_gate.csv"
    )
    assert result["ncua_credit_union_deposit_bridge_path"] == str(
        processed_dir / "tdc_ncua_credit_union_deposit_bridge.csv"
    )
    assert result["fdic_savings_institution_deposit_bridge_path"] == str(
        processed_dir / "tdc_fdic_savings_institution_deposit_bridge.csv"
    )
    assert result["monetary_target_preference_review_path"] == str(
        processed_dir / "tdc_monetary_target_preference_review.csv"
    )
    cells = pd.read_csv(processed_dir / "tdc_fiscal_reconciliation_cells.csv")
    residuals = pd.read_csv(processed_dir / "tdc_fiscal_reconciliation_residuals.csv")
    source_quality = pd.read_csv(processed_dir / "tdc_fiscal_source_quality.csv")
    review = pd.read_csv(processed_dir / "tdc_receipt_promotion_review.csv")
    receipt_unblock = pd.read_csv(processed_dir / "tdc_receipt_unblock_status.csv")
    downstream_contract = pd.read_csv(processed_dir / "tdc_downstream_estimator_contract.csv")
    downstream_contrib = pd.read_csv(processed_dir / "tdc_downstream_component_contribution_review.csv")
    downstream_gap = pd.read_csv(processed_dir / "tdc_downstream_estimator_gap_review.csv")
    fiscal_receipt_boundary = pd.read_csv(processed_dir / "tdc_fiscal_receipt_boundary_review.csv")
    downstream_use_case = pd.read_csv(processed_dir / "tdc_downstream_deposit_effect_use_case_review.csv")
    downstream_problem_variable = pd.read_csv(processed_dir / "tdc_downstream_problem_variable_review.csv")
    downstream_series_panel = pd.read_csv(processed_dir / "tdc_downstream_deposit_effect_series_panel.csv")
    downstream_comparison_panel = pd.read_csv(
        processed_dir / "tdc_downstream_deposit_effect_comparison_panel.csv"
    )
    downstream_handoff_bundle = json.loads((processed_dir / "tdc_downstream_handoff_bundle.json").read_text())
    downstream_ingest_manifest = pd.read_csv(processed_dir / "tdc_downstream_ingest_manifest.csv")
    downstream_consistency_review = pd.read_csv(processed_dir / "tdc_downstream_consistency_review.csv")
    backend_closeout_review = pd.read_csv(processed_dir / "tdc_backend_closeout_review.csv")
    backend_release_check = pd.read_csv(processed_dir / "tdc_backend_release_check.csv")
    readiness = pd.read_csv(processed_dir / "tdc_bank_receipt_default_readiness.csv")
    bank_source_map = pd.read_csv(processed_dir / "tdc_bank_receipt_source_map.csv")
    bank_stop_gate = pd.read_csv(processed_dir / "tdc_bank_receipt_stop_gate.csv")
    monetary = pd.read_csv(processed_dir / "tdc_monetary_stage0_diagnostics.csv")
    monetary_stage1 = pd.read_csv(processed_dir / "tdc_monetary_stage1_controls.csv")
    monetary_overlap = pd.read_csv(processed_dir / "tdc_monetary_control_overlap_audit.csv")
    monetary_residual = pd.read_csv(processed_dir / "tdc_monetary_residual_interpretation.csv")
    monetary_wedge = pd.read_csv(processed_dir / "tdc_monetary_target_wedge.csv")
    monetary_definition = pd.read_csv(processed_dir / "tdc_monetary_target_definition_bridge.csv")
    monetary_definition_decomp = pd.read_csv(processed_dir / "tdc_monetary_target_definition_decomposition.csv")
    monetary_bank_stress = pd.read_csv(processed_dir / "tdc_monetary_bank_target_stress_review.csv")
    monetary_bank_attr = pd.read_csv(processed_dir / "tdc_monetary_bank_target_gap_attribution.csv")
    monetary_nonbank_bridge_attr = pd.read_csv(processed_dir / "tdc_monetary_nonbank_depository_bridge_attribution.csv")
    monetary_liability_audit = pd.read_csv(processed_dir / "tdc_monetary_bank_liability_candidate_audit.csv")
    monetary_bank_perimeter = pd.read_csv(processed_dir / "tdc_monetary_bank_perimeter_gap_review.csv")
    monetary_bank_perimeter_map = pd.read_csv(processed_dir / "tdc_monetary_bank_perimeter_source_map.csv")
    ncua_bridge = pd.read_csv(processed_dir / "tdc_ncua_credit_union_deposit_bridge.csv")
    fdic_bridge = pd.read_csv(processed_dir / "tdc_fdic_savings_institution_deposit_bridge.csv")
    monetary_pref = pd.read_csv(processed_dir / "tdc_monetary_target_preference_review.csv")
    assert "row_family" in cells.columns
    assert "tier3_reconstruction_residual_mil" in residuals.columns
    assert "reliability_grade" in source_quality.columns
    assert "promotion_status" in review.columns
    assert "best_external_research_target" in receipt_unblock.columns
    assert "best_downstream_use" in downstream_contract.columns
    assert "component_family" in downstream_contrib.columns
    assert "dominant_component_key" in downstream_gap.columns
    assert "receipt_family" in fiscal_receipt_boundary.columns
    assert "target_question" in downstream_use_case.columns
    assert "interpretation_risk" in downstream_problem_variable.columns
    assert "series_key" in downstream_series_panel.columns
    assert "latest_nonzero_date" in downstream_series_panel.columns
    assert "comparison_key" in downstream_comparison_panel.columns
    assert "latest_nonzero_date" in downstream_comparison_panel.columns
    assert downstream_handoff_bundle["bundle_format"] == "tdc_downstream_handoff_v1"
    assert "summary" in downstream_handoff_bundle
    assert "estimator_contract" in downstream_handoff_bundle
    assert "backend_closeout_review" in downstream_handoff_bundle
    assert "backend_release_check" in downstream_handoff_bundle
    assert "artifact_key" in downstream_ingest_manifest.columns
    assert "ingest_priority" in downstream_ingest_manifest.columns
    assert "check_key" in downstream_consistency_review.columns
    assert set(downstream_consistency_review["status"]) == {"pass"}
    assert "release_readiness" in backend_closeout_review.columns
    assert "metric_value" in backend_release_check.columns
    assert "overall_recommendation" in readiness.columns
    assert "still_missing_for_current_default" in bank_source_map.columns
    assert "recommended_action" in bank_stop_gate.columns
    assert "delta_partial_m2_less_currency_level_mil" in monetary.columns
    assert "simple_non_treasury_control_subtotal_mil" in monetary_stage1.columns
    assert "refined_non_treasury_control_subtotal_mil" in monetary_stage1.columns
    assert "overlap_risk" in monetary_overlap.columns
    assert "residual_regime" in monetary_residual.columns
    assert "bank_wedge_dominance" in monetary_wedge.columns
    assert "bank_wedge_alignment_status" in monetary_definition.columns
    assert "federally_insured_credit_union_shares_and_deposits_mil" in ncua_bridge.columns
    assert "total_savings_institution_deposits_mil" in fdic_bridge.columns
    assert "has_credit_union_bridge_side" in monetary_bank_perimeter.columns
    assert "current_repo_stance" in monetary_bank_perimeter_map.columns
    assert "target_definition_component_dominance" in monetary_definition_decomp.columns
    assert "review_status" in monetary_bank_stress.columns
    assert "bank_residual_component_dominance" in monetary_bank_attr.columns
    assert "nonbank_bridge_materiality" in monetary_nonbank_bridge_attr.columns
    assert "loaded_liability_context_materiality" in monetary_liability_audit.columns
    assert "missing_source_families" in monetary_bank_perimeter.columns
    assert "candidate_series_or_product" in monetary_bank_perimeter_map.columns
    assert "recommendation_status" in monetary_pref.columns


def test_pipeline_writes_bank_minor_industry_share_availability_when_raw_input_is_present(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"

    generate_synthetic_raw_bundle(raw_dir, seed=7)
    pd.DataFrame(
        {
            "tax_year": [2022, 2022, 2022],
            "source_table": ["Publication 16 Table 5.3"] * 3,
            "source_url": ["https://www.irs.gov/pub/irs-soi/22co53ccr.xlsx"] * 3,
            "industry_key": [
                "commercial_banking",
                "savings_and_other_depository_credit_intermediation",
                "offices_of_bank_holding_companies",
            ],
            "industry_label": [
                "Commercial banking",
                "Savings institutions and other depository credit intermediation",
                "Offices of bank holding companies",
            ],
            "perimeter_type": ["bank_minor_industry", "bank_minor_industry", "bank_holding_minor_industry"],
            "source_column": ["ER", "ES", "FZ"],
            "income_subject_to_tax_raw": ["d", "d", "d"],
            "income_subject_to_tax_status": ["suppressed", "suppressed", "suppressed"],
            "income_subject_to_tax_thousands": [None, None, None],
            "total_income_tax_after_credits_raw": ["d", "d", "d"],
            "total_income_tax_after_credits_status": ["suppressed", "suppressed", "suppressed"],
            "total_income_tax_after_credits_thousands": [None, None, None],
            "usable_for_bank_only_share": [False, False, False],
        }
    ).to_csv(raw_dir / "irs__soi_bank_minor_industry_availability.csv", index=False)

    result = run_estimation_pipeline(raw_dir=raw_dir, processed_dir=processed_dir)

    assert result["bank_minor_industry_share_availability_path"] == str(
        processed_dir / "tdc_bank_minor_industry_share_availability.csv"
    )
    assert (processed_dir / "tdc_bank_minor_industry_share_availability.csv").exists()
    assert (processed_dir / "tdc_bank_minor_industry_share_availability.md").exists()
    availability = pd.read_csv(processed_dir / "tdc_bank_minor_industry_share_availability.csv")
    assert "public_bank_only_share_available" in availability.columns
    markdown = (processed_dir / "tdc_bank_minor_industry_share_availability.md").read_text()
    assert "Bank Minor-Industry Share Availability" in markdown
