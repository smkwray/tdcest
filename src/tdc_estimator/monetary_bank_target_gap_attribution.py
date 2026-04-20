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


def _dominance_label(shared_share: object, small_time_share: object, perimeter_share: object) -> str:
    components = {
        "shared_depository_component_dominant": pd.to_numeric(shared_share, errors="coerce"),
        "small_time_component_dominant": pd.to_numeric(small_time_share, errors="coerce"),
        "bank_minus_liquid_component_dominant": pd.to_numeric(perimeter_share, errors="coerce"),
    }
    clean = {k: float(v) for k, v in components.items() if pd.notna(v)}
    if len(clean) < 3:
        return "insufficient_data"
    label, value = max(clean.items(), key=lambda item: item[1])
    if value >= 0.5:
        return label
    return "mixed_bank_residual_components"


def build_monetary_bank_target_gap_attribution(
    residuals: pd.DataFrame | None,
    decomposition: pd.DataFrame | None,
) -> pd.DataFrame:
    if residuals is None or residuals.empty or decomposition is None or decomposition.empty:
        return pd.DataFrame()

    residual_frame = residuals.copy()
    residual_frame["date"] = pd.to_datetime(residual_frame["date"])
    residual_map = residual_frame.pivot(index="date", columns="target_family")
    if ("gap_vs_tier3_mil", "depository_target") not in residual_map.columns or (
        "gap_vs_tier3_mil",
        "commercial_bank_deposit_target",
    ) not in residual_map.columns:
        return pd.DataFrame()

    decomp = decomposition.copy()
    decomp["date"] = pd.to_datetime(decomp["date"])
    decomp = decomp.set_index("date")

    index = residual_map.index.intersection(decomp.index).sort_values()
    if len(index) == 0:
        return pd.DataFrame()

    out = pd.DataFrame(index=index)
    out["depository_gap_vs_tier3_mil"] = pd.to_numeric(
        residual_map.loc[index, ("gap_vs_tier3_mil", "depository_target")], errors="coerce"
    )
    out["bank_gap_vs_tier3_mil"] = pd.to_numeric(
        residual_map.loc[index, ("gap_vs_tier3_mil", "commercial_bank_deposit_target")], errors="coerce"
    )
    out["depository_residual_after_expanded_mil"] = pd.to_numeric(
        residual_map.loc[index, ("residual_after_expanded_mil", "depository_target")], errors="coerce"
    )
    out["bank_residual_after_expanded_mil"] = pd.to_numeric(
        residual_map.loc[index, ("residual_after_expanded_mil", "commercial_bank_deposit_target")], errors="coerce"
    )
    out["small_time_component_mil"] = pd.to_numeric(decomp.loc[index, "small_time_component_mil"], errors="coerce")
    out["bank_minus_liquid_target_wedge_mil"] = pd.to_numeric(
        decomp.loc[index, "bank_minus_liquid_target_wedge_mil"], errors="coerce"
    )
    out["bank_specific_residual_wedge_mil"] = pd.to_numeric(
        decomp.loc[index, "bank_specific_residual_wedge_mil"], errors="coerce"
    )

    out["reconstructed_bank_gap_mil"] = (
        out["depository_gap_vs_tier3_mil"]
        + out["small_time_component_mil"]
        + out["bank_minus_liquid_target_wedge_mil"]
    )
    out["bank_gap_reconstruction_error_mil"] = out["bank_gap_vs_tier3_mil"] - out["reconstructed_bank_gap_mil"]
    out["reconstructed_bank_residual_mil"] = (
        out["depository_residual_after_expanded_mil"] + out["bank_specific_residual_wedge_mil"]
    )
    out["bank_residual_reconstruction_error_mil"] = (
        out["bank_residual_after_expanded_mil"] - out["reconstructed_bank_residual_mil"]
    )

    out["shared_depository_share_of_bank_residual"] = [
        _safe_share(shared, total)
        for shared, total in zip(
            out["depository_residual_after_expanded_mil"],
            out["bank_residual_after_expanded_mil"],
        )
    ]
    out["small_time_share_of_bank_residual"] = [
        _safe_share(component, total)
        for component, total in zip(
            out["small_time_component_mil"],
            out["bank_residual_after_expanded_mil"],
        )
    ]
    out["bank_minus_liquid_share_of_bank_residual"] = [
        _safe_share(component, total)
        for component, total in zip(
            out["bank_minus_liquid_target_wedge_mil"],
            out["bank_residual_after_expanded_mil"],
        )
    ]
    out["bank_residual_component_dominance"] = [
        _dominance_label(shared, small_time, perimeter)
        for shared, small_time, perimeter in zip(
            out["shared_depository_share_of_bank_residual"],
            out["small_time_share_of_bank_residual"],
            out["bank_minus_liquid_share_of_bank_residual"],
        )
    ]

    out.index.name = "date"
    return out.reset_index()


def render_monetary_bank_target_gap_attribution_markdown(attribution: pd.DataFrame) -> str:
    title = "# Monetary Bank Target Gap Attribution"
    intro = (
        "Additive attribution of the commercial-bank-deposit target gap and residual. "
        "This artifact shows how much of the bank gap is shared with the depository target, how much comes from the small-time subtraction, and how much comes from the residual bank-minus-liquid/perimeter wedge."
    )
    if attribution.empty:
        return "\n".join([title, "", intro, "", "No monetary bank-target gap attribution is available."])

    latest = attribution.iloc[-1]
    summary = (
        f"Latest quarter: {pd.Timestamp(latest['date']).date().isoformat()}. "
        f"Bank gap {_format_millions(latest.get('bank_gap_vs_tier3_mil'))} = shared depository gap {_format_millions(latest.get('depository_gap_vs_tier3_mil'))} + "
        f"small-time {_format_millions(latest.get('small_time_component_mil'))} + "
        f"bank-minus-liquid/perimeter {_format_millions(latest.get('bank_minus_liquid_target_wedge_mil'))}. "
        f"Bank residual after expanded controls {_format_millions(latest.get('bank_residual_after_expanded_mil'))}; "
        f"dominance {latest.get('bank_residual_component_dominance')}."
    )

    header = [
        "| Quarter | Bank gap vs Tier 3 | Shared depository gap | Small-time component | Bank minus liquid component | Bank residual after expanded | Shared depository residual | Small-time share of bank residual | Bank minus liquid share of bank residual | Dominance | Gap reconstruction error | Residual reconstruction error |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |",
    ]
    rows: list[str] = []
    for _, row in attribution.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(row["date"]).date().isoformat(),
                    _format_millions(row.get("bank_gap_vs_tier3_mil")),
                    _format_millions(row.get("depository_gap_vs_tier3_mil")),
                    _format_millions(row.get("small_time_component_mil")),
                    _format_millions(row.get("bank_minus_liquid_target_wedge_mil")),
                    _format_millions(row.get("bank_residual_after_expanded_mil")),
                    _format_millions(row.get("depository_residual_after_expanded_mil")),
                    _format_millions(
                        pd.to_numeric(row.get("small_time_share_of_bank_residual"), errors="coerce") * 100
                        if pd.notna(row.get("small_time_share_of_bank_residual"))
                        else pd.NA
                    ),
                    _format_millions(
                        pd.to_numeric(row.get("bank_minus_liquid_share_of_bank_residual"), errors="coerce") * 100
                        if pd.notna(row.get("bank_minus_liquid_share_of_bank_residual"))
                        else pd.NA
                    ),
                    str(row.get("bank_residual_component_dominance")),
                    _format_millions(row.get("bank_gap_reconstruction_error_mil")),
                    _format_millions(row.get("bank_residual_reconstruction_error_mil")),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- `Shared depository gap` is the part of the bank gap already present in the preferred depository target.",
        "- `Small-time component` and `bank minus liquid component` together make up the target-definition wedge on top of that shared depository gap.",
        "- `Bank residual after expanded` should reconstruct to shared depository residual plus the bank-specific wedge when the target-definition bridge holds.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_monetary_bank_target_gap_attribution(
    *,
    monetary_residual_interpretation: pd.DataFrame,
    monetary_target_definition_decomposition: pd.DataFrame,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    attribution = build_monetary_bank_target_gap_attribution(
        residuals=monetary_residual_interpretation,
        decomposition=monetary_target_definition_decomposition,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    attribution.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_monetary_bank_target_gap_attribution_markdown(attribution), encoding="utf-8")

    return csv_path, markdown_path, attribution
