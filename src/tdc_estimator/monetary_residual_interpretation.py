from __future__ import annotations

from pathlib import Path

import pandas as pd


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def _safe_share(num: object, den: object) -> float | pd._libs.missing.NAType:
    num = pd.to_numeric(num, errors="coerce")
    den = pd.to_numeric(den, errors="coerce")
    if pd.isna(num) or pd.isna(den) or float(den) == 0.0:
        return pd.NA
    return float(num) / float(den)


def _residual_label(share: object) -> str:
    share = pd.to_numeric(share, errors="coerce")
    if pd.isna(share):
        return "insufficient_data"
    value = abs(float(share))
    if value >= 0.75:
        return "mostly_unresolved"
    if value >= 0.4:
        return "partly_explained"
    return "largely_explained"


def _build_target_view(frame: pd.DataFrame, *, target_prefix: str, gap_col: str) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    out["target_family"] = target_prefix
    out["gap_vs_tier3_mil"] = pd.to_numeric(frame[gap_col], errors="coerce")
    out["residual_after_simple_mil"] = pd.to_numeric(
        frame[f"{target_prefix}_minus_tier3_bank_only_flow_mil_minus_simple_controls_mil"], errors="coerce"
    )
    out["residual_after_refined_mil"] = pd.to_numeric(
        frame[f"{target_prefix}_minus_tier3_bank_only_flow_mil_minus_refined_controls_mil"], errors="coerce"
    )
    out["residual_after_expanded_mil"] = pd.to_numeric(
        frame[f"{target_prefix}_minus_tier3_bank_only_flow_mil_minus_expanded_controls_mil"], errors="coerce"
    )
    out["simple_explained_mil"] = out["gap_vs_tier3_mil"] - out["residual_after_simple_mil"]
    out["incremental_refined_explained_mil"] = out["residual_after_simple_mil"] - out["residual_after_refined_mil"]
    out["incremental_expanded_explained_mil"] = (
        out["residual_after_refined_mil"] - out["residual_after_expanded_mil"]
    )
    out["total_explained_after_expanded_mil"] = out["gap_vs_tier3_mil"] - out["residual_after_expanded_mil"]
    out["expanded_residual_share_of_gap"] = [
        _safe_share(resid, gap) for resid, gap in zip(out["residual_after_expanded_mil"], out["gap_vs_tier3_mil"])
    ]
    out["total_explained_share_after_expanded"] = [
        _safe_share(explained, gap)
        for explained, gap in zip(out["total_explained_after_expanded_mil"], out["gap_vs_tier3_mil"])
    ]
    out["residual_regime"] = out["expanded_residual_share_of_gap"].map(_residual_label)
    return out


def build_monetary_residual_interpretation(controls: pd.DataFrame | None) -> pd.DataFrame:
    if controls is None or controls.empty:
        return pd.DataFrame()

    parts: list[pd.DataFrame] = []
    mappings = [
        ("depository_target", "depository_target_minus_tier3_bank_only_flow_mil"),
        ("commercial_bank_deposit_target", "commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil"),
    ]
    for target_prefix, gap_col in mappings:
        if gap_col not in controls.columns:
            continue
        part = _build_target_view(controls, target_prefix=target_prefix, gap_col=gap_col)
        parts.append(part)

    if not parts:
        return pd.DataFrame()

    out = pd.concat(parts)
    out.index.name = "date"
    out = out.reset_index().sort_values(["date", "target_family"]).reset_index(drop=True)
    return out


def render_monetary_residual_interpretation_markdown(residuals: pd.DataFrame) -> str:
    title = "# Monetary Residual Interpretation"
    intro = (
        "Residual-interpretation layer on top of Monetary Stage 1. "
        "This artifact shows how much of each target gap is reduced by the simple, refined, and expanded control blocks, "
        "and how much remains unresolved."
    )
    if residuals.empty:
        return "\n".join([title, "", intro, "", "No monetary residual interpretation is available."])

    latest_date = pd.Timestamp(residuals["date"].max())
    latest = residuals[pd.to_datetime(residuals["date"]) == latest_date].copy()
    latest = latest.sort_values("target_family")

    summary_parts = []
    for _, row in latest.iterrows():
        summary_parts.append(
            f"{row['target_family']}: gap {_format_millions(row['gap_vs_tier3_mil'])}, "
            f"expanded residual {_format_millions(row['residual_after_expanded_mil'])}, "
            f"regime {row['residual_regime']}"
        )
    summary = f"Latest quarter: {latest_date.date().isoformat()}. " + "; ".join(summary_parts) + "."

    header = [
        "| Quarter | Target | Gap vs Tier 3 | Simple explained | Incremental refined | Incremental expanded | Expanded residual | Explained share after expanded | Residual share of gap | Regime |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    rows: list[str] = []
    for _, row in residuals.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(row["date"]).date().isoformat(),
                    str(row["target_family"]),
                    _format_millions(row.get("gap_vs_tier3_mil")),
                    _format_millions(row.get("simple_explained_mil")),
                    _format_millions(row.get("incremental_refined_explained_mil")),
                    _format_millions(row.get("incremental_expanded_explained_mil")),
                    _format_millions(row.get("residual_after_expanded_mil")),
                    _format_millions(
                        pd.to_numeric(row.get("total_explained_share_after_expanded"), errors="coerce") * 100
                        if pd.notna(row.get("total_explained_share_after_expanded"))
                        else pd.NA
                    ),
                    _format_millions(
                        pd.to_numeric(row.get("expanded_residual_share_of_gap"), errors="coerce") * 100
                        if pd.notna(row.get("expanded_residual_share_of_gap"))
                        else pd.NA
                    ),
                    str(row.get("residual_regime")),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- `Simple explained` is the portion of the Tier 3 gap removed by the simple subtotal.",
        "- `Incremental refined` is the additional portion removed when moving from the simple to the refined subtotal.",
        "- `Incremental expanded` is the additional portion removed when moving from the refined to the expanded subtotal.",
        "- `Regime` is based on the absolute expanded residual share of the original gap.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_monetary_residual_interpretation(
    *,
    monetary_stage1_controls: pd.DataFrame,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    residuals = build_monetary_residual_interpretation(monetary_stage1_controls)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    residuals.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_monetary_residual_interpretation_markdown(residuals), encoding="utf-8")

    return csv_path, markdown_path, residuals
