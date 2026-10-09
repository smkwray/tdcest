"""H.4.1 reserve-factor ledger: fixture economics through the production builder and CLI.

The fixture draws unrounded Table 1 factor levels, derives reserve balances from
the balance-sheet identity, and publishes every row, parent, and total rounded to
the nearest USD million, as H.4.1 does. Balance-sheet events are posted to the
unrounded factors, so each test reads the ledger difference an event produces.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd
import pytest

from tdc_estimator.catalog import H41_LEDGER_REGISTRY, H41_TABLE1_ROWS, H41Row
from tdc_estimator.cli import main
from tdc_estimator.reserve_factor_ledger import (
    AFTER_ROW,
    BEFORE_ROW,
    CASH_KEYS,
    LEDGER_OUTPUT_FILES,
    REPORTED,
    build_reserve_factor_ledger,
    build_weekly_ledger,
    h41_levels,
    load_h41_rows,
)
from tdc_estimator.settlement_routes import SettlementEvent, event_incidence
from tdc_estimator.trc_export import TRC_OUTPUT_FILES, load_fiscus_inputs

ROOT = Path(__file__).resolve().parents[1]
CAL = pd.date_range("2002-12-18", "2026-01-07", freq="W-WED")
SHELL = pd.period_range("2002Q1", "2025Q4", freq="Q")
ROWS = load_h41_rows()
FACTORS = [k for k, e in ROWS.items() if e.row.role == "factor"]
CHECKS = [k for k, e in ROWS.items() if e.row.role == "check"]
MEMOS = [k for k, e in ROWS.items() if e.row.role == "memo"]
LAST_OBS = {  # fixture last observation of each removed row
    "cpff_llc": "2010-08-25", "mmiff_llcs": "2009-10-28", "maiden_lane_llc": "2020-03-11",
    "maiden_lane_ii_llc": "2020-03-11", "maiden_lane_iii_llc": "2020-03-11", "talf_llc": "2014-11-05",
    "aia_alico_preferred_interests": "2011-01-12", "cpff_ii_llc": "2022-07-20",
    "corporate_credit_facilities_llc": "2022-12-21", "municipal_liquidity_facility_llc": "2025-02-26",
    "talf_ii_llc": "2025-02-26", "supplementary_financing_account": "2012-11-07",
    "service_related_deposits": "2012-07-11", "aig_disposition_funds_held_as_agent": "2011-01-12",
}
SCALE = {"treasury_securities": 700_000.0, "currency_in_circulation": 650_000.0, "unamortized_discounts": -1_000.0,
         "mortgage_backed_securities": 50_000.0, "other_liabilities_and_capital": 20_000.0}
VARIANTS = ["trc_core", "trc_preferred", "trc_mmf_lower", "trc_mmf_upper"]


def last_wednesday(quarter: pd.Period) -> pd.Timestamp:
    day = quarter.end_time.normalize()
    while day.weekday() != 2:
        day -= pd.Timedelta(days=1)
    return day


def observed(key: str) -> np.ndarray:
    row = ROWS[key].row
    mask = np.ones(len(CAL), dtype=bool)
    if row.discontinued:
        mask &= CAL <= pd.Timestamp(LAST_OBS[key])
    if row.introduced:
        mask &= CAL >= pd.Timestamp(row.introduced) + pd.Timedelta(days=7)
    return mask


def make_truth() -> pd.DataFrame:
    """Unrounded factor and memo levels; zero wherever a row is absent from Table 1."""
    assert set(LAST_OBS) == {k for k, e in ROWS.items() if e.row.discontinued}
    rng = np.random.default_rng(20261009)
    n, truth = len(CAL), {}
    for key in [*FACTORS, *MEMOS]:
        scale = SCALE.get(key, 2_000.0)
        level = scale + np.cumsum(rng.normal(0, abs(scale) * 0.01, n)) + rng.uniform(-0.45, 0.45, n)
        row, mask = ROWS[key].row, observed(key)
        if row.discontinued:
            last = pd.Timestamp(LAST_OBS[key])
            active = (CAL >= last - pd.Timedelta(days=3 * 365)) & (CAL <= last - pd.Timedelta(days=28))
            if row.terminal_nonzero:
                active |= (CAL > last - pd.Timedelta(days=28)) & (CAL <= last)
            level = np.where(active, np.abs(level) + 100.0, 0.0)
        level = np.where(mask, level, 0.0)
        truth[key] = level
    truth = pd.DataFrame(truth, index=CAL)
    truth["treasury_securities"] += np.where(CAL >= pd.Timestamp("2020-03-18"), 2_500_000.0, 0.0)
    truth["treasury_securities"] += truth["treasury_inflation_compensation"]
    deferred = np.clip((CAL - pd.Timestamp("2022-09-07")).days / 7, 0, None) * 400.0
    truth["other_liabilities_and_capital"] -= deferred  # deferred asset turns the published row negative
    return truth


def publish(truth: pd.DataFrame) -> dict[str, pd.DataFrame]:
    sides = pd.Series({k: ROWS[k].side for k in FACTORS})
    values = {k: truth[k] for k in [*FACTORS, *MEMOS]}
    values["reserve_balances"] = (truth[FACTORS] * sides).sum(axis=1)
    for key in CHECKS:
        values[key] = truth[list(ROWS[key].descendants)].sum(axis=1)
    frames = {}
    for key, value in values.items():
        mask = observed(key) if key in FACTORS else np.ones(len(CAL), dtype=bool)
        frames[key] = pd.DataFrame({"date": CAL[mask].strftime("%Y-%m-%d"),
                                    "value": np.round(np.asarray(value)[mask]).astype(np.int64).astype(str)})
    rb = pd.to_numeric(frames["reserve_balances"].set_index("date")["value"])
    td = pd.to_numeric(frames["term_deposits"].set_index("date")["value"])
    quarters = pd.period_range("2002Q1", "2025Q4", freq="Q")
    fl = []
    for i, quarter in enumerate(quarters):
        wed = last_wednesday(quarter).strftime("%Y-%m-%d")
        fl.append(float(rb[wed] + td[wed] + 40 * np.sin(i)) if wed in rb.index else 20_000.0 + i)
    fl = pd.Series(np.round(fl), index=quarters)
    fu = fl.diff()
    fu.iloc[0] = 15.0
    fu[pd.Period("2007Q1")] += 123.0  # a series break: transactions differ from the level change
    for key, series in [("z1_reserves_level", fl), ("z1_reserves_transactions", fu)]:
        frames[key] = pd.DataFrame({"date": quarters.end_time.strftime("%Y-%m-%d"),
                                    "value": series.astype(np.int64).astype(str).to_numpy()})
    return frames


def quarter_levels(frames: dict[str, pd.DataFrame], key: str) -> pd.Series:
    series = pd.to_numeric(frames[key].set_index("date")["value"])
    return pd.Series([float(series.get(last_wednesday(q).strftime("%Y-%m-%d"), 0.0)) for q in
                      pd.period_range("2001Q4", "2025Q4", freq="Q")], index=pd.period_range("2001Q4", "2025Q4", freq="Q"))


def make_components(frames: dict[str, pd.DataFrame], route_extra: dict[str, float] | None = None) -> pd.DataFrame:
    """Admitted-TRC stand-in: cash leg = H.4.1 C^H plus clock noise, arbitrary Fed bridge and route."""
    route_extra = route_extra or {}
    i = np.arange(len(SHELL))
    tga = quarter_levels(frames, "treasury_general_account")
    sfp = quarter_levels(frames, "supplementary_financing_account")
    rb = quarter_levels(frames, "reserve_balances")
    c_h = (-(tga.diff()) - sfp.diff()).reindex(SHELL)
    measured = SHELL >= pd.Period("2003Q1")
    cash = np.where(measured, c_h + 7.0 * (i % 5 - 2), np.nan)
    active = SHELL >= pd.Period("2013Q4")
    extra = np.array([route_extra.get(str(q), 0.0) for q in SHELL])
    comp = pd.DataFrame({
        "quarter": SHELL.astype(str),
        "delta_rb_z1": pd.to_numeric(frames["z1_reserves_transactions"]["value"]).to_numpy(),
        "trc_cash_leg": cash,
        "trc_fed_bridge": 1_000.0 + 3.3 * i,
        "tga_clock": np.where(SHELL < pd.Period("2006Q1"), "h41_last_wednesday", "dts_final_business_day"),
        "mmf_route_lb": np.where(active, 10.25 + i, 0.0) + extra,
        "mmf_route_prop": np.where(active, 20.5 + i, 0.0) + extra,
        "mmf_route_ub": np.where(active, 30.75 + i, 0.0) + extra,
        "delta_rb_h41": rb.diff().reindex(SHELL).where(measured).to_numpy(),
        "delta_tga_h41": tga.diff().reindex(SHELL).where(measured).to_numpy(),
    })
    comp["trc_core"] = comp["trc_cash_leg"] + comp["trc_fed_bridge"]
    comp["trc_preferred"] = comp["trc_core"] + comp["mmf_route_prop"]
    comp["trc_mmf_lower"] = comp["trc_core"] + comp["mmf_route_lb"]
    comp["trc_mmf_upper"] = comp["trc_core"] + comp["mmf_route_ub"]
    return comp


def post(truth: pd.DataFrame, date: str, postings: dict[str, float], weeks: int = 8) -> pd.DataFrame:
    """Post a balanced balance-sheet event for ``weeks`` Wednesdays; reserve balances follow the identity."""
    out = truth.copy()
    window = (CAL >= pd.Timestamp(date)) & (CAL < pd.Timestamp(date) + pd.Timedelta(weeks=weeks))
    implied = 0.0
    for key, amount in postings.items():
        if key == "reserve_balances":
            continue
        out.loc[window, key] += amount
        implied += ROWS[key].side * amount
    assert implied == postings.get("reserve_balances", 0.0), "event is not balance-sheet consistent"
    return out


@pytest.fixture(scope="module")
def base():
    truth = make_truth()
    frames = publish(truth)
    comp = make_components(frames)
    return {"truth": truth, "frames": frames, "comp": comp, "result": build_reserve_factor_ledger(frames, comp)}


def weekly_row(result, date: str) -> pd.Series:
    return result.weekly.set_index("date").loc[date]


def event_delta(base, date: str, postings: dict[str, float]) -> pd.Series:
    frames = publish(post(base["truth"], date, postings))
    result = build_reserve_factor_ledger(frames, make_components(frames))
    numeric = [c for c in result.weekly.columns if c.startswith(("f_", "c_h", "s_h", "rho", "delta_"))]
    return weekly_row(result, date)[numeric].astype(float) - weekly_row(base["result"], date)[numeric].astype(float)


def test_registry_is_nonoverlapping_and_rejects_parent_child_double_entry():
    factors = [r for r in H41_TABLE1_ROWS if r.role == "factor"]
    assert sum(r.key == "supplementary_financing_account" for r in factors) == 1
    assert not any("tax and loan" in r.label.lower() or "ttl" in r.key for r in H41_TABLE1_ROWS)
    assert set(ROWS["deposits_other_than_reserve_balances"].descendants) >= set(CASH_KEYS)
    assert ROWS["reverse_repurchase_agreements"].row.role == "check"
    assert {ROWS[k].side for k in ROWS["total_absorbing"].descendants} == {-1}
    child = H41Row("treasury_bills", "WSHOBL", "Bills", "treasury_securities", "factor")
    with pytest.raises(ValueError, match="parent and child"):
        load_h41_rows((*H41_TABLE1_ROWS, child))
    parent_as_factor = tuple(H41Row(r.key, r.series_id, r.label, r.parent, "factor") if r.key == "securities_held_outright"
                             else r for r in H41_TABLE1_ROWS)
    with pytest.raises(ValueError, match="parent and child|check row"):
        load_h41_rows(parent_as_factor)
    with pytest.raises(ValueError, match="terminal_nonzero"):
        load_h41_rows((*H41_TABLE1_ROWS, H41Row("x", "X", "x", "total_supplying", "factor", terminal_nonzero="y")))
    with pytest.raises(ValueError, match="twice"):
        load_h41_rows((*H41_TABLE1_ROWS, H41Row("float_again", "WOFSRBFL", "Float", "reserve_bank_credit", "factor")))


def test_level_and_change_closure_within_rounding_bound(base):
    weekly = base["result"].weekly
    live = weekly.iloc[1:]
    assert (weekly["rho_level"].abs() <= weekly["level_bound"]).all()
    assert (live["rho"].abs() <= live["change_bound"]).all()
    assert weekly["rho_level"].abs().max() >= 1  # the fixture carries real rounding error
    factor_sum = live[[f"f_{k}" for k in FACTORS]].sum(axis=1)
    assert np.array_equal(live["delta_reserve_balances"], factor_sum + live["rho"])
    assert np.array_equal(live["c_h"], live[[f"f_{k}" for k in CASH_KEYS]].sum(axis=1))
    for key in CHECKS:
        assert weekly[f"gap_{key}"].abs().max() <= 0.5 * (len(ROWS[key].descendants) + 1)
    assert weekly.iloc[0]["ledger_status"] == "unavailable_no_prior_wednesday"
    assert np.isnan(weekly.iloc[0]["rho"])


def test_closure_breach_or_an_omitted_row_raises(base):
    frames = {k: v.copy() for k, v in base["frames"].items()}
    frames["float"].loc[600, "value"] = str(int(frames["float"].loc[600, "value"]) + 40)
    with pytest.raises(ValueError, match="closure exceeds the rounding bound"):
        build_reserve_factor_ledger(frames, base["comp"])
    # Silently dropping a historical facility from the map breaks closure against the published parents.
    rows = load_h41_rows(tuple(r for r in H41_TABLE1_ROWS if r.key != "maiden_lane_llc"))
    levels, status, _ = h41_levels(base["frames"], rows)
    with pytest.raises(ValueError, match="closure exceeds the rounding bound"):
        build_weekly_ledger(levels, status, rows)


def test_quarters_telescope_between_last_wednesdays(base):
    weekly, quarterly = base["result"].weekly, base["result"].quarterly.set_index("quarter")
    assert quarterly.index[0] == "2003Q1" and quarterly.index[-1] == "2025Q4"
    assert base["result"].stats["quarterly"]["incomplete_trailing_quarter"]["quarter"] == "2026Q1"
    assert (quarterly.loc["2003Q1", "start_wednesday"], quarterly.loc["2003Q1", "end_wednesday"]) == ("2002-12-25", "2003-03-26")
    assert quarterly.loc["2003Q2", "start_wednesday"] == "2003-03-26"
    rb = weekly.set_index("date")["reserve_balances"]
    for quarter, row in quarterly.iterrows():
        assert row.delta_reserve_balances == rb[row.end_wednesday] - rb[row.start_wednesday]
        inside = weekly[(weekly.date > row.start_wednesday) & (weekly.date <= row.end_wednesday)]
        assert set(inside.quarter) == {quarter} and len(inside) == row.n_weeks
        for column in ["f_treasury_securities", "f_maiden_lane_llc", "f_supplementary_financing_account", "rho", "c_h"]:
            assert inside[column].sum() == row[column], (quarter, column)
    assert (quarterly["rho"].abs() <= quarterly["change_bound"]).all()


def test_structural_rows_are_explicit_and_missing_rows_raise(base):
    levels, status, coverage = h41_levels(base["frames"], ROWS)
    assert status.loc["2008-09-17", "supplementary_financing_account"] == BEFORE_ROW
    assert status.loc["2008-09-24", "supplementary_financing_account"] == REPORTED
    assert status.loc["2020-03-18", "maiden_lane_llc"] == AFTER_ROW
    assert status.loc["2011-01-19", "aia_alico_preferred_interests"] == AFTER_ROW
    assert coverage["aia_alico_preferred_interests"]["last_value"] != 0
    weekly = base["result"].weekly.set_index("date")
    assert "supplementary_financing_account=" + BEFORE_ROW in weekly.loc["2008-09-17", "structural_zero_rows"]
    assert "maiden_lane_llc=" + AFTER_ROW in weekly.loc["2020-03-18", "structural_zero_rows"]
    assert weekly.loc["2010-01-06", "structural_zero_rows"].count("=") < weekly.loc["2024-01-03", "structural_zero_rows"].count("=")

    def broken(key, transform):
        frames = dict(base["frames"])
        frames[key] = transform(frames[key].copy())
        return frames

    cases = [
        (broken("maiden_lane_llc", lambda f: f.drop(index=700)), "missing inside its reporting span"),
        (broken("maiden_lane_llc", lambda f: f[f.date <= "2019-06-05"]), "nonzero balance without a declared reason"),
        (broken("float", lambda f: f[f.date <= "2025-06-04"]), "the row should exist"),
        (broken("supplementary_financing_account", lambda f: f[f.date >= "2008-10-08"]), "week of its declared introduction"),
        ({k: v for k, v in base["frames"].items() if k != "cpff_llc"}, "inputs missing"),
        (broken("loans", lambda f: f.assign(value=f["value"].where(f.index != 10, "."))), "missing or nonnumeric"),
    ]
    for frames, message in cases:
        with pytest.raises(ValueError, match=message):
            build_reserve_factor_ledger(frames, base["comp"])


def test_unit_tax_payment_lowers_reserves_and_spending_raises_them(base):
    tdc, trc = event_incidence(SettlementEvent("covered_deposit", "treasury_general_account", 1.0))
    tax = event_delta(base, "2017-05-10", {"treasury_general_account": 1.0, "reserve_balances": -1.0})
    assert tax["delta_reserve_balances"] == -1 == trc == tdc
    assert tax["c_h"] == -1 and tax["f_treasury_general_account"] == -1
    assert tax.drop(["delta_reserve_balances", "c_h", "f_treasury_general_account"]).abs().max() == 0
    spend = event_delta(base, "2017-05-10", {"treasury_general_account": -1.0, "reserve_balances": 1.0})
    assert spend["delta_reserve_balances"] == 1 and spend["c_h"] == 1 and spend["rho"] == 0


def test_sfp_counted_once_and_ttl_never_in_fed_cash(base):
    sfp = event_delta(base, "2009-06-10", {"supplementary_financing_account": 1.0, "reserve_balances": -1.0})
    assert sfp["c_h"] == -1 and sfp["f_supplementary_financing_account"] == -1 and sfp["delta_reserve_balances"] == -1
    assert sfp.drop(["c_h", "f_supplementary_financing_account", "delta_reserve_balances"]).abs().max() == 0
    # A TT&L call moves cash from a commercial-bank claim to the TGA: only the TGA leg is Fed cash.
    call = event_delta(base, "2007-03-07", {"treasury_general_account": 1.0, "reserve_balances": -1.0})
    _, call_trc = event_incidence(SettlementEvent("tt_and_l", "treasury_general_account", 1.0))
    assert call["c_h"] == call_trc == -1 and call["delta_reserve_balances"] == -1
    assert not any(spec.dataset_id.startswith("fiscaldata.") for spec in H41_LEDGER_REGISTRY.inputs)


def test_discount_and_other_liability_signs_survive(base):
    levels, _, _ = h41_levels(base["frames"], ROWS)
    assert (levels["unamortized_discounts"] < 0).all()
    assert (levels["other_liabilities_and_capital"] < 0).any() and (levels["other_liabilities_and_capital"] > 0).any()
    weekly = base["result"].weekly.set_index("date")
    assert np.array_equal(weekly["f_unamortized_discounts"].iloc[1:], levels["unamortized_discounts"].diff().iloc[1:])
    assert np.array_equal(weekly["f_other_liabilities_and_capital"].iloc[1:],
                          -levels["other_liabilities_and_capital"].diff().iloc[1:])
    discount = event_delta(base, "2015-02-04", {"unamortized_discounts": -1.0, "reserve_balances": -1.0})
    assert discount["f_unamortized_discounts"] == -1 and discount["delta_reserve_balances"] == -1
    # Interest on reserves paid while the remittance account is a deferred asset.
    deferred = event_delta(base, "2024-02-07", {"other_liabilities_and_capital": -1.0, "reserve_balances": 1.0})
    assert deferred["f_other_liabilities_and_capital"] == 1 and deferred["delta_reserve_balances"] == 1


def test_mmf_purchase_funded_by_on_rrp_runoff_is_zero_trc_and_not_counted_twice(base):
    truth = post(base["truth"], "2019-02-06", {"treasury_general_account": 1.0, "rrp_others": -1.0, "reserve_balances": 0.0})
    frames = publish(truth)
    result = build_reserve_factor_ledger(frames, make_components(frames, {"2019Q1": 1.0}))
    week = weekly_row(result, "2019-02-06").astype(str)
    before = weekly_row(base["result"], "2019-02-06").astype(str)
    diff = {c: float(week[c]) - float(before[c]) for c in ["c_h", "f_rrp_others", "delta_reserve_balances", "rho"]}
    assert diff == {"c_h": -1.0, "f_rrp_others": 1.0, "delta_reserve_balances": 0.0, "rho": 0.0}
    new = result.bridges.set_index(["quarter", "trc_variant"]).loc["2019Q1"]
    old = base["result"].bridges.set_index(["quarter", "trc_variant"]).loc["2019Q1"]
    change = (new[["x", "gamma", "c_h", "c_m", "n_rrp_others", "bridge_cash", "gap", "y_z"]]
              - old[["x", "gamma", "c_h", "c_m", "n_rrp_others", "bridge_cash", "gap", "y_z"]])
    for variant in ["trc_preferred", "trc_mmf_lower", "trc_mmf_upper"]:
        assert change.loc[variant, "c_h"] == -1 and change.loc[variant, "c_m"] == -1
        assert change.loc[variant, "gamma"] == pytest.approx(1.0)
        assert change.loc[variant, "x"] == pytest.approx(0.0)  # core cash -1 plus route +1
        assert change.loc[variant, "n_rrp_others"] == pytest.approx(0.0)  # the route is not counted again
        assert change.loc[variant, "gap"] == pytest.approx(0.0)
    assert change.loc["trc_core", "x"] == pytest.approx(-1.0) and change.loc["trc_core", "n_rrp_others"] == pytest.approx(1.0)
    assert result.stats["bridges"]["identity"]["trc_preferred"]["max_abs_identity_error"] < 1e-9


def test_bridge_identity_holds_row_by_row_for_every_variant(base):
    bridges = base["result"].bridges
    assert sorted(bridges.trc_variant.unique()) == sorted(VARIANTS)
    for variant, frame in bridges.groupby("trc_variant"):
        frame = frame.set_index("quarter")
        live = frame[frame.bridge_status.eq("reconciled_mixed_clock")]
        assert len(live) == 92 and live.index[0] == "2003Q1"
        assert frame.loc[["2002Q1", "2002Q4"], "bridge_status"].eq("unavailable_no_opening_level").all()
        rhs = (live.sum_other_factors + live.n_rrp_others + live.bridge_outcome + live.bridge_cash
               + live.bridge_securities + live.rho)
        assert np.allclose(live.y_z - live.x, rhs, atol=1e-9, rtol=0)
        assert np.allclose(live.bridge_outcome, live.bridge_outcome_term_deposits + live.bridge_outcome_z1_flow_vs_level
                           + live.bridge_outcome_unattributed, atol=1e-9, rtol=0)
        assert np.array_equal(live.n_rrp_others, live.f_rrp_others - live.gamma)
        if variant != "trc_core":
            naive = rhs - live.n_rrp_others + live.f_rrp_others  # leaves the whole RRP change in the remainder
            post = live.index >= "2013Q4"
            assert np.allclose(naive[post] - (live.y_z - live.x)[post], live.gamma[post])
            assert (live.gamma[post] > 0).all()
    one = bridges[bridges.trc_variant.eq("trc_core")].set_index("quarter")
    assert one.loc["2007Q1", "bridge_outcome_z1_flow_vs_level"] == 123
    assert one.loc["2003Q1":"2005Q4", "c_m_clock"].eq("h41_last_wednesday").all()
    assert set(base["result"].stats["bridge_summary_by_era"]) == {
        "2003Q1-2008Q3", "2008Q4", "2009Q1-2015Q3", "2015Q4", "2016Q1-2025Q4", "2003Q1-2025Q4"}


def git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-c", "core.hooksPath=/dev/null",
         "-c", "commit.gpgsign=false", "-C", str(root), *args],
        check=True, capture_output=True,
    )


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_repo(root: Path, base) -> dict[str, str]:
    input_dir = root / H41_LEDGER_REGISTRY.input_dir
    input_dir.mkdir(parents=True)
    inputs = {}
    for spec in H41_LEDGER_REGISTRY.inputs:
        relative = H41_LEDGER_REGISTRY.input_dir / f"{spec.key}.csv"
        data = base["frames"][spec.key].to_csv(index=False, lineterminator="\n").encode("utf-8")
        (root / relative).write_bytes(data)
        inputs[spec.key] = {
            "dataset_id": spec.dataset_id, "argv": list(spec.argv), "file": relative.as_posix(),
            "sha256": hashlib.sha256(data).hexdigest(), "byte_count": len(data), "cache_key": "fixture",
            "retrieved_at_utc": "fixture", "vintage": "fixture", "source_url": "fixture", "source_metadata": {},
            "row_count": len(base["frames"][spec.key]), "data_coverage": {},
        }
    manifest = root / H41_LEDGER_REGISTRY.manifest
    manifest.write_text(json.dumps({"schema_version": H41_LEDGER_REGISTRY.schema_version, "inputs": inputs}, indent=2))
    processed = root / "data" / "processed"
    processed.mkdir(parents=True)
    base["comp"].to_csv(processed / TRC_OUTPUT_FILES["components"], index=False, lineterminator="\n")
    components = sha(processed / TRC_OUTPUT_FILES["components"])
    (processed / TRC_OUTPUT_FILES["receipt"]).write_text(json.dumps(
        {"producer_commit": "fixture", "outputs": {"components": {"sha256": components}}}))
    (processed / TRC_OUTPUT_FILES["series"]).write_text("admitted\n")
    (root / ".gitignore").write_text("data/\n")
    (root / "README.md").write_text("fixture\n")
    git(root, "init", "-q")
    git(root, "add", ".gitignore", "README.md")
    git(root, "commit", "-q", "-m", "fixture")
    return {"manifest": sha(manifest), "components": components}


def ledger_args(root: Path, hashes: dict[str, str]) -> list[str]:
    return ["reserve-factor-ledger-export", "--root", str(root), "--inputs-manifest-sha256", hashes["manifest"],
            "--trc-components-sha256", hashes["components"]]


def test_cli_exports_hash_bound_outputs_and_never_touches_trc(tmp_path, base):
    hashes = make_repo(tmp_path, base)
    processed = tmp_path / "data" / "processed"
    trc_before = {name: (processed / name).read_bytes() for name in
                  [TRC_OUTPUT_FILES["components"], TRC_OUTPUT_FILES["receipt"], TRC_OUTPUT_FILES["series"]]}
    assert main(ledger_args(tmp_path, hashes)) == 0
    receipt = json.loads((processed / LEDGER_OUTPUT_FILES["receipt"]).read_text())
    for role, output in receipt["outputs"].items():
        assert sha(tmp_path / output["path"]) == output["sha256"]
    assert {name: (processed / name).read_bytes() for name in trc_before} == trc_before
    assert not set(LEDGER_OUTPUT_FILES.values()) & set(TRC_OUTPUT_FILES.values())
    assert receipt["units"] == "USD million"
    assert receipt["inputs"]["trc_quarterly_components_v1"]["sha256"] == hashes["components"]
    assert {entry["series_id"] for entry in receipt["factor_map"]} >= {"WRBWFRBL", "WDTGAL", "WDSFAL", "WSHOTSL", "WUDSHO"}
    weekly = pd.read_csv(processed / LEDGER_OUTPUT_FILES["weekly"])
    assert set(c for c in weekly.columns if c.startswith("f_")) <= set(receipt["column_clocks"]["weekly"])
    bridges = pd.read_csv(processed / LEDGER_OUTPUT_FILES["bridges"])
    assert {"bridge_outcome", "bridge_cash", "bridge_securities"} <= set(receipt["column_clocks"]["bridges"])
    assert len(bridges) == 4 * len(SHELL)

    wrong = dict(hashes, components="0" * 64)
    with pytest.raises(ValueError, match="source hash mismatch"):
        main(ledger_args(tmp_path, wrong))
    (processed / TRC_OUTPUT_FILES["receipt"]).write_text(json.dumps({"outputs": {"components": {"sha256": "f" * 64}}}))
    with pytest.raises(ValueError, match="not the one the TRC receipt admits"):
        main(ledger_args(tmp_path, hashes))
    (tmp_path / "README.md").write_text("changed\n")
    with pytest.raises(ValueError, match="clean committed"):
        main(ledger_args(tmp_path, hashes))


ADMITTED_TRC_HASHES = {
    "trc_quarterly_components_v1.csv": "bb7058c70d88adf85fde6f64ce263390c1d310d4c70be07583960eef0d52b7e9",
    "trc_quarterly_series_v1.csv": "f06560b0d8ae5c8dd2639956aa4d5818ab0a8eea3a6bb5ef53e64ea3c69a5de9",
    "trc_route_registry_v1.csv": "6dd3e4f533ed749b784029366f394f0c742d0c4523527466b0cb9c801ee8ece6",
}


@pytest.mark.integration
def test_real_ledger_closes_and_bridges_the_admitted_trc():
    root = Path(os.environ.get("TDCEST_LEDGER_INTEGRATION_ROOT", ROOT))
    processed = root / "data" / "processed"
    required = [root / H41_LEDGER_REGISTRY.manifest, *(processed / name for name in ADMITTED_TRC_HASHES)]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        pytest.fail(f"integration inputs absent: {missing}")
    for name, expected in ADMITTED_TRC_HASHES.items():
        assert sha(processed / name) == expected, name
    manifest = json.loads((root / H41_LEDGER_REGISTRY.manifest).read_text())
    frames, _ = load_fiscus_inputs(root, manifest, H41_LEDGER_REGISTRY)
    result = build_reserve_factor_ledger(frames, pd.read_csv(processed / "trc_quarterly_components_v1.csv"))
    closure = result.stats["weekly_closure"]
    assert closure["rho_level"]["max_ratio_to_bound"] < 1 and closure["rho"]["max_ratio_to_bound"] < 1
    bridges = result.stats["bridges"]
    assert bridges["y_h_minus_admitted_delta_rb_h41_max_abs"] == 0  # same last-Wednesday dating as the TRC diagnostic
    assert bridges["bridge_cash_max_abs_2003Q1_2005Q4_same_h41_clock"] == 0
    assert bridges["admitted_y_z_minus_fetched_fu713113003_max_abs"] == 0
    for variant in VARIANTS:
        assert bridges["identity"][variant] == {"max_abs_identity_error": pytest.approx(0, abs=1e-6), "n_reconciled": 92}
    sfp = result.weekly.set_index("date")["f_supplementary_financing_account"]
    assert sfp.loc["2008-09-24"] == -159806  # first SFP Wednesday drains reserves
    assert result.quarterly["quarter"].iloc[0] == "2003Q1"
