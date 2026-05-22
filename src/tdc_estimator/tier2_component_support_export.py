from __future__ import annotations

from pathlib import Path

import pandas as pd


SUPPORT_EXPORT_COLUMNS = {
    "bank": "bank_tier2_component_interest_proxy",
    "row": "row_tier2_component_interest_proxy",
    "credit_union": "credit_union_tier2_component_interest_proxy",
}

DEFAULT_CONSTRAINED_COMPONENT_START = "2022-03-31"


def build_tier2_component_support_exports(
    candidate: pd.DataFrame,
    *,
    min_date: str | pd.Timestamp | None = DEFAULT_CONSTRAINED_COMPONENT_START,
) -> dict[str, pd.DataFrame]:
    if candidate.empty:
        return {key: pd.DataFrame(columns=["date", column]) for key, column in SUPPORT_EXPORT_COLUMNS.items()}
    df = candidate.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    if min_date is not None:
        df = df.loc[df["date"].ge(pd.Timestamp(min_date).normalize())].copy()
    df["component_anchored_interest_mil"] = pd.to_numeric(df["component_anchored_interest_mil"], errors="coerce")
    grouped = (
        df.dropna(subset=["date", "sector_group"])
        .groupby(["date", "sector_group"], as_index=False)["component_anchored_interest_mil"]
        .sum(min_count=1)
    )
    out: dict[str, pd.DataFrame] = {}
    for sector_group, value_column in SUPPORT_EXPORT_COLUMNS.items():
        rows = grouped.loc[grouped["sector_group"].astype(str).eq(sector_group), ["date", "component_anchored_interest_mil"]]
        support = rows.rename(columns={"component_anchored_interest_mil": value_column}).sort_values("date")
        support["date"] = pd.to_datetime(support["date"]).dt.date.astype(str)
        out[sector_group] = support.reset_index(drop=True)
    return out


def render_tier2_component_support_export_summary(exports: dict[str, pd.DataFrame]) -> str:
    lines = [
        "# Tier 2 Component-Anchored Support Exports",
        "",
        "These support files contain the constrained component-anchored default window. Earlier component-pool backcast quarters are available in `tier2_regression_interest_backcast.csv` instead of these canonical support files.",
        "",
        "| Sector | Rows | First date | Latest date | Latest value (mil) |",
        "|---|---:|---:|---:|---:|",
    ]
    for sector, frame in exports.items():
        if frame.empty:
            lines.append(f"| {sector} | 0 |  |  | NA |")
            continue
        date = pd.to_datetime(frame["date"], errors="coerce")
        value_col = [col for col in frame.columns if col != "date"][0]
        latest_idx = date.idxmax()
        latest_value = pd.to_numeric(frame.loc[latest_idx, value_col], errors="coerce")
        lines.append(
            f"| {sector} | {len(frame):,} | {date.min().date().isoformat()} | "
            f"{date.max().date().isoformat()} | ${float(latest_value):,.0f} |"
        )
    lines.extend(
        [
            "",
            "Promotion rule: consume these only through explicit component-anchored estimator wiring. Do not alias them to old coupon proxy names, because they already include coupon accrual, bill discount, and FRN interest.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_tier2_component_support_exports(
    *,
    candidate_path: Path | str,
    out_dir: Path | str,
    markdown_path: Path | str,
) -> tuple[dict[str, Path], Path, dict[str, pd.DataFrame]]:
    candidate = pd.read_csv(candidate_path)
    exports = build_tier2_component_support_exports(candidate)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for sector, frame in exports.items():
        path = out / f"support__{SUPPORT_EXPORT_COLUMNS[sector]}.csv"
        frame.to_csv(path, index=False)
        paths[sector] = path
    md_out = Path(markdown_path)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.write_text(render_tier2_component_support_export_summary(exports), encoding="utf-8")
    return paths, md_out, exports
