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


def _dominance_label(share: object) -> str:
    share = pd.to_numeric(share, errors="coerce")
    if pd.isna(share):
        return "insufficient_data"
    value = abs(float(share))
    if value >= 0.66:
        return "bank_target_wedge_dominant"
    if value >= 0.33:
        return "mixed_shared_and_bank_specific"
    return "shared_residual_dominant"


def build_monetary_target_wedge(controls: pd.DataFrame | None) -> pd.DataFrame:
    if controls is None or controls.empty:
        return pd.DataFrame()

    frame = pd.DataFrame(index=controls.index)
    frame["depository_target_change_mil"] = pd.to_numeric(
        controls.get("delta_depository_target_level_mil"), errors="coerce"
    )
    frame["commercial_bank_deposit_target_change_mil"] = pd.to_numeric(
        controls.get("delta_commercial_bank_deposits_level_mil"), errors="coerce"
    )
    frame["bank_minus_depository_target_wedge_mil"] = (
        frame["commercial_bank_deposit_target_change_mil"] - frame["depository_target_change_mil"]
    )
    frame["depository_gap_vs_tier3_mil"] = pd.to_numeric(
        controls.get("depository_target_minus_tier3_bank_only_flow_mil"), errors="coerce"
    )
    frame["bank_gap_vs_tier3_mil"] = pd.to_numeric(
        controls.get("commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil"), errors="coerce"
    )
    frame["gap_wedge_vs_tier3_mil"] = frame["bank_gap_vs_tier3_mil"] - frame["depository_gap_vs_tier3_mil"]
    frame["depository_residual_after_expanded_mil"] = pd.to_numeric(
        controls.get("depository_target_minus_tier3_bank_only_flow_mil_minus_expanded_controls_mil"),
        errors="coerce",
    )
    frame["bank_residual_after_expanded_mil"] = pd.to_numeric(
        controls.get("commercial_bank_deposit_target_minus_tier3_bank_only_flow_mil_minus_expanded_controls_mil"),
        errors="coerce",
    )
    frame["bank_specific_residual_wedge_mil"] = (
        frame["bank_residual_after_expanded_mil"] - frame["depository_residual_after_expanded_mil"]
    )
    frame["bank_specific_residual_share_of_bank_residual"] = [
        _safe_share(wedge, bank_resid)
        for wedge, bank_resid in zip(
            frame["bank_specific_residual_wedge_mil"],
            frame["bank_residual_after_expanded_mil"],
        )
    ]
    frame["shared_depository_residual_share_of_bank_residual"] = [
        _safe_share(dep_resid, bank_resid)
        for dep_resid, bank_resid in zip(
            frame["depository_residual_after_expanded_mil"],
            frame["bank_residual_after_expanded_mil"],
        )
    ]
    frame["bank_wedge_dominance"] = frame["bank_specific_residual_share_of_bank_residual"].map(_dominance_label)

    for col in [
        "delta_commercial_bank_cash_assets_mil",
        "delta_foreign_official_custody_treasuries_mil",
        "delta_foreign_related_treasury_agency_non_mbs_mil",
        "delta_tga_weekly_level_mil",
    ]:
        if col in controls.columns:
            frame[col] = pd.to_numeric(controls[col], errors="coerce")

    frame = frame.dropna(
        subset=[
            "bank_minus_depository_target_wedge_mil",
            "bank_specific_residual_wedge_mil",
        ],
        how="all",
    )
    frame.index.name = "date"
    return frame.reset_index()


def render_monetary_target_wedge_markdown(wedge: pd.DataFrame) -> str:
    title = "# Monetary Target Wedge"
    intro = (
        "Target-wedge diagnostic for the monetary residual system. "
        "This artifact explains how much of the unresolved commercial-bank-deposit residual is shared with the depository target, "
        "and how much is a bank-target-specific wedge that survives the expanded Stage 1 controls."
    )
    if wedge.empty:
        return "\n".join([title, "", intro, "", "No monetary target wedge diagnostic is available."])

    latest = wedge.iloc[-1]
    summary = (
        f"Latest quarter: {pd.Timestamp(latest['date']).date().isoformat()}. "
        f"Bank-minus-depository target wedge {_format_millions(latest.get('bank_minus_depository_target_wedge_mil'))}; "
        f"depository residual after expanded controls {_format_millions(latest.get('depository_residual_after_expanded_mil'))}; "
        f"bank residual after expanded controls {_format_millions(latest.get('bank_residual_after_expanded_mil'))}; "
        f"bank-specific residual wedge {_format_millions(latest.get('bank_specific_residual_wedge_mil'))}; "
        f"dominance {latest.get('bank_wedge_dominance')}."
    )

    header = [
        "| Quarter | Bank minus depository target wedge | Depository residual after expanded | Bank residual after expanded | Bank-specific residual wedge | Bank-specific share of bank residual | Shared depository share of bank residual | Dominance | Bank cash-assets context | Foreign custody context | Foreign-related bank Tsy/agency context | TGA context |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    rows: list[str] = []
    for _, row in wedge.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(row["date"]).date().isoformat(),
                    _format_millions(row.get("bank_minus_depository_target_wedge_mil")),
                    _format_millions(row.get("depository_residual_after_expanded_mil")),
                    _format_millions(row.get("bank_residual_after_expanded_mil")),
                    _format_millions(row.get("bank_specific_residual_wedge_mil")),
                    _format_millions(
                        pd.to_numeric(row.get("bank_specific_residual_share_of_bank_residual"), errors="coerce") * 100
                        if pd.notna(row.get("bank_specific_residual_share_of_bank_residual"))
                        else pd.NA
                    ),
                    _format_millions(
                        pd.to_numeric(
                            row.get("shared_depository_residual_share_of_bank_residual"), errors="coerce"
                        )
                        * 100
                        if pd.notna(row.get("shared_depository_residual_share_of_bank_residual"))
                        else pd.NA
                    ),
                    str(row.get("bank_wedge_dominance")),
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
        "- `Bank-specific residual wedge` = bank residual after expanded controls minus depository residual after expanded controls.",
        "- Because the Stage 1 controls are applied symmetrically, this wedge isolates the part of the unresolved bank residual that is specific to the bank target rather than shared with the depository target.",
        "- Context columns are included to help interpret that wedge, but they are not part of the signed Stage 1 subtotals.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_monetary_target_wedge(
    *,
    monetary_stage1_controls: pd.DataFrame,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    wedge = build_monetary_target_wedge(monetary_stage1_controls)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    wedge.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_monetary_target_wedge_markdown(wedge), encoding="utf-8")

    return csv_path, markdown_path, wedge
