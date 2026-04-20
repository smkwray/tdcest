from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.bank_occ_timing_sensitivity import (
    build_bank_occ_timing_sensitivity,
    render_bank_occ_timing_sensitivity_markdown,
    write_bank_occ_timing_sensitivity,
)


def test_build_bank_occ_timing_sensitivity_allocates_annual_occ_half_to_q1_and_q3() -> None:
    estimates = pd.DataFrame(
        {
            "tdc_tier3_fiscal_corrected_bank_only_ru_flow": [-10.0, -20.0, -30.0],
        },
        index=pd.to_datetime(["2025-03-31", "2025-06-30", "2025-09-30"]),
    )
    pilot = pd.DataFrame(
        [
            ["2025-09-30", 2025, "Fines, Penalties, and Forfeitures, Not Otherwise Classified, Office of the Comptroller of Currency, Treasury", 450.488, "occ_candidate", False],
            ["2025-09-30", 2025, "Fees and Assessments, Financial Research Fund, Departmental Offices, Treasury", 103.282, "ofr_candidate", False],
        ],
        columns=["date", "fiscal_year", "receipt_line_item_nm", "receipt_amt_mil", "pilot_bucket", "default_eligible"],
    )
    pilot["date"] = pd.to_datetime(pilot["date"])

    out = build_bank_occ_timing_sensitivity(estimates, pilot, start="2025-03-31")

    assert round(float(out.loc[pd.Timestamp("2025-03-31"), "occ_due_date_allocated_receipt_mil"]), 3) == 225.244
    assert round(float(out.loc[pd.Timestamp("2025-09-30"), "occ_due_date_allocated_receipt_mil"]), 3) == 225.244
    assert float(out.loc[pd.Timestamp("2025-06-30"), "occ_due_date_allocated_receipt_mil"]) == 0.0
    assert round(float(out.loc[pd.Timestamp("2025-03-31"), "tdc_tier3_bank_only_plus_occ_timing_sensitivity"]), 3) == 215.244
    assert round(float(out.loc[pd.Timestamp("2025-09-30"), "tdc_tier3_bank_only_occ_timing_delta"]), 3) == 225.244


def test_write_bank_occ_timing_sensitivity_outputs(tmp_path: Path) -> None:
    estimates = pd.DataFrame(
        {"tdc_tier3_fiscal_corrected_bank_only_ru_flow": [-40.0]},
        index=pd.to_datetime(["2025-03-31"]),
    )
    pilot = pd.DataFrame(
        [
            ["2025-09-30", 2025, "Fines, Penalties, and Forfeitures, Not Otherwise Classified, Office of the Comptroller of Currency, Treasury", 450.488, "occ_candidate", False],
        ],
        columns=["date", "fiscal_year", "receipt_line_item_nm", "receipt_amt_mil", "pilot_bucket", "default_eligible"],
    )
    pilot["date"] = pd.to_datetime(pilot["date"])

    csv_path = tmp_path / "occ.csv"
    md_path = tmp_path / "occ.md"
    _, _, sensitivity = write_bank_occ_timing_sensitivity(estimates, pilot, csv_path=csv_path, markdown_path=md_path)

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(sensitivity)
    markdown = render_bank_occ_timing_sensitivity_markdown(sensitivity)
    assert "Bank OCC Timing Sensitivity" in markdown
    assert "March 31 and September 30" in markdown
