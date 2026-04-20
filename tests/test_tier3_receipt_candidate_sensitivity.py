from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.tier3_receipt_candidate_sensitivity import (
    build_tier3_receipt_candidate_sensitivity,
    render_tier3_receipt_candidate_sensitivity_markdown,
    write_tier3_receipt_candidate_sensitivity,
)


def test_build_tier3_receipt_candidate_sensitivity_stacks_bank_and_row_candidates() -> None:
    estimates = pd.DataFrame(
        {"tdc_tier3_fiscal_corrected_bank_only_ru_flow": [100.0, -40.0]},
        index=pd.to_datetime(["2025-09-30", "2025-12-31"]),
    )
    bank_bridge = pd.DataFrame(
        {
            "bank_corp_tax_receipts_gross_strict_depository_mil": [10.0, 12.0],
            "bank_corp_tax_receipts_gross_depository_plus_bhc_mil": [15.0, 18.0],
            "bank_corp_tax_receipts_gross_finance_share_mil": [25.0, 30.0],
            "soi_tax_year_used": [2024, 2024],
            "share_age_eligible_for_default": [True, False],
        },
        index=pd.to_datetime(["2025-09-30", "2025-12-31"]),
    )
    occ = pd.DataFrame(
        {
            "occ_due_date_allocated_receipt_mil": [2.0, 0.0],
            "occ_annual_candidate_source_year": [2025, None],
        },
        index=pd.to_datetime(["2025-09-30", "2025-12-31"]),
    )
    row_state = pd.DataFrame(
        {
            "row_state_visa_allocated_receipt_mil": [5.0, 0.0],
            "state_visa_source_fiscal_year": [2025, None],
        },
        index=pd.to_datetime(["2025-09-30", "2025-12-31"]),
    )

    out = build_tier3_receipt_candidate_sensitivity(
        estimates,
        bank_corp_tax_bridge=bank_bridge,
        bank_occ_timing_sensitivity=occ,
        row_state_visa_timing_sensitivity=row_state,
        start="2025-09-30",
    )

    assert round(float(out.loc[pd.Timestamp("2025-09-30"), "tdc_tier3_bank_only_plus_bank_strict_depository_bridge_and_occ_timing"]), 3) == 112.0
    assert (
        round(float(out.loc[pd.Timestamp("2025-09-30"), "tdc_tier3_bank_only_plus_bank_depository_plus_bhc_occ_and_row_state_visa"]), 3)
        == 122.0
    )
    assert (
        round(
            float(
                out.loc[
                    pd.Timestamp("2025-09-30"),
                    "tdc_tier3_bank_only_plus_bank_finance_upper_benchmark_occ_and_row_state_visa",
                ]
            ),
            3,
        )
        == 132.0
    )
    assert round(float(out.loc[pd.Timestamp("2025-09-30"), "bank_corp_tax_depository_plus_bhc_bridge_policy_eligible_delta_mil"]), 3) == 15.0
    assert round(float(out.loc[pd.Timestamp("2025-12-31"), "tdc_tier3_bank_only_plus_bank_corp_tax_strict_depository_bridge"]), 3) == -28.0
    assert round(float(out.loc[pd.Timestamp("2025-12-31"), "bank_corp_tax_depository_plus_bhc_bridge_policy_eligible_delta_mil"]), 3) == 0.0
    assert (
        round(
            float(out.loc[pd.Timestamp("2025-12-31"), "tdc_tier3_bank_only_plus_policy_eligible_bank_depository_plus_bhc_occ_and_row_state_visa"]),
            3,
        )
        == -40.0
    )


def test_write_tier3_receipt_candidate_sensitivity_outputs(tmp_path: Path) -> None:
    estimates = pd.DataFrame(
        {"tdc_tier3_fiscal_corrected_bank_only_ru_flow": [10.0]},
        index=pd.to_datetime(["2025-12-31"]),
    )
    bank_bridge = pd.DataFrame(
        {
            "bank_corp_tax_receipts_gross_strict_depository_mil": [3.0],
            "bank_corp_tax_receipts_gross_depository_plus_bhc_mil": [4.0],
            "bank_corp_tax_receipts_gross_finance_share_mil": [7.0],
            "share_age_eligible_for_default": [False],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )

    csv_path = tmp_path / "receipt_candidate.csv"
    md_path = tmp_path / "receipt_candidate.md"
    _, _, sensitivity = write_tier3_receipt_candidate_sensitivity(
        estimates,
        bank_corp_tax_bridge=bank_bridge,
        csv_path=csv_path,
        markdown_path=md_path,
        start="2025-12-31",
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(sensitivity)
    markdown = render_tier3_receipt_candidate_sensitivity_markdown(sensitivity)
    assert "Tier 3 Receipt Candidate Sensitivity" in markdown
    assert "bank corporate-tax bridge" in markdown
    assert "Policy-eligible dep+BHC" in markdown
