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


def _sign_alignment_label(bridge: object, wedge: object) -> str:
    bridge = pd.to_numeric(bridge, errors="coerce")
    wedge = pd.to_numeric(wedge, errors="coerce")
    if pd.isna(bridge) or pd.isna(wedge):
        return "insufficient_data"
    if float(bridge) == 0.0 or float(wedge) == 0.0:
        return "zero_or_flat"
    return "same_sign" if float(bridge) * float(wedge) > 0 else "opposite_sign"


def _materiality_label(abs_share: object) -> str:
    abs_share = pd.to_numeric(abs_share, errors="coerce")
    if pd.isna(abs_share):
        return "insufficient_data"
    value = float(abs_share)
    if value >= 0.5:
        return "major_bridge_component"
    if value >= 0.2:
        return "meaningful_bridge_component"
    return "minor_bridge_component"


def build_monetary_nonbank_depository_bridge_attribution(
    stage0: pd.DataFrame | None,
    decomposition: pd.DataFrame | None,
) -> pd.DataFrame:
    if stage0 is None or stage0.empty or decomposition is None or decomposition.empty:
        return pd.DataFrame()

    stage0_frame = stage0.copy()
    if "date" in stage0_frame.columns:
        stage0_frame["date"] = pd.to_datetime(stage0_frame["date"])
    else:
        stage0_frame = stage0_frame.reset_index(names="date")
        stage0_frame["date"] = pd.to_datetime(stage0_frame["date"])
    stage0_frame = stage0_frame.set_index("date")

    decomposition_frame = decomposition.copy()
    decomposition_frame["date"] = pd.to_datetime(decomposition_frame["date"])
    decomposition_frame = decomposition_frame.set_index("date")

    index = stage0_frame.index.intersection(decomposition_frame.index).sort_values()
    if len(index) == 0:
        return pd.DataFrame()

    out = pd.DataFrame(index=index)
    out["bank_minus_depository_target_wedge_mil"] = pd.to_numeric(
        decomposition_frame.loc[index, "bank_minus_depository_target_wedge_mil"], errors="coerce"
    )
    out["small_time_component_mil"] = pd.to_numeric(
        decomposition_frame.loc[index, "small_time_component_mil"], errors="coerce"
    )
    out["bank_minus_liquid_target_wedge_mil"] = pd.to_numeric(
        decomposition_frame.loc[index, "bank_minus_liquid_target_wedge_mil"], errors="coerce"
    )
    out["delta_credit_union_deposits_level_mil"] = pd.to_numeric(
        stage0_frame.loc[index, "delta_credit_union_deposits_level_mil"], errors="coerce"
    )
    out["delta_thrift_deposits_level_mil"] = pd.to_numeric(
        stage0_frame.loc[index, "delta_thrift_deposits_level_mil"], errors="coerce"
    )
    out["delta_nonbank_depository_bridge_level_mil"] = pd.to_numeric(
        stage0_frame.loc[index, "delta_nonbank_depository_bridge_level_mil"], errors="coerce"
    )
    out["residual_bank_minus_liquid_wedge_after_nonbank_bridge_mil"] = (
        out["bank_minus_liquid_target_wedge_mil"] - out["delta_nonbank_depository_bridge_level_mil"]
    )
    out["nonbank_depository_bridge_share_of_bank_minus_liquid_wedge"] = [
        _safe_share(bridge, wedge)
        for bridge, wedge in zip(
            out["delta_nonbank_depository_bridge_level_mil"],
            out["bank_minus_liquid_target_wedge_mil"],
        )
    ]
    out["abs_nonbank_depository_bridge_share_of_bank_minus_liquid_wedge"] = [
        _safe_share(abs(bridge), abs(wedge))
        for bridge, wedge in zip(
            out["delta_nonbank_depository_bridge_level_mil"],
            out["bank_minus_liquid_target_wedge_mil"],
        )
    ]
    out["abs_residual_bank_minus_liquid_share_after_nonbank_bridge"] = [
        _safe_share(abs(resid), abs(wedge))
        for resid, wedge in zip(
            out["residual_bank_minus_liquid_wedge_after_nonbank_bridge_mil"],
            out["bank_minus_liquid_target_wedge_mil"],
        )
    ]
    out["nonbank_bridge_sign_alignment"] = [
        _sign_alignment_label(bridge, wedge)
        for bridge, wedge in zip(
            out["delta_nonbank_depository_bridge_level_mil"],
            out["bank_minus_liquid_target_wedge_mil"],
        )
    ]
    out["nonbank_bridge_materiality"] = [
        _materiality_label(share)
        for share in out["abs_nonbank_depository_bridge_share_of_bank_minus_liquid_wedge"]
    ]
    out.index.name = "date"
    return out.reset_index()


def render_monetary_nonbank_depository_bridge_attribution_markdown(attribution: pd.DataFrame) -> str:
    title = "# Monetary Nonbank Depository Bridge Attribution"
    intro = (
        "Attribution of the bank-minus-liquid or perimeter wedge against the loaded nonbank depository bridge. "
        "This artifact uses the live NCUA plus FDIC bridge-side changes to show how much of the remaining bank-target wedge is plausibly nonbank-depository perimeter and how much remains bank-only."
    )
    if attribution.empty:
        return "\n".join([title, "", intro, "", "No monetary nonbank-depository bridge attribution is available."])

    latest = attribution.iloc[-1]
    summary = (
        f"Latest quarter: {pd.Timestamp(latest['date']).date().isoformat()}. "
        f"Bank-minus-liquid wedge {_format_millions(latest.get('bank_minus_liquid_target_wedge_mil'))}; "
        f"loaded nonbank-depository bridge {_format_millions(latest.get('delta_nonbank_depository_bridge_level_mil'))}; "
        f"residual after loaded bridge {_format_millions(latest.get('residual_bank_minus_liquid_wedge_after_nonbank_bridge_mil'))}; "
        f"materiality {latest.get('nonbank_bridge_materiality')}."
    )

    header = [
        "| Quarter | Bank minus depository wedge | Small-time component | Bank minus liquid wedge | Credit-union bridge change | Thrift bridge change | Nonbank depository bridge change | Nonbank bridge share of bank minus liquid wedge | Abs nonbank bridge share | Residual after loaded bridge | Abs residual share after loaded bridge | Sign alignment | Materiality |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    rows: list[str] = []
    for _, row in attribution.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(row["date"]).date().isoformat(),
                    _format_millions(row.get("bank_minus_depository_target_wedge_mil")),
                    _format_millions(row.get("small_time_component_mil")),
                    _format_millions(row.get("bank_minus_liquid_target_wedge_mil")),
                    _format_millions(row.get("delta_credit_union_deposits_level_mil")),
                    _format_millions(row.get("delta_thrift_deposits_level_mil")),
                    _format_millions(row.get("delta_nonbank_depository_bridge_level_mil")),
                    _format_millions(
                        pd.to_numeric(row.get("nonbank_depository_bridge_share_of_bank_minus_liquid_wedge"), errors="coerce") * 100
                        if pd.notna(row.get("nonbank_depository_bridge_share_of_bank_minus_liquid_wedge"))
                        else pd.NA
                    ),
                    _format_millions(
                        pd.to_numeric(row.get("abs_nonbank_depository_bridge_share_of_bank_minus_liquid_wedge"), errors="coerce") * 100
                        if pd.notna(row.get("abs_nonbank_depository_bridge_share_of_bank_minus_liquid_wedge"))
                        else pd.NA
                    ),
                    _format_millions(row.get("residual_bank_minus_liquid_wedge_after_nonbank_bridge_mil")),
                    _format_millions(
                        pd.to_numeric(row.get("abs_residual_bank_minus_liquid_share_after_nonbank_bridge"), errors="coerce") * 100
                        if pd.notna(row.get("abs_residual_bank_minus_liquid_share_after_nonbank_bridge"))
                        else pd.NA
                    ),
                    str(row.get("nonbank_bridge_sign_alignment")),
                    str(row.get("nonbank_bridge_materiality")),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- `Nonbank depository bridge change` = credit-union bridge change plus thrift bridge change.",
        "- This artifact does not turn the nonbank depository bridge into a signed estimator control. It uses the loaded bridge only to interpret the bank-minus-liquid or perimeter wedge.",
        "- `Residual after loaded bridge` is the remaining bank-minus-liquid wedge after subtracting the loaded nonbank depository bridge change.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_monetary_nonbank_depository_bridge_attribution(
    *,
    monetary_stage0_diagnostics: pd.DataFrame,
    monetary_target_definition_decomposition: pd.DataFrame,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    attribution = build_monetary_nonbank_depository_bridge_attribution(
        stage0=monetary_stage0_diagnostics,
        decomposition=monetary_target_definition_decomposition,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    attribution.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        render_monetary_nonbank_depository_bridge_attribution_markdown(attribution),
        encoding="utf-8",
    )

    return csv_path, markdown_path, attribution
