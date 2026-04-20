from __future__ import annotations

from pathlib import Path

import pandas as pd


DEFAULT_POST2022_START = "2022-09-30"


def _maybe(df: pd.DataFrame, column: str) -> pd.Series:
    if column in df.columns:
        return df[column]
    return pd.Series(index=df.index, dtype="float64")


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def build_post2022_bank_only_attribution(
    estimates: pd.DataFrame,
    corrections: pd.DataFrame,
    *,
    start: str = DEFAULT_POST2022_START,
) -> pd.DataFrame:
    frame = pd.DataFrame(index=estimates.index)
    frame["tdc_base_bank_only_ru_flow"] = _maybe(estimates, "tdc_base_bank_only_ru_flow")
    frame["tdc_tier1_fed_corrected_bank_only_ru_flow"] = _maybe(
        estimates, "tdc_tier1_fed_corrected_bank_only_ru_flow"
    )
    frame["tdc_tier2_interest_corrected_bank_only_ru_flow"] = _maybe(
        estimates, "tdc_tier2_interest_corrected_bank_only_ru_flow"
    )
    frame["tdc_tier3_fiscal_corrected_bank_only_ru_flow"] = _maybe(
        estimates, "tdc_tier3_fiscal_corrected_bank_only_ru_flow"
    )
    frame["fed_coupon_correction"] = _maybe(corrections, "tier1_fed_coupon_correction")
    frame["bank_coupon_correction"] = _maybe(corrections, "tier2_bank_coupon_correction")
    frame["row_coupon_correction"] = _maybe(corrections, "tier2_row_coupon_correction")
    frame["bank_noninterest_outlay_correction"] = _maybe(corrections, "tier3_bank_noninterest_outlay_correction")
    frame["row_noninterest_outlay_correction"] = _maybe(corrections, "tier3_row_noninterest_outlay_correction")
    frame["bank_nonborrow_receipt_correction"] = _maybe(corrections, "tier3_bank_nonborrow_receipt_correction")
    frame["row_nonborrow_receipt_correction"] = _maybe(corrections, "tier3_row_nonborrow_receipt_correction")
    frame["mint_cb_cash_factor_correction"] = _maybe(corrections, "tier3_mint_cb_cash_factor_correction")
    frame["tier1_delta_from_base"] = _maybe(corrections, "tdc_tier1_bank_only_delta_from_base")
    frame["tier2_delta_from_base"] = _maybe(corrections, "tdc_tier2_bank_only_delta_from_base")
    frame["tier2_delta_from_tier1"] = _maybe(corrections, "tdc_tier2_bank_only_delta_from_tier1")
    frame["tier3_delta_from_base"] = _maybe(corrections, "tdc_tier3_bank_only_delta_from_base")
    frame["tier3_delta_from_tier2"] = _maybe(corrections, "tdc_tier3_bank_only_delta_from_tier2")

    correction_term_map = {
        "fed_coupon_correction": "tier1_fed_coupon_correction",
        "bank_coupon_correction": "tier2_bank_coupon_correction",
        "row_coupon_correction": "tier2_row_coupon_correction",
    }
    available_terms = [
        output_column
        for output_column, source_column in correction_term_map.items()
        if source_column in corrections.columns
    ]
    if available_terms:
        frame["total_coupon_correction"] = frame[available_terms].sum(axis=1, min_count=1)
        abs_terms = frame[available_terms].abs()
        abs_total = abs_terms.sum(axis=1, min_count=1)
        for column in available_terms:
            share_column = column.replace("_correction", "_share_abs_pct")
            frame[share_column] = (abs_terms[column] / abs_total) * 100.0
            frame.loc[abs_total <= 0, share_column] = pd.NA

        labels = {
            "fed_coupon_correction": "fed",
            "bank_coupon_correction": "bank",
            "row_coupon_correction": "row",
        }
        frame["dominant_coupon_correction"] = pd.NA
        valid = abs_total > 0
        if valid.any():
            dominant = abs_terms.loc[valid].idxmax(axis=1)
            frame.loc[valid, "dominant_coupon_correction"] = dominant.map(labels)

    fiscal_terms = [
        column
        for column, source_column in {
            "bank_noninterest_outlay_correction": "tier3_bank_noninterest_outlay_correction",
            "row_noninterest_outlay_correction": "tier3_row_noninterest_outlay_correction",
            "bank_nonborrow_receipt_correction": "tier3_bank_nonborrow_receipt_correction",
            "row_nonborrow_receipt_correction": "tier3_row_nonborrow_receipt_correction",
            "mint_cb_cash_factor_correction": "tier3_mint_cb_cash_factor_correction",
        }.items()
        if source_column in corrections.columns
    ]
    if fiscal_terms:
        frame["total_fiscal_correction"] = frame[fiscal_terms].sum(axis=1, min_count=1)

    frame = frame.loc[pd.to_datetime(frame.index) >= pd.Timestamp(start)].copy()
    frame = frame.dropna(how="all")
    return frame


def render_post2022_bank_only_attribution_markdown(attribution: pd.DataFrame) -> str:
    title = "# Post-2022 Bank-Only Correction Attribution"
    intro = (
        "Quarter-by-quarter attribution for the default bank-only estimator ladder beginning "
        f"{DEFAULT_POST2022_START}. Negative correction values mean the corrected tier is lower "
        "than its parent estimator in that quarter."
    )
    if attribution.empty:
        return "\n".join([title, "", intro, "", "No post-2022 corrected-quarter observations are available."])

    latest_date = attribution.index.max()
    latest = attribution.loc[latest_date]
    latest_summary = (
        f"Latest quarter: {pd.Timestamp(latest_date).date().isoformat()}. "
        f"Base {_format_millions(latest.get('tdc_base_bank_only_ru_flow'))}; "
        f"Tier 1 {_format_millions(latest.get('tdc_tier1_fed_corrected_bank_only_ru_flow'))}; "
        f"Tier 2 {_format_millions(latest.get('tdc_tier2_interest_corrected_bank_only_ru_flow'))}; "
        f"Tier 3 {_format_millions(latest.get('tdc_tier3_fiscal_corrected_bank_only_ru_flow'))}; "
        f"Fed {_format_millions(latest.get('fed_coupon_correction'))}; "
        f"Bank {_format_millions(latest.get('bank_coupon_correction'))}; "
        f"ROW {_format_millions(latest.get('row_coupon_correction'))}; "
        f"fiscal {_format_millions(latest.get('total_fiscal_correction'))}; "
        f"dominant correction: {latest.get('dominant_coupon_correction', 'n/a')}."
    )

    header = (
        "| Quarter | Base | Tier 1 | Tier 2 | Tier 3 | Fed corr | Bank corr | ROW corr | Coupon corr | Fiscal corr | Tier3-Tier2 | Dominant |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"
    )
    rows: list[str] = []
    for date, row in attribution.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(date).date().isoformat(),
                    _format_millions(row.get("tdc_base_bank_only_ru_flow")),
                    _format_millions(row.get("tdc_tier1_fed_corrected_bank_only_ru_flow")),
                    _format_millions(row.get("tdc_tier2_interest_corrected_bank_only_ru_flow")),
                    _format_millions(row.get("tdc_tier3_fiscal_corrected_bank_only_ru_flow")),
                    _format_millions(row.get("fed_coupon_correction")),
                    _format_millions(row.get("bank_coupon_correction")),
                    _format_millions(row.get("row_coupon_correction")),
                    _format_millions(row.get("total_coupon_correction")),
                    _format_millions(row.get("total_fiscal_correction")),
                    _format_millions(row.get("tier3_delta_from_tier2")),
                    str(row.get("dominant_coupon_correction", "n/a")),
                ]
            )
            + " |"
        )

    return "\n".join([title, "", intro, "", latest_summary, "", header, *rows, ""])


def write_post2022_bank_only_attribution(
    estimates: pd.DataFrame,
    corrections: pd.DataFrame,
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    start: str = DEFAULT_POST2022_START,
) -> tuple[Path, Path, pd.DataFrame]:
    attribution = build_post2022_bank_only_attribution(estimates, corrections, start=start)

    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = attribution.copy()
    to_write.index.name = "date"
    to_write.to_csv(csv_path)

    markdown_path = Path(markdown_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_post2022_bank_only_attribution_markdown(attribution), encoding="utf-8")

    return csv_path, markdown_path, attribution
