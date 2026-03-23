from __future__ import annotations

import pandas as pd

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
            "fed_remit_or_deferred": [2.0, 0.0],
        },
        index=idx,
    )
    estimates, components, meta = compute_estimates(quarterly)

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

    assert round(estimates.loc[idx[0], "tdc_base_bank_only_ru_flow"], 6) == round(expected_bank_only[0], 6)
    assert round(estimates.loc[idx[1], "tdc_base_bank_only_ru_flow"], 6) == round(expected_bank_only[1], 6)
    assert round(estimates.loc[idx[0], "tdc_base_broad_depository_np_cu_ru_flow"], 6) == round(expected_broad_np[0], 6)
    assert round(estimates.loc[idx[1], "tdc_base_broad_depository_np_cu_ru_flow"], 6) == round(expected_broad_np[1], 6)
    assert round(estimates.loc[idx[0], "tdc_broad_depository_np_corp_cu_ru_flow"], 6) == round(expected_broad_np_corp[0], 6)
    assert round(estimates.loc[idx[1], "tdc_broad_depository_np_corp_cu_ru_flow"], 6) == round(expected_broad_np_corp[1], 6)
    assert round(estimates.loc[idx[0], "tdc_credit_union_aggregate_sensitivity"], 6) == round(expected_aggregate_cu[0], 6)
    assert round(estimates.loc[idx[1], "tdc_credit_union_aggregate_sensitivity"], 6) == round(expected_aggregate_cu[1], 6)
    assert round(components.loc[idx[0], "credit_unions_total_tsy_tx_reconstructed"], 6) == 3.9
    assert round(components.loc[idx[1], "credit_unions_total_tsy_tx_reconstructed"], 6) == 5.4
    assert meta["preferred_method"] == "tdc_base_bank_only_ru_flow"


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

    estimates, _, meta = compute_estimates(quarterly)

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
