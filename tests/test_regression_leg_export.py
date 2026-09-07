from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from tdc_estimator.cli import main
from tdc_estimator.tier2_regression_series import build_regression_leg_table


def inputs():
    dates = pd.period_range("2002Q1", "2025Q4", freq="Q").end_time.normalize()
    quarterly = pd.DataFrame({
        "date": dates, "fed_tsy_tx": 10., "us_chartered_tsy_tx": 20.,
        "foreign_offices_tsy_tx": 3., "affiliated_areas_tsy_tx": 2.,
        "row_tsy_tx": 4., "treasury_operating_cash_tx": 6.,
        "fed_remit_or_deferred": 5.,
    })
    effective = (dates >= "2013-09-30").astype(float) * 7.
    regression = pd.DataFrame({
        "date": dates, "tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow": 24. + effective,
        "tdc_tier2_regression_bank_only_ru_flow": 24.,
        "tdc_tier2_regression_domestic_bank_only_ru_flow": 25.,
        "row_tier2_regression_interest_proxy": 5., "bank_tier2_regression_interest_proxy": 8.,
        "fed_tsy_coupon_interest_proxy": 1., "mmf_rrp_adjustment_prop": 7.,
        "row_method_tier": "fixture", "tier2_regression_bank_row_method_tier": "fixture",
    })
    return quarterly, regression


def test_independent_reconstruction_and_mechanism_gate():
    frame = build_regression_leg_table(*inputs())
    assert len(frame) == 96
    assert frame.R.eq(-1).all()
    assert frame.O.eq(-6).all()
    assert frame.loc[frame.quarter == "2013Q2", "J"].item() == 31.
    assert frame.loc[frame.quarter == "2013Q3", "J"].item() == 38.
    assert frame.J.equals(frame.J_expanded)
    assert frame.filter(like="gap").eq(0).all().all()


def test_only_pre_mechanism_missing_mmf_is_structural():
    quarterly, regression = inputs()
    regression.loc[regression.date < "2013-09-30", "mmf_rrp_adjustment_prop"] = float("nan")
    frame = build_regression_leg_table(quarterly, regression)
    assert frame.mmf_adjustment_raw_missing.sum() == 46
    assert frame.loc[frame.mmf_adjustment_raw_missing, "effective_mmf_rrp_adjustment_prop"].eq(0).all()
    regression.loc[regression.date == "2013-09-30", "mmf_rrp_adjustment_prop"] = float("nan")
    with pytest.raises(ValueError, match="nonfinite required"):
        build_regression_leg_table(quarterly, regression)


@pytest.mark.parametrize("defect", ["missing_row", "duplicate", "bad_date", "missing_column", "nan", "inf", "blank_tier", "cash_drift", "row_drift", "fed_drift"])
def test_bad_inputs_fail_closed(defect):
    quarterly, regression = inputs()
    if defect == "missing_row":
        quarterly = quarterly.iloc[1:]
    elif defect == "duplicate":
        quarterly = pd.concat([quarterly, quarterly.iloc[:1]])
    elif defect == "bad_date":
        quarterly.loc[0, "date"] = pd.Timestamp("2002-03-30")
    elif defect == "missing_column":
        quarterly = quarterly.drop(columns="foreign_offices_tsy_tx")
    elif defect in {"nan", "inf"}:
        quarterly.loc[0, "fed_tsy_tx"] = float(defect)
    elif defect == "blank_tier":
        regression.loc[0, "row_method_tier"] = ""
    else:
        column = {"cash_drift": "treasury_operating_cash_tx", "row_drift": "row_tsy_tx", "fed_drift": "fed_tsy_tx"}[defect]
        quarterly.loc[0, column] += .01
    with pytest.raises(ValueError):
        build_regression_leg_table(quarterly, regression)


def test_cli_exports_receipted_pinned_sources_and_rejects_changed_input(tmp_path, monkeypatch, capsys):
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    paths = [processed / "quarterly_inputs.csv", processed / "tdc_tier2_regression_series.csv"]
    for frame, path in zip(inputs(), paths):
        frame.to_csv(path, index=False)
    hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
    monkeypatch.setattr("tdc_estimator.tier2_regression_series.subprocess.check_output",
                        lambda args, **kwargs: "" if "status" in args else "a" * 40)
    args = ["regression-leg-export", "--root", str(tmp_path), "--quarterly-sha256", hashes[0], "--regression-sha256", hashes[1]]
    assert main(args) == 0
    receipt = json.loads((processed / "tdc_regression_legs_v1_receipt.json").read_text())
    assert receipt["output"]["sha256"] == hashlib.sha256((processed / "tdc_regression_legs_v1.csv").read_bytes()).hexdigest()
    assert receipt["negative_R_quarters"] == 96
    assert receipt["negative_R_with_nonnegative_raw_purchases"] == 96
    assert all(item["delta_usd_million"] is None for item in receipt["source_resolution"].values())
    assert json.loads(capsys.readouterr().out)["sample"]["n"] == 96
    paths[0].write_bytes(paths[0].read_bytes() + b"\n")
    with pytest.raises(ValueError, match="source hash mismatch"):
        main(args)
    monkeypatch.setattr("tdc_estimator.tier2_regression_series.subprocess.check_output", lambda *a, **k: " M src/producer.py")
    with pytest.raises(ValueError, match="clean committed"):
        main(args)
