from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.mts_remittances import (
    build_monthly_fed_remittance_mts,
    monthly_fed_remittance_from_mts_receipts_csv,
    parse_fed_remittance_receipt_from_mts_text,
)


def test_parse_fed_remittance_receipt_from_mts_text_uses_current_month_net():
    text = """
Miscellaneous Receipts:
  Deposits of earnings by Federal Reserve Banks . . . . . . . . .                                                              1,879         ......        1,879        5,881        ......         5,881        5,539         ......         5,539
"""

    assert parse_fed_remittance_receipt_from_mts_text(text) == 1879.0


def test_build_monthly_fed_remittance_mts_uses_cached_pdfs(monkeypatch, tmp_path: Path):
    cache = tmp_path / "cache"
    cache.mkdir()
    pdf_path = cache / "MonthlyTreasuryStatement_200201.pdf"
    pdf_path.write_bytes(b"fake pdf")

    monkeypatch.setattr("tdc_estimator.mts_remittances.pdf_bytes_to_text", lambda payload: """
  Deposits of earnings by Federal Reserve Banks . . . . . . . . .                                                              1,912        ......        1,912        7,451        ......       7,451          7,739        ......       7,739
""")

    monthly = build_monthly_fed_remittance_mts(start="2002-01-31", end="2002-01-31", cache_dir=cache)

    assert monthly["date"].tolist() == [pd.Timestamp("2002-01-31")]
    assert monthly["value"].tolist() == [1912.0]


def test_monthly_fed_remittance_from_mts_receipts_csv_converts_dollars_to_millions(tmp_path: Path):
    path = tmp_path / "treasury__mts_receipts.csv"
    pd.DataFrame(
        {
            "record_date": ["2025-12-31"],
            "classification_desc": ["Deposit of Earnings, Federal Reserve System"],
            "current_month_net_rcpt_amt": [716_449_400.0],
        }
    ).to_csv(path, index=False)

    monthly = monthly_fed_remittance_from_mts_receipts_csv(path)

    assert monthly["date"].tolist() == [pd.Timestamp("2025-12-31")]
    assert round(float(monthly["value"].iloc[0]), 6) == 716.4494
