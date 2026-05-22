from __future__ import annotations

from pathlib import Path

import pandas as pd

from .tier3_component_crosswalk import build_tier3_component_crosswalk
from .tier3_source import build_tier3_source_diagnostics


def _read_indexed(path: Path | str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "date" not in frame.columns:
        raise ValueError(f"{path} is missing required column: date")
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.set_index("date").sort_index()


def _series(frame: pd.DataFrame, column: str, index: pd.DatetimeIndex, fill: float = 0.0) -> pd.Series:
    if frame is None or frame.empty or column not in frame.columns:
        return pd.Series(fill, index=index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").reindex(index).fillna(fill)


def _source_tier_rank(value: object) -> int:
    text = str(value)
    if "D_pdf_text_parsed" in text:
        return 1
    if "A_fiscaldata_api" in text:
        return 2
    return 0


def build_tier3_historical_vintages(
    *,
    mts_outlays_path: Path | str,
    bank_receipts_bridge: pd.DataFrame,
    bea_row_anchor: pd.DataFrame,
    mrv_overlay: pd.DataFrame | None = None,
    start: str = "2003-03-31",
) -> pd.DataFrame:
    diagnostics = build_tier3_source_diagnostics(mts_outlays_path=mts_outlays_path, start=start)
    bank = bank_receipts_bridge.copy()
    bea = bea_row_anchor.copy()
    mrv = mrv_overlay.copy() if mrv_overlay is not None else pd.DataFrame()
    for frame in [bank, bea, mrv]:
        if not frame.empty and "date" in frame.columns:
            frame["date"] = pd.to_datetime(frame["date"])
            frame.set_index("date", inplace=True)

    index = pd.DatetimeIndex(diagnostics.index.union(bank.index).union(bea.index).union(mrv.index)).sort_values()
    index = index[index >= pd.Timestamp(start)]
    out = pd.DataFrame(index=index)

    out["outlay_banks_mil"] = _series(diagnostics, "bank_noninterest_outlay_source", index)
    out["outlay_row_narrow_mil"] = _series(diagnostics, "row_outlay_default_selected", index)
    out["outlay_row_broad_sensitivity_mil"] = _series(diagnostics, "row_outlay_broad_selected", index)
    out["cashfactor_mil"] = _series(diagnostics, "mint_cb_cash_factor_source", index)
    out["receipt_banks_strict_lower_mil"] = _series(bank, "bank_corp_tax_receipts_gross_strict_depository_mil", index)
    out["receipt_banks_depository_bhc_central_mil"] = _series(bank, "bank_corp_tax_receipts_gross_depository_plus_bhc_mil", index)
    out["receipt_banks_finance_upper_mil"] = _series(bank, "bank_corp_tax_receipts_gross_finance_share_mil", index)
    bea_anchor = _series(bea, "bea_row_current_receipts_total_q_mil", index, fill=float("nan"))
    bea_anchor_available = bea_anchor.notna()
    out["receipt_row_bea_anchor_mil"] = bea_anchor
    out["receipt_row_mrv_identified_mil"] = _series(mrv, "mrv_cbsp_primary_timing_overlay_mil", index)

    source_tier = diagnostics.copy()
    out["outlay_source_tier_rank"] = source_tier.index.map(
        lambda date: _source_tier_rank(source_tier.loc[date].get("source_tier", "")) if "source_tier" in source_tier.columns and date in source_tier.index else 0
    )
    out["machine_readable_source_available"] = out.index >= pd.Timestamp("2015-03-31")
    out["historical_research_source_available"] = out.index >= pd.Timestamp(start)

    live_mask = out.index >= pd.Timestamp("2022-09-30")
    mr_mask = out["machine_readable_source_available"]
    partial_shell_correction = -out["outlay_banks_mil"] - out["outlay_row_narrow_mil"] + out["cashfactor_mil"]
    out["tier3_live_partial_shell_correction_mil"] = partial_shell_correction.where(live_mask)
    out["tier3_live_default_correction_mil"] = out["tier3_live_partial_shell_correction_mil"]
    out["tier3_machinereadable_only_correction_mil"] = (
        partial_shell_correction.where(mr_mask)
    )
    out["tier3_extended_research_correction_mil"] = (
        -out["outlay_banks_mil"]
        - out["outlay_row_narrow_mil"]
        + out["receipt_banks_depository_bhc_central_mil"]
        + out["receipt_row_bea_anchor_mil"]
        + out["cashfactor_mil"]
    ).where(bea_anchor_available)
    out["tier3_bea_anchored_research_correction_mil"] = (
        -out["outlay_banks_mil"]
        - out["outlay_row_broad_sensitivity_mil"]
        + out["receipt_banks_strict_lower_mil"]
        + out["receipt_row_bea_anchor_mil"]
        + out["cashfactor_mil"]
    ).where(bea_anchor_available)
    out["receipt_row_mrv_nonadditive_overlay_mil"] = out["receipt_row_mrv_identified_mil"]
    out["receipt_row_additive_rule"] = "bea_anchor_only_mrv_nonadditive_overlay"
    out["live_receipt_completion_status"] = "bank_and_row_receipts_missing_not_measured"
    out["live_estimator_governance_status"] = "tier2_headline_tier3_partial_shell_diagnostic"
    out["live_default_wiring_changed"] = False

    crosswalk = build_tier3_component_crosswalk().set_index("component_key")
    out["worst_component_key"] = "receipt_row_bea_anchor"
    out["worst_component_fragility_rank"] = int(crosswalk.loc["receipt_row_bea_anchor", "fragility_rank"])
    out["worst_component_fragility_note"] = str(crosswalk.loc["receipt_row_bea_anchor", "fragility_note"])
    out.loc[out.index < pd.Timestamp("2015-03-31"), "structural_break_flags"] = "pre_fiscaldata_pdf_text_history"
    out.loc[out.index >= pd.Timestamp("2015-03-31"), "structural_break_flags"] = "fiscaldata_machine_readable_window"
    out.loc[out.index >= pd.Timestamp("2022-09-30"), "structural_break_flags"] = (
        out.loc[out.index >= pd.Timestamp("2022-09-30"), "structural_break_flags"] + "|source_backed_tier3_partial_shell_boundary"
    )
    out.loc[~bea_anchor_available, "structural_break_flags"] = out.loc[~bea_anchor_available, "structural_break_flags"] + "|bea_row_anchor_missing"
    return out


def build_tier3_historical_vintages_from_paths(
    *,
    mts_outlays_path: Path | str,
    bank_receipts_bridge_path: Path | str,
    bea_row_anchor_path: Path | str,
    mrv_overlay_path: Path | str | None = None,
    start: str = "2003-03-31",
) -> pd.DataFrame:
    return build_tier3_historical_vintages(
        mts_outlays_path=mts_outlays_path,
        bank_receipts_bridge=_read_indexed(bank_receipts_bridge_path),
        bea_row_anchor=_read_indexed(bea_row_anchor_path),
        mrv_overlay=_read_indexed(mrv_overlay_path) if mrv_overlay_path is not None and Path(mrv_overlay_path).exists() else pd.DataFrame(),
        start=start,
    )


def render_tier3_historical_vintages_markdown(vintages: pd.DataFrame) -> str:
    title = "# Tier 3 Historical Vintages"
    intro = (
        "Research assembly panel for Tier 3 correction deltas relative to Tier 2. "
        "This does not promote Tier 3 as the public headline; it exposes historical vintages, the live partial shell, and component quality fields."
    )
    if vintages.empty:
        return "\n".join([title, "", intro, "", "No vintage rows are available."])

    latest_complete_index = vintages["tier3_extended_research_correction_mil"].dropna().index.max()
    latest = vintages.loc[latest_complete_index] if pd.notna(latest_complete_index) else vintages.loc[vintages.index.max()]
    latest_extended = (
        "n/a"
        if pd.isna(latest["tier3_extended_research_correction_mil"])
        else f"{float(latest['tier3_extended_research_correction_mil']):,.3f}"
    )
    latest_bea_anchored = (
        "n/a"
        if pd.isna(latest["tier3_bea_anchored_research_correction_mil"])
        else f"{float(latest['tier3_bea_anchored_research_correction_mil']):,.3f}"
    )
    summary = (
        f"Rows: {len(vintages)} from {vintages.index.min().date().isoformat()} through {vintages.index.max().date().isoformat()}. "
        f"Latest complete research quarter {pd.Timestamp(latest.name).date().isoformat()}. "
        f"Latest extended research correction {latest_extended}; "
        f"latest BEA-anchored sensitivity {latest_bea_anchored}; "
        f"worst component `{latest['worst_component_key']}`."
    )
    header = (
        "| Quarter | Live partial-shell delta | Machine-readable shell delta | Extended research delta | BEA-anchored delta | Bank receipt central | ROW BEA anchor | MRV overlay | Worst component |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"
    )
    rows = [
        "| "
        + " | ".join(
            [
                pd.Timestamp(date).date().isoformat(),
                "n/a" if pd.isna(row["tier3_live_partial_shell_correction_mil"]) else f"{float(row['tier3_live_partial_shell_correction_mil']):,.3f}",
                "n/a"
                if pd.isna(row["tier3_machinereadable_only_correction_mil"])
                else f"{float(row['tier3_machinereadable_only_correction_mil']):,.3f}",
                f"{float(row['tier3_extended_research_correction_mil']):,.3f}",
                f"{float(row['tier3_bea_anchored_research_correction_mil']):,.3f}",
                f"{float(row['receipt_banks_depository_bhc_central_mil']):,.3f}",
                f"{float(row['receipt_row_bea_anchor_mil']):,.3f}",
                f"{float(row['receipt_row_mrv_nonadditive_overlay_mil']):,.3f}",
                str(row["worst_component_key"]),
            ]
        )
        + " |"
        for date, row in vintages.iterrows()
    ]
    notes = [
        "Notes:",
        "- Live and machine-readable shell deltas are outlay-backed diagnostics; bank and ROW receipt cells are missing/not measured, not economic zero evidence.",
        "- MRV is carried as a non-additive overlay and does not increase `tier3_extended_research_correction_mil` beyond the BEA anchor.",
        "- `worst_component_key` is currently driven by payer-identity fragility, not numeric magnitude.",
    ]
    return "\n".join([title, "", intro, "", summary, "", header, *rows, "", *notes, ""])


def write_tier3_historical_vintages_from_paths(
    *,
    mts_outlays_path: Path | str,
    bank_receipts_bridge_path: Path | str,
    bea_row_anchor_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str,
    mrv_overlay_path: Path | str | None = None,
    start: str = "2003-03-31",
) -> tuple[Path, Path, pd.DataFrame]:
    vintages = build_tier3_historical_vintages_from_paths(
        mts_outlays_path=mts_outlays_path,
        bank_receipts_bridge_path=bank_receipts_bridge_path,
        bea_row_anchor_path=bea_row_anchor_path,
        mrv_overlay_path=mrv_overlay_path,
        start=start,
    )
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = vintages.copy()
    to_write.index.name = "date"
    to_write.to_csv(csv_path)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_tier3_historical_vintages_markdown(vintages), encoding="utf-8")
    return csv_path, markdown_path, vintages
