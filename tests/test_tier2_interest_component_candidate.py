from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.tier2_interest_component_candidate import (
    build_tier2_interest_component_candidate,
    summarize_tier2_interest_component_candidate,
    write_tier2_interest_component_candidate,
)
from tdc_estimator.treasury_interest_components import build_treasury_interest_component_pools


def _component_pools() -> pd.DataFrame:
    return build_treasury_interest_component_pools(
        pd.DataFrame(
            {
                "record_date": ["2025-01-31", "2025-02-28"],
                "expense_catg_desc": ["INTEREST EXPENSE ON PUBLIC ISSUES"] * 2,
                "expense_group_desc": ["ACCRUED INTEREST EXPENSE", "AMORTIZED DISCOUNT"],
                "expense_type_desc": ["Treasury Notes", "Treasury Bills"],
                "month_expense_amt": ["8000000000", "2000000000"],
            }
        )
    )


def test_build_tier2_interest_component_candidate_allocates_component_pools():
    sector_maturity = pd.DataFrame(
        {
            "date": ["2025-03-31"] * 4,
            "sector_key": ["fed", "bank_us_chartered", "foreigners_total", "credit_unions_marketable_proxy"],
            "coupon_share": [1.0, 1.0, 1.0, 1.0],
            "bill_share": [1.0, 1.0, 1.0, 1.0],
            "coupon_only_maturity_years": [1.0, 1.0, 1.0, 1.0],
        }
    )
    sector_panel = pd.DataFrame(
        {
            "date": ["2025-03-31"] * 4,
            "sector_key": ["fed", "bank_us_chartered", "foreigners_total", "credit_unions_marketable_proxy"],
            "level": [1000.0, 1000.0, 2000.0, 1000.0],
        }
    )
    curves = pd.DataFrame({"date": ["2025-03-31"], "1y": [4.0]})
    fed_components = pd.DataFrame({"date": ["2025-03-31"], "fed_tsy_coupon_interest_proxy": [1000.0]})

    out = build_tier2_interest_component_candidate(
        component_pools=_component_pools(),
        sector_maturity=sector_maturity,
        sector_panel=sector_panel,
        curves=curves,
        fed_components=fed_components,
    )

    coupon = out[out["component_key"].eq("coupon_accrual")].set_index("sector_group")
    bills = out[out["component_key"].eq("bill_amortized_discount")].set_index("sector_group")
    assert coupon.loc["bank", "component_anchored_interest_mil"] == 1750.0
    assert coupon.loc["row", "component_anchored_interest_mil"] == 3500.0
    assert coupon.loc["credit_union", "component_anchored_interest_mil"] == 1750.0
    assert bills.loc["bank", "component_anchored_interest_mil"] == 400.0
    assert bills.loc["row", "component_anchored_interest_mil"] == 800.0
    assert "diagnostic_only" in coupon.loc["bank", "candidate_default_status"]


def test_build_tier2_interest_component_candidate_subtracts_fed_bill_component():
    sector_maturity = pd.DataFrame(
        {
            "date": ["2025-03-31"],
            "sector_key": ["bank_us_chartered"],
            "coupon_share": [1.0],
            "bill_share": [1.0],
            "coupon_only_maturity_years": [1.0],
        }
    )
    sector_panel = pd.DataFrame({"date": ["2025-03-31"], "sector_key": ["bank_us_chartered"], "level": [1.0]})
    curves = pd.DataFrame({"date": ["2025-03-31"], "1y": [4.0]})
    fed_components = pd.DataFrame(
        {
            "date": ["2025-03-31"],
            "fed_tsy_coupon_interest_proxy": [0.0],
            "fed_tsy_bill_discount_interest_proxy": [500.0],
        }
    )

    out = build_tier2_interest_component_candidate(
        component_pools=_component_pools(),
        sector_maturity=sector_maturity,
        sector_panel=sector_panel,
        curves=curves,
        fed_components=fed_components,
    )

    bank_bill = out[
        out["sector_group"].eq("bank") & out["component_key"].eq("bill_amortized_discount")
    ].iloc[0]
    assert bank_bill["allocation_pool_mil"] == 1500.0
    assert bank_bill["component_anchored_interest_mil"] == 1500.0


def test_build_tier2_interest_component_candidate_prefers_contract_weights():
    sector_maturity = pd.DataFrame(
        {
            "date": ["2025-03-31"],
            "sector_key": ["bank_us_chartered"],
            "coupon_share": [1.0],
            "bill_share": [1.0],
            "coupon_only_maturity_years": [1.0],
        }
    )
    sector_panel = pd.DataFrame({"date": ["2025-03-31"], "sector_key": ["bank_us_chartered"], "level": [1.0]})
    curves = pd.DataFrame({"date": ["2025-03-31"], "1y": [4.0]})
    contract = pd.DataFrame(
        {
            "date": ["2025-03-31", "2025-03-31"],
            "sector_key": ["bank_us_chartered", "foreigners_total"],
            "component_key": ["coupon_accrual", "coupon_accrual"],
            "central_weight": [1.0, 3.0],
            "low_weight": [0.5, 2.5],
            "high_weight": [1.5, 3.5],
        }
    )

    out = build_tier2_interest_component_candidate(
        component_pools=_component_pools(),
        sector_maturity=sector_maturity,
        sector_panel=sector_panel,
        curves=curves,
        interest_allocation_weights=contract,
    )

    bank_coupon = out[
        out["sector_group"].eq("bank") & out["component_key"].eq("coupon_accrual")
    ].iloc[0]
    assert bank_coupon["component_anchored_interest_mil"] == 2000.0
    assert bank_coupon["component_anchored_interest_low_mil"] == 800.0
    assert bank_coupon["component_anchored_interest_high_mil"] == 4000.0
    assert bank_coupon["allocator_basis"] == "wamest_interest_contract_central_weight"


def test_build_tier2_interest_component_candidate_uses_bucket_backcast_before_contract_window():
    sector_maturity = pd.DataFrame(
        {
            "date": ["2011-03-31", "2025-03-31"],
            "sector_key": ["bank_us_chartered", "bank_us_chartered"],
            "coupon_share": [1.0, 1.0],
            "bill_share": [1.0, 1.0],
            "coupon_only_maturity_years": [1.0, 1.0],
        }
    )
    sector_panel = pd.DataFrame(
        {
            "date": ["2011-03-31", "2025-03-31"],
            "sector_key": ["bank_us_chartered", "bank_us_chartered"],
            "level": [100.0, 100.0],
        }
    )
    component_pools = build_treasury_interest_component_pools(
        pd.DataFrame(
            {
                "record_date": ["2011-03-31", "2025-03-31"],
                "expense_catg_desc": ["INTEREST EXPENSE ON PUBLIC ISSUES"] * 2,
                "expense_group_desc": ["ACCRUED INTEREST EXPENSE"] * 2,
                "expense_type_desc": ["Treasury Notes"] * 2,
                "month_expense_amt": ["1000000000", "2000000000"],
            }
        )
    )
    contract = pd.DataFrame(
        {
            "date": ["2025-03-31"],
            "sector_key": ["bank_us_chartered"],
            "component_key": ["coupon_accrual"],
            "central_weight": [25.0],
            "low_weight": [25.0],
            "high_weight": [25.0],
        }
    )
    buckets = pd.DataFrame(
        {
            "date": ["2011-03-31"],
            "sector_key": ["bank_us_chartered"],
            "component_key": ["coupon_accrual"],
            "bucket_weight": [0.5],
        }
    )

    out = build_tier2_interest_component_candidate(
        component_pools=component_pools,
        sector_maturity=sector_maturity,
        sector_panel=sector_panel,
        curves=pd.DataFrame({"date": ["2011-03-31", "2025-03-31"], "1y": [4.0, 4.0]}),
        interest_allocation_weights=contract,
        component_bucket_weights=buckets,
    )

    bank_2011 = out[
        out["sector_group"].eq("bank")
        & out["component_key"].eq("coupon_accrual")
        & pd.to_datetime(out["date"]).eq(pd.Timestamp("2011-03-31"))
    ].iloc[0]
    bank_2025 = out[
        out["sector_group"].eq("bank")
        & out["component_key"].eq("coupon_accrual")
        & pd.to_datetime(out["date"]).eq(pd.Timestamp("2025-03-31"))
    ].iloc[0]
    assert bank_2011["selected_raw_weight_mil"] == 50.0
    assert bank_2025["selected_raw_weight_mil"] == 25.0


def test_build_tier2_interest_component_candidate_applies_source_constraints():
    sector_maturity = pd.DataFrame(
        {
            "date": ["2025-03-31"] * 3,
            "sector_key": ["bank_us_chartered", "foreigners_total", "money_market_funds"],
            "coupon_share": [0.5, 0.5, 0.5],
            "bill_share": [0.5, 0.5, 0.5],
            "coupon_only_maturity_years": [1.0, 1.0, 1.0],
        }
    )
    sector_panel = pd.DataFrame(
        {
            "date": ["2025-03-31"] * 3,
            "sector_key": ["bank_us_chartered", "foreigners_total", "money_market_funds"],
            "level": [1000.0, 1000.0, 1000.0],
        }
    )
    curves = pd.DataFrame({"date": ["2025-03-31"], "1y": [4.0]})
    constraints = pd.DataFrame(
        {
            "date": ["2025-03-31"],
            "sector_key": ["bank_broad_private_depositories_marketable_proxy"],
            "constraint_status": ["usable_constraint"],
            "level_mil": [1_000_000.0],
            "bill_weight_proxy": [0.25],
            "coupon_weight_proxy": [0.75],
        }
    )

    out = build_tier2_interest_component_candidate(
        component_pools=_component_pools(),
        sector_maturity=sector_maturity,
        sector_panel=sector_panel,
        curves=curves,
        source_constraints=constraints,
    )

    bank_coupon = out[
        out["sector_group"].eq("bank") & out["component_key"].eq("coupon_accrual")
    ].iloc[0]
    bank_bill = out[
        out["sector_group"].eq("bank") & out["component_key"].eq("bill_amortized_discount")
    ].iloc[0]
    assert bank_coupon["selected_raw_weight_mil"] == 750_000.0
    assert bank_bill["selected_raw_weight_mil"] == 250_000.0
    assert bank_coupon["allocator_basis"].endswith("_with_source_constraints")


def test_build_tier2_interest_component_candidate_applies_level_only_fallback_split():
    sector_maturity = pd.DataFrame(
        {
            "date": ["2025-03-31"] * 3,
            "sector_key": ["credit_unions_marketable_proxy", "foreigners_total", "money_market_funds"],
            "coupon_share": [0.8, 0.5, 0.5],
            "bill_share": [0.2, 0.5, 0.5],
            "coupon_only_maturity_years": [1.0, 1.0, 1.0],
        }
    )
    sector_panel = pd.DataFrame(
        {
            "date": ["2025-03-31"] * 3,
            "sector_key": ["credit_unions_marketable_proxy", "foreigners_total", "money_market_funds"],
            "level": [1000.0, 1000.0, 1000.0],
        }
    )
    constraints = pd.DataFrame(
        {
            "date": ["2025-03-31"],
            "sector_key": ["credit_unions_marketable_proxy"],
            "constraint_status": ["usable_level_constraint_wamest_split_fallback"],
            "level_mil": [2_000_000.0],
            "bill_weight_proxy": [pd.NA],
            "coupon_weight_proxy": [pd.NA],
            "fallback_split_accepted": [True],
        }
    )

    out = build_tier2_interest_component_candidate(
        component_pools=_component_pools(),
        sector_maturity=sector_maturity,
        sector_panel=sector_panel,
        curves=pd.DataFrame({"date": ["2025-03-31"], "1y": [4.0]}),
        source_constraints=constraints,
    )

    cu_coupon = out[
        out["sector_group"].eq("credit_union") & out["component_key"].eq("coupon_accrual")
    ].iloc[0]
    cu_bill = out[
        out["sector_group"].eq("credit_union") & out["component_key"].eq("bill_amortized_discount")
    ].iloc[0]
    assert cu_coupon["selected_raw_weight_mil"] == 1_600_000.0
    assert cu_bill["selected_raw_weight_mil"] == 400_000.0


def test_write_tier2_interest_component_candidate_and_summary(tmp_path: Path):
    treasury_path = tmp_path / "treasury__interest_expense.csv"
    maturity_path = tmp_path / "maturity.csv"
    panel_path = tmp_path / "panel.csv"
    curve_path = tmp_path / "curve.csv"
    csv_path = tmp_path / "candidate.csv"
    md_path = tmp_path / "candidate.md"

    pd.DataFrame(
        {
            "record_date": ["2025-01-31", "2025-02-28"],
            "expense_catg_desc": ["INTEREST EXPENSE ON PUBLIC ISSUES"] * 2,
            "expense_group_desc": ["ACCRUED INTEREST EXPENSE", "AMORTIZED DISCOUNT"],
            "expense_type_desc": ["Treasury Notes", "Treasury Bills"],
            "month_expense_amt": ["8000000000", "2000000000"],
        }
    ).to_csv(treasury_path, index=False)
    pd.DataFrame(
        {
            "date": ["2025-03-31"] * 3,
            "sector_key": ["bank_us_chartered", "foreigners_total", "credit_unions_marketable_proxy"],
            "coupon_share": [1.0, 1.0, 1.0],
            "bill_share": [1.0, 1.0, 1.0],
            "coupon_only_maturity_years": [1.0, 1.0, 1.0],
        }
    ).to_csv(maturity_path, index=False)
    pd.DataFrame(
        {
            "date": ["2025-03-31"] * 3,
            "sector_key": ["bank_us_chartered", "foreigners_total", "credit_unions_marketable_proxy"],
            "level": [1000.0, 2000.0, 1000.0],
        }
    ).to_csv(panel_path, index=False)
    pd.DataFrame({"date": ["2025-03-31"], "1y": [4.0]}).to_csv(curve_path, index=False)

    written_csv, written_md = write_tier2_interest_component_candidate(
        treasury_interest_path=treasury_path,
        sector_maturity_path=maturity_path,
        sector_panel_path=panel_path,
        curve_path=curve_path,
        out_csv_path=csv_path,
        out_markdown_path=md_path,
    )

    assert written_csv == csv_path
    assert written_md == md_path
    out = pd.read_csv(csv_path)
    assert set(out["component_key"]) == {"coupon_accrual", "bill_amortized_discount"}
    summary = summarize_tier2_interest_component_candidate(out)
    assert "diagnostic candidate" in summary
    assert "Latest-quarter read" in md_path.read_text(encoding="utf-8")
