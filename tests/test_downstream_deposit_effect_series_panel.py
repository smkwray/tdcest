from __future__ import annotations

import pandas as pd

from tdc_estimator.downstream_deposit_effect_series_panel import (
    build_downstream_deposit_effect_series_panel,
)


def test_downstream_deposit_effect_series_panel_builds_live_historical_and_nondefault_series() -> None:
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
    historical = pd.DataFrame(
        {
            "date": ["2024-12-31"],
            "tdc_tier3_bank_only_plus_historical_bank_receipt_candidate": [103.0],
            "tdc_tier3_bank_only_plus_historical_bank_receipt_lower_bound": [98.0],
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

    frame = build_downstream_deposit_effect_series_panel(
        estimates=estimates,
        tier3_historical_bank_receipt_research=historical,
        row_state_visa_timing_sensitivity=row_mrv,
        receipt_unblock_status=receipt,
    )

    keys = set(frame["series_key"])
    assert "tdc_tier3_fiscal_corrected_bank_only_ru_flow" in keys
    assert "tdc_tier3_bank_only_plus_historical_bank_receipt_candidate" in keys
    assert "row_mrv_primary_nondefault_pilot_series" in keys

    tier2_row = frame.loc[frame["series_key"].eq("tdc_tier2_interest_corrected_bank_only_ru_flow")].iloc[-1]
    assert tier2_row["default_classification"] == "headline_default"

    tier3_row = frame.loc[frame["series_key"].eq("tdc_tier3_fiscal_corrected_bank_only_ru_flow")].iloc[-1]
    assert tier3_row["use_case_key"] == "tier3_partial_shell_diagnostic"
    assert tier3_row["default_classification"] == "diagnostic_outlay_only_partial_shell"

    historical_row = frame.loc[
        frame["series_key"].eq("tdc_tier3_bank_only_plus_historical_bank_receipt_candidate")
    ].iloc[0]
    assert bool(historical_row["historical_only"]) is True

    mrv_row = frame.loc[frame["series_key"].eq("row_mrv_primary_nondefault_pilot_series")].iloc[-1]
    assert bool(mrv_row["nondefault_only"]) is True
    assert mrv_row["row_receipt_boundary"] == "stop_at_mrv_nondefault_pilot"
    assert mrv_row["latest_nonzero_date"] == pd.Timestamp("2025-09-30")
    assert mrv_row["latest_nonzero_value_millions"] == 0.5
