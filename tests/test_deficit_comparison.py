"""Measured TDC against the MTS deficit: fixture economics through the production builders and CLI.

The fixture legs carry every raw regression-leg column, and C is built from them with the
published leg arithmetic written out here, independent of the registry. The monthly MTS
surplus is negative in deficit months, as Treasury and FRED publish it.
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

from tdc_estimator import catalog
from tdc_estimator.catalog import (
    MEASUREMENT_VINTAGES,
    ComparisonPeriod,
    deficit_comparison_periods,
    fiscus_registries,
)
from tdc_estimator.cli import main
from tdc_estimator.deficit_comparison import (
    DEFICIT_KEY,
    OUTPUT_FILES,
    build_comparison,
)
from tdc_estimator.trc_export import load_fiscus_inputs

ROOT = Path(__file__).resolve().parents[1]
VINTAGE = MEASUREMENT_VINTAGES["2026q2"]
QUARTERS = pd.period_range("2002Q1", VINTAGE.quarter_end, freq="Q")
MONTHS = pd.period_range("2002-01", "2026-06", freq="M")
REGISTRY = fiscus_registries(VINTAGE)["deficit"]
RAW_COLUMNS = [
    "us_chartered_tsy_tx", "foreign_offices_tsy_tx", "affiliated_areas_tsy_tx", "bank_tier2_regression_interest_proxy",
    "row_tsy_tx", "row_tier2_regression_interest_proxy", "fed_tsy_tx", "fed_tsy_coupon_interest_proxy",
    "fed_remit_positive", "effective_mmf_rrp_adjustment_prop",
]


def make_legs(rng: np.random.Generator, tdc: np.ndarray | None = None) -> pd.DataFrame:
    """Raw legs; Treasury operating cash closes C on ``tdc`` when given. No ON RRP route before 2013Q3."""
    n = len(QUARTERS)
    legs = pd.DataFrame({column: rng.normal(0, 40_000, n).round(3) for column in RAW_COLUMNS})
    legs["effective_mmf_rrp_adjustment_prop"] = legs["effective_mmf_rrp_adjustment_prop"].where(
        QUARTERS >= pd.Period("2013Q3"), 0.0)
    before_cash = (legs.us_chartered_tsy_tx + legs.foreign_offices_tsy_tx + legs.affiliated_areas_tsy_tx
                   - legs.bank_tier2_regression_interest_proxy
                   + legs.row_tsy_tx - legs.row_tier2_regression_interest_proxy
                   + legs.fed_tsy_tx - legs.fed_tsy_coupon_interest_proxy + legs.fed_remit_positive
                   + legs.effective_mmf_rrp_adjustment_prop)
    legs["treasury_operating_cash_tx"] = rng.normal(0, 40_000, n).round(3) if tdc is None else before_cash - tdc
    legs["C"] = before_cash - legs["treasury_operating_cash_tx"]
    legs["tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow"] = legs["C"]
    legs.insert(0, "quarter", QUARTERS.astype(str))
    return legs


def make_surplus(values: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({"date": MONTHS.start_time.strftime("%Y-%m-%d"), "value": [f"{v:.8f}" for v in values]})


@pytest.fixture()
def rng() -> np.random.Generator:
    return np.random.default_rng(20261115)


def test_funding_legs_follow_the_published_leg_definitions_and_sum_to_measured_tdc(rng):
    legs = make_legs(rng)
    quarterly, periods = build_comparison(legs, make_surplus(rng.normal(-40_000, 60_000, len(MONTHS))), VINTAGE)
    expected = {
        "banks": legs.us_chartered_tsy_tx + legs.foreign_offices_tsy_tx + legs.affiliated_areas_tsy_tx
        - legs.bank_tier2_regression_interest_proxy,
        "foreign": legs.row_tsy_tx - legs.row_tier2_regression_interest_proxy,
        "fed": legs.fed_tsy_tx - legs.fed_tsy_coupon_interest_proxy + legs.fed_remit_positive,
        "treasury_cash_drawdown": -legs.treasury_operating_cash_tx,
        "mmf_on_rrp": legs.effective_mmf_rrp_adjustment_prop,
    }
    for key, values in expected.items():
        np.testing.assert_allclose(quarterly[key], values, rtol=0, atol=1e-9, err_msg=key)
        assert periods.loc[0, f"{key}_cumulative"] == pytest.approx(values.sum(), abs=1e-6)
    np.testing.assert_allclose(quarterly["tdc"], legs["C"], rtol=0, atol=0)
    assert quarterly["leg_reconciliation_gap"].abs().max() < 1e-6
    assert "ratio" not in " ".join(quarterly.columns)  # a single quarter's deficit can be near zero or negative


def test_surplus_months_reduce_the_deficit_with_their_sign(rng):
    legs = make_legs(rng)
    surplus = np.full(len(MONTHS), -50_000.0)
    april_2026 = MONTHS.get_loc(pd.Period("2026-04", "M"))
    surplus[april_2026] = 215_000.0  # a tax-season surplus month
    quarterly, periods = build_comparison(legs, make_surplus(surplus), VINTAGE)
    row = quarterly.set_index("quarter").loc["2026Q2"]
    assert row["deficit"] == pytest.approx(50_000 - 215_000 + 50_000)  # a quarterly surplus stays negative
    full = periods.set_index("period").loc[f"2002Q1-{VINTAGE.quarter_end}"]
    assert full["deficit_cumulative"] == pytest.approx(-surplus.sum())
    # Counting the surplus month as a deficit would overstate the cumulative deficit by twice its size.
    assert full["deficit_cumulative"] == pytest.approx(50_000 * (len(MONTHS) - 1) - 215_000)
    # A quarter is the sum of its own three calendar months.
    q1 = MONTHS.get_loc(pd.Period("2002-01", "M"))
    assert quarterly.set_index("quarter").loc["2002Q1", "deficit"] == pytest.approx(-surplus[q1:q1 + 3].sum())


def test_a_missing_unparsable_or_short_input_raises_instead_of_truncating(rng):
    legs = make_legs(rng)
    surplus = make_surplus(rng.normal(-40_000, 60_000, len(MONTHS)))
    with pytest.raises(ValueError, match=r"missing months \['2014-08'\]"):
        build_comparison(legs, surplus[surplus["date"] != "2014-08-01"], VINTAGE)
    with pytest.raises(ValueError, match=r"missing months \['2026-06'\]"):
        build_comparison(legs, surplus.iloc[:-1], VINTAGE)
    blank = surplus.copy()
    blank.loc[100, "value"] = "."
    with pytest.raises(ValueError, match="missing or nonnumeric"):
        build_comparison(legs, blank, VINTAGE)
    # Legs that end before the vintage endpoint belong to an earlier vintage.
    with pytest.raises(ValueError, match=r"missing quarters \['2026Q1', '2026Q2'\]"):
        build_comparison(legs.iloc[:-2], surplus, VINTAGE)
    gapped = legs.copy()
    gapped.loc[50, "fed_tsy_tx"] = np.nan
    with pytest.raises(ValueError, match="nonfinite"):
        build_comparison(gapped, surplus, VINTAGE)


def test_legs_that_do_not_reconcile_to_measured_tdc_raise(rng):
    legs = make_legs(rng)
    surplus = make_surplus(rng.normal(-40_000, 60_000, len(MONTHS)))
    noise = legs.copy()
    noise.loc[60, "row_tsy_tx"] += 1e-8  # floating noise inside the regression-leg tolerance
    quarterly, _ = build_comparison(noise, surplus, VINTAGE)
    assert quarterly["leg_reconciliation_gap"].abs().max() == pytest.approx(1e-8, rel=1e-2)
    broken = legs.copy()
    broken.loc[60, "fed_tsy_tx"] += 1.0  # a leg moves while C does not
    with pytest.raises(ValueError, match=r"differ from C by (1\.0|0\.9999)"):
        build_comparison(broken, surplus, VINTAGE)
    relabeled = legs.copy()
    relabeled.loc[10, "tdc_tier2_regression_mmf_rrp_prop_bank_only_ru_flow"] += 5.0
    with pytest.raises(ValueError, match="C differs from"):
        build_comparison(relabeled, surplus, VINTAGE)


def test_period_ratio_is_a_ratio_of_sums_not_an_average_of_quarterly_ratios(rng):
    # Alternate small and large deficits; TDC is one-for-one in small quarters and a tenth in large ones.
    small = np.arange(len(QUARTERS)) % 2 == 0
    deficit = np.where(small, 9_000.0, 990_000.0)
    tdc = np.where(small, 9_000.0, 99_000.0)
    surplus = np.repeat(-deficit / 3, 3)
    quarterly, periods = build_comparison(make_legs(rng, tdc), make_surplus(surplus), VINTAGE)
    np.testing.assert_array_equal(quarterly["deficit"], deficit)
    for row in periods.itertuples():
        block = (QUARTERS >= pd.Period(row.first_quarter)) & (QUARTERS <= pd.Period(row.last_quarter))
        ratio_of_sums = tdc[block].sum() / deficit[block].sum()
        mean_ratio = (tdc[block] / deficit[block]).mean()
        assert row.tdc_to_deficit_ratio == pytest.approx(ratio_of_sums, rel=1e-12), row.period
        assert abs(row.tdc_to_deficit_ratio - mean_ratio) > 0.4, row.period  # the fixture tells them apart


def test_a_period_without_a_cumulative_deficit_has_no_ratio(rng):
    surplus = np.full(len(MONTHS), -10_000.0)
    surplus[(MONTHS >= pd.Period("2020-01", "M")) & (MONTHS <= pd.Period("2021-12", "M"))] = 5_000.0
    with pytest.raises(ValueError, match="2020Q1-2021Q4: cumulative deficit .* not positive"):
        build_comparison(make_legs(rng), make_surplus(surplus), VINTAGE)


def git(root: Path, *args: str) -> None:
    env = {**os.environ, "GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
           "GIT_COMMITTER_NAME": "fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
    subprocess.run(["git", "-C", str(root), *args], check=True, env=env, capture_output=True)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_repo(root: Path, legs: pd.DataFrame, surplus: pd.DataFrame) -> tuple[str, str]:
    """A clean committed checkout with the legs and a fiscus-shaped deficit manifest; returns their hashes."""
    processed = root / "data" / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    legs_path = processed / "tdc_regression_legs_v1.csv"
    legs.to_csv(legs_path, index=False, lineterminator="\n")
    (spec,) = REGISTRY.inputs
    relative = REGISTRY.input_dir / f"{spec.key}.csv"
    (root / relative).parent.mkdir(parents=True, exist_ok=True)
    data = surplus.to_csv(index=False, lineterminator="\n").encode("utf-8")
    (root / relative).write_bytes(data)
    entry = {
        "dataset_id": spec.dataset_id, "argv": list(spec.argv), "file": relative.as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(), "byte_count": len(data), "cache_key": "fixture",
        "retrieved_at_utc": "fixture", "vintage": "fixture", "source_url": "fixture", "source_metadata": {},
        "row_count": len(surplus), "data_coverage": {}, "series_id": spec.series_id,
    }
    manifest = root / REGISTRY.manifest
    manifest.write_text(json.dumps({"schema_version": REGISTRY.schema_version, "inputs": {spec.key: entry}}))
    if not (root / ".git").exists():
        (root / ".gitignore").write_text("data/\n")
        (root / "README.md").write_text("fixture\n")
        git(root, "init", "-q")
        git(root, "add", ".gitignore", "README.md")
        git(root, "commit", "-q", "-m", "fixture")
    return sha(legs_path), sha(manifest)


def export(root: Path, legs_sha: str, manifest_sha: str) -> int:
    return main(["deficit-comparison-export", "--root", str(root), "--legs-sha256", legs_sha,
                 "--inputs-manifest-sha256", manifest_sha, "--vintage", VINTAGE.name])


def test_cli_exports_hash_bound_tables_and_refuses_unbound_inputs(tmp_path, rng):
    legs_sha, manifest_sha = make_repo(tmp_path, make_legs(rng), make_surplus(rng.normal(-40_000, 60_000, len(MONTHS))))
    assert export(tmp_path, legs_sha, manifest_sha) == 0
    processed = tmp_path / "data" / "processed"
    receipt = json.loads((processed / OUTPUT_FILES["receipt"]).read_text())
    for output in receipt["outputs"].values():
        assert sha(tmp_path / output["path"]) == output["sha256"]
        assert (tmp_path / output["path"]).stat().st_size == output["byte_count"]
    head = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], capture_output=True, text=True).stdout
    assert receipt["producer_commit"] == head.strip()
    assert receipt["vintage"] == "2026q2" and receipt["units"] == "USD million"
    assert receipt["inputs"]["regression_legs"]["sha256"] == legs_sha
    assert receipt["deficit_source"]["dataset_id"] == "fred.mtsds133fms"
    assert receipt["deficit_source"]["sha256"] == receipt["inputs"]["fiscus_inputs"][DEFICIT_KEY]["sha256"]
    for phrase in ["differently scoped", "modified cash", "not the share of deficit dollars", "not a retention"]:
        assert phrase in receipt["interpretation"]
    quarterly = pd.read_csv(processed / OUTPUT_FILES["quarterly"])
    periods = pd.read_csv(processed / OUTPUT_FILES["periods"])
    assert set(quarterly.columns) == set(receipt["columns"]["quarterly"])
    assert set(periods.columns) == set(receipt["columns"]["periods"])
    assert len(quarterly) == len(QUARTERS) == receipt["sample"]["n"]

    with pytest.raises(ValueError, match="regression_legs: source hash mismatch"):
        export(tmp_path, "0" * 64, manifest_sha)
    with pytest.raises(ValueError, match="inputs_manifest: source hash mismatch"):
        export(tmp_path, legs_sha, "0" * 64)
    (tmp_path / "README.md").write_text("changed\n")
    with pytest.raises(ValueError, match="clean committed"):
        export(tmp_path, legs_sha, manifest_sha)


def test_periods_come_from_the_single_config_definition(tmp_path, rng, monkeypatch):
    legs_sha, manifest_sha = make_repo(tmp_path, make_legs(rng), make_surplus(rng.normal(-40_000, 60_000, len(MONTHS))))
    periods_path = tmp_path / "data" / "processed" / OUTPUT_FILES["periods"]
    assert export(tmp_path, legs_sha, manifest_sha) == 0
    exported = pd.read_csv(periods_path)
    assert list(zip(exported["first_quarter"], exported["last_quarter"])) == list(deficit_comparison_periods(VINTAGE))
    assert exported["period"].tolist() == ["2002Q1-2026Q2", "2002Q1-2007Q4", "2008Q1-2019Q4", "2020Q1-2021Q4",
                                           "2022Q1-2026Q2"]
    assert exported["n_quarters"].tolist() == [98, 24, 48, 8, 18]
    # An open-ended period closes at the vintage endpoint.
    assert deficit_comparison_periods(MEASUREMENT_VINTAGES["v1"])[-1] == ("2022Q1", "2025Q4")
    # Changing the one config definition changes the export; no other period list exists.
    monkeypatch.setattr(catalog, "DEFICIT_COMPARISON_PERIODS",
                        (ComparisonPeriod("2002Q1", "2003Q4"), ComparisonPeriod("2010Q1", None)))
    assert export(tmp_path, legs_sha, manifest_sha) == 0
    patched = pd.read_csv(periods_path)
    assert patched["period"].tolist() == ["2002Q1-2003Q4", "2010Q1-2026Q2"]
    assert patched["n_quarters"].tolist() == [8, 66]
    monkeypatch.setattr(catalog, "DEFICIT_COMPARISON_PERIODS", (ComparisonPeriod("2002Q1", "2026Q4"),))
    with pytest.raises(ValueError, match="end by 2026Q2"):
        export(tmp_path, legs_sha, manifest_sha)


# Full-window figures from the 2026q2 legs and FRED MTSDS133FMS read 2026-11-15, USD million.
RETAINED_LEGS_SHA256 = "3da1a39412194932415a3000247b9f06ef0e632c6d3c566232fa997ec512ae70"
RETAINED_FULL_WINDOW = {"tdc_cumulative": 12_797_945.6, "deficit_cumulative": 25_748_288.6,
                        "banks_cumulative": 1_548_997.5, "foreign_cumulative": 5_718_595.4,
                        "fed_cumulative": 3_904_479.2, "treasury_cash_drawdown_cumulative": -866_793.0,
                        "mmf_on_rrp_cumulative": 2_492_666.6}
RETAINED_RATIOS = {"2002Q1-2026Q2": 0.49704, "2002Q1-2007Q4": 0.65952, "2008Q1-2019Q4": 0.53048,
                   "2020Q1-2021Q4": 0.85725, "2022Q1-2026Q2": 0.13601}


@pytest.mark.integration
def test_retained_2026q2_inputs_reproduce_the_full_window_comparison():
    root = Path(os.environ.get("TDCEST_DEFICIT_ROOT", ROOT / "data" / "refresh_2026q2"))
    legs_path = root / "data" / "processed" / "tdc_regression_legs_v1.csv"
    receipt_path = root / "data" / "processed" / OUTPUT_FILES["receipt"]
    missing = [str(path) for path in [legs_path, root / REGISTRY.manifest, receipt_path] if not path.exists()]
    if missing:
        pytest.fail(f"integration inputs absent: {missing}")
    assert sha(legs_path) == RETAINED_LEGS_SHA256
    frames, _ = load_fiscus_inputs(root, json.loads((root / REGISTRY.manifest).read_text()), REGISTRY)
    quarterly, periods = build_comparison(pd.read_csv(legs_path), frames[DEFICIT_KEY], VINTAGE)
    rows = periods.set_index("period")
    for column, value in RETAINED_FULL_WINDOW.items():
        assert round(rows.loc["2002Q1-2026Q2", column], 1) == value, column
    assert {period: round(ratio, 5) for period, ratio in rows["tdc_to_deficit_ratio"].items()} == RETAINED_RATIOS
    assert quarterly["leg_reconciliation_gap"].abs().max() < 1e-6
    # The retained export reproduces from this code byte for byte.
    receipt = json.loads(receipt_path.read_text())
    for role, frame in [("quarterly", quarterly), ("periods", periods)]:
        payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
        assert hashlib.sha256(payload).hexdigest() == receipt["outputs"][role]["sha256"], role
