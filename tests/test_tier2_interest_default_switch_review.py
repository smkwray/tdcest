from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.tier2_interest_default_switch_review import (
    build_tier2_interest_default_switch_review,
    render_tier2_interest_default_switch_review,
    write_tier2_interest_default_switch_review,
)


def _candidate() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31"],
            "sector_group": ["bank", "bank"],
            "component_key": ["coupon_accrual", "bill_amortized_discount"],
            "component_anchored_interest_mil": [100.0, 20.0],
            "current_raw_proxy_mil": [130.0, 10.0],
        }
    )


def _window() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "promotion_ready_constraint_window": [True],
            "credit_union_has_documented_fallback_split": [True],
        }
    )


def _pools(*, frn: float = 5.0, tips_comp: float = 10.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2025-12-31"] * 4,
            "quarter_expense_mil": [200.0, 50.0, frn, tips_comp],
            "included_in_coupon_pool": [True, False, False, False],
            "included_in_bill_discount_pool": [False, True, False, False],
            "included_in_frn_pool": [False, False, True, False],
            "included_in_tips_inflation_comp_pool": [False, False, False, True],
        }
    )


def test_build_tier2_interest_default_switch_review_blocks_on_unallocated_components() -> None:
    review = build_tier2_interest_default_switch_review(
        candidate=_candidate(),
        source_window_validation=_window(),
        component_pools=_pools(),
    )

    rows = review.set_index("gate")
    assert rows.loc["source_window_coverage", "status"] == "pass"
    assert rows.loc["credit_union_split_basis", "status"] == "caveat"
    assert rows.loc["frn_interest_allocation", "status"] == "blocker"
    assert rows.loc["tips_inflation_compensation_treatment", "status"] == "blocker"
    assert rows.loc["overall_default_switch_decision", "status"] == "blocker"
    assert "Do not switch live Tier 2 defaults yet" in render_tier2_interest_default_switch_review(review)


def test_build_tier2_interest_default_switch_review_can_be_ready_with_caveats() -> None:
    review = build_tier2_interest_default_switch_review(
        candidate=_candidate(),
        source_window_validation=_window(),
        component_pools=_pools(frn=0.0, tips_comp=0.0),
    )

    rows = review.set_index("gate")
    assert rows.loc["overall_default_switch_decision", "status"] == "ready_with_caveats"


def test_build_tier2_interest_default_switch_review_accepts_tips_exclusion_decision() -> None:
    review = build_tier2_interest_default_switch_review(
        candidate=_candidate(),
        source_window_validation=_window(),
        component_pools=_pools(frn=0.0, tips_comp=10.0),
        tips_treatment_decision=pd.DataFrame(
            {
                "decision_key": ["tips_inflation_compensation_default_treatment"],
                "status": ["accepted_default_exclusion"],
                "default_treatment": ["exclude_from_default_interest_correction_keep_diagnostic"],
            }
        ),
    )

    rows = review.set_index("gate")
    assert rows.loc["tips_inflation_compensation_treatment", "status"] == "caveat"
    assert rows.loc["overall_default_switch_decision", "status"] == "ready_with_caveats"


def test_build_tier2_interest_default_switch_review_passes_frn_specific_weights() -> None:
    candidate = pd.concat(
        [
            _candidate(),
            pd.DataFrame(
                {
                    "date": ["2025-12-31"],
                    "sector_group": ["bank"],
                    "component_key": ["frn_accrued_interest"],
                    "component_anchored_interest_mil": [5.0],
                    "current_raw_proxy_mil": [pd.NA],
                    "allocator_basis": ["wamest_interest_contract_frn_weight"],
                }
            ),
        ],
        ignore_index=True,
    )
    review = build_tier2_interest_default_switch_review(
        candidate=candidate,
        source_window_validation=_window(),
        component_pools=_pools(frn=5.0, tips_comp=0.0),
    )

    rows = review.set_index("gate")
    assert rows.loc["frn_interest_allocation", "status"] == "pass"
    assert rows.loc["frn_interest_allocation", "recommended_action"] == "none"
    assert rows.loc["overall_default_switch_decision", "status"] == "ready_with_caveats"


def test_write_tier2_interest_default_switch_review(tmp_path: Path) -> None:
    candidate_path = tmp_path / "candidate.csv"
    window_path = tmp_path / "window.csv"
    pools_path = tmp_path / "pools.csv"
    out_path = tmp_path / "review.csv"
    md_path = tmp_path / "review.md"
    _candidate().to_csv(candidate_path, index=False)
    _window().to_csv(window_path, index=False)
    _pools().to_csv(pools_path, index=False)

    written_csv, written_md, review = write_tier2_interest_default_switch_review(
        candidate_path=candidate_path,
        source_window_validation_path=window_path,
        component_pools_path=pools_path,
        csv_path=out_path,
        markdown_path=md_path,
    )

    assert written_csv == out_path
    assert written_md == md_path
    assert out_path.exists()
    assert md_path.exists()
    assert not review.empty
