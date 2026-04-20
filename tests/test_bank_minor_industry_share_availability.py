from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.bank_minor_industry_share_availability import (
    build_bank_minor_industry_share_availability,
    render_bank_minor_industry_share_availability_markdown,
    write_bank_minor_industry_share_availability,
)


def test_build_bank_minor_industry_share_availability_flags_latest_bank_rows_unusable() -> None:
    frame = pd.DataFrame(
        {
            "tax_year": [2022, 2022, 2022],
            "industry_key": [
                "commercial_banking",
                "savings_and_other_depository_credit_intermediation",
                "offices_of_bank_holding_companies",
            ],
            "industry_label": [
                "Commercial banking",
                "Savings institutions and other depository credit intermediation",
                "Offices of bank holding companies",
            ],
            "perimeter_type": ["bank_minor_industry", "bank_minor_industry", "bank_holding_minor_industry"],
            "income_subject_to_tax_status": ["suppressed", "suppressed", "suppressed"],
            "total_income_tax_after_credits_status": ["suppressed", "suppressed", "suppressed"],
            "usable_for_bank_only_share": [False, False, False],
        }
    )

    availability = build_bank_minor_industry_share_availability(frame)

    assert availability["required_for_bank_only_share"].all()
    assert not availability["public_bank_only_share_available"].any()
    assert set(availability["review_status"]) == {"not_usable_for_bank_only_default"}


def test_write_bank_minor_industry_share_availability_outputs_markdown(tmp_path: Path) -> None:
    input_path = tmp_path / "availability_raw.csv"
    csv_path = tmp_path / "availability_processed.csv"
    markdown_path = tmp_path / "availability.md"

    pd.DataFrame(
        {
            "tax_year": [2022],
            "industry_key": ["commercial_banking"],
            "industry_label": ["Commercial banking"],
            "perimeter_type": ["bank_minor_industry"],
            "income_subject_to_tax_status": ["suppressed"],
            "total_income_tax_after_credits_status": ["suppressed"],
            "usable_for_bank_only_share": [False],
        }
    ).to_csv(input_path, index=False)

    _, _, processed = write_bank_minor_industry_share_availability(
        input_path=input_path,
        csv_path=csv_path,
        markdown_path=markdown_path,
    )

    assert csv_path.exists()
    assert markdown_path.exists()
    assert len(pd.read_csv(csv_path)) == len(processed)
    markdown = render_bank_minor_industry_share_availability_markdown(processed)
    assert "Bank Minor-Industry Share Availability" in markdown
    assert "Usable bank-only rows: 0 of 1." in markdown
