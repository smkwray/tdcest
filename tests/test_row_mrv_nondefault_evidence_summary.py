from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.row_mrv_nondefault_evidence_summary import (
    build_row_mrv_nondefault_evidence_summary,
    render_row_mrv_nondefault_evidence_summary_markdown,
    write_row_mrv_nondefault_evidence_summary,
)


def _sample_payment() -> pd.DataFrame:
    return pd.DataFrame([{"check_name": "treasury_annual_receipt_line"}])


def _sample_checklist() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"check_name": "a", "status": "complete"},
            {"check_name": "b", "status": "partial"},
            {"check_name": "c", "status": "missing"},
        ]
    )


def _sample_source_map() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_family_key": "cash_treatment_and_retention",
                "currently_loaded": True,
                "current_repo_stance": "stronger_nondefault_cash_route_bundle_loaded",
            },
            {
                "source_family_key": "legal_remitter_or_debited_account_proof",
                "currently_loaded": False,
                "current_repo_stance": "post_level_route_examples_loaded_but_no_global_default_clearing_remitter_source",
            },
            {
                "source_family_key": "observed_quarterly_cash_timing_or_remittance_schedule",
                "currently_loaded": False,
                "current_repo_stance": "cadence_examples_loaded_but_no_quarterly_cash_series",
            },
        ]
    )


def _sample_stop_gate() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "check_name": "overall_stop_decision",
                "status": "stop_at_mrv_nondefault_pilot",
                "metric_value": "legal_remitter_or_debited_account_proof;observed_quarterly_cash_timing_or_remittance_schedule",
            }
        ]
    )


def test_build_row_mrv_nondefault_evidence_summary_collapses_state() -> None:
    frame = build_row_mrv_nondefault_evidence_summary(
        row_mrv_payment_chain_review=_sample_payment(),
        row_mrv_promotion_checklist=_sample_checklist(),
        row_mrv_source_map=_sample_source_map(),
        row_mrv_stop_gate=_sample_stop_gate(),
    )
    row = frame.iloc[0]
    assert row["overall_recommendation"] == "stop_at_mrv_nondefault_pilot"
    assert row["cash_route_state"] == "stronger_nondefault_cash_route_bundle_loaded"


def test_write_row_mrv_nondefault_evidence_summary_outputs(tmp_path: Path) -> None:
    csv_path = tmp_path / "row_mrv_nondefault_evidence_summary.csv"
    markdown_path = tmp_path / "row_mrv_nondefault_evidence_summary.md"

    _, _, frame = write_row_mrv_nondefault_evidence_summary(
        csv_path=csv_path,
        markdown_path=markdown_path,
        row_mrv_payment_chain_review=_sample_payment(),
        row_mrv_promotion_checklist=_sample_checklist(),
        row_mrv_source_map=_sample_source_map(),
        row_mrv_stop_gate=_sample_stop_gate(),
    )

    assert csv_path.exists()
    assert markdown_path.exists()
    assert len(pd.read_csv(csv_path)) == len(frame)
    markdown = render_row_mrv_nondefault_evidence_summary_markdown(frame)
    assert "ROW MRV Nondefault Evidence Summary" in markdown
    assert "stop_at_mrv_nondefault_pilot" in markdown
