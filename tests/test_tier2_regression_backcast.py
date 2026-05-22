from __future__ import annotations

import pandas as pd

from tdc_estimator.tier2_regression_backcast import build_tier2_regression_backcast


def test_tier2_regression_backcast_marks_method_tiers(tmp_path):
    candidate = pd.DataFrame(
        {
            "date": ["2010-06-30", "2022-03-31"],
            "sector_group": ["bank", "bank"],
            "component_anchored_interest_mil": [20.0, 40.0],
        }
    )
    legacy = tmp_path / "legacy.csv"
    pd.DataFrame(
        {
            "date": ["2002-03-31", "2010-06-30", "2022-03-31"],
            "bank_tsy_coupon_interest_proxy": [5.0, 10.0, 30.0],
        }
    ).to_csv(legacy, index=False)

    out = build_tier2_regression_backcast(
        candidate=candidate,
        legacy_proxy_paths={
            "bank_tsy_coupon_interest_proxy": legacy,
            "bank_tsy_bill_discount_interest_proxy": None,
        },
    )

    bank = out.loc[out["sector_group"].eq("bank")].set_index(pd.to_datetime(out.loc[out["sector_group"].eq("bank"), "date"]))
    assert bank.loc[pd.Timestamp("2002-03-31"), "tier2_regression_interest_proxy"] == 10.0
    assert bank.loc[pd.Timestamp("2002-03-31"), "method_tier"] == "pre_component_h15_scaled_backcast"
    assert bank.loc[pd.Timestamp("2010-06-30"), "method_tier"] == "component_pool_wamest_bucket_backcast"
    assert bank.loc[pd.Timestamp("2022-03-31"), "method_tier"] == "constrained_component"
