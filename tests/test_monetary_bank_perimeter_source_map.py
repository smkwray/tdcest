from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.monetary_bank_perimeter_source_map import (
    build_monetary_bank_perimeter_source_map,
    render_monetary_bank_perimeter_source_map_markdown,
    write_monetary_bank_perimeter_source_map,
)


def test_build_monetary_bank_perimeter_source_map_lists_candidate_sources() -> None:
    review = pd.DataFrame(
        {
            "has_bank_only_liquid_deposit_subcomponents": [False],
            "has_large_time_or_wholesale_deposit_components": [False],
            "has_credit_union_bridge_side": [True],
            "has_thrift_savings_bridge_side": [False],
            "has_bank_vs_broad_depository_bridge": [False],
            "missing_source_families": [
                "bank_only_liquid_deposit_subcomponents;large_time_or_wholesale_deposit_components;bank_vs_broad_depository_bridge"
            ],
        }
    )

    out = build_monetary_bank_perimeter_source_map(review)
    assert len(out) == 3
    assert "LTDACBM027SBOG" in out["candidate_series_or_product"].tolist()
    assert any("FDIC BankFind Suite quarterly financial data for savings institutions" in text for text in out["candidate_series_or_product"].tolist())
    row = out.loc[out["source_family_key"].eq("bank_vs_broad_depository_bridge")].iloc[0]
    assert row["current_repo_stance"] == "credit_union_side_loaded_fdic_thrift_missing"
    liquid_row = out.loc[out["source_family_key"].eq("bank_only_liquid_deposit_subcomponents")].iloc[0]
    assert liquid_row["current_repo_stance"] == "loaded_broad_context_not_subcomponent"
    assert "ODSACBM027SBOG" in liquid_row["candidate_series_or_product"]


def test_write_monetary_bank_perimeter_source_map_outputs_files(tmp_path: Path) -> None:
    review = pd.DataFrame(
        {
            "has_bank_only_liquid_deposit_subcomponents": [False],
            "has_large_time_or_wholesale_deposit_components": [False],
            "has_credit_union_bridge_side": [False],
            "has_thrift_savings_bridge_side": [False],
            "has_bank_vs_broad_depository_bridge": [False],
            "missing_source_families": [
                "bank_only_liquid_deposit_subcomponents;large_time_or_wholesale_deposit_components;bank_vs_broad_depository_bridge"
            ],
        }
    )

    csv_path = tmp_path / "map.csv"
    md_path = tmp_path / "map.md"
    _, _, source_map = write_monetary_bank_perimeter_source_map(
        monetary_bank_perimeter_gap_review=review,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(source_map)
    markdown = render_monetary_bank_perimeter_source_map_markdown(source_map)
    assert "Monetary Bank Perimeter Source Map" in markdown
    assert "LTDACBM027SBOG" in markdown


def test_build_monetary_bank_perimeter_source_map_marks_loaded_bridge_when_both_sides_present() -> None:
    review = pd.DataFrame(
        {
            "has_bank_only_liquid_deposit_subcomponents": [False],
            "has_large_time_or_wholesale_deposit_components": [True],
            "has_credit_union_bridge_side": [True],
            "has_thrift_savings_bridge_side": [True],
            "has_bank_vs_broad_depository_bridge": [True],
            "missing_source_families": ["bank_only_liquid_deposit_subcomponents"],
        }
    )

    out = build_monetary_bank_perimeter_source_map(review)
    row = out.loc[out["source_family_key"].eq("bank_vs_broad_depository_bridge")].iloc[0]
    assert row["current_repo_stance"] == "bridge_sides_loaded"
    assert bool(row["currently_loaded"])
