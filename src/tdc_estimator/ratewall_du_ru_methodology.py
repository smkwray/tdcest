from __future__ import annotations

from pathlib import Path

import pandas as pd


RATEWALL_DU_RU_METHODOLOGY_FIELDS = [
    "date",
    "quarter",
    "treasury_interest_total_bil",
    "treasury_interest_to_du_bil",
    "treasury_interest_to_ru_bil",
    "treasury_interest_du_share",
    "tdcest_interest_method_tier",
    "tdcest_interest_split_method",
    "z1_security_absorption_du_bil",
    "z1_security_absorption_fed_bil",
    "z1_security_absorption_banks_bil",
    "z1_security_absorption_row_bil",
    "z1_security_absorption_core_ru_bil",
    "z1_security_absorption_mmf_plumbing_bil",
    "z1_security_absorption_dealer_bridge_bil",
    "z1_security_absorption_other_financial_bil",
    "z1_security_absorption_unmapped_bil",
    "z1_security_absorption_total_mapped_bil",
    "z1_domestic_nonbank_proxy_caveat",
    "z1_mmf_plumbing_label",
    "z1_holder_source_layer",
    "z1_residual_interpretation",
    "methodology_proxy_label",
    "tdcest_interest_tier_caveat",
    "methodology_status",
    "source_status",
]


def _quarter_from_date(value: object) -> str:
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return ""
    return f"{timestamp.year}Q{((timestamp.month - 1) // 3) + 1}"


def _to_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def build_ratewall_du_ru_methodology_panel(
    du_fiscal_flow: pd.DataFrame,
    interest_method: pd.DataFrame,
    z1_holder_absorption: pd.DataFrame,
) -> pd.DataFrame:
    """Build the TDC-EST-owned DU/RU export used by RateWall."""
    if du_fiscal_flow.empty:
        return pd.DataFrame(columns=RATEWALL_DU_RU_METHODOLOGY_FIELDS)

    interest = du_fiscal_flow.copy()
    interest["date"] = pd.to_datetime(interest["date"], errors="coerce")
    interest = interest.dropna(subset=["date"]).copy()
    interest["quarter"] = interest["date"].map(_quarter_from_date)
    interest["treasury_interest_total_bil"] = (
        _to_numeric(interest, "treasury_interest_gross_proxy") / 1000.0
    )
    interest["treasury_interest_to_du_bil"] = (
        _to_numeric(interest, "du_coupon_proxy_primary") / 1000.0
    )
    interest["treasury_interest_to_ru_bil"] = (
        interest["treasury_interest_total_bil"] - interest["treasury_interest_to_du_bil"]
    )
    interest["treasury_interest_du_share"] = (
        interest["treasury_interest_to_du_bil"] / interest["treasury_interest_total_bil"]
    )
    interest.loc[
        interest["treasury_interest_total_bil"].isna()
        | interest["treasury_interest_total_bil"].eq(0),
        "treasury_interest_du_share",
    ] = pd.NA

    method = interest_method.copy()
    if not method.empty and "date" in method.columns:
        method["quarter"] = pd.to_datetime(method["date"], errors="coerce").map(
            _quarter_from_date
        )
        method = method.loc[:, ["quarter", "bank_method_tier", "row_method_tier", "credit_union_method_tier"]]
    else:
        method = pd.DataFrame(
            columns=[
                "quarter",
                "bank_method_tier",
                "row_method_tier",
                "credit_union_method_tier",
            ]
        )

    holder = z1_holder_absorption.copy()
    if not holder.empty and "quarter" in holder.columns:
        holder["quarter"] = pd.to_datetime(holder["quarter"], errors="coerce").map(
            _quarter_from_date
        )
    else:
        holder = pd.DataFrame(columns=["quarter"])

    base = interest.loc[
        :,
        [
            "date",
            "quarter",
            "treasury_interest_total_bil",
            "treasury_interest_to_du_bil",
            "treasury_interest_to_ru_bil",
            "treasury_interest_du_share",
        ],
    ].merge(method, on="quarter", how="left")

    holder_fields = [
        "quarter",
        "sector_tx_fed",
        "sector_tx_banks",
        "sector_tx_row",
        "sector_tx_mmf",
        "sector_tx_domestic_nonbank",
        "sector_tx_dealer_bridge",
        "sector_tx_other_financial",
        "sector_tx_unmapped",
        "holder_source_layer",
        "residual_interpretation",
    ]
    holder = holder.reindex(columns=holder_fields)
    base = base.merge(holder, on="quarter", how="left")

    fed = _to_numeric(base, "sector_tx_fed")
    banks = _to_numeric(base, "sector_tx_banks")
    row = _to_numeric(base, "sector_tx_row")
    mmf = _to_numeric(base, "sector_tx_mmf")
    du = _to_numeric(base, "sector_tx_domestic_nonbank")
    dealer = _to_numeric(base, "sector_tx_dealer_bridge")
    other = _to_numeric(base, "sector_tx_other_financial")
    unmapped = _to_numeric(base, "sector_tx_unmapped")

    tier_text = (
        base[["bank_method_tier", "row_method_tier", "credit_union_method_tier"]]
        .fillna("")
        .agg(";".join, axis=1)
        .str.strip(";")
    )
    out = pd.DataFrame(
        {
            "date": base["date"].dt.strftime("%Y-%m-%d"),
            "quarter": base["quarter"],
            "treasury_interest_total_bil": base["treasury_interest_total_bil"],
            "treasury_interest_to_du_bil": base["treasury_interest_to_du_bil"],
            "treasury_interest_to_ru_bil": base["treasury_interest_to_ru_bil"],
            "treasury_interest_du_share": base["treasury_interest_du_share"],
            "tdcest_interest_method_tier": tier_text,
            "tdcest_interest_split_method": "tdcest_du_coupon_proxy_primary_residual_ru",
            "z1_security_absorption_du_bil": du,
            "z1_security_absorption_fed_bil": fed,
            "z1_security_absorption_banks_bil": banks,
            "z1_security_absorption_row_bil": row,
            "z1_security_absorption_core_ru_bil": fed + banks + row,
            "z1_security_absorption_mmf_plumbing_bil": mmf,
            "z1_security_absorption_dealer_bridge_bil": dealer,
            "z1_security_absorption_other_financial_bil": other,
            "z1_security_absorption_unmapped_bil": unmapped,
            "z1_security_absorption_total_mapped_bil": fed
            + banks
            + row
            + mmf
            + du
            + dealer
            + other
            + unmapped,
            "z1_domestic_nonbank_proxy_caveat": (
                "domestic_nonbank_z1_holder_transaction_proxy_not_exact_"
                "deposit_funded_final_demand"
            ),
            "z1_mmf_plumbing_label": (
                "mmf_onrrp_plumbing_separate_from_deposit_funded_du"
            ),
            "z1_holder_source_layer": base.get("holder_source_layer", ""),
            "z1_residual_interpretation": base.get("residual_interpretation", ""),
            "methodology_proxy_label": (
                "owner_directed_tdcest_interest_z1_holder_absorption_"
                "methodology_proxy_nonheadline_noncanonical"
            ),
            "tdcest_interest_tier_caveat": tier_text.map(
                lambda value: (
                    "backcast_edge_or_component_pool_method"
                    if "backcast" in value
                    else (
                        "modern_constrained_component_method"
                        if "constrained_component" in value
                        else "method_tier_missing_or_mixed"
                    )
                )
            ),
        }
    )
    available = (
        out["treasury_interest_total_bil"].notna()
        & out["treasury_interest_to_du_bil"].notna()
        & out["treasury_interest_to_ru_bil"].notna()
        & out["z1_security_absorption_du_bil"].notna()
        & out["z1_security_absorption_core_ru_bil"].notna()
    )
    out["methodology_status"] = "blocked_missing_tdcest_interest_or_z1_absorption_input"
    out.loc[
        available,
        "methodology_status",
    ] = "pass_tdcest_interest_split_and_z1_absorption_available"
    out["source_status"] = "tdcest_ratewall_du_ru_methodology_export"
    return out.loc[:, RATEWALL_DU_RU_METHODOLOGY_FIELDS]


def render_ratewall_du_ru_methodology_markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "# RateWall DU/RU Methodology Export\n\nNo rows were generated.\n"
    counts = frame["methodology_status"].value_counts().to_dict()
    first = frame["quarter"].dropna().iloc[0]
    latest = frame["quarter"].dropna().iloc[-1]
    return "\n".join(
        [
            "# RateWall DU/RU Methodology Export",
            "",
            f"- Quarter range: `{first}` to `{latest}`.",
            f"- Status counts: `{counts}`.",
            "- Interest split: TDC-EST gross Treasury interest less DU coupon proxy gives RU interest.",
            "- Security absorption: exact Z.1 holder absorption buckets from the TDCMix source layer.",
            "- Domestic nonbank bucket: methodology proxy, not exact deposit-funded final demand.",
            "- MMF bucket: ON RRP/MMF plumbing context kept separate from deposit-funded DU.",
            "- Use: downstream methodology surface; not a standalone causal or welfare claim.",
            "",
        ]
    )


def write_ratewall_du_ru_methodology_panel(
    *,
    du_fiscal_flow_path: Path | str,
    interest_method_path: Path | str,
    z1_holder_absorption_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str | None = None,
) -> tuple[Path, Path | None, pd.DataFrame]:
    du_fiscal_flow = pd.read_csv(du_fiscal_flow_path)
    interest_method = (
        pd.read_csv(interest_method_path)
        if Path(interest_method_path).exists()
        else pd.DataFrame()
    )
    z1_holder_absorption = (
        pd.read_csv(z1_holder_absorption_path)
        if Path(z1_holder_absorption_path).exists()
        else pd.DataFrame()
    )
    frame = build_ratewall_du_ru_methodology_panel(
        du_fiscal_flow,
        interest_method,
        z1_holder_absorption,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False)

    written_md: Path | None = None
    if markdown_path is not None:
        written_md = Path(markdown_path)
        written_md.parent.mkdir(parents=True, exist_ok=True)
        written_md.write_text(
            render_ratewall_du_ru_methodology_markdown(frame),
            encoding="utf-8",
        )
    return csv_path, written_md, frame
