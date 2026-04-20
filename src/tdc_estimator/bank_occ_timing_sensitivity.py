from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_bank_occ_timing_sensitivity(
    estimates: pd.DataFrame,
    pilot: pd.DataFrame,
    *,
    start: str = "2022-03-31",
) -> pd.DataFrame:
    if estimates is None or estimates.empty or pilot is None or pilot.empty:
        return pd.DataFrame()

    occ = pilot.loc[pilot["pilot_bucket"].eq("occ_candidate")].copy()
    if occ.empty:
        return pd.DataFrame()

    occ["date"] = pd.to_datetime(occ["date"])
    rows: list[dict[str, object]] = []
    for _, row in occ.iterrows():
        year = pd.Timestamp(row["date"]).year
        half_amount = float(row["receipt_amt_mil"]) / 2.0
        for quarter_end in [pd.Timestamp(year=year, month=3, day=31), pd.Timestamp(year=year, month=9, day=30)]:
            rows.append(
                {
                    "date": quarter_end,
                    "occ_annual_candidate_source_year": year,
                    "occ_annual_candidate_total_mil": float(row["receipt_amt_mil"]),
                    "occ_due_date_allocated_receipt_mil": half_amount,
                }
            )

    alloc = pd.DataFrame(rows)
    alloc = (
        alloc.groupby(["date", "occ_annual_candidate_source_year", "occ_annual_candidate_total_mil"], as_index=False)[
            "occ_due_date_allocated_receipt_mil"
        ]
        .sum()
        .sort_values("date")
        .reset_index(drop=True)
    )

    out = pd.DataFrame(index=pd.DatetimeIndex(sorted(estimates.index.union(pd.to_datetime(alloc["date"]))))).sort_index()
    out["occ_due_date_allocated_receipt_mil"] = (
        alloc.set_index("date")["occ_due_date_allocated_receipt_mil"].reindex(out.index).fillna(0.0)
    )
    out["occ_annual_candidate_total_mil"] = (
        alloc.drop_duplicates("date").set_index("date")["occ_annual_candidate_total_mil"].reindex(out.index)
    )
    out["occ_annual_candidate_source_year"] = (
        alloc.drop_duplicates("date").set_index("date")["occ_annual_candidate_source_year"].reindex(out.index)
    )

    if "tdc_tier3_fiscal_corrected_bank_only_ru_flow" in estimates.columns:
        out["tdc_tier3_bank_only_plus_occ_timing_sensitivity"] = (
            estimates["tdc_tier3_fiscal_corrected_bank_only_ru_flow"].reindex(out.index)
            + out["occ_due_date_allocated_receipt_mil"]
        )
        out["tdc_tier3_bank_only_occ_timing_delta"] = out["occ_due_date_allocated_receipt_mil"]

    return out.loc[out.index >= pd.Timestamp(start)].copy()


def render_bank_occ_timing_sensitivity_markdown(sensitivity: pd.DataFrame) -> str:
    title = "# Bank OCC Timing Sensitivity"
    intro = (
        "Quarterly OCC timing sensitivity built from the annual OCC-linked bank non-tax pilot. "
        "Amounts are in millions. This artifact assumes the annual OCC candidate amount is split evenly across the two current semiannual OCC assessment due dates, "
        "March 31 and September 30, and remains a timing sensitivity rather than a default Tier 3 correction."
    )
    if sensitivity.empty:
        return "\n".join([title, "", intro, "", "No OCC-linked pilot lines are available for timing allocation."])

    nonzero = sensitivity.loc[sensitivity["occ_due_date_allocated_receipt_mil"].ne(0.0)].copy()
    latest_date = nonzero.index.max() if not nonzero.empty else sensitivity.index.max()
    latest = sensitivity.loc[latest_date]
    summary = (
        f"Latest OCC allocation quarter: {pd.Timestamp(latest_date).date().isoformat()}. "
        f"Source-year annual OCC candidate {float(latest.get('occ_annual_candidate_total_mil', 0.0)):,.3f}; "
        f"allocated quarterly receipt sensitivity {float(latest.get('occ_due_date_allocated_receipt_mil', 0.0)):,.3f}; "
        f"Tier 3 bank-only delta {float(latest.get('tdc_tier3_bank_only_occ_timing_delta', 0.0)):,.3f}."
    )

    header = [
        "| Quarter | OCC source year | OCC annual candidate | OCC allocated receipt | Tier 3 bank-only plus OCC | Delta vs default Tier 3 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    rows = []
    for date, row in sensitivity.loc[sensitivity["occ_due_date_allocated_receipt_mil"].ne(0.0)].iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(date).date().isoformat(),
                    "n/a" if pd.isna(row.get("occ_annual_candidate_source_year")) else str(int(row["occ_annual_candidate_source_year"])),
                    f"{float(row.get('occ_annual_candidate_total_mil', 0.0)):,.3f}",
                    f"{float(row.get('occ_due_date_allocated_receipt_mil', 0.0)):,.3f}",
                    "n/a"
                    if pd.isna(row.get("tdc_tier3_bank_only_plus_occ_timing_sensitivity"))
                    else f"{float(row.get('tdc_tier3_bank_only_plus_occ_timing_sensitivity', 0.0)):,.3f}",
                    "n/a"
                    if pd.isna(row.get("tdc_tier3_bank_only_occ_timing_delta"))
                    else f"{float(row.get('tdc_tier3_bank_only_occ_timing_delta', 0.0)):,.3f}",
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- Current OCC guidance states that semiannual assessments are due March 31 and September 30, based on call-report information as of December 31 and June 30, respectively.",
        "- This artifact uses those due dates only as a quarterly timing convention for the annual OCC-linked public pilot amount.",
        "- The public account-title pilot still does not prove quarterly cash timing or budget treatment tightly enough for default Tier 3 use.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_bank_occ_timing_sensitivity(
    estimates: pd.DataFrame,
    pilot: pd.DataFrame,
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    start: str = "2022-03-31",
) -> tuple[Path, Path, pd.DataFrame]:
    sensitivity = build_bank_occ_timing_sensitivity(estimates, pilot, start=start)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = sensitivity.copy()
    to_write.index.name = "date"
    to_write.to_csv(csv_path)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_bank_occ_timing_sensitivity_markdown(sensitivity), encoding="utf-8")

    return csv_path, markdown_path, sensitivity
