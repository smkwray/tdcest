from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.interest_source_window_validation import (
    build_interest_source_window_validation,
    summarize_interest_source_window_validation,
    write_interest_source_window_validation,
)


def test_build_interest_source_window_validation_flags_missing_regulatory_window():
    candidate = pd.DataFrame({"date": ["2025-09-30", "2025-12-31"]})
    constraints = pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31", "2025-09-30", "2025-12-31"],
            "sector_key": [
                "bank_broad_private_depositories_marketable_proxy",
                "credit_unions_marketable_proxy",
                "money_market_funds",
                "foreigners_total",
            ],
            "constraint_status": ["usable_constraint"] * 4,
            "bill_weight_proxy": [0.1, None, 0.5, 0.2],
            "coupon_weight_proxy": [0.9, None, 0.5, 0.8],
        }
    )

    out = build_interest_source_window_validation(candidate=candidate, constraints=constraints)

    rows = out.set_index("date")
    assert not rows.loc[pd.Timestamp("2025-09-30"), "bank_has_constraint"]
    assert rows.loc[pd.Timestamp("2025-12-31"), "bank_has_constraint"]
    assert not rows.loc[pd.Timestamp("2025-12-31"), "credit_union_has_constraint"]
    assert not out["promotion_ready_constraint_window"].any()
    assert "Promotion-ready" in summarize_interest_source_window_validation(out)


def test_write_interest_source_window_validation(tmp_path: Path):
    candidate_path = tmp_path / "candidate.csv"
    constraints_path = tmp_path / "constraints.csv"
    out_path = tmp_path / "validation.csv"
    md_path = tmp_path / "validation.md"
    pd.DataFrame({"date": ["2025-12-31"]}).to_csv(candidate_path, index=False)
    pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "sector_key": ["foreigners_total"],
            "constraint_status": ["usable_constraint"],
            "bill_weight_proxy": [0.2],
            "coupon_weight_proxy": [0.8],
        }
    ).to_csv(constraints_path, index=False)

    written_csv, written_md, frame = write_interest_source_window_validation(
        candidate_path=candidate_path,
        constraints_path=constraints_path,
        out_path=out_path,
        markdown_out_path=md_path,
    )

    assert written_csv == out_path
    assert written_md == md_path
    assert out_path.exists()
    assert md_path.exists()
    assert len(frame) == 1


def test_build_interest_source_window_validation_accepts_documented_fallback_split():
    candidate = pd.DataFrame({"date": ["2025-12-31"]})
    constraints = pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31", "2025-12-31", "2025-12-31"],
            "sector_key": [
                "bank_broad_private_depositories_marketable_proxy",
                "credit_unions_marketable_proxy",
                "money_market_funds",
                "foreigners_total",
            ],
            "constraint_status": [
                "usable_constraint",
                "usable_level_constraint_wamest_split_fallback",
                "usable_constraint",
                "usable_constraint",
            ],
            "bill_weight_proxy": [0.1, None, 0.5, 0.2],
            "coupon_weight_proxy": [0.9, None, 0.5, 0.8],
            "fallback_split_accepted": [False, True, False, False],
        }
    )

    out = build_interest_source_window_validation(candidate=candidate, constraints=constraints)

    assert out.loc[0, "credit_union_has_documented_fallback_split"]
    assert out.loc[0, "credit_union_has_constraint"]
    assert out.loc[0, "promotion_ready_constraint_window"]
