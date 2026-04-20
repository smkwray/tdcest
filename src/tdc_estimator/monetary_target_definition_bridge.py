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


def _alignment_label(value: object) -> str:
    value = pd.to_numeric(value, errors="coerce")
    if pd.isna(value):
        return "insufficient_data"
    if abs(float(value)) <= 1e-6:
        return "wedge_matches_target_definition"
    return "wedge_not_fully_explained_by_target_definition"


def build_monetary_target_definition_bridge(
    stage0: pd.DataFrame | None,
    wedge: pd.DataFrame | None,
) -> pd.DataFrame:
    if stage0 is None or stage0.empty or wedge is None or wedge.empty:
        return pd.DataFrame()

    stage0_frame = stage0.copy()
    if "date" in stage0_frame.columns:
        stage0_frame["date"] = pd.to_datetime(stage0_frame["date"])
        stage0_frame = stage0_frame.set_index("date")
    else:
        stage0_frame.index = pd.to_datetime(stage0_frame.index)

    wedge_frame = wedge.copy()
    wedge_frame["date"] = pd.to_datetime(wedge_frame["date"])
    wedge_frame = wedge_frame.set_index("date")

    index = stage0_frame.index.intersection(wedge_frame.index).sort_values()
    if len(index) == 0:
        return pd.DataFrame()

    out = pd.DataFrame(index=index)
    out["partial_target_change_mil"] = pd.to_numeric(
        stage0_frame.reindex(index)["delta_partial_m2_less_currency_level_mil"], errors="coerce"
    )
    out["depository_target_change_mil"] = pd.to_numeric(
        stage0_frame.reindex(index)["delta_depository_target_level_mil"], errors="coerce"
    )
    out["liquid_target_change_mil"] = pd.to_numeric(
        stage0_frame.reindex(index)["delta_liquid_deposit_target_level_mil"], errors="coerce"
    )
    out["commercial_bank_target_change_mil"] = pd.to_numeric(
        stage0_frame.reindex(index)["delta_commercial_bank_deposits_level_mil"], errors="coerce"
    )

    out["retail_mmf_component_mil"] = out["partial_target_change_mil"] - out["depository_target_change_mil"]
    out["small_time_component_mil"] = out["liquid_target_change_mil"] - out["depository_target_change_mil"]
    out["bank_minus_depository_target_wedge_mil"] = (
        out["commercial_bank_target_change_mil"] - out["depository_target_change_mil"]
    )
    out["bank_minus_liquid_target_wedge_mil"] = out["commercial_bank_target_change_mil"] - out["liquid_target_change_mil"]

    out["bank_specific_residual_wedge_mil"] = pd.to_numeric(
        wedge_frame.reindex(index)["bank_specific_residual_wedge_mil"], errors="coerce"
    )
    out["depository_residual_after_expanded_mil"] = pd.to_numeric(
        wedge_frame.reindex(index)["depository_residual_after_expanded_mil"], errors="coerce"
    )
    out["bank_residual_after_expanded_mil"] = pd.to_numeric(
        wedge_frame.reindex(index)["bank_residual_after_expanded_mil"], errors="coerce"
    )
    out["wedge_alignment_gap_mil"] = (
        out["bank_specific_residual_wedge_mil"] - out["bank_minus_depository_target_wedge_mil"]
    )
    out["bank_wedge_alignment_status"] = out["wedge_alignment_gap_mil"].map(_alignment_label)
    out["bank_wedge_share_of_bank_target_change"] = [
        _safe_share(wedge_val, bank_target)
        for wedge_val, bank_target in zip(
            out["bank_minus_depository_target_wedge_mil"],
            out["commercial_bank_target_change_mil"],
        )
    ]

    out = out.dropna(
        subset=[
            "bank_minus_depository_target_wedge_mil",
            "bank_specific_residual_wedge_mil",
        ],
        how="all",
    )
    out.index.name = "date"
    return out.reset_index()


def render_monetary_target_definition_bridge_markdown(bridge: pd.DataFrame) -> str:
    title = "# Monetary Target Definition Bridge"
    intro = (
        "Target-definition bridge for the monetary diagnostic. "
        "This artifact checks whether the unresolved commercial-bank-deposit residual is fundamentally the same object as the raw bank-minus-depository target wedge."
    )
    if bridge.empty:
        return "\n".join([title, "", intro, "", "No monetary target-definition bridge is available."])

    latest = bridge.iloc[-1]
    summary = (
        f"Latest quarter: {pd.Timestamp(latest['date']).date().isoformat()}. "
        f"Retail MMF component {_format_millions(latest.get('retail_mmf_component_mil'))}; "
        f"small-time component {_format_millions(latest.get('small_time_component_mil'))}; "
        f"bank-minus-depository wedge {_format_millions(latest.get('bank_minus_depository_target_wedge_mil'))}; "
        f"bank-specific residual wedge {_format_millions(latest.get('bank_specific_residual_wedge_mil'))}; "
        f"alignment status {latest.get('bank_wedge_alignment_status')}."
    )

    header = [
        "| Quarter | Retail MMF component | Small-time component | Bank minus depository wedge | Bank minus liquid wedge | Bank-specific residual wedge | Alignment gap | Alignment status | Bank wedge share of bank target change |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    rows: list[str] = []
    for _, row in bridge.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(row["date"]).date().isoformat(),
                    _format_millions(row.get("retail_mmf_component_mil")),
                    _format_millions(row.get("small_time_component_mil")),
                    _format_millions(row.get("bank_minus_depository_target_wedge_mil")),
                    _format_millions(row.get("bank_minus_liquid_target_wedge_mil")),
                    _format_millions(row.get("bank_specific_residual_wedge_mil")),
                    _format_millions(row.get("wedge_alignment_gap_mil")),
                    str(row.get("bank_wedge_alignment_status")),
                    _format_millions(
                        pd.to_numeric(row.get("bank_wedge_share_of_bank_target_change"), errors="coerce") * 100
                        if pd.notna(row.get("bank_wedge_share_of_bank_target_change"))
                        else pd.NA
                    ),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- `Retail MMF component` is the difference between the partial and depository targets.",
        "- `Small-time component` is the difference between the liquid and depository targets.",
        "- `Alignment gap` = bank-specific residual wedge minus raw bank-minus-depository target wedge.",
        "- When the alignment gap is zero, the unresolved bank residual is behaving like a target-definition wedge rather than an omitted Stage 1 control.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_monetary_target_definition_bridge(
    *,
    monetary_stage0_diagnostics: pd.DataFrame,
    monetary_target_wedge: pd.DataFrame,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    bridge = build_monetary_target_definition_bridge(
        stage0=monetary_stage0_diagnostics,
        wedge=monetary_target_wedge,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    bridge.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_monetary_target_definition_bridge_markdown(bridge), encoding="utf-8")

    return csv_path, markdown_path, bridge
