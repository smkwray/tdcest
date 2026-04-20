from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from tdc_estimator.ncua_call_report import (
    build_ncua_credit_union_deposit_bridge,
    extract_ncua_quarterly_bridge_row,
    write_ncua_credit_union_deposit_bridge,
)


def _write_test_zip(path: Path, *, cycle_date: str = "12/31/2025 0:00:00") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fs220 = f"""CU_NUMBER,CYCLE_DATE,ACCT_013,ACCT_018
1,{cycle_date},900000,1000000
2,{cycle_date},1800000,2000000
3,{cycle_date},45000,50000
"""
    foicu = """CU_NUMBER,CU_TYPE
1,1
2,2
3,3
"""
    with ZipFile(path, "w") as zf:
        zf.writestr("FS220.txt", fs220)
        zf.writestr("FOICU.txt", foicu)


def test_extract_ncua_quarterly_bridge_row_aggregates_credit_union_totals(tmp_path: Path) -> None:
    zip_path = tmp_path / "call-report-data-2025-12.zip"
    _write_test_zip(zip_path)

    row = extract_ncua_quarterly_bridge_row(zip_path)

    assert row.date == pd.Timestamp("2025-12-31")
    assert round(row.total_credit_union_shares_and_deposits_mil, 3) == 3.05
    assert round(row.federally_insured_credit_union_shares_and_deposits_mil, 3) == 3.0
    assert round(row.nonfederally_insured_credit_union_shares_and_deposits_mil, 3) == 0.05
    assert round(row.federally_insured_credit_union_member_shares_mil, 3) == 2.7
    assert round(row.federally_insured_credit_union_implied_nonmember_deposits_mil, 3) == 0.3
    assert row.federally_insured_credit_union_count == 2
    assert row.nonfederally_insured_credit_union_count == 1


def test_write_ncua_credit_union_deposit_bridge_writes_detail_and_support(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    _write_test_zip(cache_dir / "call-report-data-2030-12.zip", cycle_date="12/31/2025 0:00:00")

    detail_path = tmp_path / "ncua__credit_union_deposit_bridge.csv"
    support_path = tmp_path / "support__credit_union_deposits.csv"
    out_path, support_out_path, frame = write_ncua_credit_union_deposit_bridge(
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
    assert round(float(support.loc[0, "value"]), 3) == 3.0


def test_build_ncua_credit_union_deposit_bridge_deduplicates_quarters(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    _write_test_zip(cache_dir / "call-report-data-2030-12.zip", cycle_date="12/31/2025 0:00:00")
    _write_test_zip(cache_dir / "call-report-data-2030-09.zip", cycle_date="9/30/2025 0:00:00")

    frame = build_ncua_credit_union_deposit_bridge(cache_dir=cache_dir, start_year=2030, end_year=2030)

    assert list(pd.to_datetime(frame["date"]).dt.date.astype(str)) == ["2025-09-30", "2025-12-31"]
