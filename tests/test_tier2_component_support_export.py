from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.tier2_component_support_export import (
    build_tier2_component_support_exports,
    render_tier2_component_support_export_summary,
    write_tier2_component_support_exports,
)


def _candidate() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31", "2025-12-31"],
            "sector_group": ["bank", "bank", "row"],
            "component_key": ["coupon_accrual", "bill_amortized_discount", "coupon_accrual"],
            "component_anchored_interest_mil": [100.0, 20.0, 50.0],
        }
    )


def test_build_tier2_component_support_exports_sums_components_by_sector() -> None:
    exports = build_tier2_component_support_exports(_candidate())

    bank = exports["bank"]
    row = exports["row"]
    cu = exports["credit_union"]
    assert bank.loc[0, "bank_tier2_component_interest_proxy"] == 120.0
    assert row.loc[0, "row_tier2_component_interest_proxy"] == 50.0
    assert cu.empty
    assert "Promotion rule" in render_tier2_component_support_export_summary(exports)


def test_write_tier2_component_support_exports(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.csv"
    out_dir = tmp_path / "raw"
    md_path = tmp_path / "support_exports.md"
    _candidate().to_csv(candidate_path, index=False)

    paths, written_md, exports = write_tier2_component_support_exports(
        candidate_path=candidate_path,
        out_dir=out_dir,
        markdown_path=md_path,
    )

    assert paths["bank"].exists()
    assert paths["row"].exists()
    assert paths["credit_union"].exists()
    assert written_md == md_path
    assert md_path.exists()
    assert exports["bank"].loc[0, "bank_tier2_component_interest_proxy"] == 120.0
