from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.tier2_tips_treatment_decision import (
    build_tier2_tips_treatment_decision,
    render_tier2_tips_treatment_decision,
    write_tier2_tips_treatment_decision,
)


def _pools() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31"],
            "quarter_expense_mil": [100.0, 25.0],
            "component_key": ["tips_accrued_interest", "tips_inflation_compensation"],
            "included_in_coupon_pool": [True, False],
            "included_in_tips_inflation_comp_pool": [False, True],
        }
    )


def test_build_tier2_tips_treatment_decision_excludes_inflation_compensation() -> None:
    out = build_tier2_tips_treatment_decision(_pools())

    rows = out.set_index("decision_key")
    assert rows.loc["tips_coupon_accrual_default_treatment", "default_treatment"] == "include_in_coupon_accrual_pool"
    assert (
        rows.loc["tips_inflation_compensation_default_treatment", "default_treatment"]
        == "exclude_from_default_interest_correction_keep_diagnostic"
    )
    assert rows.loc["tips_coupon_accrual_default_treatment", "latest_component_amount_mil"] == 100.0
    assert rows.loc["tips_inflation_compensation_default_treatment", "latest_component_amount_mil"] == 25.0
    assert "Bottom line" in render_tier2_tips_treatment_decision(out)


def test_write_tier2_tips_treatment_decision(tmp_path: Path) -> None:
    pools_path = tmp_path / "pools.csv"
    csv_path = tmp_path / "tips_decision.csv"
    md_path = tmp_path / "tips_decision.md"
    _pools().to_csv(pools_path, index=False)

    written_csv, written_md, decision = write_tier2_tips_treatment_decision(
        component_pools_path=pools_path,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert written_csv == csv_path
    assert written_md == md_path
    assert csv_path.exists()
    assert md_path.exists()
    assert len(decision) == 2
