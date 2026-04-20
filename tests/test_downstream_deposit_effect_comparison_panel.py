from __future__ import annotations

import pandas as pd

from tdc_estimator.downstream_deposit_effect_comparison_panel import (
    build_downstream_deposit_effect_comparison_panel,
)


def test_downstream_deposit_effect_comparison_panel_builds_live_historical_and_nondefault_deltas() -> None:
    index = pd.to_datetime(["2025-09-30", "2025-12-31"])
    estimates = pd.DataFrame(
        {
            "tdc_base_bank_only_ru_flow": [10.0, 11.0],
            "tdc_tier2_interest_corrected_bank_only_ru_flow": [8.0, 9.0],
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [7.0, 6.0],
            "tdc_tier3_fiscal_corrected_broad_depository_np_cu_ru_flow": [7.5, 6.5],
        },
        index=index,
    )
    corrections = pd.DataFrame(index=index)
    historical = pd.DataFrame(
        {
            "date": ["2024-12-31"],
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [100.0],
            "tdc_tier3_bank_only_plus_historical_bank_receipt_candidate": [107.0],
            "tdc_tier3_bank_only_plus_historical_bank_receipt_lower_bound": [102.0],
        }
    )
    row_mrv = pd.DataFrame(
        {
            "date": ["2025-09-30", "2025-12-31"],
            "row_state_visa_allocated_receipt_mil": [0.5, 0.0],
        }
    )
    receipt = pd.DataFrame(
        [
            {
                "branch_key": "bank_table51_historical_window",
                "promotion_boundary": "historical_default_only_current_nondefault",
            },
            {
                "branch_key": "bank_table51_current_window",
                "promotion_boundary": "historical_default_only_current_nondefault",
            },
            {
                "branch_key": "row_mrv_cbsp_primary",
                "promotion_boundary": "stop_at_mrv_nondefault_pilot",
            },
        ]
    )

    frame = build_downstream_deposit_effect_comparison_panel(
        estimates=estimates,
        corrections=corrections,
        tier3_historical_bank_receipt_research=historical,
        row_state_visa_timing_sensitivity=row_mrv,
        receipt_unblock_status=receipt,
    )

    keys = set(frame["comparison_key"])
    assert "bank_only_tier2_minus_base" in keys
    assert "bank_only_tier3_minus_tier2" in keys
    assert "historical_bank_receipt_candidate_minus_default_tier3" in keys
    assert "row_mrv_nondefault_pilot_minus_live_zero" in keys

    tier2_gap = frame.loc[frame["comparison_key"].eq("bank_only_tier2_minus_base")].iloc[-1]
    assert tier2_gap["net_delta_millions"] == -2.0

    hist_gap = frame.loc[
        frame["comparison_key"].eq("historical_bank_receipt_candidate_minus_default_tier3")
    ].iloc[0]
    assert bool(hist_gap["historical_only"]) is True
    assert hist_gap["net_delta_millions"] == 7.0

    row_gap = frame.loc[frame["comparison_key"].eq("row_mrv_nondefault_pilot_minus_live_zero")].iloc[-1]
    assert bool(row_gap["nondefault_only"]) is True
    assert row_gap["row_receipt_boundary"] == "stop_at_mrv_nondefault_pilot"
    assert row_gap["latest_nonzero_date"] == pd.Timestamp("2025-09-30")
    assert row_gap["latest_nonzero_value_millions"] == 0.5
