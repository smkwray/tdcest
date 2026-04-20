from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.monetary_bank_perimeter_gap_review import (
    build_monetary_bank_perimeter_gap_review,
    render_monetary_bank_perimeter_gap_review_markdown,
    write_monetary_bank_perimeter_gap_review,
)


def test_build_monetary_bank_perimeter_gap_review_requires_new_sources_when_families_missing() -> None:
    quarterly = pd.DataFrame(
        {
            "commercial_bank_deposits": [1.0],
            "small_time_deposits": [1.0],
            "retail_money_market_funds": [1.0],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )
    attribution = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "bank_gap_vs_tier3_mil": [371.0],
            "bank_minus_liquid_target_wedge_mil": [179.0],
            "bank_minus_liquid_share_of_bank_residual": [179.0 / 290.0],
        }
    )

    review = build_monetary_bank_perimeter_gap_review(quarterly, attribution)
    row = review.iloc[0]

    assert row["review_status"] == "new_source_families_required"
    assert row["recommended_next_step"] == "keep_as_perimeter_stress_test"
    assert "bank_only_liquid_deposit_subcomponents" in row["missing_source_families"]
    assert not bool(row["has_credit_union_bridge_side"])
    assert not bool(row["has_thrift_savings_bridge_side"])


def test_write_monetary_bank_perimeter_gap_review_outputs_files(tmp_path: Path) -> None:
    quarterly = pd.DataFrame(
        {
            "commercial_bank_deposits": [1.0],
            "small_time_deposits": [1.0],
            "retail_money_market_funds": [1.0],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )
    attribution = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "bank_gap_vs_tier3_mil": [371.0],
            "bank_minus_liquid_target_wedge_mil": [179.0],
            "bank_minus_liquid_share_of_bank_residual": [179.0 / 290.0],
        }
    )

    csv_path = tmp_path / "review.csv"
    md_path = tmp_path / "review.md"
    _, _, review = write_monetary_bank_perimeter_gap_review(
        quarterly=quarterly,
        monetary_bank_target_gap_attribution=attribution,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(review)
    markdown = render_monetary_bank_perimeter_gap_review_markdown(review)
    assert "Monetary Bank Perimeter Gap Review" in markdown
    assert "new_source_families_required" in markdown
    assert "Credit-union bridge side loaded?" in markdown


def test_build_monetary_bank_perimeter_gap_review_recognizes_loaded_broad_depository_bridge() -> None:
    quarterly = pd.DataFrame(
        {
            "commercial_bank_deposits": [1.0],
            "small_time_deposits": [1.0],
            "retail_money_market_funds": [1.0],
            "credit_union_deposits": [0.9],
            "thrift_deposits": [0.6],
            "large_time_deposits_all_commercial_banks": [0.4],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )
    attribution = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "bank_gap_vs_tier3_mil": [371.0],
            "bank_minus_liquid_target_wedge_mil": [179.0],
            "bank_minus_liquid_share_of_bank_residual": [179.0 / 290.0],
        }
    )
    nonbank_bridge = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "delta_nonbank_depository_bridge_level_mil": [32.0],
            "nonbank_depository_bridge_share_of_bank_minus_liquid_wedge": [32.0 / 179.0],
            "residual_bank_minus_liquid_wedge_after_nonbank_bridge_mil": [147.0],
            "nonbank_bridge_materiality": ["minor_bridge_component"],
        }
    )
    liability_audit = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "loaded_liability_context_total_mil": [80.0],
            "loaded_liability_context_share_of_bank_minus_liquid_wedge": [80.0 / 179.0],
            "residual_bank_minus_liquid_wedge_after_loaded_liability_context_mil": [99.0],
            "loaded_liability_context_materiality": ["meaningful_loaded_context"],
        }
    )

    review = build_monetary_bank_perimeter_gap_review(quarterly, attribution, nonbank_bridge, liability_audit)
    row = review.iloc[0]

    assert bool(row["has_credit_union_bridge_side"])
    assert bool(row["has_thrift_savings_bridge_side"])
    assert bool(row["has_bank_vs_broad_depository_bridge"])
    assert "bank_vs_broad_depository_bridge" not in str(row["missing_source_families"])
    assert row["recommended_next_step"] == "target_bank_only_liquid_subcomponents"
    assert round(float(row["loaded_nonbank_depository_bridge_change_mil"]), 3) == 32.0
    assert round(float(row["loaded_liability_context_total_mil"]), 3) == 80.0
