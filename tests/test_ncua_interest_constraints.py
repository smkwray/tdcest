from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from tdc_estimator.ncua_interest_constraints import (
    build_ncua_interest_constraints_from_cache,
    normalize_ncua_interest_constraints_zip,
    write_ncua_interest_constraints_from_cache,
)


def _write_ncua_zip(path: Path, *, cycle_date: str = "12/31/2025 0:00:00") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fs220q = f"""CU_NUMBER,CYCLE_DATE,ACCT_NV0001,ACCT_NV0002,ACCT_NV0003,ACCT_NV0004,ACCT_NV0087,ACCT_NV0153,ACCT_NV0154,ACCT_NV0155,ACCT_NV0156,ACCT_NV0157,ACCT_NV0158
1,{cycle_date},100,110,300,330,10,50,60,70,80,90,350
2,{cycle_date},200,220,400,440,20,150,160,170,180,190,850
"""
    with ZipFile(path, "w") as zf:
        zf.writestr("FS220Q.txt", fs220q)


def test_normalize_ncua_interest_constraints_zip_extracts_treasury_level_and_fallback() -> None:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "call-report-data-2025-12.zip"
        _write_ncua_zip(zip_path)

        out = normalize_ncua_interest_constraints_zip(zip_path)

    row = out.iloc[0]
    assert row["date"] == pd.Timestamp("2025-12-31")
    assert row["total_treasuries_amortized_cost"] == 1000.0
    assert row["total_treasuries_fair_value"] == 1130.0
    assert row["total_treasuries_level_proxy"] == 1030.0
    assert round(float(row["investment_short_share_le_1y"]), 6) == round(200 / 1200, 6)
    assert bool(row["fallback_split_accepted"])


def test_build_and_write_ncua_interest_constraints_from_cache(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    _write_ncua_zip(cache / "call-report-data-2025-12.zip", cycle_date="12/31/2025 0:00:00")
    _write_ncua_zip(cache / "call-report-data-2025-09.zip", cycle_date="9/30/2025 0:00:00")

    frame = build_ncua_interest_constraints_from_cache(cache)
    assert list(pd.to_datetime(frame["date"]).dt.date.astype(str)) == ["2025-09-30", "2025-12-31"]

    out_path, written = write_ncua_interest_constraints_from_cache(
        cache_dir=cache,
        out_path=tmp_path / "ncua_interest_constraints_normalized.csv",
    )
    assert out_path.exists()
    assert len(written) == 2
