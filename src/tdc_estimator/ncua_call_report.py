from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile

import pandas as pd

from .config import USER_AGENT

QUARTER_MONTHS = (3, 6, 9, 12)
FEDERALLY_INSURED_CU_TYPES = {"1", "2"}
NONFEDERALLY_INSURED_CU_TYPES = {"3"}


@dataclass(frozen=True)
class NCUAQuarterlyBridgeRow:
    date: pd.Timestamp
    source_zip_url: str
    source_zip_file: str
    total_credit_union_shares_and_deposits_mil: float
    federally_insured_credit_union_shares_and_deposits_mil: float
    nonfederally_insured_credit_union_shares_and_deposits_mil: float
    total_credit_union_member_shares_mil: float
    federally_insured_credit_union_member_shares_mil: float
    nonfederally_insured_credit_union_member_shares_mil: float
    total_credit_union_implied_nonmember_deposits_mil: float
    federally_insured_credit_union_implied_nonmember_deposits_mil: float
    nonfederally_insured_credit_union_implied_nonmember_deposits_mil: float
    total_credit_union_count: int
    federally_insured_credit_union_count: int
    nonfederally_insured_credit_union_count: int


def ncua_quarterly_zip_url(*, year: int, month: int) -> str:
    return f"https://ncua.gov/files/publications/analysis/call-report-data-{year}-{month:02d}.zip"


def download_ncua_quarterly_zip(*, year: int, month: int, out_path: Path | str) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = Request(ncua_quarterly_zip_url(year=year, month=month), headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=120) as resp:
        out_path.write_bytes(resp.read())
    return out_path


def _read_zip_csv(zf: ZipFile, member_name: str) -> pd.DataFrame:
    with zf.open(member_name) as fh:
        return pd.read_csv(io.TextIOWrapper(fh, encoding="utf-8", errors="replace"))


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def extract_ncua_quarterly_bridge_row(path: Path | str) -> NCUAQuarterlyBridgeRow:
    path = Path(path)
    with ZipFile(path) as zf:
        fs220 = _read_zip_csv(zf, "FS220.txt")
        foicu = _read_zip_csv(zf, "FOICU.txt")

    fs220 = fs220.rename(columns=str.upper)
    foicu = foicu.rename(columns=str.upper)
    if "CU_NUMBER" not in fs220.columns or "CU_NUMBER" not in foicu.columns:
        raise ValueError(f"NCUA ZIP {path} is missing CU_NUMBER linkage fields.")
    if "ACCT_018" not in fs220.columns or "ACCT_013" not in fs220.columns:
        raise ValueError(f"NCUA ZIP {path} is missing required FS220 share/deposit fields.")
    if "CYCLE_DATE" not in fs220.columns:
        raise ValueError(f"NCUA ZIP {path} is missing CYCLE_DATE in FS220.")
    if "CU_TYPE" not in foicu.columns:
        raise ValueError(f"NCUA ZIP {path} is missing CU_TYPE in FOICU.")

    joined = fs220[["CU_NUMBER", "CYCLE_DATE", "ACCT_013", "ACCT_018"]].merge(
        foicu[["CU_NUMBER", "CU_TYPE"]],
        on="CU_NUMBER",
        how="left",
        validate="one_to_one",
    )
    if joined["CU_TYPE"].isna().any():
        raise ValueError(f"NCUA ZIP {path} could not map every CU_NUMBER to a CU_TYPE.")

    joined["ACCT_013"] = _numeric(joined["ACCT_013"])
    joined["ACCT_018"] = _numeric(joined["ACCT_018"])
    joined["implied_nonmember_deposits"] = joined["ACCT_018"] - joined["ACCT_013"]

    cycle_date = pd.to_datetime(joined["CYCLE_DATE"], errors="coerce").dropna()
    if cycle_date.empty:
        raise ValueError(f"NCUA ZIP {path} has no parsable CYCLE_DATE values.")
    date = pd.Timestamp(cycle_date.iloc[0]).normalize()

    def _aggregate(mask: pd.Series) -> tuple[float, float, float, int]:
        subset = joined.loc[mask]
        return (
            float(subset["ACCT_018"].sum()) / 1_000_000.0,
            float(subset["ACCT_013"].sum()) / 1_000_000.0,
            float(subset["implied_nonmember_deposits"].sum()) / 1_000_000.0,
            int(len(subset)),
        )

    total_deposits_mil, total_member_mil, total_nonmember_mil, total_count = _aggregate(
        pd.Series(True, index=joined.index)
    )
    insured_deposits_mil, insured_member_mil, insured_nonmember_mil, insured_count = _aggregate(
        joined["CU_TYPE"].astype(str).isin(FEDERALLY_INSURED_CU_TYPES)
    )
    noninsured_deposits_mil, noninsured_member_mil, noninsured_nonmember_mil, noninsured_count = _aggregate(
        joined["CU_TYPE"].astype(str).isin(NONFEDERALLY_INSURED_CU_TYPES)
    )

    return NCUAQuarterlyBridgeRow(
        date=date,
        source_zip_url=ncua_quarterly_zip_url(year=date.year, month=date.month),
        source_zip_file=path.name,
        total_credit_union_shares_and_deposits_mil=total_deposits_mil,
        federally_insured_credit_union_shares_and_deposits_mil=insured_deposits_mil,
        nonfederally_insured_credit_union_shares_and_deposits_mil=noninsured_deposits_mil,
        total_credit_union_member_shares_mil=total_member_mil,
        federally_insured_credit_union_member_shares_mil=insured_member_mil,
        nonfederally_insured_credit_union_member_shares_mil=noninsured_member_mil,
        total_credit_union_implied_nonmember_deposits_mil=total_nonmember_mil,
        federally_insured_credit_union_implied_nonmember_deposits_mil=insured_nonmember_mil,
        nonfederally_insured_credit_union_implied_nonmember_deposits_mil=noninsured_nonmember_mil,
        total_credit_union_count=total_count,
        federally_insured_credit_union_count=insured_count,
        nonfederally_insured_credit_union_count=noninsured_count,
    )


def build_ncua_credit_union_deposit_bridge(
    *,
    cache_dir: Path | str,
    start_year: int = 2022,
    end_year: int = 2025,
) -> pd.DataFrame:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []

    for year in range(start_year, end_year + 1):
        for month in QUARTER_MONTHS:
            zip_path = cache_dir / f"call-report-data-{year}-{month:02d}.zip"
            if not zip_path.exists():
                try:
                    download_ncua_quarterly_zip(year=year, month=month, out_path=zip_path)
                except HTTPError as exc:
                    if exc.code == 404:
                        continue
                    raise
            row = extract_ncua_quarterly_bridge_row(zip_path)
            rows.append(row.__dict__)

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows).sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    return out


def write_ncua_credit_union_deposit_bridge(
    *,
    out_path: Path | str,
    support_out_path: Path | str,
    cache_dir: Path | str,
    start_year: int = 2022,
    end_year: int = 2025,
) -> tuple[Path, Path, pd.DataFrame]:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    support_out_path = Path(support_out_path)
    support_out_path.parent.mkdir(parents=True, exist_ok=True)

    frame = build_ncua_credit_union_deposit_bridge(
        cache_dir=cache_dir,
        start_year=start_year,
        end_year=end_year,
    )
    frame.to_csv(out_path, index=False)

    support = pd.DataFrame(
        {
            "date": pd.to_datetime(frame["date"]).dt.date.astype(str),
            "value": pd.to_numeric(frame["federally_insured_credit_union_shares_and_deposits_mil"], errors="coerce"),
        }
    )
    support.to_csv(support_out_path, index=False)
    return out_path, support_out_path, frame
