from __future__ import annotations

from pathlib import Path

import pandas as pd


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def build_monetary_stage1_controls(
    quarterly: pd.DataFrame | None,
    monetary_stage0: pd.DataFrame | None,
) -> pd.DataFrame:
    if quarterly is None or quarterly.empty or monetary_stage0 is None or monetary_stage0.empty:
        return pd.DataFrame()

    index = pd.DatetimeIndex(monetary_stage0.index).sort_values().unique()
    frame = monetary_stage0.copy().reindex(index)

    def qdiff(col: str, scale: float = 1.0) -> pd.Series:
        if col not in quarterly.columns:
            return pd.Series(index=index, dtype="float64")
        series = pd.to_numeric(quarterly[col], errors="coerce").reindex(index) * scale
        return series.diff()

    if "delta_bank_credit_level_mil" not in frame.columns:
        frame["delta_bank_credit_level_mil"] = qdiff("bank_credit", 1000.0)
    frame["delta_loans_and_leases_bank_credit_level_mil"] = qdiff("loans_and_leases_bank_credit", 1000.0)
    frame["delta_securities_in_bank_credit_level_mil"] = qdiff("securities_in_bank_credit", 1000.0)
    frame["delta_treasury_agency_non_mbs_bank_securities_level_mil"] = qdiff(
        "treasury_agency_non_mbs_bank_securities", 1000.0
    )
    frame["delta_other_securities_ex_treasury_agency_level_mil"] = (
        frame["delta_securities_in_bank_credit_level_mil"]
        - frame["delta_treasury_agency_non_mbs_bank_securities_level_mil"]
    )
    frame["delta_retail_money_market_funds_level_mil"] = qdiff("retail_money_market_funds", 1000.0)
    frame["delta_reverse_repo_treasury_level_mil"] = qdiff("reverse_repo_treasury", 1000.0)
    frame["delta_reserve_balances_with_frb_mil"] = qdiff("reserve_balances_with_frb", 1.0)
    frame["delta_term_deposits_at_fed_mil"] = qdiff("term_deposits_at_fed", 1.0)
    frame["delta_other_deposits_at_fed_mil"] = qdiff("other_deposits_at_fed", 1.0)
    frame["delta_fed_liquidity_credit_loans_net_mil"] = qdiff("fed_liquidity_credit_loans_net", 1.0)
    frame["delta_tga_weekly_level_mil"] = qdiff("tga_weekly", 1.0)
    frame["delta_commercial_bank_borrowings_mil"] = qdiff("commercial_bank_borrowings", 1.0)
    frame["delta_commercial_bank_cash_assets_mil"] = qdiff("commercial_bank_cash_assets", 1000.0)
    frame["delta_foreign_official_custody_treasuries_mil"] = qdiff("foreign_official_custody_treasuries", 1.0)
    frame["delta_foreign_related_treasury_agency_non_mbs_mil"] = qdiff(
        "foreign_related_treasury_agency_non_mbs", 1000.0
    )

    frame["bank_credit_additive_proxy_mil"] = frame["delta_bank_credit_level_mil"]
    frame["non_treasury_bank_credit_proxy_mil"] = (
        frame["delta_loans_and_leases_bank_credit_level_mil"].fillna(0.0)
        + frame["delta_other_securities_ex_treasury_agency_level_mil"].fillna(0.0)
    )
    frame["retail_mmf_rotation_proxy_mil"] = -frame["delta_retail_money_market_funds_level_mil"]
    frame["rrp_drain_proxy_mil"] = -frame["delta_reverse_repo_treasury_level_mil"]
    frame["reserve_balance_liquidity_proxy_mil"] = frame["delta_reserve_balances_with_frb_mil"]
    frame["fed_term_deposit_absorption_proxy_mil"] = -frame["delta_term_deposits_at_fed_mil"]
    frame["fed_other_deposits_absorption_proxy_mil"] = -frame["delta_other_deposits_at_fed_mil"]
    frame["fed_liquidity_credit_support_proxy_mil"] = frame["delta_fed_liquidity_credit_loans_net_mil"]
    frame["bank_borrowing_funding_proxy_mil"] = frame["delta_commercial_bank_borrowings_mil"]
    frame["simple_non_treasury_control_subtotal_mil"] = (
        frame["bank_credit_additive_proxy_mil"].fillna(0.0)
        + frame["retail_mmf_rotation_proxy_mil"].fillna(0.0)
        + frame["rrp_drain_proxy_mil"].fillna(0.0)
        + frame["reserve_balance_liquidity_proxy_mil"].fillna(0.0)
    )
    frame["refined_non_treasury_control_subtotal_mil"] = (
        frame["non_treasury_bank_credit_proxy_mil"].fillna(0.0)
        + frame["retail_mmf_rotation_proxy_mil"].fillna(0.0)
        + frame["rrp_drain_proxy_mil"].fillna(0.0)
        + frame["reserve_balance_liquidity_proxy_mil"].fillna(0.0)
    )
    frame["expanded_liquidity_and_funding_control_subtotal_mil"] = (
        frame["refined_non_treasury_control_subtotal_mil"].fillna(0.0)
        + frame["fed_term_deposit_absorption_proxy_mil"].fillna(0.0)
        + frame["fed_other_deposits_absorption_proxy_mil"].fillna(0.0)
        + frame["fed_liquidity_credit_support_proxy_mil"].fillna(0.0)
        + frame["bank_borrowing_funding_proxy_mil"].fillna(0.0)
    )

    for target_prefix, target_col in [
        ("depository_target", "delta_depository_target_level_mil"),
        ("liquid_target", "delta_liquid_deposit_target_level_mil"),
        ("commercial_bank_deposit_target", "delta_commercial_bank_deposits_level_mil"),
    ]:
        for tier_col in ["tier2_bank_only_flow_mil", "tier3_bank_only_flow_mil"]:
            if target_col in frame.columns and tier_col in frame.columns:
                base_gap_col = f"{target_prefix}_minus_{tier_col}"
                if base_gap_col not in frame.columns:
                    frame[base_gap_col] = (
                        pd.to_numeric(frame[target_col], errors="coerce")
                        - pd.to_numeric(frame[tier_col], errors="coerce")
                    )
                frame[f"{target_prefix}_minus_{tier_col}_minus_simple_controls_mil"] = (
                    pd.to_numeric(frame[base_gap_col], errors="coerce")
                    - frame["simple_non_treasury_control_subtotal_mil"]
                )
                frame[f"{target_prefix}_minus_{tier_col}_minus_refined_controls_mil"] = (
                    pd.to_numeric(frame[base_gap_col], errors="coerce")
                    - frame["refined_non_treasury_control_subtotal_mil"]
                )
                frame[f"{target_prefix}_minus_{tier_col}_minus_expanded_controls_mil"] = (
                    pd.to_numeric(frame[base_gap_col], errors="coerce")
                    - frame["expanded_liquidity_and_funding_control_subtotal_mil"]
                )

    frame["control_notes"] = (
        "Stage 1 partial controls. Sign conventions: retail MMF and RRP increases enter as deposit-drain proxies; "
        "reserve-balance increases enter as a liquidity-support proxy. The simple subtotal uses total bank credit, while the refined subtotal "
        "uses loans and leases plus other securities excluding Treasury/agency non-MBS securities. The expanded subtotal adds Fed term deposits, "
        "other deposits at the Fed, Fed liquidity-credit loans, and bank borrowings. Commercial-bank cash assets are shown as context only. "
        "Foreign-official custody holdings and foreign-related Treasury/agency securities are also shown as overlap-risk context only. "
        "TGA change is reported as timing context, not included in the control subtotals."
    )
    frame = frame.dropna(
        subset=[
            "simple_non_treasury_control_subtotal_mil",
            "refined_non_treasury_control_subtotal_mil",
            "expanded_liquidity_and_funding_control_subtotal_mil",
            "depository_target_minus_tier3_bank_only_flow_mil",
            "commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil",
        ],
        how="all",
    )
    return frame


def render_monetary_stage1_controls_markdown(controls: pd.DataFrame) -> str:
    title = "# Monetary Stage 1 Controls"
    intro = (
        "First control-block diagnostic layered on top of Monetary Stage 0. "
        "This artifact does not create a new estimator. It shows how much of the Stage 0 target gaps remain after "
        "simple, refined, and expanded non-Treasury control subtotals built from bank-credit blocks, retail MMF rotation, ON RRP, reserve balances, and a first deeper Fed/funding layer."
    )
    if controls.empty:
        return "\n".join([title, "", intro, "", "No monetary Stage 1 controls are available."])

    latest_date = controls.index.max()
    latest = controls.loc[latest_date]
    summary = (
        f"Latest quarter: {pd.Timestamp(latest_date).date().isoformat()}. "
        f"Simple control subtotal {_format_millions(latest.get('simple_non_treasury_control_subtotal_mil'))}; "
        f"refined control subtotal {_format_millions(latest.get('refined_non_treasury_control_subtotal_mil'))}; "
        f"expanded control subtotal {_format_millions(latest.get('expanded_liquidity_and_funding_control_subtotal_mil'))}; "
        f"depository gap vs Tier 3 {_format_millions(latest.get('depository_target_minus_tier3_bank_only_flow_mil'))}; "
        f"depository residual after expanded controls {_format_millions(latest.get('depository_target_minus_tier3_bank_only_flow_mil_minus_expanded_controls_mil'))}; "
        f"bank-deposit gap vs Tier 3 {_format_millions(latest.get('commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil'))}; "
        f"bank-deposit residual after expanded controls {_format_millions(latest.get('commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil_minus_expanded_controls_mil'))}."
    )

    header = [
        "| Quarter | Simple subtotal | Refined subtotal | Expanded subtotal | Loans and leases | Other securities ex Tsy/agency | Fed loans | Term-deposit absorb | Other-Fed-deposit absorb | Bank borrowing support | MMF rotation | RRP drain | Reserve-balance proxy | Depository residual after expanded controls | Bank-deposit residual after expanded controls | Bank cash-assets context | Foreign custody context | Foreign-related bank Tsy/agency context | TGA change context |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    rows: list[str] = []
    for date, row in controls.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(date).date().isoformat(),
                    _format_millions(row.get("simple_non_treasury_control_subtotal_mil")),
                    _format_millions(row.get("refined_non_treasury_control_subtotal_mil")),
                    _format_millions(row.get("expanded_liquidity_and_funding_control_subtotal_mil")),
                    _format_millions(row.get("delta_loans_and_leases_bank_credit_level_mil")),
                    _format_millions(row.get("delta_other_securities_ex_treasury_agency_level_mil")),
                    _format_millions(row.get("fed_liquidity_credit_support_proxy_mil")),
                    _format_millions(row.get("fed_term_deposit_absorption_proxy_mil")),
                    _format_millions(row.get("fed_other_deposits_absorption_proxy_mil")),
                    _format_millions(row.get("bank_borrowing_funding_proxy_mil")),
                    _format_millions(row.get("retail_mmf_rotation_proxy_mil")),
                    _format_millions(row.get("rrp_drain_proxy_mil")),
                    _format_millions(row.get("reserve_balance_liquidity_proxy_mil")),
                    _format_millions(row.get("depository_target_minus_tier3_bank_only_flow_mil_minus_expanded_controls_mil")),
                    _format_millions(row.get("commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil_minus_expanded_controls_mil")),
                    _format_millions(row.get("delta_commercial_bank_cash_assets_mil")),
                    _format_millions(row.get("delta_foreign_official_custody_treasuries_mil")),
                    _format_millions(row.get("delta_foreign_related_treasury_agency_non_mbs_mil")),
                    _format_millions(row.get("delta_tga_weekly_level_mil")),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- This is still a heuristic control set, not a structural monetary model.",
        "- `Simple subtotal` uses total bank credit plus MMF, RRP, and reserve-balance controls.",
        "- `Refined subtotal` replaces total bank credit with loans and leases plus other securities excluding Treasury/agency non-MBS securities to reduce overlap with Treasury-heavy bank-security channels.",
        "- `Expanded subtotal` adds Fed liquidity-credit loans, term deposits, other deposits at the Fed, and commercial-bank borrowings as a first deeper liquidity/funding block.",
        "- Commercial-bank cash assets, foreign-official custody holdings, foreign-related Treasury/agency securities, and TGA change are shown as context only, not included in the control subtotals.",
        "- Large residuals after controls indicate that the tension is not explained by this first-pass non-Treasury block alone.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_monetary_stage1_controls(
    *,
    quarterly: pd.DataFrame,
    monetary_stage0: pd.DataFrame,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    controls = build_monetary_stage1_controls(quarterly, monetary_stage0)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = controls.copy()
    to_write.index.name = "date"
    to_write.to_csv(csv_path)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_monetary_stage1_controls_markdown(controls), encoding="utf-8")

    return csv_path, markdown_path, controls
