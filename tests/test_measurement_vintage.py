"""A measurement vintage moves sample endpoints only.

Revisions between vintages are read as data revisions. That reading holds only if a later
vintage requests the same series, units and clocks over the same start, and its samples run
complete through the declared endpoint.
"""

from __future__ import annotations

import pandas as pd
import pytest

from tdc_estimator.catalog import DEFAULT_VINTAGE, MEASUREMENT_VINTAGES, fiscus_registries
from tdc_estimator.reserve_factor_ledger import eras as ledger_eras
from tdc_estimator.settlement_routes import load_settlement_routes, route_registry_frame
from tdc_estimator.tier2_regression_series import build_regression_leg_table, leg_quarters
from tdc_estimator.trc_reserve_component import period_windows
from tdc_estimator.weekly_trc import summary_windows

REFRESH = MEASUREMENT_VINTAGES["2026q2"]
IDENTITY_FIELDS = ["key", "dataset_id", "usd_million_per_unit", "clock", "series_id", "native_units"]


@pytest.mark.parametrize("name,v1_end,refresh_end", [
    ("trc", DEFAULT_VINTAGE.quarter_end_date, REFRESH.quarter_end_date),
    ("weekly-trc", DEFAULT_VINTAGE.weekly_end, REFRESH.weekly_end),
    ("h41-ledger", None, None),
])
def test_vintage_changes_request_endpoints_not_series_identity(name, v1_end, refresh_end):
    old, new = fiscus_registries(DEFAULT_VINTAGE)[name], fiscus_registries(REFRESH)[name]
    assert (old.input_dir, old.manifest, old.schema_version) == (new.input_dir, new.manifest, new.schema_version)
    assert len(old.inputs) == len(new.inputs)
    for before, after in zip(old.inputs, new.inputs):
        assert [getattr(before, f) for f in IDENTITY_FIELDS] == [getattr(after, f) for f in IDENTITY_FIELDS]
        expected = before.argv if v1_end is None else tuple(t.replace(v1_end, refresh_end) for t in before.argv)
        assert after.argv == expected, before.key
        if before.snapshot_window:
            assert after.snapshot_window == (before.snapshot_window[0], refresh_end)


def _leg_inputs(end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.period_range("2002Q1", end, freq="Q").end_time.normalize()
    quarterly = pd.DataFrame({
        "date": dates, "fed_tsy_tx": 10., "us_chartered_tsy_tx": 20., "foreign_offices_tsy_tx": 3.,
        "affiliated_areas_tsy_tx": 2., "row_tsy_tx": 4., "treasury_operating_cash_tx": 6.,
        "fed_remit_or_deferred": 5.,
    })
    effective = (dates >= "2013-09-30").astype(float) * 7.  # MMF route is structurally zero before ON RRP
    regression = pd.DataFrame({
        "date": dates, "tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow": 24. + effective,
        "tdc_tier2_regression_bank_only_ru_flow": 24., "tdc_tier2_regression_domestic_bank_only_ru_flow": 25.,
        "row_tier2_regression_interest_proxy": 5., "bank_tier2_regression_interest_proxy": 8.,
        "fed_tsy_coupon_interest_proxy": 1., "mmf_rrp_adjustment_prop": 7.,
        "row_method_tier": "fixture", "tier2_regression_bank_row_method_tier": "fixture",
    })
    return quarterly, regression


def test_refresh_legs_close_through_the_endpoint_and_never_shorten_silently():
    quarters = leg_quarters(REFRESH)
    frame = build_regression_leg_table(*_leg_inputs(REFRESH.quarter_end), quarters)
    assert frame.quarter.iloc[[0, -1]].tolist() == ["2002Q1", "2026Q2"] and len(frame) == 98
    assert (frame.C - frame[["R", "J", "O"]].sum(axis=1)).abs().max() == 0
    # Inputs that stop at the admitted endpoint cannot be published under the later vintage.
    with pytest.raises(ValueError, match="expected exactly 98 complete quarters"):
        build_regression_leg_table(*_leg_inputs(DEFAULT_VINTAGE.quarter_end), quarters)


def test_only_open_ended_eras_follow_the_endpoint():
    assert period_windows(DEFAULT_VINTAGE.quarter_end) == [
        ("2003Q1", "2007Q4"), ("2008Q1", "2014Q4"), ("2015Q1", "2019Q4"), ("2020Q1", "2025Q4")]
    assert period_windows("2026Q2")[:3] == period_windows("2025Q4")[:3]
    assert period_windows("2026Q2")[-1] == ("2020Q1", "2026Q2")
    closed = [era for era in ledger_eras("2025Q4") if era[1] != "2025Q4"]
    assert closed == [era for era in ledger_eras("2026Q2") if era[1] != "2026Q2"]
    assert [era[1] for era in summary_windows("2026Q3")] == ["2008Q3", "2008Q4", "2015Q4", "2026Q3", "2026Q3", "2026Q3"]


def test_route_registry_keeps_incidence_and_moves_only_measured_coverage_end():
    old, new = route_registry_frame(), route_registry_frame(REFRESH)
    assert old.drop(columns="coverage_end").equals(new.drop(columns="coverage_end"))
    measured = old.coverage_end.eq(DEFAULT_VINTAGE.quarter_end)
    assert new.loc[measured, "coverage_end"].eq(REFRESH.quarter_end).all()
    assert new.loc[~measured, "coverage_end"].equals(old.loc[~measured, "coverage_end"])
    assert len(load_settlement_routes()) == len(new)
