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


def _materiality_label(abs_share: object) -> str:
    abs_share = pd.to_numeric(abs_share, errors="coerce")
    if pd.isna(abs_share):
        return "insufficient_data"
    value = float(abs_share)
    if value >= 0.66:
        return "major_loaded_context"
    if value >= 0.33:
        return "meaningful_loaded_context"
    return "minor_loaded_context"


def build_monetary_bank_liability_candidate_audit(
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

    decomp = decomposition.copy()
    decomp["date"] = pd.to_datetime(decomp["date"])
    decomp = decomp.set_index("date")

    index = stage0_frame.index.intersection(decomp.index).sort_values()
    if len(index) == 0:
        return pd.DataFrame()

    out = pd.DataFrame(index=index)
    out["bank_minus_liquid_target_wedge_mil"] = pd.to_numeric(
        decomp.loc[index, "bank_minus_liquid_target_wedge_mil"], errors="coerce"
    )
    out["delta_nonbank_depository_bridge_level_mil"] = pd.to_numeric(
        stage0_frame.loc[index, "delta_nonbank_depository_bridge_level_mil"], errors="coerce"
    )
    out["delta_large_time_deposits_all_commercial_banks_level_mil"] = pd.to_numeric(
        stage0_frame.loc[index, "delta_large_time_deposits_all_commercial_banks_level_mil"], errors="coerce"
    )
    out["delta_other_deposits_all_commercial_banks_level_mil"] = pd.to_numeric(
        stage0_frame.loc[index, "delta_other_deposits_all_commercial_banks_level_mil"], errors="coerce"
    )
    out["loaded_liability_context_total_mil"] = (
        out["delta_nonbank_depository_bridge_level_mil"].fillna(0.0)
        + out["delta_large_time_deposits_all_commercial_banks_level_mil"].fillna(0.0)
    )
    out["residual_bank_minus_liquid_wedge_after_loaded_liability_context_mil"] = (
        out["bank_minus_liquid_target_wedge_mil"] - out["loaded_liability_context_total_mil"]
    )
    out["nonbank_bridge_share_of_bank_minus_liquid_wedge"] = [
        _safe_share(component, total)
        for component, total in zip(
            out["delta_nonbank_depository_bridge_level_mil"],
            out["bank_minus_liquid_target_wedge_mil"],
        )
    ]
    out["large_time_share_of_bank_minus_liquid_wedge"] = [
        _safe_share(component, total)
        for component, total in zip(
            out["delta_large_time_deposits_all_commercial_banks_level_mil"],
            out["bank_minus_liquid_target_wedge_mil"],
        )
    ]
    out["other_deposits_share_of_bank_minus_liquid_wedge"] = [
        _safe_share(component, total)
        for component, total in zip(
            out["delta_other_deposits_all_commercial_banks_level_mil"],
            out["bank_minus_liquid_target_wedge_mil"],
        )
    ]
    out["loaded_liability_context_share_of_bank_minus_liquid_wedge"] = [
        _safe_share(component, total)
        for component, total in zip(
            out["loaded_liability_context_total_mil"],
            out["bank_minus_liquid_target_wedge_mil"],
        )
    ]
    out["abs_loaded_liability_context_share_of_bank_minus_liquid_wedge"] = [
        _safe_share(abs(component), abs(total))
        for component, total in zip(
            out["loaded_liability_context_total_mil"],
            out["bank_minus_liquid_target_wedge_mil"],
        )
    ]
    out["abs_residual_bank_minus_liquid_share_after_loaded_liability_context"] = [
        _safe_share(abs(component), abs(total))
        for component, total in zip(
            out["residual_bank_minus_liquid_wedge_after_loaded_liability_context_mil"],
            out["bank_minus_liquid_target_wedge_mil"],
        )
    ]
    out["loaded_liability_context_materiality"] = [
        _materiality_label(share)
        for share in out["abs_loaded_liability_context_share_of_bank_minus_liquid_wedge"]
    ]
    out.index.name = "date"
    return out.reset_index()


def render_monetary_bank_liability_candidate_audit_markdown(audit: pd.DataFrame) -> str:
    title = "# Monetary Bank Liability Candidate Audit"
    intro = (
        "Audit of the remaining bank-minus-liquid or perimeter wedge against the currently loaded bank-liability context. "
        "This artifact compares that wedge to the loaded nonbank depository bridge and the loaded large-time-deposit block together."
    )
    if audit.empty:
        return "\n".join([title, "", intro, "", "No monetary bank-liability candidate audit is available."])

    latest = audit.iloc[-1]
    summary = (
        f"Latest quarter: {pd.Timestamp(latest['date']).date().isoformat()}. "
        f"Bank-minus-liquid wedge {_format_millions(latest.get('bank_minus_liquid_target_wedge_mil'))}; "
        f"nonbank bridge {_format_millions(latest.get('delta_nonbank_depository_bridge_level_mil'))}; "
        f"large-time {_format_millions(latest.get('delta_large_time_deposits_all_commercial_banks_level_mil'))}; "
        f"other-deposits {_format_millions(latest.get('delta_other_deposits_all_commercial_banks_level_mil'))}; "
        f"loaded liability context total {_format_millions(latest.get('loaded_liability_context_total_mil'))}; "
        f"residual after loaded context {_format_millions(latest.get('residual_bank_minus_liquid_wedge_after_loaded_liability_context_mil'))}; "
        f"materiality {latest.get('loaded_liability_context_materiality')}."
    )

    header = [
        "| Quarter | Bank minus liquid wedge | Nonbank bridge | Large-time deposits | Other deposits | Loaded liability context total | Nonbank share of wedge | Large-time share of wedge | Other-deposits share of wedge | Loaded context share of wedge | Abs loaded context share | Residual after loaded context | Abs residual share after loaded context | Materiality |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    rows: list[str] = []
    for _, row in audit.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(row["date"]).date().isoformat(),
                    _format_millions(row.get("bank_minus_liquid_target_wedge_mil")),
                    _format_millions(row.get("delta_nonbank_depository_bridge_level_mil")),
                    _format_millions(row.get("delta_large_time_deposits_all_commercial_banks_level_mil")),
                    _format_millions(row.get("delta_other_deposits_all_commercial_banks_level_mil")),
                    _format_millions(row.get("loaded_liability_context_total_mil")),
                    _format_millions(
                        pd.to_numeric(row.get("nonbank_bridge_share_of_bank_minus_liquid_wedge"), errors="coerce") * 100
                        if pd.notna(row.get("nonbank_bridge_share_of_bank_minus_liquid_wedge"))
                        else pd.NA
                    ),
                    _format_millions(
                        pd.to_numeric(row.get("large_time_share_of_bank_minus_liquid_wedge"), errors="coerce") * 100
                        if pd.notna(row.get("large_time_share_of_bank_minus_liquid_wedge"))
                        else pd.NA
                    ),
                    _format_millions(
                        pd.to_numeric(row.get("other_deposits_share_of_bank_minus_liquid_wedge"), errors="coerce") * 100
                        if pd.notna(row.get("other_deposits_share_of_bank_minus_liquid_wedge"))
                        else pd.NA
                    ),
                    _format_millions(
                        pd.to_numeric(row.get("loaded_liability_context_share_of_bank_minus_liquid_wedge"), errors="coerce") * 100
                        if pd.notna(row.get("loaded_liability_context_share_of_bank_minus_liquid_wedge"))
                        else pd.NA
                    ),
                    _format_millions(
                        pd.to_numeric(row.get("abs_loaded_liability_context_share_of_bank_minus_liquid_wedge"), errors="coerce") * 100
                        if pd.notna(row.get("abs_loaded_liability_context_share_of_bank_minus_liquid_wedge"))
                        else pd.NA
                    ),
                    _format_millions(row.get("residual_bank_minus_liquid_wedge_after_loaded_liability_context_mil")),
                    _format_millions(
                        pd.to_numeric(row.get("abs_residual_bank_minus_liquid_share_after_loaded_liability_context"), errors="coerce") * 100
                        if pd.notna(row.get("abs_residual_bank_minus_liquid_share_after_loaded_liability_context"))
                        else pd.NA
                    ),
                    str(row.get("loaded_liability_context_materiality")),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- `Loaded liability context total` = nonbank depository bridge change plus large-time-deposit change.",
        "- `Other deposits` is reported separately as the best remaining public broad bank-deposit context candidate. It is not included in the loaded liability total because it is broader than a clean bank-only liquid subcomponent.",
        "- This is still a diagnostic context audit, not a signed estimator correction.",
        "- The residual after loaded context is the part of the bank-minus-liquid wedge that still lacks coverage even after the currently loaded nonbank bridge and large-time block.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_monetary_bank_liability_candidate_audit(
    *,
    monetary_stage0_diagnostics: pd.DataFrame,
    monetary_target_definition_decomposition: pd.DataFrame,
    csv_path: Path | str,
    markdown_path: Path | str,
) -> tuple[Path, Path, pd.DataFrame]:
    audit = build_monetary_bank_liability_candidate_audit(
        stage0=monetary_stage0_diagnostics,
        decomposition=monetary_target_definition_decomposition,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(csv_path, index=False)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        render_monetary_bank_liability_candidate_audit_markdown(audit),
        encoding="utf-8",
    )

    return csv_path, markdown_path, audit
