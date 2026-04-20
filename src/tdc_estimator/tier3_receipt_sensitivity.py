from __future__ import annotations

from pathlib import Path

import pandas as pd


DEFAULT_START = "2022-09-30"


def _maybe(df: pd.DataFrame, column: str) -> pd.Series:
    if column in df.columns:
        return df[column]
    return pd.Series(index=df.index, dtype="float64")


def _format_millions(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.3f}"


def build_tier3_bank_receipt_upper_bound_sensitivity(
    estimates: pd.DataFrame,
    receipt_diagnostics: pd.DataFrame,
    *,
    start: str = DEFAULT_START,
) -> pd.DataFrame:
    if "rcm_bank_channel_total_candidate" not in receipt_diagnostics.columns:
        return pd.DataFrame()

    index = pd.DatetimeIndex(sorted(estimates.index.union(receipt_diagnostics.index)))
    frame = pd.DataFrame(index=index)
    frame["tdc_tier3_fiscal_corrected_bank_only_ru_flow"] = _maybe(
        estimates, "tdc_tier3_fiscal_corrected_bank_only_ru_flow"
    ).reindex(index)
    frame["rcm_bank_channel_total_candidate"] = _maybe(
        receipt_diagnostics, "rcm_bank_channel_total_candidate"
    ).reindex(index)
    frame["rcm_bank_channel_non_tax_candidate"] = _maybe(
        receipt_diagnostics, "rcm_bank_channel_non_tax_candidate"
    ).reindex(index)
    frame["tdc_tier3_bank_only_plus_rcm_bank_channel_total_upper_bound"] = (
        frame["tdc_tier3_fiscal_corrected_bank_only_ru_flow"] + frame["rcm_bank_channel_total_candidate"]
    )
    frame["tdc_tier3_bank_only_plus_rcm_bank_channel_non_tax_upper_bound"] = (
        frame["tdc_tier3_fiscal_corrected_bank_only_ru_flow"] + frame["rcm_bank_channel_non_tax_candidate"]
    )
    frame["rcm_bank_channel_total_upper_bound_delta"] = frame["rcm_bank_channel_total_candidate"]
    frame["rcm_bank_channel_non_tax_upper_bound_delta"] = frame["rcm_bank_channel_non_tax_candidate"]

    frame = frame.loc[pd.to_datetime(frame.index) >= pd.Timestamp(start)].copy()
    frame = frame.dropna(
        subset=[
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow",
            "rcm_bank_channel_total_candidate",
        ],
        how="any",
    )
    return frame


def render_tier3_bank_receipt_upper_bound_sensitivity_markdown(sensitivity: pd.DataFrame) -> str:
    title = "# Tier 3 Bank-Receipt Upper-Bound Sensitivity"
    intro = (
        "Quarter-by-quarter upper-bound sensitivity that adds Treasury Revenue Collections `Bank` channel "
        "totals to the default Tier 3 bank-only series. Amounts are in millions. This is not a default "
        "estimator correction. It is a routing-heavy upper bound that asks what the bank-only Tier 3 path "
        "would look like if the visible Revenue Collections `Bank` channel were treated as a bank-sector "
        "nonborrow receipt flow."
    )
    if sensitivity.empty:
        return "\n".join([title, "", intro, "", "No Revenue Collections bank-channel sensitivity is available."])

    latest_date = sensitivity.index.max()
    latest = sensitivity.loc[latest_date]
    latest_summary = (
        f"Latest source-covered quarter: {pd.Timestamp(latest_date).date().isoformat()}. "
        f"Default Tier 3 {_format_millions(latest.get('tdc_tier3_fiscal_corrected_bank_only_ru_flow'))}; "
        f"RCM bank-channel candidate {_format_millions(latest.get('rcm_bank_channel_total_candidate'))}; "
        f"RCM bank non-tax candidate {_format_millions(latest.get('rcm_bank_channel_non_tax_candidate'))}; "
        f"upper-bound total {_format_millions(latest.get('tdc_tier3_bank_only_plus_rcm_bank_channel_total_upper_bound'))}; "
        f"upper-bound non-tax {_format_millions(latest.get('tdc_tier3_bank_only_plus_rcm_bank_channel_non_tax_upper_bound'))}."
    )

    header = (
        "| Quarter | Default Tier 3 | RCM bank cand. | RCM bank non-tax | Upper-bound total | Upper-bound non-tax |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: |"
    )
    rows: list[str] = []
    for date, row in sensitivity.iterrows():
        rows.append(
            "| "
            + " | ".join(
                [
                    pd.Timestamp(date).date().isoformat(),
                    _format_millions(row.get("tdc_tier3_fiscal_corrected_bank_only_ru_flow")),
                    _format_millions(row.get("rcm_bank_channel_total_candidate")),
                    _format_millions(row.get("rcm_bank_channel_non_tax_candidate")),
                    _format_millions(row.get("tdc_tier3_bank_only_plus_rcm_bank_channel_total_upper_bound")),
                    _format_millions(row.get("tdc_tier3_bank_only_plus_rcm_bank_channel_non_tax_upper_bound")),
                ]
            )
            + " |"
        )

    notes = [
        "Notes:",
        "- The default Tier 3 series remains unchanged and continues to exclude bank nonborrow receipt corrections.",
        "- Revenue Collections `Bank` reflects payment-routing through banking networks, not a clean bank-sector counterparty flow.",
        "- The `non-tax` variant is included as a narrower upper bound, not as a preferred correction.",
    ]

    return "\n".join([title, "", intro, "", latest_summary, "", header, *rows, "", *notes, ""])


def write_tier3_bank_receipt_upper_bound_sensitivity(
    estimates: pd.DataFrame,
    receipt_diagnostics: pd.DataFrame,
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    start: str = DEFAULT_START,
) -> tuple[Path, Path, pd.DataFrame]:
    sensitivity = build_tier3_bank_receipt_upper_bound_sensitivity(
        estimates,
        receipt_diagnostics,
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
        render_tier3_bank_receipt_upper_bound_sensitivity_markdown(sensitivity),
        encoding="utf-8",
    )

    return csv_path, markdown_path, sensitivity
