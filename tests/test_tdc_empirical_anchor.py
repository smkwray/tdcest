from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tdc_estimator.tdc_empirical_anchor import (
    ANCHOR_COLUMNS,
    build_tdc_empirical_anchor,
    write_tdc_empirical_anchor,
)


CANONICAL = "tdc_tier2_canonical_depository_institution_mmf_rrp_prop_ru_flow"


def _sample_estimates() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"date": "2021-12-31", CANONICAL: None},
            {"date": "2022-03-31", CANONICAL: 100.0},
            {"date": "2022-06-30", CANONICAL: -25.0},
        ]
    )


def _sample_components() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2022-03-31",
                "du_noninterest_outlay_proxy": 80.0,
                "du_receipt_proxy": 20.0,
                "du_coupon_proxy_selected_narrow": 5.0,
                "minus_treasury_operating_cash_tx": 3.0,
                "fed_remit_positive": 2.0,
            },
            {
                "date": "2022-06-30",
                "du_noninterest_outlay_proxy": 40.0,
                "du_receipt_proxy": 70.0,
                "du_coupon_proxy_selected_narrow": 4.0,
                "minus_treasury_operating_cash_tx": -8.0,
                "fed_remit_positive": 1.0,
            },
        ]
    )


def test_build_tdc_empirical_anchor_closes_identity_and_declares_boundaries() -> None:
    anchor, manifest = build_tdc_empirical_anchor(
        estimates=_sample_estimates(),
        components=_sample_components(),
        method_meta={"canonical_tier2_method": CANONICAL, "preferred_method": "tdc_base_bank_only_ru_flow"},
        source_hashes_by_file={"tdc_estimates.csv": "abc123"},
        generated_at_utc="2026-06-06T00:00:00+00:00",
        tdcest_commit_or_version="test-version",
    )

    assert list(anchor.columns) == ANCHOR_COLUMNS
    assert anchor["quarter"].tolist() == ["2022-Q1", "2022-Q2"]
    assert manifest["row_count"] == 2
    assert manifest["quarter_start"] == "2022-Q1"
    assert manifest["quarter_end"] == "2022-Q2"
    assert manifest["source_hashes_by_file"] == {"tdc_estimates.csv": "abc123"}
    assert manifest["claim_flags"]["historical_empirical_accounting_decomposition"] is True
    assert manifest["claim_flags"]["public_launch_ready"] is False
    assert manifest["claim_flags"]["secondary_trades_measured_claim_allowed"] is False

    channel_total = (
        anchor["tdc_fiscal_flow"]
        + anchor["tdc_debt_service"]
        + anchor["tdc_auction_absorption_primary_proxy"]
        + anchor["tdc_secondary_and_reconciliation_residual"]
        + anchor["tdc_other_named"]
    )
    assert (anchor["tdc_change"] - channel_total).abs().max() == 0.0
    assert ((anchor["closing_tdc_level"] - anchor["opening_tdc_level"]) - anchor["tdc_change"]).abs().max() == 0.0
    assert set(anchor["auction_absorption_measurement_status"]) == {"primary_allocation_proxy"}
    assert set(anchor["secondary_trades_measurement_status"]) == {
        "residual_unidentified_or_bounded_residual"
    }
    assert "not source-observed stock levels" in anchor.iloc[0]["known_boundaries"]


def test_write_tdc_empirical_anchor_outputs_csv_and_manifest(tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    processed.mkdir()
    _sample_estimates().to_csv(processed / "tdc_estimates.csv", index=False)
    _sample_components().to_csv(processed / "tdc_components.csv", index=False)
    (processed / "method_meta.json").write_text(
        json.dumps({"canonical_tier2_method": CANONICAL}),
        encoding="utf-8",
    )

    csv_path, manifest_path, anchor, manifest = write_tdc_empirical_anchor(
        processed_dir=processed,
        generated_at_utc="2026-06-06T00:00:00+00:00",
    )

    assert csv_path == processed / "tdc_empirical_anchor.csv"
    assert manifest_path == processed / "tdc_empirical_anchor_manifest.json"
    written = pd.read_csv(csv_path)
    written_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(written) == len(anchor) == written_manifest["row_count"] == manifest["row_count"]
    assert set(written_manifest["source_hashes_by_file"]) == {
        "tdc_estimates.csv",
        "tdc_components.csv",
        "method_meta.json",
    }
