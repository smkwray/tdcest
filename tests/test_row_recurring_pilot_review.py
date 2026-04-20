from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.row_recurring_pilot_review import (
    build_row_recurring_pilot_review,
    render_row_recurring_pilot_review_markdown,
    write_row_recurring_pilot_review,
)


def _sample_pilot() -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {
                "date": "2025-09-30",
                "fiscal_year": 2025,
                "receipt_line_item_nm": "Consular and Border Security Programs, Machine Readable Visa Fee, State",
                "receipt_amt_mil": 2487.431,
                "pilot_bucket": "mrv_cbsp_primary_candidate",
            },
            {
                "date": "2025-09-30",
                "fiscal_year": 2025,
                "receipt_line_item_nm": "Consular and Border Security Programs, Immigrant Visa Security Surcharge, State",
                "receipt_amt_mil": 55.192,
                "pilot_bucket": "state_visa_secondary_sensitivity",
            },
            {
                "date": "2025-09-30",
                "fiscal_year": 2025,
                "receipt_line_item_nm": "Consular and Border Security Programs, Diversity Visa Lottery Fee, State",
                "receipt_amt_mil": 18.706,
                "pilot_bucket": "state_visa_secondary_sensitivity",
            },
        ]
    )
    df["date"] = pd.to_datetime(df["date"])
    return df


def _sample_timing() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "row_state_visa_allocated_receipt_mil": [578.399],
            "row_state_visa_secondary_allocated_receipt_mil": [16.845],
            "row_state_visa_total_allocated_receipt_mil": [595.244],
        },
        index=pd.to_datetime(["2025-09-30"]),
    )


def _sample_readiness() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "check_name": "debited_account_or_legal_remitter",
                "metric_value": "needs_cash_payer_and_debited_account_evidence",
            }
        ]
    )


def test_build_row_recurring_pilot_review_separates_primary_and_secondary_branches() -> None:
    review = build_row_recurring_pilot_review(
        row_visa_consular_pilot=_sample_pilot(),
        row_state_visa_timing_sensitivity=_sample_timing(),
        row_mrv_default_readiness=_sample_readiness(),
    )

    primary = review.loc[review["branch_name"].eq("mrv_cbsp_primary")].iloc[0]
    secondary = review.loc[review["branch_name"].eq("secondary_state_visa")].iloc[0]

    assert primary["promotion_status"] == "future_row_mrv_default_pilot_under_review"
    assert secondary["promotion_status"] == "keep_secondary_visa_nondefault"
    assert round(float(primary["latest_quarter_amount_mil"]), 3) == 578.399
    assert round(float(secondary["latest_quarter_amount_mil"]), 3) == 16.845


def test_write_row_recurring_pilot_review_outputs(tmp_path: Path) -> None:
    csv_path = tmp_path / "row_recurring_pilot_review.csv"
    markdown_path = tmp_path / "row_recurring_pilot_review.md"

    _, _, review = write_row_recurring_pilot_review(
        csv_path=csv_path,
        markdown_path=markdown_path,
        row_visa_consular_pilot=_sample_pilot(),
        row_state_visa_timing_sensitivity=_sample_timing(),
        row_mrv_default_readiness=_sample_readiness(),
    )

    assert csv_path.exists()
    assert markdown_path.exists()
    assert len(pd.read_csv(csv_path)) == len(review)
    markdown = render_row_recurring_pilot_review_markdown(review)
    assert "ROW Recurring Pilot Review" in markdown
    assert "secondary_state_visa" in markdown
