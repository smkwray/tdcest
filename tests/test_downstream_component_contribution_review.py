from __future__ import annotations

import pandas as pd

from tdc_estimator.downstream_component_contribution_review import (
    build_downstream_component_contribution_review,
)


def test_downstream_component_contribution_review_includes_live_and_historical_rows():
    index = pd.to_datetime(["2024-12-31", "2025-12-31"])
    estimates = pd.DataFrame(
        {
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [96.0, -40.0],
            "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow": [98.0, -39.0],
        },
        index=index,
    )
    components = pd.DataFrame(
        {
            "fed_tsy_tx": [20.0, 21.0],
            "bank_depository_tsy_tx": [30.0, 31.0],
            "row_tsy_tx": [10.0, 11.0],
            "minus_treasury_operating_cash_tx": [15.0, 16.0],
            "fed_remit_positive": [1.0, 0.0],
            "np_credit_unions_tsy_tx": [2.0, 2.5],
        },
        index=index,
    )
    corrections = pd.DataFrame(
        {
            "tier1_fed_coupon_correction": [-5.0, -5.5],
            "tier2_bank_coupon_correction": [-6.0, -6.5],
            "tier2_row_coupon_correction": [-7.0, -7.5],
            "tier3_bank_noninterest_outlay_correction": [-1.0, -1.1],
            "tier3_row_noninterest_outlay_correction": [-2.0, -2.1],
            "tier3_bank_nonborrow_receipt_correction": [0.0, 0.0],
            "tier3_row_nonborrow_receipt_correction": [0.0, 0.0],
            "tier3_mint_cb_cash_factor_correction": [0.5, 0.0],
        },
        index=index,
    )
    historical = pd.DataFrame(
        [
            {
                "date": "2024-12-31",
                "tdc_tier3_fiscal_corrected_bank_only_ru_flow": 96.0,
                "tdc_tier3_bank_only_plus_historical_bank_receipt_candidate": 103.0,
                "tdc_tier3_bank_only_plus_historical_bank_receipt_lower_bound": 98.0,
                "bank_receipt_historical_default_candidate_delta_mil": 7.0,
                "bank_receipt_historical_lower_bound_delta_mil": 2.0,
            }
        ]
    )
    receipt = pd.DataFrame(
        [
            {"branch_key": "bank_table51_current_window", "summary_note": "Current bank receipt remains nondefault."},
            {"branch_key": "row_mrv_cbsp_primary", "summary_note": "MRV remains nondefault."},
        ]
    )

    frame = build_downstream_component_contribution_review(
        estimates=estimates,
        components=components,
        corrections=corrections,
        tier3_historical_bank_receipt_research=historical,
        receipt_unblock_status=receipt,
    )

    scenarios = set(frame["scenario_key"])
    assert "latest_live_bank_tier3_default" in scenarios
    assert "latest_live_broad_tier3_default" in scenarios
    assert "latest_historical_bank_receipt_variant" in scenarios
    overlay = frame.loc[frame["component_key"].eq("bank_receipt_historical_default_candidate_delta_mil")]
    assert not overlay.empty
