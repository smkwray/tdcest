from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tdc_estimator.wamest_interest_contract import (
    has_wamest_interest_contract,
    read_available_wamest_interest_contract,
    read_wamest_interest_allocation_weights,
    resolve_wamest_interest_contract_paths,
)


def test_read_wamest_interest_allocation_weights_validates_schema(tmp_path: Path):
    path = tmp_path / "sector_interest_allocation_weights.csv"
    pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "sector_key": ["foreigners_total"],
            "component_key": ["bill_amortized_discount"],
            "central_weight": [0.42],
            "low_weight": [0.35],
            "high_weight": [0.50],
            "weight_basis": ["tic_anchor"],
            "source_family": ["TIC"],
            "observability_tier": ["B"],
        }
    ).to_csv(path, index=False)

    out = read_wamest_interest_allocation_weights(path)

    assert out.loc[0, "sector_key"] == "foreigners_total"
    assert out.loc[0, "date"] == pd.Timestamp("2025-12-31")


def test_read_wamest_interest_allocation_weights_rejects_missing_columns(tmp_path: Path):
    path = tmp_path / "sector_interest_allocation_weights.csv"
    pd.DataFrame({"date": ["2025-12-31"], "sector_key": ["foreigners_total"]}).to_csv(path, index=False)

    with pytest.raises(ValueError, match="missing required WAMEST interest-contract columns"):
        read_wamest_interest_allocation_weights(path)


def test_read_wamest_interest_allocation_weights_rejects_unknown_components(tmp_path: Path):
    path = tmp_path / "sector_interest_allocation_weights.csv"
    pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "sector_key": ["foreigners_total"],
            "component_key": ["mystery_interest"],
            "central_weight": [0.42],
            "low_weight": [0.35],
            "high_weight": [0.50],
            "weight_basis": ["tic_anchor"],
            "source_family": ["TIC"],
            "observability_tier": ["B"],
        }
    ).to_csv(path, index=False)

    with pytest.raises(ValueError, match="unknown WAMEST interest component_key"):
        read_wamest_interest_allocation_weights(path)


def test_resolve_and_read_available_wamest_interest_contract(tmp_path: Path):
    release = tmp_path / "outputs" / "full_coverage_release"
    release.mkdir(parents=True)
    allocation = release / "sector_interest_allocation_weights.csv"
    pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "sector_key": ["bank_us_chartered"],
            "component_key": ["notes_accrued_interest"],
            "central_weight": [0.05],
            "low_weight": [0.03],
            "high_weight": [0.08],
            "weight_basis": ["regulatory_constraint"],
            "source_family": ["FFIEC"],
            "observability_tier": ["C"],
        }
    ).to_csv(allocation, index=False)

    paths = resolve_wamest_interest_contract_paths(tmp_path)
    tables = read_available_wamest_interest_contract(tmp_path)

    assert paths["sector_interest_allocation_weights"] == allocation
    assert tables["sector_interest_allocation_weights"] is not None
    assert tables["sector_component_bucket_weights"] is None
    assert has_wamest_interest_contract(tmp_path)
    assert not has_wamest_interest_contract(tmp_path / "missing")
