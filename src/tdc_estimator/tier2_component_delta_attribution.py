from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_tier2_component_delta_attribution(candidate: pd.DataFrame) -> pd.DataFrame:
    if candidate.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "sector_group",
                "component_key",
                "component_anchored_interest_mil",
                "current_proxy_comparable_mil",
                "component_minus_current_mil",
                "delta_share_of_sector_total",
                "allocator_basis",
            ]
        )
    df = candidate.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    for col in ["component_anchored_interest_mil", "current_raw_proxy_mil"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["current_proxy_comparable_mil"] = df["current_raw_proxy_mil"].fillna(0.0)
    df["component_minus_current_mil"] = (
        df["component_anchored_interest_mil"].fillna(0.0) - df["current_proxy_comparable_mil"]
    )
    component_rows = df[
        [
            "date",
            "sector_group",
            "component_key",
            "component_anchored_interest_mil",
            "current_proxy_comparable_mil",
            "component_minus_current_mil",
            "allocator_basis",
        ]
    ].copy()

    totals = (
        component_rows.groupby(["date", "sector_group"], as_index=False)
        .agg(
            component_anchored_interest_mil=("component_anchored_interest_mil", "sum"),
            current_proxy_comparable_mil=("current_proxy_comparable_mil", "sum"),
            component_minus_current_mil=("component_minus_current_mil", "sum"),
        )
    )
    totals["component_key"] = "sector_total"
    totals["allocator_basis"] = "sum_of_component_rows"

    out = pd.concat([component_rows, totals], ignore_index=True, sort=False)
    total_delta = out.loc[out["component_key"].eq("sector_total"), ["date", "sector_group", "component_minus_current_mil"]]
    total_delta = total_delta.rename(columns={"component_minus_current_mil": "sector_total_delta_mil"})
    out = out.merge(total_delta, on=["date", "sector_group"], how="left")
    denominator = out["sector_total_delta_mil"].where(out["sector_total_delta_mil"].abs().gt(0.0))
    out["delta_share_of_sector_total"] = out["component_minus_current_mil"] / denominator
    return out.sort_values(["date", "sector_group", "component_key"]).reset_index(drop=True)


def render_tier2_component_delta_attribution(attribution: pd.DataFrame) -> str:
    lines = [
        "# Tier 2 Component Delta Attribution",
        "",
        "This decomposes the difference between the staged component-anchored Tier 2 interest candidate and the current live coupon/bill proxy support files.",
        "",
    ]
    if attribution.empty:
        return "\n".join(lines + ["No attribution rows were available."]) + "\n"
    df = attribution.copy()
    latest_date = pd.to_datetime(df["date"], errors="coerce").max()
    latest = df.loc[pd.to_datetime(df["date"], errors="coerce").eq(latest_date)].copy()
    totals = latest.loc[latest["component_key"].eq("sector_total")].sort_values("sector_group")
    lines.extend(
        [
            f"Latest quarter: {latest_date.date().isoformat()}.",
            "",
            "| Sector | Component total (mil) | Comparable current proxy (mil) | Component minus current (mil) |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in totals.itertuples(index=False):
        lines.append(
            f"| {row.sector_group} | ${float(row.component_anchored_interest_mil):,.0f} | "
            f"${float(row.current_proxy_comparable_mil):,.0f} | ${float(row.component_minus_current_mil):,.0f} |"
        )
    lines.extend(["", "Latest component contributions:", "", "| Sector | Component | Delta (mil) | Share of sector delta |"])
    lines.append("|---|---|---:|---:|")
    pieces = latest.loc[~latest["component_key"].eq("sector_total")].copy()
    for row in pieces.sort_values(["sector_group", "component_key"]).itertuples(index=False):
        share = "" if pd.isna(row.delta_share_of_sector_total) else f"{float(row.delta_share_of_sector_total):.1%}"
        lines.append(
            f"| {row.sector_group} | {row.component_key} | ${float(row.component_minus_current_mil):,.0f} | {share} |"
        )
    lines.extend(
        [
            "",
            "Interpretation: FRN rows have no old live proxy counterpart, so their comparable current proxy is zero. Coupon and bill rows compare directly with the current raw support files.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_tier2_component_delta_attribution(
    *,
    candidate_path: Path | str,
    out_csv_path: Path | str,
    out_markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    candidate = pd.read_csv(candidate_path)
    attribution = build_tier2_component_delta_attribution(candidate)
    csv_path = Path(out_csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    out = attribution.copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.date.astype(str)
    out.to_csv(csv_path, index=False)
    md_path = Path(out_markdown_path)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_tier2_component_delta_attribution(attribution), encoding="utf-8")
    return csv_path, md_path, attribution
