from __future__ import annotations

import pandas as pd

from tdc_estimator.backend_release_check import build_backend_release_check


def test_backend_release_check_marks_backend_ready_when_closeout_checks_pass() -> None:
    consistency = pd.DataFrame(
        [
            {"check_key": "one", "status": "pass"},
            {"check_key": "two", "status": "pass"},
        ]
    )
    closeout = pd.DataFrame(
        [
            {"review_key": "downstream_contract_layer", "release_readiness": "closeout_ready", "binding_boundary": "keep green"},
            {"review_key": "bank_receipt_branch", "release_readiness": "bounded_historical_ready", "binding_boundary": "stale_share_rule"},
            {"review_key": "row_mrv_branch", "release_readiness": "bounded_nondefault_ready", "binding_boundary": "evidence_boundary"},
            {"review_key": "fiscal_shell", "release_readiness": "bounded_diagnostic_ready", "binding_boundary": "receipt_cells_still_partial"},
            {"review_key": "monetary_crosscheck", "release_readiness": "diagnostic_only_stable", "binding_boundary": "stop_at_perimeter_stress_test"},
        ]
    )

    frame = build_backend_release_check(
        downstream_consistency_review=consistency,
        backend_closeout_review=closeout,
    )

    assert not frame.empty
    overall = frame.loc[frame["check_key"].eq("overall_release_recommendation")].iloc[0]
    assert overall["status"] == "pass"
    assert overall["metric_value"] == "backend_bounded_closeout_ready"
