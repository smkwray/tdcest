from __future__ import annotations

import pandas as pd

from tdc_estimator.tier2_component_delta_attribution import build_tier2_component_delta_attribution


def test_delta_attribution_treats_missing_current_proxy_as_zero_for_new_components():
    candidate = pd.DataFrame(
        {
            "date": ["2025-12-31", "2025-12-31"],
            "sector_group": ["bank", "bank"],
            "component_key": ["coupon_accrual", "frn_accrued_interest"],
            "component_anchored_interest_mil": [80.0, 20.0],
            "current_raw_proxy_mil": [100.0, pd.NA],
            "allocator_basis": ["coupon", "frn_fallback"],
        }
    )

    out = build_tier2_component_delta_attribution(candidate)

    frn = out.loc[out["component_key"].eq("frn_accrued_interest")].iloc[0]
    total = out.loc[out["component_key"].eq("sector_total")].iloc[0]
    assert frn["current_proxy_comparable_mil"] == 0.0
    assert frn["component_minus_current_mil"] == 20.0
    assert total["component_minus_current_mil"] == 0.0
