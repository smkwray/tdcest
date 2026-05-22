from __future__ import annotations

from pathlib import Path

import pandas as pd


SECTOR_PROXY_COLUMNS = {
    "bank": "bank_tier2_regression_interest_proxy",
    "row": "row_tier2_regression_interest_proxy",
    "credit_union": "credit_union_tier2_regression_interest_proxy",
}

LEGACY_PROXY_COLUMNS = {
    "bank": ["bank_tsy_coupon_interest_proxy", "bank_tsy_bill_discount_interest_proxy"],
    "row": ["row_tsy_coupon_interest_proxy", "row_tsy_bill_discount_interest_proxy"],
    "credit_union": ["credit_union_tsy_coupon_interest_proxy", "credit_union_tsy_bill_discount_interest_proxy"],
}


def _read_series(path: Path | str, value_column: str | None = None) -> pd.Series:
    df = pd.read_csv(path)
    if "date" not in df.columns:
        return pd.Series(dtype="float64")
    column = value_column if value_column in df.columns else None
    if column is None:
        candidates = [col for col in df.columns if col != "date"]
        column = candidates[0] if candidates else None
    if column is None:
        return pd.Series(dtype="float64")
    out = pd.Series(
        pd.to_numeric(df[column], errors="coerce").values,
        index=pd.to_datetime(df["date"], errors="coerce").dt.normalize(),
        name=column,
    )
    return out.dropna().sort_index().astype("float64")


def _legacy_total(paths: dict[str, Path | str | None], sector: str) -> pd.Series:
    total = pd.Series(dtype="float64")
    for column in LEGACY_PROXY_COLUMNS[sector]:
        path = paths.get(column)
        if path is None or not Path(path).exists():
            continue
        series = _read_series(path, column)
        total = series if total.empty else total.add(series, fill_value=0.0)
    return total.sort_index()


def _component_total(candidate: pd.DataFrame, sector: str) -> pd.Series:
    if candidate.empty:
        return pd.Series(dtype="float64")
    df = candidate.loc[candidate["sector_group"].astype(str).eq(sector)].copy()
    if df.empty:
        return pd.Series(dtype="float64")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df["component_anchored_interest_mil"] = pd.to_numeric(df["component_anchored_interest_mil"], errors="coerce")
    return df.groupby("date")["component_anchored_interest_mil"].sum(min_count=1).dropna().sort_index()


def _scale_ratio(component: pd.Series, legacy: pd.Series) -> float:
    overlap = pd.concat([component.rename("component"), legacy.rename("legacy")], axis=1, sort=False).dropna()
    overlap = overlap.loc[overlap["legacy"].abs().gt(0.0)]
    if overlap.empty:
        return 1.0
    early = overlap.loc[overlap.index <= (overlap.index.min() + pd.DateOffset(years=5))]
    sample = early if not early.empty else overlap
    ratios = sample["component"] / sample["legacy"]
    ratios = ratios.replace([float("inf"), float("-inf")], pd.NA).dropna()
    return float(ratios.median()) if not ratios.empty else 1.0


def build_tier2_regression_backcast(
    *,
    candidate: pd.DataFrame,
    legacy_proxy_paths: dict[str, Path | str | None],
    constrained_start: str | pd.Timestamp = "2022-03-31",
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    constrained_start_ts = pd.Timestamp(constrained_start).normalize()
    for sector, value_column in SECTOR_PROXY_COLUMNS.items():
        component = _component_total(candidate, sector)
        legacy = _legacy_total(legacy_proxy_paths, sector)
        if component.empty and legacy.empty:
            continue
        ratio = _scale_ratio(component, legacy)
        all_dates = component.index.union(legacy.index).sort_values()
        frame = pd.DataFrame({"date": all_dates})
        frame["sector_group"] = sector
        frame["component_anchored_interest_mil"] = component.reindex(all_dates).to_numpy()
        frame["legacy_h15_interest_proxy_mil"] = legacy.reindex(all_dates).to_numpy()
        frame["backcast_scale_ratio"] = ratio
        scaled = frame["legacy_h15_interest_proxy_mil"] * ratio
        has_component = frame["component_anchored_interest_mil"].notna()
        frame[value_column] = frame["component_anchored_interest_mil"].where(has_component, scaled)
        frame["method_tier"] = "pre_component_h15_scaled_backcast"
        frame.loc[has_component, "method_tier"] = "component_pool_wamest_bucket_backcast"
        frame.loc[has_component & frame["date"].ge(constrained_start_ts), "method_tier"] = "constrained_component"
        frame["evidence_grade"] = frame["method_tier"].map(
            {
                "constrained_component": "medium_high",
                "component_pool_wamest_bucket_backcast": "medium",
                "pre_component_h15_scaled_backcast": "low_medium",
            }
        )
        frame["backcast_flag"] = frame["method_tier"].ne("constrained_component")
        rows.append(frame)
    if not rows:
        return pd.DataFrame(
            columns=[
                "date",
                "sector_group",
                "component_anchored_interest_mil",
                "legacy_h15_interest_proxy_mil",
                "backcast_scale_ratio",
                "tier2_regression_interest_proxy",
                "method_tier",
                "evidence_grade",
                "backcast_flag",
            ]
        )
    out = pd.concat(rows, ignore_index=True).sort_values(["date", "sector_group"]).reset_index(drop=True)
    out["tier2_regression_interest_proxy"] = pd.NA
    for sector, value_column in SECTOR_PROXY_COLUMNS.items():
        mask = out["sector_group"].eq(sector)
        if value_column not in out.columns:
            continue
        out.loc[mask, "tier2_regression_interest_proxy"] = out.loc[mask, value_column]
    return out


def render_tier2_regression_backcast_summary(backcast: pd.DataFrame) -> str:
    lines = [
        "# Tier 2 Regression Backcast",
        "",
        "Regression-grade Tier 2 interest support with explicit method tiers.",
        "",
    ]
    if backcast.empty:
        return "\n".join(lines + ["No backcast rows were available."]) + "\n"
    df = backcast.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    value = pd.to_numeric(df["tier2_regression_interest_proxy"], errors="coerce")
    lines.extend(
        [
            f"Coverage runs from {df['date'].min().date().isoformat()} through {df['date'].max().date().isoformat()}.",
            "",
            "| Method tier | Rows | First date | Latest date |",
            "|---|---:|---:|---:|",
        ]
    )
    for tier, group in df.groupby("method_tier", sort=True):
        lines.append(
            f"| {tier} | {len(group):,} | {group['date'].min().date().isoformat()} | "
            f"{group['date'].max().date().isoformat()} |"
        )
    latest = df.loc[df["date"].eq(df["date"].max())].copy()
    latest["value"] = value.reindex(latest.index)
    lines.extend(["", "Latest-quarter sector values:", "", "| Sector | Value (mil) | Method tier |", "|---|---:|---|"])
    for row in latest.sort_values("sector_group").itertuples(index=False):
        lines.append(f"| {row.sector_group} | ${float(row.value):,.0f} | {row.method_tier} |")
    lines.extend(
        [
            "",
            "Use this for regression windows that need pre-2022 history. Do not describe all tiers as equally identified: 2022+ is constrained component, 2010-2021 is component-pool/WAMEST-bucket backcast, and pre-2010 is scaled H15 backcast.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_tier2_regression_backcast(
    *,
    candidate_path: Path | str,
    legacy_proxy_paths: dict[str, Path | str | None],
    out_csv_path: Path | str,
    out_markdown_path: Path | str,
    out_wide_csv_path: Path | str | None = None,
) -> tuple[Path, Path, pd.DataFrame]:
    candidate = pd.read_csv(candidate_path)
    backcast = build_tier2_regression_backcast(candidate=candidate, legacy_proxy_paths=legacy_proxy_paths)
    out_csv = Path(out_csv_path)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    write = backcast.copy()
    if "date" in write.columns:
        write["date"] = pd.to_datetime(write["date"], errors="coerce").dt.date.astype(str)
    write.to_csv(out_csv, index=False)
    if out_wide_csv_path is not None and not backcast.empty:
        wide = (
            backcast.pivot_table(
                index="date",
                columns="sector_group",
                values="tier2_regression_interest_proxy",
                aggfunc="sum",
            )
            .rename(
                columns={
                    "bank": "bank_tier2_regression_interest_proxy",
                    "row": "row_tier2_regression_interest_proxy",
                    "credit_union": "credit_union_tier2_regression_interest_proxy",
                }
            )
            .reset_index()
        )
        for column in [
            "bank_tier2_regression_interest_proxy",
            "row_tier2_regression_interest_proxy",
            "credit_union_tier2_regression_interest_proxy",
        ]:
            if column not in wide.columns:
                wide[column] = pd.NA
        wide["bank_row_tier2_regression_interest_proxy"] = (
            wide["bank_tier2_regression_interest_proxy"] + wide["row_tier2_regression_interest_proxy"]
        )
        wide["di_tier2_regression_interest_proxy"] = (
            wide["bank_row_tier2_regression_interest_proxy"] + wide["credit_union_tier2_regression_interest_proxy"]
        )
        tiers = backcast.pivot_table(index="date", columns="sector_group", values="method_tier", aggfunc="first")
        for sector in ["bank", "row", "credit_union"]:
            if sector in tiers.columns:
                wide[f"{sector}_method_tier"] = tiers[sector].reindex(pd.to_datetime(wide["date"]).dt.normalize()).to_numpy()
        wide["date"] = pd.to_datetime(wide["date"], errors="coerce").dt.date.astype(str)
        out_wide = Path(out_wide_csv_path)
        out_wide.parent.mkdir(parents=True, exist_ok=True)
        wide.to_csv(out_wide, index=False)
    out_md = Path(out_markdown_path)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_tier2_regression_backcast_summary(backcast), encoding="utf-8")
    return out_csv, out_md, backcast
