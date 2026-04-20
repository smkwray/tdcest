from __future__ import annotations

from pathlib import Path

import pandas as pd


STRICT_MRV_LINE = "Consular and Border Security Programs, Machine Readable Visa Fee, State"
STRICT_IV_LINES = {
    "Consular and Border Security Programs, Immigrant Visa Security Surcharge, State",
    "Consular and Border Security Programs, Diversity Visa Lottery Fee, State",
}
PRIMARY_BUCKETS = {"mrv_cbsp_primary_candidate", "strict_state_visa_candidate"}
SECONDARY_BUCKETS = {"state_visa_secondary_sensitivity"}
DEFAULT_BLOCKER = "no_public_debited_account_or_actual_cash_payer_proof"


def _load_state_visa_monthly(path: Path | str) -> pd.DataFrame:
    df = pd.read_csv(path).copy()
    required = {"date", "fiscal_year", "niv_issuances_total", "iv_issuances_total"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"State visa monthly file {path} is missing required columns: {missing}")
    df["date"] = pd.to_datetime(df["date"])
    df["fiscal_year"] = pd.to_numeric(df["fiscal_year"], errors="raise").astype(int)
    df["niv_issuances_total"] = pd.to_numeric(df["niv_issuances_total"], errors="coerce").fillna(0.0)
    df["iv_issuances_total"] = pd.to_numeric(df["iv_issuances_total"], errors="coerce").fillna(0.0)
    return df.sort_values("date").reset_index(drop=True)


def build_row_state_visa_timing_sensitivity(
    estimates: pd.DataFrame,
    pilot: pd.DataFrame,
    *,
    state_visa_monthly_path: Path | str,
    start: str = "2022-09-30",
) -> pd.DataFrame:
    if estimates is None or estimates.empty or pilot is None or pilot.empty:
        return pd.DataFrame()

    monthly = _load_state_visa_monthly(state_visa_monthly_path)
    candidates = pilot.loc[pilot["pilot_bucket"].isin(PRIMARY_BUCKETS | SECONDARY_BUCKETS)].copy()
    if candidates.empty:
        return pd.DataFrame()

    candidates["date"] = pd.to_datetime(candidates["date"])
    annual_parts: list[dict[str, object]] = []
    for date, group in candidates.groupby("date"):
        fiscal_year = int(group["fiscal_year"].iloc[0])
        primary_mask = group["receipt_line_item_nm"].eq(STRICT_MRV_LINE) | group["pilot_bucket"].eq("mrv_cbsp_primary_candidate")
        secondary_mask = group["receipt_line_item_nm"].isin(STRICT_IV_LINES) | group["pilot_bucket"].eq(
            "state_visa_secondary_sensitivity"
        )
        primary_annual = group.loc[primary_mask, "receipt_amt_mil"].sum()
        secondary_annual = group.loc[secondary_mask, "receipt_amt_mil"].sum()
        annual_parts.append(
            {
                "date": pd.Timestamp(date),
                "fiscal_year": fiscal_year,
                "state_visa_strict_annual_total_mil": float(group["receipt_amt_mil"].sum()),
                "state_mrv_cbsp_primary_annual_mil": float(primary_annual),
                "state_visa_secondary_annual_mil": float(secondary_annual),
            }
        )

    annual = pd.DataFrame(annual_parts).sort_values("date").reset_index(drop=True)
    monthly = monthly.merge(
        annual.loc[
            :,
            [
                "fiscal_year",
                "state_visa_strict_annual_total_mil",
                "state_mrv_cbsp_primary_annual_mil",
                "state_visa_secondary_annual_mil",
            ],
        ],
        on="fiscal_year",
        how="inner",
    )
    if monthly.empty:
        return pd.DataFrame()

    fiscal_niv_totals = monthly.groupby("fiscal_year")["niv_issuances_total"].transform("sum")
    fiscal_iv_totals = monthly.groupby("fiscal_year")["iv_issuances_total"].transform("sum")
    monthly["state_mrv_cbsp_allocated_mil"] = monthly["state_mrv_cbsp_primary_annual_mil"] * (
        monthly["niv_issuances_total"] / fiscal_niv_totals.where(fiscal_niv_totals.ne(0), 1.0)
    )
    monthly["state_visa_secondary_allocated_mil"] = monthly["state_visa_secondary_annual_mil"] * (
        monthly["iv_issuances_total"] / fiscal_iv_totals.where(fiscal_iv_totals.ne(0), 1.0)
    )
    # Keep the legacy top-line column as the MRV-first primary bridge so downstream
    # surfaces can tighten without a full file/interface rename.
    monthly["row_state_visa_allocated_receipt_mil"] = monthly["state_mrv_cbsp_allocated_mil"]
    monthly["row_state_mrv_cbsp_allocated_receipt_mil"] = monthly["state_mrv_cbsp_allocated_mil"]
    monthly["row_state_visa_secondary_allocated_receipt_mil"] = monthly["state_visa_secondary_allocated_mil"]
    monthly["row_state_visa_total_allocated_receipt_mil"] = (
        monthly["row_state_visa_allocated_receipt_mil"] + monthly["row_state_visa_secondary_allocated_receipt_mil"]
    )

    monthly["quarter"] = monthly["date"].dt.to_period("Q").dt.to_timestamp("Q")
    quarterly = (
        monthly.groupby(["quarter", "fiscal_year"], as_index=False)
        .agg(
            {
                "state_visa_strict_annual_total_mil": "max",
                "state_mrv_cbsp_primary_annual_mil": "max",
                "state_visa_secondary_annual_mil": "max",
                "state_mrv_cbsp_allocated_mil": "sum",
                "state_visa_secondary_allocated_mil": "sum",
                "row_state_visa_allocated_receipt_mil": "sum",
                "row_state_mrv_cbsp_allocated_receipt_mil": "sum",
                "row_state_visa_secondary_allocated_receipt_mil": "sum",
                "row_state_visa_total_allocated_receipt_mil": "sum",
            }
        )
        .rename(
            columns={
                "quarter": "date",
                "fiscal_year": "state_visa_source_fiscal_year",
            }
        )
        .sort_values("date")
    )
    quarterly["state_mrv_source_fiscal_year"] = quarterly["state_visa_source_fiscal_year"]
    quarterly["row_receipt_correction_default_mil"] = 0.0
    quarterly["default_eligible"] = False
    quarterly["default_blocker"] = DEFAULT_BLOCKER
    quarterly["payer_identity_grade"] = "B_applicant_link_not_debited_account"
    quarterly["cash_treatment_grade"] = "B_cbsp_receipt_account_public_annual"
    quarterly["timing_grade"] = "C_niv_issuance_share_not_observed_cash_date"

    out = pd.DataFrame(index=pd.DatetimeIndex(sorted(estimates.index.union(pd.to_datetime(quarterly["date"]))))).sort_index()
    aligned = quarterly.set_index("date")
    for col in aligned.columns:
        out[col] = aligned[col].reindex(out.index)
    out["row_state_visa_allocated_receipt_mil"] = out["row_state_visa_allocated_receipt_mil"].fillna(0.0)
    out["row_state_mrv_cbsp_allocated_receipt_mil"] = out["row_state_mrv_cbsp_allocated_receipt_mil"].fillna(0.0)
    out["row_state_visa_secondary_allocated_receipt_mil"] = out["row_state_visa_secondary_allocated_receipt_mil"].fillna(0.0)
    out["row_state_visa_total_allocated_receipt_mil"] = out["row_state_visa_total_allocated_receipt_mil"].fillna(0.0)
    out["row_receipt_correction_default_mil"] = out["row_receipt_correction_default_mil"].fillna(0.0)
    out["default_eligible"] = out["default_eligible"].fillna(False).astype(bool)
    out["default_blocker"] = out["default_blocker"].fillna(DEFAULT_BLOCKER)

    if "tdc_tier3_fiscal_corrected_bank_only_ru_flow" in estimates.columns:
        out["tdc_tier3_bank_only_plus_row_state_visa_timing_sensitivity"] = (
            estimates["tdc_tier3_fiscal_corrected_bank_only_ru_flow"].reindex(out.index)
            + out["row_state_visa_allocated_receipt_mil"]
        )
        out["tdc_tier3_bank_only_row_state_visa_timing_delta"] = out["row_state_visa_allocated_receipt_mil"]
        out["tdc_tier3_bank_only_plus_row_state_visa_total_timing_sensitivity"] = (
            estimates["tdc_tier3_fiscal_corrected_bank_only_ru_flow"].reindex(out.index)
            + out["row_state_visa_total_allocated_receipt_mil"]
        )

    return out.loc[out.index >= pd.Timestamp(start)].copy()


def render_row_state_visa_timing_sensitivity_markdown(sensitivity: pd.DataFrame) -> str:
    title = "# ROW State MRV / CBSP Timing Bridge"
    intro = (
        "Quarterly MRV-first ROW timing bridge built from the annual State visa pilot and official monthly State visa issuance counts. "
        "Amounts are in millions. The main quarterly ROW delta uses only the Machine Readable Visa / CBSP line allocated by monthly NIV issuance shares. "
        "Secondary visa lines remain visible as a separate IV-based sensitivity and do not enter the main ROW receipt delta or the default Tier 3 correction."
    )
    if sensitivity.empty:
        return "\n".join([title, "", intro, "", "No overlapping strict State/visa pilot rows and monthly State issuance data are available."])

    nonzero = sensitivity.loc[sensitivity["row_state_visa_allocated_receipt_mil"].ne(0.0)].copy()
    latest_date = nonzero.index.max() if not nonzero.empty else sensitivity.index.max()
    latest = sensitivity.loc[latest_date]
    summary = (
        f"Latest MRV / CBSP allocation quarter: {pd.Timestamp(latest_date).date().isoformat()}. "
        f"Source fiscal year {int(latest['state_mrv_source_fiscal_year']) if pd.notna(latest['state_mrv_source_fiscal_year']) else 'n/a'}; "
        f"strict annual total {float(latest.get('state_visa_strict_annual_total_mil', 0.0)):,.3f}; "
        f"primary MRV quarterly sensitivity {float(latest.get('row_state_visa_allocated_receipt_mil', 0.0)):,.3f}; "
        f"secondary visa quarterly sensitivity {float(latest.get('row_state_visa_secondary_allocated_receipt_mil', 0.0)):,.3f}; "
        f"Tier 3 bank-only delta {float(latest.get('tdc_tier3_bank_only_row_state_visa_timing_delta', 0.0)):,.3f}."
    )

    header = [
        "| Quarter | Source fiscal year | Strict annual total | MRV / CBSP alloc. | Secondary visa alloc. | Total ROW visa alloc. | Tier 3 bank-only plus MRV bridge | Delta vs default Tier 3 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    rows = []
    for date, row in nonzero.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(date).date().isoformat(),
                    "n/a" if pd.isna(row.get("state_mrv_source_fiscal_year")) else str(int(row["state_mrv_source_fiscal_year"])),
                    f"{float(row.get('state_visa_strict_annual_total_mil', 0.0)):,.3f}",
                    f"{float(row.get('state_mrv_cbsp_allocated_mil', 0.0)):,.3f}",
                    f"{float(row.get('state_visa_secondary_allocated_mil', 0.0)):,.3f}",
                    f"{float(row.get('row_state_visa_total_allocated_receipt_mil', 0.0)):,.3f}",
                    "n/a"
                    if pd.isna(row.get("tdc_tier3_bank_only_plus_row_state_visa_timing_sensitivity"))
                    else f"{float(row.get('tdc_tier3_bank_only_plus_row_state_visa_timing_sensitivity', 0.0)):,.3f}",
                    "n/a"
                    if pd.isna(row.get("tdc_tier3_bank_only_row_state_visa_timing_delta"))
                    else f"{float(row.get('tdc_tier3_bank_only_row_state_visa_timing_delta', 0.0)):,.3f}",
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- Monthly NIV and IV issuance totals come from official State monthly visa-statistics workbooks.",
        "- The main quarterly bridge is MRV-first. Secondary visa lines remain visible for auditability but do not enter the main downstream ROW delta.",
        "- This artifact is a timing bridge only. It still does not prove that the legal payer or debited account matches the strict ROW cash-payer identity in every case.",
        "- Passport and broad-consular lines remain excluded from this MRV-first timing bridge.",
    ]
    return "\n".join([title, "", intro, "", summary, "", *header, *rows, "", *notes, ""])


def write_row_state_visa_timing_sensitivity(
    estimates: pd.DataFrame,
    pilot: pd.DataFrame,
    *,
    state_visa_monthly_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str,
    start: str = "2022-09-30",
) -> tuple[Path, Path, pd.DataFrame]:
    sensitivity = build_row_state_visa_timing_sensitivity(
        estimates,
        pilot,
        state_visa_monthly_path=state_visa_monthly_path,
        start=start,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = sensitivity.copy()
    to_write.index.name = "date"
    to_write.to_csv(csv_path)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_row_state_visa_timing_sensitivity_markdown(sensitivity), encoding="utf-8")

    return csv_path, markdown_path, sensitivity
