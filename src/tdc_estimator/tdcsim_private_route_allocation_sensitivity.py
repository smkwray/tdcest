from __future__ import annotations

from pathlib import Path

import pandas as pd


CONTRACT_VERSION = "tdc_tdcsim_private_route_allocation_sensitivity_v1"

TDCSIM_PRIVATE_ROUTE_ALLOCATION_SENSITIVITY_FIELDS = [
    "allocation_row_id",
    "owner_project",
    "contract_version",
    "ref_quarter",
    "object_family",
    "lookback_window_quarters",
    "native_source_frequency",
    "native_source_unit",
    "unit_conversion_status",
    "tdcsim_holder_bucket",
    "tdcsim_private_alignment_status",
    "route_class",
    "route_subclass",
    "source_sector_route_ids",
    "fund_scope",
    "raw_amount_bil",
    "denominator_bil",
    "share_lambda_0",
    "share_lambda_0_5",
    "share_lambda_1",
    "share_low",
    "share_central",
    "share_high",
    "evidence_tier",
    "measurement_stage",
    "mapping_burden",
    "assumption_status",
    "sensitivity_parameter",
    "sensitivity_label",
    "z1_table",
    "z1_series_ids",
    "sec_nmfp_retail_treasury_share",
    "sec_nmfp_institutional_treasury_share",
    "sec_nmfp_onrrp_memo_share",
    "onrrp_stock_bil",
    "onrrp_treatment",
    "mmf_split_status",
    "m1_scope",
    "m2_scope",
    "deposit_pass_through_scope",
    "holder_vehicle_observed",
    "debited_claim_type_observed",
    "payment_route_observed",
    "ultimate_investor_observed",
    "current_demand_eligible",
    "canonical_tdc_math_change",
    "source_inputs",
    "source_backed_fields",
    "assumption_fields",
    "allocation_status",
    "source_backed_private_bucket_split_status",
    "allowed_use",
    "blocked_use",
    "exact_blocker",
    "evidence_mode_enabled",
    "canonical_ratio_entry",
    "enters_main_ratio",
    "holder_allocation_enabled",
    "incidence_claim_enabled",
    "welfare_claim_enabled",
    "tax_output_enabled",
    "mpc_output_enabled",
    "prior_narrowing_allowed",
    "pricing_output_enabled",
]


DIRECT_FLOW_COLUMNS = [
    "z1_component_households_nonprofits_treasuries_residual_holder_bn",
    "z1_component_nonfinancial_corporate_treasuries_bn",
    "z1_component_nonfinancial_noncorporate_us_government_securities_bn",
]

NONDEPOSIT_FLOW_COLUMNS = [
    "z1_component_state_local_governments_treasuries_ex_slgs_bn",
    "z1_component_security_brokers_dealers_treasuries_net_bn",
    "z1_component_government_sponsored_enterprises_treasuries_bn",
    "z1_component_insurance_pensions_total_treasuries_bn",
    "z1_component_mutual_funds_treasuries_bn",
    "z1_component_closed_end_funds_treasuries_bn",
    "z1_component_exchange_traded_funds_treasuries_bn",
    "z1_component_asset_backed_securities_issuers_treasuries_bn",
    "z1_component_holding_companies_treasuries_bn",
    "z1_component_central_clearing_counterparties_treasuries_bn",
]

MMF_FLOW_COLUMNS = ["z1_component_money_market_funds_total_treasuries_bn"]

DIRECT_STOCK_SECTORS = ["households_residual", "nonfinancial_corporates"]

NONDEPOSIT_STOCK_SECTORS = [
    "state_local_governments",
    "dealers",
    "insurers",
    "mutual_funds_etfs",
    "other_financial",
    "pensions",
]

MMF_STOCK_SECTORS = ["money_market_funds"]


def _quarter_from_date(value: object) -> str:
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return ""
    return f"{timestamp.year}Q{((timestamp.month - 1) // 3) + 1}"


def _format_number(value: object) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(0.0, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def _positive_sum(frame: pd.DataFrame, columns: list[str]) -> float:
    if frame.empty:
        return 0.0
    total = 0.0
    for column in columns:
        total += float(_numeric(frame, column).clip(lower=0.0).sum())
    return total


def _mmf_split_by_quarter(mmf_context: pd.DataFrame) -> pd.DataFrame:
    if mmf_context.empty:
        return pd.DataFrame(
            columns=[
                "ref_quarter",
                "sec_nmfp_retail_treasury_share",
                "sec_nmfp_institutional_treasury_share",
                "sec_nmfp_onrrp_memo_share",
                "onrrp_stock_bil",
                "mmf_split_status",
            ]
        )
    frame = mmf_context.copy()
    frame["treasury_total_bil"] = _numeric(frame, "treasury_total_bil")
    frame["fed_onrrp_bil"] = _numeric(frame, "fed_onrrp_bil")
    treasury = frame.loc[
        frame["route_id"].astype(str).str.contains("treasury_holdings_context")
    ].copy()
    onrrp = frame.loc[
        frame["route_id"].astype(str).str.contains("onrrp_plumbing_context")
    ].copy()

    rows: list[dict[str, object]] = []
    for quarter, group in treasury.groupby("quarter"):
        retail = float(
            group.loc[group["fund_scope"].eq("retail_mmf"), "treasury_total_bil"].sum()
        )
        institutional = float(
            group.loc[
                group["fund_scope"].eq("institutional_or_nonretail_mmf"),
                "treasury_total_bil",
            ].sum()
        )
        treasury_total = retail + institutional
        onrrp_total = float(onrrp.loc[onrrp["quarter"].eq(quarter), "fed_onrrp_bil"].sum())
        if treasury_total <= 0:
            retail_share = 0.0
            institutional_share = 0.0
            split_status = "sec_nmfp_treasury_split_unavailable"
        else:
            retail_share = retail / treasury_total
            institutional_share = institutional / treasury_total
            split_status = "z1_mmf_aggregate_replaced_by_sec_nmfp_treasury_split"
        memo_denominator = treasury_total + onrrp_total
        memo_share = onrrp_total / memo_denominator if memo_denominator > 0 else 0.0
        rows.append(
            {
                "ref_quarter": str(quarter),
                "sec_nmfp_retail_treasury_share": retail_share,
                "sec_nmfp_institutional_treasury_share": institutional_share,
                "sec_nmfp_onrrp_memo_share": memo_share,
                "onrrp_stock_bil": onrrp_total,
                "mmf_split_status": split_status,
            }
        )
    return pd.DataFrame(rows)


def _build_flow_amounts(z1_flow: pd.DataFrame) -> pd.DataFrame:
    if z1_flow.empty or "quarter" not in z1_flow.columns:
        return pd.DataFrame()
    frame = z1_flow.copy()
    frame["date"] = pd.to_datetime(frame["quarter"], errors="coerce")
    frame = frame.loc[frame["date"].notna()].sort_values("date").copy()
    rows: list[dict[str, object]] = []
    for position in range(len(frame)):
        window = frame.iloc[max(0, position - 3) : position + 1]
        if len(window) < 4:
            continue
        quarter = _quarter_from_date(frame.iloc[position]["date"])
        rows.append(
            {
                "ref_quarter": quarter,
                "object_family": "flow_absorption_trailing_4q",
                "lookback_window_quarters": 4,
                "native_source_frequency": "quarterly",
                "native_source_unit": "billions_usd_trailing_four_quarter_positive_absorption",
                "unit_conversion_status": "source_billions_no_conversion",
                "z1_table": "F.210",
                "direct_amount_bil": _positive_sum(window, DIRECT_FLOW_COLUMNS),
                "nondeposit_amount_bil": _positive_sum(
                    window, NONDEPOSIT_FLOW_COLUMNS
                ),
                "mmf_amount_bil": _positive_sum(window, MMF_FLOW_COLUMNS),
                "direct_source_ids": ";".join(DIRECT_FLOW_COLUMNS),
                "nondeposit_source_ids": ";".join(NONDEPOSIT_FLOW_COLUMNS),
                "mmf_source_ids": ";".join(MMF_FLOW_COLUMNS),
            }
        )
    return pd.DataFrame(rows)


def _build_stock_amounts(z1_stock: pd.DataFrame) -> pd.DataFrame:
    if z1_stock.empty:
        return pd.DataFrame()
    frame = z1_stock.copy()
    if {"date", "sector", "holdings"}.issubset(frame.columns):
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.loc[frame["date"].notna()].copy()
        frame["ref_quarter"] = frame["date"].map(_quarter_from_date)
        frame["holdings_bil"] = _numeric(frame, "holdings") / 1000.0
        grouped = (
            frame.groupby(["ref_quarter", "sector"], as_index=False)["holdings_bil"]
            .sum()
            .pivot(index="ref_quarter", columns="sector", values="holdings_bil")
            .fillna(0.0)
            .reset_index()
        )
    elif {"date", "series_key", "level"}.issubset(frame.columns):
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.loc[frame["date"].notna()].copy()
        frame["ref_quarter"] = frame["date"].map(_quarter_from_date)
        frame["level"] = _numeric(frame, "level")
        grouped = (
            frame.groupby(["ref_quarter", "series_key"], as_index=False)["level"]
            .sum()
            .pivot(index="ref_quarter", columns="series_key", values="level")
            .fillna(0.0)
            .reset_index()
        )
    else:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    for _, row in grouped.sort_values("ref_quarter").iterrows():
        direct = sum(float(row.get(sector, 0.0)) for sector in DIRECT_STOCK_SECTORS)
        nondeposit = sum(
            float(row.get(sector, 0.0)) for sector in NONDEPOSIT_STOCK_SECTORS
        )
        mmf = sum(float(row.get(sector, 0.0)) for sector in MMF_STOCK_SECTORS)
        rows.append(
            {
                "ref_quarter": row["ref_quarter"],
                "object_family": "stock_interest_quarter_end",
                "lookback_window_quarters": 1,
                "native_source_frequency": "quarterly_end_of_period",
                "native_source_unit": "billions_usd_quarter_end_stock",
                "unit_conversion_status": "source_millions_converted_to_billions",
                "z1_table": "L.210",
                "direct_amount_bil": max(direct, 0.0),
                "nondeposit_amount_bil": max(nondeposit, 0.0),
                "mmf_amount_bil": max(mmf, 0.0),
                "direct_source_ids": ";".join(DIRECT_STOCK_SECTORS),
                "nondeposit_source_ids": ";".join(NONDEPOSIT_STOCK_SECTORS),
                "mmf_source_ids": ";".join(MMF_STOCK_SECTORS),
            }
        )
    return pd.DataFrame(rows)


def _route_specs(amount_row: pd.Series) -> list[dict[str, object]]:
    direct = float(amount_row["direct_amount_bil"])
    nondeposit = float(amount_row["nondeposit_amount_bil"])
    mmf = float(amount_row["mmf_amount_bil"])
    denominator = direct + nondeposit + mmf
    if denominator <= 0:
        return []

    return [
        {
            "route_class": "deposit_funded_domestic_nonbank_possible",
            "route_subclass": "ambiguous_direct_real_sector_domestic_holders",
            "source_sector_route_ids": amount_row["direct_source_ids"],
            "fund_scope": "not_mmf",
            "raw_amount_bil": direct,
            "share_lambda_0": 0.0,
            "share_lambda_0_5": 0.5 * direct / denominator,
            "share_lambda_1": direct / denominator,
            "m1_scope": "unknown",
            "m2_scope": "unknown_or_mixed",
            "deposit_pass_through_scope": "unknown_or_mixed",
            "holder_vehicle_observed": "direct_domestic_nonbank_holder_vehicle",
            "debited_claim_type_observed": "not_observed",
            "payment_route_observed": "not_observed",
            "ultimate_investor_observed": "not_observed",
            "exact_blocker": (
                "z1_sector_absorption_does_not_identify_debited_bank_deposit_"
                "funding_route"
            ),
        },
        {
            "route_class": "non_deposit_funded_domestic_nonbank_ex_mmf",
            "route_subclass": (
                "portfolio_plumbing_plus_unassigned_ambiguous_direct_sectors"
            ),
            "source_sector_route_ids": amount_row["nondeposit_source_ids"],
            "fund_scope": "not_mmf",
            "raw_amount_bil": nondeposit,
            "share_lambda_0": (nondeposit + direct) / denominator,
            "share_lambda_0_5": (nondeposit + 0.5 * direct) / denominator,
            "share_lambda_1": nondeposit / denominator,
            "m1_scope": "false_or_unknown",
            "m2_scope": "false_or_unknown",
            "deposit_pass_through_scope": "false_or_unknown",
            "holder_vehicle_observed": "domestic_nonbank_financial_or_public_holder_vehicle",
            "debited_claim_type_observed": "not_observed",
            "payment_route_observed": "not_observed",
            "ultimate_investor_observed": "not_observed",
            "exact_blocker": (
                "z1_sector_absorption_identifies_holder_vehicle_not_funding_route"
            ),
        },
        {
            "route_class": "mmf_onrrp_like_intermediated",
            "route_subclass": "retail_and_institutional_mmf_treasury_holdings",
            "source_sector_route_ids": amount_row["mmf_source_ids"],
            "fund_scope": "retail_mmf;institutional_or_nonretail_mmf",
            "raw_amount_bil": mmf,
            "share_lambda_0": mmf / denominator,
            "share_lambda_0_5": mmf / denominator,
            "share_lambda_1": mmf / denominator,
            "m1_scope": "false",
            "m2_scope": "mixed_retail_mmf_and_non_m2_mmf",
            "deposit_pass_through_scope": "false",
            "holder_vehicle_observed": "mmf_holder_vehicle",
            "debited_claim_type_observed": "mmf_share_claim",
            "payment_route_observed": "not_observed",
            "ultimate_investor_observed": "not_observed",
            "exact_blocker": (
                "sec_nmfp_fund_scope_and_onrrp_holdings_do_not_identify_final_"
                "investor_or_deposit_recipient"
            ),
        },
    ]


def _base_row(
    *,
    amount_row: pd.Series,
    split_row: pd.Series,
    route: dict[str, object],
    source_inputs: str,
) -> dict[str, str]:
    denominator = (
        float(amount_row["direct_amount_bil"])
        + float(amount_row["nondeposit_amount_bil"])
        + float(amount_row["mmf_amount_bil"])
    )
    shares = [
        float(route["share_lambda_0"]),
        float(route["share_lambda_0_5"]),
        float(route["share_lambda_1"]),
    ]
    object_family = str(amount_row["object_family"])
    route_class = str(route["route_class"])
    return {
        "allocation_row_id": (
            f"tdcest_private_route_sensitivity::{amount_row['ref_quarter']}::"
            f"{object_family}::{route_class}"
        ),
        "owner_project": "tdcest",
        "contract_version": CONTRACT_VERSION,
        "ref_quarter": str(amount_row["ref_quarter"]),
        "object_family": object_family,
        "lookback_window_quarters": str(int(amount_row["lookback_window_quarters"])),
        "native_source_frequency": str(amount_row["native_source_frequency"]),
        "native_source_unit": str(amount_row["native_source_unit"]),
        "unit_conversion_status": str(amount_row["unit_conversion_status"]),
        "tdcsim_holder_bucket": "Private",
        "tdcsim_private_alignment_status": "included_private_like_proxy",
        "route_class": route_class,
        "route_subclass": str(route["route_subclass"]),
        "source_sector_route_ids": str(route["source_sector_route_ids"]),
        "fund_scope": str(route["fund_scope"]),
        "raw_amount_bil": _format_number(route["raw_amount_bil"]),
        "denominator_bil": _format_number(denominator),
        "share_lambda_0": _format_number(route["share_lambda_0"]),
        "share_lambda_0_5": _format_number(route["share_lambda_0_5"]),
        "share_lambda_1": _format_number(route["share_lambda_1"]),
        "share_low": _format_number(min(shares)),
        "share_central": _format_number(route["share_lambda_0_5"]),
        "share_high": _format_number(max(shares)),
        "evidence_tier": "bounded_proxy",
        "measurement_stage": (
            "holder_stock"
            if object_family == "stock_interest_quarter_end"
            else "holder_flow"
        ),
        "mapping_burden": "requires_unobserved_actor_split",
        "assumption_status": "bounded_assumption",
        "sensitivity_parameter": "lambda_direct_sector_deposit_funded_fraction",
        "sensitivity_label": "mechanical_midpoint_not_estimate",
        "z1_table": str(amount_row["z1_table"]),
        "z1_series_ids": str(route["source_sector_route_ids"]),
        "sec_nmfp_retail_treasury_share": _format_number(
            split_row["sec_nmfp_retail_treasury_share"]
        ),
        "sec_nmfp_institutional_treasury_share": _format_number(
            split_row["sec_nmfp_institutional_treasury_share"]
        ),
        "sec_nmfp_onrrp_memo_share": _format_number(
            split_row["sec_nmfp_onrrp_memo_share"]
        ),
        "onrrp_stock_bil": _format_number(split_row["onrrp_stock_bil"]),
        "onrrp_treatment": "memo_only_not_additive",
        "mmf_split_status": str(split_row["mmf_split_status"]),
        "m1_scope": str(route["m1_scope"]),
        "m2_scope": str(route["m2_scope"]),
        "deposit_pass_through_scope": str(route["deposit_pass_through_scope"]),
        "holder_vehicle_observed": str(route["holder_vehicle_observed"]),
        "debited_claim_type_observed": str(route["debited_claim_type_observed"]),
        "payment_route_observed": str(route["payment_route_observed"]),
        "ultimate_investor_observed": str(route["ultimate_investor_observed"]),
        "current_demand_eligible": "false",
        "canonical_tdc_math_change": "false",
        "source_inputs": source_inputs,
        "source_backed_fields": (
            "z1_holder_vehicle_amounts;sec_nmfp_retail_institutional_treasury_"
            "shares;sec_nmfp_onrrp_memo"
        ),
        "assumption_fields": (
            "lambda_direct_sector_deposit_funded_fraction;route_class_grouping"
        ),
        "allocation_status": "bounded_noncanonical_proxy",
        "source_backed_private_bucket_split_status": (
            "not_source_backed_private_bucket_split"
        ),
        "allowed_use": "tdcsim_ratewall_sensitivity_sidecar_context_only",
        "blocked_use": (
            "canonical_tdc_math;tdcsim_central_holder_allocation;ratewall_"
            "evidence_mode;pricing_incidence_welfare_tax_mpc_or_prior_narrowing"
        ),
        "exact_blocker": str(route["exact_blocker"]),
        "evidence_mode_enabled": "false",
        "canonical_ratio_entry": "false",
        "enters_main_ratio": "false",
        "holder_allocation_enabled": "false",
        "incidence_claim_enabled": "false",
        "welfare_claim_enabled": "false",
        "tax_output_enabled": "false",
        "mpc_output_enabled": "false",
        "prior_narrowing_allowed": "false",
        "pricing_output_enabled": "false",
    }


def build_tdcsim_private_route_allocation_sensitivity(
    *,
    z1_flow: pd.DataFrame,
    z1_stock: pd.DataFrame,
    mmf_route_split_context: pd.DataFrame,
    source_inputs: str = "",
) -> pd.DataFrame:
    """Build a bounded noncanonical route sensitivity for TDCSim Private.

    The table allocates included domestic-private-like Z.1 Treasury holder
    context into three route classes under lambda bands. It is a sensitivity
    surface only: it never turns Z.1 holder vehicles into a source-backed
    TDCSim Private funding-route split.
    """

    split = _mmf_split_by_quarter(mmf_route_split_context)
    amount_frames = [_build_stock_amounts(z1_stock), _build_flow_amounts(z1_flow)]
    amount_frames = [frame for frame in amount_frames if not frame.empty]
    if not amount_frames or split.empty:
        return pd.DataFrame(columns=TDCSIM_PRIVATE_ROUTE_ALLOCATION_SENSITIVITY_FIELDS)

    amounts = pd.concat(amount_frames, ignore_index=True)
    amounts = amounts.merge(split, on="ref_quarter", how="inner")

    rows: list[dict[str, str]] = []
    for _, amount_row in amounts.sort_values(["ref_quarter", "object_family"]).iterrows():
        for route in _route_specs(amount_row):
            rows.append(
                _base_row(
                    amount_row=amount_row,
                    split_row=amount_row,
                    route=route,
                    source_inputs=source_inputs,
                )
            )

    return pd.DataFrame(
        rows,
        columns=TDCSIM_PRIVATE_ROUTE_ALLOCATION_SENSITIVITY_FIELDS,
    )


def render_tdcsim_private_route_allocation_sensitivity_markdown(
    frame: pd.DataFrame,
) -> str:
    if frame.empty:
        return "# TDCSim Private Route Allocation Sensitivity\n\nNo rows were generated.\n"
    latest_quarter = frame["ref_quarter"].dropna().iloc[-1]
    object_families = sorted(frame["object_family"].dropna().unique())
    return "\n".join(
        [
            "# TDCSim Private Route Allocation Sensitivity",
            "",
            f"- Contract version: `{CONTRACT_VERSION}`.",
            f"- Quarter range: `{frame['ref_quarter'].dropna().iloc[0]}` to `{latest_quarter}`.",
            f"- Route sensitivity rows: `{len(frame)}`.",
            f"- Object families: `{'; '.join(object_families)}`.",
            "- Boundary: bounded noncanonical proxy only; not a source-backed TDCSim `Private` split.",
            "- ON-RRP treatment: memo-only, not added to Treasury holder denominators.",
            "- Allowed use: TDCSim and RateWall sensitivity sidecar context only; no canonical TDC, Evidence Mode, allocation, incidence, welfare, tax, MPC, pricing, or prior-narrowing use.",
            "",
        ]
    )


def write_tdcsim_private_route_allocation_sensitivity(
    *,
    z1_flow_path: Path | str,
    z1_stock_path: Path | str,
    mmf_route_split_context_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str | None = None,
) -> tuple[Path, Path | None, pd.DataFrame]:
    z1_flow_path = Path(z1_flow_path)
    z1_stock_path = Path(z1_stock_path)
    mmf_route_split_context_path = Path(mmf_route_split_context_path)
    frame = build_tdcsim_private_route_allocation_sensitivity(
        z1_flow=pd.read_csv(z1_flow_path),
        z1_stock=pd.read_csv(z1_stock_path),
        mmf_route_split_context=pd.read_csv(mmf_route_split_context_path),
        source_inputs=(
            f"{z1_flow_path.name};{z1_stock_path.name};"
            f"{mmf_route_split_context_path.name}"
        ),
    )
    target = Path(csv_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False)
    md_target: Path | None = None
    if markdown_path is not None:
        md_target = Path(markdown_path)
        md_target.parent.mkdir(parents=True, exist_ok=True)
        md_target.write_text(
            render_tdcsim_private_route_allocation_sensitivity_markdown(frame),
            encoding="utf-8",
        )
    return target, md_target, frame
