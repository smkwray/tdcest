from __future__ import annotations

from pathlib import Path

import pandas as pd

from tdc_estimator.fed_coupon import (
    estimate_quarterly_fed_coupon_interest_from_soma_snapshots,
    resolve_wamest_soma_path,
    write_quarterly_fed_coupon_interest_proxy_from_soma_csvs,
    write_quarterly_fed_coupon_interest_proxy_from_soma_csv,
)


def test_estimate_quarterly_fed_coupon_interest_from_soma_snapshots_uses_coupon_schedule_and_latest_snapshot():
    holdings = pd.DataFrame(
        {
            "As Of Date": ["2026-03-11", "2026-03-11", "2026-06-10", "2026-06-10"],
            "CUSIP": ["912345AA1", "912345BB2", "912345CC3", "912345DD4"],
            "Security Type": ["Notes/Bonds", "Bills", "Notes/Bonds", "Notes/Bonds"],
            "Maturity Date": ["2026-09-15", "2026-03-26", "2026-09-15", "2026-12-15"],
            "Coupon (%)": [4.0, 0.0, 4.0, 4.0],
            "Par Value": [100.0, 75.0, 120.0, 120.0],
        }
    )

    result = estimate_quarterly_fed_coupon_interest_from_soma_snapshots(holdings)

    assert round(float(result.loc[pd.Timestamp("2026-03-31")]), 6) == 2.0
    assert round(float(result.loc[pd.Timestamp("2026-06-30")]), 6) == 2.4


def test_write_quarterly_fed_coupon_interest_proxy_from_soma_csv_writes_date_value_csv(tmp_path: Path):
    soma_path = tmp_path / "soma.csv"
    out_path = tmp_path / "support__fed_tsy_coupon_interest_proxy.csv"
    pd.DataFrame(
        {
            "As Of Date": ["2026-03-11"],
            "CUSIP": ["912345AA1"],
            "Security Type": ["Notes/Bonds"],
            "Maturity Date": ["2026-09-15"],
            "Coupon (%)": [4.0],
            "Par Value": [100.0],
        }
    ).to_csv(soma_path, index=False)

    written = write_quarterly_fed_coupon_interest_proxy_from_soma_csv(soma_path, out_path)
    frame = pd.read_csv(written)

    assert written == out_path
    assert list(frame.columns) == ["date", "value"]
    assert frame.loc[0, "date"] == "2026-03-31"
    assert round(float(frame.loc[0, "value"]), 6) == 2.0


def test_write_quarterly_fed_coupon_interest_proxy_from_soma_csvs_combines_snapshots(tmp_path: Path):
    q1 = tmp_path / "soma_q1.csv"
    q2 = tmp_path / "soma_q2.csv"
    out_path = tmp_path / "support__fed_tsy_coupon_interest_proxy.csv"
    pd.DataFrame(
        {
            "As Of Date": ["2026-03-11"],
            "CUSIP": ["912345AA1"],
            "Security Type": ["Notes/Bonds"],
            "Maturity Date": ["2026-09-15"],
            "Coupon (%)": [4.0],
            "Par Value": [100.0],
        }
    ).to_csv(q1, index=False)
    pd.DataFrame(
        {
            "As Of Date": ["2026-06-10"],
            "CUSIP": ["912345DD4"],
            "Security Type": ["Notes/Bonds"],
            "Maturity Date": ["2026-12-15"],
            "Coupon (%)": [4.0],
            "Par Value": [120.0],
        }
    ).to_csv(q2, index=False)

    written = write_quarterly_fed_coupon_interest_proxy_from_soma_csvs([q1, q2], out_path)
    frame = pd.read_csv(written)

    assert frame["date"].tolist() == ["2026-03-31", "2026-06-30"]
    assert [round(float(value), 6) for value in frame["value"].tolist()] == [2.0, 2.4]


def test_resolve_wamest_soma_path_prefers_normalized_artifact(tmp_path: Path):
    wamest_root = tmp_path / "wamest"
    soma = wamest_root / "data" / "external" / "normalized" / "soma_holdings_fed.csv"
    soma.parent.mkdir(parents=True, exist_ok=True)
    soma.write_text("As Of Date,CUSIP\n", encoding="utf-8")

    assert resolve_wamest_soma_path(wamest_root) == soma
