from __future__ import annotations

import pandas as pd

from tdc_estimator.downstream_estimator_gap_review import build_downstream_estimator_gap_review


def test_downstream_estimator_gap_review_includes_live_and_historical_gaps() -> None:
    index = pd.to_datetime(["2025-12-31"])
    estimates = pd.DataFrame(
        {
            "tdc_base_bank_only_ru_flow": [80.0],
            "tdc_tier2_interest_corrected_bank_only_ru_flow": [50.0],
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [40.0],
            "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow": [45.0],
        },
        index=index,
    )
    components = pd.DataFrame(
        {
            "np_credit_unions_tsy_tx": [4.0],
            "corp_credit_unions_tsy_tx": [1.0],
            "ncua_capitalization_deposit_tx": [0.5],
        },
        index=index,
    )
    corrections = pd.DataFrame(
        {
            "tier1_fed_coupon_correction": [-5.0],
            "tier2_bank_coupon_correction": [-10.0],
            "tier2_row_coupon_correction": [-15.0],
            "tier3_bank_noninterest_outlay_correction": [-2.0],
            "tier3_row_noninterest_outlay_correction": [-7.0],
            "tier3_bank_nonborrow_receipt_correction": [0.0],
            "tier3_row_nonborrow_receipt_correction": [0.0],
            "tier3_mint_cb_cash_factor_correction": [-1.0],
        },
        index=index,
    )
    historical = pd.DataFrame(
        {
            "date": ["2024-12-31"],
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [100.0],
            "tdc_tier3_bank_only_plus_historical_bank_receipt_candidate": [107.0],
            "tdc_tier3_bank_only_plus_historical_bank_receipt_lower_bound": [102.0],
            "bank_receipt_historical_default_candidate_delta_mil": [7.0],
            "bank_receipt_historical_lower_bound_delta_mil": [2.0],
        }
    )

    frame = build_downstream_estimator_gap_review(
        estimates=estimates,
        components=components,
        corrections=corrections,
        tier3_historical_bank_receipt_research=historical,
    )

    assert set(frame["gap_key"]) == {
        "latest_live_base_to_tier2_bank_only",
        "latest_live_tier2_to_tier3_bank_only",
        "latest_live_bank_to_broad_depository_tier3",
        "latest_historical_bank_receipt_overlay",
        "latest_historical_candidate_to_lower_bound",
    }

    live_gap = frame.loc[frame["gap_key"].eq("latest_live_base_to_tier2_bank_only")].iloc[0]
    assert live_gap["net_delta_millions"] == -30.0
    assert live_gap["dominant_component_key"] == "tier2_row_coupon_correction"

    historical_gap = frame.loc[frame["gap_key"].eq("latest_historical_bank_receipt_overlay")].iloc[0]
    assert historical_gap["net_delta_millions"] == 7.0
    assert historical_gap["lhs_value_millions"] == 107.0
    assert historical_gap["rhs_value_millions"] == 100.0
    assert historical_gap["dominant_component_key"] == "bank_receipt_historical_default_candidate_delta_mil"
    assert historical_gap["dominant_component_role"] == "additive_driver"
    assert historical_gap["secondary_component_key"] == "n/a"

    lower_gap = frame.loc[frame["gap_key"].eq("latest_historical_candidate_to_lower_bound")].iloc[0]
    assert lower_gap["lhs_value_millions"] == 107.0
    assert lower_gap["rhs_value_millions"] == 102.0
    assert lower_gap["dominant_component_role"] == "endpoint_context"
    assert lower_gap["secondary_component_role"] == "endpoint_context"
    assert lower_gap["secondary_component_millions"] == -2.0

    perimeter_gap = frame.loc[frame["gap_key"].eq("latest_live_bank_to_broad_depository_tier3")].iloc[0]
    assert perimeter_gap["dominant_component_key"] == "np_credit_unions_tsy_tx"
    assert perimeter_gap["secondary_component_key"] == "n/a"
