from __future__ import annotations

from pathlib import Path

import pandas as pd

BEA_ROW_RECEIPT_COMPONENTS = {
    "bea_row_taxes_received_saar": "bea_row_taxes_q_mil",
    "bea_row_social_insurance_received_saar": "bea_row_social_insurance_q_mil",
    "bea_row_current_transfer_receipts_received_saar": "bea_row_current_transfers_q_mil",
}
BEA_ROW_RECEIPT_SERIES_IDS = {
    "bea_row_taxes_received_saar": "W008RC1Q027SBEA",
    "bea_row_social_insurance_received_saar": "W781RC1Q027SBEA",
    "bea_row_current_transfer_receipts_received_saar": "LA0000281Q027SBEA",
}
BEA_ROW_RECEIPT_CONVERSION_METHOD = "saar_divide_by_4"
BEA_ROW_ITA_CROSSCHECK_SERIES_IDS = {
    "ita_secondary_income_receipts": "IEAXSIR",
    "ita_total_receipts_credits": "IEAX",
}


def build_bea_row_receipts_benchmark(
    quarterly: pd.DataFrame,
    *,
    start: str = "2022-09-30",
) -> pd.DataFrame:
    missing = [key for key in BEA_ROW_RECEIPT_COMPONENTS if key not in quarterly.columns]
    if missing:
        return pd.DataFrame()

    out = pd.DataFrame(index=quarterly.index)
    for source_key, out_key in BEA_ROW_RECEIPT_COMPONENTS.items():
        out[out_key] = pd.to_numeric(quarterly[source_key], errors="coerce") * 250.0
    out["bea_row_current_receipts_total_q_mil"] = out.sum(axis=1, min_count=1)
    out["conversion_method"] = BEA_ROW_RECEIPT_CONVERSION_METHOD
    out["source_series_ids"] = "|".join(BEA_ROW_RECEIPT_SERIES_IDS.values())
    out["source_role"] = "bea_nipa_macro_anchor_not_treasury_cash_payer"
    return out.loc[out.index >= pd.Timestamp(start)].copy()


def _read_fred_quarterly_series(path: Path | str, *, value_key: str) -> pd.Series:
    frame = pd.read_csv(path)
    normalized_columns = {str(column).strip().lower(): column for column in frame.columns}
    date_column = normalized_columns.get("date") or normalized_columns.get("observation_date")
    value_column = normalized_columns.get("value")
    if date_column is None:
        raise ValueError(f"FRED file {path} is missing required column: date")
    if value_column is None:
        candidate_columns = [column for column in frame.columns if column != date_column]
        if len(candidate_columns) != 1:
            raise ValueError(f"FRED file {path} is missing required column: value")
        value_column = candidate_columns[0]

    dates = pd.to_datetime(frame[date_column], errors="coerce")
    values = pd.to_numeric(frame[value_column], errors="coerce")
    out = pd.Series(values.to_numpy(), index=dates.dt.to_period("Q").dt.to_timestamp("Q"), name=value_key)
    return out.dropna().sort_index()


def build_bea_row_receipts_benchmark_from_fred_paths(
    *,
    taxes_path: Path | str,
    social_insurance_path: Path | str,
    current_transfers_path: Path | str,
    start: str = "2003-03-31",
) -> pd.DataFrame:
    series = [
        _read_fred_quarterly_series(taxes_path, value_key="bea_row_taxes_received_saar"),
        _read_fred_quarterly_series(social_insurance_path, value_key="bea_row_social_insurance_received_saar"),
        _read_fred_quarterly_series(current_transfers_path, value_key="bea_row_current_transfer_receipts_received_saar"),
    ]
    quarterly = pd.concat(series, axis=1).sort_index()
    return build_bea_row_receipts_benchmark(quarterly, start=start)


def build_bea_row_receipts_ita_crosscheck(
    benchmark: pd.DataFrame,
    *,
    secondary_income_receipts: pd.Series,
    total_receipts_credits: pd.Series,
) -> pd.DataFrame:
    if benchmark.empty:
        return pd.DataFrame()

    out = benchmark.copy()
    out["ita_secondary_income_receipts_q_mil"] = secondary_income_receipts.reindex(out.index)
    out["ita_total_receipts_credits_q_mil"] = total_receipts_credits.reindex(out.index)
    total = pd.to_numeric(out["bea_row_current_receipts_total_q_mil"], errors="coerce")
    secondary = pd.to_numeric(out["ita_secondary_income_receipts_q_mil"], errors="coerce")
    credits = pd.to_numeric(out["ita_total_receipts_credits_q_mil"], errors="coerce")
    out["bea_row_share_of_ita_secondary_income_receipts"] = total / secondary
    out["bea_row_share_of_ita_total_receipts_credits"] = total / credits
    out["ita_crosscheck_source_series_ids"] = "|".join(BEA_ROW_ITA_CROSSCHECK_SERIES_IDS.values())
    out["ita_crosscheck_source_role"] = "ita_scale_crosscheck_not_treasury_cash_payer"
    out["row_anchor_exceeds_ita_secondary_income"] = total > secondary
    return out


def build_bea_row_receipts_ita_crosscheck_from_fred_paths(
    *,
    taxes_path: Path | str,
    social_insurance_path: Path | str,
    current_transfers_path: Path | str,
    secondary_income_receipts_path: Path | str,
    total_receipts_credits_path: Path | str,
    start: str = "2003-03-31",
) -> pd.DataFrame:
    benchmark = build_bea_row_receipts_benchmark_from_fred_paths(
        taxes_path=taxes_path,
        social_insurance_path=social_insurance_path,
        current_transfers_path=current_transfers_path,
        start=start,
    )
    secondary_income = _read_fred_quarterly_series(
        secondary_income_receipts_path,
        value_key="ita_secondary_income_receipts_q_mil",
    )
    total_receipts = _read_fred_quarterly_series(
        total_receipts_credits_path,
        value_key="ita_total_receipts_credits_q_mil",
    )
    return build_bea_row_receipts_ita_crosscheck(
        benchmark,
        secondary_income_receipts=secondary_income,
        total_receipts_credits=total_receipts,
    )


def render_bea_row_receipts_benchmark_markdown(benchmark: pd.DataFrame) -> str:
    title = "# BEA ROW Receipts Benchmark"
    intro = (
        "Quarter-by-quarter BEA/NIPA benchmark for federal current receipts from the rest of the world. "
        "Amounts are in quarterly millions after converting FRED/BEA quarterly SAAR series using `saar_divide_by_4` "
        "(`billions * 1,000 / 4`). "
        "This is an official macro benchmark, not a default Treasury cash-payer correction."
    )
    if benchmark.empty:
        return "\n".join([title, "", intro, "", "Required BEA/FRED component series are not loaded."])

    latest_date = benchmark.index.max()
    latest = benchmark.loc[latest_date]
    latest_summary = (
        f"Latest benchmark quarter: {pd.Timestamp(latest_date).date().isoformat()}. "
        f"Taxes from ROW {float(latest['bea_row_taxes_q_mil']):,.3f}; "
        f"social insurance from ROW {float(latest['bea_row_social_insurance_q_mil']):,.3f}; "
        f"current transfers from ROW {float(latest['bea_row_current_transfers_q_mil']):,.3f}; "
        f"total {float(latest['bea_row_current_receipts_total_q_mil']):,.3f}."
    )

    header = (
        "| Quarter | Taxes from ROW | Social insurance from ROW | Current transfers from ROW | Total |\n"
        "| --- | ---: | ---: | ---: | ---: |"
    )
    rows = [
        "| "
        + " | ".join(
            [
                pd.Timestamp(date).date().isoformat(),
                f"{float(row['bea_row_taxes_q_mil']):,.3f}",
                f"{float(row['bea_row_social_insurance_q_mil']):,.3f}",
                f"{float(row['bea_row_current_transfers_q_mil']):,.3f}",
                f"{float(row['bea_row_current_receipts_total_q_mil']):,.3f}",
            ]
        )
        + " |"
        for date, row in benchmark.iterrows()
    ]
    notes = [
        "Notes:",
        "- Component series are BEA/FRED Table 3.2 concepts: taxes from the rest of the world (`W008RC1Q027SBEA`), social-insurance contributions from the rest of the world (`W781RC1Q027SBEA`), and current transfer receipts from the rest of the world (`LA0000281Q027SBEA`).",
        "- This benchmark is useful for scale checks and coverage ratios, but it does not identify the actual Treasury cash payer or debited-account residency.",
    ]
    return "\n".join([title, "", intro, "", latest_summary, "", header, *rows, "", *notes, ""])


def render_bea_row_receipts_ita_crosscheck_markdown(crosscheck: pd.DataFrame) -> str:
    title = "# BEA ROW Receipts ITA Cross-Check"
    intro = (
        "Scale check for the BEA/NIPA rest-of-world federal receipts anchor against BEA international "
        "transactions account receipts. Amounts are quarterly millions. This artifact is diagnostic only; "
        "it does not identify Treasury cash payers or authorize adding ITA and BEA receipts together."
    )
    if crosscheck.empty:
        return "\n".join([title, "", intro, "", "Required BEA/FRED and ITA/FRED series are not loaded."])

    latest_date = crosscheck.index.max()
    latest = crosscheck.loc[latest_date]
    latest_summary = (
        f"Latest cross-check quarter: {pd.Timestamp(latest_date).date().isoformat()}. "
        f"BEA ROW federal receipts {float(latest['bea_row_current_receipts_total_q_mil']):,.3f}; "
        f"ITA secondary-income receipts {float(latest['ita_secondary_income_receipts_q_mil']):,.3f}; "
        f"ROW share of ITA secondary-income receipts "
        f"{float(latest['bea_row_share_of_ita_secondary_income_receipts']):.3%}."
    )
    status_counts = crosscheck["row_anchor_exceeds_ita_secondary_income"].value_counts(dropna=False).to_dict()
    header = (
        "| Quarter | BEA ROW federal receipts | ITA secondary-income receipts | ITA total credits | ROW / secondary income | ROW / total credits |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: |"
    )
    rows = [
        "| "
        + " | ".join(
            [
                pd.Timestamp(date).date().isoformat(),
                f"{float(row['bea_row_current_receipts_total_q_mil']):,.3f}",
                f"{float(row['ita_secondary_income_receipts_q_mil']):,.3f}",
                f"{float(row['ita_total_receipts_credits_q_mil']):,.3f}",
                f"{float(row['bea_row_share_of_ita_secondary_income_receipts']):.3%}",
                f"{float(row['bea_row_share_of_ita_total_receipts_credits']):.3%}",
            ]
        )
        + " |"
        for date, row in crosscheck.iterrows()
    ]
    notes = [
        "Notes:",
        "- ITA/FRED cross-check series are secondary-income receipts (`IEAXSIR`) and total exports of goods, services, and income receipts credits (`IEAX`).",
        f"- Anchor-exceeds-secondary-income flags: {status_counts}.",
        "- The BEA ROW federal receipts anchor and ITA receipt aggregates are overlapping macro-account concepts, so the ratios are scale checks only.",
    ]
    return "\n".join([title, "", intro, "", latest_summary, "", header, *rows, "", *notes, ""])


def write_bea_row_receipts_benchmark(
    quarterly: pd.DataFrame,
    *,
    csv_path: Path | str,
    markdown_path: Path | str,
    start: str = "2022-09-30",
) -> tuple[Path, Path, pd.DataFrame]:
    benchmark = build_bea_row_receipts_benchmark(quarterly, start=start)

    csv_path = Path(csv_path)
    markdown_path = Path(markdown_path)
    if benchmark.empty:
        return csv_path, markdown_path, benchmark

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = benchmark.copy()
    to_write.index.name = "date"
    to_write.to_csv(csv_path)

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_bea_row_receipts_benchmark_markdown(benchmark), encoding="utf-8")

    return csv_path, markdown_path, benchmark


def write_bea_row_receipts_benchmark_from_fred_paths(
    *,
    taxes_path: Path | str,
    social_insurance_path: Path | str,
    current_transfers_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str,
    start: str = "2003-03-31",
) -> tuple[Path, Path, pd.DataFrame]:
    benchmark = build_bea_row_receipts_benchmark_from_fred_paths(
        taxes_path=taxes_path,
        social_insurance_path=social_insurance_path,
        current_transfers_path=current_transfers_path,
        start=start,
    )

    csv_path = Path(csv_path)
    markdown_path = Path(markdown_path)
    if benchmark.empty:
        return csv_path, markdown_path, benchmark

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = benchmark.copy()
    to_write.index.name = "date"
    to_write.to_csv(csv_path)

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_bea_row_receipts_benchmark_markdown(benchmark), encoding="utf-8")
    return csv_path, markdown_path, benchmark


def write_bea_row_receipts_ita_crosscheck_from_fred_paths(
    *,
    taxes_path: Path | str,
    social_insurance_path: Path | str,
    current_transfers_path: Path | str,
    secondary_income_receipts_path: Path | str,
    total_receipts_credits_path: Path | str,
    csv_path: Path | str,
    markdown_path: Path | str,
    start: str = "2003-03-31",
) -> tuple[Path, Path, pd.DataFrame]:
    crosscheck = build_bea_row_receipts_ita_crosscheck_from_fred_paths(
        taxes_path=taxes_path,
        social_insurance_path=social_insurance_path,
        current_transfers_path=current_transfers_path,
        secondary_income_receipts_path=secondary_income_receipts_path,
        total_receipts_credits_path=total_receipts_credits_path,
        start=start,
    )

    csv_path = Path(csv_path)
    markdown_path = Path(markdown_path)
    if crosscheck.empty:
        return csv_path, markdown_path, crosscheck

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = crosscheck.copy()
    to_write.index.name = "date"
    to_write.to_csv(csv_path)

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_bea_row_receipts_ita_crosscheck_markdown(crosscheck), encoding="utf-8")
    return csv_path, markdown_path, crosscheck
