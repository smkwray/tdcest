from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tdc_estimator.catalog import LocalSeries
from tdc_estimator.io import build_quarterly_frame
from tdc_estimator.tier2_component_support_export import (
    assert_component_support_source_window_ready,
    build_tier2_component_support_exports,
    render_tier2_component_support_export_summary,
    write_tier2_component_support_exports,
)
from tdc_estimator.tier2_interest_release_manifest import (
    MANIFEST_FILENAME,
    default_component_release_dates,
)


def _candidate() -> pd.DataFrame:
    rows = []
    for date in default_component_release_dates():
        for sector, value in [("bank", 120.0), ("row", 50.0), ("credit_union", 10.0)]:
            rows.append(
                {
                    "date": date,
                    "sector_group": sector,
                    "component_key": "coupon_accrual",
                    "component_anchored_interest_mil": value,
                }
            )
    return pd.DataFrame(rows)


def _constraints() -> pd.DataFrame:
    rows = []
    for date in default_component_release_dates():
        rows.extend(
            [
                {
                    "date": date,
                    "sector_key": "bank_broad_private_depositories_marketable_proxy",
                    "constraint_status": "usable_level_constraint_wamest_split_fallback",
                    "level_mil": 100.0,
                    "bill_weight_proxy": pd.NA,
                    "coupon_weight_proxy": pd.NA,
                    "fallback_split_accepted": True,
                },
                {
                    "date": date,
                    "sector_key": "credit_unions_marketable_proxy",
                    "constraint_status": "usable_level_constraint_wamest_split_fallback",
                    "level_mil": 10.0,
                    "bill_weight_proxy": pd.NA,
                    "coupon_weight_proxy": pd.NA,
                    "fallback_split_accepted": True,
                },
                {
                    "date": date,
                    "sector_key": "money_market_funds",
                    "constraint_status": "usable_denominator_constraint",
                    "level_mil": 20.0,
                    "bill_weight_proxy": 0.8,
                    "coupon_weight_proxy": 0.2,
                    "fallback_split_accepted": False,
                },
                {
                    "date": date,
                    "sector_key": "foreigners_total",
                    "constraint_status": "usable_level_constraint_wamest_split_fallback",
                    "level_mil": 80.0,
                    "bill_weight_proxy": pd.NA,
                    "coupon_weight_proxy": pd.NA,
                    "fallback_split_accepted": True,
                },
            ]
        )
    return pd.DataFrame(rows)


def test_build_tier2_component_support_exports_sums_components_by_sector() -> None:
    exports = build_tier2_component_support_exports(_candidate())

    bank = exports["bank"]
    row = exports["row"]
    cu = exports["credit_union"]
    assert len(bank) == 16
    assert len(row) == 16
    assert len(cu) == 16
    assert bank.loc[0, "bank_tier2_component_interest_proxy"] == 120.0
    assert row.loc[0, "row_tier2_component_interest_proxy"] == 50.0
    assert cu.loc[0, "credit_union_tier2_component_interest_proxy"] == 10.0
    assert "Promotion rule" in render_tier2_component_support_export_summary(exports)


def test_write_tier2_component_support_exports(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.csv"
    constraints_path = tmp_path / "constraints.csv"
    out_dir = tmp_path / "raw"
    md_path = tmp_path / "support_exports.md"
    _candidate().to_csv(candidate_path, index=False)
    _constraints().to_csv(constraints_path, index=False)

    paths, written_md, exports = write_tier2_component_support_exports(
        candidate_path=candidate_path,
        out_dir=out_dir,
        markdown_path=md_path,
        source_constraints_path=constraints_path,
    )

    assert paths["bank"].exists()
    assert paths["row"].exists()
    assert paths["credit_union"].exists()
    assert (out_dir / MANIFEST_FILENAME).exists()
    assert written_md == md_path
    assert md_path.exists()
    assert exports["bank"].loc[0, "bank_tier2_component_interest_proxy"] == 120.0


def test_component_support_export_blocks_missing_source_window() -> None:
    constraints = _constraints().loc[lambda df: ~df["sector_key"].eq("foreigners_total")].copy()

    with pytest.raises(ValueError, match="source-window validation is not promotion-ready"):
        assert_component_support_source_window_ready(candidate=_candidate(), constraints=constraints)


def test_component_support_export_blocks_truncated_candidate_window() -> None:
    truncated = _candidate().loc[lambda df: ~df["date"].eq(default_component_release_dates()[-1])].copy()

    with pytest.raises(ValueError, match="candidate date window mismatch"):
        assert_component_support_source_window_ready(candidate=truncated, constraints=_constraints())


def test_component_support_export_blocks_bogus_usable_status() -> None:
    constraints = _constraints()
    constraints.loc[0, "constraint_status"] = "usable_nonsense_future_status"

    with pytest.raises(ValueError, match="unexpected usable source statuses"):
        assert_component_support_source_window_ready(candidate=_candidate(), constraints=constraints)


def test_component_support_export_blocks_missing_candidate_sector() -> None:
    candidate = _candidate().loc[lambda df: ~df["sector_group"].eq("bank")].copy()

    with pytest.raises(ValueError, match="candidate missing sector_group=bank"):
        assert_component_support_source_window_ready(candidate=candidate, constraints=_constraints())


def test_component_support_manifest_blocks_tampered_support_file(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.csv"
    constraints_path = tmp_path / "constraints.csv"
    out_dir = tmp_path / "raw"
    md_path = tmp_path / "support_exports.md"
    _candidate().to_csv(candidate_path, index=False)
    _constraints().to_csv(constraints_path, index=False)
    write_tier2_component_support_exports(
        candidate_path=candidate_path,
        out_dir=out_dir,
        markdown_path=md_path,
        source_constraints_path=constraints_path,
    )
    bank_path = out_dir / "support__bank_tier2_component_interest_proxy.csv"
    bank = pd.read_csv(bank_path)
    bank.loc[0, "bank_tier2_component_interest_proxy"] = 0.0
    bank.to_csv(bank_path, index=False)

    with pytest.raises(ValueError, match="hash mismatch"):
        build_quarterly_frame(
            out_dir,
            specs=[],
            local_specs=[
                LocalSeries(
                    key="bank_tier2_component_interest_proxy",
                    description="Bank support",
                    agg="sum",
                )
            ],
        )
