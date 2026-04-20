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


def _component_dominance_label(small_time_share: object, bank_minus_liquid_share: object) -> str:
    small_time_share = pd.to_numeric(small_time_share, errors="coerce")
    bank_minus_liquid_share = pd.to_numeric(bank_minus_liquid_share, errors="coerce")
    if pd.isna(small_time_share) or pd.isna(bank_minus_liquid_share):
        return "insufficient_data"
    if float(bank_minus_liquid_share) >= 0.66:
        return "bank_minus_liquid_component_dominant"
    if float(small_time_share) >= 0.66:
        return "small_time_component_dominant"
    return "mixed_target_definition_components"


def build_monetary_target_definition_decomposition(bridge: pd.DataFrame | None) -> pd.DataFrame:
    if bridge is None or bridge.empty:
        return pd.DataFrame()

    frame = bridge.copy()
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"])
    else:
        frame = frame.reset_index(names="date")
        frame["date"] = pd.to_datetime(frame["date"])

    out = pd.DataFrame()
    out["date"] = frame["date"]
    out["bank_minus_depository_target_wedge_mil"] = pd.to_numeric(
        frame.get("bank_minus_depository_target_wedge_mil"), errors="coerce"
    )
    out["small_time_component_mil"] = pd.to_numeric(frame.get("small_time_component_mil"), errors="coerce")
    out["bank_minus_liquid_target_wedge_mil"] = pd.to_numeric(
        frame.get("bank_minus_liquid_target_wedge_mil"), errors="coerce"
    )
    out["bank_specific_residual_wedge_mil"] = pd.to_numeric(
        frame.get("bank_specific_residual_wedge_mil"), errors="coerce"
    )
    out["small_time_share_of_target_wedge"] = [
        _safe_share(component, total)
        for component, total in zip(
            out["small_time_component_mil"],
            out["bank_minus_depository_target_wedge_mil"],
        )
    ]
    out["bank_minus_liquid_share_of_target_wedge"] = [
        _safe_share(component, total)
        for component, total in zip(
            out["bank_minus_liquid_target_wedge_mil"],
            out["bank_minus_depository_target_wedge_mil"],
        )
    ]

    abs_component_sum = (
        out["small_time_component_mil"].abs() + out["bank_minus_liquid_target_wedge_mil"].abs()
    )
    out["abs_small_time_share_of_components"] = [
        _safe_share(component, total)
        for component, total in zip(
            out["small_time_component_mil"].abs(),
            abs_component_sum,
        )
    ]
    out["abs_bank_minus_liquid_share_of_components"] = [
        _safe_share(component, total)
        for component, total in zip(
            out["bank_minus_liquid_target_wedge_mil"].abs(),
            abs_component_sum,
        )
    ]
    out["target_definition_component_dominance"] = [
        _component_dominance_label(small_time_share, bank_minus_liquid_share)
        for small_time_share, bank_minus_liquid_share in zip(
            out["abs_small_time_share_of_components"],
            out["abs_bank_minus_liquid_share_of_components"],
        )
    ]
    out["bank_minus_liquid_component_net_of_small_time_mil"] = out["bank_minus_liquid_target_wedge_mil"]
    return out


def render_monetary_target_definition_decomposition_markdown(decomposition: pd.DataFrame) -> str:
    title = "# Monetary Target Definition Decomposition"
    intro = (
        "Decomposition of the bank-minus-depository target-definition wedge. "
        "This artifact splits that wedge into the small-time-deposit component and the residual bank-minus-liquid/perimeter component."
    )
    if decomposition.empty:
        return "\n".join([title, "", intro, "", "No monetary target-definition decomposition is available."])

    latest = decomposition.iloc[-1]
    summary = (
        f"Latest quarter: {pd.Timestamp(latest['date']).date().isoformat()}. "
        f"Bank-minus-depository wedge {_format_millions(latest.get('bank_minus_depository_target_wedge_mil'))}; "
        f"small-time component {_format_millions(latest.get('small_time_component_mil'))}; "
        f"bank-minus-liquid component {_format_millions(latest.get('bank_minus_liquid_target_wedge_mil'))}; "
        f"dominance {latest.get('target_definition_component_dominance')}."
    )

    header = [
        "| Quarter | Bank minus depository wedge | Small-time component | Bank minus liquid component | Small-time share of wedge | Bank minus liquid share of wedge | Abs small-time share of components | Abs bank minus liquid share of components | Dominance |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    rows: list[str] = []
    for _, row in decomposition.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(row["date"]).date().isoformat(),
                    _format_millions(row.get("bank_minus_depository_target_wedge_mil")),
                    _format_millions(row.get("small_time_component_mil")),
                    _format_millions(row.get("bank_minus_liquid_target_wedge_mil")),
                    _format_millions(
                        pd.to_numeric(row.get("small_time_share_of_target_wedge"), errors="coerce") * 100
                        if pd.notna(row.get("small_time_share_of_target_wedge"))
                        else pd.NA
                    ),
                    _format_millions(
                        pd.to_numeric(row.get("bank_minus_liquid_share_of_target_wedge"), errors="coerce") * 100
                        if pd.notna(row.get("bank_minus_liquid_share_of_target_wedge"))
                        else pd.NA
                    ),
                    _format_millions(
                        pd.to_numeric(row.get("abs_small_time_share_of_components"), errors="coerce") * 100
                        if pd.notna(row.get("abs_small_time_share_of_components"))
                        else pd.NA
                    ),
                    _format_millions(
                        pd.to_numeric(row.get("abs_bank_minus_liquid_share_of_components"), errors="coerce") * 100
                        if pd.notna(row.get("abs_bank_minus_liquid_share_of_components"))
                        else pd.NA
                    ),
                    str(row.get("target_definition_component_dominance")),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- `Bank minus depository wedge` = commercial-bank-deposit target change minus depository target change.",
        "- `Bank minus liquid component` is the residual bank-target/perimeter wedge after removing the small-time component.",
        "- Absolute component shares use absolute values so opposite-signed small-time moves do not hide the dominant structural component.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_monetary_target_definition_decomposition(
    *,
    monetary_target_definition_bridge: pd.DataFrame,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    decomposition = build_monetary_target_definition_decomposition(monetary_target_definition_bridge)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    decomposition.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        render_monetary_target_definition_decomposition_markdown(decomposition),
        encoding="utf-8",
    )

    return csv_path, markdown_path, decomposition
