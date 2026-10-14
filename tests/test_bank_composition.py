"""Bank balance-sheet composition: fixture economics through the production builders and CLI.

The fixture publishes every S.122.1 line as whole USD million with the published
hierarchy (total financial assets = sum of the asset lines; total currency and
deposits = checkable + time and savings + interbank liabilities) and every H.8
Table 4 line with its parents equal to the sum of their children. Each test reads
what an accounting event or a source defect does to the exported tables.
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

from tdc_estimator.bank_composition import (
    ASSET_CATEGORIES,
    OUTPUT_FILES,
    build_h8_table,
    build_z1_tables,
)
from tdc_estimator.catalog import (
    BANK_COMPOSITION_REGISTRY,
    BANK_H8_BASE_MONTH,
    BANK_H8_LINES,
    BANK_H8_MONTH,
    BANK_Z1_LINES,
)
from tdc_estimator.cli import main
from tdc_estimator.trc_export import load_fiscus_inputs

ROOT = Path(__file__).resolve().parents[1]
QUARTERS = pd.period_range("2001Q4", "2026Q2", freq="Q")
MONTHS = pd.period_range(BANK_H8_BASE_MONTH, BANK_H8_MONTH, freq="M")
ASSET_LINES = [line for line in BANK_Z1_LINES if line.column in ASSET_CATEGORIES]
LEAF_H8 = [line for line in BANK_H8_LINES if not any(other.parent == line.key for other in BANK_H8_LINES)]


def z1_frame(values: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({"date": QUARTERS.end_time.strftime("%Y-%m-%d"),
                         "value": np.asarray(values, dtype=np.int64).astype(str)})


def make_z1(rng: np.random.Generator) -> dict[str, pd.DataFrame]:
    """Integer USD million transactions and levels that obey the S.122.1 hierarchy."""
    n, tx, lv = len(QUARTERS), {}, {}
    for line in ASSET_LINES:
        tx[line.code] = rng.integers(-40_000, 60_000, n)
        lv[line.code] = 500_000 + np.cumsum(tx[line.code]) + rng.integers(-5_000, 5_000, n)  # valuation
    tx["764090005"] = sum(tx[line.code] for line in ASSET_LINES)
    lv["764090005"] = sum(lv[line.code] for line in ASSET_LINES)
    for code in ["763127005", "763130005", "764110005"]:
        tx[code] = rng.integers(-50_000, 90_000, n)
        lv[code] = 3_000_000 + np.cumsum(tx[code])
    tx["764100005"] = tx["763127005"] + tx["763130005"] + tx["764110005"]
    lv["764100005"] = lv["763127005"] + lv["763130005"] + lv["764110005"]
    tx["764190005"] = tx["764100005"] + rng.integers(-20_000, 20_000, n)
    lv["764190005"] = lv["764100005"] + 2_000_000
    frames = {}
    for line in BANK_Z1_LINES:
        frames[f"z1_fu{line.code}"] = z1_frame(tx[line.code])
        frames[f"z1_{line.level_prefix.lower()}{line.code}"] = z1_frame(lv[line.code])
    return frames


def make_h8(rng: np.random.Generator) -> dict[str, pd.DataFrame]:
    """Leaves in units of 0.1 million; parents are exact sums; each line published in its own unit."""
    tenths = {line.key: rng.integers(1_000_000, 30_000_000, len(MONTHS)) for line in LEAF_H8}
    pending = [line for line in BANK_H8_LINES if line.key not in tenths]
    while pending:
        for line in list(pending):
            children = [c.key for c in BANK_H8_LINES if c.parent == line.key]
            if all(child in tenths for child in children):
                tenths[line.key] = sum(tenths[child] for child in children)
                pending.remove(line)
    frames = {}
    for line in BANK_H8_LINES:
        if line.usd_million_per_unit == 1.0:
            text = [f"{v / 10:.1f}" for v in tenths[line.key]]
        else:
            text = [f"{v / 10_000:.4f}" for v in tenths[line.key]]
        frames[f"h8_{line.key}"] = pd.DataFrame({"date": MONTHS.start_time.strftime("%Y-%m-%d"), "value": text})
    return frames


@pytest.fixture()
def frames() -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(20261014)
    return {**make_z1(rng), **make_h8(rng)}


def series(frame: pd.DataFrame) -> pd.Series:
    return pd.Series(pd.to_numeric(frame["value"]).to_numpy(), index=frame["date"])


def test_annual_rows_are_sums_of_quarterly_transactions_and_the_partial_year_is_labeled(frames):
    quarterly, annual, _, stats = build_z1_tables(frames)
    assert quarterly["period"].iloc[0] == "2002Q1" and quarterly["period"].iloc[-1] == "2026Q2"
    assert annual["period"].tolist() == [str(y) for y in range(2002, 2026)] + ["2026H1"]
    assert annual.set_index("period").loc["2026H1", "n_quarters"] == 2
    year = quarterly["period"].str[:4]
    flows = [c for c in quarterly.columns if c != "period"]
    expected = quarterly[flows].groupby(year).sum()
    got = annual.assign(year=annual["period"].str[:4]).set_index("year")[flows]
    pd.testing.assert_frame_equal(got.sort_index(), expected.sort_index(), check_names=False, atol=1e-9, rtol=0)
    # A calendar-year deposit level change telescopes from one fourth-quarter level to the next.
    level = series(frames["z1_fl764100005"])
    assert annual.set_index("period").loc["2025", "deposits_level_change"] == pytest.approx(
        (level["2025-12-31"] - level["2024-12-31"]) / 1000)
    assert stats["quarterly_sample"]["n"] == 98


def test_named_residual_closes_categories_on_total_and_a_double_count_raises(frames):
    quarterly, _, _, stats = build_z1_tables(frames)
    total = quarterly[ASSET_CATEGORIES].sum(axis=1)
    assert (quarterly["total_financial_assets"] - total).abs().max() < 1e-9
    assert stats["closure"]["assets_transactions"]["max_abs_usd_million"] == 0
    # The residual is the sum of the named remaining lines, independent of the total.
    residual_lines = [line.code for line in BANK_Z1_LINES if line.column == "all_other_assets"]
    independent = sum(series(frames[f"z1_fu{code}"]).iloc[1:].to_numpy() for code in residual_lines) / 1000
    np.testing.assert_allclose(quarterly["all_other_assets"].to_numpy(), independent, atol=1e-9)
    # Municipal securities and loans in the municipal column, while bank loans to state and local
    # governments already sit in depository institution loans n.e.c., counts those loans twice.
    doubled = dict(frames)
    muni = series(frames["z1_fu763062005"]).to_numpy() + 2_400
    doubled["z1_fu763062005"] = z1_frame(muni)
    with pytest.raises(ValueError, match="closure gap"):
        build_z1_tables(doubled)
    # Published rounding inside the bound is reported, not hidden.
    rounded = dict(frames)
    rounded["z1_fu764090005"] = z1_frame(series(frames["z1_fu764090005"]).to_numpy() + 3)
    quarterly, _, _, stats = build_z1_tables(rounded)
    assert quarterly["asset_closure_gap"].max() == pytest.approx(0.003)
    assert stats["closure"]["assets_transactions"]["max_abs_usd_million"] == 3


def test_end_quarter_holdings_shares_sum_to_one_and_liabilities_stay_memo(frames):
    _, _, holdings, _ = build_z1_tables(frames)
    categories = holdings[holdings["role"] == "asset_category"]
    assert categories["category"].tolist() == ASSET_CATEGORIES
    assert categories["share_of_total_financial_assets"].sum() == pytest.approx(1.0, abs=1e-12)
    total = holdings.set_index("category").loc["total_financial_assets"]
    assert total["share_of_total_financial_assets"] == 1.0
    assert categories["level_usd_bn"].sum() == pytest.approx(total["level_usd_bn"])
    memo = holdings[holdings["role"] == "memo_liability"]
    assert memo["share_of_total_financial_assets"].isna().all()
    assert (holdings["quarter"] == "2026Q2").all()
    level = series(frames["z1_lm763061100"])
    assert holdings.set_index("category").loc["treasury", "level_usd_bn"] == level["2026-06-30"] / 1000


def test_a_series_ending_before_the_required_period_fails_instead_of_truncating(frames):
    short = dict(frames)
    short["z1_fu763065005"] = frames["z1_fu763065005"].iloc[:-1]
    with pytest.raises(ValueError, match="before the required 2026Q2"):
        build_z1_tables(short)
    short_level = dict(frames)
    short_level["z1_fl764100005"] = frames["z1_fl764100005"].iloc[:-1]
    with pytest.raises(ValueError, match="before the required 2026Q2"):
        build_z1_tables(short_level)
    short_h8 = dict(frames)
    short_h8["h8_ci_loans"] = frames["h8_ci_loans"].iloc[:-1]
    with pytest.raises(ValueError, match="no observation for 2026-09"):
        build_h8_table(short_h8)


def test_missing_or_gapped_values_raise_instead_of_zero_fill(frames):
    blank = dict(frames)
    values = frames["z1_fu763066005"].copy()
    values.loc[40, "value"] = "ND"
    blank["z1_fu763066005"] = values
    with pytest.raises(ValueError, match="missing or nonnumeric"):
        build_z1_tables(blank)
    gapped = dict(frames)
    gapped["z1_fu763066005"] = frames["z1_fu763066005"].drop(index=40)
    with pytest.raises(ValueError, match="missing quarters"):
        build_z1_tables(gapped)


def test_deposit_outcome_is_the_level_change_and_a_series_break_shows_in_the_flow_gap(frames):
    broken = dict(frames)
    level = series(frames["z1_fl764100005"]).to_numpy().copy()
    jump = QUARTERS.get_loc(pd.Period("2014Q3"))
    level[jump:] += 62_635  # reclassification: the level moves with no transaction
    broken["z1_fl764100005"] = z1_frame(level)
    broken["z1_fl763130005"] = z1_frame(series(frames["z1_fl763130005"]).to_numpy() + np.where(
        np.arange(len(QUARTERS)) >= jump, 62_635, 0))
    quarterly, _, _, _ = build_z1_tables(broken)
    row = quarterly.set_index("period").loc["2014Q3"]
    assert row["deposits_flow_level_gap"] == pytest.approx(62.635)
    assert row["deposits_level_change"] == pytest.approx(row["deposits_transactions"] + 62.635)
    others = quarterly.set_index("period").drop(index="2014Q3")["deposits_flow_level_gap"]
    assert (others.abs() < 1e-9).all()
    parts = quarterly[["checkable_deposits", "time_savings_deposits", "interbank_liabilities"]].sum(axis=1)
    np.testing.assert_allclose(parts, quarterly["deposits_transactions"], atol=1e-9)
    tx_total_liabilities = series(frames["z1_fu764190005"]).iloc[1:].to_numpy() / 1000
    np.testing.assert_allclose(quarterly["nondeposit_liabilities"] + quarterly["deposits_transactions"],
                               tx_total_liabilities, atol=1e-9)


def test_h8_twelve_month_change_units_and_hierarchy(frames):
    table, stats = build_h8_table(frames)
    rows = table.set_index("key")
    base, month = f"level_{BANK_H8_BASE_MONTH}_usd_bn", f"level_{BANK_H8_MONTH}_usd_bn"
    np.testing.assert_allclose(rows["change_12m_usd_bn"], rows[month] - rows[base], atol=1e-9)
    # Lines published in USD million are converted to USD billion before they join a parent.
    raw = series(frames["h8_all_other_consumer"])
    assert rows.loc["all_other_consumer", month] == pytest.approx(raw.iloc[-1] / 1000)
    assert rows.loc["other_consumer", month] == pytest.approx(
        rows.loc["auto", month] + rows.loc["all_other_consumer", month])
    assert stats["closure"]["commercial_re"]["children"] == [
        "construction_land", "farmland", "multifamily", "nonfarm_nonresidential"]
    assert table["fred_id"].tolist() == [line.series_id for line in BANK_H8_LINES]
    broken = dict(frames)
    values = frames["h8_multifamily"].copy()
    values.loc[values.index[-1], "value"] = f"{float(values['value'].iloc[-1]) + 0.01:.4f}"
    broken["h8_multifamily"] = values
    with pytest.raises(ValueError, match="commercial_re"):
        build_h8_table(broken)


def git(root: Path, *args: str) -> None:
    env = {**os.environ, "GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
           "GIT_COMMITTER_NAME": "fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}
    subprocess.run(["git", "-C", str(root), *args], check=True, env=env, capture_output=True)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_repo(root: Path, frames: dict[str, pd.DataFrame], z1_package: dict[str, str] | None = None) -> str:
    input_dir = root / BANK_COMPOSITION_REGISTRY.input_dir
    input_dir.mkdir(parents=True, exist_ok=True)
    inputs = {}
    for spec in BANK_COMPOSITION_REGISTRY.inputs:
        relative = BANK_COMPOSITION_REGISTRY.input_dir / f"{spec.key}.csv"
        data = frames[spec.key].to_csv(index=False, lineterminator="\n").encode("utf-8")
        (root / relative).write_bytes(data)
        package = (z1_package or {}).get(spec.key, "a" * 64)
        metadata = {"release_date": "2026-09-11", "package_sha256": package} if spec.key.startswith("z1_") else {}
        inputs[spec.key] = {
            "dataset_id": spec.dataset_id, "argv": list(spec.argv), "file": relative.as_posix(),
            "sha256": hashlib.sha256(data).hexdigest(), "byte_count": len(data), "cache_key": "fixture",
            "retrieved_at_utc": "fixture", "vintage": f"z1-release:2026-09-11|sha256:{package}"
            if spec.key.startswith("z1_") else "fixture", "source_url": "fixture", "source_metadata": metadata,
            "row_count": len(frames[spec.key]), "data_coverage": {}, "series_id": spec.series_id,
        }
    manifest = root / BANK_COMPOSITION_REGISTRY.manifest
    manifest.write_text(json.dumps({"schema_version": BANK_COMPOSITION_REGISTRY.schema_version, "inputs": inputs}))
    if not (root / ".git").exists():
        (root / ".gitignore").write_text("data/\n")
        (root / "README.md").write_text("fixture\n")
        git(root, "init", "-q")
        git(root, "add", ".gitignore", "README.md")
        git(root, "commit", "-q", "-m", "fixture")
    return sha(manifest)


def test_cli_exports_hash_bound_tables_with_labels_and_refuses_unbound_inputs(tmp_path, frames):
    manifest_sha = make_repo(tmp_path, frames)
    assert main(["bank-composition-export", "--root", str(tmp_path), "--inputs-manifest-sha256", manifest_sha]) == 0
    processed = tmp_path / "data" / "processed"
    receipt = json.loads((processed / OUTPUT_FILES["receipt"]).read_text())
    for output in receipt["outputs"].values():
        assert sha(tmp_path / output["path"]) == output["sha256"]
    assert receipt["units"] == "USD billion"
    assert receipt["z1"]["release_date"] == "2026-09-11" and receipt["z1"]["end_quarter"] == "2026Q2"
    labels = " ".join(receipt["labels"])
    for required in ["private-label MBS", "exclude valuation changes", "commercial banks only",
                     "not the exclusive", "first and junior liens"]:
        assert required in labels
    columns = receipt["columns"]
    for role, metadata in [("quarterly", "z1_flows"), ("annual", "z1_flows")]:
        frame = pd.read_csv(processed / OUTPUT_FILES[role])
        assert set(frame.columns) <= set(columns[metadata])
    assert "BOGZ1FU763062000Q" in columns["z1_flows"]["municipal"]["definition"]
    assert "not pure corporate bonds" in columns["z1_flows"]["corporate_foreign_bonds"]["definition"].lower()
    holdings = pd.read_csv(processed / OUTPUT_FILES["holdings"])
    assert set(holdings["category"]) <= set(columns["z1_holdings"])
    h8 = pd.read_csv(processed / OUTPUT_FILES["h8"])
    assert set(h8["key"]) == set(columns["h8"])
    assert {key for key in receipt["coverage"]} == {spec.key for spec in BANK_COMPOSITION_REGISTRY.inputs}

    with pytest.raises(ValueError, match="source hash mismatch"):
        main(["bank-composition-export", "--root", str(tmp_path), "--inputs-manifest-sha256", "0" * 64])
    mixed = make_repo(tmp_path, frames, z1_package={"z1_fu763061100": "b" * 64})
    with pytest.raises(ValueError, match="one release package"):
        main(["bank-composition-export", "--root", str(tmp_path), "--inputs-manifest-sha256", mixed])
    (tmp_path / "README.md").write_text("changed\n")
    with pytest.raises(ValueError, match="clean committed"):
        main(["bank-composition-export", "--root", str(tmp_path), "--inputs-manifest-sha256", manifest_sha])


# Published H.8 release of 2026-10-09, Table 4 (domestically chartered, SA), USD billion.
H8_TABLE4_2026_09 = {"ci_loans": 2328.4, "commercial_re": 3014.2, "multifamily": 621.2, "closed_end_residential": 2407.6,
                     "credit_cards": 1092.8, "auto": 526.9, "all_other_consumer": 307.4, "treasury_agency_mbs": 2659.3,
                     "other_securities_mbs": 82.6, "other_securities_non_mbs": 826.4, "ndfi_loans": 1534.8,
                     "loans_nec": 1167.1, "deposits": 18023.7}


@pytest.mark.integration
def test_real_inputs_close_exactly_and_match_the_published_h8_table():
    root = Path(os.environ.get("TDCEST_BANK_COMPOSITION_ROOT", ROOT))
    manifest_path = root / BANK_COMPOSITION_REGISTRY.manifest
    if not manifest_path.exists():
        pytest.fail(f"integration inputs absent: {manifest_path}")
    frames, records = load_fiscus_inputs(root, json.loads(manifest_path.read_text()), BANK_COMPOSITION_REGISTRY)
    _, _, holdings, stats = build_z1_tables(frames)
    for measure in ["assets_transactions", "assets_levels", "deposits_transactions", "deposits_levels"]:
        assert stats["closure"][measure]["max_abs_usd_million"] == 0, measure
    assert holdings.set_index("category").loc["total_financial_assets", "level_usd_bn"] == pytest.approx(23135.3, abs=0.05)
    table, _ = build_h8_table(frames)
    published = table.set_index("key")[f"level_{BANK_H8_MONTH}_usd_bn"].round(1)
    for key, value in H8_TABLE4_2026_09.items():
        assert published[key] == pytest.approx(value, abs=1e-9), key
