from __future__ import annotations

import pandas as pd
import pytest

from tdc_estimator.dst_du_sector_allocation import build_dst_du_sector_allocation


def _expense(rows):
    return pd.DataFrame(
        rows,
        columns=["date", "component_key", "dst_du_expense_complement_mil", "method_tier"],
    )


def _positions(rows):
    return pd.DataFrame(
        rows,
        columns=["date", "sector_key", "coupon_position_mil", "bill_position_mil", "position_basis"],
    )


def test_allocation_closure_shares_and_aggregate_invariants():
    expense = _expense(
        [
            ("2022-03-31", "coupon_accrual", 100.0, "certified_modern_component_identity"),
            ("2022-03-31", "bill_amortized_discount", 40.0, "certified_modern_component_identity"),
        ]
    )
    positions = _positions(
        [
            ("2022-03-31", "households_nonprofits", 60.0, 10.0, "z1_level_model_allocated"),
            ("2022-03-31", "nonfinancial_corporates", 20.0, 0.0, "z1_level_model_allocated"),
            ("2022-03-31", "life_insurers", 20.0, 0.0, "z1_level_model_allocated"),
            ("2022-03-31", "money_market_funds", 0.0, 30.0, "nmfp_position_anchored"),
        ]
    )
    panel = build_dst_du_sector_allocation(expense_panel=expense, positions=positions)

    coupon = panel[
        (panel.component_key == "coupon_accrual") & (~panel.sector_key.str.startswith("dst_du"))
    ]
    assert abs(coupon.allocated_mil.sum() - 100.0) < 1e-9
    assert abs(coupon.share_of_component.sum() - 1.0) < 1e-12
    hh = coupon[coupon.sector_key == "households_nonprofits"].iloc[0]
    assert hh.allocated_mil == 60.0

    bills = panel[
        (panel.component_key == "bill_amortized_discount")
        & (panel.sector_key == "money_market_funds")
    ].iloc[0]
    assert bills.allocated_mil == 30.0  # 40 * 30/40
    assert bills.position_basis == "nmfp_position_anchored"

    narrow = panel[
        (panel.component_key == "coupon_accrual") & (panel.sector_key == "dst_du_narrow")
    ].iloc[0]
    broad = panel[
        (panel.component_key == "coupon_accrual") & (panel.sector_key == "dst_du_broad")
    ].iloc[0]
    assert narrow.allocated_mil == 80.0
    assert broad.allocated_mil == 100.0  # narrow + life_insurers
    assert broad.allocated_mil >= narrow.allocated_mil


def test_unknown_sector_fails_closed():
    expense = _expense([("2022-03-31", "coupon_accrual", 10.0, "t")])
    positions = _positions([("2022-03-31", "banks", 1.0, 0.0, "z1")])
    with pytest.raises(ValueError, match="outside the DU universe"):
        build_dst_du_sector_allocation(expense_panel=expense, positions=positions)


def test_missing_positions_route_to_explicit_unallocated():
    expense = _expense([("2022-03-31", "coupon_accrual", 10.0, "t")])
    positions = _positions([("2021-12-31", "households_nonprofits", 5.0, 0.0, "z1_level_model_allocated")])
    panel = build_dst_du_sector_allocation(expense_panel=expense, positions=positions)
    row = panel[
        (panel.component_key == "coupon_accrual")
        & (panel.date == pd.Timestamp("2022-03-31"))
        & (panel.sector_key == "dst_du_unallocated")
    ]
    assert len(row) == 1
    assert row.allocated_mil.iloc[0] == 10.0
