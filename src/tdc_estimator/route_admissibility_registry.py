from __future__ import annotations

from pathlib import Path

import pandas as pd


ROUTE_ADMISSIBILITY_REGISTRY_FIELDS = [
    "route_rule_id",
    "route_id",
    "route_label",
    "preferred_guardrail_label",
    "source_artifact",
    "source_family",
    "source_status",
    "observation_granularity",
    "holder_vehicle_observed",
    "ultimate_investor_observed",
    "debited_claim_type",
    "debited_claim_observed",
    "funding_route_observed",
    "payment_route_observed",
    "m1_scope",
    "m2_scope",
    "deposit_pass_through_scope",
    "tdc_admissibility",
    "ratewall_current_demand_gate",
    "current_demand_eligible",
    "canonical_tdc_math_change",
    "onrrp_boundary_status",
    "onrrp_counterparty_scope",
    "onrrp_boundary_source_url",
    "onrrp_boundary_blocker",
    "evidence_required_to_pass",
    "exact_blocker",
    "source_url",
    "series_id",
    "first_observed_quarter",
    "latest_observed_quarter",
    "notes",
]


SOURCE_METADATA = {
    "h6_monetary_aggregate": {
        "source_url": "https://www.federalreserve.gov/releases/h6/current/default.htm",
        "series_id": "H.6 retail money market funds",
    },
    "tdcest_mmf_rrp_adjustment": {
        "source_url": (
            "https://www.federalreserve.gov/monetarypolicy/"
            "overnight-reverse-repurchase-agreements.htm"
        ),
        "series_id": "Fed overnight reverse repurchase agreements; TDC-EST MMF RRP adjustment",
    },
    "z1_holder_absorption": {
        "source_url": "https://www.federalreserve.gov/releases/z1/preview/html/f210.htm",
        "series_id": "Z.1 F.210 Treasury securities by holder sector",
    },
    "target_route_contract": {
        "source_url": "",
        "series_id": "TDC-EST target route placeholder",
    },
    "sec_nmfp_fund_type_portfolio_context": {
        "source_url": "https://www.sec.gov/data-research/sec-markets-data/dera-form-n-mfp-data-sets",
        "series_id": "SEC Form N-MFP fund retail flag and portfolio holdings",
    },
}


ROUTE_RULES = {
    "retail_mmf_m2_non_deposit_scope": {
        "preferred_guardrail_label": "retail_mmf_m2_non_deposit_scope",
        "observation_granularity": "aggregate_sector",
        "holder_vehicle_observed": "retail_mmf_fund",
        "ultimate_investor_observed": "false",
        "debited_claim_type": "mmf_share_claim",
        "debited_claim_observed": "false",
        "funding_route_observed": "sector_aggregate_only",
        "payment_route_observed": "not_observed",
        "tdc_admissibility": "context_only",
        "ratewall_current_demand_gate": "fail_noncurrent_claim",
        "onrrp_boundary_status": "not_onrrp_route",
        "onrrp_counterparty_scope": "not_applicable",
        "onrrp_boundary_source_url": "",
        "onrrp_boundary_blocker": "not_applicable",
        "evidence_required_to_pass": "direct_bank_deposit_debit_or_domestic_deposit_disbursement_source_required",
    },
    "mmf_onrrp_runoff_non_m2_plumbing": {
        "preferred_guardrail_label": "mmf_onrrp_tsy_reallocation",
        "observation_granularity": "fed_liability_route",
        "holder_vehicle_observed": "z1_mmf_aggregate",
        "ultimate_investor_observed": "false",
        "debited_claim_type": "fed_rrp_liability",
        "debited_claim_observed": "true",
        "funding_route_observed": "fed_rrp_runoff_observed",
        "payment_route_observed": "not_observed",
        "tdc_admissibility": "named_plumbing_adjustment",
        "ratewall_current_demand_gate": "fail_noncurrent_claim",
        "onrrp_boundary_status": "nyfed_fed_liability_counterparty_type_context",
        "onrrp_counterparty_scope": "mmf_counterparty_aggregate",
        "onrrp_boundary_source_url": "https://www.newyorkfed.org/markets/rrp_counterparties",
        "onrrp_boundary_blocker": "counterparty_type_does_not_identify_treasury_purchase_or_final_deposit_recipient",
        "evidence_required_to_pass": "entity_linked_onrrp_to_treasury_purchase_and_deposit_recipient_source_required",
    },
    "z1_domestic_nonbank_mixed_unknown_m2_scope": {
        "preferred_guardrail_label": "mixed_domestic_nonbank_absorption_context",
        "observation_granularity": "aggregate_sector",
        "holder_vehicle_observed": "z1_domestic_nonbank_aggregate",
        "ultimate_investor_observed": "false",
        "debited_claim_type": "mixed_unknown",
        "debited_claim_observed": "false",
        "funding_route_observed": "mixed_unknown",
        "payment_route_observed": "mixed_unknown",
        "tdc_admissibility": "context_only",
        "ratewall_current_demand_gate": "fail_mixed_unknown",
        "onrrp_boundary_status": "not_onrrp_route",
        "onrrp_counterparty_scope": "not_applicable",
        "onrrp_boundary_source_url": "",
        "onrrp_boundary_blocker": "not_applicable",
        "evidence_required_to_pass": "source_backed_debited_claim_and_payment_route_split_required",
    },
    "z1_mmf_plumbing_mixed_retail_institutional_onrrp_scope": {
        "preferred_guardrail_label": "mixed_mmf_absorption_context",
        "observation_granularity": "aggregate_sector",
        "holder_vehicle_observed": "z1_mmf_aggregate",
        "ultimate_investor_observed": "false",
        "debited_claim_type": "mixed_unknown",
        "debited_claim_observed": "false",
        "funding_route_observed": "mixed_unknown",
        "payment_route_observed": "not_observed",
        "tdc_admissibility": "context_only",
        "ratewall_current_demand_gate": "fail_mixed_unknown",
        "onrrp_boundary_status": "mixed_mmf_onrrp_boundary_unresolved",
        "onrrp_counterparty_scope": "mixed_retail_institutional_and_onrrp_mmf_scope",
        "onrrp_boundary_source_url": "https://www.newyorkfed.org/markets/rrp_counterparties",
        "onrrp_boundary_blocker": "aggregate_mmf_route_does_not_identify_retail_institutional_or_final_deposit_route",
        "evidence_required_to_pass": "retail_institutional_onrrp_and_final_investor_route_split_required",
    },
    "z1_dealer_repo_bridge_non_m2_or_unknown_scope": {
        "preferred_guardrail_label": "dealer_repo_absorption_context",
        "observation_granularity": "aggregate_sector",
        "holder_vehicle_observed": "z1_dealer_repo",
        "ultimate_investor_observed": "false",
        "debited_claim_type": "repo_claim",
        "debited_claim_observed": "false",
        "funding_route_observed": "sector_aggregate_only",
        "payment_route_observed": "not_observed",
        "tdc_admissibility": "context_only",
        "ratewall_current_demand_gate": "fail_noncurrent_claim",
        "onrrp_boundary_status": "not_onrrp_route",
        "onrrp_counterparty_scope": "not_applicable",
        "onrrp_boundary_source_url": "",
        "onrrp_boundary_blocker": "not_applicable",
        "evidence_required_to_pass": "direct_deposit_debit_source_required",
    },
    "z1_other_financial_non_m2_scope": {
        "preferred_guardrail_label": "nondeposit_claim_absorption_context",
        "observation_granularity": "aggregate_sector",
        "holder_vehicle_observed": "z1_other_financial",
        "ultimate_investor_observed": "false",
        "debited_claim_type": "mixed_unknown",
        "debited_claim_observed": "false",
        "funding_route_observed": "sector_aggregate_only",
        "payment_route_observed": "not_observed",
        "tdc_admissibility": "context_only",
        "ratewall_current_demand_gate": "fail_noncurrent_claim",
        "onrrp_boundary_status": "not_onrrp_route",
        "onrrp_counterparty_scope": "not_applicable",
        "onrrp_boundary_source_url": "",
        "onrrp_boundary_blocker": "not_applicable",
        "evidence_required_to_pass": "direct_deposit_debit_source_required",
    },
    "institutional_mmf_non_m2_target_not_split": {
        "preferred_guardrail_label": "institutional_mmf_target_route_blocked",
        "observation_granularity": "synthetic_target_placeholder",
        "holder_vehicle_observed": "synthetic_target_placeholder",
        "ultimate_investor_observed": "false",
        "debited_claim_type": "not_observed",
        "debited_claim_observed": "false",
        "funding_route_observed": "not_observed",
        "payment_route_observed": "not_observed",
        "tdc_admissibility": "target_contract_blocked",
        "ratewall_current_demand_gate": "fail_not_observed",
        "onrrp_boundary_status": "not_onrrp_route",
        "onrrp_counterparty_scope": "not_applicable",
        "onrrp_boundary_source_url": "",
        "onrrp_boundary_blocker": "not_applicable",
        "evidence_required_to_pass": "source_backed_institutional_mmf_route_split_required",
    },
    "retail_mmf_treasury_holdings_context": {
        "preferred_guardrail_label": "retail_mmf_treasury_portfolio_context",
        "observation_granularity": "fund_scope_portfolio",
        "holder_vehicle_observed": "retail_mmf_fund",
        "ultimate_investor_observed": "false",
        "debited_claim_type": "mmf_share_claim",
        "debited_claim_observed": "false",
        "funding_route_observed": "portfolio_holdings_only",
        "payment_route_observed": "not_observed",
        "tdc_admissibility": "context_only",
        "ratewall_current_demand_gate": "fail_investor_type_only",
        "onrrp_boundary_status": "not_onrrp_route",
        "onrrp_counterparty_scope": "not_applicable",
        "onrrp_boundary_source_url": "",
        "onrrp_boundary_blocker": "not_applicable",
        "evidence_required_to_pass": "final_investor_current_demand_split_required",
    },
    "retail_mmf_onrrp_plumbing_context": {
        "preferred_guardrail_label": "retail_mmf_onrrp_plumbing_context",
        "observation_granularity": "fund_scope_portfolio",
        "holder_vehicle_observed": "retail_mmf_fund",
        "ultimate_investor_observed": "false",
        "debited_claim_type": "fed_rrp_liability",
        "debited_claim_observed": "true",
        "funding_route_observed": "fed_rrp_runoff_observed",
        "payment_route_observed": "not_observed",
        "tdc_admissibility": "context_only",
        "ratewall_current_demand_gate": "fail_noncurrent_claim",
        "onrrp_boundary_status": "sec_nmfp_fed_onrrp_portfolio_context",
        "onrrp_counterparty_scope": "retail_mmf_fund_scope",
        "onrrp_boundary_source_url": "https://www.sec.gov/data-research/sec-markets-data/dera-form-n-mfp-data-sets",
        "onrrp_boundary_blocker": "fund_scope_and_onrrp_holding_do_not_identify_final_investor_or_deposit_recipient",
        "evidence_required_to_pass": "entity_linked_onrrp_to_treasury_purchase_and_deposit_recipient_source_required",
    },
    "institutional_or_nonretail_mmf_treasury_holdings_context": {
        "preferred_guardrail_label": "institutional_mmf_treasury_portfolio_context",
        "observation_granularity": "fund_scope_portfolio",
        "holder_vehicle_observed": "institutional_or_nonretail_mmf_fund",
        "ultimate_investor_observed": "false",
        "debited_claim_type": "mmf_share_claim",
        "debited_claim_observed": "false",
        "funding_route_observed": "portfolio_holdings_only",
        "payment_route_observed": "not_observed",
        "tdc_admissibility": "context_only",
        "ratewall_current_demand_gate": "fail_investor_type_only",
        "onrrp_boundary_status": "not_onrrp_route",
        "onrrp_counterparty_scope": "not_applicable",
        "onrrp_boundary_source_url": "",
        "onrrp_boundary_blocker": "not_applicable",
        "evidence_required_to_pass": "final_investor_current_demand_split_required",
    },
    "institutional_or_nonretail_mmf_onrrp_plumbing_context": {
        "preferred_guardrail_label": "institutional_mmf_onrrp_plumbing_context",
        "observation_granularity": "fund_scope_portfolio",
        "holder_vehicle_observed": "institutional_or_nonretail_mmf_fund",
        "ultimate_investor_observed": "false",
        "debited_claim_type": "fed_rrp_liability",
        "debited_claim_observed": "true",
        "funding_route_observed": "fed_rrp_runoff_observed",
        "payment_route_observed": "not_observed",
        "tdc_admissibility": "context_only",
        "ratewall_current_demand_gate": "fail_noncurrent_claim",
        "onrrp_boundary_status": "sec_nmfp_fed_onrrp_portfolio_context",
        "onrrp_counterparty_scope": "institutional_or_nonretail_mmf_fund_scope",
        "onrrp_boundary_source_url": "https://www.sec.gov/data-research/sec-markets-data/dera-form-n-mfp-data-sets",
        "onrrp_boundary_blocker": "fund_scope_and_onrrp_holding_do_not_identify_final_investor_or_deposit_recipient",
        "evidence_required_to_pass": "entity_linked_onrrp_to_treasury_purchase_and_deposit_recipient_source_required",
    },
}


def _first_nonblank(values: pd.Series, default: str = "") -> str:
    for value in values:
        if pd.notna(value) and str(value) != "":
            text = str(value)
            if text in {"True", "False"}:
                return text.lower()
            return text
    return default


def _quarter_bounds(frame: pd.DataFrame) -> tuple[str, str]:
    if "quarter" not in frame.columns or frame.empty:
        return "", ""
    quarters = sorted(str(value) for value in frame["quarter"] if str(value))
    if not quarters:
        return "", ""
    return quarters[0], quarters[-1]


def _route_summaries(frame: pd.DataFrame, *, source_artifact: str) -> dict[str, dict[str, str]]:
    summaries: dict[str, dict[str, str]] = {}
    if frame.empty or "route_id" not in frame.columns:
        return summaries
    for route_id, group in frame.groupby("route_id", sort=True):
        first, latest = _quarter_bounds(group)
        summaries[str(route_id)] = {
            "route_id": str(route_id),
            "route_label": _first_nonblank(group.get("route_label", pd.Series(dtype=str))),
            "source_artifact": source_artifact,
            "source_family": _first_nonblank(group.get("source_family", pd.Series(dtype=str))),
            "source_status": _first_nonblank(group.get("source_status", pd.Series(dtype=str))),
            "m1_scope": _first_nonblank(group.get("m1_scope", pd.Series(dtype=str))),
            "m2_scope": _first_nonblank(group.get("m2_scope", pd.Series(dtype=str))),
            "deposit_pass_through_scope": _first_nonblank(
                group.get("deposit_pass_through_scope", pd.Series(dtype=str))
            ),
            "current_demand_eligible": _first_nonblank(
                group.get("current_demand_eligible", pd.Series(dtype=str)), "false"
            ),
            "canonical_tdc_math_change": _first_nonblank(
                group.get("canonical_tdc_math_change", pd.Series(dtype=str)), "false"
            ),
            "exact_blocker": _first_nonblank(group.get("exact_blocker", pd.Series(dtype=str))),
            "first_observed_quarter": first,
            "latest_observed_quarter": latest,
            "notes": _first_nonblank(group.get("notes", pd.Series(dtype=str))),
        }
    return summaries


def build_route_admissibility_registry(
    *,
    monetary_route_bridge: pd.DataFrame,
    mmf_route_split_context: pd.DataFrame,
) -> pd.DataFrame:
    """Build the quarterless route admissibility registry.

    The amount-bearing bridge/context tables remain the source for quarterly
    values. This registry is a route-rule guardrail that records what the
    sources actually observe and keeps RateWall current-demand use fail-closed.
    """

    summaries = {}
    summaries.update(
        _route_summaries(
            monetary_route_bridge,
            source_artifact="tdc_domestic_nonbank_monetary_route_bridge.csv",
        )
    )
    summaries.update(
        _route_summaries(
            mmf_route_split_context,
            source_artifact="tdc_mmf_route_split_context.csv",
        )
    )
    rows: list[dict[str, str]] = []
    for route_id in sorted(summaries):
        summary = summaries[route_id]
        rule = ROUTE_RULES.get(route_id)
        if rule is None:
            rule = {
                "preferred_guardrail_label": "unknown_route_context_blocked",
                "observation_granularity": "aggregate_sector",
                "holder_vehicle_observed": "mixed_unknown",
                "ultimate_investor_observed": "false",
                "debited_claim_type": "not_observed",
                "debited_claim_observed": "false",
                "funding_route_observed": "not_observed",
                "payment_route_observed": "not_observed",
                "tdc_admissibility": "exclude",
                "ratewall_current_demand_gate": "fail_not_observed",
                "onrrp_boundary_status": "not_onrrp_route",
                "onrrp_counterparty_scope": "not_applicable",
                "onrrp_boundary_source_url": "",
                "onrrp_boundary_blocker": "not_applicable",
                "evidence_required_to_pass": "route_specific_source_contract_required",
            }
        metadata = SOURCE_METADATA.get(summary["source_family"], {})
        rows.append(
            {
                "route_rule_id": f"route_admissibility::{route_id}",
                "route_id": route_id,
                "route_label": summary["route_label"],
                "preferred_guardrail_label": rule["preferred_guardrail_label"],
                "source_artifact": summary["source_artifact"],
                "source_family": summary["source_family"],
                "source_status": summary["source_status"],
                "observation_granularity": rule["observation_granularity"],
                "holder_vehicle_observed": rule["holder_vehicle_observed"],
                "ultimate_investor_observed": rule["ultimate_investor_observed"],
                "debited_claim_type": rule["debited_claim_type"],
                "debited_claim_observed": rule["debited_claim_observed"],
                "funding_route_observed": rule["funding_route_observed"],
                "payment_route_observed": rule["payment_route_observed"],
                "m1_scope": summary["m1_scope"],
                "m2_scope": summary["m2_scope"],
                "deposit_pass_through_scope": summary["deposit_pass_through_scope"],
                "tdc_admissibility": rule["tdc_admissibility"],
                "ratewall_current_demand_gate": rule["ratewall_current_demand_gate"],
                "current_demand_eligible": summary["current_demand_eligible"],
                "canonical_tdc_math_change": summary["canonical_tdc_math_change"],
                "onrrp_boundary_status": rule["onrrp_boundary_status"],
                "onrrp_counterparty_scope": rule["onrrp_counterparty_scope"],
                "onrrp_boundary_source_url": rule["onrrp_boundary_source_url"],
                "onrrp_boundary_blocker": rule["onrrp_boundary_blocker"],
                "evidence_required_to_pass": rule["evidence_required_to_pass"],
                "exact_blocker": summary["exact_blocker"],
                "source_url": metadata.get("source_url", ""),
                "series_id": metadata.get("series_id", ""),
                "first_observed_quarter": summary["first_observed_quarter"],
                "latest_observed_quarter": summary["latest_observed_quarter"],
                "notes": summary["notes"],
            }
        )
    return pd.DataFrame(rows, columns=ROUTE_ADMISSIBILITY_REGISTRY_FIELDS)


def render_route_admissibility_registry_markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "# TDC Route Admissibility Registry\n\nNo rows were generated.\n"
    gate_counts = frame["ratewall_current_demand_gate"].value_counts().to_dict()
    onrrp_rows = int(frame["onrrp_boundary_status"].ne("not_onrrp_route").sum())
    return "\n".join(
        [
            "# TDC Route Admissibility Registry",
            "",
            f"- Route rules: `{len(frame)}`.",
            f"- Current-demand eligible rows: `{int(frame['current_demand_eligible'].eq('true').sum())}`.",
            f"- Canonical TDC math-change rows: `{int(frame['canonical_tdc_math_change'].eq('true').sum())}`.",
            f"- ON-RRP boundary rows: `{onrrp_rows}`.",
            f"- Current-demand gate counts: `{gate_counts}`.",
            "- Boundary: quarterless source-owned guardrail; amount-bearing route data remain in the bridge/context tables.",
            "- RateWall use: guardrail-only; this registry does not enter current-demand or canonical runtime math.",
            "",
        ]
    )


def write_route_admissibility_registry(
    *,
    monetary_route_bridge_path: Path | str,
    mmf_route_split_context_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str | None = None,
) -> tuple[Path, Path | None, pd.DataFrame]:
    monetary = pd.read_csv(monetary_route_bridge_path)
    mmf = pd.read_csv(mmf_route_split_context_path)
    frame = build_route_admissibility_registry(
        monetary_route_bridge=monetary,
        mmf_route_split_context=mmf,
    )
    target = Path(csv_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False)
    md_target: Path | None = None
    if markdown_path is not None:
        md_target = Path(markdown_path)
        md_target.parent.mkdir(parents=True, exist_ok=True)
        md_target.write_text(
            render_route_admissibility_registry_markdown(frame),
            encoding="utf-8",
        )
    return target, md_target, frame
