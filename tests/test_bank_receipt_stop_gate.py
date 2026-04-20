from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.bank_receipt_stop_gate import (
    build_bank_receipt_stop_gate,
    render_bank_receipt_stop_gate_markdown,
    write_bank_receipt_stop_gate,
)


def _sample_readiness() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "check_name": "perimeter_contamination",
                "status": "pass",
                "metric_name": "bridge_basis",
                "metric_value": "table51_bank_minor_industry_bridge",
                "details": "Perimeter loaded.",
            },
            {
                "check_name": "stale_share_rule",
                "status": "fail",
                "metric_name": "stale_share_years",
                "metric_value": "4",
                "details": "Share too stale.",
            },
            {
                "check_name": "estimator_integration_overlap",
                "status": "warn",
                "metric_name": "latest_overlap",
                "metric_value": "bridge_latest=2026-03-31 estimator_latest=2025-12-31",
                "details": "Overlap warning.",
            },
            {
                "check_name": "no_double_count_and_sign",
                "status": "pass",
                "metric_name": "integration_sign_status",
                "metric_value": "isolated_positive_candidate",
                "details": "Sign ok.",
            },
        ]
    )


def _sample_historical() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "quarter_end": "2024-12-31",
                "share_age_eligible_for_default": True,
            },
            {
                "quarter_end": "2026-03-31",
                "share_age_eligible_for_default": False,
            },
        ]
    )


def _sample_source_map() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_family_key": "fresher_public_irs_bank_minor_shares",
                "current_repo_stance": "missing_fresher_public_share_history",
                "notes": "Need fresher public IRS bank-minor shares.",
            }
        ]
    )


def test_build_bank_receipt_stop_gate_keeps_historical_default_current_nondefault() -> None:
    gate = build_bank_receipt_stop_gate(
        bank_receipt_default_readiness=_sample_readiness(),
        bank_receipt_historical_promotion=_sample_historical(),
        bank_receipt_source_map=_sample_source_map(),
    )

    stale = gate.loc[gate["check_name"].eq("fresher_public_share_loaded")].iloc[0]
    summary = gate.loc[gate["row_type"].eq("summary")].iloc[0]

    assert stale["status"] == "fail"
    assert summary["status"] == "historical_default_only_current_nondefault"


def test_build_bank_receipt_stop_gate_blocks_current_default_when_overlap_warns() -> None:
    readiness = _sample_readiness().copy()
    readiness.loc[readiness["check_name"].eq("stale_share_rule"), "status"] = "pass"
    readiness.loc[readiness["check_name"].eq("stale_share_rule"), "metric_value"] = "0"

    gate = build_bank_receipt_stop_gate(
        bank_receipt_default_readiness=readiness,
        bank_receipt_historical_promotion=_sample_historical(),
        bank_receipt_source_map=_sample_source_map(),
    )

    summary = gate.loc[gate["row_type"].eq("summary")].iloc[0]
    assert summary["status"] == "current_nondefault_until_overlap_alignment"
    assert bool(summary["passes_for_current_default"]) is False
    assert summary["blocking_issue_type"] == "integration_overlap_boundary"


def test_write_bank_receipt_stop_gate_outputs(tmp_path: Path) -> None:
    csv_path = tmp_path / "bank_receipt_stop_gate.csv"
    markdown_path = tmp_path / "bank_receipt_stop_gate.md"

    _, _, gate = write_bank_receipt_stop_gate(
        csv_path=csv_path,
        markdown_path=markdown_path,
        bank_receipt_default_readiness=_sample_readiness(),
        bank_receipt_historical_promotion=_sample_historical(),
        bank_receipt_source_map=_sample_source_map(),
    )

    assert csv_path.exists()
    assert markdown_path.exists()
    assert len(pd.read_csv(csv_path)) == len(gate)
    markdown = render_bank_receipt_stop_gate_markdown(gate)
    assert "Bank Receipt Stop Gate" in markdown
    assert "historical_default_only_current_nondefault" in markdown
