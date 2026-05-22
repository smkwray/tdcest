from __future__ import annotations

import pandas as pd

from tdc_estimator.fed_component_extension_export import build_fed_component_extension_support


def test_fed_component_extension_sums_bill_and_frn_only():
    fed_components = pd.DataFrame(
        {
            "date": ["2025-12-31"],
            "fed_tsy_coupon_interest_proxy": [25_000.0],
            "fed_tsy_bill_discount_interest_proxy": [440.0],
            "fed_tsy_frn_interest_proxy": [108.0],
            "fed_tsy_tips_coupon_interest_proxy": [760.0],
            "fed_tsy_tips_inflation_comp_proxy": [2_900.0],
        }
    )

    support = build_fed_component_extension_support(fed_components)

    assert support.loc[0, "date"] == "2025-12-31"
    assert support.loc[0, "fed_tier1_component_extension_proxy"] == 548.0
