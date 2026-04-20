from __future__ import annotations

import pandas as pd

from tdc_estimator.attribution import (
    build_post2022_bank_only_attribution,
    render_post2022_bank_only_attribution_markdown,
)


def test_build_post2022_bank_only_attribution_tracks_recent_corrections():
    idx = pd.to_datetime(["2022-06-30", "2022-09-30", "2022-12-31"])
    estimates = pd.DataFrame(
        {
            "tdc_base_bank_only_ru_flow": [10.0, 20.0, 30.0],
            "tdc_tier1_fed_corrected_bank_only_ru_flow": [9.0, 16.0, 27.0],
            "tdc_tier2_interest_corrected_bank_only_ru_flow": [8.5, 15.0, 25.0],
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [8.25, 14.5, 24.0],
        },
        index=idx,
    )
    corrections = pd.DataFrame(
        {
            "tier1_fed_coupon_correction": [-1.0, -4.0, -3.0],
            "tier2_bank_coupon_correction": [-0.2, -0.5, -1.5],
            "tier2_row_coupon_correction": [-0.3, -0.5, -0.5],
            "tdc_tier1_bank_only_delta_from_base": [-1.0, -4.0, -3.0],
            "tdc_tier2_bank_only_delta_from_base": [-1.5, -5.0, -5.0],
            "tdc_tier2_bank_only_delta_from_tier1": [-0.5, -1.0, -2.0],
            "tier3_bank_noninterest_outlay_correction": [-0.5, -0.7, -0.8],
            "tier3_row_noninterest_outlay_correction": [-0.1, -0.2, -0.3],
            "tier3_bank_nonborrow_receipt_correction": [0.15, 0.20, 0.25],
            "tier3_row_nonborrow_receipt_correction": [0.05, 0.10, 0.10],
            "tier3_mint_cb_cash_factor_correction": [0.15, 0.20, 0.25],
            "tdc_tier3_bank_only_delta_from_base": [-1.75, -5.5, -6.0],
            "tdc_tier3_bank_only_delta_from_tier2": [-0.25, -0.5, -1.0],
        },
        index=idx,
    )

    attribution = build_post2022_bank_only_attribution(estimates, corrections)

    assert list(attribution.index) == list(pd.to_datetime(["2022-09-30", "2022-12-31"]))
    assert round(attribution.loc[pd.Timestamp("2022-09-30"), "total_coupon_correction"], 6) == -5.0
    assert round(attribution.loc[pd.Timestamp("2022-09-30"), "total_fiscal_correction"], 6) == -0.4
    assert round(attribution.loc[pd.Timestamp("2022-12-31"), "fed_coupon_share_abs_pct"], 6) == 60.0
    assert round(attribution.loc[pd.Timestamp("2022-12-31"), "bank_coupon_share_abs_pct"], 6) == 30.0
    assert round(attribution.loc[pd.Timestamp("2022-12-31"), "row_coupon_share_abs_pct"], 6) == 10.0
    assert attribution.loc[pd.Timestamp("2022-09-30"), "dominant_coupon_correction"] == "fed"
    assert round(attribution.loc[pd.Timestamp("2022-12-31"), "tier3_delta_from_tier2"], 6) == -1.0


def test_render_post2022_bank_only_attribution_markdown_includes_latest_summary():
    idx = pd.to_datetime(["2022-09-30"])
    attribution = pd.DataFrame(
        {
            "tdc_base_bank_only_ru_flow": [20.0],
            "tdc_tier1_fed_corrected_bank_only_ru_flow": [16.0],
            "tdc_tier2_interest_corrected_bank_only_ru_flow": [15.0],
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [14.5],
            "fed_coupon_correction": [-4.0],
            "bank_coupon_correction": [-0.5],
            "row_coupon_correction": [-0.5],
            "total_coupon_correction": [-5.0],
            "total_fiscal_correction": [-0.5],
            "tier3_delta_from_tier2": [-0.5],
            "dominant_coupon_correction": ["fed"],
        },
        index=idx,
    )

    markdown = render_post2022_bank_only_attribution_markdown(attribution)

    assert "# Post-2022 Bank-Only Correction Attribution" in markdown
    assert "Latest quarter: 2022-09-30." in markdown
    assert "| 2022-09-30 | 20.000 | 16.000 | 15.000 | 14.500 | -4.000 | -0.500 | -0.500 | -5.000 | -0.500 | -0.500 | fed |" in markdown
