from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.bank_receipt_historical_promotion import (
    build_bank_receipt_historical_promotion,
    render_bank_receipt_historical_promotion_markdown,
    write_bank_receipt_historical_promotion,
)


def test_build_bank_receipt_historical_promotion_splits_eligible_and_stale_quarters() -> None:
    bridge = pd.DataFrame(
        {
            "soi_tax_year_used": [2022, 2022],
            "share_status": ["carry_forward_latest", "carry_forward_latest"],
            "stale_share_years": [2, 4],
            "share_age_eligible_for_default": [True, False],
            "bank_corp_tax_receipts_gross_strict_depository_mil": [1763.75, 769.815],
            "bank_corp_tax_receipts_gross_depository_plus_bhc_mil": [6948.526, 3032.789],
            "bank_corp_tax_receipts_gross_finance_share_mil": [17294.0, 7548.179],
        },
        index=pd.to_datetime(["2024-12-31", "2026-03-31"]),
    )

    review = build_bank_receipt_historical_promotion(bank_corp_tax_receipts_bridge=bridge)

    eligible = review.loc[review["quarter_end"].eq(pd.Timestamp("2024-12-31"))].iloc[0]
    stale = review.loc[review["quarter_end"].eq(pd.Timestamp("2026-03-31"))].iloc[0]

    assert eligible["historical_window_status"] == "historical_age_eligible_window"
    assert eligible["promotion_readiness_label"] == "historical_default_candidate_under_current_policy"
    assert float(eligible["age_eligible_default_candidate_mil"]) == 6948.526
    assert stale["historical_window_status"] == "stale_share_nondefault_window"
    assert stale["promotion_readiness_label"] == "bridge_only_share_too_stale"
    assert float(stale["age_eligible_default_candidate_mil"]) == 0.0


def test_write_bank_receipt_historical_promotion_outputs_files(tmp_path: Path) -> None:
    csv_path = tmp_path / "historical.csv"
    markdown_path = tmp_path / "historical.md"
    bridge = pd.DataFrame(
        {
            "soi_tax_year_used": [2022],
            "share_status": ["carry_forward_latest"],
            "stale_share_years": [2],
            "share_age_eligible_for_default": [True],
            "bank_corp_tax_receipts_gross_strict_depository_mil": [100.0],
            "bank_corp_tax_receipts_gross_depository_plus_bhc_mil": [300.0],
            "bank_corp_tax_receipts_gross_finance_share_mil": [700.0],
        },
        index=pd.to_datetime(["2024-12-31"]),
    )

    _, _, review = write_bank_receipt_historical_promotion(
        csv_path=csv_path,
        markdown_path=markdown_path,
        bank_corp_tax_receipts_bridge=bridge,
    )

    assert csv_path.exists()
    assert markdown_path.exists()
    assert len(pd.read_csv(csv_path)) == len(review)
    markdown = render_bank_receipt_historical_promotion_markdown(review)
    assert "Bank Receipt Historical Promotion Review" in markdown
    assert "Latest age-eligible historical quarter" in markdown
