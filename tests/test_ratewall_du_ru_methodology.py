from __future__ import annotations

import pandas as pd
import pytest

from tdc_estimator.ratewall_du_ru_methodology import (
    build_ratewall_du_ru_methodology_panel,
)


def test_build_ratewall_du_ru_methodology_panel_combines_tdcest_interest_and_z1_absorption() -> None:
    du_fiscal_flow = pd.DataFrame(
        {
            "date": ["2025-03-31", "2025-06-30"],
            "treasury_interest_gross_proxy": [1000.0, 1200.0],
            "du_coupon_proxy_primary": [250.0, 300.0],
        }
    )
    interest_method = pd.DataFrame(
        {
            "date": ["2025-03-31", "2025-06-30"],
            "bank_method_tier": ["component_pool_wamest_bucket_backcast", "constrained_component"],
            "row_method_tier": ["component_pool_wamest_bucket_backcast", "constrained_component"],
            "credit_union_method_tier": ["component_pool_wamest_bucket_backcast", "constrained_component"],
        }
    )
    z1_holder_absorption = pd.DataFrame(
        {
            "quarter": ["2025-03-31", "2025-06-30"],
            "sector_tx_fed": [1.0, 2.0],
            "sector_tx_banks": [3.0, 4.0],
            "sector_tx_row": [5.0, 6.0],
            "sector_tx_mmf": [7.0, 8.0],
            "sector_tx_domestic_nonbank": [9.0, 10.0],
            "sector_tx_dealer_bridge": [11.0, 12.0],
            "sector_tx_other_financial": [13.0, 14.0],
            "sector_tx_unmapped": [15.0, 16.0],
            "holder_source_layer": ["z1_exact_fu_transactions", "z1_exact_fu_transactions"],
            "residual_interpretation": ["official FU layer", "official FU layer"],
        }
    )

    frame = build_ratewall_du_ru_methodology_panel(
        du_fiscal_flow,
        interest_method,
        z1_holder_absorption,
    )

    latest = frame.loc[frame["quarter"].eq("2025Q2")].iloc[0]
    assert latest["treasury_interest_total_bil"] == 1.2
    assert latest["treasury_interest_to_du_bil"] == 0.3
    assert latest["treasury_interest_to_ru_bil"] == pytest.approx(0.9)
    assert latest["treasury_interest_du_share"] == 0.25
    assert latest["z1_security_absorption_du_bil"] == 10.0
    assert latest["z1_security_absorption_fed_bil"] == 2.0
    assert latest["z1_security_absorption_banks_bil"] == 4.0
    assert latest["z1_security_absorption_row_bil"] == 6.0
    assert latest["z1_security_absorption_core_ru_bil"] == 12.0
    assert latest["z1_security_absorption_mmf_plumbing_bil"] == 8.0
    assert latest["z1_security_absorption_total_mapped_bil"] == 72.0
    assert latest["z1_domestic_nonbank_proxy_caveat"] == (
        "domestic_nonbank_z1_holder_transaction_proxy_not_exact_"
        "deposit_funded_final_demand"
    )
    assert latest["z1_mmf_plumbing_label"] == (
        "mmf_onrrp_plumbing_separate_from_deposit_funded_du"
    )
    assert latest["methodology_proxy_label"] == (
        "owner_directed_tdcest_interest_z1_holder_absorption_"
        "methodology_proxy_nonheadline_noncanonical"
    )
    assert latest["tdcest_interest_tier_caveat"] == (
        "modern_constrained_component_method"
    )
    assert latest["methodology_status"] == (
        "pass_tdcest_interest_split_and_z1_absorption_available"
    )
