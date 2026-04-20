from __future__ import annotations

from pathlib import Path

import pandas as pd


DEFAULT_START = "2022-09-30"


def _series(df: pd.DataFrame | None, column: str, index: pd.DatetimeIndex) -> pd.Series:
    if df is None or df.empty or column not in df.columns:
        return pd.Series(0.0, index=index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").reindex(index).fillna(0.0)


def _meta(df: pd.DataFrame | None, column: str, index: pd.DatetimeIndex) -> pd.Series:
    if df is None or df.empty or column not in df.columns:
        return pd.Series(index=index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").reindex(index)


def _bool_meta(df: pd.DataFrame | None, column: str, index: pd.DatetimeIndex, *, default: bool = False) -> pd.Series:
    if df is None or df.empty or column not in df.columns:
        return pd.Series(default, index=index, dtype="bool")
    series = df[column].reindex(index)
    normalized = series.astype("object").map(
        lambda value: value
        if isinstance(value, bool)
        else str(value).strip().lower() in {"true", "1", "yes"}
        if pd.notna(value)
        else default
    )
    return normalized.fillna(default).astype(bool)


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def build_tier3_receipt_candidate_sensitivity(
    estimates: pd.DataFrame,
    *,
    bank_corp_tax_bridge: pd.DataFrame | None = None,
    bank_occ_timing_sensitivity: pd.DataFrame | None = None,
    row_state_visa_timing_sensitivity: pd.DataFrame | None = None,
    start: str = DEFAULT_START,
) -> pd.DataFrame:
    if estimates is None or estimates.empty or "tdc_tier3_fiscal_corrected_bank_only_ru_flow" not in estimates.columns:
        return pd.DataFrame()

    has_any_candidate = any(
        df is not None and not df.empty
        for df in [bank_corp_tax_bridge, bank_occ_timing_sensitivity, row_state_visa_timing_sensitivity]
    )
    if not has_any_candidate:
        return pd.DataFrame()

    index = pd.DatetimeIndex(estimates.index).sort_values().unique()
    frame = pd.DataFrame(index=index)
    frame["tdc_tier3_fiscal_corrected_bank_only_ru_flow"] = pd.to_numeric(
        estimates["tdc_tier3_fiscal_corrected_bank_only_ru_flow"], errors="coerce"
    ).reindex(index)

    frame["bank_corp_tax_strict_depository_bridge_delta_mil"] = _series(
        bank_corp_tax_bridge,
        "bank_corp_tax_receipts_gross_strict_depository_mil",
        index,
    )
    frame["bank_corp_tax_depository_plus_bhc_bridge_delta_mil"] = _series(
        bank_corp_tax_bridge,
        "bank_corp_tax_receipts_gross_depository_plus_bhc_mil",
        index,
    )
    frame["bank_corp_tax_finance_upper_benchmark_delta_mil"] = _series(
        bank_corp_tax_bridge,
        "bank_corp_tax_receipts_gross_finance_share_mil",
        index,
    )
    frame["occ_timing_delta_mil"] = _series(
        bank_occ_timing_sensitivity,
        "occ_due_date_allocated_receipt_mil",
        index,
    )
    frame["row_state_visa_timing_delta_mil"] = _series(
        row_state_visa_timing_sensitivity,
        "row_state_visa_allocated_receipt_mil",
        index,
    )

    frame["bank_corp_tax_share_year_used"] = _meta(bank_corp_tax_bridge, "soi_tax_year_used", index)
    frame["bank_corp_tax_share_age_eligible_for_default"] = _bool_meta(
        bank_corp_tax_bridge,
        "share_age_eligible_for_default",
        index,
        default=True,
    )
    frame["occ_source_year"] = _meta(bank_occ_timing_sensitivity, "occ_annual_candidate_source_year", index)
    frame["row_state_visa_source_fiscal_year"] = _meta(row_state_visa_timing_sensitivity, "state_visa_source_fiscal_year", index)
    frame["bank_corp_tax_strict_depository_bridge_policy_eligible_delta_mil"] = frame[
        "bank_corp_tax_strict_depository_bridge_delta_mil"
    ].where(
        frame["bank_corp_tax_share_age_eligible_for_default"], 0.0
    )
    frame["bank_corp_tax_depository_plus_bhc_bridge_policy_eligible_delta_mil"] = frame[
        "bank_corp_tax_depository_plus_bhc_bridge_delta_mil"
    ].where(
        frame["bank_corp_tax_share_age_eligible_for_default"], 0.0
    )

    frame["tdc_tier3_bank_only_plus_bank_corp_tax_strict_depository_bridge"] = (
        frame["tdc_tier3_fiscal_corrected_bank_only_ru_flow"] + frame["bank_corp_tax_strict_depository_bridge_delta_mil"]
    )
    frame["tdc_tier3_bank_only_plus_bank_corp_tax_depository_plus_bhc_bridge"] = (
        frame["tdc_tier3_fiscal_corrected_bank_only_ru_flow"]
        + frame["bank_corp_tax_depository_plus_bhc_bridge_delta_mil"]
    )
    frame["tdc_tier3_bank_only_plus_bank_strict_depository_bridge_and_occ_timing"] = (
        frame["tdc_tier3_fiscal_corrected_bank_only_ru_flow"]
        + frame["bank_corp_tax_strict_depository_bridge_delta_mil"]
        + frame["occ_timing_delta_mil"]
    )
    frame["tdc_tier3_bank_only_plus_bank_depository_plus_bhc_bridge_and_occ_timing"] = (
        frame["tdc_tier3_fiscal_corrected_bank_only_ru_flow"]
        + frame["bank_corp_tax_depository_plus_bhc_bridge_delta_mil"]
        + frame["occ_timing_delta_mil"]
    )
    frame["tdc_tier3_bank_only_plus_bank_depository_plus_bhc_occ_and_row_state_visa"] = (
        frame["tdc_tier3_fiscal_corrected_bank_only_ru_flow"]
        + frame["bank_corp_tax_depository_plus_bhc_bridge_delta_mil"]
        + frame["occ_timing_delta_mil"]
        + frame["row_state_visa_timing_delta_mil"]
    )
    frame["tdc_tier3_bank_only_plus_bank_finance_upper_benchmark_occ_and_row_state_visa"] = (
        frame["tdc_tier3_fiscal_corrected_bank_only_ru_flow"]
        + frame["bank_corp_tax_finance_upper_benchmark_delta_mil"]
        + frame["occ_timing_delta_mil"]
        + frame["row_state_visa_timing_delta_mil"]
    )
    frame["tdc_tier3_bank_only_plus_policy_eligible_bank_depository_plus_bhc_occ_and_row_state_visa"] = (
        frame["tdc_tier3_fiscal_corrected_bank_only_ru_flow"]
        + frame["bank_corp_tax_depository_plus_bhc_bridge_policy_eligible_delta_mil"]
        + frame["occ_timing_delta_mil"]
        + frame["row_state_visa_timing_delta_mil"]
    )
    frame["tdc_tier3_bank_only_plus_policy_eligible_bank_strict_depository_occ_and_row_state_visa"] = (
        frame["tdc_tier3_fiscal_corrected_bank_only_ru_flow"]
        + frame["bank_corp_tax_strict_depository_bridge_policy_eligible_delta_mil"]
        + frame["occ_timing_delta_mil"]
        + frame["row_state_visa_timing_delta_mil"]
    )

    frame = frame.loc[frame.index >= pd.Timestamp(start)].copy()
    frame = frame.dropna(subset=["tdc_tier3_fiscal_corrected_bank_only_ru_flow"], how="any")

    nonzero_mask = (
        frame["bank_corp_tax_strict_depository_bridge_delta_mil"].ne(0.0)
        | frame["bank_corp_tax_depository_plus_bhc_bridge_delta_mil"].ne(0.0)
        | frame["bank_corp_tax_finance_upper_benchmark_delta_mil"].ne(0.0)
        | frame["bank_corp_tax_strict_depository_bridge_policy_eligible_delta_mil"].ne(0.0)
        | frame["bank_corp_tax_depository_plus_bhc_bridge_policy_eligible_delta_mil"].ne(0.0)
        | frame["occ_timing_delta_mil"].ne(0.0)
        | frame["row_state_visa_timing_delta_mil"].ne(0.0)
    )
    return frame.loc[nonzero_mask].copy()


def render_tier3_receipt_candidate_sensitivity_markdown(sensitivity: pd.DataFrame) -> str:
    title = "# Tier 3 Receipt Candidate Sensitivity"
    intro = (
        "Quarter-by-quarter receipt-candidate sensitivity around the default Tier 3 bank-only series. "
        "Amounts are in millions. This artifact keeps the default Tier 3 estimator unchanged and shows what happens "
        "if the strongest current non-default receipt candidates are layered in: the Table 5.1 bank corporate-tax bridge variants, "
        "the OCC timing sensitivity, and the MRV-first ROW bridge."
    )
    if sensitivity.empty:
        return "\n".join([title, "", intro, "", "No receipt-candidate sensitivity inputs are available."])

    latest_date = sensitivity.index.max()
    latest = sensitivity.loc[latest_date]

    latest_row_state_date = (
        sensitivity.loc[sensitivity["row_state_visa_timing_delta_mil"].ne(0.0)].index.max()
        if sensitivity["row_state_visa_timing_delta_mil"].ne(0.0).any()
        else None
    )
    latest_occ_date = (
        sensitivity.loc[sensitivity["occ_timing_delta_mil"].ne(0.0)].index.max()
        if sensitivity["occ_timing_delta_mil"].ne(0.0).any()
        else None
    )
    latest_policy_eligible_bank_date = (
        sensitivity.loc[sensitivity["bank_corp_tax_depository_plus_bhc_bridge_policy_eligible_delta_mil"].ne(0.0)].index.max()
        if sensitivity["bank_corp_tax_depository_plus_bhc_bridge_policy_eligible_delta_mil"].ne(0.0).any()
        else None
    )

    summary = [
        (
            f"Latest quarter in view: {pd.Timestamp(latest_date).date().isoformat()}. "
            f"Default Tier 3 {_format_millions(latest.get('tdc_tier3_fiscal_corrected_bank_only_ru_flow'))}; "
            f"bank strict-depository bridge delta {_format_millions(latest.get('bank_corp_tax_strict_depository_bridge_delta_mil'))}; "
            f"bank depository-plus-BHC bridge delta {_format_millions(latest.get('bank_corp_tax_depository_plus_bhc_bridge_delta_mil'))}; "
            f"policy-eligible bank depository-plus-BHC delta {_format_millions(latest.get('bank_corp_tax_depository_plus_bhc_bridge_policy_eligible_delta_mil'))}; "
            f"bank finance upper benchmark delta {_format_millions(latest.get('bank_corp_tax_finance_upper_benchmark_delta_mil'))}; "
            f"OCC timing delta {_format_millions(latest.get('occ_timing_delta_mil'))}; "
            f"ROW MRV bridge delta {_format_millions(latest.get('row_state_visa_timing_delta_mil'))}."
        )
    ]
    if latest_policy_eligible_bank_date is not None:
        policy_bank = sensitivity.loc[latest_policy_eligible_bank_date]
        summary.append(
            "Latest policy-eligible bank-bridge quarter: "
            f"{pd.Timestamp(latest_policy_eligible_bank_date).date().isoformat()} with delta "
            f"{_format_millions(policy_bank.get('bank_corp_tax_depository_plus_bhc_bridge_policy_eligible_delta_mil'))}."
        )
    if latest_occ_date is not None:
        occ = sensitivity.loc[latest_occ_date]
        summary.append(
            "Latest OCC-timing quarter: "
            f"{pd.Timestamp(latest_occ_date).date().isoformat()} with delta "
            f"{_format_millions(occ.get('occ_timing_delta_mil'))}."
        )
    if latest_row_state_date is not None:
        row_state = sensitivity.loc[latest_row_state_date]
        summary.append(
            "Latest ROW MRV bridge quarter: "
            f"{pd.Timestamp(latest_row_state_date).date().isoformat()} with delta "
            f"{_format_millions(row_state.get('row_state_visa_timing_delta_mil'))}."
        )

    header = [
        "| Quarter | Default Tier 3 | Bank strict depository | Bank dep+BHC | Policy-eligible dep+BHC | Finance upper benchmark | OCC timing | ROW MRV bridge | Strict+OCC | Policy-eligible dep+BHC+OCC+ROW | Dep+BHC+OCC+ROW | Finance upper benchmark+OCC+ROW |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    rows: list[str] = []
    for date, row in sensitivity.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(date).date().isoformat(),
                    _format_millions(row.get("tdc_tier3_fiscal_corrected_bank_only_ru_flow")),
                    _format_millions(row.get("bank_corp_tax_strict_depository_bridge_delta_mil")),
                    _format_millions(row.get("bank_corp_tax_depository_plus_bhc_bridge_delta_mil")),
                    _format_millions(row.get("bank_corp_tax_depository_plus_bhc_bridge_policy_eligible_delta_mil")),
                    _format_millions(row.get("bank_corp_tax_finance_upper_benchmark_delta_mil")),
                    _format_millions(row.get("occ_timing_delta_mil")),
                    _format_millions(row.get("row_state_visa_timing_delta_mil")),
                    _format_millions(row.get("tdc_tier3_bank_only_plus_bank_strict_depository_bridge_and_occ_timing")),
                    _format_millions(row.get("tdc_tier3_bank_only_plus_policy_eligible_bank_depository_plus_bhc_occ_and_row_state_visa")),
                    _format_millions(row.get("tdc_tier3_bank_only_plus_bank_depository_plus_bhc_occ_and_row_state_visa")),
                    _format_millions(row.get("tdc_tier3_bank_only_plus_bank_finance_upper_benchmark_occ_and_row_state_visa")),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- The bank corporate-tax bridge remains a graded bridge, not a direct payer-identity receipt series.",
        "- `Policy-eligible dep+BHC` clips the main bank default-candidate bridge to quarters that still satisfy the bridge's current stale-share policy.",
        "- The OCC layer is a due-date timing sensitivity built from annual public account-title evidence, not a promoted default correction.",
        "- The ROW layer is now MRV-first; secondary visa lines remain visible in the underlying bridge but do not feed the main ROW delta here.",
        "- The combined stacks are useful for scale and sign analysis, but they should not be treated as a published default Tier 3 path.",
    ]

    return "\n".join([title, "", intro, "", *summary, "", *header, *rows, "", *notes, ""])


def write_tier3_receipt_candidate_sensitivity(
    estimates: pd.DataFrame,
    *,
    bank_corp_tax_bridge: pd.DataFrame | None = None,
    bank_occ_timing_sensitivity: pd.DataFrame | None = None,
    row_state_visa_timing_sensitivity: pd.DataFrame | None = None,
    csv_path: Path | str,
    markdown_path: Path | str,
    start: str = DEFAULT_START,
) -> tuple[Path, Path, pd.DataFrame]:
    sensitivity = build_tier3_receipt_candidate_sensitivity(
        estimates,
        bank_corp_tax_bridge=bank_corp_tax_bridge,
        bank_occ_timing_sensitivity=bank_occ_timing_sensitivity,
        row_state_visa_timing_sensitivity=row_state_visa_timing_sensitivity,
        start=start,
    )

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = sensitivity.copy()
    to_write.index.name = "date"
    to_write.to_csv(csv_path)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        render_tier3_receipt_candidate_sensitivity_markdown(sensitivity),
        encoding="utf-8",
    )

    return csv_path, markdown_path, sensitivity
