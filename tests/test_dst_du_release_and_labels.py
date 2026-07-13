"""MUST 4 (transitive manifest validation) and MUST 6 (label locks) tests."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tdc_estimator.dst_du_release_manifest import (
    SCHEMA_VERSION,
    validate_dst_du_release_manifest,
)
from tdc_estimator.nonmarketable_sidecar import (
    CORE_EXCLUSION_LABEL,
    SAVINGS_BOND_LABEL,
    SLGS_LABEL,
    build_nonmarketable_sidecar,
)

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"


def _write_manifest(tmp_path: Path) -> Path:
    processed = tmp_path / "processed"
    raw = tmp_path / "raw"
    processed.mkdir()
    raw.mkdir()
    (processed / "a.csv").write_text("x,y\n1,2\n")
    (raw / "b.csv").write_text("x,y\n3,4\n")
    import hashlib

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "inputs": {"raw/b.csv": hashlib.sha256((raw / "b.csv").read_bytes()).hexdigest()},
        "outputs": {"processed/a.csv": hashlib.sha256((processed / "a.csv").read_bytes()).hexdigest()},
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def test_manifest_validation_passes_then_fails_on_input_mutation(tmp_path):
    manifest_path = _write_manifest(tmp_path)
    validate_dst_du_release_manifest(
        processed_dir=tmp_path / "processed", raw_dir=tmp_path / "raw", manifest_path=manifest_path
    )
    (tmp_path / "raw" / "b.csv").write_text("x,y\n3,5\n")  # mutate a declared INPUT
    with pytest.raises(ValueError, match="inputs:raw/b.csv hash mismatch"):
        validate_dst_du_release_manifest(
            processed_dir=tmp_path / "processed",
            raw_dir=tmp_path / "raw",
            manifest_path=manifest_path,
        )


def test_manifest_validation_fails_on_missing_output(tmp_path):
    manifest_path = _write_manifest(tmp_path)
    (tmp_path / "processed" / "a.csv").unlink()
    with pytest.raises(ValueError, match="outputs:processed/a.csv missing"):
        validate_dst_du_release_manifest(
            processed_dir=tmp_path / "processed",
            raw_dir=tmp_path / "raw",
            manifest_path=manifest_path,
        )


def test_sidecar_labels_are_locked():
    ledger = pd.DataFrame(
        [
            {
                "record_date": "2025-12-31",
                "expense_catg_desc": "INTEREST EXPENSE ON PUBLIC ISSUES",
                "expense_group_desc": "SAVINGS BONDS",
                "expense_type_desc": "Series I",
                "month_expense_amt": 1_000_000_000.0,
            },
            {
                "record_date": "2025-12-31",
                "expense_catg_desc": "INTEREST EXPENSE ON PUBLIC ISSUES",
                "expense_group_desc": "ACCRUED INTEREST EXPENSE",
                "expense_type_desc": "State & Local Government-C/I's, Notes & Bonds",
                "month_expense_amt": 500_000_000.0,
            },
            {
                "record_date": "2025-12-31",
                "expense_catg_desc": "INTEREST EXPENSE ON GOVT ACCOUNT SERIES",
                "expense_group_desc": "CASH BASIS GAS PAYMENTS",
                "expense_type_desc": "GAS",
                "month_expense_amt": 50_000_000_000.0,
            },
        ]
    )
    panel = build_nonmarketable_sidecar(ledger)
    row = panel.iloc[0]
    assert row["savings_bond_label"] == SAVINGS_BOND_LABEL
    assert "no_redemption_bridge" in SAVINGS_BOND_LABEL
    assert row["slgs_label"] == SLGS_LABEL
    assert "not_household_du" in SLGS_LABEL
    assert row["core_exclusion_label"] == CORE_EXCLUSION_LABEL
    assert row["nonmarketable_savings_bond_expense_sidecar_mil"] == 1000.0
    assert row["nonmarketable_slgs_expense_sidecar_mil"] == 500.0


def _live(path_name: str) -> pd.DataFrame:
    path = PROCESSED / path_name
    if not path.exists():
        pytest.skip(f"local artifact absent: {path_name}")
    return pd.read_csv(path)


def test_live_long_history_refuses_pre_2002_and_uses_schema_tiers():
    frame = _live("dst_du_long_history.csv")
    dates = pd.to_datetime(frame["date"])
    assert dates.min() >= pd.Timestamp("2002-01-01"), "pre-2002 numerical values are refused"
    allowed = {
        "certified_modern_component_identity",
        "analysis_component_identity",
        "backcast_bounded_ratio_expense_equivalent",
    }
    assert set(frame["method_tier"].unique()) <= allowed
    assert not [c for c in frame.columns if "cash" in c.lower()]


def test_live_reconciliation_outcome_is_deterministic_and_unrelaxed():
    path = PROCESSED / "dst_du_reconciliation_manifest.json"
    if not path.exists():
        pytest.skip("local reconciliation manifest absent")
    manifest = json.loads(path.read_text())
    assert manifest["outcome"] in {
        "promotable_modern_aggregate",
        "canonical_aggregate_research_sector_split_conditional_on_open_gates",
        "research_tier_canonical_tier2_unchanged",
    }
    assert manifest["gates"]["signed_mean_pct_max"] == 2.0  # never relaxed


def test_live_sector_allocation_carries_honest_labels():
    frame = _live("dst_du_sector_allocation_panel.csv")
    sectors = frame[~frame["sector_key"].str.startswith("dst_du")]
    assert set(sectors["sector_split_label"].unique()) == {
        "model_allocated_aggregate_disciplined"
    }
    mmf = sectors[sectors["sector_key"] == "money_market_funds"]
    if not mmf.empty:
        assert set(mmf["position_basis"].unique()) == {"nmfp_position_anchored"}
