from __future__ import annotations

import pandas as pd

from tdc_estimator.tier2_regression_backcast import build_tier2_regression_backcast


def test_tier2_regression_backcast_marks_method_tiers(tmp_path):
    candidate = pd.DataFrame(
        {
            "date": ["2010-06-30", "2022-03-31"],
            "sector_group": ["bank", "bank"],
            "component_anchored_interest_mil": [20.0, 40.0],
            "source_observability_tiers": ["D", "D"],
            "source_families": ["Z1_WAMEST", "Z1_WAMEST"],
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

    assert "evidence_grade" not in bank
    assert bank.loc[pd.Timestamp("2022-03-31"), "method_grade"] == "medium_high"
    assert bank.loc[pd.Timestamp("2022-03-31"), "source_observability_tiers"] == "D"
    assert bank.loc[pd.Timestamp("2010-06-30"), "source_observability_tiers"] == "D"
    assert bank.loc[pd.Timestamp("2002-03-31"), "source_observability_tiers"] == "unreported"


def test_backcast_writer_preserves_source_evidence_in_wide_export(tmp_path):
    from tdc_estimator.tier2_regression_backcast import write_tier2_regression_backcast

    path = tmp_path / "candidate.csv"
    pd.DataFrame({"date": ["2022-03-31"], "sector_group": ["bank"], "component_anchored_interest_mil": [40.],
                  "source_observability_tiers": ["D"], "source_families": ["Z1_WAMEST"],
                  "denominator_observability_tiers": ["A|D"]}).to_csv(path, index=False)
    wide_path = tmp_path / "wide.csv"
    write_tier2_regression_backcast(candidate_path=path, legacy_proxy_paths={}, out_csv_path=tmp_path / "backcast.csv",
                                   out_markdown_path=tmp_path / "summary.md", out_wide_csv_path=wide_path)
    wide = pd.read_csv(wide_path)
    assert wide.loc[0, "bank_method_grade"] == "medium_high"
    assert wide.loc[0, "bank_source_observability_tiers"] == "D"
    assert wide.loc[0, "bank_denominator_observability_tiers"] == "A|D"
