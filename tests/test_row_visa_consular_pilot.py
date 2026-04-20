from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.row_visa_consular_pilot import (
    build_row_visa_consular_pilot,
    render_row_visa_consular_pilot_markdown,
    write_row_visa_consular_pilot,
)


def test_build_row_visa_consular_pilot_buckets_lines() -> None:
    candidates = pd.DataFrame(
        [
            ["2025-09-30", 2025, "row", "Consular and Border Security Programs, Machine Readable Visa Fee, State", 2487.431, "B", "future_row_pilot"],
            ["2025-09-30", 2025, "row", "Consular and Border Security Programs, Immigrant Visa Security Surcharge, State", 55.192, "B", "future_row_pilot"],
            ["2025-09-30", 2025, "row", "Immigration Examinations Fee Account, Homeland Security", 7498.102, "C", "row_bridge_mixed"],
            ["2025-09-30", 2025, "row", "Consular and Border Security Programs, Passport Security Surcharge, State", 1783.123, "D", "reject_default_mixed_domestic"],
            ["2025-09-30", 2025, "row", "Interest on Quota in International Monetary Fund (Article V, Section 9), Treasury", 852.408, "C", "row_account_bridge"],
        ],
        columns=["date", "fiscal_year", "counterparty_group", "receipt_line_item_nm", "receipt_amt_mil", "payer_grade", "recommended_role"],
    )
    candidates["date"] = pd.to_datetime(candidates["date"])

    pilot = build_row_visa_consular_pilot(candidates)

    assert set(pilot["pilot_bucket"]) == {
        "mrv_cbsp_primary_candidate",
        "state_visa_secondary_sensitivity",
        "mixed_immigration_or_sponsor_candidate",
        "passport_or_broad_consular_excluded",
    }
    assert "Interest on Quota in International Monetary Fund (Article V, Section 9), Treasury" not in set(pilot["receipt_line_item_nm"])
    assert not pilot["default_eligible"].any()
    mrv = pilot.loc[pilot["pilot_bucket"].eq("mrv_cbsp_primary_candidate")].iloc[0]
    assert mrv["recommended_role"] == "future_row_default_pilot_under_review"
    assert mrv["default_blocker"] == "no_public_debited_account_or_actual_cash_payer_proof"


def test_write_row_visa_consular_pilot_outputs(tmp_path: Path) -> None:
    candidates = pd.DataFrame(
        [
            ["2025-09-30", 2025, "row", "Consular and Border Security Programs, Diversity Visa Lottery Fee, State", 18.706, "B", "future_row_pilot"],
            ["2025-09-30", 2025, "row", "Consular and Border Security Programs, Expedited Passport Fees, State", 346.639, "D", "reject_default_mixed_domestic"],
        ],
        columns=["date", "fiscal_year", "counterparty_group", "receipt_line_item_nm", "receipt_amt_mil", "payer_grade", "recommended_role"],
    )
    candidates["date"] = pd.to_datetime(candidates["date"])

    csv_path = tmp_path / "pilot.csv"
    md_path = tmp_path / "pilot.md"
    _, _, pilot = write_row_visa_consular_pilot(candidates, csv_path=csv_path, markdown_path=md_path)

    assert csv_path.exists()
    assert md_path.exists()
    assert len(pd.read_csv(csv_path)) == len(pilot)
    markdown = render_row_visa_consular_pilot_markdown(pilot)
    assert "ROW Visa And Consular Pilot" in markdown
    assert "mrv_cbsp_primary_candidate" in markdown
