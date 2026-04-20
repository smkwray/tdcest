from __future__ import annotations

import pandas as pd

from tdc_estimator.bea_row_receipts_benchmark import (
    build_bea_row_receipts_benchmark,
    render_bea_row_receipts_benchmark_markdown,
)


def test_build_bea_row_receipts_benchmark_converts_saar_billions_to_quarterly_millions():
    quarterly = pd.DataFrame(
        {
            "bea_row_taxes_received_saar": [42.862],
            "bea_row_social_insurance_received_saar": [6.846],
            "bea_row_current_transfer_receipts_received_saar": [0.973],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )

    benchmark = build_bea_row_receipts_benchmark(quarterly)

    row = benchmark.iloc[0]
    assert round(row["bea_row_taxes_q_mil"], 3) == 10715.500
    assert round(row["bea_row_social_insurance_q_mil"], 3) == 1711.500
    assert round(row["bea_row_current_transfers_q_mil"], 3) == 243.250
    assert round(row["bea_row_current_receipts_total_q_mil"], 3) == 12670.250


def test_render_bea_row_receipts_benchmark_markdown_mentions_benchmark_only_role():
    benchmark = pd.DataFrame(
        {
            "bea_row_taxes_q_mil": [10715.5],
            "bea_row_social_insurance_q_mil": [1711.5],
            "bea_row_current_transfers_q_mil": [243.25],
            "bea_row_current_receipts_total_q_mil": [12670.25],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )

    markdown = render_bea_row_receipts_benchmark_markdown(benchmark)

    assert "BEA ROW Receipts Benchmark" in markdown
    assert "official macro benchmark" in markdown
    assert "2025-12-31" in markdown
