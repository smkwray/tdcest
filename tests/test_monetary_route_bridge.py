from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.monetary_route_bridge import (
    build_monetary_route_bridge,
    render_monetary_route_bridge_markdown,
    write_monetary_route_bridge,
)


def test_build_monetary_route_bridge_labels_non_m2_routes() -> None:
    quarterly = pd.DataFrame(
        {
            "date": ["2025-03-31", "2025-06-30"],
            "retail_money_market_funds": [1000.0, 1040.0],
            "mmf_rrp_adjustment_prop": [0.0, 2500.0],
        }
    )
    methodology = pd.DataFrame(
        {
            "date": ["2025-03-31", "2025-06-30"],
            "quarter": ["2025Q1", "2025Q2"],
            "z1_security_absorption_du_bil": [9.0, 10.0],
            "z1_security_absorption_mmf_plumbing_bil": [7.0, 8.0],
            "z1_security_absorption_dealer_bridge_bil": [11.0, 12.0],
            "z1_security_absorption_other_financial_bil": [13.0, 14.0],
            "methodology_status": [
                "pass_tdcest_interest_split_and_z1_absorption_available",
                "pass_tdcest_interest_split_and_z1_absorption_available",
            ],
        }
    )

    bridge = build_monetary_route_bridge(
        quarterly,
        ratewall_du_ru_methodology=methodology,
    )
    latest = bridge.loc[bridge["quarter"].eq("2025Q2")]
    by_route = {row["route_id"]: row for _, row in latest.iterrows()}

    retail = by_route["retail_mmf_m2_non_deposit_scope"]
    assert retail["m2_scope"] == "true"
    assert retail["deposit_pass_through_scope"] == "false"
    assert retail["amount_bil"] == "40"

    onrrp = by_route["mmf_onrrp_runoff_non_m2_plumbing"]
    assert onrrp["m2_scope"] == "false"
    assert onrrp["deposit_pass_through_scope"] == "false"
    assert onrrp["amount_bil"] == "2.5"
    assert onrrp["canonical_tdc_math_change"] == "false"

    domestic = by_route["z1_domestic_nonbank_mixed_unknown_m2_scope"]
    assert domestic["m2_scope"] == "unknown_or_mixed"
    assert domestic["deposit_pass_through_scope"] == "unknown_or_mixed"
    assert domestic["ratewall_treatment"] == (
        "blocked_until_m2_or_deposit_funding_split_exists"
    )

    other = by_route["z1_other_financial_non_m2_scope"]
    assert other["m2_scope"] == "false"
    assert other["current_demand_eligible"] == "false"

    institutional = by_route["institutional_mmf_non_m2_target_not_split"]
    assert institutional["amount_status"] == "not_separately_observed_current_export"
    assert institutional["m2_scope"] == "false"


def test_write_monetary_route_bridge_outputs_files(tmp_path: Path) -> None:
    quarterly = pd.DataFrame(
        {
            "date": ["2025-03-31", "2025-06-30"],
            "retail_money_market_funds": [1000.0, 1040.0],
            "mmf_rrp_adjustment_prop": [0.0, 2500.0],
        }
    )
    csv_path = tmp_path / "bridge.csv"
    md_path = tmp_path / "bridge.md"

    _, _, bridge = write_monetary_route_bridge(
        quarterly=quarterly,
        ratewall_du_ru_methodology=None,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(bridge)
    markdown = render_monetary_route_bridge_markdown(bridge)
    assert "TDC Monetary Route Bridge" in markdown
    assert "classification-only" in markdown
