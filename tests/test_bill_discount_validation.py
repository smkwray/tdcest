from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.bill_discount_validation import (
    build_bill_discount_validation_from_files,
    build_bill_discount_validation_table,
    quarterly_treasury_bill_amortized_discount,
    summarize_bill_discount_validation,
)


def test_quarterly_treasury_bill_amortized_discount_filters_bill_discount_rows():
    treasury = pd.DataFrame(
        {
            "record_date": ["2025-01-31", "2025-02-28", "2025-03-31", "2025-03-31"],
            "expense_catg_desc": ["INTEREST EXPENSE ON PUBLIC ISSUES"] * 4,
            "expense_group_desc": ["AMORTIZED DISCOUNT", "AMORTIZED DISCOUNT", "AMORTIZED DISCOUNT", "ACCRUED INTEREST EXPENSE"],
            "expense_type_desc": ["Treasury Bills", "Treasury Bills", "Treasury Bills", "Treasury Notes"],
            "month_expense_amt": ["1000000000.00", "2000000000.00", "3000000000.00", "9000000000.00"],
        }
    )

    series = quarterly_treasury_bill_amortized_discount(treasury)

    assert round(float(series.loc[pd.Timestamp("2025-03-31")]), 6) == 6000.0


def test_build_bill_discount_validation_table_reports_proxy_shares():
    treasury = pd.DataFrame(
        {
            "record_date": ["2025-01-31", "2025-02-28", "2025-03-31"],
            "expense_catg_desc": ["INTEREST EXPENSE ON PUBLIC ISSUES"] * 3,
            "expense_group_desc": ["AMORTIZED DISCOUNT"] * 3,
            "expense_type_desc": ["Treasury Bills"] * 3,
            "month_expense_amt": ["1000000000", "2000000000", "3000000000"],
        }
    )
    index = pd.DatetimeIndex([pd.Timestamp("2025-03-31")])

    out = build_bill_discount_validation_table(
        treasury,
        bank_proxy=pd.Series([1000.0], index=index),
        row_proxy=pd.Series([2000.0], index=index),
        credit_union_proxy=pd.Series([100.0], index=index),
    )

    row = out.iloc[0]
    assert row["treasury_bill_amortized_discount_mil"] == 6000.0
    assert row["bank_row_proxy_mil"] == 3000.0
    assert row["bank_row_cu_proxy_mil"] == 3100.0
    assert round(row["bank_row_share_of_aggregate"], 6) == 0.5
    assert round(row["bank_row_cu_share_of_aggregate"], 6) == round(3100.0 / 6000.0, 6)
    assert row["has_treasury_bill_benchmark"]
    assert row["has_all_sector_proxies"]


def test_build_bill_discount_validation_from_files_and_summary(tmp_path: Path):
    treasury_path = tmp_path / "treasury__interest_expense.csv"
    bank_path = tmp_path / "support__bank_tsy_bill_discount_interest_proxy.csv"
    row_path = tmp_path / "support__row_tsy_bill_discount_interest_proxy.csv"
    cu_path = tmp_path / "support__credit_union_tsy_bill_discount_interest_proxy.csv"
    pd.DataFrame(
        {
            "record_date": ["2025-10-31", "2025-11-30", "2025-12-31"],
            "expense_group_desc": ["AMORTIZED DISCOUNT"] * 3,
            "expense_type_desc": ["Treasury Bills"] * 3,
            "month_expense_amt": ["22000000000", "21000000000", "23000000000"],
        }
    ).to_csv(treasury_path, index=False)
    pd.DataFrame({"date": ["2025-12-31"], "value": [5000.0]}).to_csv(bank_path, index=False)
    pd.DataFrame({"date": ["2025-12-31"], "row_tsy_bill_discount_interest_proxy": [13000.0]}).to_csv(
        row_path, index=False
    )
    pd.DataFrame({"date": ["2025-12-31"], "credit_union_tsy_bill_discount_interest_proxy": [125.0]}).to_csv(
        cu_path, index=False
    )

    out = build_bill_discount_validation_from_files(
        treasury_interest_path=treasury_path,
        bank_proxy_path=bank_path,
        row_proxy_path=row_path,
        credit_union_proxy_path=cu_path,
    )
    summary = summarize_bill_discount_validation(out)

    assert out.loc[0, "treasury_bill_amortized_discount_mil"] == 66000.0
    assert "Latest quarter (2025-12-31)" in summary
    assert "bank+ROW+credit-union proxy" in summary
