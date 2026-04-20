from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.row_state_visa_timing_sensitivity import (
    build_row_state_visa_timing_sensitivity,
    render_row_state_visa_timing_sensitivity_markdown,
    write_row_state_visa_timing_sensitivity,
)


def test_build_row_state_visa_timing_sensitivity_keeps_mrv_as_primary_bridge_and_iv_as_secondary(tmp_path: Path) -> None:
    monthly_path = tmp_path / "state__visa_issuances_monthly.csv"
    pd.DataFrame(
        [
            ["2024-10-31", 2025, 100, 40],
            ["2024-11-30", 2025, 300, 60],
            ["2024-12-31", 2025, 600, 100],
            ["2025-01-31", 2025, 1000, 200],
        ],
        columns=["date", "fiscal_year", "niv_issuances_total", "iv_issuances_total"],
    ).to_csv(monthly_path, index=False)

    estimates = pd.DataFrame(
        {"tdc_tier3_fiscal_corrected_bank_only_ru_flow": [1.0, 2.0]},
        index=pd.to_datetime(["2024-12-31", "2025-03-31"]),
    )
    pilot = pd.DataFrame(
        [
            ["2025-09-30", 2025, "Consular and Border Security Programs, Machine Readable Visa Fee, State", 100.0, "mrv_cbsp_primary_candidate", False],
            ["2025-09-30", 2025, "Consular and Border Security Programs, Immigrant Visa Security Surcharge, State", 20.0, "state_visa_secondary_sensitivity", False],
            ["2025-09-30", 2025, "Consular and Border Security Programs, Diversity Visa Lottery Fee, State", 10.0, "state_visa_secondary_sensitivity", False],
        ],
        columns=["date", "fiscal_year", "receipt_line_item_nm", "receipt_amt_mil", "pilot_bucket", "default_eligible"],
    )
    pilot["date"] = pd.to_datetime(pilot["date"])

    out = build_row_state_visa_timing_sensitivity(
        estimates,
        pilot,
        state_visa_monthly_path=monthly_path,
        start="2024-12-31",
    )

    # Q4 2024 uses Oct-Dec allocations over the observed FY total: MRV 5 + 15 + 30, IV 3 + 4.5 + 7.5
    assert round(float(out.loc[pd.Timestamp("2024-12-31"), "state_mrv_cbsp_allocated_mil"]), 3) == 50.0
    assert round(float(out.loc[pd.Timestamp("2024-12-31"), "state_visa_secondary_allocated_mil"]), 3) == 15.0
    assert round(float(out.loc[pd.Timestamp("2024-12-31"), "row_state_visa_allocated_receipt_mil"]), 3) == 50.0
    assert round(float(out.loc[pd.Timestamp("2024-12-31"), "row_state_visa_total_allocated_receipt_mil"]), 3) == 65.0
    # Q1 2025 uses the remaining Jan allocation in this synthetic fixture
    assert round(float(out.loc[pd.Timestamp("2025-03-31"), "row_state_visa_allocated_receipt_mil"]), 3) == 50.0
    assert round(float(out.loc[pd.Timestamp("2025-03-31"), "row_state_visa_secondary_allocated_receipt_mil"]), 3) == 15.0
    assert (out["row_receipt_correction_default_mil"] == 0.0).all()
    assert not out["default_eligible"].any()


def test_write_row_state_visa_timing_sensitivity_outputs(tmp_path: Path) -> None:
    monthly_path = tmp_path / "state__visa_issuances_monthly.csv"
    pd.DataFrame([["2025-01-31", 2025, 10, 2]], columns=["date", "fiscal_year", "niv_issuances_total", "iv_issuances_total"]).to_csv(
        monthly_path, index=False
    )
    estimates = pd.DataFrame(
        {"tdc_tier3_fiscal_corrected_bank_only_ru_flow": [0.0]},
        index=pd.to_datetime(["2025-03-31"]),
    )
    pilot = pd.DataFrame(
        [
            ["2025-09-30", 2025, "Consular and Border Security Programs, Machine Readable Visa Fee, State", 50.0, "mrv_cbsp_primary_candidate", False],
        ],
        columns=["date", "fiscal_year", "receipt_line_item_nm", "receipt_amt_mil", "pilot_bucket", "default_eligible"],
    )
    pilot["date"] = pd.to_datetime(pilot["date"])

    csv_path = tmp_path / "row.csv"
    md_path = tmp_path / "row.md"
    _, _, sensitivity = write_row_state_visa_timing_sensitivity(
        estimates,
        pilot,
        state_visa_monthly_path=monthly_path,
        csv_path=csv_path,
        markdown_path=md_path,
        start="2025-03-31",
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(sensitivity)
    markdown = render_row_state_visa_timing_sensitivity_markdown(sensitivity)
    assert "ROW State MRV / CBSP Timing Bridge" in markdown
    assert "main quarterly ROW delta uses only the Machine Readable Visa / CBSP line" in markdown
