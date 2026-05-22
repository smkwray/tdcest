from __future__ import annotations

import pandas as pd

from tdc_estimator.tier2_component_default_decision import build_tier2_component_default_decision


def test_default_decision_keeps_caveated_candidate_nondefault():
    review = pd.DataFrame(
        {
            "gate": ["source_window_coverage", "frn_interest_allocation", "overall_default_switch_decision"],
            "status": ["pass", "caveat", "ready_with_caveats"],
            "detail": ["ok", "fallback", "ready"],
        }
    )
    comparison = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "comparison_key": ["fed_extension_bank_only"],
            "component_minus_live_mil": [-549.0],
        }
    )

    decision = build_tier2_component_default_decision(
        default_switch_review=review,
        comparison=comparison,
    )

    final = decision.loc[decision["gate"].eq("final_default_decision")].iloc[0]
    frn = decision.loc[decision["gate"].eq("frn_interest_allocation")].iloc[0]
    fed = decision.loc[decision["gate"].eq("fed_bill_frn_extension_scope")].iloc[0]
    assert final["default_decision_status"] == "do_not_switch_default"
    assert frn["default_decision_status"] == "default_blocker"
    assert fed["default_decision_status"] == "accepted_caveat"


def test_default_decision_passes_frn_when_upstream_gate_passes():
    review = pd.DataFrame(
        {
            "gate": ["source_window_coverage", "frn_interest_allocation", "overall_default_switch_decision"],
            "status": ["pass", "pass", "ready_with_caveats"],
            "detail": ["ok", "frn weights", "ready"],
        }
    )
    comparison = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "comparison_key": ["fed_extension_bank_only"],
            "component_minus_live_mil": [-549.0],
        }
    )

    decision = build_tier2_component_default_decision(
        default_switch_review=review,
        comparison=comparison,
    )

    frn = decision.loc[decision["gate"].eq("frn_interest_allocation")].iloc[0]
    assert frn["default_decision_status"] == "pass"


def test_default_decision_accepts_quantified_small_cu_split_sensitivity():
    review = pd.DataFrame(
        {
            "gate": ["credit_union_split_basis", "live_proxy_scale_comparison", "overall_default_switch_decision"],
            "status": ["caveat", "caveat", "ready_with_caveats"],
            "detail": ["cu fallback", "deltas", "ready"],
        }
    )
    comparison = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "comparison_key": ["fed_extension_bank_only"],
            "component_minus_live_mil": [-549.0],
        }
    )
    cu_split = pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31"],
            "component_key": ["bill_amortized_discount", "coupon_accrual"],
            "current_component_anchored_interest_mil": [100.0, 300.0],
            "alternative_component_anchored_interest_mil": [90.0, 311.0],
            "current_cu_bill_share": [0.28, 0.28],
            "alternative_cu_bill_share": [0.26, 0.26],
        }
    )

    decision = build_tier2_component_default_decision(
        default_switch_review=review,
        comparison=comparison,
        cu_split_sensitivity=cu_split,
    )

    cu = decision.loc[decision["gate"].eq("credit_union_split_basis")].iloc[0]
    final = decision.loc[decision["gate"].eq("final_default_decision")].iloc[0]
    assert cu["default_decision_status"] == "accepted_caveat"
    assert "quantified" in cu["decision_detail"]
    assert final["default_decision_status"] == "do_not_switch_default"


def test_default_decision_approves_when_live_delta_acceptance_is_present():
    review = pd.DataFrame(
        {
            "gate": [
                "source_window_coverage",
                "credit_union_split_basis",
                "frn_interest_allocation",
                "tips_inflation_compensation_treatment",
                "live_proxy_scale_comparison",
                "overall_default_switch_decision",
            ],
            "status": ["pass", "caveat", "pass", "caveat", "caveat", "ready_with_caveats"],
            "detail": ["ok", "cu fallback", "frn", "tips", "deltas", "ready"],
        }
    )
    comparison = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "comparison_key": ["fed_extension_bank_only"],
            "component_minus_live_mil": [-549.0],
        }
    )
    cu_split = pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31"],
            "component_key": ["bill_amortized_discount", "coupon_accrual"],
            "current_component_anchored_interest_mil": [100.0, 300.0],
            "alternative_component_anchored_interest_mil": [90.0, 311.0],
            "current_cu_bill_share": [0.28, 0.28],
            "alternative_cu_bill_share": [0.26, 0.26],
        }
    )
    live_delta = pd.DataFrame(
        {
            "sector_group": ["all_selected"],
            "acceptance_status": ["accepted_caveat"],
            "acceptance_basis": ["accepted method delta"],
        }
    )

    decision = build_tier2_component_default_decision(
        default_switch_review=review,
        comparison=comparison,
        cu_split_sensitivity=cu_split,
        live_delta_acceptance=live_delta,
    )

    live = decision.loc[decision["gate"].eq("live_proxy_scale_comparison")].iloc[0]
    final = decision.loc[decision["gate"].eq("final_default_decision")].iloc[0]
    assert live["default_decision_status"] == "accepted_caveat"
    assert final["default_decision_status"] == "approved_for_default_switch"
