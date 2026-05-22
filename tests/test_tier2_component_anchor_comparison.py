from __future__ import annotations

import pandas as pd

from tdc_estimator.tier2_component_anchor_comparison import (
    build_tier2_component_anchor_comparison,
    render_tier2_component_anchor_acceptance_memo,
)


def test_component_anchor_comparison_pairs_live_and_candidate_rows():
    estimates = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "tdc_tier2_h15_intensity_corrected_bank_only_ru_flow": [100.0],
            "tdc_tier2_component_anchored_bank_only_ru_flow": [92.0],
            "tdc_tier2_h15_intensity_corrected_depository_institution_np_cu_ru_flow": [105.0],
            "tdc_tier2_component_anchored_depository_institution_np_cu_ru_flow": [96.0],
        }
    )

    comparison = build_tier2_component_anchor_comparison(estimates)

    assert set(comparison["comparison_key"]) == {"bank_only", "depository_institution_np_cu"}
    bank = comparison.loc[comparison["comparison_key"].eq("bank_only")].iloc[0]
    assert bank["component_minus_legacy_h15_mil"] == -8.0
    assert round(bank["component_minus_legacy_h15_pct_of_abs_legacy_h15"], 6) == -0.08


def test_acceptance_memo_uses_strict_default_decision_when_available():
    comparison = build_tier2_component_anchor_comparison(
        pd.DataFrame(
            {
                "date": ["2025-12-31"],
                "tdc_tier2_h15_intensity_corrected_bank_only_ru_flow": [100.0],
                "tdc_tier2_component_anchored_bank_only_ru_flow": [92.0],
            }
        )
    )
    review = pd.DataFrame({"status": ["pass", "caveat"]})
    decision = pd.DataFrame(
        {
            "gate": ["final_default_decision"],
            "default_decision_status": ["approved_for_default_switch"],
        }
    )

    memo = render_tier2_component_anchor_acceptance_memo(comparison, review, decision)

    assert "Status: `approved_for_default_switch`" in memo
    assert "Component-anchored rows have passed strict default-switch gates" in memo
