from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tdc_estimator.fdic_savings_institution import (
    build_fdic_savings_institution_deposit_bridge,
    extract_fdic_savings_institution_bridge_row,
    write_fdic_savings_institution_deposit_bridge,
)


def _write_test_snapshot(path: Path, *, repdte: str = "20251231") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": {
            "total": 3,
            "quarter_end": "2025-12-31",
            "source_api_url": "https://api.fdic.gov/banks/financials?filters=BKCLASS:SB",
        },
        "data": [
            {"data": {"BKCLASS": "SB", "REPDTE": repdte, "CERT": 1, "DEP": 200000}},
            {"data": {"BKCLASS": "SI", "REPDTE": repdte, "CERT": 2, "DEP": 300000}},
            {"data": {"BKCLASS": "SL", "REPDTE": repdte, "CERT": 3, "DEP": 50000}},
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_extract_fdic_savings_institution_bridge_row_aggregates_deposits(tmp_path: Path) -> None:
    snapshot = tmp_path / "fdic_financials_savings_institutions_20251231.json"
    _write_test_snapshot(snapshot)

    row = extract_fdic_savings_institution_bridge_row(snapshot)

    assert row.date == pd.Timestamp("2025-12-31")
    assert round(row.total_savings_institution_deposits_mil, 3) == 550.0
    assert round(row.federal_savings_bank_deposits_mil, 3) == 200.0
    assert round(row.state_savings_bank_deposits_mil, 3) == 300.0
    assert round(row.state_savings_and_loan_deposits_mil, 3) == 50.0
    assert row.total_savings_institution_count == 3


def test_write_fdic_savings_institution_deposit_bridge_writes_detail_and_support(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    _write_test_snapshot(cache_dir / "fdic_financials_savings_institutions_20301231.json")

    detail_path = tmp_path / "fdic__savings_institution_deposit_bridge.csv"
    support_path = tmp_path / "support__thrift_deposits.csv"
    out_path, support_out_path, frame = write_fdic_savings_institution_deposit_bridge(
        out_path=detail_path,
        support_out_path=support_path,
        cache_dir=cache_dir,
        start_year=2030,
        end_year=2030,
    )

    assert out_path.exists()
    assert support_out_path.exists()
    assert len(frame) == 1
    support = pd.read_csv(support_out_path)
    assert support.loc[0, "date"] == "2025-12-31"
    assert round(float(support.loc[0, "value"]), 3) == 550.0


def test_build_fdic_savings_institution_deposit_bridge_deduplicates_quarters(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    _write_test_snapshot(cache_dir / "fdic_financials_savings_institutions_20300930.json", repdte="20250930")
    _write_test_snapshot(cache_dir / "fdic_financials_savings_institutions_20301231.json", repdte="20251231")

    frame = build_fdic_savings_institution_deposit_bridge(cache_dir=cache_dir, start_year=2030, end_year=2030)

    assert list(pd.to_datetime(frame["date"]).dt.date.astype(str)) == ["2025-09-30", "2025-12-31"]
