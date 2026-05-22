from __future__ import annotations

import io
import re
from pathlib import Path
from zipfile import ZipFile

import pandas as pd


NCUA_ZIP_PATTERN = re.compile(r"call-report-data-(\d{4})-(\d{2})\.zip$")

TREASURY_COLUMNS = {
    "treasury_htm_amortized_cost": "ACCT_NV0001",
    "treasury_htm_fair_value": "ACCT_NV0002",
    "treasury_afs_amortized_cost": "ACCT_NV0003",
    "treasury_afs_fair_value": "ACCT_NV0004",
    "treasury_trading_fair_value": "ACCT_NV0087",
}

TOTAL_INVESTMENT_MATURITY_COLUMNS = {
    "investment_bucket_le_1y": "ACCT_NV0153",
    "investment_bucket_1_3y": "ACCT_NV0154",
    "investment_bucket_3_5y": "ACCT_NV0155",
    "investment_bucket_5_10y": "ACCT_NV0156",
    "investment_bucket_over_10y": "ACCT_NV0157",
    "investment_ladder_total": "ACCT_NV0158",
}


def _read_zip_csv(zf: ZipFile, member_name: str) -> pd.DataFrame:
    with zf.open(member_name) as fh:
        return pd.read_csv(io.TextIOWrapper(fh, encoding="utf-8", errors="replace"), dtype=str)


def _num(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(0.0, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def _zip_sort_key(path: Path) -> tuple[int, int, str]:
    match = NCUA_ZIP_PATTERN.search(path.name)
    if match is None:
        return (9999, 99, path.name)
    return (int(match.group(1)), int(match.group(2)), path.name)


def normalize_ncua_interest_constraints_zip(path: Path | str) -> pd.DataFrame:
    path = Path(path)
    with ZipFile(path) as zf:
        fs220q = _read_zip_csv(zf, "FS220Q.txt")
    fs220q = fs220q.rename(columns=str.upper)
    if "CYCLE_DATE" not in fs220q.columns:
        raise ValueError(f"NCUA ZIP {path} is missing CYCLE_DATE in FS220Q.")
    date_values = pd.to_datetime(fs220q["CYCLE_DATE"], errors="coerce").dropna()
    if date_values.empty:
        raise ValueError(f"NCUA ZIP {path} has no parsable CYCLE_DATE values in FS220Q.")

    row: dict[str, object] = {
        "date": pd.Timestamp(date_values.iloc[0]).normalize(),
        "source_zip_file": path.name,
        "source_zip_path": str(path),
        "reporter_count": int(len(fs220q)),
    }
    for out_column, source_column in TREASURY_COLUMNS.items():
        row[out_column] = float(_num(fs220q, source_column).sum())
    for out_column, source_column in TOTAL_INVESTMENT_MATURITY_COLUMNS.items():
        row[out_column] = float(_num(fs220q, source_column).sum())

    row["total_treasuries_amortized_cost"] = float(row["treasury_htm_amortized_cost"]) + float(
        row["treasury_afs_amortized_cost"]
    )
    row["total_treasuries_fair_value"] = (
        float(row["treasury_htm_fair_value"])
        + float(row["treasury_afs_fair_value"])
        + float(row["treasury_trading_fair_value"])
    )
    row["total_treasuries_level_proxy"] = float(row["total_treasuries_amortized_cost"]) + float(
        row["treasury_trading_fair_value"]
    )
    ladder_total = float(row["investment_ladder_total"])
    row["investment_short_share_le_1y"] = (
        float(row["investment_bucket_le_1y"]) / ladder_total if ladder_total > 0 else pd.NA
    )
    row["fallback_split_accepted"] = True
    row["fallback_split_basis"] = "ncua_treasury_level_only_wamest_interest_contract_split_fallback"
    return pd.DataFrame([row])


def build_ncua_interest_constraints_from_cache(cache_dir: Path | str) -> pd.DataFrame:
    cache = Path(cache_dir)
    paths = sorted(cache.glob("call-report-data-*.zip"), key=_zip_sort_key)
    frames = [normalize_ncua_interest_constraints_zip(path) for path in paths]
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    return out


def write_ncua_interest_constraints_from_cache(
    *,
    cache_dir: Path | str,
    out_path: Path | str,
) -> tuple[Path, pd.DataFrame]:
    frame = build_ncua_interest_constraints_from_cache(cache_dir)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False)
    return out, frame
