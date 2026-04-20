from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.monetary_stage0 import (
    build_monetary_stage0_diagnostics,
    render_monetary_stage0_diagnostics_markdown,
    write_monetary_stage0_diagnostics,
)


def test_build_monetary_stage0_diagnostics_computes_partial_target_gaps() -> None:
    quarterly = pd.DataFrame(
        {
            "m2": [10.0, 10.4],
            "currency": [2.0, 2.1],
            "retail_money_market_funds": [1.0, 1.1],
            "small_time_deposits": [0.5, 0.55],
            "commercial_bank_deposits": [6.8, 6.95],
            "credit_union_deposits": [900.0, 930.0],
            "thrift_deposits": [600.0, 640.0],
            "large_time_deposits_all_commercial_banks": [1.4, 1.5],
            "other_deposits_all_commercial_banks": [5.4, 5.45],
            "bank_credit": [9.0, 9.3],
        },
        index=pd.to_datetime(["2025-09-30", "2025-12-31"]),
    )
    estimates = pd.DataFrame(
        {
            "tdc_base_bank_only_ru_flow": [100.0, 120.0],
            "tdc_tier2_interest_corrected_bank_only_ru_flow": [60.0, 80.0],
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [55.0, 70.0],
        },
        index=pd.to_datetime(["2025-09-30", "2025-12-31"]),
    )

    out = build_monetary_stage0_diagnostics(quarterly, estimates, start="2025-09-30")

    latest = out.loc[pd.Timestamp("2025-12-31")]
    assert round(float(latest["delta_partial_m2_less_currency_level_mil"]), 3) == 300.0
    assert round(float(latest["delta_depository_target_level_mil"]), 3) == 200.0
    assert round(float(latest["delta_liquid_deposit_target_level_mil"]), 3) == 150.0
    assert round(float(latest["delta_commercial_bank_deposits_level_mil"]), 3) == 150.0
    assert round(float(latest["delta_credit_union_deposits_level_mil"]), 3) == 30.0
    assert round(float(latest["delta_thrift_deposits_level_mil"]), 3) == 40.0
    assert round(float(latest["delta_nonbank_depository_bridge_level_mil"]), 3) == 70.0
    assert round(float(latest["delta_large_time_deposits_all_commercial_banks_level_mil"]), 3) == 100.0
    assert round(float(latest["delta_other_deposits_all_commercial_banks_level_mil"]), 3) == 50.0
    assert round(float(latest["partial_target_minus_tier0_bank_only_flow_mil"]), 3) == 180.0
    assert round(float(latest["depository_target_minus_tier3_bank_only_flow_mil"]), 3) == 130.0
    assert round(float(latest["commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil"]), 3) == 80.0
    assert round(float(latest["partial_target_minus_tier2_bank_only_flow_mil"]), 3) == 220.0
    assert round(float(latest["partial_target_minus_tier3_bank_only_flow_mil"]), 3) == 230.0
    assert not bool(latest["target_is_partial"])
    assert bool(latest["has_commercial_bank_deposit_series"])
    assert bool(latest["has_credit_union_deposit_series"])
    assert bool(latest["has_thrift_deposit_series"])
    assert bool(latest["has_large_time_bank_deposit_series"])
    assert bool(latest["has_other_deposits_bank_series"])


def test_write_monetary_stage0_diagnostics_outputs_files(tmp_path: Path) -> None:
    csv_path = tmp_path / "monetary.csv"
    md_path = tmp_path / "monetary.md"
    quarterly = pd.DataFrame(
        {
            "m2": [10.0, 10.2],
            "currency": [2.0, 2.1],
            "retail_money_market_funds": [1.0, 1.0],
            "small_time_deposits": [0.5, 0.5],
            "commercial_bank_deposits": [6.8, 6.9],
            "credit_union_deposits": [900.0, 930.0],
            "thrift_deposits": [600.0, 640.0],
            "large_time_deposits_all_commercial_banks": [1.4, 1.5],
            "other_deposits_all_commercial_banks": [5.4, 5.45],
        },
        index=pd.to_datetime(["2025-09-30", "2025-12-31"]),
    )
    estimates = pd.DataFrame(
        {"tdc_base_bank_only_ru_flow": [100.0, 120.0]},
        index=pd.to_datetime(["2025-09-30", "2025-12-31"]),
    )

    _, _, diagnostics = write_monetary_stage0_diagnostics(
        quarterly=quarterly,
        estimates=estimates,
        csv_path=csv_path,
        markdown_path=md_path,
        start="2025-09-30",
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(diagnostics)
    markdown = render_monetary_stage0_diagnostics_markdown(diagnostics)
    assert "Monetary Stage 0 Diagnostics" in markdown
    assert "commercial-bank-deposit change" in markdown
    assert "credit-union-deposit change" in markdown
    assert "thrift-deposit change" in markdown
    assert "nonbank-depository-bridge change" in markdown
    assert "large-time-deposit change" in markdown
    assert "other-deposits change" in markdown
