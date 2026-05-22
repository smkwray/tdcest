from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.bill_discount_allocator import (
    build_bill_discount_allocation_table,
    summarize_bill_discount_allocation,
    write_bill_discount_allocation,
)


def test_build_bill_discount_allocation_keeps_explicit_residual():
    validation = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "treasury_bill_amortized_discount_mil": [1000.0],
            "bank_tsy_bill_discount_interest_proxy": [100.0],
            "row_tsy_bill_discount_interest_proxy": [250.0],
            "credit_union_tsy_bill_discount_interest_proxy": [10.0],
        }
    )

    out = build_bill_discount_allocation_table(validation)

    by_sector = out.set_index("sector_key")
    assert by_sector.loc["bank", "bill_discount_proxy_mil"] == 100.0
    assert by_sector.loc["row", "proxy_share_of_official_pool"] == 0.25
    assert by_sector.loc["credit_union", "is_selected_tier2_subtraction_sector"]
    assert by_sector.loc["unallocated_residual", "bill_discount_proxy_mil"] == 640.0
    assert not by_sector.loc["unallocated_residual", "is_selected_tier2_subtraction_sector"]


def test_write_bill_discount_allocation_and_summary(tmp_path: Path):
    treasury_path = tmp_path / "treasury__interest_expense.csv"
    bank_path = tmp_path / "support__bank_tsy_bill_discount_interest_proxy.csv"
    row_path = tmp_path / "support__row_tsy_bill_discount_interest_proxy.csv"
    cu_path = tmp_path / "support__credit_union_tsy_bill_discount_interest_proxy.csv"
    csv_path = tmp_path / "sector_bill_discount_allocations.csv"
    md_path = tmp_path / "bill_discount_allocation_validation.md"

    pd.DataFrame(
        {
            "record_date": ["2025-10-31", "2025-11-30", "2025-12-31"],
            "expense_catg_desc": ["INTEREST EXPENSE ON PUBLIC ISSUES"] * 3,
            "expense_group_desc": ["AMORTIZED DISCOUNT"] * 3,
            "expense_type_desc": ["Treasury Bills"] * 3,
            "month_expense_amt": ["1000000000", "2000000000", "3000000000"],
        }
    ).to_csv(treasury_path, index=False)
    pd.DataFrame({"date": ["2025-12-31"], "value": [1000.0]}).to_csv(bank_path, index=False)
    pd.DataFrame({"date": ["2025-12-31"], "row_tsy_bill_discount_interest_proxy": [2000.0]}).to_csv(
        row_path, index=False
    )
    pd.DataFrame({"date": ["2025-12-31"], "credit_union_tsy_bill_discount_interest_proxy": [100.0]}).to_csv(
        cu_path, index=False
    )

    written_csv, written_md = write_bill_discount_allocation(
        treasury_interest_path=treasury_path,
        bank_proxy_path=bank_path,
        row_proxy_path=row_path,
        credit_union_proxy_path=cu_path,
        out_csv_path=csv_path,
        out_markdown_path=md_path,
    )

    assert written_csv == csv_path
    assert written_md == md_path
    out = pd.read_csv(csv_path)
    residual = out.loc[out["sector_key"].eq("unallocated_residual"), "bill_discount_proxy_mil"].iloc[0]
    assert residual == 2900.0
    summary = summarize_bill_discount_allocation(out)
    assert "current bank + ROW + credit-union proxies sum" in summary
    assert "does not renormalize" in summary
