from __future__ import annotations

import pandas as pd

from tdc_estimator.tier3_receipts_source import (
    build_tier3_receipt_source_diagnostics,
    render_tier3_receipt_source_diagnostics_markdown,
)


def test_build_tier3_receipt_source_diagnostics_tracks_candidates_but_keeps_defaults_zero(tmp_path):
    receipts_path = tmp_path / "mts_receipts.csv"
    pd.DataFrame(
        [
            ["2025-04-30", "Deposit of Earnings, Federal Reserve System", 100_000_000.0],
            ["2025-05-31", "Deposit of Earnings, Federal Reserve System", 110_000_000.0],
            ["2025-06-30", "Deposit of Earnings, Federal Reserve System", 120_000_000.0],
            ["2025-04-30", "Customs Duties", 200_000_000.0],
            ["2025-05-31", "Customs Duties", 300_000_000.0],
            ["2025-06-30", "Customs Duties", 400_000_000.0],
            ["2025-04-30", "Deposits by States", 500_000_000.0],
            ["2025-05-31", "Deposits by States", 100_000_000.0],
            ["2025-06-30", "Deposits by States", 200_000_000.0],
        ],
        columns=["record_date", "classification_desc", "current_month_net_rcpt_amt"],
    ).to_csv(receipts_path, index=False)

    diagnostics = build_tier3_receipt_source_diagnostics(mts_receipts_path=receipts_path, start="2025-03-31")

    assert list(diagnostics.index) == list(pd.to_datetime(["2025-06-30"]))
    row = diagnostics.loc[pd.Timestamp("2025-06-30")]
    assert round(row["fed_earnings_receipts_candidate"], 6) == 330.0
    assert round(row["customs_duties_candidate"], 6) == 900.0
    assert round(row["deposits_by_states_candidate"], 6) == 800.0
    assert round(row["bank_nonborrow_receipt_included_default"], 6) == 0.0
    assert round(row["row_nonborrow_receipt_included_default"], 6) == 0.0


def test_build_tier3_receipt_source_diagnostics_can_include_revenue_collections_bank_channel(tmp_path):
    receipts_path = tmp_path / "mts_receipts.csv"
    rcm_path = tmp_path / "revenue_collections.csv"

    pd.DataFrame(
        [
            ["2025-04-30", "Deposit of Earnings, Federal Reserve System", 100_000_000.0],
            ["2025-05-31", "Deposit of Earnings, Federal Reserve System", 110_000_000.0],
            ["2025-06-30", "Deposit of Earnings, Federal Reserve System", 120_000_000.0],
        ],
        columns=["record_date", "classification_desc", "current_month_net_rcpt_amt"],
    ).to_csv(receipts_path, index=False)

    pd.DataFrame(
        [
            ["2025-04-30", "Bank", "Non-Tax", 200_000_000.0],
            ["2025-05-31", "Bank", "IRS Tax", 300_000_000.0],
            ["2025-06-30", "Bank", "IRS Non-Tax", 400_000_000.0],
            ["2025-06-30", "Internet", "Non-Tax", 900_000_000.0],
        ],
        columns=["record_date", "channel_type_desc", "tax_category_desc", "net_collections_amt"],
    ).to_csv(rcm_path, index=False)

    diagnostics = build_tier3_receipt_source_diagnostics(
        mts_receipts_path=receipts_path,
        revenue_collections_path=rcm_path,
        start="2025-03-31",
    )

    row = diagnostics.loc[pd.Timestamp("2025-06-30")]
    assert round(row["rcm_bank_channel_total_candidate"], 6) == 900.0
    assert round(row["rcm_bank_channel_non_tax_candidate"], 6) == 200.0
    assert round(row["rcm_bank_channel_irs_tax_candidate"], 6) == 300.0
    assert round(row["rcm_bank_channel_irs_nontax_candidate"], 6) == 400.0
    assert round(row["bank_nonborrow_receipt_included_default"], 6) == 0.0


def test_render_tier3_receipt_source_diagnostics_markdown_includes_exclusion_notes():
    diagnostics = pd.DataFrame(
        {
            "fed_earnings_receipts_candidate": [330.0],
            "customs_duties_candidate": [900.0],
            "deposits_by_states_candidate": [800.0],
            "rcm_bank_channel_total_candidate": [900.0],
            "rcm_bank_channel_non_tax_candidate": [200.0],
            "bank_nonborrow_receipt_included_default": [0.0],
            "row_nonborrow_receipt_included_default": [0.0],
        },
        index=pd.to_datetime(["2025-06-30"]),
    )

    markdown = render_tier3_receipt_source_diagnostics_markdown(diagnostics)

    assert "Latest source-covered quarter: 2025-06-30." in markdown
    assert "RCM bank-channel candidate 900.000" in markdown
    assert "default bank receipt included 0.000" in markdown
    assert "Customs Duties" in markdown
    assert "domestic importer" in markdown
    assert "routing through banking networks" in markdown
