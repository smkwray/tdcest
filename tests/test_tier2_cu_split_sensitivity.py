from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.tier2_cu_split_sensitivity import (
    build_tier2_cu_split_sensitivity,
    summarize_tier2_cu_split_sensitivity,
    write_tier2_cu_split_sensitivity,
)


def _candidate() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31", "2025-12-31"],
            "sector_group": ["credit_union", "credit_union", "bank"],
            "component_key": ["bill_amortized_discount", "coupon_accrual", "bill_amortized_discount"],
            "selected_raw_weight_mil": [20.0, 80.0, 900.0],
            "denominator_raw_weight_mil": [1000.0, 2000.0, 1000.0],
            "allocation_pool_mil": [5000.0, 8000.0, 5000.0],
            "component_anchored_interest_mil": [100.0, 320.0, 4500.0],
        }
    )


def _ncua() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "total_treasuries_level_proxy": [100_000_000_000.0],
            "investment_short_share_le_1y": [0.30],
        }
    )


def test_build_tier2_cu_split_sensitivity_recomputes_only_cu_coupon_and_bill() -> None:
    out = build_tier2_cu_split_sensitivity(candidate=_candidate(), ncua_constraints=_ncua())

    assert set(out["component_key"]) == {"bill_amortized_discount", "coupon_accrual"}
    bill = out.set_index("component_key").loc["bill_amortized_discount"]
    coupon = out.set_index("component_key").loc["coupon_accrual"]
    assert bill["current_cu_bill_share"] == 0.2
    assert bill["alternative_cu_bill_share"] == 0.3
    assert bill["alternative_selected_raw_weight_mil"] == 30.0
    assert coupon["alternative_selected_raw_weight_mil"] == 70.0
    assert round(float(bill["alternative_component_anchored_interest_mil"]), 6) == round(5000.0 * 30.0 / 1010.0, 6)
    assert out["sensitivity_status"].eq("sensitivity_not_default").all()


def test_write_tier2_cu_split_sensitivity(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.csv"
    ncua_path = tmp_path / "ncua.csv"
    out_csv = tmp_path / "cu_split.csv"
    out_md = tmp_path / "cu_split.md"
    _candidate().to_csv(candidate_path, index=False)
    _ncua().to_csv(ncua_path, index=False)

    written_csv, written_md, frame = write_tier2_cu_split_sensitivity(
        candidate_path=candidate_path,
        ncua_constraints_path=ncua_path,
        out_csv_path=out_csv,
        out_markdown_path=out_md,
    )

    assert written_csv == out_csv
    assert written_md == out_md
    assert len(frame) == 2
    assert "NCUA broad-ladder alternative" in out_md.read_text(encoding="utf-8")
    assert "not promoted to default" in summarize_tier2_cu_split_sensitivity(frame)
