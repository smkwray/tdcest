from __future__ import annotations

from pathlib import Path

import pandas as pd


OUTPUT_COLUMN = "fed_tier1_component_extension_proxy"


def build_fed_component_extension_support(fed_components: pd.DataFrame) -> pd.DataFrame:
    if fed_components.empty:
        return pd.DataFrame(columns=["date", OUTPUT_COLUMN])
    df = fed_components.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    bill = pd.to_numeric(df.get("fed_tsy_bill_discount_interest_proxy"), errors="coerce").fillna(0.0)
    frn = pd.to_numeric(df.get("fed_tsy_frn_interest_proxy"), errors="coerce").fillna(0.0)
    out = pd.DataFrame({"date": df["date"], OUTPUT_COLUMN: bill + frn})
    out = out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    out["date"] = out["date"].dt.date.astype(str)
    return out


def render_fed_component_extension_summary(support: pd.DataFrame) -> str:
    lines = [
        "# Fed Tier 1 Component Extension Support",
        "",
        "This staged support file adds exact SOMA bill-discount and FRN-interest components to the existing Fed coupon Tier 1 correction.",
        "",
        "Default treatment: nondefault. TIPS inflation compensation remains excluded, and the separate TIPS coupon diagnostic is not added here to avoid double-counting coupon-like SOMA payments already handled by the existing coupon schedule.",
        "",
    ]
    if support.empty:
        return "\n".join(lines + ["No support rows were available."]) + "\n"
    df = support.copy()
    dates = pd.to_datetime(df["date"], errors="coerce")
    values = pd.to_numeric(df[OUTPUT_COLUMN], errors="coerce")
    latest_idx = dates.idxmax()
    latest = dates.loc[latest_idx].date().isoformat()
    latest_value = values.loc[latest_idx]
    nonzero = int(values.fillna(0.0).ne(0.0).sum())
    lines.extend(
        [
            f"Coverage runs from {dates.min().date().isoformat()} through {dates.max().date().isoformat()}.",
            f"Nonzero quarters: {nonzero:,}.",
            f"Latest quarter ({latest}) Fed bill+FRN extension is ${float(latest_value):,.0f} million.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_fed_component_extension_support(
    *,
    fed_components_path: Path | str,
    out_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    fed_components = pd.read_csv(fed_components_path)
    support = build_fed_component_extension_support(fed_components)
    csv_path = Path(out_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    support.to_csv(csv_path, index=False)
    md_path = Path(markdown_path)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_fed_component_extension_summary(support), encoding="utf-8")
    return csv_path, md_path, support
