from __future__ import annotations

from pathlib import Path

import pandas as pd


Z1_DOMESTIC_NONBANK_SECTOR_CONTEXT_FIELDS = [
    "date",
    "quarter",
    "sector_route_id",
    "sector_label",
    "z1_component_field",
    "z1_component_amount_bil",
    "sector_route_family",
    "holder_vehicle_observed",
    "debited_claim_type",
    "funding_route_observed",
    "payment_route_observed",
    "m1_scope",
    "m2_scope",
    "deposit_pass_through_scope",
    "tdc_admissibility",
    "ratewall_current_demand_gate",
    "current_demand_eligible",
    "canonical_tdc_math_change",
    "exact_blocker",
    "source_family",
    "source_url",
    "series_id",
    "source_status",
    "notes",
]


SECTOR_SPECS = [
    {
        "sector_route_id": "z1_mmf_sector_context",
        "sector_label": "Money market funds Treasury-security transactions.",
        "z1_component_field": "z1_component_money_market_funds_total_treasuries_bn",
        "sector_route_family": "z1_mmf_aggregate",
        "holder_vehicle_observed": "z1_mmf_aggregate",
        "debited_claim_type": "mmf_share_claim",
        "funding_route_observed": "sector_aggregate_only",
        "m2_scope": "mixed_retail_mmf_and_non_m2_mmf",
        "ratewall_current_demand_gate": "fail_mixed_unknown",
        "exact_blocker": "z1_mmf_sector_does_not_split_retail_institutional_onrrp_or_final_investor_route",
    },
    {
        "sector_route_id": "z1_security_brokers_dealers_sector_context",
        "sector_label": "Security brokers and dealers Treasury-security net transactions.",
        "z1_component_field": "z1_component_security_brokers_dealers_treasuries_net_bn",
        "sector_route_family": "z1_dealer_repo",
        "holder_vehicle_observed": "z1_dealer_repo",
        "debited_claim_type": "repo_claim",
        "funding_route_observed": "sector_aggregate_only",
        "m2_scope": "false_or_unknown",
        "ratewall_current_demand_gate": "fail_noncurrent_claim",
        "exact_blocker": "dealer_repo_sector_is_market_plumbing_not_deposit_recipient_route",
    },
    {
        "sector_route_id": "z1_gse_sector_context",
        "sector_label": "Government-sponsored enterprises Treasury-security transactions.",
        "z1_component_field": "z1_component_government_sponsored_enterprises_treasuries_bn",
        "sector_route_family": "z1_gse_plumbing",
        "holder_vehicle_observed": "z1_gse",
        "debited_claim_type": "agency_or_fed_liability_related_claim",
        "funding_route_observed": "sector_aggregate_only",
        "m2_scope": "false",
        "ratewall_current_demand_gate": "fail_noncurrent_claim",
        "exact_blocker": "gse_sector_does_not_identify_bank_deposit_debit_or_recipient_current_demand",
    },
    {
        "sector_route_id": "z1_mutual_funds_sector_context",
        "sector_label": "Mutual funds Treasury-security transactions.",
        "z1_component_field": "z1_component_mutual_funds_treasuries_bn",
        "sector_route_family": "z1_fund_share_claim",
        "holder_vehicle_observed": "z1_mutual_fund",
        "debited_claim_type": "mutual_fund_share_claim",
        "funding_route_observed": "sector_aggregate_only",
        "m2_scope": "false",
        "ratewall_current_demand_gate": "fail_noncurrent_claim",
        "exact_blocker": "mutual_fund_sector_does_not_identify_deposit_debit_or_final_current_demand",
    },
    {
        "sector_route_id": "z1_closed_end_funds_sector_context",
        "sector_label": "Closed-end funds Treasury-security transactions.",
        "z1_component_field": "z1_component_closed_end_funds_treasuries_bn",
        "sector_route_family": "z1_fund_share_claim",
        "holder_vehicle_observed": "z1_closed_end_fund",
        "debited_claim_type": "mutual_fund_share_claim",
        "funding_route_observed": "sector_aggregate_only",
        "m2_scope": "false",
        "ratewall_current_demand_gate": "fail_noncurrent_claim",
        "exact_blocker": "closed_end_fund_sector_does_not_identify_deposit_debit_or_final_current_demand",
    },
    {
        "sector_route_id": "z1_exchange_traded_funds_sector_context",
        "sector_label": "Exchange-traded funds Treasury-security transactions.",
        "z1_component_field": "z1_component_exchange_traded_funds_treasuries_bn",
        "sector_route_family": "z1_fund_share_claim",
        "holder_vehicle_observed": "z1_exchange_traded_fund",
        "debited_claim_type": "mutual_fund_share_claim",
        "funding_route_observed": "sector_aggregate_only",
        "m2_scope": "false",
        "ratewall_current_demand_gate": "fail_noncurrent_claim",
        "exact_blocker": "etf_sector_does_not_identify_deposit_debit_or_final_current_demand",
    },
    {
        "sector_route_id": "z1_insurance_pensions_sector_context",
        "sector_label": "Insurance and pension funds Treasury-security transactions.",
        "z1_component_field": "z1_component_insurance_pensions_total_treasuries_bn",
        "sector_route_family": "z1_insurance_pension_claim",
        "holder_vehicle_observed": "z1_insurance_pensions",
        "debited_claim_type": "pension_insurance_claim",
        "funding_route_observed": "sector_aggregate_only",
        "m2_scope": "false",
        "ratewall_current_demand_gate": "fail_noncurrent_claim",
        "exact_blocker": "insurance_pension_sector_does_not_identify_deposit_debit_or_current_demand_route",
    },
    {
        "sector_route_id": "z1_households_nonprofits_residual_sector_context",
        "sector_label": "Households and nonprofits residual Treasury-security transactions.",
        "z1_component_field": "z1_component_households_nonprofits_treasuries_residual_holder_bn",
        "sector_route_family": "z1_household_nonprofit_residual",
        "holder_vehicle_observed": "z1_households_nonprofits_residual",
        "debited_claim_type": "mixed_unknown",
        "funding_route_observed": "mixed_unknown",
        "m2_scope": "unknown_or_mixed",
        "ratewall_current_demand_gate": "fail_mixed_unknown",
        "exact_blocker": "household_nonprofit_residual_does_not_identify_debited_claim_or_payment_route",
    },
    {
        "sector_route_id": "z1_nonfinancial_corporate_sector_context",
        "sector_label": "Nonfinancial corporate Treasury-security transactions.",
        "z1_component_field": "z1_component_nonfinancial_corporate_treasuries_bn",
        "sector_route_family": "z1_nonfinancial_business",
        "holder_vehicle_observed": "z1_nonfinancial_corporate",
        "debited_claim_type": "mixed_unknown",
        "funding_route_observed": "mixed_unknown",
        "m2_scope": "unknown_or_mixed",
        "ratewall_current_demand_gate": "fail_mixed_unknown",
        "exact_blocker": "nonfinancial_corporate_sector_does_not_identify_debited_claim_or_current_demand_route",
    },
    {
        "sector_route_id": "z1_nonfinancial_noncorporate_sector_context",
        "sector_label": "Nonfinancial noncorporate Treasury-security transactions.",
        "z1_component_field": "z1_component_nonfinancial_noncorporate_us_government_securities_bn",
        "sector_route_family": "z1_nonfinancial_business",
        "holder_vehicle_observed": "z1_nonfinancial_noncorporate",
        "debited_claim_type": "mixed_unknown",
        "funding_route_observed": "mixed_unknown",
        "m2_scope": "unknown_or_mixed",
        "ratewall_current_demand_gate": "fail_mixed_unknown",
        "exact_blocker": "nonfinancial_noncorporate_sector_does_not_identify_debited_claim_or_current_demand_route",
    },
    {
        "sector_route_id": "z1_state_local_governments_sector_context",
        "sector_label": "State and local governments Treasury-security transactions excluding SLGS.",
        "z1_component_field": "z1_component_state_local_governments_treasuries_ex_slgs_bn",
        "sector_route_family": "z1_public_nonfederal",
        "holder_vehicle_observed": "z1_state_local_government",
        "debited_claim_type": "mixed_unknown",
        "funding_route_observed": "sector_aggregate_only",
        "m2_scope": "false",
        "ratewall_current_demand_gate": "fail_noncurrent_claim",
        "exact_blocker": "state_local_government_sector_is_not_deposit_user_current_demand_route",
    },
    {
        "sector_route_id": "z1_abs_issuers_sector_context",
        "sector_label": "Asset-backed securities issuers Treasury-security transactions.",
        "z1_component_field": "z1_component_asset_backed_securities_issuers_treasuries_bn",
        "sector_route_family": "z1_structured_finance",
        "holder_vehicle_observed": "z1_abs_issuer",
        "debited_claim_type": "repo_claim",
        "funding_route_observed": "sector_aggregate_only",
        "m2_scope": "false",
        "ratewall_current_demand_gate": "fail_noncurrent_claim",
        "exact_blocker": "abs_issuer_sector_does_not_identify_deposit_debit_or_final_current_demand",
    },
    {
        "sector_route_id": "z1_holding_companies_sector_context",
        "sector_label": "Holding companies Treasury-security transactions.",
        "z1_component_field": "z1_component_holding_companies_treasuries_bn",
        "sector_route_family": "z1_other_financial",
        "holder_vehicle_observed": "z1_holding_company",
        "debited_claim_type": "mixed_unknown",
        "funding_route_observed": "sector_aggregate_only",
        "m2_scope": "false",
        "ratewall_current_demand_gate": "fail_noncurrent_claim",
        "exact_blocker": "holding_company_sector_does_not_identify_deposit_debit_or_current_demand_route",
    },
    {
        "sector_route_id": "z1_central_clearing_counterparties_sector_context",
        "sector_label": "Central clearing counterparties Treasury-security transactions.",
        "z1_component_field": "z1_component_central_clearing_counterparties_treasuries_bn",
        "sector_route_family": "z1_market_plumbing",
        "holder_vehicle_observed": "z1_central_clearing_counterparty",
        "debited_claim_type": "repo_claim",
        "funding_route_observed": "sector_aggregate_only",
        "m2_scope": "false",
        "ratewall_current_demand_gate": "fail_noncurrent_claim",
        "exact_blocker": "central_clearing_counterparty_sector_is_market_plumbing_not_current_demand_route",
    },
]


def _quarter_from_date(value: object) -> str:
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return ""
    return f"{timestamp.year}Q{((timestamp.month - 1) // 3) + 1}"


def _format_number(value: object) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def build_z1_domestic_nonbank_sector_context(
    z1_holder_absorption: pd.DataFrame,
) -> pd.DataFrame:
    """Build a Z.1 sector context panel for domestic nonbank Treasury routes."""

    if z1_holder_absorption.empty or "quarter" not in z1_holder_absorption.columns:
        return pd.DataFrame(columns=Z1_DOMESTIC_NONBANK_SECTOR_CONTEXT_FIELDS)
    frame = z1_holder_absorption.copy()
    frame["date"] = pd.to_datetime(frame["quarter"], errors="coerce")
    frame = frame.loc[frame["date"].notna()].copy()
    frame["quarter_label"] = frame["date"].map(_quarter_from_date)
    rows: list[dict[str, str]] = []
    for _, source_row in frame.sort_values("date").iterrows():
        for spec in SECTOR_SPECS:
            field = spec["z1_component_field"]
            if field not in source_row.index:
                continue
            amount = pd.to_numeric(source_row[field], errors="coerce")
            if pd.isna(amount):
                continue
            rows.append(
                {
                    "date": pd.Timestamp(source_row["date"]).strftime("%Y-%m-%d"),
                    "quarter": source_row["quarter_label"],
                    "sector_route_id": spec["sector_route_id"],
                    "sector_label": spec["sector_label"],
                    "z1_component_field": field,
                    "z1_component_amount_bil": _format_number(amount),
                    "sector_route_family": spec["sector_route_family"],
                    "holder_vehicle_observed": spec["holder_vehicle_observed"],
                    "debited_claim_type": spec["debited_claim_type"],
                    "funding_route_observed": spec["funding_route_observed"],
                    "payment_route_observed": "not_observed",
                    "m1_scope": "false",
                    "m2_scope": spec["m2_scope"],
                    "deposit_pass_through_scope": (
                        "unknown_or_mixed"
                        if spec["m2_scope"] == "unknown_or_mixed"
                        else "false"
                    ),
                    "tdc_admissibility": "context_only",
                    "ratewall_current_demand_gate": spec[
                        "ratewall_current_demand_gate"
                    ],
                    "current_demand_eligible": "false",
                    "canonical_tdc_math_change": "false",
                    "exact_blocker": spec["exact_blocker"],
                    "source_family": "z1_sector_treasury_holder_transactions",
                    "source_url": "https://www.federalreserve.gov/releases/z1/preview/html/f210.htm",
                    "series_id": field,
                    "source_status": "source_backed_z1_sector_context",
                    "notes": (
                        "Z.1 sector Treasury-security transaction context only; "
                        "does not identify debited claim, payment route, final "
                        "investor spending, or deposit-recipient current demand."
                    ),
                }
            )
    return pd.DataFrame(rows, columns=Z1_DOMESTIC_NONBANK_SECTOR_CONTEXT_FIELDS)


def render_z1_domestic_nonbank_sector_context_markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "# Z.1 Domestic Nonbank Sector Context\n\nNo rows were generated.\n"
    latest_quarter = frame["quarter"].dropna().iloc[-1]
    latest = frame.loc[frame["quarter"].eq(latest_quarter)]
    families = sorted(frame["sector_route_family"].dropna().unique())
    return "\n".join(
        [
            "# Z.1 Domestic Nonbank Sector Context",
            "",
            f"- Quarter range: `{frame['quarter'].dropna().iloc[0]}` to `{latest_quarter}`.",
            f"- Sector route rows: `{len(frame)}`.",
            f"- Latest-quarter sector route rows: `{len(latest)}`.",
            f"- Sector route families: `{'; '.join(families)}`.",
            "- Boundary: Z.1 sector holder context only; no row identifies a deposit debit, final investor, or current-demand payment route.",
            "- RateWall use: guardrail/context only, not current-demand or canonical TDC math.",
            "",
        ]
    )


def write_z1_domestic_nonbank_sector_context(
    *,
    z1_holder_absorption_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str | None = None,
) -> tuple[Path, Path | None, pd.DataFrame]:
    frame = build_z1_domestic_nonbank_sector_context(
        pd.read_csv(z1_holder_absorption_path)
    )
    target = Path(csv_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False)
    md_target: Path | None = None
    if markdown_path is not None:
        md_target = Path(markdown_path)
        md_target.parent.mkdir(parents=True, exist_ok=True)
        md_target.write_text(
            render_z1_domestic_nonbank_sector_context_markdown(frame),
            encoding="utf-8",
        )
    return target, md_target, frame
