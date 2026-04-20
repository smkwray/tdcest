from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.tier3_historical_bank_receipt_research import (
    build_tier3_historical_bank_receipt_research,
    render_tier3_historical_bank_receipt_research_markdown,
    write_tier3_historical_bank_receipt_research,
)


def test_build_tier3_historical_bank_receipt_research_uses_only_age_eligible_quarters() -> None:
    estimates = pd.DataFrame(
        {"tdc_tier3_fiscal_corrected_bank_only_ru_flow": [100.0, 200.0, 300.0]},
        index=pd.to_datetime(["2024-09-30", "2024-12-31", "2025-03-31"]),
    )
    historical = pd.DataFrame(
        {
            "quarter_end": pd.to_datetime(["2024-09-30", "2024-12-31", "2025-03-31"]),
            "share_age_eligible_for_default": [True, True, False],
            "age_eligible_default_candidate_mil": [8.0, 10.0, 0.0],
            "age_eligible_lower_bound_candidate_mil": [2.0, 3.0, 0.0],
            "historical_window_status": [
                "historical_age_eligible_window",
                "historical_age_eligible_window",
                "stale_share_nondefault_window",
            ],
            "promotion_readiness_label": [
                "historical_default_candidate_under_current_policy",
                "historical_default_candidate_under_current_policy",
                "bridge_only_share_too_stale",
            ],
            "recommended_historical_variant": ["depository_plus_bhc", "depository_plus_bhc", "depository_plus_bhc"],
        }
    )

    out = build_tier3_historical_bank_receipt_research(
        estimates,
        bank_receipt_historical_promotion=historical,
        start="2024-09-30",
    )

    assert list(out.index) == list(pd.to_datetime(["2024-09-30", "2024-12-31"]))
    assert float(out.loc[pd.Timestamp("2024-09-30"), "tdc_tier3_bank_only_plus_historical_bank_receipt_candidate"]) == 108.0
    assert float(out.loc[pd.Timestamp("2024-12-31"), "tdc_tier3_bank_only_plus_historical_bank_receipt_candidate"]) == 210.0


def test_write_tier3_historical_bank_receipt_research_outputs_files(tmp_path: Path) -> None:
    estimates = pd.DataFrame(
        {"tdc_tier3_fiscal_corrected_bank_only_ru_flow": [100.0]},
        index=pd.to_datetime(["2024-12-31"]),
    )
    historical = pd.DataFrame(
        {
            "quarter_end": pd.to_datetime(["2024-12-31"]),
            "share_age_eligible_for_default": [True],
            "age_eligible_default_candidate_mil": [10.0],
            "age_eligible_lower_bound_candidate_mil": [3.0],
            "historical_window_status": ["historical_age_eligible_window"],
            "promotion_readiness_label": ["historical_default_candidate_under_current_policy"],
            "recommended_historical_variant": ["depository_plus_bhc"],
        }
    )
    csv_path = tmp_path / "historical_research.csv"
    md_path = tmp_path / "historical_research.md"

    _, _, research = write_tier3_historical_bank_receipt_research(
        estimates,
        bank_receipt_historical_promotion=historical,
        csv_path=csv_path,
        markdown_path=md_path,
        start="2024-12-31",
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(research)
    markdown = render_tier3_historical_bank_receipt_research_markdown(research)
    assert "Tier 3 Historical Bank Receipt Research Surface" in markdown
    assert "Latest historical age-eligible quarter" in markdown
