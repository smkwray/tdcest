from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.row_mrv_bea_overlay import (
    build_row_mrv_bea_overlay,
    render_row_mrv_bea_overlay_markdown,
    write_row_mrv_bea_overlay_from_paths,
)


def test_build_row_mrv_bea_overlay_keeps_mrv_non_additive_and_flags_fy2019_plus() -> None:
    anchor = pd.DataFrame(
        {"bea_row_current_receipts_total_q_mil": [1000.0]},
        index=pd.to_datetime(["2025-03-31"]),
    )
    timing = pd.DataFrame(
        {
            "row_state_mrv_cbsp_allocated_receipt_mil": [100.0],
            "row_state_visa_secondary_allocated_receipt_mil": [20.0],
            "row_state_visa_total_allocated_receipt_mil": [120.0],
            "state_mrv_source_fiscal_year": [2025],
        },
        index=pd.to_datetime(["2025-03-31"]),
    )

    overlay = build_row_mrv_bea_overlay(anchor, timing, start="2025-03-31")

    row = overlay.iloc[0]
    assert row["non_additive_rule"] == "do_not_add_mrv_to_bea_anchor"
    assert row["non_additive_bea_anchor_total_q_mil"] == 1000.0
    assert pd.isna(row["additive_bea_plus_mrv_total_q_mil"])
    assert round(float(row["mrv_primary_share_of_bea_row_anchor"]), 3) == 0.1
    assert bool(row["fy2019_plus_visa_methodology_break"])
    assert not bool(row["default_eligible"])


def test_write_row_mrv_bea_overlay_from_paths_outputs_artifact(tmp_path: Path) -> None:
    anchor_path = tmp_path / "anchor.csv"
    timing_path = tmp_path / "timing.csv"
    pd.DataFrame(
        {"date": ["2025-03-31"], "bea_row_current_receipts_total_q_mil": [1000.0]},
    ).to_csv(anchor_path, index=False)
    pd.DataFrame(
        {
            "date": ["2025-03-31"],
            "row_state_mrv_cbsp_allocated_receipt_mil": [100.0],
            "row_state_visa_secondary_allocated_receipt_mil": [20.0],
            "row_state_visa_total_allocated_receipt_mil": [120.0],
            "state_mrv_source_fiscal_year": [2025],
        }
    ).to_csv(timing_path, index=False)

    csv_path = tmp_path / "overlay.csv"
    md_path = tmp_path / "overlay.md"
    _, _, overlay = write_row_mrv_bea_overlay_from_paths(
        bea_anchor_path=anchor_path,
        row_state_visa_timing_sensitivity_path=timing_path,
        csv_path=csv_path,
        markdown_path=md_path,
        start="2025-03-31",
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(overlay)
    markdown = render_row_mrv_bea_overlay_markdown(overlay)
    assert "Nondefault MRV / CBSP overlay" in markdown
    assert "intentionally blank" in markdown
