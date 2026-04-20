from __future__ import annotations

from pathlib import Path

import pandas as pd

BEA_ROW_RECEIPT_COMPONENTS = {
    "bea_row_taxes_received_saar": "bea_row_taxes_q_mil",
    "bea_row_social_insurance_received_saar": "bea_row_social_insurance_q_mil",
    "bea_row_current_transfer_receipts_received_saar": "bea_row_current_transfers_q_mil",
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
    return out.loc[out.index >= pd.Timestamp(start)].copy()


def render_bea_row_receipts_benchmark_markdown(benchmark: pd.DataFrame) -> str:
    title = "# BEA ROW Receipts Benchmark"
    intro = (
        "Quarter-by-quarter BEA/NIPA benchmark for federal current receipts from the rest of the world. "
        "Amounts are in quarterly millions after converting FRED/BEA quarterly SAAR series using `billions * 250`. "
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
        "- Component series are BEA/FRED Table 3.2 concepts: taxes from the rest of the world, social-insurance contributions from the rest of the world, and current transfer receipts from the rest of the world.",
        "- This benchmark is useful for scale checks and coverage ratios, but it does not identify the actual Treasury cash payer or debited-account residency.",
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
