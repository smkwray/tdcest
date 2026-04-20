from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .config import USER_AGENT

FDIC_FINANCIALS_API_BASE = "https://api.fdic.gov/banks/financials"
QUARTER_MONTHS = (3, 6, 9, 12)
SAVINGS_INSTITUTION_BKCLASS = ("SB", "SI", "SL")
BKCLASS_LABELS = {
    "SB": "federal_savings_bank",
    "SI": "state_savings_bank",
    "SL": "state_savings_and_loan",
}


@dataclass(frozen=True)
class FDICSavingsInstitutionQuarterlyRow:
    date: pd.Timestamp
    source_api_url: str
    source_cache_file: str
    total_savings_institution_deposits_mil: float
    federal_savings_bank_deposits_mil: float
    state_savings_bank_deposits_mil: float
    state_savings_and_loan_deposits_mil: float
    total_savings_institution_count: int
    federal_savings_bank_count: int
    state_savings_bank_count: int
    state_savings_and_loan_count: int


def fdic_quarter_end(*, year: int, month: int) -> pd.Timestamp:
    return (pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)).normalize()


def fdic_savings_institution_filter(*, quarter_end: pd.Timestamp) -> str:
    date_token = pd.Timestamp(quarter_end).strftime("%Y%m%d")
    class_filter = " OR ".join(f"BKCLASS:{bkclass}" for bkclass in SAVINGS_INSTITUTION_BKCLASS)
    return f"({class_filter}) AND REPDTE:{date_token}"


def fdic_savings_institution_query_url(
    *,
    quarter_end: pd.Timestamp,
    limit: int = 10000,
    offset: int = 0,
) -> str:
    params = {
        "filters": fdic_savings_institution_filter(quarter_end=quarter_end),
        "fields": "CERT,NAME,BKCLASS,REPDTE,DEP",
        "limit": str(limit),
        "offset": str(offset),
        "format": "json",
    }
    return f"{FDIC_FINANCIALS_API_BASE}?{urlencode(params)}"


def _fetch_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=120) as resp:
        return json.load(resp)


def download_fdic_savings_institution_snapshot(
    *,
    quarter_end: pd.Timestamp,
    out_path: Path | str,
    page_size: int = 10000,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    quarter_end = pd.Timestamp(quarter_end).normalize()

    first_url = fdic_savings_institution_query_url(quarter_end=quarter_end, limit=page_size, offset=0)
    first_payload = _fetch_json(first_url)
    total = int(first_payload.get("meta", {}).get("total", 0))
    data_rows = list(first_payload.get("data", []))

    offset = page_size
    while offset < total:
        page_url = fdic_savings_institution_query_url(quarter_end=quarter_end, limit=page_size, offset=offset)
        payload = _fetch_json(page_url)
        data_rows.extend(payload.get("data", []))
        offset += page_size

    payload_to_cache = {
        "meta": {
            "total": total,
            "filters": fdic_savings_institution_filter(quarter_end=quarter_end),
            "page_size": page_size,
            "quarter_end": quarter_end.strftime("%Y-%m-%d"),
            "source_api_url": first_url,
        },
        "data": data_rows,
    }
    out_path.write_text(json.dumps(payload_to_cache, indent=2), encoding="utf-8")
    return out_path


def extract_fdic_savings_institution_bridge_row(path: Path | str) -> FDICSavingsInstitutionQuarterlyRow:
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    data_rows = payload.get("data", [])
    if not data_rows:
        raise ValueError(f"FDIC snapshot {path} contains no rows.")

    normalized = pd.DataFrame([row.get("data", {}) for row in data_rows])
    if normalized.empty:
        raise ValueError(f"FDIC snapshot {path} has no nested data rows.")
    required = {"BKCLASS", "REPDTE", "DEP"}
    missing = required.difference(normalized.columns)
    if missing:
        raise ValueError(f"FDIC snapshot {path} is missing required columns: {sorted(missing)}")

    normalized["DEP"] = pd.to_numeric(normalized["DEP"], errors="coerce").fillna(0.0)
    normalized["REPDTE"] = pd.to_datetime(normalized["REPDTE"], format="%Y%m%d", errors="coerce")
    if normalized["REPDTE"].isna().all():
        raise ValueError(f"FDIC snapshot {path} has no parsable REPDTE values.")
    date = pd.Timestamp(normalized["REPDTE"].dropna().iloc[0]).normalize()

    def _aggregate(bkclass: str | None = None) -> tuple[float, int]:
        subset = normalized if bkclass is None else normalized.loc[normalized["BKCLASS"].astype(str) == bkclass]
        return float(subset["DEP"].sum()) / 1000.0, int(len(subset))

    total_deposits_mil, total_count = _aggregate()
    sb_deposits_mil, sb_count = _aggregate("SB")
    si_deposits_mil, si_count = _aggregate("SI")
    sl_deposits_mil, sl_count = _aggregate("SL")

    return FDICSavingsInstitutionQuarterlyRow(
        date=date,
        source_api_url=str(payload.get("meta", {}).get("source_api_url") or fdic_savings_institution_query_url(quarter_end=date)),
        source_cache_file=path.name,
        total_savings_institution_deposits_mil=total_deposits_mil,
        federal_savings_bank_deposits_mil=sb_deposits_mil,
        state_savings_bank_deposits_mil=si_deposits_mil,
        state_savings_and_loan_deposits_mil=sl_deposits_mil,
        total_savings_institution_count=total_count,
        federal_savings_bank_count=sb_count,
        state_savings_bank_count=si_count,
        state_savings_and_loan_count=sl_count,
    )


def build_fdic_savings_institution_deposit_bridge(
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
            quarter_end = fdic_quarter_end(year=year, month=month)
            cache_path = cache_dir / f"fdic_financials_savings_institutions_{quarter_end.strftime('%Y%m%d')}.json"
            if not cache_path.exists():
                download_fdic_savings_institution_snapshot(quarter_end=quarter_end, out_path=cache_path)
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            if not payload.get("data"):
                continue
            row = extract_fdic_savings_institution_bridge_row(cache_path)
            rows.append(row.__dict__)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)


def write_fdic_savings_institution_deposit_bridge(
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

    frame = build_fdic_savings_institution_deposit_bridge(
        cache_dir=cache_dir,
        start_year=start_year,
        end_year=end_year,
    )
    frame.to_csv(out_path, index=False)

    support = pd.DataFrame(
        {
            "date": pd.to_datetime(frame["date"]).dt.date.astype(str),
            "value": pd.to_numeric(frame["total_savings_institution_deposits_mil"], errors="coerce"),
        }
    )
    support.to_csv(support_out_path, index=False)
    return out_path, support_out_path, frame
