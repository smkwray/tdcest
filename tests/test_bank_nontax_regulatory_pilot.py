from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.bank_nontax_regulatory_pilot import (
    build_bank_nontax_regulatory_pilot,
    render_bank_nontax_regulatory_pilot_markdown,
    write_bank_nontax_regulatory_pilot,
)


def test_build_bank_nontax_regulatory_pilot_buckets_lines() -> None:
    candidates = pd.DataFrame(
        [
            ["2025-09-30", 2025, "bank", "Fines, Penalties, and Forfeitures, Not Otherwise Classified, Office of the Comptroller of Currency, Treasury", 450.488, "B", "bank_nontax_sensitivity"],
            ["2025-09-30", 2025, "bank", "Fees and Assessments, Financial Research Fund, Departmental Offices, Treasury", 103.282, "C", "large_bhc_assessment_sensitivity"],
            ["2025-09-30", 2025, "bank", "Fines, Penalties, and Forfeitures, Not Otherwise Classified, Federal Deposit Insurance Corporation", 153.186, "C", "bank_regulatory_penalty_sensitivity"],
            ["2025-09-30", 2025, "row", "Consular and Border Security Programs, Machine Readable Visa Fee, State", 2487.431, "B", "future_row_pilot"],
        ],
        columns=["date", "fiscal_year", "counterparty_group", "receipt_line_item_nm", "receipt_amt_mil", "payer_grade", "recommended_role"],
    )
    candidates["date"] = pd.to_datetime(candidates["date"])

    pilot = build_bank_nontax_regulatory_pilot(candidates)

    assert set(pilot["pilot_bucket"]) == {
        "occ_candidate",
        "ofr_candidate",
        "fdic_or_other_bank_regulatory_candidate",
    }
    assert "Consular and Border Security Programs, Machine Readable Visa Fee, State" not in set(pilot["receipt_line_item_nm"])
    assert not pilot["default_eligible"].any()


def test_write_bank_nontax_regulatory_pilot_outputs(tmp_path: Path) -> None:
    candidates = pd.DataFrame(
        [
            ["2025-09-30", 2025, "bank", "Interest, Financial Research Fund, Departmental Offices, Treasury", 4.969, "C", "large_bhc_assessment_sensitivity"],
        ],
        columns=["date", "fiscal_year", "counterparty_group", "receipt_line_item_nm", "receipt_amt_mil", "payer_grade", "recommended_role"],
    )
    candidates["date"] = pd.to_datetime(candidates["date"])

    csv_path = tmp_path / "pilot.csv"
    md_path = tmp_path / "pilot.md"
    _, _, pilot = write_bank_nontax_regulatory_pilot(candidates, csv_path=csv_path, markdown_path=md_path)

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(pilot)
    markdown = render_bank_nontax_regulatory_pilot_markdown(pilot)
    assert "Bank Non-Tax Regulatory Pilot" in markdown
    assert "ofr_candidate" in markdown
