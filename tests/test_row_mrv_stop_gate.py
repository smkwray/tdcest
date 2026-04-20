from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.row_mrv_stop_gate import (
    build_row_mrv_stop_gate,
    render_row_mrv_stop_gate_markdown,
    write_row_mrv_stop_gate,
)


def _sample_checklist() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "check_name": "treasury_receipt_account_identification",
                "status": "complete",
                "required_for_default": True,
                "metric_value": "19-X-5713-5 / main_account_rollup",
            },
            {
                "check_name": "payer_scope_and_exclusions",
                "status": "complete",
                "required_for_default": True,
                "metric_name": "scope_control",
                "metric_value": "mrv_primary_under_review; secondary_visa_nondefault; iv_aos_exclusion_loaded",
            },
            {
                "check_name": "cash_treatment_and_retained_account",
                "status": "partial",
                "required_for_default": True,
                "metric_value": "B_cbsp_receipt_account_public_annual",
                "next_evidence_needed": "find stronger cash-treatment evidence",
            },
            {
                "check_name": "annual_reconciliation",
                "status": "complete",
                "required_for_default": True,
                "metric_name": "annual_alignment",
                "metric_value": "annual_mrv_bridge_matches_treasury_line",
            },
            {
                "check_name": "legal_remitter_or_debited_account",
                "status": "missing",
                "required_for_default": True,
                "metric_name": "blocking_condition",
                "metric_value": "no_public_legal_remitter_or_debited_account_proof_for_mrv",
                "next_evidence_needed": "find public remitter or debited-account proof",
            },
            {
                "check_name": "observed_quarterly_cash_timing",
                "status": "missing",
                "required_for_default": True,
                "metric_name": "timing_basis",
                "metric_value": "monthly_niv_issuance_share_proxy",
                "next_evidence_needed": "find public quarterly cash timing",
            },
        ]
    )


def _sample_source_map() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_family_key": "treasury_state_account_mapping",
                "current_repo_stance": "loaded_account_family_support",
                "notes": "loaded",
            },
            {
                "source_family_key": "cash_treatment_and_retention",
                "current_repo_stance": "partial_retained_account_evidence",
                "notes": "find stronger public cash-treatment evidence",
            },
            {
                "source_family_key": "legal_remitter_or_debited_account_proof",
                "current_repo_stance": "no_public_remitter_or_debited_account_source_loaded",
                "notes": "find public remitter or debited-account proof",
            },
            {
                "source_family_key": "observed_quarterly_cash_timing_or_remittance_schedule",
                "current_repo_stance": "activity_proxy_only",
                "notes": "find public quarterly cash timing",
            },
        ]
    )


def test_build_row_mrv_stop_gate_keeps_nondefault_boundary() -> None:
    gate = build_row_mrv_stop_gate(
        row_mrv_promotion_checklist=_sample_checklist(),
        row_mrv_source_map=_sample_source_map(),
    )

    remitter = gate.loc[gate["check_name"].eq("legal_remitter_or_debited_account_source")].iloc[0]
    summary = gate.loc[gate["row_type"].eq("summary")].iloc[0]

    assert remitter["status"] == "fail"
    assert summary["status"] == "stop_at_mrv_nondefault_pilot"
    assert "partial_default_blockers=1" in str(summary["metric_value"])
    assert "missing_required_checks=2" in str(summary["metric_value"])


def test_build_row_mrv_stop_gate_respects_all_required_checklist_rows() -> None:
    checklist = _sample_checklist().copy()
    checklist.loc[checklist["check_name"].eq("annual_reconciliation"), "status"] = "missing"

    gate = build_row_mrv_stop_gate(
        row_mrv_promotion_checklist=checklist,
        row_mrv_source_map=_sample_source_map(),
    )

    annual = gate.loc[gate["check_name"].eq("annual_reconciliation_loaded")].iloc[0]
    summary = gate.loc[gate["row_type"].eq("summary")].iloc[0]
    assert annual["status"] == "fail"
    assert bool(summary["passes_for_default"]) is False
    assert "missing_required_checks=3" in str(summary["metric_value"])


def test_write_row_mrv_stop_gate_outputs(tmp_path: Path) -> None:
    csv_path = tmp_path / "row_mrv_stop_gate.csv"
    markdown_path = tmp_path / "row_mrv_stop_gate.md"

    _, _, gate = write_row_mrv_stop_gate(
        csv_path=csv_path,
        markdown_path=markdown_path,
        row_mrv_promotion_checklist=_sample_checklist(),
        row_mrv_source_map=_sample_source_map(),
    )

    assert csv_path.exists()
    assert markdown_path.exists()
    assert len(pd.read_csv(csv_path)) == len(gate)
    markdown = render_row_mrv_stop_gate_markdown(gate)
    assert "ROW MRV Stop Gate" in markdown
    assert "stop_at_mrv_nondefault_pilot" in markdown
