from __future__ import annotations

import pandas as pd

from tdc_estimator.z1_domestic_nonbank_sector_context import (
    build_z1_domestic_nonbank_sector_context,
    render_z1_domestic_nonbank_sector_context_markdown,
)


def test_z1_domestic_nonbank_sector_context_splits_sectors_fail_closed() -> None:
    source = pd.DataFrame(
        {
            "quarter": ["2025-12-31"],
            "z1_component_money_market_funds_total_treasuries_bn": [285.458],
            "z1_component_security_brokers_dealers_treasuries_net_bn": [49.779],
            "z1_component_government_sponsored_enterprises_treasuries_bn": [-8.424],
            "z1_component_mutual_funds_treasuries_bn": [37.911],
            "z1_component_closed_end_funds_treasuries_bn": [0.054],
            "z1_component_exchange_traded_funds_treasuries_bn": [36.43],
            "z1_component_insurance_pensions_total_treasuries_bn": [0.361],
            "z1_component_households_nonprofits_treasuries_residual_holder_bn": [
                54.416
            ],
            "z1_component_nonfinancial_corporate_treasuries_bn": [3.729],
            "z1_component_nonfinancial_noncorporate_us_government_securities_bn": [
                0.84
            ],
            "z1_component_state_local_governments_treasuries_ex_slgs_bn": [-21.174],
            "z1_component_asset_backed_securities_issuers_treasuries_bn": [0.133],
            "z1_component_holding_companies_treasuries_bn": [-5.783],
            "z1_component_central_clearing_counterparties_treasuries_bn": [12.509],
        }
    )

    panel = build_z1_domestic_nonbank_sector_context(source)

    assert len(panel) == 14
    assert set(panel["current_demand_eligible"]) == {"false"}
    assert set(panel["canonical_tdc_math_change"]) == {"false"}
    assert not any(
        str(value).startswith("pass_")
        for value in panel["ratewall_current_demand_gate"]
    )
    by_sector = {row["sector_route_id"]: row for _, row in panel.iterrows()}

    mmf = by_sector["z1_mmf_sector_context"]
    assert mmf["m2_scope"] == "mixed_retail_mmf_and_non_m2_mmf"
    assert mmf["ratewall_current_demand_gate"] == "fail_mixed_unknown"

    dealer = by_sector["z1_security_brokers_dealers_sector_context"]
    assert dealer["debited_claim_type"] == "repo_claim"
    assert dealer["ratewall_current_demand_gate"] == "fail_noncurrent_claim"

    household = by_sector["z1_households_nonprofits_residual_sector_context"]
    assert household["debited_claim_type"] == "mixed_unknown"
    assert household["deposit_pass_through_scope"] == "unknown_or_mixed"


def test_z1_domestic_nonbank_sector_context_markdown_records_boundary() -> None:
    source = pd.DataFrame(
        {
            "quarter": ["2025-12-31"],
            "z1_component_money_market_funds_total_treasuries_bn": [285.458],
        }
    )
    panel = build_z1_domestic_nonbank_sector_context(source)

    markdown = render_z1_domestic_nonbank_sector_context_markdown(panel)

    assert "Z.1 Domestic Nonbank Sector Context" in markdown
    assert "no row identifies a deposit debit" in markdown
