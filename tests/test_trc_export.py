"""TRC export: materialized fixtures through the production CLI, plus an integration lane.

The fixture repository is a real git checkout. The frozen leg table is produced
by the production `regression-leg-export` command from fixture inputs, then
`trc-export` consumes it with hash-pinned fiscus-style inputs. The 2008 DTS
Table I balances and Z.1 operating-cash transactions are the published values.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from tdc_estimator.catalog import TRC_FISCUS_INPUTS
from tdc_estimator.cli import main
from tdc_estimator.mmf_rrp import mmf_on_rrp_route_adjustment
from tdc_estimator.settlement_routes import SettlementEvent, event_incidence, load_settlement_routes
from tdc_estimator.tier2_regression_series import write_regression_leg_table
from tdc_estimator.trc_export import (
    FISCUS_INPUT_DIR,
    INPUTS_MANIFEST,
    MANIFEST_SCHEMA_VERSION,
    TRC_OUTPUT_FILES,
    load_fiscus_inputs,
)
from tdc_estimator.trc_reserve_component import (
    TrcInputs,
    build_trc_components,
    parse_dts_table_i,
    reserve_factor_remainder,
)

ROOT = Path(__file__).resolve().parents[1]
LEVEL_QUARTERS = pd.period_range("2001Q4", "2025Q4", freq="Q")
SHELL = pd.period_range("2002Q1", "2025Q4", freq="Q")
REAL_2008_DTS = {  # DTS Table I closing balances, USD million
    "2008-06-30": {"tga": 4978, "ttl": 48338},
    "2008-09-18": {"tga": 5345, "sfp": 39988, "ttl": 6907},
    "2008-09-30": {"tga": 32988, "sfp": 299491, "ttl": 39129},
    "2008-12-31": {"tga": 106123, "sfp": 259325, "ttl": 1199},
}
REAL_2008_Z1_TOC = {"2008Q3": 318292.0, "2008Q4": -4960.0}  # Z.1 FU313024000
SFP_START, LINES_END = pd.Timestamp("2008-09-18"), pd.Timestamp("2022-04-15")
NONDEFAULT = {
    "route_bound_gse_on_rrp", "route_bound_foreign_official", "trc_route_bounded_nondefault",
    "remainder_on_rrp", "remainder_foreign_official", "memo_reserves_plus_rrp_others",
    "memo_h3_total_reserves", "memo_us_chartered_reserves", "diag_h41_reserve_change", "diag_trc_h41_tga",
}


def _wiggle(day: pd.Timestamp, mult: int, mod: int) -> int:
    return (day.toordinal() * mult) % mod


def tga(day):
    real = REAL_2008_DTS.get(day.strftime("%Y-%m-%d"), {})
    return real.get("tga", 5000 + _wiggle(day, 37, 9973))


def sfp(day):
    real = REAL_2008_DTS.get(day.strftime("%Y-%m-%d"), {})
    if day < SFP_START:
        return None
    if "sfp" in real:
        return real["sfp"]
    return 200000 if day <= pd.Timestamp("2011-06-30") else 0


def ttl(day):
    real = REAL_2008_DTS.get(day.strftime("%Y-%m-%d"), {})
    if "ttl" in real:
        return real["ttl"]
    return 2000 + _wiggle(day, 13, 500) if day < pd.Timestamp("2011-12-01") else 0


def last_weekday(quarter, weekday=None):
    """Last business day (or last given weekday) on or before the quarter end."""
    day = quarter.end_time.normalize()
    while (day.weekday() > 4) if weekday is None else (day.weekday() != weekday):
        day -= pd.Timedelta(days=1)
    return day


def dts_frame() -> pd.DataFrame:
    days = {pd.Timestamp("2005-10-03"), *map(pd.Timestamp, REAL_2008_DTS)}
    for quarter in pd.period_range("2005Q4", "2025Q4", freq="Q"):
        days |= {last_weekday(quarter), last_weekday(quarter, 2)}
    rows = []
    for day in sorted(days):
        accounts = []
        if day <= pd.Timestamp("2021-09-30"):
            accounts.append(("Federal Reserve Account", tga(day), tga(day)))
        elif day <= LINES_END:
            accounts.append(("Treasury General Account (TGA)", tga(day), tga(day)))
        else:
            accounts += [("Treasury General Account (TGA) Closing Balance", tga(day), "null"),
                         ("Treasury General Account (TGA) Opening Balance", 1, "null"),
                         ("Total TGA Deposits (Table II)", 2, "null")]
        if day <= LINES_END:
            if sfp(day) is not None:
                name = "Supplementary Financing Prog" if day < pd.Timestamp("2013-01-04") else "Supplementary Financing Program Account"
                accounts.append((name, sfp(day), sfp(day)))
            name = ("Tax and Loan Note Accounts (Table V)" if day <= pd.Timestamp("2012-05-31")
                    else "Account Short-Term Cash Investments (Table V)" if day <= pd.Timestamp("2013-01-03")
                    else "Short-Term Cash Investments (Table V)")
            accounts.append((name, ttl(day), ttl(day)))
        if pd.Timestamp("2008-12-01") <= day <= pd.Timestamp("2010-09-30"):
            accounts.append(("Financial Institution Account", 0, 0))
        rows += [(day.strftime("%Y-%m-%d"), *account) for account in accounts]
    frame = pd.DataFrame(rows, columns=["record_date", "account_type", "open_today_bal", "close_today_bal"])
    frame["table_nbr"] = "I"
    return frame


def dts_level(quarter, fn):
    value = fn(last_weekday(quarter))
    return 0.0 if value is None else float(value)


def fixture_frames() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    wednesdays = pd.date_range("2002-12-18", "2025-12-31", freq="W-WED")

    def rb(d):
        return (20000 if d < pd.Timestamp("2008-10-01") else 1_500_000) + _wiggle(d, 17, 5000)

    def h41(fn):
        return pd.DataFrame({"date": wednesdays.strftime("%Y-%m-%d"), "value": [str(int(fn(d))) for d in wednesdays]})

    months = pd.date_range("2002-01-01", "2025-12-01", freq="MS")
    sources = {
        "dts_operating_cash_balance_table_i": dts_frame(),
        "h41_tga_wednesday": h41(tga),
        "h41_reserve_balances_wednesday": h41(rb),
        "h41_rrp_others_wednesday": h41(lambda d: 0 if d < pd.Timestamp("2013-09-23") else 1000 + _wiggle(d, 11, 3000)),
        "h41_rrp_foreign_official_wednesday": h41(lambda d: 20000 + _wiggle(d, 5, 2000)),
        "h41_foreign_official_deposits_wednesday": h41(lambda d: 100 + _wiggle(d, 3, 50)),
        "h41_custody_marketable_treasury_wednesday": h41(lambda d: 0 if d < pd.Timestamp("2007-07-04") else 1_000_000 + _wiggle(d, 29, 50000)),
        "h3_total_reserves_monthly": pd.DataFrame({
            "date": months.strftime("%Y-%m-%d"),
            "value": [f"{rb(m + pd.offsets.MonthEnd(0)) / 1000:.1f}" for m in months]}),
    }
    sfp_levels = pd.Series([0.0 if q < pd.Period("2008Q3") else dts_level(q, sfp) for q in LEVEL_QUARTERS], index=LEVEL_QUARTERS)
    z1 = {
        "z1_reserves_transactions": [1000.0 * (((i * 7) % 11) - 5) for i in range(len(SHELL))],
        "z1_sfp_transactions": sfp_levels.diff().reindex(SHELL).tolist(),
        "z1_us_chartered_reserves_transactions": [500.0 * (((i * 3) % 7) - 3) for i in range(len(SHELL))],
    }
    for key, values in z1.items():
        sources[key] = pd.DataFrame({"date": SHELL.end_time.strftime("%Y-%m-%d"), "value": [f"{v:g}" for v in values]})

    n = len(LEVEL_QUARTERS)
    i = np.arange(n)
    active = LEVEL_QUARTERS >= pd.Period("2013Q3")
    dts_q = LEVEL_QUARTERS >= pd.Period("2005Q4")
    toc = pd.Series(100.0 * (i % 9 - 4), index=LEVEL_QUARTERS)
    tga_l = pd.Series([dts_level(q, tga) if d else np.nan for q, d in zip(LEVEL_QUARTERS, dts_q)], index=LEVEL_QUARTERS)
    ttl_l = pd.Series([dts_level(q, ttl) if d else np.nan for q, d in zip(LEVEL_QUARTERS, dts_q)], index=LEVEL_QUARTERS)
    partition = tga_l.diff() + sfp_levels.diff() + ttl_l.diff()
    toc[LEVEL_QUARTERS >= pd.Period("2006Q1")] = partition[LEVEL_QUARTERS >= pd.Period("2006Q1")]
    for quarter, value in REAL_2008_Z1_TOC.items():
        toc[pd.Period(quarter)] = value
    quarterly = pd.DataFrame({
        "date": LEVEL_QUARTERS.end_time.strftime("%Y-%m-%d"),
        "fed_tsy_tx": 1000.0 + 10 * i, "us_chartered_tsy_tx": 200.0 + i, "foreign_offices_tsy_tx": 30.0,
        "affiliated_areas_tsy_tx": 5.0, "row_tsy_tx": 400.0 + 2 * i, "treasury_operating_cash_tx": toc.to_numpy(),
        "fed_remit_or_deferred": 50.0,
        "mmf_rrp_adjustment_lb": np.where(active, 10.0, np.nan),
        "mmf_rrp_adjustment_prop": np.where(active, 20.0, np.nan),
        "mmf_rrp_adjustment_ub": np.where(active, 30.0, np.nan),
        "gse_tsy_tx": 5.0, "gse_tsy_level": 1000.0 + 5 * i,
        "gse_on_rrp": np.where(active, np.where(i % 2 == 0, 3000.0, 1000.0), np.nan),
    })
    first = LEVEL_QUARTERS.get_loc(pd.Period("2013Q3"))
    quarterly.loc[first, ["mmf_rrp_adjustment_lb", "mmf_rrp_adjustment_prop", "mmf_rrp_adjustment_ub"]] = [np.nan, 0.0, 0.0]

    q = quarterly.iloc[1:].reset_index(drop=True)
    effective = np.where(SHELL >= pd.Period("2013Q3"), q["mmf_rrp_adjustment_prop"].fillna(0.0), 0.0)
    row_interest, bank_interest, coupon = 40.0, 8.0, 60.0
    r_leg = q["row_tsy_tx"] - row_interest
    j_leg = (q["fed_tsy_tx"] + q[["us_chartered_tsy_tx", "foreign_offices_tsy_tx", "affiliated_areas_tsy_tx"]].sum(axis=1)
             + q["fed_remit_or_deferred"] - coupon - bank_interest + effective)
    canonical = r_leg + j_leg - q["treasury_operating_cash_tx"]
    regression = pd.DataFrame({
        "date": q["date"], "tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow": canonical,
        "tdc_tier2_regression_bank_only_ru_flow": canonical - effective,
        "tdc_tier2_regression_domestic_bank_only_ru_flow": canonical - effective - r_leg,
        "row_tier2_regression_interest_proxy": row_interest, "bank_tier2_regression_interest_proxy": bank_interest,
        "fed_tsy_coupon_interest_proxy": coupon, "mmf_rrp_adjustment_prop": q["mmf_rrp_adjustment_prop"],
        "row_method_tier": "fixture", "tier2_regression_bank_row_method_tier": "fixture",
    })
    return quarterly, regression, sources


def git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-c", "core.hooksPath=/dev/null",
         "-c", "commit.gpgsign=false", "-C", str(root), *args],
        check=True, capture_output=True,
    )


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(root: Path, sources: dict[str, pd.DataFrame]) -> str:
    inputs = {}
    for spec in TRC_FISCUS_INPUTS:
        relative = FISCUS_INPUT_DIR / f"{spec.key}.csv"
        data = sources[spec.key].to_csv(index=False, lineterminator="\n").encode("utf-8")
        (root / relative).write_bytes(data)
        inputs[spec.key] = {
            "dataset_id": spec.dataset_id, "argv": list(spec.argv), "file": relative.as_posix(),
            "sha256": hashlib.sha256(data).hexdigest(), "byte_count": len(data), "cache_key": "fixture",
            "retrieved_at_utc": "fixture", "vintage": "fixture", "source_url": "fixture", "source_metadata": {},
            "row_count": len(sources[spec.key]), "data_coverage": {},
        }
    text = json.dumps({"schema_version": MANIFEST_SCHEMA_VERSION, "inputs": inputs}, indent=2) + "\n"
    (root / INPUTS_MANIFEST).write_text(text)
    return sha(root / INPUTS_MANIFEST)


def make_repo(root: Path) -> dict[str, str]:
    quarterly, regression, sources = fixture_frames()
    processed = root / "data" / "processed"
    (root / FISCUS_INPUT_DIR).mkdir(parents=True)
    processed.mkdir(parents=True)
    quarterly.to_csv(processed / "quarterly_inputs.csv", index=False)
    regression.to_csv(processed / "tdc_tier2_regression_series.csv", index=False)
    manifest_hash = write_manifest(root, sources)
    (root / ".gitignore").write_text("data/\n")
    (root / "README.md").write_text("fixture\n")
    git(root, "init", "-q")
    git(root, "add", ".gitignore", "README.md")
    git(root, "commit", "-q", "-m", "fixture")
    hashes = {"quarterly": sha(processed / "quarterly_inputs.csv"),
              "regression": sha(processed / "tdc_tier2_regression_series.csv"), "manifest": manifest_hash}
    assert main(["regression-leg-export", "--root", str(root), "--quarterly-sha256", hashes["quarterly"],
                 "--regression-sha256", hashes["regression"]]) == 0
    hashes["legs"] = sha(processed / "tdc_regression_legs_v1.csv")
    return hashes


def trc_args(root: Path, hashes: dict[str, str]) -> list[str]:
    return ["trc-export", "--root", str(root), "--legs-sha256", hashes["legs"],
            "--quarterly-sha256", hashes["quarterly"], "--inputs-manifest-sha256", hashes["manifest"]]


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    root = tmp_path_factory.mktemp("trc_repo")
    hashes = make_repo(root)
    processed = root / "data" / "processed"
    legacy = {name: (processed / name).read_bytes() for name in
              ["tdc_regression_legs_v1.csv", "tdc_regression_legs_v1_receipt.json", "quarterly_inputs.csv"]}
    assert main(trc_args(root, hashes)) == 0
    components = pd.read_csv(processed / TRC_OUTPUT_FILES["components"]).set_index("quarter")
    series = pd.read_csv(processed / TRC_OUTPUT_FILES["series"], keep_default_na=True)
    receipt = json.loads((processed / TRC_OUTPUT_FILES["receipt"]).read_text())
    return {"root": root, "hashes": hashes, "legacy": legacy, "components": components, "series": series,
            "receipt": receipt}


def test_2002_observations_are_unavailable_never_zero(exported):
    comp, series = exported["components"], exported["series"]
    year = comp.loc[["2002Q1", "2002Q2", "2002Q3", "2002Q4"]]
    trc_columns = ["trc_cash_leg", "trc_core", "trc_preferred", "trc_mmf_lower", "trc_mmf_upper",
                   "nontreasury_residual", "wedge_measured"]
    assert year[trc_columns].isna().all().all()
    assert year["trc_status"].eq("unavailable_no_opening_tga_level").all()
    rows = series[series.series_id.isin(["trc_core", "trc_preferred", "nontreasury_residual"])
                  & series.quarter.str.startswith("2002")]
    assert len(rows) == 12
    assert rows[["value_lower", "value_central", "value_upper"]].isna().all().all()
    assert rows.measurement_status.eq("unavailable_no_opening_tga_level").all()
    assert np.isfinite(comp.loc["2003Q1", "trc_preferred"])
    assert comp.loc["2003Q1", "tga_clock"] == "h41_last_wednesday"


def test_2008_operating_cash_contains_tga_ttl_and_sfp_and_rejects_double_subtraction(exported):
    comp = exported["components"]
    q3, q4 = comp.loc["2008Q3"], comp.loc["2008Q4"]
    assert (q3.delta_tga, q3.delta_ttl, q3.delta_sfp) == (28010, -9209, 299491)
    assert (q4.delta_tga, q4.delta_ttl, q4.delta_sfp) == (73135, -37930, -40166)
    assert q3.delta_tga + q3.delta_ttl + q3.delta_sfp == q3.z1_treasury_operating_cash_tx == 318292
    assert q4.z1_treasury_operating_cash_tx - (q4.delta_tga + q4.delta_ttl + q4.delta_sfp) == 1  # published rounding
    for row in [q3, q4]:
        assert row.trc_cash_leg == -(row.delta_tga + row.delta_sfp)
        draft = -row.z1_treasury_operating_cash_tx - row.delta_sfp
        # The draft counts SFP twice and imports TT&L into the reserve leg.
        assert draft - row.trc_cash_leg == pytest.approx(-(row.delta_sfp + row.delta_ttl) - row.cash_partition_gap)
        assert draft != row.trc_cash_leg
    assert q3.trc_cash_leg == -327501
    assert q3.wedge_residual_u == pytest.approx(0.0, abs=1e-6)
    assert q4.wedge_residual_u == pytest.approx(-1.0, abs=1e-6)


def test_remainder_cells_subtract_treasury_allocations_exactly_once(exported):
    # A fund moves 60 from ON RRP into an auction and 40 from ON RRP into its bank deposit.
    _, auction_trc = event_incidence(SettlementEvent("mmf_on_rrp", "treasury_general_account", 60.0))
    delta_tga, delta_rrp, reserve_change = 60.0, -100.0, 40.0
    allocation = pd.DataFrame({"lower": [60.0], "central": [60.0], "upper": [60.0]})
    measured_trc = -delta_tga + allocation.central[0]
    cell = reserve_factor_remainder(pd.Series([delta_rrp]), allocation)
    assert measured_trc == auction_trc == 0.0
    assert measured_trc + cell.central[0] == reserve_change
    assert measured_trc + -delta_rrp != reserve_change  # omitting the allocation double counts it
    # A foreign official account pays 30 at auction and moves 20 to a correspondent bank.
    _, official_trc = event_incidence(SettlementEvent("foreign_official_deposit", "treasury_general_account", 30.0))
    fo = reserve_factor_remainder(pd.Series([-50.0]), pd.DataFrame({"lower": [30.0], "central": [30.0], "upper": [30.0]}))
    assert -30.0 + 30.0 == official_trc and official_trc + fo.central[0] == 20.0

    comp = exported["components"].loc["2014Q1":]
    assert np.allclose(comp.remainder_on_rrp_central, -comp.delta_rrp_others_h41 - comp.mmf_route_prop)
    assert np.allclose(comp.remainder_on_rrp_lower, -comp.delta_rrp_others_h41 - comp.mmf_route_ub)
    assert np.allclose(comp.remainder_on_rrp_upper, -comp.delta_rrp_others_h41 - comp.mmf_route_lb)
    assert np.allclose(comp.remainder_foreign_official_central, -comp.delta_fo_cash)
    assert np.allclose(comp.remainder_foreign_official_lower, -comp.delta_fo_cash - comp.fo_route_upper)
    full = exported["components"].loc["2003Q1":]
    assert np.allclose(full.nontreasury_residual + full.trc_preferred, full.delta_rb_z1)


def test_frozen_tdc_artifacts_stay_byte_identical(exported):
    root, processed = exported["root"], exported["root"] / "data" / "processed"
    for name, data in exported["legacy"].items():
        assert (processed / name).read_bytes() == data
    hashes = exported["hashes"]
    assert main(["regression-leg-export", "--root", str(root), "--quarterly-sha256", hashes["quarterly"],
                 "--regression-sha256", hashes["regression"]]) == 0
    for name in ["tdc_regression_legs_v1.csv", "tdc_regression_legs_v1_receipt.json"]:
        assert (processed / name).read_bytes() == exported["legacy"][name]
    assert not set(TRC_OUTPUT_FILES.values()) & set(exported["legacy"])
    receipt = exported["receipt"]
    for role, output in receipt["outputs"].items():
        assert sha(root / output["path"]) == output["sha256"]
    assert receipt["inputs"]["tdc_regression_legs_v1"]["sha256"] == hashes["legs"]
    assert receipt["inputs"]["inputs_manifest"]["sha256"] == hashes["manifest"]


def test_series_contract_and_default_policy(exported):
    series, comp = exported["series"], exported["components"]
    values = series[["value_lower", "value_central", "value_upper"]]
    unavailable = series.measurement_status.str.startswith("unavailable")
    assert unavailable.equals(values.isna().all(axis=1))
    assert set(series.loc[~series.default_eligible, "series_id"]) == NONDEFAULT
    preferred = series[(series.series_id == "trc_preferred") & ~unavailable]
    assert preferred.measurement_status.eq("partial_one_sided_route_coverage").all()
    assert len(preferred) == 92
    assert (preferred.value_lower <= preferred.value_central + 1e-9).all()
    assert (preferred.value_central <= preferred.value_upper + 1e-9).all()
    routes = load_settlement_routes()
    for coverage in series.route_coverage.dropna():
        assert set(coverage.split("|")) <= set(routes)
    clocks = series[series.series_id == "trc_core"].set_index("quarter").clock
    assert clocks["2005Q4"].startswith("treasury_fed_deposits:h41_last_wednesday")
    assert clocks["2006Q1"].startswith("treasury_fed_deposits:dts_final_business_day")
    # Both endpoints of the first DTS-clock change are DTS levels.
    assert comp.loc["2006Q1", "delta_tga"] == dts_level(pd.Period("2006Q1"), tga) - dts_level(pd.Period("2005Q4"), tga)
    legacy = series[series.series_id == "trc_preferred"].legacy_artifact_hash_set.iloc[0]
    assert exported["hashes"]["legs"] in legacy and exported["hashes"]["quarterly"] in legacy
    registry = pd.read_csv(exported["root"] / "data" / "processed" / TRC_OUTPUT_FILES["route_registry"])
    assert dict(zip(registry.route_id, registry.trc_incidence)) == {k: r.trc_incidence for k, r in routes.items()}


def test_foreign_official_bound_is_never_a_point_estimate(exported):
    series, comp = exported["series"], exported["components"]
    bound = series[series.series_id == "route_bound_foreign_official"].set_index("quarter")
    assert bound.value_central.isna().all()
    assert bound.loc["2007Q3", "measurement_status"] == "unavailable_custody_not_reported"
    assert bound.loc["2007Q4", "measurement_status"] == "nondefault_heuristic_opposite_sign_overlap_bound"
    live = comp.loc["2007Q4":]
    up = (live.delta_custody > 0) & (live.delta_fo_cash < 0)
    assert up.any()
    assert np.allclose(live.loc[up, "fo_route_upper"], np.minimum(live.delta_custody, -live.delta_fo_cash)[up])
    assert live.loc[up, "fo_route_lower"].eq(0).all()
    same_sign = np.sign(live.delta_custody) == np.sign(live.delta_fo_cash)
    assert live.loc[same_sign, ["fo_route_lower", "fo_route_upper"]].eq(0).all().all()


def test_cli_rejects_dirty_tree_hash_mismatch_and_tampered_inputs(tmp_path):
    hashes = make_repo(tmp_path)
    bad = dict(hashes, legs="0" * 64)
    with pytest.raises(ValueError, match="source hash mismatch"):
        main(trc_args(tmp_path, bad))
    target = tmp_path / FISCUS_INPUT_DIR / "z1_reserves_transactions.csv"
    original = target.read_bytes()
    target.write_bytes(original + b"\n")
    with pytest.raises(ValueError, match="z1_reserves_transactions: source hash mismatch"):
        main(trc_args(tmp_path, hashes))
    target.write_bytes(original)
    manifest = json.loads((tmp_path / INPUTS_MANIFEST).read_text())
    manifest["inputs"]["z1_reserves_transactions"]["argv"][1] = "FU713113005.Q"
    (tmp_path / INPUTS_MANIFEST).write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="request differs"):
        main(trc_args(tmp_path, dict(hashes, manifest=sha(tmp_path / INPUTS_MANIFEST))))
    (tmp_path / "README.md").write_text("changed\n")
    with pytest.raises(ValueError, match="clean committed"):
        main(trc_args(tmp_path, hashes))
    assert not (tmp_path / "data" / "processed" / TRC_OUTPUT_FILES["series"]).exists()


def _dts(rows):
    return pd.DataFrame(rows, columns=["record_date", "account_type", "open_today_bal", "close_today_bal"])


BASE_DTS = [
    ("2008-09-17", "Federal Reserve Account", "1", "10"),
    ("2008-09-17", "Tax and Loan Note Accounts (Table V)", "1", "5"),
    ("2008-09-18", "Federal Reserve Account", "1", "11"),
    ("2008-09-18", "Supplementary Financing Prog", "0", "40"),
    ("2008-09-18", "Tax and Loan Note Accounts (Table V)", "1", "6"),
    ("2011-09-30", "Federal Reserve Account", "1", "13"),
    ("2011-09-30", "Supplementary Financing Program", "0", "0"),
    ("2011-09-30", "Tax and Loan Note Accounts (Table V)", "1", "0"),
    ("2022-04-18", "Treasury General Account (TGA) Closing Balance", "12", "null"),
    ("2022-04-18", "Total TGA Deposits (Table II)", "3", "null"),
]


@pytest.mark.parametrize("change,message", [
    (lambda r: r + [("2008-09-18", "Unknown Account", "1", "1")], "unrecognized account types"),
    (lambda r: r + [("2008-09-18", "Federal Reserve Account", "1", "2")], "ambiguous duplicate"),
    (lambda r: [x if x[1] != "Treasury General Account (TGA) Closing Balance" else (x[0], x[1], "12", "12") for x in r],
     "ambiguous TGA closing"),
    (lambda r: [x for x in r if x[:2] != ("2008-09-17", "Federal Reserve Account")], "exactly one TGA"),
    (lambda r: r + [("2009-01-02", "Federal Reserve Account", "1", "1"),
                    ("2009-01-02", "Tax and Loan Note Accounts (Table V)", "0", "3")], "missing inside its reporting span"),
    (lambda r: [x if x[:2] != ("2011-09-30", "Tax and Loan Note Accounts (Table V)") else (*x[:3], "7") for x in r],
     "discontinued with a nonzero"),
    (lambda r: [x if x[:2] != ("2008-09-18", "Supplementary Financing Prog") else (*x[:3], "x") for x in r], "nonnumeric"),
])
def test_dts_parser_fails_loud(change, message):
    assert parse_dts_table_i(_dts(BASE_DTS)).loc["2022-04-18", "tga"] == 12
    with pytest.raises(ValueError, match=message):
        parse_dts_table_i(_dts(change(list(BASE_DTS))))


def test_dts_parser_structural_zeros_are_explicit():
    daily = parse_dts_table_i(_dts(BASE_DTS))
    assert daily.loc["2008-09-17", "sfp_status"] == "structural_zero_pre_program"
    assert daily.loc["2022-04-18", "sfp_status"] == "structural_zero_line_discontinued"
    assert daily.loc["2022-04-18", "ttl_status"] == "structural_zero_line_discontinued"
    assert daily.loc["2008-09-18", ["tga", "sfp", "ttl"]].tolist() == [11, 40, 6]


def test_mmf_route_status_is_explicit_and_fails_closed():
    quarters = pd.period_range("2013Q2", "2014Q1", freq="Q")
    frame = pd.DataFrame({"mmf_rrp_adjustment_lb": [np.nan, np.nan, 1.0, 2.0],
                          "mmf_rrp_adjustment_prop": [np.nan, 0.0, 2.0, 3.0],
                          "mmf_rrp_adjustment_ub": [np.nan, 0.0, 3.0, 4.0]}, index=quarters)
    out = mmf_on_rrp_route_adjustment(frame)
    assert out.mmf_route_status.tolist() == [
        "structural_zero_pre_on_rrp_mechanism", "observed_one_sided_lb_implied_by_zero_ub",
        "observed_one_sided", "observed_one_sided"]
    assert out.loc[quarters[0], ["mmf_route_lb", "mmf_route_prop", "mmf_route_ub"]].eq(0).all()
    assert out.mmf_route_raw_missing.tolist() == [True, True, False, False]
    broken = frame.copy()
    broken.loc[quarters[2], "mmf_rrp_adjustment_prop"] = np.nan
    with pytest.raises(ValueError, match="missing active-period"):
        mmf_on_rrp_route_adjustment(broken)
    broken = frame.copy()
    broken.loc[quarters[3], "mmf_rrp_adjustment_lb"] = 5.0
    with pytest.raises(ValueError, match="out of order"):
        mmf_on_rrp_route_adjustment(broken)


FROZEN_HASHES = {
    "tdc_regression_legs_v1.csv": "bea2379870d1f129d15ca183312a3682c863b565dcae58f18fbbd609ced340c6",
    "quarterly_inputs.csv": "99f8a263ff5e1e9b89499f694d825954f226bf452f7626e33b2f4faa1a249bfe",
    "tdc_tier2_regression_series.csv": "7457fdd4e8442ef2718489eb6ab0d3e7cf453496d8bc48e9eb49467355dcd6d5",
}
REFERENCE_EPISODES = {  # USD billion: (Z.1 reserve change, core plus proportional MMF route)
    "2008Q3": (182.8, -329.4), "2008Q4": (575.7, -28.8), "2009Q1": (-32.1, 111.4),
    "2020Q2": (312.8, 46.5), "2021Q2": (-161.1, 530.0), "2021Q3": (347.6, 926.8),
    "2023Q2": (-136.9, -277.1), "2023Q3": (19.8, -132.8), "2023Q4": (68.1, -1.7),
}
# 2003-2007 is 0.011 because the 2006Q1 TGA change uses DTS at both endpoints;
# a mixed H.4.1-to-DTS 2006Q1 change gives 0.010.
REFERENCE_CORRELATIONS = {"2003Q1-2007Q4": 0.011, "2008Q1-2014Q4": 0.359, "2015Q1-2019Q4": 0.760, "2020Q1-2025Q4": 0.681}


@pytest.mark.integration
def test_real_inputs_reproduce_reference_episodes(tmp_path, monkeypatch):
    root = Path(os.environ.get("TDCEST_TRC_INTEGRATION_ROOT", ROOT))
    processed = root / "data" / "processed"
    required = [processed / name for name in FROZEN_HASHES] + [root / INPUTS_MANIFEST]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        pytest.fail(f"integration inputs absent: {missing}")
    for name, expected in FROZEN_HASHES.items():
        assert sha(processed / name) == expected, name
    manifest = json.loads((root / INPUTS_MANIFEST).read_text())
    frames, _ = load_fiscus_inputs(root, manifest)
    comp, stats = build_trc_components(TrcInputs(
        pd.read_csv(processed / "tdc_regression_legs_v1.csv"), pd.read_csv(processed / "quarterly_inputs.csv"), frames))
    comp = comp.set_index("quarter")
    for quarter, (reserves, trc) in REFERENCE_EPISODES.items():
        assert round(comp.loc[quarter, "delta_rb_z1"] / 1e3, 1) == reserves, quarter
        assert round(comp.loc[quarter, "trc_preferred"] / 1e3, 1) == trc, quarter
    observed = stats["correlation_z1_reserve_change_with_trc"]["trc_preferred"]
    assert {window: round(value, 3) for window, value in observed.items()} == REFERENCE_CORRELATIONS
    assert comp.loc["2002Q1":"2002Q4", "trc_preferred"].isna().all()
    assert stats["sfp_change_dts_vs_z1"]["max_abs_difference"] == 0
    # This branch reproduces the frozen leg table byte for byte from its pinned inputs.
    rebuilt = tmp_path / "data" / "processed"
    rebuilt.mkdir(parents=True)
    for name in ["quarterly_inputs.csv", "tdc_tier2_regression_series.csv"]:
        shutil.copyfile(processed / name, rebuilt / name)
    monkeypatch.setattr("tdc_estimator.tier2_regression_series.subprocess.check_output",
                        lambda args, **kwargs: "" if "status" in args else "0" * 40)
    write_regression_leg_table(
        root=tmp_path, quarterly_path=rebuilt / "quarterly_inputs.csv",
        regression_path=rebuilt / "tdc_tier2_regression_series.csv",
        quarterly_sha256=FROZEN_HASHES["quarterly_inputs.csv"],
        regression_sha256=FROZEN_HASHES["tdc_tier2_regression_series.csv"],
        out_path=rebuilt / "tdc_regression_legs_v1.csv", receipt_path=rebuilt / "receipt.json",
    )
    assert sha(rebuilt / "tdc_regression_legs_v1.csv") == FROZEN_HASHES["tdc_regression_legs_v1.csv"]
