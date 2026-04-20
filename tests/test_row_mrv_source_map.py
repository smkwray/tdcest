from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.row_mrv_source_map import (
    build_row_mrv_source_map,
    render_row_mrv_source_map_markdown,
    write_row_mrv_source_map,
)


def _sample_checklist() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "check_name": "treasury_receipt_account_identification",
                "status": "complete",
                "required_for_default": True,
                "next_evidence_needed": "tighten only if exact sub-account source appears",
            },
            {
                "check_name": "cash_treatment_and_retained_account",
                "status": "partial",
                "required_for_default": True,
                "next_evidence_needed": "find stronger public cash-treatment evidence",
            },
            {
                "check_name": "legal_remitter_or_debited_account",
                "status": "missing",
                "required_for_default": True,
                "next_evidence_needed": "find public remitter or debited-account evidence",
            },
            {
                "check_name": "observed_quarterly_cash_timing",
                "status": "missing",
                "required_for_default": True,
                "next_evidence_needed": "find quarterly cash timing or remittance schedule",
            },
        ]
    )


def test_build_row_mrv_source_map_marks_missing_source_families() -> None:
    source_map = build_row_mrv_source_map(row_mrv_promotion_checklist=_sample_checklist())

    remitter = source_map.loc[source_map["source_family_key"].eq("legal_remitter_or_debited_account_proof")].iloc[0]
    timing = source_map.loc[
        source_map["source_family_key"].eq("observed_quarterly_cash_timing_or_remittance_schedule")
    ].iloc[0]
    account = source_map.loc[source_map["source_family_key"].eq("treasury_state_account_mapping")].iloc[0]

    assert bool(account["currently_loaded"]) is True
    assert bool(remitter["still_missing_for_default"]) is True
    assert bool(timing["still_missing_for_default"]) is True


def test_write_row_mrv_source_map_outputs(tmp_path: Path) -> None:
    csv_path = tmp_path / "row_mrv_source_map.csv"
    markdown_path = tmp_path / "row_mrv_source_map.md"

    _, _, source_map = write_row_mrv_source_map(
        csv_path=csv_path,
        markdown_path=markdown_path,
        row_mrv_promotion_checklist=_sample_checklist(),
    )

    assert csv_path.exists()
    assert markdown_path.exists()
    assert len(pd.read_csv(csv_path)) == len(source_map)
    markdown = render_row_mrv_source_map_markdown(source_map)
    assert "ROW MRV Source Map" in markdown
    assert "legal_remitter_or_debited_account_proof" in markdown
