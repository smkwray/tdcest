from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.treasury_interest_components import (
    build_treasury_interest_component_pools,
    summarize_treasury_interest_component_pools,
    write_treasury_interest_component_pools,
)


def test_build_treasury_interest_component_pools_separates_instruments():
    source = pd.DataFrame(
        {
            "record_date": ["2025-01-31", "2025-02-28", "2025-03-31", "2025-03-31", "bad-date"],
            "expense_catg_desc": [
                "INTEREST EXPENSE ON PUBLIC ISSUES",
                "INTEREST EXPENSE ON PUBLIC ISSUES",
                "INTEREST EXPENSE ON PUBLIC ISSUES",
                "INTEREST EXPENSE ON PUBLIC ISSUES",
                "record_date",
            ],
            "expense_group_desc": [
                "ACCRUED INTEREST EXPENSE",
                "AMORTIZED DISCOUNT",
                "ACCRUED INTEREST EXPENSE",
                "ACCRUED INTEREST EXPENSE",
                "expense_group_desc",
            ],
            "expense_type_desc": [
                "Treasury Notes",
                "Treasury Bills",
                "Int. Expense Inflation Compensation (TIPS)",
                "Treasury Floating Rate Notes (FRN)",
                "expense_type_desc",
            ],
            "month_expense_amt": ["1000000000", "2000000000", "3000000000", "4000000000", "month_expense_amt"],
        }
    )

    out = build_treasury_interest_component_pools(source)

    by_key = out.set_index("component_key")
    assert by_key.loc["notes_accrued_interest", "quarter_expense_mil"] == 1000.0
    assert by_key.loc["bill_amortized_discount", "quarter_expense_mil"] == 2000.0
    assert by_key.loc["tips_inflation_compensation", "quarter_expense_mil"] == 3000.0
    assert by_key.loc["frn_accrued_interest", "quarter_expense_mil"] == 4000.0
    assert bool(by_key.loc["notes_accrued_interest", "included_in_coupon_pool"])
    assert bool(by_key.loc["bill_amortized_discount", "included_in_bill_discount_pool"])
    assert not bool(by_key.loc["tips_inflation_compensation", "included_in_coupon_pool"])
    assert bool(by_key.loc["tips_inflation_compensation", "included_in_tips_inflation_comp_pool"])
    assert bool(by_key.loc["frn_accrued_interest", "included_in_frn_pool"])


def test_write_treasury_interest_component_pools_and_summary(tmp_path: Path):
    treasury_path = tmp_path / "treasury__interest_expense.csv"
    csv_path = tmp_path / "treasury_interest_component_pools_q.csv"
    md_path = tmp_path / "treasury_interest_component_pools_q.md"
    pd.DataFrame(
        {
            "record_date": ["2025-01-31", "2025-02-28", "2025-03-31"],
            "expense_catg_desc": ["INTEREST EXPENSE ON PUBLIC ISSUES"] * 3,
            "expense_group_desc": ["ACCRUED INTEREST EXPENSE", "ACCRUED INTEREST EXPENSE", "AMORTIZED DISCOUNT"],
            "expense_type_desc": ["Treasury Notes", "Treasury Bonds", "Treasury Bills"],
            "month_expense_amt": ["1000000000", "2000000000", "3000000000"],
        }
    ).to_csv(treasury_path, index=False)

    written_csv, written_md = write_treasury_interest_component_pools(
        treasury_interest_path=treasury_path,
        out_csv_path=csv_path,
        out_markdown_path=md_path,
    )

    assert written_csv == csv_path
    assert written_md == md_path
    out = pd.read_csv(csv_path)
    assert set(out["component_key"]) == {
        "notes_accrued_interest",
        "bonds_accrued_interest",
        "bill_amortized_discount",
    }
    summary = md_path.read_text(encoding="utf-8")
    assert "Latest quarter (2025-03-31)" in summary
    assert "Treasury bill amortized discount" in summary


def test_summarize_treasury_interest_component_pools_handles_empty():
    assert "No component rows" in summarize_treasury_interest_component_pools(pd.DataFrame())
