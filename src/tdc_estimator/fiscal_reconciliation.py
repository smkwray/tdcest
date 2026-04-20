from __future__ import annotations

from pathlib import Path

import pandas as pd


DEFAULT_START = "2022-09-30"


def _maybe(df: pd.DataFrame | None, column: str, index: pd.DatetimeIndex) -> pd.Series:
    if df is None or df.empty or column not in df.columns:
        return pd.Series(index=index, dtype="float64")
    series = pd.to_numeric(df[column], errors="coerce")
    return series.reindex(index)


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def _cell_rows(
    index: pd.DatetimeIndex,
    series: pd.Series,
    *,
    estimator_view: str,
    row_family: str,
    counterparty_column: str,
    source: str,
    role: str,
    reliability_grade: str,
    included_in_headline: bool,
    sign_in_reconciliation: int,
    notes: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    aligned = pd.to_numeric(series, errors="coerce").reindex(index)
    for date, value in aligned.items():
        if pd.isna(value):
            continue
        rows.append(
            {
                "date": pd.Timestamp(date),
                "estimator_view": estimator_view,
                "row_family": row_family,
                "counterparty_column": counterparty_column,
                "value_millions": float(value),
                "source": source,
                "role": role,
                "reliability_grade": reliability_grade,
                "included_in_headline": bool(included_in_headline),
                "sign_in_reconciliation": int(sign_in_reconciliation),
                "notes": notes,
            }
        )
    return rows


def build_fiscal_reconciliation_cells(
    estimates: pd.DataFrame,
    components: pd.DataFrame,
    corrections: pd.DataFrame,
    *,
    bea_row_receipts_benchmark: pd.DataFrame | None = None,
    bank_corp_tax_receipts_bridge: pd.DataFrame | None = None,
    tier3_source_diagnostics: pd.DataFrame | None = None,
    tier3_receipt_source_diagnostics: pd.DataFrame | None = None,
    bank_occ_timing_sensitivity: pd.DataFrame | None = None,
    row_state_visa_timing_sensitivity: pd.DataFrame | None = None,
    start: str = DEFAULT_START,
) -> pd.DataFrame:
    index = pd.DatetimeIndex(estimates.index).sort_values().unique()
    rows: list[dict[str, object]] = []
    base = dict(estimator_view="bank_only")

    default_specs = [
        (
            _maybe(components, "fed_tsy_tx", index),
            "treasury_security_net_transactions",
            "fed_soma",
            "z1_fred",
            "default",
            "high",
            True,
            1,
            "Fed/SOMA Treasury-security transactions in the reserve-user-flow ladder.",
        ),
        (
            _maybe(components, "bank_depository_tsy_tx", index),
            "treasury_security_net_transactions",
            "banks_default",
            "z1_fred",
            "default",
            "high",
            True,
            1,
            "Default bank-perimeter Treasury-security transactions: U.S.-chartered banks, foreign banking offices in the U.S., and banks in U.S.-affiliated areas.",
        ),
        (
            _maybe(components, "row_tsy_tx", index),
            "treasury_security_net_transactions",
            "row_total",
            "z1_fred",
            "default",
            "high",
            True,
            1,
            "Rest-of-world Treasury-security transactions included in the bank-only headline.",
        ),
        (
            _maybe(components, "minus_treasury_operating_cash_tx", index),
            "treasury_operating_cash_change",
            "treasury_cash",
            "z1_fred",
            "default",
            "high",
            True,
            -1,
            "Treasury operating cash contribution carried with the existing negative cash-offset convention.",
        ),
        (
            _maybe(components, "fed_remit_positive", index),
            "fed_remittances",
            "fed_soma",
            "h41_fred",
            "default",
            "medium_high",
            True,
            1,
            "Positive-only Fed remittance convention preserved from the base estimator.",
        ),
        (
            _maybe(corrections, "tier1_fed_coupon_correction", index),
            "coupon_interest_outlays",
            "fed_soma",
            "local_soma_coupon_proxy",
            "default",
            "high",
            True,
            -1,
            "Exact SOMA-based Treasury coupon-interest correction to the Fed.",
        ),
        (
            _maybe(corrections, "tier2_bank_coupon_correction", index),
            "coupon_interest_outlays",
            "banks_default",
            "local_sector_coupon_proxy",
            "default",
            "medium",
            True,
            -1,
            "Proxy Treasury coupon-interest correction to the default bank perimeter.",
        ),
        (
            _maybe(corrections, "tier2_row_coupon_correction", index),
            "coupon_interest_outlays",
            "row_total",
            "local_sector_coupon_proxy",
            "default",
            "medium",
            True,
            -1,
            "Proxy Treasury coupon-interest correction to the rest of the world, with scale audited against BEA/FRED.",
        ),
        (
            _maybe(corrections, "tier3_bank_noninterest_outlay_correction", index),
            "noninterest_outlays",
            "banks_default",
            "mts_source_diagnostics",
            "default",
            "medium",
            True,
            -1,
            "Current default bank noninterest-outlay correction from MTS Financial Agent Services-style lines.",
        ),
        (
            _maybe(corrections, "tier3_row_noninterest_outlay_correction", index),
            "noninterest_outlays",
            "row_total",
            "mts_source_diagnostics",
            "default",
            "medium",
            True,
            -1,
            "Current default narrow ROW noninterest-outlay correction from selected MTS foreign and international lines.",
        ),
        (
            _maybe(corrections, "tier3_bank_nonborrow_receipt_correction", index),
            "nonborrow_receipts",
            "banks_default",
            "tier3_support_file",
            "default",
            "low",
            True,
            1,
            "Current default bank nonborrow-receipt correction. This remains zero in the live source-backed build.",
        ),
        (
            _maybe(corrections, "tier3_row_nonborrow_receipt_correction", index),
            "nonborrow_receipts",
            "row_total",
            "tier3_support_file",
            "default",
            "low",
            True,
            1,
            "Current default ROW nonborrow-receipt correction. This remains zero in the live source-backed build.",
        ),
        (
            _maybe(corrections, "tier3_mint_cb_cash_factor_correction", index),
            "mint_cb_cash_factor",
            "treasury_cash",
            "mts_source_diagnostics",
            "default",
            "medium",
            True,
            1,
            "Mint or central-bank cash-factor adjustment used in the current Tier 3 build.",
        ),
    ]
    for series, row_family, counterparty, source, role, reliability, include, sign, notes in default_specs:
        rows.extend(
            _cell_rows(
                index,
                series,
                row_family=row_family,
                counterparty_column=counterparty,
                source=source,
                role=role,
                reliability_grade=reliability,
                included_in_headline=include,
                sign_in_reconciliation=sign,
                notes=notes,
                **base,
            )
        )

    sensitivity_specs = [
        (
            _maybe(components, "np_credit_unions_tsy_tx", index),
            "treasury_security_net_transactions",
            "credit_unions_np",
            "z1_fred",
            "sensitivity",
            "medium",
            False,
            1,
            "Natural-person credit-union Treasury-security transactions for the broad-depository sensitivity.",
        ),
        (
            _maybe(tier3_source_diagnostics, "row_outlay_broad_selected", index),
            "noninterest_outlays",
            "row_total",
            "mts_source_diagnostics",
            "sensitivity",
            "low_medium",
            False,
            -1,
            "Broad security-heavy ROW outlay profile retained as a published sensitivity rather than the default narrow profile.",
        ),
        (
            _maybe(tier3_receipt_source_diagnostics, "rcm_bank_channel_total_candidate", index),
            "nonborrow_receipts",
            "banks_default",
            "treasury_revenue_collections",
            "sensitivity",
            "low",
            False,
            1,
            "Revenue Collections Bank channel upper bound. Routing-heavy and excluded from the default counterparty map.",
        ),
        (
            _maybe(tier3_receipt_source_diagnostics, "rcm_bank_channel_non_tax_candidate", index),
            "nonborrow_receipts",
            "banks_default",
            "treasury_revenue_collections",
            "sensitivity",
            "low",
            False,
            1,
            "Revenue Collections Bank non-tax upper bound. Still routing-heavy and excluded from the default counterparty map.",
        ),
        (
            _maybe(bank_occ_timing_sensitivity, "occ_due_date_allocated_receipt_mil", index),
            "nonborrow_receipts",
            "banks_default",
            "annual_account_pilot_plus_occ_timing",
            "sensitivity",
            "medium_low",
            False,
            1,
            "OCC due-date timing sensitivity built from the annual bank non-tax pilot and current semiannual assessment cadence.",
        ),
        (
            _maybe(row_state_visa_timing_sensitivity, "row_state_visa_allocated_receipt_mil", index),
            "nonborrow_receipts",
            "row_total",
            "annual_account_pilot_plus_state_visa_timing",
            "sensitivity",
            "medium_low",
            False,
            1,
            "ROW State/visa timing sensitivity built from the strict annual pilot and monthly NIV/IV issuance shares.",
        ),
    ]
    for series, row_family, counterparty, source, role, reliability, include, sign, notes in sensitivity_specs:
        rows.extend(
            _cell_rows(
                index,
                series,
                row_family=row_family,
                counterparty_column=counterparty,
                source=source,
                role=role,
                reliability_grade=reliability,
                included_in_headline=include,
                sign_in_reconciliation=sign,
                notes=notes,
                **base,
            )
        )

    benchmark_specs = [
        (
            _maybe(bea_row_receipts_benchmark, "bea_row_current_receipts_total_q_mil", index),
            "nonborrow_receipts",
            "row_total",
            "bea_nipa_table_3_2",
            "benchmark",
            "medium",
            False,
            1,
            "BEA/NIPA ROW current-receipts benchmark. Official macro benchmark, not a Treasury cash-payer default.",
        ),
        (
            _maybe(bank_corp_tax_receipts_bridge, "bank_corp_tax_receipts_gross_strict_depository_mil", index),
            "nonborrow_receipts",
            "banks_default",
            "mts_plus_irs_soi_bridge",
            "benchmark",
            "medium",
            False,
            1,
            "Bank corporate-tax receipt bridge using MTS quarterly cash totals and IRS Publication 16 Table 5.1 strict-depository shares.",
        ),
        (
            _maybe(bank_corp_tax_receipts_bridge, "bank_corp_tax_receipts_gross_depository_plus_bhc_mil", index),
            "nonborrow_receipts",
            "banks_default",
            "mts_plus_irs_soi_bridge",
            "benchmark",
            "medium",
            False,
            1,
            "Primary bank corporate-tax default-candidate bridge using MTS quarterly cash totals and IRS Publication 16 Table 5.1 depository-plus-BHC shares.",
        ),
        (
            _maybe(bank_corp_tax_receipts_bridge, "bank_corp_tax_receipts_gross_finance_share_mil", index),
            "nonborrow_receipts",
            "banks_default",
            "mts_plus_irs_soi_bridge",
            "benchmark",
            "medium_low",
            False,
            1,
            "Upper benchmark only: MTS quarterly cash totals with broad finance-sector annual shares retained for scale comparison.",
        ),
    ]
    for series, row_family, counterparty, source, role, reliability, include, sign, notes in benchmark_specs:
        rows.extend(
            _cell_rows(
                index,
                series,
                row_family=row_family,
                counterparty_column=counterparty,
                source=source,
                role=role,
                reliability_grade=reliability,
                included_in_headline=include,
                sign_in_reconciliation=sign,
                notes=notes,
                **base,
            )
        )

    cells = pd.DataFrame(rows)
    if cells.empty:
        return cells
    return cells.loc[cells["date"] >= pd.Timestamp(start)].sort_values(
        ["date", "role", "row_family", "counterparty_column", "source"]
    ).reset_index(drop=True)


def build_fiscal_reconciliation_residuals(
    estimates: pd.DataFrame,
    cells: pd.DataFrame,
    *,
    start: str = DEFAULT_START,
) -> pd.DataFrame:
    if cells is None or cells.empty:
        return pd.DataFrame()

    index = pd.DatetimeIndex(estimates.index).sort_values().unique()
    default_cells = cells.loc[cells["role"].eq("default") & cells["included_in_headline"].eq(True)].copy()
    if default_cells.empty:
        return pd.DataFrame()

    out = pd.DataFrame(index=index)

    def _sum_subset(mask: pd.Series) -> pd.Series:
        sub = default_cells.loc[mask, ["date", "value_millions"]].copy()
        if sub.empty:
            return pd.Series(0.0, index=index, dtype="float64")
        return sub.groupby("date")["value_millions"].sum().reindex(index).fillna(0.0)

    tier0 = _sum_subset(
        default_cells["row_family"].isin(
            ["treasury_security_net_transactions", "treasury_operating_cash_change", "fed_remittances"]
        )
    )
    tier1_coupon = _sum_subset(
        default_cells["row_family"].eq("coupon_interest_outlays")
        & default_cells["counterparty_column"].eq("fed_soma")
    )
    tier2_coupon = _sum_subset(
        default_cells["row_family"].eq("coupon_interest_outlays")
        & default_cells["counterparty_column"].isin(["banks_default", "row_total"])
    )
    tier3_fiscal = _sum_subset(
        default_cells["row_family"].isin(["noninterest_outlays", "nonborrow_receipts", "mint_cb_cash_factor"])
    )

    out["tier0_reconstructed_default_mil"] = tier0
    out["tier1_reconstructed_default_mil"] = tier0 + tier1_coupon
    out["tier2_reconstructed_default_mil"] = out["tier1_reconstructed_default_mil"] + tier2_coupon
    out["tier3_reconstructed_default_mil"] = out["tier2_reconstructed_default_mil"] + tier3_fiscal

    out["tdc_base_bank_only_ru_flow"] = _maybe(estimates, "tdc_base_bank_only_ru_flow", index)
    out["tdc_tier1_fed_corrected_bank_only_ru_flow"] = _maybe(estimates, "tdc_tier1_fed_corrected_bank_only_ru_flow", index)
    out["tdc_tier2_interest_corrected_bank_only_ru_flow"] = _maybe(estimates, "tdc_tier2_interest_corrected_bank_only_ru_flow", index)
    out["tdc_tier3_fiscal_corrected_bank_only_ru_flow"] = _maybe(estimates, "tdc_tier3_fiscal_corrected_bank_only_ru_flow", index)

    out["tier0_reconstruction_residual_mil"] = out["tdc_base_bank_only_ru_flow"] - out["tier0_reconstructed_default_mil"]
    out["tier1_reconstruction_residual_mil"] = (
        out["tdc_tier1_fed_corrected_bank_only_ru_flow"] - out["tier1_reconstructed_default_mil"]
    )
    out["tier2_reconstruction_residual_mil"] = (
        out["tdc_tier2_interest_corrected_bank_only_ru_flow"] - out["tier2_reconstructed_default_mil"]
    )
    out["tier3_reconstruction_residual_mil"] = (
        out["tdc_tier3_fiscal_corrected_bank_only_ru_flow"] - out["tier3_reconstructed_default_mil"]
    )
    return out.loc[out.index >= pd.Timestamp(start)].copy()


def build_fiscal_source_quality(cells: pd.DataFrame, *, start: str = DEFAULT_START) -> pd.DataFrame:
    if cells is None or cells.empty:
        return pd.DataFrame()

    rows: list[dict[str, object]] = []
    for keys, sub in cells.loc[cells["date"] >= pd.Timestamp(start)].groupby(
        [
            "estimator_view",
            "row_family",
            "counterparty_column",
            "source",
            "role",
            "reliability_grade",
            "included_in_headline",
            "sign_in_reconciliation",
            "notes",
        ],
        dropna=False,
    ):
        (
            estimator_view,
            row_family,
            counterparty_column,
            source,
            role,
            reliability_grade,
            included_in_headline,
            sign_in_reconciliation,
            notes,
        ) = keys
        latest = sub.sort_values("date").iloc[-1]
        rows.append(
            {
                "estimator_view": estimator_view,
                "row_family": row_family,
                "counterparty_column": counterparty_column,
                "source": source,
                "role": role,
                "reliability_grade": reliability_grade,
                "included_in_headline": bool(included_in_headline),
                "sign_in_reconciliation": int(sign_in_reconciliation),
                "first_date": pd.Timestamp(sub["date"].min()).date().isoformat(),
                "last_date": pd.Timestamp(sub["date"].max()).date().isoformat(),
                "nonzero_quarter_count": int(sub["value_millions"].fillna(0.0).ne(0.0).sum()),
                "latest_value_millions": float(latest["value_millions"]),
                "notes": notes,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["role", "row_family", "counterparty_column", "source"]
    ).reset_index(drop=True)


def render_fiscal_reconciliation_residuals_markdown(residuals: pd.DataFrame) -> str:
    title = "# Fiscal Reconciliation Residuals"
    intro = (
        "Quarter-by-quarter residual check for the fiscal reconciliation shell around the default bank-only ladder. "
        "Amounts are in millions. Residuals should stay near zero when the shell is faithfully reproducing the live Tier 0 through Tier 3 default path."
    )
    if residuals.empty:
        return "\n".join([title, "", intro, "", "No fiscal reconciliation residuals are available."])

    latest_date = residuals.index.max()
    latest = residuals.loc[latest_date]
    summary = (
        f"Latest quarter: {pd.Timestamp(latest_date).date().isoformat()}. "
        f"Tier 0 residual {_format_millions(latest.get('tier0_reconstruction_residual_mil'))}; "
        f"Tier 1 residual {_format_millions(latest.get('tier1_reconstruction_residual_mil'))}; "
        f"Tier 2 residual {_format_millions(latest.get('tier2_reconstruction_residual_mil'))}; "
        f"Tier 3 residual {_format_millions(latest.get('tier3_reconstruction_residual_mil'))}."
    )
    return "\n".join([title, "", intro, "", summary, ""])


def render_fiscal_source_quality_markdown(source_quality: pd.DataFrame) -> str:
    title = "# Fiscal Source Quality"
    intro = (
        "Source-quality summary for the fiscal reconciliation shell. "
        "Each row is a currently wired reconciliation cell family with its role, reliability grade, headline status, and latest observed value."
    )
    if source_quality.empty:
        return "\n".join([title, "", intro, "", "No fiscal source-quality rows are available."])

    latest_default = source_quality.loc[source_quality["included_in_headline"].eq(True)].head(1)
    summary = "Default, benchmark, and sensitivity rows are now graded explicitly in the reconciliation shell."
    if not latest_default.empty:
        row = latest_default.iloc[0]
        summary = (
            "Example headline cell: "
            f"{row['row_family']} / {row['counterparty_column']} from {row['source']} "
            f"with reliability {row['reliability_grade']}."
        )
    return "\n".join([title, "", intro, "", summary, ""])


def write_fiscal_reconciliation_outputs(
    estimates: pd.DataFrame,
    components: pd.DataFrame,
    corrections: pd.DataFrame,
    *,
    cells_csv_path: Path | str,
    residuals_csv_path: Path | str,
    source_quality_csv_path: Path | str,
    residuals_markdown_path: Path | str,
    source_quality_markdown_path: Path | str,
    bea_row_receipts_benchmark: pd.DataFrame | None = None,
    bank_corp_tax_receipts_bridge: pd.DataFrame | None = None,
    tier3_source_diagnostics: pd.DataFrame | None = None,
    tier3_receipt_source_diagnostics: pd.DataFrame | None = None,
    bank_occ_timing_sensitivity: pd.DataFrame | None = None,
    row_state_visa_timing_sensitivity: pd.DataFrame | None = None,
    start: str = DEFAULT_START,
) -> tuple[Path, Path, Path, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cells = build_fiscal_reconciliation_cells(
        estimates,
        components,
        corrections,
        bea_row_receipts_benchmark=bea_row_receipts_benchmark,
        bank_corp_tax_receipts_bridge=bank_corp_tax_receipts_bridge,
        tier3_source_diagnostics=tier3_source_diagnostics,
        tier3_receipt_source_diagnostics=tier3_receipt_source_diagnostics,
        bank_occ_timing_sensitivity=bank_occ_timing_sensitivity,
        row_state_visa_timing_sensitivity=row_state_visa_timing_sensitivity,
        start=start,
    )
    residuals = build_fiscal_reconciliation_residuals(estimates, cells, start=start)
    source_quality = build_fiscal_source_quality(cells, start=start)

    cells_csv_path = Path(cells_csv_path)
    cells_csv_path.parent.mkdir(parents=True, exist_ok=True)
    cells.to_csv(cells_csv_path, index=False)

    residuals_csv_path = Path(residuals_csv_path)
    residuals_csv_path.parent.mkdir(parents=True, exist_ok=True)
    residuals_to_write = residuals.copy()
    residuals_to_write.index.name = "date"
    residuals_to_write.to_csv(residuals_csv_path)

    source_quality_csv_path = Path(source_quality_csv_path)
    source_quality_csv_path.parent.mkdir(parents=True, exist_ok=True)
    source_quality.to_csv(source_quality_csv_path, index=False)

    residuals_markdown_path = Path(residuals_markdown_path)
    residuals_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    residuals_markdown_path.write_text(
        render_fiscal_reconciliation_residuals_markdown(residuals),
        encoding="utf-8",
    )

    source_quality_markdown_path = Path(source_quality_markdown_path)
    source_quality_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    source_quality_markdown_path.write_text(
        render_fiscal_source_quality_markdown(source_quality),
        encoding="utf-8",
    )

    return (
        cells_csv_path,
        residuals_csv_path,
        source_quality_csv_path,
        cells,
        residuals,
        source_quality,
    )
