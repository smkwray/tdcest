from __future__ import annotations

import pandas as pd
import pytest

from tdc_estimator.estimators import compute_estimates


def test_base_estimator_formula_and_credit_union_ladder():
    idx = pd.to_datetime(["2024-03-31", "2024-06-30"])
    quarterly = pd.DataFrame(
        {
            "fed_tsy_tx": [10.0, 12.0],
            "us_chartered_tsy_tx": [20.0, 25.0],
            "foreign_offices_tsy_tx": [1.0, 2.0],
            "affiliated_areas_tsy_tx": [0.5, 0.5],
            "np_credit_unions_tsy_tx": [3.0, 4.0],
            "corp_credit_unions_tsy_tx": [0.8, 1.2],
            "ncua_capitalization_deposit_tx": [0.1, 0.2],
            "row_tsy_tx": [30.0, 28.0],
            "treasury_operating_cash_tx": [5.0, -8.0],
            "treasury_fed_internal_cash_tx": [0.0, 0.0],
            "fed_remit_or_deferred": [2.0, 0.0],
            "fed_tsy_coupon_interest_proxy": [1.5, 2.0],
            "fed_tier1_component_extension_proxy": [0.15, 0.2],
            "bank_tsy_coupon_interest_proxy": [0.7, 0.9],
            "row_tsy_coupon_interest_proxy": [1.1, 1.3],
            "credit_union_tsy_coupon_interest_proxy": [0.2, 0.25],
            "bank_tsy_bill_discount_interest_proxy": [0.05, 0.06],
            "row_tsy_bill_discount_interest_proxy": [0.07, 0.08],
            "credit_union_tsy_bill_discount_interest_proxy": [0.01, 0.02],
            "bank_tier2_component_interest_proxy": [0.8, 1.0],
            "row_tier2_component_interest_proxy": [1.2, 1.5],
            "credit_union_tier2_component_interest_proxy": [0.3, 0.35],
            "mmf_rrp_adjustment_lb": [0.5, 0.7],
            "mmf_rrp_adjustment_prop": [1.0, 1.4],
            "mmf_rrp_adjustment_ub": [1.8, 2.1],
            "mmf_rrp_bills_adjustment_lb": [0.3, 0.4],
            "mmf_rrp_bills_adjustment_prop": [0.6, 0.8],
            "mmf_rrp_bills_adjustment_ub": [0.9, 1.0],
            "bank_noninterest_outlay_proxy": [0.4, 0.6],
            "row_noninterest_outlay_proxy": [0.2, 0.3],
            "bank_nonborrow_receipt_proxy": [0.1, 0.2],
            "row_nonborrow_receipt_proxy": [0.05, 0.08],
            "mint_cb_cash_factor_proxy": [0.03, 0.04],
        },
        index=idx,
    )
    estimates, components, corrections, meta = compute_estimates(quarterly)

    expected_bank_only = (
        10 + 20 + 1 + 0.5 + 30 - 5 + 2,
        12 + 25 + 2 + 0.5 + 28 + 8 + 0,
    )
    expected_broad_np = (expected_bank_only[0] + 3.0, expected_bank_only[1] + 4.0)
    expected_broad_np_corp = (expected_broad_np[0] + 0.8, expected_broad_np[1] + 1.2)
    expected_aggregate_cu = (
        expected_broad_np_corp[0] + 0.1,
        expected_broad_np_corp[1] + 0.2,
    )
    expected_tier1_bank_only = (expected_bank_only[0] - 1.5, expected_bank_only[1] - 2.0)
    expected_tier1_broad_np = (expected_broad_np[0] - 1.5, expected_broad_np[1] - 2.0)
    expected_tier1_domestic = (
        (10 + 20 + 1 + 0.5 - 5 + 2) - 1.5,
        (12 + 25 + 2 + 0.5 + 8 + 0) - 2.0,
    )
    expected_tier2_bank_only = (
        expected_tier1_bank_only[0] - 0.7 - 1.1,
        expected_tier1_bank_only[1] - 0.9 - 1.3,
    )
    expected_tier2_broad_np = (
        expected_tier1_broad_np[0] - 0.7 - 1.1,
        expected_tier1_broad_np[1] - 0.9 - 1.3,
    )
    expected_tier2_di_np_cu = (
        expected_tier2_broad_np[0] - 0.2,
        expected_tier2_broad_np[1] - 0.25,
    )
    expected_tier2_component_bank_only = (
        expected_tier1_bank_only[0] - 0.8 - 1.2,
        expected_tier1_bank_only[1] - 1.0 - 1.5,
    )
    expected_tier2_component_broad_np = (
        expected_tier1_broad_np[0] - 0.8 - 1.2,
        expected_tier1_broad_np[1] - 1.0 - 1.5,
    )
    expected_tier2_component_di_np_cu = (
        expected_tier2_component_broad_np[0] - 0.3,
        expected_tier2_component_broad_np[1] - 0.35,
    )
    expected_tier2_component_domestic = (
        expected_tier1_domestic[0] - 0.8,
        expected_tier1_domestic[1] - 1.0,
    )
    expected_tier2_component_fed_extension_bank_only = (
        expected_tier2_component_bank_only[0] - 0.15,
        expected_tier2_component_bank_only[1] - 0.2,
    )
    expected_tier2_component_fed_extension_di_np_cu = (
        expected_tier2_component_di_np_cu[0] - 0.15,
        expected_tier2_component_di_np_cu[1] - 0.2,
    )
    expected_tier2_interest_robust = (
        expected_tier2_bank_only[0] - 0.05 - 0.07,
        expected_tier2_bank_only[1] - 0.06 - 0.08,
    )
    expected_tier2_di_interest_robust = (
        expected_tier2_di_np_cu[0] - 0.05 - 0.07 - 0.01,
        expected_tier2_di_np_cu[1] - 0.06 - 0.08 - 0.02,
    )
    expected_tier3_bank_only = (
        expected_tier2_component_bank_only[0] - 0.4 - 0.2 + 0.1 + 0.05 + 0.03,
        expected_tier2_component_bank_only[1] - 0.6 - 0.3 + 0.2 + 0.08 + 0.04,
    )
    expected_tier3_broad_np = (
        expected_tier2_component_broad_np[0] - 0.4 - 0.2 + 0.1 + 0.05 + 0.03,
        expected_tier2_component_broad_np[1] - 0.6 - 0.3 + 0.2 + 0.08 + 0.04,
    )
    expected_tier3_domestic = (
        expected_tier2_component_domestic[0] - 0.4 + 0.1 + 0.03,
        expected_tier2_component_domestic[1] - 0.6 + 0.2 + 0.04,
    )

    assert round(estimates.loc[idx[0], "tdc_base_bank_only_ru_flow"], 6) == round(expected_bank_only[0], 6)
    assert round(estimates.loc[idx[1], "tdc_base_bank_only_ru_flow"], 6) == round(expected_bank_only[1], 6)
    assert round(estimates.loc[idx[0], "tdc_base_broad_depository_np_cu_ru_flow"], 6) == round(expected_broad_np[0], 6)
    assert round(estimates.loc[idx[1], "tdc_base_broad_depository_np_cu_ru_flow"], 6) == round(expected_broad_np[1], 6)
    assert round(estimates.loc[idx[0], "tdc_broad_depository_np_corp_cu_ru_flow"], 6) == round(expected_broad_np_corp[0], 6)
    assert round(estimates.loc[idx[1], "tdc_broad_depository_np_corp_cu_ru_flow"], 6) == round(expected_broad_np_corp[1], 6)
    assert round(estimates.loc[idx[0], "tdc_credit_union_aggregate_sensitivity"], 6) == round(expected_aggregate_cu[0], 6)
    assert round(estimates.loc[idx[1], "tdc_credit_union_aggregate_sensitivity"], 6) == round(expected_aggregate_cu[1], 6)
    assert round(estimates.loc[idx[0], "tdc_tier1_fed_corrected_bank_only_ru_flow"], 6) == round(expected_tier1_bank_only[0], 6)
    assert round(estimates.loc[idx[1], "tdc_tier1_fed_corrected_bank_only_ru_flow"], 6) == round(expected_tier1_bank_only[1], 6)
    assert round(estimates.loc[idx[0], "tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow"], 6) == round(expected_tier1_broad_np[0], 6)
    assert round(estimates.loc[idx[1], "tdc_tier1_fed_corrected_broad_depository_np_cu_ru_flow"], 6) == round(expected_tier1_broad_np[1], 6)
    assert round(estimates.loc[idx[0], "tdc_tier1_fed_corrected_domestic_bank_only_ru_flow"], 6) == round(expected_tier1_domestic[0], 6)
    assert round(estimates.loc[idx[1], "tdc_tier1_fed_corrected_domestic_bank_only_ru_flow"], 6) == round(expected_tier1_domestic[1], 6)
    assert round(estimates.loc[idx[0], "tdc_tier2_interest_corrected_bank_only_ru_flow"], 6) == round(expected_tier2_component_bank_only[0], 6)
    assert round(estimates.loc[idx[1], "tdc_tier2_interest_corrected_bank_only_ru_flow"], 6) == round(expected_tier2_component_bank_only[1], 6)
    assert round(estimates.loc[idx[0], "tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow"], 6) == round(expected_tier2_component_broad_np[0], 6)
    assert round(estimates.loc[idx[1], "tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow"], 6) == round(expected_tier2_component_broad_np[1], 6)
    assert round(estimates.loc[idx[0], "tdc_tier2_interest_corrected_depository_institution_np_cu_ru_flow"], 6) == round(expected_tier2_component_di_np_cu[0], 6)
    assert round(estimates.loc[idx[1], "tdc_tier2_interest_corrected_depository_institution_np_cu_ru_flow"], 6) == round(expected_tier2_component_di_np_cu[1], 6)
    assert round(estimates.loc[idx[0], "tdc_tier2_h15_treasury_interest_robust_bank_only_ru_flow"], 6) == round(expected_tier2_interest_robust[0], 6)
    assert round(estimates.loc[idx[1], "tdc_tier2_h15_treasury_interest_robust_bank_only_ru_flow"], 6) == round(expected_tier2_interest_robust[1], 6)
    assert round(estimates.loc[idx[0], "tdc_tier2_h15_treasury_interest_robust_depository_institution_np_cu_ru_flow"], 6) == round(expected_tier2_di_interest_robust[0], 6)
    assert round(estimates.loc[idx[1], "tdc_tier2_h15_treasury_interest_robust_depository_institution_np_cu_ru_flow"], 6) == round(expected_tier2_di_interest_robust[1], 6)
    assert round(estimates.loc[idx[0], "tdc_tier2_h15_treasury_interest_robust_mmf_rrp_prop_bank_only_ru_flow"], 6) == round(expected_tier2_interest_robust[0] + 1.0, 6)
    assert round(estimates.loc[idx[1], "tdc_tier2_h15_treasury_interest_robust_mmf_rrp_prop_depository_institution_np_cu_ru_flow"], 6) == round(expected_tier2_di_interest_robust[1] + 1.4, 6)
    assert round(estimates.loc[idx[0], "tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow"], 6) == round(expected_tier2_component_di_np_cu[0] + 1.0, 6)
    assert round(estimates.loc[idx[1], "tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow"], 6) == round(expected_tier2_component_di_np_cu[1] + 1.4, 6)
    assert round(estimates.loc[idx[0], "tdc_tier2_mmf_rrp_prop_bank_only_ru_flow"], 6) == round(expected_tier2_component_bank_only[0] + 1.0, 6)
    assert round(estimates.loc[idx[1], "tdc_tier2_mmf_rrp_prop_bank_only_ru_flow"], 6) == round(expected_tier2_component_bank_only[1] + 1.4, 6)
    assert round(estimates.loc[idx[0], "tdc_tier2_mmf_rrp_lb_bank_only_ru_flow"], 6) == round(expected_tier2_component_bank_only[0] + 0.5, 6)
    assert round(estimates.loc[idx[1], "tdc_tier2_mmf_rrp_ub_bank_only_ru_flow"], 6) == round(expected_tier2_component_bank_only[1] + 2.1, 6)
    assert round(estimates.loc[idx[0], "tdc_tier2_mmf_rrp_prop_depository_institution_np_cu_ru_flow"], 6) == round(expected_tier2_component_di_np_cu[0] + 1.0, 6)
    assert round(estimates.loc[idx[1], "tdc_tier2_h15_mmf_rrp_bills_prop_bank_only_ru_flow"], 6) == round(expected_tier2_bank_only[1] + 0.8, 6)
    assert round(estimates.loc[idx[0], "tdc_tier2_interest_corrected_domestic_bank_only_ru_flow"], 6) == round(expected_tier2_component_domestic[0], 6)
    assert round(estimates.loc[idx[1], "tdc_tier2_interest_corrected_domestic_bank_only_ru_flow"], 6) == round(expected_tier2_component_domestic[1], 6)
    assert round(estimates.loc[idx[0], "tdc_tier2_component_anchored_bank_only_ru_flow"], 6) == round(expected_tier2_component_bank_only[0], 6)
    assert round(estimates.loc[idx[1], "tdc_tier2_component_anchored_bank_only_ru_flow"], 6) == round(expected_tier2_component_bank_only[1], 6)
    assert round(estimates.loc[idx[0], "tdc_tier2_component_anchored_broad_depository_np_cu_ru_flow"], 6) == round(expected_tier2_component_broad_np[0], 6)
    assert round(estimates.loc[idx[1], "tdc_tier2_component_anchored_broad_depository_np_cu_ru_flow"], 6) == round(expected_tier2_component_broad_np[1], 6)
    assert round(estimates.loc[idx[0], "tdc_tier2_component_anchored_depository_institution_np_cu_ru_flow"], 6) == round(expected_tier2_component_di_np_cu[0], 6)
    assert round(estimates.loc[idx[1], "tdc_tier2_component_anchored_depository_institution_np_cu_ru_flow"], 6) == round(expected_tier2_component_di_np_cu[1], 6)
    assert round(estimates.loc[idx[0], "tdc_tier2_component_anchored_domestic_bank_only_ru_flow"], 6) == round(expected_tier2_component_domestic[0], 6)
    assert round(estimates.loc[idx[1], "tdc_tier2_component_anchored_domestic_bank_only_ru_flow"], 6) == round(expected_tier2_component_domestic[1], 6)
    assert round(estimates.loc[idx[0], "tdc_tier2_component_anchored_mmf_rrp_prop_bank_only_ru_flow"], 6) == round(expected_tier2_component_bank_only[0] + 1.0, 6)
    assert round(estimates.loc[idx[1], "tdc_tier2_component_anchored_mmf_rrp_prop_depository_institution_np_cu_ru_flow"], 6) == round(expected_tier2_component_di_np_cu[1] + 1.4, 6)
    assert round(estimates.loc[idx[0], "tdc_tier2_component_anchored_fed_extension_bank_only_ru_flow"], 6) == round(expected_tier2_component_fed_extension_bank_only[0], 6)
    assert round(estimates.loc[idx[1], "tdc_tier2_component_anchored_fed_extension_depository_institution_np_cu_ru_flow"], 6) == round(expected_tier2_component_fed_extension_di_np_cu[1], 6)
    assert round(estimates.loc[idx[0], "tdc_tier2_component_anchored_fed_extension_mmf_rrp_prop_bank_only_ru_flow"], 6) == round(expected_tier2_component_fed_extension_bank_only[0] + 1.0, 6)
    assert round(estimates.loc[idx[0], "tdc_tier3_fiscal_corrected_bank_only_ru_flow"], 6) == round(expected_tier3_bank_only[0], 6)
    assert round(estimates.loc[idx[1], "tdc_tier3_fiscal_corrected_bank_only_ru_flow"], 6) == round(expected_tier3_bank_only[1], 6)
    assert round(estimates.loc[idx[0], "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow"], 6) == round(expected_tier3_broad_np[0], 6)
    assert round(estimates.loc[idx[1], "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow"], 6) == round(expected_tier3_broad_np[1], 6)
    assert round(estimates.loc[idx[0], "tdc_tier3_fiscal_corrected_domestic_bank_only_ru_flow"], 6) == round(expected_tier3_domestic[0], 6)
    assert round(estimates.loc[idx[1], "tdc_tier3_fiscal_corrected_domestic_bank_only_ru_flow"], 6) == round(expected_tier3_domestic[1], 6)
    assert round(components.loc[idx[0], "fed_tsy_coupon_interest_proxy"], 6) == 1.5
    assert round(components.loc[idx[1], "fed_tsy_coupon_interest_proxy"], 6) == 2.0
    assert round(components.loc[idx[0], "fed_tier1_component_extension_proxy"], 6) == 0.15
    assert round(components.loc[idx[0], "bank_tsy_coupon_interest_proxy"], 6) == 0.7
    assert round(components.loc[idx[1], "bank_tsy_coupon_interest_proxy"], 6) == 0.9
    assert round(components.loc[idx[0], "row_tsy_coupon_interest_proxy"], 6) == 1.1
    assert round(components.loc[idx[1], "row_tsy_coupon_interest_proxy"], 6) == 1.3
    assert round(components.loc[idx[0], "credit_union_tsy_coupon_interest_proxy"], 6) == 0.2
    assert round(components.loc[idx[0], "bank_tsy_bill_discount_interest_proxy"], 6) == 0.05
    assert round(components.loc[idx[0], "row_tsy_bill_discount_interest_proxy"], 6) == 0.07
    assert round(components.loc[idx[0], "credit_union_tsy_bill_discount_interest_proxy"], 6) == 0.01
    assert round(components.loc[idx[0], "bank_tier2_component_interest_proxy"], 6) == 0.8
    assert round(components.loc[idx[0], "row_tier2_component_interest_proxy"], 6) == 1.2
    assert round(components.loc[idx[0], "credit_union_tier2_component_interest_proxy"], 6) == 0.3
    assert round(components.loc[idx[1], "mmf_rrp_adjustment_prop"], 6) == 1.4
    assert round(corrections.loc[idx[0], "tier1_fed_coupon_correction"], 6) == -1.5
    assert round(corrections.loc[idx[1], "tier1_fed_coupon_correction"], 6) == -2.0
    assert round(corrections.loc[idx[0], "tier1_fed_component_extension_correction"], 6) == -0.15
    assert round(corrections.loc[idx[0], "tier2_bank_h15_coupon_correction"], 6) == -0.7
    assert round(corrections.loc[idx[1], "tier2_bank_h15_coupon_correction"], 6) == -0.9
    assert round(corrections.loc[idx[0], "tier2_row_h15_coupon_correction"], 6) == -1.1
    assert round(corrections.loc[idx[1], "tier2_row_h15_coupon_correction"], 6) == -1.3
    assert round(corrections.loc[idx[0], "tier2_credit_union_h15_coupon_correction"], 6) == -0.2
    assert round(corrections.loc[idx[0], "tier2_bank_bill_discount_robustness_correction"], 6) == -0.05
    assert round(corrections.loc[idx[0], "tier2_row_bill_discount_robustness_correction"], 6) == -0.07
    assert round(corrections.loc[idx[0], "tier2_credit_union_bill_discount_robustness_correction"], 6) == -0.01
    assert round(corrections.loc[idx[0], "tier2_bank_component_interest_correction"], 6) == -0.8
    assert round(corrections.loc[idx[0], "tier2_row_component_interest_correction"], 6) == -1.2
    assert round(corrections.loc[idx[0], "tier2_credit_union_component_interest_correction"], 6) == -0.3
    assert round(corrections.loc[idx[1], "tier2_mmf_rrp_prop_adjustment"], 6) == 1.4
    assert round(corrections.loc[idx[0], "tdc_tier1_bank_only_delta_from_base"], 6) == -1.5
    assert round(corrections.loc[idx[1], "tdc_tier1_bank_only_delta_from_base"], 6) == -2.0
    assert round(corrections.loc[idx[0], "tdc_tier2_bank_only_delta_from_base"], 6) == round(
        expected_tier2_component_bank_only[0] - expected_bank_only[0], 6
    )
    assert round(corrections.loc[idx[1], "tdc_tier2_bank_only_delta_from_base"], 6) == round(
        expected_tier2_component_bank_only[1] - expected_bank_only[1], 6
    )
    assert round(corrections.loc[idx[0], "tdc_tier2_bank_only_delta_from_tier1"], 6) == -2.0
    assert round(corrections.loc[idx[1], "tdc_tier2_bank_only_delta_from_tier1"], 6) == -2.5
    assert round(corrections.loc[idx[0], "tier3_bank_noninterest_outlay_correction"], 6) == -0.4
    assert round(corrections.loc[idx[1], "tier3_bank_noninterest_outlay_correction"], 6) == -0.6
    assert round(corrections.loc[idx[0], "tier3_row_noninterest_outlay_correction"], 6) == -0.2
    assert round(corrections.loc[idx[1], "tier3_row_noninterest_outlay_correction"], 6) == -0.3
    assert round(corrections.loc[idx[0], "tier3_bank_nonborrow_receipt_correction"], 6) == 0.1
    assert round(corrections.loc[idx[1], "tier3_bank_nonborrow_receipt_correction"], 6) == 0.2
    assert round(corrections.loc[idx[0], "tier3_row_nonborrow_receipt_correction"], 6) == 0.05
    assert round(corrections.loc[idx[1], "tier3_row_nonborrow_receipt_correction"], 6) == 0.08
    assert round(corrections.loc[idx[0], "tier3_mint_cb_cash_factor_correction"], 6) == 0.03
    assert round(corrections.loc[idx[1], "tier3_mint_cb_cash_factor_correction"], 6) == 0.04
    assert round(corrections.loc[idx[0], "tdc_tier3_bank_only_delta_from_base"], 6) == round(
        expected_tier3_bank_only[0] - expected_bank_only[0], 6
    )
    assert round(corrections.loc[idx[1], "tdc_tier3_bank_only_delta_from_base"], 6) == round(
        expected_tier3_bank_only[1] - expected_bank_only[1], 6
    )
    assert round(corrections.loc[idx[0], "tdc_tier3_bank_only_delta_from_tier2"], 6) == -0.42
    assert round(corrections.loc[idx[1], "tdc_tier3_bank_only_delta_from_tier2"], 6) == -0.58
    assert round(components.loc[idx[0], "credit_unions_total_tsy_tx_reconstructed"], 6) == 3.9
    assert round(components.loc[idx[1], "credit_unions_total_tsy_tx_reconstructed"], 6) == 5.4
    assert meta["preferred_method"] == "tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow"
    assert meta["canonical_tier2_method"] == "tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow"
    assert meta["canonical_tier2_status"] == "available"
    assert meta["ladder_inputs_by_deposit_concept"] == {
        "bank_only": "tdc_base_bank_only_ru_flow",
        "broad_depository": "tdc_base_broad_depository_np_cu_ru_flow",
    }
    assert meta["cash_term"]["transaction_series_key"] == "treasury_operating_cash_tx"
    assert meta["cash_term"]["diagnostic_only_series"] == ["tga_weekly"]
    assert "Tax and Loan" in meta["cash_term"]["historical_treatment"]
    assert meta["correction_inputs"]["fed_tsy_coupon_interest_proxy"]["raw_filename"] == "support__fed_tsy_coupon_interest_proxy.csv"
    assert meta["correction_inputs"]["fed_tier1_component_extension_proxy"]["raw_filename"] == "support__fed_tier1_component_extension_proxy.csv"
    assert meta["correction_inputs"]["bank_tsy_coupon_interest_proxy"]["raw_filename"] == "support__bank_tsy_coupon_interest_proxy.csv"
    assert meta["correction_inputs"]["row_tsy_coupon_interest_proxy"]["raw_filename"] == "support__row_tsy_coupon_interest_proxy.csv"
    assert meta["correction_inputs"]["credit_union_tsy_coupon_interest_proxy"]["raw_filename"] == "support__credit_union_tsy_coupon_interest_proxy.csv"
    assert meta["correction_inputs"]["bank_tier2_component_interest_proxy"]["raw_filename"] == "support__bank_tier2_component_interest_proxy.csv"
    assert meta["correction_inputs"]["row_tier2_component_interest_proxy"]["raw_filename"] == "support__row_tier2_component_interest_proxy.csv"
    assert meta["correction_inputs"]["credit_union_tier2_component_interest_proxy"]["raw_filename"] == "support__credit_union_tier2_component_interest_proxy.csv"
    assert meta["correction_inputs"]["mmf_fund_month_rrp_adjustment"]["raw_filename"] == "support__mmf_fund_month.csv"
    assert meta["correction_inputs"]["bank_noninterest_outlay_proxy"]["raw_filename"] == "support__bank_noninterest_outlay_proxy.csv"
    assert meta["correction_inputs"]["row_noninterest_outlay_proxy"]["raw_filename"] == "support__row_noninterest_outlay_proxy.csv"
    assert meta["correction_inputs"]["bank_nonborrow_receipt_proxy"]["raw_filename"] == "support__bank_nonborrow_receipt_proxy.csv"
    assert meta["correction_inputs"]["row_nonborrow_receipt_proxy"]["raw_filename"] == "support__row_nonborrow_receipt_proxy.csv"
    assert meta["correction_inputs"]["mint_cb_cash_factor_proxy"]["raw_filename"] == "support__mint_cb_cash_factor_proxy.csv"
    assert meta["bank_perimeter"]["default_bank_block"] == "us_chartered_plus_foreign_offices_plus_affiliated_areas"


def test_tier2_requires_bank_and_row_support_inputs():
    idx = pd.to_datetime(["2024-03-31"])
    quarterly = pd.DataFrame(
        {
            "fed_tsy_tx": [10.0],
            "us_chartered_tsy_tx": [20.0],
            "foreign_offices_tsy_tx": [1.0],
            "affiliated_areas_tsy_tx": [0.5],
            "np_credit_unions_tsy_tx": [3.0],
            "corp_credit_unions_tsy_tx": [0.8],
            "ncua_capitalization_deposit_tx": [0.1],
            "row_tsy_tx": [30.0],
            "treasury_operating_cash_tx": [5.0],
            "treasury_fed_internal_cash_tx": [0.0],
            "fed_remit_or_deferred": [2.0],
            "fed_tsy_coupon_interest_proxy": [1.5],
        },
        index=idx,
    )

    estimates, _, _, _ = compute_estimates(quarterly)

    assert "tdc_tier1_fed_corrected_bank_only_ru_flow" in estimates.columns
    assert "tdc_tier2_interest_corrected_bank_only_ru_flow" not in estimates.columns
    assert "tdc_tier2_interest_corrected_broad_depository_np_cu_ru_flow" not in estimates.columns
    assert "tdc_tier2_interest_corrected_domestic_bank_only_ru_flow" not in estimates.columns


def test_tier3_requires_fiscal_support_inputs():
    idx = pd.to_datetime(["2024-03-31"])
    quarterly = pd.DataFrame(
        {
            "fed_tsy_tx": [10.0],
            "us_chartered_tsy_tx": [20.0],
            "foreign_offices_tsy_tx": [1.0],
            "affiliated_areas_tsy_tx": [0.5],
            "np_credit_unions_tsy_tx": [3.0],
            "corp_credit_unions_tsy_tx": [0.8],
            "ncua_capitalization_deposit_tx": [0.1],
            "row_tsy_tx": [30.0],
            "treasury_operating_cash_tx": [5.0],
            "treasury_fed_internal_cash_tx": [0.0],
            "fed_remit_or_deferred": [2.0],
            "fed_tsy_coupon_interest_proxy": [1.5],
            "bank_tsy_coupon_interest_proxy": [0.7],
            "row_tsy_coupon_interest_proxy": [1.1],
        },
        index=idx,
    )

    estimates, _, _, _ = compute_estimates(quarterly)

    assert "tdc_tier2_interest_corrected_bank_only_ru_flow" in estimates.columns
    assert "tdc_tier3_fiscal_corrected_bank_only_ru_flow" not in estimates.columns
    assert "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow" not in estimates.columns
    assert "tdc_tier3_fiscal_corrected_domestic_bank_only_ru_flow" not in estimates.columns


def test_historical_extension_backfills_from_level_sensitivity_before_transaction_history():
    idx = pd.to_datetime(["1990-03-31", "1990-06-30", "2002-12-31"])
    quarterly = pd.DataFrame(
        {
            "fed_tsy_tx": [float("nan"), float("nan"), 10.0],
            "us_chartered_tsy_tx": [float("nan"), float("nan"), 20.0],
            "foreign_offices_tsy_tx": [float("nan"), float("nan"), 1.0],
            "affiliated_areas_tsy_tx": [float("nan"), float("nan"), 0.5],
            "np_credit_unions_tsy_tx": [float("nan"), float("nan"), 3.0],
            "corp_credit_unions_tsy_tx": [float("nan"), float("nan"), 0.8],
            "ncua_capitalization_deposit_tx": [float("nan"), float("nan"), 0.1],
            "row_tsy_tx": [float("nan"), float("nan"), 30.0],
            "treasury_operating_cash_tx": [float("nan"), float("nan"), 5.0],
            "treasury_fed_internal_cash_tx": [float("nan"), float("nan"), 0.0],
            "fed_remit_or_deferred": [float("nan"), float("nan"), 2.0],
            "fed_tsy_level": [100.0, 120.0, 140.0],
            "us_chartered_tsy_level": [200.0, 230.0, 260.0],
            "foreign_offices_tsy_level": [20.0, 21.0, 22.0],
            "affiliated_areas_tsy_level": [10.0, 12.0, 13.0],
            "np_credit_unions_tsy_level": [30.0, 34.0, 38.0],
            "row_tsy_level": [300.0, 320.0, 350.0],
            "treasury_operating_cash_level": [80.0, 90.0, 95.0],
        },
        index=idx,
    )

    estimates, _, _, meta = compute_estimates(quarterly)

    expected_bank_backfill = (120 + 230 + 21 + 12 + 320) - (100 + 200 + 20 + 10 + 300) - (90 - 80)
    expected_broad_backfill = expected_bank_backfill + ((34 - 30))

    assert round(estimates.loc[idx[1], "tdc_level_bank_only_sensitivity"], 6) == round(expected_bank_backfill, 6)
    assert round(estimates.loc[idx[1], "tdc_bank_only_extended_1990"], 6) == round(expected_bank_backfill, 6)
    assert pd.isna(estimates.loc[idx[1], "tdc_base_bank_only_ru_flow"])
    assert round(estimates.loc[idx[1], "tdc_level_broad_depository_np_cu_sensitivity"], 6) == round(expected_broad_backfill, 6)
    assert round(estimates.loc[idx[1], "tdc_broad_depository_extended_1990"], 6) == round(expected_broad_backfill, 6)
    assert pd.isna(estimates.loc[idx[1], "tdc_base_broad_depository_np_cu_ru_flow"])
    assert round(estimates.loc[idx[2], "tdc_base_bank_only_ru_flow"], 6) == 58.5
    assert round(estimates.loc[idx[2], "tdc_bank_only_extended_1990"], 6) == 58.5
    assert meta["historical_backfill"]["historical_extension_starts"] == "1990-03-31"
    assert meta["historical_backfill"]["transaction_history_starts"] == "2002-12-31"


def test_transaction_history_starts_2002q1_when_mts_remittance_backfill_is_available():
    idx = pd.to_datetime(["2002-03-31", "2002-06-30", "2002-12-31"])
    quarterly = pd.DataFrame(
        {
            "fed_tsy_tx": [10.0, 11.0, 12.0],
            "us_chartered_tsy_tx": [20.0, 21.0, 22.0],
            "foreign_offices_tsy_tx": [1.0, 1.0, 1.0],
            "affiliated_areas_tsy_tx": [0.5, 0.5, 0.5],
            "np_credit_unions_tsy_tx": [3.0, 3.0, 3.0],
            "corp_credit_unions_tsy_tx": [0.8, 0.8, 0.8],
            "ncua_capitalization_deposit_tx": [0.1, 0.1, 0.1],
            "row_tsy_tx": [30.0, 31.0, 32.0],
            "treasury_operating_cash_tx": [5.0, 5.0, 5.0],
            "treasury_fed_internal_cash_tx": [0.0, 0.0, 0.0],
            "fed_remit_or_deferred": [2.0, 2.0, 2.0],
        },
        index=idx,
    )

    estimates, _, _, meta = compute_estimates(quarterly)

    assert round(estimates.loc[idx[0], "tdc_base_bank_only_ru_flow"], 6) == 58.5
    assert meta["historical_backfill"]["transaction_history_starts"] == "2002-03-31"


def test_canonical_row_is_never_filled_from_h15_coupon_only_rows():
    # Without component-anchored interest support the H.15 path still builds its
    # coupon-only DI + MMF rows, but those omit bill discount and FRN interest. The
    # canonical row and the headline pointers must stay empty rather than relabel them.
    idx = pd.to_datetime(["2024-03-31", "2024-06-30"])
    quarterly = pd.DataFrame(
        {
            "fed_tsy_tx": [10.0, 12.0],
            "us_chartered_tsy_tx": [20.0, 25.0],
            "foreign_offices_tsy_tx": [1.0, 2.0],
            "affiliated_areas_tsy_tx": [0.5, 0.5],
            "np_credit_unions_tsy_tx": [3.0, 4.0],
            "corp_credit_unions_tsy_tx": [0.8, 1.2],
            "ncua_capitalization_deposit_tx": [0.1, 0.2],
            "row_tsy_tx": [30.0, 28.0],
            "treasury_operating_cash_tx": [5.0, -8.0],
            "treasury_fed_internal_cash_tx": [0.0, 0.0],
            "fed_remit_or_deferred": [2.0, 0.0],
            "fed_tsy_coupon_interest_proxy": [1.5, 2.0],
            "bank_tsy_coupon_interest_proxy": [0.7, 0.9],
            "row_tsy_coupon_interest_proxy": [1.1, 1.3],
            "credit_union_tsy_coupon_interest_proxy": [0.2, 0.25],
            "mmf_rrp_adjustment_lb": [0.5, 0.7],
            "mmf_rrp_adjustment_prop": [1.0, 1.4],
            "mmf_rrp_adjustment_ub": [1.8, 2.1],
        },
        index=idx,
    )
    estimates, _, _, meta = compute_estimates(quarterly)

    assert "tdc_tier2_h15_mmf_rrp_prop_depository_institution_np_cu_ru_flow" in estimates.columns
    assert "tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow" not in estimates.columns
    assert meta["preferred_method"] is None
    assert meta["canonical_tier2_method"] is None
    assert meta["canonical_tier2_status"].startswith("unavailable: requires component-anchored")


def test_decomposition_proxy_puts_h8_billions_on_the_z1_million_scale():
    # M2, currency and bank credit come from H.8/H.6 in USD billions; the Z.1 bank Treasury
    # levels are USD millions. Mixing them made the proxy track bank Treasury holdings alone.
    idx = pd.to_datetime(["2024-03-31", "2024-06-30"])
    quarterly = pd.DataFrame(
        {
            "fed_tsy_tx": [0.0, 0.0],
            "us_chartered_tsy_tx": [0.0, 0.0],
            "foreign_offices_tsy_tx": [0.0, 0.0],
            "affiliated_areas_tsy_tx": [0.0, 0.0],
            "row_tsy_tx": [0.0, 0.0],
            "treasury_operating_cash_tx": [0.0, 0.0],
            "treasury_fed_internal_cash_tx": [0.0, 0.0],
            "fed_remit_or_deferred": [0.0, 0.0],
            "m2": [21000.0, 21100.0],
            "currency": [2300.0, 2310.0],
            "bank_credit": [17500.0, 17560.0],
            "us_chartered_tsy_level": [3_900_000.0, 3_930_000.0],
            "foreign_offices_tsy_level": [100_000.0, 101_000.0],
            "affiliated_areas_tsy_level": [5_000.0, 5_000.0],
        },
        index=idx,
    )
    estimates, _, _, _ = compute_estimates(quarterly)

    # (100 - 10 - (60 - 31)) billion = 61 billion = 61,000 million.
    assert estimates.loc[idx[1], "tdc_decomposition_proxy_bank_centric"] == pytest.approx(61_000.0)


def _fail_closed_frame(dates: list[str]) -> pd.DataFrame:
    n = len(dates)
    return pd.DataFrame(
        {
            "fed_tsy_tx": [10.0] * n,
            "us_chartered_tsy_tx": [20.0] * n,
            "foreign_offices_tsy_tx": [1.0] * n,
            "affiliated_areas_tsy_tx": [0.5] * n,
            "row_tsy_tx": [30.0] * n,
            "treasury_operating_cash_tx": [5.0] * n,
            "treasury_fed_internal_cash_tx": [0.0] * n,
            "fed_remit_or_deferred": [2.0] * n,
        },
        index=pd.to_datetime(dates),
    )


def test_a_missing_required_leg_leaves_the_quarter_missing_instead_of_zero():
    # A failed or short download used to enter as zero through min_count=1 sums, so a
    # quarter without ROW purchases or remittances still published a full-looking TDC.
    quarterly = _fail_closed_frame(["2024-03-31", "2024-06-30", "2024-09-30"])
    quarterly.loc["2024-06-30", "row_tsy_tx"] = float("nan")
    quarterly.loc["2024-09-30", "foreign_offices_tsy_tx"] = float("nan")
    estimates, _, _, _ = compute_estimates(quarterly)

    base = estimates["tdc_base_bank_only_ru_flow"]
    assert base.loc["2024-03-31"] == pytest.approx(10 + 20 + 1 + 0.5 + 30 - 5 + 2)
    assert base.loc["2024-06-30":].isna().all()


def test_remittances_are_required_and_missing_quarters_stay_missing():
    quarterly = _fail_closed_frame(["2024-03-31", "2024-06-30"])
    quarterly.loc["2024-06-30", "fed_remit_or_deferred"] = float("nan")
    estimates, _, _, _ = compute_estimates(quarterly)
    assert pd.isna(estimates.loc["2024-06-30", "tdc_base_bank_only_ru_flow"])
    assert estimates.loc["2024-06-30", "tdc_no_remit_bank_only"] == pytest.approx(10 + 20 + 1 + 0.5 + 30 - 5)

    with pytest.raises(ValueError, match="fed_remit_or_deferred"):
        compute_estimates(quarterly.drop(columns="fed_remit_or_deferred"))


def test_level_backfill_records_where_remittances_are_excluded():
    dates = ["2001-09-30", "2001-12-31", "2002-03-31", "2002-06-30"]
    quarterly = _fail_closed_frame(dates)
    quarterly["fed_remit_or_deferred"] = [float("nan"), float("nan"), 2.0, 3.0]
    for key, level in {
        "fed_tsy_level": [100.0, 110.0, 120.0, 130.0],
        "us_chartered_tsy_level": [50.0, 52.0, 54.0, 56.0],
        "foreign_offices_tsy_level": [5.0, 5.0, 5.0, 5.0],
        "affiliated_areas_tsy_level": [1.0, 1.0, 1.0, 1.0],
        "row_tsy_level": [200.0, 205.0, 210.0, 215.0],
        "treasury_operating_cash_level": [30.0, 31.0, 32.0, 33.0],
    }.items():
        quarterly[key] = level
    estimates, components, _, meta = compute_estimates(quarterly)

    assert components.loc["2001-12-31", "fed_remit_positive"] != components.loc["2001-12-31", "fed_remit_positive"]
    level = estimates["tdc_level_bank_only_sensitivity"]
    assert level.loc["2001-12-31"] == pytest.approx(10 + 2 + 5 - 1)  # no remittance before coverage
    assert level.loc["2002-06-30"] == pytest.approx(10 + 2 + 5 - 1 + 3)
    assert meta["historical_backfill"]["fed_remittance_coverage_start"] == "2002-03-31"


def test_mmf_route_is_zero_before_on_rrp_and_missing_when_unobserved_after():
    dates = ["2013-06-30", "2013-09-30", "2013-12-31", "2014-03-31"]
    quarterly = _fail_closed_frame(dates)
    for key in ["fed_tsy_coupon_interest_proxy", "bank_tsy_coupon_interest_proxy", "row_tsy_coupon_interest_proxy"]:
        quarterly[key] = 0.0
    nan = float("nan")
    quarterly["mmf_rrp_adjustment_lb"] = [nan, nan, 1.0, nan]
    quarterly["mmf_rrp_adjustment_prop"] = [nan, 0.0, 2.0, nan]
    quarterly["mmf_rrp_adjustment_ub"] = [nan, 0.0, 3.0, nan]
    estimates, _, corrections, meta = compute_estimates(quarterly)

    prop = corrections["tier2_mmf_rrp_prop_adjustment"]
    lb = corrections["tier2_mmf_rrp_lb_adjustment"]
    assert prop.loc["2013-06-30"] == 0.0  # before the facility: structurally zero
    assert lb.loc["2013-09-30"] == 0.0  # 0 <= lb <= ub = 0
    assert prop.loc["2013-12-31"] == 2.0
    assert pd.isna(prop.loc["2014-03-31"])  # active quarter without filings: missing, not zero
    assert pd.isna(estimates.loc["2014-03-31", "tdc_tier2_mmf_rrp_prop_bank_only_ru_flow"])
    assert meta["mmf_rrp_route_status_counts"]["mmf_rrp_adjustment"] == {
        "missing_active_period": 1,
        "observed_one_sided": 1,
        "observed_one_sided_lb_implied_by_zero_ub": 1,
        "structural_zero_pre_on_rrp_mechanism": 1,
    }

    with pytest.raises(ValueError, match="lb, prop and ub together"):
        compute_estimates(quarterly.drop(columns="mmf_rrp_adjustment_ub"))


def test_a_late_starting_remittance_series_is_not_backfilled_inside_the_transaction_era():
    # The level-change backfill may exclude unknown remittances only before transaction data
    # begin. A remittance series that starts late must leave transaction-era quarters empty,
    # not fill them with a level-change estimate that silently drops remittances.
    dates = ["2023-12-31", "2024-03-31", "2024-06-30"]
    quarterly = _fail_closed_frame(dates)
    quarterly["fed_remit_or_deferred"] = [float("nan"), float("nan"), 3.0]
    for key, level in {
        "fed_tsy_level": [100.0, 110.0, 120.0],
        "us_chartered_tsy_level": [50.0, 52.0, 54.0],
        "foreign_offices_tsy_level": [5.0, 5.0, 5.0],
        "affiliated_areas_tsy_level": [1.0, 1.0, 1.0],
        "row_tsy_level": [200.0, 205.0, 210.0],
        "treasury_operating_cash_level": [30.0, 31.0, 32.0],
    }.items():
        quarterly[key] = level
    estimates, _, _, meta = compute_estimates(quarterly)

    assert meta["historical_backfill"]["transaction_history_starts"] == "2002-12-31"
    assert pd.isna(estimates.loc["2024-03-31", "tdc_level_bank_only_sensitivity"])
    assert pd.isna(estimates.loc["2024-03-31", "tdc_bank_only_extended_1990"])
    assert estimates.loc["2024-06-30", "tdc_level_bank_only_sensitivity"] == pytest.approx(10 + 2 + 5 - 1 + 3)
    assert estimates.loc["2024-06-30", "tdc_bank_only_extended_1990"] == pytest.approx(10 + 20 + 1 + 0.5 + 30 - 5 + 3)


def test_canonical_metadata_requires_an_observed_quarter():
    quarterly = _fail_closed_frame(["2024-03-31", "2024-06-30"])
    for key in ["fed_tsy_coupon_interest_proxy", "bank_tsy_coupon_interest_proxy", "row_tsy_coupon_interest_proxy",
                "credit_union_tsy_coupon_interest_proxy", "np_credit_unions_tsy_tx"]:
        quarterly[key] = 0.0
    for key in ["bank_tier2_component_interest_proxy", "row_tier2_component_interest_proxy",
                "credit_union_tier2_component_interest_proxy"]:
        quarterly[key] = float("nan")
    for key in ["mmf_rrp_adjustment_lb", "mmf_rrp_adjustment_prop", "mmf_rrp_adjustment_ub"]:
        quarterly[key] = 0.0
    estimates, _, _, meta = compute_estimates(quarterly)

    assert estimates["tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow"].isna().all()
    assert meta["preferred_method"] is None
    assert meta["canonical_tier2_status"].startswith("unavailable")


def _internal_transfer_frame(operating_cash, internal):
    idx = pd.to_datetime(["2020-03-31", "2020-06-30"])
    return pd.DataFrame(
        {
            "fed_tsy_tx": [10.0, 12.0],
            "us_chartered_tsy_tx": [20.0, 25.0],
            "foreign_offices_tsy_tx": [1.0, 2.0],
            "affiliated_areas_tsy_tx": [0.5, 0.5],
            "np_credit_unions_tsy_tx": [3.0, 4.0],
            "corp_credit_unions_tsy_tx": [0.8, 1.2],
            "ncua_capitalization_deposit_tx": [0.1, 0.2],
            "row_tsy_tx": [30.0, 28.0],
            "treasury_operating_cash_tx": operating_cash,
            "treasury_fed_internal_cash_tx": internal,
            "fed_remit_or_deferred": [2.0, 1.0],
        },
        index=idx,
    )


def test_treasury_fed_internal_transfers_leave_tdc_unchanged():
    # Quarter two: Treasury pays 114 of equity into the facility LLCs (operating cash -114) and the
    # LLCs buy 95.6 of nonmarketable Treasury securities (operating cash +95.6). Neither touches a deposit.
    baseline, _, _, _ = compute_estimates(_internal_transfer_frame([5.0, -8.0], [0.0, 0.0]))
    internal = -114.0 + 95.6
    shifted, components, _, _ = compute_estimates(_internal_transfer_frame([5.0, -8.0 + internal], [0.0, internal]))
    columns = [c for c in baseline.columns if c.endswith("_ru_flow") or c == "tdc_no_remit_bank_only"]
    assert columns
    pd.testing.assert_frame_equal(shifted[columns], baseline[columns])
    assert components["minus_treasury_operating_cash_tx"].tolist() == [-5.0, 8.0]
    # Read on raw operating cash, the transfers would add 18.4 to measured TDC.
    raw, _, _, _ = compute_estimates(_internal_transfer_frame([5.0, -8.0 + internal], [0.0, 0.0]))
    assert raw.loc[raw.index[1], "tdc_base_bank_only_ru_flow"] - baseline.loc[baseline.index[1], "tdc_base_bank_only_ru_flow"] == pytest.approx(-internal)


def test_operating_cash_term_requires_the_internal_transfer_series():
    frame = _internal_transfer_frame([5.0, -8.0], [0.0, 0.0])
    with pytest.raises(ValueError, match="treasury_fed_internal_cash_tx"):
        compute_estimates(frame.drop(columns="treasury_fed_internal_cash_tx"))
    frame.loc[frame.index[1], "treasury_fed_internal_cash_tx"] = float("nan")
    with pytest.raises(ValueError, match="internal cash support missing"):
        compute_estimates(frame)
