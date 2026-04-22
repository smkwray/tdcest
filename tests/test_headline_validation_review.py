from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.headline_validation_review import (
    build_headline_validation_review,
    render_headline_validation_review_markdown,
    write_headline_validation_review,
)


def test_build_headline_validation_review_prefers_tier1_when_gap_is_coupon_dominated() -> None:
    idx = pd.to_datetime(["2025-09-30", "2025-12-31"])
    estimates = pd.DataFrame(
        {
            "tdc_tier1_fed_corrected_bank_only_ru_flow": [100.0, 120.0],
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [20.0, 30.0],
        },
        index=idx,
    )
    corrections = pd.DataFrame(
        {
            "tier2_bank_coupon_correction": [-10.0, -12.0],
            "tier2_row_coupon_correction": [-68.0, -78.0],
            "tier3_bank_noninterest_outlay_correction": [-1.0, -1.0],
            "tier3_row_noninterest_outlay_correction": [-1.0, -1.0],
            "tier3_bank_nonborrow_receipt_correction": [0.0, 0.0],
            "tier3_row_nonborrow_receipt_correction": [0.0, 0.0],
            "tier3_mint_cb_cash_factor_correction": [0.0, 0.0],
        },
        index=idx,
    )

    review = build_headline_validation_review(estimates, corrections, input_audit=None)

    latest = review.loc[pd.Timestamp("2025-12-31")]
    assert round(float(latest["tier3_minus_tier1_mil"]), 6) == -90.0
    assert round(float(latest["bank_row_coupon_correction_mil"]), 6) == -90.0
    assert round(float(latest["coupon_share_of_abs_gap_pct"]), 6) == 100.0
    assert latest["headline_recommendation"] == "prefer_tier1_headline"
    assert "receipt corrections remain tiny relative to the gap" in latest["headline_reason"]


def test_build_headline_validation_review_prefers_tier1_when_coupon_gate_is_flagged() -> None:
    idx = pd.to_datetime(["2025-12-31"])
    estimates = pd.DataFrame(
        {
            "tdc_tier1_fed_corrected_bank_only_ru_flow": [100.0],
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [80.0],
        },
        index=idx,
    )
    corrections = pd.DataFrame(
        {
            "tier2_bank_coupon_correction": [-10.0],
            "tier2_row_coupon_correction": [-8.0],
            "tier3_bank_noninterest_outlay_correction": [-1.0],
            "tier3_row_noninterest_outlay_correction": [-1.0],
            "tier3_bank_nonborrow_receipt_correction": [0.0],
            "tier3_row_nonborrow_receipt_correction": [0.0],
            "tier3_mint_cb_cash_factor_correction": [0.0],
        },
        index=idx,
    )
    input_audit = pd.DataFrame(
        [
            {"series_key": "row_tsy_coupon_interest_proxy", "audit_status": "possible_x1000_mismatch"},
        ]
    )

    review = build_headline_validation_review(estimates, corrections, input_audit=input_audit)

    latest = review.iloc[0]
    assert bool(latest["coupon_gate_failed"]) is True
    assert latest["headline_recommendation"] == "prefer_tier1_headline"
    assert "scale audit is still flagged" in latest["headline_reason"]


def test_write_headline_validation_review_outputs_files(tmp_path: Path) -> None:
    idx = pd.to_datetime(["2025-12-31"])
    estimates = pd.DataFrame(
        {
            "tdc_tier1_fed_corrected_bank_only_ru_flow": [100.0],
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [80.0],
        },
        index=idx,
    )
    corrections = pd.DataFrame(
        {
            "tier2_bank_coupon_correction": [-10.0],
            "tier2_row_coupon_correction": [-8.0],
            "tier3_bank_noninterest_outlay_correction": [-1.0],
            "tier3_row_noninterest_outlay_correction": [-1.0],
            "tier3_bank_nonborrow_receipt_correction": [0.0],
            "tier3_row_nonborrow_receipt_correction": [0.0],
            "tier3_mint_cb_cash_factor_correction": [0.0],
        },
        index=idx,
    )
    csv_path = tmp_path / "headline_review.csv"
    md_path = tmp_path / "headline_review.md"

    _, _, review = write_headline_validation_review(
        estimates,
        corrections,
        csv_path=csv_path,
        markdown_path=md_path,
        input_audit=None,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(review)
    markdown = render_headline_validation_review_markdown(review)
    assert "Headline Estimate Validation Review" in markdown
