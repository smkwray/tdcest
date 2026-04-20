from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.monetary_control_overlap_audit import (
    build_monetary_control_overlap_audit,
    render_monetary_control_overlap_audit_markdown,
    write_monetary_control_overlap_audit,
)


def test_build_monetary_control_overlap_audit_grades_context_and_signed_terms() -> None:
    controls = pd.DataFrame(
        {
            "depository_target_minus_tier3_bank_only_flow_mil": [100.0],
            "commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil": [200.0],
            "bank_credit_additive_proxy_mil": [80.0],
            "non_treasury_bank_credit_proxy_mil": [50.0],
            "retail_mmf_rotation_proxy_mil": [-10.0],
            "rrp_drain_proxy_mil": [-5.0],
            "reserve_balance_liquidity_proxy_mil": [12.0],
            "fed_term_deposit_absorption_proxy_mil": [-3.0],
            "fed_other_deposits_absorption_proxy_mil": [4.0],
            "fed_liquidity_credit_support_proxy_mil": [7.0],
            "bank_borrowing_funding_proxy_mil": [9.0],
            "delta_commercial_bank_cash_assets_mil": [11.0],
            "delta_foreign_official_custody_treasuries_mil": [-20.0],
            "delta_foreign_related_treasury_agency_non_mbs_mil": [30.0],
            "delta_tga_weekly_level_mil": [15.0],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )

    audit = build_monetary_control_overlap_audit(controls)

    foreign_custody = audit.loc[audit["term_key"] == "delta_foreign_official_custody_treasuries_mil"].iloc[0]
    refined_bank = audit.loc[audit["term_key"] == "non_treasury_bank_credit_proxy_mil"].iloc[0]

    assert foreign_custody["stage_role"] == "context_only"
    assert foreign_custody["overlap_risk"] == "high"
    assert foreign_custody["recommendation"] == "keep_context_only_due_to_ladder_overlap"
    assert round(float(foreign_custody["latest_abs_share_of_depository_gap"]), 3) == 0.2
    assert refined_bank["stage_role"] == "refined_signed_control"
    assert refined_bank["recommendation"] == "keep_signed_preferred_bank_block"


def test_write_monetary_control_overlap_audit_outputs_files(tmp_path: Path) -> None:
    controls = pd.DataFrame(
        {
            "depository_target_minus_tier3_bank_only_flow_mil": [100.0],
            "commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil": [200.0],
            "bank_credit_additive_proxy_mil": [80.0],
            "non_treasury_bank_credit_proxy_mil": [50.0],
            "retail_mmf_rotation_proxy_mil": [-10.0],
            "rrp_drain_proxy_mil": [-5.0],
            "reserve_balance_liquidity_proxy_mil": [12.0],
            "fed_term_deposit_absorption_proxy_mil": [-3.0],
            "fed_other_deposits_absorption_proxy_mil": [4.0],
            "fed_liquidity_credit_support_proxy_mil": [7.0],
            "bank_borrowing_funding_proxy_mil": [9.0],
            "delta_commercial_bank_cash_assets_mil": [11.0],
            "delta_foreign_official_custody_treasuries_mil": [-20.0],
            "delta_foreign_related_treasury_agency_non_mbs_mil": [30.0],
            "delta_tga_weekly_level_mil": [15.0],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )

    csv_path = tmp_path / "overlap.csv"
    md_path = tmp_path / "overlap.md"
    _, _, audit = write_monetary_control_overlap_audit(
        monetary_stage1_controls=controls,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(audit)
    markdown = render_monetary_control_overlap_audit_markdown(audit)
    assert "Monetary Control Overlap Audit" in markdown
    assert "High-overlap context-only terms" in markdown
