from __future__ import annotations

from pathlib import Path

import pandas as pd


MRV_OVERLAY_ROLE = "identified_subcomponent_or_timing_refinement_nondefault"
NON_ADDITIVE_RULE = "do_not_add_mrv_to_bea_anchor"
FY2019_BREAK_NOTE = "State monthly visa-statistics bridge is treated as FY2019+ methodology-sensitive timing evidence."


def _read_indexed_csv(path: Path | str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "date" not in frame.columns:
        raise ValueError(f"{path} is missing required column: date")
    frame["date"] = pd.to_datetime(frame["date"])
    return frame.set_index("date").sort_index()


def build_row_mrv_bea_overlay(
    bea_anchor: pd.DataFrame,
    row_state_visa_timing_sensitivity: pd.DataFrame,
    *,
    start: str = "2003-03-31",
) -> pd.DataFrame:
    if bea_anchor is None or bea_anchor.empty:
        return pd.DataFrame()

    anchor = bea_anchor.copy()
    timing = row_state_visa_timing_sensitivity.copy() if row_state_visa_timing_sensitivity is not None else pd.DataFrame()
    if "date" in anchor.columns:
        anchor["date"] = pd.to_datetime(anchor["date"])
        anchor = anchor.set_index("date")
    if not timing.empty and "date" in timing.columns:
        timing["date"] = pd.to_datetime(timing["date"])
        timing = timing.set_index("date")

    out = pd.DataFrame(index=pd.DatetimeIndex(anchor.index).sort_values())
    out["bea_row_current_receipts_total_q_mil"] = pd.to_numeric(
        anchor.get("bea_row_current_receipts_total_q_mil"),
        errors="coerce",
    )

    timing_columns = {
        "row_state_mrv_cbsp_allocated_receipt_mil": "mrv_cbsp_primary_timing_overlay_mil",
        "row_state_visa_secondary_allocated_receipt_mil": "mrv_secondary_visa_timing_overlay_mil",
        "row_state_visa_total_allocated_receipt_mil": "mrv_total_visa_timing_overlay_mil",
    }
    for source_col, out_col in timing_columns.items():
        if not timing.empty and source_col in timing.columns:
            out[out_col] = pd.to_numeric(timing[source_col], errors="coerce").reindex(out.index).fillna(0.0)
        else:
            out[out_col] = 0.0

    if not timing.empty and "state_mrv_source_fiscal_year" in timing.columns:
        out["state_mrv_source_fiscal_year"] = pd.to_numeric(timing["state_mrv_source_fiscal_year"], errors="coerce").reindex(out.index)
    else:
        out["state_mrv_source_fiscal_year"] = pd.NA

    denominator = out["bea_row_current_receipts_total_q_mil"].where(out["bea_row_current_receipts_total_q_mil"].ne(0))
    out["mrv_primary_share_of_bea_row_anchor"] = out["mrv_cbsp_primary_timing_overlay_mil"] / denominator
    out["mrv_total_visa_share_of_bea_row_anchor"] = out["mrv_total_visa_timing_overlay_mil"] / denominator
    out["non_additive_bea_anchor_total_q_mil"] = out["bea_row_current_receipts_total_q_mil"]
    out["additive_bea_plus_mrv_total_q_mil"] = pd.NA
    out["mrv_overlay_role"] = MRV_OVERLAY_ROLE
    out["non_additive_rule"] = NON_ADDITIVE_RULE
    out["default_eligible"] = False
    out["fy2019_plus_visa_methodology_break"] = out["state_mrv_source_fiscal_year"].ge(2019).fillna(False).astype(bool)
    out["visa_methodology_break_note"] = out["fy2019_plus_visa_methodology_break"].map(
        {True: FY2019_BREAK_NOTE, False: "No FY2019+ State visa timing bridge is loaded for this quarter."}
    )
    out["overlay_status"] = "pass_non_additive_overlay"
    out.loc[
        out["mrv_total_visa_timing_overlay_mil"].gt(out["bea_row_current_receipts_total_q_mil"]),
        "overlay_status",
    ] = "warn_mrv_total_exceeds_bea_anchor"
    return out.loc[out.index >= pd.Timestamp(start)].copy()


def build_row_mrv_bea_overlay_from_paths(
    *,
    bea_anchor_path: Path | str,
    row_state_visa_timing_sensitivity_path: Path | str,
    start: str = "2003-03-31",
) -> pd.DataFrame:
    bea_anchor = _read_indexed_csv(bea_anchor_path)
    timing = _read_indexed_csv(row_state_visa_timing_sensitivity_path)
    return build_row_mrv_bea_overlay(bea_anchor, timing, start=start)


def render_row_mrv_bea_overlay_markdown(overlay: pd.DataFrame) -> str:
    title = "# ROW MRV BEA Overlay"
    intro = (
        "Nondefault MRV / CBSP overlay against the BEA/NIPA ROW federal receipts anchor. "
        "MRV is treated only as an identified subcomponent or timing refinement candidate; "
        "the non-additive anchor total remains the BEA anchor."
    )
    if overlay.empty:
        return "\n".join([title, "", intro, "", "No BEA anchor and MRV timing overlap is available."])

    nonzero = overlay.loc[overlay["mrv_total_visa_timing_overlay_mil"].ne(0.0)]
    latest_date = nonzero.index.max() if not nonzero.empty else overlay.index.max()
    latest = overlay.loc[latest_date]
    status_counts = overlay["overlay_status"].value_counts(dropna=False).to_dict()
    summary = (
        f"Latest MRV overlay quarter: {pd.Timestamp(latest_date).date().isoformat()}. "
        f"BEA anchor {float(latest['bea_row_current_receipts_total_q_mil']):,.3f}; "
        f"MRV primary overlay {float(latest['mrv_cbsp_primary_timing_overlay_mil']):,.3f}; "
        f"primary share {float(latest['mrv_primary_share_of_bea_row_anchor']):.3%}; "
        f"non-additive rule `{latest['non_additive_rule']}`."
    )

    header = [
        "| Quarter | BEA anchor | MRV primary overlay | Secondary visa overlay | MRV total overlay | MRV / BEA anchor | FY2019+ break | Status |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    rows = []
    for date, row in nonzero.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(date).date().isoformat(),
                    f"{float(row['bea_row_current_receipts_total_q_mil']):,.3f}",
                    f"{float(row['mrv_cbsp_primary_timing_overlay_mil']):,.3f}",
                    f"{float(row['mrv_secondary_visa_timing_overlay_mil']):,.3f}",
                    f"{float(row['mrv_total_visa_timing_overlay_mil']):,.3f}",
                    f"{float(row['mrv_primary_share_of_bea_row_anchor']):.3%}",
                    str(bool(row["fy2019_plus_visa_methodology_break"])),
                    str(row["overlay_status"]),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        f"- Overlay status counts: {status_counts}.",
        "- `additive_bea_plus_mrv_total_q_mil` is intentionally blank because MRV is not added to the BEA anchor.",
        "- FY2019+ State visa timing rows carry a methodology-break flag so downstream research can avoid smoothing across that boundary without review.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_row_mrv_bea_overlay_from_paths(
    *,
    bea_anchor_path: Path | str,
    row_state_visa_timing_sensitivity_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str,
    start: str = "2003-03-31",
) -> tuple[Path, Path, pd.DataFrame]:
    overlay = build_row_mrv_bea_overlay_from_paths(
        bea_anchor_path=bea_anchor_path,
        row_state_visa_timing_sensitivity_path=row_state_visa_timing_sensitivity_path,
        start=start,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = overlay.copy()
    to_write.index.name = "date"
    to_write.to_csv(csv_path)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_row_mrv_bea_overlay_markdown(overlay), encoding="utf-8")
    return csv_path, markdown_path, overlay
