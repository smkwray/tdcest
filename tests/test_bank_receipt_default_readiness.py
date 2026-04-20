from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.bank_receipt_default_readiness import (
    build_bank_receipt_default_readiness,
    render_bank_receipt_default_readiness_markdown,
    write_bank_receipt_default_readiness,
)


def test_build_bank_receipt_default_readiness_flags_perimeter_and_stale_share_failures() -> None:
    bridge = pd.DataFrame(
        {
            "soi_tax_year_used": [2022],
            "share_status": ["carry_forward_latest"],
            "bank_tax_share_strict_depository": [0.014655],
            "bank_tax_share_depository_plus_bhc": [0.057736],
            "bank_corp_tax_receipts_gross_depository_plus_bhc_mil": [3032.789],
        },
        index=pd.to_datetime(["2026-03-31"]),
    )
    shares = pd.DataFrame(
        {
            "tax_year": [2020, 2021, 2022],
            "strict_depository_share_after_credits": [0.018, 0.016, 0.014655],
            "depository_plus_bhc_share_after_credits": [0.066, 0.061, 0.057736],
        }
    )
    estimates = pd.DataFrame(
        {"tdc_tier3_fiscal_corrected_bank_only_ru_flow": [-40162.529547]},
        index=pd.to_datetime(["2025-12-31"]),
    )

    readiness = build_bank_receipt_default_readiness(
        bank_corp_tax_receipts_bridge=bridge,
        irs_soi_bank_tax_shares=shares,
        bank_minor_industry_availability=None,
        estimates=estimates,
    )

    perimeter = readiness.loc[readiness["check_name"].eq("perimeter_contamination")].iloc[0]
    stale = readiness.loc[readiness["check_name"].eq("stale_share_rule")].iloc[0]
    overlap = readiness.loc[readiness["check_name"].eq("estimator_integration_overlap")].iloc[0]

    assert perimeter["status"] == "pass"
    assert bool(perimeter["passes_for_default"])
    assert stale["status"] == "fail"
    assert overlap["status"] == "warn"
    assert readiness["overall_recommendation"].iloc[0] == "not_yet_promotable"


def test_write_bank_receipt_default_readiness_outputs(tmp_path: Path) -> None:
    csv_path = tmp_path / "readiness.csv"
    md_path = tmp_path / "readiness.md"

    bridge = pd.DataFrame(
        {
            "soi_tax_year_used": [2022],
            "share_status": ["carry_forward_latest"],
            "bank_tax_share_strict_depository": [0.014655],
            "bank_tax_share_depository_plus_bhc": [0.057736],
            "bank_corp_tax_receipts_gross_depository_plus_bhc_mil": [100.0],
        },
        index=pd.to_datetime(["2025-12-31"]),
    )
    shares = pd.DataFrame(
        {
            "tax_year": [2021, 2022],
            "strict_depository_share_after_credits": [0.016, 0.014655],
            "depository_plus_bhc_share_after_credits": [0.061, 0.057736],
        }
    )
    estimates = pd.DataFrame(
        {"tdc_tier3_fiscal_corrected_bank_only_ru_flow": [0.0]},
        index=pd.to_datetime(["2025-12-31"]),
    )

    _, _, readiness = write_bank_receipt_default_readiness(
        csv_path=csv_path,
        markdown_path=md_path,
        bank_corp_tax_receipts_bridge=bridge,
        irs_soi_bank_tax_shares=shares,
        bank_minor_industry_availability=None,
        estimates=estimates,
    )

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(readiness)
    markdown = render_bank_receipt_default_readiness_markdown(readiness)
    assert "Bank Receipt Default Readiness" in markdown
    assert "perimeter_contamination" in markdown


def test_build_bank_receipt_default_readiness_uses_minor_industry_availability_evidence() -> None:
    bridge = pd.DataFrame(
        {
            "soi_tax_year_used": [2022],
            "share_status": ["carry_forward_latest"],
            "bank_tax_share_strict_depository": [0.014655],
            "bank_tax_share_depository_plus_bhc": [0.057736],
            "bank_corp_tax_receipts_gross_depository_plus_bhc_mil": [100.0],
        },
        index=pd.to_datetime(["2026-03-31"]),
    )
    shares = pd.DataFrame(
        {
            "tax_year": [2022],
            "strict_depository_share_after_credits": [0.014655],
            "depository_plus_bhc_share_after_credits": [0.057736],
        }
    )
    availability = pd.DataFrame(
        {
            "tax_year": [2022, 2022, 2022],
            "industry_key": [
                "commercial_banking",
                "savings_and_other_depository_credit_intermediation",
                "offices_of_bank_holding_companies",
            ],
            "perimeter_type": ["bank_minor_industry", "bank_minor_industry", "bank_holding_minor_industry"],
            "income_subject_to_tax_status": ["suppressed", "suppressed", "suppressed"],
            "total_income_tax_after_credits_status": ["suppressed", "suppressed", "suppressed"],
        }
    )
    estimates = pd.DataFrame(
        {"tdc_tier3_fiscal_corrected_bank_only_ru_flow": [0.0]},
        index=pd.to_datetime(["2025-12-31"]),
    )

    readiness = build_bank_receipt_default_readiness(
        bank_corp_tax_receipts_bridge=bridge,
        irs_soi_bank_tax_shares=shares,
        bank_minor_industry_availability=availability,
        estimates=estimates,
    )

    perimeter = readiness.loc[readiness["check_name"].eq("perimeter_contamination")].iloc[0]
    assert "commercial_banking=suppressed/suppressed" in perimeter["metric_value"]
    assert "Latest public Publication 16 Table 5.3 bank-like rows" in perimeter["details"]
