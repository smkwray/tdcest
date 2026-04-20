from __future__ import annotations

import pandas as pd

from tdc_estimator.tier3_receipt_sensitivity import (
    build_tier3_bank_receipt_upper_bound_sensitivity,
    render_tier3_bank_receipt_upper_bound_sensitivity_markdown,
)


def test_build_tier3_bank_receipt_upper_bound_sensitivity_adds_rcm_candidates_to_default_tier3():
    estimates = pd.DataFrame(
        {
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [100.0, 125.0],
        },
        index=pd.to_datetime(["2025-03-31", "2025-06-30"]),
    )
    receipt_diagnostics = pd.DataFrame(
        {
            "rcm_bank_channel_total_candidate": [300.0, 400.0],
            "rcm_bank_channel_non_tax_candidate": [40.0, 50.0],
        },
        index=pd.to_datetime(["2025-03-31", "2025-06-30"]),
    )

    sensitivity = build_tier3_bank_receipt_upper_bound_sensitivity(
        estimates,
        receipt_diagnostics,
        start="2025-03-31",
    )

    row = sensitivity.loc[pd.Timestamp("2025-06-30")]
    assert round(row["tdc_tier3_fiscal_corrected_bank_only_ru_flow"], 6) == 125.0
    assert round(row["tdc_tier3_bank_only_plus_rcm_bank_channel_total_upper_bound"], 6) == 525.0
    assert round(row["tdc_tier3_bank_only_plus_rcm_bank_channel_non_tax_upper_bound"], 6) == 175.0
    assert round(row["rcm_bank_channel_total_upper_bound_delta"], 6) == 400.0
    assert round(row["rcm_bank_channel_non_tax_upper_bound_delta"], 6) == 50.0


def test_build_tier3_bank_receipt_upper_bound_sensitivity_returns_empty_without_rcm_bank_candidate():
    estimates = pd.DataFrame(
        {
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [100.0],
        },
        index=pd.to_datetime(["2025-06-30"]),
    )
    receipt_diagnostics = pd.DataFrame(
        {
            "fed_earnings_receipts_candidate": [10.0],
        },
        index=pd.to_datetime(["2025-06-30"]),
    )

    sensitivity = build_tier3_bank_receipt_upper_bound_sensitivity(estimates, receipt_diagnostics)

    assert sensitivity.empty


def test_render_tier3_bank_receipt_upper_bound_sensitivity_markdown_includes_upper_bound_language():
    sensitivity = pd.DataFrame(
        {
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [125.0],
            "rcm_bank_channel_total_candidate": [400.0],
            "rcm_bank_channel_non_tax_candidate": [50.0],
            "tdc_tier3_bank_only_plus_rcm_bank_channel_total_upper_bound": [525.0],
            "tdc_tier3_bank_only_plus_rcm_bank_channel_non_tax_upper_bound": [175.0],
        },
        index=pd.to_datetime(["2025-06-30"]),
    )

    markdown = render_tier3_bank_receipt_upper_bound_sensitivity_markdown(sensitivity)

    assert "Tier 3 Bank-Receipt Upper-Bound Sensitivity" in markdown
    assert "Latest source-covered quarter: 2025-06-30." in markdown
    assert "upper-bound total 525.000" in markdown
    assert "routing through banking networks" in markdown
