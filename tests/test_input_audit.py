from __future__ import annotations

import pandas as pd

from tdc_estimator.input_audit import build_input_audit, render_input_audit_markdown


def test_build_input_audit_flags_possible_x1000_row_coupon_mismatch():
    quarterly = pd.DataFrame(
        {
            "bank_tsy_coupon_interest_proxy": [14.507459],
            "row_tsy_coupon_interest_proxy": [70.346378],
            "bea_row_fed_interest_paid_saar": [285.891],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )
    series_meta = {
        "row_tsy_coupon_interest_proxy": {
            "source_kind": "local_support",
            "raw_filename": "support__row_tsy_coupon_interest_proxy.csv",
        },
        "bank_tsy_coupon_interest_proxy": {
            "source_kind": "local_support",
            "raw_filename": "support__bank_tsy_coupon_interest_proxy.csv",
        },
        "bea_row_fed_interest_paid_saar": {
            "source_kind": "fred",
            "raw_filename": "fred__bea_row_fed_interest_paid_saar.csv",
        },
    }

    audit = build_input_audit(quarterly, series_meta)

    row = audit.loc[audit["series_key"].eq("row_tsy_coupon_interest_proxy")].iloc[0]
    assert row["audit_status"] == "possible_x1000_mismatch"
    assert round(float(row["benchmark_quarterly_millions"]), 3) == 71472.75
    assert round(float(row["ratio_if_x1000"]), 3) == 0.984
    bank = audit.loc[audit["series_key"].eq("bank_tsy_coupon_interest_proxy")].iloc[0]
    assert bank["audit_status"] == "coupled_scale_risk"


def test_render_input_audit_markdown_mentions_provisional_status_when_flagged():
    audit = pd.DataFrame(
        [
            {
                "series_key": "row_tsy_coupon_interest_proxy",
                "series_group": "tier2_coupon",
                "native_frequency": "Quarterly support file",
                "source_unit": "Intended to be millions of U.S. dollars",
                "latest_value": 70.346378,
                "audit_status": "possible_x1000_mismatch",
                "ratio_to_benchmark": 0.000984,
                "ratio_if_x1000": 0.984,
                "benchmark_quarterly_millions": 71472.75,
                "audit_note": "Possible scale mismatch.",
            }
        ]
    )

    markdown = render_input_audit_markdown(audit)

    assert "Input Unit And Frequency Audit" in markdown
    assert "possible_x1000_mismatch" in markdown
    assert "coupled_scale_risk" in markdown
    assert "Tier 2 and Tier 3 numerical magnitudes provisional" in markdown
