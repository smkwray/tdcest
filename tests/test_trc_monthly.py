import numpy as np
import pandas as pd
import pytest

from tdc_estimator import trc_monthly as tm


def weekly(start="2013-07-03", periods=40, missing=()):
    dates = pd.date_range(start, periods=periods, freq="W-WED")
    rng = np.random.default_rng(3)
    delta = rng.normal(0, 10, periods)
    level = 1000 + np.cumsum(delta)
    frame = pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "trc_core": rng.normal(0, 5, periods),
                          "trc_par_sensitivity": rng.normal(0, 5, periods), "c_h": rng.normal(0, 5, periods),
                          "delta_reserve_balances": delta, "reserve_balances_start": level - delta,
                          "reserve_balances_end": level})
    frame.loc[list(missing), ["trc_core", "trc_par_sensitivity"]] = np.nan
    return frame


def fund_month(months=("2013-08", "2013-09", "2013-10", "2013-11", "2013-12", "2014-01")):
    rows = []
    for i, m in enumerate(months):
        end = pd.Period(m, freq="M").end_time.strftime("%Y-%m-%d")
        for fund, scale in (("A", 1.0), ("B", 2.0)):
            rows.append({"date": end, "fund_id": fund, "mmf_rrp_adjustment_lb": 0.5 * scale * i,
                         "mmf_rrp_adjustment_prop": scale * i, "mmf_rrp_adjustment_ub": 1.5 * scale * i})
    return pd.DataFrame(rows)


def test_months_follow_wednesdays_and_reserve_levels():
    """Each week belongs to its Wednesday's month; the monthly change is the change between last Wednesdays."""
    m = tm.build_monthly(weekly(), fund_month()).set_index("month")
    w = weekly()
    w["month"] = pd.to_datetime(w["date"]).dt.to_period("M").astype(str)
    for month, row in m.iterrows():
        sub = w[w["month"] == month]
        assert row["weeks"] == len(sub) and row["end_wednesday"] == sub["date"].iloc[-1]
        assert row["delta_reserve_balances"] == pytest.approx(sub["delta_reserve_balances"].sum())
        assert row["reserve_balances_end"] - row["reserve_balances_start"] == pytest.approx(row["delta_reserve_balances"])
        assert row["trc_core"] == pytest.approx(sub["trc_core"].sum())


def test_partial_edge_months_are_dropped_and_incomplete_core_months_are_missing():
    w = weekly(start="2013-07-10", periods=40, missing=(9,))
    m = tm.build_monthly(w, fund_month()).set_index("month")
    assert "2013-07" not in m.index  # 2013-07-03 is absent, so July is partial
    missing_month = pd.Period(pd.Timestamp(w["date"][9]), freq="M").strftime("%Y-%m")
    assert np.isnan(m.loc[missing_month, "trc_core"]) and np.isnan(m.loc[missing_month, "trc_preferred"])
    assert not np.isnan(m.loc[missing_month, "c_h"])


def test_route_is_zero_before_on_rrp_missing_after_filings_and_added_to_core():
    m = tm.build_monthly(weekly(periods=40), fund_month()).set_index("month")
    assert m.loc["2013-08", "mmf_route_prop"] == 0.0 and m.loc["2013-08", "mmf_route_status"].startswith("structural_zero")
    assert m.loc["2013-10", "mmf_route_prop"] == pytest.approx(3 * 2)  # funds A (1x) and B (2x), month index 2
    assert np.isnan(m.loc["2014-02", "mmf_route_prop"]) and m.loc["2014-02", "mmf_route_status"].startswith("unavailable")
    assert m.loc["2013-10", "trc_preferred"] == pytest.approx(m.loc["2013-10", "trc_core"] + 6)


def test_monthly_routes_must_reproduce_the_quarterly_route():
    m = tm.build_monthly(weekly(periods=40), fund_month())
    # Q3: July and August are structural zeros, September (month index 1) is 3; Q4 is 3 * (2 + 3 + 4).
    good = pd.DataFrame({"quarter": ["2013Q3", "2013Q4"], "mmf_route_prop": [3.0, 27.0]})
    assert tm.quarterly_route_check(m, good)["max_gap"] == pytest.approx(0.0)
    with pytest.raises(ValueError, match="reproduce"):
        tm.quarterly_route_check(m, good.assign(mmf_route_prop=1.0))
    with pytest.raises(ValueError, match="missing"):
        tm.quarterly_route_check(m, good.assign(mmf_route_prop=np.nan))
    with pytest.raises(ValueError, match="missing"):
        tm.quarterly_route_check(m, good.iloc[:1])


def test_duplicate_fund_months_and_gaps_are_refused():
    with pytest.raises(ValueError, match="duplicate"):
        tm.monthly_routes(pd.concat([fund_month(), fund_month().iloc[:1]]))
    with pytest.raises(ValueError, match="consecutive"):
        tm.build_monthly(weekly().drop(index=5), fund_month())


def test_interior_route_gaps_and_missing_reserve_levels_are_refused():
    """Review round 1: a missing filed month or a missing reserve level must fail, not pass the checks."""
    gap = fund_month()
    gap = gap[~gap["date"].str.startswith("2013-11")]
    with pytest.raises(ValueError, match="inside the filed span"):
        tm.build_monthly(weekly(periods=40), gap)
    w = weekly(periods=40)
    november = pd.to_datetime(w["date"]).dt.strftime("%Y-%m").eq("2013-11")
    w.loc[november, ["delta_reserve_balances", "reserve_balances_start", "reserve_balances_end"]] = np.nan
    with pytest.raises(ValueError, match="missing reserve"):
        tm.build_monthly(w, fund_month())


def test_missing_lower_bound_with_zero_route_is_zero():
    fm = fund_month()
    fm.loc[fm["date"].str.startswith("2013-09"), "mmf_rrp_adjustment_lb"] = np.nan
    fm.loc[fm["date"].str.startswith("2013-09"), ["mmf_rrp_adjustment_prop", "mmf_rrp_adjustment_ub"]] = 0.0
    m = tm.build_monthly(weekly(periods=40), fm).set_index("month")
    assert m.loc["2013-09", "mmf_route_lb"] == 0.0 and m.loc["2013-09", "mmf_route_status"].endswith("implied_by_zero_ub")
