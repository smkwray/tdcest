from __future__ import annotations

import pandas as pd

from tdc_estimator.tier3_pre2003_feasibility import (
    build_tier3_pre2003_feasibility_panel,
    render_tier3_pre2003_feasibility_markdown,
)


def test_build_tier3_pre2003_feasibility_panel_keeps_bank_terms_blank(tmp_path) -> None:
    outlays = tmp_path / "outlays.csv"
    receipts = tmp_path / "receipts.csv"
    pd.DataFrame(
        [
            ["1999-01-31", "International Disaster Assistance", 10_000_000.0],
            ["1999-02-28", "United States Mint", -3_000_000.0],
            ["1999-03-31", "Foreign Agricultural Service", 20_000_000.0],
        ],
        columns=["record_date", "classification_desc", "current_month_net_outly_amt"],
    ).to_csv(outlays, index=False)
    pd.DataFrame(
        [
            ["1999-01-31", "Corporation Income Taxes", 100_000_000.0, 10_000_000.0, 90_000_000.0],
        ],
        columns=[
            "record_date",
            "classification_desc",
            "current_month_gross_rcpt_amt",
            "current_month_refund_amt",
            "current_month_net_rcpt_amt",
        ],
    ).to_csv(receipts, index=False)
    bea = pd.DataFrame({"bea_row_current_receipts_total_q_mil": [50.0]}, index=pd.to_datetime(["1999-03-31"]))

    panel = build_tier3_pre2003_feasibility_panel(
        mts_outlays_path=outlays,
        mts_receipts_path=receipts,
        bea_row_anchor=bea,
        start="1999-03-31",
        end="1999-03-31",
    )

    row = panel.iloc[0]
    assert pd.isna(row["bank_outlay_direct_mil"])
    assert pd.isna(row["bank_receipt_bridge_mil"])
    assert bool(row["missing_bank_outlay_fas"])
    assert bool(row["missing_bank_receipt_share"])
    assert round(float(row["partial_tier3_pre2003_correction_mil"]), 3) == 23.0


def test_render_tier3_pre2003_feasibility_markdown_marks_not_full_vintage() -> None:
    panel = pd.DataFrame(
        {
            "partial_tier3_pre2003_correction_mil": [1.0],
        },
        index=pd.to_datetime(["1999-03-31"]),
    )

    markdown = render_tier3_pre2003_feasibility_markdown(panel)

    assert "not a full Tier 3 vintage" in markdown
    assert "Average partial correction" in markdown
