from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.monetary_stage1_controls import (
    build_monetary_stage1_controls,
    render_monetary_stage1_controls_markdown,
    write_monetary_stage1_controls,
)


def test_build_monetary_stage1_controls_computes_control_subtotal_and_residuals() -> None:
    quarterly = pd.DataFrame(
        {
            "bank_credit": [9.0, 9.3],
            "loans_and_leases_bank_credit": [6.0, 6.2],
            "securities_in_bank_credit": [3.0, 3.1],
            "treasury_agency_non_mbs_bank_securities": [1.1, 1.15],
            "retail_money_market_funds": [1.0, 1.2],
            "reverse_repo_treasury": [0.5, 0.6],
            "reserve_balances_with_frb": [3000.0, 3050.0],
            "term_deposits_at_fed": [10.0, 15.0],
            "other_deposits_at_fed": [20.0, 23.0],
            "fed_liquidity_credit_loans_net": [50.0, 65.0],
            "commercial_bank_borrowings": [100.0, 140.0],
            "commercial_bank_cash_assets": [2.0, 2.1],
            "foreign_official_custody_treasuries": [500.0, 520.0],
            "foreign_related_treasury_agency_non_mbs": [40.0, 40.3],
            "tga_weekly": [700.0, 680.0],
        },
        index=pd.to_datetime(["2025-09-30", "2025-12-31"]),
    )
    stage0 = pd.DataFrame(
        {
            "delta_depository_target_level_mil": [100.0, 120.0],
            "delta_liquid_deposit_target_level_mil": [90.0, 110.0],
            "delta_commercial_bank_deposits_level_mil": [130.0, 140.0],
            "tier2_bank_only_flow_mil": [40.0, 50.0],
            "tier3_bank_only_flow_mil": [35.0, 45.0],
            "delta_bank_credit_level_mil": [200.0, 300.0],
        },
        index=pd.to_datetime(["2025-09-30", "2025-12-31"]),
    )

    out = build_monetary_stage1_controls(quarterly, stage0)
    latest = out.loc[pd.Timestamp("2025-12-31")]

    assert round(float(latest["retail_mmf_rotation_proxy_mil"]), 3) == -200.0
    assert round(float(latest["rrp_drain_proxy_mil"]), 3) == -100.0
    assert round(float(latest["reserve_balance_liquidity_proxy_mil"]), 3) == 50.0
    assert round(float(latest["simple_non_treasury_control_subtotal_mil"]), 3) == 50.0
    assert round(float(latest["delta_other_securities_ex_treasury_agency_level_mil"]), 3) == 50.0
    assert round(float(latest["non_treasury_bank_credit_proxy_mil"]), 3) == 250.0
    assert round(float(latest["refined_non_treasury_control_subtotal_mil"]), 3) == 0.0
    assert round(float(latest["fed_term_deposit_absorption_proxy_mil"]), 3) == -5.0
    assert round(float(latest["fed_other_deposits_absorption_proxy_mil"]), 3) == -3.0
    assert round(float(latest["fed_liquidity_credit_support_proxy_mil"]), 3) == 15.0
    assert round(float(latest["bank_borrowing_funding_proxy_mil"]), 3) == 40.0
    assert round(float(latest["expanded_liquidity_and_funding_control_subtotal_mil"]), 3) == 47.0
    assert round(float(latest["delta_foreign_official_custody_treasuries_mil"]), 3) == 20.0
    assert round(float(latest["delta_foreign_related_treasury_agency_non_mbs_mil"]), 3) == 300.0
    assert round(float(latest["depository_target_minus_tier3_bank_only_flow_mil_minus_simple_controls_mil"]), 3) == 25.0
    assert round(float(latest["commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil_minus_simple_controls_mil"]), 3) == 45.0
    assert round(float(latest["depository_target_minus_tier3_bank_only_flow_mil_minus_refined_controls_mil"]), 3) == 75.0
    assert round(float(latest["commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil_minus_refined_controls_mil"]), 3) == 95.0
    assert round(float(latest["depository_target_minus_tier3_bank_only_flow_mil_minus_expanded_controls_mil"]), 3) == 28.0
    assert round(float(latest["commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil_minus_expanded_controls_mil"]), 3) == 48.0


def test_write_monetary_stage1_controls_outputs_files(tmp_path: Path) -> None:
    csv_path = tmp_path / "stage1.csv"
    md_path = tmp_path / "stage1.md"
    quarterly = pd.DataFrame(
        {
            "bank_credit": [9.0, 9.3],
            "loans_and_leases_bank_credit": [6.0, 6.2],
            "securities_in_bank_credit": [3.0, 3.1],
            "treasury_agency_non_mbs_bank_securities": [1.1, 1.15],
            "retail_money_market_funds": [1.0, 1.2],
            "reverse_repo_treasury": [0.5, 0.6],
            "reserve_balances_with_frb": [3000.0, 3050.0],
            "term_deposits_at_fed": [10.0, 15.0],
            "other_deposits_at_fed": [20.0, 23.0],
            "fed_liquidity_credit_loans_net": [50.0, 65.0],
            "commercial_bank_borrowings": [100.0, 140.0],
            "commercial_bank_cash_assets": [2.0, 2.1],
            "foreign_official_custody_treasuries": [500.0, 520.0],
            "foreign_related_treasury_agency_non_mbs": [40.0, 40.3],
            "tga_weekly": [700.0, 680.0],
        },
        index=pd.to_datetime(["2025-09-30", "2025-12-31"]),
    )
    stage0 = pd.DataFrame(
        {
            "delta_depository_target_level_mil": [100.0, 120.0],
            "delta_commercial_bank_deposits_level_mil": [130.0, 140.0],
            "tier3_bank_only_flow_mil": [35.0, 45.0],
            "delta_bank_credit_level_mil": [200.0, 300.0],
        },
        index=pd.to_datetime(["2025-09-30", "2025-12-31"]),
    )

    _, _, controls = write_monetary_stage1_controls(
        quarterly=quarterly,
        monetary_stage0=stage0,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(controls)
    markdown = render_monetary_stage1_controls_markdown(controls)
    assert "Monetary Stage 1 Controls" in markdown
    assert "control-block diagnostic" in markdown
    assert "Refined subtotal" in markdown
    assert "Expanded subtotal" in markdown
    assert "Foreign custody context" in markdown
