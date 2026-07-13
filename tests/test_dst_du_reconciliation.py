from __future__ import annotations

import pandas as pd

from tdc_estimator.dst_du_reconciliation import build_dst_du_reconciliation


def _expense_window(coupon: float, bill: float, frn: float, pool: float) -> pd.DataFrame:
    dates = pd.date_range("2022-03-31", "2025-12-31", freq="QE")
    rows = []
    for date in dates:
        for key, value in [
            ("coupon_accrual", coupon),
            ("bill_amortized_discount", bill),
            ("frn_accrued_interest", frn),
        ]:
            rows.append(
                {
                    "date": date,
                    "component_key": key,
                    "dst_du_expense_complement_mil": value,
                    "official_component_pool_mil": pool,
                    "method_tier": "certified_modern_component_identity",
                }
            )
    return pd.DataFrame(rows)


def _direct(coupon: float, bill: float) -> pd.DataFrame:
    dates = pd.date_range("2022-03-31", "2025-12-31", freq="QE")
    return pd.DataFrame(
        {"direct_du_coupon_mil": coupon, "direct_du_bill_discount_mil": bill}, index=dates
    )


def test_matching_forms_pass_but_open_gates_hold_outcome_conditional():
    report, manifest = build_dst_du_reconciliation(
        expense_panel=_expense_window(100.0, 50.0, 10.0, 1000.0),
        direct=_direct(100.0, 50.0),
    )
    total = report[report.comparison == "total_ex_frn"].iloc[0]
    assert total.mae_pct == 0.0
    assert bool(total.gate_signed_mean) and bool(total.gate_annual_components)
    # aggregate + components pass, but FFIEC/SHL/ITA gates remain open -> conditional
    assert manifest["outcome"] == (
        "canonical_aggregate_research_sector_split_conditional_on_open_gates"
    )


def test_failing_aggregate_yields_research_tier_outcome():
    report, manifest = build_dst_du_reconciliation(
        expense_panel=_expense_window(100.0, 50.0, 10.0, 1000.0),
        direct=_direct(400.0, 200.0),
    )
    total = report[report.comparison == "total_ex_frn"].iloc[0]
    assert not bool(total.gate_mae)
    assert manifest["outcome"] == "research_tier_canonical_tier2_unchanged"


def test_gates_are_recorded_verbatim():
    _, manifest = build_dst_du_reconciliation(
        expense_panel=_expense_window(100.0, 50.0, 10.0, 1000.0),
        direct=_direct(100.0, 50.0),
    )
    assert manifest["gates"]["signed_mean_pct_max"] == 2.0
    assert manifest["gates"]["min_quarters_within_10pct"] == 14
    assert "ffiec_002_rcfd0260_pilot" in manifest["open_source_gates_not_evaluated_here"]
