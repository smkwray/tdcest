from __future__ import annotations

import pandas as pd

from tdc_estimator.monetary_route_bridge import build_monetary_route_bridge
from tdc_estimator.route_admissibility_registry import (
    build_route_admissibility_registry,
    render_route_admissibility_registry_markdown,
)


def _source_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
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
    monetary = build_monetary_route_bridge(
        quarterly,
        ratewall_du_ru_methodology=methodology,
    )
    mmf = pd.DataFrame(
        [
            {
                "date": "2025-03-31",
                "quarter": "2025Q1",
                "route_id": "retail_mmf_treasury_holdings_context",
                "route_label": "Retail MMF Treasury holdings context.",
                "source_family": "sec_nmfp_fund_type_portfolio_context",
                "source_artifact_count": "1",
                "fund_scope": "retail_mmf",
                "fund_type_scope": "all_sec_nmfp_money_market_fund_categories",
                "fund_count": "1",
                "total_assets_bil": "1",
                "treasury_total_bil": "0.3",
                "treasury_bills_bil": "0.3",
                "treasury_coupons_bil": "0",
                "fed_onrrp_bil": "0.1",
                "m1_scope": "false",
                "m2_scope": "true",
                "deposit_pass_through_scope": "false",
                "current_demand_eligible": "false",
                "tdc_estimator_treatment": "context_only_not_canonical_tdc_math",
                "ratewall_treatment": "context_only_not_deposit_pass_through",
                "canonical_tdc_math_change": "false",
                "exact_blocker": "fund_type_and_portfolio_holdings_do_not_identify_final_investor_current_demand_conversion",
                "source_status": "source_backed_sec_nmfp_context",
                "notes": "SEC N-MFP identifies fund retail status and portfolio Treasury holdings.",
            },
            {
                "date": "2025-03-31",
                "quarter": "2025Q1",
                "route_id": "retail_mmf_onrrp_plumbing_context",
                "route_label": "Retail MMF Fed ON-RRP holdings context.",
                "source_family": "sec_nmfp_fund_type_portfolio_context",
                "source_artifact_count": "1",
                "fund_scope": "retail_mmf",
                "fund_type_scope": "all_sec_nmfp_money_market_fund_categories",
                "fund_count": "1",
                "total_assets_bil": "1",
                "treasury_total_bil": "0.3",
                "treasury_bills_bil": "0.3",
                "treasury_coupons_bil": "0",
                "fed_onrrp_bil": "0.1",
                "m1_scope": "false",
                "m2_scope": "true",
                "deposit_pass_through_scope": "false",
                "current_demand_eligible": "false",
                "tdc_estimator_treatment": "context_only_not_canonical_tdc_math",
                "ratewall_treatment": "fed_onrrp_plumbing_context_only",
                "canonical_tdc_math_change": "false",
                "exact_blocker": "fed_onrrp_holdings_are_fed_plumbing_not_bank_deposit_or_recipient_demand_evidence",
                "source_status": "source_backed_sec_nmfp_context",
                "notes": "SEC N-MFP identifies Fed ON-RRP portfolio holdings by fund scope.",
            },
            {
                "date": "2025-03-31",
                "quarter": "2025Q1",
                "route_id": "institutional_or_nonretail_mmf_treasury_holdings_context",
                "route_label": "Institutional/nonretail MMF Treasury holdings context.",
                "source_family": "sec_nmfp_fund_type_portfolio_context",
                "source_artifact_count": "1",
                "fund_scope": "institutional_or_nonretail_mmf",
                "fund_type_scope": "all_sec_nmfp_money_market_fund_categories",
                "fund_count": "1",
                "total_assets_bil": "2",
                "treasury_total_bil": "0.7",
                "treasury_bills_bil": "0",
                "treasury_coupons_bil": "0.7",
                "fed_onrrp_bil": "0.4",
                "m1_scope": "false",
                "m2_scope": "false",
                "deposit_pass_through_scope": "false",
                "current_demand_eligible": "false",
                "tdc_estimator_treatment": "context_only_not_canonical_tdc_math",
                "ratewall_treatment": "context_only_not_deposit_pass_through",
                "canonical_tdc_math_change": "false",
                "exact_blocker": "fund_type_and_portfolio_holdings_do_not_identify_final_investor_current_demand_conversion",
                "source_status": "source_backed_sec_nmfp_context",
                "notes": "SEC N-MFP identifies fund retail status and portfolio Treasury holdings.",
            },
            {
                "date": "2025-03-31",
                "quarter": "2025Q1",
                "route_id": "institutional_or_nonretail_mmf_onrrp_plumbing_context",
                "route_label": "Institutional/nonretail MMF Fed ON-RRP holdings context.",
                "source_family": "sec_nmfp_fund_type_portfolio_context",
                "source_artifact_count": "1",
                "fund_scope": "institutional_or_nonretail_mmf",
                "fund_type_scope": "all_sec_nmfp_money_market_fund_categories",
                "fund_count": "1",
                "total_assets_bil": "2",
                "treasury_total_bil": "0.7",
                "treasury_bills_bil": "0",
                "treasury_coupons_bil": "0.7",
                "fed_onrrp_bil": "0.4",
                "m1_scope": "false",
                "m2_scope": "false",
                "deposit_pass_through_scope": "false",
                "current_demand_eligible": "false",
                "tdc_estimator_treatment": "context_only_not_canonical_tdc_math",
                "ratewall_treatment": "fed_onrrp_plumbing_context_only",
                "canonical_tdc_math_change": "false",
                "exact_blocker": "fed_onrrp_holdings_are_fed_plumbing_not_bank_deposit_or_recipient_demand_evidence",
                "source_status": "source_backed_sec_nmfp_context",
                "notes": "SEC N-MFP identifies Fed ON-RRP portfolio holdings by fund scope.",
            },
        ]
    )
    return monetary, mmf


def test_route_admissibility_registry_covers_route_ids_without_quarterly_bloat() -> None:
    monetary, mmf = _source_frames()
    registry = build_route_admissibility_registry(
        monetary_route_bridge=monetary,
        mmf_route_split_context=mmf,
    )

    expected = set(monetary["route_id"]) | set(mmf["route_id"])
    assert set(registry["route_id"]) == expected
    assert registry["route_id"].is_unique
    assert "quarter" not in registry.columns


def test_route_admissibility_registry_fail_closes_current_demand() -> None:
    monetary, mmf = _source_frames()
    registry = build_route_admissibility_registry(
        monetary_route_bridge=monetary,
        mmf_route_split_context=mmf,
    )
    by_route = {row["route_id"]: row for _, row in registry.iterrows()}

    assert set(registry["current_demand_eligible"]) == {"false"}
    assert set(registry["canonical_tdc_math_change"]) == {"false"}
    assert not any(
        str(value).startswith("pass_")
        for value in registry["ratewall_current_demand_gate"]
    )

    retail = by_route["retail_mmf_m2_non_deposit_scope"]
    assert retail["m2_scope"] == "true"
    assert retail["deposit_pass_through_scope"] == "false"
    assert retail["tdc_admissibility"] == "context_only"

    retail_holding = by_route["retail_mmf_treasury_holdings_context"]
    assert retail_holding["m2_scope"] == "true"
    assert retail_holding["deposit_pass_through_scope"] == "false"
    assert retail_holding["ratewall_current_demand_gate"] == "fail_investor_type_only"

    institutional = by_route[
        "institutional_or_nonretail_mmf_treasury_holdings_context"
    ]
    assert institutional["m2_scope"] == "false"
    assert institutional["tdc_admissibility"] == "context_only"

    onrrp = by_route["mmf_onrrp_runoff_non_m2_plumbing"]
    assert onrrp["debited_claim_type"] == "fed_rrp_liability"
    assert onrrp["tdc_admissibility"] == "named_plumbing_adjustment"
    assert onrrp["ratewall_current_demand_gate"] == "fail_noncurrent_claim"
    assert onrrp["onrrp_boundary_status"] == (
        "nyfed_fed_liability_counterparty_type_context"
    )
    assert onrrp["onrrp_counterparty_scope"] == "mmf_counterparty_aggregate"

    broad_z1 = by_route["z1_domestic_nonbank_mixed_unknown_m2_scope"]
    assert broad_z1["debited_claim_type"] == "mixed_unknown"
    assert broad_z1["ratewall_current_demand_gate"] == "fail_mixed_unknown"

    dealer = by_route["z1_dealer_repo_bridge_non_m2_or_unknown_scope"]
    assert dealer["tdc_admissibility"] == "context_only"
    assert dealer["ratewall_current_demand_gate"] == "fail_noncurrent_claim"

    retail_onrrp = by_route["retail_mmf_onrrp_plumbing_context"]
    assert retail_onrrp["onrrp_boundary_status"] == (
        "sec_nmfp_fed_onrrp_portfolio_context"
    )
    assert retail_onrrp["onrrp_counterparty_scope"] == "retail_mmf_fund_scope"
    assert retail_onrrp["current_demand_eligible"] == "false"


def test_route_admissibility_registry_markdown_records_guardrail_boundary() -> None:
    monetary, mmf = _source_frames()
    registry = build_route_admissibility_registry(
        monetary_route_bridge=monetary,
        mmf_route_split_context=mmf,
    )

    markdown = render_route_admissibility_registry_markdown(registry)

    assert "TDC Route Admissibility Registry" in markdown
    assert "quarterless source-owned guardrail" in markdown
    assert "Current-demand eligible rows: `0`" in markdown
    assert "ON-RRP boundary rows: `4`" in markdown
