from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.tier3_research_comparison import (
    build_tier3_research_comparison,
    render_tier3_research_comparison_markdown,
    write_tier3_research_comparison,
)


def _sample_estimates() -> pd.DataFrame:
    idx = pd.to_datetime(["2024-12-31", "2025-12-31"])
    return pd.DataFrame(
        {
            "tdc_tier2_interest_corrected_bank_only_ru_flow": [90.0, 80.0],
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [96.0, 70.0],
        },
        index=idx,
    )


def _sample_historical() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2024-12-31",
                "tdc_tier3_fiscal_corrected_bank_only_ru_flow": 96.0,
                "tdc_tier3_bank_only_plus_historical_bank_receipt_candidate": 103.0,
                "tdc_tier3_bank_only_plus_historical_bank_receipt_lower_bound": 98.0,
            }
        ]
    )


def _sample_receipt_status() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "branch_key": "bank_table51_historical_window",
                "promotion_boundary": "historical_default_only_current_nondefault",
            },
            {
                "branch_key": "bank_table51_current_window",
                "promotion_boundary": "historical_default_only_current_nondefault",
                "latest_relevant_date": "2026-03-31",
                "latest_value_millions": 3032.789,
            },
            {
                "branch_key": "row_mrv_cbsp_primary",
                "promotion_boundary": "stop_at_mrv_nondefault_pilot",
                "latest_value_millions": 578.399,
            },
        ]
    )


def test_build_tier3_research_comparison_includes_live_and_historical_rows() -> None:
    frame = build_tier3_research_comparison(
        estimates=_sample_estimates(),
        tier3_historical_bank_receipt_research=_sample_historical(),
        receipt_unblock_status=_sample_receipt_status(),
    )

    assert frame["comparison_key"].isin(["latest_live_tier2_vs_partial_shell", "latest_historical_bank_window"]).all()
    hist = frame.loc[frame["comparison_key"].eq("latest_historical_bank_window")].iloc[0]
    assert float(hist["historical_bank_receipt_variant_mil"]) == 103.0


def test_write_tier3_research_comparison_outputs(tmp_path: Path) -> None:
    csv_path = tmp_path / "tier3_research_comparison.csv"
    markdown_path = tmp_path / "tier3_research_comparison.md"

    _, _, frame = write_tier3_research_comparison(
        csv_path=csv_path,
        markdown_path=markdown_path,
        estimates=_sample_estimates(),
        tier3_historical_bank_receipt_research=_sample_historical(),
        receipt_unblock_status=_sample_receipt_status(),
    )

    assert csv_path.exists()
    assert markdown_path.exists()
    assert len(pd.read_csv(csv_path)) == len(frame)
    markdown = render_tier3_research_comparison_markdown(frame)
    assert "Tier 3 Research Comparison" in markdown
    assert "latest_historical_bank_window" in markdown
