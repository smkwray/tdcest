"""DS^T_DU sector allocation within the expense-layer complement.

Allocates each quarter's DS+U complement (from ``dst_du_expense_panel.csv``)
across the domestic deposit-user holder universe by Treasury position shares
(identity note sections 2-3): coupon-family components (nominal coupon, FRN)
are allocated by sector coupon positions and the bill component by sector bill
positions. MMFs are the position-anchored module (observed N-MFP fund-month
Treasury totals and bill holdings); every other sector is model-allocated from
Z.1 levels with the wamest coupon-share split. Sector rows are honestly labeled
"model_allocated_aggregate_disciplined" — the aggregate is the disciplined
object, the split is not claim-grade (identity note section 7).

Invariants enforced here: shares sum to one within each component family and
quarter; allocated amounts sum exactly back to the complement; narrow/broad/
domestic-public aggregates are sums over nonoverlapping constituents with
broad = narrow + additions; no sector appears in both DU and RU universes.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import load_quarterly_fred_series

NARROW_SECTORS = [
    "households_nonprofits",
    "nonfinancial_corporates",
    "nonfinancial_noncorporate_business",
]
BROAD_ADDITION_SECTORS = [
    "life_insurers",
    "property_casualty_insurers",
    "private_defined_benefit_pensions",
    "private_defined_contribution_pensions",
]
OTHER_DOMESTIC_SECTORS = [
    "money_market_funds",
    "mutual_funds",
    "exchange_traded_funds",
    "closed_end_funds",
    "security_brokers_and_dealers",
    "holding_companies",
    "asset_backed_securities_issuers",
    "government_sponsored_enterprises",
    "other_financial_business",
]
DOMESTIC_PUBLIC_SECTORS = [
    "state_local_governments",
    "state_local_employee_defined_benefit_pensions",
    "federal_defined_benefit_pensions",
    "federal_defined_contribution_pensions",
]
DU_UNIVERSE = (
    NARROW_SECTORS + BROAD_ADDITION_SECTORS + OTHER_DOMESTIC_SECTORS + DOMESTIC_PUBLIC_SECTORS
)

Z1_LEVEL_FILES = {
    "households_nonprofits": "fred__du_households_tsy_level.csv",
    "nonfinancial_corporates": "fred__du_nonfinancial_corporates_tsy_level.csv",
    "nonfinancial_noncorporate_business": "fred__du_noncorporate_tsy_level.csv",
    "life_insurers": "fred__du_life_insurers_tsy_level.csv",
    "property_casualty_insurers": "fred__du_pc_insurers_tsy_level.csv",
    "private_defined_benefit_pensions": "fred__du_private_db_pensions_tsy_level.csv",
    "private_defined_contribution_pensions": "fred__du_private_dc_pensions_tsy_level.csv",
    "mutual_funds": "fred__du_mutual_funds_tsy_level.csv",
    "exchange_traded_funds": "fred__du_etf_tsy_level.csv",
    "closed_end_funds": "fred__du_closed_end_funds_tsy_level.csv",
    "security_brokers_and_dealers": "fred__du_brokers_dealers_tsy_level.csv",
    "holding_companies": "fred__du_holding_companies_tsy_level.csv",
    "asset_backed_securities_issuers": "fred__du_abs_issuers_tsy_level.csv",
    "government_sponsored_enterprises": "fred__du_gse_tsy_level.csv",
    "other_financial_business": "fred__du_other_financial_tsy_level.csv",
    "state_local_governments": "fred__du_sl_governments_tsy_level.csv",
    "state_local_employee_defined_benefit_pensions": "fred__du_sl_governments_pensions_tsy_level.csv",
    "federal_defined_benefit_pensions": "fred__du_federal_db_pensions_tsy_level.csv",
    "federal_defined_contribution_pensions": "fred__du_federal_dc_pensions_tsy_level.csv",
}
MMF_FUND_MONTH_FILE = "support__mmf_fund_month.csv"

COUPON_FAMILY_COMPONENTS = ["coupon_accrual", "frn_accrued_interest"]
BILL_COMPONENT = "bill_amortized_discount"
TOTAL_COMPONENT_KEY = "total_core"

BASIS_NMFP = "nmfp_position_anchored"
BASIS_Z1 = "z1_level_model_allocated"
SECTOR_SPLIT_LABEL = "model_allocated_aggregate_disciplined"

AGGREGATE_ROWS = {
    "dst_du_narrow": NARROW_SECTORS,
    "dst_du_broad": NARROW_SECTORS + BROAD_ADDITION_SECTORS,
    "dst_du_other_domestic": OTHER_DOMESTIC_SECTORS,
    "dst_du_domestic_public": DOMESTIC_PUBLIC_SECTORS,
}


def _mmf_quarterly_positions(raw_dir: Path) -> pd.DataFrame:
    path = raw_dir / MMF_FUND_MONTH_FILE
    if not path.exists():
        return pd.DataFrame()
    fund_month = pd.read_csv(path, parse_dates=["date"])
    quarter_end = fund_month[fund_month["date"].dt.is_quarter_end]
    grouped = quarter_end.groupby("date")[["treasury_total", "treasury_bills"]].sum()
    out = pd.DataFrame(
        {
            "coupon_position_mil": (grouped["treasury_total"] - grouped["treasury_bills"]).clip(lower=0.0),
            "bill_position_mil": grouped["treasury_bills"].clip(lower=0.0),
        }
    )
    return out


def _coupon_share_lookup(sector_maturity: pd.DataFrame) -> pd.DataFrame:
    frame = sector_maturity.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["coupon_share"] = pd.to_numeric(frame["coupon_share"], errors="coerce").clip(0.0, 1.0)
    return frame.dropna(subset=["date", "coupon_share"])[["date", "sector_key", "coupon_share"]]


def build_du_position_frame(
    *,
    raw_dir: Path | str,
    sector_maturity: pd.DataFrame,
) -> pd.DataFrame:
    """Per (date, sector): coupon and bill Treasury positions in $M with basis labels."""
    raw = Path(raw_dir)
    shares = _coupon_share_lookup(sector_maturity)
    rows: list[pd.DataFrame] = []
    for sector, filename in Z1_LEVEL_FILES.items():
        path = raw / filename
        if not path.exists():
            continue
        level = load_quarterly_fred_series(path, agg="last").rename("level")
        frame = level.reset_index()
        frame.columns = ["date", "level"]
        frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
        frame["sector_key"] = sector
        frame = frame.merge(shares[shares["sector_key"] == sector], on=["date", "sector_key"], how="left")
        frame["coupon_share"] = frame["coupon_share"].ffill().bfill()
        frame = frame.dropna(subset=["level", "coupon_share"])
        frame["coupon_position_mil"] = frame["level"] * frame["coupon_share"]
        frame["bill_position_mil"] = frame["level"] * (1.0 - frame["coupon_share"])
        frame["position_basis"] = BASIS_Z1
        rows.append(frame[["date", "sector_key", "coupon_position_mil", "bill_position_mil", "position_basis"]])

    mmf = _mmf_quarterly_positions(raw)
    if not mmf.empty:
        frame = mmf.reset_index().rename(columns={"index": "date"})
        frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
        frame["sector_key"] = "money_market_funds"
        frame["position_basis"] = BASIS_NMFP
        rows.append(frame[["date", "sector_key", "coupon_position_mil", "bill_position_mil", "position_basis"]])

    if not rows:
        raise ValueError("No DU sector position inputs were found under the raw directory.")
    positions = pd.concat(rows, ignore_index=True)
    duplicated = positions.duplicated(subset=["date", "sector_key"])
    if duplicated.any():
        raise ValueError("Duplicate (date, sector) rows in the DU position frame.")
    return positions.sort_values(["date", "sector_key"]).reset_index(drop=True)


def build_dst_du_sector_allocation(
    *,
    expense_panel: pd.DataFrame,
    positions: pd.DataFrame,
) -> pd.DataFrame:
    expense = expense_panel.copy()
    expense["date"] = pd.to_datetime(expense["date"], errors="coerce").dt.normalize()
    pos = positions.copy()
    pos["date"] = pd.to_datetime(pos["date"], errors="coerce").dt.normalize()
    unknown = set(pos["sector_key"]) - set(DU_UNIVERSE)
    if unknown:
        raise ValueError(f"Position frame contains sectors outside the DU universe: {sorted(unknown)}")

    components = expense[expense["component_key"] != TOTAL_COMPONENT_KEY]
    rows: list[dict[str, object]] = []
    for (date, component), group in components.groupby(["date", "component_key"]):
        amount = float(group["dst_du_expense_complement_mil"].iloc[0])
        tier = str(group["method_tier"].iloc[0])
        position_column = (
            "bill_position_mil" if component == BILL_COMPONENT else "coupon_position_mil"
        )
        quarter_positions = pos[pos["date"] == date]
        weights = pd.to_numeric(quarter_positions[position_column], errors="coerce").fillna(0.0)
        total_weight = float(weights.sum())
        if quarter_positions.empty or total_weight <= 0.0:
            rows.append(
                {
                    "date": date,
                    "component_key": str(component),
                    "sector_key": "dst_du_unallocated",
                    "allocated_mil": amount,
                    "share_of_component": 1.0,
                    "position_basis": "no_position_inputs",
                    "sector_split_label": SECTOR_SPLIT_LABEL,
                    "method_tier": tier,
                }
            )
            continue
        for _, position_row in quarter_positions.iterrows():
            weight = float(pd.to_numeric(position_row[position_column], errors="coerce") or 0.0)
            share = weight / total_weight
            rows.append(
                {
                    "date": date,
                    "component_key": str(component),
                    "sector_key": str(position_row["sector_key"]),
                    "allocated_mil": amount * share,
                    "share_of_component": share,
                    "position_basis": str(position_row["position_basis"]),
                    "sector_split_label": SECTOR_SPLIT_LABEL,
                    "method_tier": tier,
                }
            )

    panel = pd.DataFrame(rows)
    if panel.empty:
        raise ValueError("Sector allocation produced no rows.")

    check = panel.groupby(["date", "component_key"]).agg(
        allocated=("allocated_mil", "sum"), share=("share_of_component", "sum")
    )
    expected = components.set_index(["date", "component_key"])["dst_du_expense_complement_mil"]
    joined = check.join(expected)
    gaps = (joined["allocated"] - joined["dst_du_expense_complement_mil"]).abs()
    if (gaps > 1e-6).any() or ((joined["share"] - 1.0).abs() > 1e-9).any():
        raise ValueError("Sector allocation failed closure: allocations must sum to the complement.")

    aggregates: list[dict[str, object]] = []
    for (date, component), group in panel.groupby(["date", "component_key"]):
        indexed = group.set_index("sector_key")
        for aggregate_key, members in AGGREGATE_ROWS.items():
            present = [m for m in members if m in indexed.index]
            aggregates.append(
                {
                    "date": date,
                    "component_key": str(component),
                    "sector_key": aggregate_key,
                    "allocated_mil": float(indexed.loc[present, "allocated_mil"].sum()),
                    "share_of_component": float(indexed.loc[present, "share_of_component"].sum()),
                    "position_basis": "aggregate_of_constituents",
                    "sector_split_label": SECTOR_SPLIT_LABEL,
                    "method_tier": str(group["method_tier"].iloc[0]),
                }
            )
    combined = pd.concat([panel, pd.DataFrame(aggregates)], ignore_index=True)

    wide = combined[combined["sector_key"].isin(["dst_du_narrow", "dst_du_broad"])]
    pivot = wide.pivot_table(
        index=["date", "component_key"], columns="sector_key", values="allocated_mil", aggfunc="first"
    )
    if not ((pivot["dst_du_broad"] - pivot["dst_du_narrow"]) >= -1e-9).all():
        raise ValueError("Aggregate invariant violated: broad must be >= narrow.")
    return combined.sort_values(["date", "component_key", "sector_key"]).reset_index(drop=True)


def render_dst_du_sector_allocation_summary(panel: pd.DataFrame) -> str:
    latest_date = panel["date"].max()
    latest = panel[(panel["date"] == latest_date)]
    total_by_sector = (
        latest[~latest["sector_key"].str.startswith("dst_du_")]
        .groupby("sector_key")["allocated_mil"]
        .sum()
        .sort_values(ascending=False)
    )
    mmf_basis = latest.loc[latest["sector_key"] == "money_market_funds", "position_basis"].unique()
    lines = [
        "# DS^T_DU sector allocation panel",
        "",
        "Sector split of the expense-layer DS+U complement by Treasury position",
        "shares. The AGGREGATE complement is the disciplined object; this split is",
        f"'{SECTOR_SPLIT_LABEL}' — not claim-grade. MMF is position-anchored from",
        "N-MFP fund-month observations; all other sectors are model-allocated from",
        "Z.1 levels with wamest coupon-share splits. Coupon-family components",
        "(nominal coupon, FRN) use coupon positions; bill discount uses bill",
        "positions. Conventions: DS^T_DU identity note (2026-07-13).",
        "",
        f"Latest quarter ({pd.Timestamp(latest_date).date()}), top sector allocations across the core components ($M):",
        "",
    ]
    for sector, value in total_by_sector.head(8).items():
        lines.append(f"- {sector}: {value:,.1f}")
    lines += [
        "",
        f"MMF basis: {', '.join(mmf_basis) if len(mmf_basis) else 'absent'}.",
    ]
    return "\n".join(lines) + "\n"


def write_dst_du_sector_allocation(
    *,
    expense_panel_path: Path | str,
    raw_dir: Path | str,
    sector_maturity_path: Path | str,
    out_csv_path: Path | str,
    out_markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    expense = pd.read_csv(expense_panel_path)
    maturity = pd.read_csv(sector_maturity_path)
    positions = build_du_position_frame(raw_dir=raw_dir, sector_maturity=maturity)
    panel = build_dst_du_sector_allocation(expense_panel=expense, positions=positions)
    out_csv = Path(out_csv_path)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    write = panel.copy()
    write["date"] = pd.to_datetime(write["date"], errors="coerce").dt.date.astype(str)
    write.to_csv(out_csv, index=False)
    out_md = Path(out_markdown_path)
    out_md.write_text(render_dst_du_sector_allocation_summary(panel), encoding="utf-8")
    return out_csv, out_md, panel
