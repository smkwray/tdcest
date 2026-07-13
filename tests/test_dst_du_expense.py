from __future__ import annotations

import pandas as pd
import pytest

from tdc_estimator.dst_du_expense import (
    ANALYSIS_TIER,
    CERTIFIED_TIER,
    TOTAL_COMPONENT_KEY,
    build_dst_du_expense_panel,
)


def _candidate(rows: list[tuple[str, str, str, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        rows,
        columns=[
            "date",
            "sector_group",
            "component_key",
            "official_component_pool_mil",
            "fed_exact_component_mil",
            "component_anchored_interest_mil",
        ],
    )


def test_complement_closure_tiers_and_totals():
    candidate = _candidate(
        [
            ("2022-03-31", "bank", "coupon_accrual", 1000.0, 200.0, 300.0),
            ("2022-03-31", "credit_union", "coupon_accrual", 1000.0, 200.0, 50.0),
            ("2022-03-31", "row", "coupon_accrual", 1000.0, 200.0, 250.0),
            ("2022-03-31", "bank", "bill_amortized_discount", 400.0, 100.0, 120.0),
            ("2022-03-31", "credit_union", "bill_amortized_discount", 400.0, 100.0, 20.0),
            ("2022-03-31", "row", "bill_amortized_discount", 400.0, 100.0, 60.0),
            ("2010-06-30", "bank", "coupon_accrual", 500.0, 150.0, 100.0),
            ("2010-06-30", "credit_union", "coupon_accrual", 500.0, 150.0, 25.0),
            ("2010-06-30", "row", "coupon_accrual", 500.0, 150.0, 125.0),
        ]
    )
    panel = build_dst_du_expense_panel(
        candidate, certified_dates=[pd.Timestamp("2022-03-31")]
    )

    coupon = panel[
        (panel["component_key"] == "coupon_accrual")
        & (panel["date"] == pd.Timestamp("2022-03-31"))
    ].iloc[0]
    assert coupon["dst_du_expense_complement_mil"] == 200.0  # 1000 - 200 - 600
    closure = (
        coupon["official_component_pool_mil"]
        - coupon["fed_exact_component_mil"]
        - coupon["ru_allocated_total_mil"]
        - coupon["dst_du_expense_complement_mil"]
    )
    assert closure == 0.0
    assert coupon["method_tier"] == CERTIFIED_TIER
    assert coupon["estimand_layer"] == "expense_control"

    older = panel[
        (panel["component_key"] == "coupon_accrual")
        & (panel["date"] == pd.Timestamp("2010-06-30"))
    ].iloc[0]
    assert older["method_tier"] == ANALYSIS_TIER
    assert older["dst_du_expense_complement_mil"] == 100.0  # 500 - 150 - 250

    total = panel[
        (panel["component_key"] == TOTAL_COMPONENT_KEY)
        & (panel["date"] == pd.Timestamp("2022-03-31"))
    ].iloc[0]
    assert total["official_component_pool_mil"] == 1400.0
    assert total["dst_du_expense_complement_mil"] == 300.0  # 200 coupon + 100 bill
    assert total["method_tier"] == CERTIFIED_TIER


def test_negative_complement_fails_closed():
    candidate = _candidate(
        [
            ("2022-03-31", "bank", "coupon_accrual", 100.0, 30.0, 60.0),
            ("2022-03-31", "row", "coupon_accrual", 100.0, 30.0, 20.0),
        ]
    )
    with pytest.raises(ValueError, match="negative complement"):
        build_dst_du_expense_panel(candidate)


def test_nan_ru_allocation_fails_closed():
    candidate = _candidate(
        [
            ("2022-03-31", "bank", "coupon_accrual", 100.0, 10.0, float("nan")),
            ("2022-03-31", "row", "coupon_accrual", 100.0, 10.0, 20.0),
        ]
    )
    with pytest.raises(ValueError, match="NaN RU allocation"):
        build_dst_du_expense_panel(candidate)


def test_missing_fed_exact_is_zero_and_flagged():
    candidate = _candidate(
        [
            ("2022-03-31", "bank", "frn_accrued_interest", 100.0, float("nan"), 40.0),
            ("2022-03-31", "row", "frn_accrued_interest", 100.0, float("nan"), 10.0),
        ]
    )
    panel = build_dst_du_expense_panel(candidate)
    row = panel[panel["component_key"] == "frn_accrued_interest"].iloc[0]
    assert row["fed_exact_component_mil"] == 0.0
    assert bool(row["fed_exact_missing"]) is True
    assert row["dst_du_expense_complement_mil"] == 50.0


def test_no_cash_labeled_columns_in_output():
    candidate = _candidate(
        [
            ("2022-03-31", "bank", "coupon_accrual", 100.0, 10.0, 40.0),
            ("2022-03-31", "row", "coupon_accrual", 100.0, 10.0, 10.0),
        ]
    )
    panel = build_dst_du_expense_panel(candidate)
    assert not [c for c in panel.columns if "cash" in c.lower()]
